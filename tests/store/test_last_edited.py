"""Decisions #5 and #3 — history without a column, and an honest banner."""

from foodbrew.store import audit, records


def test_an_untouched_record_has_no_last_edited(conn):
    assert audit.last_edited_for(conn, "enzyme").get("lactase_fungal_acid") is None


def test_an_edit_stamps_that_record_only(conn):
    records.update(conn, "enzyme", "lactase_fungal_acid", {"ph_shelf_stable_min": 3.2})
    edits = audit.last_edited_for(conn, "enzyme")
    assert edits["lactase_fungal_acid"]
    assert "inulinase" not in edits


def test_the_newest_edit_wins(conn):
    records.update(conn, "enzyme", "lactase_fungal_acid", {"ph_shelf_stable_min": 3.2})
    first = audit.last_edited_for(conn, "enzyme")["lactase_fungal_acid"]
    records.update(conn, "enzyme", "lactase_fungal_acid", {"ph_shelf_stable_min": 3.4})
    second = audit.last_edited_for(conn, "enzyme")["lactase_fungal_acid"]
    assert second >= first


def test_a_global_reset_does_not_pretend_to_be_a_per_record_edit(conn):
    records.reset_all(conn)
    assert audit.last_edited_for(conn, "enzyme") == {}


def test_a_record_edited_then_reset_keeps_its_history(conn):
    """Reset-to-baseline is itself an edit of that record, so it stamps it."""
    records.update(conn, "enzyme", "lactase_fungal_acid", {"ph_shelf_stable_min": 3.2})
    records.reset_record(conn, "enzyme", "lactase_fungal_acid")
    assert audit.last_edited_for(conn, "enzyme")["lactase_fungal_acid"]


def test_a_global_reset_erases_an_earlier_edits_last_edited_too(conn):
    """A record touched before a *global* reset is back at its shipped value
    after it, same as every other row `reset_all` overwrites — it must not
    go on claiming the founder's pre-reset edit still stands."""
    records.update(conn, "enzyme", "lactase_fungal_acid", {"ph_shelf_stable_min": 3.2})
    records.reset_all(conn)
    assert audit.last_edited_for(conn, "enzyme").get("lactase_fungal_acid") is None


def test_an_added_field_is_reported_as_an_upgrade_not_an_edit(conn, vinaigrette_rows):
    import json

    from foodbrew.store import evaluations as evaluations_store
    from foodbrew.store.snapshot import diff_snapshots

    stored = evaluations_store.run(conn, vinaigrette_rows["formulation_id"])
    old = json.loads(stored.input_snapshot_json)
    for food in old["foods"].values():
        food.pop("allergens", None)

    changes = diff_snapshots(json.dumps(old, sort_keys=True), stored.input_snapshot_json)
    assert changes
    assert all(c.kind == "field_added" for c in changes if c.field == "allergens")
