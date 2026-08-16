"""Food catalogue reads, and custom-food creation.

Spec §5.4 makes `confirmed` mean "verified against a named source", which a web
form is not. Custom foods are therefore stored `user_provided` by construction:
the caller supplies bare values and this module attaches the label. There is no
parameter by which a client chooses one (plan decision #9).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence

from foodbrew.engine import ValidationRejection
from foodbrew.engine.allergens import parse as parse_allergens
from foodbrew.engine.types import Food, StructuralClass, TruthLabel
from foodbrew.store.ids import new_id
from foodbrew.store.rowmap import food_from_row

#: What the founder typing a number into the database editor means.
CUSTOM_SOURCE = "entered by founder"

_ROLE_COLUMNS = {
    "recipe_ingredient": "is_recipe_ingredient",
    "trigger": "is_trigger_food",
    "application": "is_application_food",
}


def list_by_role(conn: sqlite3.Connection, role: str | None) -> tuple[Food, ...]:
    if role is None:
        rows = conn.execute("SELECT * FROM food ORDER BY name")
    else:
        column = _ROLE_COLUMNS.get(role)
        if column is None:
            raise ValidationRejection(f"Unknown role '{role}'.")
        rows = conn.execute(f"SELECT * FROM food WHERE {column} = 1 ORDER BY name")
    return tuple(food_from_row(r) for r in rows)


def get(conn: sqlite3.Connection, food_id: str) -> Food | None:
    row = conn.execute("SELECT * FROM food WHERE id = ?", (food_id,)).fetchone()
    return food_from_row(row) if row else None


def _tracked_columns(prefix: str, value) -> dict:
    """A supplied value is user_provided; an omitted one stays unconfirmed."""
    if value is None:
        return {
            prefix: None,
            f"{prefix}_status": TruthLabel.UNCONFIRMED.value,
            f"{prefix}_source": "",
        }
    return {
        prefix: float(value),
        f"{prefix}_status": TruthLabel.USER_PROVIDED.value,
        f"{prefix}_source": CUSTOM_SOURCE,
    }


def create_custom(
    conn: sqlite3.Connection,
    *,
    name: str,
    category: str,
    is_recipe_ingredient: bool,
    is_trigger_food: bool,
    is_application_food: bool,
    ph: float | None,
    water_content_pct: float | None,
    typical_load_value: float | None,
    typical_load_unit: str,
    contains_substrate_ids: Sequence[str],
    structural: Sequence[str],
    allergens: Sequence[str] = (),
    contains_protease: bool,
    is_heat_processed: bool,
    notes: str,
) -> str:
    try:
        parse_allergens(allergens)
    except ValueError as exc:
        raise ValidationRejection(str(exc)) from exc

    if not (is_recipe_ingredient or is_trigger_food or is_application_food):
        raise ValidationRejection(
            "Give this food at least one role: recipe ingredient, trigger food, "
            "or application food."
        )

    known = {r["id"] for r in conn.execute("SELECT id FROM substrate")}
    for substrate_id in contains_substrate_ids:
        if substrate_id not in known:
            raise ValidationRejection(f"Unknown substrate '{substrate_id}'.")
    for entry in structural:
        try:
            StructuralClass(entry)
        except ValueError as exc:
            raise ValidationRejection(f"Unknown structural class '{entry}'.") from exc

    food_id = f"custom_{new_id()}"
    row = {
        "id": food_id, "name": name, "category": category,
        "is_recipe_ingredient": int(is_recipe_ingredient),
        "is_trigger_food": int(is_trigger_food),
        "is_application_food": int(is_application_food),
        "contains_substrate_ids_json": json.dumps(list(contains_substrate_ids)),
        "typical_load_unit": typical_load_unit,
        "contains_protease": int(contains_protease),
        "is_heat_processed": int(is_heat_processed),
        "structural_json": json.dumps(list(structural)),
        "allergens_json": json.dumps(list(allergens)),
        "notes": notes,
        **_tracked_columns("ph", ph),
        **_tracked_columns("water_content_pct", water_content_pct),
        **_tracked_columns("typical_load_value", typical_load_value),
    }
    columns = ", ".join(f'"{c}"' for c in row)
    placeholders = ", ".join("?" for _ in row)
    conn.execute(
        f"INSERT INTO food ({columns}) VALUES ({placeholders})", tuple(row.values())
    )
    conn.commit()
    return food_id
