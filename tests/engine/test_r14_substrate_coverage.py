import pytest

from foodbrew.engine.rules import r14_substrate_coverage as r14
from foodbrew.engine.types import (
    Deadline,
    Enzyme,
    EvalContext,
    Food,
    Format,
    Formulation,
    Phase,
    SelectedEnzyme,
    Substrate,
    Tracked,
    TruthLabel,
    Verdict,
)

SUBSTRATES = {
    "lactose": Substrate(id="lactose", name="Lactose"),
    "gos": Substrate(id="gos", name="GOS", is_prebiotic=True),
    "polyol": Substrate(id="polyol", name="Polyols", no_commercial_enzyme=True),
}
FOODS = {
    "milk": Food(id="milk", name="Milk", category="dairy", is_trigger_food=True,
                 contains_substrate_ids=("lactose",)),
    "beans": Food(id="beans", name="Black beans", category="legume", is_trigger_food=True,
                  contains_substrate_ids=("gos",)),
    "mushroom": Food(id="mushroom", name="Mushrooms", category="veg", is_trigger_food=True,
                     contains_substrate_ids=("polyol",)),
}


def _enzyme(eid, substrate_id):
    return Enzyme(
        id=eid, name=eid, substrate_id=substrate_id, source_type="fungal", priority="high",
        deadline=Deadline.BEFORE_COLON,
        ph_min=Tracked(3.0, TruthLabel.CONFIRMED, "t"),
        ph_max=Tracked(7.0, TruthLabel.CONFIRMED, "t"),
        ph_opt_low=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
        ph_opt_high=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
        ph_shelf_stable_min=Tracked(None, TruthLabel.UNCONFIRMED), dose_unit="FCC",
    )


def _ctx(trigger_ids, enzyme_ids):
    enzymes = {"lactase": _enzyme("lactase", "lactose"),
               "alpha_gal": _enzyme("alpha_gal", "gos")}
    return EvalContext(
        formulation=Formulation(
            id="f", format=Format.DUAL_CHAMBER, recipe=(),
            enzymes=tuple(SelectedEnzyme(e, 100.0, Phase.DRY) for e in enzyme_ids),
            target_trigger_food_ids=trigger_ids,
        ),
        enzymes=enzymes, foods=FOODS, substrates=SUBSTRATES,
    )


def test_covered_substrate_passes():
    f = r14.evaluate(_ctx(("milk",), ("lactase",)))[0]
    assert f.verdict is Verdict.PASS


def test_uncovered_substrate_is_red_and_names_it():
    f = r14.evaluate(_ctx(("milk",), ()))[0]
    assert f.verdict is Verdict.RED
    assert "no enzyme selected for Lactose" in f.message


def test_zero_enzymes_with_trigger_foods_reds_never_passes():
    findings = r14.evaluate(_ctx(("milk", "beans"), ()))
    assert len(findings) == 2
    assert all(f.verdict is Verdict.RED for f in findings)


def test_polyol_is_cannot_assess_not_red():
    # Spec §13 fixture (j) — the tool never maps polyols to an enzyme.
    f = r14.evaluate(_ctx(("mushroom",), ("lactase",)))
    polyol = [x for x in f if "Polyol" in x.message][0]
    assert polyol.verdict is Verdict.CANNOT_ASSESS
    assert "no commercial enzyme exists" in polyol.message


def test_partial_coverage_reports_per_substrate():
    findings = r14.evaluate(_ctx(("milk", "beans"), ("lactase",)))
    by_verdict = {f.verdict for f in findings}
    assert Verdict.PASS in by_verdict and Verdict.RED in by_verdict


def test_zero_enzymes_and_zero_trigger_foods_raises_validation_error():
    with pytest.raises(r14.ValidationRejection, match="at least one trigger food"):
        r14.evaluate(_ctx((), ()))
