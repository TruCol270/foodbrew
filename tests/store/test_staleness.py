"""Spec §10 screen 4's banner, and plan decision #9."""

import json

from foodbrew.store import evaluations
from foodbrew.store.snapshot import diff_snapshots
from tests.store.test_variant_store import _vinaigrette


def test_an_untouched_evaluation_is_fresh(conn):
    stored = evaluations.run(conn, _vinaigrette(conn))
    assert evaluations.freshness(conn, stored) == (False, ())


def test_re_running_does_not_make_the_first_run_stale(conn):
    formulation_id = _vinaigrette(conn)
    first = evaluations.run(conn, formulation_id)
    evaluations.run(conn, formulation_id)
    assert evaluations.freshness(conn, first)[0] is False


def test_editing_a_referenced_enzyme_makes_it_stale_and_names_the_field(conn):
    stored = evaluations.run(conn, _vinaigrette(conn))
    conn.execute(
        "UPDATE enzyme SET ph_shelf_stable_min = 2.5,"
        " ph_shelf_stable_min_status = 'confirmed',"
        " ph_shelf_stable_min_source = 'supplier spec' WHERE id = 'lactase_fungal_acid'"
    )
    conn.commit()

    stale, changes = evaluations.freshness(conn, stored)
    assert stale
    assert [(c.kind, c.record_id, c.field) for c in changes] == [
        ("enzyme", "lactase_fungal_acid", "ph_shelf_stable_min")
    ]
    assert changes[0].after["value"] == 2.5


def test_editing_an_unreferenced_record_leaves_it_fresh(conn):
    """The snapshot holds the referenced closure, not the whole catalogue."""
    stored = evaluations.run(conn, _vinaigrette(conn))
    conn.execute("UPDATE enzyme SET notes = 'edited' WHERE id = 'amylase'")
    conn.commit()
    assert evaluations.freshness(conn, stored)[0] is False


def test_editing_a_referenced_food_is_caught(conn):
    stored = evaluations.run(conn, _vinaigrette(conn))
    conn.execute(
        "UPDATE food SET water_content_pct = 95.0,"
        " water_content_pct_status = 'user_provided' WHERE id = 'white_vinegar'"
    )
    conn.commit()
    stale, changes = evaluations.freshness(conn, stored)
    assert stale
    assert changes[0].record_id == "white_vinegar"


def test_the_diff_reports_an_added_record():
    empty = {"enzymes": {}, "foods": {}, "substrates": {}, "formulation": {}}
    added = {**empty, "enzymes": {"amylase": {"name": "Amylase"}}}
    changes = diff_snapshots(json.dumps(empty), json.dumps(added))
    assert (changes[0].kind, changes[0].record_id, changes[0].after) == (
        "enzyme", "amylase", "added"
    )


def test_two_identical_snapshots_report_nothing(conn):
    stored = evaluations.run(conn, _vinaigrette(conn))
    assert diff_snapshots(stored.input_snapshot_json, stored.input_snapshot_json) == ()
