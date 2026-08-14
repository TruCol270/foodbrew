"""R10 — strain blending (spec §6.1, KB §4k). Advisory, never a failure."""

from __future__ import annotations

from foodbrew.engine.gi_model import active_regions, regions_before_deadline
from foodbrew.engine.types import EvalContext, RuleFinding, Verdict

RULE_ID = "R10"
ADVISORY = True

#: Suggest a complementary source when the enzyme covers at most this many of
#: the regions it could usefully work in before its deadline.
_NARROW_WINDOW_MAX_REGIONS = 1


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    if not ctx.gi_regions:
        return []

    findings: list[RuleFinding] = []
    for selected in ctx.selected_enzymes():
        enzyme = ctx.enzyme_for(selected)
        if not (enzyme.ph_min.usable and enzyme.ph_max.usable):
            continue

        allowed = {r.id for r in regions_before_deadline(enzyme.deadline, ctx.gi_regions)}
        active_before = [
            r.id for r in active_regions(enzyme, ctx.gi_regions) if r.id in allowed
        ]
        if len(active_before) > _NARROW_WINDOW_MAX_REGIONS or not active_before:
            continue

        findings.append(
            RuleFinding(
                RULE_ID, Verdict.PASS,
                f"{enzyme.name} is active in only {', '.join(active_before)} before its "
                f"deadline. Pairing a complementary source — an acid variant with a "
                f"neutral one, the way Enzymedica blends strains — would widen the active "
                f"window across more of the tract.",
                {
                    "active_before_deadline": active_before,
                    "ph_min": float(enzyme.ph_min.value),
                    "ph_max": float(enzyme.ph_max.value),
                },
                enzyme_id=enzyme.id,
            )
        )

    return findings
