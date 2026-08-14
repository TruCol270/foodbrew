import pytest

from foodbrew.db import create_database
from foodbrew.engine import ValidationRejection
from foodbrew.store import recipes
from foodbrew.store.connection import connect


@pytest.fixture
def conn(tmp_path):
    db = create_database(tmp_path / "foodbrew.db")
    with connect(db) as c:
        yield c


def test_create_and_read_a_recipe(conn):
    rid = recipes.create(conn, name="House vinaigrette", notes="", ingredients=[
        {"food_id": "olive_oil", "amount_g": 100.0, "order": 1},
        {"food_id": "white_vinegar", "amount_g": 50.0, "order": 2},
    ])
    stored = recipes.get(conn, rid)
    assert stored.name == "House vinaigrette"
    assert [i.food_id for i in stored.ingredients] == ["olive_oil", "white_vinegar"]
    assert stored.created_at


def test_ingredients_come_back_in_order(conn):
    rid = recipes.create(conn, name="r", notes="", ingredients=[
        {"food_id": "white_vinegar", "amount_g": 1.0, "order": 9},
        {"food_id": "olive_oil", "amount_g": 1.0, "order": 2},
    ])
    assert [i.order for i in recipes.get(conn, rid).ingredients] == [2, 9]


def test_a_recipe_with_no_ingredients_is_rejected(conn):
    """Spec §6.7 — rejected at validation, not evaluated (plan decision #3)."""
    with pytest.raises(ValidationRejection, match="at least one ingredient"):
        recipes.create(conn, name="empty", notes="", ingredients=[])


def test_an_unknown_food_id_is_rejected(conn):
    with pytest.raises(ValidationRejection, match="no_such_food"):
        recipes.create(conn, name="r", notes="", ingredients=[
            {"food_id": "no_such_food", "amount_g": 1.0, "order": 1},
        ])


def test_a_negative_amount_is_rejected(conn):
    with pytest.raises(ValidationRejection, match="amount"):
        recipes.create(conn, name="r", notes="", ingredients=[
            {"food_id": "olive_oil", "amount_g": -1.0, "order": 1},
        ])


def test_update_replaces_the_ingredient_list(conn):
    rid = recipes.create(conn, name="r", notes="", ingredients=[
        {"food_id": "olive_oil", "amount_g": 100.0, "order": 1},
    ])
    recipes.update(conn, rid, name="r2", notes="n", ingredients=[
        {"food_id": "white_vinegar", "amount_g": 20.0, "order": 1},
    ])
    stored = recipes.get(conn, rid)
    assert stored.name == "r2"
    assert [i.food_id for i in stored.ingredients] == ["white_vinegar"]


def test_get_returns_none_for_an_unknown_id(conn):
    assert recipes.get(conn, "nope") is None


def test_list_is_newest_first(conn):
    a = recipes.create(conn, name="a", notes="", ingredients=[
        {"food_id": "olive_oil", "amount_g": 1.0, "order": 1}])
    b = recipes.create(conn, name="b", notes="", ingredients=[
        {"food_id": "olive_oil", "amount_g": 1.0, "order": 1}])
    listed = [r.id for r in recipes.list_all(conn)]
    assert listed.index(b) <= listed.index(a)
