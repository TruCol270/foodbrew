"""Spec §5.3's computed_dose_json — one meal's arithmetic, and its refusals."""

import dataclasses

import pytest

from foodbrew.engine.language import contains_prohibited
from foodbrew.engine.symptoms import SERVINGS, computed_dose
from foodbrew.engine.types import Phase, Tracked, TruthLabel


@pytest.fixture
def ctx(make_ctx, with_load):
    return make_ctx(
        enzymes=(("lactase_fungal_acid", 9000.0, Phase.WET),),
        recipe=(("olive_oil", 100.0),),
        trigger_foods=("milk",),
        foods=with_load(milk=6.0),
    )


def test_units_delivered_is_the_dose_times_the_doses_used(ctx):
    math = computed_dose(
        context=ctx, trigger_food_id="milk", amount_value=1.0,
        amount_unit=SERVINGS, doses_used=2.0,
    )
    entry = math.enzymes[0]
    assert entry.enzyme_id == "lactase_fungal_acid"
    assert entry.units_delivered == 18000.0


def test_the_load_scales_with_servings_and_says_how(ctx):
    math = computed_dose(
        context=ctx, trigger_food_id="milk", amount_value=2.0,
        amount_unit=SERVINGS, doses_used=1.0,
    )
    assert math.substrate_load.value == 12.0
    assert math.substrate_load.status is TruthLabel.CALCULATED
    assert "per serving" in math.substrate_load.source
    assert math.note == ""


def test_an_unrecognised_unit_refuses_the_load_rather_than_converting(ctx):
    math = computed_dose(
        context=ctx, trigger_food_id="milk", amount_value=250.0,
        amount_unit="ml", doses_used=1.0,
    )
    assert math.substrate_load.value is None
    assert "servings" in math.note
    # The dose arithmetic is independent of the amount and still works.
    assert math.enzymes[0].units_delivered == 9000.0


def test_an_unconfirmed_threshold_reports_cannot_tell_and_names_the_field(ctx, seed):
    catalog = dict(seed.enzymes)
    catalog["lactase_fungal_acid"] = dataclasses.replace(
        catalog["lactase_fungal_acid"],
        dose_evidence_threshold=Tracked(None, TruthLabel.UNCONFIRMED),
    )
    context = dataclasses.replace(ctx, enzymes=catalog)
    math = computed_dose(
        context=context, trigger_food_id="milk", amount_value=1.0,
        amount_unit=SERVINGS, doses_used=1.0,
    )
    entry = math.enzymes[0]
    assert entry.meets_threshold is None
    assert entry.ratio is None
    assert entry.blocking_field.endswith("dose_evidence_threshold")


def test_no_doses_entered_yet_is_a_gap_not_a_zero(ctx):
    math = computed_dose(
        context=ctx, trigger_food_id="milk", amount_value=1.0,
        amount_unit=SERVINGS, doses_used=None,
    )
    entry = math.enzymes[0]
    assert entry.units_delivered is None
    assert entry.meets_threshold is None
    assert entry.blocking_field == "no number of doses entered"


def test_a_meal_no_selected_enzyme_covers_says_so_plainly(ctx):
    math = computed_dose(
        context=ctx, trigger_food_id="romaine", amount_value=1.0,
        amount_unit=SERVINGS, doses_used=1.0,
    )
    assert math.enzymes == ()
    assert "was not working on it" in math.note


def test_an_unknown_food_is_refused_rather_than_guessed(ctx):
    math = computed_dose(
        context=ctx, trigger_food_id="nope", amount_value=1.0,
        amount_unit=SERVINGS, doses_used=1.0,
    )
    assert math.enzymes == ()
    assert "not a food this evaluation knew about" in math.note


def test_meeting_the_threshold_is_reported_both_ways(ctx, seed):
    # The shipped seed leaves lactase_fungal_acid.dose_evidence_threshold
    # unconfirmed by design (KB: "No independent full-dose threshold
    # published for lactase in the source set." — see test_golden_fixtures.py
    # and test_views.py, which assert exactly that). This test needs a usable
    # threshold to exercise meets_threshold both ways, so it supplies one
    # explicitly rather than relying on the seed to carry it.
    catalog = dict(seed.enzymes)
    catalog["lactase_fungal_acid"] = dataclasses.replace(
        catalog["lactase_fungal_acid"],
        dose_evidence_threshold=Tracked(6000.0, TruthLabel.CONFIRMED, "KB Table B"),
    )
    context = dataclasses.replace(ctx, enzymes=catalog)

    under = dataclasses.replace(
        context,
        formulation=dataclasses.replace(
            context.formulation,
            enzymes=(dataclasses.replace(context.formulation.enzymes[0], dose=100.0),),
        ),
    )
    assert computed_dose(
        context=under, trigger_food_id="milk", amount_value=1.0,
        amount_unit=SERVINGS, doses_used=1.0,
    ).enzymes[0].meets_threshold is False

    assert computed_dose(
        context=context, trigger_food_id="milk", amount_value=1.0,
        amount_unit=SERVINGS, doses_used=1.0,
    ).enzymes[0].meets_threshold is True


def test_the_payload_round_trips_as_plain_json(ctx):
    import json

    math = computed_dose(
        context=ctx, trigger_food_id="milk", amount_value=1.0,
        amount_unit=SERVINGS, doses_used=1.0,
    )
    text = json.dumps(math.as_dict(), sort_keys=True)
    assert json.loads(text)["enzymes"][0]["units_delivered"] == 9000.0
    assert contains_prohibited(text) == ()
