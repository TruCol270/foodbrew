"""Wire models. Every tracked field is an object, never a bare number (§1.3.2)."""

from __future__ import annotations

from typing import Any

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
                and name not in {"aliases", "deadline", "degrades_structural"}
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
    notes: str
    ph: TrackedOut
    water_content_pct: TrackedOut
    typical_load_value: TrackedOut

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


class EvaluationSummaryOut(BaseModel):
    id: str
    formulation_id: str
    created_at: str
    headline: str
    engine_version: str


class ErrorOut(BaseModel):
    detail: str
