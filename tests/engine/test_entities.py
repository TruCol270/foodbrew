from foodbrew.engine.types import (
    Deadline,
    Enzyme,
    EvalContext,
    Food,
    Format,
    Formulation,
    Phase,
    ProcessStep,
    RecipeIngredient,
    SelectedEnzyme,
    Substrate,
    Tracked,
    TruthLabel,
)


def _t(v, status=TruthLabel.CONFIRMED):
    return Tracked(value=v, status=status, source="test")


def test_enzyme_holds_tracked_fields():
    e = Enzyme(
        id="lactase_fungal_acid",
        name="Lactase (fungal, acid)",
        substrate_id="lactose",
        source_type="fungal",
        priority="high",
        deadline=Deadline.BEFORE_SMALL_INTESTINE,
        ph_min=_t(2.5),
        ph_max=_t(5.4),
        ph_opt_low=_t(5.0),
        ph_opt_high=_t(5.0),
        ph_shelf_stable_min=Tracked(None, TruthLabel.UNCONFIRMED),
        dose_unit="FCC",
    )
    assert e.ph_min.value == 2.5
    assert e.ph_shelf_stable_min.usable is False
    assert e.is_protease is False
    assert e.degrades_structural == ()


def test_food_role_flags_default_false():
    f = Food(id="romaine", name="Romaine", category="green")
    assert f.is_recipe_ingredient is False
    assert f.is_application_food is False
    assert f.structural == ()


def test_eval_context_indexes_by_id():
    e = Enzyme(
        id="e1", name="E", substrate_id="lactose", source_type="fungal",
        priority="high", deadline=Deadline.BEFORE_COLON,
        ph_min=_t(3.0), ph_max=_t(7.0), ph_opt_low=_t(5.0), ph_opt_high=_t(5.0),
        ph_shelf_stable_min=Tracked(None, TruthLabel.UNCONFIRMED), dose_unit="FCC",
    )
    f = Food(id="milk", name="Milk", category="dairy")
    s = Substrate(id="lactose", name="Lactose")
    form = Formulation(
        id="f1",
        format=Format.PREMIXED_WET,
        recipe=(RecipeIngredient(food_id="milk", amount_g=100.0),),
        enzymes=(SelectedEnzyme(enzyme_id="e1", dose=9000.0, phase=Phase.WET),),
    )
    ctx = EvalContext(
        formulation=form, enzymes={"e1": e}, foods={"milk": f}, substrates={"lactose": s}
    )
    assert ctx.enzymes["e1"].name == "E"
    assert ctx.selected_enzymes()[0].enzyme_id == "e1"
    assert ctx.enzyme_for(ctx.selected_enzymes()[0]).id == "e1"


def test_process_step_ordering_and_heat_flag():
    steps = (
        ProcessStep(order=1, label="Blend base", is_heat=False),
        ProcessStep(order=2, label="Pasteurise", is_heat=True),
    )
    form = Formulation(
        id="f2", format=Format.PREMIXED_WET, recipe=(), enzymes=(),
        process_steps=steps, enzyme_addition_index=1,
    )
    assert [s.order for s in form.process_steps] == [1, 2]
    assert form.enzyme_addition_index == 1
