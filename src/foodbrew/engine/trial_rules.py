"""Pure decisions the kitchen trial depends on (spec §6.6 and Workflow E).

M4 builds the capture UI on top of these; the rules themselves live here so they
are testable without a database and cannot be bypassed by a form.
"""

from __future__ import annotations

from enum import Enum

#: 21 CFR 114 acidified-foods line, cited in the founder's condiment materials.
#: Above this, a low-acid product left at room temperature is a food-safety
#: problem rather than a formulation one, so the tool declines to schedule it.
ACIDIFIED_FOOD_PH_LIMIT = 4.6


class ConfidenceTier(str, Enum):
    """Spec §6.6. Deliberately only two values — nothing recorded at home is
    ever demonstrated, proven, or validated."""

    ANECDOTE = "anecdote"
    SUGGESTIVE = "suggestive"


def confidence_tier(*, was_blinded: bool, had_undressed_control: bool) -> ConfidenceTier:
    """Rigor is captured opportunistically, per observation, not committed up front."""
    if was_blinded or had_undressed_control:
        return ConfidenceTier.SUGGESTIVE
    return ConfidenceTier.ANECDOTE


def ambient_storage_allowed(measured_ph: float | None) -> bool:
    """An ambient storage watch requires a measured pH strictly below the limit.

    No measurement means no ambient watch: an unknown pH is not an argument for
    leaving a possibly low-acid product on the counter.
    """
    if measured_ph is None:
        return False
    return float(measured_ph) < ACIDIFIED_FOOD_PH_LIMIT
