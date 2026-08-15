"""Recipe persistence, plus the validation spec §6.7 places at the boundary."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from foodbrew.engine import ValidationRejection
from foodbrew.engine.types import RecipeIngredient
from foodbrew.store.clock import now_iso
from foodbrew.store.ids import new_id


@dataclass(frozen=True, slots=True)
class StoredRecipe:
    id: str
    name: str
    notes: str
    created_at: str
    ingredients: tuple[RecipeIngredient, ...]


def _validate(conn: sqlite3.Connection, ingredients: Sequence[dict]) -> None:
    """Spec §6.7: a recipe with zero ingredients is rejected, not evaluated.

    Nothing in the engine owns this one — R14 owns the other degenerate case —
    so it is enforced here and again at evaluate time, raising the same type so
    both map to one HTTP status.
    """
    if not ingredients:
        raise ValidationRejection("Add at least one ingredient to this recipe.")

    known = {r["id"] for r in conn.execute("SELECT id FROM food")}
    seen: set[str] = set()
    for item in ingredients:
        food_id = item["food_id"]
        if food_id not in known:
            raise ValidationRejection(f"Unknown food '{food_id}'.")
        if food_id in seen:
            raise ValidationRejection(
                f"'{food_id}' appears twice — combine it into one amount."
            )
        seen.add(food_id)
        if float(item["amount_g"]) < 0:
            raise ValidationRejection(f"'{food_id}': amount cannot be negative.")


def _write_ingredients(conn, recipe_id: str, ingredients: Sequence[dict]) -> None:
    conn.execute("DELETE FROM recipe_ingredient WHERE recipe_id = ?", (recipe_id,))
    conn.executemany(
        'INSERT INTO recipe_ingredient (recipe_id, food_id, amount_g, "order")'
        " VALUES (?, ?, ?, ?)",
        [
            (recipe_id, i["food_id"], float(i["amount_g"]), int(i.get("order", n)))
            for n, i in enumerate(ingredients, start=1)
        ],
    )


def create(conn, *, name: str, notes: str, ingredients: Sequence[dict]) -> str:
    _validate(conn, ingredients)
    recipe_id = new_id()
    conn.execute(
        "INSERT INTO recipe (id, name, notes, created_at) VALUES (?, ?, ?, ?)",
        (recipe_id, name, notes, now_iso()),
    )
    _write_ingredients(conn, recipe_id, ingredients)
    conn.commit()
    return recipe_id


def update(conn, recipe_id: str, *, name: str, notes: str, ingredients: Sequence[dict]) -> None:
    _validate(conn, ingredients)
    conn.execute(
        "UPDATE recipe SET name = ?, notes = ? WHERE id = ?", (name, notes, recipe_id)
    )
    _write_ingredients(conn, recipe_id, ingredients)
    conn.commit()


def get(conn, recipe_id: str) -> StoredRecipe | None:
    row = conn.execute("SELECT * FROM recipe WHERE id = ?", (recipe_id,)).fetchone()
    if row is None:
        return None
    return StoredRecipe(
        id=row["id"], name=row["name"], notes=row["notes"], created_at=row["created_at"],
        ingredients=ingredients_for(conn, recipe_id),
    )


def ingredients_for(conn, recipe_id: str) -> tuple[RecipeIngredient, ...]:
    return tuple(
        RecipeIngredient(r["food_id"], float(r["amount_g"]), int(r["order"]))
        for r in conn.execute(
            'SELECT food_id, amount_g, "order" FROM recipe_ingredient'
            ' WHERE recipe_id = ? ORDER BY "order", food_id',
            (recipe_id,),
        )
    )


def list_all(conn) -> tuple[StoredRecipe, ...]:
    rows = conn.execute("SELECT * FROM recipe ORDER BY created_at DESC, id DESC").fetchall()
    return tuple(
        StoredRecipe(
            id=r["id"], name=r["name"], notes=r["notes"], created_at=r["created_at"],
            ingredients=ingredients_for(conn, r["id"]),
        )
        for r in rows
    )
