"""Create the SQLite database and populate reference tables from seed JSON."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from foodbrew.seedload.loader import Seed, load_seed

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

EXPECTED_TABLES = frozenset({
    "substrate", "enzyme", "food", "gi_region", "recipe", "recipe_ingredient",
    "formulation", "evaluation", "rule_finding", "variant_suggestion", "trial",
    "trial_batch", "trial_observation", "trial_symptom_entry", "proposal", "audit_event",
})


def _tracked_cols(prefix: str, tracked) -> dict:
    value = tracked.value
    if isinstance(value, bool):
        value = int(value)
    return {
        prefix: value,
        f"{prefix}_status": tracked.status.value,
        f"{prefix}_source": tracked.source,
    }


def _insert(conn: sqlite3.Connection, table: str, row: dict) -> None:
    cols = ", ".join(f'"{c}"' for c in row)
    placeholders = ", ".join("?" for _ in row)
    conn.execute(
        f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})",
        tuple(row.values()),
    )


def load_reference_data(conn: sqlite3.Connection, seed: Seed) -> None:
    for s in seed.substrates.values():
        _insert(conn, "substrate", {
            "id": s.id, "name": s.name,
            "native_human_enzyme": int(s.native_human_enzyme),
            "is_prebiotic": int(s.is_prebiotic),
            "no_commercial_enzyme": int(s.no_commercial_enzyme),
            "notes": s.notes,
        })

    for r in seed.gi_regions:
        _insert(conn, "gi_region", {
            "id": r.id, "name": r.name, "ph_low": r.ph_low, "ph_high": r.ph_high,
            "order": r.order, "dormant": int(r.dormant), "transit_note": r.transit_note,
        })

    for e in seed.enzymes.values():
        row = {
            "id": e.id, "name": e.name, "aliases_json": json.dumps(list(e.aliases)),
            "substrate_id": e.substrate_id, "source_type": e.source_type,
            "priority": e.priority, "deadline": e.deadline.value,
            "site_of_action": e.site_of_action, "dose_unit": e.dose_unit,
            "dose_benchmark_note": e.dose_benchmark_note,
            "is_protease": int(e.is_protease),
            "is_natural_source": int(e.is_natural_source),
            "food_grade_note": e.food_grade_note,
            "heat_labile_note": e.heat_labile_note,
            "degrades_structural_json": json.dumps([
                {"structural_class": x.structural_class.value, "tier": x.tier.value}
                for x in e.degrades_structural
            ]),
            "cost_tier": e.cost_tier, "supplier_note": e.supplier_note, "notes": e.notes,
        }
        for prefix in (
            "ph_min", "ph_max", "ph_opt_low", "ph_opt_high", "ph_shelf_stable_min",
            "temp_min_c", "temp_max_c", "temp_opt_c",
            "dose_min", "dose_max", "dose_evidence_threshold", "is_gras",
        ):
            row.update(_tracked_cols(prefix, getattr(e, prefix)))
        _insert(conn, "enzyme", row)

    for f in seed.foods.values():
        row = {
            "id": f.id, "name": f.name, "category": f.category,
            "is_recipe_ingredient": int(f.is_recipe_ingredient),
            "is_trigger_food": int(f.is_trigger_food),
            "is_application_food": int(f.is_application_food),
            "contains_substrate_ids_json": json.dumps(list(f.contains_substrate_ids)),
            "typical_load_unit": f.typical_load_unit,
            "contains_protease": int(f.contains_protease),
            "is_heat_processed": int(f.is_heat_processed),
            "structural_json": json.dumps([s.value for s in f.structural]),
            "notes": f.notes,
        }
        for prefix in ("ph", "water_content_pct", "typical_load_value"):
            row.update(_tracked_cols(prefix, getattr(f, prefix)))
        _insert(conn, "food", row)


def create_database(path: Path | str, seed: Seed | None = None) -> Path:
    """Create (or refresh) the database at `path`. Idempotent."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        load_reference_data(conn, seed or load_seed())
        conn.commit()
    finally:
        conn.close()
    return path


def ensure_database(path: Path | str, seed: Seed | None = None) -> Path:
    """Create the database on first boot; otherwise leave its contents alone.

    `create_database` refreshes reference rows with INSERT OR REPLACE, which is
    right for a first boot and right for M3's reset-to-baseline button, and
    wrong for a restart: from M3 the founder's edits live in those same rows.
    """
    path = Path(path)
    if not path.exists():
        return create_database(path, seed)

    conn = sqlite3.connect(path)
    try:
        present = {
            r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        conn.close()
    missing = EXPECTED_TABLES - present
    if missing:
        raise ValueError(
            f"{path} exists but its schema is missing: {', '.join(sorted(missing))}"
        )
    return path
