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
    finally:
        conn.close()
    missing = EXPECTED_TABLES - present
    if missing:
        raise ValueError(
            f"{path} exists but its schema is missing: {', '.join(sorted(missing))}"
        )
    return path
