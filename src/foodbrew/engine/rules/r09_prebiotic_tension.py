"""R9 — prebiotic tension (spec §6.1, KB §4i). Advisory, never RED.

KB §4i names inulin, fructans AND GOS, so alpha-galactosidase triggers this as
surely as inulinase does. A product-philosophy call the founder owns; the rule
just keeps it visible.
"""

from __future__ import annotations

from foodbrew.engine.types import EvalContext, RuleFinding, Verdict

RULE_ID = "R9"
ADVISORY = True


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    findings: list[RuleFinding] = []

    for selected in ctx.selected_enzymes():
        enzyme = ctx.enzyme_for(selected)
        substrate = ctx.substrates.get(enzyme.substrate_id)
        if substrate is None or not substrate.is_prebiotic:
            continue

        findings.append(
            RuleFinding(
                RULE_ID, Verdict.AMBER,
                f"{enzyme.name} breaks down {substrate.name}, which relieves gas but also "
                f"removes a prebiotic that feeds the gut microbiome. Consider dosing to a "
                f"symptom threshold rather than to zero. Garlic and onion carry more "
                f"short-chain fructans than inulin.",
                {"substrate": substrate.id, "is_prebiotic": True},
                enzyme_id=enzyme.id,
            )
        )

    return findings
