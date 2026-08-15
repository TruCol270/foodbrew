"""Workflow D, and plan decisions #7, #8 and #16."""

import pytest

from foodbrew.engine import ValidationRejection
from foodbrew.store import audit, foods, records
from foodbrew.store.reference import load_catalog


def _enzyme(conn, enzyme_id="lactase_fungal_acid"):
    return load_catalog(conn).enzymes[enzyme_id]


def test_a_founder_edit_is_user_provided_not_confirmed(conn):
    records.update(conn, "enzyme", "lactase_fungal_acid", {"ph_shelf_stable_min": 3.4})
    field = _enzyme(conn).ph_shelf_stable_min
    assert (field.value, field.status.value) == (3.4, "user_provided")
    assert field.source == "entered by founder"


def test_clearing_a_value_returns_it_to_unconfirmed(conn):
    records.update(conn, "enzyme", "lactase_fungal_acid", {"ph_shelf_stable_min": 3.4})
    records.update(conn, "enzyme", "lactase_fungal_acid", {"ph_shelf_stable_min": None})
    field = _enzyme(conn).ph_shelf_stable_min
    assert (field.value, field.status.value, field.source) == (None, "unconfirmed", "")


def test_a_boolean_tracked_field_survives_the_round_trip(conn):
    records.update(conn, "enzyme", "lactase_fungal_acid", {"is_gras": "yes"})
    assert _enzyme(conn).is_gras.value is True


def test_a_plain_field_carries_no_label(conn):
    records.update(conn, "enzyme", "lactase_fungal_acid", {"supplier_note": "Amano quote 08/26"})
    assert _enzyme(conn).supplier_note == "Amano quote 08/26"


def test_clearing_a_note_empties_it_rather_than_writing_the_word_none(conn):
    records.update(conn, "enzyme", "lactase_fungal_acid", {"supplier_note": "Amano quote"})
    records.update(conn, "enzyme", "lactase_fungal_acid", {"supplier_note": None})
    assert _enzyme(conn).supplier_note == ""


@pytest.mark.parametrize("table, field", [
    ("enzyme", "id"),
    ("enzyme", "substrate_id"),
    ("enzyme", "ph_min_status"),
    ("food", "is_trigger_food"),
    ("food", "id"),
])
def test_fields_outside_the_allowlist_are_refused(conn, table, field):
    with pytest.raises(ValidationRejection):
        records.update(conn, table, "lactase_fungal_acid" if table == "enzyme" else "milk",
                       {field: "x"})


def test_an_unknown_table_is_refused(conn):
    with pytest.raises(ValidationRejection):
        records.update(conn, "evaluation", "anything", {"notes": "x"})


def test_a_non_numeric_value_is_refused_in_plain_english(conn):
    with pytest.raises(ValidationRejection) as excinfo:
        records.update(conn, "enzyme", "lactase_fungal_acid", {"ph_min": "acidic"})
    assert "enter a number" in str(excinfo.value)


def test_every_edit_leaves_an_audit_event(conn):
    # 6.7 is deliberately milk's own seeded pH (spec §9.3, every seeded food pH
    # is unconfirmed): the number does not move, but the status/source do, so
    # the audit row still has to differ before vs. after on the whole record.
    records.update(conn, "food", "milk", {"ph": 6.7})
    event = audit.list_recent(conn)[0]
    assert (event.action, event.entity) == ("update", "food:milk")
    assert event.before != event.after
    assert event.before["ph_status"] != event.after["ph_status"]


def test_reset_restores_the_shipped_value_and_its_label(conn):
    original = _enzyme(conn).ph_min
    records.update(conn, "enzyme", "lactase_fungal_acid", {"ph_min": 1.0})
    records.reset_record(conn, "enzyme", "lactase_fungal_acid")
    assert _enzyme(conn).ph_min == original
    assert audit.list_recent(conn)[0].action == "reset"


def test_a_custom_food_has_no_baseline_to_reset_to(conn):
    food_id = foods.create_custom(
        conn, name="Her vinaigrette base", category="", is_recipe_ingredient=True,
        is_trigger_food=False, is_application_food=False, ph=3.1, water_content_pct=60.0,
        typical_load_value=None, typical_load_unit="", contains_substrate_ids=[],
        structural=[], contains_protease=False, is_heat_processed=False, notes="",
    )
    with pytest.raises(ValidationRejection) as excinfo:
        records.reset_record(conn, "food", food_id)
    assert "no baseline" in str(excinfo.value)


def test_reset_all_discards_every_edit(conn):
    records.update(conn, "enzyme", "lactase_fungal_acid", {"ph_min": 1.0})
    records.update(conn, "food", "milk", {"ph": 1.0})
    records.reset_all(conn)
    catalog = load_catalog(conn)
    assert catalog.enzymes["lactase_fungal_acid"].ph_min.value != 1.0
    assert catalog.foods["milk"].ph.value != 1.0
    assert audit.list_recent(conn)[0].action == "reset_all"


def test_set_confirmed_needs_a_citation(conn):
    with pytest.raises(ValidationRejection):
        records.set_confirmed(conn, "enzyme", "lactase_fungal_acid", "temp_max_c", 55.0, "  ")


def test_set_confirmed_records_the_citation_as_the_source(conn):
    records.set_confirmed(
        conn, "enzyme", "lactase_fungal_acid", "temp_max_c", 55.0, "Amano datasheet 2026"
    )
    conn.commit()
    field = _enzyme(conn).temp_max_c
    assert (field.value, field.status.value, field.source) == (
        55.0, "confirmed", "Amano datasheet 2026"
    )


def test_a_plain_field_cannot_be_confirmed(conn):
    """Only a tracked field has a paired source column to record the citation in."""
    with pytest.raises(ValidationRejection):
        records.set_confirmed(conn, "enzyme", "lactase_fungal_acid", "notes", "x", "a source")
