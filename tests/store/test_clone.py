"""Plan decision #15 — applying a variant is append-only."""

import pytest

from foodbrew.engine import ValidationRejection
from foodbrew.engine.patch import set_format
from foodbrew.engine.types import Format, Phase
from foodbrew.store import evaluations, formulations
from tests.store.test_variant_store import _vinaigrette


def test_the_clone_carries_the_patch_and_names_its_parent(conn):
    source_id = _vinaigrette(conn)
    clone_id = formulations.clone_with_patch(conn, source_id, set_format(Format.DRY_SACHET))

    clone = formulations.get(conn, clone_id)
    assert clone.format is Format.DRY_SACHET
    assert clone.enzymes[0].phase is Phase.DRY
    assert clone.parent_formulation_id == source_id


def test_the_source_is_untouched(conn):
    source_id = _vinaigrette(conn)
    before = formulations.get(conn, source_id)
    formulations.clone_with_patch(conn, source_id, set_format(Format.DRY_SACHET))
    assert formulations.get(conn, source_id) == before


def test_an_evaluation_of_the_source_is_untouched(conn):
    source_id = _vinaigrette(conn)
    original = evaluations.run(conn, source_id)
    clone_id = formulations.clone_with_patch(conn, source_id, set_format(Format.DRY_SACHET))
    clone_result = evaluations.run(conn, clone_id)

    reread = evaluations.get(conn, original.id)
    assert reread.overall == original.overall
    assert clone_result.overall != original.overall


def test_the_clone_keeps_the_recipe_and_the_measured_pH(conn):
    source_id = _vinaigrette(conn)
    clone_id = formulations.clone_with_patch(conn, source_id, set_format(Format.DRY_SACHET))
    source, clone = formulations.get(conn, source_id), formulations.get(conn, clone_id)
    assert clone.recipe == source.recipe
    assert clone.measured_ph == source.measured_ph


def test_a_patch_the_engine_would_refuse_never_creates_a_row(conn):
    source_id = _vinaigrette(conn, target_trigger_food_ids=[])
    before = conn.execute("SELECT COUNT(*) AS n FROM formulation").fetchone()["n"]
    with pytest.raises(ValidationRejection):
        formulations.clone_with_patch(conn, source_id, {"ops": [
            {"op": "remove_enzyme", "enzyme_id": "lactase_fungal_acid"},
        ]})
    assert conn.execute("SELECT COUNT(*) AS n FROM formulation").fetchone()["n"] == before


def test_an_unknown_formulation_is_refused(conn):
    with pytest.raises(ValidationRejection):
        formulations.clone_with_patch(conn, "nope", set_format(Format.DRY_SACHET))
