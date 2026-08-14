"""Ordered rule registry.

Every rule module exposes exactly three names:
    RULE_ID: str          e.g. "R1"
    ADVISORY: bool        static default; R12 overrides per-finding at runtime
    evaluate(ctx) -> list[RuleFinding]

R13 has no module: spec §6.1 defines it as the aggregation and format
recommendation, which live in flags.py.
"""

from __future__ import annotations

from foodbrew.engine.rules import (
    r01_ph_survival,
    r02_gi_window,
    r03_no_heat,
    r04_water_activation,
    r05_protease_conflict,
    r06_encapsulation,
    r07_dosing,
    r08_taste_drift,
    r09_prebiotic_tension,
    r10_strain_blending,
    r11_food_grade,
    r12_temperature,
    r14_substrate_coverage,
    r15_applied_texture,
    r16_clean_label,
)

ALL_RULES = (
    r01_ph_survival,
    r02_gi_window,
    r03_no_heat,
    r04_water_activation,
    r05_protease_conflict,
    r06_encapsulation,
    r07_dosing,
    r08_taste_drift,
    r09_prebiotic_tension,
    r10_strain_blending,
    r11_food_grade,
    r12_temperature,
    r14_substrate_coverage,
    r15_applied_texture,
    r16_clean_label,
)

#: Spec §6.4 — rules whose verdicts may set the headline.
HEADLINE_RULE_IDS = frozenset(m.RULE_ID for m in ALL_RULES if not m.ADVISORY)
#: Spec §6.4 — advisory rules can never change the overall flag.
ADVISORY_RULE_IDS = frozenset(m.RULE_ID for m in ALL_RULES if m.ADVISORY)
