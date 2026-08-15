"""Workflow A step 5 — propose an enzyme set from the substrate map.

A proposal, not a decision: the founder adds and removes enzymes afterwards,
and removing one does not remove the finding (R14 still reports the uncovered
substrate). Pure, so M3's R14 auto-variant reuses it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from foodbrew.engine.conventions import phase_for_format
from foodbrew.engine.types import (
    Enzyme,
    Food,
    Format,
    SelectedEnzyme,
    Substrate,
)

#: Proposal order within one substrate. Anything unlisted sorts last, then by id,
#: so the proposal is stable rather than dictionary-ordered.
_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def enzyme_for_substrate(substrate_id: str, enzymes: Mapping[str, Enzyme]) -> Enzyme | None:
    """The catalogue's preferred enzyme for one substrate, or None if it has none.

    Priority first, then id, so the choice is stable rather than dictionary-ordered.
    `propose_enzymes` and M3's R14 auto-variant both go through here.
    """
    candidates = [e for e in enzymes.values() if e.substrate_id == substrate_id]
    if not candidates:
        return None
    candidates.sort(key=lambda e: (_PRIORITY_ORDER.get(e.priority, 99), e.id))
    return candidates[0]


def proposed_dose(enzyme: Enzyme) -> float | None:
    """The evidence threshold if there is one, else the benchmark floor, else nothing.

    A dose is never invented: with neither field usable the selection carries
    `dose=None`, and R7 returns cannot_assess naming the missing dose rather
    than the engine guessing a number the founder would then trust.
    """
    if enzyme.dose_evidence_threshold.usable:
        return float(enzyme.dose_evidence_threshold.value)
    if enzyme.dose_min.usable:
        return float(enzyme.dose_min.value)
    return None


def propose_enzymes(
    *,
    trigger_food_ids: Iterable[str],
    format: Format,
    foods: Mapping[str, Food],
    substrates: Mapping[str, Substrate],
    enzymes: Mapping[str, Enzyme],
) -> tuple[SelectedEnzyme, ...]:
    """Enzymes covering the substrates the selected trigger foods carry."""
    wanted: set[str] = set()
    for food_id in trigger_food_ids:
        food = foods.get(food_id)
        if food is None:
            continue
        for substrate_id in food.contains_substrate_ids:
            substrate = substrates.get(substrate_id)
            # Spec §6.2 R14: polyols have no commercial enzyme, and the tool
            # never maps them to one. R14 reports the gap instead.
            if substrate is None or substrate.no_commercial_enzyme:
                continue
            wanted.add(substrate_id)

    phase = phase_for_format(format)
    chosen = {
        substrate_id: enzyme
        for substrate_id, enzyme in (
            (sid, enzyme_for_substrate(sid, enzymes)) for sid in sorted(wanted)
        )
        if enzyme is not None
    }

    return tuple(
        SelectedEnzyme(
            enzyme_id=enzyme.id, dose=proposed_dose(enzyme), phase=phase, encapsulated=False
        )
        for _, enzyme in sorted(chosen.items())
    )
