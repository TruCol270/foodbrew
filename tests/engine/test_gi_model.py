from foodbrew.engine.gi_model import active_regions, overlaps_region, regions_before_deadline
from foodbrew.engine.types import Deadline, Enzyme, GIRegion, Tracked, TruthLabel
from foodbrew.seedload.loader import load_seed

SEED = load_seed()
REGIONS = SEED.gi_regions


def _enzyme(ph_min, ph_max, deadline=Deadline.BEFORE_COLON, status=TruthLabel.CONFIRMED):
    return Enzyme(
        id="x", name="X", substrate_id="lactose", source_type="fungal", priority="high",
        deadline=deadline,
        ph_min=Tracked(ph_min, status, "t"), ph_max=Tracked(ph_max, status, "t"),
        ph_opt_low=Tracked(5.0, status, "t"), ph_opt_high=Tracked(5.0, status, "t"),
        ph_shelf_stable_min=Tracked(None, TruthLabel.UNCONFIRMED), dose_unit="FCC",
    )


def test_overlaps_region_true_when_ranges_intersect():
    fed = GIRegion(id="stomach_fed", name="", ph_low=4.0, ph_high=6.0, order=3)
    assert overlaps_region(_enzyme(2.5, 5.4), fed) is True


def test_overlaps_region_false_when_disjoint():
    jejunum = GIRegion(id="jejunum_ileum", name="", ph_low=7.0, ph_high=7.5, order=5)
    assert overlaps_region(_enzyme(2.5, 5.4), jejunum) is False


def test_mouth_is_never_active_even_when_ph_fits():
    # Spec §8 — dwell is seconds, so the mouth is dormant regardless of pH fit.
    ids = {r.id for r in active_regions(_enzyme(6.0, 8.0), REGIONS)}
    assert "mouth" not in ids


def test_fungal_lactase_active_in_fed_stomach_not_duodenum():
    # Spec §8: lactase's 5.4 ceiling drops it out at the duodenum.
    ids = {r.id for r in active_regions(_enzyme(2.5, 5.4), REGIONS)}
    assert "stomach_fed" in ids
    assert "duodenum" not in ids


def test_xylose_isomerase_active_in_jejunum():
    ids = {r.id for r in active_regions(_enzyme(7.0, 9.0), REGIONS)}
    assert "jejunum_ileum" in ids


def test_active_regions_empty_when_ph_unconfirmed():
    assert active_regions(_enzyme(2.5, 5.4, status=TruthLabel.UNCONFIRMED), REGIONS) == ()


def test_regions_before_colon_deadline_excludes_colon():
    ids = {r.id for r in regions_before_deadline(Deadline.BEFORE_COLON, REGIONS)}
    assert "colon" not in ids
    assert "jejunum_ileum" in ids


def test_regions_before_small_intestine_deadline_stops_at_stomach():
    ids = {r.id for r in regions_before_deadline(Deadline.BEFORE_SMALL_INTESTINE, REGIONS)}
    assert ids == {"mouth", "stomach_fasting", "stomach_fed"}


def test_small_intestine_deadline_includes_small_intestine_regions():
    ids = {r.id for r in regions_before_deadline(Deadline.SMALL_INTESTINE, REGIONS)}
    assert "duodenum" in ids and "jejunum_ileum" in ids and "colon" not in ids
