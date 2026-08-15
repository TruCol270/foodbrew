"""Spec §3 Workflow B — the variant comparison table. Pure.

Rows are the UNION across columns, not the intersection. Variants legitimately
differ in which enzymes they select, and a row present on one side and absent on
another is exactly the difference the founder opened this screen to see — so an
absent cell renders "not in this variant" and is never dropped (plan decision
#10).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from foodbrew.engine.rules.r14_substrate_coverage import ValidationRejection
from foodbrew.engine.types import DwellProfile, RuleFinding, Verdict
from foodbrew.engine.views import RULE_TITLES

#: A readability cap and a bound on the query behind it (plan decision #10).
MAX_COLUMNS = 6

MISSING = "not in this variant"

_SECTION_ORDER = ("Verdict", "Setup", "Rules", "Dose per serving", "Occasion envelope")


@dataclass(frozen=True, slots=True)
class ComparisonSide:
    """One evaluation, reduced to what a comparison row can read."""

    evaluation_id: str
    label: str
    headline: str
    format: str
    dwell_profile: str | None
    findings: tuple[RuleFinding, ...]
    envelope: Mapping[DwellProfile, Verdict]
    #: enzyme_id -> (dose, unit, enzyme name)
    doses: Mapping[str, tuple[float | None, str, str]]


@dataclass(frozen=True, slots=True)
class Column:
    evaluation_id: str
    label: str
    headline: str


@dataclass(frozen=True, slots=True)
class Cell:
    text: str
    #: The verdict this cell reports, when it reports one, for colouring.
    verdict: str | None
    present: bool


@dataclass(frozen=True, slots=True)
class Row:
    section: str
    key: str
    label: str
    cells: tuple[Cell, ...]
    changed: bool


@dataclass(frozen=True, slots=True)
class Comparison:
    columns: tuple[Column, ...]
    rows: tuple[Row, ...]


def _finding_key(finding: RuleFinding) -> tuple[str, str, str]:
    return (finding.rule_id, finding.enzyme_id or "", finding.food_id or "")


def _finding_label(key: tuple[str, str, str]) -> str:
    rule_id, enzyme_id, food_id = key
    parts = [f"{rule_id} — {RULE_TITLES.get(rule_id, rule_id)}"]
    subject = " / ".join(p for p in (enzyme_id, food_id) if p)
    if subject:
        parts.append(subject)
    return " · ".join(parts)


def _absent() -> Cell:
    return Cell(MISSING, None, False)


def _row(section: str, key: str, label: str, cells: Sequence[Cell]) -> Row:
    signature = {(c.text, c.verdict, c.present) for c in cells}
    return Row(section, key, label, tuple(cells), changed=len(signature) > 1)


def compare(sides: Sequence[ComparisonSide]) -> Comparison:
    if len(sides) < 2:
        raise ValidationRejection("Pick at least two evaluations to compare.")
    if len(sides) > MAX_COLUMNS:
        raise ValidationRejection(
            f"Compare up to {MAX_COLUMNS} evaluations at a time — you picked {len(sides)}."
        )

    lookups = [{_finding_key(f): f for f in side.findings} for side in sides]
    rows: list[Row] = []

    rows.append(_row("Verdict", "headline", "Headline", [
        Cell(side.headline, None, True) for side in sides
    ]))
    rows.append(_row("Setup", "format", "Format", [
        Cell(side.format, None, True) for side in sides
    ]))
    rows.append(_row("Setup", "dwell_profile", "Declared use occasion", [
        Cell(side.dwell_profile or "not declared", None, True) for side in sides
    ]))

    finding_keys: list[tuple[str, str, str]] = []
    for lookup in lookups:
        for key in lookup:
            if key not in finding_keys:
                finding_keys.append(key)
    finding_keys.sort(key=lambda k: (int(k[0][1:]), k[1], k[2]))

    for key in finding_keys:
        cells = []
        for lookup in lookups:
            finding = lookup.get(key)
            cells.append(
                Cell(finding.message, str(finding.verdict), True)
                if finding is not None
                else _absent()
            )
        rows.append(_row("Rules", ":".join(key), _finding_label(key), cells))

    enzyme_ids: list[str] = []
    for side in sides:
        for enzyme_id in side.doses:
            if enzyme_id not in enzyme_ids:
                enzyme_ids.append(enzyme_id)
    enzyme_ids.sort()

    for enzyme_id in enzyme_ids:
        cells = []
        label = enzyme_id
        for side in sides:
            entry = side.doses.get(enzyme_id)
            if entry is None:
                cells.append(_absent())
                continue
            dose, unit, name = entry
            label = name
            cells.append(
                Cell("no dose set" if dose is None else f"{dose} {unit}".strip(), None, True)
            )
        rows.append(_row("Dose per serving", f"dose:{enzyme_id}", label, cells))

    for profile in DwellProfile:
        cells = []
        for side in sides:
            verdict = side.envelope.get(profile)
            cells.append(
                Cell(str(verdict), str(verdict), True) if verdict is not None else _absent()
            )
        rows.append(
            _row("Occasion envelope", f"envelope:{profile.value}", profile.value, cells)
        )

    # Rows are appended in `_SECTION_ORDER` already; the constant exists so the
    # renderer can group by it, not so this function can re-sort. Sorting here
    # would need `rows.index`, which compares frozen dataclasses by value and
    # would collapse two genuinely identical rows onto one position.
    return Comparison(
        columns=tuple(
            Column(side.evaluation_id, side.label, side.headline) for side in sides
        ),
        rows=tuple(rows),
    )
