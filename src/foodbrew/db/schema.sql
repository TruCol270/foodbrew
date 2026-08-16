-- Spec §5. Tracked values are stored as three columns: <field>, <field>_status,
-- <field>_source, mirroring the Tracked dataclass.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS substrate (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    native_human_enzyme INTEGER NOT NULL DEFAULT 0,
    is_prebiotic INTEGER NOT NULL DEFAULT 0,
    no_commercial_enzyme INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS enzyme (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    aliases_json TEXT NOT NULL DEFAULT '[]',
    substrate_id TEXT NOT NULL REFERENCES substrate(id),
    source_type TEXT NOT NULL,
    priority TEXT NOT NULL,
    deadline TEXT NOT NULL,
    site_of_action TEXT NOT NULL DEFAULT '',
    ph_min REAL, ph_min_status TEXT NOT NULL, ph_min_source TEXT NOT NULL DEFAULT '',
    ph_max REAL, ph_max_status TEXT NOT NULL, ph_max_source TEXT NOT NULL DEFAULT '',
    ph_opt_low REAL, ph_opt_low_status TEXT NOT NULL, ph_opt_low_source TEXT NOT NULL DEFAULT '',
    ph_opt_high REAL, ph_opt_high_status TEXT NOT NULL, ph_opt_high_source TEXT NOT NULL DEFAULT '',
    ph_shelf_stable_min REAL, ph_shelf_stable_min_status TEXT NOT NULL,
        ph_shelf_stable_min_source TEXT NOT NULL DEFAULT '',
    temp_min_c REAL, temp_min_c_status TEXT NOT NULL, temp_min_c_source TEXT NOT NULL DEFAULT '',
    temp_max_c REAL, temp_max_c_status TEXT NOT NULL, temp_max_c_source TEXT NOT NULL DEFAULT '',
    temp_opt_c REAL, temp_opt_c_status TEXT NOT NULL, temp_opt_c_source TEXT NOT NULL DEFAULT '',
    dose_unit TEXT NOT NULL DEFAULT '',
    dose_min REAL, dose_min_status TEXT NOT NULL, dose_min_source TEXT NOT NULL DEFAULT '',
    dose_max REAL, dose_max_status TEXT NOT NULL, dose_max_source TEXT NOT NULL DEFAULT '',
    dose_evidence_threshold REAL, dose_evidence_threshold_status TEXT NOT NULL,
        dose_evidence_threshold_source TEXT NOT NULL DEFAULT '',
    dose_benchmark_note TEXT NOT NULL DEFAULT '',
    is_protease INTEGER NOT NULL DEFAULT 0,
    is_natural_source INTEGER NOT NULL DEFAULT 0,
    is_gras INTEGER, is_gras_status TEXT NOT NULL, is_gras_source TEXT NOT NULL DEFAULT '',
    food_grade_note TEXT NOT NULL DEFAULT '',
    heat_labile_note TEXT NOT NULL DEFAULT '',
    degrades_structural_json TEXT NOT NULL DEFAULT '[]',
    cost_tier TEXT NOT NULL DEFAULT '',
    supplier_note TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS food (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '',
    is_recipe_ingredient INTEGER NOT NULL DEFAULT 0,
    is_trigger_food INTEGER NOT NULL DEFAULT 0,
    is_application_food INTEGER NOT NULL DEFAULT 0,
    ph REAL, ph_status TEXT NOT NULL, ph_source TEXT NOT NULL DEFAULT '',
    water_content_pct REAL, water_content_pct_status TEXT NOT NULL,
        water_content_pct_source TEXT NOT NULL DEFAULT '',
    contains_substrate_ids_json TEXT NOT NULL DEFAULT '[]',
    typical_load_value REAL, typical_load_value_status TEXT NOT NULL,
        typical_load_value_source TEXT NOT NULL DEFAULT '',
    typical_load_unit TEXT NOT NULL DEFAULT '',
    contains_protease INTEGER NOT NULL DEFAULT 0,
    is_heat_processed INTEGER NOT NULL DEFAULT 0,
    structural_json TEXT NOT NULL DEFAULT '[]',
    allergens_json TEXT NOT NULL DEFAULT '[]',
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS gi_region (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    ph_low REAL NOT NULL,
    ph_high REAL NOT NULL,
    "order" INTEGER NOT NULL,
    dormant INTEGER NOT NULL DEFAULT 0,
    transit_note TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS recipe (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recipe_ingredient (
    recipe_id TEXT NOT NULL REFERENCES recipe(id) ON DELETE CASCADE,
    food_id TEXT NOT NULL REFERENCES food(id),
    amount_g REAL NOT NULL,
    "order" INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (recipe_id, food_id)
);

CREATE TABLE IF NOT EXISTS formulation (
    id TEXT PRIMARY KEY,
    recipe_id TEXT NOT NULL REFERENCES recipe(id),
    format TEXT NOT NULL,
    target_trigger_food_ids_json TEXT NOT NULL DEFAULT '[]',
    application_food_ids_json TEXT NOT NULL DEFAULT '[]',
    dwell_profile TEXT,
    enzyme_selection_json TEXT NOT NULL DEFAULT '[]',
    serving_size_g REAL,
    measured_ph REAL, measured_ph_status TEXT NOT NULL DEFAULT 'unconfirmed',
        measured_ph_source TEXT NOT NULL DEFAULT '',
    process_steps_json TEXT NOT NULL DEFAULT '[]',
    enzyme_addition_index INTEGER,
    parent_formulation_id TEXT REFERENCES formulation(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evaluation (
    id TEXT PRIMARY KEY,
    formulation_id TEXT NOT NULL REFERENCES formulation(id),
    engine_version TEXT NOT NULL,
    input_snapshot_json TEXT NOT NULL,
    overall_flag TEXT NOT NULL,
    occasion_envelope_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rule_finding (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluation_id TEXT NOT NULL REFERENCES evaluation(id) ON DELETE CASCADE,
    rule_id TEXT NOT NULL,
    enzyme_id TEXT,
    food_id TEXT,
    verdict TEXT NOT NULL,
    advisory INTEGER NOT NULL DEFAULT 0,
    message TEXT NOT NULL,
    evidence_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS variant_suggestion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluation_id TEXT NOT NULL REFERENCES evaluation(id) ON DELETE CASCADE,
    suggestion_type TEXT NOT NULL,
    description TEXT NOT NULL,
    patch_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS trial (
    id TEXT PRIMARY KEY,
    evaluation_id TEXT NOT NULL REFERENCES evaluation(id),
    protocol_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'planned',
    started_at TEXT,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS trial_batch (
    id TEXT PRIMARY KEY,
    trial_id TEXT NOT NULL REFERENCES trial(id) ON DELETE CASCADE,
    made_at TEXT NOT NULL,
    batch_size_g REAL,
    measured_ph REAL,
    ph_method TEXT NOT NULL DEFAULT 'none',
    make_minutes INTEGER,
    difficulty_score INTEGER,
    enzyme_source_note TEXT NOT NULL DEFAULT '',
    enzyme_addition_step INTEGER,
    process_notes TEXT NOT NULL DEFAULT '',
    storage_mode TEXT NOT NULL DEFAULT 'refrigerated',
    -- Spec Workflow E / 21 CFR 114: ambient needs a measured pH below 4.6.
    CHECK (storage_mode != 'ambient' OR (measured_ph IS NOT NULL AND measured_ph < 4.6))
);

CREATE TABLE IF NOT EXISTS trial_observation (
    id TEXT PRIMARY KEY,
    trial_batch_id TEXT NOT NULL REFERENCES trial_batch(id) ON DELETE CASCADE,
    observed_at TEXT NOT NULL,
    elapsed_minutes INTEGER NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('taste', 'usability', 'food_texture', 'storage')),
    dwell_bucket TEXT NOT NULL,
    score INTEGER,
    free_text TEXT NOT NULL DEFAULT '',
    was_blinded INTEGER NOT NULL DEFAULT 0,
    application_food_id TEXT REFERENCES food(id),
    had_undressed_control INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS trial_symptom_entry (
    id TEXT PRIMARY KEY,
    trial_batch_id TEXT NOT NULL REFERENCES trial_batch(id) ON DELETE CASCADE,
    eaten_at TEXT NOT NULL,
    trigger_food_id TEXT NOT NULL REFERENCES food(id),
    amount_value REAL,
    amount_unit TEXT NOT NULL DEFAULT '',
    doses_used REAL,
    computed_dose_json TEXT NOT NULL DEFAULT '{}',
    outcome_score INTEGER,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS proposal (
    id TEXT PRIMARY KEY,
    table_name TEXT NOT NULL,
    record_id TEXT NOT NULL,
    field TEXT NOT NULL,
    proposed_value TEXT,
    source_citation TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected'))
);

CREATE TABLE IF NOT EXISTS audit_event (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL DEFAULT 'founder',
    action TEXT NOT NULL,
    entity TEXT NOT NULL,
    before_json TEXT,
    after_json TEXT,
    timestamp TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rule_finding_eval ON rule_finding(evaluation_id);
CREATE INDEX IF NOT EXISTS idx_evaluation_formulation ON evaluation(formulation_id);
CREATE INDEX IF NOT EXISTS idx_trial_batch_trial ON trial_batch(trial_id);
