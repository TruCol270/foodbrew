import pytest

from foodbrew.engine.rules import r01_ph_survival as r1
from foodbrew.engine.types import (
    Deadline, Enzyme, EvalContext, Food, Format, Formulation, Phase,
    SelectedEnzyme, Tracked, TruthLabel, Verdict,
)

FALLBACK_MARGIN = 1.0


def _lactase(shelf_floor=None, shelf_status=TruthLabel.UNCONFIRMED):
    return Enzyme(
        id="lactase", name="Lactase (fungal, acid)", substrate_id="lactose",
        source_type="fungal", priority="high", deadline=Deadline.BEFORE_SMALL_INTESTINE,
        ph_min=Tracked(2.5, TruthLabel.CONFIRMED, "KB"),
        ph_max=Tracked(5.4, TruthLabel.CONFIRMED, "KB"),
        ph_opt_low=Tracked(5.0, TruthLabel.CONFIRMED, "KB"),
        ph_opt_high=Tracked(5.0, TruthLabel.CONFIRMED, "KB"),
        ph_shelf_stable_min=Tracked(shelf_floor, shelf_status, "t"),
        dose_unit="FCC",
    )


def _ctx(fmt, ph, phase=Phase.WET, enzyme=None):
    e = enzyme or _lactase()
    form = Formulation(
        id="f", format=fmt, recipe=(), enzymes=(SelectedEnzyme("lactase", 9000.0, phase),),
        measured_ph=Tracked(ph, TruthLabel.USER_PROVIDED, "bench") if ph is not None
        else Tracked(None, TruthLabel.UNCONFIRMED),
    )
    return EvalContext(formulation=form, enzymes={"lactase": e}, foods={}, substrates={})


def test_vinaigrette_at_ph_3_is_red_via_fallback_margin():
    # Spec §6.1 R1 worked case: ph_min 2.5 + 1.0 = 3.5 floor; 3.0 breaches it.
    findings = r1.evaluate(_ctx(Format.PREMIXED_WET, 3.0))
    assert len(findings) == 1
    assert findings[0].verdict is Verdict.RED
    assert findings[0].evidence["fallback_floor"] == pytest.approx(3.5)
    assert "margin heuristic" in findings[0].message


def test_ph_4_4_is_amber_below_optimum_but_above_floor():
    # DEVIATION note in this plan: R1's rule text makes this AMBER, not pass.
    findings = r1.evaluate(_ctx(Format.PREMIXED_WET, 4.4))
    assert findings[0].verdict is Verdict.AMBER
    assert "below its optimum" in findings[0].message


def test_ph_at_optimum_passes():
    findings = r1.evaluate(_ctx(Format.PREMIXED_WET, 5.0))
    assert findings[0].verdict is Verdict.PASS


def test_confirmed_shelf_floor_is_used_instead_of_fallback():
    e = _lactase(shelf_floor=4.0, shelf_status=TruthLabel.CONFIRMED)
    findings = r1.evaluate(_ctx(Format.PREMIXED_WET, 3.8, enzyme=e))
    assert findings[0].verdict is Verdict.RED
    assert findings[0].evidence["floor_source"] == "ph_shelf_stable_min"
    assert "margin heuristic" not in findings[0].message


def test_dry_phase_enzyme_is_skipped():
    assert r1.evaluate(_ctx(Format.DUAL_CHAMBER, 3.0, phase=Phase.DRY)) == []


def test_dry_sachet_format_is_skipped():
    assert r1.evaluate(_ctx(Format.DRY_SACHET, 3.0, phase=Phase.DRY)) == []


def test_unresolvable_ph_is_cannot_assess():
    findings = r1.evaluate(_ctx(Format.PREMIXED_WET, None))
    assert findings[0].verdict is Verdict.CANNOT_ASSESS
    assert "no wet ingredient" in findings[0].message


def test_unconfirmed_ph_min_is_cannot_assess():
    e = Enzyme(
        id="lactase", name="L", substrate_id="lactose", source_type="fungal",
        priority="high", deadline=Deadline.BEFORE_SMALL_INTESTINE,
        ph_min=Tracked(None, TruthLabel.UNCONFIRMED), ph_max=Tracked(None, TruthLabel.UNCONFIRMED),
        ph_opt_low=Tracked(None, TruthLabel.UNCONFIRMED),
        ph_opt_high=Tracked(None, TruthLabel.UNCONFIRMED),
        ph_shelf_stable_min=Tracked(None, TruthLabel.UNCONFIRMED), dose_unit="",
    )
    findings = r1.evaluate(_ctx(Format.PREMIXED_WET, 3.0, enzyme=e))
    assert findings[0].verdict is Verdict.CANNOT_ASSESS
    assert "ph_min" in findings[0].message
