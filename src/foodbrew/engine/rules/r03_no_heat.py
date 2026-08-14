"""R3 — no heat after the enzyme goes in (spec §6.1, KB §4b and §4j)."""

from __future__ import annotations

from foodbrew.engine.types import EvalContext, RuleFinding, Verdict

RULE_ID = "R3"
ADVISORY = False


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    form = ctx.formulation
    findings: list[RuleFinding] = []

    if not form.process_steps or form.enzyme_addition_index is None:
        findings.append(
            RuleFinding(
                RULE_ID, Verdict.CANNOT_ASSESS,
                "Cannot check the no-heat rule: the process sequence or the "
                "enzyme_addition_index is not recorded. Add the process steps and mark "
                "where the enzyme goes in.",
                {"missing_field": "process_steps / enzyme_addition_index"},
            )
        )
    else:
        offending = [
            s for s in form.process_steps
            if s.is_heat and s.order >= form.enzyme_addition_index
        ]
        evidence = {
            "enzyme_addition_index": form.enzyme_addition_index,
            "heat_steps": [
                {"order": s.order, "label": s.label}
                for s in form.process_steps if s.is_heat
            ],
        }
        if offending:
            labels = ", ".join(f"'{s.label}' (step {s.order})" for s in offending)
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.RED,
                    f"Heat is applied at or after the enzyme goes in: {labels}. Heat "
                    f"denatures the enzyme and denaturation is permanent. Move the enzyme "
                    f"addition to after the heat step, at the end.",
                    evidence,
                )
            )
        else:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.PASS,
                    "No heat step falls at or after the enzyme addition point.",
                    evidence,
                )
            )

    # KB §4j informational notes — a cooked protease-bearing food no longer
    # contributes protease, which suppresses the R5 conflict for that food.
    for ingredient in form.recipe:
        food = ctx.foods.get(ingredient.food_id)
        if food is None or not food.contains_protease or not food.is_heat_processed:
            continue
        findings.append(
            RuleFinding(
                RULE_ID, Verdict.PASS,
                f"{food.name} is heat-processed, so it no longer contributes protease "
                f"(cooking destroys naturally occurring enzymes). Its co-formulation "
                f"conflict is suppressed.",
                {"food": food.id, "is_heat_processed": True},
                food_id=food.id,
            )
        )

    return findings
