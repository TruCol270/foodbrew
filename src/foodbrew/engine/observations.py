"""Spec §6.6 and §6.3 — what a trial observation means, and what it does not.

Pure, and deliberately inert: nothing here mutates a prediction. The observed
envelope is a second column computed beside the stored one (plan decision #10),
and no function in this module can change a verdict, a finding, or a headline.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from foodbrew.engine.texture import dwell_bucket
from foodbrew.engine.trial_rules import ConfidenceTier, confidence_tier
from foodbrew.engine.types import DwellProfile, TruthLabel, Verdict, worst


class ObservationType(StrEnum):
    """Spec §5.3. Closed, and deliberately without `symptom`: symptoms are their
    own table so per-meal dose linkage is never bypassed (plan decision #6)."""

    TASTE = "taste"
    USABILITY = "usability"
    FOOD_TEXTURE = "food_texture"
    STORAGE = "storage"


#: Plan decision #9. An engineering convention that makes §6.3's Observed column
#: computable, stated wherever it is shown, NOT a scientific claim — the same
#: standing as conventions.FALLBACK_MARGIN_PH. The founder scores against this
#: wording, so the wording is the interface.
TEXTURE_SCALE: Mapping[int, str] = {
    1: "indistinguishable from the undressed portion",
    2: "slightly softer — would not notice without comparing",
    3: "clearly softer than the undressed portion",
    4: "limp, wilted, or watery",
    5: "badly broken down",
}

_TEXTURE_VERDICT: Mapping[int, Verdict] = {
    1: Verdict.PASS,
    2: Verdict.PASS,
    3: Verdict.AMBER,
    4: Verdict.RED,
    5: Verdict.RED,
}

#: Shown next to every observed verdict, so the column never reads as a measurement.
TEXTURE_SCALE_NOTE = (
    "Observed texture is scored 1 to 5 against the undressed portion and mapped to "
    "a verdict by a stated convention, not by a measurement."
)


def texture_verdict(score: int) -> Verdict:
    """Spec §6.3's Observed column, via the decision #9 convention."""
    if score not in _TEXTURE_VERDICT:
        raise ValueError(f"texture score must be 1 to 5, got {score}")
    return _TEXTURE_VERDICT[score]


@dataclass(frozen=True, slots=True)
class ObservationRecord:
    """One row of `trial_observation` (§5.3), as the engine sees it."""

    id: str
    type: ObservationType
    observed_at: str
    elapsed_minutes: int
    score: int | None = None
    free_text: str = ""
    was_blinded: bool = False
    had_undressed_control: bool = False
    application_food_id: str = ""

    @property
    def dwell_bucket(self) -> DwellProfile:
        """Spec §6.3 — derived from elapsed minutes and from nothing else."""
        return dwell_bucket(self.elapsed_minutes)

    @property
    def tier(self) -> ConfidenceTier:
        """Spec §6.6 — rigor captured opportunistically, per observation."""
        return confidence_tier(
            was_blinded=self.was_blinded,
            had_undressed_control=self.had_undressed_control,
        )

    @property
    def status(self) -> TruthLabel:
        """Every trial value is `observed` (§5.4). The tier qualifies it; nothing
        upgrades it, and no prediction ever overwrites it."""
        return TruthLabel.OBSERVED


@dataclass(frozen=True, slots=True)
class ObservedProfile:
    """One cell of §6.3's Observed column."""

    #: None means nothing was recorded in this bucket — never a pass by default.
    verdict: Verdict | None
    tier: ConfidenceTier | None
    observation_count: int
    #: The observation that set the verdict, for "why does it say that".
    driving_observation_id: str = ""


def observed_envelope(
    observations: Sequence[ObservationRecord],
) -> dict[DwellProfile, ObservedProfile]:
    """Spec §6.3 — the worst scored texture observation in each dwell bucket.

    Only `food_texture` observations with a score contribute: taste and
    usability answer different questions, and an unscored note is a comment,
    not a reading. An empty bucket reports None, because "she has not looked
    yet" and "she looked and it was fine" are different facts.
    """
    out: dict[DwellProfile, ObservedProfile] = {}
    for profile in DwellProfile:
        scored = [
            o
            for o in observations
            if o.type is ObservationType.FOOD_TEXTURE
            and o.score is not None
            and o.dwell_bucket is profile
        ]
        if not scored:
            out[profile] = ObservedProfile(None, None, 0)
            continue

        verdict = worst(texture_verdict(o.score) for o in scored)
        drivers = [o for o in scored if texture_verdict(o.score) is verdict]
        # Weakest tier among the drivers: one blinded reading does not lend its
        # rigor to an unblinded one that reached the same verdict.
        tier = (
            ConfidenceTier.SUGGESTIVE
            if all(o.tier is ConfidenceTier.SUGGESTIVE for o in drivers)
            else ConfidenceTier.ANECDOTE
        )
        out[profile] = ObservedProfile(
            verdict=verdict,
            tier=tier,
            observation_count=len(scored),
            driving_observation_id=drivers[0].id,
        )
    return out


class ExportClass(StrEnum):
    """Spec §6.6 — how much the founder's own judgement counts as evidence."""

    FINDING = "finding"
    OBSERVATION = "observation"
    HYPOTHESIS = "hypothesis"


#: Spec §6.6 — symptom response is the weakest measurement available: unblinded
#: self-report on a product she is invested in. It is never anything but a
#: hypothesis, whatever flags the entry carries.
SYMPTOM_EXPORT_CLASS = ExportClass.HYPOTHESIS


def export_class(record: ObservationRecord) -> ExportClass:
    """Spec §6.6's split, applied per observation.

    Taste and usability are subjective questions by nature, so her answer *is*
    the data. Applied-food texture is partly objective and cheaply controlled,
    so it is a finding when she used the undressed control and an observation
    when she did not. Storage is uncontrolled watching, so it is an observation;
    §6.6 does not name it, and calling it a finding would be the generous read.
    """
    if record.type in {ObservationType.TASTE, ObservationType.USABILITY}:
        return ExportClass.FINDING
    if record.type is ObservationType.FOOD_TEXTURE and record.had_undressed_control:
        return ExportClass.FINDING
    return ExportClass.OBSERVATION
