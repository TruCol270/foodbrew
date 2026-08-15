"""Workflows B and C — apply a suggestion, and compare what changed.

Applying takes a stored suggestion id, never a patch body: the server applies
what its own engine wrote (plan decision #2). The result is a new formulation
and a new evaluation; the originals are untouched (decision #15).
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from foodbrew.api.deps import get_conn
from foodbrew.api.routers.evaluations import evaluation_out
from foodbrew.api.schemas import (
    ApplyVariantIn,
    ComparisonCellOut,
    ComparisonColumnOut,
    ComparisonOut,
    ComparisonRowOut,
    EvaluationOut,
)
from foodbrew.engine import ValidationRejection
from foodbrew.engine.compare import ComparisonSide, compare
from foodbrew.engine.views import dose_cards
from foodbrew.store import evaluations as evaluations_store
from foodbrew.store import formulations as formulations_store
from foodbrew.store import variants as variants_store
from foodbrew.store.snapshot import context_from_snapshot

router = APIRouter(tags=["variants"])


@router.post(
    "/evaluations/{evaluation_id}/apply-variant",
    response_model=EvaluationOut,
    status_code=201,
)
def apply_variant(
    evaluation_id: str,
    payload: ApplyVariantIn,
    conn: sqlite3.Connection = Depends(get_conn),
):
    stored = evaluations_store.get(conn, evaluation_id)
    if stored is None:
        raise HTTPException(status_code=404, detail=f"No evaluation '{evaluation_id}'.")

    suggestion = variants_store.get(conn, payload.suggestion_id)
    if suggestion is None or suggestion.evaluation_id != evaluation_id:
        raise HTTPException(
            status_code=404,
            detail=f"No suggestion {payload.suggestion_id} on this evaluation.",
        )
    if not suggestion.is_applicable:
        raise ValidationRejection(
            "This one is a note rather than a change — there is nothing to apply."
        )

    formulation_id = formulations_store.clone_with_patch(
        conn, stored.formulation_id, suggestion.patch
    )
    return evaluation_out(evaluations_store.run(conn, formulation_id))


@router.get("/compare", response_model=ComparisonOut)
def compare_evaluations(
    ids: list[str] = Query(default_factory=list),
    conn: sqlite3.Connection = Depends(get_conn),
):
    """Spec §10 — `GET /compare?ids=…`, by evaluation id (plan decision #10)."""
    sides = []
    for evaluation_id in ids:
        stored = evaluations_store.get(conn, evaluation_id)
        if stored is None:
            raise HTTPException(status_code=404, detail=f"No evaluation '{evaluation_id}'.")
        ctx = context_from_snapshot(stored.input_snapshot_json)
        sides.append(
            ComparisonSide(
                evaluation_id=stored.id,
                label=f"{stored.display} · {stored.created_at[:16].replace('T', ' ')}",
                headline=stored.display,
                format=ctx.formulation.format.value,
                dwell_profile=(
                    ctx.formulation.dwell_profile.value
                    if ctx.formulation.dwell_profile
                    else None
                ),
                findings=stored.findings,
                envelope=stored.envelope,
                doses={
                    card.enzyme_id: (card.dose, card.dose_unit, card.enzyme_name)
                    for card in dose_cards(ctx)
                },
            )
        )

    comparison = compare(sides)
    return ComparisonOut(
        columns=[
            ComparisonColumnOut(
                evaluation_id=c.evaluation_id, label=c.label, headline=c.headline
            )
            for c in comparison.columns
        ],
        rows=[
            ComparisonRowOut(
                section=row.section, key=row.key, label=row.label, changed=row.changed,
                cells=[
                    ComparisonCellOut(text=cell.text, verdict=cell.verdict, present=cell.present)
                    for cell in row.cells
                ],
            )
            for row in comparison.rows
        ],
    )
