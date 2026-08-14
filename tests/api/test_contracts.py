"""Cross-cutting contracts. These are the API-layer equivalents of M1's
tests/engine/test_purity.py: cheap, global, and hard to violate by accident.
"""

import pathlib

import pytest

from foodbrew.api import schemas

#: Spec §10 — prohibited in engine output, report, and anything the founder reads.
PROHIBITED = ("safe", "validated", "guaranteed", "clinically proven", "proven", "demonstrated")

TRACKED_KEYS = {"value", "status", "source"}
VALID_STATUSES = {"confirmed", "unconfirmed", "user_provided", "calculated", "observed"}
SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "foodbrew"


def _tracked_objects(node):
    """Yield every dict that looks like a Tracked triple, at any depth."""
    if isinstance(node, dict):
        if set(node) == TRACKED_KEYS:
            yield node
        for value in node.values():
            yield from _tracked_objects(value)
    elif isinstance(node, list):
        for item in node:
            yield from _tracked_objects(item)


@pytest.fixture
def evaluated(client, vinaigrette):
    return client.post(
        f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
    ).json()


def test_every_tracked_value_on_the_wire_carries_a_valid_status(client, evaluated):
    payloads = [
        evaluated,
        client.get("/api/v1/enzymes").json(),
        client.get("/api/v1/foods").json(),
    ]
    seen = 0
    for payload in payloads:
        for tracked in _tracked_objects(payload):
            assert tracked["status"] in VALID_STATUSES
            seen += 1
    assert seen > 50, "the sweep found suspiciously few tracked values"


def test_no_numeric_enzyme_field_is_serialized_bare(client):
    """Plan decision #7 — a bare float would strand the number from its label."""
    enzyme = next(e for e in client.get("/api/v1/enzymes").json() if e["id"] == "lactase_fungal_acid")
    for field in ("ph_min", "ph_max", "ph_shelf_stable_min", "dose_min", "is_gras"):
        assert isinstance(enzyme[field], dict)
        assert set(enzyme[field]) == TRACKED_KEYS


def test_no_prohibited_word_appears_in_any_engine_or_api_message(evaluated):
    for finding in evaluated["findings"]:
        lowered = finding["message"].lower()
        for word in PROHIBITED:
            assert word not in lowered, f"{finding['rule_id']}: '{word}' in message"


def test_no_prohibited_word_appears_in_api_source_copy():
    """Catches a banned word typed into a docstring, error string, or title."""
    for path in (SRC / "api").rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        for word in PROHIBITED:
            assert word not in text, f"{path.name}: '{word}'"


def test_the_store_layer_never_imports_the_api_layer():
    for path in (SRC / "store").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "foodbrew.api" not in text, f"{path.name} imports the API layer"
        assert "fastapi" not in text, f"{path.name} imports FastAPI"


def test_the_engine_never_imports_the_store_or_api_layers():
    for path in (SRC / "engine").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for forbidden in ("foodbrew.store", "foodbrew.api", "foodbrew.db", "fastapi", "sqlite3"):
            assert forbidden not in text, f"{path.name} imports {forbidden}"


def test_no_schema_lets_a_client_choose_a_truth_label():
    for name in dir(schemas):
        model = getattr(schemas, name)
        fields = getattr(model, "model_fields", None)
        if not fields or name.endswith("Out") or name == "TrackedOut":
            continue
        assert not any("status" in f for f in fields), f"{name} exposes a status field"
