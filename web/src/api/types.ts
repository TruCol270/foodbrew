export type TruthLabel =
  | 'confirmed' | 'unconfirmed' | 'user_provided' | 'calculated' | 'observed'

export type Verdict = 'pass' | 'amber' | 'cannot_assess' | 'red'
export type Headline = 'GREEN' | 'AMBER' | 'GRAY' | 'RED'
export type DwellProfile = 'immediate' | 'packed' | 'marinade'
export type Format = 'premixed_wet' | 'dry_sachet' | 'dual_chamber' | 'encapsulated_in_wet'

/** Spec §5.4 — a value never travels without its label. */
export interface Tracked<T = number | boolean | null> {
  value: T
  status: TruthLabel
  source: string
}

export interface Substrate {
  id: string
  name: string
  native_human_enzyme: boolean
  is_prebiotic: boolean
  no_commercial_enzyme: boolean
  notes: string
}

export interface Enzyme {
  id: string
  name: string
  aliases: string[]
  substrate_id: string
  source_type: string
  priority: string
  deadline: string
  site_of_action: string
  dose_unit: string
  dose_benchmark_note: string
  is_protease: boolean
  is_natural_source: boolean
  food_grade_note: string
  heat_labile_note: string
  cost_tier: string
  supplier_note: string
  notes: string
  degrades_structural: { structural_class: string; tier: string }[]
  ph_min: Tracked
  ph_max: Tracked
  ph_opt_low: Tracked
  ph_opt_high: Tracked
  ph_shelf_stable_min: Tracked
  temp_min_c: Tracked
  temp_max_c: Tracked
  temp_opt_c: Tracked
  dose_min: Tracked
  dose_max: Tracked
  dose_evidence_threshold: Tracked
  is_gras: Tracked
}

export interface Food {
  id: string
  name: string
  category: string
  is_recipe_ingredient: boolean
  is_trigger_food: boolean
  is_application_food: boolean
  contains_substrate_ids: string[]
  typical_load_unit: string
  contains_protease: boolean
  is_heat_processed: boolean
  structural: string[]
  notes: string
  ph: Tracked
  water_content_pct: Tracked
  typical_load_value: Tracked
}

export interface Ingredient { food_id: string; amount_g: number; order: number }

export interface Recipe {
  id: string
  name: string
  notes: string
  created_at: string
  ingredients: Ingredient[]
}

export interface SubstrateRow {
  substrate_id: string
  substrate_name: string
  from_food_names: string[]
  is_prebiotic: boolean
  no_commercial_enzyme: boolean
}

export interface SelectedEnzyme {
  enzyme_id: string
  dose: number | null
  phase: 'wet' | 'dry'
  encapsulated: boolean
  source_choice: string
}

export interface ProcessStep { order: number; label: string; is_heat: boolean }

export interface Formulation {
  id: string
  recipe_id: string
  format: Format
  target_trigger_food_ids: string[]
  application_food_ids: string[]
  dwell_profile: DwellProfile | null
  enzymes: SelectedEnzyme[]
  serving_size_g: number | null
  measured_ph: Tracked
  process_steps: ProcessStep[]
  enzyme_addition_index: number | null
  parent_formulation_id: string | null
}

export interface Finding {
  rule_id: string
  rule_title: string
  verdict: Verdict
  advisory: boolean
  message: string
  evidence: Record<string, unknown>
  enzyme_id: string | null
  food_id: string | null
}

export interface RegionState {
  region_id: string
  name: string
  ph_low: number
  ph_high: number
  order: number
  dormant: boolean
  active: boolean
  before_deadline: boolean
}

export interface GiLane {
  enzyme_id: string
  enzyme_name: string
  deadline: string
  ph_min: Tracked
  ph_max: Tracked
  regions: RegionState[]
}

export interface DoseCard {
  enzyme_id: string
  enzyme_name: string
  substrate_id: string
  dose: number | null
  dose_unit: string
  dose_min: Tracked
  dose_max: Tracked
  dose_evidence_threshold: Tracked
  substrate_load: Tracked
  meets_threshold: boolean | null
  ratio: number | null
  above_benchmark_max: boolean | null
}

export interface Evaluation {
  id: string
  formulation_id: string
  engine_version: string
  created_at: string
  headline: Headline
  overall: Verdict
  findings: Finding[]
  blockers: Finding[]
  data_gaps: Finding[]
  cautions: Finding[]
  advisories: Finding[]
  envelope: Record<DwellProfile, Verdict>
  gi_strip: GiLane[]
  dose_cards: DoseCard[]
}

export interface EvaluationSummary {
  id: string
  formulation_id: string
  created_at: string
  headline: Headline
  engine_version: string
}
