"""Spec §5.3 / §10 screen 6 — what a meal actually delivered, against the threshold.

Pure. The same function backs the live preview and the stored entry, so what she
watched while typing is what gets frozen into the row (plan decision #8).

This is not a kinetics model and does not pretend to be one: it multiplies the
per-serving dose she chose by the number of doses she used, and compares that
with the enzyme's evidence threshold. §12 item 2 already says dose guidance is
benchmark-based; this is the same arithmetic applied to one meal.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from foodbrew.engine.dosing import assess_dose
from foodbrew.engine.types import EvalContext, Tracked, TruthLabel

#: The one amount unit the substrate-load arithmetic understands. A trigger
#: food's `typical_load_value` is a per-serving figure (§9.3), so servings is
#: the only unit that can be multiplied by it without inventing a conversion.
SERVINGS = "servings"


@dataclass(frozen=True, slots=True)
class EnzymeDose:
    enzyme_id: str
    enzyme_name: str
    dose_unit: str
    #: Dose per serving of dressing, as selected on the formulation.
    dose_per_serving: float | None
    units_delivered: float | None
    threshold: Tracked
    #: None whenever any input is unusable — never a guess, exactly as R7.
    meets_threshold: bool | None
    ratio: float | None
    blocking_field: str = ""

    def as_dict(self) -> dict:
        return {
            "enzyme_id": self.enzyme_id,
            "enzyme_name": self.enzyme_name,
            "dose_unit": self.dose_unit,
            "dose_per_serving": self.dose_per_serving,
            "units_delivered": self.units_delivered,
            "threshold": {
                "value": self.threshold.value,
                "status": str(self.threshold.status),
                "source": self.threshold.source,
            },
            "meets_threshold": self.meets_threshold,
            "ratio": self.ratio,
            "blocking_field": self.blocking_field,
        }


@dataclass(frozen=True, slots=True)
class SymptomDoseMath:
    trigger_food_id: str
    trigger_food_name: str
    amount_value: float | None
    amount_unit: str
    doses_used: float | None
    substrate_ids: tuple[str, ...]
    enzymes: tuple[EnzymeDose, ...]
    #: The substrate this meal presented, when it can be worked out at all.
    substrate_load: Tracked
    #: Plain-English statement of what could not be worked out, if anything.
    note: str = ""

    def as_dict(self) -> dict:
        return {
            "trigger_food_id": self.trigger_food_id,
            "trigger_food_name": self.trigger_food_name,
            "amount_value": self.amount_value,
            "amount_unit": self.amount_unit,
            "doses_used": self.doses_used,
            "substrate_ids": list(self.substrate_ids),
            "enzymes": [e.as_dict() for e in self.enzymes],
            "substrate_load": {
                "value": self.substrate_load.value,
                "status": str(self.substrate_load.status),
                "source": self.substrate_load.source,
            },
            "note": self.note,
        }


def _load_for_meal(food, amount_value: float | None, amount_unit: str) -> tuple[Tracked, str]:
    if not food.typical_load_value.usable:
        return (
            Tracked(None, TruthLabel.UNCONFIRMED, f"{food.id}.typical_load_value"),
            f"How much substrate a serving of {food.name} carries is not recorded, so "
            f"the amount you ate cannot be turned into a load.",
        )
    if amount_value is None:
        return (
            Tracked(None, TruthLabel.UNCONFIRMED, "no amount entered"),
            "Enter how much you ate to see the load this meal presented.",
        )
    if amount_unit != SERVINGS:
        return (
            Tracked(None, TruthLabel.UNCONFIRMED, f"amount unit '{amount_unit}'"),
            f"Amounts are counted in servings here, because the recorded load for "
            f"{food.name} is a per-serving figure. Convert what you ate to servings "
            f"to see the load.",
        )
    value = float(food.typical_load_value.value) * float(amount_value)
    return (
        Tracked(
            value,
            TruthLabel.CALCULATED,
            f"{food.typical_load_value.value} {food.typical_load_unit} per serving "
            f"× {amount_value} servings",
        ),
        "",
    )


def computed_dose(
    *,
    context: EvalContext,
    trigger_food_id: str,
    amount_value: float | None,
    amount_unit: str,
    doses_used: float | None,
) -> SymptomDoseMath:
    """Spec §5.3 — units delivered vs `dose_evidence_threshold`, for one meal.

    `context` is the evaluation's own frozen snapshot (plan decision #7), so a
    later edit to an enzyme's threshold cannot retroactively change what a meal
    already eaten is judged against.
    """
    food = context.foods.get(trigger_food_id)
    if food is None:
        return SymptomDoseMath(
            trigger_food_id=trigger_food_id, trigger_food_name=trigger_food_id,
            amount_value=amount_value, amount_unit=amount_unit, doses_used=doses_used,
            substrate_ids=(), enzymes=(),
            substrate_load=Tracked(None, TruthLabel.UNCONFIRMED, "unknown food"),
            note=f"'{trigger_food_id}' is not a food this evaluation knew about.",
        )

    substrate_ids = tuple(food.contains_substrate_ids)
    load, note = _load_for_meal(food, amount_value, amount_unit)

    doses: list[EnzymeDose] = []
    for selected in context.selected_enzymes():
        enzyme = context.enzyme_for(selected)
        if enzyme.substrate_id not in substrate_ids:
            continue

        threshold = enzyme.dose_evidence_threshold
        delivered = (
            float(selected.dose) * float(doses_used)
            if selected.dose is not None and doses_used is not None
            else None
        )
        blocking = ""
        if selected.dose is None:
            blocking = f"{enzyme.id}: no dose is set on this formulation"
        elif doses_used is None:
            blocking = "no number of doses entered"
        elif not threshold.usable:
            blocking = f"{enzyme.id}.dose_evidence_threshold"

        if delivered is not None and threshold.usable:
            assessment = assess_dose(delivered, float(threshold.value), None)
            meets, ratio = assessment.meets_threshold, assessment.ratio
        else:
            meets = ratio = None

        doses.append(
            EnzymeDose(
                enzyme_id=enzyme.id, enzyme_name=enzyme.name, dose_unit=enzyme.dose_unit,
                dose_per_serving=selected.dose, units_delivered=delivered,
                threshold=threshold, meets_threshold=meets, ratio=ratio,
                blocking_field=blocking,
            )
        )

    if not doses:
        covered = ", ".join(substrate_ids) if substrate_ids else "no recorded substrate"
        note = (
            f"No enzyme on this formulation targets what {food.name} carries "
            f"({covered}). Whatever happened at this meal, the blend was not "
            f"working on it."
        )

    return SymptomDoseMath(
        trigger_food_id=food.id, trigger_food_name=food.name,
        amount_value=amount_value, amount_unit=amount_unit, doses_used=doses_used,
        substrate_ids=substrate_ids, enzymes=tuple(doses),
        substrate_load=load, note=note,
    )
