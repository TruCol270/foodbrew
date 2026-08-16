"""Spec §5.2 audit_event. Every write to a reference record leaves one of these.

`record` deliberately does NOT commit. The trace and the change it describes are
one transaction, and a writer that committed here would leave a window where the
audit row exists and the edit does not — or the reverse, if the caller then
failed. The caller commits both together.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass

from foodbrew.store.clock import now_iso

#: Spec §3 — single user, no auth on localhost. Recorded anyway so the column
#: means something the day there is a second actor.
DEFAULT_ACTOR = "founder"


@dataclass(frozen=True, slots=True)
class AuditEvent:
    id: int
    actor: str
    action: str
    entity: str
    before: dict | None
    after: dict | None
    timestamp: str


def _dump(payload: Mapping | None) -> str | None:
    if payload is None:
        return None
    return json.dumps(dict(payload), sort_keys=True, default=str)


def record(
    conn: sqlite3.Connection,
    *,
    action: str,
    entity: str,
    before: Mapping | None = None,
    after: Mapping | None = None,
    actor: str = DEFAULT_ACTOR,
) -> None:
    """`entity` is `<table>:<id>` — the schema has no separate entity_id column."""
    conn.execute(
        "INSERT INTO audit_event (actor, action, entity, before_json, after_json, timestamp)"
        " VALUES (?,?,?,?,?,?)",
        (actor, action, entity, _dump(before), _dump(after), now_iso()),
    )


def last_edited_for(conn: sqlite3.Connection, table: str) -> dict[str, str]:
    """Newest edit timestamp per record of `table`, keyed by record id.

    Derived, not stored (plan decision #5): every edit already writes an
    audit_event whose entity is "<table>:<id>". A global reset writes
    entity='reference' and therefore does NOT stamp individual records — a
    record with no row here has never been edited, and the editor says
    "shipped value" rather than inventing a date.
    """
    prefix = f"{table}:"
    return {
        row["entity"][len(prefix):]: row["last_edited"]
        for row in conn.execute(
            "SELECT entity, MAX(timestamp) AS last_edited FROM audit_event"
            " WHERE entity LIKE ? GROUP BY entity",
            (prefix + "%",),
        )
    }


def list_recent(conn: sqlite3.Connection, limit: int = 50) -> tuple[AuditEvent, ...]:
    rows = conn.execute(
        "SELECT * FROM audit_event ORDER BY timestamp DESC, id DESC LIMIT ?", (limit,)
    ).fetchall()
    return tuple(
        AuditEvent(
            id=row["id"], actor=row["actor"], action=row["action"], entity=row["entity"],
            before=json.loads(row["before_json"]) if row["before_json"] else None,
            after=json.loads(row["after_json"]) if row["after_json"] else None,
            timestamp=row["timestamp"],
        )
        for row in rows
    )
