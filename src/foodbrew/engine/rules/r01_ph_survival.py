"""R1 — in-jar pH survival (spec §6.1, KB §4a)."""

from __future__ import annotations

from foodbrew.engine.conventions import (
    FALLBACK_MARGIN_PH,
    WET_FORMATS,
    resolve_recipe_ph,
    shelf_stable_floor,
)
from foodbrew.engine.types import (
    EvalContext,
    Phase,
    RuleFinding,
    Verdict,
)

RULE_ID = "R1"
ADVISORY = False


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    # Formats where an enzyme in the wet phase sits in liquid for shelf
    # duration — same set Task 2 extracted for phase_for_format, routed
    # through here rather than a second, value-identical local copy.
    if ctx.formulation.format not in WET_FORMATS:
        return []

    findings: list[RuleFinding] = []
    ph = resolve_recipe_ph(ctx.formulation, ctx.foods, ctx.latest_trial_ph)

    for selected in ctx.selected_enzymes():
        if selected.phase is not Phase.WET:
            continue
        enzyme = ctx.enzyme_for(selected)

        if not enzyme.ph_min.usable:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.CANNOT_ASSESS,
                    f"{enzyme.name}: cannot assess in-jar pH survival because "
                    f"ph_min is unconfirmed. Confirm with the supplier.",
                    {"missing_field": f"{enzyme.id}.ph_min"},
                    enzyme_id=enzyme.id,
                )
            )
            continue

        if ph.value is None:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.CANNOT_ASSESS,
                    f"{enzyme.name}: cannot assess in-jar pH survival because the "
                    f"recipe pH could not be resolved ({ph.blocking_field}). Enter a "
                    f"measured pH for this formulation, or confirm the ingredient data.",
                    {"blocking_field": ph.blocking_field, "ph_origin": ph.origin},
                    enzyme_id=enzyme.id,
                )
            )
            continue

        floor_resolution = shelf_stable_floor(enzyme)
        floor = floor_resolution.value
        floor_source = floor_resolution.source
        heuristic_note = (
            " This uses the stated margin heuristic (ph_min + "
            f"{FALLBACK_MARGIN_PH}) because no shelf-stable floor is confirmed — "
            "supplier confirmation required."
            if floor_resolution.is_heuristic
            else ""
        )

        evidence = {
            "recipe_ph": ph.value,
            "ph_origin": ph.origin,
            "ph_status": ph.status.value,
            "driving_food_id": ph.driving_food_id,
            "floor": floor,
            "floor_source": floor_source,
            "ph_min": float(enzyme.ph_min.value),
            "fallback_floor": float(enzyme.ph_min.value) + FALLBACK_MARGIN_PH,
        }

        if ph.value < floor:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.RED,
                    f"{enzyme.name}: recipe pH {ph.value} is below the sustained-exposure "
                    f"floor of {floor}, so the enzyme is expected to denature on the shelf. "
                    f"Denaturation is permanent.{heuristic_note}",
                    evidence, enzyme_id=enzyme.id,
                )
            )
            continue

        opt_low = float(enzyme.ph_opt_low.value) if enzyme.ph_opt_low.usable else None
        if opt_low is not None and ph.value < opt_low:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.AMBER,
                    f"{enzyme.name}: recipe pH {ph.value} is above the survival floor but "
                    f"below its optimum of {opt_low}, so activity is sluggish. Survival is "
                    f"not the same as activity; a sluggish enzyme recovers once conditions "
                    f"improve, provided it has not denatured.",
                    evidence | {"ph_opt_low": opt_low}, enzyme_id=enzyme.id,
                )
            )
            continue

        findings.append(
            RuleFinding(
                RULE_ID, Verdict.PASS,
                f"{enzyme.name}: recipe pH {ph.value} sits at or above its optimum.",
                evidence, enzyme_id=enzyme.id,
            )
        )

    return findings
