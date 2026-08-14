"""R11 — food-grade and GRAS status (spec §6.1, KB §4l).

Headline-capable by default. is_gras is a static catalogue field, unconfirmed
for 10 of the 12 shipped enzymes (GRAS status was never a research target for
most of them, only flagship enzymes). Headline-capable against that catalogue
would gray almost every formulation regardless of merit, the same failure
shape R12 was redesigned to avoid — so only the unconfirmed-is_gras branch is
advisory; a confirmed non-GRAS enzyme still reds the headline as before.
"""

from __future__ import annotations

from foodbrew.engine.types import EvalContext, RuleFinding, Verdict

RULE_ID = "R11"
ADVISORY = False

#: Shown alongside every R11 finding: finished-product rules are out of scope.
SCOPE_BANNER = (
    "Finished-product rules — food-contact compliance and acidified-food regulations — are "
    "outside this tool's scope."
)


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    findings: list[RuleFinding] = []

    for selected in ctx.selected_enzymes():
        enzyme = ctx.enzyme_for(selected)
        evidence = {"is_gras": enzyme.is_gras.value, "status": enzyme.is_gras.status.value}

        if not enzyme.is_gras.usable:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.CANNOT_ASSESS,
                    f"{enzyme.name}: GRAS status is not recorded. Ask the supplier whether "
                    f"this enzyme is food grade and GRAS-affirmed, and at what cost tier — "
                    f"food grade costs more than technical grade. {SCOPE_BANNER}",
                    evidence, enzyme_id=enzyme.id, advisory=True,
                )
            )
        elif enzyme.is_gras.value:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.PASS,
                    f"{enzyme.name} is recorded as food grade and GRAS, which is a cost and "
                    f"time advantage. {SCOPE_BANNER}",
                    evidence, enzyme_id=enzyme.id,
                )
            )
        else:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.RED,
                    f"{enzyme.name} is recorded as not GRAS. A finished food cannot carry a "
                    f"non-GRAS enzyme. {SCOPE_BANNER}",
                    evidence, enzyme_id=enzyme.id,
                )
            )

    return findings
