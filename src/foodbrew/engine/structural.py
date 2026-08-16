"""Validation for the two structured catalogue fields (plan decision #4).

`enzyme.degrades_structural` and `food.structural` are JSON lists over closed
enums, not `Tracked` scalars, and `r15_applied_texture` reads them directly.
Their provenance lives INSIDE the value: `SeverityTier.UNCONFIRMED` is the
unconfirmed state, and §6.3.1 maps it to cannot_assess on every profile. So
answering §15 item 4 is flipping a tier from `unconfirmed` to `gradual` with a
citation — not attaching a truth label to a list.

Pure. This module validates; it never writes.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from foodbrew.engine.types import SeverityTier, StructuralClass


class StructuralError(ValueError):
    """Invalid structured payload. The store turns this into a ValidationRejection."""


def parse_enzyme_entries(raw: Sequence | str) -> tuple[dict, ...]:
    """`[{"structural_class": ..., "tier": ...}, ...]`, both closed enums."""
    entries = _as_list(raw)
    out: list[dict] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise StructuralError(
                "each entry is an object with a structural_class and a tier"
            )
        cls = _enum(StructuralClass, entry.get("structural_class"), "structural_class")
        tier = _enum(SeverityTier, entry.get("tier"), "tier")
        if cls.value in seen:
            raise StructuralError(f"'{cls.value}' appears twice; keep one entry per class")
        seen.add(cls.value)
        out.append({"structural_class": cls.value, "tier": tier.value})
    return tuple(out)


def parse_food_classes(raw: Sequence | str) -> tuple[str, ...]:
    """`["pectin_cellulose", ...]` — a food carries classes, not tiers."""
    out: list[str] = []
    for value in _as_list(raw):
        cls = _enum(StructuralClass, value, "structural class")
        if cls.value not in out:
            out.append(cls.value)
    return tuple(out)


def _as_list(raw: Sequence | str) -> list:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise StructuralError("that is not valid JSON") from exc
    if not isinstance(raw, list):
        raise StructuralError("expected a list")
    return raw


def _enum(enum_cls, value, what: str):
    try:
        return enum_cls(value)
    except ValueError as exc:
        allowed = ", ".join(m.value for m in enum_cls)
        raise StructuralError(f"unknown {what} '{value}'; allowed: {allowed}") from exc
