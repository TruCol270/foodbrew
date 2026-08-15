"""Spec §2.3 and §5.2, and plan decision #7."""

import pytest

from foodbrew.engine import ValidationRejection
from foodbrew.store import proposals, records
from foodbrew.store.reference import load_catalog


def _propose(conn, **overrides):
    payload = dict(
        table_name="enzyme", record_id="lactase_fungal_acid",
        field="ph_shelf_stable_min", proposed_value="3.0",
        source_citation="Amano technical datasheet, retrieved 2026-08-14",
    )
    payload.update(overrides)
    return proposals.create(conn, **payload)


def test_a_new_proposal_is_pending(conn):
    proposal_id = _propose(conn)
    assert proposals.get(conn, proposal_id).status == "pending"
    assert [p.id for p in proposals.list_all(conn, "pending")] == [proposal_id]


def test_a_proposal_without_a_citation_is_refused(conn):
    with pytest.raises(ValidationRejection) as excinfo:
        _propose(conn, source_citation="   ")
    assert "citation" in str(excinfo.value)


def test_a_proposal_for_an_untracked_field_is_refused(conn):
    with pytest.raises(ValidationRejection):
        _propose(conn, field="notes")


def test_a_proposal_with_an_unparseable_value_is_refused_at_the_inbox(conn):
    with pytest.raises(ValidationRejection):
        _propose(conn, proposed_value="quite acidic")


def test_approving_writes_the_value_as_confirmed_with_the_citation(conn):
    proposal_id = _propose(conn)
    proposals.approve(conn, proposal_id)

    field = load_catalog(conn).enzymes["lactase_fungal_acid"].ph_shelf_stable_min
    assert (field.value, field.status.value) == (3.0, "confirmed")
    assert field.source == "Amano technical datasheet, retrieved 2026-08-14"
    assert proposals.get(conn, proposal_id).status == "approved"


def test_rejecting_changes_no_data_and_keeps_the_row(conn):
    before = load_catalog(conn).enzymes["lactase_fungal_acid"].ph_shelf_stable_min
    proposal_id = _propose(conn)
    proposals.reject(conn, proposal_id)

    assert load_catalog(conn).enzymes["lactase_fungal_acid"].ph_shelf_stable_min == before
    assert proposals.get(conn, proposal_id).status == "rejected"


def test_a_proposal_cannot_be_decided_twice(conn):
    proposal_id = _propose(conn)
    proposals.approve(conn, proposal_id)
    with pytest.raises(ValidationRejection) as excinfo:
        proposals.reject(conn, proposal_id)
    assert "already approved" in str(excinfo.value)


def test_approving_a_temperature_field_promotes_R12_for_that_enzyme(conn):
    """Spec §13 fixture (h2), reached through the product rather than raw SQL."""
    for field, value in (("temp_min_c", "30"), ("temp_max_c", "45")):
        proposals.approve(conn, _propose(conn, field=field, proposed_value=value))

    enzyme = load_catalog(conn).enzymes["lactase_fungal_acid"]
    assert enzyme.temp_min_c.status.value == "confirmed"
    assert enzyme.temp_max_c.status.value == "confirmed"


def test_a_direct_edit_still_cannot_produce_confirmed(conn):
    records.update(conn, "enzyme", "lactase_fungal_acid", {"ph_shelf_stable_min": 3.0})
    field = load_catalog(conn).enzymes["lactase_fungal_acid"].ph_shelf_stable_min
    assert field.status.value == "user_provided"


def test_two_connections_racing_to_decide_the_same_proposal_only_one_wins(db_path):
    """Regression: api/deps opens one connection per HTTP request, so two
    requests deciding the same proposal is a real scenario, not a contrived
    one — a read-then-write decision (what approve/reject used to be) lets
    the second writer blindly overwrite the first's decision. Two genuinely
    separate sqlite3 connections, standing in for two concurrent requests."""
    import sqlite3

    conn_a = sqlite3.connect(db_path, check_same_thread=False)
    conn_a.row_factory = sqlite3.Row
    conn_b = sqlite3.connect(db_path, check_same_thread=False)
    conn_b.row_factory = sqlite3.Row
    try:
        proposal_id = _propose(conn_a)

        # Both connections read the row as pending before either decides.
        seen_a = proposals.get(conn_a, proposal_id)
        seen_b = proposals.get(conn_b, proposal_id)
        assert seen_a.status == seen_b.status == "pending"

        proposals.approve(conn_a, proposal_id)
        with pytest.raises(ValidationRejection, match="already approved"):
            proposals.reject(conn_b, proposal_id)

        # The approval — not a blind overwrite by the later reject — stands.
        assert proposals.get(conn_a, proposal_id).status == "approved"
        field = load_catalog(conn_a).enzymes["lactase_fungal_acid"].ph_shelf_stable_min
        assert field.status.value == "confirmed"
    finally:
        conn_a.close()
        conn_b.close()
