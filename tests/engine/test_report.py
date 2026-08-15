"""Spec §10 screen 8 and §13's report lint."""

import pytest

from foodbrew.engine.evaluate import evaluate
from foodbrew.engine.format_search import recommend_format
from foodbrew.engine.language import contains_prohibited
from foodbrew.engine.report import (
    DISCLAIMER,
    ReportInput,
    ReportSuggestion,
    render_markdown,
)
from foodbrew.engine.types import Format, Phase, ProcessStep
from foodbrew.engine.variants import suggest


@pytest.fixture
def rendered(make_ctx):
    def _render(**kwargs):
        ctx = make_ctx(**kwargs)
        result = evaluate(ctx)
        data = ReportInput(
            evaluation_id="eval-1",
            created_at="2026-08-14T12:00:00+00:00",
            engine_version="1.0.0",
            recipe_name="Vinaigrette",
            headline=result.display,
            context=ctx,
            findings=result.findings,
            envelope=result.envelope,
            recommendation=recommend_format(ctx),
            suggestions=tuple(
                ReportSuggestion(
                    s.suggestion_type.value, s.description, s.triggered_by
                )
                for s in suggest(ctx, result.findings)
            ),
        )
        return render_markdown(data)

    return _render


def test_the_disclaimer_is_the_last_thing_on_the_page(rendered):
    text = rendered(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    assert text.rstrip().endswith(DISCLAIMER)


def test_no_prohibited_word_survives_the_report_lint(rendered):
    """Spec §13. Word boundaries, so the footer's 'safety' passes (decision #11)."""
    for kwargs in (
        {"fmt": Format.PREMIXED_WET, "measured_ph": 3.0, "trigger_foods": ("milk",)},
        {"fmt": Format.DRY_SACHET, "trigger_foods": ("milk", "black_beans")},
        {
            "fmt": Format.DRY_SACHET,
            "enzymes": (("cellulase", None, Phase.DRY),),
            "trigger_foods": ("broccoli",),
            "application_foods": ("mixed_greens",),
        },
    ):
        text = rendered(**kwargs)
        assert contains_prohibited(text) == (), kwargs


def test_the_footer_itself_would_fail_a_substring_lint_and_passes_this_one():
    assert "safe" in DISCLAIMER
    assert contains_prohibited(DISCLAIMER) == ()


def test_every_required_section_is_present(rendered):
    text = rendered(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    for heading in (
        "## What was checked",
        "## What the rules found",
        "## Dose per serving",
        "## Where each enzyme can work",
        "## Which occasions this can support",
        "## Format",
        "## What was observed",
        "## Provenance",
    ):
        assert heading in text, heading


def test_the_observed_section_says_there_is_no_trial_rather_than_being_absent(rendered):
    """Plan decision #12 — M4 fills this section, it does not create it."""
    text = rendered(fmt=Format.DRY_SACHET, trigger_foods=("milk",))
    assert "No trial has been recorded for this formulation yet." in text


def test_every_value_travels_with_its_label(rendered):
    text = rendered(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    assert "(entered by you" in text          # the measured pH
    assert "(not confirmed" in text           # the seeded shelf-stable floor


def test_a_blocker_is_reported_with_its_rule_and_its_message(rendered):
    text = rendered(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    assert "### Blockers" in text
    assert "R1 — In-jar pH survival" in text


def test_the_process_sequence_marks_the_heat_step_and_the_addition_point(rendered):
    text = rendered(
        fmt=Format.DRY_SACHET,
        trigger_foods=("milk",),
        process_steps=(ProcessStep(1, "warm", True), ProcessStep(2, "whisk", False)),
        enzyme_addition_index=2,
    )
    assert "1. warm — involves heat" in text
    assert "2. whisk — enzyme goes in here" in text


def test_a_stale_report_says_so_in_provenance(make_ctx):
    ctx = make_ctx(fmt=Format.DRY_SACHET, trigger_foods=("milk",))
    result = evaluate(ctx)
    text = render_markdown(
        ReportInput(
            evaluation_id="eval-1", created_at="t", engine_version="1.0.0",
            recipe_name="R", headline=result.display, context=ctx,
            findings=result.findings, envelope=result.envelope,
            recommendation=recommend_format(ctx), stale=True,
        )
    )
    assert "has changed since it ran" in text
