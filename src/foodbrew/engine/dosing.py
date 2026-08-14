"""Dose arithmetic for R7 (spec §6.1, KB §4g)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DoseAssessment:
    meets_threshold: bool
    ratio: float
    #: True when the dose exceeds the confirmed benchmark maximum.
    above_benchmark_max: bool


def assess_dose(
    dose: float, threshold: float, benchmark_max: float | None
) -> DoseAssessment:
    """Compare a per-serving dose against the evidence threshold.

    Spec §6.1 R7: an underdosed enzyme behaves like placebo, so the threshold is
    a floor, not a target. Overdosing works but is an expensive way to solve it.
    """
    return DoseAssessment(
        meets_threshold=dose >= threshold,
        ratio=dose / threshold if threshold else float("inf"),
        above_benchmark_max=benchmark_max is not None and dose > benchmark_max,
    )
