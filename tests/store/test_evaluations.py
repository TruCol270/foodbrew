import pytest

from foodbrew.db import create_database
from foodbrew.engine import evaluate
from foodbrew.engine.types import Verdict
from foodbrew.store import evaluations, formulations, recipes
from foodbrew.store.connection import connect
from foodbrew.store.snapshot import context_from_snapshot


@pytest.fixture
def conn(tmp_path):
    with connect(create_database(tmp_path / "foodbrew.db")) as c:
        yield c


@pytest.fixture
def formulation_id(conn):
    rid = recipes.create(conn, name="vinaigrette", notes="", ingredients=[
        {"food_id": "olive_oil", "amount_g": 100.0, "order": 1},
        {"food_id": "white_vinegar", "amount_g": 50.0, "order": 2},
    ])
    return formulations.create(
        conn, recipe_id=rid, format="premixed_wet",
        target_trigger_food_ids=["milk"], application_food_ids=["romaine"],
        dwell_profile=None,
        enzymes=[{"enzyme_id": "lactase_fungal_acid", "dose": 9000.0, "phase": "wet",
                  "encapsulated": False, "source_choice": ""}],
        serving_size_g=30.0, measured_ph=3.0,
        process_steps=[{"order": 1, "label": "whisk", "is_heat": False}],
        enzyme_addition_index=1, parent_formulation_id=None,
    )


def test_run_persists_an_evaluation_and_its_findings(conn, formulation_id):
    stored = evaluations.run(conn, formulation_id)
    assert stored.id
    assert stored.overall is Verdict.RED
    assert stored.display == "RED"
    assert stored.findings
    count = conn.execute(
        "SELECT COUNT(*) AS n FROM rule_finding WHERE evaluation_id = ?", (stored.id,)
    ).fetchone()["n"]
    assert count == len(stored.findings)


def test_read_returns_the_stored_result_without_re_running(conn, formulation_id):
    """Plan decision #5 — a stored evaluation is a record, not a recomputation."""
    stored = evaluations.run(conn, formulation_id)
    conn.execute("UPDATE rule_finding SET message = 'tampered' WHERE evaluation_id = ?",
                 (stored.id,))
    conn.commit()
    reread = evaluations.get(conn, stored.id)
    assert all(f.message == "tampered" for f in reread.findings)


def test_read_reconstructs_the_four_finding_groups(conn, formulation_id):
    stored = evaluations.run(conn, formulation_id)
    reread = evaluations.get(conn, stored.id)
    assert [f.rule_id for f in reread.blockers] == [f.rule_id for f in stored.blockers]
    assert [f.rule_id for f in reread.advisories] == [f.rule_id for f in stored.advisories]
    assert all(f.advisory for f in reread.advisories)


def test_the_stored_snapshot_reproduces_the_stored_verdict(conn, formulation_id):
    """Spec §4 — re-running the snapshot on the same engine version is identical."""
    stored = evaluations.run(conn, formulation_id)
    replayed = evaluate(context_from_snapshot(stored.input_snapshot_json))
    assert replayed.overall is stored.overall
    assert [f.message for f in replayed.findings] == [f.message for f in stored.findings]


def test_editing_a_source_record_never_mutates_a_stored_evaluation(conn, formulation_id):
    """Spec §4 and §13's property test, now across the database boundary."""
    stored = evaluations.run(conn, formulation_id)
    before = [(f.rule_id, f.verdict, f.message) for f in stored.findings]
    conn.execute(
        "UPDATE enzyme SET ph_min = 1.0, ph_shelf_stable_min = 1.0,"
        " ph_shelf_stable_min_status = 'confirmed' WHERE id = 'lactase_fungal_acid'"
    )
    conn.commit()

    reread = evaluations.get(conn, stored.id)
    assert [(f.rule_id, f.verdict, f.message) for f in reread.findings] == before
    replayed = evaluate(context_from_snapshot(reread.input_snapshot_json))
    assert replayed.overall is stored.overall


def test_evaluations_are_append_only(conn, formulation_id):
    first = evaluations.run(conn, formulation_id)
    second = evaluations.run(conn, formulation_id)
    assert first.id != second.id
    listed = evaluations.list_for_formulation(conn, formulation_id)
    assert [e.id for e in listed][0] == second.id
    assert len(listed) == 2


def test_the_envelope_round_trips(conn, formulation_id):
    stored = evaluations.run(conn, formulation_id)
    reread = evaluations.get(conn, stored.id)
    assert reread.envelope == stored.envelope


def test_get_returns_none_for_an_unknown_id(conn):
    assert evaluations.get(conn, "nope") is None
