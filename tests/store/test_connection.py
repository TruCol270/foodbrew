import sqlite3

import pytest

from foodbrew.db import create_database
from foodbrew.store.clock import now_iso
from foodbrew.store.connection import connect
from foodbrew.store.ids import new_id


def test_foreign_keys_are_enforced_on_every_connection(tmp_path):
    # schema.sql's own PRAGMA applies only to the connection that ran it, so a
    # fresh connection must set it again or every FK in the schema is decorative.
    db = create_database(tmp_path / "foodbrew.db")
    with connect(db) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO recipe_ingredient (recipe_id, food_id, amount_g)"
                " VALUES ('nope', 'also-nope', 1.0)"
            )


def test_rows_are_addressable_by_column_name(tmp_path):
    db = create_database(tmp_path / "foodbrew.db")
    with connect(db) as conn:
        row = conn.execute("SELECT id, name FROM enzyme LIMIT 1").fetchone()
    assert row["id"]
    assert row["name"]


def test_connection_closes_on_exit(tmp_path):
    db = create_database(tmp_path / "foodbrew.db")
    with connect(db) as conn:
        pass
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_new_id_is_unique_and_urlsafe():
    ids = {new_id() for _ in range(500)}
    assert len(ids) == 500
    assert all(i.isalnum() for i in ids)


def test_now_iso_is_utc_and_sortable():
    a, b = now_iso(), now_iso()
    assert a.endswith("+00:00")
    assert a <= b
