from foodbrew.engine.rules import r08_taste_drift as r8
from foodbrew.engine.rules import r09_prebiotic_tension as r9
from foodbrew.engine.rules import r10_strain_blending as r10
from foodbrew.engine.types import (
    Deadline, Enzyme, EvalContext, Food, Format, Formulation, Phase,
    RecipeIngredient, SelectedEnzyme, Substrate, Tracked, TruthLabel, Verdict,
)

SUBSTRATES = {
    "lactose": Substrate(id="lactose", name="Lactose", native_human_enzyme=True),
    "gos": Substrate(id="gos", name="GOS", is_prebiotic=True),
    "inulin_fructan": Substrate(id="inulin_fructan", name="Inulin-type fructans",
                                is_prebiotic=True),
}


def _enzyme(eid, substrate_id, ph_min=2.5, ph_max=5.4):
    return Enzyme(
        id=eid, name=eid, substrate_id=substrate_id, source_type="fungal",
        priority="high", deadline=Deadline.BEFORE_COLON,
        ph_min=Tracked(ph_min, TruthLabel.CONFIRMED, "t"),
        ph_max=Tracked(ph_max, TruthLabel.CONFIRMED, "t"),
        ph_opt_low=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
        ph_opt_high=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
        ph_shelf_stable_min=Tracked(None, TruthLabel.UNCONFIRMED), dose_unit="FCC",
    )


def _ctx(enzymes_map, selections, fmt=Format.PREMIXED_WET, recipe=(), foods=None,
         gi_regions=()):
    return EvalContext(
        formulation=Formulation(id="f", format=fmt, recipe=recipe, enzymes=selections),
        enzymes=enzymes_map, foods=foods or {}, substrates=SUBSTRATES,
        gi_regions=gi_regions,
    )


# --- R8 -------------------------------------------------------------------

def test_r8_is_advisory():
    assert r8.ADVISORY is True


def test_r8_amber_when_enzyme_shares_wet_phase_with_its_substrate_in_recipe():
    foods = {"yogurt": Food(id="yogurt", name="Yogurt", category="dairy",
                            contains_substrate_ids=("lactose",))}
    ctx = _ctx({"lactase": _enzyme("lactase", "lactose")},
               (SelectedEnzyme("lactase", 9000.0, Phase.WET),),
               recipe=(RecipeIngredient("yogurt", 100.0),), foods=foods)
    f = r8.evaluate(ctx)[0]
    assert f.verdict is Verdict.AMBER
    assert "sweeter" in f.message


def test_r8_note_only_when_enzyme_is_dry():
    foods = {"yogurt": Food(id="yogurt", name="Yogurt", category="dairy",
                            contains_substrate_ids=("lactose",))}
    ctx = _ctx({"lactase": _enzyme("lactase", "lactose")},
               (SelectedEnzyme("lactase", 9000.0, Phase.DRY),),
               fmt=Format.DUAL_CHAMBER,
               recipe=(RecipeIngredient("yogurt", 100.0),), foods=foods)
    f = r8.evaluate(ctx)[0]
    assert f.verdict is Verdict.PASS
    assert "begins at mixing" in f.message


def test_r8_no_finding_when_substrate_absent_from_recipe():
    ctx = _ctx({"lactase": _enzyme("lactase", "lactose")},
               (SelectedEnzyme("lactase", 9000.0, Phase.WET),))
    assert r8.evaluate(ctx) == []


# --- R9 -------------------------------------------------------------------

def test_r9_is_advisory():
    assert r9.ADVISORY is True


def test_r9_fires_for_alpha_galactosidase_because_gos_is_prebiotic():
    # Spec §13 fixture (g) — KB §4i names GOS alongside inulin and fructans.
    ctx = _ctx({"alpha_gal": _enzyme("alpha_gal", "gos")},
               (SelectedEnzyme("alpha_gal", 800.0, Phase.DRY),))
    f = r9.evaluate(ctx)[0]
    assert f.verdict is Verdict.AMBER
    assert "symptom threshold" in f.message


def test_r9_fires_for_inulinase():
    ctx = _ctx({"inulinase": _enzyme("inulinase", "inulin_fructan")},
               (SelectedEnzyme("inulinase", 100.0, Phase.DRY),))
    assert r9.evaluate(ctx)[0].verdict is Verdict.AMBER


def test_r9_silent_for_lactase():
    ctx = _ctx({"lactase": _enzyme("lactase", "lactose")},
               (SelectedEnzyme("lactase", 9000.0, Phase.DRY),))
    assert r9.evaluate(ctx) == []


# --- R10 ------------------------------------------------------------------

def test_r10_is_advisory():
    assert r10.ADVISORY is True


def test_r10_suggests_pairing_when_window_is_narrow():
    from foodbrew.seedload.loader import load_seed
    regions = load_seed().gi_regions
    ctx = _ctx({"lactase": _enzyme("lactase", "lactose", 2.5, 5.4)},
               (SelectedEnzyme("lactase", 9000.0, Phase.DRY),), gi_regions=regions)
    f = r10.evaluate(ctx)[0]
    assert f.verdict is Verdict.PASS
    assert "complementary" in f.message


def test_r10_silent_for_broad_window_enzyme():
    from foodbrew.seedload.loader import load_seed
    regions = load_seed().gi_regions
    ctx = _ctx({"broad": _enzyme("broad", "lactose", 2.0, 9.0)},
               (SelectedEnzyme("broad", 100.0, Phase.DRY),), gi_regions=regions)
    assert r10.evaluate(ctx) == []
