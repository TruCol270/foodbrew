"""Spec §10 — the words this tool never uses about its own output, in one place.

Two lints consume this list and they match differently, on purpose (plan
decision #11):

* `contains_prohibited` matches on WORD BOUNDARIES. "safety" is not "safe", and
  the §10 screen-8 footer says "Not a safety, efficacy, or regulatory
  determination" — a substring match would forbid the disclaimer itself.
* `tests/api/test_contracts.py` matches on SUBSTRINGS across `api/` source. That
  is stricter than this list needs, and nothing under `api/` has any reason to
  contain the letters, so it stays stricter.
"""

from __future__ import annotations

import re

#: Spec §10. Closed list. Adding to it is a product decision, not a refactor.
PROHIBITED_WORDS: tuple[str, ...] = (
    "safe",
    "validated",
    "guaranteed",
    "clinically proven",
    "proven",
    "demonstrated",
)

_PATTERNS = tuple(
    (word, re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)) for word in PROHIBITED_WORDS
)


def contains_prohibited(text: str) -> tuple[str, ...]:
    """Every prohibited word appearing in `text` as a whole word, in list order."""
    return tuple(word for word, pattern in _PATTERNS if pattern.search(text))
