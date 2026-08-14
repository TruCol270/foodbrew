from foodbrew.engine.rules import r03_no_heat as r3
from foodbrew.engine.types import (
    EvalContext, Food, Format, Formulation, Phase, ProcessStep,
    RecipeIngredient, SelectedEnzyme, Tracked, TruthLabel, Verdict,
)


def _ctx(steps, addition_index, foods=None, recipe=()):
    form = Formulation(
        id="f", format=Format.PREMIXED_WET, recipe=recipe,
        enzymes=(SelectedEnzyme("e", 100.0, Phase.WET),),
        process_steps=steps, enzyme_addition_index=addition_index,
    )
    return EvalContext(
        formulation=form, enzymes={}, foods=foods or {}, substrates={}
    )


HEAT_THEN_ENZYME = (
    ProcessStep(1, "Blend base"),
    ProcessStep(2, "Pasteurise", is_heat=True),
    ProcessStep(3, "Add enzyme"),
)
ENZYME_THEN_HEAT = (
    ProcessStep(1, "Blend base"),
    ProcessStep(2, "Add enzyme"),
    ProcessStep(3, "Hot fill", is_heat=True),
)


def test_heat_after_enzyme_addition_is_red():
    f = r3.evaluate(_ctx(ENZYME_THEN_HEAT, addition_index=2))[0]
    assert f.verdict is Verdict.RED
    assert "Hot fill" in f.message
    assert "after the heat step" in f.message


def test_heat_at_the_same_index_as_addition_is_red():
    steps = (ProcessStep(1, "Blend"), ProcessStep(2, "Heat and add enzyme", is_heat=True))
    f = r3.evaluate(_ctx(steps, addition_index=2))[0]
    assert f.verdict is Verdict.RED


def test_heat_strictly_before_addition_passes():
    f = r3.evaluate(_ctx(HEAT_THEN_ENZYME, addition_index=3))[0]
    assert f.verdict is Verdict.PASS


def test_no_heat_steps_at_all_passes():
    steps = (ProcessStep(1, "Blend"), ProcessStep(2, "Add enzyme"))
    f = r3.evaluate(_ctx(steps, addition_index=2))[0]
    assert f.verdict is Verdict.PASS


def test_missing_addition_index_is_cannot_assess():
    f = r3.evaluate(_ctx(ENZYME_THEN_HEAT, addition_index=None))[0]
    assert f.verdict is Verdict.CANNOT_ASSESS
    assert "enzyme_addition_index" in f.message


def test_no_process_steps_is_cannot_assess():
    f = r3.evaluate(_ctx((), addition_index=None))[0]
    assert f.verdict is Verdict.CANNOT_ASSESS


def test_cooked_protease_food_emits_a_suppression_note():
    # Spec §6.1 R3 / KB §4j: cooking destroys naturally occurring enzymes, so a
    # cooked pineapple no longer contributes protease. R5 reads the same flag.
    foods = {
        "pineapple_fresh": Food(
            id="pineapple_fresh", name="Pineapple", category="fruit",
            contains_protease=True, is_heat_processed=True,
        )
    }
    findings = r3.evaluate(
        _ctx(HEAT_THEN_ENZYME, 3, foods=foods, recipe=(RecipeIngredient("pineapple_fresh", 20.0),))
    )
    notes = [f for f in findings if f.food_id == "pineapple_fresh"]
    assert len(notes) == 1
    assert notes[0].verdict is Verdict.PASS
    assert "no longer contributes protease" in notes[0].message
