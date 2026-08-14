"""R4 — water activation (spec §6.1, KB §4c).

Dry is inert; wet is active and unstoppable. R4 alone never REDs: the magnitude
of activity loss is unknown without bench stability data. Escalation to RED comes
from R1 (pH kill), R5 (protease) or R6 through normal worst-of aggregation. That
calibration is what makes an acidic vinaigrette RED and a creamy premix AMBER
without hardcoding KB §4m.
"""

from __future__ import annotations

from foodbrew.engine.types import EvalContext, Format, Phase, RuleFinding, Verdict

RULE_ID = "R4"
ADVISORY = False

_SEPARATION_CAVEAT = (
    " An AMBER here is not a green light to ship premixed: KB §4c requires physical "
    "separation of the dry enzyme from the liquid for shelf life, and shipping wet "
    "requires bench stability data this tool cannot supply."
)


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    selected = ctx.selected_enzymes()
    if not selected:
        return []

    fmt = ctx.formulation.format
    wet_phase = [s for s in selected if s.phase is Phase.WET]
    evidence = {
        "format": fmt.value,
        "enzymes_in_wet_phase": [s.enzyme_id for s in wet_phase],
    }

    if fmt is Format.ENCAPSULATED_IN_WET:
        return [
            RuleFinding(
                RULE_ID, Verdict.AMBER,
                "The enzyme is encapsulated but still sits in liquid on the shelf. "
                "Encapsulation delays exposure rather than preventing it — see R6 for "
                "whether the capsule is being asked to do more than it can." + _SEPARATION_CAVEAT,
                evidence,
            )
        ]

    if not wet_phase:
        return [
            RuleFinding(
                RULE_ID, Verdict.PASS,
                "Every enzyme is kept dry and separate from the liquid, so it stays inert "
                "until use. Water is the on/off switch.",
                evidence,
            )
        ]

    names = ", ".join(s.enzyme_id for s in wet_phase)
    return [
        RuleFinding(
            RULE_ID, Verdict.AMBER,
            f"Water switches the enzyme on: {names} sits in liquid for the whole shelf "
            f"life, so activity decays and the enzyme digests the jar contents in the "
            f"meantime. How fast is unknown without stability data." + _SEPARATION_CAVEAT,
            evidence,
        )
    ]
