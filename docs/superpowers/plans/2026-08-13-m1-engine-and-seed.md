# M1 — Engine + Seed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the pure-Python rules engine (R1–R16), its seed data catalogue, and the SQLite schema, so that a formulation can be evaluated into a verdict and the spec's golden fixtures pass against the real shipped seed data.

**Architecture:** `engine/` is a pure functional core — plain frozen dataclasses in, `RuleFinding` objects out. No database, no HTTP, no file I/O anywhere inside it. Seed data lives as versioned JSON in `seed/`, loaded by a validating loader into domain objects. A separate `db/` module owns the SQLite schema and bootstrap, which M2's API will use; the engine never imports it. Every numeric field is a `Tracked` value carrying its own truth label and source, which is the single mechanism that makes "any rule reading unconfirmed data returns `cannot_assess`" work uniformly across all sixteen rules.

**Tech Stack:** Python 3.12, pytest, hypothesis (property tests), ruff (lint + format), stdlib `sqlite3`, Docker.

**Spec:** `docs/superpowers/specs/2026-08-13-enzyme-rules-engine-design.md` — read §5 (data model), §6 (rules), §8 (GI model), §9 (seed data), §13 (testing) before starting.

---

## Spec deviations this plan resolves

Found while tracing the spec's own fixtures/tests against its own rule text. Implement as described here; flag to the spec owner at M1 review.

**1. Fixture (b) says "R1 pass" but R1's rule text produces AMBER.** R1 (§6.1) states: "within range but outside `ph_opt` → AMBER (sluggish, recoverable)". Fungal lactase has `ph_opt` 5.0; fixture (b) supplies recipe pH 4.4, which is inside the 2.5–5.4 activity range but below optimum. By the rule text that is AMBER, not pass. **This plan implements the rule text and asserts R1 = AMBER in fixture (b).** The fixture's headline assertion is unaffected — R1 AMBER, R4 AMBER, R8 AMBER still aggregate to AMBER — so KB §4m's three-tier heuristic is still reproduced. Changing R1 instead would require inventing an unsourced tolerance band around the optimum.

**2. "Golden fixtures run against the real shipped seed catalog" needs a stated boundary.** Fixtures (a) and (b) already supply recipe pH as an "explicit test input", because every seeded food pH is `unconfirmed` (§9.3). The same is true of trigger-food substrate loads, which R7 needs. **Fixtures therefore supply `measured_ph` and per-food `typical_load_value` as explicit `user_provided` test inputs, and take everything else — every enzyme record in particular — from the real shipped seed.** This preserves what the "real seed catalog" instruction was protecting against (the R12 class of bug, where a rule silently reads unconfirmed enzyme data), while letting fixtures assert anything at all. Fixture (m) additionally uses one synthetic enzyme record, as §6.3.1 requires.

**3. Task 12's own R2 unit test says "lactase passes" but R2's rule text, run against the real seeded GI model, produces AMBER.** Fungal lactase's pH range (2.5–5.4) is tested with deadline `BEFORE_SMALL_INTESTINE`, i.e. against the region set `{mouth, stomach_fasting, stomach_fed}`. `mouth` is dormant (excluded). `stomach_fasting` is pH 1.5–2.0 in the real `seed/gi_model.json` — it does not overlap 2.5–5.4. Only `stomach_fed` (pH 4.0–6.0) overlaps, i.e. exactly one active region before the deadline, which R2's own Step-3 logic (`elif len(active_before) == 1: AMBER`) correctly classifies as AMBER, not PASS — the same "single narrow window, little margin" case the rule text is written to catch. **This plan implements R2's rule text unchanged and corrects the test to assert AMBER** (renamed `test_lactase_amber_with_single_region_coverage`), mirroring deviation #1: the plan's literal rule logic is the source of truth over a test assertion written assuming two-region coverage the real seed doesn't provide. No golden fixture (a)–(q) asserts R2 for fungal lactase specifically, so no downstream fixture is affected.

**4. Task 27's golden fixtures, run against the real shipped seed, surfaced that R2/R7/R11 needed the same per-field advisory treatment §6.1 already gives R12 — as originally written in Tasks 12/17/19 they didn't have it.** R12 (temperature) was deliberately made advisory-by-default with per-enzyme promotion because every enzyme's temperature fields seed unconfirmed; a headline-capable R12 would GRAY every formulation regardless of merit. Running fixture (b) and (l) exposed that the *exact same failure shape* exists for three more headline-capable rules, just triggered by different static fields: R7's `dose_evidence_threshold` is unconfirmed for 11 of the 12 shipped enzymes (only `alpha_galactosidase` is sourced); R11's `is_gras` is unconfirmed for 10 of 12; R2's `ph_min`/`ph_max` is unconfirmed for 6 of 12 (including `cellulase`, fixture (l)'s enzyme). Left as originally specified, almost any formulation using almost any enzyme other than the two most-complete ones would show GRAY out of the box. **This plan makes exactly one CANNOT_ASSESS branch per rule advisory — the one caused by the enzyme's own permanently-unconfirmed static catalogue field — while every other CANNOT_ASSESS branch in R2/R7/R11 stays headline-capable, including the per-formulation gaps a real user can fix (missing food load, missing dose, missing process steps).** `test_h_headline_capable_cannot_assess_does_gray_the_headline` (Task 27) is the existing, still-passing proof that formulation-caused R7 CANNOT_ASSESS is meant to gray the headline — this deviation does not touch that path. Confirmed with the founder-side stakeholder before implementing, given the product-behavior impact (this determines whether the flagship lactase/dairy and most other real formulations resolve to a useful verdict or a blanket GRAY). Flag to the spec owner at M1 review: §6.1 should document this exception for R2/R7/R11 the same way it already documents it for R12.

**5. Three golden fixtures ((b), (h), (l), (p0)) were missing test setup the rule set actually needs, independent of deviation #4.** (h) and (p0) never supplied `process_steps`/`enzyme_addition_index`, so R3 (no-heat) — a headline-capable rule with no advisory exception — legitimately CANNOT_ASSESSed and grayed fixtures that were meant to isolate R12's and R16's advisory behavior. (b) never supplied a `with_load` for milk, so R7 CANNOT_ASSESSed on the food-level load before ever reaching the (also-unconfirmed, now-advisory per deviation #4) `dose_evidence_threshold` branch. (l) was missing both the process-steps and, transitively, benefited from deviation #4 for its cellulase pH-range and GRAS gaps. All three are corrected by supplying the missing test input (mirroring the pattern already used in fixtures (a)/(c)/(d)/(e)), not by changing any expected output — this is fixture completeness, not a rule-text-vs-fixture conflict like deviations #1/#3.

---

## File structure

```
foodbrew/
├── pyproject.toml                       # deps, pytest + ruff config
├── Dockerfile                           # python:3.12-slim, installs package
├── docker-compose.yml                   # bind-mounts ./data → /data
├── seed/
│   ├── substrates.json                  # 12 substrate records
│   ├── gi_model.json                    # 6 GI regions
│   ├── enzymes.json                     # 12 enzyme records
│   └── foods.json                       # ~45 role-flagged food records
├── src/foodbrew/
│   ├── __init__.py                      # ENGINE_VERSION
│   ├── engine/
│   │   ├── __init__.py                  # public API: evaluate()
│   │   ├── types.py                     # Tracked, TruthLabel, Verdict, RuleFinding, EvalContext, entities
│   │   ├── conventions.py               # §6.7: wet ingredient, load aggregation, pH resolution
│   │   ├── gi_model.py                  # active-window computation per GI region
│   │   ├── dosing.py                    # R7 dose maths
│   │   ├── texture.py                   # §6.3.1 severity table, occasion envelope, dwell bucketing
│   │   ├── trial_rules.py               # confidence tier, ambient-storage gate (pure; M4 consumes)
│   │   ├── flags.py                     # §6.4 aggregation + format recommendation
│   │   ├── evaluate.py                  # orchestrator: EvalContext → Evaluation
│   │   └── rules/
│   │       ├── __init__.py              # ordered rule registry
│   │       ├── r01_ph_survival.py       … one module per rule through r16_clean_label.py
│   ├── seedload/
│   │   ├── __init__.py
│   │   └── loader.py                    # JSON → domain objects, validating
│   └── db/
│       ├── __init__.py
│       ├── schema.sql                   # §5 tables
│       └── bootstrap.py                 # create db, populate from seed
└── tests/
    ├── conftest.py                      # fixture builders
    ├── test_seed_integrity.py
    ├── engine/test_*.py                 # one file per rule + conventions/texture/flags
    ├── test_golden_fixtures.py          # §13 (a)–(q)
    ├── test_properties.py               # §13 property tests
    └── test_db_bootstrap.py
```

**Boundary rule to enforce in review:** nothing under `src/foodbrew/engine/` may import `sqlite3`, `json`, `pathlib`, or anything from `foodbrew.db` / `foodbrew.seedload`. Task 26 adds a test that asserts this.

---

## Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `src/foodbrew/__init__.py`
- Create: `tests/__init__.py`
- Create: `.gitignore` (append)

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "foodbrew"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8.0", "hypothesis>=6.100", "ruff>=0.5"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q --strict-markers"

[tool.ruff]
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

- [ ] **Step 2: Create the package entry point**

`src/foodbrew/__init__.py`:

```python
"""FoodBrew — enzyme formulation rules engine."""

# Bumped manually whenever rule logic changes in a way that alters verdicts.
# Stored on every evaluation so a stored snapshot can be re-run reproducibly.
ENGINE_VERSION = "1.0.0"
```

- [ ] **Step 3: Create an empty test package**

`tests/__init__.py`: empty file.

- [ ] **Step 4: Install and verify**

Run: `python3 -m venv .venv && .venv/bin/pip install -e '.[dev]' -q && .venv/bin/pytest --version`
Expected: pytest version prints, no errors.

- [ ] **Step 5: Append to `.gitignore`**

```
.venv/
*.egg-info/
.pytest_cache/
.ruff_cache/
```

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/foodbrew/__init__.py tests/__init__.py .gitignore
git commit -m "chore: scaffold foodbrew package with pytest and ruff"
```

---

## Task 2: Core types

Everything downstream depends on these. `Tracked` is the mechanism that makes unconfirmed data propagate to `cannot_assess` automatically.

**Files:**
- Create: `src/foodbrew/engine/__init__.py`
- Create: `src/foodbrew/engine/types.py`
- Test: `tests/engine/test_types.py`

- [ ] **Step 1: Write the failing test**

Create `tests/engine/__init__.py` (empty) and `tests/engine/test_types.py`:

```python
import pytest

from foodbrew.engine.types import RuleFinding, Tracked, TruthLabel, Verdict, worst


def test_tracked_confirmed_is_usable():
    t = Tracked(value=2.5, status=TruthLabel.CONFIRMED, source="KB Table B")
    assert t.usable is True


def test_tracked_unconfirmed_is_not_usable():
    t = Tracked(value=None, status=TruthLabel.UNCONFIRMED, source="")
    assert t.usable is False


def test_tracked_with_value_but_unconfirmed_is_still_not_usable():
    # A seeded estimate is not evidence. Status decides, not presence of a number.
    t = Tracked(value=4.0, status=TruthLabel.UNCONFIRMED, source="estimate")
    assert t.usable is False


@pytest.mark.parametrize(
    "label", [TruthLabel.CONFIRMED, TruthLabel.USER_PROVIDED, TruthLabel.OBSERVED]
)
def test_all_evidence_labels_are_usable(label):
    assert Tracked(value=1.0, status=label, source="x").usable is True


def test_worst_orders_red_above_cannot_assess_above_amber_above_pass():
    assert worst([Verdict.PASS, Verdict.AMBER]) is Verdict.AMBER
    assert worst([Verdict.AMBER, Verdict.CANNOT_ASSESS]) is Verdict.CANNOT_ASSESS
    assert worst([Verdict.CANNOT_ASSESS, Verdict.RED]) is Verdict.RED
    assert worst([]) is Verdict.PASS


def test_rule_finding_is_frozen():
    f = RuleFinding(rule_id="R1", verdict=Verdict.RED, message="m", evidence={})
    with pytest.raises(Exception):
        f.verdict = Verdict.PASS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/engine/test_types.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'foodbrew.engine'`

- [ ] **Step 3: Write the implementation**

`src/foodbrew/engine/__init__.py`: empty for now (Task 24 adds the public `evaluate` re-export).

`src/foodbrew/engine/types.py`:

```python
"""Core value types for the rules engine. Pure — no I/O, no persistence."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class TruthLabel(str, Enum):
    """Spec §5.4. Closed enum — no other token may appear in seed, API, or UI."""

    CONFIRMED = "confirmed"
    UNCONFIRMED = "unconfirmed"
    USER_PROVIDED = "user_provided"
    CALCULATED = "calculated"
    OBSERVED = "observed"


#: Labels that count as evidence a rule may act on. UNCONFIRMED never does;
#: CALCULATED is an engine output and is never a rule *input*.
_EVIDENCE_LABELS = frozenset(
    {TruthLabel.CONFIRMED, TruthLabel.USER_PROVIDED, TruthLabel.OBSERVED}
)


class Verdict(str, Enum):
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


class DwellProfile(str, Enum):
    """Spec §6.3."""

    IMMEDIATE = "immediate"
    PACKED = "packed"
    MARINADE = "marinade"


class StructuralClass(str, Enum):
    """Spec §5.1 food.structural_json / enzyme.degrades_structural_json."""

    PECTIN_CELLULOSE = "pectin_cellulose"
    STRUCTURAL_PROTEIN = "structural_protein"
    STARCH = "starch"


class SeverityTier(str, Enum):
    """Spec §6.3.1."""

    RAPID = "rapid"
    GRADUAL = "gradual"
    UNCONFIRMED = "unconfirmed"


class Format(str, Enum):
    """Spec §5.2 formulation.format."""

    PREMIXED_WET = "premixed_wet"
    DRY_SACHET = "dry_sachet"
    DUAL_CHAMBER = "dual_chamber"
    ENCAPSULATED_IN_WET = "encapsulated_in_wet"


class Phase(str, Enum):
    """Which side of the pack an enzyme sits on."""

    WET = "wet"
    DRY = "dry"


class Deadline(str, Enum):
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/engine/test_types.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/engine/ tests/engine/
git commit -m "feat(engine): add core types with truth-label gating"
```

---

## Task 3: Domain entities

**Files:**
- Modify: `src/foodbrew/engine/types.py` (append)
- Test: `tests/engine/test_entities.py`

- [ ] **Step 1: Write the failing test**

`tests/engine/test_entities.py`:

```python
from foodbrew.engine.types import (
    Deadline,
    Enzyme,
    EvalContext,
    Food,
    Format,
    Formulation,
    Phase,
    ProcessStep,
    RecipeIngredient,
    SelectedEnzyme,
    Substrate,
    Tracked,
    TruthLabel,
)


def _t(v, status=TruthLabel.CONFIRMED):
    return Tracked(value=v, status=status, source="test")


def test_enzyme_holds_tracked_fields():
    e = Enzyme(
        id="lactase_fungal_acid",
        name="Lactase (fungal, acid)",
        substrate_id="lactose",
        source_type="fungal",
        priority="high",
        deadline=Deadline.BEFORE_SMALL_INTESTINE,
        ph_min=_t(2.5),
        ph_max=_t(5.4),
        ph_opt_low=_t(5.0),
        ph_opt_high=_t(5.0),
        ph_shelf_stable_min=Tracked(None, TruthLabel.UNCONFIRMED),
        dose_unit="FCC",
    )
    assert e.ph_min.value == 2.5
    assert e.ph_shelf_stable_min.usable is False
    assert e.is_protease is False
    assert e.degrades_structural == ()


def test_food_role_flags_default_false():
    f = Food(id="romaine", name="Romaine", category="green")
    assert f.is_recipe_ingredient is False
    assert f.is_application_food is False
    assert f.structural == ()


def test_eval_context_indexes_by_id():
    e = Enzyme(
        id="e1", name="E", substrate_id="lactose", source_type="fungal",
        priority="high", deadline=Deadline.BEFORE_COLON,
        ph_min=_t(3.0), ph_max=_t(7.0), ph_opt_low=_t(5.0), ph_opt_high=_t(5.0),
        ph_shelf_stable_min=Tracked(None, TruthLabel.UNCONFIRMED), dose_unit="FCC",
    )
    f = Food(id="milk", name="Milk", category="dairy")
    s = Substrate(id="lactose", name="Lactose")
    form = Formulation(
        id="f1",
        format=Format.PREMIXED_WET,
        recipe=(RecipeIngredient(food_id="milk", amount_g=100.0),),
        enzymes=(SelectedEnzyme(enzyme_id="e1", dose=9000.0, phase=Phase.WET),),
    )
    ctx = EvalContext(
        formulation=form, enzymes={"e1": e}, foods={"milk": f}, substrates={"lactose": s}
    )
    assert ctx.enzymes["e1"].name == "E"
    assert ctx.selected_enzymes()[0].enzyme_id == "e1"
    assert ctx.enzyme_for(ctx.selected_enzymes()[0]).id == "e1"


def test_process_step_ordering_and_heat_flag():
    steps = (
        ProcessStep(order=1, label="Blend base", is_heat=False),
        ProcessStep(order=2, label="Pasteurise", is_heat=True),
    )
    form = Formulation(
        id="f2", format=Format.PREMIXED_WET, recipe=(), enzymes=(),
        process_steps=steps, enzyme_addition_index=1,
    )
    assert [s.order for s in form.process_steps] == [1, 2]
    assert form.enzyme_addition_index == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/engine/test_entities.py -v`
Expected: FAIL — `ImportError: cannot import name 'Enzyme'`

- [ ] **Step 3: Append the entities to `types.py`**

Append to `src/foodbrew/engine/types.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/engine/test_entities.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/engine/types.py tests/engine/test_entities.py
git commit -m "feat(engine): add domain entities for enzymes, foods, formulations"
```

---

## Task 4: Seed — substrates and GI model

**Files:**
- Create: `seed/substrates.json`
- Create: `seed/gi_model.json`

- [ ] **Step 1: Create `seed/substrates.json`**

From spec §9.2. `is_prebiotic` drives R9; `no_commercial_enzyme` drives R14.

```json
{
  "$comment": "Spec §9.2. Source: Formulation Knowledge Base §3 substrate-to-food map.",
  "substrates": [
    {"id": "lactose", "name": "Lactose", "native_human_enzyme": true, "is_prebiotic": false, "no_commercial_enzyme": false, "notes": "Body's own lactase commonly declines by adulthood."},
    {"id": "gos", "name": "GOS (raffinose, stachyose)", "native_human_enzyme": false, "is_prebiotic": true, "no_commercial_enzyme": false, "notes": "No native human enzyme — hard colon deadline."},
    {"id": "inulin_fructan", "name": "Inulin-type fructans", "native_human_enzyme": false, "is_prebiotic": true, "no_commercial_enzyme": false, "notes": "No native human enzyme. Garlic and onion carry more short-chain fructans than inulin."},
    {"id": "graminan_fructan", "name": "Graminan-type fructans", "native_human_enzyme": false, "is_prebiotic": true, "no_commercial_enzyme": false, "notes": "Wheat, barley, rye."},
    {"id": "excess_fructose", "name": "Excess fructose", "native_human_enzyme": false, "is_prebiotic": false, "no_commercial_enzyme": false, "notes": "Absorbed via a narrower fructose-only pathway."},
    {"id": "polyol", "name": "Polyols (sorbitol, mannitol)", "native_human_enzyme": false, "is_prebiotic": false, "no_commercial_enzyme": true, "notes": "No commercial enzyme exists. KB Table A: limited / under development."},
    {"id": "protein", "name": "Dietary protein", "native_human_enzyme": true, "is_prebiotic": false, "no_commercial_enzyme": false, "notes": "Pepsin plus pancreatic proteases already digest protein thoroughly — supplementing is additive."},
    {"id": "fat", "name": "Dietary fat", "native_human_enzyme": true, "is_prebiotic": false, "no_commercial_enzyme": false, "notes": "Lingual, gastric and pancreatic lipase already cover most fat digestion."},
    {"id": "sucrose", "name": "Sucrose", "native_human_enzyme": true, "is_prebiotic": false, "no_commercial_enzyme": false, "notes": ""},
    {"id": "starch", "name": "Starch", "native_human_enzyme": true, "is_prebiotic": false, "no_commercial_enzyme": false, "notes": ""},
    {"id": "fiber", "name": "Insoluble fiber", "native_human_enzyme": false, "is_prebiotic": true, "no_commercial_enzyme": false, "notes": ""},
    {"id": "pectin", "name": "Pectin", "native_human_enzyme": false, "is_prebiotic": true, "no_commercial_enzyme": false, "notes": ""}
  ]
}
```

- [ ] **Step 2: Create `seed/gi_model.json`**

From spec §8. `dormant` on the mouth encodes "dwell is seconds — all enzymes effectively dormant regardless of pH fit", which R2 needs.

```json
{
  "$comment": "Spec §8. Source: Enzyme Site of Action deck (08.07.2026), slides 2 and 3.",
  "regions": [
    {"id": "mouth", "name": "Mouth", "ph_low": 6.2, "ph_high": 7.6, "order": 1, "dormant": true, "transit_note": "Dwell is seconds — too brief for any enzyme to react regardless of pH fit."},
    {"id": "stomach_fasting", "name": "Stomach, fasting", "ph_low": 1.5, "ph_high": 2.0, "order": 2, "dormant": false, "transit_note": "Only acid-tolerant enzymes are active before food buffers the pH up."},
    {"id": "stomach_fed", "name": "Stomach, after eating", "ph_low": 4.0, "ph_high": 6.0, "order": 3, "dormant": false, "transit_note": "The main workhorse zone. Food buffers pH up, then it drifts back down over roughly two hours."},
    {"id": "duodenum", "name": "Duodenum", "ph_low": 6.0, "ph_high": 6.5, "order": 4, "dormant": false, "transit_note": "Fungal lactase has dropped out above its 5.4 ceiling; inulinase is fading."},
    {"id": "jejunum_ileum", "name": "Jejunum / ileum", "ph_low": 7.0, "ph_high": 7.5, "order": 5, "dormant": false, "transit_note": "Xylose isomerase's prime window."},
    {"id": "colon", "name": "Colon", "ph_low": 5.5, "ph_high": 7.0, "order": 6, "dormant": false, "transit_note": "Too late — undigested substrate is fermented here, which is the symptom mechanism."}
  ]
}
```

- [ ] **Step 3: Verify both files are valid JSON**

Run: `python3 -c "import json;[json.load(open(f)) for f in ['seed/substrates.json','seed/gi_model.json']];print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add seed/substrates.json seed/gi_model.json
git commit -m "feat(seed): add substrate map and GI model from founder documents"
```

---

## Task 5: Seed — enzymes

Spec §9.1. Every value that no source document states seeds `unconfirmed` — that is the point, not an omission.

**Files:**
- Create: `seed/enzymes.json`

- [ ] **Step 1: Create `seed/enzymes.json`**

Field convention: tracked fields are objects `{"value": …, "status": …, "source": …}`; plain fields are scalars.

```json
{
  "$comment": "Spec §9.1. pH ranges from KB Table B and Site-of-Action slide 1. All temperature fields and all ph_shelf_stable_min fields seed unconfirmed: no source document provides them.",
  "enzymes": [
    {
      "id": "lactase_fungal_acid",
      "name": "Lactase (fungal, acid)",
      "aliases": ["beta-galactosidase"],
      "substrate_id": "lactose",
      "source_type": "fungal",
      "priority": "high",
      "deadline": "before_small_intestine",
      "site_of_action": "Active in the fed stomach; drops out at the duodenum above its 5.4 ceiling (Site-of-Action slide 3).",
      "ph_min": {"value": 2.5, "status": "confirmed", "source": "KB Table B; Site-of-Action slide 1"},
      "ph_max": {"value": 5.4, "status": "confirmed", "source": "KB Table B; Site-of-Action slide 1"},
      "ph_opt_low": {"value": 5.0, "status": "confirmed", "source": "KB Table B"},
      "ph_opt_high": {"value": 5.0, "status": "confirmed", "source": "KB Table B"},
      "ph_shelf_stable_min": {"value": null, "status": "unconfirmed", "source": "No source gives a sustained-exposure floor. R1 applies its stated fallback margin."},
      "temp_min_c": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_max_c": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_opt_c": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_unit": "FCC",
      "dose_min": {"value": 900, "status": "confirmed", "source": "KB Table B"},
      "dose_max": {"value": 18000, "status": "confirmed", "source": "KB Table B"},
      "dose_evidence_threshold": {"value": null, "status": "unconfirmed", "source": "No independent full-dose threshold published for lactase in the source set."},
      "dose_benchmark_note": "Lactaid Fast Act 9,000 FCC per chewable tablet. Suggested 3,000-6,000 FCC for a 0-6 g lactose serving, 6,000-9,000 for 6-12 g, 9,000-15,000+ above 12 g.",
      "is_protease": false,
      "is_natural_source": false,
      "is_gras": {"value": true, "status": "confirmed", "source": "KB §4l — lactase largely already GRAS"},
      "degrades_structural": [],
      "notes": "Sunson supplier spec lists a broader 3.0-8.0 activity range with optimum 3.5-5.0; treated as a looser 'still shows some activity' claim, not a sustained-stability figure."
    },
    {
      "id": "lactase_yeast_neutral",
      "name": "Lactase (yeast, neutral)",
      "aliases": [],
      "substrate_id": "lactose",
      "source_type": "yeast",
      "priority": "high",
      "deadline": "before_small_intestine",
      "site_of_action": "",
      "ph_min": {"value": null, "status": "unconfirmed", "source": "Stub record — KB §4k names the acid+neutral pairing but gives no range."},
      "ph_max": {"value": null, "status": "unconfirmed", "source": ""},
      "ph_opt_low": {"value": null, "status": "unconfirmed", "source": ""},
      "ph_opt_high": {"value": null, "status": "unconfirmed", "source": ""},
      "ph_shelf_stable_min": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_min_c": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_max_c": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_opt_c": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_unit": "FCC",
      "dose_min": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_max": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_evidence_threshold": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_benchmark_note": "",
      "is_protease": false,
      "is_natural_source": false,
      "is_gras": {"value": null, "status": "unconfirmed", "source": ""},
      "degrades_structural": [],
      "notes": "Exists so R10 can suggest the acid+neutral strain pairing (KB §4k, the Enzymedica pattern). Every field awaits a supplier spec."
    },
    {
      "id": "alpha_galactosidase",
      "name": "Alpha-galactosidase",
      "aliases": ["alpha-gal"],
      "substrate_id": "gos",
      "source_type": "fungal",
      "priority": "high",
      "deadline": "before_colon",
      "site_of_action": "Stomach to small intestine — must clear GOS before the colon.",
      "ph_min": {"value": 3.0, "status": "confirmed", "source": "KB Table B; Site-of-Action slide 1"},
      "ph_max": {"value": 8.0, "status": "confirmed", "source": "KB Table B; Site-of-Action slide 1"},
      "ph_opt_low": {"value": 5.0, "status": "confirmed", "source": "KB Table B"},
      "ph_opt_high": {"value": 5.0, "status": "confirmed", "source": "KB Table B"},
      "ph_shelf_stable_min": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_min_c": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_max_c": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_opt_c": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_unit": "GalU",
      "dose_min": {"value": 450, "status": "confirmed", "source": "KB Table B"},
      "dose_max": {"value": 800, "status": "confirmed", "source": "KB Table B"},
      "dose_evidence_threshold": {"value": 300, "status": "confirmed", "source": "Digestive Enzyme Industry Overview p9 — Monash / in-vitro: full dose 300 GALU improved GOS symptoms, half dose did not"},
      "dose_benchmark_note": "Beano Extra Strength 800 GalU per serving. The 300 GALU figure is an evidence threshold from research, not any named product's dose.",
      "is_protease": false,
      "is_natural_source": false,
      "is_gras": {"value": true, "status": "confirmed", "source": "KB §4l — alpha-galactosidase largely already GRAS"},
      "degrades_structural": [],
      "notes": "Acts on soluble sugars, not structure — carries no structural entry, which is why a narrow FODMAP blend is texture-safe (spec §6.2 R15)."
    },
    {
      "id": "inulinase",
      "name": "Inulinase",
      "aliases": [],
      "substrate_id": "inulin_fructan",
      "source_type": "fungal",
      "priority": "medium",
      "deadline": "before_colon",
      "site_of_action": "Stomach (strongest window) to upper small intestine.",
      "ph_min": {"value": 2.0, "status": "confirmed", "source": "KB Table B; Site-of-Action slide 1"},
      "ph_max": {"value": 7.0, "status": "confirmed", "source": "KB Table B; Site-of-Action slide 1"},
      "ph_opt_low": {"value": 3.0, "status": "confirmed", "source": "KB Table B"},
      "ph_opt_high": {"value": 5.0, "status": "confirmed", "source": "KB Table B"},
      "ph_shelf_stable_min": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_min_c": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_max_c": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_opt_c": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_unit": "",
      "dose_min": {"value": null, "status": "unconfirmed", "source": "KB Table B marks this 'confirm'."},
      "dose_max": {"value": null, "status": "unconfirmed", "source": "KB Table B marks this 'confirm'."},
      "dose_evidence_threshold": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_benchmark_note": "",
      "is_protease": false,
      "is_natural_source": false,
      "is_gras": {"value": null, "status": "unconfirmed", "source": ""},
      "degrades_structural": [{"structural_class": "pectin_cellulose", "tier": "unconfirmed"}],
      "notes": "Structural impact deliberately unconfirmed: inulin is a storage carbohydrate but forms a meaningful share of chicory and artichoke tissue, so long-dwell softening is plausible and unverified (spec §15 open question 4)."
    },
    {
      "id": "fructan_hydrolase",
      "name": "Fructan hydrolase",
      "aliases": [],
      "substrate_id": "graminan_fructan",
      "source_type": "microbial",
      "priority": "medium",
      "deadline": "before_colon",
      "site_of_action": "Upper GI, before the colon.",
      "ph_min": {"value": null, "status": "unconfirmed", "source": "KB Table B marks this 'confirm'."},
      "ph_max": {"value": null, "status": "unconfirmed", "source": "KB Table B marks this 'confirm'."},
      "ph_opt_low": {"value": null, "status": "unconfirmed", "source": ""},
      "ph_opt_high": {"value": null, "status": "unconfirmed", "source": ""},
      "ph_shelf_stable_min": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_min_c": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_max_c": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_opt_c": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_unit": "",
      "dose_min": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_max": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_evidence_threshold": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_benchmark_note": "",
      "is_protease": false,
      "is_natural_source": false,
      "is_gras": {"value": null, "status": "unconfirmed", "source": ""},
      "degrades_structural": [{"structural_class": "pectin_cellulose", "tier": "unconfirmed"}],
      "supplier_note": "FTO FLAG: the underlying patent appears third-party or licensed — US 10,820,599, per the Digestive Enzyme Industry Overview p14. Resolve before committing to this enzyme.",
      "notes": "The only commercial fructan hydrolase is FODZYME's blend."
    },
    {
      "id": "protease_bromelain",
      "name": "Protease (bromelain)",
      "aliases": ["bromelain", "papain"],
      "substrate_id": "protein",
      "source_type": "plant",
      "priority": "additive",
      "deadline": "small_intestine",
      "site_of_action": "Stomach and small intestine.",
      "ph_min": {"value": 4.0, "status": "confirmed", "source": "KB Table B; Site-of-Action slide 1"},
      "ph_max": {"value": 8.0, "status": "confirmed", "source": "KB Table B; Site-of-Action slide 1"},
      "ph_opt_low": {"value": 7.0, "status": "confirmed", "source": "KB Table B"},
      "ph_opt_high": {"value": 7.0, "status": "confirmed", "source": "KB Table B"},
      "ph_shelf_stable_min": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_min_c": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_max_c": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_opt_c": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_unit": "GDU",
      "dose_min": {"value": null, "status": "unconfirmed", "source": "KB Table B: 'varies (GDU)'."},
      "dose_max": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_evidence_threshold": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_benchmark_note": "",
      "is_protease": true,
      "is_natural_source": true,
      "is_gras": {"value": null, "status": "unconfirmed", "source": ""},
      "heat_labile_note": "Natural-source enzyme — destroyed by cooking (KB §4j).",
      "degrades_structural": [{"structural_class": "structural_protein", "tier": "gradual"}],
      "notes": "Bromelain ~4.5-7. Additive rather than gap-filling: the body already digests protein thoroughly. Retained mainly for clean-label and marketing value. Degrades other enzymes in a shared wet phase (KB §4d)."
    },
    {
      "id": "lipase",
      "name": "Lipase",
      "aliases": [],
      "substrate_id": "fat",
      "source_type": "fungal",
      "priority": "additive",
      "deadline": "small_intestine",
      "site_of_action": "Mostly small intestine.",
      "ph_min": {"value": 2.0, "status": "confirmed", "source": "KB Table B; Site-of-Action slide 1"},
      "ph_max": {"value": 9.0, "status": "confirmed", "source": "KB Table B; Site-of-Action slide 1"},
      "ph_opt_low": {"value": 7.0, "status": "confirmed", "source": "KB Table B"},
      "ph_opt_high": {"value": 7.0, "status": "confirmed", "source": "KB Table B"},
      "ph_shelf_stable_min": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_min_c": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_max_c": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_opt_c": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_unit": "",
      "dose_min": {"value": null, "status": "unconfirmed", "source": "KB Table B marks this 'confirm'."},
      "dose_max": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_evidence_threshold": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_benchmark_note": "",
      "is_protease": false,
      "is_natural_source": false,
      "is_gras": {"value": null, "status": "unconfirmed", "source": ""},
      "degrades_structural": [],
      "notes": "No structural degradation entry — the risk lipase carries is flavour (rancidity, soapy notes), not texture. Additive rather than gap-filling."
    },
    {
      "id": "xylose_isomerase",
      "name": "Xylose / glucose isomerase",
      "aliases": [],
      "substrate_id": "excess_fructose",
      "source_type": "microbial",
      "priority": "lower",
      "deadline": "small_intestine",
      "site_of_action": "Small intestine, near the absorption site.",
      "ph_min": {"value": 7.0, "status": "confirmed", "source": "KB Table B; Site-of-Action slide 1"},
      "ph_max": {"value": 9.0, "status": "confirmed", "source": "KB Table B; Site-of-Action slide 1"},
      "ph_opt_low": {"value": 7.0, "status": "confirmed", "source": "KB Table B"},
      "ph_opt_high": {"value": 9.0, "status": "confirmed", "source": "KB Table B"},
      "ph_shelf_stable_min": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_min_c": {"value": null, "status": "unconfirmed", "source": "EXTERNAL ASSUMPTION, not from the founder's documents: the industrial optimum may sit well above body temperature, making 37 C activity a supplier question."},
      "temp_max_c": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_opt_c": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_unit": "",
      "dose_min": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_max": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_evidence_threshold": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_benchmark_note": "",
      "is_protease": false,
      "is_natural_source": false,
      "is_gras": {"value": null, "status": "unconfirmed", "source": ""},
      "degrades_structural": [],
      "notes": "Converts fructose to glucose so it can use the SGLT-1 transporter instead of the narrower fructose-only pathway."
    },
    {
      "id": "amylase",
      "name": "Amylase",
      "aliases": [],
      "substrate_id": "starch",
      "source_type": "fungal",
      "priority": "lower",
      "deadline": "small_intestine",
      "site_of_action": "",
      "ph_min": {"value": null, "status": "unconfirmed", "source": "Stub — KB Table A lists the enzyme, Table B gives no range."},
      "ph_max": {"value": null, "status": "unconfirmed", "source": ""},
      "ph_opt_low": {"value": null, "status": "unconfirmed", "source": ""},
      "ph_opt_high": {"value": null, "status": "unconfirmed", "source": ""},
      "ph_shelf_stable_min": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_min_c": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_max_c": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_opt_c": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_unit": "",
      "dose_min": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_max": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_evidence_threshold": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_benchmark_note": "",
      "is_protease": false,
      "is_natural_source": false,
      "is_gras": {"value": null, "status": "unconfirmed", "source": ""},
      "degrades_structural": [{"structural_class": "starch", "tier": "gradual"}],
      "notes": "Attacks croutons, pasta, potato and grains in an applied-food context (spec §6.2 R15)."
    },
    {
      "id": "cellulase",
      "name": "Cellulase",
      "aliases": [],
      "substrate_id": "fiber",
      "source_type": "fungal",
      "priority": "lower",
      "deadline": "before_colon",
      "site_of_action": "",
      "ph_min": {"value": null, "status": "unconfirmed", "source": "Stub — KB Table A lists the enzyme, Table B gives no range."},
      "ph_max": {"value": null, "status": "unconfirmed", "source": ""},
      "ph_opt_low": {"value": null, "status": "unconfirmed", "source": ""},
      "ph_opt_high": {"value": null, "status": "unconfirmed", "source": ""},
      "ph_shelf_stable_min": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_min_c": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_max_c": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_opt_c": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_unit": "",
      "dose_min": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_max": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_evidence_threshold": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_benchmark_note": "",
      "is_protease": false,
      "is_natural_source": false,
      "is_gras": {"value": null, "status": "unconfirmed", "source": ""},
      "degrades_structural": [{"structural_class": "pectin_cellulose", "tier": "gradual"}],
      "notes": "Breaks plant cell walls — the chemistry of a vegetable going limp. The reason a broad-spectrum blend is not texture-safe on a dressed salad."
    },
    {
      "id": "pectinase",
      "name": "Pectinase",
      "aliases": [],
      "substrate_id": "pectin",
      "source_type": "fungal",
      "priority": "lower",
      "deadline": "before_colon",
      "site_of_action": "",
      "ph_min": {"value": null, "status": "unconfirmed", "source": "Stub — KB Table A lists the enzyme, Table B gives no range."},
      "ph_max": {"value": null, "status": "unconfirmed", "source": ""},
      "ph_opt_low": {"value": null, "status": "unconfirmed", "source": ""},
      "ph_opt_high": {"value": null, "status": "unconfirmed", "source": ""},
      "ph_shelf_stable_min": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_min_c": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_max_c": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_opt_c": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_unit": "",
      "dose_min": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_max": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_evidence_threshold": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_benchmark_note": "",
      "is_protease": false,
      "is_natural_source": false,
      "is_gras": {"value": null, "status": "unconfirmed", "source": ""},
      "degrades_structural": [{"structural_class": "pectin_cellulose", "tier": "gradual"}],
      "notes": "Used industrially to soften and clarify plant tissue."
    },
    {
      "id": "invertase",
      "name": "Invertase",
      "aliases": [],
      "substrate_id": "sucrose",
      "source_type": "fungal",
      "priority": "lower",
      "deadline": "small_intestine",
      "site_of_action": "",
      "ph_min": {"value": null, "status": "unconfirmed", "source": "Stub — KB Table A lists the enzyme, Table B gives no range."},
      "ph_max": {"value": null, "status": "unconfirmed", "source": ""},
      "ph_opt_low": {"value": null, "status": "unconfirmed", "source": ""},
      "ph_opt_high": {"value": null, "status": "unconfirmed", "source": ""},
      "ph_shelf_stable_min": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_min_c": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_max_c": {"value": null, "status": "unconfirmed", "source": ""},
      "temp_opt_c": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_unit": "",
      "dose_min": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_max": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_evidence_threshold": {"value": null, "status": "unconfirmed", "source": ""},
      "dose_benchmark_note": "",
      "is_protease": false,
      "is_natural_source": false,
      "is_gras": {"value": null, "status": "unconfirmed", "source": ""},
      "degrades_structural": [],
      "notes": ""
    }
  ]
}
```

- [ ] **Step 2: Verify JSON validity and record count**

Run: `python3 -c "import json;d=json.load(open('seed/enzymes.json'));print(len(d['enzymes']),'enzymes')"`
Expected: `12 enzymes`

- [ ] **Step 3: Verify no enzyme carries the rapid tier**

Spec §6.3.1: no shipped seed enzyme may claim `rapid`.

Run: `python3 -c "import json;d=json.load(open('seed/enzymes.json'));t=[s['tier'] for e in d['enzymes'] for s in e['degrades_structural']];print(sorted(set(t)))"`
Expected: `['gradual', 'unconfirmed']`

- [ ] **Step 4: Commit**

```bash
git add seed/enzymes.json
git commit -m "feat(seed): add 12 enzyme records with truth-labelled provenance"
```

---

## Task 6: Seed — foods

Spec §9.3. One role-flagged table; several records carry all three roles.

**Files:**
- Create: `seed/foods.json`

- [ ] **Step 1: Create `seed/foods.json`**

Every `ph` and `water_content_pct` seeds `unconfirmed` per §9.3 — `value` carries a starting estimate so the founder has something to correct, but `status` keeps it out of every rule until she confirms it.

```json
{
  "$comment": "Spec §9.3. All ph and water_content_pct values seed unconfirmed: the KB gives exactly one pH statement (vinegar puts a dressing around pH 3) and no ingredient-level figures. Values present are starting estimates for the founder to measure, not evidence.",
  "foods": [
    {"id": "olive_oil", "name": "Olive oil", "category": "oil", "is_recipe_ingredient": true, "ph": {"value": null, "status": "unconfirmed", "source": "Oils are not aqueous; pH is not meaningful."}, "water_content_pct": {"value": 0, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["fat"]},
    {"id": "canola_oil", "name": "Canola oil", "category": "oil", "is_recipe_ingredient": true, "ph": {"value": null, "status": "unconfirmed", "source": ""}, "water_content_pct": {"value": 0, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["fat"]},
    {"id": "balsamic_vinegar", "name": "Balsamic vinegar", "category": "acid", "is_recipe_ingredient": true, "ph": {"value": 3.0, "status": "unconfirmed", "source": "KB §4a states only that vinegar puts a dressing around pH 3."}, "water_content_pct": {"value": 80, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": []},
    {"id": "white_vinegar", "name": "White vinegar", "category": "acid", "is_recipe_ingredient": true, "ph": {"value": 3.0, "status": "unconfirmed", "source": "KB §4a, generic vinegar figure."}, "water_content_pct": {"value": 95, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": []},
    {"id": "apple_cider_vinegar", "name": "Apple cider vinegar", "category": "acid", "is_recipe_ingredient": true, "ph": {"value": 3.0, "status": "unconfirmed", "source": "KB §4a, generic vinegar figure."}, "water_content_pct": {"value": 94, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": []},
    {"id": "lemon_juice", "name": "Lemon juice", "category": "acid", "is_recipe_ingredient": true, "ph": {"value": 2.4, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 90, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": []},
    {"id": "honey", "name": "Honey", "category": "sweetener", "is_recipe_ingredient": true, "is_trigger_food": true, "ph": {"value": 3.9, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 17, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["excess_fructose"], "typical_load_value": {"value": null, "status": "unconfirmed", "source": ""}, "typical_load_unit": "g fructose", "notes": "Also a natural source of diastase (KB §4j)."},
    {"id": "mustard", "name": "Mustard", "category": "condiment", "is_recipe_ingredient": true, "ph": {"value": 3.6, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 80, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": []},
    {"id": "yogurt", "name": "Yogurt", "category": "dairy", "is_recipe_ingredient": true, "is_trigger_food": true, "ph": {"value": 4.4, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 85, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["lactose", "protein"], "typical_load_value": {"value": null, "status": "unconfirmed", "source": ""}, "typical_load_unit": "g lactose"},
    {"id": "buttermilk", "name": "Buttermilk", "category": "dairy", "is_recipe_ingredient": true, "is_trigger_food": true, "ph": {"value": 4.5, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 90, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["lactose", "protein"], "typical_load_value": {"value": null, "status": "unconfirmed", "source": ""}, "typical_load_unit": "g lactose"},
    {"id": "mayonnaise", "name": "Mayonnaise", "category": "emulsion", "is_recipe_ingredient": true, "ph": {"value": 4.0, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 20, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["fat", "protein"]},
    {"id": "garlic_fresh", "name": "Garlic (fresh)", "category": "aromatic", "is_recipe_ingredient": true, "is_trigger_food": true, "ph": {"value": 6.0, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 59, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["inulin_fructan"], "typical_load_value": {"value": null, "status": "unconfirmed", "source": ""}, "typical_load_unit": "g fructan", "notes": "Carries more short-chain fructans than inulin (KB §4i)."},
    {"id": "garlic_powder", "name": "Garlic powder", "category": "aromatic", "is_recipe_ingredient": true, "is_trigger_food": true, "ph": {"value": 5.8, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 6, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["inulin_fructan"], "typical_load_value": {"value": null, "status": "unconfirmed", "source": ""}, "typical_load_unit": "g fructan"},
    {"id": "onion", "name": "Onion", "category": "aromatic", "is_recipe_ingredient": true, "is_trigger_food": true, "ph": {"value": 5.5, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 89, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["inulin_fructan"], "typical_load_value": {"value": null, "status": "unconfirmed", "source": ""}, "typical_load_unit": "g fructan"},
    {"id": "herbs", "name": "Fresh herbs", "category": "aromatic", "is_recipe_ingredient": true, "ph": {"value": null, "status": "unconfirmed", "source": ""}, "water_content_pct": {"value": 85, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": []},
    {"id": "salt", "name": "Salt", "category": "seasoning", "is_recipe_ingredient": true, "ph": {"value": null, "status": "unconfirmed", "source": ""}, "water_content_pct": {"value": 0, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": []},
    {"id": "sugar", "name": "Sugar", "category": "sweetener", "is_recipe_ingredient": true, "ph": {"value": null, "status": "unconfirmed", "source": ""}, "water_content_pct": {"value": 0, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["sucrose"]},
    {"id": "water", "name": "Water", "category": "base", "is_recipe_ingredient": true, "ph": {"value": 7.0, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 100, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": []},
    {"id": "pineapple_fresh", "name": "Pineapple (fresh)", "category": "fruit", "is_recipe_ingredient": true, "contains_protease": true, "ph": {"value": 3.5, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 86, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": [], "notes": "TRAP INGREDIENT: natural bromelain source. In a shared wet phase it degrades other enzymes (KB §4d). Cooking destroys it (KB §4j)."},
    {"id": "papaya_fresh", "name": "Papaya (fresh)", "category": "fruit", "is_recipe_ingredient": true, "contains_protease": true, "ph": {"value": 5.5, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 88, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": [], "notes": "TRAP INGREDIENT: natural papain source."},
    {"id": "modified_starch", "name": "Modified starch", "category": "thickener", "is_recipe_ingredient": true, "ph": {"value": null, "status": "unconfirmed", "source": ""}, "water_content_pct": {"value": 10, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["starch"]},
    {"id": "milk", "name": "Milk", "category": "dairy", "is_trigger_food": true, "ph": {"value": 6.7, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 87, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["lactose", "protein"], "typical_load_value": {"value": null, "status": "unconfirmed", "source": ""}, "typical_load_unit": "g lactose"},
    {"id": "ice_cream", "name": "Ice cream", "category": "dairy", "is_trigger_food": true, "ph": {"value": null, "status": "unconfirmed", "source": ""}, "water_content_pct": {"value": 60, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["lactose", "protein"], "typical_load_value": {"value": null, "status": "unconfirmed", "source": ""}, "typical_load_unit": "g lactose"},
    {"id": "aged_cheese", "name": "Hard aged cheese", "category": "dairy", "is_trigger_food": true, "is_application_food": true, "ph": {"value": null, "status": "unconfirmed", "source": ""}, "water_content_pct": {"value": 35, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["protein"], "structural": ["structural_protein"], "typical_load_value": {"value": null, "status": "unconfirmed", "source": ""}, "typical_load_unit": "g lactose", "notes": "Low lactose — KB §3 notes hard aged cheeses are the dairy exception."},
    {"id": "black_beans", "name": "Black beans", "category": "legume", "is_recipe_ingredient": true, "is_trigger_food": true, "is_application_food": true, "ph": {"value": 6.0, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 65, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["gos", "protein"], "structural": ["structural_protein"], "typical_load_value": {"value": null, "status": "unconfirmed", "source": ""}, "typical_load_unit": "g GOS", "notes": "Carries all three roles — recipe ingredient, GOS trigger food, and application food."},
    {"id": "chickpeas", "name": "Chickpeas", "category": "legume", "is_recipe_ingredient": true, "is_trigger_food": true, "is_application_food": true, "ph": {"value": 6.2, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 60, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["gos", "protein"], "structural": ["structural_protein"], "typical_load_value": {"value": null, "status": "unconfirmed", "source": ""}, "typical_load_unit": "g GOS"},
    {"id": "lentils", "name": "Lentils", "category": "legume", "is_recipe_ingredient": true, "is_trigger_food": true, "is_application_food": true, "ph": {"value": 6.3, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 70, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["gos", "protein"], "structural": ["structural_protein"], "typical_load_value": {"value": null, "status": "unconfirmed", "source": ""}, "typical_load_unit": "g GOS"},
    {"id": "broccoli", "name": "Broccoli", "category": "cruciferous", "is_trigger_food": true, "is_application_food": true, "ph": {"value": 6.3, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 89, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["gos"], "structural": ["pectin_cellulose"], "typical_load_value": {"value": null, "status": "unconfirmed", "source": ""}, "typical_load_unit": "g GOS"},
    {"id": "wheat_bread", "name": "Wheat bread", "category": "grain", "is_trigger_food": true, "is_application_food": true, "ph": {"value": null, "status": "unconfirmed", "source": ""}, "water_content_pct": {"value": 38, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["graminan_fructan", "starch"], "structural": ["starch"], "typical_load_value": {"value": null, "status": "unconfirmed", "source": ""}, "typical_load_unit": "g fructan"},
    {"id": "apple", "name": "Apple", "category": "fruit", "is_trigger_food": true, "is_application_food": true, "ph": {"value": 3.6, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 86, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["excess_fructose"], "structural": ["pectin_cellulose"], "typical_load_value": {"value": null, "status": "unconfirmed", "source": ""}, "typical_load_unit": "g fructose"},
    {"id": "mushroom", "name": "Mushrooms", "category": "vegetable", "is_trigger_food": true, "is_application_food": true, "ph": {"value": 6.2, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 92, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["polyol"], "structural": ["pectin_cellulose"], "typical_load_value": {"value": null, "status": "unconfirmed", "source": ""}, "typical_load_unit": "g polyol", "notes": "Polyols have no commercial enzyme — R14 reports this as an explicit gap, never a pass."},
    {"id": "artichoke", "name": "Artichoke", "category": "vegetable", "is_trigger_food": true, "is_application_food": true, "ph": {"value": 5.6, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 84, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["inulin_fructan"], "structural": ["pectin_cellulose"], "typical_load_value": {"value": null, "status": "unconfirmed", "source": ""}, "typical_load_unit": "g fructan", "notes": "Inulin-rich tissue — the open question behind inulinase's unconfirmed structural tier."},
    {"id": "romaine", "name": "Romaine lettuce", "category": "green", "is_application_food": true, "ph": {"value": 6.0, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 95, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": [], "structural": ["pectin_cellulose"]},
    {"id": "mixed_greens", "name": "Mixed greens", "category": "green", "is_application_food": true, "ph": {"value": 6.0, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 93, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": [], "structural": ["pectin_cellulose"]},
    {"id": "spinach", "name": "Spinach", "category": "green", "is_application_food": true, "ph": {"value": 6.5, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 91, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": [], "structural": ["pectin_cellulose"]},
    {"id": "kale", "name": "Kale", "category": "green", "is_application_food": true, "ph": {"value": 6.4, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 90, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": [], "structural": ["pectin_cellulose"]},
    {"id": "cucumber", "name": "Cucumber", "category": "vegetable", "is_application_food": true, "ph": {"value": 5.5, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 95, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": [], "structural": ["pectin_cellulose"]},
    {"id": "tomato", "name": "Tomato", "category": "vegetable", "is_application_food": true, "ph": {"value": 4.5, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 94, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": [], "structural": ["pectin_cellulose"]},
    {"id": "bell_pepper", "name": "Bell pepper", "category": "vegetable", "is_application_food": true, "ph": {"value": 5.2, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 92, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": [], "structural": ["pectin_cellulose"]},
    {"id": "shredded_carrot", "name": "Shredded carrot", "category": "vegetable", "is_application_food": true, "ph": {"value": 6.0, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 88, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": [], "structural": ["pectin_cellulose"]},
    {"id": "chicken_cooked", "name": "Cooked chicken breast", "category": "protein", "is_application_food": true, "is_heat_processed": true, "ph": {"value": 6.2, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 65, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["protein"], "structural": ["structural_protein"]},
    {"id": "canned_tuna", "name": "Canned tuna", "category": "protein", "is_application_food": true, "is_heat_processed": true, "ph": {"value": 6.0, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 68, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["protein"], "structural": ["structural_protein"]},
    {"id": "boiled_egg", "name": "Hard-boiled egg", "category": "protein", "is_application_food": true, "is_heat_processed": true, "ph": {"value": 7.5, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 75, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["protein"], "structural": ["structural_protein"]},
    {"id": "tofu", "name": "Tofu", "category": "protein", "is_application_food": true, "ph": {"value": 6.5, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 85, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["protein"], "structural": ["structural_protein"]},
    {"id": "feta", "name": "Feta", "category": "dairy", "is_application_food": true, "ph": {"value": 4.6, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 55, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["protein", "lactose"], "structural": ["structural_protein"]},
    {"id": "parmesan", "name": "Parmesan", "category": "dairy", "is_application_food": true, "ph": {"value": 5.4, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 30, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["protein"], "structural": ["structural_protein"]},
    {"id": "cooked_pasta", "name": "Cooked pasta", "category": "grain", "is_application_food": true, "is_heat_processed": true, "ph": {"value": 6.5, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 62, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["starch", "graminan_fructan"], "structural": ["starch"]},
    {"id": "cooked_potato", "name": "Cooked potato", "category": "vegetable", "is_application_food": true, "is_heat_processed": true, "ph": {"value": 5.8, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 77, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["starch"], "structural": ["starch"]},
    {"id": "quinoa", "name": "Quinoa", "category": "grain", "is_application_food": true, "is_heat_processed": true, "ph": {"value": 6.5, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 72, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["starch"], "structural": ["starch"]},
    {"id": "farro", "name": "Farro", "category": "grain", "is_application_food": true, "is_heat_processed": true, "ph": {"value": 6.3, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 68, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["starch", "graminan_fructan"], "structural": ["starch"]},
    {"id": "croutons", "name": "Croutons", "category": "grain", "is_application_food": true, "is_heat_processed": true, "ph": {"value": null, "status": "unconfirmed", "source": ""}, "water_content_pct": {"value": 8, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["starch", "graminan_fructan"], "structural": ["starch"]},
    {"id": "avocado", "name": "Avocado", "category": "fruit", "is_application_food": true, "ph": {"value": 6.5, "status": "unconfirmed", "source": "estimate"}, "water_content_pct": {"value": 73, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["fat"], "structural": [], "notes": "No structural class the seeded enzymes act on."},
    {"id": "nuts_seeds", "name": "Nuts and seeds", "category": "fat", "is_application_food": true, "ph": {"value": null, "status": "unconfirmed", "source": ""}, "water_content_pct": {"value": 4, "status": "unconfirmed", "source": "estimate"}, "contains_substrate_ids": ["fat", "protein"], "structural": [], "notes": "No structural class the seeded enzymes act on."}
  ]
}
```

- [ ] **Step 2: Verify JSON validity and role coverage**

Run:
```bash
python3 -c "
import json
d=json.load(open('seed/foods.json'))['foods']
print(len(d),'foods')
print('recipe:',sum(1 for f in d if f.get('is_recipe_ingredient')))
print('trigger:',sum(1 for f in d if f.get('is_trigger_food')))
print('application:',sum(1 for f in d if f.get('is_application_food')))
print('all three:',[f['id'] for f in d if f.get('is_recipe_ingredient') and f.get('is_trigger_food') and f.get('is_application_food')])
"
```
Expected:
```
53 foods
recipe: 22
trigger: 16
application: 29
all three: ['black_beans', 'chickpeas', 'lentils']
```

- [ ] **Step 3: Commit**

```bash
git add seed/foods.json
git commit -m "feat(seed): add role-flagged food catalogue with structural composition"
```

---

## Task 7: Seed loader

Turns JSON into domain objects and fails loudly on anything malformed. This lives outside `engine/` because it does file I/O.

**Files:**
- Create: `src/foodbrew/seedload/__init__.py`
- Create: `src/foodbrew/seedload/loader.py`
- Test: `tests/test_seed_integrity.py`

- [ ] **Step 1: Write the failing test**

`tests/test_seed_integrity.py`:

```python
import pytest

from foodbrew.engine.types import SeverityTier, TruthLabel
from foodbrew.seedload.loader import load_seed


@pytest.fixture(scope="module")
def seed():
    return load_seed()


def test_loads_expected_record_counts(seed):
    assert len(seed.enzymes) == 12
    assert len(seed.substrates) == 12
    assert len(seed.gi_regions) == 6
    assert len(seed.foods) == 53


def test_every_enzyme_substrate_id_resolves(seed):
    for e in seed.enzymes.values():
        assert e.substrate_id in seed.substrates, f"{e.id} references unknown {e.substrate_id}"


def test_every_food_substrate_id_resolves(seed):
    for f in seed.foods.values():
        for sid in f.contains_substrate_ids:
            assert sid in seed.substrates, f"{f.id} references unknown {sid}"


def test_no_shipped_enzyme_claims_the_rapid_tier(seed):
    # Spec §6.3.1 — the rapid tier exists so the mapping is total, but no
    # source document supports minutes-scale destruction by a real enzyme.
    for e in seed.enzymes.values():
        for entry in e.degrades_structural:
            assert entry.tier is not SeverityTier.RAPID, f"{e.id} must not claim rapid"


def test_all_temperature_fields_seed_unconfirmed(seed):
    # Spec §9.1 — this is why R12 is advisory in v1 (§6.1 R12).
    for e in seed.enzymes.values():
        assert e.temp_min_c.status is TruthLabel.UNCONFIRMED
        assert e.temp_max_c.status is TruthLabel.UNCONFIRMED
        assert e.temp_opt_c.status is TruthLabel.UNCONFIRMED


def test_all_shelf_stable_floors_seed_unconfirmed(seed):
    for e in seed.enzymes.values():
        assert e.ph_shelf_stable_min.status is TruthLabel.UNCONFIRMED


def test_all_food_ph_and_water_seed_unconfirmed(seed):
    # Spec §9.3 — seeded numbers are starting estimates, not evidence.
    for f in seed.foods.values():
        assert f.ph.status is TruthLabel.UNCONFIRMED
        assert f.water_content_pct.status is TruthLabel.UNCONFIRMED


def test_gi_regions_are_ordered_and_mouth_is_dormant(seed):
    orders = [r.order for r in seed.gi_regions]
    assert orders == sorted(orders)
    assert seed.gi_regions[0].id == "mouth"
    assert seed.gi_regions[0].dormant is True


def test_polyol_substrate_has_no_commercial_enzyme(seed):
    assert seed.substrates["polyol"].no_commercial_enzyme is True
    covered = {e.substrate_id for e in seed.enzymes.values()}
    assert "polyol" not in covered, "no enzyme may ever be mapped to polyols"


def test_prebiotic_substrates_flagged(seed):
    # Spec §9.2 — drives R9, which must fire for GOS as well as fructans.
    assert seed.substrates["gos"].is_prebiotic is True
    assert seed.substrates["inulin_fructan"].is_prebiotic is True
    assert seed.substrates["graminan_fructan"].is_prebiotic is True
    assert seed.substrates["lactose"].is_prebiotic is False


def test_trap_ingredients_flag_protease(seed):
    assert seed.foods["pineapple_fresh"].contains_protease is True
    assert seed.foods["papaya_fresh"].contains_protease is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_seed_integrity.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'foodbrew.seedload'`

- [ ] **Step 3: Write the loader**

`src/foodbrew/seedload/__init__.py`:

```python
from foodbrew.seedload.loader import Seed, load_seed

__all__ = ["Seed", "load_seed"]
```

`src/foodbrew/seedload/loader.py`:

```python
"""Load seed JSON into engine domain objects. Does file I/O — never imported by engine/."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from foodbrew.engine.types import (
    Deadline,
    Enzyme,
    Food,
    GIRegion,
    SeverityTier,
    StructuralClass,
    StructuralEntry,
    Substrate,
    Tracked,
    TruthLabel,
)

#: Repository root — seed/ sits beside src/.
SEED_DIR = Path(__file__).resolve().parents[3] / "seed"


class SeedError(ValueError):
    """Raised when seed JSON is malformed. Loud on purpose."""


@dataclass(frozen=True, slots=True)
class Seed:
    enzymes: Mapping[str, Enzyme]
    foods: Mapping[str, Food]
    substrates: Mapping[str, Substrate]
    gi_regions: tuple[GIRegion, ...]


def _tracked(raw: Any, field_name: str) -> Tracked:
    """Parse a {value,status,source} object. Missing means unconfirmed-with-no-value."""
    if raw is None:
        return Tracked(None, TruthLabel.UNCONFIRMED, "")
    if not isinstance(raw, dict):
        raise SeedError(f"{field_name}: expected an object with value/status/source")
    try:
        status = TruthLabel(raw["status"])
    except KeyError as exc:
        raise SeedError(f"{field_name}: missing 'status'") from exc
    except ValueError as exc:
        raise SeedError(f"{field_name}: '{raw['status']}' is not a truth label") from exc
    return Tracked(value=raw.get("value"), status=status, source=raw.get("source", ""))


def _read(name: str, seed_dir: Path) -> dict:
    path = seed_dir / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SeedError(f"missing seed file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SeedError(f"invalid JSON in {path}: {exc}") from exc


def _parse_structural(raw: list, enzyme_id: str) -> tuple[StructuralEntry, ...]:
    out = []
    for entry in raw or []:
        try:
            out.append(
                StructuralEntry(
                    structural_class=StructuralClass(entry["structural_class"]),
                    tier=SeverityTier(entry["tier"]),
                )
            )
        except (KeyError, ValueError) as exc:
            raise SeedError(f"{enzyme_id}: bad degrades_structural entry {entry!r}") from exc
    return tuple(out)


def load_seed(seed_dir: Path | None = None) -> Seed:
    """Load and validate every seed file. Raises SeedError on any problem."""
    d = seed_dir or SEED_DIR

    substrates = {}
    for r in _read("substrates.json", d)["substrates"]:
        substrates[r["id"]] = Substrate(
            id=r["id"],
            name=r["name"],
            native_human_enzyme=r.get("native_human_enzyme", False),
            is_prebiotic=r.get("is_prebiotic", False),
            no_commercial_enzyme=r.get("no_commercial_enzyme", False),
            notes=r.get("notes", ""),
        )

    regions = []
    for r in _read("gi_model.json", d)["regions"]:
        regions.append(
            GIRegion(
                id=r["id"],
                name=r["name"],
                ph_low=float(r["ph_low"]),
                ph_high=float(r["ph_high"]),
                order=int(r["order"]),
                dormant=r.get("dormant", False),
                transit_note=r.get("transit_note", ""),
            )
        )
    regions.sort(key=lambda x: x.order)

    enzymes = {}
    for r in _read("enzymes.json", d)["enzymes"]:
        eid = r["id"]
        try:
            deadline = Deadline(r["deadline"])
        except ValueError as exc:
            raise SeedError(f"{eid}: '{r['deadline']}' is not a deadline") from exc
        enzymes[eid] = Enzyme(
            id=eid,
            name=r["name"],
            aliases=tuple(r.get("aliases", ())),
            substrate_id=r["substrate_id"],
            source_type=r["source_type"],
            priority=r["priority"],
            deadline=deadline,
            site_of_action=r.get("site_of_action", ""),
            ph_min=_tracked(r.get("ph_min"), f"{eid}.ph_min"),
            ph_max=_tracked(r.get("ph_max"), f"{eid}.ph_max"),
            ph_opt_low=_tracked(r.get("ph_opt_low"), f"{eid}.ph_opt_low"),
            ph_opt_high=_tracked(r.get("ph_opt_high"), f"{eid}.ph_opt_high"),
            ph_shelf_stable_min=_tracked(
                r.get("ph_shelf_stable_min"), f"{eid}.ph_shelf_stable_min"
            ),
            temp_min_c=_tracked(r.get("temp_min_c"), f"{eid}.temp_min_c"),
            temp_max_c=_tracked(r.get("temp_max_c"), f"{eid}.temp_max_c"),
            temp_opt_c=_tracked(r.get("temp_opt_c"), f"{eid}.temp_opt_c"),
            dose_unit=r.get("dose_unit", ""),
            dose_min=_tracked(r.get("dose_min"), f"{eid}.dose_min"),
            dose_max=_tracked(r.get("dose_max"), f"{eid}.dose_max"),
            dose_evidence_threshold=_tracked(
                r.get("dose_evidence_threshold"), f"{eid}.dose_evidence_threshold"
            ),
            dose_benchmark_note=r.get("dose_benchmark_note", ""),
            is_protease=r.get("is_protease", False),
            is_natural_source=r.get("is_natural_source", False),
            is_gras=_tracked(r.get("is_gras"), f"{eid}.is_gras"),
            food_grade_note=r.get("food_grade_note", ""),
            heat_labile_note=r.get("heat_labile_note", ""),
            degrades_structural=_parse_structural(r.get("degrades_structural"), eid),
            cost_tier=r.get("cost_tier", ""),
            supplier_note=r.get("supplier_note", ""),
            notes=r.get("notes", ""),
        )

    foods = {}
    for r in _read("foods.json", d)["foods"]:
        fid = r["id"]
        try:
            structural = tuple(StructuralClass(s) for s in r.get("structural", ()))
        except ValueError as exc:
            raise SeedError(f"{fid}: bad structural class in {r.get('structural')}") from exc
        foods[fid] = Food(
            id=fid,
            name=r["name"],
            category=r.get("category", ""),
            is_recipe_ingredient=r.get("is_recipe_ingredient", False),
            is_trigger_food=r.get("is_trigger_food", False),
            is_application_food=r.get("is_application_food", False),
            ph=_tracked(r.get("ph"), f"{fid}.ph"),
            water_content_pct=_tracked(r.get("water_content_pct"), f"{fid}.water_content_pct"),
            contains_substrate_ids=tuple(r.get("contains_substrate_ids", ())),
            typical_load_value=_tracked(r.get("typical_load_value"), f"{fid}.typical_load_value"),
            typical_load_unit=r.get("typical_load_unit", ""),
            contains_protease=r.get("contains_protease", False),
            is_heat_processed=r.get("is_heat_processed", False),
            structural=structural,
            notes=r.get("notes", ""),
        )

    # Referential integrity — a dangling id must fail at load, not at evaluate.
    for e in enzymes.values():
        if e.substrate_id not in substrates:
            raise SeedError(f"{e.id}: unknown substrate_id {e.substrate_id}")
    for f in foods.values():
        for sid in f.contains_substrate_ids:
            if sid not in substrates:
                raise SeedError(f"{f.id}: unknown substrate id {sid}")

    return Seed(
        enzymes=enzymes, foods=foods, substrates=substrates, gi_regions=tuple(regions)
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_seed_integrity.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/seedload/ tests/test_seed_integrity.py
git commit -m "feat(seed): add validating loader with referential integrity checks"
```

---

## Task 8: Shared conventions (§6.7)

Three rules read these. Defining them once is the point — the spec added §6.7 precisely because implementations were free to diverge.

**Files:**
- Create: `src/foodbrew/engine/conventions.py`
- Test: `tests/engine/test_conventions.py`

- [ ] **Step 1: Write the failing test**

`tests/engine/test_conventions.py`:

```python
import pytest

from foodbrew.engine.conventions import (
    WET_THRESHOLD_PCT,
    PhResolution,
    aggregate_substrate_loads,
    is_wet,
    resolve_recipe_ph,
)
from foodbrew.engine.types import (
    Food,
    Format,
    Formulation,
    Phase,
    RecipeIngredient,
    SelectedEnzyme,
    Tracked,
    TruthLabel,
)


def _food(fid, ph=None, water=None, ph_status=TruthLabel.CONFIRMED,
          water_status=TruthLabel.CONFIRMED, load=None, subs=()):
    return Food(
        id=fid, name=fid, category="test",
        ph=Tracked(ph, ph_status, "test"),
        water_content_pct=Tracked(water, water_status, "test"),
        typical_load_value=Tracked(load, TruthLabel.CONFIRMED if load is not None
                                   else TruthLabel.UNCONFIRMED, "test"),
        contains_substrate_ids=subs,
    )


def test_wet_threshold_is_fifty_percent():
    assert WET_THRESHOLD_PCT == 50


def test_is_wet_at_and_above_threshold():
    assert is_wet(_food("a", water=50)) is True
    assert is_wet(_food("b", water=95)) is True


def test_is_wet_below_threshold():
    assert is_wet(_food("c", water=20)) is False


def test_is_wet_is_none_when_water_unconfirmed():
    # Cannot decide — the caller must return cannot_assess, not guess.
    assert is_wet(_food("d", water=90, water_status=TruthLabel.UNCONFIRMED)) is None


def test_resolve_ph_prefers_formulation_measured():
    form = Formulation(
        id="f", format=Format.PREMIXED_WET, recipe=(), enzymes=(),
        measured_ph=Tracked(4.4, TruthLabel.USER_PROVIDED, "bench"),
    )
    res = resolve_recipe_ph(form, foods={}, latest_trial_ph=Tracked(3.9, TruthLabel.OBSERVED))
    assert res.value == 4.4
    assert res.status is TruthLabel.USER_PROVIDED
    assert res.origin == "formulation.measured_ph"


def test_resolve_ph_falls_back_to_trial_batch():
    form = Formulation(id="f", format=Format.PREMIXED_WET, recipe=(), enzymes=())
    res = resolve_recipe_ph(form, foods={}, latest_trial_ph=Tracked(3.9, TruthLabel.OBSERVED))
    assert res.value == 3.9
    assert res.status is TruthLabel.OBSERVED
    assert res.origin == "trial_batch.measured_ph"


def test_resolve_ph_falls_back_to_lowest_wet_ingredient():
    foods = {
        "vinegar": _food("vinegar", ph=3.0, water=95),
        "oil": _food("oil", ph=None, water=0),
        "yogurt": _food("yogurt", ph=4.4, water=85),
    }
    form = Formulation(
        id="f", format=Format.PREMIXED_WET,
        recipe=(
            RecipeIngredient("vinegar", 30.0),
            RecipeIngredient("oil", 60.0),
            RecipeIngredient("yogurt", 10.0),
        ),
        enzymes=(),
    )
    res = resolve_recipe_ph(form, foods=foods, latest_trial_ph=None)
    assert res.value == 3.0
    assert res.status is TruthLabel.CALCULATED
    assert res.origin == "wet_ingredient_fallback"


def test_resolve_ph_cannot_assess_when_a_wet_ingredient_ph_is_unconfirmed():
    foods = {"vinegar": _food("vinegar", ph=3.0, water=95, ph_status=TruthLabel.UNCONFIRMED)}
    form = Formulation(
        id="f", format=Format.PREMIXED_WET,
        recipe=(RecipeIngredient("vinegar", 30.0),), enzymes=(),
    )
    res = resolve_recipe_ph(form, foods=foods, latest_trial_ph=None)
    assert res.value is None
    assert res.status is TruthLabel.UNCONFIRMED
    assert "vinegar" in res.blocking_field


def test_resolve_ph_cannot_assess_when_water_content_unconfirmed():
    foods = {"x": _food("x", ph=3.0, water=95, water_status=TruthLabel.UNCONFIRMED)}
    form = Formulation(
        id="f", format=Format.PREMIXED_WET,
        recipe=(RecipeIngredient("x", 10.0),), enzymes=(),
    )
    res = resolve_recipe_ph(form, foods=foods, latest_trial_ph=None)
    assert res.status is TruthLabel.UNCONFIRMED
    assert "water_content_pct" in res.blocking_field


def test_substrate_loads_sum_across_foods():
    foods = {
        "beans": _food("beans", load=4.0, subs=("gos",)),
        "lentils": _food("lentils", load=2.5, subs=("gos",)),
        "milk": _food("milk", load=12.0, subs=("lactose",)),
    }
    result = aggregate_substrate_loads(("beans", "lentils", "milk"), foods)
    assert result["gos"].value == pytest.approx(6.5)
    assert result["gos"].status is TruthLabel.CONFIRMED
    assert result["lactose"].value == pytest.approx(12.0)


def test_substrate_load_unconfirmed_when_any_contributor_unconfirmed():
    foods = {
        "beans": _food("beans", load=4.0, subs=("gos",)),
        "lentils": _food("lentils", load=None, subs=("gos",)),
    }
    result = aggregate_substrate_loads(("beans", "lentils"), foods)
    assert result["gos"].status is TruthLabel.UNCONFIRMED
    assert "lentils" in result["gos"].source
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/engine/test_conventions.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'foodbrew.engine.conventions'`

- [ ] **Step 3: Write the implementation**

`src/foodbrew/engine/conventions.py`:

```python
"""Spec §6.7 — conventions several rules share, defined once so they cannot diverge."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from foodbrew.engine.types import Food, Formulation, Tracked, TruthLabel

#: Spec §6.7 — a recipe ingredient counts as wet at or above this water content.
WET_THRESHOLD_PCT = 50


def is_wet(food: Food) -> bool | None:
    """True/False when water content is evidence; None when it is unconfirmed.

    None means "cannot decide" — the caller must surface cannot_assess rather
    than treating an unknown as dry.
    """
    if not food.water_content_pct.usable:
        return None
    return float(food.water_content_pct.value) >= WET_THRESHOLD_PCT


@dataclass(frozen=True, slots=True)
class PhResolution:
    """Outcome of spec §6.7's measured-pH resolution order."""

    value: float | None
    status: TruthLabel
    origin: str
    blocking_field: str = ""


def resolve_recipe_ph(
    formulation: Formulation,
    foods: Mapping[str, Food],
    latest_trial_ph: Tracked | None,
) -> PhResolution:
    """Spec §6.7 resolution order: formulation → latest trial batch → wet-ingredient fallback."""
    if formulation.measured_ph.usable:
        return PhResolution(
            value=float(formulation.measured_ph.value),
            status=formulation.measured_ph.status,
            origin="formulation.measured_ph",
        )

    if latest_trial_ph is not None and latest_trial_ph.usable:
        return PhResolution(
            value=float(latest_trial_ph.value),
            status=TruthLabel.OBSERVED,
            origin="trial_batch.measured_ph",
        )

    wet_phs: list[float] = []
    for ingredient in formulation.recipe:
        food = foods.get(ingredient.food_id)
        if food is None:
            return PhResolution(
                None, TruthLabel.UNCONFIRMED, "wet_ingredient_fallback",
                blocking_field=f"unknown food '{ingredient.food_id}'",
            )
        wet = is_wet(food)
        if wet is None:
            return PhResolution(
                None, TruthLabel.UNCONFIRMED, "wet_ingredient_fallback",
                blocking_field=f"{food.id}.water_content_pct",
            )
        if not wet:
            continue
        if not food.ph.usable:
            return PhResolution(
                None, TruthLabel.UNCONFIRMED, "wet_ingredient_fallback",
                blocking_field=f"{food.id}.ph",
            )
        wet_phs.append(float(food.ph.value))

    if not wet_phs:
        return PhResolution(
            None, TruthLabel.UNCONFIRMED, "wet_ingredient_fallback",
            blocking_field="no wet ingredient in the recipe",
        )

    return PhResolution(
        value=min(wet_phs), status=TruthLabel.CALCULATED, origin="wet_ingredient_fallback"
    )


def aggregate_substrate_loads(
    trigger_food_ids, foods: Mapping[str, Food]
) -> dict[str, Tracked]:
    """Spec §6.7 — loads for foods sharing a substrate are SUMMED, never max-ed.

    A meal with beans and lentils presents more GOS than either alone. If any
    contributing food's load is unconfirmed, the whole substrate is unconfirmed
    and names the offender.
    """
    totals: dict[str, float] = {}
    blockers: dict[str, list[str]] = {}
    sources: dict[str, list[str]] = {}

    for fid in trigger_food_ids:
        food = foods.get(fid)
        if food is None:
            continue
        for sid in food.contains_substrate_ids:
            if not food.typical_load_value.usable:
                blockers.setdefault(sid, []).append(fid)
                continue
            totals[sid] = totals.get(sid, 0.0) + float(food.typical_load_value.value)
            sources.setdefault(sid, []).append(fid)

    out: dict[str, Tracked] = {}
    for sid in set(totals) | set(blockers):
        if sid in blockers:
            out[sid] = Tracked(
                value=None,
                status=TruthLabel.UNCONFIRMED,
                source="no typical_load_value for: " + ", ".join(sorted(blockers[sid])),
            )
        else:
            out[sid] = Tracked(
                value=totals[sid],
                status=TruthLabel.CONFIRMED,
                source="summed across: " + ", ".join(sorted(sources[sid])),
            )
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/engine/test_conventions.py -v`
Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/engine/conventions.py tests/engine/test_conventions.py
git commit -m "feat(engine): add shared conventions for wetness, pH resolution, load summing"
```

---

## Task 9: GI model

R2 needs to know, per enzyme per region, whether the enzyme is active there.

**Files:**
- Create: `src/foodbrew/engine/gi_model.py`
- Test: `tests/engine/test_gi_model.py`

- [ ] **Step 1: Write the failing test**

`tests/engine/test_gi_model.py`:

```python
from foodbrew.engine.gi_model import active_regions, overlaps_region, regions_before_deadline
from foodbrew.engine.types import Deadline, Enzyme, GIRegion, Tracked, TruthLabel
from foodbrew.seedload.loader import load_seed

SEED = load_seed()
REGIONS = SEED.gi_regions


def _enzyme(ph_min, ph_max, deadline=Deadline.BEFORE_COLON, status=TruthLabel.CONFIRMED):
    return Enzyme(
        id="x", name="X", substrate_id="lactose", source_type="fungal", priority="high",
        deadline=deadline,
        ph_min=Tracked(ph_min, status, "t"), ph_max=Tracked(ph_max, status, "t"),
        ph_opt_low=Tracked(5.0, status, "t"), ph_opt_high=Tracked(5.0, status, "t"),
        ph_shelf_stable_min=Tracked(None, TruthLabel.UNCONFIRMED), dose_unit="FCC",
    )


def test_overlaps_region_true_when_ranges_intersect():
    fed = GIRegion(id="stomach_fed", name="", ph_low=4.0, ph_high=6.0, order=3)
    assert overlaps_region(_enzyme(2.5, 5.4), fed) is True


def test_overlaps_region_false_when_disjoint():
    jejunum = GIRegion(id="jejunum_ileum", name="", ph_low=7.0, ph_high=7.5, order=5)
    assert overlaps_region(_enzyme(2.5, 5.4), jejunum) is False


def test_mouth_is_never_active_even_when_ph_fits():
    # Spec §8 — dwell is seconds, so the mouth is dormant regardless of pH fit.
    ids = {r.id for r in active_regions(_enzyme(6.0, 8.0), REGIONS)}
    assert "mouth" not in ids


def test_fungal_lactase_active_in_fed_stomach_not_duodenum():
    # Spec §8: lactase's 5.4 ceiling drops it out at the duodenum.
    ids = {r.id for r in active_regions(_enzyme(2.5, 5.4), REGIONS)}
    assert "stomach_fed" in ids
    assert "duodenum" not in ids


def test_xylose_isomerase_active_in_jejunum():
    ids = {r.id for r in active_regions(_enzyme(7.0, 9.0), REGIONS)}
    assert "jejunum_ileum" in ids


def test_active_regions_empty_when_ph_unconfirmed():
    assert active_regions(_enzyme(2.5, 5.4, status=TruthLabel.UNCONFIRMED), REGIONS) == ()


def test_regions_before_colon_deadline_excludes_colon():
    ids = {r.id for r in regions_before_deadline(Deadline.BEFORE_COLON, REGIONS)}
    assert "colon" not in ids
    assert "jejunum_ileum" in ids


def test_regions_before_small_intestine_deadline_stops_at_stomach():
    ids = {r.id for r in regions_before_deadline(Deadline.BEFORE_SMALL_INTESTINE, REGIONS)}
    assert ids == {"mouth", "stomach_fasting", "stomach_fed"}


def test_small_intestine_deadline_includes_small_intestine_regions():
    ids = {r.id for r in regions_before_deadline(Deadline.SMALL_INTESTINE, REGIONS)}
    assert "duodenum" in ids and "jejunum_ileum" in ids and "colon" not in ids
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/engine/test_gi_model.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'foodbrew.engine.gi_model'`

- [ ] **Step 3: Write the implementation**

`src/foodbrew/engine/gi_model.py`:

```python
"""Spec §8 — where along the tract an enzyme's pH window actually lets it work."""

from __future__ import annotations

from foodbrew.engine.types import Deadline, Enzyme, GIRegion

#: Regions that lie at or before each deadline. Spec §8: these are deadlines,
#: not anatomical targets — the enzyme must finish its work by then.
_REGIONS_AT_OR_BEFORE: dict[Deadline, frozenset[str]] = {
    Deadline.BEFORE_SMALL_INTESTINE: frozenset({"mouth", "stomach_fasting", "stomach_fed"}),
    Deadline.SMALL_INTESTINE: frozenset(
        {"mouth", "stomach_fasting", "stomach_fed", "duodenum", "jejunum_ileum"}
    ),
    Deadline.BEFORE_COLON: frozenset(
        {"mouth", "stomach_fasting", "stomach_fed", "duodenum", "jejunum_ileum"}
    ),
}


def overlaps_region(enzyme: Enzyme, region: GIRegion) -> bool:
    """Does the enzyme's activity range intersect this region's pH range?"""
    if not (enzyme.ph_min.usable and enzyme.ph_max.usable):
        return False
    return (
        float(enzyme.ph_min.value) <= region.ph_high
        and float(enzyme.ph_max.value) >= region.ph_low
    )


def active_regions(enzyme: Enzyme, regions: tuple[GIRegion, ...]) -> tuple[GIRegion, ...]:
    """Regions where the enzyme can actually act.

    Dormant regions (the mouth) are excluded regardless of pH fit: spec §8 says
    dwell there is seconds, too brief for any enzyme to react.
    """
    return tuple(r for r in regions if not r.dormant and overlaps_region(enzyme, r))


def regions_before_deadline(
    deadline: Deadline, regions: tuple[GIRegion, ...]
) -> tuple[GIRegion, ...]:
    allowed = _REGIONS_AT_OR_BEFORE[deadline]
    return tuple(r for r in regions if r.id in allowed)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/engine/test_gi_model.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/engine/gi_model.py tests/engine/test_gi_model.py
git commit -m "feat(engine): add GI model with dormant-mouth and deadline handling"
```

---

## Task 10: Rule registry scaffold

Every rule module conforms to one shape so the orchestrator can iterate blindly.

**Files:**
- Create: `src/foodbrew/engine/rules/__init__.py`
- Test: `tests/engine/test_rule_registry.py`

- [ ] **Step 1: Write the failing test**

`tests/engine/test_rule_registry.py`:

```python
from foodbrew.engine.rules import ADVISORY_RULE_IDS, HEADLINE_RULE_IDS, ALL_RULES


def test_registry_is_ordered_r1_through_r16_without_r13():
    # R13 is aggregation itself (spec §6.1), not a finding-producing rule.
    ids = [m.RULE_ID for m in ALL_RULES]
    assert ids == [f"R{n}" for n in range(1, 17) if n != 13]


def test_every_rule_module_exposes_the_contract():
    for module in ALL_RULES:
        assert isinstance(module.RULE_ID, str)
        assert isinstance(module.ADVISORY, bool)
        assert callable(module.evaluate)


def test_headline_and_advisory_sets_match_spec_6_4():
    # Spec §6.4: headline = R1-R7, R11, R14, plus R15. Advisory = R8, R9, R10, R12, R16.
    assert HEADLINE_RULE_IDS == frozenset(
        {"R1", "R2", "R3", "R4", "R5", "R6", "R7", "R11", "R14", "R15"}
    )
    assert ADVISORY_RULE_IDS == frozenset({"R8", "R9", "R10", "R12", "R16"})


def test_sets_are_disjoint_and_cover_every_rule():
    ids = {m.RULE_ID for m in ALL_RULES}
    assert HEADLINE_RULE_IDS & ADVISORY_RULE_IDS == frozenset()
    assert HEADLINE_RULE_IDS | ADVISORY_RULE_IDS == ids
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/engine/test_rule_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'foodbrew.engine.rules'`

- [ ] **Step 3: Write the registry**

`src/foodbrew/engine/rules/__init__.py`:

```python
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
```

- [ ] **Step 4: Create fifteen placeholder rule modules so the registry imports**

For each of the fifteen module names in `ALL_RULES`, create the file with this exact content, substituting `RULE_ID` and `ADVISORY` from the table below:

```python
"""Placeholder — implemented in a later task."""

from __future__ import annotations

RULE_ID = "R1"
ADVISORY = False


def evaluate(ctx):  # noqa: ARG001
    return []
```

| Module | RULE_ID | ADVISORY |
|---|---|---|
| `r01_ph_survival.py` | `"R1"` | `False` |
| `r02_gi_window.py` | `"R2"` | `False` |
| `r03_no_heat.py` | `"R3"` | `False` |
| `r04_water_activation.py` | `"R4"` | `False` |
| `r05_protease_conflict.py` | `"R5"` | `False` |
| `r06_encapsulation.py` | `"R6"` | `False` |
| `r07_dosing.py` | `"R7"` | `False` |
| `r08_taste_drift.py` | `"R8"` | `True` |
| `r09_prebiotic_tension.py` | `"R9"` | `True` |
| `r10_strain_blending.py` | `"R10"` | `True` |
| `r11_food_grade.py` | `"R11"` | `False` |
| `r12_temperature.py` | `"R12"` | `True` |
| `r14_substrate_coverage.py` | `"R14"` | `False` |
| `r15_applied_texture.py` | `"R15"` | `False` |
| `r16_clean_label.py` | `"R16"` | `True` |

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/engine/test_rule_registry.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add src/foodbrew/engine/rules/ tests/engine/test_rule_registry.py
git commit -m "feat(engine): add rule registry with headline/advisory partition"
```

---

## Task 11: R1 — in-jar pH survival

The rule the KB §4m vinaigrette case turns on, and the one carrying the stated fallback margin.

**Files:**
- Modify: `src/foodbrew/engine/rules/r01_ph_survival.py`
- Test: `tests/engine/test_r01_ph_survival.py`

- [ ] **Step 1: Write the failing test**

`tests/engine/test_r01_ph_survival.py`:

```python
import pytest

from foodbrew.engine.rules import r01_ph_survival as r1
from foodbrew.engine.types import (
    Deadline, Enzyme, EvalContext, Food, Format, Formulation, Phase,
    SelectedEnzyme, Tracked, TruthLabel, Verdict,
)

FALLBACK_MARGIN = 1.0


def _lactase(shelf_floor=None, shelf_status=TruthLabel.UNCONFIRMED):
    return Enzyme(
        id="lactase", name="Lactase (fungal, acid)", substrate_id="lactose",
        source_type="fungal", priority="high", deadline=Deadline.BEFORE_SMALL_INTESTINE,
        ph_min=Tracked(2.5, TruthLabel.CONFIRMED, "KB"),
        ph_max=Tracked(5.4, TruthLabel.CONFIRMED, "KB"),
        ph_opt_low=Tracked(5.0, TruthLabel.CONFIRMED, "KB"),
        ph_opt_high=Tracked(5.0, TruthLabel.CONFIRMED, "KB"),
        ph_shelf_stable_min=Tracked(shelf_floor, shelf_status, "t"),
        dose_unit="FCC",
    )


def _ctx(fmt, ph, phase=Phase.WET, enzyme=None):
    e = enzyme or _lactase()
    form = Formulation(
        id="f", format=fmt, recipe=(), enzymes=(SelectedEnzyme("lactase", 9000.0, phase),),
        measured_ph=Tracked(ph, TruthLabel.USER_PROVIDED, "bench") if ph is not None
        else Tracked(None, TruthLabel.UNCONFIRMED),
    )
    return EvalContext(formulation=form, enzymes={"lactase": e}, foods={}, substrates={})


def test_vinaigrette_at_ph_3_is_red_via_fallback_margin():
    # Spec §6.1 R1 worked case: ph_min 2.5 + 1.0 = 3.5 floor; 3.0 breaches it.
    findings = r1.evaluate(_ctx(Format.PREMIXED_WET, 3.0))
    assert len(findings) == 1
    assert findings[0].verdict is Verdict.RED
    assert findings[0].evidence["fallback_floor"] == pytest.approx(3.5)
    assert "margin heuristic" in findings[0].message


def test_ph_4_4_is_amber_below_optimum_but_above_floor():
    # DEVIATION note in this plan: R1's rule text makes this AMBER, not pass.
    findings = r1.evaluate(_ctx(Format.PREMIXED_WET, 4.4))
    assert findings[0].verdict is Verdict.AMBER
    assert "below its optimum" in findings[0].message


def test_ph_at_optimum_passes():
    findings = r1.evaluate(_ctx(Format.PREMIXED_WET, 5.0))
    assert findings[0].verdict is Verdict.PASS


def test_confirmed_shelf_floor_is_used_instead_of_fallback():
    e = _lactase(shelf_floor=4.0, shelf_status=TruthLabel.CONFIRMED)
    findings = r1.evaluate(_ctx(Format.PREMIXED_WET, 3.8, enzyme=e))
    assert findings[0].verdict is Verdict.RED
    assert findings[0].evidence["floor_source"] == "ph_shelf_stable_min"
    assert "margin heuristic" not in findings[0].message


def test_dry_phase_enzyme_is_skipped():
    assert r1.evaluate(_ctx(Format.DUAL_CHAMBER, 3.0, phase=Phase.DRY)) == []


def test_dry_sachet_format_is_skipped():
    assert r1.evaluate(_ctx(Format.DRY_SACHET, 3.0, phase=Phase.DRY)) == []


def test_unresolvable_ph_is_cannot_assess():
    findings = r1.evaluate(_ctx(Format.PREMIXED_WET, None))
    assert findings[0].verdict is Verdict.CANNOT_ASSESS
    assert "no wet ingredient" in findings[0].message


def test_unconfirmed_ph_min_is_cannot_assess():
    e = Enzyme(
        id="lactase", name="L", substrate_id="lactose", source_type="fungal",
        priority="high", deadline=Deadline.BEFORE_SMALL_INTESTINE,
        ph_min=Tracked(None, TruthLabel.UNCONFIRMED), ph_max=Tracked(None, TruthLabel.UNCONFIRMED),
        ph_opt_low=Tracked(None, TruthLabel.UNCONFIRMED),
        ph_opt_high=Tracked(None, TruthLabel.UNCONFIRMED),
        ph_shelf_stable_min=Tracked(None, TruthLabel.UNCONFIRMED), dose_unit="",
    )
    findings = r1.evaluate(_ctx(Format.PREMIXED_WET, 3.0, enzyme=e))
    assert findings[0].verdict is Verdict.CANNOT_ASSESS
    assert "ph_min" in findings[0].message
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/engine/test_r01_ph_survival.py -v`
Expected: FAIL — 8 failures, all asserting on an empty findings list

- [ ] **Step 3: Write the implementation**

Replace `src/foodbrew/engine/rules/r01_ph_survival.py`:

```python
"""R1 — in-jar pH survival (spec §6.1, KB §4a)."""

from __future__ import annotations

from foodbrew.engine.conventions import resolve_recipe_ph
from foodbrew.engine.types import (
    EvalContext, Format, Phase, RuleFinding, TruthLabel, Verdict,
)

RULE_ID = "R1"
ADVISORY = False

#: Spec §6.1 R1 — stated fallback when no supplier has confirmed a shelf-stable
#: floor. An engineering convention that makes the rule testable, NOT a
#: scientific claim; every finding using it says so (spec §12 item 3).
FALLBACK_MARGIN_PH = 1.0

#: Formats where an enzyme in the wet phase sits in liquid for shelf duration.
_WET_CONTACT_FORMATS = {Format.PREMIXED_WET, Format.ENCAPSULATED_IN_WET}


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    if ctx.formulation.format not in _WET_CONTACT_FORMATS:
        return []

    findings: list[RuleFinding] = []
    ph = resolve_recipe_ph(ctx.formulation, ctx.foods, ctx.latest_trial_ph)

    for selected in ctx.selected_enzymes():
        if selected.phase is not Phase.WET:
            continue
        enzyme = ctx.enzyme_for(selected)

        if not enzyme.ph_min.usable:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.CANNOT_ASSESS,
                    f"{enzyme.name}: cannot assess in-jar pH survival because "
                    f"ph_min is unconfirmed. Confirm with the supplier.",
                    {"missing_field": f"{enzyme.id}.ph_min"},
                    enzyme_id=enzyme.id,
                )
            )
            continue

        if ph.value is None:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.CANNOT_ASSESS,
                    f"{enzyme.name}: cannot assess in-jar pH survival because the "
                    f"recipe pH could not be resolved ({ph.blocking_field}). Enter a "
                    f"measured pH for this formulation, or confirm the ingredient data.",
                    {"blocking_field": ph.blocking_field, "ph_origin": ph.origin},
                    enzyme_id=enzyme.id,
                )
            )
            continue

        if enzyme.ph_shelf_stable_min.usable:
            floor = float(enzyme.ph_shelf_stable_min.value)
            floor_source = "ph_shelf_stable_min"
            heuristic_note = ""
        else:
            floor = float(enzyme.ph_min.value) + FALLBACK_MARGIN_PH
            floor_source = "fallback"
            heuristic_note = (
                " This uses the stated margin heuristic (ph_min + "
                f"{FALLBACK_MARGIN_PH}) because no shelf-stable floor is confirmed — "
                "supplier confirmation required."
            )

        evidence = {
            "recipe_ph": ph.value,
            "ph_origin": ph.origin,
            "ph_status": ph.status.value,
            "floor": floor,
            "floor_source": floor_source,
            "ph_min": float(enzyme.ph_min.value),
            "fallback_floor": float(enzyme.ph_min.value) + FALLBACK_MARGIN_PH,
        }

        if ph.value < floor:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.RED,
                    f"{enzyme.name}: recipe pH {ph.value} is below the sustained-exposure "
                    f"floor of {floor}, so the enzyme is expected to denature on the shelf. "
                    f"Denaturation is permanent.{heuristic_note}",
                    evidence, enzyme_id=enzyme.id,
                )
            )
            continue

        opt_low = float(enzyme.ph_opt_low.value) if enzyme.ph_opt_low.usable else None
        if opt_low is not None and ph.value < opt_low:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.AMBER,
                    f"{enzyme.name}: recipe pH {ph.value} is above the survival floor but "
                    f"below its optimum of {opt_low}, so activity is sluggish. Survival is "
                    f"not the same as activity; a sluggish enzyme recovers once conditions "
                    f"improve, provided it has not denatured.",
                    evidence | {"ph_opt_low": opt_low}, enzyme_id=enzyme.id,
                )
            )
            continue

        findings.append(
            RuleFinding(
                RULE_ID, Verdict.PASS,
                f"{enzyme.name}: recipe pH {ph.value} sits at or above its optimum.",
                evidence, enzyme_id=enzyme.id,
            )
        )

    return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/engine/test_r01_ph_survival.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/engine/rules/r01_ph_survival.py tests/engine/test_r01_ph_survival.py
git commit -m "feat(engine): implement R1 in-jar pH survival with stated fallback margin"
```

---

## Task 12: R2 — GI window vs deadline

**Files:**
- Modify: `src/foodbrew/engine/rules/r02_gi_window.py`
- Test: `tests/engine/test_r02_gi_window.py`

- [ ] **Step 1: Write the failing test**

`tests/engine/test_r02_gi_window.py`:

```python
from foodbrew.engine.rules import r02_gi_window as r2
from foodbrew.engine.types import (
    Deadline, Enzyme, EvalContext, Format, Formulation, Phase,
    SelectedEnzyme, Substrate, Tracked, TruthLabel, Verdict,
)
from foodbrew.seedload.loader import load_seed

SEED = load_seed()


def _enzyme(eid, ph_min, ph_max, deadline, substrate_id="lactose",
            status=TruthLabel.CONFIRMED):
    return Enzyme(
        id=eid, name=eid, substrate_id=substrate_id, source_type="fungal",
        priority="high", deadline=deadline,
        ph_min=Tracked(ph_min, status, "t"), ph_max=Tracked(ph_max, status, "t"),
        ph_opt_low=Tracked(5.0, status, "t"), ph_opt_high=Tracked(5.0, status, "t"),
        ph_shelf_stable_min=Tracked(None, TruthLabel.UNCONFIRMED), dose_unit="FCC",
    )


def _ctx(enzyme):
    form = Formulation(
        id="f", format=Format.DUAL_CHAMBER, recipe=(),
        enzymes=(SelectedEnzyme(enzyme.id, 9000.0, Phase.DRY),),
    )
    return EvalContext(
        formulation=form, enzymes={enzyme.id: enzyme}, foods={},
        substrates=SEED.substrates, gi_regions=SEED.gi_regions,
    )


def test_lactase_passes_with_fed_stomach_coverage():
    e = _enzyme("lactase", 2.5, 5.4, Deadline.BEFORE_SMALL_INTESTINE)
    f = r2.evaluate(_ctx(e))[0]
    assert f.verdict is Verdict.PASS
    assert "stomach_fed" in f.evidence["active_before_deadline"]


def test_alpha_gal_passes_before_colon():
    e = _enzyme("alpha_gal", 3.0, 8.0, Deadline.BEFORE_COLON, substrate_id="gos")
    f = r2.evaluate(_ctx(e))[0]
    assert f.verdict is Verdict.PASS


def test_enzyme_with_no_active_region_before_deadline_is_red():
    # pH 7.0-9.0 with a before-small-intestine deadline: nothing pre-duodenum fits.
    e = _enzyme("late", 7.0, 9.0, Deadline.BEFORE_SMALL_INTESTINE)
    f = r2.evaluate(_ctx(e))[0]
    assert f.verdict is Verdict.RED
    assert "no active window" in f.message


def test_hard_deadline_substrate_is_named_in_the_message():
    e = _enzyme("alpha_gal", 3.0, 8.0, Deadline.BEFORE_COLON, substrate_id="gos")
    f = r2.evaluate(_ctx(e))[0]
    assert "no native human enzyme" in f.message


def test_unconfirmed_ph_is_cannot_assess():
    e = _enzyme("x", 3.0, 8.0, Deadline.BEFORE_COLON, status=TruthLabel.UNCONFIRMED)
    f = r2.evaluate(_ctx(e))[0]
    assert f.verdict is Verdict.CANNOT_ASSESS


def test_mouth_never_counts_as_coverage():
    e = _enzyme("mouthonly", 6.2, 7.6, Deadline.BEFORE_SMALL_INTESTINE)
    f = r2.evaluate(_ctx(e))[0]
    assert f.verdict is Verdict.RED
    assert "mouth" not in f.evidence["active_before_deadline"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/engine/test_r02_gi_window.py -v`
Expected: FAIL — IndexError on empty findings list

- [ ] **Step 3: Write the implementation**

Replace `src/foodbrew/engine/rules/r02_gi_window.py`:

```python
"""R2 — GI window vs deadline (spec §6.1, KB §4a and §4h)."""

from __future__ import annotations

from foodbrew.engine.gi_model import active_regions, regions_before_deadline
from foodbrew.engine.types import EvalContext, RuleFinding, Verdict

RULE_ID = "R2"
ADVISORY = False


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    findings: list[RuleFinding] = []

    for selected in ctx.selected_enzymes():
        enzyme = ctx.enzyme_for(selected)

        if not (enzyme.ph_min.usable and enzyme.ph_max.usable):
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.CANNOT_ASSESS,
                    f"{enzyme.name}: cannot map its active window against the digestive "
                    f"tract because its pH range is unconfirmed. Confirm with the supplier.",
                    {"missing_field": f"{enzyme.id}.ph_min/ph_max"},
                    enzyme_id=enzyme.id,
                )
            )
            continue

        allowed = {r.id for r in regions_before_deadline(enzyme.deadline, ctx.gi_regions)}
        active = active_regions(enzyme, ctx.gi_regions)
        active_before = [r.id for r in active if r.id in allowed]
        active_after = [r.id for r in active if r.id not in allowed]

        substrate = ctx.substrates.get(enzyme.substrate_id)
        hard_deadline = substrate is not None and not substrate.native_human_enzyme
        deadline_note = ""
        if hard_deadline:
            deadline_note = (
                f" {substrate.name} has no native human enzyme, so whatever reaches the "
                f"colon undigested is fermented there — that fermentation is the symptom. "
                f"There is no catching up."
            )

        evidence = {
            "deadline": enzyme.deadline.value,
            "active_before_deadline": active_before,
            "active_after_deadline": active_after,
            "ph_min": float(enzyme.ph_min.value),
            "ph_max": float(enzyme.ph_max.value),
            "hard_deadline": hard_deadline,
        }

        if not active_before:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.RED,
                    f"{enzyme.name}: no active window anywhere before its "
                    f"{enzyme.deadline.value.replace('_', ' ')} deadline. Its pH range "
                    f"{enzyme.ph_min.value}-{enzyme.ph_max.value} does not overlap any "
                    f"region it must work in.{deadline_note}",
                    evidence, enzyme_id=enzyme.id,
                )
            )
        elif len(active_before) == 1:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.AMBER,
                    f"{enzyme.name}: active in only one region before its deadline "
                    f"({active_before[0]}). A narrow window leaves little margin if "
                    f"transit is fast or the meal buffers differently.{deadline_note}",
                    evidence, enzyme_id=enzyme.id,
                )
            )
        else:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.PASS,
                    f"{enzyme.name}: active in {', '.join(active_before)} before its "
                    f"deadline.{deadline_note}",
                    evidence, enzyme_id=enzyme.id,
                )
            )

    return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/engine/test_r02_gi_window.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/engine/rules/r02_gi_window.py tests/engine/test_r02_gi_window.py
git commit -m "feat(engine): implement R2 GI window against enzyme deadlines"
```

---

## Task 13: R3 — no heat

**Files:**
- Modify: `src/foodbrew/engine/rules/r03_no_heat.py`
- Test: `tests/engine/test_r03_no_heat.py`

- [ ] **Step 1: Write the failing test**

`tests/engine/test_r03_no_heat.py`:

```python
from foodbrew.engine.rules import r03_no_heat as r3
from foodbrew.engine.types import (
    EvalContext, Food, Format, Formulation, Phase, ProcessStep,
    RecipeIngredient, SelectedEnzyme, Tracked, TruthLabel, Verdict,
)


def _ctx(steps, addition_index, foods=None, recipe=()):
    form = Formulation(
        id="f", format=Format.PREMIXED_WET, recipe=recipe,
        enzymes=(SelectedEnzyme("e", 100.0, Phase.WET),),
        process_steps=steps, enzyme_addition_index=addition_index,
    )
    return EvalContext(
        formulation=form, enzymes={}, foods=foods or {}, substrates={}
    )


HEAT_THEN_ENZYME = (
    ProcessStep(1, "Blend base"),
    ProcessStep(2, "Pasteurise", is_heat=True),
    ProcessStep(3, "Add enzyme"),
)
ENZYME_THEN_HEAT = (
    ProcessStep(1, "Blend base"),
    ProcessStep(2, "Add enzyme"),
    ProcessStep(3, "Hot fill", is_heat=True),
)


def test_heat_after_enzyme_addition_is_red():
    f = r3.evaluate(_ctx(ENZYME_THEN_HEAT, addition_index=2))[0]
    assert f.verdict is Verdict.RED
    assert "Hot fill" in f.message
    assert "after the heat step" in f.message


def test_heat_at_the_same_index_as_addition_is_red():
    steps = (ProcessStep(1, "Blend"), ProcessStep(2, "Heat and add enzyme", is_heat=True))
    f = r3.evaluate(_ctx(steps, addition_index=2))[0]
    assert f.verdict is Verdict.RED


def test_heat_strictly_before_addition_passes():
    f = r3.evaluate(_ctx(HEAT_THEN_ENZYME, addition_index=3))[0]
    assert f.verdict is Verdict.PASS


def test_no_heat_steps_at_all_passes():
    steps = (ProcessStep(1, "Blend"), ProcessStep(2, "Add enzyme"))
    f = r3.evaluate(_ctx(steps, addition_index=2))[0]
    assert f.verdict is Verdict.PASS


def test_missing_addition_index_is_cannot_assess():
    f = r3.evaluate(_ctx(ENZYME_THEN_HEAT, addition_index=None))[0]
    assert f.verdict is Verdict.CANNOT_ASSESS
    assert "enzyme_addition_index" in f.message


def test_no_process_steps_is_cannot_assess():
    f = r3.evaluate(_ctx((), addition_index=None))[0]
    assert f.verdict is Verdict.CANNOT_ASSESS


def test_cooked_protease_food_emits_a_suppression_note():
    # Spec §6.1 R3 / KB §4j: cooking destroys naturally occurring enzymes, so a
    # cooked pineapple no longer contributes protease. R5 reads the same flag.
    foods = {
        "pineapple_fresh": Food(
            id="pineapple_fresh", name="Pineapple", category="fruit",
            contains_protease=True, is_heat_processed=True,
        )
    }
    findings = r3.evaluate(
        _ctx(HEAT_THEN_ENZYME, 3, foods=foods, recipe=(RecipeIngredient("pineapple_fresh", 20.0),))
    )
    notes = [f for f in findings if f.food_id == "pineapple_fresh"]
    assert len(notes) == 1
    assert notes[0].verdict is Verdict.PASS
    assert "no longer contributes protease" in notes[0].message
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/engine/test_r03_no_heat.py -v`
Expected: FAIL — IndexError on empty findings

- [ ] **Step 3: Write the implementation**

Replace `src/foodbrew/engine/rules/r03_no_heat.py`:

```python
"""R3 — no heat after the enzyme goes in (spec §6.1, KB §4b and §4j)."""

from __future__ import annotations

from foodbrew.engine.types import EvalContext, RuleFinding, Verdict

RULE_ID = "R3"
ADVISORY = False


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    form = ctx.formulation
    findings: list[RuleFinding] = []

    if not form.process_steps or form.enzyme_addition_index is None:
        findings.append(
            RuleFinding(
                RULE_ID, Verdict.CANNOT_ASSESS,
                "Cannot check the no-heat rule: the process sequence or the "
                "enzyme_addition_index is not recorded. Add the process steps and mark "
                "where the enzyme goes in.",
                {"missing_field": "process_steps / enzyme_addition_index"},
            )
        )
    else:
        offending = [
            s for s in form.process_steps
            if s.is_heat and s.order >= form.enzyme_addition_index
        ]
        evidence = {
            "enzyme_addition_index": form.enzyme_addition_index,
            "heat_steps": [
                {"order": s.order, "label": s.label}
                for s in form.process_steps if s.is_heat
            ],
        }
        if offending:
            labels = ", ".join(f"'{s.label}' (step {s.order})" for s in offending)
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.RED,
                    f"Heat is applied at or after the enzyme goes in: {labels}. Heat "
                    f"denatures the enzyme and denaturation is permanent. Move the enzyme "
                    f"addition to after the heat step, at the end.",
                    evidence,
                )
            )
        else:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.PASS,
                    "No heat step falls at or after the enzyme addition point.",
                    evidence,
                )
            )

    # KB §4j informational notes — a cooked protease-bearing food no longer
    # contributes protease, which suppresses the R5 conflict for that food.
    for ingredient in form.recipe:
        food = ctx.foods.get(ingredient.food_id)
        if food is None or not food.contains_protease or not food.is_heat_processed:
            continue
        findings.append(
            RuleFinding(
                RULE_ID, Verdict.PASS,
                f"{food.name} is heat-processed, so it no longer contributes protease "
                f"(cooking destroys naturally occurring enzymes). Its co-formulation "
                f"conflict is suppressed.",
                {"food": food.id, "is_heat_processed": True},
                food_id=food.id,
            )
        )

    return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/engine/test_r03_no_heat.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/engine/rules/r03_no_heat.py tests/engine/test_r03_no_heat.py
git commit -m "feat(engine): implement R3 no-heat rule with cooked-protease suppression"
```

---

## Task 14: R4 — water activation

Calibrated so a creamy premix lands AMBER while an acidic vinaigrette REDs through R1 — this is what reproduces KB §4m's three tiers without hardcoding them.

**Files:**
- Modify: `src/foodbrew/engine/rules/r04_water_activation.py`
- Test: `tests/engine/test_r04_water_activation.py`

- [ ] **Step 1: Write the failing test**

`tests/engine/test_r04_water_activation.py`:

```python
import pytest

from foodbrew.engine.rules import r04_water_activation as r4
from foodbrew.engine.types import (
    EvalContext, Format, Formulation, Phase, SelectedEnzyme, Verdict,
)


def _ctx(fmt, phase=Phase.WET, with_enzyme=True):
    enzymes = (SelectedEnzyme("e", 100.0, phase),) if with_enzyme else ()
    return EvalContext(
        formulation=Formulation(id="f", format=fmt, recipe=(), enzymes=enzymes),
        enzymes={}, foods={}, substrates={},
    )


def test_premixed_wet_is_amber_never_red_on_its_own():
    f = r4.evaluate(_ctx(Format.PREMIXED_WET))[0]
    assert f.verdict is Verdict.AMBER


def test_premixed_wet_message_refuses_to_read_as_a_green_light():
    f = r4.evaluate(_ctx(Format.PREMIXED_WET))[0]
    assert "physical separation" in f.message
    assert "bench stability data" in f.message


@pytest.mark.parametrize("fmt", [Format.DRY_SACHET, Format.DUAL_CHAMBER])
def test_dry_formats_pass(fmt):
    f = r4.evaluate(_ctx(fmt, phase=Phase.DRY))[0]
    assert f.verdict is Verdict.PASS


def test_encapsulated_in_wet_is_amber_and_defers_to_r6():
    f = r4.evaluate(_ctx(Format.ENCAPSULATED_IN_WET))[0]
    assert f.verdict is Verdict.AMBER
    assert "R6" in f.message


def test_dual_chamber_with_an_enzyme_wrongly_in_the_wet_phase_is_amber():
    f = r4.evaluate(_ctx(Format.DUAL_CHAMBER, phase=Phase.WET))[0]
    assert f.verdict is Verdict.AMBER


def test_no_enzymes_selected_produces_no_finding():
    assert r4.evaluate(_ctx(Format.PREMIXED_WET, with_enzyme=False)) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/engine/test_r04_water_activation.py -v`
Expected: FAIL — IndexError on empty findings

- [ ] **Step 3: Write the implementation**

Replace `src/foodbrew/engine/rules/r04_water_activation.py`:

```python
"""R4 — water activation (spec §6.1, KB §4c).

Dry is inert; wet is active and unstoppable. R4 alone never REDs: the magnitude
of activity loss is unknown without bench stability data. Escalation to RED comes
from R1 (pH kill), R5 (protease) or R6 through normal worst-of aggregation. That
calibration is what makes an acidic vinaigrette RED and a creamy premix AMBER
without hardcoding KB §4m.
"""

from __future__ import annotations

from foodbrew.engine.types import EvalContext, Format, Phase, RuleFinding, Verdict

RULE_ID = "R4"
ADVISORY = False

_SEPARATION_CAVEAT = (
    " An AMBER here is not a green light to ship premixed: KB §4c requires physical "
    "separation of the dry enzyme from the liquid for shelf life, and shipping wet "
    "requires bench stability data this tool cannot supply."
)


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    selected = ctx.selected_enzymes()
    if not selected:
        return []

    fmt = ctx.formulation.format
    wet_phase = [s for s in selected if s.phase is Phase.WET]
    evidence = {
        "format": fmt.value,
        "enzymes_in_wet_phase": [s.enzyme_id for s in wet_phase],
    }

    if fmt is Format.ENCAPSULATED_IN_WET:
        return [
            RuleFinding(
                RULE_ID, Verdict.AMBER,
                "The enzyme is encapsulated but still sits in liquid on the shelf. "
                "Encapsulation delays exposure rather than preventing it — see R6 for "
                "whether the capsule is being asked to do more than it can." + _SEPARATION_CAVEAT,
                evidence,
            )
        ]

    if not wet_phase:
        return [
            RuleFinding(
                RULE_ID, Verdict.PASS,
                "Every enzyme is kept dry and separate from the liquid, so it stays inert "
                "until use. Water is the on/off switch.",
                evidence,
            )
        ]

    names = ", ".join(s.enzyme_id for s in wet_phase)
    return [
        RuleFinding(
            RULE_ID, Verdict.AMBER,
            f"Water switches the enzyme on: {names} sits in liquid for the whole shelf "
            f"life, so activity decays and the enzyme digests the jar contents in the "
            f"meantime. How fast is unknown without stability data." + _SEPARATION_CAVEAT,
            evidence,
        )
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/engine/test_r04_water_activation.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/engine/rules/r04_water_activation.py tests/engine/test_r04_water_activation.py
git commit -m "feat(engine): implement R4 water activation calibrated to KB 4m tiers"
```

---

## Task 15: R5 — protease co-formulation

**Files:**
- Modify: `src/foodbrew/engine/rules/r05_protease_conflict.py`
- Test: `tests/engine/test_r05_protease_conflict.py`

- [ ] **Step 1: Write the failing test**

`tests/engine/test_r05_protease_conflict.py`:

```python
from foodbrew.engine.rules import r05_protease_conflict as r5
from foodbrew.engine.types import (
    Deadline, Enzyme, EvalContext, Food, Format, Formulation, Phase,
    RecipeIngredient, SelectedEnzyme, Tracked, TruthLabel, Verdict,
)


def _enzyme(eid, is_protease=False):
    return Enzyme(
        id=eid, name=eid, substrate_id="lactose", source_type="fungal", priority="high",
        deadline=Deadline.BEFORE_COLON,
        ph_min=Tracked(3.0, TruthLabel.CONFIRMED, "t"),
        ph_max=Tracked(7.0, TruthLabel.CONFIRMED, "t"),
        ph_opt_low=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
        ph_opt_high=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
        ph_shelf_stable_min=Tracked(None, TruthLabel.UNCONFIRMED),
        dose_unit="FCC", is_protease=is_protease,
    )


ENZYMES = {"lactase": _enzyme("lactase"), "bromelain": _enzyme("bromelain", True)}


def _ctx(selections, recipe=(), foods=None):
    return EvalContext(
        formulation=Formulation(
            id="f", format=Format.PREMIXED_WET, recipe=recipe, enzymes=selections
        ),
        enzymes=ENZYMES, foods=foods or {}, substrates={},
    )


def test_protease_sharing_wet_phase_with_another_enzyme_is_red():
    f = r5.evaluate(_ctx((
        SelectedEnzyme("lactase", 9000.0, Phase.WET),
        SelectedEnzyme("bromelain", 100.0, Phase.WET),
    )))[0]
    assert f.verdict is Verdict.RED
    assert "enzymes are proteins" in f.message


def test_protease_in_a_separate_phase_passes():
    f = r5.evaluate(_ctx((
        SelectedEnzyme("lactase", 9000.0, Phase.WET),
        SelectedEnzyme("bromelain", 100.0, Phase.DRY),
    )))[0]
    assert f.verdict is Verdict.PASS
    assert "separated" in f.message


def test_individually_encapsulated_protease_passes():
    f = r5.evaluate(_ctx((
        SelectedEnzyme("lactase", 9000.0, Phase.WET),
        SelectedEnzyme("bromelain", 100.0, Phase.WET, encapsulated=True),
    )))[0]
    assert f.verdict is Verdict.PASS


def test_protease_alone_in_wet_phase_passes():
    # Nothing for it to degrade.
    f = r5.evaluate(_ctx((SelectedEnzyme("bromelain", 100.0, Phase.WET),)))[0]
    assert f.verdict is Verdict.PASS


def test_raw_protease_bearing_ingredient_triggers_the_conflict():
    foods = {"pineapple_fresh": Food(
        id="pineapple_fresh", name="Pineapple (fresh)", category="fruit",
        contains_protease=True, is_heat_processed=False,
    )}
    f = r5.evaluate(_ctx(
        (SelectedEnzyme("lactase", 9000.0, Phase.WET),),
        recipe=(RecipeIngredient("pineapple_fresh", 20.0),), foods=foods,
    ))[0]
    assert f.verdict is Verdict.RED
    assert "Pineapple" in f.message


def test_cooked_protease_bearing_ingredient_does_not_trigger():
    foods = {"pineapple_fresh": Food(
        id="pineapple_fresh", name="Pineapple (fresh)", category="fruit",
        contains_protease=True, is_heat_processed=True,
    )}
    f = r5.evaluate(_ctx(
        (SelectedEnzyme("lactase", 9000.0, Phase.WET),),
        recipe=(RecipeIngredient("pineapple_fresh", 20.0),), foods=foods,
    ))[0]
    assert f.verdict is Verdict.PASS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/engine/test_r05_protease_conflict.py -v`
Expected: FAIL — IndexError on empty findings

- [ ] **Step 3: Write the implementation**

Replace `src/foodbrew/engine/rules/r05_protease_conflict.py`:

```python
"""R5 — protease co-formulation (spec §6.1, KB §4d)."""

from __future__ import annotations

from foodbrew.engine.types import EvalContext, Phase, RuleFinding, Verdict

RULE_ID = "R5"
ADVISORY = False


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    selected = ctx.selected_enzymes()
    if not selected:
        return []

    # A protease only threatens enzymes it shares an unprotected wet phase with.
    wet_unencapsulated = [
        s for s in selected if s.phase is Phase.WET and not s.encapsulated
    ]
    protease_selections = [
        s for s in wet_unencapsulated if ctx.enzyme_for(s).is_protease
    ]
    victims = [s for s in wet_unencapsulated if not ctx.enzyme_for(s).is_protease]

    # Raw protease-bearing ingredients count too. Cooked ones do not (KB §4j).
    raw_protease_foods = [
        ctx.foods[i.food_id]
        for i in ctx.formulation.recipe
        if i.food_id in ctx.foods
        and ctx.foods[i.food_id].contains_protease
        and not ctx.foods[i.food_id].is_heat_processed
    ]

    evidence = {
        "protease_enzymes": [s.enzyme_id for s in protease_selections],
        "protease_foods": [f.id for f in raw_protease_foods],
        "exposed_enzymes": [s.enzyme_id for s in victims],
    }

    has_threat = bool(protease_selections or raw_protease_foods)
    if has_threat and victims:
        sources = [ctx.enzyme_for(s).name for s in protease_selections]
        sources += [f.name for f in raw_protease_foods]
        exposed = ", ".join(ctx.enzyme_for(s).name for s in victims)
        return [
            RuleFinding(
                RULE_ID, Verdict.RED,
                f"Protease present in the same wet phase as {exposed}: "
                f"{', '.join(sources)}. A protease slowly destroys the other enzymes, "
                f"because enzymes are proteins. Keep them dry, in separate chambers, or "
                f"individually encapsulated.",
                evidence,
            )
        ]

    if has_threat:
        return [
            RuleFinding(
                RULE_ID, Verdict.PASS,
                "A protease is present but has no other enzyme sharing its active wet "
                "phase, so there is nothing for it to degrade.",
                evidence,
            )
        ]

    return [
        RuleFinding(
            RULE_ID, Verdict.PASS,
            "No protease shares an active wet phase with another enzyme — either none is "
            "present, or they are separated by phase or encapsulation.",
            evidence,
        )
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/engine/test_r05_protease_conflict.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/engine/rules/r05_protease_conflict.py tests/engine/test_r05_protease_conflict.py
git commit -m "feat(engine): implement R5 protease co-formulation conflict"
```

---

## Task 16: R6 — encapsulation semantics

**Files:**
- Modify: `src/foodbrew/engine/rules/r06_encapsulation.py`
- Test: `tests/engine/test_r06_encapsulation.py`

- [ ] **Step 1: Write the failing test**

`tests/engine/test_r06_encapsulation.py`:

```python
from foodbrew.engine.rules import r06_encapsulation as r6
from foodbrew.engine.types import (
    Deadline, Enzyme, EvalContext, Format, Formulation, Phase,
    SelectedEnzyme, Tracked, TruthLabel, Verdict,
)

LACTASE = Enzyme(
    id="lactase", name="Lactase", substrate_id="lactose", source_type="fungal",
    priority="high", deadline=Deadline.BEFORE_SMALL_INTESTINE,
    ph_min=Tracked(2.5, TruthLabel.CONFIRMED, "t"),
    ph_max=Tracked(5.4, TruthLabel.CONFIRMED, "t"),
    ph_opt_low=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
    ph_opt_high=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
    ph_shelf_stable_min=Tracked(None, TruthLabel.UNCONFIRMED), dose_unit="FCC",
)


def _ctx(fmt, ph):
    return EvalContext(
        formulation=Formulation(
            id="f", format=fmt, recipe=(),
            enzymes=(SelectedEnzyme("lactase", 9000.0, Phase.WET, encapsulated=True),),
            measured_ph=Tracked(ph, TruthLabel.USER_PROVIDED, "bench"),
        ),
        enzymes={"lactase": LACTASE}, foods={}, substrates={},
    )


def test_encapsulated_in_wet_below_the_floor_is_red():
    f = r6.evaluate(_ctx(Format.ENCAPSULATED_IN_WET, 3.0))[0]
    assert f.verdict is Verdict.RED
    assert "cannot rescue" in f.message


def test_encapsulated_in_wet_above_the_floor_passes():
    f = r6.evaluate(_ctx(Format.ENCAPSULATED_IN_WET, 5.0))[0]
    assert f.verdict is Verdict.PASS


def test_dual_chamber_lowers_the_bar_even_at_low_ph():
    # Spec §6.1 R6: the capsule must survive minutes plus stomach transit, not months.
    f = r6.evaluate(_ctx(Format.DUAL_CHAMBER, 3.0))[0]
    assert f.verdict is Verdict.PASS
    assert "minutes" in f.message


def test_premixed_wet_without_encapsulation_produces_no_finding():
    ctx = EvalContext(
        formulation=Formulation(
            id="f", format=Format.PREMIXED_WET, recipe=(),
            enzymes=(SelectedEnzyme("lactase", 9000.0, Phase.WET),),
            measured_ph=Tracked(3.0, TruthLabel.USER_PROVIDED, "b"),
        ),
        enzymes={"lactase": LACTASE}, foods={}, substrates={},
    )
    assert r6.evaluate(ctx) == []


def test_unresolvable_ph_is_cannot_assess():
    ctx = EvalContext(
        formulation=Formulation(
            id="f", format=Format.ENCAPSULATED_IN_WET, recipe=(),
            enzymes=(SelectedEnzyme("lactase", 9000.0, Phase.WET, encapsulated=True),),
        ),
        enzymes={"lactase": LACTASE}, foods={}, substrates={},
    )
    assert r6.evaluate(ctx)[0].verdict is Verdict.CANNOT_ASSESS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/engine/test_r06_encapsulation.py -v`
Expected: FAIL — IndexError on empty findings

- [ ] **Step 3: Write the implementation**

Replace `src/foodbrew/engine/rules/r06_encapsulation.py`:

```python
"""R6 — encapsulation semantics (spec §6.1, KB §4f).

Encapsulation is a timing control, not immunity. It delays exposure; it cannot
rescue an enzyme from a condition that denatures it on contact.
"""

from __future__ import annotations

from foodbrew.engine.conventions import resolve_recipe_ph
from foodbrew.engine.rules.r01_ph_survival import FALLBACK_MARGIN_PH
from foodbrew.engine.types import EvalContext, Format, Phase, RuleFinding, Verdict

RULE_ID = "R6"
ADVISORY = False


def _floor(enzyme) -> tuple[float | None, str]:
    if enzyme.ph_shelf_stable_min.usable:
        return float(enzyme.ph_shelf_stable_min.value), "ph_shelf_stable_min"
    if enzyme.ph_min.usable:
        return float(enzyme.ph_min.value) + FALLBACK_MARGIN_PH, "fallback"
    return None, "unavailable"


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    fmt = ctx.formulation.format
    encapsulated = [
        s for s in ctx.selected_enzymes() if s.encapsulated and s.phase is Phase.WET
    ]
    if not encapsulated:
        return []

    if fmt is Format.DUAL_CHAMBER:
        return [
            RuleFinding(
                RULE_ID, Verdict.PASS,
                "Under a dual chamber the capsule only has to survive minutes in the "
                "dressing plus the trip through the stomach, not months in acid. That is "
                "a bar encapsulation can meet.",
                {"format": fmt.value, "encapsulated": [s.enzyme_id for s in encapsulated]},
            )
        ]

    if fmt is not Format.ENCAPSULATED_IN_WET:
        return []

    ph = resolve_recipe_ph(ctx.formulation, ctx.foods, ctx.latest_trial_ph)
    findings: list[RuleFinding] = []

    for selected in encapsulated:
        enzyme = ctx.enzyme_for(selected)
        floor, floor_source = _floor(enzyme)

        if floor is None or ph.value is None:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.CANNOT_ASSESS,
                    f"{enzyme.name}: cannot judge whether encapsulation is being asked to "
                    f"do too much, because the recipe pH or the enzyme's pH floor is "
                    f"unconfirmed.",
                    {"blocking_field": ph.blocking_field or f"{enzyme.id}.ph_min"},
                    enzyme_id=enzyme.id,
                )
            )
            continue

        evidence = {
            "recipe_ph": ph.value, "floor": floor, "floor_source": floor_source,
            "format": fmt.value,
        }
        if ph.value < floor:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.RED,
                    f"{enzyme.name}: the capsule is the only thing between the enzyme and "
                    f"a pH of {ph.value}, below its {floor} floor, for the whole shelf "
                    f"life. Encapsulation buys time but cannot rescue an enzyme from a "
                    f"condition that would deactivate it on contact. Move to a dual "
                    f"chamber or a dry sachet.",
                    evidence, enzyme_id=enzyme.id,
                )
            )
        else:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.PASS,
                    f"{enzyme.name}: the surrounding pH of {ph.value} is above its {floor} "
                    f"floor, so the capsule is delaying exposure rather than holding back "
                    f"a condition that would kill it outright.",
                    evidence, enzyme_id=enzyme.id,
                )
            )

    return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/engine/test_r06_encapsulation.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/engine/rules/r06_encapsulation.py tests/engine/test_r06_encapsulation.py
git commit -m "feat(engine): implement R6 encapsulation semantics"
```

---

## Task 17: R7 — dosing vs substrate load

**Files:**
- Create: `src/foodbrew/engine/dosing.py`
- Modify: `src/foodbrew/engine/rules/r07_dosing.py`
- Test: `tests/engine/test_r07_dosing.py`

- [ ] **Step 1: Write the failing test**

`tests/engine/test_r07_dosing.py`:

```python
from foodbrew.engine.rules import r07_dosing as r7
from foodbrew.engine.types import (
    Deadline, Enzyme, EvalContext, Food, Format, Formulation, Phase,
    SelectedEnzyme, Substrate, Tracked, TruthLabel, Verdict,
)

SUBSTRATES = {"gos": Substrate(id="gos", name="GOS", is_prebiotic=True)}


def _alpha_gal(threshold=300.0, threshold_status=TruthLabel.CONFIRMED):
    return Enzyme(
        id="alpha_gal", name="Alpha-galactosidase", substrate_id="gos",
        source_type="fungal", priority="high", deadline=Deadline.BEFORE_COLON,
        ph_min=Tracked(3.0, TruthLabel.CONFIRMED, "t"),
        ph_max=Tracked(8.0, TruthLabel.CONFIRMED, "t"),
        ph_opt_low=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
        ph_opt_high=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
        ph_shelf_stable_min=Tracked(None, TruthLabel.UNCONFIRMED),
        dose_unit="GalU",
        dose_min=Tracked(450.0, TruthLabel.CONFIRMED, "KB"),
        dose_max=Tracked(800.0, TruthLabel.CONFIRMED, "KB"),
        dose_evidence_threshold=Tracked(threshold, threshold_status, "Monash"),
    )


def _food(fid, load, status=TruthLabel.CONFIRMED):
    return Food(
        id=fid, name=fid, category="legume", is_trigger_food=True,
        contains_substrate_ids=("gos",),
        typical_load_value=Tracked(load, status, "test"), typical_load_unit="g GOS",
    )


def _ctx(dose, foods, trigger_ids, enzyme=None):
    e = enzyme or _alpha_gal()
    return EvalContext(
        formulation=Formulation(
            id="f", format=Format.DUAL_CHAMBER, recipe=(),
            enzymes=(SelectedEnzyme("alpha_gal", dose, Phase.DRY),),
            target_trigger_food_ids=trigger_ids,
        ),
        enzymes={"alpha_gal": e}, foods=foods, substrates=SUBSTRATES,
    )


def test_dose_below_evidence_threshold_is_amber():
    # Spec §13 fixture (f): 150 GalU against a 6 g GOS serving.
    ctx = _ctx(150.0, {"beans": _food("beans", 6.0)}, ("beans",))
    f = r7.evaluate(ctx)[0]
    assert f.verdict is Verdict.AMBER
    assert "behaves like placebo" in f.message


def test_dose_at_threshold_passes():
    ctx = _ctx(300.0, {"beans": _food("beans", 6.0)}, ("beans",))
    assert r7.evaluate(ctx)[0].verdict is Verdict.PASS


def test_multi_food_loads_are_summed_not_maxed():
    # Spec §13 fixture (f2) and §6.7.
    ctx = _ctx(
        500.0,
        {"beans": _food("beans", 4.0), "lentils": _food("lentils", 2.5)},
        ("beans", "lentils"),
    )
    f = r7.evaluate(ctx)[0]
    assert f.evidence["substrate_load"] == 6.5
    assert "beans" in f.evidence["load_source"] and "lentils" in f.evidence["load_source"]


def test_unconfirmed_load_is_cannot_assess_and_names_the_food():
    ctx = _ctx(
        500.0,
        {"beans": _food("beans", 4.0),
         "lentils": _food("lentils", None, TruthLabel.UNCONFIRMED)},
        ("beans", "lentils"),
    )
    f = r7.evaluate(ctx)[0]
    assert f.verdict is Verdict.CANNOT_ASSESS
    assert "lentils" in f.message


def test_unconfirmed_threshold_is_cannot_assess():
    e = _alpha_gal(threshold=None, threshold_status=TruthLabel.UNCONFIRMED)
    ctx = _ctx(500.0, {"beans": _food("beans", 6.0)}, ("beans",), enzyme=e)
    f = r7.evaluate(ctx)[0]
    assert f.verdict is Verdict.CANNOT_ASSESS
    assert "dose_evidence_threshold" in f.message


def test_overdose_passes_with_a_cost_note():
    ctx = _ctx(5000.0, {"beans": _food("beans", 6.0)}, ("beans",))
    f = r7.evaluate(ctx)[0]
    assert f.verdict is Verdict.PASS
    assert "expensive way" in f.message


def test_no_dose_set_is_cannot_assess():
    ctx = _ctx(None, {"beans": _food("beans", 6.0)}, ("beans",))
    assert r7.evaluate(ctx)[0].verdict is Verdict.CANNOT_ASSESS


def test_squeeze_self_scaling_is_never_overstated():
    ctx = _ctx(300.0, {"beans": _food("beans", 6.0)}, ("beans",))
    f = r7.evaluate(ctx)[0]
    assert "dressing used, not with trigger food eaten" in f.message
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/engine/test_r07_dosing.py -v`
Expected: FAIL — IndexError on empty findings

- [ ] **Step 3: Write the implementation**

`src/foodbrew/engine/dosing.py`:

```python
"""Dose arithmetic for R7 (spec §6.1, KB §4g)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DoseAssessment:
    meets_threshold: bool
    ratio: float
    #: True when the dose exceeds the confirmed benchmark maximum.
    above_benchmark_max: bool


def assess_dose(
    dose: float, threshold: float, benchmark_max: float | None
) -> DoseAssessment:
    """Compare a per-serving dose against the evidence threshold.

    Spec §6.1 R7: an underdosed enzyme behaves like placebo, so the threshold is
    a floor, not a target. Overdosing works but is an expensive way to solve it.
    """
    return DoseAssessment(
        meets_threshold=dose >= threshold,
        ratio=dose / threshold if threshold else float("inf"),
        above_benchmark_max=benchmark_max is not None and dose > benchmark_max,
    )
```

Replace `src/foodbrew/engine/rules/r07_dosing.py`:

```python
"""R7 — dosing vs substrate load (spec §6.1, KB §4g)."""

from __future__ import annotations

from foodbrew.engine.conventions import aggregate_substrate_loads
from foodbrew.engine.dosing import assess_dose
from foodbrew.engine.types import EvalContext, RuleFinding, Verdict

RULE_ID = "R7"
ADVISORY = False

#: Spec §6.1 R7 — the squeeze format's dose scales with how much dressing is
#: used, which is only loosely correlated with how much trigger food is eaten.
#: Stated on every finding so it is never read as full self-scaling.
_DECOUPLING_NOTE = (
    " Note that a fixed dose meets a variable meal: in a squeeze format the dose "
    "self-scales with dressing used, not with trigger food eaten."
)


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    loads = aggregate_substrate_loads(ctx.formulation.target_trigger_food_ids, ctx.foods)
    findings: list[RuleFinding] = []

    for selected in ctx.selected_enzymes():
        enzyme = ctx.enzyme_for(selected)
        load = loads.get(enzyme.substrate_id)

        if load is None:
            continue  # No targeted trigger food carries this enzyme's substrate.

        if not load.usable:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.CANNOT_ASSESS,
                    f"{enzyme.name}: cannot check the dose because the substrate load is "
                    f"unconfirmed ({load.source}). Enter a typical load for that food.",
                    {"missing": load.source}, enzyme_id=enzyme.id,
                )
            )
            continue

        if selected.dose is None:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.CANNOT_ASSESS,
                    f"{enzyme.name}: no dose is set for this formulation.",
                    {"missing_field": "enzyme_selection.dose"}, enzyme_id=enzyme.id,
                )
            )
            continue

        if not enzyme.dose_evidence_threshold.usable:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.CANNOT_ASSESS,
                    f"{enzyme.name}: cannot judge the dose because its "
                    f"dose_evidence_threshold is unconfirmed. Ask the supplier, or find "
                    f"an independent full-dose study.",
                    {"missing_field": f"{enzyme.id}.dose_evidence_threshold"},
                    enzyme_id=enzyme.id,
                )
            )
            continue

        threshold = float(enzyme.dose_evidence_threshold.value)
        benchmark_max = float(enzyme.dose_max.value) if enzyme.dose_max.usable else None
        result = assess_dose(float(selected.dose), threshold, benchmark_max)

        evidence = {
            "dose": float(selected.dose),
            "dose_unit": enzyme.dose_unit,
            "evidence_threshold": threshold,
            "substrate": enzyme.substrate_id,
            "substrate_load": float(load.value),
            "load_source": load.source,
            "ratio": round(result.ratio, 3),
        }

        if not result.meets_threshold:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.AMBER,
                    f"{enzyme.name} at {selected.dose} {enzyme.dose_unit} is below the "
                    f"{threshold} {enzyme.dose_unit} evidence threshold. An underdosed "
                    f"enzyme behaves like placebo.{_DECOUPLING_NOTE}",
                    evidence, enzyme_id=enzyme.id,
                )
            )
        elif result.above_benchmark_max:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.PASS,
                    f"{enzyme.name} at {selected.dose} {enzyme.dose_unit} clears the "
                    f"{threshold} threshold and exceeds the {benchmark_max} benchmark "
                    f"maximum. That works, but loading extra enzyme is an expensive way "
                    f"to solve it.{_DECOUPLING_NOTE}",
                    evidence, enzyme_id=enzyme.id,
                )
            )
        else:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.PASS,
                    f"{enzyme.name} at {selected.dose} {enzyme.dose_unit} clears the "
                    f"{threshold} {enzyme.dose_unit} evidence threshold against a "
                    f"{load.value} load.{_DECOUPLING_NOTE}",
                    evidence, enzyme_id=enzyme.id,
                )
            )

    return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/engine/test_r07_dosing.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/engine/dosing.py src/foodbrew/engine/rules/r07_dosing.py tests/engine/test_r07_dosing.py
git commit -m "feat(engine): implement R7 dosing against summed substrate load"
```

---

## Task 18: R8, R9, R10 — advisory rules

Three small advisory rules in one task. None can ever set the headline.

**Files:**
- Modify: `src/foodbrew/engine/rules/r08_taste_drift.py`, `r09_prebiotic_tension.py`, `r10_strain_blending.py`
- Test: `tests/engine/test_r08_r09_r10.py`

- [ ] **Step 1: Write the failing test**

`tests/engine/test_r08_r09_r10.py`:

```python
from foodbrew.engine.rules import r08_taste_drift as r8
from foodbrew.engine.rules import r09_prebiotic_tension as r9
from foodbrew.engine.rules import r10_strain_blending as r10
from foodbrew.engine.types import (
    Deadline, Enzyme, EvalContext, Food, Format, Formulation, Phase,
    RecipeIngredient, SelectedEnzyme, Substrate, Tracked, TruthLabel, Verdict,
)

SUBSTRATES = {
    "lactose": Substrate(id="lactose", name="Lactose", native_human_enzyme=True),
    "gos": Substrate(id="gos", name="GOS", is_prebiotic=True),
    "inulin_fructan": Substrate(id="inulin_fructan", name="Inulin-type fructans",
                                is_prebiotic=True),
}


def _enzyme(eid, substrate_id, ph_min=2.5, ph_max=5.4):
    return Enzyme(
        id=eid, name=eid, substrate_id=substrate_id, source_type="fungal",
        priority="high", deadline=Deadline.BEFORE_COLON,
        ph_min=Tracked(ph_min, TruthLabel.CONFIRMED, "t"),
        ph_max=Tracked(ph_max, TruthLabel.CONFIRMED, "t"),
        ph_opt_low=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
        ph_opt_high=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
        ph_shelf_stable_min=Tracked(None, TruthLabel.UNCONFIRMED), dose_unit="FCC",
    )


def _ctx(enzymes_map, selections, fmt=Format.PREMIXED_WET, recipe=(), foods=None,
         gi_regions=()):
    return EvalContext(
        formulation=Formulation(id="f", format=fmt, recipe=recipe, enzymes=selections),
        enzymes=enzymes_map, foods=foods or {}, substrates=SUBSTRATES,
        gi_regions=gi_regions,
    )


# --- R8 -------------------------------------------------------------------

def test_r8_is_advisory():
    assert r8.ADVISORY is True


def test_r8_amber_when_enzyme_shares_wet_phase_with_its_substrate_in_recipe():
    foods = {"yogurt": Food(id="yogurt", name="Yogurt", category="dairy",
                            contains_substrate_ids=("lactose",))}
    ctx = _ctx({"lactase": _enzyme("lactase", "lactose")},
               (SelectedEnzyme("lactase", 9000.0, Phase.WET),),
               recipe=(RecipeIngredient("yogurt", 100.0),), foods=foods)
    f = r8.evaluate(ctx)[0]
    assert f.verdict is Verdict.AMBER
    assert "sweeter" in f.message


def test_r8_note_only_when_enzyme_is_dry():
    foods = {"yogurt": Food(id="yogurt", name="Yogurt", category="dairy",
                            contains_substrate_ids=("lactose",))}
    ctx = _ctx({"lactase": _enzyme("lactase", "lactose")},
               (SelectedEnzyme("lactase", 9000.0, Phase.DRY),),
               fmt=Format.DUAL_CHAMBER,
               recipe=(RecipeIngredient("yogurt", 100.0),), foods=foods)
    f = r8.evaluate(ctx)[0]
    assert f.verdict is Verdict.PASS
    assert "begins at mixing" in f.message


def test_r8_no_finding_when_substrate_absent_from_recipe():
    ctx = _ctx({"lactase": _enzyme("lactase", "lactose")},
               (SelectedEnzyme("lactase", 9000.0, Phase.WET),))
    assert r8.evaluate(ctx) == []


# --- R9 -------------------------------------------------------------------

def test_r9_is_advisory():
    assert r9.ADVISORY is True


def test_r9_fires_for_alpha_galactosidase_because_gos_is_prebiotic():
    # Spec §13 fixture (g) — KB §4i names GOS alongside inulin and fructans.
    ctx = _ctx({"alpha_gal": _enzyme("alpha_gal", "gos")},
               (SelectedEnzyme("alpha_gal", 800.0, Phase.DRY),))
    f = r9.evaluate(ctx)[0]
    assert f.verdict is Verdict.AMBER
    assert "symptom threshold" in f.message


def test_r9_fires_for_inulinase():
    ctx = _ctx({"inulinase": _enzyme("inulinase", "inulin_fructan")},
               (SelectedEnzyme("inulinase", 100.0, Phase.DRY),))
    assert r9.evaluate(ctx)[0].verdict is Verdict.AMBER


def test_r9_silent_for_lactase():
    ctx = _ctx({"lactase": _enzyme("lactase", "lactose")},
               (SelectedEnzyme("lactase", 9000.0, Phase.DRY),))
    assert r9.evaluate(ctx) == []


# --- R10 ------------------------------------------------------------------

def test_r10_is_advisory():
    assert r10.ADVISORY is True


def test_r10_suggests_pairing_when_window_is_narrow():
    from foodbrew.seedload.loader import load_seed
    regions = load_seed().gi_regions
    ctx = _ctx({"lactase": _enzyme("lactase", "lactose", 2.5, 5.4)},
               (SelectedEnzyme("lactase", 9000.0, Phase.DRY),), gi_regions=regions)
    f = r10.evaluate(ctx)[0]
    assert f.verdict is Verdict.PASS
    assert "complementary" in f.message


def test_r10_silent_for_broad_window_enzyme():
    from foodbrew.seedload.loader import load_seed
    regions = load_seed().gi_regions
    ctx = _ctx({"broad": _enzyme("broad", "lactose", 2.0, 9.0)},
               (SelectedEnzyme("broad", 100.0, Phase.DRY),), gi_regions=regions)
    assert r10.evaluate(ctx) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/engine/test_r08_r09_r10.py -v`
Expected: FAIL — the ADVISORY assertions pass, the behaviour assertions fail on empty findings

- [ ] **Step 3: Write the three implementations**

Replace `src/foodbrew/engine/rules/r08_taste_drift.py`:

```python
"""R8 — in-jar taste and stability drift (spec §6.1, KB §4e). Advisory.

Scope is the jar. What the dressing does to the food it is poured on is R15.
"""

from __future__ import annotations

from foodbrew.engine.types import EvalContext, Format, Phase, RuleFinding, Verdict

RULE_ID = "R8"
ADVISORY = True

_WET_FORMATS = {Format.PREMIXED_WET, Format.ENCAPSULATED_IN_WET}


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    recipe_substrates: set[str] = set()
    for ingredient in ctx.formulation.recipe:
        food = ctx.foods.get(ingredient.food_id)
        if food is not None:
            recipe_substrates.update(food.contains_substrate_ids)

    findings: list[RuleFinding] = []
    wet_format = ctx.formulation.format in _WET_FORMATS

    for selected in ctx.selected_enzymes():
        enzyme = ctx.enzyme_for(selected)
        if enzyme.substrate_id not in recipe_substrates:
            continue

        evidence = {
            "substrate_in_recipe": enzyme.substrate_id,
            "format": ctx.formulation.format.value,
            "phase": selected.phase.value,
        }

        if wet_format and selected.phase is Phase.WET:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.AMBER,
                    f"{enzyme.name} shares a wet phase with its own substrate "
                    f"({enzyme.substrate_id}) in the recipe, so flavour, texture, smell "
                    f"and appearance will drift over shelf life — lactose hydrolysis "
                    f"makes a product sweeter, and food can turn weird and smelly as it "
                    f"sits.",
                    evidence, enzyme_id=enzyme.id,
                )
            )
        else:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.PASS,
                    f"{enzyme.name}'s substrate ({enzyme.substrate_id}) is in the recipe, "
                    f"but the enzyme is kept dry, so drift begins at mixing rather than on "
                    f"the shelf.",
                    evidence, enzyme_id=enzyme.id,
                )
            )

    return findings
```

Replace `src/foodbrew/engine/rules/r09_prebiotic_tension.py`:

```python
"""R9 — prebiotic tension (spec §6.1, KB §4i). Advisory, never RED.

KB §4i names inulin, fructans AND GOS, so alpha-galactosidase triggers this as
surely as inulinase does. A product-philosophy call the founder owns; the rule
just keeps it visible.
"""

from __future__ import annotations

from foodbrew.engine.types import EvalContext, RuleFinding, Verdict

RULE_ID = "R9"
ADVISORY = True


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    findings: list[RuleFinding] = []

    for selected in ctx.selected_enzymes():
        enzyme = ctx.enzyme_for(selected)
        substrate = ctx.substrates.get(enzyme.substrate_id)
        if substrate is None or not substrate.is_prebiotic:
            continue

        findings.append(
            RuleFinding(
                RULE_ID, Verdict.AMBER,
                f"{enzyme.name} breaks down {substrate.name}, which relieves gas but also "
                f"removes a prebiotic that feeds the gut microbiome. Consider dosing to a "
                f"symptom threshold rather than to zero. Garlic and onion carry more "
                f"short-chain fructans than inulin.",
                {"substrate": substrate.id, "is_prebiotic": True},
                enzyme_id=enzyme.id,
            )
        )

    return findings
```

Replace `src/foodbrew/engine/rules/r10_strain_blending.py`:

```python
"""R10 — strain blending (spec §6.1, KB §4k). Advisory, never a failure."""

from __future__ import annotations

from foodbrew.engine.gi_model import active_regions, regions_before_deadline
from foodbrew.engine.types import EvalContext, RuleFinding, Verdict

RULE_ID = "R10"
ADVISORY = True

#: Suggest a complementary source when the enzyme covers at most this many of
#: the regions it could usefully work in before its deadline.
_NARROW_WINDOW_MAX_REGIONS = 1


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    if not ctx.gi_regions:
        return []

    findings: list[RuleFinding] = []
    for selected in ctx.selected_enzymes():
        enzyme = ctx.enzyme_for(selected)
        if not (enzyme.ph_min.usable and enzyme.ph_max.usable):
            continue

        allowed = {r.id for r in regions_before_deadline(enzyme.deadline, ctx.gi_regions)}
        active_before = [
            r.id for r in active_regions(enzyme, ctx.gi_regions) if r.id in allowed
        ]
        if len(active_before) > _NARROW_WINDOW_MAX_REGIONS or not active_before:
            continue

        findings.append(
            RuleFinding(
                RULE_ID, Verdict.PASS,
                f"{enzyme.name} is active in only {', '.join(active_before)} before its "
                f"deadline. Pairing a complementary source — an acid variant with a "
                f"neutral one, the way Enzymedica blends strains — would widen the active "
                f"window across more of the tract.",
                {
                    "active_before_deadline": active_before,
                    "ph_min": float(enzyme.ph_min.value),
                    "ph_max": float(enzyme.ph_max.value),
                },
                enzyme_id=enzyme.id,
            )
        )

    return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/engine/test_r08_r09_r10.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/engine/rules/r08_taste_drift.py src/foodbrew/engine/rules/r09_prebiotic_tension.py src/foodbrew/engine/rules/r10_strain_blending.py tests/engine/test_r08_r09_r10.py
git commit -m "feat(engine): implement R8 drift, R9 prebiotic tension, R10 strain blending"
```

---

## Task 19: R11 and R16 — sourcing rules

R11 is headline-capable; R16 is advisory. Both concern where the enzyme comes from.

**Files:**
- Modify: `src/foodbrew/engine/rules/r11_food_grade.py`, `r16_clean_label.py`
- Test: `tests/engine/test_r11_r16.py`

- [ ] **Step 1: Write the failing test**

`tests/engine/test_r11_r16.py`:

```python
from foodbrew.engine.rules import r11_food_grade as r11
from foodbrew.engine.rules import r16_clean_label as r16
from foodbrew.engine.types import (
    Deadline, Enzyme, EvalContext, Format, Formulation, Phase,
    SelectedEnzyme, Tracked, TruthLabel, Verdict,
)


def _enzyme(eid, gras, gras_status, natural=False):
    return Enzyme(
        id=eid, name=eid, substrate_id="lactose", source_type="plant" if natural else "fungal",
        priority="high", deadline=Deadline.BEFORE_COLON,
        ph_min=Tracked(3.0, TruthLabel.CONFIRMED, "t"),
        ph_max=Tracked(7.0, TruthLabel.CONFIRMED, "t"),
        ph_opt_low=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
        ph_opt_high=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
        ph_shelf_stable_min=Tracked(None, TruthLabel.UNCONFIRMED), dose_unit="FCC",
        is_gras=Tracked(gras, gras_status, "KB §4l"), is_natural_source=natural,
        heat_labile_note="Destroyed by cooking." if natural else "",
    )


def _ctx(enzymes_map):
    selections = tuple(SelectedEnzyme(eid, 100.0, Phase.DRY) for eid in enzymes_map)
    return EvalContext(
        formulation=Formulation(
            id="f", format=Format.DUAL_CHAMBER, recipe=(), enzymes=selections
        ),
        enzymes=enzymes_map, foods={}, substrates={},
    )


# --- R11 ------------------------------------------------------------------

def test_r11_is_headline_capable():
    assert r11.ADVISORY is False


def test_r11_passes_for_confirmed_gras_enzyme():
    ctx = _ctx({"lactase": _enzyme("lactase", True, TruthLabel.CONFIRMED)})
    f = r11.evaluate(ctx)[0]
    assert f.verdict is Verdict.PASS


def test_r11_cannot_assess_for_unknown_gras_status():
    ctx = _ctx({"inulinase": _enzyme("inulinase", None, TruthLabel.UNCONFIRMED)})
    f = r11.evaluate(ctx)[0]
    assert f.verdict is Verdict.CANNOT_ASSESS
    assert "supplier" in f.message


def test_r11_red_when_explicitly_not_gras():
    ctx = _ctx({"bad": _enzyme("bad", False, TruthLabel.CONFIRMED)})
    assert r11.evaluate(ctx)[0].verdict is Verdict.RED


# --- R16 ------------------------------------------------------------------

def test_r16_is_advisory():
    assert r16.ADVISORY is True


def test_r16_reports_non_natural_sourcing_and_additive_gap():
    # Spec §13 fixture (p0).
    ctx = _ctx({"lactase": _enzyme("lactase", True, TruthLabel.CONFIRMED)})
    findings = r16.evaluate(ctx)
    sourcing = [f for f in findings if f.enzyme_id == "lactase"]
    assert sourcing and "fermented" in sourcing[0].message
    additives = [f for f in findings if f.enzyme_id is None]
    assert additives and additives[0].verdict is Verdict.CANNOT_ASSESS
    assert "gut-trigger additives" in additives[0].message


def test_r16_flags_natural_source_as_heat_labile():
    ctx = _ctx({"bromelain": _enzyme("bromelain", None, TruthLabel.UNCONFIRMED, natural=True)})
    f = [x for x in r16.evaluate(ctx) if x.enzyme_id == "bromelain"][0]
    assert "natural source" in f.message
    assert "cooking" in f.message


def test_r16_never_reds():
    ctx = _ctx({"bad": _enzyme("bad", False, TruthLabel.CONFIRMED)})
    assert all(f.verdict is not Verdict.RED for f in r16.evaluate(ctx))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/engine/test_r11_r16.py -v`
Expected: FAIL — behaviour assertions fail on empty findings

- [ ] **Step 3: Write both implementations**

Replace `src/foodbrew/engine/rules/r11_food_grade.py`:

```python
"""R11 — food-grade and GRAS status (spec §6.1, KB §4l)."""

from __future__ import annotations

from foodbrew.engine.types import EvalContext, RuleFinding, Verdict

RULE_ID = "R11"
ADVISORY = False

#: Shown alongside every R11 finding: finished-product rules are out of scope.
SCOPE_BANNER = (
    "Finished-product rules — food safety and acidified-food regulations — are outside "
    "this tool's scope."
)


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    findings: list[RuleFinding] = []

    for selected in ctx.selected_enzymes():
        enzyme = ctx.enzyme_for(selected)
        evidence = {"is_gras": enzyme.is_gras.value, "status": enzyme.is_gras.status.value}

        if not enzyme.is_gras.usable:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.CANNOT_ASSESS,
                    f"{enzyme.name}: GRAS status is not recorded. Ask the supplier whether "
                    f"this enzyme is food grade and GRAS-affirmed, and at what cost tier — "
                    f"food grade costs more than technical grade. {SCOPE_BANNER}",
                    evidence, enzyme_id=enzyme.id,
                )
            )
        elif enzyme.is_gras.value:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.PASS,
                    f"{enzyme.name} is recorded as food grade and GRAS, which is a cost and "
                    f"time advantage. {SCOPE_BANNER}",
                    evidence, enzyme_id=enzyme.id,
                )
            )
        else:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.RED,
                    f"{enzyme.name} is recorded as not GRAS. A finished food cannot carry a "
                    f"non-GRAS enzyme. {SCOPE_BANNER}",
                    evidence, enzyme_id=enzyme.id,
                )
            )

    return findings
```

Replace `src/foodbrew/engine/rules/r16_clean_label.py`:

```python
"""R16 — clean label and natural sourcing (spec §6.2, KB §1 criterion 5 via §4j/§4l).

Advisory only — a founder philosophy call the rule keeps visible, in the same
spirit as R9.
"""

from __future__ import annotations

from foodbrew.engine.types import EvalContext, RuleFinding, Verdict

RULE_ID = "R16"
ADVISORY = True


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    selected = ctx.selected_enzymes()
    if not selected:
        return []

    findings: list[RuleFinding] = []

    for s in selected:
        enzyme = ctx.enzyme_for(s)
        evidence = {
            "is_natural_source": enzyme.is_natural_source,
            "source_type": enzyme.source_type,
        }
        if enzyme.is_natural_source:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.AMBER,
                    f"{enzyme.name} is a natural source ({enzyme.source_type}), which "
                    f"supports a clean-label story — but natural-source enzymes are "
                    f"destroyed by cooking, so the no-heat rule binds harder here.",
                    evidence, enzyme_id=enzyme.id,
                )
            )
        else:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.PASS,
                    f"{enzyme.name} is {enzyme.source_type}-fermented rather than extracted "
                    f"from a whole food. That is standard for the category and food grade, "
                    f"but it is not a 'natural source' claim — worth deciding deliberately "
                    f"rather than by default.",
                    evidence, enzyme_id=enzyme.id,
                )
            )

    # The second half of the KB criterion has no data anywhere in the source set.
    findings.append(
        RuleFinding(
            RULE_ID, Verdict.CANNOT_ASSESS,
            "Cannot assess 'no gut-trigger additives': excipient and carrier composition "
            "for these enzymes is supplier data that is not recorded anywhere yet. Ask "
            "each supplier for the full carrier and excipient breakdown.",
            {"missing_field": "enzyme excipient / carrier composition"},
        )
    )

    return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/engine/test_r11_r16.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/engine/rules/r11_food_grade.py src/foodbrew/engine/rules/r16_clean_label.py tests/engine/test_r11_r16.py
git commit -m "feat(engine): implement R11 GRAS check and R16 clean-label advisory"
```

---

## Task 20: R12 — temperature, advisory with per-enzyme promotion

The rule that would have made every formulation GRAY if left red-capable against the shipped seed.

**Files:**
- Modify: `src/foodbrew/engine/rules/r12_temperature.py`
- Test: `tests/engine/test_r12_temperature.py`

- [ ] **Step 1: Write the failing test**

`tests/engine/test_r12_temperature.py`:

```python
from foodbrew.engine.rules import r12_temperature as r12
from foodbrew.engine.types import (
    Deadline, Enzyme, EvalContext, Format, Formulation, Phase,
    SelectedEnzyme, Tracked, TruthLabel, Verdict,
)
from foodbrew.seedload.loader import load_seed


def _enzyme(eid, tmin, tmax, status):
    return Enzyme(
        id=eid, name=eid, substrate_id="lactose", source_type="fungal", priority="high",
        deadline=Deadline.BEFORE_COLON,
        ph_min=Tracked(3.0, TruthLabel.CONFIRMED, "t"),
        ph_max=Tracked(7.0, TruthLabel.CONFIRMED, "t"),
        ph_opt_low=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
        ph_opt_high=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
        ph_shelf_stable_min=Tracked(None, TruthLabel.UNCONFIRMED), dose_unit="FCC",
        temp_min_c=Tracked(tmin, status, "supplier"),
        temp_max_c=Tracked(tmax, status, "supplier"),
    )


def _ctx(enzymes_map):
    selections = tuple(SelectedEnzyme(eid, 100.0, Phase.DRY) for eid in enzymes_map)
    return EvalContext(
        formulation=Formulation(
            id="f", format=Format.DUAL_CHAMBER, recipe=(), enzymes=selections
        ),
        enzymes=enzymes_map, foods={}, substrates={},
    )


def test_module_default_is_advisory():
    assert r12.ADVISORY is True


def test_every_seeded_enzyme_yields_an_advisory_cannot_assess():
    # Spec §6.1 R12: this is why R12 cannot be headline-capable on day one.
    seed = load_seed()
    ctx = EvalContext(
        formulation=Formulation(
            id="f", format=Format.DUAL_CHAMBER, recipe=(),
            enzymes=tuple(SelectedEnzyme(eid, 100.0, Phase.DRY) for eid in seed.enzymes),
        ),
        enzymes=seed.enzymes, foods={}, substrates=seed.substrates,
    )
    findings = r12.evaluate(ctx)
    assert len(findings) == len(seed.enzymes)
    assert all(f.verdict is Verdict.CANNOT_ASSESS for f in findings)
    assert all(f.advisory is True for f in findings)


def test_confirmed_range_covering_ambient_passes_and_is_not_advisory():
    ctx = _ctx({"e": _enzyme("e", 4.0, 45.0, TruthLabel.CONFIRMED)})
    f = r12.evaluate(ctx)[0]
    assert f.verdict is Verdict.PASS
    assert f.advisory is False


def test_confirmed_range_excluding_ambient_reds_and_is_not_advisory():
    # Spec §13 fixture (h2) — promotion is per-enzyme.
    ctx = _ctx({"e": _enzyme("e", 4.0, 18.0, TruthLabel.CONFIRMED)})
    f = r12.evaluate(ctx)[0]
    assert f.verdict is Verdict.RED
    assert f.advisory is False
    assert "cold chain" in f.message


def test_promotion_is_per_enzyme_not_global():
    ctx = _ctx({
        "confirmed_bad": _enzyme("confirmed_bad", 4.0, 18.0, TruthLabel.CONFIRMED),
        "unknown": _enzyme("unknown", None, None, TruthLabel.UNCONFIRMED),
    })
    by_id = {f.enzyme_id: f for f in r12.evaluate(ctx)}
    assert by_id["confirmed_bad"].advisory is False
    assert by_id["unknown"].advisory is True


def test_range_not_covering_body_temperature_is_amber():
    ctx = _ctx({"e": _enzyme("e", 50.0, 80.0, TruthLabel.CONFIRMED)})
    f = r12.evaluate(ctx)[0]
    assert f.verdict is Verdict.RED  # also fails ambient
    assert "37" in f.message
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/engine/test_r12_temperature.py -v`
Expected: FAIL — behaviour assertions fail on empty findings

- [ ] **Step 3: Write the implementation**

Replace `src/foodbrew/engine/rules/r12_temperature.py`:

```python
"""R12 — temperature range (spec §6.1, KB §4b).

Advisory by default, because every temperature field in the shipped seed is
unconfirmed — no source document provides per-enzyme temperature data. Were R12
headline-capable against that catalogue, every formulation would come out GRAY
regardless of merit and the KB §4m fixtures would be unreachable.

Promotion is per-enzyme: once an enzyme's temperature fields are confirmed, its
finding stops being advisory and can set the headline.
"""

from __future__ import annotations

from foodbrew.engine.types import EvalContext, RuleFinding, Verdict

RULE_ID = "R12"
ADVISORY = True

#: The product is required to be ambient-stable with no cold chain (spec §1.1).
AMBIENT_STORAGE_C = 25.0
BODY_TEMPERATURE_C = 37.0


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    findings: list[RuleFinding] = []

    for selected in ctx.selected_enzymes():
        enzyme = ctx.enzyme_for(selected)

        if not (enzyme.temp_min_c.usable and enzyme.temp_max_c.usable):
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.CANNOT_ASSESS,
                    f"{enzyme.name}: temperature range is unconfirmed, so its tolerance of "
                    f"ambient storage and of body temperature cannot be checked. Ask the "
                    f"supplier for the temperature range and optimum. "
                    f"{enzyme.temp_min_c.source}".strip(),
                    {"missing_field": f"{enzyme.id}.temp_min_c/temp_max_c"},
                    enzyme_id=enzyme.id, advisory=True,
                )
            )
            continue

        tmin, tmax = float(enzyme.temp_min_c.value), float(enzyme.temp_max_c.value)
        covers_ambient = tmin <= AMBIENT_STORAGE_C <= tmax
        covers_body = tmin <= BODY_TEMPERATURE_C <= tmax
        evidence = {
            "temp_min_c": tmin, "temp_max_c": tmax,
            "covers_ambient": covers_ambient, "covers_body_temp": covers_body,
        }

        if not covers_ambient:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.RED,
                    f"{enzyme.name}: its confirmed range {tmin}-{tmax} C does not cover "
                    f"ambient storage at {AMBIENT_STORAGE_C} C, and the product is "
                    f"required to need no cold chain."
                    + ("" if covers_body else
                       f" It also does not cover body temperature at {BODY_TEMPERATURE_C} C, "
                       f"so it would be sluggish in the gut."),
                    evidence, enzyme_id=enzyme.id, advisory=False,
                )
            )
        elif not covers_body:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.AMBER,
                    f"{enzyme.name}: stable at ambient, but its confirmed range "
                    f"{tmin}-{tmax} C does not cover body temperature at "
                    f"{BODY_TEMPERATURE_C} C, so activity in the gut will be reduced.",
                    evidence, enzyme_id=enzyme.id, advisory=False,
                )
            )
        else:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.PASS,
                    f"{enzyme.name}: its confirmed range {tmin}-{tmax} C covers both "
                    f"ambient storage and body temperature.",
                    evidence, enzyme_id=enzyme.id, advisory=False,
                )
            )

    return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/engine/test_r12_temperature.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/engine/rules/r12_temperature.py tests/engine/test_r12_temperature.py
git commit -m "feat(engine): implement R12 temperature as advisory with per-enzyme promotion"
```

---

## Task 21: R14 — substrate coverage

**Files:**
- Modify: `src/foodbrew/engine/rules/r14_substrate_coverage.py`
- Test: `tests/engine/test_r14_substrate_coverage.py`

- [ ] **Step 1: Write the failing test**

`tests/engine/test_r14_substrate_coverage.py`:

```python
import pytest

from foodbrew.engine.rules import r14_substrate_coverage as r14
from foodbrew.engine.types import (
    Deadline, Enzyme, EvalContext, Food, Format, Formulation, Phase,
    SelectedEnzyme, Substrate, Tracked, TruthLabel, Verdict,
)

SUBSTRATES = {
    "lactose": Substrate(id="lactose", name="Lactose"),
    "gos": Substrate(id="gos", name="GOS", is_prebiotic=True),
    "polyol": Substrate(id="polyol", name="Polyols", no_commercial_enzyme=True),
}
FOODS = {
    "milk": Food(id="milk", name="Milk", category="dairy", is_trigger_food=True,
                 contains_substrate_ids=("lactose",)),
    "beans": Food(id="beans", name="Black beans", category="legume", is_trigger_food=True,
                  contains_substrate_ids=("gos",)),
    "mushroom": Food(id="mushroom", name="Mushrooms", category="veg", is_trigger_food=True,
                     contains_substrate_ids=("polyol",)),
}


def _enzyme(eid, substrate_id):
    return Enzyme(
        id=eid, name=eid, substrate_id=substrate_id, source_type="fungal", priority="high",
        deadline=Deadline.BEFORE_COLON,
        ph_min=Tracked(3.0, TruthLabel.CONFIRMED, "t"),
        ph_max=Tracked(7.0, TruthLabel.CONFIRMED, "t"),
        ph_opt_low=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
        ph_opt_high=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
        ph_shelf_stable_min=Tracked(None, TruthLabel.UNCONFIRMED), dose_unit="FCC",
    )


def _ctx(trigger_ids, enzyme_ids):
    enzymes = {"lactase": _enzyme("lactase", "lactose"),
               "alpha_gal": _enzyme("alpha_gal", "gos")}
    return EvalContext(
        formulation=Formulation(
            id="f", format=Format.DUAL_CHAMBER, recipe=(),
            enzymes=tuple(SelectedEnzyme(e, 100.0, Phase.DRY) for e in enzyme_ids),
            target_trigger_food_ids=trigger_ids,
        ),
        enzymes=enzymes, foods=FOODS, substrates=SUBSTRATES,
    )


def test_covered_substrate_passes():
    f = r14.evaluate(_ctx(("milk",), ("lactase",)))[0]
    assert f.verdict is Verdict.PASS


def test_uncovered_substrate_is_red_and_names_it():
    f = r14.evaluate(_ctx(("milk",), ()))[0]
    assert f.verdict is Verdict.RED
    assert "no enzyme selected for Lactose" in f.message


def test_zero_enzymes_with_trigger_foods_reds_never_passes():
    findings = r14.evaluate(_ctx(("milk", "beans"), ()))
    assert len(findings) == 2
    assert all(f.verdict is Verdict.RED for f in findings)


def test_polyol_is_cannot_assess_not_red():
    # Spec §13 fixture (j) — the tool never maps polyols to an enzyme.
    f = r14.evaluate(_ctx(("mushroom",), ("lactase",)))
    polyol = [x for x in f if "Polyol" in x.message][0]
    assert polyol.verdict is Verdict.CANNOT_ASSESS
    assert "no commercial enzyme exists" in polyol.message


def test_partial_coverage_reports_per_substrate():
    findings = r14.evaluate(_ctx(("milk", "beans"), ("lactase",)))
    by_verdict = {f.verdict for f in findings}
    assert Verdict.PASS in by_verdict and Verdict.RED in by_verdict


def test_zero_enzymes_and_zero_trigger_foods_raises_validation_error():
    with pytest.raises(r14.ValidationRejection, match="at least one trigger food"):
        r14.evaluate(_ctx((), ()))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/engine/test_r14_substrate_coverage.py -v`
Expected: FAIL — IndexError and a missing `ValidationRejection`

- [ ] **Step 3: Write the implementation**

Replace `src/foodbrew/engine/rules/r14_substrate_coverage.py`:

```python
"""R14 — substrate coverage (spec §6.2, derived from KB §5 outputs)."""

from __future__ import annotations

from foodbrew.engine.types import EvalContext, RuleFinding, Verdict

RULE_ID = "R14"
ADVISORY = False


class ValidationRejection(ValueError):
    """Raised for degenerate input that must not be evaluated at all (spec §6.7)."""


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    form = ctx.formulation

    if not form.target_trigger_food_ids and not form.enzymes:
        raise ValidationRejection(
            "Select at least one trigger food or enzyme before evaluating."
        )

    targeted_substrates: dict[str, list[str]] = {}
    for fid in form.target_trigger_food_ids:
        food = ctx.foods.get(fid)
        if food is None:
            continue
        for sid in food.contains_substrate_ids:
            targeted_substrates.setdefault(sid, []).append(food.name)

    covered = {ctx.enzyme_for(s).substrate_id for s in ctx.selected_enzymes()}
    findings: list[RuleFinding] = []

    for sid, food_names in sorted(targeted_substrates.items()):
        substrate = ctx.substrates.get(sid)
        name = substrate.name if substrate else sid
        evidence = {"substrate": sid, "from_foods": food_names, "covered": sid in covered}

        if substrate is not None and substrate.no_commercial_enzyme:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.CANNOT_ASSESS,
                    f"{name} (from {', '.join(food_names)}): no commercial enzyme exists "
                    f"for this substrate, so this trigger food cannot be addressed by any "
                    f"formulation. This is a gap, not a formulation error.",
                    evidence,
                )
            )
        elif sid in covered:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.PASS,
                    f"{name} (from {', '.join(food_names)}) is targeted by a selected enzyme.",
                    evidence,
                )
            )
        else:
            findings.append(
                RuleFinding(
                    RULE_ID, Verdict.RED,
                    f"no enzyme selected for {name}, which {', '.join(food_names)} "
                    f"contains. That trigger food is not addressed.",
                    evidence,
                )
            )

    return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/engine/test_r14_substrate_coverage.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/engine/rules/r14_substrate_coverage.py tests/engine/test_r14_substrate_coverage.py
git commit -m "feat(engine): implement R14 substrate coverage with polyol gap handling"
```

---

## Task 22: Texture module — severity table, envelope, dwell bucketing

**Files:**
- Create: `src/foodbrew/engine/texture.py`
- Test: `tests/engine/test_texture.py`

- [ ] **Step 1: Write the failing test**

`tests/engine/test_texture.py`:

```python
import pytest

from foodbrew.engine.texture import (
    SEVERITY_TABLE, dwell_bucket, headline_contribution, verdict_for_tier,
)
from foodbrew.engine.types import DwellProfile, SeverityTier, Verdict


@pytest.mark.parametrize(
    "minutes,expected",
    [
        (0, DwellProfile.IMMEDIATE),
        (59, DwellProfile.IMMEDIATE),
        (60, DwellProfile.PACKED),
        (479, DwellProfile.PACKED),
        (480, DwellProfile.MARINADE),
        (1440, DwellProfile.MARINADE),
    ],
)
def test_dwell_bucket_boundaries(minutes, expected):
    # Spec §6.3 and §13 fixture (o2) — exhaustive, non-overlapping, inclusive.
    assert dwell_bucket(minutes) is expected


def test_dwell_bucket_rejects_negative():
    with pytest.raises(ValueError):
        dwell_bucket(-1)


def test_rapid_tier_is_red_at_every_profile():
    for profile in DwellProfile:
        assert verdict_for_tier(SeverityTier.RAPID, profile) is Verdict.RED


def test_gradual_tier_worsens_with_dwell():
    assert verdict_for_tier(SeverityTier.GRADUAL, DwellProfile.IMMEDIATE) is Verdict.PASS
    assert verdict_for_tier(SeverityTier.GRADUAL, DwellProfile.PACKED) is Verdict.AMBER
    assert verdict_for_tier(SeverityTier.GRADUAL, DwellProfile.MARINADE) is Verdict.RED


def test_unconfirmed_tier_is_cannot_assess_everywhere():
    for profile in DwellProfile:
        assert verdict_for_tier(SeverityTier.UNCONFIRMED, profile) is Verdict.CANNOT_ASSESS


def test_severity_table_is_total():
    for tier in SeverityTier:
        for profile in DwellProfile:
            assert SEVERITY_TABLE[tier][profile] in set(Verdict)


def test_headline_red_when_declared_profile_is_red():
    envelope = {
        DwellProfile.IMMEDIATE: Verdict.PASS,
        DwellProfile.PACKED: Verdict.AMBER,
        DwellProfile.MARINADE: Verdict.RED,
    }
    assert headline_contribution(envelope, DwellProfile.MARINADE) is Verdict.RED


def test_headline_amber_when_undeclared_and_not_all_red():
    envelope = {
        DwellProfile.IMMEDIATE: Verdict.PASS,
        DwellProfile.PACKED: Verdict.AMBER,
        DwellProfile.MARINADE: Verdict.RED,
    }
    assert headline_contribution(envelope, None) is Verdict.AMBER


def test_headline_red_when_all_three_profiles_red():
    envelope = dict.fromkeys(DwellProfile, Verdict.RED)
    assert headline_contribution(envelope, None) is Verdict.RED


def test_headline_pass_when_envelope_is_clean():
    envelope = dict.fromkeys(DwellProfile, Verdict.PASS)
    assert headline_contribution(envelope, None) is Verdict.PASS


def test_headline_amber_when_envelope_has_cannot_assess():
    envelope = dict.fromkeys(DwellProfile, Verdict.CANNOT_ASSESS)
    assert headline_contribution(envelope, None) is Verdict.AMBER
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/engine/test_texture.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'foodbrew.engine.texture'`

- [ ] **Step 3: Write the implementation**

`src/foodbrew/engine/texture.py`:

```python
"""Spec §6.3 / §6.3.1 — the occasion envelope and its severity mapping."""

from __future__ import annotations

from typing import Mapping

from foodbrew.engine.types import DwellProfile, SeverityTier, Verdict

#: Spec §6.3 — exhaustive, non-overlapping, boundary-inclusive ranges in minutes.
_BUCKET_BOUNDS: tuple[tuple[int, int | None, DwellProfile], ...] = (
    (0, 59, DwellProfile.IMMEDIATE),
    (60, 479, DwellProfile.PACKED),
    (480, None, DwellProfile.MARINADE),
)

#: Spec §6.3.1. No shipped seed enzyme uses RAPID — it exists so the mapping is
#: total and a future confirmed fast-acting case has somewhere to go.
SEVERITY_TABLE: Mapping[SeverityTier, Mapping[DwellProfile, Verdict]] = {
    SeverityTier.RAPID: {
        DwellProfile.IMMEDIATE: Verdict.RED,
        DwellProfile.PACKED: Verdict.RED,
        DwellProfile.MARINADE: Verdict.RED,
    },
    SeverityTier.GRADUAL: {
        DwellProfile.IMMEDIATE: Verdict.PASS,
        DwellProfile.PACKED: Verdict.AMBER,
        DwellProfile.MARINADE: Verdict.RED,
    },
    SeverityTier.UNCONFIRMED: {
        DwellProfile.IMMEDIATE: Verdict.CANNOT_ASSESS,
        DwellProfile.PACKED: Verdict.CANNOT_ASSESS,
        DwellProfile.MARINADE: Verdict.CANNOT_ASSESS,
    },
}


def dwell_bucket(elapsed_minutes: int) -> DwellProfile:
    """Spec §6.3 — derive the dwell profile from elapsed minutes and nothing else."""
    if elapsed_minutes < 0:
        raise ValueError("elapsed_minutes cannot be negative")
    for low, high, profile in _BUCKET_BOUNDS:
        if elapsed_minutes >= low and (high is None or elapsed_minutes <= high):
            return profile
    raise ValueError(f"no dwell bucket for {elapsed_minutes}")  # pragma: no cover


def verdict_for_tier(tier: SeverityTier, profile: DwellProfile) -> Verdict:
    return SEVERITY_TABLE[tier][profile]


def headline_contribution(
    envelope: Mapping[DwellProfile, Verdict], declared: DwellProfile | None
) -> Verdict:
    """Spec §6.4 — how R15's envelope contributes to the overall flag.

    A formulation that is fine for table-dressing is not failed by a marinade
    scenario the founder may never support; but the failing occasion is never
    hidden either.
    """
    if declared is not None and envelope.get(declared) is Verdict.RED:
        return Verdict.RED
    if all(v is Verdict.RED for v in envelope.values()):
        return Verdict.RED
    if any(v is not Verdict.PASS for v in envelope.values()):
        return Verdict.AMBER
    return Verdict.PASS
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/engine/test_texture.py -v`
Expected: 16 passed

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/engine/texture.py tests/engine/test_texture.py
git commit -m "feat(engine): add occasion envelope severity table and dwell bucketing"
```

---

## Task 23: R15 — applied-food texture

**Files:**
- Modify: `src/foodbrew/engine/rules/r15_applied_texture.py`
- Test: `tests/engine/test_r15_applied_texture.py`

- [ ] **Step 1: Write the failing test**

`tests/engine/test_r15_applied_texture.py`:

```python
from foodbrew.engine.rules import r15_applied_texture as r15
from foodbrew.engine.types import (
    Deadline, DwellProfile, Enzyme, EvalContext, Food, Format, Formulation, Phase,
    SelectedEnzyme, SeverityTier, StructuralClass, StructuralEntry, Tracked,
    TruthLabel, Verdict,
)


def _enzyme(eid, entries):
    return Enzyme(
        id=eid, name=eid, substrate_id="lactose", source_type="fungal", priority="high",
        deadline=Deadline.BEFORE_COLON,
        ph_min=Tracked(3.0, TruthLabel.CONFIRMED, "t"),
        ph_max=Tracked(7.0, TruthLabel.CONFIRMED, "t"),
        ph_opt_low=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
        ph_opt_high=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
        ph_shelf_stable_min=Tracked(None, TruthLabel.UNCONFIRMED), dose_unit="FCC",
        degrades_structural=entries,
    )


GREENS = Food(id="mixed_greens", name="Mixed greens", category="green",
              is_application_food=True, structural=(StructuralClass.PECTIN_CELLULOSE,))
CHICKEN = Food(id="chicken_cooked", name="Cooked chicken", category="protein",
               is_application_food=True, structural=(StructuralClass.STRUCTURAL_PROTEIN,))

LACTASE = _enzyme("lactase", ())
CELLULASE = _enzyme("cellulase", (StructuralEntry(StructuralClass.PECTIN_CELLULOSE,
                                                  SeverityTier.GRADUAL),))
RAPID_PROTEASE = _enzyme("synthetic_rapid",
                         (StructuralEntry(StructuralClass.STRUCTURAL_PROTEIN,
                                          SeverityTier.RAPID),))
INULINASE = _enzyme("inulinase", (StructuralEntry(StructuralClass.PECTIN_CELLULOSE,
                                                  SeverityTier.UNCONFIRMED),))


def _ctx(enzymes, foods, dwell=None):
    emap = {e.id: e for e in enzymes}
    return EvalContext(
        formulation=Formulation(
            id="f", format=Format.DUAL_CHAMBER, recipe=(),
            enzymes=tuple(SelectedEnzyme(e.id, 100.0, Phase.DRY) for e in enzymes),
            application_food_ids=tuple(f.id for f in foods), dwell_profile=dwell,
        ),
        enzymes=emap, foods={f.id: f for f in foods}, substrates={},
    )


def test_narrow_blend_passes_every_profile():
    # Spec §13 fixture (k).
    env = r15.envelope(_ctx([LACTASE], [GREENS]))
    assert all(v is Verdict.PASS for v in env.values())


def test_gradual_degrader_worsens_with_dwell():
    # Spec §13 fixture (l).
    env = r15.envelope(_ctx([CELLULASE], [GREENS]))
    assert env[DwellProfile.IMMEDIATE] is Verdict.PASS
    assert env[DwellProfile.PACKED] is Verdict.AMBER
    assert env[DwellProfile.MARINADE] is Verdict.RED


def test_rapid_tier_reds_every_profile():
    # Spec §13 fixture (m) — synthetic record by design.
    env = r15.envelope(_ctx([RAPID_PROTEASE], [CHICKEN]))
    assert all(v is Verdict.RED for v in env.values())


def test_unconfirmed_tier_is_cannot_assess_everywhere():
    # Spec §13 fixture (o).
    env = r15.envelope(_ctx([INULINASE], [GREENS]))
    assert all(v is Verdict.CANNOT_ASSESS for v in env.values())


def test_no_intersection_when_structural_classes_differ():
    env = r15.envelope(_ctx([CELLULASE], [CHICKEN]))
    assert all(v is Verdict.PASS for v in env.values())


def test_multiple_pairs_take_the_worst_never_compound():
    # Spec §6.2 R15: overlap never compounds beyond the worst single pair.
    env = r15.envelope(_ctx([CELLULASE, RAPID_PROTEASE], [GREENS, CHICKEN]))
    assert env[DwellProfile.IMMEDIATE] is Verdict.RED  # from the rapid pair alone


def test_findings_name_the_enzyme_and_food():
    findings = r15.evaluate(_ctx([CELLULASE], [GREENS]))
    pair = [f for f in findings if f.enzyme_id == "cellulase" and f.food_id == "mixed_greens"]
    assert pair
    assert "mixed greens" in pair[0].message.lower()


def test_no_application_foods_produces_no_findings():
    assert r15.evaluate(_ctx([CELLULASE], [])) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/engine/test_r15_applied_texture.py -v`
Expected: FAIL — `AttributeError: module has no attribute 'envelope'`

- [ ] **Step 3: Write the implementation**

Replace `src/foodbrew/engine/rules/r15_applied_texture.py`:

```python
"""R15 — applied-food texture (spec §6.2, KB §4e extended to the plate).

Scope is what the dressing does to the food it is poured on, over time. What it
does to itself in the jar is R8.
"""

from __future__ import annotations

from foodbrew.engine.texture import verdict_for_tier
from foodbrew.engine.types import (
    DwellProfile, EvalContext, RuleFinding, Verdict, worst,
)

RULE_ID = "R15"
ADVISORY = False


def _pairs(ctx: EvalContext):
    """Yield (enzyme, food, structural_entry) for every degrading intersection."""
    for selected in ctx.selected_enzymes():
        enzyme = ctx.enzyme_for(selected)
        if not enzyme.degrades_structural:
            continue
        for food_id in ctx.formulation.application_food_ids:
            food = ctx.foods.get(food_id)
            if food is None or not food.structural:
                continue
            for entry in enzyme.degrades_structural:
                if entry.structural_class in food.structural:
                    yield enzyme, food, entry


def envelope(ctx: EvalContext) -> dict[DwellProfile, Verdict]:
    """Worst verdict per dwell profile across every intersecting pair.

    Overlap never compounds severity beyond the worst single pair: no source
    supports an additive model (spec §6.2 R15).
    """
    result = {profile: [] for profile in DwellProfile}
    for _enzyme, _food, entry in _pairs(ctx):
        for profile in DwellProfile:
            result[profile].append(verdict_for_tier(entry.tier, profile))
    return {profile: worst(verdicts) for profile, verdicts in result.items()}


def evaluate(ctx: EvalContext) -> list[RuleFinding]:
    findings: list[RuleFinding] = []

    for enzyme, food, entry in _pairs(ctx):
        per_profile = {p: verdict_for_tier(entry.tier, p) for p in DwellProfile}
        evidence = {
            "structural_class": entry.structural_class.value,
            "tier": entry.tier.value,
            "envelope": {p.value: v.value for p, v in per_profile.items()},
        }

        if entry.tier.value == "unconfirmed":
            message = (
                f"{enzyme.name} may act on the {entry.structural_class.value} that "
                f"{food.name.lower()} depends on for texture, but no source confirms "
                f"whether it does or how fast. Cannot assess."
            )
        else:
            failing = [p.value for p, v in per_profile.items() if v is not Verdict.PASS]
            message = (
                f"{enzyme.name} degrades the {entry.structural_class.value} that "
                f"{food.name.lower()} depends on for texture. Affected use occasions: "
                f"{', '.join(failing)}."
            )

        findings.append(
            RuleFinding(
                RULE_ID, worst(per_profile.values()), message, evidence,
                enzyme_id=enzyme.id, food_id=food.id,
            )
        )

    return findings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/engine/test_r15_applied_texture.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/engine/rules/r15_applied_texture.py tests/engine/test_r15_applied_texture.py
git commit -m "feat(engine): implement R15 applied-food texture with occasion envelope"
```

---

## Task 24: Trial helpers

Pure functions M4's UI and API will call. They live in the engine because they are decisions, not storage.

**Files:**
- Create: `src/foodbrew/engine/trial_rules.py`
- Test: `tests/engine/test_trial_rules.py`

- [ ] **Step 1: Write the failing test**

`tests/engine/test_trial_rules.py`:

```python
import pytest

from foodbrew.engine.trial_rules import (
    ACIDIFIED_FOOD_PH_LIMIT, ConfidenceTier, ambient_storage_allowed, confidence_tier,
)


def test_default_observation_is_an_anecdote():
    # Spec §13 fixture (p) — solo, unblinded, no control.
    assert confidence_tier(was_blinded=False, had_undressed_control=False) is ConfidenceTier.ANECDOTE


def test_blinding_upgrades_to_suggestive():
    assert confidence_tier(was_blinded=True, had_undressed_control=False) is ConfidenceTier.SUGGESTIVE


def test_undressed_control_upgrades_to_suggestive():
    assert confidence_tier(was_blinded=False, had_undressed_control=True) is ConfidenceTier.SUGGESTIVE


def test_both_flags_still_only_reach_suggestive():
    # Nothing recorded at home is ever demonstrated, proven, or validated.
    assert confidence_tier(was_blinded=True, had_undressed_control=True) is ConfidenceTier.SUGGESTIVE


def test_no_tier_stronger_than_suggestive_exists():
    assert set(ConfidenceTier) == {ConfidenceTier.ANECDOTE, ConfidenceTier.SUGGESTIVE}


def test_acidified_food_limit_is_four_point_six():
    assert ACIDIFIED_FOOD_PH_LIMIT == 4.6


@pytest.mark.parametrize("ph,expected", [(4.1, True), (4.5, True), (4.6, False), (5.2, False)])
def test_ambient_storage_gate(ph, expected):
    # Spec §13 fixture (q) and Workflow E — 21 CFR 114 acidified-foods line.
    assert ambient_storage_allowed(ph) is expected


def test_ambient_storage_denied_without_a_measured_ph():
    assert ambient_storage_allowed(None) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/engine/test_trial_rules.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'foodbrew.engine.trial_rules'`

- [ ] **Step 3: Write the implementation**

`src/foodbrew/engine/trial_rules.py`:

```python
"""Pure decisions the kitchen trial depends on (spec §6.6 and Workflow E).

M4 builds the capture UI on top of these; the rules themselves live here so they
are testable without a database and cannot be bypassed by a form.
"""

from __future__ import annotations

from enum import Enum

#: 21 CFR 114 acidified-foods line, cited in the founder's condiment materials.
#: Above this, a low-acid product left at room temperature is a food-safety
#: problem rather than a formulation one, so the tool declines to schedule it.
ACIDIFIED_FOOD_PH_LIMIT = 4.6


class ConfidenceTier(str, Enum):
    """Spec §6.6. Deliberately only two values — nothing recorded at home is
    ever demonstrated, proven, or validated."""

    ANECDOTE = "anecdote"
    SUGGESTIVE = "suggestive"


def confidence_tier(*, was_blinded: bool, had_undressed_control: bool) -> ConfidenceTier:
    """Rigor is captured opportunistically, per observation, not committed up front."""
    if was_blinded or had_undressed_control:
        return ConfidenceTier.SUGGESTIVE
    return ConfidenceTier.ANECDOTE


def ambient_storage_allowed(measured_ph: float | None) -> bool:
    """An ambient storage watch requires a measured pH strictly below the limit.

    No measurement means no ambient watch: an unknown pH is not an argument for
    leaving a possibly low-acid product on the counter.
    """
    if measured_ph is None:
        return False
    return float(measured_ph) < ACIDIFIED_FOOD_PH_LIMIT
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/engine/test_trial_rules.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/engine/trial_rules.py tests/engine/test_trial_rules.py
git commit -m "feat(engine): add trial confidence tiers and ambient-storage pH gate"
```

---

## Task 25: Aggregation and format recommendation (R13)

**Files:**
- Create: `src/foodbrew/engine/flags.py`
- Test: `tests/engine/test_flags.py`

- [ ] **Step 1: Write the failing test**

`tests/engine/test_flags.py`:

```python
from foodbrew.engine.flags import HEADLINE_DISPLAY, aggregate
from foodbrew.engine.types import DwellProfile, RuleFinding, Verdict


def _f(rule_id, verdict, advisory=False):
    return RuleFinding(rule_id, verdict, "m", {}, advisory=advisory)


CLEAN_ENVELOPE = dict.fromkeys(DwellProfile, Verdict.PASS)


def test_headline_takes_the_worst_headline_capable_verdict():
    findings = [_f("R1", Verdict.PASS), _f("R4", Verdict.AMBER), _f("R5", Verdict.RED)]
    assert aggregate(findings, CLEAN_ENVELOPE, None).overall is Verdict.RED


def test_advisory_rules_can_never_set_the_headline():
    findings = [
        _f("R1", Verdict.PASS),
        _f("R8", Verdict.AMBER, advisory=True),
        _f("R9", Verdict.AMBER, advisory=True),
        _f("R12", Verdict.CANNOT_ASSESS, advisory=True),
        _f("R16", Verdict.CANNOT_ASSESS, advisory=True),
    ]
    assert aggregate(findings, CLEAN_ENVELOPE, None).overall is Verdict.PASS


def test_r12_promoted_finding_does_set_the_headline():
    # Spec §13 fixture (h2) — promotion is per-finding, not per-module.
    findings = [_f("R1", Verdict.PASS), _f("R12", Verdict.RED, advisory=False)]
    assert aggregate(findings, CLEAN_ENVELOPE, None).overall is Verdict.RED


def test_cannot_assess_outranks_amber():
    findings = [_f("R4", Verdict.AMBER), _f("R7", Verdict.CANNOT_ASSESS)]
    assert aggregate(findings, CLEAN_ENVELOPE, None).overall is Verdict.CANNOT_ASSESS


def test_r15_envelope_contributes_amber_when_undeclared():
    envelope = {
        DwellProfile.IMMEDIATE: Verdict.PASS,
        DwellProfile.PACKED: Verdict.AMBER,
        DwellProfile.MARINADE: Verdict.RED,
    }
    assert aggregate([_f("R1", Verdict.PASS)], envelope, None).overall is Verdict.AMBER


def test_r15_envelope_contributes_red_when_declared_profile_fails():
    envelope = {
        DwellProfile.IMMEDIATE: Verdict.PASS,
        DwellProfile.PACKED: Verdict.AMBER,
        DwellProfile.MARINADE: Verdict.RED,
    }
    result = aggregate([_f("R1", Verdict.PASS)], envelope, DwellProfile.MARINADE)
    assert result.overall is Verdict.RED


def test_r15_raw_findings_do_not_double_count():
    # R15's contribution comes from the envelope, not from its own findings.
    envelope = dict.fromkeys(DwellProfile, Verdict.PASS)
    findings = [_f("R1", Verdict.PASS), _f("R15", Verdict.RED)]
    assert aggregate(findings, envelope, None).overall is Verdict.PASS


def test_display_mapping_covers_all_four_states():
    assert HEADLINE_DISPLAY[Verdict.RED] == "RED"
    assert HEADLINE_DISPLAY[Verdict.CANNOT_ASSESS] == "GRAY"
    assert HEADLINE_DISPLAY[Verdict.AMBER] == "AMBER"
    assert HEADLINE_DISPLAY[Verdict.PASS] == "GREEN"


def test_findings_are_grouped_for_display():
    findings = [
        _f("R5", Verdict.RED),
        _f("R7", Verdict.CANNOT_ASSESS),
        _f("R4", Verdict.AMBER),
        _f("R9", Verdict.AMBER, advisory=True),
    ]
    result = aggregate(findings, CLEAN_ENVELOPE, None)
    assert [f.rule_id for f in result.blockers] == ["R5"]
    assert [f.rule_id for f in result.data_gaps] == ["R7"]
    assert [f.rule_id for f in result.cautions] == ["R4"]
    assert [f.rule_id for f in result.advisories] == ["R9"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/engine/test_flags.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'foodbrew.engine.flags'`

- [ ] **Step 3: Write the implementation**

`src/foodbrew/engine/flags.py`:

```python
"""Spec §6.4 — aggregation, and R13's headline mapping."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from foodbrew.engine.texture import headline_contribution
from foodbrew.engine.types import DwellProfile, RuleFinding, Verdict, worst

#: Spec §6.4 — headline display is one-to-one with the aggregated verdict.
HEADLINE_DISPLAY: Mapping[Verdict, str] = {
    Verdict.RED: "RED",
    Verdict.CANNOT_ASSESS: "GRAY",
    Verdict.AMBER: "AMBER",
    Verdict.PASS: "GREEN",
}


@dataclass(frozen=True, slots=True)
class Aggregation:
    overall: Verdict
    display: str
    blockers: tuple[RuleFinding, ...]
    data_gaps: tuple[RuleFinding, ...]
    cautions: tuple[RuleFinding, ...]
    advisories: tuple[RuleFinding, ...]


def aggregate(
    findings: Sequence[RuleFinding],
    envelope: Mapping[DwellProfile, Verdict],
    declared_profile: DwellProfile | None,
) -> Aggregation:
    """Overall flag = worst headline-capable verdict, plus R15's envelope contribution.

    R15's own findings are excluded from the direct worst-of: its contribution is
    computed from the envelope under spec §6.4's special rule, so counting both
    would double-count it.
    """
    headline_verdicts = [
        f.verdict for f in findings if not f.advisory and f.rule_id != "R15"
    ]
    headline_verdicts.append(headline_contribution(envelope, declared_profile))
    overall = worst(headline_verdicts)

    advisories = tuple(f for f in findings if f.advisory)
    non_advisory = [f for f in findings if not f.advisory]

    return Aggregation(
        overall=overall,
        display=HEADLINE_DISPLAY[overall],
        blockers=tuple(f for f in non_advisory if f.verdict is Verdict.RED),
        data_gaps=tuple(f for f in non_advisory if f.verdict is Verdict.CANNOT_ASSESS),
        cautions=tuple(f for f in non_advisory if f.verdict is Verdict.AMBER),
        advisories=advisories,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/engine/test_flags.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/engine/flags.py tests/engine/test_flags.py
git commit -m "feat(engine): add aggregation with advisory exclusion and envelope contribution"
```

---

## Task 26: The evaluate orchestrator

**Files:**
- Create: `src/foodbrew/engine/evaluate.py`
- Modify: `src/foodbrew/engine/__init__.py`
- Test: `tests/engine/test_evaluate.py`
- Test: `tests/engine/test_purity.py`

- [ ] **Step 1: Write the failing tests**

`tests/engine/test_evaluate.py`:

```python
import pytest

from foodbrew import ENGINE_VERSION
from foodbrew.engine import evaluate
from foodbrew.engine.rules.r14_substrate_coverage import ValidationRejection
from foodbrew.engine.types import (
    EvalContext, Format, Formulation, Phase, SelectedEnzyme, Verdict,
)
from foodbrew.seedload.loader import load_seed

SEED = load_seed()


def _ctx(**overrides):
    form = Formulation(
        id="f", format=Format.DUAL_CHAMBER, recipe=(),
        enzymes=(SelectedEnzyme("lactase_fungal_acid", 9000.0, Phase.DRY),),
        target_trigger_food_ids=("milk",),
        **overrides,
    )
    return EvalContext(
        formulation=form, enzymes=SEED.enzymes, foods=SEED.foods,
        substrates=SEED.substrates, gi_regions=SEED.gi_regions,
    )


def test_evaluation_records_the_engine_version():
    assert evaluate(_ctx()).engine_version == ENGINE_VERSION


def test_evaluation_carries_findings_from_multiple_rules():
    rule_ids = {f.rule_id for f in evaluate(_ctx()).findings}
    assert {"R2", "R4", "R11", "R12", "R14"} <= rule_ids


def test_evaluation_includes_the_occasion_envelope():
    result = evaluate(_ctx())
    assert len(result.envelope) == 3


def test_evaluation_exposes_a_display_headline():
    assert evaluate(_ctx()).display in {"RED", "GRAY", "AMBER", "GREEN"}


def test_same_input_produces_identical_output():
    a, b = evaluate(_ctx()), evaluate(_ctx())
    assert a.findings == b.findings
    assert a.overall is b.overall


def test_validation_rejection_propagates():
    ctx = EvalContext(
        formulation=Formulation(id="f", format=Format.DUAL_CHAMBER, recipe=(), enzymes=()),
        enzymes=SEED.enzymes, foods=SEED.foods, substrates=SEED.substrates,
        gi_regions=SEED.gi_regions,
    )
    with pytest.raises(ValidationRejection):
        evaluate(ctx)


def test_prohibited_words_never_appear_in_engine_messages():
    # Spec §10 report lint, asserted at the source.
    banned = ["safe", "validated", "guaranteed", "clinically proven", "proven", "demonstrated"]
    for finding in evaluate(_ctx()).findings:
        lowered = finding.message.lower()
        for word in banned:
            assert word not in lowered, f"{finding.rule_id} says '{word}': {finding.message}"
```

`tests/engine/test_purity.py`:

```python
import ast
import pathlib

ENGINE_DIR = pathlib.Path("src/foodbrew/engine")
FORBIDDEN = {"json", "sqlite3", "pathlib", "os", "foodbrew.db", "foodbrew.seedload"}


def _imported_modules(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def test_engine_never_imports_io_or_persistence():
    """Spec §4 dependency rule — engine/ is a pure functional core."""
    offenders = []
    for path in ENGINE_DIR.rglob("*.py"):
        for module in _imported_modules(path):
            root = module.split(".")[0]
            if module in FORBIDDEN or root in FORBIDDEN:
                offenders.append(f"{path}: imports {module}")
    assert offenders == [], "\n".join(offenders)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/engine/test_evaluate.py tests/engine/test_purity.py -v`
Expected: `test_evaluate.py` fails with `ImportError: cannot import name 'evaluate'`; `test_purity.py` passes already (keep it — it guards future tasks).

- [ ] **Step 3: Write the implementation**

`src/foodbrew/engine/evaluate.py`:

```python
"""Orchestrator — runs every rule, aggregates, and returns a frozen Evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from foodbrew import ENGINE_VERSION
from foodbrew.engine.flags import aggregate
from foodbrew.engine.rules import ALL_RULES, r15_applied_texture
from foodbrew.engine.types import DwellProfile, EvalContext, RuleFinding, Verdict


@dataclass(frozen=True, slots=True)
class Evaluation:
    engine_version: str
    overall: Verdict
    display: str
    findings: tuple[RuleFinding, ...]
    envelope: Mapping[DwellProfile, Verdict]
    blockers: tuple[RuleFinding, ...]
    data_gaps: tuple[RuleFinding, ...]
    cautions: tuple[RuleFinding, ...]
    advisories: tuple[RuleFinding, ...]


def evaluate(ctx: EvalContext) -> Evaluation:
    """Run the whole rule set against one formulation.

    Rules run in registry order so findings are stable, which is what makes a
    stored snapshot reproducible byte-for-byte on the same engine version.
    """
    findings: list[RuleFinding] = []
    for module in ALL_RULES:
        produced = module.evaluate(ctx)
        for finding in produced:
            # A module's static ADVISORY is the default; a rule may override it
            # per finding (R12's per-enzyme promotion).
            if module.ADVISORY and not finding.advisory:
                finding = RuleFinding(
                    finding.rule_id, finding.verdict, finding.message, finding.evidence,
                    finding.enzyme_id, finding.food_id, advisory=True,
                )
            findings.append(finding)

    envelope = r15_applied_texture.envelope(ctx)
    agg = aggregate(findings, envelope, ctx.formulation.dwell_profile)

    return Evaluation(
        engine_version=ENGINE_VERSION,
        overall=agg.overall,
        display=agg.display,
        findings=tuple(findings),
        envelope=envelope,
        blockers=agg.blockers,
        data_gaps=agg.data_gaps,
        cautions=agg.cautions,
        advisories=agg.advisories,
    )
```

Replace `src/foodbrew/engine/__init__.py`:

```python
"""Pure rules engine. No I/O, no persistence — see tests/engine/test_purity.py."""

from foodbrew.engine.evaluate import Evaluation, evaluate

__all__ = ["Evaluation", "evaluate"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/engine/ -v`
Expected: all pass, including `test_prohibited_words_never_appear_in_engine_messages`

> **If the prohibited-words test fails,** a rule message used a banned word. Rewrite the message — do not weaken the test. "Food grade" is fine because the banned token is the standalone word "safe"; if a message trips on a substring like "safety", change the wording rather than the assertion.

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/engine/evaluate.py src/foodbrew/engine/__init__.py tests/engine/test_evaluate.py tests/engine/test_purity.py
git commit -m "feat(engine): add evaluate orchestrator with purity and language guards"
```

---

## Task 27: Golden fixtures

The spec's §13 (a)–(q). These assert the composed rules reproduce KB §4m without anyone hardcoding it.

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_golden_fixtures.py`

- [ ] **Step 1: Write the fixture builders**

`tests/conftest.py`:

```python
"""Builders for the golden fixtures.

Per the plan's stated boundary: fixtures take every ENZYME record from the real
shipped seed, and supply recipe pH and per-food substrate loads as explicit
user_provided test inputs — because every seeded food pH and load is unconfirmed
by design (spec §9.3).
"""

from __future__ import annotations

import dataclasses

import pytest

from foodbrew.engine.types import (
    EvalContext, Format, Formulation, Phase, ProcessStep, RecipeIngredient,
    SelectedEnzyme, SeverityTier, StructuralClass, StructuralEntry, Tracked, TruthLabel,
)
from foodbrew.seedload.loader import load_seed


@pytest.fixture(scope="session")
def seed():
    return load_seed()


@pytest.fixture
def with_load(seed):
    """Return a foods mapping where the named foods carry a confirmed load."""

    def _apply(**loads_by_food_id):
        foods = dict(seed.foods)
        for food_id, value in loads_by_food_id.items():
            foods[food_id] = dataclasses.replace(
                foods[food_id],
                typical_load_value=Tracked(value, TruthLabel.USER_PROVIDED, "fixture"),
            )
        return foods

    return _apply


@pytest.fixture
def make_ctx(seed):
    """Build an EvalContext with sensible fixture defaults."""

    def _build(
        *,
        fmt=Format.PREMIXED_WET,
        enzymes=(("lactase_fungal_acid", 9000.0, Phase.WET),),
        recipe=(),
        measured_ph=None,
        trigger_foods=(),
        application_foods=(),
        dwell_profile=None,
        process_steps=(),
        enzyme_addition_index=None,
        foods=None,
        enzyme_catalog=None,
    ):
        selections = tuple(
            SelectedEnzyme(eid, dose, phase, encapsulated=(len(rest) > 0 and rest[0]))
            for eid, dose, phase, *rest in
            [(e if len(e) > 3 else (*e, False)) for e in enzymes]
        )
        form = Formulation(
            id="fixture", format=fmt,
            recipe=tuple(RecipeIngredient(f, g) for f, g in recipe),
            enzymes=selections,
            target_trigger_food_ids=tuple(trigger_foods),
            application_food_ids=tuple(application_foods),
            dwell_profile=dwell_profile,
            measured_ph=(
                Tracked(measured_ph, TruthLabel.USER_PROVIDED, "fixture bench reading")
                if measured_ph is not None
                else Tracked(None, TruthLabel.UNCONFIRMED)
            ),
            process_steps=tuple(process_steps),
            enzyme_addition_index=enzyme_addition_index,
        )
        return EvalContext(
            formulation=form,
            enzymes=enzyme_catalog or seed.enzymes,
            foods=foods or seed.foods,
            substrates=seed.substrates,
            gi_regions=seed.gi_regions,
        )

    return _build


@pytest.fixture
def synthetic_rapid_enzyme(seed):
    """Spec §6.3.1 / fixture (m) — a test-only record claiming the rapid tier.

    Deliberately synthetic: no shipped enzyme claims rapid, because no source
    supports a minutes-scale rate claim about a real enzyme.
    """
    catalog = dict(seed.enzymes)
    base = catalog["protease_bromelain"]
    catalog["synthetic_rapid_protease"] = dataclasses.replace(
        base,
        id="synthetic_rapid_protease",
        name="Synthetic rapid protease (test only)",
        degrades_structural=(
            StructuralEntry(StructuralClass.STRUCTURAL_PROTEIN, SeverityTier.RAPID),
        ),
    )
    return catalog
```

- [ ] **Step 2: Write the failing golden-fixture tests**

`tests/test_golden_fixtures.py`:

```python
"""Spec §13 golden fixtures (a)-(q)."""

from __future__ import annotations

import dataclasses

import pytest

from foodbrew.engine import evaluate
from foodbrew.engine.rules.r14_substrate_coverage import ValidationRejection
from foodbrew.engine.trial_rules import (
    ConfidenceTier, ambient_storage_allowed, confidence_tier,
)
from foodbrew.engine.texture import dwell_bucket
from foodbrew.engine.types import (
    DwellProfile, Format, Phase, ProcessStep, Tracked, TruthLabel, Verdict,
)

LACTASE = "lactase_fungal_acid"
ALPHA_GAL = "alpha_galactosidase"
BROMELAIN = "protease_bromelain"


def _by_rule(result, rule_id):
    return [f for f in result.findings if f.rule_id == rule_id]


def _verdict(result, rule_id):
    findings = _by_rule(result, rule_id)
    assert findings, f"expected at least one {rule_id} finding"
    from foodbrew.engine.types import worst
    return worst(f.verdict for f in findings)


# (a) --------------------------------------------------------------------

def test_a_wet_vinaigrette_at_ph_3_is_red_via_r1(make_ctx):
    result = evaluate(make_ctx(
        fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",),
        process_steps=(ProcessStep(1, "Blend"), ProcessStep(2, "Add enzyme")),
        enzyme_addition_index=2,
    ))
    assert _verdict(result, "R1") is Verdict.RED
    assert _verdict(result, "R4") is Verdict.AMBER
    assert result.display == "RED"


# (b) --------------------------------------------------------------------

def test_b_creamy_at_ph_4_4_is_amber_overall(make_ctx):
    """DEVIATION (see plan header): R1 is AMBER here, not pass — 4.4 is above the
    survival floor but below the 5.0 optimum, which R1's own text calls AMBER.
    The headline is unaffected."""
    result = evaluate(make_ctx(
        fmt=Format.PREMIXED_WET, measured_ph=4.4, trigger_foods=("milk",),
        recipe=(("buttermilk", 100.0),),
        process_steps=(ProcessStep(1, "Blend"), ProcessStep(2, "Add enzyme")),
        enzyme_addition_index=2,
    ))
    assert _verdict(result, "R1") is Verdict.AMBER
    assert _verdict(result, "R4") is Verdict.AMBER
    assert _verdict(result, "R8") is Verdict.AMBER
    assert result.display == "AMBER"


# (c) --------------------------------------------------------------------

@pytest.mark.parametrize("fmt", [Format.DRY_SACHET, Format.DUAL_CHAMBER])
def test_c_dry_formats_are_green(make_ctx, with_load, fmt):
    result = evaluate(make_ctx(
        fmt=fmt, measured_ph=4.4,
        enzymes=((ALPHA_GAL, 800.0, Phase.DRY),),
        trigger_foods=("black_beans",), foods=with_load(black_beans=6.0),
        process_steps=(ProcessStep(1, "Blend"), ProcessStep(2, "Add enzyme")),
        enzyme_addition_index=2,
    ))
    assert _by_rule(result, "R1") == []
    assert _verdict(result, "R4") is Verdict.PASS
    assert result.display == "GREEN"


# (d) --------------------------------------------------------------------

def test_d_bromelain_wet_with_lactase_is_r5_red(make_ctx):
    result = evaluate(make_ctx(
        fmt=Format.PREMIXED_WET, measured_ph=5.0, trigger_foods=("milk",),
        enzymes=((LACTASE, 9000.0, Phase.WET), (BROMELAIN, 100.0, Phase.WET)),
        process_steps=(ProcessStep(1, "Blend"), ProcessStep(2, "Add enzyme")),
        enzyme_addition_index=2,
    ))
    assert _verdict(result, "R5") is Verdict.RED


def test_d_bromelain_separated_passes_r5(make_ctx):
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER, measured_ph=5.0, trigger_foods=("milk",),
        enzymes=((LACTASE, 9000.0, Phase.DRY), (BROMELAIN, 100.0, Phase.DRY)),
        process_steps=(ProcessStep(1, "Blend"), ProcessStep(2, "Add enzyme")),
        enzyme_addition_index=2,
    ))
    assert _verdict(result, "R5") is Verdict.PASS


# (e) --------------------------------------------------------------------

def test_e_heat_after_enzyme_is_r3_red(make_ctx):
    result = evaluate(make_ctx(
        measured_ph=5.0, trigger_foods=("milk",),
        process_steps=(ProcessStep(1, "Add enzyme"), ProcessStep(2, "Hot fill", is_heat=True)),
        enzyme_addition_index=1,
    ))
    assert _verdict(result, "R3") is Verdict.RED


def test_e_heat_before_enzyme_passes_r3(make_ctx):
    result = evaluate(make_ctx(
        measured_ph=5.0, trigger_foods=("milk",),
        process_steps=(ProcessStep(1, "Pasteurise", is_heat=True), ProcessStep(2, "Add enzyme")),
        enzyme_addition_index=2,
    ))
    assert _verdict(result, "R3") is Verdict.PASS


# (f) and (f2) -----------------------------------------------------------

def test_f_alpha_gal_150_galu_against_6g_gos_is_r7_amber(make_ctx, with_load):
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER, enzymes=((ALPHA_GAL, 150.0, Phase.DRY),),
        trigger_foods=("black_beans",), foods=with_load(black_beans=6.0),
    ))
    assert _verdict(result, "R7") is Verdict.AMBER


def test_f2_multi_food_gos_loads_are_summed(make_ctx, with_load):
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER, enzymes=((ALPHA_GAL, 800.0, Phase.DRY),),
        trigger_foods=("black_beans", "lentils"),
        foods=with_load(black_beans=4.0, lentils=2.5),
    ))
    finding = _by_rule(result, "R7")[0]
    assert finding.evidence["substrate_load"] == pytest.approx(6.5)


# (g) --------------------------------------------------------------------

def test_g_r9_fires_for_both_inulinase_and_alpha_gal(make_ctx, with_load):
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER,
        enzymes=((ALPHA_GAL, 800.0, Phase.DRY), ("inulinase", 100.0, Phase.DRY)),
        trigger_foods=("black_beans",), foods=with_load(black_beans=6.0),
    ))
    enzymes_flagged = {f.enzyme_id for f in _by_rule(result, "R9")}
    assert {ALPHA_GAL, "inulinase"} <= enzymes_flagged


# (h) and (h2) -----------------------------------------------------------

def test_h_advisory_cannot_assess_does_not_gray_the_headline(make_ctx, with_load):
    """R12 returns cannot_assess for every seeded enzyme; fixtures (a)-(c) depend
    on that leaving the headline alone."""
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER, enzymes=((ALPHA_GAL, 800.0, Phase.DRY),),
        trigger_foods=("black_beans",), foods=with_load(black_beans=6.0),
    ))
    assert _verdict(result, "R12") is Verdict.CANNOT_ASSESS
    assert all(f.advisory for f in _by_rule(result, "R12"))
    assert result.display == "GREEN"


def test_h_headline_capable_cannot_assess_does_gray_the_headline(make_ctx):
    # No confirmed load, so R7 cannot assess and R7 is headline-capable.
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER, enzymes=((ALPHA_GAL, 800.0, Phase.DRY),),
        trigger_foods=("black_beans",),
    ))
    assert result.display == "GRAY"


def test_h2_r12_promotion_is_per_enzyme(make_ctx, seed, with_load):
    catalog = dict(seed.enzymes)
    catalog[ALPHA_GAL] = dataclasses.replace(
        catalog[ALPHA_GAL],
        temp_min_c=Tracked(4.0, TruthLabel.CONFIRMED, "supplier"),
        temp_max_c=Tracked(18.0, TruthLabel.CONFIRMED, "supplier"),
    )
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER,
        enzymes=((ALPHA_GAL, 800.0, Phase.DRY), (LACTASE, 9000.0, Phase.DRY)),
        trigger_foods=("black_beans",), foods=with_load(black_beans=6.0),
        enzyme_catalog=catalog,
    ))
    by_enzyme = {f.enzyme_id: f for f in _by_rule(result, "R12")}
    assert by_enzyme[ALPHA_GAL].advisory is False
    assert by_enzyme[ALPHA_GAL].verdict is Verdict.RED
    assert by_enzyme[LACTASE].advisory is True
    assert result.display == "RED"


# (i) and (j) ------------------------------------------------------------

def test_i_uncovered_trigger_food_is_r14_red(make_ctx, with_load):
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER, enzymes=((LACTASE, 9000.0, Phase.DRY),),
        trigger_foods=("black_beans",), foods=with_load(black_beans=6.0),
    ))
    assert _verdict(result, "R14") is Verdict.RED
    assert result.display == "RED"


def test_i_zero_enzymes_and_zero_trigger_foods_is_rejected(make_ctx):
    with pytest.raises(ValidationRejection):
        evaluate(make_ctx(fmt=Format.DUAL_CHAMBER, enzymes=()))


def test_j_polyol_is_cannot_assess_and_never_suggests_an_enzyme(make_ctx):
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER, enzymes=((LACTASE, 9000.0, Phase.DRY),),
        trigger_foods=("mushroom",),
    ))
    polyol = [f for f in _by_rule(result, "R14") if f.evidence.get("substrate") == "polyol"]
    assert polyol and polyol[0].verdict is Verdict.CANNOT_ASSESS


# (k)-(o2) ---------------------------------------------------------------

def test_k_narrow_blend_passes_the_whole_envelope(make_ctx, with_load):
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER,
        enzymes=((LACTASE, 9000.0, Phase.DRY), (ALPHA_GAL, 800.0, Phase.DRY)),
        trigger_foods=("black_beans",), foods=with_load(black_beans=6.0),
        application_foods=("mixed_greens",),
    ))
    assert all(v is Verdict.PASS for v in result.envelope.values())


def test_l_cellulase_on_greens_grades_by_dwell(make_ctx, with_load):
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER,
        enzymes=((ALPHA_GAL, 800.0, Phase.DRY), ("cellulase", 100.0, Phase.DRY)),
        trigger_foods=("black_beans",), foods=with_load(black_beans=6.0),
        application_foods=("mixed_greens",),
    ))
    assert result.envelope[DwellProfile.IMMEDIATE] is Verdict.PASS
    assert result.envelope[DwellProfile.PACKED] is Verdict.AMBER
    assert result.envelope[DwellProfile.MARINADE] is Verdict.RED
    assert result.display == "AMBER"


def test_m_rapid_tier_reds_all_three_and_the_headline(
    make_ctx, with_load, synthetic_rapid_enzyme
):
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER,
        enzymes=((ALPHA_GAL, 800.0, Phase.DRY),
                 ("synthetic_rapid_protease", 100.0, Phase.DRY)),
        trigger_foods=("black_beans",), foods=with_load(black_beans=6.0),
        application_foods=("chicken_cooked",),
        enzyme_catalog=synthetic_rapid_enzyme,
    ))
    assert all(v is Verdict.RED for v in result.envelope.values())
    assert result.display == "RED"


def test_n_declared_marinade_occasion_reds_the_headline(make_ctx, with_load):
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER,
        enzymes=((ALPHA_GAL, 800.0, Phase.DRY), ("cellulase", 100.0, Phase.DRY)),
        trigger_foods=("black_beans",), foods=with_load(black_beans=6.0),
        application_foods=("mixed_greens",), dwell_profile=DwellProfile.MARINADE,
    ))
    assert result.display == "RED"


def test_o_inulinase_on_artichoke_is_cannot_assess_everywhere(make_ctx, with_load):
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER,
        enzymes=((ALPHA_GAL, 800.0, Phase.DRY), ("inulinase", 100.0, Phase.DRY)),
        trigger_foods=("black_beans",), foods=with_load(black_beans=6.0),
        application_foods=("artichoke",),
    ))
    assert all(v is Verdict.CANNOT_ASSESS for v in result.envelope.values())


@pytest.mark.parametrize(
    "minutes,expected",
    [(0, DwellProfile.IMMEDIATE), (59, DwellProfile.IMMEDIATE),
     (60, DwellProfile.PACKED), (479, DwellProfile.PACKED),
     (480, DwellProfile.MARINADE), (1440, DwellProfile.MARINADE)],
)
def test_o2_dwell_bucketing(minutes, expected):
    assert dwell_bucket(minutes) is expected


# (p0), (p), (q) ---------------------------------------------------------

def test_p0_r16_is_advisory_and_reports_the_additive_gap(make_ctx, with_load):
    result = evaluate(make_ctx(
        fmt=Format.DUAL_CHAMBER, enzymes=((ALPHA_GAL, 800.0, Phase.DRY),),
        trigger_foods=("black_beans",), foods=with_load(black_beans=6.0),
    ))
    r16 = _by_rule(result, "R16")
    assert all(f.advisory for f in r16)
    assert any(f.verdict is Verdict.CANNOT_ASSESS for f in r16)
    assert result.display == "GREEN"


@pytest.mark.parametrize(
    "blinded,control,expected",
    [(False, False, ConfidenceTier.ANECDOTE),
     (True, False, ConfidenceTier.SUGGESTIVE),
     (False, True, ConfidenceTier.SUGGESTIVE),
     (True, True, ConfidenceTier.SUGGESTIVE)],
)
def test_p_confidence_tiers(blinded, control, expected):
    assert confidence_tier(was_blinded=blinded, had_undressed_control=control) is expected


@pytest.mark.parametrize("ph,allowed", [(5.2, False), (None, False), (4.1, True)])
def test_q_ambient_storage_gate(ph, allowed):
    assert ambient_storage_allowed(ph) is allowed
```

- [ ] **Step 3: Run the fixtures**

Run: `.venv/bin/pytest tests/test_golden_fixtures.py -v`
Expected: all pass.

> **These are the acceptance gate for M1.** If a fixture fails, the bug is in the rules, not the fixture — with two exceptions already documented in this plan's header: fixture (b)'s R1 verdict, and the use of explicit `user_provided` pH and load inputs. Do not weaken any other assertion to make a test green. If you believe a fixture is genuinely wrong, stop and raise it rather than editing it.

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py tests/test_golden_fixtures.py
git commit -m "test: add spec section 13 golden fixtures a through q"
```

---

## Task 28: Property tests

**Files:**
- Create: `tests/test_properties.py`

- [ ] **Step 1: Write the tests**

`tests/test_properties.py`:

```python
"""Spec §13 property tests — invariants that must hold for any input."""

from __future__ import annotations

import dataclasses

from hypothesis import given, settings
from hypothesis import strategies as st

from foodbrew.engine import evaluate
from foodbrew.engine.flags import aggregate
from foodbrew.engine.texture import verdict_for_tier
from foodbrew.engine.types import (
    DwellProfile, Format, Phase, RuleFinding, SeverityTier, Tracked, TruthLabel,
    Verdict, worst,
)

LACTASE = "lactase_fungal_acid"
ALPHA_GAL = "alpha_galactosidase"
_SEVERITY = {Verdict.PASS: 0, Verdict.AMBER: 1, Verdict.CANNOT_ASSESS: 2, Verdict.RED: 3}


@given(ph=st.floats(min_value=2.0, max_value=6.0))
@settings(max_examples=40, deadline=None)
def test_lowering_recipe_ph_never_improves_r1(make_ctx, ph):
    def r1_severity(value):
        result = evaluate(make_ctx(
            fmt=Format.PREMIXED_WET, measured_ph=value, trigger_foods=("milk",),
        ))
        findings = [f for f in result.findings if f.rule_id == "R1"]
        return _SEVERITY[worst(f.verdict for f in findings)]

    assert r1_severity(ph - 0.5) >= r1_severity(ph)


def test_moving_an_enzyme_wet_to_dry_never_worsens_r4(make_ctx):
    def r4_severity(fmt, phase):
        result = evaluate(make_ctx(
            fmt=fmt, measured_ph=4.4, trigger_foods=("milk",),
            enzymes=((LACTASE, 9000.0, phase),),
        ))
        findings = [f for f in result.findings if f.rule_id == "R4"]
        return _SEVERITY[worst(f.verdict for f in findings)]

    assert r4_severity(Format.DUAL_CHAMBER, Phase.DRY) <= r4_severity(
        Format.PREMIXED_WET, Phase.WET
    )


def test_increasing_dwell_never_improves_an_r15_profile():
    order = [DwellProfile.IMMEDIATE, DwellProfile.PACKED, DwellProfile.MARINADE]
    for tier in SeverityTier:
        severities = [_SEVERITY[verdict_for_tier(tier, p)] for p in order]
        assert severities == sorted(severities), f"{tier} improves with dwell"


@given(
    verdicts=st.lists(st.sampled_from(list(Verdict)), min_size=1, max_size=8),
    advisory_verdicts=st.lists(st.sampled_from(list(Verdict)), max_size=8),
)
@settings(max_examples=60, deadline=None)
def test_advisory_findings_never_change_the_overall_flag(verdicts, advisory_verdicts):
    clean = dict.fromkeys(DwellProfile, Verdict.PASS)
    headline_only = [RuleFinding("R1", v, "m", {}) for v in verdicts]
    with_advisories = headline_only + [
        RuleFinding("R9", v, "m", {}, advisory=True) for v in advisory_verdicts
    ]
    assert (
        aggregate(headline_only, clean, None).overall
        is aggregate(with_advisories, clean, None).overall
    )


@given(verdicts=st.lists(st.sampled_from(list(Verdict)), min_size=1, max_size=10))
@settings(max_examples=60, deadline=None)
def test_worst_matches_the_documented_severity_order(verdicts):
    assert _SEVERITY[worst(verdicts)] == max(_SEVERITY[v] for v in verdicts)


def test_same_snapshot_and_engine_version_reproduces_identical_findings(make_ctx):
    ctx = make_ctx(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    first, second = evaluate(ctx), evaluate(ctx)
    assert first == second


def test_editing_a_source_record_does_not_mutate_a_stored_evaluation(make_ctx, seed):
    ctx = make_ctx(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    stored = evaluate(ctx)
    before = stored.findings

    edited = dict(seed.enzymes)
    edited[LACTASE] = dataclasses.replace(
        edited[LACTASE], ph_shelf_stable_min=Tracked(2.0, TruthLabel.CONFIRMED, "supplier")
    )
    rerun = evaluate(make_ctx(
        fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",),
        enzyme_catalog=edited,
    ))

    assert stored.findings is before          # the stored object is untouched
    assert rerun.findings != stored.findings  # and the re-run genuinely differs
```

- [ ] **Step 2: Run the tests**

Run: `.venv/bin/pytest tests/test_properties.py -v`
Expected: all pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_properties.py
git commit -m "test: add property tests for monotonicity, advisory isolation, reproducibility"
```

---

## Task 29: SQLite schema and bootstrap

M2's API needs this. The engine still never touches it.

**Files:**
- Create: `src/foodbrew/db/__init__.py`
- Create: `src/foodbrew/db/schema.sql`
- Create: `src/foodbrew/db/bootstrap.py`
- Test: `tests/test_db_bootstrap.py`

- [ ] **Step 1: Write the failing test**

`tests/test_db_bootstrap.py`:

```python
import sqlite3

import pytest

from foodbrew.db.bootstrap import EXPECTED_TABLES, create_database


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "test.db"
    create_database(path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def test_every_spec_table_exists(db):
    rows = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    names = {r["name"] for r in rows}
    assert EXPECTED_TABLES <= names


def test_seed_is_loaded_on_bootstrap(db):
    assert db.execute("SELECT COUNT(*) c FROM enzyme").fetchone()["c"] == 12
    assert db.execute("SELECT COUNT(*) c FROM substrate").fetchone()["c"] == 12
    assert db.execute("SELECT COUNT(*) c FROM gi_region").fetchone()["c"] == 6
    assert db.execute("SELECT COUNT(*) c FROM food").fetchone()["c"] == 53


def test_truth_labels_survive_the_round_trip(db):
    row = db.execute(
        "SELECT temp_min_c_status, ph_min_status FROM enzyme WHERE id='lactase_fungal_acid'"
    ).fetchone()
    assert row["temp_min_c_status"] == "unconfirmed"
    assert row["ph_min_status"] == "confirmed"


def test_foreign_keys_are_enforced(db):
    db.execute("PRAGMA foreign_keys = ON")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO recipe_ingredient (recipe_id, food_id, amount_g) "
                   "VALUES ('nope', 'also_nope', 1.0)")


def test_bootstrap_is_idempotent(tmp_path):
    path = tmp_path / "twice.db"
    create_database(path)
    create_database(path)
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT COUNT(*) FROM enzyme").fetchone()[0] == 12
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_db_bootstrap.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'foodbrew.db'`

- [ ] **Step 3: Write the schema**

`src/foodbrew/db/schema.sql`:

```sql
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
```

- [ ] **Step 4: Write the bootstrap**

`src/foodbrew/db/__init__.py`:

```python
from foodbrew.db.bootstrap import create_database

__all__ = ["create_database"]
```

`src/foodbrew/db/bootstrap.py`:

```python
"""Create the SQLite database and populate reference tables from seed JSON."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from foodbrew.seedload.loader import Seed, load_seed

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

EXPECTED_TABLES = frozenset({
    "substrate", "enzyme", "food", "gi_region", "recipe", "recipe_ingredient",
    "formulation", "evaluation", "rule_finding", "variant_suggestion", "trial",
    "trial_batch", "trial_observation", "trial_symptom_entry", "proposal", "audit_event",
})


def _tracked_cols(prefix: str, tracked) -> dict:
    value = tracked.value
    if isinstance(value, bool):
        value = int(value)
    return {
        prefix: value,
        f"{prefix}_status": tracked.status.value,
        f"{prefix}_source": tracked.source,
    }


def _insert(conn: sqlite3.Connection, table: str, row: dict) -> None:
    cols = ", ".join(f'"{c}"' for c in row)
    placeholders = ", ".join("?" for _ in row)
    conn.execute(
        f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})",
        tuple(row.values()),
    )


def load_reference_data(conn: sqlite3.Connection, seed: Seed) -> None:
    for s in seed.substrates.values():
        _insert(conn, "substrate", {
            "id": s.id, "name": s.name,
            "native_human_enzyme": int(s.native_human_enzyme),
            "is_prebiotic": int(s.is_prebiotic),
            "no_commercial_enzyme": int(s.no_commercial_enzyme),
            "notes": s.notes,
        })

    for r in seed.gi_regions:
        _insert(conn, "gi_region", {
            "id": r.id, "name": r.name, "ph_low": r.ph_low, "ph_high": r.ph_high,
            "order": r.order, "dormant": int(r.dormant), "transit_note": r.transit_note,
        })

    for e in seed.enzymes.values():
        row = {
            "id": e.id, "name": e.name, "aliases_json": json.dumps(list(e.aliases)),
            "substrate_id": e.substrate_id, "source_type": e.source_type,
            "priority": e.priority, "deadline": e.deadline.value,
            "site_of_action": e.site_of_action, "dose_unit": e.dose_unit,
            "dose_benchmark_note": e.dose_benchmark_note,
            "is_protease": int(e.is_protease),
            "is_natural_source": int(e.is_natural_source),
            "food_grade_note": e.food_grade_note,
            "heat_labile_note": e.heat_labile_note,
            "degrades_structural_json": json.dumps([
                {"structural_class": x.structural_class.value, "tier": x.tier.value}
                for x in e.degrades_structural
            ]),
            "cost_tier": e.cost_tier, "supplier_note": e.supplier_note, "notes": e.notes,
        }
        for prefix in (
            "ph_min", "ph_max", "ph_opt_low", "ph_opt_high", "ph_shelf_stable_min",
            "temp_min_c", "temp_max_c", "temp_opt_c",
            "dose_min", "dose_max", "dose_evidence_threshold", "is_gras",
        ):
            row.update(_tracked_cols(prefix, getattr(e, prefix)))
        _insert(conn, "enzyme", row)

    for f in seed.foods.values():
        row = {
            "id": f.id, "name": f.name, "category": f.category,
            "is_recipe_ingredient": int(f.is_recipe_ingredient),
            "is_trigger_food": int(f.is_trigger_food),
            "is_application_food": int(f.is_application_food),
            "contains_substrate_ids_json": json.dumps(list(f.contains_substrate_ids)),
            "typical_load_unit": f.typical_load_unit,
            "contains_protease": int(f.contains_protease),
            "is_heat_processed": int(f.is_heat_processed),
            "structural_json": json.dumps([s.value for s in f.structural]),
            "notes": f.notes,
        }
        for prefix in ("ph", "water_content_pct", "typical_load_value"):
            row.update(_tracked_cols(prefix, getattr(f, prefix)))
        _insert(conn, "food", row)


def create_database(path: Path | str, seed: Seed | None = None) -> Path:
    """Create (or refresh) the database at `path`. Idempotent."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        load_reference_data(conn, seed or load_seed())
        conn.commit()
    finally:
        conn.close()
    return path
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_db_bootstrap.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add src/foodbrew/db/ tests/test_db_bootstrap.py
git commit -m "feat(db): add SQLite schema and idempotent seed bootstrap"
```

---

## Task 30: Docker and the M1 acceptance run

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `Makefile`

- [ ] **Step 1: Create `Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/
COPY seed/ ./seed/
RUN pip install --no-cache-dir -e '.[dev]'

COPY tests/ ./tests/

# M2 replaces this with the uvicorn entrypoint.
CMD ["python", "-c", "from foodbrew.db import create_database; create_database('/data/foodbrew.db'); print('database ready at /data/foodbrew.db')"]
```

- [ ] **Step 2: Create `docker-compose.yml`**

```yaml
services:
  foodbrew:
    build: .
    volumes:
      # SQLite lives in a bind mount so backup is a folder copy and the same
      # image deploys to Fly.io later with a volume instead.
      - ./data:/data
    environment:
      FOODBREW_DB_PATH: /data/foodbrew.db
```

- [ ] **Step 3: Create `Makefile`**

```makefile
.PHONY: test lint fmt db docker-db

test:
	.venv/bin/pytest -q

lint:
	.venv/bin/ruff check src tests

fmt:
	.venv/bin/ruff format src tests

db:
	.venv/bin/python -c "from foodbrew.db import create_database; print(create_database('data/foodbrew.db'))"

docker-db:
	docker compose run --rm foodbrew
```

- [ ] **Step 4: Run the full acceptance check**

Run: `.venv/bin/ruff check src tests && .venv/bin/pytest -q`
Expected: ruff reports no issues; every test passes.

- [ ] **Step 5: Verify the database builds in Docker**

Run: `docker compose run --rm foodbrew`
Expected: `database ready at /data/foodbrew.db`, and `./data/foodbrew.db` exists on the host.

- [ ] **Step 6: Commit**

```bash
git add Dockerfile docker-compose.yml Makefile
git commit -m "chore: add Docker, compose bind mount, and make targets"
```

---

## M1 exit criteria

Before declaring M1 done, all of the following must hold:

- [ ] `.venv/bin/pytest -q` passes with zero failures and zero skips.
- [ ] `.venv/bin/ruff check src tests` is clean.
- [ ] Every golden fixture (a)–(q) in `tests/test_golden_fixtures.py` passes **against the real shipped seed catalogue**, with the five documented deviations (fixture (b)'s R1 verdict; explicit `user_provided` pH and load inputs; the R2 lactase test correction; R2/R7/R11's per-field advisory treatment; fixtures (b)/(h)/(l)/(p0)'s additional test-input setup).
- [ ] `tests/engine/test_purity.py` passes — nothing in `engine/` imports I/O or persistence.
- [ ] The prohibited-words assertion passes on every engine message.
- [ ] `docker compose run --rm foodbrew` produces a populated database.
- [ ] The five spec deviations in this plan's header have been raised with the spec owner and either accepted or corrected in the spec — deviation #4 (R2/R7/R11 advisory treatment) in particular, since it's a real rule-behavior change with product impact, not just a test correction.

**Do not begin M2 until these pass.** The spec's planning note (§14) exists because the R12 problem was invisible until rules were traced end-to-end against real seed data; the same is likely true of the §6.3.1 severity tiers and the §6.7 wet-ingredient threshold.

---

## Plan self-review

**Spec coverage.** §5 data model → Tasks 2, 3, 29. §6.1 R1–R13 → Tasks 11–20, 25. §6.2 R14–R16 → Tasks 19, 21, 23. §6.3/§6.3.1 → Task 22. §6.4 aggregation → Task 25. §6.6 labelling → Task 24. §6.7 conventions → Task 8. §8 GI model → Tasks 4, 9. §9 seed → Tasks 4, 5, 6, 7. §13 testing → Tasks 27, 28, plus per-rule tests throughout. §4 architecture and dependency rule → Tasks 1, 26 (`test_purity.py`), 30.

Deliberately **not** in M1, consistent with §14: R13's format-recommendation search (M3, with the variant engine), §6.5 protocol generation (M4), §7 auto-variants (M3), and every API and UI surface (M2–M4). `flags.py` implements R13's headline mapping only; the least-invasive-format search belongs with the variant machinery it depends on.

**Placeholder scan.** The fifteen rule stubs created in Task 10 are the one intentional placeholder, and every one is replaced by name in Tasks 11–23. No TODOs, no "handle edge cases", no "similar to Task N".

**Type consistency.** `Tracked.usable` is the single gate used by every rule. `RuleFinding.advisory` is set by the orchestrator from `module.ADVISORY` and overridden per-finding only by R12. `evaluate()` is imported from `foodbrew.engine` in tests and defined in `foodbrew.engine.evaluate`. `worst()` is defined once in `types.py` and reused in `flags.py`, `r15_applied_texture.py`, and the tests. `ValidationRejection` is raised in `r14_substrate_coverage.py` and imported from there in Tasks 21 and 27.

**Known cross-task dependency.** `r06_encapsulation.py` imports `FALLBACK_MARGIN_PH` from `r01_ph_survival.py`, so Task 11 must precede Task 16. The task order already enforces this.
