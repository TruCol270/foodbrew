"""Decision #4 over real SQLite — the §15 item 4 answer, recorded in product."""

import json

import pytest

from foodbrew.engine import ValidationRejection
from foodbrew.store import records


def _entries(conn, enzyme_id):
    row = conn.execute(
        "SELECT degrades_structural_json FROM enzyme WHERE id = ?", (enzyme_id,)
    ).fetchone()
    return json.loads(row["degrades_structural_json"])


def test_inulinase_can_be_moved_off_unconfirmed(conn):
    """Spec §15 item 4: the answer has an in-product home now."""
    before = _entries(conn, "inulinase")
    assert any(e["tier"] == "unconfirmed" for e in before)

    records.update_structured(
        conn, "enzyme", "inulinase", "degrades_structural_json",
        [{"structural_class": "pectin_cellulose", "tier": "gradual"}],
    )
    after = _entries(conn, "inulinase")
    assert after == [{"structural_class": "pectin_cellulose", "tier": "gradual"}]


def test_the_edit_is_audited(conn):
    records.update_structured(
        conn, "enzyme", "inulinase", "degrades_structural_json",
        [{"structural_class": "pectin_cellulose", "tier": "gradual"}],
    )
    row = conn.execute(
        "SELECT * FROM audit_event WHERE entity = 'enzyme:inulinase' ORDER BY id DESC"
    ).fetchone()
    assert row is not None
    assert "gradual" in row["after_json"]


def test_an_illegal_tier_is_refused_before_anything_is_written(conn):
    before = _entries(conn, "inulinase")
    with pytest.raises(ValidationRejection):
        records.update_structured(
            conn, "enzyme", "inulinase", "degrades_structural_json",
            [{"structural_class": "pectin_cellulose", "tier": "quick"}],
        )
    assert _entries(conn, "inulinase") == before


def test_a_scalar_field_cannot_be_written_through_the_structured_door(conn):
    with pytest.raises(ValidationRejection):
        records.update_structured(conn, "enzyme", "inulinase", "ph_min", [])


def test_a_structured_field_cannot_be_written_through_the_scalar_door(conn):
    with pytest.raises(ValidationRejection):
        records.update(conn, "enzyme", "inulinase", {"degrades_structural_json": "[]"})


def test_the_change_reaches_r15_on_the_next_evaluation(conn, vinaigrette_rows):
    """The whole point: a confirmed tier changes what the envelope can say."""
    from foodbrew.store import evaluations as evaluations_store

    records.update_structured(
        conn, "enzyme", "lactase_fungal_acid", "degrades_structural_json",
        [{"structural_class": "pectin_cellulose", "tier": "gradual"}],
    )
    rerun = evaluations_store.run(conn, vinaigrette_rows["formulation_id"])
    r15 = [f for f in rerun.findings if f.rule_id == "R15"]
    assert r15, "R15 now has an intersection to report"
