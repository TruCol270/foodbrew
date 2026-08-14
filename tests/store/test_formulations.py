import pytest

from foodbrew.db import create_database
from foodbrew.engine import ValidationRejection, evaluate
from foodbrew.engine.types import DwellProfile, Format, Phase, TruthLabel
from foodbrew.store import formulations, recipes
from foodbrew.store.connection import connect


@pytest.fixture
def conn(tmp_path):
    with connect(create_database(tmp_path / "foodbrew.db")) as c:
        yield c


@pytest.fixture
def recipe_id(conn):
    return recipes.create(conn, name="vinaigrette", notes="", ingredients=[
        {"food_id": "olive_oil", "amount_g": 100.0, "order": 1},
        {"food_id": "white_vinegar", "amount_g": 50.0, "order": 2},
    ])


def _create(conn, recipe_id, **overrides):
    payload = dict(
        recipe_id=recipe_id, format="premixed_wet",
        target_trigger_food_ids=["milk"], application_food_ids=["romaine"],
        dwell_profile=None,
        enzymes=[{"enzyme_id": "lactase_fungal_acid", "dose": 9000.0, "phase": "wet",
                  "encapsulated": False, "source_choice": ""}],
        serving_size_g=30.0, measured_ph=3.0,
        process_steps=[{"order": 1, "label": "whisk", "is_heat": False}],
        enzyme_addition_index=1, parent_formulation_id=None,
    )
    payload.update(overrides)
    return formulations.create(conn, **payload)


def test_create_and_read_a_formulation(conn, recipe_id):
    fid = _create(conn, recipe_id)
    stored = formulations.get(conn, fid)
    assert stored.format is Format.PREMIXED_WET
    assert stored.enzymes[0].enzyme_id == "lactase_fungal_acid"
    assert stored.enzymes[0].phase is Phase.WET
    assert stored.measured_ph.status is TruthLabel.USER_PROVIDED
    assert stored.dwell_profile is None


def test_a_declared_dwell_profile_round_trips(conn, recipe_id):
    fid = _create(conn, recipe_id, dwell_profile="marinade")
    assert formulations.get(conn, fid).dwell_profile is DwellProfile.MARINADE


def test_an_unknown_enzyme_id_is_rejected(conn, recipe_id):
    with pytest.raises(ValidationRejection, match="enzyme"):
        _create(conn, recipe_id, enzymes=[{"enzyme_id": "nope", "dose": None,
                                           "phase": "dry", "encapsulated": False,
                                           "source_choice": ""}])


def test_zero_enzymes_and_zero_trigger_foods_is_rejected(conn, recipe_id):
    """Spec §6.2 R14 — rejected at validation, no evaluation created."""
    with pytest.raises(ValidationRejection, match="trigger food or enzyme"):
        _create(conn, recipe_id, enzymes=[], target_trigger_food_ids=[])


def test_hydrate_builds_a_context_the_engine_can_evaluate(conn, recipe_id):
    fid = _create(conn, recipe_id)
    ctx = formulations.hydrate_context(conn, fid)
    assert ctx.formulation.id == fid
    assert [i.food_id for i in ctx.formulation.recipe] == ["olive_oil", "white_vinegar"]
    assert evaluate(ctx).display in {"RED", "GRAY", "AMBER", "GREEN"}


def test_hydrated_context_reproduces_golden_fixture_a(conn, recipe_id):
    """Spec §13 (a): wet vinaigrette, pH 3.0, fungal lactase → RED via R1."""
    fid = _create(conn, recipe_id, measured_ph=3.0)
    result = evaluate(formulations.hydrate_context(conn, fid))
    r1 = [f for f in result.findings if f.rule_id == "R1"]
    assert any(f.verdict == "red" for f in r1)
    assert result.display == "RED"


def test_hydration_picks_up_the_latest_trial_batch_ph(conn, recipe_id):
    """Spec §6.7 step 2 / plan decision #8 — M4 writes these rows; hydration reads them now."""
    fid = _create(conn, recipe_id, measured_ph=None)
    conn.execute(
        "INSERT INTO evaluation (id, formulation_id, engine_version, input_snapshot_json,"
        " overall_flag, occasion_envelope_json, created_at)"
        " VALUES ('e1', ?, '1.0.0', '{}', 'amber', '{}', '2026-08-14T00:00:00+00:00')",
        (fid,),
    )
    conn.execute(
        "INSERT INTO trial (id, evaluation_id, protocol_json, status)"
        " VALUES ('t1', 'e1', '{}', 'running')"
    )
    conn.execute(
        "INSERT INTO trial_batch (id, trial_id, made_at, measured_ph, ph_method)"
        " VALUES ('b1', 't1', '2026-08-14T01:00:00+00:00', 4.1, 'meter')"
    )
    conn.commit()

    ctx = formulations.hydrate_context(conn, fid)
    assert ctx.latest_trial_ph.value == 4.1
    assert ctx.latest_trial_ph.status is TruthLabel.OBSERVED


def test_hydration_returns_no_trial_ph_when_no_trial_exists(conn, recipe_id):
    fid = _create(conn, recipe_id, measured_ph=None)
    assert formulations.hydrate_context(conn, fid).latest_trial_ph is None
