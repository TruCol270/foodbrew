def _payload(recipe_id, **overrides):
    body = {
        "recipe_id": recipe_id, "format": "premixed_wet",
        "target_trigger_food_ids": ["milk"], "application_food_ids": ["romaine"],
        "dwell_profile": None,
        "enzymes": [{"enzyme_id": "lactase_fungal_acid", "dose": 9000.0, "phase": "wet"}],
        "serving_size_g": 30.0, "measured_ph": 3.0,
        "process_steps": [{"order": 1, "label": "whisk", "is_heat": False}],
        "enzyme_addition_index": 1,
    }
    body.update(overrides)
    return body


def test_create_and_read_a_formulation(client, vinaigrette):
    created = client.post("/api/v1/formulations", json=_payload(vinaigrette["recipe_id"]))
    assert created.status_code == 201
    body = created.json()
    assert body["measured_ph"] == {
        "value": 3.0, "status": "user_provided", "source": body["measured_ph"]["source"]
    }
    fetched = client.get(f"/api/v1/formulations/{body['id']}").json()
    assert fetched["enzymes"][0]["enzyme_id"] == "lactase_fungal_acid"


def test_proposed_enzymes_cover_the_selected_trigger_foods(client, vinaigrette):
    proposed = client.get(
        "/api/v1/proposed-enzymes",
        params={"trigger_food_ids": ["milk"], "format": "dry_sachet"},
    ).json()
    assert any(s["enzyme_id"].startswith("lactase") for s in proposed)
    assert all(s["phase"] == "dry" for s in proposed)


def test_no_enzyme_is_ever_proposed_for_a_polyol_food(client):
    """Spec §6.2 R14 — polyols get a stated gap, never a suggested enzyme."""
    foods = client.get("/api/v1/foods", params={"role": "trigger"}).json()
    substrates = {s["id"]: s for s in client.get("/api/v1/substrates").json()}
    polyol_foods = [
        f["id"] for f in foods
        if any(substrates[s]["no_commercial_enzyme"] for s in f["contains_substrate_ids"])
    ]
    assert polyol_foods
    proposed = client.get(
        "/api/v1/proposed-enzymes",
        params={"trigger_food_ids": polyol_foods, "format": "dry_sachet"},
    ).json()
    enzymes = {e["id"]: e for e in client.get("/api/v1/enzymes").json()}
    for selection in proposed:
        substrate_id = enzymes[selection["enzyme_id"]]["substrate_id"]
        assert substrates[substrate_id]["no_commercial_enzyme"] is False


def test_zero_enzymes_and_zero_trigger_foods_is_refused(client, vinaigrette):
    response = client.post("/api/v1/formulations", json=_payload(
        vinaigrette["recipe_id"], enzymes=[], target_trigger_food_ids=[]
    ))
    assert response.status_code == 422
    assert "trigger food or enzyme" in response.json()["detail"]


def test_an_unknown_enzyme_is_refused(client, vinaigrette):
    response = client.post("/api/v1/formulations", json=_payload(
        vinaigrette["recipe_id"], enzymes=[{"enzyme_id": "nope", "phase": "dry"}]
    ))
    assert response.status_code == 422


def test_an_out_of_range_ph_is_refused_by_the_schema(client, vinaigrette):
    response = client.post("/api/v1/formulations", json=_payload(
        vinaigrette["recipe_id"], measured_ph=99.0
    ))
    assert response.status_code == 422


def test_an_unknown_formulation_is_404(client):
    assert client.get("/api/v1/formulations/nope").status_code == 404
