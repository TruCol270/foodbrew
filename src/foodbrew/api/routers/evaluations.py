"""Running and reading evaluations (§10 screen 4).

Running writes a new row; reading returns the stored one, with derived views
rebuilt from that evaluation's own snapshot rather than from current records,
so an evaluation looks exactly as it did when it ran (plan decision #5).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException

from foodbrew.api.deps import get_conn
from foodbrew.api.schemas import (
    DoseCardOut,
    EvaluationOut,
    EvaluationSummaryOut,
    FindingOut,
    FormatOptionOut,
    FormatRecommendationOut,
    GiLaneOut,
    ObservedEnvelopeOut,
    ObservedProfileOut,
    RegionStateOut,
    SnapshotChangeOut,
    SuggestionOut,
    TrackedOut,
)
from foodbrew.engine.format_search import recommend_format
from foodbrew.engine.observations import TEXTURE_SCALE_NOTE, observed_envelope
from foodbrew.engine.views import RULE_TITLES, dose_cards, gi_strip
from foodbrew.store import evaluations as store
from foodbrew.store import trials as trials_store
from foodbrew.store.snapshot import context_from_snapshot

router = APIRouter(tags=["evaluations"])


def _finding(f) -> FindingOut:
    return FindingOut(
        rule_id=f.rule_id, rule_title=RULE_TITLES.get(f.rule_id, f.rule_id),
        verdict=str(f.verdict), advisory=f.advisory, message=f.message,
        evidence=dict(f.evidence), enzyme_id=f.enzyme_id, food_id=f.food_id,
    )


def _recommendation(recommendation) -> FormatRecommendationOut:
    return FormatRecommendationOut(
        current=recommendation.current.value,
        recommended=recommendation.recommended.value if recommendation.recommended else None,
        options=[
            FormatOptionOut(
                format=option.format.value, title=option.title,
                is_current=option.is_current, clears=option.clears, reds=list(option.reds),
            )
            for option in recommendation.options
        ],
        unfixable=list(recommendation.unfixable),
        message=recommendation.message,
    )


def _observed(conn, evaluation_id: str) -> tuple[ObservedEnvelopeOut | None, list[str]]:
    """Spec §6.3 — the Observed column, from the trials that test this evaluation.

    Read-only and additive: the stored envelope, the findings, and the headline
    are untouched (plan decision #10). The newest trial with any observation
    wins; earlier ones stay readable on their own screens.
    """
    stored_trials = trials_store.list_for_evaluation(conn, evaluation_id)
    if not stored_trials:
        return None, []

    with_records = [t for t in stored_trials if t.observations]
    source = with_records[0] if with_records else stored_trials[0]
    envelope = observed_envelope(source.observations)
    return (
        ObservedEnvelopeOut(
            trial_id=source.id,
            profiles={
                str(profile): ObservedProfileOut(
                    verdict=str(cell.verdict) if cell.verdict is not None else None,
                    confidence_tier=str(cell.tier) if cell.tier is not None else None,
                    observation_count=cell.observation_count,
                    driving_observation_id=cell.driving_observation_id,
                )
                for profile, cell in envelope.items()
            },
            scale_note=TEXTURE_SCALE_NOTE,
        ),
        [t.id for t in stored_trials],
    )


def evaluation_out(
    stored, *, stale: bool = False, changes=(), observed=None, trial_ids=()
) -> EvaluationOut:
    ctx = context_from_snapshot(stored.input_snapshot_json)
    return EvaluationOut(
        id=stored.id, formulation_id=stored.formulation_id,
        engine_version=stored.engine_version, created_at=stored.created_at,
        headline=stored.display, overall=str(stored.overall),
        findings=[_finding(f) for f in stored.findings],
        blockers=[_finding(f) for f in stored.blockers],
        data_gaps=[_finding(f) for f in stored.data_gaps],
        cautions=[_finding(f) for f in stored.cautions],
        advisories=[_finding(f) for f in stored.advisories],
        envelope={str(k): str(v) for k, v in stored.envelope.items()},
        gi_strip=[
            GiLaneOut(
                enzyme_id=lane.enzyme_id, enzyme_name=lane.enzyme_name,
                deadline=str(lane.deadline),
                ph_min=TrackedOut.of(lane.ph_min), ph_max=TrackedOut.of(lane.ph_max),
                regions=[RegionStateOut(**asdict(r)) for r in lane.regions],
            )
            for lane in gi_strip(ctx)
        ],
        dose_cards=[
            DoseCardOut(
                enzyme_id=c.enzyme_id, enzyme_name=c.enzyme_name,
                substrate_id=c.substrate_id, dose=c.dose, dose_unit=c.dose_unit,
                dose_min=TrackedOut.of(c.dose_min), dose_max=TrackedOut.of(c.dose_max),
                dose_evidence_threshold=TrackedOut.of(c.dose_evidence_threshold),
                substrate_load=TrackedOut.of(c.substrate_load),
                meets_threshold=c.meets_threshold, ratio=c.ratio,
                above_benchmark_max=c.above_benchmark_max,
            )
            for c in dose_cards(ctx)
        ],
        suggestions=[
            SuggestionOut(
                id=s.id, suggestion_type=s.suggestion_type, description=s.description,
                raised_by=list(s.raised_by), is_applicable=s.is_applicable,
            )
            for s in stored.suggestions
        ],
        format_recommendation=_recommendation(recommend_format(ctx)),
        stale=stale,
        changes=[
            SnapshotChangeOut(
                kind=c.kind, record_id=c.record_id, field=c.field,
                before=c.before, after=c.after,
            )
            for c in changes
        ],
        observed=observed,
        trial_ids=list(trial_ids),
    )


def _summary(stored) -> EvaluationSummaryOut:
    return EvaluationSummaryOut(
        id=stored.id, formulation_id=stored.formulation_id,
        created_at=stored.created_at, headline=stored.display,
        engine_version=stored.engine_version,
    )


@router.post(
    "/formulations/{formulation_id}/evaluate", response_model=EvaluationOut, status_code=201
)
def run_evaluation(formulation_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    # A run just froze its own inputs, so it cannot be stale.
    return evaluation_out(store.run(conn, formulation_id))


@router.get("/formulations/{formulation_id}/evaluations", response_model=list[EvaluationSummaryOut])
def list_for_formulation(formulation_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    return [_summary(e) for e in store.list_for_formulation(conn, formulation_id)]


@router.get("/evaluations", response_model=list[EvaluationSummaryOut])
def list_recent(limit: int = 10, conn: sqlite3.Connection = Depends(get_conn)):
    return [_summary(e) for e in store.list_recent(conn, limit)]


@router.get("/evaluations/{evaluation_id}", response_model=EvaluationOut)
def get_evaluation(evaluation_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    stored = store.get(conn, evaluation_id)
    if stored is None:
        raise HTTPException(status_code=404, detail=f"No evaluation '{evaluation_id}'.")
    stale, changes = store.freshness(conn, stored)
    observed, trial_ids = _observed(conn, evaluation_id)
    return evaluation_out(
        stored, stale=stale, changes=changes, observed=observed, trial_ids=trial_ids
    )


@router.get("/evaluations/{evaluation_id}/snapshot")
def get_snapshot(evaluation_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    """The frozen inputs, for audit and for M3's compare view."""
    stored = store.get(conn, evaluation_id)
    if stored is None:
        raise HTTPException(status_code=404, detail=f"No evaluation '{evaluation_id}'.")
    return json.loads(stored.input_snapshot_json)
