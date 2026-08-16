"""Spec §10 screen 8 — the handoff report, rendered as Markdown. Pure.

The renderer lives in the engine rather than beside the endpoint that serves it
because `tests/api/test_contracts.py` greps every file under `api/` for the
prohibited words as substrings, and the §10 footer contains "safety" (plan
decision #11). Keeping the disclaimer here means the api-source lint stays
strict and the footer stays intact.

Observed results are M4's. Until a trial exists they render as an explicit
absence rather than being omitted, so M4 fills a section rather than
restructuring the document (plan decision #12).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from foodbrew.engine.allergens import NOTHING_RECORDED, Declaration, declare
from foodbrew.engine.flags import group_findings
from foodbrew.engine.format_search import FORMAT_TITLES, FormatRecommendation
from foodbrew.engine.formula import Formula, process_lines
from foodbrew.engine.formula import build as build_formula
from foodbrew.engine.observations import TEXTURE_SCALE_NOTE, ExportClass
from foodbrew.engine.types import (
    DwellProfile,
    EvalContext,
    RuleFinding,
    Tracked,
    TruthLabel,
    Verdict,
)
from foodbrew.engine.variants import SuggestionType
from foodbrew.engine.views import RULE_TITLES, dose_cards, gi_strip

#: Spec §10 screen 8. Fixed text, on every rendering, at the end.
DISCLAIMER = (
    "Formulation decision support. Not a safety, efficacy, or regulatory determination."
)

_VERDICT_TEXT: Mapping[Verdict, str] = {
    Verdict.RED: "blocker",
    Verdict.CANNOT_ASSESS: "cannot assess",
    Verdict.AMBER: "caution",
    Verdict.PASS: "clear",
}

_LABEL_TEXT: Mapping[TruthLabel, str] = {
    TruthLabel.CONFIRMED: "confirmed",
    TruthLabel.UNCONFIRMED: "not confirmed",
    TruthLabel.USER_PROVIDED: "entered by you",
    TruthLabel.CALCULATED: "calculated",
    TruthLabel.OBSERVED: "observed in a trial",
}

_OCCASION_TEXT: Mapping[DwellProfile, str] = {
    DwellProfile.IMMEDIATE: "Dressed at the table (eaten within the hour)",
    DwellProfile.PACKED: "Packed ahead (dressed 1 to 8 hours before eating)",
    DwellProfile.MARINADE: "Marinade (left 8 hours or more, on purpose)",
}

_NOTE_TYPES = frozenset(
    {
        SuggestionType.RECIPE_NOTE,
        SuggestionType.BEHAVIOUR_NOTE,
        SuggestionType.SUPPLIER_QUESTION,
    }
)


@dataclass(frozen=True, slots=True)
class ReportSuggestion:
    """A suggestion reduced to what the report prints.

    Deliberately not `variants.Suggestion`: the report is rendered from a
    *stored* evaluation, whose suggestions come back as `store.variants
    .StoredSuggestion` rows. Both sides map into this in two lines, and the
    renderer stays ignorant of which one it was handed.
    """

    suggestion_type: str
    description: str
    raised_by: tuple[str, ...]


_OCCASION_SHORT: Mapping[DwellProfile, str] = {
    DwellProfile.IMMEDIATE: "within the hour",
    DwellProfile.PACKED: "1 to 8 hours",
    DwellProfile.MARINADE: "8 hours or more",
}


@dataclass(frozen=True, slots=True)
class ReportObservation:
    """One `trial_observation`, already classified by §6.6."""

    observation_type: str
    export_class: ExportClass
    tier: str
    occasion: str
    observed_at: str
    elapsed_minutes: int
    application_food_name: str = ""
    score: int | None = None
    #: The founder's own words. Quoted, never adopted (plan decision #13).
    free_text: str = ""


@dataclass(frozen=True, slots=True)
class ReportSymptomEntry:
    """One `trial_symptom_entry`, with its frozen dose math already rendered."""

    eaten_at: str
    trigger_food_name: str
    amount: str
    doses_used: float | None
    outcome_score: int | None
    #: One line per enzyme: delivered vs threshold, or what blocked the sum.
    dose_lines: tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""


@dataclass(frozen=True, slots=True)
class TrialReport:
    """Everything §6.6 needs about one trial, assembled by the caller."""

    trial_id: str
    status: str
    batch_count: int
    observations: tuple[ReportObservation, ...] = field(default_factory=tuple)
    symptoms: tuple[ReportSymptomEntry, ...] = field(default_factory=tuple)
    #: Display text per dwell profile, e.g. "clearly softer (anecdote)".
    observed_envelope: Mapping[DwellProfile, str] = field(default_factory=dict)
    #: The batch pH, when one was measured, phrased for the report.
    measured_ph_note: str = ""

    @property
    def observation_count(self) -> int:
        return len(self.observations) + len(self.symptoms)

    def of_class(self, export_class: ExportClass) -> tuple[ReportObservation, ...]:
        return tuple(o for o in self.observations if o.export_class is export_class)


@dataclass(frozen=True, slots=True)
class ReportBatch:
    """One `trial_batch` as a batch record — the document reviewed first when a
    batch misses spec, which is why every parameter it captured is printed."""

    made_at: str
    batch_size_g: float | None
    measured_ph: float | None
    ph_method: str
    make_minutes: int | None
    difficulty_score: int | None
    enzyme_source_note: str
    enzyme_addition_step: int | None
    storage_mode: str
    process_notes: str = ""


@dataclass(frozen=True, slots=True)
class ReportInput:
    """Everything the report needs, already frozen. The renderer derives the rest."""

    evaluation_id: str
    created_at: str
    engine_version: str
    recipe_name: str
    headline: str
    context: EvalContext
    findings: tuple[RuleFinding, ...]
    envelope: Mapping[DwellProfile, Verdict]
    recommendation: FormatRecommendation
    suggestions: tuple[ReportSuggestion, ...] = field(default_factory=tuple)
    #: True when a referenced record has changed since this evaluation ran.
    stale: bool = False
    #: None until the founder has run a trial against this evaluation (§6.6).
    trial: TrialReport | None = None
    #: Identity of the recipe this formula belongs to, for the header block.
    recipe_id: str = ""
    #: Batch records from the trial, newest last. Empty until a batch is logged.
    batches: tuple[ReportBatch, ...] = field(default_factory=tuple)


def _tracked(value: Tracked, unit: str = "") -> str:
    if value.value is None:
        shown = "not recorded"
    elif isinstance(value.value, bool):
        shown = "yes" if value.value else "no"
    else:
        shown = f"{value.value}{f' {unit}' if unit else ''}"
    source = f" — {value.source}" if value.source else ""
    return f"{shown} ({_LABEL_TEXT[value.status]}{source})"


def _findings_section(title: str, blurb: str, findings: Sequence[RuleFinding]) -> list[str]:
    if not findings:
        return []
    lines = [f"### {title}", "", blurb, ""]
    for finding in findings:
        rule = f"{finding.rule_id} — {RULE_TITLES.get(finding.rule_id, finding.rule_id)}"
        lines.append(f"- **{rule}** ({_VERDICT_TEXT[finding.verdict]}): {finding.message}")
    lines.append("")
    return lines


def _identity_block(data: ReportInput) -> list[str]:
    """The header a specification sheet opens with: what this is, and which run."""
    form = data.context.formulation
    serving = "not set" if form.serving_size_g is None else f"{form.serving_size_g} g"
    return [
        "## Product and formula identity",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Product | {data.recipe_name} |",
        f"| Recipe id | {data.recipe_id or 'not recorded'} |",
        "| Formula basis | percent of total batch weight (sums to 100) |",
        f"| Format | {FORMAT_TITLES.get(form.format, form.format.value)} |",
        f"| Serving size | {serving} |",
        f"| Declared use occasion | "
        f"{form.dwell_profile.value if form.dwell_profile else 'not declared'} |",
        f"| Measured pH | {_tracked(form.measured_ph)} |",
        f"| Evaluation | {data.evaluation_id} |",
        f"| Engine version | {data.engine_version} |",
        "",
    ]


def _formula_section(formula: Formula) -> list[str]:
    """Percent of total beside weights, in order of addition (decisions #6, #7)."""
    if formula.is_empty:
        return ["## Formula", "", "No ingredients are recorded for this recipe.", ""]

    lines = [
        "## Formula",
        "",
        "Percent of total batch weight, in the order the ingredients go in. The "
        "percentages are the formula; the grams are one batch of it. Percent is "
        "calculated from the weights, so the two cannot disagree.",
        "",
        "| # | Ingredient | % of total | Grams | pH | Water content | Allergens |",
        "| ---: | --- | ---: | ---: | --- | --- | --- |",
    ]
    for position, line in enumerate(formula.lines, start=1):
        percent = "—" if line.percent_of_total is None else f"{line.percent_of_total:g}"
        allergens = line.allergen_text or "not recorded"
        lines.append(
            f"| {position} | {line.food_name} | {percent} | {line.amount_g:g} "
            f"| {_tracked(line.ph)} | {_tracked(line.water_content_pct, '%')} | {allergens} |"
        )

    total_percent = (
        "—" if formula.printed_percent_total is None else f"{formula.printed_percent_total:g}"
    )
    lines += [
        f"| | **Total** | **{total_percent}** | **{formula.total_g:g}** | | | |",
        "",
    ]
    if formula.printed_percent_total is not None and formula.printed_percent_total != 100:
        lines += [
            f"The printed percentages total {total_percent} rather than 100 because each "
            "is rounded to two decimals. The grams are exact.",
            "",
        ]
    return lines


def _allergen_section(declaration: Declaration) -> list[str]:
    lines = ["## Allergens", ""]
    if declaration.is_empty:
        lines += [
            "No allergen is recorded for any ingredient in this recipe. That is a gap "
            "in the ingredient records, not a statement that the product is free of "
            "allergens.",
            "",
        ]
    else:
        lines += ["| Allergen | From |", "| --- | --- |"]
        for entry in declaration.entries:
            lines.append(f"| {entry.text} | {', '.join(entry.from_food_names)} |")
        lines.append("")
    if declaration.unrecorded_food_names:
        lines += [
            "Allergens are "
            + NOTHING_RECORDED
            + " for: "
            + ", ".join(declaration.unrecorded_food_names)
            + ". Fill these in before anyone relies on the declaration above.",
            "",
        ]
    return lines


def _process_section(data: ReportInput) -> list[str]:
    form = data.context.formulation
    steps = process_lines(form.process_steps, form.enzyme_addition_index)
    if not steps:
        return []
    lines = [
        "## Process",
        "",
        "| Step | Operation | Heat | Enzyme added here |",
        "| ---: | --- | --- | --- |",
    ]
    for step in steps:
        lines.append(
            f"| {step.order} | {step.label} | {'yes' if step.is_heat else 'no'} "
            f"| {'yes' if step.is_enzyme_addition_point else 'no'} |"
        )
    lines.append("")
    return lines


def _targets_section(data: ReportInput) -> list[str]:
    """What a specification sheet carries that this tool cannot measure.

    Stating the absence is the convention: an incomplete spec says which
    parameters are outstanding rather than omitting the rows (spec §12).
    """
    return [
        "## Finished-product parameters",
        "",
        "| Parameter | Value | Basis |",
        "| --- | --- | --- |",
        f"| pH | {_tracked(data.context.formulation.measured_ph)} | measured, or "
        "estimated from the lowest-pH wet ingredient |",
        "| Water activity | not measured | needs a lab instrument this tool does not model |",
        "| Viscosity | not measured | outside the rules this tool evaluates |",
        "| Nutrition | not calculated | no nutrient data is held for these ingredients |",
        "",
    ]


def _selected_foods_section(data: ReportInput) -> list[str]:
    ctx = data.context
    form = ctx.formulation
    lines: list[str] = []
    for title, ids in (
        ("Trigger foods this is meant to cover", form.target_trigger_food_ids),
        ("Foods it will be poured on", form.application_food_ids),
    ):
        names = [ctx.foods[i].name if i in ctx.foods else i for i in ids]
        lines += [f"### {title}", "", ", ".join(names) if names else "none selected", ""]
    return lines


def _inputs_section(data: ReportInput) -> list[str]:
    """Spec §10 screen 8, in the shape a bench sheet and a spec sheet use."""
    formula = build_formula(
        data.context.formulation.recipe,
        data.context.foods,
        allergen_text_for=_allergen_text,
    )
    declaration = declare(
        [i.food_id for i in data.context.formulation.recipe], data.context.foods
    )
    return (
        _identity_block(data)
        + _formula_section(formula)
        + _allergen_section(declaration)
        + _process_section(data)
        + _targets_section(data)
        + _selected_foods_section(data)
    )


def _allergen_text(food) -> str:
    from foodbrew.engine.allergens import ALLERGEN_TEXT, Allergen

    return ", ".join(ALLERGEN_TEXT[Allergen(a)] for a in getattr(food, "allergens", ()) or ())


def _dose_section(data: ReportInput) -> list[str]:
    cards = dose_cards(data.context)
    if not cards:
        return []
    lines = [
        "## Dose per serving",
        "",
        "Dose is driven by how much of the substrate a serving carries, not by the "
        "weight of the food. Below the evidence threshold an enzyme behaves like a "
        "placebo, which is why an under-dose is flagged rather than rounded up.",
        "",
        "| Enzyme | Your dose | Benchmark range | Evidence threshold "
        "| Substrate in a serving | Clears it |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for card in cards:
        clears = (
            "cannot tell"
            if card.meets_threshold is None
            else ("yes" if card.meets_threshold else "no")
        )
        dose = "not set" if card.dose is None else f"{card.dose} {card.dose_unit}".strip()
        low = _tracked(card.dose_min, card.dose_unit)
        high = _tracked(card.dose_max, card.dose_unit)
        lines.append(
            f"| {card.enzyme_name} | {dose} | {low} to {high} "
            f"| {_tracked(card.dose_evidence_threshold, card.dose_unit)} "
            f"| {_tracked(card.substrate_load)} | {clears} |"
        )
    lines.append("")
    return lines


def _gi_section(data: ReportInput) -> list[str]:
    lanes = gi_strip(data.context)
    if not lanes:
        return []
    regions = lanes[0].regions
    header = " | ".join(r.name for r in regions)
    divider = " | ".join("---" for _ in regions)
    lines = [
        "## Where each enzyme can work",
        "",
        "A deadline, not a target: anything left when the food reaches the colon "
        "ferments there. The mouth is dormant for every enzyme because food is there "
        "for seconds.",
        "",
        f"| Enzyme | {header} |",
        f"| --- | {divider} |",
    ]
    for lane in lanes:
        cells = []
        for region in lane.regions:
            if region.dormant:
                cells.append("dormant")
            elif region.active and region.before_deadline:
                cells.append("active")
            elif region.active:
                cells.append("active, past its deadline")
            else:
                cells.append("—")
        lines.append(f"| {lane.enzyme_name} | {' | '.join(cells)} |")
    lines.append("")
    return lines


def _envelope_section(data: ReportInput) -> list[str]:
    lines = [
        "## Which occasions this can support",
        "",
        "What the dressing does to the food it sits on, by how long it sits there. An "
        "occasion you do not intend to sell is still listed, so nothing is hidden.",
        "",
        "| Occasion | Predicted | Observed |",
        "| --- | --- | --- |",
    ]
    observed = data.trial.observed_envelope if data.trial else {}
    for profile in DwellProfile:
        verdict = data.envelope.get(profile)
        predicted = _VERDICT_TEXT[verdict] if verdict is not None else "not evaluated"
        seen = observed.get(profile) or ("no trial yet" if data.trial is None else "not looked at")
        lines.append(f"| {_OCCASION_TEXT[profile]} | {predicted} | {seen} |")
    lines.append("")
    if data.trial and observed:
        lines += [TEXTURE_SCALE_NOTE, ""]
    return lines


def _format_section(data: ReportInput) -> list[str]:
    recommendation = data.recommendation
    lines = ["## Format", "", recommendation.message, "", "| Format | Blockers |", "| --- | --- |"]
    for option in recommendation.options:
        marker = " (current)" if option.is_current else ""
        blockers = ", ".join(option.reds) if option.reds else "none on the rules checked"
        lines.append(f"| {option.title}{marker} | {blockers} |")
    lines.append("")
    return lines


def _suggestions_section(data: ReportInput) -> list[str]:
    actionable = [s for s in data.suggestions if s.suggestion_type not in _NOTE_TYPES]
    if not actionable:
        return []
    lines = [
        "## Changes the rules suggest",
        "",
        "None of these is pre-cleared. Each one is re-run through the whole rule set "
        "when it is applied, and its own flags are reported then.",
        "",
    ]
    for suggestion in actionable:
        rules = ", ".join(suggestion.raised_by)
        lines.append(f"- **{rules}:** {suggestion.description}")
    lines.append("")
    return lines


def _open_questions_section(data: ReportInput) -> list[str]:
    # `==`, not `is`: `suggestion_type` is a plain str here, and StrEnum compares
    # and hashes as its value, so equality and set membership both work — but
    # identity does not.
    questions = [
        s for s in data.suggestions if s.suggestion_type == SuggestionType.SUPPLIER_QUESTION
    ]
    gaps = group_findings(data.findings).data_gaps
    if not questions and not gaps:
        return []
    lines = ["## Open questions", "", "Answers a supplier or a bench run would close.", ""]
    for gap in gaps:
        lines.append(f"- **{gap.rule_id}:** {gap.message}")
    for question in questions:
        lines.append(f"- **{', '.join(question.raised_by)}:** {question.description}")
    lines.append("")
    return lines


def _quote(text: str) -> list[str]:
    """Her words, reproduced and attributed — never rewritten (plan decision #13)."""
    return [f"> {line}" for line in text.strip().splitlines()] + [""]


def _observation_lines(records: Sequence[ReportObservation]) -> list[str]:
    lines: list[str] = []
    for record in records:
        subject = f" on {record.application_food_name}" if record.application_food_name else ""
        score = f", scored {record.score} of 5" if record.score is not None else ""
        lines.append(
            f"- **{record.observation_type.replace('_', ' ')}**{subject} — "
            f"{record.occasion} after making it{score} ({record.tier}, "
            f"observed {record.observed_at[:16].replace('T', ' ')})"
        )
        if record.free_text:
            lines += _quote(record.free_text)
    lines.append("")
    return lines


def _observed_section(data: ReportInput) -> list[str]:
    """Spec §10 screen 8 and §6.6 — the split by how much her judgement counts."""
    trial = data.trial
    if trial is None:
        return [
            "## What was observed",
            "",
            "No trial has been recorded for this formulation yet. Everything above is a "
            "prediction from the rules and the data behind them; nothing here was measured.",
            "",
        ]

    lines = [
        "## What was observed",
        "",
        f"Trial {trial.trial_id}, {trial.status}. {trial.batch_count} "
        f"batch(es), {trial.observation_count} record(s). This was one person, in a "
        "kitchen, mostly unblinded — so each section below says how much weight its "
        "contents carry.",
        "",
    ]
    if trial.status == "abandoned":
        lines += [
            f"This trial was abandoned after {trial.observation_count} record(s). What "
            "is below was really recorded; what is missing was never run.",
            "",
        ]
    if trial.measured_ph_note:
        lines += [trial.measured_ph_note, ""]

    findings = trial.of_class(ExportClass.FINDING)
    lines += ["### Findings", ""]
    if findings:
        lines += [
            "Taste, how it was to make, how it was to use — subjective questions where "
            "her answer is the data — plus any applied-food texture she compared "
            "against an undressed portion.",
            "",
        ]
        lines += _observation_lines(findings)
    else:
        lines += ["Nothing in this trial reached this bar yet.", ""]

    observations = trial.of_class(ExportClass.OBSERVATION)
    lines += ["### Observations", ""]
    if observations:
        lines += [
            "Watched, not controlled. Applied-food texture with no undressed portion to "
            "compare against, and storage watching.",
            "",
        ]
        lines += _observation_lines(observations)
    else:
        lines += ["Nothing recorded in this class.", ""]

    lines += ["### Hypotheses for a food scientist to test", ""]
    if trial.symptoms:
        lines += [
            "Symptom response, unblinded, single subject, on a product she has a stake "
            "in. This is the weakest measurement here and is listed so a real test can "
            "be designed around it. The dose arithmetic is attached to every entry, so "
            "a null result can be read as an under-dose rather than as a failure.",
            "",
        ]
        for entry in trial.symptoms:
            outcome = (
                f"outcome scored {entry.outcome_score} of 5"
                if entry.outcome_score is not None
                else "no outcome score"
            )
            doses = "not recorded" if entry.doses_used is None else f"{entry.doses_used}"
            lines.append(
                f"- **{entry.trigger_food_name}**, {entry.amount}, {doses} dose(s) — "
                f"{outcome} ({entry.eaten_at[:16].replace('T', ' ')})"
            )
            for line in entry.dose_lines:
                lines.append(f"  - {line}")
            if entry.notes:
                lines += _quote(entry.notes)
        lines.append("")
    else:
        lines += ["No meal was logged in this trial.", ""]

    return lines


def _batch_record_section(data: ReportInput) -> list[str]:
    """The batch record. First document reviewed when a batch misses spec, so it
    prints every parameter the trial captured rather than summarising them."""
    if not data.batches:
        return []
    lines = [
        "## Batch records",
        "",
        "What was actually made, as it was made. Blank cells are parameters that "
        "were not recorded for that batch.",
        "",
        "| Made | Size | pH (method) | Minutes | Difficulty | Enzyme added after step "
        "| Enzyme source | Storage |",
        "| --- | ---: | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for batch in data.batches:
        ph = (
            "not measured"
            if batch.measured_ph is None
            else f"{batch.measured_ph:g} ({batch.ph_method})"
        )
        lines.append(
            f"| {batch.made_at[:16].replace('T', ' ')} "
            f"| {'' if batch.batch_size_g is None else f'{batch.batch_size_g:g} g'} "
            f"| {ph} "
            f"| {'' if batch.make_minutes is None else batch.make_minutes} "
            f"| {'' if batch.difficulty_score is None else f'{batch.difficulty_score} of 5'} "
            f"| {'' if batch.enzyme_addition_step is None else batch.enzyme_addition_step} "
            f"| {batch.enzyme_source_note or 'not recorded'} "
            f"| {batch.storage_mode} |"
        )
    lines.append("")
    for batch in data.batches:
        if batch.process_notes:
            lines += [
                f"**Notes on the batch made {batch.made_at[:16].replace('T', ' ')}:**",
                "",
            ]
            lines += _quote(batch.process_notes)
    return lines


def _provenance_section(data: ReportInput) -> list[str]:
    lines = [
        "## Provenance",
        "",
        f"- **Evaluation:** {data.evaluation_id}",
        f"- **Run at:** {data.created_at}",
        f"- **Engine version:** {data.engine_version}",
        "- **Inputs:** frozen with this evaluation. Editing a record afterwards does "
        "not change it; re-run to see the effect of a change.",
    ]
    if data.stale:
        lines.append(
            "- **Note:** a record this evaluation used has changed since it ran. "
            "Re-run before relying on the numbers above."
        )
    lines.append("")
    return lines


def render_markdown(data: ReportInput) -> str:
    groups = group_findings(data.findings)

    lines = [
        f"# Formulation report — {data.recipe_name}",
        "",
        f"**{data.headline}**",
        "",
    ]
    lines += _inputs_section(data)
    lines += ["## What the rules found", ""]
    lines += _findings_section(
        "Blockers", "These stop the formulation as specified.", groups.blockers
    )
    lines += _findings_section(
        "Data gaps",
        "Missing values. Fill these in and re-run to get a verdict.",
        groups.data_gaps,
    )
    lines += _findings_section(
        "Cautions",
        "Not blockers, but they change over time or with use.",
        groups.cautions,
    )
    lines += _findings_section(
        "Advisory",
        "Notes that never change the headline — decisions that belong to you.",
        groups.advisories,
    )
    lines += _dose_section(data)
    lines += _gi_section(data)
    lines += _envelope_section(data)
    lines += _format_section(data)
    lines += _suggestions_section(data)
    lines += _observed_section(data)
    lines += _batch_record_section(data)
    lines += _open_questions_section(data)
    lines += _provenance_section(data)
    lines += ["---", "", DISCLAIMER, ""]

    return "\n".join(lines)
