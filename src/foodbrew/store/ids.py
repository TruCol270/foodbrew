"""Identifier generation. Separated so tests can monkeypatch one symbol."""

from __future__ import annotations

import uuid


def new_id() -> str:
    """A URL-safe opaque id. Hex, so it needs no escaping in a path segment."""
    return uuid.uuid4().hex
