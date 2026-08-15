"""Cross-cutting contracts M3 introduces. Cheap, global, and hard to violate by
accident — the same shape as M2's test_contracts.py.
"""

import pathlib

import pytest

from foodbrew.api import schemas
from foodbrew.engine.patch import PatchOp

SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "foodbrew"


def test_no_request_schema_accepts_a_patch():
    """Plan decision #2 — the server applies only what its own engine wrote."""
    banned = {"patch", "patch_json", "ops"}
    for name in dir(schemas):
        model = getattr(schemas, name)
        fields = getattr(model, "model_fields", None)
        if not fields or name.endswith("Out"):
            continue
        assert not (banned & set(fields)), f"{name} accepts a patch from the client"


def test_the_engine_still_imports_no_storage_or_transport():
    """M3 adds five engine modules; the M1 boundary has to survive all of them."""
    for path in (SRC / "engine").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for forbidden in ("foodbrew.store", "foodbrew.api", "foodbrew.db", "fastapi", "sqlite3"):
            assert forbidden not in text, f"{path.name} imports {forbidden}"


def test_the_store_layer_still_imports_no_transport():
    for path in (SRC / "store").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "foodbrew.api" not in text, f"{path.name} imports the API layer"
        assert "fastapi" not in text, f"{path.name} imports FastAPI"


@pytest.mark.parametrize("op", list(PatchOp))
def test_every_patch_op_is_reachable_from_the_engine_not_from_a_route(op):
    """A route that named an op directly would be building patches by hand."""
    for path in (SRC / "api").rglob("*.py"):
        assert op.value not in path.read_text(encoding="utf-8"), f"{path.name} names {op.value}"


def test_no_prohibited_word_appears_in_any_m3_api_source():
    """M2's substring lint, restated because M3 adds four router modules."""
    from foodbrew.engine.language import PROHIBITED_WORDS

    for path in (SRC / "api").rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        for word in PROHIBITED_WORDS:
            assert word not in text, f"{path.name}: '{word}'"


def test_a_suggestion_is_never_offered_without_a_way_to_read_it(client, vinaigrette):
    evaluation = client.post(
        f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
    ).json()
    for suggestion in evaluation["suggestions"]:
        assert suggestion["description"].strip()
        assert suggestion["raised_by"]


def test_an_evaluation_payload_still_carries_valid_labels_everywhere(client, vinaigrette):
    """M3 adds `changes`, whose before/after can hold whole tracked objects."""
    from tests.api.test_contracts import VALID_STATUSES, _tracked_objects

    evaluation = client.post(
        f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
    ).json()
    for tracked in _tracked_objects(evaluation):
        assert tracked["status"] in VALID_STATUSES
