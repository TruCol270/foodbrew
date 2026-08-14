"""R12 — temperature range (spec §6.1, KB §4b).

Advisory by default, because every temperature field in the shipped seed is
unconfirmed — no source document provides per-enzyme temperature data. Were R12
headline-capable against that catalogue, every formulation would come out GRAY
regardless of merit and the KB §4m fixtures would be unreachable.

Promotion is per-enzyme: once an enzyme's temperature fields are confirmed, its
finding stops being advisory and can set the headline.
"""

from __future__ import annotations

from foodbrew.engine.types import EvalContext, RuleFinding, Verdict

RULE_ID = "R12"
ADVISORY = True

#: The product is required to be ambient-stable with no cold chain (spec §1.1).
AMBIENT_STORAGE_C = 25.0
BODY_TEMPERATURE_C = 37.0


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    findings: list[RuleFinding] = []

    for selected in ctx.selected_enzymes():
        enzyme = ctx.enzyme_for(selected)

        if not (enzyme.temp_min_c.usable and enzyme.temp_max_c.usable):
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.CANNOT_ASSESS,
                    f"{enzyme.name}: temperature range is unconfirmed, so its tolerance of "
                    f"ambient storage and of body temperature cannot be checked. Ask the "
                    f"supplier for the temperature range and optimum. "
                    f"{enzyme.temp_min_c.source}".strip(),
                    {"missing_field": f"{enzyme.id}.temp_min_c/temp_max_c"},
                    enzyme_id=enzyme.id, advisory=True,
                )
            )
            continue

        tmin, tmax = float(enzyme.temp_min_c.value), float(enzyme.temp_max_c.value)
        covers_ambient = tmin <= AMBIENT_STORAGE_C <= tmax
        covers_body = tmin <= BODY_TEMPERATURE_C <= tmax
        evidence = {
            "temp_min_c": tmin, "temp_max_c": tmax,
            "covers_ambient": covers_ambient, "covers_body_temp": covers_body,
        }

        if not covers_ambient:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.RED,
                    f"{enzyme.name}: its confirmed range {tmin}-{tmax} C does not cover "
                    f"ambient storage at {AMBIENT_STORAGE_C} C, and the product is "
                    f"required to need no cold chain."
                    + ("" if covers_body else
                       f" It also does not cover body temperature at {BODY_TEMPERATURE_C} C, "
                       f"so it would be sluggish in the gut."),
                    evidence, enzyme_id=enzyme.id, advisory=False,
                )
            )
        elif not covers_body:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.AMBER,
                    f"{enzyme.name}: stable at ambient, but its confirmed range "
                    f"{tmin}-{tmax} C does not cover body temperature at "
                    f"{BODY_TEMPERATURE_C} C, so activity in the gut will be reduced.",
                    evidence, enzyme_id=enzyme.id, advisory=False,
                )
            )
        else:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.PASS,
                    f"{enzyme.name}: its confirmed range {tmin}-{tmax} C covers both "
                    f"ambient storage and body temperature.",
                    evidence, enzyme_id=enzyme.id, advisory=False,
                )
            )

    return findings
