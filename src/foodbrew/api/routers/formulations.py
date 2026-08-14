"""Formulation setup (§10 screen 3), including the proposed enzyme set."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from foodbrew.api.deps import get_conn
from foodbrew.api.schemas import (
    FormulationIn,
    FormulationOut,
    ProcessStepIn,
    SelectedEnzymeIn,
    TrackedOut,
)
from foodbrew.engine import ValidationRejection
from foodbrew.engine.selection import propose_enzymes
from foodbrew.engine.types import Format
from foodbrew.store import formulations as store
from foodbrew.store.reference import load_catalog

router = APIRouter(tags=["formulations"])


def _out(formulation, recipe_id: str) -> dict:
    return {
        "id": formulation.id, "recipe_id": recipe_id, "format": str(formulation.format),
        "target_trigger_food_ids": list(formulation.target_trigger_food_ids),
        "application_food_ids": list(formulation.application_food_ids),
        "dwell_profile": str(formulation.dwell_profile) if formulation.dwell_profile else None,
        "enzymes": [
            SelectedEnzymeIn(
                enzyme_id=s.enzyme_id, dose=s.dose, phase=str(s.phase),
                encapsulated=s.encapsulated, source_choice=s.source_choice,
            )
            for s in formulation.enzymes
        ],
        "serving_size_g": formulation.serving_size_g,
        "measured_ph": TrackedOut.of(formulation.measured_ph),
        "process_steps": [
            ProcessStepIn(order=s.order, label=s.label, is_heat=s.is_heat)
            for s in formulation.process_steps
        ],
        "enzyme_addition_index": formulation.enzyme_addition_index,
        "parent_formulation_id": formulation.parent_formulation_id,
    }


@router.post("/formulations", response_model=FormulationOut, status_code=201)
def create_formulation(payload: FormulationIn, conn: sqlite3.Connection = Depends(get_conn)):
    formulation_id = store.create(
        conn,
        recipe_id=payload.recipe_id, format=payload.format,
        target_trigger_food_ids=payload.target_trigger_food_ids,
        application_food_ids=payload.application_food_ids,
        dwell_profile=payload.dwell_profile,
        enzymes=[e.model_dump() for e in payload.enzymes],
        serving_size_g=payload.serving_size_g, measured_ph=payload.measured_ph,
        process_steps=[s.model_dump() for s in payload.process_steps],
        enzyme_addition_index=payload.enzyme_addition_index,
        parent_formulation_id=payload.parent_formulation_id,
    )
    return _out(store.get(conn, formulation_id), payload.recipe_id)


@router.get("/formulations/{formulation_id}", response_model=FormulationOut)
def get_formulation(formulation_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    formulation = store.get(conn, formulation_id)
    if formulation is None:
        raise HTTPException(status_code=404, detail=f"No formulation '{formulation_id}'.")
    return _out(formulation, store.recipe_id_for(conn, formulation_id))


@router.get("/proposed-enzymes", response_model=list[SelectedEnzymeIn])
def proposed_enzymes(
    trigger_food_ids: list[str] = Query(default_factory=list),
    format: str = Query(default="dry_sachet"),
    conn: sqlite3.Connection = Depends(get_conn),
):
    """Workflow A step 5. A proposal the founder edits — never a locked decision."""
    try:
        fmt = Format(format)
    except ValueError as exc:
        raise ValidationRejection(f"Unknown format '{format}'.") from exc
    catalog = load_catalog(conn)
    return [
        SelectedEnzymeIn(
            enzyme_id=s.enzyme_id, dose=s.dose, phase=str(s.phase),
            encapsulated=s.encapsulated, source_choice=s.source_choice,
        )
        for s in propose_enzymes(
            trigger_food_ids=tuple(trigger_food_ids), format=fmt,
            foods=catalog.foods, substrates=catalog.substrates, enzymes=catalog.enzymes,
        )
    ]
