"""Load seed JSON into engine domain objects. Does file I/O — never imported by engine/."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from foodbrew.engine.allergens import parse as parse_allergens
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

#: Repository root — seed/ sits beside src/.
SEED_DIR = Path(__file__).resolve().parents[3] / "seed"


class SeedError(ValueError):
    """Raised when seed JSON is malformed. Loud on purpose."""


@dataclass(frozen=True, slots=True)
class Seed:
    enzymes: Mapping[str, Enzyme]
    foods: Mapping[str, Food]
    substrates: Mapping[str, Substrate]
    gi_regions: tuple[GIRegion, ...]


def _tracked(raw: Any, field_name: str) -> Tracked:
    """Parse a {value,status,source} object. Missing means unconfirmed-with-no-value."""
    if raw is None:
        return Tracked(None, TruthLabel.UNCONFIRMED, "")
    if not isinstance(raw, dict):
        raise SeedError(f"{field_name}: expected an object with value/status/source")
    try:
        status = TruthLabel(raw["status"])
    except KeyError as exc:
        raise SeedError(f"{field_name}: missing 'status'") from exc
    except ValueError as exc:
        raise SeedError(f"{field_name}: '{raw['status']}' is not a truth label") from exc
    return Tracked(value=raw.get("value"), status=status, source=raw.get("source", ""))


def _read(name: str, seed_dir: Path) -> dict:
    path = seed_dir / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SeedError(f"missing seed file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SeedError(f"invalid JSON in {path}: {exc}") from exc


def _parse_structural(raw: list, enzyme_id: str) -> tuple[StructuralEntry, ...]:
    out = []
    for entry in raw or []:
        try:
            out.append(
                StructuralEntry(
                    structural_class=StructuralClass(entry["structural_class"]),
                    tier=SeverityTier(entry["tier"]),
                )
            )
        except (KeyError, ValueError) as exc:
            raise SeedError(f"{enzyme_id}: bad degrades_structural entry {entry!r}") from exc
    return tuple(out)


def load_seed(seed_dir: Path | None = None) -> Seed:
    """Load and validate every seed file. Raises SeedError on any problem."""
    d = seed_dir or SEED_DIR

    substrates = {}
    for r in _read("substrates.json", d)["substrates"]:
        substrates[r["id"]] = Substrate(
            id=r["id"],
            name=r["name"],
            native_human_enzyme=r.get("native_human_enzyme", False),
            is_prebiotic=r.get("is_prebiotic", False),
            no_commercial_enzyme=r.get("no_commercial_enzyme", False),
            notes=r.get("notes", ""),
        )

    regions = []
    for r in _read("gi_model.json", d)["regions"]:
        regions.append(
            GIRegion(
                id=r["id"],
                name=r["name"],
                ph_low=float(r["ph_low"]),
                ph_high=float(r["ph_high"]),
                order=int(r["order"]),
                dormant=r.get("dormant", False),
                transit_note=r.get("transit_note", ""),
            )
        )
    regions.sort(key=lambda x: x.order)

    enzymes = {}
    for r in _read("enzymes.json", d)["enzymes"]:
        eid = r["id"]
        try:
            deadline = Deadline(r["deadline"])
        except ValueError as exc:
            raise SeedError(f"{eid}: '{r['deadline']}' is not a deadline") from exc
        enzymes[eid] = Enzyme(
            id=eid,
            name=r["name"],
            aliases=tuple(r.get("aliases", ())),
            substrate_id=r["substrate_id"],
            source_type=r["source_type"],
            priority=r["priority"],
            deadline=deadline,
            site_of_action=r.get("site_of_action", ""),
            ph_min=_tracked(r.get("ph_min"), f"{eid}.ph_min"),
            ph_max=_tracked(r.get("ph_max"), f"{eid}.ph_max"),
            ph_opt_low=_tracked(r.get("ph_opt_low"), f"{eid}.ph_opt_low"),
            ph_opt_high=_tracked(r.get("ph_opt_high"), f"{eid}.ph_opt_high"),
            ph_shelf_stable_min=_tracked(
                r.get("ph_shelf_stable_min"), f"{eid}.ph_shelf_stable_min"
            ),
            temp_min_c=_tracked(r.get("temp_min_c"), f"{eid}.temp_min_c"),
            temp_max_c=_tracked(r.get("temp_max_c"), f"{eid}.temp_max_c"),
            temp_opt_c=_tracked(r.get("temp_opt_c"), f"{eid}.temp_opt_c"),
            dose_unit=r.get("dose_unit", ""),
            dose_min=_tracked(r.get("dose_min"), f"{eid}.dose_min"),
            dose_max=_tracked(r.get("dose_max"), f"{eid}.dose_max"),
            dose_evidence_threshold=_tracked(
                r.get("dose_evidence_threshold"), f"{eid}.dose_evidence_threshold"
            ),
            dose_benchmark_note=r.get("dose_benchmark_note", ""),
            is_protease=r.get("is_protease", False),
            is_natural_source=r.get("is_natural_source", False),
            is_gras=_tracked(r.get("is_gras"), f"{eid}.is_gras"),
            food_grade_note=r.get("food_grade_note", ""),
            heat_labile_note=r.get("heat_labile_note", ""),
            degrades_structural=_parse_structural(r.get("degrades_structural"), eid),
            cost_tier=r.get("cost_tier", ""),
            supplier_note=r.get("supplier_note", ""),
            notes=r.get("notes", ""),
        )

    foods = {}
    for r in _read("foods.json", d)["foods"]:
        fid = r["id"]
        try:
            structural = tuple(StructuralClass(s) for s in r.get("structural", ()))
        except ValueError as exc:
            raise SeedError(f"{fid}: bad structural class in {r.get('structural')}") from exc
        try:
            allergens = tuple(a.value for a in parse_allergens(r.get("allergens", ())))
        except ValueError as exc:
            raise SeedError(f"{fid}: {exc}") from exc
        foods[fid] = Food(
            id=fid,
            name=r["name"],
            category=r.get("category", ""),
            is_recipe_ingredient=r.get("is_recipe_ingredient", False),
            is_trigger_food=r.get("is_trigger_food", False),
            is_application_food=r.get("is_application_food", False),
            ph=_tracked(r.get("ph"), f"{fid}.ph"),
            water_content_pct=_tracked(r.get("water_content_pct"), f"{fid}.water_content_pct"),
            contains_substrate_ids=tuple(r.get("contains_substrate_ids", ())),
            typical_load_value=_tracked(r.get("typical_load_value"), f"{fid}.typical_load_value"),
            typical_load_unit=r.get("typical_load_unit", ""),
            contains_protease=r.get("contains_protease", False),
            is_heat_processed=r.get("is_heat_processed", False),
            structural=structural,
            allergens=allergens,
            notes=r.get("notes", ""),
        )

    # Referential integrity — a dangling id must fail at load, not at evaluate.
    for e in enzymes.values():
        if e.substrate_id not in substrates:
            raise SeedError(f"{e.id}: unknown substrate_id {e.substrate_id}")
    for f in foods.values():
        for sid in f.contains_substrate_ids:
            if sid not in substrates:
                raise SeedError(f"{f.id}: unknown substrate id {sid}")

    return Seed(
        enzymes=enzymes, foods=foods, substrates=substrates, gi_regions=tuple(regions)
    )
