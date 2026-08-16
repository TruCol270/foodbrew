"""Workflow D — the database editor's writes, and reset to baseline.

Two truth labels down two paths (plan decision #7). A direct edit here writes
`user_provided`, because §5.4 makes `confirmed` mean "verified against a named
source" and a web form is not one. `set_confirmed` exists for exactly one
caller — an approved proposal, which carries the citation that goes in the
paired `*_source` column.

Column names cannot be bound as SQL parameters, so every name that reaches an
f-string comes from the allowlists below and every value is bound (decision
#16). The same allowlists are the type map `store/proposals.py` parses a
proposal's TEXT value with, so the two writers cannot disagree about what
`ph_min` is.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from typing import Any

from foodbrew.engine import ValidationRejection, structural
from foodbrew.engine.types import TruthLabel
from foodbrew.seedload.loader import load_seed
from foodbrew.store import audit
from foodbrew.store.foods import CUSTOM_SOURCE
from foodbrew.store.rowmap import enzyme_to_row, food_to_row

EDITABLE_TABLES = ("enzyme", "food")

#: Tracked columns: writing one writes its `_status` and `_source` too.
TRACKED_FIELDS: Mapping[str, Mapping[str, type]] = {
    "enzyme": {
        "ph_min": float, "ph_max": float, "ph_opt_low": float, "ph_opt_high": float,
        "ph_shelf_stable_min": float, "temp_min_c": float, "temp_max_c": float,
        "temp_opt_c": float, "dose_min": float, "dose_max": float,
        "dose_evidence_threshold": float, "is_gras": bool,
    },
    "food": {"ph": float, "water_content_pct": float, "typical_load_value": float},
}

#: Plain columns: free text the founder owns, carrying no truth label of its own.
PLAIN_FIELDS: Mapping[str, Mapping[str, type]] = {
    "enzyme": {
        "notes": str, "supplier_note": str, "dose_unit": str,
        "dose_benchmark_note": str, "food_grade_note": str, "cost_tier": str,
    },
    "food": {"notes": str, "category": str, "typical_load_unit": str},
}

#: JSON list columns over closed enums (plan decision #4). Separate from
#: TRACKED_FIELDS because they carry no _status/_source pair — their provenance
#: is the tier inside the value — and separate from PLAIN_FIELDS because a free
#: string is not a legal value for either of them.
STRUCTURED_FIELDS: Mapping[str, Mapping[str, str]] = {
    "enzyme": {"degrades_structural_json": "enzyme_entries"},
    "food": {"structural_json": "food_classes"},
}


def structured_kind(table: str, field: str) -> str | None:
    return STRUCTURED_FIELDS.get(table, {}).get(field)


def coerce_structured(table: str, field: str, raw) -> str:
    """Validate through the engine and return the JSON text to store."""
    kind = structured_kind(table, field)
    if kind is None:
        raise ValidationRejection(f"'{field}' is not a structured field on {table}.")
    try:
        if kind == "enzyme_entries":
            return json.dumps(list(structural.parse_enzyme_entries(raw)))
        return json.dumps(list(structural.parse_food_classes(raw)))
    except structural.StructuralError as exc:
        raise ValidationRejection(f"'{field}': {exc}") from exc


def update_structured(
    conn: sqlite3.Connection, table: str, record_id: str, field: str, raw
) -> None:
    """A founder edit to a structured field. Audited like every other edit."""
    check_table(table)
    payload = coerce_structured(table, field, raw)
    before = conn.execute(
        f"SELECT {field} FROM {table} WHERE id = ?", (record_id,)
    ).fetchone()
    if before is None:
        raise ValidationRejection(f"No {table} '{record_id}'.")

    conn.execute(f"UPDATE {table} SET {field} = ? WHERE id = ?", (payload, record_id))
    audit.record(
        conn, action="edit", entity=f"{table}:{record_id}",
        before={field: before[field]}, after={field: payload},
    )
    conn.commit()


def check_table(table: str) -> None:
    if table not in EDITABLE_TABLES:
        raise ValidationRejection(f"'{table}' is not an editable table.")


def field_type(table: str, field: str) -> type:
    check_table(table)
    for group in (TRACKED_FIELDS, PLAIN_FIELDS):
        if field in group[table]:
            return group[table][field]
    raise ValidationRejection(f"'{field}' cannot be edited on a {table} record.")


def coerce(table: str, field: str, raw: Any) -> Any:
    """Parse an incoming value to the column's type, or refuse it in plain English."""
    expected = field_type(table, field)
    if expected is bool:
        if isinstance(raw, str):
            lowered = raw.strip().lower()
            if lowered in {"true", "yes", "1"}:
                return True
            if lowered in {"false", "no", "0"}:
                return False
            raise ValidationRejection(f"'{field}': enter yes or no.")
        return bool(raw)
    if expected is float:
        try:
            return float(raw)
        except (TypeError, ValueError) as exc:
            raise ValidationRejection(f"'{field}': enter a number.") from exc
    # A plain text column is NOT NULL DEFAULT '', and clearing a note through
    # the editor sends null. `str(None)` would put the four characters "None"
    # in the column and the founder would read it back as her own note.
    return "" if raw is None else str(raw)


def _row_snapshot(conn: sqlite3.Connection, table: str, record_id: str) -> dict:
    row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (record_id,)).fetchone()
    if row is None:
        raise ValidationRejection(f"No {table} '{record_id}'.")
    return dict(row)


def _replace(conn: sqlite3.Connection, table: str, row: Mapping) -> None:
    columns = ", ".join(f'"{c}"' for c in row)
    placeholders = ", ".join("?" for _ in row)
    conn.execute(
        f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})",
        tuple(row.values()),
    )


def update(
    conn: sqlite3.Connection, table: str, record_id: str, fields: Mapping[str, Any]
) -> None:
    """A founder edit. Every value written here is `user_provided` (decision #7)."""
    check_table(table)
    before = _row_snapshot(conn, table, record_id)

    assignments: list[str] = []
    values: list[Any] = []
    for field, raw in fields.items():
        if field in TRACKED_FIELDS[table]:
            assignments += [f'"{field}" = ?', f'"{field}_status" = ?', f'"{field}_source" = ?']
            if raw is None:
                values += [None, TruthLabel.UNCONFIRMED.value, ""]
            else:
                parsed = coerce(table, field, raw)
                values += [
                    int(parsed) if isinstance(parsed, bool) else parsed,
                    TruthLabel.USER_PROVIDED.value,
                    CUSTOM_SOURCE,
                ]
        else:
            # Coerce first: `coerce` is what rejects a field outside the
            # allowlist, and it has to raise before anything is appended.
            value = coerce(table, field, raw)
            assignments.append(f'"{field}" = ?')
            values.append(value)

    if not assignments:
        raise ValidationRejection("Nothing to change.")

    conn.execute(
        f"UPDATE {table} SET {', '.join(assignments)} WHERE id = ?",
        (*values, record_id),
    )
    audit.record(
        conn, action="update", entity=f"{table}:{record_id}",
        before=before, after=_row_snapshot(conn, table, record_id),
    )
    conn.commit()


def set_confirmed(
    conn: sqlite3.Connection, table: str, record_id: str, field: str, raw: Any, source: str
) -> None:
    """The only path to `confirmed` — an approved proposal with a citation (§2.3, §5.4)."""
    # Explicit rather than relying on TRACKED_FIELDS.get(table, {}) to fall
    # through empty for a bad table — that happened to reject too, but only
    # as a side effect, and would stop doing so silently if TRACKED_FIELDS
    # ever gained a key for something that isn't an editable table.
    check_table(table)
    if field not in TRACKED_FIELDS.get(table, {}):
        raise ValidationRejection(f"'{field}' does not carry a source, so it cannot be confirmed.")
    if not source.strip():
        raise ValidationRejection("A confirmed value needs a source citation.")

    before = _row_snapshot(conn, table, record_id)
    parsed = coerce(table, field, raw)
    conn.execute(
        f'UPDATE {table} SET "{field}" = ?, "{field}_status" = ?, "{field}_source" = ?'
        " WHERE id = ?",
        (
            int(parsed) if isinstance(parsed, bool) else parsed,
            TruthLabel.CONFIRMED.value,
            source,
            record_id,
        ),
    )
    audit.record(
        conn, action="confirm", entity=f"{table}:{record_id}",
        before=before, after=_row_snapshot(conn, table, record_id),
    )


def reset_record(conn: sqlite3.Connection, table: str, record_id: str) -> None:
    """Workflow D's reset-to-baseline, one record at a time (plan decision #8)."""
    check_table(table)
    seed = load_seed()
    catalogue = seed.enzymes if table == "enzyme" else seed.foods
    record = catalogue.get(record_id)
    if record is None:
        raise ValidationRejection(
            f"'{record_id}' is not in the shipped catalogue, so it has no baseline to "
            f"go back to. Edit the values you want to change instead."
        )

    before = _row_snapshot(conn, table, record_id)
    row = enzyme_to_row(record) if table == "enzyme" else food_to_row(record)
    _replace(conn, table, row)
    audit.record(
        conn, action="reset", entity=f"{table}:{record_id}", before=before, after=dict(row)
    )
    conn.commit()


def reset_all(conn: sqlite3.Connection) -> None:
    """Destructive: discards every edit to every enzyme and food row.

    Substrates and GI regions are not editable and are left alone; the boot-time
    `create_database` path is still what refreshes those.
    """
    seed = load_seed()
    for enzyme in seed.enzymes.values():
        _replace(conn, "enzyme", enzyme_to_row(enzyme))
    for food in seed.foods.values():
        _replace(conn, "food", food_to_row(food))
    audit.record(conn, action="reset_all", entity="reference")
    conn.commit()
