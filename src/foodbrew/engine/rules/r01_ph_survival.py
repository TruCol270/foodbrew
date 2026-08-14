"""R1 — in-jar pH survival (spec §6.1, KB §4a)."""

from __future__ import annotations

from foodbrew.engine.conventions import resolve_recipe_ph
from foodbrew.engine.types import (
    EvalContext,
    Format,
    Phase,
    RuleFinding,
    Verdict,
)

RULE_ID = "R1"
ADVISORY = False

#: Spec §6.1 R1 — stated fallback when no supplier has confirmed a shelf-stable
#: floor. An engineering convention that makes the rule testable, NOT a
#: scientific claim; every finding using it says so (spec §12 item 3).
FALLBACK_MARGIN_PH = 1.0

#: Formats where an enzyme in the wet phase sits in liquid for shelf duration.
_WET_CONTACT_FORMATS = {Format.PREMIXED_WET, Format.ENCAPSULATED_IN_WET}


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    if ctx.formulation.format not in _WET_CONTACT_FORMATS:
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

        if enzyme.ph_shelf_stable_min.usable:
            floor = float(enzyme.ph_shelf_stable_min.value)
            floor_source = "ph_shelf_stable_min"
            heuristic_note = ""
        else:
            floor = float(enzyme.ph_min.value) + FALLBACK_MARGIN_PH
            floor_source = "fallback"
            heuristic_note = (
                " This uses the stated margin heuristic (ph_min + "
                f"{FALLBACK_MARGIN_PH}) because no shelf-stable floor is confirmed — "
                "supplier confirmation required."
            )

        evidence = {
            "recipe_ph": ph.value,
            "ph_origin": ph.origin,
            "ph_status": ph.status.value,
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
