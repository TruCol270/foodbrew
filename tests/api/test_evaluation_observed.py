"""Spec §6.3's Observed column and §13's "an observation never mutates a prediction"."""

import pytest


@pytest.fixture
def evaluated(client, vinaigrette):
    return client.post(
        f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
    ).json()


def _trial_with(client, evaluation_id, **observation):
    trial = client.post(f"/api/v1/evaluations/{evaluation_id}/trial").json()
    batch = client.post(
        f"/api/v1/trials/{trial['id']}/batches", json={"batch_size_g": 200.0}
    ).json()["batches"][0]
    if observation:
        client.post(f"/api/v1/trial-batches/{batch['id']}/observations", json=observation)
    return trial


def test_without_a_trial_the_observed_column_is_absent(client, evaluated):
    payload = client.get(f"/api/v1/evaluations/{evaluated['id']}").json()
    assert payload["observed"] is None
    assert payload["trial_ids"] == []


def test_an_observation_fills_its_bucket_and_leaves_the_others_empty(client, evaluated):
    _trial_with(
        client, evaluated["id"], type="food_texture", elapsed_minutes=240, score=4,
        application_food_id="romaine",
    )
    payload = client.get(f"/api/v1/evaluations/{evaluated['id']}").json()
    profiles = payload["observed"]["profiles"]
    assert profiles["packed"]["verdict"] == "red"
    assert profiles["packed"]["confidence_tier"] == "anecdote"
    assert profiles["immediate"]["verdict"] is None
    assert "convention" in payload["observed"]["scale_note"]


def test_the_observed_column_never_moves_the_headline_or_the_prediction(client, evaluated):
    before = client.get(f"/api/v1/evaluations/{evaluated['id']}").json()
    _trial_with(
        client, evaluated["id"], type="food_texture", elapsed_minutes=1440, score=5,
        application_food_id="romaine",
    )
    after = client.get(f"/api/v1/evaluations/{evaluated['id']}").json()
    assert after["headline"] == before["headline"]
    assert after["overall"] == before["overall"]
    assert after["envelope"] == before["envelope"]
    assert after["findings"] == before["findings"]


def test_a_trial_with_no_observations_still_lists_its_id(client, evaluated):
    trial = _trial_with(client, evaluated["id"])
    payload = client.get(f"/api/v1/evaluations/{evaluated['id']}").json()
    assert payload["trial_ids"] == [trial["id"]]
    assert all(p["verdict"] is None for p in payload["observed"]["profiles"].values())
