"""Decision #2 and #3 — allergens survive every boundary they cross."""

import json

import pytest
from fastapi.testclient import TestClient

from foodbrew.api.app import create_app
from foodbrew.api.settings import Settings
from foodbrew.engine.allergens import Allergen
from foodbrew.store import snapshot
from foodbrew.store.rowmap import food_from_row, food_to_row


# tests/api/conftest.py's `client` fixture is scoped to tests/api/ and is not
# visible here — this file lives in tests/store/, so the fixture is redefined
# locally rather than reaching across suite boundaries.
@pytest.fixture
def client(db_path, tmp_path):
    app = create_app(Settings(db_path=db_path, web_dist=tmp_path / "no-web-build"))
    with TestClient(app) as c:
        yield c


def test_the_seed_carries_the_dairy_and_wheat_declarations(seed):
    assert Allergen.MILK.value in seed.foods["yogurt"].allergens
    assert Allergen.WHEAT.value in seed.foods["croutons"].allergens
    assert Allergen.EGG.value in seed.foods["mayonnaise"].allergens
    assert Allergen.FISH.value in seed.foods["canned_tuna"].allergens


def test_a_food_with_no_allergen_record_has_an_empty_tuple(seed):
    assert seed.foods["olive_oil"].allergens == ()


def test_nuts_seeds_is_left_unrecorded_rather_than_guessed(seed):
    """A generic nut/seed entry could be tree nut, peanut or sesame; the seed
    declines to choose and the report reports it as a gap."""
    assert seed.foods["nuts_seeds"].allergens == ()


def test_the_row_round_trip_preserves_allergens(conn, seed):
    row_dict = food_to_row(seed.foods["yogurt"])
    assert json.loads(row_dict["allergens_json"]) == ["milk"]

    conn.execute("DELETE FROM food WHERE id = 'yogurt'")
    cols = ", ".join(f'"{c}"' for c in row_dict)
    placeholders = ", ".join("?" for _ in row_dict)
    conn.execute(f"INSERT INTO food ({cols}) VALUES ({placeholders})", tuple(row_dict.values()))
    conn.commit()

    back = food_from_row(conn.execute("SELECT * FROM food WHERE id = 'yogurt'").fetchone())
    assert back.allergens == ("milk",)


def test_the_snapshot_round_trip_preserves_allergens(conn, vinaigrette_rows):
    from foodbrew.store import evaluations as evaluations_store

    stored = evaluations_store.run(conn, vinaigrette_rows["formulation_id"])
    payload = json.loads(stored.input_snapshot_json)
    milk = payload["foods"]["milk"]
    assert milk["allergens"] == ["milk"]

    ctx = snapshot.context_from_snapshot(stored.input_snapshot_json)
    assert ctx.foods["milk"].allergens == ("milk",)


def test_a_pre_m5_snapshot_without_the_key_still_thaws(conn, vinaigrette_rows):
    """Decision #3 — every evaluation that ran before M5 must still open."""
    from foodbrew.store import evaluations as evaluations_store

    stored = evaluations_store.run(conn, vinaigrette_rows["formulation_id"])
    payload = json.loads(stored.input_snapshot_json)
    for food in payload["foods"].values():
        food.pop("allergens", None)

    ctx = snapshot.context_from_snapshot(json.dumps(payload, sort_keys=True))
    assert ctx.foods["milk"].allergens == ()


def test_the_api_serialises_allergens(client):
    foods = client.get("/api/v1/foods").json()
    yogurt = next(f for f in foods if f["id"] == "yogurt")
    assert yogurt["allergens"] == ["milk"]


def test_a_custom_food_cannot_declare_an_unknown_allergen(client):
    response = client.post(
        "/api/v1/foods",
        json={"name": "Test dressing base", "allergens": ["dairy"]},
    )
    assert response.status_code == 422
    assert "dairy" in response.json()["detail"]
