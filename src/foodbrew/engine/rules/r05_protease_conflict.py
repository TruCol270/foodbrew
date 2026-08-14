"""R5 — protease co-formulation (spec §6.1, KB §4d)."""

from __future__ import annotations

from foodbrew.engine.types import EvalContext, Phase, RuleFinding, Verdict

RULE_ID = "R5"
ADVISORY = False


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    selected = ctx.selected_enzymes()
    if not selected:
        return []

    # A protease only threatens enzymes it shares an unprotected wet phase with.
    wet_unencapsulated = [
        s for s in selected if s.phase is Phase.WET and not s.encapsulated
    ]
    protease_selections = [
        s for s in wet_unencapsulated if ctx.enzyme_for(s).is_protease
    ]
    victims = [s for s in wet_unencapsulated if not ctx.enzyme_for(s).is_protease]

    # Raw protease-bearing ingredients count too. Cooked ones do not (KB §4j).
    raw_protease_foods = [
        ctx.foods[i.food_id]
        for i in ctx.formulation.recipe
        if i.food_id in ctx.foods
        and ctx.foods[i.food_id].contains_protease
        and not ctx.foods[i.food_id].is_heat_processed
    ]

    evidence = {
        "protease_enzymes": [s.enzyme_id for s in protease_selections],
        "protease_foods": [f.id for f in raw_protease_foods],
        "exposed_enzymes": [s.enzyme_id for s in victims],
    }

    has_threat = bool(protease_selections or raw_protease_foods)
    if has_threat and victims:
        sources = [ctx.enzyme_for(s).name for s in protease_selections]
        sources += [f.name for f in raw_protease_foods]
        exposed = ", ".join(ctx.enzyme_for(s).name for s in victims)
        return [
            RuleFinding(
                RULE_ID, Verdict.RED,
                f"Protease present in the same wet phase as {exposed}: "
                f"{', '.join(sources)}. A protease slowly destroys the other enzymes, "
                f"because enzymes are proteins. Keep them dry, in separate chambers, or "
                f"individually encapsulated.",
                evidence,
            )
        ]

    if has_threat:
        return [
            RuleFinding(
                RULE_ID, Verdict.PASS,
                "A protease is present but has no other enzyme sharing its active wet "
                "phase, so there is nothing for it to degrade.",
                evidence,
            )
        ]

    return [
        RuleFinding(
            RULE_ID, Verdict.PASS,
            "No protease shares an active wet phase with another enzyme — either none is "
            "present, or they are separated by phase or encapsulation.",
            evidence,
        )
    ]
