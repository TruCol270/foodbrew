from foodbrew.store import audit


def test_an_event_round_trips_with_both_sides(conn):
    audit.record(
        conn, action="update", entity="enzyme:lactase_fungal_acid",
        before={"ph_min": 2.5}, after={"ph_min": 3.0},
    )
    conn.commit()
    events = audit.list_recent(conn)
    assert len(events) == 1
    assert events[0].entity == "enzyme:lactase_fungal_acid"
    assert events[0].before == {"ph_min": 2.5}
    assert events[0].after == {"ph_min": 3.0}
    assert events[0].actor == "founder"


def test_recording_does_not_commit_on_its_own(db_path):
    """The trace and the change it describes are one transaction."""
    from foodbrew.store.connection import connect

    with connect(db_path) as writer:
        audit.record(writer, action="update", entity="food:milk")
        writer.rollback()

    with connect(db_path) as reader:
        assert audit.list_recent(reader) == ()


def test_the_newest_event_comes_first(conn):
    for n in range(3):
        audit.record(conn, action="update", entity=f"enzyme:e{n}")
    conn.commit()
    assert [e.entity for e in audit.list_recent(conn)][0] == "enzyme:e2"


def test_a_reset_records_no_after_side(conn):
    audit.record(conn, action="reset", entity="food:milk", before={"ph": 7.0})
    conn.commit()
    assert audit.list_recent(conn)[0].after is None
