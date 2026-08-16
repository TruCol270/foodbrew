"""Plan decision #1 — the first migration, and the boot check that needed it."""

import sqlite3

import pytest

from foodbrew.db import create_database, ensure_database
from foodbrew.db.bootstrap import MIGRATIONS, apply_migrations, missing_columns


def _columns(path, table):
    conn = sqlite3.connect(path)
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


def test_a_fresh_database_already_has_every_migrated_column(db_path):
    for table, column, _ddl in MIGRATIONS:
        assert column in _columns(db_path, table)


def test_applying_migrations_to_a_fresh_database_changes_nothing(db_path):
    conn = sqlite3.connect(db_path)
    try:
        assert apply_migrations(conn) == ()
    finally:
        conn.close()


def test_a_pre_migration_database_is_upgraded_on_boot(tmp_path):
    """The M1-M4 case: a real database whose food table predates the column."""
    path = create_database(tmp_path / "old.db")
    conn = sqlite3.connect(path)
    try:
        conn.execute("ALTER TABLE food DROP COLUMN allergens_json")
        conn.commit()
    finally:
        conn.close()
    assert "allergens_json" not in _columns(path, "food")

    ensure_database(path)
    assert "allergens_json" in _columns(path, "food")


def test_the_upgrade_preserves_the_rows_it_finds(tmp_path):
    path = create_database(tmp_path / "old.db")
    conn = sqlite3.connect(path)
    try:
        before = conn.execute("SELECT COUNT(*) FROM food").fetchone()[0]
        conn.execute("ALTER TABLE food DROP COLUMN allergens_json")
        conn.commit()
    finally:
        conn.close()

    ensure_database(path)
    conn = sqlite3.connect(path)
    try:
        after = conn.execute("SELECT COUNT(*) FROM food").fetchone()[0]
        defaulted = conn.execute(
            "SELECT COUNT(*) FROM food WHERE allergens_json = '[]'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert after == before > 0
    assert defaulted == after, "an added column takes its default on existing rows"


def test_migrating_twice_is_a_no_op(tmp_path):
    path = create_database(tmp_path / "twice.db")
    conn = sqlite3.connect(path)
    try:
        assert apply_migrations(conn) == ()
        assert apply_migrations(conn) == ()
        assert missing_columns(conn) == ()
    finally:
        conn.close()


def test_a_database_missing_a_table_still_fails_loudly(tmp_path):
    path = create_database(tmp_path / "broken.db")
    conn = sqlite3.connect(path)
    try:
        conn.execute("DROP TABLE trial_observation")
        conn.commit()
    finally:
        conn.close()
    with pytest.raises(ValueError) as exc:
        ensure_database(path)
    assert "trial_observation" in str(exc.value)
