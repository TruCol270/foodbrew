"""R6 — encapsulation semantics (spec §6.1, KB §4f).

Encapsulation is a timing control, not immunity. It delays exposure; it cannot
rescue an enzyme from a condition that denatures it on contact.
"""

from __future__ import annotations

from foodbrew.engine.conventions import resolve_recipe_ph
from foodbrew.engine.rules.r01_ph_survival import FALLBACK_MARGIN_PH
from foodbrew.engine.types import EvalContext, Format, Phase, RuleFinding, Verdict

RULE_ID = "R6"
ADVISORY = False


def _floor(enzyme) -> tuple[float | None, str]:
    if enzyme.ph_shelf_stable_min.usable:
        return float(enzyme.ph_shelf_stable_min.value), "ph_shelf_stable_min"
    if enzyme.ph_min.usable:
        return float(enzyme.ph_min.value) + FALLBACK_MARGIN_PH, "fallback"
    return None, "unavailable"


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    fmt = ctx.formulation.format
    encapsulated = [
        s for s in ctx.selected_enzymes() if s.encapsulated and s.phase is Phase.WET
    ]
    if not encapsulated:
        return []

    if fmt is Format.DUAL_CHAMBER:
        return [
            RuleFinding(
                RULE_ID, Verdict.PASS,
                "Under a dual chamber the capsule only has to survive minutes in the "
                "dressing plus the trip through the stomach, not months in acid. That is "
                "a bar encapsulation can meet.",
                {"format": fmt.value, "encapsulated": [s.enzyme_id for s in encapsulated]},
            )
        ]

    if fmt is not Format.ENCAPSULATED_IN_WET:
        return []

    ph = resolve_recipe_ph(ctx.formulation, ctx.foods, ctx.latest_trial_ph)
    findings: list[RuleFinding] = []

    for selected in encapsulated:
        enzyme = ctx.enzyme_for(selected)
        floor, floor_source = _floor(enzyme)

        if floor is None or ph.value is None:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.CANNOT_ASSESS,
                    f"{enzyme.name}: cannot judge whether encapsulation is being asked to "
                    f"do too much, because the recipe pH or the enzyme's pH floor is "
                    f"unconfirmed.",
                    {"blocking_field": ph.blocking_field or f"{enzyme.id}.ph_min"},
                    enzyme_id=enzyme.id,
                )
            )
            continue

        evidence = {
            "recipe_ph": ph.value, "floor": floor, "floor_source": floor_source,
            "format": fmt.value,
        }
        if ph.value < floor:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.RED,
                    f"{enzyme.name}: the capsule is the only thing between the enzyme and "
                    f"a pH of {ph.value}, below its {floor} floor, for the whole shelf "
                    f"life. Encapsulation buys time but cannot rescue an enzyme from a "
                    f"condition that would deactivate it on contact. Move to a dual "
                    f"chamber or a dry sachet.",
                    evidence, enzyme_id=enzyme.id,
                )
            )
        else:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.PASS,
                    f"{enzyme.name}: the surrounding pH of {ph.value} is above its {floor} "
                    f"floor, so the capsule is delaying exposure rather than holding back "
                    f"a condition that would kill it outright.",
                    evidence, enzyme_id=enzyme.id,
                )
            )

    return findings
