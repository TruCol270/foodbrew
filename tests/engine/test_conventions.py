import dataclasses

import pytest

from foodbrew.engine.conventions import (
    FALLBACK_MARGIN_PH,
    WET_THRESHOLD_PCT,
    FloorResolution,
    aggregate_substrate_loads,
    is_wet,
    phase_for_format,
    resolve_recipe_ph,
    shelf_stable_floor,
)
from foodbrew.engine.types import (
    Food,
    Format,
    Formulation,
    Phase,
    RecipeIngredient,
    Tracked,
    TruthLabel,
)


def _food(fid, ph=None, water=None, ph_status=TruthLabel.CONFIRMED,
          water_status=TruthLabel.CONFIRMED, load=None, subs=()):
    return Food(
        id=fid, name=fid, category="test",
        ph=Tracked(ph, ph_status, "test"),
        water_content_pct=Tracked(water, water_status, "test"),
        typical_load_value=Tracked(load, TruthLabel.CONFIRMED if load is not None
                                   else TruthLabel.UNCONFIRMED, "test"),
        contains_substrate_ids=subs,
    )


def test_wet_threshold_is_fifty_percent():
    assert WET_THRESHOLD_PCT == 50


def test_is_wet_at_and_above_threshold():
    assert is_wet(_food("a", water=50)) is True
    assert is_wet(_food("b", water=95)) is True


def test_is_wet_below_threshold():
    assert is_wet(_food("c", water=20)) is False


def test_is_wet_is_none_when_water_unconfirmed():
    # Cannot decide — the caller must return cannot_assess, not guess.
    assert is_wet(_food("d", water=90, water_status=TruthLabel.UNCONFIRMED)) is None


def test_resolve_ph_prefers_formulation_measured():
    form = Formulation(
        id="f", format=Format.PREMIXED_WET, recipe=(), enzymes=(),
        measured_ph=Tracked(4.4, TruthLabel.USER_PROVIDED, "bench"),
    )
    res = resolve_recipe_ph(form, foods={}, latest_trial_ph=Tracked(3.9, TruthLabel.OBSERVED))
    assert res.value == 4.4
    assert res.status is TruthLabel.USER_PROVIDED
    assert res.origin == "formulation.measured_ph"


def test_resolve_ph_falls_back_to_trial_batch():
    form = Formulation(id="f", format=Format.PREMIXED_WET, recipe=(), enzymes=())
    res = resolve_recipe_ph(form, foods={}, latest_trial_ph=Tracked(3.9, TruthLabel.OBSERVED))
    assert res.value == 3.9
    assert res.status is TruthLabel.OBSERVED
    assert res.origin == "trial_batch.measured_ph"


def test_resolve_ph_falls_back_to_lowest_wet_ingredient():
    foods = {
        "vinegar": _food("vinegar", ph=3.0, water=95),
        "oil": _food("oil", ph=None, water=0),
        "yogurt": _food("yogurt", ph=4.4, water=85),
    }
    form = Formulation(
        id="f", format=Format.PREMIXED_WET,
        recipe=(
            RecipeIngredient("vinegar", 30.0),
            RecipeIngredient("oil", 60.0),
            RecipeIngredient("yogurt", 10.0),
        ),
        enzymes=(),
    )
    res = resolve_recipe_ph(form, foods=foods, latest_trial_ph=None)
    assert res.value == 3.0
    assert res.status is TruthLabel.CALCULATED
    assert res.origin == "wet_ingredient_fallback"


def test_resolve_ph_cannot_assess_when_a_wet_ingredient_ph_is_unconfirmed():
    foods = {"vinegar": _food("vinegar", ph=3.0, water=95, ph_status=TruthLabel.UNCONFIRMED)}
    form = Formulation(
        id="f", format=Format.PREMIXED_WET,
        recipe=(RecipeIngredient("vinegar", 30.0),), enzymes=(),
    )
    res = resolve_recipe_ph(form, foods=foods, latest_trial_ph=None)
    assert res.value is None
    assert res.status is TruthLabel.UNCONFIRMED
    assert "vinegar" in res.blocking_field


def test_resolve_ph_cannot_assess_when_water_content_unconfirmed():
    foods = {"x": _food("x", ph=3.0, water=95, water_status=TruthLabel.UNCONFIRMED)}
    form = Formulation(
        id="f", format=Format.PREMIXED_WET,
        recipe=(RecipeIngredient("x", 10.0),), enzymes=(),
    )
    res = resolve_recipe_ph(form, foods=foods, latest_trial_ph=None)
    assert res.status is TruthLabel.UNCONFIRMED
    assert "water_content_pct" in res.blocking_field


def test_substrate_loads_sum_across_foods():
    foods = {
        "beans": _food("beans", load=4.0, subs=("gos",)),
        "lentils": _food("lentils", load=2.5, subs=("gos",)),
        "milk": _food("milk", load=12.0, subs=("lactose",)),
    }
    result = aggregate_substrate_loads(("beans", "lentils", "milk"), foods)
    assert result["gos"].value == pytest.approx(6.5)
    assert result["gos"].status is TruthLabel.CONFIRMED
    assert result["lactose"].value == pytest.approx(12.0)


def test_substrate_load_unconfirmed_when_any_contributor_unconfirmed():
    foods = {
        "beans": _food("beans", load=4.0, subs=("gos",)),
        "lentils": _food("lentils", load=None, subs=("gos",)),
    }
    result = aggregate_substrate_loads(("beans", "lentils"), foods)
    assert result["gos"].status is TruthLabel.UNCONFIRMED
    assert "lentils" in result["gos"].source


def test_wet_formats_put_the_enzyme_in_the_liquid():
    assert phase_for_format(Format.PREMIXED_WET) is Phase.WET
    assert phase_for_format(Format.ENCAPSULATED_IN_WET) is Phase.WET
    assert phase_for_format(Format.DUAL_CHAMBER) is Phase.DRY
    assert phase_for_format(Format.DRY_SACHET) is Phase.DRY


def test_a_confirmed_shelf_floor_wins_over_the_heuristic(seed):
    enzyme = dataclasses.replace(
        seed.enzymes["lactase_fungal_acid"],
        ph_shelf_stable_min=Tracked(3.2, TruthLabel.CONFIRMED, "supplier spec"),
    )
    resolution = shelf_stable_floor(enzyme)
    assert (resolution.value, resolution.source) == (3.2, "ph_shelf_stable_min")
    assert not resolution.is_heuristic


def test_the_shipped_seed_falls_back_to_the_stated_margin(seed):
    """Every seeded ph_shelf_stable_min is unconfirmed (spec §9.1)."""
    enzyme = seed.enzymes["lactase_fungal_acid"]
    resolution = shelf_stable_floor(enzyme)
    assert resolution.is_heuristic
    assert resolution.value == float(enzyme.ph_min.value) + FALLBACK_MARGIN_PH


def test_an_enzyme_with_no_ph_at_all_has_no_floor(seed):
    enzyme = dataclasses.replace(
        seed.enzymes["lactase_fungal_acid"],
        ph_min=Tracked(None, TruthLabel.UNCONFIRMED),
        ph_shelf_stable_min=Tracked(None, TruthLabel.UNCONFIRMED),
    )
    assert shelf_stable_floor(enzyme) == FloorResolution(None, "unavailable")


def test_the_fallback_names_the_ingredient_that_set_the_pH(make_ctx, seed):
    foods = dict(seed.foods)
    for food_id, ph, water in (("olive_oil", 6.0, 0.0), ("white_vinegar", 2.6, 95.0),
                               ("water", 7.0, 100.0)):
        foods[food_id] = dataclasses.replace(
            foods[food_id],
            ph=Tracked(ph, TruthLabel.USER_PROVIDED, "fixture"),
            water_content_pct=Tracked(water, TruthLabel.USER_PROVIDED, "fixture"),
        )
    ctx = make_ctx(
        recipe=(("olive_oil", 100.0), ("white_vinegar", 50.0), ("water", 20.0)), foods=foods
    )
    resolution = resolve_recipe_ph(ctx.formulation, foods, None)
    assert resolution.value == 2.6
    assert resolution.driving_food_id == "white_vinegar"


def test_a_measured_pH_has_no_driving_ingredient(make_ctx):
    ctx = make_ctx(measured_ph=4.4)
    resolution = resolve_recipe_ph(ctx.formulation, ctx.foods, None)
    assert resolution.origin == "formulation.measured_ph"
    assert resolution.driving_food_id == ""
