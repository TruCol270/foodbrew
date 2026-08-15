"""Spec §6.1 R13. The KB §4m tiers are golden fixtures (a)/(b)/(c); this asserts
the ladder that walks between them.
"""

import dataclasses

from foodbrew.engine.format_search import (
    FORMAT_LADDER,
    LADDER_RULE_IDS,
    recommend_format,
    reds_under,
)
from foodbrew.engine.types import Format, Phase, Tracked, TruthLabel


def test_the_ladder_runs_from_least_to_most_separated():
    assert FORMAT_LADDER == (
        Format.PREMIXED_WET,
        Format.ENCAPSULATED_IN_WET,
        Format.DUAL_CHAMBER,
        Format.DRY_SACHET,
    )


def test_advisory_rules_are_not_on_the_ladder():
    assert LADDER_RULE_IDS.isdisjoint({"R8", "R9", "R10", "R13", "R16"})


def test_an_acidic_vinaigrette_is_told_to_separate(make_ctx):
    """Golden fixture (a) as premixed wet REDs through R1; the ladder finds the
    first position where it does not."""
    ctx = make_ctx(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    recommendation = recommend_format(ctx)
    assert "R1" in next(o.reds for o in recommendation.options if o.is_current)
    assert recommendation.recommended in (Format.DUAL_CHAMBER, Format.DRY_SACHET)
    assert recommendation.unfixable == ()


def test_the_recommendation_is_the_earliest_clearing_position(make_ctx):
    ctx = make_ctx(fmt=Format.DRY_SACHET, measured_ph=3.0, trigger_foods=("milk",))
    recommendation = recommend_format(ctx)
    clearing = [o.format for o in recommendation.options if o.clears]
    assert recommendation.recommended == clearing[0]


def test_a_formulation_that_already_clears_is_told_so(make_ctx):
    ctx = make_ctx(
        fmt=Format.DRY_SACHET,
        enzymes=(("lactase_fungal_acid", 9000.0, Phase.DRY),),
        trigger_foods=("milk",),
        process_steps=(),
    )
    recommendation = recommend_format(ctx)
    assert recommendation.recommended is not None
    assert "least separated format" in recommendation.message


def test_an_uncovered_substrate_is_reported_as_unfixable_by_format(make_ctx):
    """R14 does not care how the product is packaged (plan decision #6)."""
    ctx = make_ctx(enzymes=(), trigger_foods=("black_beans",), measured_ph=6.0)
    recommendation = recommend_format(ctx)
    assert recommendation.recommended is None
    assert recommendation.unfixable == ("R14",)
    assert "however this is packaged" in recommendation.message


def test_the_candidate_moves_the_enzymes_not_just_the_label(make_ctx):
    """A dry sachet whose selections still say wet would keep REDing on R1."""
    ctx = make_ctx(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    assert "R1" in reds_under(ctx, Format.PREMIXED_WET)
    assert "R1" not in reds_under(ctx, Format.DRY_SACHET)


def test_encapsulated_in_wet_is_evaluated_with_the_capsule_on(make_ctx):
    """R6 only speaks when an enzyme is encapsulated; the ladder has to turn it
    on or the position would be indistinguishable from premixed wet."""
    ctx = make_ctx(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    assert "R6" in reds_under(ctx, Format.ENCAPSULATED_IN_WET)


def test_the_search_does_not_mutate_the_context(make_ctx):
    ctx = make_ctx(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    recommend_format(ctx)
    assert ctx.formulation.format is Format.PREMIXED_WET
    assert ctx.formulation.enzymes[0].phase is Phase.WET


def test_a_confirmed_shelf_floor_moves_the_recommendation_up_the_ladder(make_ctx, seed):
    """The answer §15 question 1 exists to collect changes the format call."""
    catalog = dict(seed.enzymes)
    catalog["lactase_fungal_acid"] = dataclasses.replace(
        catalog["lactase_fungal_acid"],
        ph_shelf_stable_min=Tracked(2.5, TruthLabel.CONFIRMED, "supplier spec"),
    )
    ctx = make_ctx(
        fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",),
        enzyme_catalog=catalog,
    )
    assert recommend_format(ctx).recommended is Format.PREMIXED_WET
