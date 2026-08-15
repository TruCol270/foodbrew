"""Spec §6.7 — conventions several rules share, defined once so they cannot diverge."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from foodbrew.engine.types import Enzyme, Food, Format, Formulation, Phase, Tracked, TruthLabel

#: Spec §6.7 — a recipe ingredient counts as wet at or above this water content.
WET_THRESHOLD_PCT = 50


def is_wet(food: Food) -> bool | None:
    """True/False when water content is evidence; None when it is unconfirmed.

    None means "cannot decide" — the caller must surface cannot_assess rather
    than treating an unknown as dry.
    """
    if not food.water_content_pct.usable:
        return None
    return float(food.water_content_pct.value) >= WET_THRESHOLD_PCT


@dataclass(frozen=True, slots=True)
class PhResolution:
    """Outcome of spec §6.7's measured-pH resolution order."""

    value: float | None
    status: TruthLabel
    origin: str
    blocking_field: str = ""
    #: The wet ingredient whose pH became the estimate. Empty unless the
    #: fallback was used — a measured pH has no driving ingredient.
    driving_food_id: str = ""


def resolve_recipe_ph(
    formulation: Formulation,
    foods: Mapping[str, Food],
    latest_trial_ph: Tracked | None,
) -> PhResolution:
    """Spec §6.7 resolution order: formulation → latest trial batch → wet-ingredient fallback."""
    if formulation.measured_ph.usable:
        return PhResolution(
            value=float(formulation.measured_ph.value),
            status=formulation.measured_ph.status,
            origin="formulation.measured_ph",
        )

    if latest_trial_ph is not None and latest_trial_ph.usable:
        return PhResolution(
            value=float(latest_trial_ph.value),
            status=TruthLabel.OBSERVED,
            origin="trial_batch.measured_ph",
        )

    wet_phs: list[tuple[float, str]] = []
    for ingredient in formulation.recipe:
        food = foods.get(ingredient.food_id)
        if food is None:
            return PhResolution(
                None, TruthLabel.UNCONFIRMED, "wet_ingredient_fallback",
                blocking_field=f"unknown food '{ingredient.food_id}'",
            )
        wet = is_wet(food)
        if wet is None:
            return PhResolution(
                None, TruthLabel.UNCONFIRMED, "wet_ingredient_fallback",
                blocking_field=f"{food.id}.water_content_pct",
            )
        if not wet:
            continue
        if not food.ph.usable:
            return PhResolution(
                None, TruthLabel.UNCONFIRMED, "wet_ingredient_fallback",
                blocking_field=f"{food.id}.ph",
            )
        wet_phs.append((float(food.ph.value), food.id))

    if not wet_phs:
        return PhResolution(
            None, TruthLabel.UNCONFIRMED, "wet_ingredient_fallback",
            blocking_field="no wet ingredient in the recipe",
        )

    lowest, driver = min(wet_phs)
    return PhResolution(
        value=lowest, status=TruthLabel.CALCULATED, origin="wet_ingredient_fallback",
        driving_food_id=driver,
    )


def aggregate_substrate_loads(
    trigger_food_ids, foods: Mapping[str, Food]
) -> dict[str, Tracked]:
    """Spec §6.7 — loads for foods sharing a substrate are SUMMED, never max-ed.

    A meal with beans and lentils presents more GOS than either alone. If any
    contributing food's load is unconfirmed, the whole substrate is unconfirmed
    and names the offender.
    """
    totals: dict[str, float] = {}
    blockers: dict[str, list[str]] = {}
    sources: dict[str, list[str]] = {}

    for fid in trigger_food_ids:
        food = foods.get(fid)
        if food is None:
            continue
        for sid in food.contains_substrate_ids:
            if not food.typical_load_value.usable:
                blockers.setdefault(sid, []).append(fid)
                continue
            totals[sid] = totals.get(sid, 0.0) + float(food.typical_load_value.value)
            sources.setdefault(sid, []).append(fid)

    out: dict[str, Tracked] = {}
    for sid in set(totals) | set(blockers):
        if sid in blockers:
            out[sid] = Tracked(
                value=None,
                status=TruthLabel.UNCONFIRMED,
                source="no typical_load_value for: " + ", ".join(sorted(blockers[sid])),
            )
        else:
            out[sid] = Tracked(
                value=totals[sid],
                status=TruthLabel.CONFIRMED,
                source="summed across: " + ", ".join(sorted(sources[sid])),
            )
    return out


#: Spec §5.2 — the formats where the enzyme sits in the liquid. Extracted from
#: selection.py's private copy because the format ladder (format_search.py) has
#: to agree with the enzyme proposal about what a format means; a `dry_sachet`
#: whose selections still say `phase: wet` is not a dry sachet (plan decision #5).
WET_FORMATS = frozenset({Format.PREMIXED_WET, Format.ENCAPSULATED_IN_WET})


def phase_for_format(fmt: Format) -> Phase:
    return Phase.WET if fmt in WET_FORMATS else Phase.DRY


@dataclass(frozen=True, slots=True)
class FloorResolution:
    """The pH an enzyme must stay above for shelf duration, and where it came from."""

    value: float | None
    #: "ph_shelf_stable_min" | "fallback" | "unavailable"
    source: str

    @property
    def is_heuristic(self) -> bool:
        return self.source == "fallback"


#: Spec §6.1 R1 — the stated fallback when no supplier has confirmed a
#: shelf-stable floor. An engineering convention that makes the rule testable,
#: NOT a scientific claim; every finding that uses it says so (spec §12 item 3).
FALLBACK_MARGIN_PH = 1.0


def shelf_stable_floor(enzyme: Enzyme) -> FloorResolution:
    """Spec §6.1 R1's floor, resolved once for R1, R6, and the variant engine."""
    if enzyme.ph_shelf_stable_min.usable:
        return FloorResolution(float(enzyme.ph_shelf_stable_min.value), "ph_shelf_stable_min")
    if enzyme.ph_min.usable:
        return FloorResolution(float(enzyme.ph_min.value) + FALLBACK_MARGIN_PH, "fallback")
    return FloorResolution(None, "unavailable")
