"""Rows → engine dataclasses. The mirror of seedload/loader.py's JSON path.

The Tracked triple (<field>, <field>_status, <field>_source) written by
db/bootstrap.py is read back here. tests/store/test_rowmap.py asserts the two
readers agree record-for-record; that test is the only thing keeping them from
drifting, so change one and run it.
"""

from __future__ import annotations

import json
import sqlite3

from foodbrew.engine.types import (
    Deadline,
    Enzyme,
    Food,
    GIRegion,
    SeverityTier,
    StructuralClass,
    StructuralEntry,
    Substrate,
    Tracked,
    TruthLabel,
)

#: Enzyme columns stored as a Tracked triple.
ENZYME_TRACKED = (
    "ph_min", "ph_max", "ph_opt_low", "ph_opt_high", "ph_shelf_stable_min",
    "temp_min_c", "temp_max_c", "temp_opt_c",
    "dose_min", "dose_max", "dose_evidence_threshold", "is_gras",
)
#: Food columns stored as a Tracked triple.
FOOD_TRACKED = ("ph", "water_content_pct", "typical_load_value")

#: Tracked columns whose SQLite INTEGER is a boolean, not a number.
_BOOLEAN_TRACKED = frozenset({"is_gras"})


def tracked(row: sqlite3.Row, prefix: str) -> Tracked:
    value = row[prefix]
    if value is not None and prefix in _BOOLEAN_TRACKED:
        value = bool(value)
    return Tracked(
        value=value,
        status=TruthLabel(row[f"{prefix}_status"]),
        source=row[f"{prefix}_source"],
    )


def substrate_from_row(row: sqlite3.Row) -> Substrate:
    return Substrate(
        id=row["id"],
        name=row["name"],
        native_human_enzyme=bool(row["native_human_enzyme"]),
        is_prebiotic=bool(row["is_prebiotic"]),
        no_commercial_enzyme=bool(row["no_commercial_enzyme"]),
        notes=row["notes"],
    )


def gi_region_from_row(row: sqlite3.Row) -> GIRegion:
    return GIRegion(
        id=row["id"],
        name=row["name"],
        ph_low=float(row["ph_low"]),
        ph_high=float(row["ph_high"]),
        order=int(row["order"]),
        dormant=bool(row["dormant"]),
        transit_note=row["transit_note"],
    )


def enzyme_from_row(row: sqlite3.Row) -> Enzyme:
    structural = tuple(
        StructuralEntry(
            structural_class=StructuralClass(entry["structural_class"]),
            tier=SeverityTier(entry["tier"]),
        )
        for entry in json.loads(row["degrades_structural_json"])
    )
    return Enzyme(
        id=row["id"],
        name=row["name"],
        aliases=tuple(json.loads(row["aliases_json"])),
        substrate_id=row["substrate_id"],
        source_type=row["source_type"],
        priority=row["priority"],
        deadline=Deadline(row["deadline"]),
        site_of_action=row["site_of_action"],
        dose_unit=row["dose_unit"],
        dose_benchmark_note=row["dose_benchmark_note"],
        is_protease=bool(row["is_protease"]),
        is_natural_source=bool(row["is_natural_source"]),
        food_grade_note=row["food_grade_note"],
        heat_labile_note=row["heat_labile_note"],
        degrades_structural=structural,
        cost_tier=row["cost_tier"],
        supplier_note=row["supplier_note"],
        notes=row["notes"],
        **{name: tracked(row, name) for name in ENZYME_TRACKED},
    )


def food_from_row(row: sqlite3.Row) -> Food:
    return Food(
        id=row["id"],
        name=row["name"],
        category=row["category"],
        is_recipe_ingredient=bool(row["is_recipe_ingredient"]),
        is_trigger_food=bool(row["is_trigger_food"]),
        is_application_food=bool(row["is_application_food"]),
        contains_substrate_ids=tuple(json.loads(row["contains_substrate_ids_json"])),
        typical_load_unit=row["typical_load_unit"],
        contains_protease=bool(row["contains_protease"]),
        is_heat_processed=bool(row["is_heat_processed"]),
        structural=tuple(StructuralClass(s) for s in json.loads(row["structural_json"])),
        notes=row["notes"],
        **{name: tracked(row, name) for name in FOOD_TRACKED},
    )
