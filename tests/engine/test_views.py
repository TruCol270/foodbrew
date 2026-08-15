from foodbrew.engine.types import Phase, TruthLabel
from foodbrew.engine.views import RULE_TITLES, dose_cards, gi_strip, substrate_summary


def test_gi_strip_marks_the_mouth_dormant_and_inactive(make_ctx):
    strip = gi_strip(make_ctx())
    regions = {r.region_id: r for r in strip[0].regions}
    assert regions["mouth"].dormant is True
    assert regions["mouth"].active is False


def test_gi_strip_marks_the_fed_stomach_active_for_fungal_lactase(make_ctx):
    """Seeded lactase is 2.5–5.4; the fed stomach is 4.0–6.0 (spec §8)."""
    strip = gi_strip(make_ctx())
    regions = {r.region_id: r for r in strip[0].regions}
    assert regions["stomach_fed"].active is True
    assert regions["stomach_fasting"].active is False


def test_gi_strip_marks_regions_at_or_before_the_deadline(make_ctx):
    strip = gi_strip(make_ctx())
    regions = {r.region_id: r for r in strip[0].regions}
    assert regions["stomach_fed"].before_deadline is True
    assert regions["colon"].before_deadline is False


def test_gi_strip_is_empty_when_the_ph_range_is_unconfirmed(make_ctx):
    ctx = make_ctx(enzymes=(("fructan_hydrolase", None, Phase.DRY),))
    lane = gi_strip(ctx)[0]
    assert all(r.active is False for r in lane.regions)
    assert lane.ph_min.status == TruthLabel.UNCONFIRMED


def test_dose_card_reports_the_threshold_comparison(make_ctx, with_load):
    ctx = make_ctx(
        enzymes=(("alpha_galactosidase", 150.0, Phase.DRY),),
        trigger_foods=("black_beans",),
        foods=with_load(black_beans=6.0),
    )
    card = dose_cards(ctx)[0]
    assert card.dose == 150.0
    assert card.meets_threshold is False  # 300 GALU threshold, spec §6.1 R7


def test_dose_card_leaves_the_comparison_none_when_the_threshold_is_unconfirmed(make_ctx):
    card = dose_cards(make_ctx())[0]
    assert card.dose_evidence_threshold.usable is False
    assert card.meets_threshold is None
    assert card.ratio is None


def test_dose_card_carries_the_summed_substrate_load(make_ctx, with_load):
    ctx = make_ctx(
        enzymes=(("alpha_galactosidase", 800.0, Phase.DRY),),
        trigger_foods=("black_beans", "lentils"),
        foods=with_load(black_beans=6.0, lentils=4.0),
    )
    card = dose_cards(ctx)[0]
    assert card.substrate_load.value == 10.0


def test_substrate_summary_names_the_substrates_a_recipe_carries(make_ctx):
    ctx = make_ctx(recipe=(("garlic_fresh", 5.0), ("olive_oil", 100.0)))
    summary = {
        row.substrate_id: row
        for row in substrate_summary(ctx.formulation.recipe, ctx.foods, ctx.substrates)
    }
    assert "inulin_fructan" in summary
    assert summary["inulin_fructan"].from_food_names == ("Garlic (fresh)",)
    assert summary["inulin_fructan"].is_prebiotic is True


def test_every_rule_has_a_title():
    for rule_id in [f"R{n}" for n in range(1, 17)]:
        assert RULE_TITLES[rule_id]
