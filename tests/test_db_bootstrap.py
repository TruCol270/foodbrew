import sqlite3

import pytest

from foodbrew.db import ensure_database
from foodbrew.db.bootstrap import EXPECTED_TABLES, create_database
from foodbrew.store.connection import connect


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "test.db"
    create_database(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def test_every_spec_table_exists(db):
    rows = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    names = {r["name"] for r in rows}
    assert EXPECTED_TABLES <= names


def test_seed_is_loaded_on_bootstrap(db):
    assert db.execute("SELECT COUNT(*) c FROM enzyme").fetchone()["c"] == 12
    assert db.execute("SELECT COUNT(*) c FROM substrate").fetchone()["c"] == 12
    assert db.execute("SELECT COUNT(*) c FROM gi_region").fetchone()["c"] == 6
    assert db.execute("SELECT COUNT(*) c FROM food").fetchone()["c"] == 53


def test_truth_labels_survive_the_round_trip(db):
    row = db.execute(
        "SELECT temp_min_c_status, ph_min_status FROM enzyme WHERE id='lactase_fungal_acid'"
    ).fetchone()
    assert row["temp_min_c_status"] == "unconfirmed"
    assert row["ph_min_status"] == "confirmed"


def test_foreign_keys_are_enforced(db):
    db.execute("PRAGMA foreign_keys = ON")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO recipe_ingredient (recipe_id, food_id, amount_g) "
                   "VALUES ('nope', 'also_nope', 1.0)")


def test_bootstrap_is_idempotent(tmp_path):
    path = tmp_path / "twice.db"
    create_database(path)
    create_database(path)
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT COUNT(*) FROM enzyme").fetchone()[0] == 12
    conn.close()


def test_ensure_database_creates_a_missing_database(tmp_path):
    path = tmp_path / "foodbrew.db"
    ensure_database(path)
    with connect(path) as conn:
        count = conn.execute("SELECT COUNT(*) AS n FROM enzyme").fetchone()["n"]
    assert count == 12


def test_ensure_database_preserves_edits_to_an_existing_database(tmp_path):
    """Plan decision #1: a restart must not revert the founder's edits."""
    path = tmp_path / "foodbrew.db"
    ensure_database(path)
    with connect(path) as conn:
        conn.execute(
            "UPDATE enzyme SET temp_min_c = 20.0, temp_min_c_status = 'user_provided'"
            " WHERE id = 'lactase_fungal_acid'"
        )
        conn.commit()

    ensure_database(path)  # a second boot

    with connect(path) as conn:
        row = conn.execute(
            "SELECT temp_min_c, temp_min_c_status FROM enzyme WHERE id = 'lactase_fungal_acid'"
        ).fetchone()
    assert row["temp_min_c"] == 20.0
    assert row["temp_min_c_status"] == "user_provided"


def test_create_database_still_refreshes_reference_data(tmp_path):
    """The destructive path is kept deliberately — it is M3's reset-to-baseline."""
    path = tmp_path / "foodbrew.db"
    create_database(path)
    with connect(path) as conn:
        conn.execute("UPDATE enzyme SET temp_min_c = 20.0 WHERE id = 'lactase_fungal_acid'")
        conn.commit()

    create_database(path)

    with connect(path) as conn:
        row = conn.execute(
            "SELECT temp_min_c FROM enzyme WHERE id = 'lactase_fungal_acid'"
        ).fetchone()
    assert row["temp_min_c"] is None


def test_ensure_database_raises_on_a_file_missing_tables(tmp_path):
    path = tmp_path / "not-a-foodbrew.db"
    sqlite3.connect(path).close()
    with pytest.raises(ValueError, match="schema"):
        ensure_database(path)
