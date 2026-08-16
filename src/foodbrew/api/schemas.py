"""Wire models. Every tracked field is an object, never a bare number (§1.3.2)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from foodbrew.engine import views
from foodbrew.engine.types import Enzyme, Food, GIRegion, Substrate, Tracked


class TrackedOut(BaseModel):
    value: Any = None
    status: str
    source: str = ""

    @classmethod
    def of(cls, tracked: Tracked) -> TrackedOut:
        return cls(value=tracked.value, status=str(tracked.status), source=tracked.source)


class SubstrateOut(BaseModel):
    id: str
    name: str
    native_human_enzyme: bool
    is_prebiotic: bool
    no_commercial_enzyme: bool
    notes: str

    @classmethod
    def of(cls, s: Substrate) -> SubstrateOut:
        return cls(**{f: getattr(s, f) for f in cls.model_fields})


class GIRegionOut(BaseModel):
    id: str
    name: str
    ph_low: float
    ph_high: float
    order: int
    dormant: bool
    transit_note: str

    @classmethod
    def of(cls, r: GIRegion) -> GIRegionOut:
        return cls(**{f: getattr(r, f) for f in cls.model_fields})


class EnzymeOut(BaseModel):
    id: str
    name: str
    aliases: list[str]
    substrate_id: str
    source_type: str
    priority: str
    deadline: str
    site_of_action: str
    dose_unit: str
    dose_benchmark_note: str
    is_protease: bool
    is_natural_source: bool
    food_grade_note: str
    heat_labile_note: str
    cost_tier: str
    supplier_note: str
    notes: str
    degrades_structural: list[dict[str, str]]
    ph_min: TrackedOut
    ph_max: TrackedOut
    ph_opt_low: TrackedOut
    ph_opt_high: TrackedOut
    ph_shelf_stable_min: TrackedOut
    temp_min_c: TrackedOut
    temp_max_c: TrackedOut
    temp_opt_c: TrackedOut
    dose_min: TrackedOut
    dose_max: TrackedOut
    dose_evidence_threshold: TrackedOut
    is_gras: TrackedOut
    #: ISO-8601 of the newest founder edit, or None if this record is untouched.
    last_edited: str | None = None

    @classmethod
    def of(cls, e: Enzyme) -> EnzymeOut:
        tracked_fields = {
            name: TrackedOut.of(getattr(e, name))
            for name, field in cls.model_fields.items()
            if field.annotation is TrackedOut
        }
        return cls(
            aliases=list(e.aliases),
            deadline=str(e.deadline),
            degrades_structural=[
                {"structural_class": str(x.structural_class), "tier": str(x.tier)}
                for x in e.degrades_structural
            ],
            **{
                name: getattr(e, name)
                for name in cls.model_fields
                if name not in tracked_fields
                and name not in {"aliases", "deadline", "degrades_structural", "last_edited"}
            },
            **tracked_fields,
        )


class FoodOut(BaseModel):
    id: str
    name: str
    category: str
    is_recipe_ingredient: bool
    is_trigger_food: bool
    is_application_food: bool
    contains_substrate_ids: list[str]
    typical_load_unit: str
    contains_protease: bool
    is_heat_processed: bool
    structural: list[str]
    allergens: list[str]
    notes: str
    ph: TrackedOut
    water_content_pct: TrackedOut
    typical_load_value: TrackedOut
    #: ISO-8601 of the newest founder edit, or None if this record is untouched.
    last_edited: str | None = None

    @classmethod
    def of(cls, f: Food) -> FoodOut:
        return cls(
            id=f.id, name=f.name, category=f.category,
            is_recipe_ingredient=f.is_recipe_ingredient,
            is_trigger_food=f.is_trigger_food,
            is_application_food=f.is_application_food,
            contains_substrate_ids=list(f.contains_substrate_ids),
            typical_load_unit=f.typical_load_unit,
            contains_protease=f.contains_protease,
            is_heat_processed=f.is_heat_processed,
            structural=[str(s) for s in f.structural],
            allergens=list(f.allergens),
            notes=f.notes,
            ph=TrackedOut.of(f.ph),
            water_content_pct=TrackedOut.of(f.water_content_pct),
            typical_load_value=TrackedOut.of(f.typical_load_value),
        )


class CustomFoodIn(BaseModel):
    """No status field anywhere: the server labels these user_provided (§5.4)."""

    name: str = Field(min_length=1)
    category: str = ""
    is_recipe_ingredient: bool = False
    is_trigger_food: bool = False
    is_application_food: bool = False
    ph: float | None = None
    water_content_pct: float | None = Field(default=None, ge=0, le=100)
    typical_load_value: float | None = Field(default=None, ge=0)
    typical_load_unit: str = ""
    contains_substrate_ids: list[str] = Field(default_factory=list)
    structural: list[str] = Field(default_factory=list)
    allergens: list[str] = Field(default_factory=list)
    contains_protease: bool = False
    is_heat_processed: bool = False
    notes: str = ""


class IngredientIn(BaseModel):
    food_id: str
    amount_g: float = Field(ge=0)
    order: int = 0


class IngredientOut(IngredientIn):
    pass


class RecipeIn(BaseModel):
    name: str = Field(min_length=1)
    notes: str = ""
    ingredients: list[IngredientIn] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _name_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name cannot be blank")
        return value.strip()


class RecipeOut(BaseModel):
    id: str
    name: str
    notes: str
    created_at: str
    ingredients: list[IngredientOut]


class SubstrateRowOut(BaseModel):
    substrate_id: str
    substrate_name: str
    from_food_names: list[str]
    is_prebiotic: bool
    no_commercial_enzyme: bool

    @classmethod
    def of(cls, row: views.SubstrateRow) -> SubstrateRowOut:
        return cls(
            substrate_id=row.substrate_id, substrate_name=row.substrate_name,
            from_food_names=list(row.from_food_names),
            is_prebiotic=row.is_prebiotic, no_commercial_enzyme=row.no_commercial_enzyme,
        )


class SelectedEnzymeIn(BaseModel):
    enzyme_id: str
    dose: float | None = Field(default=None, ge=0)
    phase: str = "dry"
    encapsulated: bool = False
    source_choice: str = ""


class ProcessStepIn(BaseModel):
    order: int
    label: str = ""
    is_heat: bool = False


class FormulationIn(BaseModel):
    recipe_id: str
    format: str
    target_trigger_food_ids: list[str] = Field(default_factory=list)
    application_food_ids: list[str] = Field(default_factory=list)
    dwell_profile: str | None = None
    enzymes: list[SelectedEnzymeIn] = Field(default_factory=list)
    serving_size_g: float | None = Field(default=None, ge=0)
    measured_ph: float | None = Field(default=None, ge=0, le=14)
    process_steps: list[ProcessStepIn] = Field(default_factory=list)
    enzyme_addition_index: int | None = None
    parent_formulation_id: str | None = None


class FormulationOut(BaseModel):
    id: str
    recipe_id: str
    format: str
    target_trigger_food_ids: list[str]
    application_food_ids: list[str]
    dwell_profile: str | None
    enzymes: list[SelectedEnzymeIn]
    serving_size_g: float | None
    measured_ph: TrackedOut
    process_steps: list[ProcessStepIn]
    enzyme_addition_index: int | None
    parent_formulation_id: str | None


class FindingOut(BaseModel):
    rule_id: str
    rule_title: str
    verdict: str
    advisory: bool
    message: str
    evidence: dict[str, Any]
    enzyme_id: str | None
    food_id: str | None


class RegionStateOut(BaseModel):
    region_id: str
    name: str
    ph_low: float
    ph_high: float
    order: int
    dormant: bool
    active: bool
    before_deadline: bool


class GiLaneOut(BaseModel):
    enzyme_id: str
    enzyme_name: str
    deadline: str
    ph_min: TrackedOut
    ph_max: TrackedOut
    regions: list[RegionStateOut]


class DoseCardOut(BaseModel):
    enzyme_id: str
    enzyme_name: str
    substrate_id: str
    dose: float | None
    dose_unit: str
    dose_min: TrackedOut
    dose_max: TrackedOut
    dose_evidence_threshold: TrackedOut
    substrate_load: TrackedOut
    meets_threshold: bool | None
    ratio: float | None
    above_benchmark_max: bool | None


class SuggestionOut(BaseModel):
    """Spec §7. Applying one is `POST /evaluations/{id}/apply-variant` with its id."""

    id: int
    suggestion_type: str
    description: str
    raised_by: list[str]
    #: False for a note — there is nothing to apply.
    is_applicable: bool


class ApplyVariantIn(BaseModel):
    """A stored suggestion id. There is deliberately no patch field: the server
    applies what it wrote, never what a client hands it (plan decision #2)."""

    suggestion_id: int


class FormatOptionOut(BaseModel):
    format: str
    title: str
    is_current: bool
    clears: bool
    reds: list[str]


class FormatRecommendationOut(BaseModel):
    current: str
    recommended: str | None
    options: list[FormatOptionOut]
    unfixable: list[str]
    message: str


class SnapshotChangeOut(BaseModel):
    kind: str
    record_id: str
    field: str
    before: Any = None
    after: Any = None


class ComparisonColumnOut(BaseModel):
    evaluation_id: str
    label: str
    headline: str


class ComparisonCellOut(BaseModel):
    text: str
    verdict: str | None
    present: bool


class ComparisonRowOut(BaseModel):
    section: str
    key: str
    label: str
    cells: list[ComparisonCellOut]
    changed: bool


class ComparisonOut(BaseModel):
    columns: list[ComparisonColumnOut]
    rows: list[ComparisonRowOut]


class RecordEditIn(BaseModel):
    """Workflow D. Field names are checked against `store/records.py`'s allowlist
    on the server; a name that is not on it is refused, which is what stops a
    client reaching a `_status` column through this door (plan decision #16)."""

    fields: dict[str, Any] = Field(default_factory=dict)


class StructuredEditIn(BaseModel):
    """A structured catalogue field. `value` is a list, checked server-side
    against the closed enums (plan decision #4); no truth label is accepted."""

    value: list[dict] | list[str]


class ProposalIn(BaseModel):
    table_name: str
    record_id: str
    field: str
    proposed_value: str
    source_citation: str = Field(min_length=1)


class ProposalOut(BaseModel):
    id: str
    table_name: str
    record_id: str
    field: str
    proposed_value: str | None
    source_citation: str
    status: str


class AuditEventOut(BaseModel):
    id: int
    actor: str
    action: str
    entity: str
    timestamp: str


class EvaluationOut(BaseModel):
    id: str
    formulation_id: str
    engine_version: str
    created_at: str
    headline: str
    overall: str
    findings: list[FindingOut]
    blockers: list[FindingOut]
    data_gaps: list[FindingOut]
    cautions: list[FindingOut]
    advisories: list[FindingOut]
    envelope: dict[str, str]
    gi_strip: list[GiLaneOut]
    dose_cards: list[DoseCardOut]
    suggestions: list[SuggestionOut]
    format_recommendation: FormatRecommendationOut
    #: True when a record this evaluation read has changed since it ran.
    stale: bool = False
    changes: list[SnapshotChangeOut] = Field(default_factory=list)
    #: Spec §6.3 — the Observed column, when a trial exists (plan decision #10).
    observed: ObservedEnvelopeOut | None = None
    trial_ids: list[str] = Field(default_factory=list)


class EvaluationSummaryOut(BaseModel):
    id: str
    formulation_id: str
    created_at: str
    headline: str
    engine_version: str


class ErrorOut(BaseModel):
    detail: str


class CheckpointOut(BaseModel):
    id: str
    kind: str
    prompt: str
    raised_by: list[str]
    due_elapsed_minutes: int | None
    application_food_id: str
    #: Empty when no observation fills this one (make-it, pH, symptom).
    observation_type: str


class ProtocolOut(BaseModel):
    engine_version: str
    checkpoints: list[CheckpointOut]
    notes: list[str]


class TrackedDoseOut(BaseModel):
    enzyme_id: str
    enzyme_name: str
    dose_unit: str
    dose_per_serving: float | None
    units_delivered: float | None
    threshold: TrackedOut
    meets_threshold: bool | None
    ratio: float | None
    blocking_field: str


class SymptomDoseOut(BaseModel):
    """Spec §5.3's computed_dose_json, and §10 screen 6's live preview."""

    trigger_food_id: str
    trigger_food_name: str
    amount_value: float | None
    amount_unit: str
    doses_used: float | None
    substrate_ids: list[str]
    enzymes: list[TrackedDoseOut]
    substrate_load: TrackedOut
    note: str


class ObservationIn(BaseModel):
    """No `dwell_bucket` and no tier: the server derives both (plan decision #2).
    No `symptom` in the Literal: symptoms have their own endpoint (decision #6)."""

    type: Literal["taste", "usability", "food_texture", "storage"]
    elapsed_minutes: int = Field(ge=0)
    score: int | None = Field(default=None, ge=1, le=5)
    free_text: str = ""
    was_blinded: bool = False
    had_undressed_control: bool = False
    application_food_id: str = ""


class ObservationOut(BaseModel):
    id: str
    type: str
    observed_at: str
    elapsed_minutes: int
    dwell_bucket: str
    score: int | None
    free_text: str
    was_blinded: bool
    had_undressed_control: bool
    application_food_id: str
    #: Spec §6.6 — derived, never stored, never sent by a client.
    confidence_tier: str
    export_class: str


class SymptomEntryIn(BaseModel):
    trigger_food_id: str
    amount_value: float | None = Field(default=None, ge=0)
    amount_unit: str = "servings"
    doses_used: float | None = Field(default=None, ge=0)
    outcome_score: int | None = Field(default=None, ge=1, le=5)
    notes: str = ""


class SymptomPreviewIn(BaseModel):
    trigger_food_id: str
    amount_value: float | None = Field(default=None, ge=0)
    amount_unit: str = "servings"
    doses_used: float | None = Field(default=None, ge=0)


class SymptomEntryOut(BaseModel):
    id: str
    eaten_at: str
    trigger_food_id: str
    amount_value: float | None
    amount_unit: str
    doses_used: float | None
    outcome_score: int | None
    notes: str
    computed_dose: SymptomDoseOut


class BatchIn(BaseModel):
    batch_size_g: float | None = Field(default=None, ge=0)
    measured_ph: float | None = Field(default=None, ge=0, le=14)
    ph_method: Literal["strip", "meter", "none"] = "none"
    make_minutes: int | None = Field(default=None, ge=0)
    difficulty_score: int | None = Field(default=None, ge=1, le=5)
    enzyme_source_note: str = ""
    enzyme_addition_step: int | None = None
    process_notes: str = ""
    storage_mode: Literal["refrigerated", "ambient"] = "refrigerated"


class BatchOut(BaseModel):
    id: str
    made_at: str
    batch_size_g: float | None
    measured_ph: float | None
    ph_method: str
    make_minutes: int | None
    difficulty_score: int | None
    enzyme_source_note: str
    enzyme_addition_step: int | None
    process_notes: str
    storage_mode: str
    observations: list[ObservationOut]
    symptom_entries: list[SymptomEntryOut]
    #: Scheduled checkpoints this batch has reached and not answered.
    due_checkpoint_ids: list[str]
    satisfied_checkpoint_ids: list[str]
    #: True when this batch's pH permits an ambient watch (§3 Workflow E).
    ambient_storage_allowed: bool


class TrialOut(BaseModel):
    id: str
    evaluation_id: str
    formulation_id: str
    status: str
    started_at: str | None
    notes: str
    protocol: ProtocolOut
    batches: list[BatchOut]


class TrialSummaryOut(BaseModel):
    id: str
    evaluation_id: str
    formulation_id: str
    status: str
    started_at: str | None
    batch_count: int
    observation_count: int
    due_checkpoint_count: int


class TrialStatusIn(BaseModel):
    """Only the two terminals — the rest of the machine runs itself (decision #12)."""

    status: Literal["complete", "abandoned"]


class ObservedProfileOut(BaseModel):
    verdict: str | None
    confidence_tier: str | None
    observation_count: int
    driving_observation_id: str


class ObservedEnvelopeOut(BaseModel):
    """Spec §6.3's second column. Computed on read; it changes no prediction."""

    trial_id: str | None
    profiles: dict[str, ObservedProfileOut]
    scale_note: str


class FormulaLineOut(BaseModel):
    position: int
    food_id: str
    food_name: str
    amount_g: float
    percent_of_total: float | None
    ph: TrackedOut
    water_content_pct: TrackedOut
    allergens: list[str]


class FormulaOut(BaseModel):
    lines: list[FormulaLineOut]
    total_g: float
    printed_percent_total: float | None


class ProcessLineOut(BaseModel):
    order: int
    label: str
    is_heat: bool
    is_enzyme_addition_point: bool


class AllergenEntryOut(BaseModel):
    allergen: str
    text: str
    from_food_names: list[str]


class AllergenDeclarationOut(BaseModel):
    entries: list[AllergenEntryOut]
    unrecorded_food_names: list[str]


class BatchRecordOut(BaseModel):
    made_at: str
    batch_size_g: float | None
    measured_ph: float | None
    ph_method: str
    make_minutes: int | None
    difficulty_score: int | None
    enzyme_source_note: str
    enzyme_addition_step: int | None
    storage_mode: str
    process_notes: str


class ReportOut(BaseModel):
    """Spec §10 screen 8 as structured data — the printable screen renders this,
    and `GET /export/{id}.md` renders the same assembly (plan decision #8)."""

    evaluation_id: str
    recipe_id: str
    recipe_name: str
    created_at: str
    engine_version: str
    headline: str
    stale: bool
    formula: FormulaOut
    process: list[ProcessLineOut]
    allergens: AllergenDeclarationOut
    batches: list[BatchRecordOut]
    serving_size_g: float | None
    measured_ph: TrackedOut
    dwell_profile: str | None
    format: str
    trigger_food_names: list[str]
    application_food_names: list[str]
