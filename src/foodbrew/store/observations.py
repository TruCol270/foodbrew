"""Spec §5.3 — `trial_observation` and `trial_symptom_entry`.

Two invariants live here and are asserted in tests/api/test_contracts_m4.py:

* `dwell_bucket` is derived from `elapsed_minutes` by `texture.dwell_bucket` and
  by nothing else — no caller may supply one (plan decision #2).
* `computed_dose_json` is frozen against the evaluation's own input snapshot, so
  a later edit to a threshold cannot change what an eaten meal is judged against
  (plan decision #7).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from foodbrew.engine import ValidationRejection
from foodbrew.engine.observations import ObservationRecord, ObservationType
from foodbrew.engine.symptoms import SERVINGS, SymptomDoseMath, computed_dose
from foodbrew.engine.texture import dwell_bucket
from foodbrew.store import trials as trials_store
from foodbrew.store.clock import now_iso
from foodbrew.store.ids import new_id
from foodbrew.store.snapshot import context_from_snapshot


@dataclass(frozen=True, slots=True)
class StoredSymptomEntry:
    id: str
    trial_batch_id: str
    eaten_at: str
    trigger_food_id: str
    amount_value: float | None
    amount_unit: str
    doses_used: float | None
    computed_dose: dict
    outcome_score: int | None
    notes: str


def _batch_context(conn: sqlite3.Connection, batch_id: str):
    """The trial, and the EvalContext frozen into the evaluation it tests."""
    row = conn.execute(
        "SELECT b.trial_id AS trial_id, e.input_snapshot_json AS snapshot"
        " FROM trial_batch b"
        " JOIN trial t ON t.id = b.trial_id"
        " JOIN evaluation e ON e.id = t.evaluation_id"
        " WHERE b.id = ?",
        (batch_id,),
    ).fetchone()
    if row is None:
        raise ValidationRejection(f"Unknown batch '{batch_id}'.")
    trial = trials_store.get(conn, row["trial_id"])
    return trial, context_from_snapshot(row["snapshot"])


def add_observation(
    conn: sqlite3.Connection,
    batch_id: str,
    *,
    type: str,
    elapsed_minutes: int,
    score: int | None = None,
    free_text: str = "",
    was_blinded: bool = False,
    had_undressed_control: bool = False,
    application_food_id: str = "",
) -> str:
    trial, context = _batch_context(conn, batch_id)
    if trial.is_terminal:
        raise ValidationRejection(
            f"This trial is {trial.status}. Start a new trial to record anything else — "
            "what is already here stays as it is."
        )
    try:
        observation_type = ObservationType(type)
    except ValueError as exc:
        allowed = ", ".join(str(t) for t in ObservationType)
        raise ValidationRejection(f"An observation has to be one of: {allowed}.") from exc

    if elapsed_minutes < 0:
        raise ValidationRejection("Time since you made it cannot be negative.")
    if score is not None and not 1 <= score <= 5:
        raise ValidationRejection("Scores run from 1 to 5.")
    if application_food_id:
        food = context.foods.get(application_food_id)
        if food is None:
            raise ValidationRejection(f"Unknown food '{application_food_id}'.")
        if application_food_id not in context.formulation.application_food_ids:
            raise ValidationRejection(
                f"{food.name} is not one of the foods this formulation said it would "
                "be poured on."
            )
    if observation_type is ObservationType.FOOD_TEXTURE and not application_food_id:
        raise ValidationRejection("Say which food you looked at.")

    observation_id = new_id()
    conn.execute(
        "INSERT INTO trial_observation (id, trial_batch_id, observed_at, elapsed_minutes,"
        " type, dwell_bucket, score, free_text, was_blinded, application_food_id,"
        " had_undressed_control) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            observation_id, batch_id, now_iso(), int(elapsed_minutes),
            str(observation_type), str(dwell_bucket(int(elapsed_minutes))), score,
            free_text, int(was_blinded), application_food_id or None,
            int(had_undressed_control),
        ),
    )
    conn.commit()
    return observation_id


def list_for_batch(conn: sqlite3.Connection, batch_id: str) -> tuple[ObservationRecord, ...]:
    return tuple(
        ObservationRecord(
            id=r["id"], type=ObservationType(r["type"]), observed_at=r["observed_at"],
            elapsed_minutes=r["elapsed_minutes"], score=r["score"],
            free_text=r["free_text"], was_blinded=bool(r["was_blinded"]),
            had_undressed_control=bool(r["had_undressed_control"]),
            application_food_id=r["application_food_id"] or "",
        )
        for r in conn.execute(
            "SELECT * FROM trial_observation WHERE trial_batch_id = ?"
            " ORDER BY elapsed_minutes, id",
            (batch_id,),
        )
    )


def preview_symptom(
    conn: sqlite3.Connection,
    batch_id: str,
    *,
    trigger_food_id: str,
    amount_value: float | None,
    amount_unit: str = SERVINGS,
    doses_used: float | None,
) -> SymptomDoseMath:
    """The live dose math (plan decision #8). Reads; writes nothing."""
    _trial, context = _batch_context(conn, batch_id)
    return computed_dose(
        context=context, trigger_food_id=trigger_food_id, amount_value=amount_value,
        amount_unit=amount_unit, doses_used=doses_used,
    )


def add_symptom_entry(
    conn: sqlite3.Connection,
    batch_id: str,
    *,
    trigger_food_id: str,
    amount_value: float | None = None,
    amount_unit: str = SERVINGS,
    doses_used: float | None = None,
    outcome_score: int | None = None,
    notes: str = "",
    eaten_at: str | None = None,
) -> str:
    """Spec §5.3 — the sole route for symptom capture (plan decision #6)."""
    trial, context = _batch_context(conn, batch_id)
    if trial.is_terminal:
        raise ValidationRejection(
            f"This trial is {trial.status}. Start a new trial to record anything else — "
            "what is already here stays as it is."
        )
    if trigger_food_id not in context.foods:
        raise ValidationRejection(f"Unknown food '{trigger_food_id}'.")
    if outcome_score is not None and not 1 <= outcome_score <= 5:
        raise ValidationRejection("Scores run from 1 to 5.")
    if amount_value is not None and amount_value < 0:
        raise ValidationRejection("An amount cannot be negative.")
    if doses_used is not None and doses_used < 0:
        raise ValidationRejection("A number of doses cannot be negative.")

    math = computed_dose(
        context=context, trigger_food_id=trigger_food_id, amount_value=amount_value,
        amount_unit=amount_unit, doses_used=doses_used,
    )
    entry_id = new_id()
    conn.execute(
        "INSERT INTO trial_symptom_entry (id, trial_batch_id, eaten_at, trigger_food_id,"
        " amount_value, amount_unit, doses_used, computed_dose_json, outcome_score, notes)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            entry_id, batch_id, eaten_at or now_iso(), trigger_food_id, amount_value,
            amount_unit, doses_used, json.dumps(math.as_dict(), sort_keys=True),
            outcome_score, notes,
        ),
    )
    conn.commit()
    return entry_id


def symptoms_for_batch(conn, batch_id: str) -> tuple[StoredSymptomEntry, ...]:
    return tuple(
        StoredSymptomEntry(
            id=r["id"], trial_batch_id=r["trial_batch_id"], eaten_at=r["eaten_at"],
            trigger_food_id=r["trigger_food_id"], amount_value=r["amount_value"],
            amount_unit=r["amount_unit"], doses_used=r["doses_used"],
            computed_dose=json.loads(r["computed_dose_json"]),
            outcome_score=r["outcome_score"], notes=r["notes"],
        )
        for r in conn.execute(
            "SELECT * FROM trial_symptom_entry WHERE trial_batch_id = ? ORDER BY eaten_at, id",
            (batch_id,),
        )
    )


def symptom_ids_for_batch(conn, batch_id: str) -> tuple[str, ...]:
    return tuple(e.id for e in symptoms_for_batch(conn, batch_id))


def symptoms_for_trial(conn, trial_id: str) -> tuple[StoredSymptomEntry, ...]:
    batch_ids = [
        r["id"]
        for r in conn.execute(
            "SELECT id FROM trial_batch WHERE trial_id = ? ORDER BY made_at, id", (trial_id,)
        )
    ]
    return tuple(e for b in batch_ids for e in symptoms_for_batch(conn, b))
