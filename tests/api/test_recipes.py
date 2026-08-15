def _payload(**overrides):
    body = {
        "name": "House vinaigrette", "notes": "",
        "ingredients": [
            {"food_id": "olive_oil", "amount_g": 100.0, "order": 1},
            {"food_id": "garlic_fresh", "amount_g": 5.0, "order": 2},
        ],
    }
    body.update(overrides)
    return body


def test_create_read_update_and_list(client):
    created = client.post("/api/v1/recipes", json=_payload())
    assert created.status_code == 201
    recipe_id = created.json()["id"]

    fetched = client.get(f"/api/v1/recipes/{recipe_id}").json()
    assert fetched["name"] == "House vinaigrette"
    assert [i["food_id"] for i in fetched["ingredients"]] == ["olive_oil", "garlic_fresh"]

    client.put(f"/api/v1/recipes/{recipe_id}", json=_payload(name="Renamed"))
    assert client.get(f"/api/v1/recipes/{recipe_id}").json()["name"] == "Renamed"

    assert recipe_id in {r["id"] for r in client.get("/api/v1/recipes").json()}


def test_the_substrate_summary_names_what_the_recipe_itself_carries(client):
    """Spec §10 screen 2 — "this recipe itself contains: GOS (garlic)…"."""
    recipe_id = client.post("/api/v1/recipes", json=_payload()).json()["id"]
    summary = client.get(f"/api/v1/recipes/{recipe_id}/substrate-summary").json()
    rows = {row["substrate_id"]: row for row in summary}
    assert "inulin_fructan" in rows
    assert rows["inulin_fructan"]["from_food_names"] == ["Garlic (fresh)"]
    assert rows["inulin_fructan"]["is_prebiotic"] is True


def test_an_empty_recipe_is_refused_with_a_plain_english_message(client):
    response = client.post("/api/v1/recipes", json=_payload(ingredients=[]))
    assert response.status_code == 422
    assert response.json()["detail"] == "Add at least one ingredient to this recipe."


def test_an_unknown_food_is_refused(client):
    response = client.post("/api/v1/recipes", json=_payload(
        ingredients=[{"food_id": "unicorn_tears", "amount_g": 1.0, "order": 1}]
    ))
    assert response.status_code == 422
    assert "unicorn_tears" in response.json()["detail"]


def test_a_negative_amount_is_refused_by_the_schema(client):
    response = client.post("/api/v1/recipes", json=_payload(
        ingredients=[{"food_id": "olive_oil", "amount_g": -5.0, "order": 1}]
    ))
    assert response.status_code == 422


def test_updating_an_unknown_recipe_is_404(client):
    assert client.put("/api/v1/recipes/nope", json=_payload()).status_code == 404
