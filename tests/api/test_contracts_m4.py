"""M4's boundaries, asserted rather than reviewed."""

import pathlib

import pytest

from foodbrew.api import schemas
from foodbrew.engine.language import contains_prohibited

SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "foodbrew"
ENGINE = SRC / "engine"


def _python_files(root):
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def test_no_engine_module_reads_a_clock():
    """Plan decision #14 — time enters the engine as an argument."""
    offenders = []
    for path in _python_files(ENGINE):
        text = path.read_text(encoding="utf-8")
        for needle in ("now_iso", "datetime.now", "time.time", "utcnow"):
            if needle in text:
                offenders.append(f"{path.name}: {needle}")
    assert not offenders, ", ".join(offenders)


def test_no_engine_module_imports_the_store_or_the_api():
    offenders = []
    for path in _python_files(ENGINE):
        text = path.read_text(encoding="utf-8")
        needles = ("foodbrew.store", "foodbrew.api", "foodbrew.db", "import sqlite3", "fastapi")
        for needle in needles:
            if needle in text:
                offenders.append(f"{path.name}: {needle}")
    assert not offenders, ", ".join(offenders)


def test_no_store_module_imports_the_api():
    offenders = [
        p.name
        for p in _python_files(SRC / "store")
        if "fastapi" in p.read_text(encoding="utf-8")
        or "foodbrew.api" in p.read_text(encoding="utf-8")
    ]
    assert not offenders, ", ".join(offenders)


@pytest.mark.parametrize("field", ["dwell_bucket", "confidence_tier", "export_class"])
def test_no_request_schema_lets_a_client_supply_a_derived_value(field):
    """Plan decision #2 — derived facts are derived on the server."""
    offenders = [
        name
        for name, model in vars(schemas).items()
        if isinstance(model, type)
        and issubclass(model, schemas.BaseModel)
        and name.endswith("In")
        and field in model.model_fields
    ]
    assert not offenders, ", ".join(offenders)


def test_no_request_schema_accepts_a_symptom_observation():
    """Plan decision #6 — one door for symptoms, and the schema is the lock."""
    assert "symptom" not in str(schemas.ObservationIn.model_fields["type"].annotation)


def test_only_the_two_terminal_statuses_are_settable():
    """Plan decision #12."""
    annotation = str(schemas.TrialStatusIn.model_fields["status"].annotation)
    assert "complete" in annotation and "abandoned" in annotation
    assert "planned" not in annotation and "running" not in annotation


def test_no_trial_endpoint_writes_to_an_evaluation_table():
    """Plan decision #10 — the router that serves trials cannot touch a prediction."""
    text = (SRC / "api" / "routers" / "trials.py").read_text(encoding="utf-8")
    for statement in ("UPDATE evaluation", "UPDATE rule_finding", "INSERT INTO evaluation"):
        assert statement not in text


def test_no_prohibited_word_appears_in_m4_source_copy():
    """M3's api-source lint, extended to the two new store modules and the router."""
    offenders = []
    for path in (
        SRC / "api" / "routers" / "trials.py",
        SRC / "store" / "trials.py",
        SRC / "store" / "observations.py",
        ENGINE / "protocol.py",
        ENGINE / "observations.py",
        ENGINE / "symptoms.py",
    ):
        for word in contains_prohibited(path.read_text(encoding="utf-8")):
            offenders.append(f"{path.name}: {word}")
    assert not offenders, ", ".join(offenders)
