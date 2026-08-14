"""Spec §8 — where along the tract an enzyme's pH window actually lets it work."""

from __future__ import annotations

from foodbrew.engine.types import Deadline, Enzyme, GIRegion

#: Regions that lie at or before each deadline. Spec §8: these are deadlines,
#: not anatomical targets — the enzyme must finish its work by then.
_REGIONS_AT_OR_BEFORE: dict[Deadline, frozenset[str]] = {
    Deadline.BEFORE_SMALL_INTESTINE: frozenset({"mouth", "stomach_fasting", "stomach_fed"}),
    Deadline.SMALL_INTESTINE: frozenset(
        {"mouth", "stomach_fasting", "stomach_fed", "duodenum", "jejunum_ileum"}
    ),
    Deadline.BEFORE_COLON: frozenset(
        {"mouth", "stomach_fasting", "stomach_fed", "duodenum", "jejunum_ileum"}
    ),
}


def overlaps_region(enzyme: Enzyme, region: GIRegion) -> bool:
    """Does the enzyme's activity range intersect this region's pH range?"""
    if not (enzyme.ph_min.usable and enzyme.ph_max.usable):
        return False
    return (
        float(enzyme.ph_min.value) <= region.ph_high
        and float(enzyme.ph_max.value) >= region.ph_low
    )


def active_regions(enzyme: Enzyme, regions: tuple[GIRegion, ...]) -> tuple[GIRegion, ...]:
    """Regions where the enzyme can actually act.

    Dormant regions (the mouth) are excluded regardless of pH fit: spec §8 says
    dwell there is seconds, too brief for any enzyme to react.
    """
    return tuple(r for r in regions if not r.dormant and overlaps_region(enzyme, r))


def regions_before_deadline(
    deadline: Deadline, regions: tuple[GIRegion, ...]
) -> tuple[GIRegion, ...]:
    allowed = _REGIONS_AT_OR_BEFORE[deadline]
    return tuple(r for r in regions if r.id in allowed)
