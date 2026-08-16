---
title: FoodBrew — Enzyme Formulation Rules Engine (MVP Design Spec)
version: 1.3
date_created: 2026-08-13
last_updated: 2026-08-13
status: Approved design, pending implementation plan
supersedes: food-formulation-mvp-spec-carl.md (generic tomato-sauce workbench — wrong product; see §1.2)
sources_of_truth:
  - "fwbackgroundmaterials/Formulation Knowledge Base - for the Recipe Generator.docx  ← PRIMARY"
  - "fwbackgroundmaterials/Enzyme Site of Action (08.07.2026).pptx"
  - "fwbackgroundmaterials/Food-Format Digestive Enzymes (08.03.2026).pdf"
  - "fwbackgroundmaterials/Digestive Enzyme Industry Overview - (06.23.2026).pdf"
  - "fwbackgroundmaterials/Condiment Industry Overview - (07.31.2026)vDIST.pdf"
  - "fwbackgroundmaterials/Functional Food and Beverage Industry Overview - (07.13.2026)vDIST.pdf"
  - "fwbackgroundmaterials/US20240206516A1 - Wyss Patent.pdf (scanned; text verified via Google Patents)"
---

# 1. What this is

## 1.1 The product being supported

The founder is building a food-based, multi-enzyme digestive blend embedded directly into a condiment — starting with salad dressing — so people can eat trigger foods (dairy, beans, garlic/onion, other FODMAP-heavy foods) without a separate Lactaid/Beano/FODZYME pill. Two-step product path:

1. A FODZYME-like shelf-stable **dry enzyme blend** that pairs with a sauce.
2. A ready-to-eat format, most likely a **dual-chamber bottle** (wet dressing in one chamber, dry enzyme powder in the other, combined at squeeze).

## 1.2 The tool

A **rules engine over an enzyme database and an ingredient database** — as specified in the founder's Formulation Knowledge Base — plus a **kitchen-trial loop** that lets her test a candidate at home before paying for professional formulation work.

Given a recipe and target trigger foods, the engine outputs: which enzymes, at what dose, with pH / temperature / stability / denaturation / co-formulation / taste flags, an assessment of what the dressing does to the food it is poured on, and a format + packaging recommendation.

Headline verdict is one of four states (§6.4): **RED** (blocker), **GRAY** (gaps block a verdict), **AMBER** (caution), **GREEN** (clear on the rules evaluated).

This spec supersedes the earlier ChatGPT-generated tomato-sauce formulation workbench spec. That spec assumed a thermal process (the founder's #1 rule is NO HEAT), modelled microbial growth instead of enzyme survival, and targeted bench food-scientists instead of the founder. Its engineering discipline is retained (truth labels, provenance, deterministic pure-function core, golden fixtures); its domain content is replaced.

## 1.3 What v1 must let the founder do (success criteria)

1. Enter a dressing recipe and target trigger foods through structured forms, with no training, and get a complete verdict in under 5 minutes.
2. Every flag traces to a named rule, and every number traces to a database record with a status label. No orphan numbers.
3. The tool never claims safety, efficacy, or regulatory compliance — it flags formulation risks and knowledge gaps.
4. When data is missing, the affected rule reports **cannot_assess** naming the missing datum, never a silent pass.
5. A target trigger food with no enzyme covering it is reported as a blocker, or as an explicit gap where no commercial enzyme exists (polyols) — never as a silent pass (R14).
6. Side-by-side comparison of 2+ recipe/format variants shows exactly which flags changed and why.
7. The founder can correct or fill in any enzyme/ingredient value herself; her edits are marked `user_provided` and never overwrite the seeded baseline.
8. She can run an at-home trial of any formulation, generated from that formulation's own open risks, and record what actually happened.
9. Trial results are stored as `observed` and displayed beside the prediction they test. A prediction never overwrites an observation, and an observation never silently becomes a claim (§6.6).
10. The report she hands a food scientist separates what she measured from what she assumed, and states which questions she could not answer at home.

# 2. Scope

## 2.1 v1 IN

- **Recipe check:** recipe + trigger foods + intended format → enzyme selection, dose guidance, per-rule flags, format recommendation.
- **What-if comparison:** clone a formulation, tweak anything, see side-by-side flag/dose diff.
- **Auto-generated variants:** rules-driven fix suggestions, each re-run through the engine so its own flags are shown honestly.
- **Applied-food texture assessment (R15)** with the occasion envelope (§6.3).
- **Kitchen trial (Workflow E):** protocol generated from the formulation's own findings; solo, unblinded capture; results flow back as `observed`.
- **Seeded databases** from the founder's documents, with `unconfirmed` gaps visible and editable.
- **Single user, local Docker deployment.** No auth on localhost. Same container deploys to Fly.io later unchanged.
- **Print-friendly report view** (browser print → PDF) covering predicted and observed, for advisors and suppliers.

## 2.2 v1 OUT (deferred; build cost estimated in §11)

- Cost modeling (per-recipe COGS from enzyme cost tiers)
- Numeric optimization / solver
- LLM layer (natural-language recipe input, chat, generated explanations)
- Multi-user accounts, hosted auth
- Multi-subject or blinded trial infrastructure (taster panels, blind-key management, per-taster scoring). Single-subject only in v1; see §6.6 for how opportunistic blinding is still captured.
- **Consumer-facing timing guidance** (KB §4h: "add immediately or 5–10 minutes before eating"). The engine computes the enzyme's GI deadline in R2 and a texture-driven usage window in R15, but turning those into label instructions is a labeling decision deferred to v1.1.
- Any microbial/safety modeling, regulatory claim generation, shelf-life prediction

## 2.3 Parallel track (not a build dependency)

A research pass proposes literature/supplier-spec values for every `unconfirmed` cell (inulinase dose, fructan hydrolase pH, acid-stable lactase variants, xylose isomerase activity at 37 °C, lipase dose, ingredient pH values, structural-degradation behavior of inulinase). Each proposal carries a source and enters the database only when the founder approves it (status flips `unconfirmed` → `confirmed`, provenance recorded). See the `proposal` table in §5.

# 3. User & workflows

**Primary user:** the founder. Non-technical. Runs the tool independently.

## Workflow A — Check a recipe
1. Build recipe: pick foods from the catalog (or add custom), enter amounts per batch and per serving.
2. Pick target trigger foods (or accept the ones implied by the recipe's own substrates).
3. Optionally pick the foods the dressing will be poured on (drives R15; defaults to a standard mixed-salad set).
4. Pick intended format: `premixed_wet` / `dry_sachet` / `dual_chamber` / `encapsulated_in_wet`.
5. Tool proposes the enzyme set from the substrate map; founder can add/remove/re-source enzymes. Removing coverage does not remove the finding — R14 reports the uncovered substrate.
6. Run → verdict screen: headline RED/GRAY/AMBER/GREEN, per-rule findings, per-enzyme dose guidance, occasion envelope, format recommendation, open data gaps.

## Workflow B — Compare variants
Clone any formulation, change anything, run both. Comparison table: one column per variant, one row per rule + dose + format call + occasion envelope, changed cells highlighted.

## Workflow C — Apply suggested fixes
Verdict screen lists auto-variants (§7). One click materializes a suggestion as a new cloned formulation with the change applied, re-runs the engine, and drops the founder into the Workflow B comparison.

## Workflow D — Maintain the database
Enzyme, ingredient, and food editors. Every field shows value, unit, status, source note, last-edited. Founder edits create `user_provided` values; "reset to baseline" restores the seed. Research-track proposals appear here for approve/reject. Editing a record never alters past evaluations (they are snapshotted, §4); affected evaluations display a "data changed since this evaluation — re-run to refresh" banner.

## Workflow E — Kitchen trial

Sits between Verdict and Report. The engine already knows what it is uncertain about — the `unconfirmed` fields and the non-pass findings — so the protocol is generated from them rather than presented as a blank form.

1. **Generate protocol** from an evaluation. Each open risk produces a specific thing to watch (§6.5).
2. **Log a batch:** date, batch size, make-time in minutes, difficulty score, process notes, where in the sequence the enzyme went, and an optional measured pH.
3. **Observe on schedule:** the protocol schedules checkpoints; she records taste, usability, applied-food texture, storage, and symptom observations as they occur.
4. **Results attach to the evaluation.** The verdict screen gains an Observed column beside each prediction it tests.
5. **Export** a report carrying both, with the honesty split of §6.6.

A trial can be **abandoned** at any point (`status = 'abandoned'`). Abandoning keeps every observation already recorded — they were real — but the trial stops appearing as active on the Home screen, its unmet checkpoints stop being due, and the report labels it "trial abandoned after N observations" rather than presenting partial data as a completed run.

**Enzyme sourcing for home trials.** The protocol recommends opening capsules of an existing consumer product (Lactaid, Beano) rather than sourcing bulk powder: already food-grade per KB §4l, and already labeled in FCC/GalU, which makes her dose arithmetic exact rather than estimated. Bulk technical-grade enzyme is explicitly not recommended for anything she intends to eat.

**Storage-watch gate.** An ambient (room-temperature) storage watch is offered only when a measured pH below 4.6 has been entered for that batch — the acidified-foods line in 21 CFR 114, the regulation already cited in her condiment materials. Above 4.6, or with no measured pH, the protocol offers refrigerated short-window observation only and states why. The tool does not walk a user through ambient shelf-stability testing of a low-acid product.

# 4. Architecture

```
docker compose up  →  one container
┌─────────────────────────────────────────────┐
│ FastAPI (uvicorn :8000)                     │
│  ├── serves React build (static)            │
│  ├── /api/v1/* JSON endpoints               │
│  ├── engine/          ← pure Python, no I/O │
│  │    ├── rules.py    (R1–R15)              │
│  │    ├── dosing.py                         │
│  │    ├── gi_model.py                       │
│  │    ├── texture.py  (R15 occasion envelope)│
│  │    ├── protocol.py (trial generation)    │
│  │    ├── variants.py (auto-suggestions)    │
│  │    └── flags.py    (aggregation)         │
│  └── SQLite /data/foodbrew.db               │
│      (bind mount ./data → /data)            │
└─────────────────────────────────────────────┘
Frontend: React + TypeScript + Vite, form-driven
```

**Dependency rule:** `engine/` contains pure functions operating on plain dataclasses/dicts. No SQLAlchemy, no HTTP, no file I/O inside the engine. `protocol.py` generates a trial protocol from an evaluation's findings and is likewise pure — it returns a protocol structure, it does not persist one. The API layer hydrates inputs from SQLite, calls the engine, persists results.

**Seed data:** versioned JSON in-repo (`seed/enzymes.json`, `seed/ingredients.json`, `seed/foods.json`, `seed/substrates.json`, `seed/gi_model.json`). Loaded on first boot only — a later boot opens the existing database unchanged, verifies its tables, and applies any additive column migration it is missing. Founder edits go to SQLite only and are never overwritten by a restart; re-seeding happens exclusively through the reset-to-baseline action (Workflow D). Every read after boot goes through SQLite, never back to `seed/*.json`.

**Versioning for reproducibility:** every evaluation stores `engine_version`, a snapshot of all inputs, and the rule outcomes. Re-running an old snapshot on the same engine version must reproduce byte-identical results. Later edits to source records never mutate a stored evaluation, and **trial observations never mutate an evaluation's predictions** — they are stored alongside and displayed beside them.

# 5. Data model (SQLite)

## 5.1 Reference data

| Table | Key fields |
|---|---|
| `enzyme` | id, name, aliases, substrate_id, source_type (fungal/yeast/microbial/plant), **ph_min, ph_max** (activity range), **ph_shelf_stable_min** (sustained-exposure floor — R1), ph_opt_low, ph_opt_high, temp_min_c, temp_max_c, temp_opt_c, site_of_action, deadline (`before_small_intestine`/`before_colon`/`small_intestine`), dose_unit, dose_min, dose_max, dose_evidence_threshold, dose_benchmark_note, is_protease, **degrades_structural_json** (list of structural classes — R15), is_gras, food_grade_note, is_natural_source (KB §4j), heat_labile_note, priority, cost_tier, supplier_note — **every numeric field paired with** `*_status` **and** `*_source` |
| `substrate` | id, name (lactose, GOS, inulin_fructan, graminan_fructan, excess_fructose, polyol, protein, fat, sucrose, starch, fiber, pectin), native_human_enzyme, is_prebiotic (drives R9), no_commercial_enzyme (e.g. polyols), notes |
| `food` | id, name, category, **role flags:** is_recipe_ingredient, is_trigger_food, is_application_food; ph, ph_status, ph_source; water_content_pct; contains_substrate_ids; typical_load_value, typical_load_unit, load_status; contains_protease; is_heat_processed; **structural_json** (which of `pectin_cellulose` / `structural_protein` / `starch` the food's texture depends on — R15); **`allergens_json`** (list over a closed nine-value vocabulary: milk, egg, fish, crustacean shellfish, tree nut, peanut, wheat, soy, sesame). Catalogue reference data, carried into the evaluation snapshot and printed as a declaration on the report. **No rule reads it** — an allergen never changes a verdict. An empty list means *not recorded*, never *contains none*.; status/source fields |

**Schema note:** the earlier draft had separate `ingredient` and `trigger_food` tables. They are merged into one `food` table with role flags, because records genuinely serve multiple roles — black beans are a recipe ingredient, a GOS trigger food, and an application food. Duplicate records would have drifted.

## 5.2 Formulation and evaluation

| Table | Key fields |
|---|---|
| `recipe` | id, name, notes, created_at |
| `recipe_ingredient` | recipe_id, food_id, amount_g, order |
| `formulation` | id, recipe_id, format, target_trigger_food_ids, **application_food_ids**, **dwell_profile** (`immediate`/`packed`/`marinade`, **nullable — null means undeclared, see R15**), enzyme_selection_json (enzyme_id, source choice, dose, encapsulated, phase `wet`/`dry`), serving_size_g, measured_ph, measured_ph_status, measured_ph_source, **process_steps_json** (ordered list of `{order:int, label:str, is_heat:bool}`), **enzyme_addition_index** (integer `order` value after which the enzyme is added; R3 flags any step with `is_heat` true whose `order` >= this value), parent_formulation_id, created_at |
| `gi_region` | id, name, ph_low, ph_high, transit_note, order |
| `evaluation` | id, formulation_id, engine_version, input_snapshot_json, overall_flag, occasion_envelope_json, created_at |
| `rule_finding` | evaluation_id, rule_id (R1–R15), enzyme_id (nullable), food_id (nullable), verdict, message, evidence_json |
| `variant_suggestion` | evaluation_id, suggestion_type, description, patch_json, created_at |
| `proposal` | id, table_name, record_id, field, proposed_value, source_citation, status (`pending`/`approved`/`rejected`) |
| `audit_event` | actor, action, entity, before_json, after_json, timestamp |

## 5.3 Kitchen trial

| Table | Key fields |
|---|---|
| `trial` | id, evaluation_id, protocol_json (generated, frozen at creation), status (`planned`/`running`/`complete`/`abandoned`), started_at, notes |
| `trial_batch` | id, trial_id, made_at, batch_size_g, **measured_ph, ph_method** (`strip`/`meter`/`none`), make_minutes, difficulty_score (1–5), enzyme_source_note, **enzyme_addition_step** (integer index into the batch's process sequence — the datum R3 cares about, captured separately from free-text notes), process_notes, storage_mode (`refrigerated`/`ambient` — ambient permitted only when measured_ph < 4.6) |
| `trial_observation` | id, trial_batch_id, observed_at, **elapsed_minutes**, type (`taste`/`usability`/`food_texture`/`storage`), **dwell_bucket** (derived: `immediate`/`packed`/`marinade`), score, free_text, **was_blinded** (default false), application_food_id (nullable), had_undressed_control (default false) |
| `trial_symptom_entry` | *(the sole route for symptom capture — `trial_observation` deliberately has no `symptom` type, so per-meal dose linkage is never bypassed)* id, trial_batch_id, eaten_at, trigger_food_id, amount_value, amount_unit, doses_used, **computed_dose_json** (engine-calculated units delivered vs `dose_evidence_threshold`), outcome_score, notes |

## 5.4 Truth labels

Every displayed value carries exactly one of five labels. This enum is closed; no other token appears in seeds, API, or UI.

- `confirmed` — verified against a named source, recorded in the paired `*_source` field. Only an approved research-track proposal (§2.3) may write `confirmed`, using the proposal's `source_citation` as the `*_source` value. A direct founder edit in the database editor always writes `user_provided` with source "entered by founder", however well-sourced the value is in her head — the form is not a named source. Structured fields (§6.3.1's `degrades_structural_json`, and `structural_json`) carry no `*_status` pair at all: their provenance is the tier inside the value, so an approved proposal writes the value and the citation is kept in the proposal row and the audit trail.
- `unconfirmed` — seeded from a "confirm" cell, inferred, or proposed but not yet approved. Any rule depending on it returns `cannot_assess`.
- `user_provided` — founder override or founder-entered custom record.
- `calculated` — engine output, carrying its rule/formula reference.
- **`observed`** — entered from a real trial. Never overwritten by a prediction, and never displayed without its confidence tier (§6.6).

# 6. The rules engine

Each rule is a pure function: `(formulation_inputs) → RuleFinding(verdict, message, evidence)`. Verdicts: `pass`, `amber`, `red`, `cannot_assess`. A rule that needs an `unconfirmed` value returns `cannot_assess` naming the missing datum — never a silent pass, never a guess.

## 6.1 KB §4 → rule mapping (traceability to the founder's document)

Every KB §4 letter a–m maps to at least one rule.

| Rule | KB § | Logic |
|---|---|---|
| **R1 In-jar pH survival** | 4a | Applies where the enzyme contacts liquid on the shelf (`premixed_wet`; `encapsulated_in_wet` at reduced severity via R6). Recipe pH = `formulation.measured_ph` when entered, else worst-case = lowest pH among wet ingredients sharing the enzyme's phase, per the wet-ingredient rule in §6.7 (§12 item 1). Compare against **`ph_shelf_stable_min`** — the floor for sustained shelf-duration exposure, distinct from and higher than the activity floor `ph_min`. Recipe pH < `ph_shelf_stable_min` → **RED**; within range but outside `ph_opt` → **AMBER** (sluggish, recoverable — survival ≠ activity; denaturation is permanent); at/above optimum → pass. When `ph_shelf_stable_min` is `unconfirmed` (the common case), the engine applies a **stated fallback margin `ph_min + 1.0`**, returns **RED** if breached, and labels the finding "margin heuristic — supplier confirmation required." Worked case: vinaigrette pH ~3.0, fungal lactase `ph_min` 2.5 → fallback floor 3.5 → RED, matching KB §4m. Dry-phase enzymes skip R1. |
| **R2 GI window vs deadline** | 4a, 4h | Using the GI model (§8), report each enzyme's active pH window per tract region against its deadline. Substrates with no native human enzyme (GOS, fructans, excess fructose) are hard deadlines — residue reaching the colon ferments; there is no catching up. Mouth is dormant for all enzymes regardless of pH fit (dwell is seconds). No active region before the deadline → RED; partial coverage → AMBER. Not covered in v1: KB §4h's pre-hydrolysis-vs-survive design choice and consumer timing instructions (§2.2). **Per-field advisory exception:** a `cannot_assess` caused solely by the enzyme's own permanently-unconfirmed static catalogue field (`ph_min`/`ph_max`, unconfirmed for 6 of the 12 shipped enzymes) is **advisory** and does not gray the headline. Headline-capable against a catalogue that seeds unconfirmed would gray every formulation regardless of merit, which makes the tool useless and the §4m fixtures unreachable. |
| **R3 No heat** | 4b, 4j | Any process step flagged heat at-or-after the enzyme addition point → **RED**, naming the fix (add enzyme after heat, at the end). Heat strictly before → pass with note. Food-level `is_heat_processed` is informational: per KB §4j, cooking destroys naturally occurring enzymes (bromelain, papain, diastase), so a cooked pineapple or papaya no longer contributes protease — this suppresses the R5 conflict for that food and is reported as a note. |
| **R4 Water activation** | 4c | Dry = inert; wet = active and unstoppable. `dry_sachet` / `dual_chamber` (enzyme dry) → **pass**. `premixed_wet` → **AMBER** on its own: water switches the enzyme on, so activity decays and the enzyme digests jar contents over shelf life; magnitude is unknown without stability data, so R4 alone never REDs. Escalation to RED comes from R1 (pH kill), R5 (protease), or R6 via normal worst-of aggregation. This calibration reproduces KB §4m's three tiers: acidic vinaigrette REDs through R1, creamy premix lands AMBER through R4/R8, dry/separated is GREEN. **An R4 AMBER is never a green light to ship premixed** — the message states that KB §4c requires physical separation for shelf life and that shipping wet requires bench stability data. `encapsulated_in_wet` → AMBER, deferring to R6. |
| **R5 Protease co-formulation** | 4d | If any selected enzyme `is_protease` (bromelain, papain) **or** any recipe food has `contains_protease` and is not heat-processed, and it shares a wet active phase with other enzymes → the protease degrades them (enzymes are proteins) → **RED**. Separated (different chamber, dry, or individually encapsulated) → pass with note. |
| **R6 Encapsulation semantics** | 4f | Encapsulation is a timing control, not immunity: it delays exposure, it cannot rescue an enzyme from a condition that denatures on contact. `encapsulated_in_wet` where the capsule is the only barrier against an R1-breaching pH for shelf duration → **RED** (asks the capsule to do what KB §4f says it cannot). Under `dual_chamber` the bar drops — the capsule must survive minutes in dressing plus stomach transit, not months in acid — so R1 is re-evaluated at that exposure and R6 returns pass with note. |
| **R7 Dosing vs substrate load** | 4g | Dose driven by substrate load per serving, not food weight. Seeded benchmarks: lactase 900–18,000 FCC (Lactaid Fast Act 9,000 FCC per chewable tablet; suggested 3,000–6,000 FCC for a 0–6 g-lactose serving, 6,000–9,000 for 6–12 g, 9,000–15,000+ for 12 g+); alpha-galactosidase 450–800 GalU (Beano Extra Strength 800 GalU/serving). **Evidence threshold, separate from any product's dose (source: Digestive Enzyme Industry Overview p9, not the KB):** Monash/in-vitro evidence shows full-dose alpha-galactosidase at 300 GALU improved GOS symptoms while half-dose did not — an underdosed enzyme behaves like placebo. Dose below `dose_evidence_threshold` → **AMBER**. Unconfirmed benchmarks (inulinase, lipase, fructan hydrolase, xylose isomerase) → `cannot_assess`. Overdose → note: works, but an expensive way to solve it. Dose-decoupling warning for fixed-dose formats meeting variable meals; the squeeze format self-scales with **dressing used, not with trigger food eaten** — stated explicitly, never presented as full self-scaling. **Per-field advisory exception:** a `cannot_assess` caused solely by the enzyme's own permanently-unconfirmed static catalogue field (`dose_evidence_threshold`, unconfirmed for 11 of the 12 shipped enzymes) is **advisory** and does not gray the headline. Every other `cannot_assess` this rule can produce — a missing food load, a missing dose on the formulation — stays headline-capable, because those are gaps the founder can close. |
| **R8 In-jar taste/stability over time** | 4e | Active enzyme sharing a wet phase with its own substrate **present in the recipe** (e.g. lactase in a dairy-based creamy dressing; protease with dairy or egg protein) → flavor, texture, smell, and appearance drift over time (lactose hydrolysis → sweeter; product can turn "weird and smelly") → **AMBER** for wet-contact formats; note for dry/separated formats (drift begins at mixing, not before). Scope is the jar; the plate is R15. |
| **R9 Prebiotic tension** | 4i | Triggered when any enzyme targeting an `is_prebiotic` substrate is selected — **inulinase, fructan hydrolase, and alpha-galactosidase** (KB §4i names inulin, fructans, *and GOS*). Advisory only, never RED: these fibers feed the microbiome, so dose to a symptom threshold rather than to zero. Notes that garlic and onion carry more short-chain fructans than inulin. A product-philosophy call the founder owns; the rule keeps it visible. |
| **R10 Strain blending** | 4k | If a selected enzyme's active window covers only part of the useful GI range (e.g. fungal acid lactase, ceiling 5.4, drops out at the duodenum), suggest pairing a complementary source (acid fungal + neutral yeast lactase — the Enzymedica pattern) to widen the window. Surfaced as an auto-variant, never a failure. |
| **R11 Food-grade / GRAS** | 4l | Selected enzyme must be food-grade with GRAS status recorded. Lactase and alpha-galactosidase are largely already GRAS (a cost and time advantage). Missing or unknown → `cannot_assess` with the supplier question text. A standing banner notes that finished-product rules (food safety, acidified-food regulations) are outside this tool's scope. **Per-field advisory exception:** a `cannot_assess` caused solely by the enzyme's own permanently-unconfirmed static catalogue field (`is_gras`, unconfirmed for 10 of the 12 shipped enzymes) is **advisory** and does not gray the headline. Headline-capable against a catalogue that seeds unconfirmed would gray every formulation regardless of merit, which makes the tool useless and the §4m fixtures unreachable. |
| **R12 Temperature range** | 4b | Enzyme temperature range vs the ambient-shelf assumption (no cold chain — a stated product requirement) and body temperature 37 °C. All per-enzyme temperature values seed `unconfirmed` — the source documents give no per-enzyme temperature data — so **R12 returns `cannot_assess` for every seeded enzyme on day one**. It is therefore **advisory in v1** (§6.4): it reports the gap and drives supplier questions, but cannot set the headline. Were it red-capable against the shipped seed catalog, every formulation would be GRAY regardless of its actual merits, which would make the tool useless and the KB §4m fixtures unreachable. **Promotion condition:** once an enzyme's temperature fields are `confirmed`, R12 becomes red-capable *for that enzyme*, evaluated per-enzyme rather than globally. Xylose isomerase carries a seeded `unconfirmed` caution (an external assumption, not from the founder's documents) that its industrial optimum may sit well above body temperature, making 37 °C activity a supplier question. |
| **R13 Format flag (headline)** | 4m | Aggregation, not an independent test — see §6.4. The KB heuristic (wet acidic vinaigrette + standard acid lactase = RED; creamy, higher-pH but still wet = AMBER; dry, separated, or encapsulated = GREEN) is **not hardcoded**; it is a golden-fixture assertion (§13 a/b/c) that the composed rules must reproduce. R13 also computes the format recommendation: the least-invasive format change (premixed → encapsulated → dual-chamber → dry sachet) under which re-running R1–R7, R11, R12, R14, R15 yields no RED. The ladder is always scanned from the top — `premixed_wet` first — never from the formulation's current format, so a formulation already on `dry_sachet` that would also clear as `premixed_wet` is told so. When no position clears, the recommendation is none, with a note naming the rules no format change can fix (an R14 uncovered substrate, for instance). |

## 6.2 Engine-derived rules

| Rule | Derived from | Logic |
|---|---|---|
| **R14 Substrate coverage** | KB §5 outputs | For every selected target trigger food, its substrate must be targeted by at least one selected enzyme. Uncovered substrate → **RED** naming it ("no enzyme selected for lactose"). Substrate flagged `no_commercial_enzyme` (polyols) → `cannot_assess` stating no commercial enzyme exists — the tool never maps polyols to an enzyme. A formulation with target trigger foods and zero enzymes is therefore RED, never a bare pass. Zero enzymes **and** zero trigger foods → rejected at validation ("select at least one trigger food or enzyme"), not evaluated. |
| **R15 Applied-food texture** | KB §4e extended to the plate | For each selected enzyme × each `application_food`: intersect the enzyme's `degrades_structural_json` entries with the food's `structural_json` classes. Each intersecting pair yields a verdict per dwell profile from the explicit severity table in §6.3.1 — there is no free-form "proportional to contact time" judgement. Emits an **occasion envelope** (§6.3) rather than a single verdict. Mechanism is direct: cellulase and pectinase break plant cell walls and pectin (the chemistry of a vegetable going limp); protease/bromelain/papain is the meat-tenderizer mechanism and also thins dairy; amylase attacks starch (croutons, pasta, potato, grains). Lactase and alpha-galactosidase act on soluble sugars, not structure, and seed with an empty `degrades_structural_json` — this is why a narrow FODMAP blend is texture-safe where a broad-spectrum blend is not. Inulinase seeds **`unconfirmed`** on this axis: inulin is a storage carbohydrate but forms a meaningful share of chicory and artichoke tissue, so long-dwell softening is plausible and unverified — it returns `cannot_assess` for those foods rather than a guess in either direction. **Multiple intersections:** when one enzyme hits several structural classes, or several enzymes hit one food, the profile's verdict is the worst across all pairs; overlap never compounds severity beyond the worst single pair, because no source supports an additive model. |
| **R16 Clean label / natural sourcing** | KB §1 success criterion 5, via §4j and §4l | Advisory only, never RED — a founder philosophy call the rule keeps visible, in the same spirit as R9. Reports, per selected enzyme, whether it is `is_natural_source` (bromelain, papain, diastase) or microbial/fungal-fermented, so the clean-label story is explicit rather than assumed; notes that natural-source enzymes are heat-labile (§4j) and that food-grade sourcing costs more than technical grade (§4l). The second half of the KB criterion — "no gut-trigger additives" — returns **`cannot_assess`** in v1: excipient and carrier composition is supplier data the founder does not yet have, and no source document lists it. The rule names that gap rather than implying a clean bill. |

## 6.3 The occasion envelope (R15 output)

R15 does not take the use occasion as an input. It evaluates all three dwell profiles and returns which occasions the formulation can honestly support:

| Dwell profile | `elapsed_minutes` range | Trial checkpoints that fill it |
|---|---|---|
| `immediate` — dressed at the table | 0 – 59 | 0 min |
| `packed` — meal prep, dressed ahead | 60 – 479 | 1 hr, 4 hr |
| `marinade` — intentional, overnight | 480 and above | overnight |

The ranges are exhaustive, non-overlapping, and boundary-inclusive as written; `dwell_bucket` on a `trial_observation` is derived from `elapsed_minutes` by this table and by nothing else. Every checkpoint the protocol schedules falls in exactly one bucket.

The envelope carries a predicted verdict per profile and, once a trial exists, an observed one beside it. `formulation.dwell_profile` is **nullable and defaults to null**, meaning undeclared. If the founder later commits to a primary occasion, setting it makes aggregation red-cap on that occasion specifically.

### 6.3.1 Severity table

Each enzyme entry in `degrades_structural_json` is `{class, tier}` where tier is `rapid`, `gradual`, or `unconfirmed`. The tier maps to a profile verdict deterministically:

| Tier | `immediate` | `packed` | `marinade` |
|---|---|---|---|
| `rapid` | red | red | red |
| `gradual` | pass | amber | red |
| `unconfirmed` | cannot_assess | cannot_assess | cannot_assess |

**No shipped seed enzyme uses `rapid`.** Every structural degrader in §9.1 seeds `gradual` (protease, cellulase, pectinase, amylase) or `unconfirmed` (inulinase, fructan hydrolase), because the source documents support the existence of these mechanisms but give no rate data, and minutes-scale destruction is not something any source claims. The `rapid` tier exists so the mapping is total and so a future confirmed fast-acting case has somewhere to go; §13 fixture (m) exercises it with an explicitly synthetic record, not a shipped one.

**Observed texture scale (engineering convention, not a measurement).** The Observed column is filled from `trial_observation.score`, a 1–5 scale scored against an undressed control: 1 indistinguishable from the undressed portion, 2 slightly softer — would not notice without comparing, 3 clearly softer than the undressed portion, 4 limp, wilted, or watery, 5 badly broken down. Scores map to verdicts as 1–2 pass, 3 amber, 4–5 red. This mapping is a stated convention with the same standing as R1's fallback margin — it exists so the column is computable, it is labelled wherever it is shown, and it is not a scientific claim. Revisit it once the founder has scored real trials against it.

## 6.4 Aggregation

Severity order: `red` > `cannot_assess` > `amber` > `pass`.

Overall flag = worst verdict among **R1–R7, R11, R14**, plus R15 under the rule below. **R8, R9, R10, R12, and R16 are advisory and cannot set the overall flag.** R12's advisory status is conditional and per-enzyme: it becomes red-capable for any enzyme whose temperature fields are `confirmed` (§6.1 R12).

**R15's contribution to the headline:**
- `dwell_profile` declared and RED at that profile → contributes **RED**.
- All three profiles RED → contributes **RED**. No usable occasion exists, so the formulation is unusable however it is sold.
- Otherwise, any non-pass in the envelope → contributes **AMBER**, and the envelope panel shows which occasions fail.

This keeps a formulation that is perfectly good for table-dressing from being failed by a marinade scenario the founder may never support, while never hiding that the marinade case fails.

Headline display maps one-to-one: `red` → **RED** (blocker), `cannot_assess` → **GRAY** (gaps block a verdict), `amber` → **AMBER** (caution), `pass` → **GREEN** (clear on the rules evaluated). `cannot_assess` is never folded into pass or fail; a GRAY headline means the tool is declining to judge, and the verdict screen lists exactly which fields are missing.

## 6.5 Trial protocol generation

`protocol.py` maps an evaluation's findings and data gaps to things to watch. She never faces a blank form.

| Finding or gap | What the protocol asks her to do | Cadence |
|---|---|---|
| R8 AMBER (in-jar drift predicted) | Taste checkpoints at day 0 / 3 / 7 — sweeter? off smell? separated? | `scheduled` |
| R1 non-pass, or `measured_ph` empty | Enter a measured pH per batch (optional; unlocks the ambient storage watch when < 4.6) | `per_use` |
| R7 AMBER or `cannot_assess` | Log trigger food and amount per use, so the engine can report whether that meal cleared the evidence threshold | `per_use` |
| R4 AMBER (wet premix) | Storage watch on the schedule permitted by pH | `scheduled` |
| **R15 envelope non-pass** | **Applied-food texture checkpoints at 0 min / 1 hr / 4 hr / overnight against a portion left undressed** | `scheduled` |
| Any format | Make-it capture: total minutes, difficulty, what went wrong, where the enzyme went in the sequence | `per_use` |
| Every trial | Usability log entries per use — was a second squeeze needed, did it feel natural | `per_use` |

Per-use items are never overdue: they are listed under "log these as they happen" rather than on the due-checkpoint clock. Scheduled items are due when the elapsed time since the batch was made reaches their offset and no observation of that type, in that dwell bucket, for that food has been recorded.

**The texture control is free.** She does not need a second batch of dressing; she leaves part of the same food undressed in the same fridge. `trial_observation.had_undressed_control` records whether she did, and observations carrying it are labeled a tier stronger (§6.6). Isolating the *enzyme* specifically would need a no-enzyme dressing — cheap for a vinaigrette, optional, and out of the default protocol.

## 6.6 How observations are labeled

v1 trials are single-subject and unblinded by default. That is a deliberate scope decision, not an oversight, and the labeling reflects it honestly. Every observation is stored `observed`, and carries a confidence tier:

- `anecdote` — single subject, unblinded, no control. The default.
- `suggestive` — the observation carries `was_blinded = true` **or** `had_undressed_control = true`.

Nothing recorded at home is ever labeled demonstrated, proven, or validated.

`was_blinded` defaults false and is a per-observation flag, not a trial-level commitment. If someone happens to be in the kitchen and hands her the cup, she ticks it and that observation is labeled a tier stronger. Rigor is captured opportunistically rather than required up front.

**The report splits the four questions by how much her own judgment counts as evidence:**

- **Taste, ease of making, ease of use** — her subjective answer *is* the data. These are subjective questions by nature, and the founder's read on them is legitimate signal. Exported as **findings**.
- **Applied-food texture** — partly objective and cheaply controlled (the undressed portion). Exported as **findings** when a control was used, **observations** when not.
- **Symptom response** — unblinded self-report on a product she is invested in; the weakest measurement available. Exported as **hypotheses for the food scientist to design a real test around**, always with the computed dose math attached, so a null result can be attributed to underdosing rather than read as failure.

## 6.7 Shared engine conventions

These are referenced by several rules and defined once here so implementations cannot diverge.

**Wet ingredient (used by R1).** A recipe ingredient counts as wet when `food.water_content_pct >= 50`. R1's fallback recipe-pH estimate is the lowest `ph` among wet ingredients sharing the enzyme's phase. If `water_content_pct` is `unconfirmed` for any recipe ingredient, R1 returns `cannot_assess` naming it, exactly as it does for an unconfirmed pH. This is the field's only consumer in v1; a future buffering model (§11) would supersede it.

**Substrate load aggregation (used by R7).** When several target trigger foods share one substrate, their `typical_load_value` figures are **summed** for that substrate, and the selected enzyme's dose is compared against the summed load — a meal with beans *and* lentils presents more GOS than either alone. Loads are never max-ed or averaged. Substrates are evaluated independently of one another. If any contributing food's load is `unconfirmed`, the substrate's R7 finding is `cannot_assess` naming that food.

**Measured-pH resolution order (used by R1).** Evaluation input hydration resolves recipe pH as: (1) `formulation.measured_ph` when set, labeled by its own status; else (2) the `measured_ph` of the most recent `trial_batch` belonging to a trial on this formulation, when one exists, labeled `observed`; else (3) the wet-ingredient fallback above, labeled `calculated`. The founder never has to copy a number between screens, and the report always states which of the three was used.

**Empty and degenerate inputs.** A recipe with zero ingredients is rejected at validation ("add at least one ingredient") and is not evaluated. A formulation with zero enzymes and zero target trigger foods is likewise rejected (§6.2 R14). A formulation with target trigger foods but no enzymes evaluates normally and REDs through R14.

# 7. Auto-variant generation

`variants.py` maps failing findings to a fix catalog. Each suggestion carries a machine-applicable `patch_json`; applying it clones the formulation, applies the patch, and re-runs the engine. Suggestions are never presented as pre-cleared — their own flags are shown.

| Trigger finding | Suggested variant |
|---|---|
| R1 RED (pH below shelf-stable floor) | Switch to an acid-stable variant of the same enzyme (surfaced even when `unconfirmed`, labeled "candidate — confirm with supplier"); raise recipe pH by reducing or replacing the acid ingredient (shown as a recipe change; the founder judges taste); change format to dual-chamber or dry sachet — this middle suggestion is a note, not a machine-applicable patch. §12 item 1 says recipe pH is a worst-case minimum over wet ingredients, not a mixing model, so an engine that removed the vinegar and reported the result would be publishing the second-lowest ingredient pH as if it were a measurement. It names the ingredient currently setting the floor and asks her to measure what she makes. The other two entries in this row remain machine-applicable. |
| R3 RED (heat after enzyme) | Move the enzyme addition point to after the heat step |
| R4 AMBER / R6 RED (wet reliance) | Dual-chamber; dry sachet pairing; individual encapsulation (carries the R6 caveat) |
| R5 RED (protease conflict) | Separate the protease into the other chamber or its own encapsulation; drop the protease (KB: additive, not gap-filling — the body already covers protein digestion), noting bromelain's remaining value is clean-label and marketing |
| R7 AMBER (below evidence threshold) | Raise dose to the evidence threshold; reduce the declared trigger-food serving |
| R10 note | Add a complementary-source enzyme pairing to widen the active window |
| R11 / R12 `cannot_assess` | No formulation patch — emits a supplier question for the report's open-questions list |
| R14 RED (uncovered substrate) | Add the enzyme targeting the uncovered substrate, at its benchmark dose |
| **R15 envelope non-pass** | Two patches that actually change R15's inputs: **drop the structure-degrading enzyme from the blend** (narrows the blend, removing the intersection), and **restrict the supported occasion set** to the profiles the envelope passes (sets `dwell_profile`). Plus one **behavioural note, not a patch**: dress immediately before eating. Format changes are deliberately *not* offered here — dual-chamber governs when the *dressing* is mixed, not how long it sits on the *food*, so it does not move any R15 profile. |

# 8. GI model (seed values, from the Enzyme Site of Action deck)

| Region | pH | Note |
|---|---|---|
| Mouth | 6.2–7.6 | Dwell is seconds — all enzymes effectively dormant regardless of pH fit |
| Stomach, fasting | 1.5–2.0 | Only acid-tolerant enzymes active pre-meal |
| Stomach, fed | 4–6 | Food buffers upward, drifts back down over ~2 h — the main workhorse window |
| Duodenum | 6.0–6.5 | Fungal lactase (ceiling 5.4) has dropped out; inulinase fading |
| Jejunum/ileum | 7.0–7.5 | Xylose isomerase's prime window |
| Colon | 5.5–7.0 | Too late — undigested substrate ferments here (the symptom mechanism) |

Overall race window: ~2–4 h mouth-to-colon. Deadlines, not anatomical targets.

**Documented source inconsistency, resolved in the seed.** Lactase's site of action is described two ways across the founder's materials: KB Table B *and* Site-of-Action slide 1 both list "mouth → stomach," while slide 3 of the same deck shows the mouth dormant for every enzyme (dwell too brief to react) and lactase active in the fed stomach, dropping out at the duodenum above its 5.4 ceiling. The inconsistency spans both documents and exists **within the deck itself** (slide 1 vs slide 3). **The seed encodes slide 3's version**, with a source note recording the discrepancy for the founder to confirm.

# 9. Seed data summary

Full tables are generated into `seed/*.json` during implementation. Every value carries a status label; anything not stated in the founder's documents seeds `unconfirmed`, never as fact.

## 9.1 Enzymes

pH ranges seed `confirmed` (source: KB Table B / Site-of-Action slide 1). **All temperature fields and all `ph_shelf_stable_min` fields seed `unconfirmed`** — no source document provides them.

| Enzyme | pH (opt) | Dose | `degrades_structural` |
|---|---|---|---|
| Lactase — fungal (acid) | 2.5–5.4 (~5.0) | 900–18,000 FCC | *(none — lactose is soluble)* |
| Lactase — yeast (neutral) | stub, `unconfirmed` | — | *(none)* |
| Alpha-galactosidase (*A. niger*) | 3.0–8.0 (~5.0) | 450–800 GalU; threshold 300 GALU | *(none — GOS is soluble)* |
| Inulinase — fungal | 2.0–7.0 (~3.0–5.0) | `unconfirmed` | **`{pectin_cellulose, unconfirmed}`** — see R15 |
| Fructan hydrolase (FODZYME blend) | `unconfirmed` | `unconfirmed` | `unconfirmed` |
| Protease / bromelain | 4.0–8.0 (~7.0); bromelain ~4.5–7 | GDU, `unconfirmed` | **`{structural_protein, gradual}`** |
| Lipase — fungal | 2.0–9.0 (~7.0) | `unconfirmed` | *(none structural; flavour/rancidity risk noted separately)* |
| Xylose / glucose isomerase | 7.0–9.0 | `unconfirmed` | *(none)* |
| Amylase | stub | `unconfirmed` | **`{starch, gradual}`** |
| Cellulase | stub | `unconfirmed` | **`{pectin_cellulose, gradual}`** |
| Pectinase | stub | `unconfirmed` | **`{pectin_cellulose, gradual}`** |
| Invertase | stub | `unconfirmed` | *(none)* |

Notes recorded on the records: lactase — one commercial supplier spec (Sunson) lists a broader 3.0–8.0 activity range with optimum 3.5–5.0, treated as a looser "still shows some activity" claim, not a sustained-stability figure. Fructan hydrolase — **FTO flag:** the underlying patent appears third-party/licensed (US 10,820,599, per the Digestive Enzyme Industry Overview). Bromelain/papain — `is_natural_source`, heat-labile.

## 9.2 Substrate map (KB §3)

lactose → dairy (hard aged cheeses low-lactose); GOS → beans, lentils, chickpeas, cruciferous; inulin-type fructans → onion, garlic, chicory, artichoke; graminan-type fructans → wheat, barley, rye; excess fructose → apples, mango, honey; polyols → mushrooms, stone fruit, sugar-free gum (**`no_commercial_enzyme` = true**); protein → meat, eggs, dairy, legumes; fat → oils, butter, fatty meats.

`is_prebiotic` = true on GOS, inulin-type fructans, graminan-type fructans (drives R9).

## 9.3 Food catalog (~45 records, role-flagged)

**Recipe ingredients (~25):** oils (olive, canola), vinegars (balsamic, white, apple cider), lemon juice, honey, mustard, yogurt, buttermilk, mayonnaise, garlic (fresh and powder), onion, herbs, salt, sugar, water, fresh pineapple and papaya (`contains_protease` = true — the trap ingredients), modified starch.

**Application foods (~20), with structural composition for R15:**

| Structural class | Foods |
|---|---|
| `pectin_cellulose` | romaine, mixed greens, spinach, kale, cucumber, tomato, bell pepper, shredded carrot |
| `structural_protein` | cooked chicken breast, canned tuna, hard-boiled egg, tofu, feta, parmesan |
| `starch` | cooked pasta, cooked potato, quinoa, farro, croutons |
| *(none — no structural class the seeded enzymes act on)* | avocado, nuts and seeds |

Beans, chickpeas, and lentils carry all three roles — recipe ingredient, GOS trigger food, and application food — which is why §5.1 merges these into one `food` table.

**All pH values and all `water_content_pct` values seed `unconfirmed`.** The wet-ingredient threshold in §6.7 therefore returns `cannot_assess` until the founder fills them in — water content is the one field she can estimate confidently without equipment, so the database editor surfaces it first.

**On pH specifically:** The KB gives exactly one pH statement — that vinegar puts a dressing around pH 3 — and no ingredient-level figures. Seeded pH values are starting estimates flagged for the founder to measure or confirm; R1 returns `cannot_assess` on an unconfirmed-pH recipe unless she supplies `measured_ph`. This is the highest-value target for the §2.3 research track and for her first bench session.

# 10. API & UI

**API (`/api/v1`):** CRUD for recipes / formulations / enzymes / foods; `POST /formulations/{id}/evaluate`; `GET /evaluations/{id}`; `POST /evaluations/{id}/apply-variant`; `GET /compare?ids=…`; `POST /evaluations/{id}/trial` (generate protocol); `POST /trials/{id}/batches`; `POST /trial-batches/{id}/observations`; `POST /trial-batches/{id}/symptom-entries`; proposals inbox; `GET /export/{evaluation_id}.md`.

**Screens:**
1. **Home** — recipe list, recent evaluations, active trials.
2. **Recipe builder** — food picker with amounts; custom-food creation (all fields stored `user_provided`); live substrate summary ("this recipe itself contains: GOS (garlic)…"); optional measured-pH entry.
3. **Formulation setup** — format picker, trigger-food picker, application-food picker, proposed enzyme set (editable), serving size, process steps with heat flags and the enzyme-addition point.
4. **Verdict** — headline RED / GRAY / AMBER / GREEN; findings grouped (Blockers / Data gaps / Cautions / Advisory); per-enzyme dose card; GI-tract strip showing each enzyme's active window against its deadline (the deck's slide-3 visual, rendered live); **occasion envelope panel** with predicted and observed columns; variant suggestions with one-click apply; "data changed since this evaluation — re-run to refresh" banner when a referenced record was edited after the evaluation.
5. **Compare** — variants side-by-side, changed cells highlighted.
6. **Trial** — protocol checklist with due checkpoints; batch log (including pH and storage mode, with the 4.6 gate enforced in the UI, not just the API); quick-entry observation forms per type; symptom entry showing computed dose against threshold as she types.
7. **Database** — enzyme and food editors, proposals inbox, reset-to-baseline.
8. **Report** — print-friendly page and Markdown export, rendered from one assembly so the two cannot disagree. Carries: product and formula identity (product, recipe id, format, serving size, declared occasion, evaluation id, engine version); the **formula** as percent of total batch weight in order of addition, with grams beside each line and a total row; the **allergen declaration**, naming ingredients whose allergens are not recorded rather than implying they carry none; the **process** sequence with heat flags and the enzyme-addition point; **finished-product parameters**, listing water activity, viscosity and nutrition as not measured rather than omitting them; findings by group; dose, GI window and occasion envelope with observed columns; **batch records** for every trial batch, with the parameters captured as it was made; observed results under §6.6's three headings; open questions; provenance; and the fixed footer.

Language throughout: plain English, no jargon without a tooltip. Prohibited words in engine output and report: "safe," "validated," "guaranteed," "clinically proven," "proven," "demonstrated."

# 11. Deferred features — what each would take

| Feature | Build sketch | Effort |
|---|---|---|
| **Cost modeling** | `cost_per_unit` on enzyme and food records (from supplier quotes); per-serving and per-batch COGS roll-up; margin sketch against a target shelf price. The Condiment Industry Overview (p21) gives the benchmark: at a $12 shelf price the retailer and middlemen take ~60%, leaving ~$5 net revenue, so a 50% gross margin needs COGS near $2.50 — with early-stage margins realistically ~20%. Pure arithmetic; blocked on real quotes. | ~2–3 days once quotes exist |
| **Numeric solver** | SciPy bounded search over ingredient amounts and dose to satisfy hard constraints (recipe pH ≥ the chosen enzyme's shelf-stable floor, dose ≥ evidence threshold, format fixed) while minimizing soft objectives (acid reduction, cost, deviation from her target flavour profile). **The solver is the easy half.** The hard half is a real recipe-pH mixing model: pH is not the minimum of ingredient pH values but a buffered nonlinear function of acid concentration, dissociation constants, and the buffering capacity of the dairy or emulsion base — and that needs bench titration data on her actual ingredients before a solver's output is worth anything. The kitchen trial's `measured_ph` capture is the collection mechanism, which is a further argument for building it first. | ~1–2 weeks after titration data exists |
| **Consumer timing guidance** | Derive "add immediately" vs "5–10 min before eating" from each enzyme's deadline, GI window, and pre-hydrolysis intent (KB §4h), and reconcile with R15's texture-driven usage window — the two converge on the same label instruction for different reasons. Needs a per-enzyme `pre_hydrolysis_intent` field and a decision from the founder on each enzyme. | ~2 days |
| **Blinded / multi-subject trials** | Taster table, blind-key generation and reveal, per-taster scoring, inter-taster agreement. Upgrades the confidence tier ceiling above `suggestive`. | ~4–5 days |
| **LLM layer** | Local (Ollama) or API model parsing free-text recipes into structured inputs and narrating verdicts in plain language; typed function-calling only; the engine remains the sole source of every number. | ~3–5 days |
| **Hosted multi-user** | Fly.io deploy (same Dockerfile), volume for SQLite, Litestream backup to R2, Cloudflare Access in front; user column on tables. | ~1–2 days |

*(The experiment log, deferred in v1.1 of this spec, is promoted into v1 as Workflow E.)*

# 12. Known limitations (stated, not hidden)

1. **Recipe pH is worst-case minimum-ingredient, not a mixing or buffering model.** Real dressing pH requires measurement. The UI accepts a measured pH (`user_provided`, or `observed` when captured in a trial batch) which overrides the estimate in R1. A proper buffering model is a solver prerequisite, not a v1 feature.
2. **Dose guidance is benchmark-based**, not a kinetics model; trigger-food substrate loads are typical values, most seeding `unconfirmed`.
3. **In-jar survival is a threshold rule with a stated fallback margin** (R1), not a time-course degradation model. The founder's materials frame low-pH survival qualitatively, so the margin is an engineering convention that makes the rule testable — labeled as such in every finding it produces, and not a scientific claim.
4. **All temperature data and all shelf-stability floors are unconfirmed at seed.** R12 returns `cannot_assess` for every enzyme until supplier specs are approved. That is honest, and it is also the tool's most visible prompt to go get those specs.
5. **R15 is a mechanism-presence rule, not a kinetics model.** It answers "can this enzyme degrade this food's structure, and is contact long enough to matter," not "how much softening in how many hours." Rate depends on dose, temperature, and pH in ways no source document supports quantifying. The trial's observed column is what turns the prediction into a real answer.
6. **A home trial cannot measure enzyme activity, percent substrate hydrolysed, or shelf stability.** Those need a lab assay. What it can measure is taste, process, usability, applied-food texture against a control, and pH.
7. **Symptom results are single-subject and unblinded.** They are hypotheses, not evidence, and the report presents them that way (§6.6). The one cheap mitigation — having anyone else hand her the sample — is captured per-observation, not required.
8. **The tool still cannot answer the build-blocking physical question** — whether a given acid-stable variant survives a pH-3 matrix through shelf life. Only a stability bench run can. The tool's job is to make sure that run is the right one, and to record what was assumed while waiting.

# 13. Testing

**Golden fixtures** (these assert that composed rules reproduce KB §4m without hardcoding it):

Golden fixtures take every **enzyme** record from the real shipped seed. They supply `measured_ph` and per-food `typical_load_value` as explicit `user_provided` test inputs, because every seeded food pH and load is `unconfirmed` by design (§9.3) and a fixture that depended on them would assert the seed's gaps rather than the rules. Fixture (m) is the one deliberately synthetic record.

- (a) Wet vinaigrette, recipe pH 3.0 (explicit test input), standard fungal lactase → RED via R1 (fallback floor 3.5 breached), R4 AMBER present.
- (b) Creamy dressing, recipe pH 4.4 (explicit test input, not asserted as any real food's pH), same enzymes → AMBER: **R1 AMBER** (4.4 is inside the activity range but below the 5.0 optimum — sluggish and recoverable, per §6.1 R1), R4 AMBER, R8 AMBER with a dairy substrate present.
- (c) Dry sachet and dual-chamber, same recipe → GREEN: R1 skipped, R4 pass.
- (d) Bromelain co-formulated wet with lactase → R5 RED; separated into the dry chamber → pass.
- (e) Heat step after the enzyme addition point → R3 RED; strictly before → pass.
- (f) Alpha-galactosidase at 150 GalU against a 6 g-GOS serving → R7 AMBER (below the 300 GALU threshold).
- (f2) **R7 multi-food summing:** two GOS trigger foods (black beans + lentils) selected together → their `typical_load_value` figures sum, and the dose is compared against the sum, not against either alone (§6.7).
- (g) Inulinase selected → R9 advisory; alpha-galactosidase selected → R9 advisory also present (GOS is prebiotic).
- (h) Any **headline-capable** rule reading an `unconfirmed` field → `cannot_assess`, never pass; overall headline GRAY. Advisory rules (R8–R10, R12, R16) returning `cannot_assess` leave the headline unchanged — fixtures (a)–(c) depend on this, since R12 returns `cannot_assess` for every enzyme in the shipped seed catalog (§6.1 R12).
- (h2) **R12 promotion:** an enzyme whose temperature fields are edited to `confirmed` and whose range excludes ambient storage → R12 becomes red-capable for that enzyme and REDs the headline; every other enzyme in the same formulation stays advisory.
- (i) Trigger food with no covering enzyme → R14 RED; zero enzymes and zero trigger foods → validation rejection, no evaluation created.
- (j) Polyol trigger food selected → R14 `cannot_assess`; no enzyme is ever suggested for it.
- (k) **R15, narrow blend:** lactase + alpha-galactosidase on mixed greens → envelope passes all three profiles (neither degrades structure; both carry an empty `degrades_structural_json`).
- (l) **R15, gradual degrader:** cellulase (`gradual`, `pectin_cellulose`) on mixed greens → pass at `immediate`, AMBER at `packed`, RED at `marinade` per §6.3.1; with `dwell_profile` null and not all three RED, the headline contributes AMBER and the envelope panel names the failing occasion.
- (m) **R15, rapid tier (synthetic record):** a test-only enzyme record tagged `{structural_protein, rapid}` on cooked chicken → RED at all three profiles → headline contributes RED. Uses a synthetic fixture record deliberately: no shipped seed enzyme claims the `rapid` tier (§6.3.1), so this asserts the mapping and the all-three-RED aggregation branch without implying an unsourced rate claim about a real enzyme.
- (n) **R15, declared occasion:** same inputs as (l) but `dwell_profile = 'marinade'` → headline contributes RED.
- (o) **R15, unconfirmed:** inulinase on artichoke → `cannot_assess` on every profile, not a pass and not a fail.
- (o2) **R15, dwell bucketing:** `elapsed_minutes` of 0, 59, 60, 479, 480, and 1440 map to `immediate`, `immediate`, `packed`, `packed`, `marinade`, `marinade` respectively (§6.3).
- (p0) **R16 advisory:** a formulation with only microbial/fungal enzymes → R16 reports non-natural sourcing and `cannot_assess` on additives, and the headline is unchanged (advisory).
- (p) **Trial labeling:** an observation with `was_blinded` false and `had_undressed_control` false → `anecdote`; either flag true → `suggestive`; no path produces any stronger tier.
- (q) **Storage gate:** batch with `measured_ph` 5.2 or null → `storage_mode = 'ambient'` rejected; 4.1 → permitted.

**Unit tests per rule**, table-driven, one file per rule.

**Property tests:** verdict monotonicity (lowering recipe pH never improves R1; moving an enzyme wet→dry never worsens R4; increasing dwell never improves an R15 profile); aggregation ordering; advisory rules R8–R10 can never change the overall flag; snapshot reproducibility (same input snapshot + engine version → byte-identical evaluation); editing a source record never mutates a stored evaluation; **recording an observation never mutates a prediction**.

**pH resolution test:** with `formulation.measured_ph` null and a trial batch carrying a measured pH, evaluation hydration picks up the batch value labeled `observed`; with both set, the formulation value wins; with neither, the wet-ingredient fallback is used and labeled `calculated` (§6.7).

**Contract test:** applying any auto-variant patch yields a formulation that re-evaluates without error.

**Report lint:** the prohibited-words list (§10) is asserted absent from every generated report and every engine message, including trial output, matched on **word boundaries** — "safety" is permitted, "safe" is not, which is what lets the §10 footer survive its own lint. A separate, stricter **substring** lint runs over `api/` source, where no prohibited word has any legitimate reason to appear.

**E2E (Playwright):** build recipe → evaluate → apply variant → compare → generate trial → log batch and observations → export report showing predicted and observed.

# 14. Milestones (~4 weeks)

- **M1 — Engine + seed (week 1):** schema, seed JSONs from the founder's documents, R1–R16, dosing, GI model, occasion envelope, aggregation, and the pure trial helpers (dwell bucketing, confidence tier, ambient-storage gate) that §13 fixtures (o2), (p), (q) assert. Golden fixtures green.
- **M2 — API + core UI (week 2):** recipe builder with custom foods and measured-pH entry, formulation setup with application foods, verdict screen with the GI strip, four headline states, and the envelope panel.
- **M3 — Variants, compare, DB editor, report (week 3):** auto-variants, side-by-side compare, proposals inbox, stale-evaluation banner, print report, Docker compose polish.
- **M4 — Kitchen trial (week 4):** protocol generation, batch and observation capture, storage gate, symptom entry with live dose math, predicted-vs-observed on the verdict screen, report honesty split.
- **M5 — Report format, punch list, and the UI pass:** the report in the shape a food scientist reads it (percent-of-total formula in order of addition, allergen declaration, process table, batch records, unmeasured parameters stated rather than omitted); the first schema migration; structured catalogue fields made editable and proposable so §15 item 4 has an in-product answer; per-record last-edited; and a design-token, accessibility and mobile pass over the whole UI.
**Planning note:** this spec is not to be turned into a single implementation plan. Plan and execute **M1 alone** first, confirm the golden fixtures pass against the *real shipped seed catalog* (not synthetic records, except fixture (m) which is synthetic by design), and only then plan M2–M4. The engine-level decisions most likely to shift under contact with real data are R12's advisory status, the §6.3.1 severity tiers, and the §6.7 wet-ingredient threshold.

- **Exit check:** the founder builds her real vinaigrette and creamy candidates unassisted, gets verdicts matching the KB's §4m expectations, runs one full kitchen trial end to end, and exports a report she would hand to a food scientist.

# 15. Open questions (tracked in-app as proposals; none block the build)

1. Acid-stable lactase and alpha-galactosidase variants and their real pH-stability specs — `ph_shelf_stable_min` exists to hold these answers. Suppliers: Amano and BIO-CAT are startup-friendly; Novonesis and IFF are the largest.
2. Fructan hydrolase sourcing and freedom to operate given US 10,820,599.
3. Inulinase, lipase, and xylose-isomerase dose benchmarks; per-enzyme temperature ranges; xylose isomerase activity at 37 °C.
4. **Does inulinase degrade the structure of inulin-rich vegetables** (chicory, artichoke) over long dwell? Seeds `unconfirmed` in R15; a supplier or literature answer would close it.
5. Whether to break down inulin at all, given its prebiotic value — the founder's product-philosophy call; R9 keeps it visible.
6. Encapsulation approach and supplier for the ready-to-eat format. **Prior art worth studying:** `US20240206516A1` (in `fwbackgroundmaterials/`, listed there as the Wyss patent; text verified via Google Patents) — "Systems and methods for sugar-reduction and/or fiber production for food and other applications." It claims enzyme particles held inactive by a reversibly-bound polyphenol inhibitor that dissociates above pH 3.5 at ionic strength ≥ 5 mmol/L: an enzyme that stays off in the product and switches on in the GI tract. Different goal (sugar → fiber conversion), same mechanism family as the inert-in-jar / active-in-body problem, and a freedom-to-operate consideration if she pursues inhibitor-particle encapsulation.
7. Ingredient-level pH values for the food catalog — measurement or supplier data, whichever comes first.
8. Which use occasions the product will support. Deliberately unanswered: R15's envelope plus the first kitchen trials are the instrument for deciding it, rather than an assumption made up front.
9. Which allergen does the generic `nuts_seeds` catalogue entry carry — tree nut, peanut, sesame, or several? Seeded as *not recorded* rather than guessed; closable through the database editor.
10. Is the observed texture scale of §6.3 calibrated the way the founder actually scores? It is an engineering convention until she has scored real trials against it.

# 16. Amendments

This spec was written before the build. These entries record where contact with
real data changed it, so a reader can tell an original sentence from an amended
one. Each was implemented in the milestone named and accepted before it shipped.

| # | Section | Amendment | Milestone |
|---|---|---|---|
| 1 | §4 | Boot semantics: seeds load on first boot only; later boots verify tables and apply additive column migrations; reads always go through SQLite | M2, M5 |
| 2 | §5.1 | `food.allergens_json` added — inert catalogue data, printed as a declaration, read by no rule | M5 |
| 3 | §5.4 | Only an approved proposal may write `confirmed`; structured fields carry their provenance in the value | M3, M5 |
| 4 | §6.1 R2/R7/R11 | Per-field advisory exception for a `cannot_assess` caused by a permanently-unconfirmed static catalogue field | M1 |
| 5 | §6.1 R13 | The format ladder is scanned from the top, not from the current format | M3 |
| 6 | §6.3 | The observed texture scale, stated as an engineering convention | M4 |
| 7 | §6.5 | Scheduled vs per-use checkpoint cadence; per-use items are never overdue | M4 |
| 8 | §7 | The "raise recipe pH" suggestion is a note, not a patch | M3 |
| 9 | §10 screen 8 | The report format, per the conventions food scientists use | M5 |
| 10 | §13 | Fixture-input policy; fixture (b)'s R1 verdict corrected; report lint matching rules stated | M1, M3 |
| 11 | §14, §15 | M5 milestone line; two new open questions | M5 |
