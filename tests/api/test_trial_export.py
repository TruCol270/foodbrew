"""§6.6's split and §13's report lint, over an exported trial."""

import pytest

from foodbrew.engine.language import contains_prohibited


@pytest.fixture
def exported(client, vinaigrette):
    def _run():
        # The seed leaves lactase's dose_evidence_threshold unconfirmed (§9.1),
        # so every dose line would read "could not be worked out". Enter one
        # through the M3 database editor FIRST — the founder's own route to a
        # usable value, stored `user_provided` — because plan decision #7 freezes
        # the dose math against the snapshot this evaluation is about to take.
        client.put(
            "/api/v1/enzymes/lactase_fungal_acid",
            json={"fields": {"dose_evidence_threshold": 6000.0}},
        )
        evaluation = client.post(
            f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
        ).json()
        return evaluation, client.get(f"/api/v1/export/{evaluation['id']}.md").text

    return _run


def _trial_with_everything(client, evaluation_id):
    trial = client.post(f"/api/v1/evaluations/{evaluation_id}/trial").json()
    batch = client.post(
        f"/api/v1/trials/{trial['id']}/batches",
        json={"batch_size_g": 200.0, "measured_ph": 3.4, "ph_method": "meter",
              "make_minutes": 12, "difficulty_score": 2},
    ).json()["batches"][0]
    client.post(
        f"/api/v1/trial-batches/{batch['id']}/observations",
        json={"type": "taste", "elapsed_minutes": 0, "score": 4,
              "free_text": "sharper than expected"},
    )
    client.post(
        f"/api/v1/trial-batches/{batch['id']}/observations",
        json={"type": "food_texture", "elapsed_minutes": 240, "score": 3,
              "application_food_id": "romaine", "had_undressed_control": True},
    )
    client.post(
        f"/api/v1/trial-batches/{batch['id']}/observations",
        json={"type": "food_texture", "elapsed_minutes": 1440, "score": 4,
              "application_food_id": "romaine"},
    )
    client.post(
        f"/api/v1/trial-batches/{batch['id']}/symptom-entries",
        json={"trigger_food_id": "milk", "amount_value": 1.0, "doses_used": 1.0,
              "outcome_score": 2, "notes": "no bloating"},
    )
    return trial


def test_before_a_trial_the_export_is_unchanged_from_m3(exported):
    _evaluation, body = exported()
    assert "No trial has been recorded for this formulation yet." in body


def test_the_exported_trial_splits_findings_observations_and_hypotheses(client, exported):
    evaluation, _body = exported()
    _trial_with_everything(client, evaluation["id"])
    body = client.get(f"/api/v1/export/{evaluation['id']}.md").text

    assert "### Findings" in body
    assert "> sharper than expected" in body           # taste — a finding
    assert "### Observations" in body                   # texture with no control
    assert "### Hypotheses for a food scientist to test" in body
    assert "evidence threshold" in body                 # dose math attached
    assert "> no bloating" in body


def test_the_exported_trial_reports_the_measured_ph_and_what_it_does(client, exported):
    evaluation, _body = exported()
    _trial_with_everything(client, evaluation["id"])
    body = client.get(f"/api/v1/export/{evaluation['id']}.md").text
    assert "Measured pH of the batch: 3.4" in body


def test_the_observed_column_appears_in_the_occasion_table(client, exported):
    evaluation, _body = exported()
    _trial_with_everything(client, evaluation["id"])
    body = client.get(f"/api/v1/export/{evaluation['id']}.md").text
    assert "| Occasion | Predicted | Observed |" in body
    assert "anecdote" in body or "suggestive" in body


def test_the_exported_trial_still_passes_the_report_lint(client, exported):
    evaluation, _body = exported()
    _trial_with_everything(client, evaluation["id"])
    body = client.get(f"/api/v1/export/{evaluation['id']}.md").text
    assert contains_prohibited(body) == ()


def test_an_abandoned_trial_says_so_in_the_export(client, exported):
    evaluation, _body = exported()
    trial = _trial_with_everything(client, evaluation["id"])
    client.post(f"/api/v1/trials/{trial['id']}/status", json={"status": "abandoned"})
    body = client.get(f"/api/v1/export/{evaluation['id']}.md").text
    assert "abandoned after" in body
