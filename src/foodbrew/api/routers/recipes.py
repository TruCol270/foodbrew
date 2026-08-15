"""Recipe CRUD and the recipe builder's live substrate summary."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from foodbrew.api.deps import get_conn
from foodbrew.api.schemas import RecipeIn, RecipeOut, SubstrateRowOut
from foodbrew.engine.views import substrate_summary
from foodbrew.store import recipes as recipes_store
from foodbrew.store.reference import load_catalog

router = APIRouter(tags=["recipes"])


def _out(stored) -> dict:
    return {
        "id": stored.id, "name": stored.name, "notes": stored.notes,
        "created_at": stored.created_at,
        "ingredients": [
            {"food_id": i.food_id, "amount_g": i.amount_g, "order": i.order}
            for i in stored.ingredients
        ],
    }


@router.get("/recipes", response_model=list[RecipeOut])
def list_recipes(conn: sqlite3.Connection = Depends(get_conn)):
    return [_out(r) for r in recipes_store.list_all(conn)]


@router.post("/recipes", response_model=RecipeOut, status_code=201)
def create_recipe(payload: RecipeIn, conn: sqlite3.Connection = Depends(get_conn)):
    recipe_id = recipes_store.create(
        conn, name=payload.name, notes=payload.notes,
        ingredients=[i.model_dump() for i in payload.ingredients],
    )
    return _out(recipes_store.get(conn, recipe_id))


@router.get("/recipes/{recipe_id}", response_model=RecipeOut)
def get_recipe(recipe_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    stored = recipes_store.get(conn, recipe_id)
    if stored is None:
        raise HTTPException(status_code=404, detail=f"No recipe '{recipe_id}'.")
    return _out(stored)


@router.put("/recipes/{recipe_id}", response_model=RecipeOut)
def update_recipe(
    recipe_id: str, payload: RecipeIn, conn: sqlite3.Connection = Depends(get_conn)
):
    if recipes_store.get(conn, recipe_id) is None:
        raise HTTPException(status_code=404, detail=f"No recipe '{recipe_id}'.")
    recipes_store.update(
        conn, recipe_id, name=payload.name, notes=payload.notes,
        ingredients=[i.model_dump() for i in payload.ingredients],
    )
    return _out(recipes_store.get(conn, recipe_id))


@router.get("/recipes/{recipe_id}/substrate-summary", response_model=list[SubstrateRowOut])
def recipe_substrate_summary(recipe_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    stored = recipes_store.get(conn, recipe_id)
    if stored is None:
        raise HTTPException(status_code=404, detail=f"No recipe '{recipe_id}'.")
    catalog = load_catalog(conn)
    rows = substrate_summary(stored.ingredients, catalog.foods, catalog.substrates)
    return [SubstrateRowOut.of(row) for row in rows]
