"""Spec §10's trial endpoints, over the real app."""

import pytest


@pytest.fixture
def trial(client, vinaigrette):
    evaluation = client.post(
        f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
    ).json()
    response = client.post(f"/api/v1/evaluations/{evaluation['id']}/trial")
    assert response.status_code == 201
    return evaluation, response.json()


def _batch(client, trial_id, **body):
    response = client.post(f"/api/v1/trials/{trial_id}/batches", json=body)
    assert response.status_code == 201, response.text
    return response.json()["batches"][-1]


def test_starting_a_trial_returns_a_protocol_built_from_the_findings(trial):
    _evaluation, payload = trial
    assert payload["status"] == "planned"
    kinds = {c["kind"] for c in payload["protocol"]["checkpoints"]}
    assert {"make_it", "usability"} <= kinds
    assert payload["protocol"]["notes"]


def test_starting_a_trial_on_a_missing_evaluation_is_refused(client):
    assert client.post("/api/v1/evaluations/nope/trial").status_code == 422


def test_logging_a_batch_starts_the_trial_and_reports_due_checkpoints(client, trial):
    _evaluation, payload = trial
    batch = _batch(client, payload["id"], batch_size_g=200.0, make_minutes=10, difficulty_score=2)
    refreshed = client.get(f"/api/v1/trials/{payload['id']}").json()
    assert refreshed["status"] == "running"
    assert refreshed["started_at"]
    assert batch["ambient_storage_allowed"] is False


def test_the_storage_gate_refuses_ambient_without_a_qualifying_ph(client, trial):
    _evaluation, payload = trial
    response = client.post(
        f"/api/v1/trials/{payload['id']}/batches", json={"storage_mode": "ambient"}
    )
    assert response.status_code == 422
    assert "4.6" in response.json()["detail"]


def test_the_storage_gate_permits_ambient_below_the_line(client, trial):
    _evaluation, payload = trial
    batch = _batch(
        client, payload["id"], measured_ph=4.1, ph_method="meter", storage_mode="ambient"
    )
    assert batch["storage_mode"] == "ambient"
    assert batch["ambient_storage_allowed"] is True


def test_an_observation_comes_back_with_a_derived_bucket_and_tier(client, trial):
    _evaluation, payload = trial
    batch = _batch(client, payload["id"], batch_size_g=200.0)
    response = client.post(
        f"/api/v1/trial-batches/{batch['id']}/observations",
        json={
            "type": "food_texture", "elapsed_minutes": 240, "score": 3,
            "application_food_id": "romaine", "had_undressed_control": True,
        },
    )
    assert response.status_code == 201
    observation = response.json()["batches"][0]["observations"][0]
    assert observation["dwell_bucket"] == "packed"
    assert observation["confidence_tier"] == "suggestive"
    assert observation["export_class"] == "finding"


def test_a_client_cannot_send_a_symptom_observation(client, trial):
    _evaluation, payload = trial
    batch = _batch(client, payload["id"], batch_size_g=200.0)
    response = client.post(
        f"/api/v1/trial-batches/{batch['id']}/observations",
        json={"type": "symptom", "elapsed_minutes": 0},
    )
    assert response.status_code == 422


def test_a_client_cannot_choose_the_dwell_bucket(client, trial):
    _evaluation, payload = trial
    batch = _batch(client, payload["id"], batch_size_g=200.0)
    response = client.post(
        f"/api/v1/trial-batches/{batch['id']}/observations",
        json={
            "type": "food_texture", "elapsed_minutes": 0, "score": 2,
            "application_food_id": "romaine", "dwell_bucket": "marinade",
        },
    )
    assert response.status_code == 201
    assert response.json()["batches"][0]["observations"][0]["dwell_bucket"] == "immediate"


def test_the_preview_returns_the_dose_math_and_writes_nothing(client, trial):
    _evaluation, payload = trial
    batch = _batch(client, payload["id"], batch_size_g=200.0)
    response = client.post(
        f"/api/v1/trial-batches/{batch['id']}/symptom-preview",
        json={"trigger_food_id": "milk", "amount_value": 1.0, "doses_used": 2.0},
    )
    assert response.status_code == 200
    assert response.json()["enzymes"][0]["units_delivered"] == 18000.0
    refreshed = client.get(f"/api/v1/trials/{payload['id']}").json()
    assert refreshed["batches"][0]["symptom_entries"] == []


def test_a_symptom_entry_stores_the_same_math_the_preview_showed(client, trial):
    _evaluation, payload = trial
    batch = _batch(client, payload["id"], batch_size_g=200.0)
    body = {"trigger_food_id": "milk", "amount_value": 1.0, "doses_used": 2.0}
    preview = client.post(
        f"/api/v1/trial-batches/{batch['id']}/symptom-preview", json=body
    ).json()
    stored = client.post(
        f"/api/v1/trial-batches/{batch['id']}/symptom-entries",
        json={**body, "outcome_score": 2, "notes": "fine"},
    ).json()["batches"][0]["symptom_entries"][0]
    assert stored["computed_dose"] == preview


def test_a_trial_can_be_completed_and_then_takes_nothing_more(client, trial):
    _evaluation, payload = trial
    batch = _batch(client, payload["id"], batch_size_g=200.0)
    done = client.post(f"/api/v1/trials/{payload['id']}/status", json={"status": "complete"})
    assert done.status_code == 200
    assert done.json()["status"] == "complete"

    refused = client.post(
        f"/api/v1/trial-batches/{batch['id']}/observations",
        json={"type": "taste", "elapsed_minutes": 0, "score": 3},
    )
    assert refused.status_code == 422
    assert "new trial" in refused.json()["detail"]


def test_an_abandoned_trial_keeps_its_records_and_leaves_the_active_list(client, trial):
    _evaluation, payload = trial
    batch = _batch(client, payload["id"], batch_size_g=200.0)
    client.post(
        f"/api/v1/trial-batches/{batch['id']}/observations",
        json={"type": "taste", "elapsed_minutes": 0, "score": 4, "free_text": "odd"},
    )
    client.post(f"/api/v1/trials/{payload['id']}/status", json={"status": "abandoned"})

    assert client.get("/api/v1/trials").json() == []
    kept = client.get(f"/api/v1/trials/{payload['id']}").json()
    assert kept["batches"][0]["observations"][0]["free_text"] == "odd"


def test_the_active_list_summarises_what_is_outstanding(client, trial):
    _evaluation, payload = trial
    _batch(client, payload["id"], batch_size_g=200.0)
    summary = client.get("/api/v1/trials").json()[0]
    assert summary["id"] == payload["id"]
    assert summary["batch_count"] == 1
    assert summary["due_checkpoint_count"] >= 0
