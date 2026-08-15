"""Spec §5.3's two capture tables, over real SQLite."""

import json

import pytest

from foodbrew.engine import ValidationRejection
from foodbrew.engine.trial_rules import ConfidenceTier
from foodbrew.engine.types import DwellProfile
from foodbrew.store import evaluations as evaluations_store
from foodbrew.store import observations, trials


@pytest.fixture
def batch(conn, vinaigrette_rows):
    evaluation = evaluations_store.run(conn, vinaigrette_rows["formulation_id"])
    trial_id = trials.create(conn, evaluation.id)
    return trial_id, trials.add_batch(conn, trial_id, batch_size_g=200.0)


def test_the_server_derives_the_dwell_bucket_from_elapsed_minutes(conn, batch):
    _trial_id, batch_id = batch
    observations.add_observation(
        conn, batch_id, type="food_texture", elapsed_minutes=240,
        score=3, application_food_id="romaine",
    )
    row = conn.execute("SELECT dwell_bucket FROM trial_observation").fetchone()
    assert row["dwell_bucket"] == str(DwellProfile.PACKED)


def test_an_observation_reads_back_with_its_tier(conn, batch):
    _trial_id, batch_id = batch
    observations.add_observation(
        conn, batch_id, type="food_texture", elapsed_minutes=0, score=2,
        application_food_id="romaine", had_undressed_control=True,
    )
    record = observations.list_for_batch(conn, batch_id)[0]
    assert record.tier is ConfidenceTier.SUGGESTIVE
    assert record.dwell_bucket is DwellProfile.IMMEDIATE


def test_symptom_is_not_an_observation_type(conn, batch):
    _trial_id, batch_id = batch
    with pytest.raises(ValidationRejection) as exc:
        observations.add_observation(conn, batch_id, type="symptom", elapsed_minutes=0)
    assert "taste" in str(exc.value)


def test_a_texture_observation_has_to_name_the_food(conn, batch):
    _trial_id, batch_id = batch
    with pytest.raises(ValidationRejection):
        observations.add_observation(
            conn, batch_id, type="food_texture", elapsed_minutes=0, score=2
        )


def test_a_food_the_formulation_never_claimed_is_refused(conn, batch):
    # "milk" is real and referenced (it is the formulation's target trigger food,
    # so it is present in the frozen snapshot) but it is not an application food
    # (only "romaine" is) — unlike "cucumber", which is not referenced by this
    # formulation at all and so is frozen out of the snapshot entirely, tripping
    # the "Unknown food" branch instead of the one this test means to exercise.
    _trial_id, batch_id = batch
    with pytest.raises(ValidationRejection) as exc:
        observations.add_observation(
            conn, batch_id, type="food_texture", elapsed_minutes=0, score=2,
            application_food_id="milk",
        )
    assert "poured on" in str(exc.value)


def test_a_symptom_entry_freezes_the_dose_math(conn, batch):
    _trial_id, batch_id = batch
    entry_id = observations.add_symptom_entry(
        conn, batch_id, trigger_food_id="milk", amount_value=1.0,
        amount_unit="servings", doses_used=2.0, outcome_score=2, notes="fine",
    )
    stored = observations.symptoms_for_batch(conn, batch_id)[0]
    assert stored.id == entry_id
    assert stored.computed_dose["enzymes"][0]["units_delivered"] == 18000.0


def test_editing_the_threshold_afterwards_does_not_change_a_recorded_meal(conn, batch):
    _trial_id, batch_id = batch
    observations.add_symptom_entry(
        conn, batch_id, trigger_food_id="milk", amount_value=1.0, doses_used=1.0
    )
    before = observations.symptoms_for_batch(conn, batch_id)[0].computed_dose
    conn.execute(
        "UPDATE enzyme SET dose_evidence_threshold = 999999,"
        " dose_evidence_threshold_status = 'user_provided' WHERE id = 'lactase_fungal_acid'"
    )
    conn.commit()
    after = observations.symptoms_for_batch(conn, batch_id)[0].computed_dose
    assert json.dumps(after, sort_keys=True) == json.dumps(before, sort_keys=True)


def test_the_preview_matches_what_a_write_would_store_and_writes_nothing(conn, batch):
    _trial_id, batch_id = batch
    preview = observations.preview_symptom(
        conn, batch_id, trigger_food_id="milk", amount_value=1.0, doses_used=1.0
    )
    assert conn.execute("SELECT COUNT(*) c FROM trial_symptom_entry").fetchone()["c"] == 0

    observations.add_symptom_entry(
        conn, batch_id, trigger_food_id="milk", amount_value=1.0, doses_used=1.0
    )
    stored = observations.symptoms_for_batch(conn, batch_id)[0].computed_dose
    assert stored == preview.as_dict()


def test_a_terminal_trial_takes_no_observations_and_no_meals(conn, batch):
    trial_id, batch_id = batch
    trials.set_status(conn, trial_id, trials.COMPLETE)
    with pytest.raises(ValidationRejection):
        observations.add_observation(conn, batch_id, type="taste", elapsed_minutes=0, score=3)
    with pytest.raises(ValidationRejection):
        observations.add_symptom_entry(conn, batch_id, trigger_food_id="milk")


def test_recording_an_observation_never_touches_the_evaluation(conn, vinaigrette_rows):
    evaluation = evaluations_store.run(conn, vinaigrette_rows["formulation_id"])
    trial_id = trials.create(conn, evaluation.id)
    batch_id = trials.add_batch(conn, trial_id, batch_size_g=200.0)
    observations.add_observation(
        conn, batch_id, type="food_texture", elapsed_minutes=1440, score=5,
        application_food_id="romaine",
    )
    after = evaluations_store.get(conn, evaluation.id)
    assert after.overall is evaluation.overall
    assert after.envelope == evaluation.envelope
    assert [f.message for f in after.findings] == [f.message for f in evaluation.findings]
