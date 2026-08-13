---
title: MVP Product and Technical Specification — AI-Centric Food Formulation and Manufacturability Virtual Lab
version: 0.1
date_created: 2026-08-13
last_updated: 2026-08-13
owner: Product / Applied Food Science
status: Proposed for implementation
 tags: [food-formulation, manufacturability, virtual-lab, optimization, AI, MVP]
---

# 1. Executive Summary

## Problem
Food scientists and process developers need to compare formulation alternatives, understand trade-offs, and decide which bench experiments to run. A general-purpose recipe chatbot is not sufficient: it lacks explicit mass balance, measurable targets, traceable assumptions, process constraints, uncertainty, and a handoff-ready experiment record.

## Recommendation
Build an evidence-backed **formulation workbench**, initially for **shelf-stable tomato-based pasta/pizza sauce**. The MVP accepts a constrained ingredient set, a single defined process, target ranges, and ingredient evidence; it produces deterministic formulation calculations, constraint checks, a transparent trade-off/optimization result, one scientifically meaningful stability model, and a ranked five-run experiment plan. Every result is labelled as calculated, modelled, retrieved, or speculative and can be exported as a scientist-reviewable experiment packet.

## Why sauce first
Sauce is preferred over beverage for the first vertical because it offers:

- Clear, measurable formulation variables: solids, pH/acidification, salt, sugar, water, oil, and viscosity proxy.
- A manageable thermal process with meaningful process constraints.
- Useful public data coverage for composition and ingredients.
- A credible path to a scientifically meaningful predictive component (growth/no-growth or shelf-stability proxy) without claiming regulatory validation.
- More room to demonstrate manufacturability than a recipe-only beverage prototype.

**Important boundary:** the MVP is a decision-support and experiment-planning system. It does not certify safety, shelf life, regulatory compliance, sensory acceptability, or production readiness.

## MVP success criteria
1. A scientist can create a formulation and obtain a reproducible, auditable calculation in under 10 minutes.
2. 100% of displayed calculated values have formula, units, input provenance, and a visible status label.
3. The system rejects or clearly flags infeasible formulations rather than silently presenting them as solutions.
4. At least 4 of 5 domain-expert reviewers judge the generated five-run plan useful enough to execute or refine.
5. On a fixed benchmark of hand-calculated formulations, mass-balance and target calculations match within defined tolerances (mass: ±0.01%; concentration: ±0.1 percentage points).

# 2. Scope and Non-Goals

## 2.1 Exact MVP boundaries

### Product class
- One class: shelf-stable tomato-based sauce.
- One batch basis: nominal 1,000 g finished batch.
- One process template: ingredient weigh-up → mix/hydrate → heat treatment → fill/cool. Parameters are configurable but the process topology is fixed.
- One formulation workspace at a time; local single-user deployment is acceptable.

### Ingredients
- 8–12 ingredient records in a seeded catalog, with a hard default maximum of 12 active ingredients per formulation.
- Recommended seed set: tomato puree, tomato paste, water, sugar, salt, vegetable oil, onion powder, garlic powder, citric acid, modified starch, black pepper, and dried herb blend.
- User may create custom ingredients, but custom properties must be explicitly marked user-provided and cannot silently inherit scientific evidence.

### Targets and constraints
- 3–5 measurable targets per formulation. Recommended default targets:
  - pH target/range
  - soluble solids (°Brix) target/range
  - salt mass fraction target/range
  - finished viscosity proxy or solids proxy
  - minimum/maximum process temperature or hold time
- Hard constraints: total mass, ingredient bounds, non-negativity, process bounds, and required ingredient presence.
- Soft objectives: target deviation and cost proxy, with explicit weighting.

### Experiments
- Exactly five recommended experiments in the MVP plan.
- Each run changes a limited number of factors and includes predicted values, rationale, uncertainty, and fields for actual observations.
- No automatic lab-instrument integration.

### AI and modelling
- Retrieval: source-linked ingredient/property lookup and evidence snippets.
- Deterministic calculations: mass balance, weighted composition, target deviations, feasibility, and cost proxy.
- One scientifically meaningful model: a transparent empirical growth/no-growth or stability-risk proxy using pH, water-activity proxy/solids, salt, and process temperature/time where data supports it. It must be labelled **modelled**, expose assumptions, and never be phrased as a safety guarantee.
- Active learning / design of experiments (DoE): select five runs to maximize coverage and information gain around feasible candidates. This is a recommendation heuristic, not proof of optimality.
- LLM: optional interface for explaining results and mapping natural language into structured inputs. The LLM must not be the source of numeric truth.

## 2.2 Explicitly out of scope
- Multi-product platform, beverages, dairy, meat, bakery, emulsions, or fermentation.
- Full sensory prediction, flavor chemistry, texture simulation, rheology model, or consumer preference model.
- Regulatory certification, HACCP plan generation, pathogen validation, challenge-study replacement, or legal claims.
- Guaranteed shelf-life prediction, microbial species-level risk assessment, or production release approval.
- CFD, heat-transfer simulation, industrial line balancing, packaging compatibility, or scale-up equivalence.
- Automatic procurement, supplier qualification, inventory, ERP/MES integration, or purchasing decisions.
- Autonomous formulation changes or unattended experiment execution.
- Training a foundation model or building a generalized food ontology.

# 3. Personas and User Stories

## Personas
- **Formulation scientist:** specifies ingredients and targets, compares candidates, and chooses bench runs.
- **Process/manufacturing scientist:** checks process bounds, mass balance, and manufacturability flags.
- **Technical reviewer/manager:** reviews provenance, assumptions, uncertainty, and experiment handoff.

## User stories and acceptance criteria

### US-01 — Define a formulation
As a formulation scientist, I want to enter ingredient amounts and properties so that I can evaluate a candidate sauce batch.

- Given a 1,000 g batch basis, when ingredient quantities are entered, then the system shows total mass, percentage-by-mass, and remaining mass to allocate.
- The system prevents negative amounts and visibly flags totals that do not equal the batch basis.

### US-02 — Set measurable targets
As a scientist, I want to define target ranges and hard/soft status so that the system evaluates trade-offs rather than hiding them.

- Each target has name, value/range, unit, tolerance, priority, and source/assumption.
- A formulation can be infeasible; infeasibility is shown with the violated constraints and smallest available relaxation suggestion.

### US-03 — Review evidence
As a reviewer, I want to inspect where ingredient properties came from so that I can judge whether an output is trustworthy.

- Every retrieved property shows source, retrieval date, field-level confidence, and whether it was transformed.
- User-provided values cannot be displayed as authoritative external facts.

### US-04 — Compare candidates
As a scientist, I want to compare candidate formulations so that I can select a defensible trade-off.

- The comparison shows target deviations, cost proxy, ingredient deltas, feasibility, modelled stability-risk output, and uncertainty.
- Results are reproducible from a saved input snapshot and calculation version.

### US-05 — Plan five experiments
As a scientist, I want five ranked experiments so that I can learn efficiently from bench work.

- The plan includes factor values, predicted outputs, expected information gain/coverage rationale, and run order.
- The system never labels a run as guaranteed best or safe.

### US-06 — Record actual results and hand off
As a scientist, I want to record observed pH, °Brix, viscosity proxy, process conditions, and notes so that model predictions can be compared with reality.

- Actual observations are immutable after submission except through an auditable correction.
- Export contains formulation, process, targets, evidence, predictions, uncertainty, and blank/filled observation fields.

# 4. Functional Requirements

Priority definitions: **P0 = required for MVP**, **P1 = should have if low risk**, **P2 = post-MVP**.

| ID | Priority | Requirement |
|---|---:|---|
| FR-001 | P0 | Create, save, clone, and archive a formulation workspace. |
| FR-002 | P0 | Maintain a seeded ingredient catalog with units, composition properties, bounds, and provenance. |
| FR-003 | P0 | Support 8–12 active ingredients and a 1,000 g batch basis. |
| FR-004 | P0 | Compute mass fractions, weighted properties, target deviations, and cost proxy deterministically. |
| FR-005 | P0 | Validate units, ranges, missing values, mass balance, and process constraints. |
| FR-006 | P0 | Distinguish hard constraints from soft objectives and show infeasibility explicitly. |
| FR-007 | P0 | Retrieve source-linked evidence from USDA FoodData Central, Open Food Facts, PubChem, or a curated local evidence table where appropriate. |
| FR-008 | P0 | Preserve input snapshots, formulas/calculation version, source references, timestamp, and status labels. |
| FR-009 | P0 | Generate a transparent candidate ranking or constrained optimization result using SciPy and/or OR-Tools/PuLP. |
| FR-010 | P0 | Provide one documented stability-risk model with input coverage checks and uncertainty/assumption disclosure. |
| FR-011 | P0 | Generate exactly five experiment recommendations using bounded DoE/active-learning logic. |
| FR-012 | P0 | Record predicted and actual experiment observations with correction history. |
| FR-013 | P0 | Export a reviewable Markdown and JSON experiment packet. |
| FR-014 | P0 | Provide a human-readable explanation of each recommendation without allowing LLM-generated numbers to bypass the calculation engine. |
| FR-015 | P1 | Interactive Pareto-style comparison of cost versus target deviation. |
| FR-016 | P1 | Import/export formulation JSON for repeatability. |
| FR-017 | P1 | Local retrieval cache and offline operation after seed data is installed. |
| FR-018 | P2 | Multi-user authentication, permissions, cloud sync, supplier integrations, and instrument connectivity. |

# 5. Output Semantics: Truth Labels

Every value and recommendation must carry one of these labels:

- **Calculated:** derived from explicit inputs by deterministic formulas, e.g., total mass or weighted salt percentage.
- **Retrieved:** copied or normalized from a named external/curated source, e.g., ingredient composition field.
- **Modelled:** generated by a stated statistical/scientific model, e.g., stability-risk proxy.
- **Speculative:** heuristic, incomplete, or dependent on unsupported assumptions, e.g., likely sensory improvement or unverified supplier substitution.
- **Observed:** entered from a real experiment or instrument; never overwritten by a prediction.

The UI, exports, and LLM explanations must preserve these labels. “Safe,” “validated,” “production-ready,” and “shelf-stable” are prohibited conclusions unless supplied as externally verified evidence and clearly attributed.

# 6. Core Workflow

1. **Create project:** choose tomato sauce template and batch basis.
2. **Select ingredients:** choose from catalog; inspect property evidence and bounds.
3. **Enter formulation:** set quantities, process temperature/hold time, and optional cost proxies.
4. **Set targets:** choose 3–5 target ranges and classify hard versus soft.
5. **Validate:** calculate mass balance and show missing evidence, infeasible bounds, and unit errors.
6. **Evaluate:** run deterministic calculations and the stability-risk model only where required inputs are covered.
7. **Explore:** generate candidate alternatives within ingredient and process bounds; rank by transparent objective function.
8. **Plan experiments:** produce five bounded runs emphasizing feasibility, target coverage, and information gain.
9. **Review/handoff:** scientist edits/approves the plan, exports packet, and performs bench work.
10. **Log results:** record observed values and deviations; compare predicted versus observed performance.
11. **Learn:** update a local calibration dataset; MVP may display residuals but must not silently retrain or alter scientific coefficients.

# 7. Data Model

Use SQLite as the MVP system of record; JSON snapshots are exportable interchange formats.

| Entity | Key fields |
|---|---|
| Project | id, name, product_class, batch_basis_g, owner, status, created_at |
| Ingredient | id, name, category, default_unit, active, allergen_note, bounds |
| IngredientProperty | ingredient_id, property_name, value, unit, basis, source_id, confidence, status |
| Source | id, title, publisher, URL/identifier, retrieval_date, license/usage_note |
| Formulation | id, project_id, version, status, notes |
| FormulationComponent | formulation_id, ingredient_id, amount_g, amount_basis, user_override, provenance |
| Target | id, formulation_id, metric, lower, upper, unit, hard_or_soft, weight |
| ProcessProfile | id, formulation_id, step_order, operation, temperature_c, time_s, notes |
| Evaluation | id, formulation_id, calc_version, created_at, feasibility, objective_value |
| MetricResult | evaluation_id, metric, value, unit, status, formula_ref, uncertainty |
| ModelRun | evaluation_id, model_name, model_version, inputs_json, output_json, applicability, caveats |
| ExperimentPlan | id, formulation_id, method_version, rationale, approval_status |
| ExperimentRun | plan_id, sequence, factor_values_json, predicted_json, actual_json, status |
| Observation | experiment_run_id, metric, value, unit, instrument_or_method, observed_at, entered_by, correction_of |
| AuditEvent | actor, action, entity, entity_id, before_json, after_json, timestamp |

## Minimum JSON evaluation contract

```json
{
  "formulation_id": "f-001",
  "calc_version": "0.1.0",
  "status": "calculated",
  "batch_basis_g": 1000.0,
  "metrics": [
    {"name": "salt_mass_fraction", "value": 0.021, "unit": "fraction", "status": "calculated", "formula_ref": "weighted_mass_fraction_v1"}
  ],
  "constraints": [{"name": "pH_range", "passed": false, "reason": "pH evidence unavailable"}],
  "model_runs": [{"name": "stability_risk_proxy", "status": "modelled", "applicability": "partial", "caveats": ["not a safety validation"]}]
}
```

# 8. Architecture

## Recommended shape
A modular Python monolith with a thin web UI is preferable to microservices for the MVP.

- **Presentation:** Streamlit or a small React client; use forms and tables before investing in rich visual design.
- **Application layer:** workflow orchestration, validation, candidate generation, experiment planning, export.
- **Domain/calculation layer:** pure functions for mass balance, composition aggregation, target scoring, constraint evaluation, and unit normalization.
- **Model layer:** versioned stability-risk model with applicability and uncertainty checks.
- **Retrieval/evidence layer:** adapters for USDA FoodData Central, Open Food Facts, PubChem, and curated local records; cache normalized results.
- **Persistence:** SQLite plus SQLAlchemy or a thin repository layer; JSON export/import.
- **Optimization:** SciPy for bounded search; OR-Tools or PuLP if linear/mixed constraints justify it.
- **Optional AI layer:** Ollama/local model for structured input parsing and explanations. It calls typed application functions and receives calculation results; it does not write directly to SQLite.
- **Observability:** structured logs, calculation version, input snapshot, and audit events; no dependency on a hosted telemetry service.

## Dependency rule
UI and LLM adapters may call application services. Application services may call domain and ports. Domain calculations must not call external APIs, the LLM, or the database. Retrieval and persistence implementations sit behind interfaces so tests can use fixtures.

## Security and privacy
- Treat formulations and observations as confidential by default.
- No secrets or API keys in formulation exports or logs.
- Validate imported JSON and cap payload sizes.
- Use parameterized database queries.
- The local MVP may omit authentication, but the boundary must be documented before any multi-user deployment.

# 9. Validation and Test Strategy

## Deterministic correctness
- Unit tests for mass balance, weighted properties, unit conversions, bounds, target scoring, and infeasibility.
- Golden fixtures hand-calculated by a food scientist.
- Property-based tests for non-negative amounts, conservation of mass, permutation invariance, and monotonicity where expected.
- Tolerance policy: mass ±0.01%; concentration ±0.1 percentage points; cost proxy ±0.01 currency units in fixture tests.

## Scientific/model validation
- Version and freeze the model coefficients and feature definitions for MVP.
- Test applicability gates: missing pH/solids/salt/process inputs must yield “not applicable” or “partial,” not a confident score.
- Compare model output against a curated literature/benchmark fixture set; report calibration, false reassurance rate, and false alarm rate where labels exist.
- Domain expert review is mandatory before describing the model as scientifically meaningful.

## Retrieval validation
- Fixture tests for source parsing and normalization.
- Field-level provenance completeness ≥99% on seeded catalog.
- Manual review of all 8–12 seed ingredients.
- Detect stale, conflicting, or missing source values; never silently select a value when conflicts are material.

## DoE/experiment-plan validation
- Verify all five runs respect hard ingredient/process bounds.
- Verify at least one baseline/center run, at least one feasible boundary or stress run, and coverage across selected factors.
- Compare recommendation quality with a simple baseline (random feasible sampling); report expert preference and coverage metrics.

## End-to-end acceptance
A seeded project can be created, evaluated, exported, and re-imported without changing calculated outputs. A reviewer can trace every displayed numeric result to inputs, formula/model version, and source or observation.

# 10. Milestones

## M0 — Domain lock and evidence pack (1 week)
- Confirm sauce template, 8–12 ingredients, 3–5 targets, process profile, and terminology.
- Curate seed property records and sources.
- Define hand-calculated golden fixtures and model applicability rules.
- **Exit:** domain expert signs off on inputs and prohibited claims.

## M1 — Calculation kernel and data model (1–2 weeks)
- SQLite schema, ingredient/evidence records, unit normalization, mass balance, target calculations, constraint engine.
- **Exit:** golden fixtures pass; persisted snapshots reproduce outputs.

## M2 — Workbench and evidence UI (1–2 weeks)
- Formulation editor, target editor, source display, validation messages, saved versions.
- **Exit:** scientist completes US-01–US-03 in usability walkthrough.

## M3 — Candidate evaluation, model, and experiment plan (2 weeks)
- Bounded optimizer/search, stability-risk proxy, five-run DoE/active-learning planner, truth labels.
- **Exit:** all outputs disclose status, assumptions, and applicability; no unsafe claims in scripted review.

## M4 — Experiment log, export, and verification (1 week)
- Observations, audit corrections, Markdown/JSON packet, regression suite, expert review.
- **Exit:** five reviewers score usefulness; go/no-go criteria met.

## Post-MVP v1.1
- Better Pareto visualization, more process templates, calibration from observed runs under explicit approval, optional instrument import, and stronger access control.

# 11. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Public composition data does not match supplier-specific materials | Misleading calculated values | Show source/basis, allow user overrides, propagate uncertainty, require confirmation for critical fields. |
| Stability model overclaims safety | Severe scientific and reputational risk | Applicability gates, conservative language, domain review, explicit “not validation” banner. |
| Sparse data makes active learning appear more rigorous than it is | Poor experiment choices | Compare to random/baseline plans; label heuristic; require scientist approval. |
| LLM invents ingredients, properties, or conclusions | Traceability failure | Typed schemas, deterministic engine, source-linked retrieval, output linting, no direct DB writes. |
| Scope expands into a general food platform | Schedule failure | Enforce one class, one process, five runs, 12 ingredients, and explicit non-goals. |
| Optimization finds mathematically valid but impractical recipes | Manufacturing failure | Ingredient bounds, process constraints, required-presence rules, practical review flags, scientist approval. |
| Dataset/licensing or API availability changes | Reproducibility failure | Cache source snapshots/identifiers, maintain curated local seed pack, record license notes. |

# 12. Go / No-Go Criteria

## Go to MVP build
- Product class, seed ingredients, process template, targets, and prohibited claims are signed off.
- At least 8 seed ingredients have reviewed evidence records and explicit fallback values or “unknown” status.
- Golden calculation fixtures exist.
- A domain expert agrees the stability model is appropriately framed as a proxy and identifies acceptable use conditions.

## Go to expert pilot
All of the following must be true:
- Mass-balance and calculation benchmark passes tolerance.
- No P0 defects in provenance, unit handling, constraint enforcement, or export/re-import.
- Five-run plans satisfy all hard constraints in 100% of test cases.
- Model refuses unsupported cases and displays caveats.
- At least 4/5 reviewers rate the workflow useful (≥4 on a 5-point usefulness scale).
- No reviewer interprets the output as regulatory or safety certification after scripted comprehension testing.

## No-go / stop conditions
- Any path presents a modelled stability result as proof of safety or shelf life.
- Numeric outputs cannot be traced to a source, input, formula, observation, or model version.
- The optimizer silently relaxes hard constraints or changes user inputs.
- The system recommends experiments outside ingredient/process bounds.
- Domain reviewers cannot agree on the meaning or acceptable use of the selected model.
- The team cannot maintain the one-class/one-process boundary.

# 13. Open Decisions

1. Confirm whether the first sauce is acidified tomato sauce, pasta sauce, or pizza sauce; select one canonical target profile.
2. Choose the exact stability-risk formulation: literature-backed empirical model, ComBase-compatible model, or a simpler conservative proxy if inputs are insufficient.
3. Decide whether °Brix and pH are user-entered ingredient properties, predicted weighted proxies, or only finished-product observations in MVP.
4. Select Streamlit versus React based on intended pilot audience and expected UI investment.
5. Establish currency and supplier basis for cost proxy; cost must remain a soft objective.
6. Define the expert reviewer panel and benchmark fixture ownership.
7. Confirm licensing and permitted caching of each external data source.

# 14. Product Positioning Statement

The MVP is an **auditable formulation and experiment-planning workbench** that helps food scientists decide what to test next. It is not an autonomous recipe generator, a digital twin of a factory, or a safety-certification engine. Its defensibility comes from explicit assumptions, reproducible calculations, evidence provenance, constrained search, and a clean scientist handoff—not from fluent AI prose.
