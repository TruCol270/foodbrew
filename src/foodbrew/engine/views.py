"""Derived views the verdict screen renders. Pure, so a stored snapshot renders
exactly as it did when it was evaluated (plan decision #5).

These are derivations, not rules: they compute nothing a rule does not already
read, and they never produce a verdict. R7's judgement lives in r07_dosing.py;
the dose card here only exposes the same arithmetic so the screen can show the
founder why the rule said what it said.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from foodbrew.engine.conventions import aggregate_substrate_loads
from foodbrew.engine.dosing import assess_dose
from foodbrew.engine.gi_model import active_regions, regions_before_deadline
from foodbrew.engine.types import (
    Deadline,
    EvalContext,
    Food,
    RecipeIngredient,
    Substrate,
    Tracked,
    TruthLabel,
)

#: Plain-English rule names for the screen, so the UI hardcodes no copy (§10).
RULE_TITLES: Mapping[str, str] = {
    "R1": "In-jar pH survival",
    "R2": "GI window vs deadline",
    "R3": "No heat",
    "R4": "Water activation",
    "R5": "Protease co-formulation",
    "R6": "Encapsulation semantics",
    "R7": "Dosing vs substrate load",
    "R8": "In-jar taste and stability over time",
    "R9": "Prebiotic tension",
    "R10": "Strain blending",
    "R11": "Food-grade and GRAS",
    "R12": "Temperature range",
    "R13": "Format flag",
    "R14": "Substrate coverage",
    "R15": "Applied-food texture",
    "R16": "Clean label and natural sourcing",
}


@dataclass(frozen=True, slots=True)
class RegionState:
    region_id: str
    name: str
    ph_low: float
    ph_high: float
    order: int
    dormant: bool
    active: bool
    before_deadline: bool


@dataclass(frozen=True, slots=True)
class GiLane:
    enzyme_id: str
    enzyme_name: str
    deadline: Deadline
    ph_min: Tracked
    ph_max: Tracked
    regions: tuple[RegionState, ...]


@dataclass(frozen=True, slots=True)
class DoseCard:
    enzyme_id: str
    enzyme_name: str
    substrate_id: str
    dose: float | None
    dose_unit: str
    dose_min: Tracked
    dose_max: Tracked
    dose_evidence_threshold: Tracked
    substrate_load: Tracked
    #: None whenever any input is unusable — never a guess, mirroring R7.
    meets_threshold: bool | None
    ratio: float | None
    above_benchmark_max: bool | None


@dataclass(frozen=True, slots=True)
class SubstrateRow:
    substrate_id: str
    substrate_name: str
    from_food_names: tuple[str, ...]
    is_prebiotic: bool
    no_commercial_enzyme: bool


def gi_strip(ctx: EvalContext) -> tuple[GiLane, ...]:
    """One lane per selected enzyme: where along the tract it can act (§8, §10)."""
    lanes: list[GiLane] = []
    for selected in ctx.selected_enzymes():
        enzyme = ctx.enzyme_for(selected)
        active = {r.id for r in active_regions(enzyme, ctx.gi_regions)}
        before = {r.id for r in regions_before_deadline(enzyme.deadline, ctx.gi_regions)}
        lanes.append(
            GiLane(
                enzyme_id=enzyme.id,
                enzyme_name=enzyme.name,
                deadline=enzyme.deadline,
                ph_min=enzyme.ph_min,
                ph_max=enzyme.ph_max,
                regions=tuple(
                    RegionState(
                        region_id=r.id, name=r.name, ph_low=r.ph_low, ph_high=r.ph_high,
                        order=r.order, dormant=r.dormant,
                        active=r.id in active, before_deadline=r.id in before,
                    )
                    for r in ctx.gi_regions
                ),
            )
        )
    return tuple(lanes)


def dose_cards(ctx: EvalContext) -> tuple[DoseCard, ...]:
    """Per-enzyme dose against the summed substrate load and evidence threshold."""
    loads = aggregate_substrate_loads(ctx.formulation.target_trigger_food_ids, ctx.foods)
    cards: list[DoseCard] = []

    for selected in ctx.selected_enzymes():
        enzyme = ctx.enzyme_for(selected)
        load = loads.get(
            enzyme.substrate_id, Tracked(None, TruthLabel.UNCONFIRMED, "no targeted trigger food")
        )
        threshold = enzyme.dose_evidence_threshold

        if selected.dose is not None and threshold.usable:
            assessment = assess_dose(
                float(selected.dose),
                float(threshold.value),
                float(enzyme.dose_max.value) if enzyme.dose_max.usable else None,
            )
            meets, ratio, over = (
                assessment.meets_threshold, assessment.ratio, assessment.above_benchmark_max
            )
        else:
            meets = ratio = over = None

        cards.append(
            DoseCard(
                enzyme_id=enzyme.id, enzyme_name=enzyme.name,
                substrate_id=enzyme.substrate_id,
                dose=selected.dose, dose_unit=enzyme.dose_unit,
                dose_min=enzyme.dose_min, dose_max=enzyme.dose_max,
                dose_evidence_threshold=threshold, substrate_load=load,
                meets_threshold=meets, ratio=ratio, above_benchmark_max=over,
            )
        )
    return tuple(cards)


def substrate_summary(
    recipe: Sequence[RecipeIngredient],
    foods: Mapping[str, Food],
    substrates: Mapping[str, Substrate],
) -> tuple[SubstrateRow, ...]:
    """Spec §10 screen 2 — "this recipe itself contains: GOS (garlic)…"."""
    names: dict[str, list[str]] = {}
    for ingredient in recipe:
        food = foods.get(ingredient.food_id)
        if food is None:
            continue
        for substrate_id in food.contains_substrate_ids:
            names.setdefault(substrate_id, []).append(food.name)

    rows: list[SubstrateRow] = []
    for substrate_id, food_names in sorted(names.items()):
        substrate = substrates.get(substrate_id)
        rows.append(
            SubstrateRow(
                substrate_id=substrate_id,
                substrate_name=substrate.name if substrate else substrate_id,
                from_food_names=tuple(dict.fromkeys(food_names)),
                is_prebiotic=bool(substrate and substrate.is_prebiotic),
                no_commercial_enzyme=bool(substrate and substrate.no_commercial_enzyme),
            )
        )
    return tuple(rows)
