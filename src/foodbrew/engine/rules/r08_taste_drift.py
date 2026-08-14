"""R8 — in-jar taste and stability drift (spec §6.1, KB §4e). Advisory.

Scope is the jar. What the dressing does to the food it is poured on is R15.
"""

from __future__ import annotations

from foodbrew.engine.types import EvalContext, Format, Phase, RuleFinding, Verdict

RULE_ID = "R8"
ADVISORY = True

_WET_FORMATS = {Format.PREMIXED_WET, Format.ENCAPSULATED_IN_WET}


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    recipe_substrates: set[str] = set()
    for ingredient in ctx.formulation.recipe:
        food = ctx.foods.get(ingredient.food_id)
        if food is not None:
            recipe_substrates.update(food.contains_substrate_ids)

    findings: list[RuleFinding] = []
    wet_format = ctx.formulation.format in _WET_FORMATS

    for selected in ctx.selected_enzymes():
        enzyme = ctx.enzyme_for(selected)
        if enzyme.substrate_id not in recipe_substrates:
            continue

        evidence = {
            "substrate_in_recipe": enzyme.substrate_id,
            "format": ctx.formulation.format.value,
            "phase": selected.phase.value,
        }

        if wet_format and selected.phase is Phase.WET:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.AMBER,
                    f"{enzyme.name} shares a wet phase with its own substrate "
                    f"({enzyme.substrate_id}) in the recipe, so flavour, texture, smell "
                    f"and appearance will drift over shelf life — lactose hydrolysis "
                    f"makes a product sweeter, and food can turn weird and smelly as it "
                    f"sits.",
                    evidence, enzyme_id=enzyme.id,
                )
            )
        else:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.PASS,
                    f"{enzyme.name}'s substrate ({enzyme.substrate_id}) is in the recipe, "
                    f"but the enzyme is kept dry, so drift begins at mixing rather than on "
                    f"the shelf.",
                    evidence, enzyme_id=enzyme.id,
                )
            )

    return findings
