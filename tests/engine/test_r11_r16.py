from foodbrew.engine.rules import r11_food_grade as r11
from foodbrew.engine.rules import r16_clean_label as r16
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


def _enzyme(eid, gras, gras_status, natural=False):
    return Enzyme(
        id=eid, name=eid, substrate_id="lactose", source_type="plant" if natural else "fungal",
        priority="high", deadline=Deadline.BEFORE_COLON,
        ph_min=Tracked(3.0, TruthLabel.CONFIRMED, "t"),
        ph_max=Tracked(7.0, TruthLabel.CONFIRMED, "t"),
        ph_opt_low=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
        ph_opt_high=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
        ph_shelf_stable_min=Tracked(None, TruthLabel.UNCONFIRMED), dose_unit="FCC",
        is_gras=Tracked(gras, gras_status, "KB §4l"), is_natural_source=natural,
        heat_labile_note="Destroyed by cooking." if natural else "",
    )


def _ctx(enzymes_map):
    selections = tuple(SelectedEnzyme(eid, 100.0, Phase.DRY) for eid in enzymes_map)
    return EvalContext(
        formulation=Formulation(
            id="f", format=Format.DUAL_CHAMBER, recipe=(), enzymes=selections
        ),
        enzymes=enzymes_map, foods={}, substrates={},
    )


# --- R11 ------------------------------------------------------------------

def test_r11_is_headline_capable():
    assert r11.ADVISORY is False


def test_r11_passes_for_confirmed_gras_enzyme():
    ctx = _ctx({"lactase": _enzyme("lactase", True, TruthLabel.CONFIRMED)})
    f = r11.evaluate(ctx)[0]
    assert f.verdict is Verdict.PASS


def test_r11_cannot_assess_for_unknown_gras_status():
    ctx = _ctx({"inulinase": _enzyme("inulinase", None, TruthLabel.UNCONFIRMED)})
    f = r11.evaluate(ctx)[0]
    assert f.verdict is Verdict.CANNOT_ASSESS
    assert "supplier" in f.message


def test_r11_red_when_explicitly_not_gras():
    ctx = _ctx({"bad": _enzyme("bad", False, TruthLabel.CONFIRMED)})
    assert r11.evaluate(ctx)[0].verdict is Verdict.RED


# --- R16 ------------------------------------------------------------------

def test_r16_is_advisory():
    assert r16.ADVISORY is True


def test_r16_reports_non_natural_sourcing_and_additive_gap():
    # Spec §13 fixture (p0).
    ctx = _ctx({"lactase": _enzyme("lactase", True, TruthLabel.CONFIRMED)})
    findings = r16.evaluate(ctx)
    sourcing = [f for f in findings if f.enzyme_id == "lactase"]
    assert sourcing and "fermented" in sourcing[0].message
    additives = [f for f in findings if f.enzyme_id is None]
    assert additives and additives[0].verdict is Verdict.CANNOT_ASSESS
    assert "gut-trigger additives" in additives[0].message


def test_r16_flags_natural_source_as_heat_labile():
    ctx = _ctx({"bromelain": _enzyme("bromelain", None, TruthLabel.UNCONFIRMED, natural=True)})
    f = [x for x in r16.evaluate(ctx) if x.enzyme_id == "bromelain"][0]
    assert "natural source" in f.message
    assert "cooking" in f.message


def test_r16_never_reds():
    ctx = _ctx({"bad": _enzyme("bad", False, TruthLabel.CONFIRMED)})
    assert all(f.verdict is not Verdict.RED for f in r16.evaluate(ctx))
