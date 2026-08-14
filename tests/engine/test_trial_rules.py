import pytest

from foodbrew.engine.trial_rules import (
    ACIDIFIED_FOOD_PH_LIMIT, ConfidenceTier, ambient_storage_allowed, confidence_tier,
)


def test_default_observation_is_an_anecdote():
    # Spec §13 fixture (p) — solo, unblinded, no control.
    assert confidence_tier(was_blinded=False, had_undressed_control=False) is ConfidenceTier.ANECDOTE


def test_blinding_upgrades_to_suggestive():
    assert confidence_tier(was_blinded=True, had_undressed_control=False) is ConfidenceTier.SUGGESTIVE


def test_undressed_control_upgrades_to_suggestive():
    assert confidence_tier(was_blinded=False, had_undressed_control=True) is ConfidenceTier.SUGGESTIVE


def test_both_flags_still_only_reach_suggestive():
    # Nothing recorded at home is ever demonstrated, proven, or validated.
    assert confidence_tier(was_blinded=True, had_undressed_control=True) is ConfidenceTier.SUGGESTIVE


def test_no_tier_stronger_than_suggestive_exists():
    assert set(ConfidenceTier) == {ConfidenceTier.ANECDOTE, ConfidenceTier.SUGGESTIVE}


def test_acidified_food_limit_is_four_point_six():
    assert ACIDIFIED_FOOD_PH_LIMIT == 4.6


@pytest.mark.parametrize("ph,expected", [(4.1, True), (4.5, True), (4.6, False), (5.2, False)])
def test_ambient_storage_gate(ph, expected):
    # Spec §13 fixture (q) and Workflow E — 21 CFR 114 acidified-foods line.
    assert ambient_storage_allowed(ph) is expected


def test_ambient_storage_denied_without_a_measured_ph():
    assert ambient_storage_allowed(None) is False
