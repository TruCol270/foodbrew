"""Spec §5.3, §3 Workflow E — the status machine and the storage gate, over real SQLite."""

import pytest

from foodbrew.engine import ValidationRejection
from foodbrew.engine.protocol import CheckpointKind
from foodbrew.store import evaluations as evaluations_store
from foodbrew.store import trials


@pytest.fixture
def evaluation(conn, vinaigrette_rows):
    return evaluations_store.run(conn, vinaigrette_rows["formulation_id"])


def test_a_new_trial_is_planned_and_carries_a_frozen_protocol(conn, evaluation):
    trial_id = trials.create(conn, evaluation.id)
    trial = trials.get(conn, trial_id)
    assert trial.status == trials.PLANNED
    assert trial.started_at is None
    assert trial.protocol.checkpoints
    assert CheckpointKind.MAKE_IT in {c.kind for c in trial.protocol.checkpoints}


def test_the_protocol_does_not_change_when_the_evaluation_is_re_run(
    conn, evaluation, vinaigrette_rows
):
    trial_id = trials.create(conn, evaluation.id)
    before = trials.get(conn, trial_id).protocol.to_json()
    conn.execute("UPDATE enzyme SET notes = 'edited' WHERE id = 'lactase_fungal_acid'")
    conn.commit()
    evaluations_store.run(conn, vinaigrette_rows["formulation_id"])
    assert trials.get(conn, trial_id).protocol.to_json() == before


def test_the_first_batch_starts_the_trial(conn, evaluation):
    trial_id = trials.create(conn, evaluation.id)
    trials.add_batch(conn, trial_id, batch_size_g=200.0, make_minutes=12, difficulty_score=2)
    trial = trials.get(conn, trial_id)
    assert trial.status == trials.RUNNING
    assert trial.started_at is not None
    assert len(trial.batches) == 1


def test_ambient_storage_without_a_measured_ph_is_refused(conn, evaluation):
    trial_id = trials.create(conn, evaluation.id)
    with pytest.raises(ValidationRejection) as exc:
        trials.add_batch(conn, trial_id, storage_mode="ambient")
    assert "4.6" in str(exc.value)


def test_ambient_storage_above_the_line_is_refused(conn, evaluation):
    trial_id = trials.create(conn, evaluation.id)
    with pytest.raises(ValidationRejection):
        trials.add_batch(conn, trial_id, measured_ph=5.2, ph_method="meter", storage_mode="ambient")


def test_ambient_storage_below_the_line_is_permitted(conn, evaluation):
    trial_id = trials.create(conn, evaluation.id)
    batch_id = trials.add_batch(
        conn, trial_id, measured_ph=4.1, ph_method="meter", storage_mode="ambient"
    )
    assert trials.get(conn, trial_id).batches[0].id == batch_id


def test_a_ph_reading_has_to_say_how_it_was_taken(conn, evaluation):
    trial_id = trials.create(conn, evaluation.id)
    with pytest.raises(ValidationRejection):
        trials.add_batch(conn, trial_id, measured_ph=4.1, ph_method="none")


def test_a_difficulty_score_off_the_scale_is_refused(conn, evaluation):
    trial_id = trials.create(conn, evaluation.id)
    with pytest.raises(ValidationRejection):
        trials.add_batch(conn, trial_id, difficulty_score=9)


@pytest.mark.parametrize("terminal", [trials.COMPLETE, trials.ABANDONED])
def test_a_terminal_trial_takes_no_more_batches_but_keeps_what_it_has(
    conn, evaluation, terminal
):
    trial_id = trials.create(conn, evaluation.id)
    trials.add_batch(conn, trial_id, batch_size_g=200.0)
    trials.set_status(conn, trial_id, terminal)

    with pytest.raises(ValidationRejection) as exc:
        trials.add_batch(conn, trial_id, batch_size_g=200.0)
    assert "new trial" in str(exc.value)
    assert len(trials.get(conn, trial_id).batches) == 1


def test_only_the_two_terminals_can_be_set_by_hand(conn, evaluation):
    trial_id = trials.create(conn, evaluation.id)
    with pytest.raises(ValidationRejection):
        trials.set_status(conn, trial_id, trials.RUNNING)


def test_a_terminal_trial_leaves_the_active_list(conn, evaluation):
    trial_id = trials.create(conn, evaluation.id)
    assert [t.id for t in trials.list_active(conn)] == [trial_id]
    trials.set_status(conn, trial_id, trials.ABANDONED)
    assert trials.list_active(conn) == ()


def test_elapsed_minutes_is_whole_minutes_and_never_negative():
    assert trials.elapsed_minutes(
        "2026-08-15T09:00:00+00:00", "2026-08-15T13:30:40+00:00"
    ) == 270
    assert trials.elapsed_minutes(
        "2026-08-15T09:00:00+00:00", "2026-08-15T08:00:00+00:00"
    ) == 0


def test_due_now_reports_reached_and_unanswered_checkpoints(conn, evaluation):
    trial_id = trials.create(conn, evaluation.id)
    trials.add_batch(conn, trial_id, batch_size_g=200.0)
    trial = trials.get(conn, trial_id)
    batch = trial.batches[0]
    due = trials.due_now(trial, batch, now=batch.made_at)
    assert all(c.due_elapsed_minutes == 0 for c in due)
    assert all(c.is_scheduled for c in due)
