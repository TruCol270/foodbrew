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


@dataclass(frozen=True, slots=True)
class Substrate:
    """Spec §5.1."""

    id: str
    name: str
    native_human_enzyme: bool = False
    is_prebiotic: bool = False
    no_commercial_enzyme: bool = False
    notes: str = ""


@dataclass(frozen=True, slots=True)
class StructuralEntry:
    """One entry of enzyme.degrades_structural_json (spec §6.3.1)."""

    structural_class: StructuralClass
    tier: SeverityTier


@dataclass(frozen=True, slots=True)
class Enzyme:
    """Spec §5.1. Every numeric field is Tracked."""

    id: str
    name: str
    substrate_id: str
    source_type: str
    priority: str
    deadline: Deadline
    ph_min: Tracked
    ph_max: Tracked
    ph_opt_low: Tracked
    ph_opt_high: Tracked
    ph_shelf_stable_min: Tracked
    dose_unit: str
    aliases: tuple[str, ...] = ()
    site_of_action: str = ""
    temp_min_c: Tracked = Tracked(None, TruthLabel.UNCONFIRMED)
    temp_max_c: Tracked = Tracked(None, TruthLabel.UNCONFIRMED)
    temp_opt_c: Tracked = Tracked(None, TruthLabel.UNCONFIRMED)
    dose_min: Tracked = Tracked(None, TruthLabel.UNCONFIRMED)
    dose_max: Tracked = Tracked(None, TruthLabel.UNCONFIRMED)
    dose_evidence_threshold: Tracked = Tracked(None, TruthLabel.UNCONFIRMED)
    dose_benchmark_note: str = ""
    is_protease: bool = False
    is_natural_source: bool = False
    is_gras: Tracked = Tracked(None, TruthLabel.UNCONFIRMED)
    food_grade_note: str = ""
    heat_labile_note: str = ""
    degrades_structural: tuple[StructuralEntry, ...] = ()
    cost_tier: str = ""
    supplier_note: str = ""
    notes: str = ""


@dataclass(frozen=True, slots=True)
class Food:
    """Spec §5.1 — one table, role-flagged, because records serve several roles."""

    id: str
    name: str
    category: str
    is_recipe_ingredient: bool = False
    is_trigger_food: bool = False
    is_application_food: bool = False
    ph: Tracked = Tracked(None, TruthLabel.UNCONFIRMED)
    water_content_pct: Tracked = Tracked(None, TruthLabel.UNCONFIRMED)
    contains_substrate_ids: tuple[str, ...] = ()
    typical_load_value: Tracked = Tracked(None, TruthLabel.UNCONFIRMED)
    typical_load_unit: str = ""
    contains_protease: bool = False
    is_heat_processed: bool = False
    structural: tuple[StructuralClass, ...] = ()
    #: Spec §5.1 / plan decision #2. Inert: no rule reads this, exactly like
    #: `notes`. It travels with the evaluation so the report can declare what is
    #: in the jar without consulting a catalogue that may have moved since.
    allergens: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True, slots=True)
class GIRegion:
    """Spec §8."""

    id: str
    name: str
    ph_low: float
    ph_high: float
    order: int
    dormant: bool = False
    transit_note: str = ""


@dataclass(frozen=True, slots=True)
class RecipeIngredient:
    food_id: str
    amount_g: float
    order: int = 0


@dataclass(frozen=True, slots=True)
class SelectedEnzyme:
    """Spec §5.2 formulation.enzyme_selection_json."""

    enzyme_id: str
    dose: float | None = None
    phase: Phase = Phase.DRY
    encapsulated: bool = False
    source_choice: str = ""


@dataclass(frozen=True, slots=True)
class ProcessStep:
    """Spec §5.2 formulation.process_steps_json."""

    order: int
    label: str
    is_heat: bool = False


@dataclass(frozen=True, slots=True)
class Formulation:
    """Spec §5.2."""

    id: str
    format: Format
    recipe: tuple[RecipeIngredient, ...]
    enzymes: tuple[SelectedEnzyme, ...]
    target_trigger_food_ids: tuple[str, ...] = ()
    application_food_ids: tuple[str, ...] = ()
    dwell_profile: DwellProfile | None = None
    serving_size_g: float | None = None
    measured_ph: Tracked = Tracked(None, TruthLabel.UNCONFIRMED)
    process_steps: tuple[ProcessStep, ...] = ()
    enzyme_addition_index: int | None = None
    parent_formulation_id: str | None = None


@dataclass(frozen=True, slots=True)
class EvalContext:
    """Everything a rule may read. Hydrated by the caller; the engine never loads it."""

    formulation: Formulation
    enzymes: Mapping[str, Enzyme]
    foods: Mapping[str, Food]
    substrates: Mapping[str, Substrate]
    gi_regions: tuple[GIRegion, ...] = ()
    #: Most recent trial batch pH for this formulation, if any (spec §6.7).
    latest_trial_ph: Tracked | None = None

    def selected_enzymes(self) -> tuple[SelectedEnzyme, ...]:
        return self.formulation.enzymes

    def enzyme_for(self, selected: SelectedEnzyme) -> Enzyme:
        return self.enzymes[selected.enzyme_id]
