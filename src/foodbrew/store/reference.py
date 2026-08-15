"""Read the reference catalogue out of SQLite."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass

from foodbrew.engine.types import Enzyme, Food, GIRegion, Substrate
from foodbrew.store.rowmap import (
    enzyme_from_row,
    food_from_row,
    gi_region_from_row,
    substrate_from_row,
)


@dataclass(frozen=True, slots=True)
class Catalog:
    """Shape-compatible with seedload.Seed, read from the database instead."""

    enzymes: Mapping[str, Enzyme]
    foods: Mapping[str, Food]
    substrates: Mapping[str, Substrate]
    gi_regions: tuple[GIRegion, ...]


def load_catalog(conn: sqlite3.Connection) -> Catalog:
    substrates = {
        r["id"]: substrate_from_row(r) for r in conn.execute("SELECT * FROM substrate")
    }
    enzymes = {r["id"]: enzyme_from_row(r) for r in conn.execute("SELECT * FROM enzyme")}
    foods = {r["id"]: food_from_row(r) for r in conn.execute("SELECT * FROM food")}
    regions = tuple(
        gi_region_from_row(r)
        for r in conn.execute('SELECT * FROM gi_region ORDER BY "order"')
    )
    return Catalog(
        enzymes=enzymes, foods=foods, substrates=substrates, gi_regions=regions
    )
