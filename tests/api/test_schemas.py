from foodbrew.api import schemas
from foodbrew.engine.types import Tracked, TruthLabel


def test_tracked_serializes_as_value_status_source():
    """Plan decision #7 — a number never travels without its label."""
    out = schemas.TrackedOut.of(Tracked(2.5, TruthLabel.CONFIRMED, "KB Table B"))
    assert out.model_dump() == {
        "value": 2.5, "status": "confirmed", "source": "KB Table B"
    }


def test_tracked_of_none_is_an_unconfirmed_object_not_a_null():
    out = schemas.TrackedOut.of(Tracked(None, TruthLabel.UNCONFIRMED, ""))
    assert out.model_dump() == {"value": None, "status": "unconfirmed", "source": ""}


def test_recipe_create_rejects_a_blank_name():
    import pydantic
    import pytest

    with pytest.raises(pydantic.ValidationError):
        schemas.RecipeIn(name="   ", notes="", ingredients=[])


def test_custom_food_schema_has_no_status_field():
    """Plan decision #9 — a client cannot choose a truth label."""
    fields = set(schemas.CustomFoodIn.model_fields)
    assert not any("status" in f for f in fields)
