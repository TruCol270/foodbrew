"""Spec §6.7's resolution order, end to end, and §13's pH resolution test."""

import pytest

from foodbrew.engine.conventions import resolve_recipe_ph
from foodbrew.engine.types import TruthLabel
from foodbrew.store import evaluations as evaluations_store
from foodbrew.store import formulations, recipes, trials


@pytest.fixture
def unmeasured(conn):
    """The same vinaigrette with no measured pH — so the fallback is in play."""
    recipe_id = recipes.create(conn, name="vinaigrette", notes="", ingredients=[
        {"food_id": "olive_oil", "amount_g": 100.0, "order": 1},
        {"food_id": "white_vinegar", "amount_g": 50.0, "order": 2},
    ])
    return formulations.create(
        conn, recipe_id=recipe_id, format="premixed_wet",
        target_trigger_food_ids=["milk"], application_food_ids=["romaine"],
        dwell_profile=None,
        enzymes=[{"enzyme_id": "lactase_fungal_acid", "dose": 9000.0, "phase": "wet",
                  "encapsulated": False, "source_choice": ""}],
        serving_size_g=30.0, measured_ph=None,
        process_steps=[{"order": 1, "label": "whisk", "is_heat": False}],
        enzyme_addition_index=1, parent_formulation_id=None,
    )


def _log_batch_ph(conn, formulation_id, ph):
    evaluation = evaluations_store.run(conn, formulation_id)
    trial_id = trials.create(conn, evaluation.id)
    trials.add_batch(conn, trial_id, measured_ph=ph, ph_method="meter")
    return evaluation


def test_a_batch_ph_becomes_the_next_evaluations_input_labelled_observed(conn, unmeasured):
    _log_batch_ph(conn, unmeasured, 3.4)
    context = formulations.hydrate_context(conn, unmeasured)
    resolution = resolve_recipe_ph(context.formulation, context.foods, context.latest_trial_ph)
    assert resolution.value == 3.4
    assert resolution.status is TruthLabel.OBSERVED
    assert resolution.origin == "trial_batch.measured_ph"


def test_a_formulation_measurement_still_wins_over_a_batch_one(conn, vinaigrette_rows):
    _log_batch_ph(conn, vinaigrette_rows["formulation_id"], 3.4)
    context = formulations.hydrate_context(conn, vinaigrette_rows["formulation_id"])
    resolution = resolve_recipe_ph(context.formulation, context.foods, context.latest_trial_ph)
    assert resolution.value == 3.0
    assert resolution.origin == "formulation.measured_ph"


def test_logging_a_batch_ph_makes_the_earlier_evaluation_stale(conn, unmeasured):
    evaluation = _log_batch_ph(conn, unmeasured, 3.4)
    stale, changes = evaluations_store.freshness(conn, evaluations_store.get(conn, evaluation.id))
    assert stale is True
    assert changes  # the banner names what moved rather than saying "something"


def test_the_re_run_carries_the_measurement_into_r1s_evidence(conn, unmeasured):
    _log_batch_ph(conn, unmeasured, 3.4)
    rerun = evaluations_store.run(conn, unmeasured)
    r1 = next(f for f in rerun.findings if f.rule_id == "R1")
    assert "3.4" in str(r1.evidence) or r1.evidence.get("recipe_ph") == 3.4


def test_the_most_recent_batch_measurement_is_the_one_used(conn, unmeasured):
    evaluation = evaluations_store.run(conn, unmeasured)
    trial_id = trials.create(conn, evaluation.id)
    trials.add_batch(conn, trial_id, measured_ph=3.9, ph_method="strip")
    trials.add_batch(conn, trial_id, measured_ph=3.2, ph_method="meter")
    context = formulations.hydrate_context(conn, unmeasured)
    assert context.latest_trial_ph.value == 3.2
