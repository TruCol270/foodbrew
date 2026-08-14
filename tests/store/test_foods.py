import pytest

from foodbrew.db import create_database
from foodbrew.engine import ValidationRejection
from foodbrew.engine.types import TruthLabel
from foodbrew.store import foods
from foodbrew.store.connection import connect
from foodbrew.store.reference import load_catalog


@pytest.fixture
def conn(tmp_path):
    with connect(create_database(tmp_path / "foodbrew.db")) as c:
        yield c


def test_a_custom_food_is_stored_user_provided(conn):
    """Spec §10 screen 2 / plan decision #9 — no client may claim `confirmed`."""
    fid = foods.create_custom(
        conn, name="Nonna's ricotta", category="dairy",
        is_recipe_ingredient=True, is_trigger_food=True, is_application_food=False,
        ph=5.9, water_content_pct=72.0, typical_load_value=4.0, typical_load_unit="g lactose",
        contains_substrate_ids=["lactose"], structural=[], contains_protease=False,
        is_heat_processed=False, notes="",
    )
    food = load_catalog(conn).foods[fid]
    assert food.ph.status is TruthLabel.USER_PROVIDED
    assert food.water_content_pct.status is TruthLabel.USER_PROVIDED
    assert food.typical_load_value.status is TruthLabel.USER_PROVIDED
    assert food.ph.source


def test_an_omitted_value_stays_unconfirmed_rather_than_user_provided(conn):
    fid = foods.create_custom(
        conn, name="Mystery powder", category="other",
        is_recipe_ingredient=True, is_trigger_food=False, is_application_food=False,
        ph=None, water_content_pct=None, typical_load_value=None, typical_load_unit="",
        contains_substrate_ids=[], structural=[], contains_protease=False,
        is_heat_processed=False, notes="",
    )
    food = load_catalog(conn).foods[fid]
    assert food.ph.status is TruthLabel.UNCONFIRMED


def test_an_unknown_substrate_id_is_rejected(conn):
    with pytest.raises(ValidationRejection, match="substrate"):
        foods.create_custom(
            conn, name="x", category="", is_recipe_ingredient=True,
            is_trigger_food=False, is_application_food=False,
            ph=None, water_content_pct=None, typical_load_value=None, typical_load_unit="",
            contains_substrate_ids=["not_a_substrate"], structural=[],
            contains_protease=False, is_heat_processed=False, notes="",
        )


def test_a_food_with_no_role_is_rejected(conn):
    with pytest.raises(ValidationRejection, match="role"):
        foods.create_custom(
            conn, name="x", category="", is_recipe_ingredient=False,
            is_trigger_food=False, is_application_food=False,
            ph=None, water_content_pct=None, typical_load_value=None, typical_load_unit="",
            contains_substrate_ids=[], structural=[], contains_protease=False,
            is_heat_processed=False, notes="",
        )


def test_listing_filters_by_role(conn):
    ingredients = foods.list_by_role(conn, "recipe_ingredient")
    triggers = foods.list_by_role(conn, "trigger")
    applications = foods.list_by_role(conn, "application")
    assert all(f.is_recipe_ingredient for f in ingredients)
    assert all(f.is_trigger_food for f in triggers)
    assert all(f.is_application_food for f in applications)
    assert len(foods.list_by_role(conn, None)) >= len(ingredients)
