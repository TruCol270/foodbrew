from foodbrew.engine import ValidationRejection
from foodbrew.engine.flags import HEADLINE_DISPLAY, aggregate, group_findings
from foodbrew.engine.types import DwellProfile, RuleFinding, Verdict


def _f(rule_id, verdict, advisory=False):
    return RuleFinding(rule_id, verdict, "m", {}, advisory=advisory)


CLEAN_ENVELOPE = dict.fromkeys(DwellProfile, Verdict.PASS)


def test_headline_takes_the_worst_headline_capable_verdict():
    findings = [_f("R1", Verdict.PASS), _f("R4", Verdict.AMBER), _f("R5", Verdict.RED)]
    assert aggregate(findings, CLEAN_ENVELOPE, None).overall is Verdict.RED


def test_advisory_rules_can_never_set_the_headline():
    findings = [
        _f("R1", Verdict.PASS),
        _f("R8", Verdict.AMBER, advisory=True),
        _f("R9", Verdict.AMBER, advisory=True),
        _f("R12", Verdict.CANNOT_ASSESS, advisory=True),
        _f("R16", Verdict.CANNOT_ASSESS, advisory=True),
    ]
    assert aggregate(findings, CLEAN_ENVELOPE, None).overall is Verdict.PASS


def test_r12_promoted_finding_does_set_the_headline():
    # Spec §13 fixture (h2) — promotion is per-finding, not per-module.
    findings = [_f("R1", Verdict.PASS), _f("R12", Verdict.RED, advisory=False)]
    assert aggregate(findings, CLEAN_ENVELOPE, None).overall is Verdict.RED


def test_cannot_assess_outranks_amber():
    findings = [_f("R4", Verdict.AMBER), _f("R7", Verdict.CANNOT_ASSESS)]
    assert aggregate(findings, CLEAN_ENVELOPE, None).overall is Verdict.CANNOT_ASSESS


def test_r15_envelope_contributes_amber_when_undeclared():
    envelope = {
        DwellProfile.IMMEDIATE: Verdict.PASS,
        DwellProfile.PACKED: Verdict.AMBER,
        DwellProfile.MARINADE: Verdict.RED,
    }
    assert aggregate([_f("R1", Verdict.PASS)], envelope, None).overall is Verdict.AMBER


def test_r15_envelope_contributes_red_when_declared_profile_fails():
    envelope = {
        DwellProfile.IMMEDIATE: Verdict.PASS,
        DwellProfile.PACKED: Verdict.AMBER,
        DwellProfile.MARINADE: Verdict.RED,
    }
    result = aggregate([_f("R1", Verdict.PASS)], envelope, DwellProfile.MARINADE)
    assert result.overall is Verdict.RED


def test_r15_raw_findings_do_not_double_count():
    # R15's contribution comes from the envelope, not from its own findings.
    envelope = dict.fromkeys(DwellProfile, Verdict.PASS)
    findings = [_f("R1", Verdict.PASS), _f("R15", Verdict.RED)]
    assert aggregate(findings, envelope, None).overall is Verdict.PASS


def test_display_mapping_covers_all_four_states():
    assert HEADLINE_DISPLAY[Verdict.RED] == "RED"
    assert HEADLINE_DISPLAY[Verdict.CANNOT_ASSESS] == "GRAY"
    assert HEADLINE_DISPLAY[Verdict.AMBER] == "AMBER"
    assert HEADLINE_DISPLAY[Verdict.PASS] == "GREEN"


def test_findings_are_grouped_for_display():
    findings = [
        _f("R5", Verdict.RED),
        _f("R7", Verdict.CANNOT_ASSESS),
        _f("R4", Verdict.AMBER),
        _f("R9", Verdict.AMBER, advisory=True),
    ]
    result = aggregate(findings, CLEAN_ENVELOPE, None)
    assert [f.rule_id for f in result.blockers] == ["R5"]
    assert [f.rule_id for f in result.data_gaps] == ["R7"]
    assert [f.rule_id for f in result.cautions] == ["R4"]
    assert [f.rule_id for f in result.advisories] == ["R9"]


def test_validation_rejection_is_importable_from_the_engine_package():
    assert issubclass(ValidationRejection, ValueError)


def test_group_findings_splits_by_verdict_and_excludes_advisories():
    findings = (
        RuleFinding("R1", Verdict.RED, "blocker"),
        RuleFinding("R7", Verdict.CANNOT_ASSESS, "gap"),
        RuleFinding("R4", Verdict.AMBER, "caution"),
        RuleFinding("R3", Verdict.PASS, "fine"),
        RuleFinding("R9", Verdict.AMBER, "advice", advisory=True),
    )
    groups = group_findings(findings)
    assert [f.rule_id for f in groups.blockers] == ["R1"]
    assert [f.rule_id for f in groups.data_gaps] == ["R7"]
    assert [f.rule_id for f in groups.cautions] == ["R4"]
    assert [f.rule_id for f in groups.advisories] == ["R9"]


def test_aggregate_reports_the_same_groups_as_group_findings():
    findings = (
        RuleFinding("R1", Verdict.RED, "blocker"),
        RuleFinding("R9", Verdict.AMBER, "advice", advisory=True),
    )
    envelope = {p: Verdict.PASS for p in DwellProfile}
    agg = aggregate(findings, envelope, None)
    groups = group_findings(findings)
    assert (agg.blockers, agg.data_gaps, agg.cautions, agg.advisories) == (
        groups.blockers, groups.data_gaps, groups.cautions, groups.advisories,
    )
