"""Time. Separated so tests can monkeypatch one symbol."""

from __future__ import annotations

from datetime import UTC, datetime


def now_iso() -> str:
    """UTC, ISO-8601, offset-suffixed — lexicographically sortable as stored."""
    return datetime.now(UTC).isoformat()
