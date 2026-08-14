import pytest

from foodbrew.engine.types import SeverityTier, TruthLabel
from foodbrew.seedload.loader import load_seed


@pytest.fixture(scope="module")
def seed():
    return load_seed()


def test_loads_expected_record_counts(seed):
    assert len(seed.enzymes) == 12
    assert len(seed.substrates) == 12
    assert len(seed.gi_regions) == 6
    assert len(seed.foods) == 53


def test_every_enzyme_substrate_id_resolves(seed):
    for e in seed.enzymes.values():
        assert e.substrate_id in seed.substrates, f"{e.id} references unknown {e.substrate_id}"


def test_every_food_substrate_id_resolves(seed):
    for f in seed.foods.values():
        for sid in f.contains_substrate_ids:
            assert sid in seed.substrates, f"{f.id} references unknown {sid}"


def test_no_shipped_enzyme_claims_the_rapid_tier(seed):
    # Spec §6.3.1 — the rapid tier exists so the mapping is total, but no
    # source document supports minutes-scale destruction by a real enzyme.
    for e in seed.enzymes.values():
        for entry in e.degrades_structural:
            assert entry.tier is not SeverityTier.RAPID, f"{e.id} must not claim rapid"


def test_all_temperature_fields_seed_unconfirmed(seed):
    # Spec §9.1 — this is why R12 is advisory in v1 (§6.1 R12).
    for e in seed.enzymes.values():
        assert e.temp_min_c.status is TruthLabel.UNCONFIRMED
        assert e.temp_max_c.status is TruthLabel.UNCONFIRMED
        assert e.temp_opt_c.status is TruthLabel.UNCONFIRMED


def test_all_shelf_stable_floors_seed_unconfirmed(seed):
    for e in seed.enzymes.values():
        assert e.ph_shelf_stable_min.status is TruthLabel.UNCONFIRMED


def test_all_food_ph_and_water_seed_unconfirmed(seed):
    # Spec §9.3 — seeded numbers are starting estimates, not evidence.
    for f in seed.foods.values():
        assert f.ph.status is TruthLabel.UNCONFIRMED
        assert f.water_content_pct.status is TruthLabel.UNCONFIRMED


def test_gi_regions_are_ordered_and_mouth_is_dormant(seed):
    orders = [r.order for r in seed.gi_regions]
    assert orders == sorted(orders)
    assert seed.gi_regions[0].id == "mouth"
    assert seed.gi_regions[0].dormant is True


def test_polyol_substrate_has_no_commercial_enzyme(seed):
    assert seed.substrates["polyol"].no_commercial_enzyme is True
    covered = {e.substrate_id for e in seed.enzymes.values()}
    assert "polyol" not in covered, "no enzyme may ever be mapped to polyols"


def test_prebiotic_substrates_flagged(seed):
    # Spec §9.2 — drives R9, which must fire for GOS as well as fructans.
    assert seed.substrates["gos"].is_prebiotic is True
    assert seed.substrates["inulin_fructan"].is_prebiotic is True
    assert seed.substrates["graminan_fructan"].is_prebiotic is True
    assert seed.substrates["lactose"].is_prebiotic is False


def test_trap_ingredients_flag_protease(seed):
    assert seed.foods["pineapple_fresh"].contains_protease is True
    assert seed.foods["papaya_fresh"].contains_protease is True
