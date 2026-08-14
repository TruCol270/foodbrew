"""Spec §6.4 — aggregation, and R13's headline mapping."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from foodbrew.engine.texture import headline_contribution
from foodbrew.engine.types import DwellProfile, RuleFinding, Verdict, worst

#: Spec §6.4 — headline display is one-to-one with the aggregated verdict.
HEADLINE_DISPLAY: Mapping[Verdict, str] = {
    Verdict.RED: "RED",
    Verdict.CANNOT_ASSESS: "GRAY",
    Verdict.AMBER: "AMBER",
    Verdict.PASS: "GREEN",
}


@dataclass(frozen=True, slots=True)
class Aggregation:
    overall: Verdict
    display: str
    blockers: tuple[RuleFinding, ...]
    data_gaps: tuple[RuleFinding, ...]
    cautions: tuple[RuleFinding, ...]
    advisories: tuple[RuleFinding, ...]


def aggregate(
    findings: Sequence[RuleFinding],
    envelope: Mapping[DwellProfile, Verdict],
    declared_profile: DwellProfile | None,
) -> Aggregation:
    """Overall flag = worst headline-capable verdict, plus R15's envelope contribution.

    R15's own findings are excluded from the direct worst-of: its contribution is
    computed from the envelope under spec §6.4's special rule, so counting both
    would double-count it.
    """
    headline_verdicts = [
        f.verdict for f in findings if not f.advisory and f.rule_id != "R15"
    ]
    headline_verdicts.append(headline_contribution(envelope, declared_profile))
    overall = worst(headline_verdicts)

    advisories = tuple(f for f in findings if f.advisory)
    non_advisory = [f for f in findings if not f.advisory]

    return Aggregation(
        overall=overall,
        display=HEADLINE_DISPLAY[overall],
        blockers=tuple(f for f in non_advisory if f.verdict is Verdict.RED),
        data_gaps=tuple(f for f in non_advisory if f.verdict is Verdict.CANNOT_ASSESS),
        cautions=tuple(f for f in non_advisory if f.verdict is Verdict.AMBER),
        advisories=advisories,
    )
