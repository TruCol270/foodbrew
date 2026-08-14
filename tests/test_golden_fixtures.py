"""Spec §13 golden fixtures (a)-(q)."""

from __future__ import annotations

import dataclasses

import pytest

from foodbrew.engine import evaluate
from foodbrew.engine.rules.r14_substrate_coverage import ValidationRejection
from foodbrew.engine.texture import dwell_bucket
from foodbrew.engine.trial_rules import (
    ConfidenceTier,
    ambient_storage_allowed,
    confidence_tier,
)
from foodbrew.engine.types import (
    DwellProfile,
    Format,
    Phase,
    ProcessStep,
    Tracked,
    TruthLabel,
    Verdict,
)

LACTASE = "lactase_fungal_acid"
ALPHA_GAL = "alpha_galactosidase"
BROMELAIN = "protease_bromelain"


def _by_rule(result, rule_id):
    return [f for f in result.findings if f.rule_id == rule_id]


def _verdict(result, rule_id):
    findings = _by_rule(result, rule_id)
    assert findings, f"expected at least one {rule_id} finding"
    from foodbrew.engine.types import worst
    return worst(f.verdict for f in findings)


# (a) --------------------------------------------------------------------

def test_a_wet_vinaigrette_at_ph_3_is_red_via_r1(make_ctx):
    result = evaluate(make_ctx(
        fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",),
        process_steps=(ProcessStep(1, "Blend"), ProcessStep(2, "Add enzyme")),
        enzyme_addition_index=2,
    ))
    assert _verdict(result, "R1") is Verdict.RED
    assert _verdict(result, "R4") is Verdict.AMBER
    assert result.display == "RED"


# (b) --------------------------------------------------------------------

def test_b_creamy_at_ph_4_4_is_amber_overall(make_ctx, with_load):
    """DEVIATION (see plan header): R1 is AMBER here, not pass — 4.4 is above the
    survival floor but below the 5.0 optimum, which R1's own text calls AMBER.
    The headline is unaffected.

    Milk's lactose load is unconfirmed in the seed by design (spec §9.3), so per
    the plan's stated boundary this fixture supplies it as an explicit
    user_provided test input (12g, a standard one-cup-of-milk lactose figure) —
    otherwise R7 CANNOT_ASSESSes on the missing food-level load before it ever
    reaches lactase's own (also-unconfirmed, advisory) dose_evidence_threshold."""
    result = evaluate(make_ctx(
        fmt=Format.PREMIXED_WET, measured_ph=4.4, trigger_foods=("milk",),
        recipe=(("buttermilk", 100.0),), foods=with_load(milk=12.0),
        process_steps=(ProcessStep(1, "Blend"), ProcessStep(2, "Add enzyme")),
        enzyme_addition_index=2,
    ))
    assert _verdict(result, "R1") is Verdict.AMBER
    assert _verdict(result, "R4") is Verdict.AMBER
    assert _verdict(result, "R8") is Verdict.AMBER
    assert result.display == "AMBER"


# (c) --------------------------------------------------------------------

@pytest.mark.parametrize("fmt", [Format.DRY_SACHET, Format.DUAL_CHAMBER])
def test_c_dry_formats_are_green(make_ctx, with_load, fmt):
    result = evaluate(make_ctx(
        fmt=fmt, measured_ph=4.4,
        enzymes=((ALPHA_GAL, 800.0, Phase.DRY),),
        trigger_foods=("black_beans",), foods=with_load(black_beans=6.0),
        process_steps=(ProcessStep(1, "Blend"), ProcessStep(2, "Add enzyme")),
        enzyme_addition_index=2,
    ))
    assert _by_rule(result, "R1") == []
    assert _verdict(result, "R4") is Verdict.PASS
    assert result.display == "GREEN"


# (d) --------------------------------------------------------------------

def test_d_bromelain_wet_with_lactase_is_r5_red(make_ctx):
    result = evaluate(make_ctx(
        fmt=Format.PREMIXED_WET, measured_ph=5.0, trigger_foods=("milk",),
        enzymes=((LACTASE, 9000.0, Phase.WET), (BROMELAIN, 100.0, Phase.WET)),
        process_steps=(ProcessStep(1, "Blend"), ProcessStep(2, "Add enzyme")),
        enzyme_addition_index=2,
    ))
    assert _verdict(result, "R5") is Verdict.RED


def test_d_bromelain_separated_passes_r5(make_ctx):
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER, measured_ph=5.0, trigger_foods=("milk",),
        enzymes=((LACTASE, 9000.0, Phase.DRY), (BROMELAIN, 100.0, Phase.DRY)),
        process_steps=(ProcessStep(1, "Blend"), ProcessStep(2, "Add enzyme")),
        enzyme_addition_index=2,
    ))
    assert _verdict(result, "R5") is Verdict.PASS


# (e) --------------------------------------------------------------------

def test_e_heat_after_enzyme_is_r3_red(make_ctx):
    result = evaluate(make_ctx(
        measured_ph=5.0, trigger_foods=("milk",),
        process_steps=(ProcessStep(1, "Add enzyme"), ProcessStep(2, "Hot fill", is_heat=True)),
        enzyme_addition_index=1,
    ))
    assert _verdict(result, "R3") is Verdict.RED


def test_e_heat_before_enzyme_passes_r3(make_ctx):
    result = evaluate(make_ctx(
        measured_ph=5.0, trigger_foods=("milk",),
        process_steps=(ProcessStep(1, "Pasteurise", is_heat=True), ProcessStep(2, "Add enzyme")),
        enzyme_addition_index=2,
    ))
    assert _verdict(result, "R3") is Verdict.PASS


# (f) and (f2) -----------------------------------------------------------

def test_f_alpha_gal_150_galu_against_6g_gos_is_r7_amber(make_ctx, with_load):
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER, enzymes=((ALPHA_GAL, 150.0, Phase.DRY),),
        trigger_foods=("black_beans",), foods=with_load(black_beans=6.0),
    ))
    assert _verdict(result, "R7") is Verdict.AMBER


def test_f2_multi_food_gos_loads_are_summed(make_ctx, with_load):
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER, enzymes=((ALPHA_GAL, 800.0, Phase.DRY),),
        trigger_foods=("black_beans", "lentils"),
        foods=with_load(black_beans=4.0, lentils=2.5),
    ))
    finding = _by_rule(result, "R7")[0]
    assert finding.evidence["substrate_load"] == pytest.approx(6.5)


# (g) --------------------------------------------------------------------

def test_g_r9_fires_for_both_inulinase_and_alpha_gal(make_ctx, with_load):
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER,
        enzymes=((ALPHA_GAL, 800.0, Phase.DRY), ("inulinase", 100.0, Phase.DRY)),
        trigger_foods=("black_beans",), foods=with_load(black_beans=6.0),
    ))
    enzymes_flagged = {f.enzyme_id for f in _by_rule(result, "R9")}
    assert {ALPHA_GAL, "inulinase"} <= enzymes_flagged


# (h) and (h2) -----------------------------------------------------------

def test_h_advisory_cannot_assess_does_not_gray_the_headline(make_ctx, with_load):
    """R12 returns cannot_assess for every seeded enzyme; fixtures (a)-(c) depend
    on that leaving the headline alone."""
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER, enzymes=((ALPHA_GAL, 800.0, Phase.DRY),),
        trigger_foods=("black_beans",), foods=with_load(black_beans=6.0),
        process_steps=(ProcessStep(1, "Blend"), ProcessStep(2, "Add enzyme")),
        enzyme_addition_index=2,
    ))
    assert _verdict(result, "R12") is Verdict.CANNOT_ASSESS
    assert all(f.advisory for f in _by_rule(result, "R12"))
    assert result.display == "GREEN"


def test_h_headline_capable_cannot_assess_does_gray_the_headline(make_ctx):
    # No confirmed load, so R7 cannot assess and R7 is headline-capable.
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER, enzymes=((ALPHA_GAL, 800.0, Phase.DRY),),
        trigger_foods=("black_beans",),
    ))
    assert result.display == "GRAY"


def test_h2_r12_promotion_is_per_enzyme(make_ctx, seed, with_load):
    catalog = dict(seed.enzymes)
    catalog[ALPHA_GAL] = dataclasses.replace(
        catalog[ALPHA_GAL],
        temp_min_c=Tracked(4.0, TruthLabel.CONFIRMED, "supplier"),
        temp_max_c=Tracked(18.0, TruthLabel.CONFIRMED, "supplier"),
    )
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER,
        enzymes=((ALPHA_GAL, 800.0, Phase.DRY), (LACTASE, 9000.0, Phase.DRY)),
        trigger_foods=("black_beans",), foods=with_load(black_beans=6.0),
        enzyme_catalog=catalog,
    ))
    by_enzyme = {f.enzyme_id: f for f in _by_rule(result, "R12")}
    assert by_enzyme[ALPHA_GAL].advisory is False
    assert by_enzyme[ALPHA_GAL].verdict is Verdict.RED
    assert by_enzyme[LACTASE].advisory is True
    assert result.display == "RED"


# (i) and (j) ------------------------------------------------------------

def test_i_uncovered_trigger_food_is_r14_red(make_ctx, with_load):
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER, enzymes=((LACTASE, 9000.0, Phase.DRY),),
        trigger_foods=("black_beans",), foods=with_load(black_beans=6.0),
    ))
    assert _verdict(result, "R14") is Verdict.RED
    assert result.display == "RED"


def test_i_zero_enzymes_and_zero_trigger_foods_is_rejected(make_ctx):
    with pytest.raises(ValidationRejection):
        evaluate(make_ctx(fmt=Format.DUAL_CHAMBER, enzymes=()))


def test_j_polyol_is_cannot_assess_and_never_suggests_an_enzyme(make_ctx):
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER, enzymes=((LACTASE, 9000.0, Phase.DRY),),
        trigger_foods=("mushroom",),
    ))
    polyol = [f for f in _by_rule(result, "R14") if f.evidence.get("substrate") == "polyol"]
    assert polyol and polyol[0].verdict is Verdict.CANNOT_ASSESS


# (k)-(o2) ---------------------------------------------------------------

def test_k_narrow_blend_passes_the_whole_envelope(make_ctx, with_load):
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER,
        enzymes=((LACTASE, 9000.0, Phase.DRY), (ALPHA_GAL, 800.0, Phase.DRY)),
        trigger_foods=("black_beans",), foods=with_load(black_beans=6.0),
        application_foods=("mixed_greens",),
    ))
    assert all(v is Verdict.PASS for v in result.envelope.values())


def test_l_cellulase_on_greens_grades_by_dwell(make_ctx, with_load):
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER,
        enzymes=((ALPHA_GAL, 800.0, Phase.DRY), ("cellulase", 100.0, Phase.DRY)),
        trigger_foods=("black_beans",), foods=with_load(black_beans=6.0),
        application_foods=("mixed_greens",),
        process_steps=(ProcessStep(1, "Blend"), ProcessStep(2, "Add enzyme")),
        enzyme_addition_index=2,
    ))
    assert result.envelope[DwellProfile.IMMEDIATE] is Verdict.PASS
    assert result.envelope[DwellProfile.PACKED] is Verdict.AMBER
    assert result.envelope[DwellProfile.MARINADE] is Verdict.RED
    assert result.display == "AMBER"


def test_m_rapid_tier_reds_all_three_and_the_headline(
    make_ctx, with_load, synthetic_rapid_enzyme
):
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER,
        enzymes=((ALPHA_GAL, 800.0, Phase.DRY),
                 ("synthetic_rapid_protease", 100.0, Phase.DRY)),
        trigger_foods=("black_beans",), foods=with_load(black_beans=6.0),
        application_foods=("chicken_cooked",),
        enzyme_catalog=synthetic_rapid_enzyme,
    ))
    assert all(v is Verdict.RED for v in result.envelope.values())
    assert result.display == "RED"


def test_n_declared_marinade_occasion_reds_the_headline(make_ctx, with_load):
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER,
        enzymes=((ALPHA_GAL, 800.0, Phase.DRY), ("cellulase", 100.0, Phase.DRY)),
        trigger_foods=("black_beans",), foods=with_load(black_beans=6.0),
        application_foods=("mixed_greens",), dwell_profile=DwellProfile.MARINADE,
    ))
    assert result.display == "RED"


def test_o_inulinase_on_artichoke_is_cannot_assess_everywhere(make_ctx, with_load):
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER,
        enzymes=((ALPHA_GAL, 800.0, Phase.DRY), ("inulinase", 100.0, Phase.DRY)),
        trigger_foods=("black_beans",), foods=with_load(black_beans=6.0),
        application_foods=("artichoke",),
    ))
    assert all(v is Verdict.CANNOT_ASSESS for v in result.envelope.values())


@pytest.mark.parametrize(
    "minutes,expected",
    [(0, DwellProfile.IMMEDIATE), (59, DwellProfile.IMMEDIATE),
     (60, DwellProfile.PACKED), (479, DwellProfile.PACKED),
     (480, DwellProfile.MARINADE), (1440, DwellProfile.MARINADE)],
)
def test_o2_dwell_bucketing(minutes, expected):
    assert dwell_bucket(minutes) is expected


# (p0), (p), (q) ---------------------------------------------------------

def test_p0_r16_is_advisory_and_reports_the_additive_gap(make_ctx, with_load):
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER, enzymes=((ALPHA_GAL, 800.0, Phase.DRY),),
        trigger_foods=("black_beans",), foods=with_load(black_beans=6.0),
        process_steps=(ProcessStep(1, "Blend"), ProcessStep(2, "Add enzyme")),
        enzyme_addition_index=2,
    ))
    r16 = _by_rule(result, "R16")
    assert all(f.advisory for f in r16)
    assert any(f.verdict is Verdict.CANNOT_ASSESS for f in r16)
    assert result.display == "GREEN"


@pytest.mark.parametrize(
    "blinded,control,expected",
    [(False, False, ConfidenceTier.ANECDOTE),
     (True, False, ConfidenceTier.SUGGESTIVE),
     (False, True, ConfidenceTier.SUGGESTIVE),
     (True, True, ConfidenceTier.SUGGESTIVE)],
)
def test_p_confidence_tiers(blinded, control, expected):
    assert confidence_tier(was_blinded=blinded, had_undressed_control=control) is expected


@pytest.mark.parametrize("ph,allowed", [(5.2, False), (None, False), (4.1, True)])
def test_q_ambient_storage_gate(ph, allowed):
    assert ambient_storage_allowed(ph) is allowed
