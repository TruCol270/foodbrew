"""Spec §13 property tests — invariants that must hold for any input."""

from __future__ import annotations

import dataclasses

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from foodbrew.engine import evaluate
from foodbrew.engine.flags import aggregate
from foodbrew.engine.texture import verdict_for_tier
from foodbrew.engine.types import (
    DwellProfile,
    Format,
    Phase,
    RuleFinding,
    SeverityTier,
    Tracked,
    TruthLabel,
    Verdict,
    worst,
)

LACTASE = "lactase_fungal_acid"
ALPHA_GAL = "alpha_galactosidase"
_SEVERITY = {Verdict.PASS: 0, Verdict.AMBER: 1, Verdict.CANNOT_ASSESS: 2, Verdict.RED: 3}


@given(ph=st.floats(min_value=2.0, max_value=6.0))
@settings(
    max_examples=40, deadline=None,
    # make_ctx is a function-scoped fixture but holds no mutable state across
    # calls (it's a pure factory closure over the session-scoped, frozen seed
    # catalogue) -- safe to reuse across Hypothesis-generated examples within
    # one test invocation, per Hypothesis's own guidance for this health check.
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_lowering_recipe_ph_never_improves_r1(make_ctx, ph):
    def r1_severity(value):
        result = evaluate(make_ctx(
            fmt=Format.PREMIXED_WET, measured_ph=value, trigger_foods=("milk",),
        ))
        findings = [f for f in result.findings if f.rule_id == "R1"]
        return _SEVERITY[worst(f.verdict for f in findings)]

    assert r1_severity(ph - 0.5) >= r1_severity(ph)


def test_moving_an_enzyme_wet_to_dry_never_worsens_r4(make_ctx):
    def r4_severity(fmt, phase):
        result = evaluate(make_ctx(
            fmt=fmt, measured_ph=4.4, trigger_foods=("milk",),
            enzymes=((LACTASE, 9000.0, phase),),
        ))
        findings = [f for f in result.findings if f.rule_id == "R4"]
        return _SEVERITY[worst(f.verdict for f in findings)]

    assert r4_severity(Format.DUAL_CHAMBER, Phase.DRY) <= r4_severity(
        Format.PREMIXED_WET, Phase.WET
    )


def test_increasing_dwell_never_improves_an_r15_profile():
    order = [DwellProfile.IMMEDIATE, DwellProfile.PACKED, DwellProfile.MARINADE]
    for tier in SeverityTier:
        severities = [_SEVERITY[verdict_for_tier(tier, p)] for p in order]
        assert severities == sorted(severities), f"{tier} improves with dwell"


@given(
    verdicts=st.lists(st.sampled_from(list(Verdict)), min_size=1, max_size=8),
    advisory_verdicts=st.lists(st.sampled_from(list(Verdict)), max_size=8),
)
@settings(max_examples=60, deadline=None)
def test_advisory_findings_never_change_the_overall_flag(verdicts, advisory_verdicts):
    clean = dict.fromkeys(DwellProfile, Verdict.PASS)
    headline_only = [RuleFinding("R1", v, "m", {}) for v in verdicts]
    with_advisories = headline_only + [
        RuleFinding("R9", v, "m", {}, advisory=True) for v in advisory_verdicts
    ]
    assert (
        aggregate(headline_only, clean, None).overall
        is aggregate(with_advisories, clean, None).overall
    )


@given(verdicts=st.lists(st.sampled_from(list(Verdict)), min_size=1, max_size=10))
@settings(max_examples=60, deadline=None)
def test_worst_matches_the_documented_severity_order(verdicts):
    assert _SEVERITY[worst(verdicts)] == max(_SEVERITY[v] for v in verdicts)


def test_same_snapshot_and_engine_version_reproduces_identical_findings(make_ctx):
    ctx = make_ctx(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    first, second = evaluate(ctx), evaluate(ctx)
    assert first == second


def test_editing_a_source_record_does_not_mutate_a_stored_evaluation(make_ctx, seed):
    ctx = make_ctx(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    stored = evaluate(ctx)
    before = stored.findings

    edited = dict(seed.enzymes)
    edited[LACTASE] = dataclasses.replace(
        edited[LACTASE], ph_shelf_stable_min=Tracked(2.0, TruthLabel.CONFIRMED, "supplier")
    )
    rerun = evaluate(make_ctx(
        fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",),
        enzyme_catalog=edited,
    ))

    assert stored.findings is before          # the stored object is untouched
    assert rerun.findings != stored.findings  # and the re-run genuinely differs
