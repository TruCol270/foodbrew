"""Spec §5.3 and Workflow E — trial and batch persistence.

The protocol is generated once, from the evaluation this trial tests, and frozen
into `trial.protocol_json` (plan decision #3). Nothing here ever writes to
`evaluation` or `rule_finding`: an observation never mutates a prediction (§4).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from foodbrew import ENGINE_VERSION
from foodbrew.engine import ValidationRejection
from foodbrew.engine.observations import ObservationRecord
from foodbrew.engine.protocol import Protocol, due_checkpoints, generate
from foodbrew.engine.protocol import satisfied_checkpoint_ids as _satisfied
from foodbrew.engine.trial_rules import ACIDIFIED_FOOD_PH_LIMIT, ambient_storage_allowed
from foodbrew.store import evaluations as evaluations_store
from foodbrew.store.clock import now_iso
from foodbrew.store.ids import new_id
from foodbrew.store.snapshot import context_from_snapshot

PLANNED, RUNNING, COMPLETE, ABANDONED = "planned", "running", "complete", "abandoned"
STATUSES = (PLANNED, RUNNING, COMPLETE, ABANDONED)
#: Spec §3 Workflow E — a terminal trial keeps everything it recorded and takes
#: nothing more (plan decision #12).
TERMINAL = (COMPLETE, ABANDONED)

PH_METHODS = ("strip", "meter", "none")
STORAGE_MODES = ("refrigerated", "ambient")


@dataclass(frozen=True, slots=True)
class StoredBatch:
    id: str
    trial_id: str
    made_at: str
    batch_size_g: float | None
    measured_ph: float | None
    ph_method: str
    make_minutes: int | None
    difficulty_score: int | None
    enzyme_source_note: str
    enzyme_addition_step: int | None
    process_notes: str
    storage_mode: str
    observations: tuple[ObservationRecord, ...] = ()
    symptom_entry_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StoredTrial:
    id: str
    evaluation_id: str
    formulation_id: str
    status: str
    started_at: str | None
    notes: str
    protocol: Protocol
    batches: tuple[StoredBatch, ...] = ()

    @property
    def observations(self) -> tuple[ObservationRecord, ...]:
        return tuple(o for b in self.batches for o in b.observations)

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL


def create(conn: sqlite3.Connection, evaluation_id: str) -> str:
    """Generate the protocol from this evaluation's findings and freeze it."""
    stored = evaluations_store.get(conn, evaluation_id)
    if stored is None:
        raise ValidationRejection(f"Unknown evaluation '{evaluation_id}'.")

    context = context_from_snapshot(stored.input_snapshot_json)
    protocol = generate(
        context=context,
        findings=stored.findings,
        envelope=stored.envelope,
        engine_version=ENGINE_VERSION,
    )
    trial_id = new_id()
    conn.execute(
        "INSERT INTO trial (id, evaluation_id, protocol_json, status, started_at, notes)"
        " VALUES (?,?,?,?,?,?)",
        (trial_id, evaluation_id, protocol.to_json(), PLANNED, None, ""),
    )
    conn.commit()
    return trial_id


def _require_writable(trial: StoredTrial) -> None:
    if trial.is_terminal:
        raise ValidationRejection(
            f"This trial is {trial.status}. Start a new trial to record anything else — "
            "what is already here stays as it is."
        )


def add_batch(
    conn: sqlite3.Connection,
    trial_id: str,
    *,
    batch_size_g: float | None = None,
    measured_ph: float | None = None,
    ph_method: str = "none",
    make_minutes: int | None = None,
    difficulty_score: int | None = None,
    enzyme_source_note: str = "",
    enzyme_addition_step: int | None = None,
    process_notes: str = "",
    storage_mode: str = "refrigerated",
) -> str:
    """Spec §5.3's `trial_batch`, with the 21 CFR 114 gate of §3 Workflow E."""
    trial = get(conn, trial_id)
    if trial is None:
        raise ValidationRejection(f"Unknown trial '{trial_id}'.")
    _require_writable(trial)

    if ph_method not in PH_METHODS:
        raise ValidationRejection(f"pH method must be one of: {', '.join(PH_METHODS)}.")
    if measured_ph is not None and ph_method == "none":
        raise ValidationRejection("Say whether you used a strip or a meter for that pH.")
    if measured_ph is not None and not 0 <= measured_ph <= 14:
        raise ValidationRejection("A pH reading has to be between 0 and 14.")
    if difficulty_score is not None and not 1 <= difficulty_score <= 5:
        raise ValidationRejection("Score how hard it was from 1 to 5.")
    if storage_mode not in STORAGE_MODES:
        raise ValidationRejection(f"Storage has to be one of: {', '.join(STORAGE_MODES)}.")
    if storage_mode == "ambient" and not ambient_storage_allowed(measured_ph):
        raise ValidationRejection(
            "Room-temperature storage needs a measured pH below "
            f"{ACIDIFIED_FOOD_PH_LIMIT} for this batch. Keep it refrigerated, or "
            "measure the pH first."
        )

    batch_id = new_id()
    made_at = now_iso()
    conn.execute(
        "INSERT INTO trial_batch (id, trial_id, made_at, batch_size_g, measured_ph,"
        " ph_method, make_minutes, difficulty_score, enzyme_source_note,"
        " enzyme_addition_step, process_notes, storage_mode)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            batch_id, trial_id, made_at, batch_size_g, measured_ph, ph_method,
            make_minutes, difficulty_score, enzyme_source_note, enzyme_addition_step,
            process_notes, storage_mode,
        ),
    )
    if trial.status == PLANNED:
        conn.execute(
            "UPDATE trial SET status = ?, started_at = ? WHERE id = ?",
            (RUNNING, made_at, trial_id),
        )
    conn.commit()
    return batch_id


def set_status(conn: sqlite3.Connection, trial_id: str, status: str) -> StoredTrial:
    """Spec §5.3 — only the two terminals are settable by hand (decision #12)."""
    trial = get(conn, trial_id)
    if trial is None:
        raise ValidationRejection(f"Unknown trial '{trial_id}'.")
    if status not in TERMINAL:
        raise ValidationRejection(
            "A trial can be marked complete or abandoned; the rest happens on its own."
        )
    if trial.is_terminal:
        raise ValidationRejection(f"This trial is already {trial.status}.")
    conn.execute("UPDATE trial SET status = ? WHERE id = ?", (status, trial_id))
    conn.commit()
    return get(conn, trial_id)


def elapsed_minutes(made_at: str, now: str) -> int:
    """Whole minutes between two ISO-8601 stamps; the engine gets the number only."""
    from datetime import datetime

    delta = datetime.fromisoformat(now) - datetime.fromisoformat(made_at)
    return max(0, int(delta.total_seconds() // 60))


def due_now(trial: StoredTrial, batch: StoredBatch, *, now: str | None = None):
    """Which scheduled checkpoints this batch has reached and not answered."""
    return due_checkpoints(
        trial.protocol,
        elapsed_minutes=elapsed_minutes(batch.made_at, now or now_iso()),
        satisfied_ids=_satisfied(trial.protocol, batch.observations),
    )


def get(conn: sqlite3.Connection, trial_id: str) -> StoredTrial | None:
    row = conn.execute("SELECT * FROM trial WHERE id = ?", (trial_id,)).fetchone()
    if row is None:
        return None
    from foodbrew.store import observations as observations_store

    formulation_row = conn.execute(
        "SELECT formulation_id FROM evaluation WHERE id = ?", (row["evaluation_id"],)
    ).fetchone()
    batches = tuple(
        StoredBatch(
            id=b["id"], trial_id=b["trial_id"], made_at=b["made_at"],
            batch_size_g=b["batch_size_g"], measured_ph=b["measured_ph"],
            ph_method=b["ph_method"], make_minutes=b["make_minutes"],
            difficulty_score=b["difficulty_score"],
            enzyme_source_note=b["enzyme_source_note"],
            enzyme_addition_step=b["enzyme_addition_step"],
            process_notes=b["process_notes"], storage_mode=b["storage_mode"],
            observations=observations_store.list_for_batch(conn, b["id"]),
            symptom_entry_ids=observations_store.symptom_ids_for_batch(conn, b["id"]),
        )
        for b in conn.execute(
            "SELECT * FROM trial_batch WHERE trial_id = ? ORDER BY made_at, id", (trial_id,)
        )
    )
    return StoredTrial(
        id=row["id"], evaluation_id=row["evaluation_id"],
        formulation_id=formulation_row["formulation_id"] if formulation_row else "",
        status=row["status"], started_at=row["started_at"], notes=row["notes"],
        protocol=Protocol.from_json(row["protocol_json"]), batches=batches,
    )


def list_for_evaluation(conn, evaluation_id: str) -> tuple[StoredTrial, ...]:
    ids = [
        r["id"]
        for r in conn.execute(
            "SELECT id FROM trial WHERE evaluation_id = ? ORDER BY rowid DESC",
            (evaluation_id,),
        )
    ]
    return tuple(get(conn, i) for i in ids)


def list_active(conn) -> tuple[StoredTrial, ...]:
    """Spec §10 screen 1 — the Home screen's active trials."""
    ids = [
        r["id"]
        for r in conn.execute(
            "SELECT id FROM trial WHERE status IN (?, ?) ORDER BY rowid DESC",
            (PLANNED, RUNNING),
        )
    ]
    return tuple(get(conn, i) for i in ids)
