import pytest
from fastapi.testclient import TestClient

from foodbrew.api.app import create_app
from foodbrew.api.settings import Settings
from foodbrew.store import formulations, recipes


@pytest.fixture
def client(db_path, tmp_path):
    app = create_app(Settings(db_path=db_path, web_dist=tmp_path / "no-web-build"))
    with TestClient(app) as c:
        yield c


@pytest.fixture
def vinaigrette(conn):
    """A recipe and formulation matching golden fixture (a): pH 3.0, wet, lactase."""
    recipe_id = recipes.create(conn, name="vinaigrette", notes="", ingredients=[
        {"food_id": "olive_oil", "amount_g": 100.0, "order": 1},
        {"food_id": "white_vinegar", "amount_g": 50.0, "order": 2},
    ])
    formulation_id = formulations.create(
        conn, recipe_id=recipe_id, format="premixed_wet",
        target_trigger_food_ids=["milk"], application_food_ids=["romaine"],
        dwell_profile=None,
        enzymes=[{"enzyme_id": "lactase_fungal_acid", "dose": 9000.0, "phase": "wet",
                  "encapsulated": False, "source_choice": ""}],
        serving_size_g=30.0, measured_ph=3.0,
        process_steps=[{"order": 1, "label": "whisk", "is_heat": False}],
        enzyme_addition_index=1, parent_formulation_id=None,
    )
    return {"recipe_id": recipe_id, "formulation_id": formulation_id}
