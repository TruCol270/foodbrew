def test_enzymes_are_listed_with_truth_labels(client):
    body = client.get("/api/v1/enzymes").json()
    assert len(body) == 12
    lactase = next(e for e in body if e["id"] == "lactase_fungal_acid")
    assert lactase["ph_min"] == {
        "value": 2.5, "status": "confirmed",
        "source": lactase["ph_min"]["source"],
    }
    assert lactase["ph_shelf_stable_min"]["status"] == "unconfirmed"


def test_foods_can_be_filtered_by_role(client):
    triggers = client.get("/api/v1/foods", params={"role": "trigger"}).json()
    assert triggers and all(f["is_trigger_food"] for f in triggers)
    everything = client.get("/api/v1/foods").json()
    assert len(everything) >= len(triggers)


def test_an_unknown_role_is_rejected(client):
    assert client.get("/api/v1/foods", params={"role": "nonsense"}).status_code == 422


def test_substrates_and_gi_model_are_available(client):
    assert len(client.get("/api/v1/substrates").json()) == 12
    regions = client.get("/api/v1/gi-model").json()
    assert [r["id"] for r in regions][0] == "mouth"
    assert any(r["dormant"] for r in regions)


def test_a_custom_food_is_created_user_provided_and_appears_in_the_catalog(client):
    created = client.post("/api/v1/foods", json={
        "name": "Nonna's ricotta", "category": "dairy",
        "is_recipe_ingredient": True, "is_trigger_food": True,
        "ph": 5.9, "water_content_pct": 72.0,
        "contains_substrate_ids": ["lactose"],
    })
    assert created.status_code == 201
    body = created.json()
    assert body["ph"]["status"] == "user_provided"
    listed = client.get("/api/v1/foods", params={"role": "trigger"}).json()
    assert body["id"] in {f["id"] for f in listed}


def test_a_custom_food_with_no_role_is_refused(client):
    response = client.post("/api/v1/foods", json={"name": "x"})
    assert response.status_code == 422
    assert "role" in response.json()["detail"]
