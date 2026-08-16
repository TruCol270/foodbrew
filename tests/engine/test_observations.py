"""Spec §6.3's Observed column, §6.6's tiers and split, and decision #9's convention."""

import pytest

from foodbrew.engine.observations import (
    SYMPTOM_EXPORT_CLASS,
    TEXTURE_SCALE,
    ExportClass,
    ObservationRecord,
    ObservationType,
    export_class,
    observed_envelope,
    texture_verdict,
)
from foodbrew.engine.trial_rules import ConfidenceTier
from foodbrew.engine.types import DwellProfile, TruthLabel, Verdict


def obs(**kw) -> ObservationRecord:
    base = dict(
        id="o1", type=ObservationType.FOOD_TEXTURE, observed_at="2026-08-15T12:00:00+00:00",
        elapsed_minutes=0, score=1,
    )
    return ObservationRecord(**{**base, **kw})


@pytest.mark.parametrize(
    "score,expected",
    [(1, Verdict.PASS), (2, Verdict.PASS), (3, Verdict.AMBER), (4, Verdict.RED), (5, Verdict.RED)],
)
def test_the_stated_scale_maps_to_a_verdict(score, expected):
    assert texture_verdict(score) is expected


def test_the_scale_has_wording_for_every_score_it_maps():
    assert sorted(TEXTURE_SCALE) == [1, 2, 3, 4, 5]


def test_a_score_off_the_scale_is_refused_rather_than_clamped():
    with pytest.raises(ValueError):
        texture_verdict(6)


def test_an_observation_derives_its_bucket_from_elapsed_minutes():
    assert obs(elapsed_minutes=59).dwell_bucket is DwellProfile.IMMEDIATE
    assert obs(elapsed_minutes=60).dwell_bucket is DwellProfile.PACKED
    assert obs(elapsed_minutes=480).dwell_bucket is DwellProfile.MARINADE


def test_every_observation_is_labelled_observed():
    assert obs().status is TruthLabel.OBSERVED


def test_the_default_tier_is_anecdote_and_either_flag_lifts_it():
    assert obs().tier is ConfidenceTier.ANECDOTE
    assert obs(was_blinded=True).tier is ConfidenceTier.SUGGESTIVE
    assert obs(had_undressed_control=True).tier is ConfidenceTier.SUGGESTIVE


def test_an_empty_bucket_reports_nothing_rather_than_a_pass():
    envelope = observed_envelope([])
    assert set(envelope) == set(DwellProfile)
    assert all(cell.verdict is None and cell.observation_count == 0 for cell in envelope.values())


def test_the_worst_scored_observation_in_a_bucket_sets_that_cell():
    envelope = observed_envelope([
        obs(id="a", elapsed_minutes=60, score=1),
        obs(id="b", elapsed_minutes=200, score=4),
        obs(id="c", elapsed_minutes=300, score=3),
    ])
    cell = envelope[DwellProfile.PACKED]
    assert cell.verdict is Verdict.RED
    assert cell.observation_count == 3
    assert cell.driving_observation_id == "b"
    assert envelope[DwellProfile.IMMEDIATE].verdict is None


def test_a_rigorous_reading_does_not_lend_its_tier_to_an_unblinded_one():
    envelope = observed_envelope([
        obs(id="a", score=4, had_undressed_control=True),
        obs(id="b", score=4),
    ])
    assert envelope[DwellProfile.IMMEDIATE].tier is ConfidenceTier.ANECDOTE

    controlled_only = observed_envelope([obs(id="a", score=4, had_undressed_control=True)])
    assert controlled_only[DwellProfile.IMMEDIATE].tier is ConfidenceTier.SUGGESTIVE


def test_taste_and_usability_never_reach_the_envelope():
    envelope = observed_envelope([
        obs(type=ObservationType.TASTE, score=5),
        obs(type=ObservationType.USABILITY, score=5),
        obs(type=ObservationType.STORAGE, score=5),
    ])
    assert all(cell.verdict is None for cell in envelope.values())


def test_an_unscored_texture_note_is_a_comment_not_a_reading():
    envelope = observed_envelope([obs(score=None, free_text="looked fine")])
    assert envelope[DwellProfile.IMMEDIATE].verdict is None


def test_the_export_split_follows_6_6():
    assert export_class(obs(type=ObservationType.TASTE)) is ExportClass.FINDING
    assert export_class(obs(type=ObservationType.USABILITY)) is ExportClass.FINDING
    assert export_class(obs(had_undressed_control=True)) is ExportClass.FINDING
    assert export_class(obs(had_undressed_control=False)) is ExportClass.OBSERVATION
    assert export_class(obs(type=ObservationType.STORAGE)) is ExportClass.OBSERVATION
    assert SYMPTOM_EXPORT_CLASS is ExportClass.HYPOTHESIS


def test_blinding_alone_does_not_promote_texture_to_a_finding():
    """§6.6: the texture question is promoted by the control, which is the thing
    that makes it partly objective. Blinding lifts the tier, not the class."""
    record = obs(was_blinded=True, had_undressed_control=False)
    assert record.tier is ConfidenceTier.SUGGESTIVE
    assert export_class(record) is ExportClass.OBSERVATION


def test_no_observation_type_is_symptom():
    assert "symptom" not in {str(t) for t in ObservationType}
