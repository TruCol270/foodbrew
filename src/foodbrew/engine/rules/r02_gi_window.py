"""R2 — GI window vs deadline (spec §6.1, KB §4a and §4h).

Headline-capable by default (missing per-formulation inputs, like an unconfirmed
recipe pH elsewhere in the engine, are supposed to gray the headline). But an
enzyme's own pH range is a static catalogue field, not a per-formulation input —
and it is unconfirmed for half the shipped seed (6 of 12 enzymes; KB Table A lists
the enzyme with no Table B range). Were that case headline-capable, most
formulations using those enzymes would come out GRAY regardless of merit, the
same failure shape R12 was redesigned to avoid. So this one CANNOT_ASSESS branch
is advisory; every other R2 finding (including CANNOT_ASSESS caused by
formulation-level gaps elsewhere in the engine) stays headline-capable.
"""

from __future__ import annotations

from foodbrew.engine.gi_model import active_regions, regions_before_deadline
from foodbrew.engine.types import EvalContext, RuleFinding, Verdict

RULE_ID = "R2"
ADVISORY = False


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    findings: list[RuleFinding] = []

    for selected in ctx.selected_enzymes():
        enzyme = ctx.enzyme_for(selected)

        if not (enzyme.ph_min.usable and enzyme.ph_max.usable):
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.CANNOT_ASSESS,
                    f"{enzyme.name}: cannot map its active window against the digestive "
                    f"tract because its pH range is unconfirmed. Confirm with the supplier.",
                    {"missing_field": f"{enzyme.id}.ph_min/ph_max"},
                    enzyme_id=enzyme.id, advisory=True,
                )
            )
            continue

        allowed = {r.id for r in regions_before_deadline(enzyme.deadline, ctx.gi_regions)}
        active = active_regions(enzyme, ctx.gi_regions)
        active_before = [r.id for r in active if r.id in allowed]
        active_after = [r.id for r in active if r.id not in allowed]

        substrate = ctx.substrates.get(enzyme.substrate_id)
        hard_deadline = substrate is not None and not substrate.native_human_enzyme
        deadline_note = ""
        if hard_deadline:
            deadline_note = (
                f" {substrate.name} has no native human enzyme, so whatever reaches the "
                f"colon undigested is fermented there — that fermentation is the symptom. "
                f"There is no catching up."
            )

        evidence = {
            "deadline": enzyme.deadline.value,
            "active_before_deadline": active_before,
            "active_after_deadline": active_after,
            "ph_min": float(enzyme.ph_min.value),
            "ph_max": float(enzyme.ph_max.value),
            "hard_deadline": hard_deadline,
        }

        if not active_before:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.RED,
                    f"{enzyme.name}: no active window anywhere before its "
                    f"{enzyme.deadline.value.replace('_', ' ')} deadline. Its pH range "
                    f"{enzyme.ph_min.value}-{enzyme.ph_max.value} does not overlap any "
                    f"region it must work in.{deadline_note}",
                    evidence, enzyme_id=enzyme.id,
                )
            )
        elif len(active_before) == 1:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.AMBER,
                    f"{enzyme.name}: active in only one region before its deadline "
                    f"({active_before[0]}). A narrow window leaves little margin if "
                    f"transit is fast or the meal buffers differently.{deadline_note}",
                    evidence, enzyme_id=enzyme.id,
                )
            )
        else:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.PASS,
                    f"{enzyme.name}: active in {', '.join(active_before)} before its "
                    f"deadline.{deadline_note}",
                    evidence, enzyme_id=enzyme.id,
                )
            )

    return findings
