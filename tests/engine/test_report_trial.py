"""Spec §6.6's split, rendered. The absence path is M3's and must stay intact."""

import pytest

from foodbrew.engine.format_search import recommend_format
from foodbrew.engine.language import contains_prohibited
from foodbrew.engine.observations import ExportClass
from foodbrew.engine.report import (
    ReportInput,
    ReportObservation,
    ReportSymptomEntry,
    TrialReport,
    render_markdown,
)
from foodbrew.engine.rules import r15_applied_texture
from foodbrew.engine.types import DwellProfile, Phase


@pytest.fixture
def base(make_ctx):
    ctx = make_ctx(
        enzymes=(("lactase_fungal_acid", 9000.0, Phase.WET),),
        recipe=(("olive_oil", 100.0), ("white_vinegar", 50.0)),
        trigger_foods=("milk",),
        application_foods=("romaine",),
        measured_ph=3.0,
    )

    def _input(trial=None):
        return ReportInput(
            evaluation_id="e1", created_at="2026-08-15T09:00:00+00:00",
            engine_version="test-engine", recipe_name="vinaigrette", headline="RED",
            context=ctx, findings=(), envelope=r15_applied_texture.envelope(ctx),
            recommendation=recommend_format(ctx), trial=trial,
        )

    return _input


def observation(**kw):
    defaults = dict(
        observation_type="food_texture", export_class=ExportClass.FINDING,
        tier="suggestive", occasion="1 to 8 hours",
        observed_at="2026-08-16T13:00:00+00:00", elapsed_minutes=240,
        application_food_name="Romaine", score=3, free_text="",
    )
    return ReportObservation(**{**defaults, **kw})


def test_without_a_trial_the_report_says_so_exactly_as_m3_did(base):
    body = render_markdown(base())
    assert "No trial has been recorded for this formulation yet." in body
    assert "| no trial yet |" in body


def test_a_trial_fills_the_three_sections_with_their_own_words(base):
    trial = TrialReport(
        trial_id="t1", status="running", batch_count=1,
        observations=(
            observation(observation_type="taste", export_class=ExportClass.FINDING,
                        application_food_name="", score=2, free_text="sweeter on day 3"),
            observation(export_class=ExportClass.OBSERVATION, tier="anecdote"),
        ),
        symptoms=(
            ReportSymptomEntry(
                eaten_at="2026-08-16T19:00:00+00:00", trigger_food_name="Milk",
                amount="1 servings", doses_used=1.0, outcome_score=2,
                dose_lines=("Lactase (fungal, acid): 9000 FCC delivered against a "
                            "3000 FCC threshold — clears it",),
                notes="no bloating this time",
            ),
        ),
        observed_envelope={DwellProfile.PACKED: "clearly softer (anecdote)"},
    )
    body = render_markdown(base(trial))

    assert "### Findings" in body
    assert "### Observations" in body
    assert "### Hypotheses for a food scientist to test" in body
    assert "> sweeter on day 3" in body
    assert "> no bloating this time" in body
    assert "9000 FCC delivered" in body
    assert "| clearly softer (anecdote) |" in body
    assert "| not looked at |" in body  # the buckets she has not filled


def test_an_empty_class_says_nothing_rather_than_being_dropped(base):
    trial = TrialReport(trial_id="t1", status="planned", batch_count=0)
    body = render_markdown(base(trial))
    assert "Nothing in this trial reached this bar yet." in body
    assert "No meal was logged in this trial." in body


def test_an_abandoned_trial_is_named_as_abandoned_with_its_count(base):
    trial = TrialReport(
        trial_id="t1", status="abandoned", batch_count=1, observations=(observation(),)
    )
    body = render_markdown(base(trial))
    assert "abandoned after 1 record(s)" in body


def test_the_symptom_section_never_reads_as_evidence(base):
    trial = TrialReport(
        trial_id="t1", status="complete", batch_count=1,
        symptoms=(ReportSymptomEntry(
            eaten_at="2026-08-16T19:00:00+00:00", trigger_food_name="Milk",
            amount="1 servings", doses_used=1.0, outcome_score=5,
        ),),
    )
    body = render_markdown(base(trial))
    assert "weakest measurement" in body
    assert contains_prohibited(body) == ()


def test_founder_free_text_is_reproduced_unaltered(base):
    """Decision #13 — the lint covers tool copy; her words are quoted and attributed."""
    trial = TrialReport(
        trial_id="t1", status="running", batch_count=1,
        observations=(observation(free_text="tastes fine to me, texture held up"),),
    )
    body = render_markdown(base(trial))
    assert "> tastes fine to me, texture held up" in body


def test_the_texture_scale_note_travels_with_the_observed_column(base):
    trial = TrialReport(
        trial_id="t1", status="running", batch_count=1,
        observed_envelope={DwellProfile.IMMEDIATE: "indistinguishable (anecdote)"},
    )
    body = render_markdown(base(trial))
    assert "stated convention, not by a measurement" in body
