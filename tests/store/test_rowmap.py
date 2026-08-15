from foodbrew.db import create_database
from foodbrew.seedload.loader import load_seed
from foodbrew.store.connection import connect
from foodbrew.store.reference import load_catalog


def test_catalog_from_db_equals_catalog_from_seed(tmp_path):
    """The two readers of the same data must not drift (plan decision #2)."""
    seed = load_seed()
    db = create_database(tmp_path / "foodbrew.db", seed)
    with connect(db) as conn:
        catalog = load_catalog(conn)

    assert catalog.enzymes == dict(seed.enzymes)
    assert catalog.foods == dict(seed.foods)
    assert catalog.substrates == dict(seed.substrates)
    assert catalog.gi_regions == seed.gi_regions


def test_tracked_status_and_source_survive_the_round_trip(tmp_path):
    seed = load_seed()
    db = create_database(tmp_path / "foodbrew.db", seed)
    with connect(db) as conn:
        catalog = load_catalog(conn)

    lactase = catalog.enzymes["lactase_fungal_acid"]
    assert lactase.ph_min.value == 2.5
    assert lactase.ph_min.status == "confirmed"
    assert "KB Table B" in lactase.ph_min.source
    # The field R1's fallback margin exists for stays unusable, as seeded.
    assert lactase.ph_shelf_stable_min.usable is False


def test_boolean_tracked_fields_come_back_as_booleans(tmp_path):
    seed = load_seed()
    db = create_database(tmp_path / "foodbrew.db", seed)
    with connect(db) as conn:
        catalog = load_catalog(conn)

    gras = [e.is_gras.value for e in catalog.enzymes.values() if e.is_gras.usable]
    assert gras, "at least one enzyme seeds a confirmed GRAS status"
    assert all(isinstance(v, bool) for v in gras)


def test_gi_regions_come_back_in_order(tmp_path):
    db = create_database(tmp_path / "foodbrew.db")
    with connect(db) as conn:
        regions = load_catalog(conn).gi_regions
    assert [r.order for r in regions] == sorted(r.order for r in regions)


def test_a_seed_record_round_trips_through_its_row(seed):
    """The reader and the writer are inverses, which is what makes reset faithful."""
    from foodbrew.store.rowmap import enzyme_from_row, enzyme_to_row, food_from_row, food_to_row

    for record, to_row, from_row in (
        (seed.enzymes["lactase_fungal_acid"], enzyme_to_row, enzyme_from_row),
        (seed.foods["milk"], food_to_row, food_from_row),
    ):
        row = to_row(record)
        # sqlite3.Row is not constructible directly; a plain dict has the same
        # __getitem__ contract the mappers use.
        assert from_row(row) == record
