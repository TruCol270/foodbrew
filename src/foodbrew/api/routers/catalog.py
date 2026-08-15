"""Read-only reference data, plus custom-food creation (§10 screen 2)."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query

from foodbrew.api.deps import get_conn
from foodbrew.api.schemas import CustomFoodIn, EnzymeOut, FoodOut, GIRegionOut, SubstrateOut
from foodbrew.store import foods as foods_store
from foodbrew.store.reference import load_catalog

router = APIRouter(tags=["catalog"])


@router.get("/enzymes", response_model=list[EnzymeOut])
def list_enzymes(conn: sqlite3.Connection = Depends(get_conn)):
    catalog = load_catalog(conn)
    return [EnzymeOut.of(e) for e in sorted(catalog.enzymes.values(), key=lambda e: e.name)]


@router.get("/substrates", response_model=list[SubstrateOut])
def list_substrates(conn: sqlite3.Connection = Depends(get_conn)):
    catalog = load_catalog(conn)
    return [SubstrateOut.of(s) for s in sorted(catalog.substrates.values(), key=lambda s: s.name)]


@router.get("/gi-model", response_model=list[GIRegionOut])
def gi_model(conn: sqlite3.Connection = Depends(get_conn)):
    return [GIRegionOut.of(r) for r in load_catalog(conn).gi_regions]


@router.get("/foods", response_model=list[FoodOut])
def list_foods(
    role: str | None = Query(default=None, description="recipe_ingredient | trigger | application"),
    conn: sqlite3.Connection = Depends(get_conn),
):
    return [FoodOut.of(f) for f in foods_store.list_by_role(conn, role)]


@router.post("/foods", response_model=FoodOut, status_code=201)
def create_food(payload: CustomFoodIn, conn: sqlite3.Connection = Depends(get_conn)):
    food_id = foods_store.create_custom(conn, **payload.model_dump())
    return FoodOut.of(foods_store.get(conn, food_id))
