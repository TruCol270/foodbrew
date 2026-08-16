"""Spec §10 — `GET /export/{evaluation_id}.md`.

The renderer lives in `engine/report.py`; this module only assembles its input
and sets a content type. The route's literal `.md` suffix is matched after the
path parameter's `[^/]+`, which resolves cleanly because evaluation ids are hex.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

from foodbrew.api.deps import get_conn
from foodbrew.engine.format_search import recommend_format
from foodbrew.engine.observations import (
    TEXTURE_SCALE,
    export_class,
    observed_envelope,
)
from foodbrew.engine.report import (
    ReportBatch,
    ReportInput,
    ReportObservation,
    ReportSuggestion,
    ReportSymptomEntry,
    TrialReport,
    render_markdown,
)
from foodbrew.store import evaluations as evaluations_store
from foodbrew.store import formulations as formulations_store
from foodbrew.store import observations as observations_store
from foodbrew.store import recipes as recipes_store
from foodbrew.store import trials as trials_store
from foodbrew.store.snapshot import context_from_snapshot

router = APIRouter(tags=["export"])

_OCCASION_SHORT = {
    "immediate": "within the hour",
    "packed": "1 to 8 hours",
    "marinade": "8 hours or more",
}


def _dose_lines(payload: dict) -> tuple[str, ...]:
    """One line per enzyme, from the math frozen with the entry (§6.6)."""
    lines = []
    for entry in payload.get("enzymes", ()):
        unit = entry["dose_unit"]
        if entry["units_delivered"] is None or entry["threshold"]["value"] is None:
            lines.append(
                f"{entry['enzyme_name']}: the delivered dose could not be worked out "
                f"({entry['blocking_field'] or 'missing input'})."
            )
            continue
        verdict = "clears it" if entry["meets_threshold"] else "below it"
        lines.append(
            f"{entry['enzyme_name']}: {entry['units_delivered']:g} {unit} delivered "
            f"against a {entry['threshold']['value']:g} {unit} evidence threshold — "
            f"{verdict}."
        )
    if payload.get("note"):
        lines.append(payload["note"])
    return tuple(lines)


def _trial_report(conn, evaluation_id: str) -> TrialReport | None:
    stored_trials = trials_store.list_for_evaluation(conn, evaluation_id)
    if not stored_trials:
        return None
    trial = next((t for t in stored_trials if t.observations), stored_trials[0])

    records = []
    for batch in trial.batches:
        for record in batch.observations:
            food = record.application_food_id
            records.append(
                ReportObservation(
                    observation_type=str(record.type),
                    export_class=export_class(record),
                    tier=str(record.tier),
                    occasion=_OCCASION_SHORT[str(record.dwell_bucket)],
                    observed_at=record.observed_at,
                    elapsed_minutes=record.elapsed_minutes,
                    application_food_name=food,
                    score=record.score,
                    free_text=record.free_text,
                )
            )

    symptoms = [
        ReportSymptomEntry(
            eaten_at=entry.eaten_at,
            trigger_food_name=entry.computed_dose.get("trigger_food_name", entry.trigger_food_id),
            amount=(
                f"{entry.amount_value:g} {entry.amount_unit}"
                if entry.amount_value is not None
                else "amount not recorded"
            ),
            doses_used=entry.doses_used,
            outcome_score=entry.outcome_score,
            dose_lines=_dose_lines(entry.computed_dose),
            notes=entry.notes,
        )
        for entry in observations_store.symptoms_for_trial(conn, trial.id)
    ]

    envelope = observed_envelope(trial.observations)
    observed = {
        profile: (
            f"{TEXTURE_SCALE[_score_for(trial, cell)]} ({cell.tier})"
            if cell.verdict is not None
            else ""
        )
        for profile, cell in envelope.items()
    }

    measured = [b.measured_ph for b in trial.batches if b.measured_ph is not None]
    note = (
        f"Measured pH of the batch: {measured[-1]}. Later evaluations of this "
        "formulation use that reading in place of the estimate."
        if measured
        else ""
    )
    return TrialReport(
        trial_id=trial.id, status=trial.status, batch_count=len(trial.batches),
        observations=tuple(records), symptoms=tuple(symptoms),
        observed_envelope=observed, measured_ph_note=note,
    )


def _score_for(trial, cell) -> int:
    """The score behind an observed cell, for the scale wording the report prints."""
    for record in trial.observations:
        if record.id == cell.driving_observation_id and record.score is not None:
            return record.score
    return 1


def report_input(conn: sqlite3.Connection, evaluation_id: str) -> ReportInput | None:
    """Assemble everything both renderers consume. The single source of the
    report's content (plan decision #8) — the markdown export and the printable
    screen are two renderings of this one value, never two assemblies."""
    stored = evaluations_store.get(conn, evaluation_id)
    if stored is None:
        return None

    ctx = context_from_snapshot(stored.input_snapshot_json)
    stale, _changes = evaluations_store.freshness(conn, stored)
    recipe_id = formulations_store.recipe_id_for(conn, stored.formulation_id)
    recipe = recipes_store.get(conn, recipe_id) if recipe_id else None
    trial = _trial_report(conn, evaluation_id)

    return ReportInput(
        evaluation_id=stored.id,
        created_at=stored.created_at,
        engine_version=stored.engine_version,
        recipe_name=recipe.name if recipe else "Untitled recipe",
        recipe_id=recipe_id or "",
        headline=stored.display,
        context=ctx,
        findings=stored.findings,
        envelope=stored.envelope,
        recommendation=recommend_format(ctx),
        suggestions=tuple(
            ReportSuggestion(s.suggestion_type, s.description, s.raised_by)
            for s in stored.suggestions
        ),
        stale=stale,
        trial=trial,
        batches=_batch_records(conn, evaluation_id),
    )


def _batch_records(conn: sqlite3.Connection, evaluation_id: str) -> tuple[ReportBatch, ...]:
    """Every batch of every trial on this evaluation, oldest first."""
    records: list[ReportBatch] = []
    for trial in trials_store.list_for_evaluation(conn, evaluation_id):
        for batch in trial.batches:
            records.append(
                ReportBatch(
                    made_at=batch.made_at, batch_size_g=batch.batch_size_g,
                    measured_ph=batch.measured_ph, ph_method=batch.ph_method,
                    make_minutes=batch.make_minutes,
                    difficulty_score=batch.difficulty_score,
                    enzyme_source_note=batch.enzyme_source_note,
                    enzyme_addition_step=batch.enzyme_addition_step,
                    storage_mode=batch.storage_mode, process_notes=batch.process_notes,
                )
            )
    return tuple(sorted(records, key=lambda r: r.made_at))


@router.get("/export/{evaluation_id}.md", response_class=PlainTextResponse)
def export_markdown(evaluation_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    data = report_input(conn, evaluation_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No evaluation '{evaluation_id}'.")
    return PlainTextResponse(render_markdown(data), media_type="text/markdown; charset=utf-8")
