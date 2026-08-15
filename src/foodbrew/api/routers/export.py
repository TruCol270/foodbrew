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
from foodbrew.engine.report import ReportInput, ReportSuggestion, render_markdown
from foodbrew.store import evaluations as evaluations_store
from foodbrew.store import formulations as formulations_store
from foodbrew.store import recipes as recipes_store
from foodbrew.store.snapshot import context_from_snapshot

router = APIRouter(tags=["export"])


@router.get("/export/{evaluation_id}.md", response_class=PlainTextResponse)
def export_markdown(evaluation_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    stored = evaluations_store.get(conn, evaluation_id)
    if stored is None:
        raise HTTPException(status_code=404, detail=f"No evaluation '{evaluation_id}'.")

    ctx = context_from_snapshot(stored.input_snapshot_json)
    stale, _changes = evaluations_store.freshness(conn, stored)

    recipe_id = formulations_store.recipe_id_for(conn, stored.formulation_id)
    recipe = recipes_store.get(conn, recipe_id) if recipe_id else None

    body = render_markdown(
        ReportInput(
            evaluation_id=stored.id,
            created_at=stored.created_at,
            engine_version=stored.engine_version,
            recipe_name=recipe.name if recipe else "Untitled recipe",
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
        )
    )
    return PlainTextResponse(body, media_type="text/markdown; charset=utf-8")
