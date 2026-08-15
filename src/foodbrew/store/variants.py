"""Spec §5.2 variant_suggestion. Written once, with the evaluation, never updated.

A suggestion is an action offered, not a display: pressing the button mutates
the database, so the patch that gets applied has to be the patch the founder was
looking at. That is why these are frozen alongside the findings rather than
recomputed on read the way dose cards are (plan decision #3).

The table has no column for `triggered_by` and plan decision #1 forbids adding
one, so `patch_json` carries the whole machine payload — `{"ops": [...],
"raised_by": [...]}` — rather than only the ops. `patch.apply_patch` reads
`ops` and ignores every other key, so the extra field costs nothing there, and
the report gets the rules that asked for a change without the description
having to spell them out in prose.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from foodbrew.engine.variants import Suggestion


@dataclass(frozen=True, slots=True)
class StoredSuggestion:
    id: int
    evaluation_id: str
    suggestion_type: str
    description: str
    #: The rule ids that asked for this change.
    raised_by: tuple[str, ...]
    #: Empty for a note — there is nothing to apply.
    ops: tuple[dict, ...]
    created_at: str

    @property
    def is_applicable(self) -> bool:
        return bool(self.ops)

    @property
    def patch(self) -> dict | None:
        return {"ops": [dict(op) for op in self.ops]} if self.ops else None


def _payload(suggestion: Suggestion) -> dict:
    return {
        "ops": list(suggestion.patch["ops"]) if suggestion.patch else [],
        "raised_by": list(suggestion.triggered_by),
    }


def write(
    conn: sqlite3.Connection,
    evaluation_id: str,
    suggestions: Sequence[Suggestion],
    created_at: str,
) -> None:
    conn.executemany(
        "INSERT INTO variant_suggestion (evaluation_id, suggestion_type, description,"
        " patch_json, created_at) VALUES (?,?,?,?,?)",
        [
            (
                evaluation_id,
                suggestion.suggestion_type.value,
                suggestion.description,
                json.dumps(_payload(suggestion), sort_keys=True, separators=(",", ":")),
                created_at,
            )
            for suggestion in suggestions
        ],
    )


def _row(row: sqlite3.Row) -> StoredSuggestion:
    payload = json.loads(row["patch_json"]) or {}
    return StoredSuggestion(
        id=row["id"],
        evaluation_id=row["evaluation_id"],
        suggestion_type=row["suggestion_type"],
        description=row["description"],
        raised_by=tuple(payload.get("raised_by", ())),
        ops=tuple(payload.get("ops") or ()),
        created_at=row["created_at"],
    )


def list_for_evaluation(
    conn: sqlite3.Connection, evaluation_id: str
) -> tuple[StoredSuggestion, ...]:
    return tuple(
        _row(row)
        for row in conn.execute(
            "SELECT * FROM variant_suggestion WHERE evaluation_id = ? ORDER BY id",
            (evaluation_id,),
        )
    )


def get(conn: sqlite3.Connection, suggestion_id: int) -> StoredSuggestion | None:
    row = conn.execute(
        "SELECT * FROM variant_suggestion WHERE id = ?", (suggestion_id,)
    ).fetchone()
    return _row(row) if row else None
