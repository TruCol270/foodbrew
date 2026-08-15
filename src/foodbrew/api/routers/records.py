"""Workflow D — the enzyme and food editors, and reset to baseline.

Nothing here decides a truth label. `store/records.py` attaches `user_provided`
to a direct edit; the only path to `confirmed` is an approved proposal, in the
router next door (plan decision #7).
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from foodbrew.api.deps import get_conn
from foodbrew.api.schemas import AuditEventOut, EnzymeOut, FoodOut, RecordEditIn
from foodbrew.store import audit as audit_store
from foodbrew.store import foods as foods_store
from foodbrew.store import records as records_store
from foodbrew.store.reference import load_catalog

router = APIRouter(tags=["database"])


def _enzyme(conn: sqlite3.Connection, enzyme_id: str) -> EnzymeOut:
    return EnzymeOut.of(load_catalog(conn).enzymes[enzyme_id])


@router.put("/enzymes/{enzyme_id}", response_model=EnzymeOut)
def update_enzyme(
    enzyme_id: str, payload: RecordEditIn, conn: sqlite3.Connection = Depends(get_conn)
):
    records_store.update(conn, "enzyme", enzyme_id, payload.fields)
    return _enzyme(conn, enzyme_id)


@router.post("/enzymes/{enzyme_id}/reset", response_model=EnzymeOut)
def reset_enzyme(enzyme_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    records_store.reset_record(conn, "enzyme", enzyme_id)
    return _enzyme(conn, enzyme_id)


@router.put("/foods/{food_id}", response_model=FoodOut)
def update_food(
    food_id: str, payload: RecordEditIn, conn: sqlite3.Connection = Depends(get_conn)
):
    records_store.update(conn, "food", food_id, payload.fields)
    return FoodOut.of(foods_store.get(conn, food_id))


@router.post("/foods/{food_id}/reset", response_model=FoodOut)
def reset_food(food_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    records_store.reset_record(conn, "food", food_id)
    return FoodOut.of(foods_store.get(conn, food_id))


@router.post("/reference/reset", status_code=204)
def reset_reference(conn: sqlite3.Connection = Depends(get_conn)) -> None:
    """Discards every edit to every enzyme and food row. There is no undo."""
    records_store.reset_all(conn)


@router.get("/audit", response_model=list[AuditEventOut])
def recent_changes(limit: int = 50, conn: sqlite3.Connection = Depends(get_conn)):
    return [
        AuditEventOut(
            id=event.id, actor=event.actor, action=event.action,
            entity=event.entity, timestamp=event.timestamp,
        )
        for event in audit_store.list_recent(conn, limit)
    ]
