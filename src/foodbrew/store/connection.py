"""Connection handling. One connection per request, never shared across requests."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def connect(path: Path | str) -> Iterator[sqlite3.Connection]:
    """Open a connection with row access by name and foreign keys enforced.

    schema.sql's `PRAGMA foreign_keys = ON` binds to the connection that ran
    the script and to nothing else, so it is re-issued here. Without it every
    REFERENCES clause in the schema is documentation rather than a constraint.

    `check_same_thread=False` corrects plan decision #10's stated assumption
    that a request's connection "opens and closes in that same thread". Under
    real concurrent load it does not: FastAPI dispatches a sync generator
    dependency's `__enter__` (this function, via api/deps.get_conn) and the
    sync endpoint body to AnyIO's threadpool as two separate `run_in_threadpool`
    calls, which are not guaranteed to land on the same OS thread. The pool
    isolation this module promises — one connection per request, never shared
    across requests, never held across an await point — still holds; only the
    single creating-thread requirement, which stdlib sqlite3 enforces by
    default and this call disables, was ever false under FastAPI's dispatch
    model. Found via tests/api's Playwright e2e spec generating genuine
    concurrent requests, which the httpx TestClient-based suite never does.
    """
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()
