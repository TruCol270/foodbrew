from foodbrew.engine.rules import r06_encapsulation as r6
from foodbrew.engine.types import (
    Deadline, Enzyme, EvalContext, Format, Formulation, Phase,
    SelectedEnzyme, Tracked, TruthLabel, Verdict,
)

LACTASE = Enzyme(
    id="lactase", name="Lactase", substrate_id="lactose", source_type="fungal",
    priority="high", deadline=Deadline.BEFORE_SMALL_INTESTINE,
    ph_min=Tracked(2.5, TruthLabel.CONFIRMED, "t"),
    ph_max=Tracked(5.4, TruthLabel.CONFIRMED, "t"),
    ph_opt_low=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
    ph_opt_high=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
    ph_shelf_stable_min=Tracked(None, TruthLabel.UNCONFIRMED), dose_unit="FCC",
)


def _ctx(fmt, ph):
    return EvalContext(
        formulation=Formulation(
            id="f", format=fmt, recipe=(),
            enzymes=(SelectedEnzyme("lactase", 9000.0, Phase.WET, encapsulated=True),),
            measured_ph=Tracked(ph, TruthLabel.USER_PROVIDED, "bench"),
        ),
        enzymes={"lactase": LACTASE}, foods={}, substrates={},
    )


def test_encapsulated_in_wet_below_the_floor_is_red():
    f = r6.evaluate(_ctx(Format.ENCAPSULATED_IN_WET, 3.0))[0]
    assert f.verdict is Verdict.RED
    assert "cannot rescue" in f.message


def test_encapsulated_in_wet_above_the_floor_passes():
    f = r6.evaluate(_ctx(Format.ENCAPSULATED_IN_WET, 5.0))[0]
    assert f.verdict is Verdict.PASS


def test_dual_chamber_lowers_the_bar_even_at_low_ph():
    # Spec §6.1 R6: the capsule must survive minutes plus stomach transit, not months.
    f = r6.evaluate(_ctx(Format.DUAL_CHAMBER, 3.0))[0]
    assert f.verdict is Verdict.PASS
    assert "minutes" in f.message


def test_premixed_wet_without_encapsulation_produces_no_finding():
    ctx = EvalContext(
        formulation=Formulation(
            id="f", format=Format.PREMIXED_WET, recipe=(),
            enzymes=(SelectedEnzyme("lactase", 9000.0, Phase.WET),),
            measured_ph=Tracked(3.0, TruthLabel.USER_PROVIDED, "b"),
        ),
        enzymes={"lactase": LACTASE}, foods={}, substrates={},
    )
    assert r6.evaluate(ctx) == []


def test_unresolvable_ph_is_cannot_assess():
    ctx = EvalContext(
        formulation=Formulation(
            id="f", format=Format.ENCAPSULATED_IN_WET, recipe=(),
            enzymes=(SelectedEnzyme("lactase", 9000.0, Phase.WET, encapsulated=True),),
        ),
        enzymes={"lactase": LACTASE}, foods={}, substrates={},
    )
    assert r6.evaluate(ctx)[0].verdict is Verdict.CANNOT_ASSESS
