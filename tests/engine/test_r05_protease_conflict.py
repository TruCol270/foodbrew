from foodbrew.engine.rules import r05_protease_conflict as r5
from foodbrew.engine.types import (
    Deadline, Enzyme, EvalContext, Food, Format, Formulation, Phase,
    RecipeIngredient, SelectedEnzyme, Tracked, TruthLabel, Verdict,
)


def _enzyme(eid, is_protease=False):
    return Enzyme(
        id=eid, name=eid, substrate_id="lactose", source_type="fungal", priority="high",
        deadline=Deadline.BEFORE_COLON,
        ph_min=Tracked(3.0, TruthLabel.CONFIRMED, "t"),
        ph_max=Tracked(7.0, TruthLabel.CONFIRMED, "t"),
        ph_opt_low=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
        ph_opt_high=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
        ph_shelf_stable_min=Tracked(None, TruthLabel.UNCONFIRMED),
        dose_unit="FCC", is_protease=is_protease,
    )


ENZYMES = {"lactase": _enzyme("lactase"), "bromelain": _enzyme("bromelain", True)}


def _ctx(selections, recipe=(), foods=None):
    return EvalContext(
        formulation=Formulation(
            id="f", format=Format.PREMIXED_WET, recipe=recipe, enzymes=selections
        ),
        enzymes=ENZYMES, foods=foods or {}, substrates={},
    )


def test_protease_sharing_wet_phase_with_another_enzyme_is_red():
    f = r5.evaluate(_ctx((
        SelectedEnzyme("lactase", 9000.0, Phase.WET),
        SelectedEnzyme("bromelain", 100.0, Phase.WET),
    )))[0]
    assert f.verdict is Verdict.RED
    assert "enzymes are proteins" in f.message


def test_protease_in_a_separate_phase_passes():
    f = r5.evaluate(_ctx((
        SelectedEnzyme("lactase", 9000.0, Phase.WET),
        SelectedEnzyme("bromelain", 100.0, Phase.DRY),
    )))[0]
    assert f.verdict is Verdict.PASS
    assert "separated" in f.message


def test_individually_encapsulated_protease_passes():
    f = r5.evaluate(_ctx((
        SelectedEnzyme("lactase", 9000.0, Phase.WET),
        SelectedEnzyme("bromelain", 100.0, Phase.WET, encapsulated=True),
    )))[0]
    assert f.verdict is Verdict.PASS


def test_protease_alone_in_wet_phase_passes():
    # Nothing for it to degrade.
    f = r5.evaluate(_ctx((SelectedEnzyme("bromelain", 100.0, Phase.WET),)))[0]
    assert f.verdict is Verdict.PASS


def test_raw_protease_bearing_ingredient_triggers_the_conflict():
    foods = {"pineapple_fresh": Food(
        id="pineapple_fresh", name="Pineapple (fresh)", category="fruit",
        contains_protease=True, is_heat_processed=False,
    )}
    f = r5.evaluate(_ctx(
        (SelectedEnzyme("lactase", 9000.0, Phase.WET),),
        recipe=(RecipeIngredient("pineapple_fresh", 20.0),), foods=foods,
    ))[0]
    assert f.verdict is Verdict.RED
    assert "Pineapple" in f.message


def test_cooked_protease_bearing_ingredient_does_not_trigger():
    foods = {"pineapple_fresh": Food(
        id="pineapple_fresh", name="Pineapple (fresh)", category="fruit",
        contains_protease=True, is_heat_processed=True,
    )}
    f = r5.evaluate(_ctx(
        (SelectedEnzyme("lactase", 9000.0, Phase.WET),),
        recipe=(RecipeIngredient("pineapple_fresh", 20.0),), foods=foods,
    ))[0]
    assert f.verdict is Verdict.PASS
