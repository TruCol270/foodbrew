"""The formula table's arithmetic: percent of total, in order of addition.

Pure. Percent is CALCULATED at render time from the weights the snapshot already
carries (plan decision #6) — never stored, never editable. A stored percent that
could disagree with the grams beside it is the orphan number this tool exists to
refuse.

True percent, not baker's percent (plan decision #7): the column sums to 100
because a dressing has no flour basis, and a scientist reading a column that
sums past 100 will assume one.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from foodbrew.engine.types import Food, ProcessStep, RecipeIngredient, Tracked

#: Percentages are rounded for display only; the sum check uses the raw values.
PERCENT_DECIMALS = 2


@dataclass(frozen=True, slots=True)
class FormulaLine:
    order: int
    food_id: str
    food_name: str
    amount_g: float
    #: None when the batch total is zero — a percentage of nothing is not zero.
    percent_of_total: float | None
    ph: Tracked
    water_content_pct: Tracked
    allergen_text: str
    #: True when this is the step the enzyme goes in after (§5.2).
    is_enzyme_addition_point: bool = False


@dataclass(frozen=True, slots=True)
class Formula:
    lines: tuple[FormulaLine, ...]
    total_g: float
    #: The rounded percentages as printed, summed — for the caption's honesty.
    printed_percent_total: float | None

    @property
    def is_empty(self) -> bool:
        return not self.lines


@dataclass(frozen=True, slots=True)
class ProcessLine:
    order: int
    label: str
    is_heat: bool
    is_enzyme_addition_point: bool


def build(
    recipe: Sequence[RecipeIngredient],
    foods: Mapping[str, Food],
    *,
    allergen_text_for=lambda food: "",
) -> Formula:
    """One formula table, ordered by `RecipeIngredient.order` then by id.

    Order of addition is `order`, which has existed since M1 and has never been
    shown to anyone. Ties break on food id so the table is deterministic, which
    is what keeps a re-rendered report byte-identical.
    """
    ordered = sorted(recipe, key=lambda i: (i.order, i.food_id))
    total = sum(float(i.amount_g) for i in ordered)

    lines: list[FormulaLine] = []
    for ingredient in ordered:
        food = foods.get(ingredient.food_id)
        percent = (
            round(float(ingredient.amount_g) / total * 100, PERCENT_DECIMALS)
            if total > 0
            else None
        )
        lines.append(
            FormulaLine(
                order=ingredient.order,
                food_id=ingredient.food_id,
                food_name=food.name if food else ingredient.food_id,
                amount_g=float(ingredient.amount_g),
                percent_of_total=percent,
                ph=food.ph if food else Tracked(None, _unconfirmed()),
                water_content_pct=(
                    food.water_content_pct if food else Tracked(None, _unconfirmed())
                ),
                allergen_text=allergen_text_for(food) if food else "",
            )
        )

    printed = (
        round(sum(line.percent_of_total for line in lines if line.percent_of_total), 2)
        if total > 0
        else None
    )
    return Formula(lines=tuple(lines), total_g=total, printed_percent_total=printed)


def _unconfirmed():
    from foodbrew.engine.types import TruthLabel

    return TruthLabel.UNCONFIRMED


def process_lines(
    steps: Sequence[ProcessStep], enzyme_addition_index: int | None
) -> tuple[ProcessLine, ...]:
    """Process steps in order, flagging where the enzyme goes in (§5.2, R3)."""
    return tuple(
        ProcessLine(
            order=step.order,
            label=step.label,
            is_heat=step.is_heat,
            is_enzyme_addition_point=(enzyme_addition_index == step.order),
        )
        for step in sorted(steps, key=lambda s: s.order)
    )
