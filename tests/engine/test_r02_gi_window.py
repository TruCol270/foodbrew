from foodbrew.engine.rules import r02_gi_window as r2
from foodbrew.engine.types import (
    Deadline,
    Enzyme,
    EvalContext,
    Format,
    Formulation,
    Phase,
    SelectedEnzyme,
    Tracked,
    TruthLabel,
    Verdict,
)
from foodbrew.seedload.loader import load_seed

SEED = load_seed()


def _enzyme(eid, ph_min, ph_max, deadline, substrate_id="lactose",
            status=TruthLabel.CONFIRMED):
    return Enzyme(
        id=eid, name=eid, substrate_id=substrate_id, source_type="fungal",
        priority="high", deadline=deadline,
        ph_min=Tracked(ph_min, status, "t"), ph_max=Tracked(ph_max, status, "t"),
        ph_opt_low=Tracked(5.0, status, "t"), ph_opt_high=Tracked(5.0, status, "t"),
        ph_shelf_stable_min=Tracked(None, TruthLabel.UNCONFIRMED), dose_unit="FCC",
    )


def _ctx(enzyme):
    form = Formulation(
        id="f", format=Format.DUAL_CHAMBER, recipe=(),
        enzymes=(SelectedEnzyme(enzyme.id, 9000.0, Phase.DRY),),
    )
    return EvalContext(
        formulation=form, enzymes={enzyme.id: enzyme}, foods={},
        substrates=SEED.substrates, gi_regions=SEED.gi_regions,
    )


def test_lactase_amber_with_single_region_coverage():
    e = _enzyme("lactase", 2.5, 5.4, Deadline.BEFORE_SMALL_INTESTINE)
    f = r2.evaluate(_ctx(e))[0]
    assert f.verdict is Verdict.AMBER
    assert "stomach_fed" in f.evidence["active_before_deadline"]


def test_alpha_gal_passes_before_colon():
    e = _enzyme("alpha_gal", 3.0, 8.0, Deadline.BEFORE_COLON, substrate_id="gos")
    f = r2.evaluate(_ctx(e))[0]
    assert f.verdict is Verdict.PASS


def test_enzyme_with_no_active_region_before_deadline_is_red():
    # pH 7.0-9.0 with a before-small-intestine deadline: nothing pre-duodenum fits.
    e = _enzyme("late", 7.0, 9.0, Deadline.BEFORE_SMALL_INTESTINE)
    f = r2.evaluate(_ctx(e))[0]
    assert f.verdict is Verdict.RED
    assert "no active window" in f.message


def test_hard_deadline_substrate_is_named_in_the_message():
    e = _enzyme("alpha_gal", 3.0, 8.0, Deadline.BEFORE_COLON, substrate_id="gos")
    f = r2.evaluate(_ctx(e))[0]
    assert "no native human enzyme" in f.message


def test_unconfirmed_ph_is_cannot_assess():
    e = _enzyme("x", 3.0, 8.0, Deadline.BEFORE_COLON, status=TruthLabel.UNCONFIRMED)
    f = r2.evaluate(_ctx(e))[0]
    assert f.verdict is Verdict.CANNOT_ASSESS


def test_mouth_never_counts_as_coverage():
    e = _enzyme("mouthonly", 6.2, 7.6, Deadline.BEFORE_SMALL_INTESTINE)
    f = r2.evaluate(_ctx(e))[0]
    assert f.verdict is Verdict.RED
    assert "mouth" not in f.evidence["active_before_deadline"]
