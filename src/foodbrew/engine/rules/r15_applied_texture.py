"""R15 — applied-food texture (spec §6.2, KB §4e extended to the plate).

Scope is what the dressing does to the food it is poured on, over time. What it
does to itself in the jar is R8.
"""

from __future__ import annotations

from foodbrew.engine.texture import verdict_for_tier
from foodbrew.engine.types import (
    DwellProfile,
    EvalContext,
    RuleFinding,
    Verdict,
    worst,
)

RULE_ID = "R15"
ADVISORY = False


def _pairs(ctx: EvalContext):
    """Yield (enzyme, food, structural_entry) for every degrading intersection."""
    for selected in ctx.selected_enzymes():
        enzyme = ctx.enzyme_for(selected)
        if not enzyme.degrades_structural:
            continue
        for food_id in ctx.formulation.application_food_ids:
            food = ctx.foods.get(food_id)
            if food is None or not food.structural:
                continue
            for entry in enzyme.degrades_structural:
                if entry.structural_class in food.structural:
                    yield enzyme, food, entry


def envelope(ctx: EvalContext) -> dict[DwellProfile, Verdict]:
    """Worst verdict per dwell profile across every intersecting pair.

    Overlap never compounds severity beyond the worst single pair: no source
    supports an additive model (spec §6.2 R15).
    """
    result = {profile: [] for profile in DwellProfile}
    for _enzyme, _food, entry in _pairs(ctx):
        for profile in DwellProfile:
            result[profile].append(verdict_for_tier(entry.tier, profile))
    return {profile: worst(verdicts) for profile, verdicts in result.items()}


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    findings: list[RuleFinding] = []

    for enzyme, food, entry in _pairs(ctx):
        per_profile = {p: verdict_for_tier(entry.tier, p) for p in DwellProfile}
        evidence = {
            "structural_class": entry.structural_class.value,
            "tier": entry.tier.value,
            "envelope": {p.value: v.value for p, v in per_profile.items()},
        }

        if entry.tier.value == "unconfirmed":
            message = (
                f"{enzyme.name} may act on the {entry.structural_class.value} that "
                f"{food.name.lower()} depends on for texture, but no source confirms "
                f"whether it does or how fast. Cannot assess."
            )
        else:
            failing = [p.value for p, v in per_profile.items() if v is not Verdict.PASS]
            message = (
                f"{enzyme.name} degrades the {entry.structural_class.value} that "
                f"{food.name.lower()} depends on for texture. Affected use occasions: "
                f"{', '.join(failing)}."
            )

        findings.append(
            RuleFinding(
                RULE_ID, worst(per_profile.values()), message, evidence,
                enzyme_id=enzyme.id, food_id=food.id,
            )
        )

    return findings
