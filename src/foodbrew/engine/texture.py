"""Spec §6.3 / §6.3.1 — the occasion envelope and its severity mapping."""

from __future__ import annotations

from collections.abc import Mapping

from foodbrew.engine.types import DwellProfile, SeverityTier, Verdict

#: Spec §6.3 — exhaustive, non-overlapping, boundary-inclusive ranges in minutes.
_BUCKET_BOUNDS: tuple[tuple[int, int | None, DwellProfile], ...] = (
    (0, 59, DwellProfile.IMMEDIATE),
    (60, 479, DwellProfile.PACKED),
    (480, None, DwellProfile.MARINADE),
)

#: Spec §6.3.1. No shipped seed enzyme uses RAPID — it exists so the mapping is
#: total and a future confirmed fast-acting case has somewhere to go.
SEVERITY_TABLE: Mapping[SeverityTier, Mapping[DwellProfile, Verdict]] = {
    SeverityTier.RAPID: {
        DwellProfile.IMMEDIATE: Verdict.RED,
        DwellProfile.PACKED: Verdict.RED,
        DwellProfile.MARINADE: Verdict.RED,
    },
    SeverityTier.GRADUAL: {
        DwellProfile.IMMEDIATE: Verdict.PASS,
        DwellProfile.PACKED: Verdict.AMBER,
        DwellProfile.MARINADE: Verdict.RED,
    },
    SeverityTier.UNCONFIRMED: {
        DwellProfile.IMMEDIATE: Verdict.CANNOT_ASSESS,
        DwellProfile.PACKED: Verdict.CANNOT_ASSESS,
        DwellProfile.MARINADE: Verdict.CANNOT_ASSESS,
    },
}


def dwell_bucket(elapsed_minutes: int) -> DwellProfile:
    """Spec §6.3 — derive the dwell profile from elapsed minutes and nothing else."""
    if elapsed_minutes < 0:
        raise ValueError("elapsed_minutes cannot be negative")
    for low, high, profile in _BUCKET_BOUNDS:
        if elapsed_minutes >= low and (high is None or elapsed_minutes <= high):
            return profile
    raise ValueError(f"no dwell bucket for {elapsed_minutes}")  # pragma: no cover


def verdict_for_tier(tier: SeverityTier, profile: DwellProfile) -> Verdict:
    return SEVERITY_TABLE[tier][profile]


def headline_contribution(
    envelope: Mapping[DwellProfile, Verdict], declared: DwellProfile | None
) -> Verdict:
    """Spec §6.4 — how R15's envelope contributes to the overall flag.

    A formulation that is fine for table-dressing is not failed by a marinade
    scenario the founder may never support; but the failing occasion is never
    hidden either.
    """
    if declared is not None and envelope.get(declared) is Verdict.RED:
        return Verdict.RED
    if all(v is Verdict.RED for v in envelope.values()):
        return Verdict.RED
    if any(v is not Verdict.PASS for v in envelope.values()):
        return Verdict.AMBER
    return Verdict.PASS
