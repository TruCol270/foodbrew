"""Spec §2.3's research track — propose a value with a citation, approve, reject."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query

from foodbrew.api.deps import get_conn
from foodbrew.api.schemas import ProposalIn, ProposalOut
from foodbrew.store import proposals as store

router = APIRouter(tags=["proposals"])


def _out(proposal) -> ProposalOut:
    return ProposalOut(**{f: getattr(proposal, f) for f in ProposalOut.model_fields})


@router.get("/proposals", response_model=list[ProposalOut])
def list_proposals(
    status: str | None = Query(default=None, description="pending | approved | rejected"),
    conn: sqlite3.Connection = Depends(get_conn),
):
    return [_out(p) for p in store.list_all(conn, status)]


@router.post("/proposals", response_model=ProposalOut, status_code=201)
def create_proposal(payload: ProposalIn, conn: sqlite3.Connection = Depends(get_conn)):
    proposal_id = store.create(conn, **payload.model_dump())
    return _out(store.get(conn, proposal_id))


@router.post("/proposals/{proposal_id}/approve", response_model=ProposalOut)
def approve_proposal(proposal_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    return _out(store.approve(conn, proposal_id))


@router.post("/proposals/{proposal_id}/reject", response_model=ProposalOut)
def reject_proposal(proposal_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    return _out(store.reject(conn, proposal_id))
