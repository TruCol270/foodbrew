---
title: FoodBrew — Enzyme Formulation Rules Engine (MVP Design Spec)
version: 1.1
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

A **rules engine over an enzyme database and an ingredient database** — exactly as specified in the founder's Formulation Knowledge Base. Given a recipe and target trigger foods, it outputs: which enzymes, at what dose, with pH / temperature / stability / denaturation / co-formulation / taste flags, and a format + packaging recommendation.

Headline verdict is one of four states (§6.3): **RED** (blocker), **GRAY** (gaps block a verdict), **AMBER** (caution), **GREEN** (clear on the rules evaluated).

This spec supersedes the earlier ChatGPT-generated tomato-sauce formulation workbench spec. That spec assumed a thermal process (the founder's #1 rule is NO HEAT), modelled microbial growth instead of enzyme survival, and targeted bench food-scientists instead of the founder. Its engineering discipline is retained (truth labels, provenance, deterministic pure-function core, golden fixtures); its domain content is replaced.

## 1.3 What v1 must let the founder do (success criteria)

1. Enter a dressing recipe and target trigger foods through structured forms, with no training, and get a complete verdict in under 5 minutes.
2. Every flag traces to a named rule, and every number traces to a database record with a status label. No orphan numbers.
3. The tool never claims safety, efficacy, or regulatory compliance — it flags formulation risks and knowledge gaps.
4. When data is missing (a "confirm with supplier" cell), the affected rule reports **cannot_assess** naming the missing datum, never a silent pass.
5. A target trigger food with no enzyme covering it is reported as a blocker, never as a pass (§6.2, R14).
6. Side-by-side comparison of 2+ recipe/format variants shows exactly which flags changed and why.
7. The founder can correct or fill in any enzyme/ingredient value herself; her edits are marked `user_provided` and never overwrite the seeded baseline.

# 2. Scope

## 2.1 v1 IN

- **Recipe check:** recipe + trigger foods + intended format → enzyme selection, dose guidance, per-rule flags, format recommendation.
- **What-if comparison:** clone a formulation, tweak (ingredients, amounts, enzyme sources, format), see side-by-side flag/dose diff.
- **Auto-generated variants:** rules-driven fix suggestions, each re-run through the engine so its own flags are shown honestly.
- **Seeded databases** from the Knowledge Base, with `unconfirmed` gaps visible and editable.
- **Single user, local Docker deployment.** No auth on localhost. Same container deploys to Fly.io later unchanged.
- **Print-friendly report view** of any evaluation (browser print → PDF) for sharing with advisors and suppliers.

## 2.2 v1 OUT (deferred; build cost estimated in §11)

- Experiment log (bench-result capture vs predictions)
- Cost modeling (per-recipe COGS from enzyme cost tiers)
- Numeric optimization / solver
- LLM layer (natural-language recipe input, chat, generated explanations)
- Multi-user accounts, hosted auth
- **Consumer-facing timing guidance** (KB §4h: "add immediately or 5–10 minutes before eating") — the engine computes the enzyme's GI deadline in R2, but translating that into consumer usage instructions is a labeling decision deferred to v1.1 (§11)
- Any microbial/safety modeling, regulatory claim generation, shelf-life prediction

## 2.3 Parallel track (not a build dependency)

A research pass proposes literature/supplier-spec values for every `unconfirmed` cell (inulinase dose, fructan hydrolase pH, acid-stable lactase variants, xylose isomerase activity at 37 °C, lipase dose, ingredient pH values). Each proposal carries a source and enters the database only when the founder approves it in the UI (status flips `unconfirmed` → `confirmed`, provenance recorded). See the `proposal` table in §5.

# 3. User & workflows

**Primary user:** the founder. Non-technical. Runs the tool independently.

## Workflow A — Check a recipe
1. Build recipe: pick ingredients from catalog (or add custom), enter amounts per batch and per serving.
2. Pick target trigger foods (or accept the ones implied by the recipe's own substrates).
3. Pick intended format: `premixed_wet` / `dry_sachet` / `dual_chamber` / `encapsulated_in_wet`.
4. Tool proposes the enzyme set from the substrate map; founder can add/remove/re-source enzymes. Removing coverage does not remove the finding — R14 reports the uncovered substrate.
5. Run → verdict screen: headline RED/GRAY/AMBER/GREEN, per-rule findings, per-enzyme dose guidance, format recommendation, open data gaps.

## Workflow B — Compare variants
Clone any formulation, change anything, run both. Comparison table: one column per variant, one row per rule + dose + format call, changed cells highlighted.

## Workflow C — Apply suggested fixes
Verdict screen lists auto-variants (§7). One click materializes a suggestion as a new cloned formulation with the change applied, re-runs the engine, drops the founder into the Workflow B comparison.

## Workflow D — Maintain the database
Enzyme and ingredient editors. Every field shows value, unit, status, source note, last-edited. Founder edits create `user_provided` values; "reset to baseline" restores the seed. Research-track proposals appear here for approve/reject. Editing a record does not alter past evaluations (they are snapshotted, §4); affected evaluations display a "data changed since this evaluation — re-run to refresh" banner (§10, screen 4).

# 4. Architecture

Approved in brainstorming; recorded here.

```
docker compose up  →  one container
┌─────────────────────────────────────────────┐
│ FastAPI (uvicorn :8000)                     │
│  ├── serves React build (static)            │
│  ├── /api/v1/* JSON endpoints               │
│  ├── engine/          ← pure Python, no I/O │
│  │    ├── rules.py    (R1–R14)              │
│  │    ├── dosing.py                         │
│  │    ├── gi_model.py                       │
│  │    ├── variants.py (auto-suggestions)    │
│  │    └── flags.py    (aggregation)         │
│  └── SQLite /data/foodbrew.db               │
│      (bind mount ./data → /data)            │
└─────────────────────────────────────────────┘
Frontend: React + TypeScript + Vite, form-driven
```

**Dependency rule:** `engine/` contains pure functions operating on plain dataclasses/dicts. No SQLAlchemy, no HTTP, no file I/O inside the engine. The API layer hydrates inputs from SQLite, calls the engine, persists the evaluation. The engine is unit-testable with zero infrastructure and portable to any future stack.

**Seed data:** versioned JSON in-repo (`seed/enzymes.json`, `seed/ingredients.json`, `seed/substrates.json`, `seed/trigger_foods.json`, `seed/gi_model.json`). Loaded on first boot; founder edits go to SQLite only; seeds stay pristine for reset and git-diffable review.

**Versioning for reproducibility:** every evaluation stores `engine_version`, a snapshot of all inputs (recipe, enzyme records used, format, process steps), and the rule outcomes. Re-running an old snapshot on the same engine version must reproduce byte-identical results. Later edits to source records never mutate a stored evaluation.

# 5. Data model (SQLite)

| Table | Key fields |
|---|---|
| `enzyme` | id, name, aliases, substrate_id, source_type (fungal/yeast/microbial/plant), **ph_min, ph_max** (activity range), **ph_shelf_stable_min** (sustained-exposure floor — see R1), ph_opt_low, ph_opt_high, temp_min_c, temp_max_c, temp_opt_c, site_of_action, deadline (`before_small_intestine` / `before_colon` / `small_intestine`), dose_unit (FCC/GalU/GDU/…), dose_min, dose_max, dose_evidence_threshold, dose_benchmark_note, is_protease, is_gras, food_grade_note, is_natural_source (KB §4j), heat_labile_note, priority (high/medium/additive/lower), cost_tier, supplier_note — **every numeric field paired with** `*_status` **and** `*_source` |
| `substrate` | id, name (lactose, GOS, inulin_fructan, graminan_fructan, excess_fructose, polyol, protein, fat, sucrose, starch, fiber, pectin), native_human_enzyme (bool), is_prebiotic (bool — drives R9), no_commercial_enzyme (bool — e.g. polyols), notes |
| `trigger_food` | id, name, substrate_id, typical_load_note, typical_load_value, typical_load_unit, load_status/load_source |
| `ingredient` | id, name, category, ph, ph_status, ph_source, water_content_pct, contains_substrate_ids, contains_protease, is_heat_processed, notes, status/source fields |
| `recipe` | id, name, notes, created_at |
| `recipe_ingredient` | recipe_id, ingredient_id, amount_g, order |
| `formulation` | id, recipe_id, format (`premixed_wet`/`dry_sachet`/`dual_chamber`/`encapsulated_in_wet`), target_trigger_food_ids, enzyme_selection_json (enzyme_id, source choice, dose, encapsulated bool, phase: `wet`/`dry`), serving_size_g, **measured_ph, measured_ph_status, measured_ph_source** (founder's bench override for R1 — §12.1), process_steps_json (ordered steps w/ heat flag + enzyme-addition point), parent_formulation_id, created_at |
| `gi_region` | id, name, ph_low, ph_high, transit_note, order |
| `evaluation` | id, formulation_id, engine_version, input_snapshot_json, overall_flag (`red`/`cannot_assess`/`amber`/`pass`), created_at |
| `rule_finding` | evaluation_id, rule_id (R1–R14), enzyme_id (nullable), verdict (`pass`/`amber`/`red`/`cannot_assess`), message, evidence_json (the exact values compared) |
| `variant_suggestion` | evaluation_id, suggestion_type, description, patch_json, created_at |
| `proposal` | id, table_name, record_id, field, proposed_value, source_citation, status (`pending`/`approved`/`rejected`) — the research-track inbox |
| `audit_event` | actor, action, entity, before_json, after_json, timestamp |

## Truth labels

Every displayed value carries exactly one of four labels. This enum is closed; no other token appears in seeds, API, or UI.

- `confirmed` — verified against a named source; the source is recorded in the paired `*_source` field (e.g. "Formulation Knowledge Base, Table B").
- `unconfirmed` — seeded from a KB "confirm" cell, inferred, or proposed by research but not yet approved. Any rule depending on it returns `cannot_assess`.
- `user_provided` — founder override or founder-entered custom record.
- `calculated` — engine output, carrying its rule/formula reference.

# 6. The rules engine

Each rule is a pure function: `(formulation_inputs) → RuleFinding(verdict, message, evidence)`. Verdicts: `pass`, `amber`, `red`, `cannot_assess`. A rule that needs an `unconfirmed` value returns `cannot_assess` naming the missing datum — never a silent pass, never a guess.

## 6.1 KB §4 → rule mapping (traceability to the founder's document)

Every KB §4 letter a–m maps to at least one rule.

| Rule | KB § | Logic |
|---|---|---|
| **R1 In-jar pH survival** | 4a | Applies to formats where the enzyme contacts liquid on the shelf (`premixed_wet`; `encapsulated_in_wet` at reduced severity via R6). Recipe pH = `formulation.measured_ph` when the founder has entered one, else worst-case = lowest pH among wet ingredients sharing the enzyme's phase (§12.1). Compare against the enzyme's **`ph_shelf_stable_min`** — the floor for sustained (shelf-duration) exposure, which is distinct from and higher than the activity-range `ph_min`. Verdicts: recipe pH < `ph_shelf_stable_min` → **RED**; within range but outside `ph_opt` → **AMBER** (sluggish, recoverable — KB: survival ≠ activity, denaturation is permanent); at/above optimum → pass. When `ph_shelf_stable_min` is `unconfirmed` (the common case — no supplier has confirmed one), the engine applies a **stated fallback margin: `ph_shelf_stable_min = ph_min + 1.0`**, returns **RED** if breached, and labels the finding "margin heuristic — supplier confirmation required," never a silent pass. Worked case: vinaigrette pH ~3.0 vs fungal lactase `ph_min` 2.5 → fallback floor 3.5 → 3.0 < 3.5 → RED, matching KB §4m. Dry-phase enzymes skip R1. |
| **R2 GI window vs deadline** | 4a, 4h | Using the GI model (§8), report each enzyme's active pH window per tract region against its deadline. Substrates with no native human enzyme (GOS, fructans, excess fructose) are hard deadlines — residue reaching the colon ferments; there is no catching up. Mouth is dormant for all enzymes regardless of pH fit (dwell is seconds). Enzyme with no active region before its deadline → RED; partial coverage → AMBER. **Not covered in v1 (deferred, §2.2):** KB §4h's per-enzyme pre-hydrolysis-vs-survive-to-gut design choice and consumer timing instructions. |
| **R3 No heat** | 4b, 4j | Any process step flagged heat at-or-after the enzyme addition point → **RED**, naming the fix (add enzyme after heat, at the end). Heat strictly before enzyme addition → pass with note. Ingredient-level `is_heat_processed` is informational: per KB §4j, cooking destroys naturally occurring enzymes (bromelain, papain, diastase), so a cooked pineapple/papaya ingredient no longer contributes protease — this suppresses the R5 conflict for that ingredient and is reported as a note. |
| **R4 Water activation** | 4c | Dry = inert; wet = active and unstoppable. `dry_sachet` / `dual_chamber` (enzyme in dry chamber) → **pass**. `premixed_wet` → **AMBER** on its own: water switches the enzyme on, so activity decays and the enzyme digests jar contents over shelf life; the magnitude is unknown without stability data, so R4 alone never REDs. Escalation to RED comes from the compounding rules — R1 (pH kill), R5 (protease conflict), R6 (encapsulation over-reliance) — via normal worst-of aggregation. This calibration is what reproduces KB §4m's three-tier heuristic: acidic vinaigrette REDs through R1, creamy premix lands AMBER through R4/R8, dry/separated is GREEN. **An R4 AMBER is never a green light to ship premixed** — its message states that KB §4c requires physical separation for shelf life and that shipping wet requires bench stability data. `encapsulated_in_wet` → AMBER, deferring to R6. |
| **R5 Protease co-formulation** | 4d | If any selected enzyme `is_protease` (bromelain, papain) **or** any recipe ingredient has `contains_protease` and is not heat-processed, and it shares a wet active phase with other enzymes → the protease degrades them (enzymes are proteins) → **RED**. Separated (different chamber, dry, or individually encapsulated) → pass with note. |
| **R6 Encapsulation semantics** | 4f | Encapsulation is a timing control, not immunity: it cannot rescue an enzyme from a condition that denatures on contact, only delay exposure. `encapsulated_in_wet` where the capsule is the only barrier against an R1-breaching pH for shelf-duration → **RED** (asks the capsule to do what KB §4f says it cannot). Under `dual_chamber`, the bar drops: the capsule must survive minutes in dressing plus stomach transit, not months in acid — R1 is re-evaluated at that exposure and R6 returns pass with note. |
| **R7 Dosing vs substrate load** | 4g | Dose driven by substrate load per serving, not food weight. Seeded benchmarks: lactase 900–18,000 FCC (Lactaid Fast Act 9,000 FCC/chewable tablet; suggested 3,000–6,000 FCC for a 0–6 g-lactose serving, 6,000–9,000 for 6–12 g, 9,000–15,000+ for 12 g+); alpha-galactosidase 450–800 GalU (Beano Extra Strength 800 GalU/serving). **Evidence threshold, separate from any product dose:** Monash/in-vitro evidence shows full-dose alpha-galactosidase at 300 GALU improved GOS symptoms while half-dose did not — an underdosed enzyme behaves like placebo. Dose below `dose_evidence_threshold` → **AMBER**. Unconfirmed benchmarks (inulinase, lipase, fructan hydrolase, xylose isomerase) → `cannot_assess`. Overdose → note: works, but an expensive way to solve it. Dose-decoupling warning for fixed-dose formats meeting variable meals; the squeeze format self-scales only with **dressing used, not with trigger food eaten** — the report states this limit explicitly and never presents it as full self-scaling. |
| **R8 Taste/stability over time** | 4e | Active enzyme sharing a wet phase with its own substrate present in the recipe (e.g. lactase in a dairy-based creamy dressing; protease with dairy/egg protein) → flavor, texture, smell, and appearance drift over time (lactose hydrolysis → sweeter; product can turn "weird and smelly") → **AMBER** for wet-contact formats; note for dry/separated formats (drift begins at mixing, not before). |
| **R9 Prebiotic tension** | 4i | Triggered when any enzyme targeting a substrate flagged `is_prebiotic` is selected — **inulinase, fructan hydrolase, and alpha-galactosidase** (KB §4i names inulin, fructans, *and GOS*). Advisory only, never RED: these fibers feed the microbiome, so dose to a symptom threshold rather than to zero. Notes that garlic and onion carry more short-chain fructans than inulin. A product-philosophy call the founder owns; the rule keeps it visible. |
| **R10 Strain blending** | 4k | If a selected enzyme's active window covers only part of the useful GI range (e.g. fungal acid lactase, ceiling 5.4, drops out at the duodenum), suggest pairing a complementary source (acid fungal + neutral yeast lactase — the Enzymedica pattern) to widen the active window. Surfaced as an auto-variant, never a failure. |
| **R11 Food-grade / GRAS** | 4l | Selected enzyme must be food-grade with GRAS status recorded. Lactase and alpha-galactosidase are largely already GRAS (a cost and time advantage). Missing or unknown → `cannot_assess` with the supplier question text. A standing banner notes that finished-product rules (food safety, acidified-food regulations) are out of this tool's scope. |
| **R12 Temperature range** | 4b | Enzyme `temp_min_c`/`temp_max_c` vs the ambient-shelf assumption (no cold chain — a stated product requirement) and body temperature 37 °C. All per-enzyme temperature values seed as `unconfirmed` — the source documents give no per-enzyme temperature data — so R12 returns `cannot_assess` until a supplier spec is approved. Xylose isomerase carries a seeded `unconfirmed` caution (external assumption, not from the founder's documents) that its industrial optimum may sit well above body temperature, making 37 °C activity a supplier question. |
| **R13 Format flag (headline)** | 4m | Aggregation, not an independent test — see §6.3. The KB heuristic (wet acidic vinaigrette + standard acid lactase = RED; creamy, higher-pH but still wet = AMBER; dry, separated, or encapsulated = GREEN) is **not hardcoded**; it is a golden-fixture assertion (§13 a/b/c) that the composed rules must reproduce. R13 also computes the format recommendation: the least-invasive format change (premixed → encapsulated → dual-chamber → dry sachet) under which re-running R1–R12 and R14 yields no RED. |

## 6.2 Engine-derived rules (not from KB §4)

| Rule | Source | Logic |
|---|---|---|
| **R14 Substrate coverage** | KB §5 outputs ("recommended enzymes and doses for the target substrates") | For every selected target trigger food, its substrate must be targeted by at least one selected enzyme. Uncovered substrate → **RED** naming it ("no enzyme selected for lactose"). Substrate flagged `no_commercial_enzyme` (polyols) → `cannot_assess` stating no commercial enzyme exists for it — the tool never maps polyols to an enzyme. A formulation with zero enzymes selected and one or more target trigger foods is therefore RED, never a bare pass. Zero enzymes **and** zero target trigger foods → the run is rejected at validation with "select at least one trigger food or enzyme," not evaluated. |

## 6.3 Aggregation

Severity order: `red` > `cannot_assess` > `amber` > `pass`.

Overall flag = worst verdict among **R1–R7, R11, R12, R14**. R8, R9, R10 are advisory and cannot set the overall flag.

Headline display maps one-to-one: `red` → **RED** (blocker), `cannot_assess` → **GRAY** (gaps block a verdict), `amber` → **AMBER** (caution), `pass` → **GREEN** (clear on the rules evaluated). `cannot_assess` is never folded into pass or fail; a GRAY headline means the tool is declining to judge, and the verdict screen lists exactly which fields are missing.

# 7. Auto-variant generation

`variants.py` maps failing findings to a fix catalog. Each suggestion carries a machine-applicable `patch_json`; applying it clones the formulation, applies the patch, and re-runs the engine. Suggestions are never presented as pre-cleared — their own flags are shown.

| Trigger finding | Suggested variant |
|---|---|
| R1 RED (pH below shelf-stable floor) | Switch to an acid-stable variant of the same enzyme (surfaced even when the record is `unconfirmed`, labeled "candidate — confirm with supplier"); raise recipe pH by reducing/replacing the acid ingredient (shown as a recipe change; the founder judges taste); change format to dual-chamber or dry sachet |
| R3 RED (heat after enzyme) | Move the enzyme addition point to after the heat step (patches process order) |
| R4 AMBER / R6 RED (wet premix reliance) | Dual-chamber; dry sachet pairing; individual encapsulation (carries the R6 caveat) |
| R5 RED (protease conflict) | Separate the protease into the other chamber or its own encapsulation; drop the protease (KB: additive, not gap-filling — the body already covers protein digestion), noting bromelain's remaining value is clean-label and marketing |
| R7 AMBER (below evidence threshold) | Raise dose to the evidence threshold; reduce the declared trigger-food serving |
| R10 note | Add a complementary-source enzyme pairing to widen the active window |
| R12 / R11 `cannot_assess` | No formulation patch — emits a supplier question for the report's open-questions list |
| R14 RED (uncovered substrate) | Add the enzyme that targets the uncovered substrate (from the substrate map), at its benchmark dose |

# 8. GI model (seed values, from the Enzyme Site of Action deck)

| Region | pH | Note |
|---|---|---|
| Mouth | 6.2–7.6 | Dwell is seconds — all enzymes effectively dormant here regardless of pH fit |
| Stomach, fasting | 1.5–2.0 | Only acid-tolerant enzymes active pre-meal |
| Stomach, fed | 4–6 | Food buffers upward, drifts back down over ~2 h — the main workhorse window |
| Duodenum | 6.0–6.5 | Fungal lactase (ceiling 5.4) has dropped out; inulinase fading |
| Jejunum/ileum | 7.0–7.5 | Xylose isomerase's prime window |
| Colon | 5.5–7.0 | Too late — undigested substrate ferments here (the symptom mechanism) |

Overall race window: ~2–4 h mouth-to-colon. Deadlines, not anatomical targets.

**Documented source inconsistency, resolved in the seed.** Lactase's site of action is described two ways across the founder's materials: KB Table B *and* Site-of-Action slide 1 both list "mouth → stomach," while slide 3 of the same deck shows the mouth dormant for every enzyme (dwell too brief to react) and lactase active in the fed stomach, dropping out at the duodenum above its 5.4 ceiling. The inconsistency therefore spans both documents and exists **within the deck itself** (slide 1 vs slide 3), not only between the KB and the deck. **The seed encodes slide 3's version** (act in the fed stomach, finish before the duodenum), with a source note recording the discrepancy for the founder to confirm.

# 9. Seed data summary

Full tables are generated into `seed/*.json` during implementation. Every value carries a status label; anything not stated in the founder's documents seeds as `unconfirmed`, never as fact.

**Enzymes** (KB Tables A/B + Site-of-Action deck). pH ranges seed `confirmed` with source "Formulation Knowledge Base Table B / Site-of-Action slide 1"; **all temperature fields and all `ph_shelf_stable_min` fields seed `unconfirmed`** (no source document provides them):

- **Lactase** — fungal (acid) pH 2.5–5.4, optimum ~5.0; yeast (neutral) variant stub `unconfirmed`. Note recorded: one commercial supplier spec (Sunson) lists a broader 3.0–8.0 activity range with optimum 3.5–5.0, treated as a looser "still shows some activity" claim, not a sustained-stability figure. Dose 900–18,000 FCC.
- **Alpha-galactosidase** — fungal (*A. niger*), pH 3.0–8.0, optimum ~5.0. Dose 450–800 GalU; `dose_evidence_threshold` 300 GALU (Monash/in-vitro full-dose finding, `confirmed`, cited to the Digestive Enzyme Industry Overview).
- **Inulinase** — fungal, pH 2.0–7.0, optimum ~3.0–5.0. Dose `unconfirmed`.
- **Fructan hydrolase** — FODZYME blend; pH `unconfirmed`. **FTO note:** the underlying patent appears third-party/licensed (US 10,820,599, per the Digestive Enzyme Industry Overview).
- **Protease / bromelain** — microbial, or pineapple/papaya; pH 4.0–8.0, optimum ~7.0; bromelain ~4.5–7. `is_protease` = true, `is_natural_source` = true, heat-labile. Dose unit GDU, value `unconfirmed`.
- **Lipase** — fungal, some plants; pH 2.0–9.0, optimum ~7.0. Dose `unconfirmed`.
- **Xylose / glucose isomerase** — microbial, pH 7.0–9.0. Dose `unconfirmed`. Carries the `unconfirmed` 37 °C-activity caution (§6.1 R12), labeled an external assumption outside the founder's documents.
- Lower-priority stubs: invertase, amylase, cellulase, pectinase (KB Table A).

**Substrate map** (KB §3): lactose → dairy (hard aged cheeses low-lactose); GOS → beans, lentils, chickpeas, cruciferous; inulin-type fructans → onion, garlic, chicory, artichoke; graminan-type fructans → wheat, barley, rye; excess fructose → apples, mango, honey; polyols → mushrooms, stone fruit, sugar-free gum (**`no_commercial_enzyme` = true**); protein → meat, eggs, dairy, legumes; fat → oils, butter, fatty meats. `is_prebiotic` = true on GOS, inulin-type fructans, and graminan-type fructans (drives R9).

**Ingredient starter catalog** (~25 records for dressings): oils (olive, canola), vinegars (balsamic, white, apple cider), lemon juice, honey, mustard, yogurt, buttermilk, mayonnaise, garlic (fresh and powder), onion, herbs, salt, sugar, water, fresh pineapple and papaya (`contains_protease` = true — the trap ingredients), modified starch.

**All ingredient pH values seed `unconfirmed`.** The KB gives only one pH statement — that vinegar puts a dressing around pH 3 — and no ingredient-level figures. Seeded pH values are therefore starting estimates flagged for the founder to measure or confirm; R1 returns `cannot_assess` on an unconfirmed-pH recipe unless the founder supplies `measured_ph`. This is the single highest-value target for the §2.3 research track and for her first bench session.

# 10. API & UI

**API (JSON, versioned `/api/v1`):** CRUD for recipes / formulations / enzymes / ingredients; `POST /formulations/{id}/evaluate`; `GET /evaluations/{id}`; `POST /evaluations/{id}/apply-variant`; `GET /compare?ids=…`; proposals inbox endpoints; `GET /export/{evaluation_id}.md`.

**Screens:**
1. **Home** — recipe list, recent evaluations.
2. **Recipe builder** — ingredient picker with amounts; custom-ingredient creation (name, category, pH, water content, substrates, protease flag, heat-processed flag — all stored `user_provided`); live substrate summary ("this recipe itself contains: GOS (garlic)…"); optional measured-pH entry.
3. **Formulation setup** — format picker, trigger-food picker, proposed enzyme set (editable), serving size, process steps with heat flags and the enzyme-addition point.
4. **Verdict** — headline RED / GRAY / AMBER / GREEN; rule findings grouped (Blockers / Data gaps / Cautions / Advisory); per-enzyme dose card; GI-tract strip showing each enzyme's active window against its deadline (the deck's slide-3 visual, rendered live); variant suggestions with one-click apply; a "data has changed since this evaluation — re-run to refresh" banner when any referenced enzyme or ingredient record was edited after the evaluation's timestamp.
5. **Compare** — variants side-by-side, changed cells highlighted.
6. **Database** — enzyme and ingredient editors, proposals inbox, reset-to-baseline.
7. **Report** — print-friendly single page of a verdict: inputs, findings, evidence values, data gaps, sources, engine version, and a fixed footer: *"Formulation decision support. Not a safety, efficacy, or regulatory determination."*

Language throughout: plain English, no jargon without a tooltip. Prohibited words in engine output: "safe," "validated," "guaranteed," "clinically proven."

# 11. Deferred features — what each would take (for when she wants more)

| Feature | Build sketch | Effort |
|---|---|---|
| **Experiment log** | Tables `experiment` + `observation` (immutable, audited corrections); attach bench results (measured pH, activity assay, taste notes at t=0 / 2 wk / 4 wk…) to a formulation; predicted-vs-observed view. Feeds measured pH straight back into R1. No new engine work. | ~3–5 days |
| **Cost modeling** | `cost_per_unit` on enzyme and ingredient records (from supplier quotes); per-serving and per-batch COGS roll-up; margin sketch against a target shelf price. The Condiment Industry Overview deck (p21) gives the benchmark to compare against: at a $12 shelf price the retailer and middlemen take ~60%, leaving ~$5 net revenue, so a 50% gross margin needs COGS near $2.50 — with early-stage margins realistically ~20%. Pure arithmetic; blocked mainly on real quotes. | ~2–3 days once quotes exist |
| **Numeric solver** | SciPy bounded search over ingredient amounts and enzyme dose to satisfy hard constraints (recipe pH ≥ chosen enzyme's shelf-stable floor, dose ≥ evidence threshold, format fixed) while minimizing soft objectives (acid reduction, cost, deviation from the founder's target flavor profile). **The solver is the easy half.** The hard half is a real recipe-pH mixing model: pH is not the minimum of ingredient pH values but a buffered nonlinear function of acid concentration, dissociation constants, and the buffering capacity of the dairy or emulsion base — that model needs bench pH-titration data on her actual ingredients before a solver's output is worth anything. Build the experiment log first so the titration data has somewhere to live. | ~1–2 weeks after titration data exists |
| **Consumer timing guidance** | Derive "add immediately" vs "5–10 min before eating" per enzyme from its deadline, GI window, and pre-hydrolysis intent (KB §4h); surface on the dose card and in the report. Needs a per-enzyme `pre_hydrolysis_intent` field and a decision from the founder on each enzyme. | ~2 days |
| **LLM layer** | Local (Ollama) or API model parsing free-text recipes into structured inputs and narrating verdicts in plain language; typed function-calling only; the engine remains the sole source of every number. | ~3–5 days |
| **Hosted multi-user** | Fly.io deploy (same Dockerfile), volume for SQLite, Litestream backup to R2, Cloudflare Access in front; user column on tables. | ~1–2 days |

# 12. Known limitations (stated, not hidden)

1. **Recipe pH is worst-case minimum-ingredient, not a mixing or buffering model.** Real dressing pH requires bench measurement. The UI accepts a measured recipe pH (`formulation.measured_ph`, `user_provided`) which overrides the estimate in R1. A proper buffering model is a solver prerequisite, not a v1 feature (§11).
2. **Dose guidance is benchmark-based**, not a kinetics model; trigger-food substrate loads are typical values, and most of them seed `unconfirmed`.
3. **In-jar survival is a threshold rule with a stated fallback margin** (R1), not a time-course degradation model. The founder's own materials frame low-pH survival qualitatively ("most food-grade lactase and alpha-gal do not survive very low pH for long"), so the margin is an engineering convention that makes the rule testable — it is labeled as such in every finding it produces, and it is not a scientific claim.
4. **All temperature data and all shelf-stability floors are unconfirmed at seed.** R12 will return `cannot_assess` for every enzyme until supplier specs are approved. This is honest, and it is also the tool's most visible prompt to go get those specs.
5. **The tool cannot answer the build-blocking physical question** — whether a given acid-stable variant actually survives a pH-3 matrix through shelf life. Only a stability bench run can. The tool's job is to make sure that bench run is the right one, and to record what it assumed while waiting for the answer.

# 13. Testing

**Golden fixtures** (the KB's own worked examples — these assert that composed rules reproduce KB §4m without hardcoding it):

- (a) Wet vinaigrette, recipe pH 3.0 (explicit test input), standard fungal lactase → RED via R1 (fallback floor 3.5 breached), with R4 AMBER present.
- (b) Creamy dressing, recipe pH 4.4 (explicit test input, not asserted as any real ingredient's pH), same enzymes → AMBER: R1 pass, R4 AMBER, R8 AMBER if a dairy substrate is present.
- (c) Dry sachet and dual-chamber, same recipe → GREEN: R1 skipped, R4 pass.
- (d) Bromelain co-formulated wet with lactase → R5 RED; separated into the dry chamber → pass.
- (e) Heat step after the enzyme addition point → R3 RED; strictly before → pass.
- (f) Alpha-galactosidase at 150 GalU against a 6 g-GOS serving → R7 AMBER (below the 300 GALU evidence threshold).
- (g) Inulinase selected → R9 advisory present; alpha-galactosidase selected → R9 advisory also present (GOS is prebiotic).
- (h) Any rule reading an `unconfirmed` field → `cannot_assess`, never pass; overall headline GRAY.
- (i) Target trigger food with no covering enzyme → R14 RED; zero enzymes and zero trigger foods → validation rejection, no evaluation created.
- (j) Polyol trigger food selected → R14 `cannot_assess` stating no commercial enzyme exists; no enzyme is ever suggested for it.

**Unit tests per rule**, table-driven, one file per rule.

**Property tests:** verdict monotonicity (lowering recipe pH never improves R1; moving an enzyme from wet to dry never worsens R4); aggregation ordering (`red` > `cannot_assess` > `amber` > `pass`); advisory rules R8–R10 can never change the overall flag; snapshot reproducibility (same input snapshot + engine version → byte-identical evaluation); editing a source record never mutates a stored evaluation.

**Contract test:** applying any auto-variant patch yields a formulation that re-evaluates without error.

**E2E (Playwright):** build recipe → evaluate → apply variant → compare → export report.

# 14. Milestones

- **M1 — Engine + seed (week 1):** schema, seed JSONs from the founder's documents, R1–R14, dosing, GI model, aggregation, golden fixtures green.
- **M2 — API + core UI (week 2):** recipe builder with custom ingredients and measured-pH entry, formulation setup, verdict screen with the GI strip and four headline states.
- **M3 — Variants, compare, DB editor, report (week 3):** auto-variants, side-by-side compare, proposals inbox, stale-evaluation banner, print report, Docker compose polish.
- **Exit check:** the founder builds her real vinaigrette and creamy candidates unassisted, gets verdicts matching the KB's §4m expectations, and exports a report she would hand to a supplier.

# 15. Open questions (tracked in-app as proposals; none block the build)

1. Acid-stable lactase and alpha-galactosidase variants, and their real pH-stability specs — the `ph_shelf_stable_min` field exists precisely to hold these answers. Suppliers: Amano and BIO-CAT are startup-friendly; Novonesis and IFF are the largest.
2. Fructan hydrolase sourcing and freedom-to-operate given US 10,820,599.
3. Inulinase, lipase, and xylose-isomerase dose benchmarks; per-enzyme temperature ranges; xylose isomerase activity at 37 °C.
4. Whether to break down inulin at all, given its prebiotic value — the founder's product-philosophy call; R9 keeps it visible on every affected formulation.
5. Encapsulation approach and supplier for the ready-to-eat format. **Prior art worth studying:** `US20240206516A1` (in `fwbackgroundmaterials/`, listed there as the Wyss patent; text verified via Google Patents) — "Systems and methods for sugar-reduction and/or fiber production for food and other applications." It claims enzyme particles held inactive by a reversibly-bound polyphenol inhibitor that dissociates above pH 3.5 at ionic strength ≥ 5 mmol/L, i.e. an enzyme that stays off in the product and switches on in the GI tract. Different goal (sugar → fiber conversion), same mechanism family as the founder's inert-in-jar / active-in-body problem, and a freedom-to-operate consideration if she pursues inhibitor-particle encapsulation.
6. Ingredient-level pH values for the starter catalog (§9) — measurement or supplier data, whichever comes first.
