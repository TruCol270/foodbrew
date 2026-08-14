"""R7 — dosing vs substrate load (spec §6.1, KB §4g).

Headline-capable by default. Two of its three CANNOT_ASSESS causes are
per-formulation inputs the founder can supply (the trigger food's substrate
load, the enzyme's dose) and are meant to gray the headline until she does —
see test_h_headline_capable_cannot_assess_does_gray_the_headline. The third,
dose_evidence_threshold, is a static catalogue field: it is unconfirmed for 11
of the 12 shipped enzymes (no independent full-dose study exists for most of
them yet). Headline-capable against that catalogue would gray almost every
formulation regardless of merit, the same failure shape R12 was redesigned to
avoid — so only that branch is advisory.
"""

from __future__ import annotations

from foodbrew.engine.conventions import aggregate_substrate_loads
from foodbrew.engine.dosing import assess_dose
from foodbrew.engine.types import EvalContext, RuleFinding, Verdict

RULE_ID = "R7"
ADVISORY = False

#: Spec §6.1 R7 — the squeeze format's dose scales with how much dressing is
#: used, which is only loosely correlated with how much trigger food is eaten.
#: Stated on every finding so it is never read as full self-scaling.
_DECOUPLING_NOTE = (
    " Note that a fixed dose meets a variable meal: in a squeeze format the dose "
    "self-scales with dressing used, not with trigger food eaten."
)


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    loads = aggregate_substrate_loads(ctx.formulation.target_trigger_food_ids, ctx.foods)
    findings: list[RuleFinding] = []

    for selected in ctx.selected_enzymes():
        enzyme = ctx.enzyme_for(selected)
        load = loads.get(enzyme.substrate_id)

        if load is None:
            continue  # No targeted trigger food carries this enzyme's substrate.

        if not load.usable:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.CANNOT_ASSESS,
                    f"{enzyme.name}: cannot check the dose because the substrate load is "
                    f"unconfirmed ({load.source}). Enter a typical load for that food.",
                    {"missing": load.source}, enzyme_id=enzyme.id,
                )
            )
            continue

        if selected.dose is None:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.CANNOT_ASSESS,
                    f"{enzyme.name}: no dose is set for this formulation.",
                    {"missing_field": "enzyme_selection.dose"}, enzyme_id=enzyme.id,
                )
            )
            continue

        if not enzyme.dose_evidence_threshold.usable:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.CANNOT_ASSESS,
                    f"{enzyme.name}: cannot judge the dose because its "
                    f"dose_evidence_threshold is unconfirmed. Ask the supplier, or find "
                    f"an independent full-dose study.",
                    {"missing_field": f"{enzyme.id}.dose_evidence_threshold"},
                    enzyme_id=enzyme.id, advisory=True,
                )
            )
            continue

        threshold = float(enzyme.dose_evidence_threshold.value)
        benchmark_max = float(enzyme.dose_max.value) if enzyme.dose_max.usable else None
        result = assess_dose(float(selected.dose), threshold, benchmark_max)

        evidence = {
            "dose": float(selected.dose),
            "dose_unit": enzyme.dose_unit,
            "evidence_threshold": threshold,
            "substrate": enzyme.substrate_id,
            "substrate_load": float(load.value),
            "load_source": load.source,
            "ratio": round(result.ratio, 3),
        }

        if not result.meets_threshold:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.AMBER,
                    f"{enzyme.name} at {selected.dose} {enzyme.dose_unit} is below the "
                    f"{threshold} {enzyme.dose_unit} evidence threshold. An underdosed "
                    f"enzyme behaves like placebo.{_DECOUPLING_NOTE}",
                    evidence, enzyme_id=enzyme.id,
                )
            )
        elif result.above_benchmark_max:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.PASS,
                    f"{enzyme.name} at {selected.dose} {enzyme.dose_unit} clears the "
                    f"{threshold} threshold and exceeds the {benchmark_max} benchmark "
                    f"maximum. That works, but loading extra enzyme is an expensive way "
                    f"to solve it.{_DECOUPLING_NOTE}",
                    evidence, enzyme_id=enzyme.id,
                )
            )
        else:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.PASS,
                    f"{enzyme.name} at {selected.dose} {enzyme.dose_unit} clears the "
                    f"{threshold} {enzyme.dose_unit} evidence threshold against a "
                    f"{load.value} load.{_DECOUPLING_NOTE}",
                    evidence, enzyme_id=enzyme.id,
                )
            )

    return findings
