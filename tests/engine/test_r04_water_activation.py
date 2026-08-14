import pytest

from foodbrew.engine.rules import r04_water_activation as r4
from foodbrew.engine.types import (
    EvalContext, Format, Formulation, Phase, SelectedEnzyme, Verdict,
)


def _ctx(fmt, phase=Phase.WET, with_enzyme=True):
    enzymes = (SelectedEnzyme("e", 100.0, phase),) if with_enzyme else ()
    return EvalContext(
        formulation=Formulation(id="f", format=fmt, recipe=(), enzymes=enzymes),
        enzymes={}, foods={}, substrates={},
    )


def test_premixed_wet_is_amber_never_red_on_its_own():
    f = r4.evaluate(_ctx(Format.PREMIXED_WET))[0]
    assert f.verdict is Verdict.AMBER


def test_premixed_wet_message_refuses_to_read_as_a_green_light():
    f = r4.evaluate(_ctx(Format.PREMIXED_WET))[0]
    assert "physical separation" in f.message
    assert "bench stability data" in f.message


@pytest.mark.parametrize("fmt", [Format.DRY_SACHET, Format.DUAL_CHAMBER])
def test_dry_formats_pass(fmt):
    f = r4.evaluate(_ctx(fmt, phase=Phase.DRY))[0]
    assert f.verdict is Verdict.PASS


def test_encapsulated_in_wet_is_amber_and_defers_to_r6():
    f = r4.evaluate(_ctx(Format.ENCAPSULATED_IN_WET))[0]
    assert f.verdict is Verdict.AMBER
    assert "R6" in f.message


def test_dual_chamber_with_an_enzyme_wrongly_in_the_wet_phase_is_amber():
    f = r4.evaluate(_ctx(Format.DUAL_CHAMBER, phase=Phase.WET))[0]
    assert f.verdict is Verdict.AMBER


def test_no_enzymes_selected_produces_no_finding():
    assert r4.evaluate(_ctx(Format.PREMIXED_WET, with_enzyme=False)) == []
