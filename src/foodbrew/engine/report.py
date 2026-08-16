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

from foodbrew.engine.flags import group_findings
from foodbrew.engine.format_search import FORMAT_TITLES, FormatRecommendation
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


def _inputs_section(data: ReportInput) -> list[str]:
    ctx = data.context
    form = ctx.formulation
    lines = ["## What was checked", ""]
    serving = "not set" if form.serving_size_g is None else f"{form.serving_size_g} g"

    lines += [
        f"- **Recipe:** {data.recipe_name}",
        f"- **Format:** {FORMAT_TITLES.get(form.format, form.format.value)}",
        f"- **Serving size:** {serving}",
        f"- **Measured pH:** {_tracked(form.measured_ph)}",
        "- **Declared use occasion:** "
        + (form.dwell_profile.value if form.dwell_profile else "not declared"),
        "",
        "### Recipe",
        "",
        "| Ingredient | Grams | pH | Water content |",
        "| --- | ---: | --- | --- |",
    ]
    for ingredient in form.recipe:
        food = ctx.foods.get(ingredient.food_id)
        name = food.name if food else ingredient.food_id
        ph = _tracked(food.ph) if food else "not recorded"
        water = _tracked(food.water_content_pct, "%") if food else "not recorded"
        lines.append(f"| {name} | {ingredient.amount_g} | {ph} | {water} |")
    lines.append("")

    for title, ids in (
        ("Trigger foods this is meant to cover", form.target_trigger_food_ids),
        ("Foods it will be poured on", form.application_food_ids),
    ):
        names = [
            ctx.foods[i].name if i in ctx.foods else i for i in ids
        ]
        lines += [f"### {title}", "", ", ".join(names) if names else "none selected", ""]

    if form.process_steps:
        lines += ["### How it is made", ""]
        for step in form.process_steps:
            marks = []
            if step.is_heat:
                marks.append("involves heat")
            if form.enzyme_addition_index == step.order:
                marks.append("enzyme goes in here")
            suffix = f" — {', '.join(marks)}" if marks else ""
            lines.append(f"{step.order}. {step.label}{suffix}")
        lines.append("")
    return lines


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
    lines += _open_questions_section(data)
    lines += _provenance_section(data)
    lines += ["---", "", DISCLAIMER, ""]

    return "\n".join(lines)
