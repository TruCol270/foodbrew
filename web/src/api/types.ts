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
  last_edited: string | null
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
  allergens: string[]
  notes: string
  ph: Tracked
  water_content_pct: Tracked
  typical_load_value: Tracked
  last_edited: string | null
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

export interface Suggestion {
  id: number
  suggestion_type: string
  description: string
  raised_by: string[]
  is_applicable: boolean
}

export interface FormatOption {
  format: Format
  title: string
  is_current: boolean
  clears: boolean
  reds: string[]
}

export interface FormatRecommendation {
  current: Format
  recommended: Format | null
  options: FormatOption[]
  unfixable: string[]
  message: string
}

export interface SnapshotChange {
  kind: string
  record_id: string
  field: string
  before: unknown
  after: unknown
}

export interface ComparisonCell { text: string; verdict: Verdict | null; present: boolean }
export interface ComparisonColumn { evaluation_id: string; label: string; headline: Headline }
export interface ComparisonRow {
  section: string
  key: string
  label: string
  cells: ComparisonCell[]
  changed: boolean
}
export interface Comparison { columns: ComparisonColumn[]; rows: ComparisonRow[] }

export interface Proposal {
  id: string
  table_name: string
  record_id: string
  field: string
  proposed_value: string | null
  source_citation: string
  status: 'pending' | 'approved' | 'rejected'
}

export interface AuditEvent {
  id: number
  actor: string
  action: string
  entity: string
  timestamp: string
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
  suggestions: Suggestion[]
  format_recommendation: FormatRecommendation
  stale: boolean
  changes: SnapshotChange[]
  observed: ObservedEnvelope | null
  trial_ids: string[]
}

export interface EvaluationSummary {
  id: string
  formulation_id: string
  created_at: string
  headline: Headline
  engine_version: string
}

export type ObservationType = 'taste' | 'usability' | 'food_texture' | 'storage'
export type ConfidenceTier = 'anecdote' | 'suggestive'
export type ExportClass = 'finding' | 'observation' | 'hypothesis'
export type TrialStatus = 'planned' | 'running' | 'complete' | 'abandoned'
export type CheckpointKind =
  | 'make_it' | 'ph' | 'taste' | 'usability' | 'food_texture' | 'storage' | 'symptom'

export interface Checkpoint {
  id: string
  kind: CheckpointKind
  prompt: string
  raised_by: string[]
  /** null means per-use: logged when it happens, never overdue. */
  due_elapsed_minutes: number | null
  application_food_id: string
  observation_type: string
}

export interface Protocol {
  engine_version: string
  checkpoints: Checkpoint[]
  notes: string[]
}

export interface EnzymeDose {
  enzyme_id: string
  enzyme_name: string
  dose_unit: string
  dose_per_serving: number | null
  units_delivered: number | null
  threshold: Tracked
  meets_threshold: boolean | null
  ratio: number | null
  blocking_field: string
}

export interface SymptomDose {
  trigger_food_id: string
  trigger_food_name: string
  amount_value: number | null
  amount_unit: string
  doses_used: number | null
  substrate_ids: string[]
  enzymes: EnzymeDose[]
  substrate_load: Tracked
  note: string
}

export interface Observation {
  id: string
  type: ObservationType
  observed_at: string
  elapsed_minutes: number
  dwell_bucket: DwellProfile
  score: number | null
  free_text: string
  was_blinded: boolean
  had_undressed_control: boolean
  application_food_id: string
  confidence_tier: ConfidenceTier
  export_class: ExportClass
}

export interface SymptomEntry {
  id: string
  eaten_at: string
  trigger_food_id: string
  amount_value: number | null
  amount_unit: string
  doses_used: number | null
  outcome_score: number | null
  notes: string
  computed_dose: SymptomDose
}

export interface TrialBatch {
  id: string
  made_at: string
  batch_size_g: number | null
  measured_ph: number | null
  ph_method: 'strip' | 'meter' | 'none'
  make_minutes: number | null
  difficulty_score: number | null
  enzyme_source_note: string
  enzyme_addition_step: number | null
  process_notes: string
  storage_mode: 'refrigerated' | 'ambient'
  observations: Observation[]
  symptom_entries: SymptomEntry[]
  due_checkpoint_ids: string[]
  satisfied_checkpoint_ids: string[]
  ambient_storage_allowed: boolean
}

export interface Trial {
  id: string
  evaluation_id: string
  formulation_id: string
  status: TrialStatus
  started_at: string | null
  notes: string
  protocol: Protocol
  batches: TrialBatch[]
}

export interface TrialSummary {
  id: string
  evaluation_id: string
  formulation_id: string
  status: TrialStatus
  started_at: string | null
  batch_count: number
  observation_count: number
  due_checkpoint_count: number
}

export interface ObservedProfile {
  verdict: Verdict | null
  confidence_tier: ConfidenceTier | null
  observation_count: number
  driving_observation_id: string
}

export interface ObservedEnvelope {
  trial_id: string | null
  profiles: Record<DwellProfile, ObservedProfile>
  scale_note: string
}

export type Allergen =
  | 'milk' | 'egg' | 'fish' | 'crustacean_shellfish' | 'tree_nut'
  | 'peanut' | 'wheat' | 'soy' | 'sesame'

export interface FormulaLine {
  position: number
  food_id: string
  food_name: string
  amount_g: number
  percent_of_total: number | null
  ph: Tracked
  water_content_pct: Tracked
  allergens: string[]
}

export interface Formula {
  lines: FormulaLine[]
  total_g: number
  printed_percent_total: number | null
}

export interface ProcessLine {
  order: number
  label: string
  is_heat: boolean
  is_enzyme_addition_point: boolean
}

export interface AllergenEntry {
  allergen: Allergen
  text: string
  from_food_names: string[]
}

export interface AllergenDeclaration {
  entries: AllergenEntry[]
  unrecorded_food_names: string[]
}

export interface BatchRecord {
  made_at: string
  batch_size_g: number | null
  measured_ph: number | null
  ph_method: 'strip' | 'meter' | 'none'
  make_minutes: number | null
  difficulty_score: number | null
  enzyme_source_note: string
  enzyme_addition_step: number | null
  storage_mode: 'refrigerated' | 'ambient'
  process_notes: string
}

export interface Report {
  evaluation_id: string
  recipe_id: string
  recipe_name: string
  created_at: string
  engine_version: string
  headline: Headline
  stale: boolean
  formula: Formula
  process: ProcessLine[]
  allergens: AllergenDeclaration
  batches: BatchRecord[]
  serving_size_g: number | null
  measured_ph: Tracked
  dwell_profile: DwellProfile | null
  format: Format
  trigger_food_names: string[]
  application_food_names: string[]
}
