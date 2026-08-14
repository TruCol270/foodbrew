from foodbrew.engine.rules import r07_dosing as r7
from foodbrew.engine.types import (
    Deadline, Enzyme, EvalContext, Food, Format, Formulation, Phase,
    SelectedEnzyme, Substrate, Tracked, TruthLabel, Verdict,
)

SUBSTRATES = {"gos": Substrate(id="gos", name="GOS", is_prebiotic=True)}


def _alpha_gal(threshold=300.0, threshold_status=TruthLabel.CONFIRMED):
    return Enzyme(
        id="alpha_gal", name="Alpha-galactosidase", substrate_id="gos",
        source_type="fungal", priority="high", deadline=Deadline.BEFORE_COLON,
        ph_min=Tracked(3.0, TruthLabel.CONFIRMED, "t"),
        ph_max=Tracked(8.0, TruthLabel.CONFIRMED, "t"),
        ph_opt_low=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
        ph_opt_high=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
        ph_shelf_stable_min=Tracked(None, TruthLabel.UNCONFIRMED),
        dose_unit="GalU",
        dose_min=Tracked(450.0, TruthLabel.CONFIRMED, "KB"),
        dose_max=Tracked(800.0, TruthLabel.CONFIRMED, "KB"),
        dose_evidence_threshold=Tracked(threshold, threshold_status, "Monash"),
    )


def _food(fid, load, status=TruthLabel.CONFIRMED):
    return Food(
        id=fid, name=fid, category="legume", is_trigger_food=True,
        contains_substrate_ids=("gos",),
        typical_load_value=Tracked(load, status, "test"), typical_load_unit="g GOS",
    )


def _ctx(dose, foods, trigger_ids, enzyme=None):
    e = enzyme or _alpha_gal()
    return EvalContext(
        formulation=Formulation(
            id="f", format=Format.DUAL_CHAMBER, recipe=(),
            enzymes=(SelectedEnzyme("alpha_gal", dose, Phase.DRY),),
            target_trigger_food_ids=trigger_ids,
        ),
        enzymes={"alpha_gal": e}, foods=foods, substrates=SUBSTRATES,
    )


def test_dose_below_evidence_threshold_is_amber():
    # Spec §13 fixture (f): 150 GalU against a 6 g GOS serving.
    ctx = _ctx(150.0, {"beans": _food("beans", 6.0)}, ("beans",))
    f = r7.evaluate(ctx)[0]
    assert f.verdict is Verdict.AMBER
    assert "behaves like placebo" in f.message


def test_dose_at_threshold_passes():
    ctx = _ctx(300.0, {"beans": _food("beans", 6.0)}, ("beans",))
    assert r7.evaluate(ctx)[0].verdict is Verdict.PASS


def test_multi_food_loads_are_summed_not_maxed():
    # Spec §13 fixture (f2) and §6.7.
    ctx = _ctx(
        500.0,
        {"beans": _food("beans", 4.0), "lentils": _food("lentils", 2.5)},
        ("beans", "lentils"),
    )
    f = r7.evaluate(ctx)[0]
    assert f.evidence["substrate_load"] == 6.5
    assert "beans" in f.evidence["load_source"] and "lentils" in f.evidence["load_source"]


def test_unconfirmed_load_is_cannot_assess_and_names_the_food():
    ctx = _ctx(
        500.0,
        {"beans": _food("beans", 4.0),
         "lentils": _food("lentils", None, TruthLabel.UNCONFIRMED)},
        ("beans", "lentils"),
    )
    f = r7.evaluate(ctx)[0]
    assert f.verdict is Verdict.CANNOT_ASSESS
    assert "lentils" in f.message


def test_unconfirmed_threshold_is_cannot_assess():
    e = _alpha_gal(threshold=None, threshold_status=TruthLabel.UNCONFIRMED)
    ctx = _ctx(500.0, {"beans": _food("beans", 6.0)}, ("beans",), enzyme=e)
    f = r7.evaluate(ctx)[0]
    assert f.verdict is Verdict.CANNOT_ASSESS
    assert "dose_evidence_threshold" in f.message


def test_overdose_passes_with_a_cost_note():
    ctx = _ctx(5000.0, {"beans": _food("beans", 6.0)}, ("beans",))
    f = r7.evaluate(ctx)[0]
    assert f.verdict is Verdict.PASS
    assert "expensive way" in f.message


def test_no_dose_set_is_cannot_assess():
    ctx = _ctx(None, {"beans": _food("beans", 6.0)}, ("beans",))
    assert r7.evaluate(ctx)[0].verdict is Verdict.CANNOT_ASSESS


def test_squeeze_self_scaling_is_never_overstated():
    ctx = _ctx(300.0, {"beans": _food("beans", 6.0)}, ("beans",))
    f = r7.evaluate(ctx)[0]
    assert "dressing used, not with trigger food eaten" in f.message
