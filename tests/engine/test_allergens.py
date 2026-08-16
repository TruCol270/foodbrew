"""The closed vocabulary, and the difference between 'none' and 'not recorded'."""

import pytest

from foodbrew.engine.allergens import (
    NOTHING_RECORDED,
    Allergen,
    declare,
    parse,
)


class FakeFood:
    def __init__(self, name, allergens=()):
        self.name = name
        self.allergens = allergens


def test_every_enum_member_has_label_text():
    from foodbrew.engine.allergens import ALLERGEN_TEXT

    assert set(ALLERGEN_TEXT) == set(Allergen)


def test_parse_accepts_the_vocabulary_and_dedupes():
    assert parse(["milk", "milk", "egg"]) == (Allergen.MILK, Allergen.EGG)


def test_parse_refuses_an_unknown_token_and_names_the_allowed_set():
    with pytest.raises(ValueError) as exc:
        parse(["dairy"])
    assert "unknown allergen 'dairy'" in str(exc.value)
    assert "milk" in str(exc.value)


def test_a_declaration_groups_ingredients_by_allergen_in_vocabulary_order():
    foods = {
        "yogurt": FakeFood("Yogurt", ("milk",)),
        "croutons": FakeFood("Croutons", ("wheat",)),
        "parmesan": FakeFood("Parmesan", ("milk",)),
    }
    declaration = declare(["yogurt", "croutons", "parmesan"], foods)
    assert [e.allergen for e in declaration.entries] == [Allergen.MILK, Allergen.WHEAT]
    assert declaration.entries[0].from_food_names == ("Yogurt", "Parmesan")
    assert declaration.unrecorded_food_names == ()


def test_a_food_with_no_allergen_record_is_a_gap_not_a_clearance():
    foods = {"olive_oil": FakeFood("Olive oil"), "yogurt": FakeFood("Yogurt", ("milk",))}
    declaration = declare(["olive_oil", "yogurt"], foods)
    assert declaration.unrecorded_food_names == ("Olive oil",)
    assert [e.allergen for e in declaration.entries] == [Allergen.MILK]


def test_a_food_absent_from_the_snapshot_is_reported_not_skipped():
    declaration = declare(["ghost"], {})
    assert declaration.unrecorded_food_names == ("ghost",)
    assert declaration.is_empty


def test_an_empty_recipe_declares_nothing_and_says_so():
    declaration = declare([], {})
    assert declaration.is_empty
    assert declaration.unrecorded_food_names == ()
    assert NOTHING_RECORDED  # the wording exists for the report to use
