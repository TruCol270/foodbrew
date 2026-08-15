import dataclasses
import json

from foodbrew.engine import evaluate
from foodbrew.engine.types import (
    EvalContext,
    Format,
    Formulation,
    Phase,
    ProcessStep,
    RecipeIngredient,
    SelectedEnzyme,
    Tracked,
    TruthLabel,
)
from foodbrew.seedload.loader import load_seed
from foodbrew.store.snapshot import context_from_snapshot, snapshot_from_context


def _ctx(seed):
    form = Formulation(
        id="f1",
        format=Format.PREMIXED_WET,
        recipe=(RecipeIngredient("olive_oil", 100.0), RecipeIngredient("white_vinegar", 50.0)),
        enzymes=(SelectedEnzyme("lactase_fungal_acid", 9000.0, Phase.WET),),
        target_trigger_food_ids=("milk",),
        application_food_ids=("romaine",),
        measured_ph=Tracked(3.0, TruthLabel.USER_PROVIDED, "bench reading"),
        process_steps=(ProcessStep(1, "whisk", False),),
        enzyme_addition_index=1,
    )
    return EvalContext(
        formulation=form,
        enzymes=seed.enzymes,
        foods=seed.foods,
        substrates=seed.substrates,
        gi_regions=seed.gi_regions,
    )


def test_snapshot_round_trips_to_an_equivalent_context():
    seed = load_seed()
    ctx = _ctx(seed)
    restored = context_from_snapshot(snapshot_from_context(ctx))
    assert restored.formulation == ctx.formulation


def test_rerunning_a_snapshot_reproduces_the_evaluation_exactly():
    """Spec §4: same snapshot + same engine version → byte-identical result."""
    seed = load_seed()
    ctx = _ctx(seed)
    first = evaluate(ctx)
    second = evaluate(context_from_snapshot(snapshot_from_context(ctx)))
    assert second == first


def test_snapshot_holds_only_the_referenced_closure():
    """Plan decision #4 — the whole catalogue is not copied per evaluation."""
    seed = load_seed()
    payload = json.loads(snapshot_from_context(_ctx(seed)))
    assert set(payload["enzymes"]) == {"lactase_fungal_acid"}
    assert set(payload["foods"]) == {"olive_oil", "white_vinegar", "milk", "romaine"}
    assert len(payload["gi_regions"]) == 6
    # Substrates reachable from those enzymes and foods, and no others.
    assert "lactose" in payload["substrates"]
    assert len(payload["substrates"]) < len(seed.substrates)


def test_snapshot_is_byte_stable():
    seed = load_seed()
    ctx = _ctx(seed)
    assert snapshot_from_context(ctx) == snapshot_from_context(ctx)


def test_snapshot_carries_the_latest_trial_ph():
    seed = load_seed()
    ctx = dataclasses.replace(
        _ctx(seed), latest_trial_ph=Tracked(4.1, TruthLabel.OBSERVED, "trial batch")
    )
    restored = context_from_snapshot(snapshot_from_context(ctx))
    assert restored.latest_trial_ph == ctx.latest_trial_ph
