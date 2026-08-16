"""The allergen vocabulary and the declaration the report prints.

Pure, and inert by design: **no rule imports this module** (plan decision #2,
asserted by tests/api/test_contracts_m5.py). An allergen never changes a
verdict — it is catalogue reference data that travels with the evaluation so the
report can state what is in the jar, exactly as `Food.notes` already does.

The vocabulary is closed because a declaration assembled from free text is a
declaration nothing can lint. These are the nine major allergens named in US
labelling law; a founder who needs a tenth is making a product decision, not
filling in a field.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum


class Allergen(StrEnum):
    MILK = "milk"
    EGG = "egg"
    FISH = "fish"
    CRUSTACEAN_SHELLFISH = "crustacean_shellfish"
    TREE_NUT = "tree_nut"
    PEANUT = "peanut"
    WHEAT = "wheat"
    SOY = "soy"
    SESAME = "sesame"


#: Label-facing wording. The report prints these, not the enum values.
ALLERGEN_TEXT: Mapping[Allergen, str] = {
    Allergen.MILK: "milk",
    Allergen.EGG: "egg",
    Allergen.FISH: "fish",
    Allergen.CRUSTACEAN_SHELLFISH: "crustacean shellfish",
    Allergen.TREE_NUT: "tree nuts",
    Allergen.PEANUT: "peanuts",
    Allergen.WHEAT: "wheat",
    Allergen.SOY: "soy",
    Allergen.SESAME: "sesame",
}

#: Spec §12's discipline applied to allergens: an empty list on a food means
#: "nothing recorded", NOT "contains no allergen". The report says which.
NOTHING_RECORDED = "not recorded for this ingredient"


def parse(values: Sequence[str]) -> tuple[Allergen, ...]:
    """Closed-vocabulary parse. An unknown token is an error, never a passthrough."""
    out: list[Allergen] = []
    for raw in values:
        try:
            allergen = Allergen(raw)
        except ValueError as exc:
            allowed = ", ".join(a.value for a in Allergen)
            raise ValueError(f"unknown allergen '{raw}'; allowed: {allowed}") from exc
        if allergen not in out:
            out.append(allergen)
    return tuple(out)


@dataclass(frozen=True, slots=True)
class DeclarationEntry:
    allergen: Allergen
    text: str
    #: Names of the recipe ingredients that carry it, in recipe order.
    from_food_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Declaration:
    entries: tuple[DeclarationEntry, ...]
    #: Recipe ingredients with no allergen record at all — a gap, not a clearance.
    unrecorded_food_names: tuple[str, ...]

    @property
    def is_empty(self) -> bool:
        return not self.entries


def declare(
    ingredient_food_ids: Sequence[str], foods: Mapping[str, object]
) -> Declaration:
    """Build the declaration for one recipe, in recipe order.

    `foods` is the evaluation's frozen food map. A food the snapshot does not
    carry is reported as unrecorded rather than skipped: the whole point of the
    declaration is that a silent omission is indistinguishable from a clearance.
    """
    carried: dict[Allergen, list[str]] = {}
    unrecorded: list[str] = []

    for food_id in ingredient_food_ids:
        food = foods.get(food_id)
        if food is None:
            unrecorded.append(food_id)
            continue
        allergens = tuple(getattr(food, "allergens", ()) or ())
        if not allergens:
            unrecorded.append(food.name)
            continue
        for allergen in allergens:
            names = carried.setdefault(Allergen(allergen), [])
            if food.name not in names:
                names.append(food.name)

    entries = tuple(
        DeclarationEntry(
            allergen=allergen,
            text=ALLERGEN_TEXT[allergen],
            from_food_names=tuple(carried[allergen]),
        )
        for allergen in Allergen
        if allergen in carried
    )
    return Declaration(entries=entries, unrecorded_food_names=tuple(unrecorded))
