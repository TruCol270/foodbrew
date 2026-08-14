"""Orchestrator — runs every rule, aggregates, and returns a frozen Evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from foodbrew import ENGINE_VERSION
from foodbrew.engine.flags import aggregate
from foodbrew.engine.rules import ALL_RULES, r15_applied_texture
from foodbrew.engine.types import DwellProfile, EvalContext, RuleFinding, Verdict


@dataclass(frozen=True, slots=True)
class Evaluation:
    engine_version: str
    overall: Verdict
    display: str
    findings: tuple[RuleFinding, ...]
    envelope: Mapping[DwellProfile, Verdict]
    blockers: tuple[RuleFinding, ...]
    data_gaps: tuple[RuleFinding, ...]
    cautions: tuple[RuleFinding, ...]
    advisories: tuple[RuleFinding, ...]


def evaluate(ctx: EvalContext) -> Evaluation:
    """Run the whole rule set against one formulation.

    Rules run in registry order so findings are stable, which is what makes a
    stored snapshot reproducible byte-for-byte on the same engine version.
    """
    findings: list[RuleFinding] = []
    for module in ALL_RULES:
        produced = module.evaluate(ctx)
        for finding in produced:
            # A module's static ADVISORY is the default; a rule may override it
            # per finding (R12's per-enzyme promotion).
            if module.ADVISORY and not finding.advisory:
                finding = RuleFinding(
                    finding.rule_id, finding.verdict, finding.message, finding.evidence,
                    finding.enzyme_id, finding.food_id, advisory=True,
                )
            findings.append(finding)

    envelope = r15_applied_texture.envelope(ctx)
    agg = aggregate(findings, envelope, ctx.formulation.dwell_profile)

    return Evaluation(
        engine_version=ENGINE_VERSION,
        overall=agg.overall,
        display=agg.display,
        findings=tuple(findings),
        envelope=envelope,
        blockers=agg.blockers,
        data_gaps=agg.data_gaps,
        cautions=agg.cautions,
        advisories=agg.advisories,
    )
