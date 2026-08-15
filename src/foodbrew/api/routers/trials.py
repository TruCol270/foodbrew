"""Spec §10 — Workflow E over HTTP.

Every refusal in here comes from the store as a `ValidationRejection` and is
turned into a 422 by the single handler in `app.py`, so the founder-facing
sentence the rule wrote is the sentence she reads (M2's pattern, unchanged).
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from foodbrew.api.deps import get_conn
from foodbrew.api.schemas import (
    BatchIn,
    BatchOut,
    CheckpointOut,
    ObservationIn,
    ObservationOut,
    ProtocolOut,
    SymptomDoseOut,
    SymptomEntryIn,
    SymptomEntryOut,
    SymptomPreviewIn,
    TrackedDoseOut,
    TrackedOut,
    TrialOut,
    TrialStatusIn,
    TrialSummaryOut,
)
from foodbrew.engine.observations import export_class
from foodbrew.engine.protocol import satisfied_checkpoint_ids
from foodbrew.engine.symptoms import SymptomDoseMath
from foodbrew.engine.trial_rules import ambient_storage_allowed
from foodbrew.engine.types import Tracked
from foodbrew.store import observations as observations_store
from foodbrew.store import trials as trials_store

router = APIRouter(tags=["trials"])


def _tracked(payload) -> TrackedOut:
    """A dose payload's tracked value, whether it arrived as a dataclass or a dict."""
    if isinstance(payload, Tracked):
        return TrackedOut.of(payload)
    return TrackedOut(
        value=payload["value"], status=payload["status"], source=payload.get("source", "")
    )


def _dose(math: SymptomDoseMath | dict) -> SymptomDoseOut:
    payload = math.as_dict() if isinstance(math, SymptomDoseMath) else math
    return SymptomDoseOut(
        trigger_food_id=payload["trigger_food_id"],
        trigger_food_name=payload["trigger_food_name"],
        amount_value=payload["amount_value"], amount_unit=payload["amount_unit"],
        doses_used=payload["doses_used"], substrate_ids=payload["substrate_ids"],
        enzymes=[
            TrackedDoseOut(
                enzyme_id=e["enzyme_id"], enzyme_name=e["enzyme_name"],
                dose_unit=e["dose_unit"], dose_per_serving=e["dose_per_serving"],
                units_delivered=e["units_delivered"], threshold=_tracked(e["threshold"]),
                meets_threshold=e["meets_threshold"], ratio=e["ratio"],
                blocking_field=e["blocking_field"],
            )
            for e in payload["enzymes"]
        ],
        substrate_load=_tracked(payload["substrate_load"]),
        note=payload["note"],
    )


def _observation(record) -> ObservationOut:
    return ObservationOut(
        id=record.id, type=str(record.type), observed_at=record.observed_at,
        elapsed_minutes=record.elapsed_minutes, dwell_bucket=str(record.dwell_bucket),
        score=record.score, free_text=record.free_text, was_blinded=record.was_blinded,
        had_undressed_control=record.had_undressed_control,
        application_food_id=record.application_food_id,
        confidence_tier=str(record.tier), export_class=str(export_class(record)),
    )


def _symptom(entry) -> SymptomEntryOut:
    return SymptomEntryOut(
        id=entry.id, eaten_at=entry.eaten_at, trigger_food_id=entry.trigger_food_id,
        amount_value=entry.amount_value, amount_unit=entry.amount_unit,
        doses_used=entry.doses_used, outcome_score=entry.outcome_score,
        notes=entry.notes, computed_dose=_dose(entry.computed_dose),
    )


def _protocol(protocol) -> ProtocolOut:
    return ProtocolOut(
        engine_version=protocol.engine_version,
        checkpoints=[
            CheckpointOut(
                id=c.id, kind=str(c.kind), prompt=c.prompt, raised_by=list(c.raised_by),
                due_elapsed_minutes=c.due_elapsed_minutes,
                application_food_id=c.application_food_id,
                observation_type=str(c.observation_type) if c.observation_type else "",
            )
            for c in protocol.checkpoints
        ],
        notes=list(protocol.notes),
    )


def trial_out(conn, trial) -> TrialOut:
    return TrialOut(
        id=trial.id, evaluation_id=trial.evaluation_id,
        formulation_id=trial.formulation_id, status=trial.status,
        started_at=trial.started_at, notes=trial.notes,
        protocol=_protocol(trial.protocol),
        batches=[
            BatchOut(
                id=b.id, made_at=b.made_at, batch_size_g=b.batch_size_g,
                measured_ph=b.measured_ph, ph_method=b.ph_method,
                make_minutes=b.make_minutes, difficulty_score=b.difficulty_score,
                enzyme_source_note=b.enzyme_source_note,
                enzyme_addition_step=b.enzyme_addition_step,
                process_notes=b.process_notes, storage_mode=b.storage_mode,
                observations=[_observation(o) for o in b.observations],
                symptom_entries=[
                    _symptom(e) for e in observations_store.symptoms_for_batch(conn, b.id)
                ],
                due_checkpoint_ids=[c.id for c in trials_store.due_now(trial, b)],
                satisfied_checkpoint_ids=sorted(
                    satisfied_checkpoint_ids(trial.protocol, b.observations)
                ),
                ambient_storage_allowed=ambient_storage_allowed(b.measured_ph),
            )
            for b in trial.batches
        ],
    )


def _summary(conn, trial) -> TrialSummaryOut:
    return TrialSummaryOut(
        id=trial.id, evaluation_id=trial.evaluation_id,
        formulation_id=trial.formulation_id, status=trial.status,
        started_at=trial.started_at, batch_count=len(trial.batches),
        observation_count=len(trial.observations)
        + len(observations_store.symptoms_for_trial(conn, trial.id)),
        due_checkpoint_count=sum(
            len(trials_store.due_now(trial, b)) for b in trial.batches
        ),
    )


def _require(conn, trial_id: str):
    trial = trials_store.get(conn, trial_id)
    if trial is None:
        raise HTTPException(status_code=404, detail=f"No trial '{trial_id}'.")
    return trial


@router.post("/evaluations/{evaluation_id}/trial", response_model=TrialOut, status_code=201)
def start_trial(evaluation_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    trial_id = trials_store.create(conn, evaluation_id)
    return trial_out(conn, trials_store.get(conn, trial_id))


@router.get("/trials", response_model=list[TrialSummaryOut])
def list_active(conn: sqlite3.Connection = Depends(get_conn)):
    return [_summary(conn, t) for t in trials_store.list_active(conn)]


@router.get("/evaluations/{evaluation_id}/trials", response_model=list[TrialSummaryOut])
def list_for_evaluation(evaluation_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    return [_summary(conn, t) for t in trials_store.list_for_evaluation(conn, evaluation_id)]


@router.get("/trials/{trial_id}", response_model=TrialOut)
def get_trial(trial_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    return trial_out(conn, _require(conn, trial_id))


@router.post("/trials/{trial_id}/status", response_model=TrialOut)
def set_status(
    trial_id: str, payload: TrialStatusIn, conn: sqlite3.Connection = Depends(get_conn)
):
    _require(conn, trial_id)
    return trial_out(conn, trials_store.set_status(conn, trial_id, payload.status))


@router.post("/trials/{trial_id}/batches", response_model=TrialOut, status_code=201)
def add_batch(trial_id: str, payload: BatchIn, conn: sqlite3.Connection = Depends(get_conn)):
    _require(conn, trial_id)
    trials_store.add_batch(conn, trial_id, **payload.model_dump())
    return trial_out(conn, trials_store.get(conn, trial_id))


@router.post("/trial-batches/{batch_id}/observations", response_model=TrialOut, status_code=201)
def add_observation(
    batch_id: str, payload: ObservationIn, conn: sqlite3.Connection = Depends(get_conn)
):
    observations_store.add_observation(conn, batch_id, **payload.model_dump())
    return trial_out(conn, trials_store.get(conn, _trial_id_for_batch(conn, batch_id)))


@router.post(
    "/trial-batches/{batch_id}/symptom-entries", response_model=TrialOut, status_code=201
)
def add_symptom_entry(
    batch_id: str, payload: SymptomEntryIn, conn: sqlite3.Connection = Depends(get_conn)
):
    observations_store.add_symptom_entry(conn, batch_id, **payload.model_dump())
    return trial_out(conn, trials_store.get(conn, _trial_id_for_batch(conn, batch_id)))


@router.post("/trial-batches/{batch_id}/symptom-preview", response_model=SymptomDoseOut)
def preview_symptom(
    batch_id: str, payload: SymptomPreviewIn, conn: sqlite3.Connection = Depends(get_conn)
):
    """Plan decision #8 — a POST because it carries a body, and it writes nothing."""
    return _dose(observations_store.preview_symptom(conn, batch_id, **payload.model_dump()))


def _trial_id_for_batch(conn, batch_id: str) -> str:
    row = conn.execute(
        "SELECT trial_id FROM trial_batch WHERE id = ?", (batch_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No batch '{batch_id}'.")
    return row["trial_id"]
