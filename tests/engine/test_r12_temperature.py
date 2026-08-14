from foodbrew.engine.rules import r12_temperature as r12
from foodbrew.engine.types import (
    Deadline, Enzyme, EvalContext, Format, Formulation, Phase,
    SelectedEnzyme, Tracked, TruthLabel, Verdict,
)
from foodbrew.seedload.loader import load_seed


def _enzyme(eid, tmin, tmax, status):
    return Enzyme(
        id=eid, name=eid, substrate_id="lactose", source_type="fungal", priority="high",
        deadline=Deadline.BEFORE_COLON,
        ph_min=Tracked(3.0, TruthLabel.CONFIRMED, "t"),
        ph_max=Tracked(7.0, TruthLabel.CONFIRMED, "t"),
        ph_opt_low=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
        ph_opt_high=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
        ph_shelf_stable_min=Tracked(None, TruthLabel.UNCONFIRMED), dose_unit="FCC",
        temp_min_c=Tracked(tmin, status, "supplier"),
        temp_max_c=Tracked(tmax, status, "supplier"),
    )


def _ctx(enzymes_map):
    selections = tuple(SelectedEnzyme(eid, 100.0, Phase.DRY) for eid in enzymes_map)
    return EvalContext(
        formulation=Formulation(
            id="f", format=Format.DUAL_CHAMBER, recipe=(), enzymes=selections
        ),
        enzymes=enzymes_map, foods={}, substrates={},
    )


def test_module_default_is_advisory():
    assert r12.ADVISORY is True


def test_every_seeded_enzyme_yields_an_advisory_cannot_assess():
    # Spec §6.1 R12: this is why R12 cannot be headline-capable on day one.
    seed = load_seed()
    ctx = EvalContext(
        formulation=Formulation(
            id="f", format=Format.DUAL_CHAMBER, recipe=(),
            enzymes=tuple(SelectedEnzyme(eid, 100.0, Phase.DRY) for eid in seed.enzymes),
        ),
        enzymes=seed.enzymes, foods={}, substrates=seed.substrates,
    )
    findings = r12.evaluate(ctx)
    assert len(findings) == len(seed.enzymes)
    assert all(f.verdict is Verdict.CANNOT_ASSESS for f in findings)
    assert all(f.advisory is True for f in findings)


def test_confirmed_range_covering_ambient_passes_and_is_not_advisory():
    ctx = _ctx({"e": _enzyme("e", 4.0, 45.0, TruthLabel.CONFIRMED)})
    f = r12.evaluate(ctx)[0]
    assert f.verdict is Verdict.PASS
    assert f.advisory is False


def test_confirmed_range_excluding_ambient_reds_and_is_not_advisory():
    # Spec §13 fixture (h2) — promotion is per-enzyme.
    ctx = _ctx({"e": _enzyme("e", 4.0, 18.0, TruthLabel.CONFIRMED)})
    f = r12.evaluate(ctx)[0]
    assert f.verdict is Verdict.RED
    assert f.advisory is False
    assert "cold chain" in f.message


def test_promotion_is_per_enzyme_not_global():
    ctx = _ctx({
        "confirmed_bad": _enzyme("confirmed_bad", 4.0, 18.0, TruthLabel.CONFIRMED),
        "unknown": _enzyme("unknown", None, None, TruthLabel.UNCONFIRMED),
    })
    by_id = {f.enzyme_id: f for f in r12.evaluate(ctx)}
    assert by_id["confirmed_bad"].advisory is False
    assert by_id["unknown"].advisory is True


def test_range_not_covering_body_temperature_is_amber():
    ctx = _ctx({"e": _enzyme("e", 50.0, 80.0, TruthLabel.CONFIRMED)})
    f = r12.evaluate(ctx)[0]
    assert f.verdict is Verdict.RED  # also fails ambient
    assert "37" in f.message
