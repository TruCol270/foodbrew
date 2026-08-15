"""Evaluation persistence. Append-only: a run writes a new row, never updates one.

Spec §4: later edits to source records never mutate a stored evaluation, and a
stored snapshot re-run on the same engine version reproduces byte-identical
results. Both properties are tested across the database boundary in
tests/store/test_evaluations.py.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from foodbrew.engine import evaluate
from foodbrew.engine.flags import HEADLINE_DISPLAY, group_findings
from foodbrew.engine.types import DwellProfile, RuleFinding, Verdict
from foodbrew.engine.variants import suggest
from foodbrew.store import variants as variant_store
from foodbrew.store.clock import now_iso
from foodbrew.store.formulations import hydrate_context
from foodbrew.store.ids import new_id
from foodbrew.store.snapshot import snapshot_from_context
from foodbrew.store.variants import StoredSuggestion


@dataclass(frozen=True, slots=True)
class StoredEvaluation:
    id: str
    formulation_id: str
    engine_version: str
    created_at: str
    overall: Verdict
    display: str
    findings: tuple[RuleFinding, ...]
    envelope: dict[DwellProfile, Verdict]
    input_snapshot_json: str
    blockers: tuple[RuleFinding, ...]
    data_gaps: tuple[RuleFinding, ...]
    cautions: tuple[RuleFinding, ...]
    advisories: tuple[RuleFinding, ...]
    suggestions: tuple[StoredSuggestion, ...] = ()


def run(conn: sqlite3.Connection, formulation_id: str) -> StoredEvaluation:
    """Hydrate, evaluate, and persist. Raises ValidationRejection on degenerate input."""
    ctx = hydrate_context(conn, formulation_id)
    result = evaluate(ctx)  # ValidationRejection propagates — nothing is written
    snapshot = snapshot_from_context(ctx)

    evaluation_id = new_id()
    created_at = now_iso()
    conn.execute(
        "INSERT INTO evaluation (id, formulation_id, engine_version, input_snapshot_json,"
        " overall_flag, occasion_envelope_json, created_at) VALUES (?,?,?,?,?,?,?)",
        (
            evaluation_id, formulation_id, result.engine_version, snapshot,
            str(result.overall),
            json.dumps({str(k): str(v) for k, v in result.envelope.items()}, sort_keys=True),
            created_at,
        ),
    )
    conn.executemany(
        "INSERT INTO rule_finding (evaluation_id, rule_id, enzyme_id, food_id, verdict,"
        " advisory, message, evidence_json) VALUES (?,?,?,?,?,?,?,?)",
        [
            (
                evaluation_id, f.rule_id, f.enzyme_id, f.food_id, str(f.verdict),
                int(f.advisory), f.message,
                json.dumps(dict(f.evidence), sort_keys=True, default=str),
            )
            for f in result.findings
        ],
    )
    variant_store.write(conn, evaluation_id, suggest(ctx, result.findings), created_at)
    conn.commit()

    return _assemble(
        evaluation_id=evaluation_id, formulation_id=formulation_id,
        engine_version=result.engine_version, created_at=created_at,
        overall=result.overall, findings=result.findings,
        envelope=dict(result.envelope), snapshot=snapshot,
        suggestions=variant_store.list_for_evaluation(conn, evaluation_id),
    )


def get(conn: sqlite3.Connection, evaluation_id: str) -> StoredEvaluation | None:
    row = conn.execute(
        "SELECT * FROM evaluation WHERE id = ?", (evaluation_id,)
    ).fetchone()
    if row is None:
        return None
    findings = tuple(
        RuleFinding(
            rule_id=r["rule_id"], verdict=Verdict(r["verdict"]), message=r["message"],
            evidence=json.loads(r["evidence_json"]),
            enzyme_id=r["enzyme_id"], food_id=r["food_id"], advisory=bool(r["advisory"]),
        )
        for r in conn.execute(
            "SELECT * FROM rule_finding WHERE evaluation_id = ? ORDER BY id",
            (evaluation_id,),
        )
    )
    return _assemble(
        evaluation_id=row["id"], formulation_id=row["formulation_id"],
        engine_version=row["engine_version"], created_at=row["created_at"],
        overall=Verdict(row["overall_flag"]), findings=findings,
        envelope={
            DwellProfile(k): Verdict(v)
            for k, v in json.loads(row["occasion_envelope_json"]).items()
        },
        snapshot=row["input_snapshot_json"],
        suggestions=variant_store.list_for_evaluation(conn, evaluation_id),
    )


def list_for_formulation(conn, formulation_id: str) -> tuple[StoredEvaluation, ...]:
    ids = [
        r["id"]
        for r in conn.execute(
            "SELECT id FROM evaluation WHERE formulation_id = ?"
            " ORDER BY created_at DESC, id DESC",
            (formulation_id,),
        )
    ]
    return tuple(get(conn, i) for i in ids)


def list_recent(conn, limit: int = 10) -> tuple[StoredEvaluation, ...]:
    ids = [
        r["id"]
        for r in conn.execute(
            "SELECT id FROM evaluation ORDER BY created_at DESC, id DESC LIMIT ?", (limit,)
        )
    ]
    return tuple(get(conn, i) for i in ids)


def _assemble(
    *, evaluation_id, formulation_id, engine_version, created_at, overall, findings,
    envelope, snapshot, suggestions=(),
) -> StoredEvaluation:
    groups = group_findings(findings)
    return StoredEvaluation(
        id=evaluation_id, formulation_id=formulation_id, engine_version=engine_version,
        created_at=created_at, overall=overall, display=HEADLINE_DISPLAY[overall],
        findings=tuple(findings), envelope=envelope, input_snapshot_json=snapshot,
        blockers=groups.blockers, data_gaps=groups.data_gaps,
        cautions=groups.cautions, advisories=groups.advisories,
        suggestions=tuple(suggestions),
    )
