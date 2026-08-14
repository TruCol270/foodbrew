import pytest

from foodbrew.engine.texture import (
    SEVERITY_TABLE, dwell_bucket, headline_contribution, verdict_for_tier,
)
from foodbrew.engine.types import DwellProfile, SeverityTier, Verdict


@pytest.mark.parametrize(
    "minutes,expected",
    [
        (0, DwellProfile.IMMEDIATE),
        (59, DwellProfile.IMMEDIATE),
        (60, DwellProfile.PACKED),
        (479, DwellProfile.PACKED),
        (480, DwellProfile.MARINADE),
        (1440, DwellProfile.MARINADE),
    ],
)
def test_dwell_bucket_boundaries(minutes, expected):
    # Spec §6.3 and §13 fixture (o2) — exhaustive, non-overlapping, inclusive.
    assert dwell_bucket(minutes) is expected


def test_dwell_bucket_rejects_negative():
    with pytest.raises(ValueError):
        dwell_bucket(-1)


def test_rapid_tier_is_red_at_every_profile():
    for profile in DwellProfile:
        assert verdict_for_tier(SeverityTier.RAPID, profile) is Verdict.RED


def test_gradual_tier_worsens_with_dwell():
    assert verdict_for_tier(SeverityTier.GRADUAL, DwellProfile.IMMEDIATE) is Verdict.PASS
    assert verdict_for_tier(SeverityTier.GRADUAL, DwellProfile.PACKED) is Verdict.AMBER
    assert verdict_for_tier(SeverityTier.GRADUAL, DwellProfile.MARINADE) is Verdict.RED


def test_unconfirmed_tier_is_cannot_assess_everywhere():
    for profile in DwellProfile:
        assert verdict_for_tier(SeverityTier.UNCONFIRMED, profile) is Verdict.CANNOT_ASSESS


def test_severity_table_is_total():
    for tier in SeverityTier:
        for profile in DwellProfile:
            assert SEVERITY_TABLE[tier][profile] in set(Verdict)


def test_headline_red_when_declared_profile_is_red():
    envelope = {
        DwellProfile.IMMEDIATE: Verdict.PASS,
        DwellProfile.PACKED: Verdict.AMBER,
        DwellProfile.MARINADE: Verdict.RED,
    }
    assert headline_contribution(envelope, DwellProfile.MARINADE) is Verdict.RED


def test_headline_amber_when_undeclared_and_not_all_red():
    envelope = {
        DwellProfile.IMMEDIATE: Verdict.PASS,
        DwellProfile.PACKED: Verdict.AMBER,
        DwellProfile.MARINADE: Verdict.RED,
    }
    assert headline_contribution(envelope, None) is Verdict.AMBER


def test_headline_red_when_all_three_profiles_red():
    envelope = dict.fromkeys(DwellProfile, Verdict.RED)
    assert headline_contribution(envelope, None) is Verdict.RED


def test_headline_pass_when_envelope_is_clean():
    envelope = dict.fromkeys(DwellProfile, Verdict.PASS)
    assert headline_contribution(envelope, None) is Verdict.PASS


def test_headline_amber_when_envelope_has_cannot_assess():
    envelope = dict.fromkeys(DwellProfile, Verdict.CANNOT_ASSESS)
    assert headline_contribution(envelope, None) is Verdict.AMBER
