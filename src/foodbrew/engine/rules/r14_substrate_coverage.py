"""R14 — substrate coverage (spec §6.2, derived from KB §5 outputs)."""

from __future__ import annotations

from foodbrew.engine.types import EvalContext, RuleFinding, Verdict

RULE_ID = "R14"
ADVISORY = False


class ValidationRejection(ValueError):
    """Raised for degenerate input that must not be evaluated at all (spec §6.7)."""


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    form = ctx.formulation

    if not form.target_trigger_food_ids and not form.enzymes:
        raise ValidationRejection(
            "Select at least one trigger food or enzyme before evaluating."
        )

    targeted_substrates: dict[str, list[str]] = {}
    for fid in form.target_trigger_food_ids:
        food = ctx.foods.get(fid)
        if food is None:
            continue
        for sid in food.contains_substrate_ids:
            targeted_substrates.setdefault(sid, []).append(food.name)

    covered = {ctx.enzyme_for(s).substrate_id for s in ctx.selected_enzymes()}
    findings: list[RuleFinding] = []

    for sid, food_names in sorted(targeted_substrates.items()):
        substrate = ctx.substrates.get(sid)
        name = substrate.name if substrate else sid
        evidence = {"substrate": sid, "from_foods": food_names, "covered": sid in covered}

        if substrate is not None and substrate.no_commercial_enzyme:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.CANNOT_ASSESS,
                    f"{name} (from {', '.join(food_names)}): no commercial enzyme exists "
                    f"for this substrate, so this trigger food cannot be addressed by any "
                    f"formulation. This is a gap, not a formulation error.",
                    evidence,
                )
            )
        elif sid in covered:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.PASS,
                    f"{name} (from {', '.join(food_names)}) is targeted by a selected enzyme.",
                    evidence,
                )
            )
        else:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.RED,
                    f"no enzyme selected for {name}, which {', '.join(food_names)} "
                    f"contains. That trigger food is not addressed.",
                    evidence,
                )
            )

    return findings
