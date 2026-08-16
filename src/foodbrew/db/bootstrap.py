"""Create the SQLite database and populate reference tables from seed JSON."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from foodbrew.seedload.loader import Seed, load_seed
from foodbrew.store.rowmap import (
    enzyme_to_row,
    food_to_row,
    gi_region_to_row,
    substrate_to_row,
)

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

EXPECTED_TABLES = frozenset({
    "substrate", "enzyme", "food", "gi_region", "recipe", "recipe_ingredient",
    "formulation", "evaluation", "rule_finding", "variant_suggestion", "trial",
    "trial_batch", "trial_observation", "trial_symptom_entry", "proposal", "audit_event",
})

#: Ordered, additive migrations. Each entry is (table, column, DDL fragment).
#:
#: `CREATE TABLE IF NOT EXISTS` is a no-op against a table that already exists,
#: so schema.sql alone cannot add a column to a database created by an earlier
#: milestone — it would boot clean and then fail on the first write. Every entry
#: here is applied with ALTER TABLE ... ADD COLUMN when PRAGMA table_info says
#: the column is absent, which makes the whole list idempotent: applying it to a
#: fresh database created from schema.sql is a no-op, and applying it twice is a
#: no-op. Columns are only ever ADDED. A migration that drops or retypes a
#: column is a different problem and this list is deliberately unable to express
#: one (plan decision #1).
MIGRATIONS: tuple[tuple[str, str, str], ...] = (
    ("food", "allergens_json", "TEXT NOT NULL DEFAULT '[]'"),
)


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def apply_migrations(conn: sqlite3.Connection) -> tuple[str, ...]:
    """Add any missing column from MIGRATIONS. Returns what it added."""
    applied: list[str] = []
    for table, column, ddl in MIGRATIONS:
        if column in _columns(conn, table):
            continue
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        applied.append(f"{table}.{column}")
    if applied:
        conn.commit()
    return tuple(applied)


def missing_columns(conn: sqlite3.Connection) -> tuple[str, ...]:
    """Columns MIGRATIONS expects that are still absent — the boot check."""
    return tuple(
        f"{table}.{column}"
        for table, column, _ddl in MIGRATIONS
        if column not in _columns(conn, table)
    )


def _insert(conn: sqlite3.Connection, table: str, row: dict) -> None:
    cols = ", ".join(f'"{c}"' for c in row)
    placeholders = ", ".join("?" for _ in row)
    conn.execute(
        f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})",
        tuple(row.values()),
    )


def load_reference_data(conn: sqlite3.Connection, seed: Seed) -> None:
    for s in seed.substrates.values():
        _insert(conn, "substrate", substrate_to_row(s))
    for r in seed.gi_regions:
        _insert(conn, "gi_region", gi_region_to_row(r))
    for e in seed.enzymes.values():
        _insert(conn, "enzyme", enzyme_to_row(e))
    for f in seed.foods.values():
        _insert(conn, "food", food_to_row(f))


def create_database(path: Path | str, seed: Seed | None = None) -> Path:
    """Create (or refresh) the database at `path`. Idempotent."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        load_reference_data(conn, seed or load_seed())
        apply_migrations(conn)
        conn.commit()
    finally:
        conn.close()
    return path


def ensure_database(path: Path | str, seed: Seed | None = None) -> Path:
    """Create the database on first boot; otherwise leave its contents alone.

    `create_database` refreshes reference rows with INSERT OR REPLACE, which is
    right for a first boot and right for M3's reset-to-baseline button, and
    wrong for a restart: from M3 the founder's edits live in those same rows.
    """
    path = Path(path)
    if not path.exists():
        return create_database(path, seed)

    conn = sqlite3.connect(path)
    try:
        present = {
            r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        missing = EXPECTED_TABLES - present
        if missing:
            raise ValueError(
                f"{path} exists but its schema is missing: {', '.join(sorted(missing))}"
            )
        # A database from an earlier milestone is missing columns, not tables —
        # the check above cannot see that, which is why this runs (decision #1).
        apply_migrations(conn)
        still_missing = missing_columns(conn)
        if still_missing:
            raise ValueError(
                f"{path} could not be upgraded; still missing: {', '.join(still_missing)}"
            )
    finally:
        conn.close()
    return path
