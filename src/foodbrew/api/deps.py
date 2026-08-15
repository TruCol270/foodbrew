"""Request-scoped dependencies.

Every endpoint is a plain `def`, so FastAPI runs it via AnyIO's threadpool
rather than the event loop. The connection opened here is scoped to one
request and never shared across requests — but the OS thread that opens it and
the OS thread that uses it can differ (see store/connection.py's docstring for
why, and plan decision #10's amendment for the concurrency bug this caused
before `check_same_thread=False` was added there).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

from fastapi import Request

from foodbrew.store.connection import connect


def get_conn(request: Request) -> Iterator[sqlite3.Connection]:
    with connect(request.app.state.settings.db_path) as conn:
        yield conn
