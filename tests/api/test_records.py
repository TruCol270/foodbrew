"""Workflow D over HTTP."""


def _enzyme(client, enzyme_id="lactase_fungal_acid"):
    return next(e for e in client.get("/api/v1/enzymes").json() if e["id"] == enzyme_id)


def test_an_edit_is_stored_as_the_founder_s_own_value(client):
    response = client.put(
        "/api/v1/enzymes/lactase_fungal_acid",
        json={"fields": {"ph_shelf_stable_min": 3.4}},
    )
    assert response.status_code == 200
    field = response.json()["ph_shelf_stable_min"]
    assert (field["value"], field["status"]) == (3.4, "user_provided")
    assert field["source"] == "entered by founder"


def test_a_client_cannot_reach_a_status_column_through_the_editor(client):
    """Plan decision #16 — the allowlist is what stops this, not the schema."""
    # lactase_fungal_acid's seeded ph_min is already confirmed (KB Table B), so
    # the invariant under test is "the rejected write changed nothing", not
    # "the status isn't confirmed" — which would be trivially true regardless.
    before = _enzyme(client)["ph_min"]
    response = client.put(
        "/api/v1/enzymes/lactase_fungal_acid",
        json={"fields": {"ph_min_status": "confirmed"}},
    )
    assert response.status_code == 422
    assert _enzyme(client)["ph_min"] == before


def test_an_unknown_field_is_refused_in_plain_english(client):
    response = client.put(
        "/api/v1/enzymes/lactase_fungal_acid", json={"fields": {"nonsense": 1}}
    )
    assert response.status_code == 422
    assert "cannot be edited" in response.json()["detail"]


def test_an_unknown_record_is_refused(client):
    response = client.put("/api/v1/enzymes/nope", json={"fields": {"notes": "x"}})
    assert response.status_code == 422


def test_a_food_edit_round_trips(client):
    response = client.put("/api/v1/foods/milk", json={"fields": {"ph": 6.7}})
    assert response.json()["ph"]["value"] == 6.7


def test_reset_puts_the_shipped_value_back(client):
    before = _enzyme(client)["ph_min"]
    client.put("/api/v1/enzymes/lactase_fungal_acid", json={"fields": {"ph_min": 1.0}})
    restored = client.post("/api/v1/enzymes/lactase_fungal_acid/reset").json()
    assert restored["ph_min"] == before


def test_resetting_a_custom_food_is_refused(client):
    created = client.post(
        "/api/v1/foods",
        json={"name": "Her base", "is_recipe_ingredient": True, "ph": 3.1},
    ).json()
    response = client.post(f"/api/v1/foods/{created['id']}/reset")
    assert response.status_code == 422
    assert "no baseline" in response.json()["detail"]


def test_the_global_reset_discards_every_edit(client):
    client.put("/api/v1/enzymes/lactase_fungal_acid", json={"fields": {"ph_min": 1.0}})
    client.put("/api/v1/foods/milk", json={"fields": {"ph": 1.0}})
    assert client.post("/api/v1/reference/reset").status_code == 204
    assert _enzyme(client)["ph_min"]["value"] != 1.0


def test_every_change_shows_up_in_the_audit_feed(client):
    client.put("/api/v1/enzymes/lactase_fungal_acid", json={"fields": {"notes": "asked Amano"}})
    feed = client.get("/api/v1/audit").json()
    assert feed[0]["action"] == "update"
    assert feed[0]["entity"] == "enzyme:lactase_fungal_acid"


def test_an_edit_makes_an_existing_evaluation_stale(client, vinaigrette):
    original = client.post(
        f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
    ).json()
    client.put(
        "/api/v1/enzymes/lactase_fungal_acid", json={"fields": {"ph_shelf_stable_min": 2.5}}
    )
    assert client.get(f"/api/v1/evaluations/{original['id']}").json()["stale"] is True
