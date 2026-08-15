"""Spec §5.2 proposal, §2.3's parallel research track.

A proposal is a value plus a source. Approving one is the single path by which a
field becomes `confirmed`, which is what §5.4's definition of that label
requires and what makes §13 fixture (h2) — R12's per-enzyme promotion —
reachable through the product rather than only through raw SQL.

Rejecting a proposal changes no data. The row stays, so the answer "we looked at
this and said no" survives, which is worth more than a clean table.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from foodbrew.engine import ValidationRejection
from foodbrew.store import audit, records
from foodbrew.store.ids import new_id

PENDING, APPROVED, REJECTED = "pending", "approved", "rejected"


@dataclass(frozen=True, slots=True)
class Proposal:
    id: str
    table_name: str
    record_id: str
    field: str
    proposed_value: str | None
    source_citation: str
    status: str


def _of(row: sqlite3.Row) -> Proposal:
    return Proposal(
        id=row["id"], table_name=row["table_name"], record_id=row["record_id"],
        field=row["field"], proposed_value=row["proposed_value"],
        source_citation=row["source_citation"], status=row["status"],
    )


def create(
    conn: sqlite3.Connection,
    *,
    table_name: str,
    record_id: str,
    field: str,
    proposed_value: str,
    source_citation: str,
) -> str:
    records.check_table(table_name)
    if field not in records.TRACKED_FIELDS[table_name]:
        raise ValidationRejection(
            f"'{field}' does not carry a source, so there is nothing to confirm about it."
        )
    if conn.execute(
        f"SELECT 1 FROM {table_name} WHERE id = ?", (record_id,)
    ).fetchone() is None:
        raise ValidationRejection(f"No {table_name} '{record_id}'.")
    if not source_citation.strip():
        raise ValidationRejection(
            "A proposal needs a source citation — that citation is what makes the "
            "value confirmed rather than entered."
        )
    # Parse now, so a bad value is refused at the inbox rather than at approval.
    records.coerce(table_name, field, proposed_value)

    proposal_id = new_id()
    conn.execute(
        "INSERT INTO proposal (id, table_name, record_id, field, proposed_value,"
        " source_citation, status) VALUES (?,?,?,?,?,?,?)",
        (proposal_id, table_name, record_id, field, str(proposed_value),
         source_citation, PENDING),
    )
    conn.commit()
    return proposal_id


def get(conn: sqlite3.Connection, proposal_id: str) -> Proposal | None:
    row = conn.execute("SELECT * FROM proposal WHERE id = ?", (proposal_id,)).fetchone()
    return _of(row) if row else None


def list_all(conn: sqlite3.Connection, status: str | None = None) -> tuple[Proposal, ...]:
    if status is None:
        rows = conn.execute("SELECT * FROM proposal ORDER BY status, id")
    else:
        if status not in (PENDING, APPROVED, REJECTED):
            raise ValidationRejection(f"Unknown proposal status '{status}'.")
        rows = conn.execute(
            "SELECT * FROM proposal WHERE status = ? ORDER BY id", (status,)
        )
    return tuple(_of(row) for row in rows)


def _require_pending(conn: sqlite3.Connection, proposal_id: str) -> Proposal:
    proposal = get(conn, proposal_id)
    if proposal is None:
        raise ValidationRejection(f"No proposal '{proposal_id}'.")
    if proposal.status != PENDING:
        raise ValidationRejection(f"This proposal was already {proposal.status}.")
    return proposal


def approve(conn: sqlite3.Connection, proposal_id: str) -> Proposal:
    proposal = _require_pending(conn, proposal_id)
    records.set_confirmed(
        conn,
        proposal.table_name,
        proposal.record_id,
        proposal.field,
        proposal.proposed_value,
        proposal.source_citation,
    )
    conn.execute("UPDATE proposal SET status = ? WHERE id = ?", (APPROVED, proposal_id))
    audit.record(
        conn, action="approve_proposal", entity=f"proposal:{proposal_id}",
        before={"status": PENDING}, after={"status": APPROVED},
    )
    conn.commit()
    return get(conn, proposal_id)


def reject(conn: sqlite3.Connection, proposal_id: str) -> Proposal:
    _require_pending(conn, proposal_id)  # raises if unknown or already decided
    conn.execute("UPDATE proposal SET status = ? WHERE id = ?", (REJECTED, proposal_id))
    audit.record(
        conn, action="reject_proposal", entity=f"proposal:{proposal_id}",
        before={"status": PENDING}, after={"status": REJECTED},
    )
    conn.commit()
    return get(conn, proposal_id)
