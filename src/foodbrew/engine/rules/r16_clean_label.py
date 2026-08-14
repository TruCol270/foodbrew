"""R16 — clean label and natural sourcing (spec §6.2, KB §1 criterion 5 via §4j/§4l).

Advisory only — a founder philosophy call the rule keeps visible, in the same
spirit as R9.
"""

from __future__ import annotations

from foodbrew.engine.types import EvalContext, RuleFinding, Verdict

RULE_ID = "R16"
ADVISORY = True


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    selected = ctx.selected_enzymes()
    if not selected:
        return []

    findings: list[RuleFinding] = []

    for s in selected:
        enzyme = ctx.enzyme_for(s)
        evidence = {
            "is_natural_source": enzyme.is_natural_source,
            "source_type": enzyme.source_type,
        }
        if enzyme.is_natural_source:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.AMBER,
                    f"{enzyme.name} is a natural source ({enzyme.source_type}), which "
                    f"supports a clean-label story — but natural-source enzymes are "
                    f"destroyed by cooking, so the no-heat rule binds harder here.",
                    evidence, enzyme_id=enzyme.id,
                )
            )
        else:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.PASS,
                    f"{enzyme.name} is {enzyme.source_type}-fermented rather than extracted "
                    f"from a whole food. That is standard for the category and food grade, "
                    f"but it is not a 'natural source' claim — worth deciding deliberately "
                    f"rather than by default.",
                    evidence, enzyme_id=enzyme.id,
                )
            )

    # The second half of the KB criterion has no data anywhere in the source set.
    findings.append(
        RuleFinding(
            RULE_ID, Verdict.CANNOT_ASSESS,
            "Cannot assess 'no gut-trigger additives': excipient and carrier composition "
            "for these enzymes is supplier data that is not recorded anywhere yet. Ask "
            "each supplier for the full carrier and excipient breakdown.",
            {"missing_field": "enzyme excipient / carrier composition"},
        )
    )

    return findings
