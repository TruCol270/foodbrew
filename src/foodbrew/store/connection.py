"""Connection handling. One connection per request, thread-confined."""

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
    """
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()
