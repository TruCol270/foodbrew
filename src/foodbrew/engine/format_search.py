"""Spec §6.1 R13 — the format recommendation. Pure.

R13 is not an independent test; it is the aggregation (flags.py) plus this
search. The search re-runs the whole engine under each format on the ladder and
reports the earliest position that produces no RED among the rules §6.1 names.

Two things make the answer trustworthy rather than plausible:

* Each candidate is built by `patch.apply_patch(..., set_format(f))` — the same
  function the apply-variant button calls — so what the recommendation promises
  and what applying it produces are the same formulation (plan decision #5).
* The ladder is scanned from the top, not from the current position, because
  it runs best-product-experience → most-separated and the least invasive
  answer to "what format works" is the earliest one that does (decision #6).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from foodbrew.engine.evaluate import evaluate
from foodbrew.engine.patch import apply_patch, set_format
from foodbrew.engine.types import EvalContext, Format, Verdict

#: Spec §6.1 R13, in the order the spec writes it: premixed → encapsulated →
#: dual-chamber → dry sachet.
FORMAT_LADDER: tuple[Format, ...] = (
    Format.PREMIXED_WET,
    Format.ENCAPSULATED_IN_WET,
    Format.DUAL_CHAMBER,
    Format.DRY_SACHET,
)

#: Spec §6.1 R13 — "re-running R1–R7, R11, R12, R14, R15 yields no RED".
#: R8, R9, R10 and R16 are advisory and excluded by name rather than by their
#: advisory flag, so the set stays legible against the spec sentence.
LADDER_RULE_IDS = frozenset(
    {"R1", "R2", "R3", "R4", "R5", "R6", "R7", "R11", "R12", "R14", "R15"}
)

#: Plain-English format names, so the UI hardcodes no copy (§10).
FORMAT_TITLES = {
    Format.PREMIXED_WET: "Premixed wet",
    Format.ENCAPSULATED_IN_WET: "Encapsulated in the wet",
    Format.DUAL_CHAMBER: "Dual chamber",
    Format.DRY_SACHET: "Dry sachet",
}


@dataclass(frozen=True, slots=True)
class FormatOption:
    format: Format
    title: str
    is_current: bool
    clears: bool
    #: Rule ids that RED under this format, sorted.
    reds: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FormatRecommendation:
    current: Format
    #: None when no position on the ladder clears every blocker.
    recommended: Format | None
    options: tuple[FormatOption, ...]
    #: Rules that RED under every format — a format change cannot fix these.
    unfixable: tuple[str, ...]
    message: str


def reds_under(ctx: EvalContext, fmt: Format) -> tuple[str, ...]:
    """Which of §6.1 R13's rules RED when this formulation is sold as `fmt`."""
    candidate = apply_patch(ctx.formulation, set_format(fmt))
    result = evaluate(dataclasses.replace(ctx, formulation=candidate))
    return tuple(
        sorted(
            {
                finding.rule_id
                for finding in result.findings
                if finding.verdict is Verdict.RED and finding.rule_id in LADDER_RULE_IDS
            }
        )
    )


def recommend_format(ctx: EvalContext) -> FormatRecommendation:
    current = ctx.formulation.format
    options = tuple(
        FormatOption(
            format=fmt,
            title=FORMAT_TITLES[fmt],
            is_current=fmt is current,
            clears=not reds,
            reds=reds,
        )
        for fmt, reds in ((fmt, reds_under(ctx, fmt)) for fmt in FORMAT_LADDER)
    )

    unfixable = tuple(sorted(set.intersection(*(set(o.reds) for o in options))))
    recommended = next((o.format for o in options if o.clears), None)

    if recommended is None:
        message = (
            "No format clears every blocker: "
            + ", ".join(unfixable)
            + " REDs however this is packaged, so the fix is in the formulation itself."
        )
    elif recommended is current:
        message = (
            f"{FORMAT_TITLES[current]} is already the least separated format that "
            f"clears these rules."
        )
    else:
        current_reds = next(o.reds for o in options if o.is_current)
        if current_reds:
            message = (
                f"{FORMAT_TITLES[recommended]} is the least separated format that clears "
                f"these rules. As {FORMAT_TITLES[current].lower()} the blockers are "
                + ", ".join(current_reds)
                + "."
            )
        else:
            # `current` itself clears every rule checked but isn't the ladder's
            # earliest clearing rung — e.g. dry sachet clears and so does the
            # less-separated dual chamber. There are no blockers to name; saying
            # so falsely (a dangling "the blockers are .") would read as a bug
            # in the tool, not a real finding.
            message = (
                f"{FORMAT_TITLES[current]} already clears these rules, but "
                f"{FORMAT_TITLES[recommended].lower()} is less separated and clears them too."
            )

    return FormatRecommendation(
        current=current,
        recommended=recommended,
        options=options,
        unfixable=unfixable,
        message=message,
    )
