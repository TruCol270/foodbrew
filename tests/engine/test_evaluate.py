import pytest

from foodbrew import ENGINE_VERSION
from foodbrew.engine import evaluate
from foodbrew.engine.rules.r14_substrate_coverage import ValidationRejection
from foodbrew.engine.types import (
    EvalContext, Format, Formulation, Phase, SelectedEnzyme, Verdict,
)
from foodbrew.seedload.loader import load_seed

SEED = load_seed()


def _ctx(**overrides):
    form = Formulation(
        id="f", format=Format.DUAL_CHAMBER, recipe=(),
        enzymes=(SelectedEnzyme("lactase_fungal_acid", 9000.0, Phase.DRY),),
        target_trigger_food_ids=("milk",),
        **overrides,
    )
    return EvalContext(
        formulation=form, enzymes=SEED.enzymes, foods=SEED.foods,
        substrates=SEED.substrates, gi_regions=SEED.gi_regions,
    )


def test_evaluation_records_the_engine_version():
    assert evaluate(_ctx()).engine_version == ENGINE_VERSION


def test_evaluation_carries_findings_from_multiple_rules():
    rule_ids = {f.rule_id for f in evaluate(_ctx()).findings}
    assert {"R2", "R4", "R11", "R12", "R14"} <= rule_ids


def test_evaluation_includes_the_occasion_envelope():
    result = evaluate(_ctx())
    assert len(result.envelope) == 3


def test_evaluation_exposes_a_display_headline():
    assert evaluate(_ctx()).display in {"RED", "GRAY", "AMBER", "GREEN"}


def test_same_input_produces_identical_output():
    a, b = evaluate(_ctx()), evaluate(_ctx())
    assert a.findings == b.findings
    assert a.overall is b.overall


def test_validation_rejection_propagates():
    ctx = EvalContext(
        formulation=Formulation(id="f", format=Format.DUAL_CHAMBER, recipe=(), enzymes=()),
        enzymes=SEED.enzymes, foods=SEED.foods, substrates=SEED.substrates,
        gi_regions=SEED.gi_regions,
    )
    with pytest.raises(ValidationRejection):
        evaluate(ctx)


def test_prohibited_words_never_appear_in_engine_messages():
    # Spec §10 report lint, asserted at the source.
    banned = ["safe", "validated", "guaranteed", "clinically proven", "proven", "demonstrated"]
    for finding in evaluate(_ctx()).findings:
        lowered = finding.message.lower()
        for word in banned:
            assert word not in lowered, f"{finding.rule_id} says '{word}': {finding.message}"
