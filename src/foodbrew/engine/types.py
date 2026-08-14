"""Core value types for the rules engine. Pure — no I/O, no persistence."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class TruthLabel(StrEnum):
    """Spec §5.4. Closed enum — no other token may appear in seed, API, or UI."""

    CONFIRMED = "confirmed"
    UNCONFIRMED = "unconfirmed"
    USER_PROVIDED = "user_provided"
    CALCULATED = "calculated"
    OBSERVED = "observed"


#: Labels that count as evidence a rule may act on. UNCONFIRMED never does;
#: CALCULATED is an engine output and is never a rule *input*.
_EVIDENCE_LABELS = frozenset({TruthLabel.CONFIRMED, TruthLabel.USER_PROVIDED, TruthLabel.OBSERVED})


class Verdict(StrEnum):
    """Spec §6. Severity order is defined by _SEVERITY below."""

    PASS = "pass"
    AMBER = "amber"
    CANNOT_ASSESS = "cannot_assess"
    RED = "red"


#: Spec §6.4: red > cannot_assess > amber > pass.
_SEVERITY = {Verdict.PASS: 0, Verdict.AMBER: 1, Verdict.CANNOT_ASSESS: 2, Verdict.RED: 3}


def worst(verdicts) -> Verdict:
    """Worst verdict in an iterable. Empty means nothing objected, so PASS."""
    items = list(verdicts)
    if not items:
        return Verdict.PASS
    return max(items, key=lambda v: _SEVERITY[v])


class DwellProfile(StrEnum):
    """Spec §6.3."""

    IMMEDIATE = "immediate"
    PACKED = "packed"
    MARINADE = "marinade"


class StructuralClass(StrEnum):
    """Spec §5.1 food.structural_json / enzyme.degrades_structural_json."""

    PECTIN_CELLULOSE = "pectin_cellulose"
    STRUCTURAL_PROTEIN = "structural_protein"
    STARCH = "starch"


class SeverityTier(StrEnum):
    """Spec §6.3.1."""

    RAPID = "rapid"
    GRADUAL = "gradual"
    UNCONFIRMED = "unconfirmed"


class Format(StrEnum):
    """Spec §5.2 formulation.format."""

    PREMIXED_WET = "premixed_wet"
    DRY_SACHET = "dry_sachet"
    DUAL_CHAMBER = "dual_chamber"
    ENCAPSULATED_IN_WET = "encapsulated_in_wet"


class Phase(StrEnum):
    """Which side of the pack an enzyme sits on."""

    WET = "wet"
    DRY = "dry"


class Deadline(StrEnum):
    """Spec §5.1 enzyme.deadline."""

    BEFORE_SMALL_INTESTINE = "before_small_intestine"
    BEFORE_COLON = "before_colon"
    SMALL_INTESTINE = "small_intestine"


@dataclass(frozen=True, slots=True)
class Tracked:
    """A value paired with its truth label and provenance (spec §5.1, §5.4).

    `usable` is the single gate every rule consults. A rule that needs a value
    whose `usable` is False must return CANNOT_ASSESS naming the field — never
    a silent pass and never a guess (spec §6).
    """

    value: Any
    status: TruthLabel
    source: str = ""

    @property
    def usable(self) -> bool:
        return self.status in _EVIDENCE_LABELS and self.value is not None


@dataclass(frozen=True, slots=True)
class RuleFinding:
    """One rule's output about one subject (spec §5.2 rule_finding)."""

    rule_id: str
    verdict: Verdict
    message: str
    evidence: Mapping[str, Any] = field(default_factory=dict)
    enzyme_id: str | None = None
    food_id: str | None = None
    #: True when this finding must not influence the headline (spec §6.4).
    #: R12 sets this per-enzyme rather than statically.
    advisory: bool = False
