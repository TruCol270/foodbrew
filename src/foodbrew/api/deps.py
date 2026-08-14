"""Request-scoped dependencies.

Every endpoint is a plain `def`, so FastAPI runs it in a worker thread and the
connection opened here is used and closed in that same thread. sqlite3 objects
are thread-confined; an async endpoint sharing a connection would be a bug that
only appears under concurrency (plan decision #10).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

from fastapi import Request

from foodbrew.store.connection import connect


def get_conn(request: Request) -> Iterator[sqlite3.Connection]:
    with connect(request.app.state.settings.db_path) as conn:
        yield conn
