# M3 — Variants, Compare, Database Editor, and Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the loop between a verdict and a decision. M2 ends with the founder reading a RED headline and having nowhere to go. M3 gives her four things: the engine's own list of fixes with a one-click apply (§7), a side-by-side comparison of what changed and why (Workflow B), a database editor and proposals inbox so she can correct or confirm any value the tool leaned on (Workflow D), and a print-friendly report plus a Markdown export she can hand a food scientist (§10 screen 8). It also delivers R13's format recommendation, deferred out of M2 by that plan's decision #6, and the "data changed since this evaluation" banner.

**Architecture:** The three M2 layers hold, and the arrow still points one way — `api → store → engine`. Everything genuinely new in M3 is a **pure engine module**: the patch vocabulary, the format ladder, the §7 suggestion catalogue, the comparison table, and the report renderer. `store/` gains writers for the three tables M1 created and nobody has written to yet (`variant_suggestion`, `proposal`, `audit_event`), plus a snapshot differ that turns M2's byte-stable snapshot into a staleness signal. `api/` gains five endpoints and no logic. The React app gains three screens and one banner.

**Tech Stack:** Unchanged. Python 3.12, FastAPI, Uvicorn, Pydantic v2, stdlib `sqlite3`, pytest + httpx `TestClient`, React 19 + TypeScript + Vite, react-router-dom, Playwright, Docker multi-stage. **M3 adds no runtime dependency and no database column** — see decision #1.

**Spec:** `docs/superpowers/specs/2026-08-13-enzyme-rules-engine-design.md` — read §3 (Workflows B, C, D), §5.2 (`variant_suggestion`, `proposal`, `audit_event`), §5.4 (truth labels), §6.1 R13, §6.4 (aggregation), §7 (auto-variant table — this is the milestone's centre of gravity), §10 (API and screens 5, 7, 8), §12 (known limitations — items 1 and 5 constrain what a patch may do), §13 (testing: the contract test and the report lint), §14 (the M3 line) before starting.

**Prior milestones:**
- `docs/superpowers/plans/2026-08-13-m1-engine-and-seed.md` — merged as `cc0ed27`. R1–R16, seed catalogue, golden fixtures.
- `docs/superpowers/plans/2026-08-14-m2-api-and-core-ui.md` — merged as `58a7c3f`. 321 tests green, ruff clean, Playwright green, CI on every PR.

---

## What M3 is not

Restated from §14 so no task drifts. **Everything under Workflow E is M4:** protocol generation (`engine/protocol.py`), the trial / batch / observation / symptom-entry tables and their capture UI, the storage gate in the browser, the live dose math on the symptom form, the predicted-vs-observed column on the verdict screen, and the §6.6 honesty split in the report.

M3 reaches forward into M4 in exactly one place, deliberately, and decision #12 justifies it: the report renders the observed sections as explicit absences ("no trial has been recorded"), so M4 fills a section rather than restructuring the document.

Also still out of v1 entirely (§2.2): cost modelling, the numeric solver, the LLM layer, multi-user auth, blinded or multi-subject trials, and consumer timing guidance.

---

## Spec deviations and decisions this plan resolves

Found by tracing §7's table, §10's endpoint list, and §5.2's three unused tables against the M2 code as merged. Implement as described here; flag items 4, 6, 7 and 11 to the spec owner at M3 review.

**1. M3 changes no table and no column — and that is a constraint the design had to earn, not a coincidence.** `db/schema.sql` already creates `variant_suggestion`, `proposal`, and `audit_event`, and `ensure_database` already lists all three in `EXPECTED_TABLES`. What `ensure_database` does *not* do is verify columns: it compares table names against `sqlite_master` and nothing else. So a new column added in M3 would leave every database created under M1 or M2 passing the boot check and then failing on the first `INSERT`, silently, at runtime. Building column-level migration machinery for one field is the wrong trade at this size. **This plan therefore fits every M3 feature into the existing schema**, which forces the one genuinely interesting storage decision in the milestone — see #3.

**2. The patch vocabulary is closed, lives in the engine, and the API never accepts a client-supplied patch.** §7 says each suggestion carries "a machine-applicable `patch_json`". Free-form JSON would make `POST /evaluations/{id}/apply-variant` an unvalidated formulation writer and would make §13's contract test ("applying any auto-variant patch yields a formulation that re-evaluates without error") unwritable, because "any patch" would be unbounded. **`engine/patch.py` defines a closed `PatchOp` enum and a pure `apply_patch(formulation, patch) -> Formulation`**, and the apply endpoint takes a stored `suggestion_id`, not a patch body. The only patches that ever reach `apply_patch` are ones this engine wrote.

**3. Suggestions are stored with the evaluation; the format recommendation is derived from its snapshot.** These look like the same kind of thing and are not. A suggestion is an **action offered** — pressing the button mutates the database — so the patch that gets applied must be the patch the founder was looking at, which means it is frozen into `variant_suggestion` at run time and read back verbatim, exactly as findings are. The format recommendation is a **read-only view**, in the same family as M2's dose cards and GI strip, so it is recomputed from the evaluation's own frozen snapshot on read (M2 decision #5's rule: derived views are pure functions of the snapshot's `EvalContext`). That split is also what keeps decision #1 true: storing the recommendation would need either a new column or an abuse of the suggestion table.

**4. A patch never edits the recipe, and §7's "raise recipe pH" suggestion carries no patch.** §7 offers "raise recipe pH by reducing or replacing the acid ingredient (shown as a recipe change; the founder judges taste)". §12 item 1 says recipe pH is a worst-case minimum over wet ingredients, not a mixing or buffering model. An engine that removed the vinegar and then reported the resulting pH would be reporting the second-lowest ingredient pH as if it were a measurement — a confident wrong number, produced by the tool, about the one quantity the whole product hinges on. **This plan emits that suggestion as a `recipe_note` with `patch = None`, naming the ingredient that set the floor** and telling her to measure the result. To name it, `PhResolution` gains a `driving_food_id` field (Task 2) which R1 also puts in its evidence, so the verdict screen can say *which* ingredient is doing the damage rather than just quoting a number. Flag to the spec owner: §7's table reads as though all its entries are machine-applicable; one of them cannot be, for the reason §12 item 1 already states.

**5. Changing the format must move the enzymes, or the ladder lies.** A `dry_sachet` whose enzyme selections still say `phase: "wet"` is incoherent — R1 and R4 would keep firing on a dry product. `selection.propose_enzymes` already encodes the mapping in a private `_WET_FORMATS`; **this plan extracts it into `conventions.phase_for_format()`** and uses it in both places. `set_format` also normalizes `encapsulated`: `True` for an `encapsulated_in_wet` target (otherwise R6, whose whole subject is the capsule, never fires and the ladder recommends a format that changes nothing), `False` for `dry_sachet` and `dual_chamber`, unchanged for `premixed_wet`. **The format ladder builds each candidate by calling `apply_patch` with that same `set_format` op** — one code path, so the recommendation and the applied result cannot disagree.

**6. The ladder is scanned from the top, not from the current format.** §6.1 R13 asks for "the least-invasive format change (premixed → encapsulated → dual-chamber → dry sachet)". That order runs best-product-experience → most-separated, so the least invasive answer to "what format works" is the earliest position that clears, whether or not the founder is currently below it. A formulation sitting on `dry_sachet` that would also clear as `premixed_wet` gets told so. When no position clears — an R14 uncovered substrate is format-independent, for instance — the recommendation is `None` with a note naming the rules that no format can fix. Flag to the spec owner: reading the ladder as "the next position after the current one" is the other defensible reading, and it would hide a better answer.

**7. Two write paths, two truth labels, and the proposals inbox is the only road to `confirmed`.** §5.4 defines `confirmed` as "verified against a named source, recorded in the paired `*_source` field", which a web form is not. So a direct founder edit in the database editor writes `user_provided` with source `entered by founder` — the same construction `store/foods.create_custom` already uses. An **approved proposal** writes the value with status `confirmed` and the proposal's `source_citation` as the source, which is exactly the flip §2.3 describes for the research track. No HTTP client ever names a label in either path, so M2's `test_no_schema_lets_a_client_choose_a_truth_label` keeps holding. This is also what makes §13 fixture (h2) reachable through the product rather than only through raw SQL: R12's per-enzyme promotion needs `confirmed` temperature fields, and now there is a screen that can produce them. Flag to the spec owner: §5.4 does not say who may write `confirmed`; this plan answers it.

**8. Reset to baseline is per record, and refuses a custom food.** M2 decision #1 said `create_database`'s destructive refresh "becomes the implementation of M3's reset button". Workflow D actually asks for a per-record reset next to each editor, which `create_database` cannot express. **`store/records.reset_enzyme` / `reset_food` re-read `seed/*.json` through `load_seed()` and rewrite that one row**; a separate, explicitly destructive `reset_all` calls `load_reference_data` for the global case. A food whose id starts with `custom_` has no baseline and is refused with a plain-English `ValidationRejection` rather than being silently deleted. `store/` importing `foodbrew.seedload` is new and permitted — M2's layering test forbids `fastapi` and `foodbrew.api` in `store/`, nothing else.

**9. Staleness is a snapshot string comparison that reports what moved.** M2 Task 5 made snapshots byte-stable (sorted keys, no incidental whitespace) so that "has this evaluation's input changed" is a string comparison. M3 spends that: re-hydrate the formulation's context now, re-freeze it, compare with the stored `input_snapshot_json`. Equal means fresh. Unequal means stale — and a field-level diff of the two payloads names the records and fields that moved, so the banner reads "Lactase (fungal, acid) — ph_shelf_stable_min changed" instead of "something changed". **Staleness is computed on the evaluation detail endpoint only**, never on the summary lists: a list of ten summaries would otherwise mean ten full catalogue hydrations for a banner nobody is looking at.

**10. Compare is keyed by evaluation id, capped at six columns, and unions its rows.** §10 lists `GET /compare?ids=…` without saying what the ids are. They are **evaluation** ids: §3 Workflow B's table has "one row per rule + dose + format call + occasion envelope", and all four of those are evaluation outputs, each already frozen and reproducible. Formulation ids would compare things that had never been run. Rows are the **union** across columns, because variants legitimately differ in which enzymes they select — a row absent from one side renders "not in this variant", never dropped, or the table would quietly hide the very difference the founder opened it to see. Six columns is a readability cap and a bound on the query, and the endpoint says so when it refuses a seventh.

**11. The report is rendered by a pure engine function, and the §10 footer is why.** M2's `tests/api/test_contracts.py::test_no_prohibited_word_appears_in_api_source_copy` greps every file under `src/foodbrew/api/` for the prohibited words as **substrings**, not as words. The §10 screen 8 footer — "Formulation decision support. Not a safety, efficacy, or regulatory determination." — contains the substring `safe`. It therefore cannot live in a router module without either failing that test or weakening it, and weakening a language guard to fit a string is the wrong direction. **`engine/report.py` owns the footer and the whole renderer**; `api/routers/export.py` only sets a content type. The new report lint matches on **word boundaries**, the way `tests/test_web_language.py` already does, so "safety" passes and "safe" would not. Flag to the spec owner: the two existing lints disagree on substring-vs-word and now that difference is load-bearing; this plan documents it rather than unifying them, because the api-source lint being stricter costs nothing.

**12. The report renders M4's observed sections as explicit absences.** §10 screen 8 lists "observed results with confidence tiers", which do not exist until M4 writes a `trial_observation`. Omitting the sections would mean M4 restructuring the document; faking them would be worse. They render as "No trial has been recorded for this formulation yet." — which is also the honest thing for a report handed to a food scientist today. Same shape as M2's decision #8.

**13. A suggestion never produces a formulation the engine refuses to evaluate.** §7 offers "drop the protease" (R5) and "drop the structure-degrading enzyme from the blend" (R15). §6.2 R14 raises `ValidationRejection` for a formulation with zero enzymes *and* zero target trigger foods, and `store.formulations._validate` refuses to create one. So a drop suggestion that would empty the selection on a formulation with no trigger foods is **suppressed at generation time**, not caught at apply time — otherwise §13's contract test fails on a suggestion the spec asked for, and the founder gets a 422 from a button the tool offered her.

**14. Suggestions are deduplicated by (type, patch) and ordered deterministically.** R1's third entry, R4's first, and R6's all point at the same dual chamber. The founder should see one button whose description names every rule that asked for it. Dedupe key is the suggestion type plus the canonical JSON of the patch; ordering is by first triggering rule id, then type, then description, so the stored rows and the screen agree run after run and a snapshot-stable evaluation stays snapshot-stable.

**15. Apply-variant is append-only, exactly like evaluate.** It clones the formulation with `parent_formulation_id` set, applies the patch, inserts a new row, and runs a new evaluation. The source formulation and every evaluation of it are untouched, which is §4's rule and M2 decision #5's rule restated for a write that did not exist yet. The clone keeps the same `recipe_id` — patches never touch the recipe (#4) — and round-trips `measured_ph` faithfully, because a formulation's `measured_ph` is only ever `user_provided` or `unconfirmed` (a trial's measured pH lives in `trial_batch` and reaches the engine through `latest_trial_ph`).

**16. The editor writes columns from a closed allowlist.** Column names cannot be parameterized in SQLite, so `store/records.py` interpolates them — from a module-level allowlist keyed by table, with the value always bound as a parameter. Anything not on the list is a `ValidationRejection` before a statement is built. The same allowlist is the type map `store/proposals.py` uses to parse a proposal's `proposed_value` (stored `TEXT`) back into a float, bool, or string, so the two writers cannot disagree about what `ph_min` is.

---

## File structure

```
foodbrew/
├── .dockerignore                       # NEW — the build context currently includes .git, .venv, node_modules
├── Dockerfile                          # runtime image drops the dev extra and the tests copy
├── docker-compose.yml                  # + healthcheck, restart policy
├── Makefile                            # + report, reset-db
├── README.md                           # + the editor, the inbox, and the export
├── src/foodbrew/
│   ├── engine/                         # every new module here is pure
│   │   ├── language.py                 # NEW: PROHIBITED_WORDS + contains_prohibited(), defined once
│   │   ├── conventions.py              #   + phase_for_format(); PhResolution.driving_food_id
│   │   ├── selection.py                #   + enzyme_for_substrate() extracted from propose_enzymes
│   │   ├── patch.py                    # NEW: the closed patch vocabulary and apply_patch()
│   │   ├── format_search.py            # NEW: R13's least-invasive format ladder
│   │   ├── variants.py                 # NEW: the §7 suggestion catalogue
│   │   ├── compare.py                  # NEW: the pure comparison table
│   │   ├── report.py                   # NEW: the report model, the Markdown renderer, the footer
│   │   └── rules/r01_ph_survival.py    #   evidence gains driving_food_id
│   ├── store/
│   │   ├── audit.py                    # NEW: audit_event writes
│   │   ├── variants.py                 # NEW: variant_suggestion persistence
│   │   ├── records.py                  # NEW: editor writes, the column allowlist, reset-to-baseline
│   │   ├── proposals.py                # NEW: the inbox, approve, reject
│   │   ├── snapshot.py                 #   + diff_snapshots()
│   │   ├── evaluations.py              #   + suggestions written on run; + freshness()
│   │   └── formulations.py             #   + clone_with_patch()
│   └── api/
│       ├── schemas.py                  #   + M3 wire models
│       └── routers/
│           ├── evaluations.py          #   + suggestions, format recommendation, staleness
│           ├── variants.py             # NEW: apply-variant and compare
│           ├── records.py              # NEW: enzyme/food editors, resets, audit feed
│           ├── proposals.py            # NEW: the inbox
│           └── export.py               # NEW: GET /export/{id}.md
├── web/
│   ├── e2e/variants.spec.ts            # NEW
│   └── src/
│       ├── api/{client.ts,types.ts}
│       ├── components/
│       │   ├── StaleBanner.tsx         # NEW
│       │   ├── VariantSuggestions.tsx  # NEW
│       │   ├── FormatRecommendation.tsx# NEW
│       │   └── ComparisonTable.tsx     # NEW
│       ├── screens/
│       │   ├── Verdict.tsx             #   + banner, recommendation, suggestions
│       │   ├── Compare.tsx             # NEW
│       │   ├── Database.tsx            # NEW
│       │   └── Report.tsx              # NEW
│       └── styles.css                  #   + the print stylesheet
└── tests/
    ├── engine/test_{language,patch,format_search,variants,compare,report}.py
    ├── store/test_{audit,variant_store,records,proposals,staleness,clone}.py
    └── api/test_{variants,compare,records,proposals,export,contracts_m3}.py
```

**Boundary rules to enforce in review.** M2's two hold unchanged and Task 20 adds a third:

- Nothing under `engine/` imports `foodbrew.store`, `foodbrew.api`, `foodbrew.db`, `fastapi`, or `sqlite3`. `engine/patch.py` and `engine/variants.py` do import `json`, for one purpose — the canonical text of a patch, which is the dedupe key. That is serialization, not I/O; `tests/engine/test_purity.py` is what proves the engine touches no file or socket and it stays green.
- Nothing under `store/` imports `fastapi` or `foodbrew.api`. `store/records.py` importing `foodbrew.seedload` is expected (decision #8), and `db/bootstrap.py` importing `store/rowmap.py` is expected (Task 11) — `rowmap` is the row↔dataclass mapper and imports nothing but `engine.types`, so neither edge creates a cycle.
- **New:** every patch any code path applies was produced by `engine/variants.py` and stored. Task 20 asserts that no request schema carries a `patch`, `patch_json`, or `ops` field, and that no module under `api/` so much as names a `PatchOp` value — a router that did would be building patches by hand.
---

## Task 1: `engine/language.py` — the prohibited-word list, defined once

The list currently exists in two places (`tests/api/test_contracts.py`, `tests/test_web_language.py`) and M3 needs a third reader — the report lint. Three copies of a safety-critical list is two too many.

**Files:**
- Create: `src/foodbrew/engine/language.py`
- Create: `tests/engine/test_language.py`
- Modify: `tests/api/test_contracts.py`, `tests/test_web_language.py`

- [ ] **Step 1: Write the module**

```python
"""Spec §10 — the words this tool never uses about its own output, in one place.

Two lints consume this list and they match differently, on purpose (plan
decision #11):

* `contains_prohibited` matches on WORD BOUNDARIES. "safety" is not "safe", and
  the §10 screen-8 footer says "Not a safety, efficacy, or regulatory
  determination" — a substring match would forbid the disclaimer itself.
* `tests/api/test_contracts.py` matches on SUBSTRINGS across `api/` source. That
  is stricter than this list needs, and nothing under `api/` has any reason to
  contain the letters, so it stays stricter.
"""

from __future__ import annotations

import re

#: Spec §10. Closed list. Adding to it is a product decision, not a refactor.
PROHIBITED_WORDS: tuple[str, ...] = (
    "safe",
    "validated",
    "guaranteed",
    "clinically proven",
    "proven",
    "demonstrated",
)

_PATTERNS = tuple(
    (word, re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)) for word in PROHIBITED_WORDS
)


def contains_prohibited(text: str) -> tuple[str, ...]:
    """Every prohibited word appearing in `text` as a whole word, in list order."""
    return tuple(word for word, pattern in _PATTERNS if pattern.search(text))
```

- [ ] **Step 2: Test it**

```python
"""The lint that guards every other lint."""

import json
import pathlib

import pytest

from foodbrew.engine.language import PROHIBITED_WORDS, contains_prohibited

SEED_DIR = pathlib.Path(__file__).resolve().parents[2] / "seed"


@pytest.mark.parametrize("word", PROHIBITED_WORDS)
def test_each_word_is_caught_on_its_own(word):
    assert contains_prohibited(f"this result is {word} to use") == (word,)


def test_safety_is_not_safe():
    """The §10 footer has to survive its own lint (plan decision #11)."""
    assert contains_prohibited("Not a safety, efficacy, or regulatory determination.") == ()


def test_matching_ignores_case_and_reports_in_list_order():
    found = contains_prohibited("PROVEN and Validated")
    assert found == ("validated", "proven")


def test_clean_text_reports_nothing():
    assert contains_prohibited("flags formulation risks and knowledge gaps") == ()


def test_no_prohibited_word_appears_in_the_shipped_seed():
    """Spec §13 report lint: the report quotes seed notes verbatim, so the seed
    is tool copy and has to comply. Founder free text does not — see Task 7."""
    offenders: list[str] = []
    for path in sorted(SEED_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for word in contains_prohibited(json.dumps(payload)):
            offenders.append(f"{path.name}: {word}")
    assert not offenders, ", ".join(offenders)
```

Run: `.venv/bin/pytest tests/engine/test_language.py -q`
Expected: 10 passed. If the seed test fails, the seed text is the bug, not the lint — fix the note.

- [ ] **Step 3: Point the two existing lints at the shared list**

In `tests/api/test_contracts.py`, replace the local tuple:

```python
from foodbrew.engine.language import PROHIBITED_WORDS as PROHIBITED
```

and delete the `PROHIBITED = (...)` line, keeping every assertion body as it is — that file's substring matching is deliberate.

In `tests/test_web_language.py`, replace `PROHIBITED = (...)` the same way and delete the local `_contains` helper in favour of `contains_prohibited`:

```python
from foodbrew.engine.language import PROHIBITED_WORDS as PROHIBITED
from foodbrew.engine.language import contains_prohibited
...
        if word in contains_prohibited(path.read_text(encoding="utf-8"))
```

Run: `.venv/bin/pytest tests/api/test_contracts.py tests/test_web_language.py -q`
Expected: unchanged results — the same tests, one list.

- [ ] **Step 4: Commit**

```bash
git add src/foodbrew/engine/language.py tests/engine/test_language.py tests/api/test_contracts.py tests/test_web_language.py
git commit -m "refactor: define the prohibited-word list once in the engine"
```

---

## Task 2: Shared conventions the variant engine and the format ladder both need

Three small extractions, each of which exists to stop two callers from drifting (plan decisions #5 and #15). None of them changes a verdict, so every M1 and M2 test must still pass untouched — that is the check at the end of this task.

**Files:**
- Modify: `src/foodbrew/engine/conventions.py`, `src/foodbrew/engine/selection.py`, `src/foodbrew/engine/rules/r01_ph_survival.py`, `src/foodbrew/engine/rules/r06_encapsulation.py`
- Modify: `tests/engine/test_conventions.py`

- [ ] **Step 1: `phase_for_format` and `shelf_stable_floor` in `conventions.py`**

Add to the imports: `Enzyme`, `Format`, `Phase`. Then append:

```python
#: Spec §5.2 — the formats where the enzyme sits in the liquid. Extracted from
#: selection.py's private copy because the format ladder (format_search.py) has
#: to agree with the enzyme proposal about what a format means; a `dry_sachet`
#: whose selections still say `phase: wet` is not a dry sachet (plan decision #5).
WET_FORMATS = frozenset({Format.PREMIXED_WET, Format.ENCAPSULATED_IN_WET})


def phase_for_format(fmt: Format) -> Phase:
    return Phase.WET if fmt in WET_FORMATS else Phase.DRY


@dataclass(frozen=True, slots=True)
class FloorResolution:
    """The pH an enzyme must stay above for shelf duration, and where it came from."""

    value: float | None
    #: "ph_shelf_stable_min" | "fallback" | "unavailable"
    source: str

    @property
    def is_heuristic(self) -> bool:
        return self.source == "fallback"


#: Spec §6.1 R1 — the stated fallback when no supplier has confirmed a
#: shelf-stable floor. An engineering convention that makes the rule testable,
#: NOT a scientific claim; every finding that uses it says so (spec §12 item 3).
FALLBACK_MARGIN_PH = 1.0


def shelf_stable_floor(enzyme: Enzyme) -> FloorResolution:
    """Spec §6.1 R1's floor, resolved once for R1, R6, and the variant engine."""
    if enzyme.ph_shelf_stable_min.usable:
        return FloorResolution(float(enzyme.ph_shelf_stable_min.value), "ph_shelf_stable_min")
    if enzyme.ph_min.usable:
        return FloorResolution(float(enzyme.ph_min.value) + FALLBACK_MARGIN_PH, "fallback")
    return FloorResolution(None, "unavailable")
```

- [ ] **Step 2: `PhResolution` learns which ingredient set the floor**

Spec §12 item 1 says the recipe pH is the minimum over wet ingredients. The rule reports the number; the §7 suggestion has to report the *ingredient* (plan decision #4). Add the field and set it in the one branch that computes a minimum:

```python
@dataclass(frozen=True, slots=True)
class PhResolution:
    """Outcome of spec §6.7's measured-pH resolution order."""

    value: float | None
    status: TruthLabel
    origin: str
    blocking_field: str = ""
    #: The wet ingredient whose pH became the estimate. Empty unless the
    #: fallback was used — a measured pH has no driving ingredient.
    driving_food_id: str = ""
```

and in `resolve_recipe_ph`, collect `(ph, food_id)` pairs rather than bare floats:

```python
    wet_phs: list[tuple[float, str]] = []
    ...
        wet_phs.append((float(food.ph.value), food.id))

    if not wet_phs:
        return PhResolution(
            None, TruthLabel.UNCONFIRMED, "wet_ingredient_fallback",
            blocking_field="no wet ingredient in the recipe",
        )

    lowest, driver = min(wet_phs)
    return PhResolution(
        value=lowest, status=TruthLabel.CALCULATED, origin="wet_ingredient_fallback",
        driving_food_id=driver,
    )
```

`min` on the tuples ties-break by food id, which makes the driver deterministic when two ingredients share the lowest pH — that determinism is load-bearing, because the driver reaches a stored suggestion.

- [ ] **Step 3: Point `selection.py`, `r01`, and `r06` at the shared helpers**

In `selection.py`, delete `_WET_FORMATS` and use the shared function:

```python
from foodbrew.engine.conventions import phase_for_format
...
    phase = phase_for_format(format)
```

In `r01_ph_survival.py`, delete the local `FALLBACK_MARGIN_PH` and replace the floor branch:

```python
from foodbrew.engine.conventions import FALLBACK_MARGIN_PH, resolve_recipe_ph, shelf_stable_floor
...
        floor_resolution = shelf_stable_floor(enzyme)
        floor = floor_resolution.value
        floor_source = floor_resolution.source
        heuristic_note = (
            " This uses the stated margin heuristic (ph_min + "
            f"{FALLBACK_MARGIN_PH}) because no shelf-stable floor is confirmed — "
            "supplier confirmation required."
            if floor_resolution.is_heuristic
            else ""
        )
```

`r01` reaches this code only after checking `enzyme.ph_min.usable`, so `floor` is never `None` here and the existing branches below are unchanged.

Then switch `r06_encapsulation.py`. **Delete its `from foodbrew.engine.rules.r01_ph_survival import FALLBACK_MARGIN_PH` line** — the new `_floor` does not reference the constant, and ruff's `F` rule set fails an unused import, which would break Step 5's clean run:

```python
from foodbrew.engine.conventions import resolve_recipe_ph, shelf_stable_floor
...
def _floor(enzyme) -> tuple[float | None, str]:
    resolution = shelf_stable_floor(enzyme)
    return resolution.value, resolution.source
```

That also removes the only cross-rule import in the engine: `r06` no longer reaches into `r01` for a constant, and both read the shared convention instead.

Add `driving_food_id` to R1's evidence dict, after `ph_status`:

```python
            "driving_food_id": ph.driving_food_id,
```

No test asserts an exact evidence dict — `grep -rn "evidence ==" tests/` returns nothing — so adding a key is additive. It does not change a verdict, so `ENGINE_VERSION` stays `1.0.0`: §4 ties the version to results, and `foodbrew/__init__.py` says "bumped manually whenever rule logic changes in a way that alters verdicts".

- [ ] **Step 4: Test the new conventions**

Append to `tests/engine/test_conventions.py`:

```python
import dataclasses

from foodbrew.engine.conventions import (
    FALLBACK_MARGIN_PH,
    phase_for_format,
    resolve_recipe_ph,
    shelf_stable_floor,
)
from foodbrew.engine.types import Format, Phase, Tracked, TruthLabel


def test_wet_formats_put_the_enzyme_in_the_liquid():
    assert phase_for_format(Format.PREMIXED_WET) is Phase.WET
    assert phase_for_format(Format.ENCAPSULATED_IN_WET) is Phase.WET
    assert phase_for_format(Format.DUAL_CHAMBER) is Phase.DRY
    assert phase_for_format(Format.DRY_SACHET) is Phase.DRY


def test_a_confirmed_shelf_floor_wins_over_the_heuristic(seed):
    enzyme = dataclasses.replace(
        seed.enzymes["lactase_fungal_acid"],
        ph_shelf_stable_min=Tracked(3.2, TruthLabel.CONFIRMED, "supplier spec"),
    )
    resolution = shelf_stable_floor(enzyme)
    assert (resolution.value, resolution.source) == (3.2, "ph_shelf_stable_min")
    assert not resolution.is_heuristic


def test_the_shipped_seed_falls_back_to_the_stated_margin(seed):
    """Every seeded ph_shelf_stable_min is unconfirmed (spec §9.1)."""
    enzyme = seed.enzymes["lactase_fungal_acid"]
    resolution = shelf_stable_floor(enzyme)
    assert resolution.is_heuristic
    assert resolution.value == float(enzyme.ph_min.value) + FALLBACK_MARGIN_PH


def test_an_enzyme_with_no_ph_at_all_has_no_floor(seed):
    enzyme = dataclasses.replace(
        seed.enzymes["lactase_fungal_acid"],
        ph_min=Tracked(None, TruthLabel.UNCONFIRMED),
        ph_shelf_stable_min=Tracked(None, TruthLabel.UNCONFIRMED),
    )
    assert shelf_stable_floor(enzyme) == FloorResolution(None, "unavailable")


def test_the_fallback_names_the_ingredient_that_set_the_pH(make_ctx, seed):
    foods = dict(seed.foods)
    for food_id, ph, water in (("olive_oil", 6.0, 0.0), ("white_vinegar", 2.6, 95.0),
                               ("water", 7.0, 100.0)):
        foods[food_id] = dataclasses.replace(
            foods[food_id],
            ph=Tracked(ph, TruthLabel.USER_PROVIDED, "fixture"),
            water_content_pct=Tracked(water, TruthLabel.USER_PROVIDED, "fixture"),
        )
    ctx = make_ctx(
        recipe=(("olive_oil", 100.0), ("white_vinegar", 50.0), ("water", 20.0)), foods=foods
    )
    resolution = resolve_recipe_ph(ctx.formulation, foods, None)
    assert resolution.value == 2.6
    assert resolution.driving_food_id == "white_vinegar"


def test_a_measured_pH_has_no_driving_ingredient(make_ctx):
    ctx = make_ctx(measured_ph=4.4)
    resolution = resolve_recipe_ph(ctx.formulation, ctx.foods, None)
    assert resolution.origin == "formulation.measured_ph"
    assert resolution.driving_food_id == ""
```

Add `FloorResolution` to the import line.

- [ ] **Step 5: Prove nothing moved**

Run: `.venv/bin/pytest -q && .venv/bin/ruff check src tests`
Expected: every pre-existing test still passes. This task is a refactor plus one additive evidence key; a single changed verdict here means the extraction was not faithful.

- [ ] **Step 6: Commit**

```bash
git add src/foodbrew/engine tests/engine/test_conventions.py
git commit -m "refactor(engine): share the format-phase mapping and the shelf-stable floor"
```

---

## Task 3: `engine/patch.py` — the closed patch vocabulary

Everything §7 can apply, and nothing else (plan decision #2). Pure: a patch is data, applying it is a function from one `Formulation` to another.

**Files:**
- Create: `src/foodbrew/engine/patch.py`
- Create: `tests/engine/test_patch.py`

- [ ] **Step 1: Write the module**

```python
"""The closed patch vocabulary (spec §7). Pure — applying a patch returns a new
Formulation and touches nothing else.

A patch is `{"ops": [{"op": "...", ...}, ...]}`. The list is closed and every
op validates its own arguments, which is what makes spec §13's contract test
("applying any auto-variant patch yields a formulation that re-evaluates
without error") a statement about a finite set rather than about arbitrary
JSON. Nothing outside `engine/variants.py` ever constructs one, and the API
applies a *stored* suggestion by id rather than accepting a patch body — so an
HTTP client cannot reach this module with input of its own (plan decision #2).

A patch never touches the recipe. Spec §12 item 1: recipe pH is a worst-case
minimum over wet ingredients, not a mixing model, so an engine that removed an
acid ingredient could not honestly report the resulting pH. §7's "raise recipe
pH" entry is therefore a note, not a patch (plan decision #4).
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping, Sequence
from enum import StrEnum
from typing import Any

from foodbrew.engine.conventions import phase_for_format
from foodbrew.engine.rules.r14_substrate_coverage import ValidationRejection
from foodbrew.engine.types import (
    DwellProfile,
    Format,
    Formulation,
    Phase,
    SelectedEnzyme,
)


class PatchOp(StrEnum):
    """Spec §7's fix catalogue, expressed as the smallest closed set that covers it."""

    SET_FORMAT = "set_format"
    SET_DWELL_PROFILE = "set_dwell_profile"
    SET_ENZYME_ADDITION_INDEX = "set_enzyme_addition_index"
    SET_ENZYME_PHASE = "set_enzyme_phase"
    SET_ENZYME_ENCAPSULATED = "set_enzyme_encapsulated"
    SET_ENZYME_DOSE = "set_enzyme_dose"
    ADD_ENZYME = "add_enzyme"
    REMOVE_ENZYME = "remove_enzyme"
    SWAP_ENZYME = "swap_enzyme"
    REMOVE_TRIGGER_FOOD = "remove_trigger_food"


#: Spec §6.1 R6 — what each format implies about encapsulation. A format absent
#: from this map leaves the flag alone: `premixed_wet` is the format where the
#: founder's own choice to encapsulate is meaningful on its own.
_ENCAPSULATION_FOR_FORMAT: Mapping[Format, bool] = {
    Format.ENCAPSULATED_IN_WET: True,
    Format.DUAL_CHAMBER: False,
    Format.DRY_SACHET: False,
}


def set_format(fmt: Format) -> dict:
    """The canonical format-change patch. `format_search` builds its ladder
    candidates with this, so a recommendation and its applied result cannot
    disagree (plan decision #5)."""
    return {"ops": [{"op": PatchOp.SET_FORMAT.value, "value": fmt.value}]}


def canonical(patch: Mapping[str, Any] | None) -> str:
    """Stable text for a patch, used as the dedupe key (plan decision #14)."""
    if patch is None:
        return ""
    return json.dumps(patch, sort_keys=True, separators=(",", ":"))


def _selection_index(formulation: Formulation, enzyme_id: str) -> int:
    for index, selected in enumerate(formulation.enzymes):
        if selected.enzyme_id == enzyme_id:
            return index
    raise ValidationRejection(f"'{enzyme_id}' is not selected on this formulation.")


def _replace_selection(formulation: Formulation, index: int, **changes) -> Formulation:
    enzymes = list(formulation.enzymes)
    enzymes[index] = dataclasses.replace(enzymes[index], **changes)
    return dataclasses.replace(formulation, enzymes=tuple(enzymes))


def _op_set_format(formulation: Formulation, raw: Mapping) -> Formulation:
    try:
        fmt = Format(raw["value"])
    except (KeyError, ValueError) as exc:
        raise ValidationRejection(f"Unknown format '{raw.get('value')}'.") from exc

    phase = phase_for_format(fmt)
    implied = _ENCAPSULATION_FOR_FORMAT.get(fmt)
    enzymes = tuple(
        dataclasses.replace(
            selected,
            phase=phase,
            encapsulated=selected.encapsulated if implied is None else implied,
        )
        for selected in formulation.enzymes
    )
    return dataclasses.replace(formulation, format=fmt, enzymes=enzymes)


def _op_set_dwell_profile(formulation: Formulation, raw: Mapping) -> Formulation:
    value = raw.get("value")
    if value is None:
        return dataclasses.replace(formulation, dwell_profile=None)
    try:
        return dataclasses.replace(formulation, dwell_profile=DwellProfile(value))
    except ValueError as exc:
        raise ValidationRejection(f"Unknown use occasion '{value}'.") from exc


def _op_set_enzyme_addition_index(formulation: Formulation, raw: Mapping) -> Formulation:
    value = raw.get("value")
    if value is None:
        raise ValidationRejection("An enzyme addition point is required.")
    return dataclasses.replace(formulation, enzyme_addition_index=int(value))


def _op_set_enzyme_phase(formulation: Formulation, raw: Mapping) -> Formulation:
    index = _selection_index(formulation, raw["enzyme_id"])
    try:
        phase = Phase(raw["value"])
    except (KeyError, ValueError) as exc:
        raise ValidationRejection(f"Unknown phase '{raw.get('value')}'.") from exc
    return _replace_selection(formulation, index, phase=phase)


def _op_set_enzyme_encapsulated(formulation: Formulation, raw: Mapping) -> Formulation:
    index = _selection_index(formulation, raw["enzyme_id"])
    return _replace_selection(formulation, index, encapsulated=bool(raw["value"]))


def _op_set_enzyme_dose(formulation: Formulation, raw: Mapping) -> Formulation:
    index = _selection_index(formulation, raw["enzyme_id"])
    value = raw.get("value")
    dose = None if value is None else float(value)
    if dose is not None and dose < 0:
        raise ValidationRejection("A dose cannot be negative.")
    return _replace_selection(formulation, index, dose=dose)


def _op_add_enzyme(formulation: Formulation, raw: Mapping) -> Formulation:
    enzyme_id = raw["enzyme_id"]
    if any(s.enzyme_id == enzyme_id for s in formulation.enzymes):
        return formulation
    dose = raw.get("dose")
    addition = SelectedEnzyme(
        enzyme_id=enzyme_id,
        dose=None if dose is None else float(dose),
        phase=phase_for_format(formulation.format),
        encapsulated=_ENCAPSULATION_FOR_FORMAT.get(formulation.format, False),
        source_choice=raw.get("source_choice", ""),
    )
    return dataclasses.replace(formulation, enzymes=(*formulation.enzymes, addition))


def _op_remove_enzyme(formulation: Formulation, raw: Mapping) -> Formulation:
    enzyme_id = raw["enzyme_id"]
    remaining = tuple(s for s in formulation.enzymes if s.enzyme_id != enzyme_id)
    if len(remaining) == len(formulation.enzymes):
        raise ValidationRejection(f"'{enzyme_id}' is not selected on this formulation.")
    return dataclasses.replace(formulation, enzymes=remaining)


def _op_swap_enzyme(formulation: Formulation, raw: Mapping) -> Formulation:
    index = _selection_index(formulation, raw["enzyme_id"])
    replacement = raw["replacement_id"]
    if any(s.enzyme_id == replacement for s in formulation.enzymes):
        return _op_remove_enzyme(formulation, {"enzyme_id": raw["enzyme_id"]})
    dose = raw.get("dose")
    return _replace_selection(
        formulation,
        index,
        enzyme_id=replacement,
        dose=None if dose is None else float(dose),
        source_choice=raw.get("source_choice", ""),
    )


def _op_remove_trigger_food(formulation: Formulation, raw: Mapping) -> Formulation:
    food_id = raw["food_id"]
    remaining = tuple(f for f in formulation.target_trigger_food_ids if f != food_id)
    return dataclasses.replace(formulation, target_trigger_food_ids=remaining)


_HANDLERS = {
    PatchOp.SET_FORMAT: _op_set_format,
    PatchOp.SET_DWELL_PROFILE: _op_set_dwell_profile,
    PatchOp.SET_ENZYME_ADDITION_INDEX: _op_set_enzyme_addition_index,
    PatchOp.SET_ENZYME_PHASE: _op_set_enzyme_phase,
    PatchOp.SET_ENZYME_ENCAPSULATED: _op_set_enzyme_encapsulated,
    PatchOp.SET_ENZYME_DOSE: _op_set_enzyme_dose,
    PatchOp.ADD_ENZYME: _op_add_enzyme,
    PatchOp.REMOVE_ENZYME: _op_remove_enzyme,
    PatchOp.SWAP_ENZYME: _op_swap_enzyme,
    PatchOp.REMOVE_TRIGGER_FOOD: _op_remove_trigger_food,
}


def apply_patch(formulation: Formulation, patch: Mapping[str, Any] | None) -> Formulation:
    """Apply every op in order and return the result. Never mutates the input."""
    if patch is None:
        raise ValidationRejection("This suggestion is a note — there is nothing to apply.")

    ops = patch.get("ops")
    if not isinstance(ops, Sequence) or isinstance(ops, str) or not ops:
        raise ValidationRejection("This suggestion carries no change to apply.")

    result = formulation
    for raw in ops:
        if not isinstance(raw, Mapping) or "op" not in raw:
            raise ValidationRejection("Malformed change in this suggestion.")
        try:
            op = PatchOp(raw["op"])
        except ValueError as exc:
            raise ValidationRejection(f"Unknown change '{raw['op']}'.") from exc
        try:
            result = _HANDLERS[op](result, raw)
        except KeyError as exc:
            raise ValidationRejection(f"'{op.value}' is missing {exc}.") from exc
    return result
```

- [ ] **Step 2: Test it**

`tests/engine/test_patch.py`:

```python
"""The patch vocabulary is closed, so its tests can be exhaustive."""

import pytest

from foodbrew.engine import ValidationRejection
from foodbrew.engine.patch import PatchOp, apply_patch, canonical, set_format
from foodbrew.engine.types import DwellProfile, Format, Phase


def test_every_op_has_a_handler():
    """A new member of the enum with no handler would raise KeyError at runtime."""
    from foodbrew.engine.patch import _HANDLERS

    assert set(_HANDLERS) == set(PatchOp)


def test_setting_a_dry_format_moves_every_enzyme_out_of_the_liquid(make_ctx):
    form = make_ctx(fmt=Format.PREMIXED_WET).formulation
    patched = apply_patch(form, set_format(Format.DRY_SACHET))
    assert patched.format is Format.DRY_SACHET
    assert all(s.phase is Phase.DRY for s in patched.enzymes)
    assert all(not s.encapsulated for s in patched.enzymes)


def test_setting_encapsulated_in_wet_actually_encapsulates(make_ctx):
    """Otherwise R6, whose subject is the capsule, never fires (plan decision #5)."""
    form = make_ctx(fmt=Format.PREMIXED_WET).formulation
    patched = apply_patch(form, set_format(Format.ENCAPSULATED_IN_WET))
    assert all(s.phase is Phase.WET and s.encapsulated for s in patched.enzymes)


def test_premixed_wet_leaves_the_encapsulation_choice_alone(make_ctx):
    form = make_ctx(
        fmt=Format.DRY_SACHET,
        enzymes=(("lactase_fungal_acid", 9000.0, Phase.DRY, True),),
    )
    patched = apply_patch(form.formulation, set_format(Format.PREMIXED_WET))
    assert patched.enzymes[0].encapsulated is True


def test_applying_a_patch_does_not_mutate_the_original(make_ctx):
    form = make_ctx(fmt=Format.PREMIXED_WET).formulation
    apply_patch(form, set_format(Format.DRY_SACHET))
    assert form.format is Format.PREMIXED_WET
    assert form.enzymes[0].phase is Phase.WET


def test_ops_apply_in_order(make_ctx):
    form = make_ctx(fmt=Format.PREMIXED_WET).formulation
    patched = apply_patch(form, {"ops": [
        {"op": "set_format", "value": "dual_chamber"},
        {"op": "set_enzyme_phase", "enzyme_id": "lactase_fungal_acid", "value": "wet"},
    ]})
    assert patched.format is Format.DUAL_CHAMBER
    assert patched.enzymes[0].phase is Phase.WET


def test_add_enzyme_takes_the_phase_the_format_implies(make_ctx):
    form = make_ctx(fmt=Format.PREMIXED_WET).formulation
    patched = apply_patch(form, {"ops": [
        {"op": "add_enzyme", "enzyme_id": "alpha_galactosidase", "dose": 300.0},
    ]})
    added = patched.enzymes[-1]
    assert (added.enzyme_id, added.dose, added.phase) == (
        "alpha_galactosidase", 300.0, Phase.WET
    )


def test_add_enzyme_is_idempotent(make_ctx):
    form = make_ctx().formulation
    patched = apply_patch(form, {"ops": [
        {"op": "add_enzyme", "enzyme_id": "lactase_fungal_acid"},
    ]})
    assert len(patched.enzymes) == len(form.enzymes)


def test_swap_replaces_in_place_and_keeps_the_position(make_ctx):
    form = make_ctx(enzymes=(
        ("lactase_fungal_acid", 9000.0, Phase.WET),
        ("alpha_galactosidase", 300.0, Phase.WET),
    )).formulation
    patched = apply_patch(form, {"ops": [{
        "op": "swap_enzyme", "enzyme_id": "lactase_fungal_acid",
        "replacement_id": "lactase_yeast_neutral", "dose": 9000.0,
    }]})
    assert [s.enzyme_id for s in patched.enzymes] == [
        "lactase_yeast_neutral", "alpha_galactosidase"
    ]


def test_swapping_onto_an_enzyme_already_selected_just_removes_the_old_one(make_ctx):
    form = make_ctx(enzymes=(
        ("lactase_fungal_acid", 9000.0, Phase.WET),
        ("lactase_yeast_neutral", 9000.0, Phase.WET),
    )).formulation
    patched = apply_patch(form, {"ops": [{
        "op": "swap_enzyme", "enzyme_id": "lactase_fungal_acid",
        "replacement_id": "lactase_yeast_neutral",
    }]})
    assert [s.enzyme_id for s in patched.enzymes] == ["lactase_yeast_neutral"]


def test_dwell_profile_round_trips_including_back_to_undeclared(make_ctx):
    form = make_ctx().formulation
    declared = apply_patch(form, {"ops": [
        {"op": "set_dwell_profile", "value": "immediate"},
    ]})
    assert declared.dwell_profile is DwellProfile.IMMEDIATE
    assert apply_patch(declared, {"ops": [
        {"op": "set_dwell_profile", "value": None},
    ]}).dwell_profile is None


def test_removing_a_trigger_food_leaves_the_rest(make_ctx):
    form = make_ctx(trigger_foods=("milk", "black_beans")).formulation
    patched = apply_patch(form, {"ops": [
        {"op": "remove_trigger_food", "food_id": "milk"},
    ]})
    assert patched.target_trigger_food_ids == ("black_beans",)


@pytest.mark.parametrize("patch, fragment", [
    (None, "nothing to apply"),
    ({}, "no change"),
    ({"ops": []}, "no change"),
    ({"ops": "set_format"}, "no change"),
    ({"ops": [{"value": "dry_sachet"}]}, "Malformed"),
    ({"ops": [{"op": "drop_the_database"}]}, "Unknown change"),
    ({"ops": [{"op": "set_format", "value": "sachet"}]}, "Unknown format"),
    ({"ops": [{"op": "remove_enzyme", "enzyme_id": "amylase"}]}, "not selected"),
    ({"ops": [{"op": "set_enzyme_dose", "enzyme_id": "lactase_fungal_acid", "value": -1}]},
     "cannot be negative"),
])
def test_malformed_patches_are_refused_in_plain_english(make_ctx, patch, fragment):
    form = make_ctx().formulation
    with pytest.raises(ValidationRejection) as excinfo:
        apply_patch(form, patch)
    assert fragment in str(excinfo.value)


def test_canonical_is_stable_across_key_order():
    a = {"ops": [{"op": "set_format", "value": "dry_sachet"}]}
    b = {"ops": [{"value": "dry_sachet", "op": "set_format"}]}
    assert canonical(a) == canonical(b)
    assert canonical(None) == ""
```

Run: `.venv/bin/pytest tests/engine/test_patch.py -q`
Expected: 20 passed.

- [ ] **Step 3: Commit**

```bash
git add src/foodbrew/engine/patch.py tests/engine/test_patch.py
git commit -m "feat(engine): add the closed patch vocabulary for auto-variants"
```

---

## Task 4: `engine/format_search.py` — R13's least-invasive format

Deferred out of M2 by that plan's decision #6, which called it "a *search* — re-running R1–R7, R11, R12, R14, R15 under each candidate format". It is built here because it needs Task 3's patch to build its candidates.

**Files:**
- Create: `src/foodbrew/engine/format_search.py`
- Create: `tests/engine/test_format_search.py`

- [ ] **Step 1: Write the module**

```python
"""Spec §6.1 R13 — the format recommendation. Pure.

R13 is not an independent test; it is the aggregation (flags.py) plus this
search. The search re-runs the whole engine under each format on the ladder and
reports the earliest position that produces no RED among the rules §6.1 names.

Two things make the answer trustworthy rather than plausible:

* Each candidate is built by `patch.apply_patch(..., set_format(f))` — the same
  function the apply-variant button calls — so what the recommendation promises
  and what applying it produces are the same formulation (plan decision #5).
* The ladder is scanned from the top, not from the current position, because
  it runs best-product-experience → most-separated and the least invasive
  answer to "what format works" is the earliest one that does (decision #6).
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from foodbrew.engine.evaluate import evaluate
from foodbrew.engine.patch import apply_patch, set_format
from foodbrew.engine.types import EvalContext, Format, Verdict

#: Spec §6.1 R13, in the order the spec writes it: premixed → encapsulated →
#: dual-chamber → dry sachet.
FORMAT_LADDER: tuple[Format, ...] = (
    Format.PREMIXED_WET,
    Format.ENCAPSULATED_IN_WET,
    Format.DUAL_CHAMBER,
    Format.DRY_SACHET,
)

#: Spec §6.1 R13 — "re-running R1–R7, R11, R12, R14, R15 yields no RED".
#: R8, R9, R10 and R16 are advisory and excluded by name rather than by their
#: advisory flag, so the set stays legible against the spec sentence.
LADDER_RULE_IDS = frozenset(
    {"R1", "R2", "R3", "R4", "R5", "R6", "R7", "R11", "R12", "R14", "R15"}
)

#: Plain-English format names, so the UI hardcodes no copy (§10).
FORMAT_TITLES = {
    Format.PREMIXED_WET: "Premixed wet",
    Format.ENCAPSULATED_IN_WET: "Encapsulated in the wet",
    Format.DUAL_CHAMBER: "Dual chamber",
    Format.DRY_SACHET: "Dry sachet",
}


@dataclass(frozen=True, slots=True)
class FormatOption:
    format: Format
    title: str
    is_current: bool
    clears: bool
    #: Rule ids that RED under this format, sorted.
    reds: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FormatRecommendation:
    current: Format
    #: None when no position on the ladder clears every blocker.
    recommended: Format | None
    options: tuple[FormatOption, ...]
    #: Rules that RED under every format — a format change cannot fix these.
    unfixable: tuple[str, ...]
    message: str


def reds_under(ctx: EvalContext, fmt: Format) -> tuple[str, ...]:
    """Which of §6.1 R13's rules RED when this formulation is sold as `fmt`."""
    candidate = apply_patch(ctx.formulation, set_format(fmt))
    result = evaluate(dataclasses.replace(ctx, formulation=candidate))
    return tuple(
        sorted(
            {
                finding.rule_id
                for finding in result.findings
                if finding.verdict is Verdict.RED and finding.rule_id in LADDER_RULE_IDS
            }
        )
    )


def recommend_format(ctx: EvalContext) -> FormatRecommendation:
    current = ctx.formulation.format
    options = tuple(
        FormatOption(
            format=fmt,
            title=FORMAT_TITLES[fmt],
            is_current=fmt is current,
            clears=not reds,
            reds=reds,
        )
        for fmt, reds in ((fmt, reds_under(ctx, fmt)) for fmt in FORMAT_LADDER)
    )

    unfixable = tuple(sorted(set.intersection(*(set(o.reds) for o in options))))
    recommended = next((o.format for o in options if o.clears), None)

    if recommended is None:
        message = (
            "No format clears every blocker: "
            + ", ".join(unfixable)
            + " REDs however this is packaged, so the fix is in the formulation itself."
        )
    elif recommended is current:
        message = (
            f"{FORMAT_TITLES[current]} is already the least separated format that "
            f"clears these rules."
        )
    else:
        message = (
            f"{FORMAT_TITLES[recommended]} is the least separated format that clears "
            f"these rules. As {FORMAT_TITLES[current].lower()} the blockers are "
            + ", ".join(next(o.reds for o in options if o.is_current))
            + "."
        )

    return FormatRecommendation(
        current=current,
        recommended=recommended,
        options=options,
        unfixable=unfixable,
        message=message,
    )
```

Note the `set.intersection(*(...))` call is safe because `FORMAT_LADDER` is never empty.

- [ ] **Step 2: Test it against the KB §4m ladder**

`tests/engine/test_format_search.py`:

```python
"""Spec §6.1 R13. The KB §4m tiers are golden fixtures (a)/(b)/(c); this asserts
the ladder that walks between them.
"""

import dataclasses

from foodbrew.engine.format_search import (
    FORMAT_LADDER,
    LADDER_RULE_IDS,
    recommend_format,
    reds_under,
)
from foodbrew.engine.types import Format, Phase, Tracked, TruthLabel


def test_the_ladder_runs_from_least_to_most_separated():
    assert FORMAT_LADDER == (
        Format.PREMIXED_WET,
        Format.ENCAPSULATED_IN_WET,
        Format.DUAL_CHAMBER,
        Format.DRY_SACHET,
    )


def test_advisory_rules_are_not_on_the_ladder():
    assert LADDER_RULE_IDS.isdisjoint({"R8", "R9", "R10", "R13", "R16"})


def test_an_acidic_vinaigrette_is_told_to_separate(make_ctx):
    """Golden fixture (a) as premixed wet REDs through R1; the ladder finds the
    first position where it does not."""
    ctx = make_ctx(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    recommendation = recommend_format(ctx)
    assert "R1" in next(o.reds for o in recommendation.options if o.is_current)
    assert recommendation.recommended in (Format.DUAL_CHAMBER, Format.DRY_SACHET)
    assert recommendation.unfixable == ()


def test_the_recommendation_is_the_earliest_clearing_position(make_ctx):
    ctx = make_ctx(fmt=Format.DRY_SACHET, measured_ph=3.0, trigger_foods=("milk",))
    recommendation = recommend_format(ctx)
    clearing = [o.format for o in recommendation.options if o.clears]
    assert recommendation.recommended == clearing[0]


def test_a_formulation_that_already_clears_is_told_so(make_ctx):
    ctx = make_ctx(
        fmt=Format.DRY_SACHET,
        enzymes=(("lactase_fungal_acid", 9000.0, Phase.DRY),),
        trigger_foods=("milk",),
        process_steps=(),
    )
    recommendation = recommend_format(ctx)
    assert recommendation.recommended is not None
    assert "least separated format" in recommendation.message


def test_an_uncovered_substrate_is_reported_as_unfixable_by_format(make_ctx):
    """R14 does not care how the product is packaged (plan decision #6)."""
    ctx = make_ctx(enzymes=(), trigger_foods=("black_beans",), measured_ph=6.0)
    recommendation = recommend_format(ctx)
    assert recommendation.recommended is None
    assert recommendation.unfixable == ("R14",)
    assert "however this is packaged" in recommendation.message


def test_the_candidate_moves_the_enzymes_not_just_the_label(make_ctx):
    """A dry sachet whose selections still say wet would keep REDing on R1."""
    ctx = make_ctx(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    assert "R1" in reds_under(ctx, Format.PREMIXED_WET)
    assert "R1" not in reds_under(ctx, Format.DRY_SACHET)


def test_encapsulated_in_wet_is_evaluated_with_the_capsule_on(make_ctx):
    """R6 only speaks when an enzyme is encapsulated; the ladder has to turn it
    on or the position would be indistinguishable from premixed wet."""
    ctx = make_ctx(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    assert "R6" in reds_under(ctx, Format.ENCAPSULATED_IN_WET)


def test_the_search_does_not_mutate_the_context(make_ctx):
    ctx = make_ctx(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    recommend_format(ctx)
    assert ctx.formulation.format is Format.PREMIXED_WET
    assert ctx.formulation.enzymes[0].phase is Phase.WET


def test_a_confirmed_shelf_floor_moves_the_recommendation_up_the_ladder(make_ctx, seed):
    """The answer §15 question 1 exists to collect changes the format call."""
    catalog = dict(seed.enzymes)
    catalog["lactase_fungal_acid"] = dataclasses.replace(
        catalog["lactase_fungal_acid"],
        ph_shelf_stable_min=Tracked(2.5, TruthLabel.CONFIRMED, "supplier spec"),
    )
    ctx = make_ctx(
        fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",),
        enzyme_catalog=catalog,
    )
    assert recommend_format(ctx).recommended is Format.PREMIXED_WET
```

Run: `.venv/bin/pytest tests/engine/test_format_search.py -q`
Expected: 10 passed. If `test_an_acidic_vinaigrette_is_told_to_separate` lands on `ENCAPSULATED_IN_WET`, that is a bug in the candidate builder — §6.1 R6 says a capsule cannot hold back a pH that denatures on contact, so R6 must RED there.

- [ ] **Step 3: Commit**

```bash
git add src/foodbrew/engine/format_search.py tests/engine/test_format_search.py
git commit -m "feat(engine): add R13's least-invasive format recommendation"
```
---

## Task 5: `engine/variants.py` — the §7 suggestion catalogue

The centre of the milestone. Every row of §7's table, plus the three constraints the spec puts on it: a suggestion is never presented as pre-cleared (its own flags are shown once it is applied and re-run), a suggestion that cannot honestly be machine-applied carries no patch (decision #4), and a suggestion never produces a formulation the engine refuses to evaluate (decision #13).

**Files:**
- Modify: `src/foodbrew/engine/selection.py`
- Create: `src/foodbrew/engine/variants.py`
- Create: `tests/engine/test_variants.py`

- [ ] **Step 1: Extract the per-substrate choice out of `selection.py`**

`propose_enzymes` already contains the "best enzyme for this substrate" policy, buried in a sort and a `setdefault`. R14's suggestion needs the same policy for one substrate, and two copies of a selection policy is how two screens start disagreeing about which lactase the tool prefers. Replace the body:

```python
def enzyme_for_substrate(substrate_id: str, enzymes: Mapping[str, Enzyme]) -> Enzyme | None:
    """The catalogue's preferred enzyme for one substrate, or None if it has none.

    Priority first, then id, so the choice is stable rather than dictionary-ordered.
    `propose_enzymes` and M3's R14 auto-variant both go through here.
    """
    candidates = [e for e in enzymes.values() if e.substrate_id == substrate_id]
    if not candidates:
        return None
    candidates.sort(key=lambda e: (_PRIORITY_ORDER.get(e.priority, 99), e.id))
    return candidates[0]


def proposed_dose(enzyme: Enzyme) -> float | None:
    """The evidence threshold if there is one, else the benchmark floor, else nothing.

    A dose is never invented: with neither field usable the selection carries
    `dose=None`, and R7 returns cannot_assess naming the missing dose rather
    than the engine guessing a number the founder would then trust.
    """
    if enzyme.dose_evidence_threshold.usable:
        return float(enzyme.dose_evidence_threshold.value)
    if enzyme.dose_min.usable:
        return float(enzyme.dose_min.value)
    return None


def propose_enzymes(
    *,
    trigger_food_ids: Iterable[str],
    format: Format,
    foods: Mapping[str, Food],
    substrates: Mapping[str, Substrate],
    enzymes: Mapping[str, Enzyme],
) -> tuple[SelectedEnzyme, ...]:
    """Enzymes covering the substrates the selected trigger foods carry."""
    wanted: set[str] = set()
    for food_id in trigger_food_ids:
        food = foods.get(food_id)
        if food is None:
            continue
        for substrate_id in food.contains_substrate_ids:
            substrate = substrates.get(substrate_id)
            # Spec §6.2 R14: polyols have no commercial enzyme, and the tool
            # never maps them to one. R14 reports the gap instead.
            if substrate is None or substrate.no_commercial_enzyme:
                continue
            wanted.add(substrate_id)

    phase = phase_for_format(format)
    chosen = {
        substrate_id: enzyme
        for substrate_id, enzyme in (
            (sid, enzyme_for_substrate(sid, enzymes)) for sid in sorted(wanted)
        )
        if enzyme is not None
    }

    return tuple(
        SelectedEnzyme(
            enzyme_id=enzyme.id, dose=proposed_dose(enzyme), phase=phase, encapsulated=False
        )
        for _, enzyme in sorted(chosen.items())
    )
```

Delete the old `_proposed_dose`. `tests/engine/test_selection.py` must pass unchanged — this is a refactor, not a policy change.

- [ ] **Step 2: Write `engine/variants.py`**

```python
"""Spec §7 — auto-variant generation. Pure.

`suggest(ctx, findings)` maps an evaluation's own findings onto §7's fix
catalogue. Three rules govern what comes out:

* **Nothing here is pre-cleared.** A suggestion is a patch plus a sentence. Its
  merit is decided by re-running the engine on the result, which is what the
  apply endpoint does — so a suggestion can and sometimes will produce a worse
  verdict, honestly reported (spec §7).
* **A suggestion that cannot honestly be applied carries no patch.** §7's "raise
  recipe pH" is a note: §12 item 1 says recipe pH is a worst-case minimum, not a
  mixing model, so the engine cannot predict the pH that removing an acid
  ingredient would produce (plan decision #4). Supplier questions and the R15
  behavioural note are notes for the same reason — there is nothing in the
  formulation to change.
* **A suggestion never produces a formulation the engine refuses.** §6.2 R14
  rejects zero enzymes with zero trigger foods; a drop suggestion that would
  reach that state is suppressed at generation rather than 422-ing a button the
  tool offered (plan decision #13).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from foodbrew.engine.conventions import resolve_recipe_ph, shelf_stable_floor
from foodbrew.engine.gi_model import active_regions, regions_before_deadline
from foodbrew.engine.patch import apply_patch, canonical, set_format
from foodbrew.engine.rules import r15_applied_texture
from foodbrew.engine.rules.r14_substrate_coverage import ValidationRejection
from foodbrew.engine.selection import enzyme_for_substrate, proposed_dose
from foodbrew.engine.types import (
    DwellProfile,
    Enzyme,
    EvalContext,
    Format,
    Phase,
    RuleFinding,
    Verdict,
)


class SuggestionType(StrEnum):
    """Spec §7's right-hand column, as a closed set the UI can group by."""

    FORMAT_CHANGE = "format_change"
    SWAP_ENZYME = "swap_enzyme"
    ADD_ENZYME = "add_enzyme"
    DROP_ENZYME = "drop_enzyme"
    SEPARATE_ENZYME = "separate_enzyme"
    ENCAPSULATE_ENZYME = "encapsulate_enzyme"
    RAISE_DOSE = "raise_dose"
    DROP_TRIGGER_FOOD = "drop_trigger_food"
    MOVE_ENZYME_ADDITION = "move_enzyme_addition"
    RESTRICT_OCCASIONS = "restrict_occasions"
    #: The three note kinds. `patch` is None on every one of them.
    RECIPE_NOTE = "recipe_note"
    BEHAVIOUR_NOTE = "behaviour_note"
    SUPPLIER_QUESTION = "supplier_question"


@dataclass(frozen=True, slots=True)
class Suggestion:
    suggestion_type: SuggestionType
    description: str
    #: None means there is nothing to apply — the suggestion is a note.
    patch: Mapping[str, Any] | None
    triggered_by: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_applicable(self) -> bool:
        return self.patch is not None


#: Spec §7 R4/R6 — the two formats that physically separate enzyme from liquid.
_SEPARATING_FORMATS = (Format.DUAL_CHAMBER, Format.DRY_SACHET)

_FORMAT_TEXT = {
    Format.DUAL_CHAMBER: "a dual chamber, wet on one side and dry powder on the other",
    Format.DRY_SACHET: "a dry sachet paired with the dressing",
}


# --------------------------------------------------------------------------- #
# Shared producers
# --------------------------------------------------------------------------- #

def _format_changes(ctx: EvalContext, rule_id: str) -> list[Suggestion]:
    return [
        Suggestion(
            SuggestionType.FORMAT_CHANGE,
            f"Sell it as {_FORMAT_TEXT[fmt]}. The enzyme stays dry until use, so water "
            f"never switches it on in the jar.",
            set_format(fmt),
            (rule_id,),
        )
        for fmt in _SEPARATING_FORMATS
        if fmt is not ctx.formulation.format
    ]


def _encapsulate(ctx: EvalContext, rule_id: str) -> list[Suggestion]:
    exposed = [
        s for s in ctx.selected_enzymes() if s.phase is Phase.WET and not s.encapsulated
    ]
    if not exposed:
        return []
    names = ", ".join(ctx.enzyme_for(s).name for s in exposed)
    return [
        Suggestion(
            SuggestionType.ENCAPSULATE_ENZYME,
            f"Encapsulate {names} individually. KB §4f is explicit that a capsule "
            f"delays exposure rather than preventing it, so this buys time and does "
            f"not rescue an enzyme from a pH that would deactivate it on contact — "
            f"R6 re-checks exactly that once you apply it.",
            {
                "ops": [
                    {
                        "op": "set_enzyme_encapsulated",
                        "enzyme_id": s.enzyme_id,
                        "value": True,
                    }
                    for s in exposed
                ]
            },
            (rule_id,),
        )
    ]


def _same_substrate_alternatives(
    ctx: EvalContext, enzyme: Enzyme, recipe_ph: float
) -> tuple[tuple[Enzyme, ...], tuple[Enzyme, ...]]:
    """Catalogue enzymes on the same substrate, split into (would clear, unknown)."""
    clears: list[Enzyme] = []
    unknown: list[Enzyme] = []
    for other in sorted(ctx.enzymes.values(), key=lambda e: e.id):
        if other.id == enzyme.id or other.substrate_id != enzyme.substrate_id:
            continue
        floor = shelf_stable_floor(other)
        if floor.value is None:
            unknown.append(other)
        elif recipe_ph >= floor.value:
            clears.append(other)
    return tuple(clears), tuple(unknown)


# --------------------------------------------------------------------------- #
# Per-rule producers. Each acts only on the verdicts §7 names for that rule.
# --------------------------------------------------------------------------- #

def _r1(ctx: EvalContext, finding: RuleFinding) -> list[Suggestion]:
    if finding.verdict is not Verdict.RED:
        return []
    enzyme = ctx.enzymes.get(finding.enzyme_id or "")
    if enzyme is None:
        return []

    ph = resolve_recipe_ph(ctx.formulation, ctx.foods, ctx.latest_trial_ph)
    if ph.value is None:
        return []

    out: list[Suggestion] = []
    clears, unknown = _same_substrate_alternatives(ctx, enzyme, ph.value)

    for other in clears:
        floor = shelf_stable_floor(other)
        qualifier = (
            " That floor is the stated margin heuristic rather than a supplier figure, "
            "so confirm it before committing."
            if floor.is_heuristic
            else ""
        )
        out.append(
            Suggestion(
                SuggestionType.SWAP_ENZYME,
                f"Swap {enzyme.name} for {other.name}, whose shelf-stable floor of "
                f"pH {floor.value} sits at or below this recipe's pH {ph.value}."
                f"{qualifier}",
                {
                    "ops": [
                        {
                            "op": "swap_enzyme",
                            "enzyme_id": enzyme.id,
                            "replacement_id": other.id,
                            "dose": proposed_dose(other),
                        }
                    ]
                },
                ("R1",),
            )
        )

    for other in unknown:
        out.append(
            Suggestion(
                SuggestionType.SUPPLIER_QUESTION,
                f"{other.name} targets the same substrate but no pH figure is recorded "
                f"for it. Candidate — confirm with the supplier before treating it as a "
                f"fix. Section 15 of the design notes names Amano and BIO-CAT as "
                f"startup-friendly suppliers.",
                None,
                ("R1",),
            )
        )

    if not clears and not unknown:
        out.append(
            Suggestion(
                SuggestionType.SUPPLIER_QUESTION,
                f"Ask a supplier for an acid-stable {enzyme.name} with a shelf-stable "
                f"floor at or below pH {ph.value}. The catalogue holds no alternative "
                f"for this substrate.",
                None,
                ("R1",),
            )
        )

    driver = ctx.foods.get(ph.driving_food_id)
    if driver is not None:
        out.append(
            Suggestion(
                SuggestionType.RECIPE_NOTE,
                f"{driver.name} is the ingredient holding this recipe at pH {ph.value}. "
                f"Reducing or replacing it would raise the pH — but this tool estimates "
                f"recipe pH as the lowest wet-ingredient pH, not as a mixing model, so "
                f"the result has to be measured rather than predicted, and the taste "
                f"call is yours. Enter the measured pH here afterwards and re-run.",
                None,
                ("R1",),
            )
        )

    return out + _format_changes(ctx, "R1")


def _r3(ctx: EvalContext, finding: RuleFinding) -> list[Suggestion]:
    if finding.verdict is not Verdict.RED:
        return []
    heat_steps = finding.evidence.get("heat_steps") or []
    orders = [int(step["order"]) for step in heat_steps]
    if not orders:
        return []
    last_heat = max(orders)
    return [
        Suggestion(
            SuggestionType.MOVE_ENZYME_ADDITION,
            f"Add the enzyme after step {last_heat}, the last step that involves heat, "
            f"rather than at step {finding.evidence.get('enzyme_addition_index')}. Heat "
            f"denatures an enzyme and denaturation is permanent, so the order is the "
            f"whole fix.",
            {"ops": [{"op": "set_enzyme_addition_index", "value": last_heat + 1}]},
            ("R3",),
        )
    ]


def _r4(ctx: EvalContext, finding: RuleFinding) -> list[Suggestion]:
    if finding.verdict is not Verdict.AMBER:
        return []
    return _format_changes(ctx, "R4") + _encapsulate(ctx, "R4")


def _r5(ctx: EvalContext, finding: RuleFinding) -> list[Suggestion]:
    if finding.verdict is not Verdict.RED:
        return []
    out: list[Suggestion] = []

    for enzyme_id in finding.evidence.get("protease_enzymes") or []:
        enzyme = ctx.enzymes.get(enzyme_id)
        if enzyme is None:
            continue
        out.append(
            Suggestion(
                SuggestionType.SEPARATE_ENZYME,
                f"Move {enzyme.name} into the dry side, away from the other enzymes. A "
                f"protease degrades them because enzymes are proteins; separation is "
                f"the whole answer.",
                {
                    "ops": [
                        {"op": "set_enzyme_phase", "enzyme_id": enzyme_id, "value": "dry"}
                    ]
                },
                ("R5",),
            )
        )
        out.append(
            Suggestion(
                SuggestionType.DROP_ENZYME,
                f"Or drop {enzyme.name} altogether. KB §4d treats a protease as additive "
                f"rather than gap-filling — the body already digests protein — so what "
                f"remains is a clean-label and marketing argument, not a digestive one.",
                {"ops": [{"op": "remove_enzyme", "enzyme_id": enzyme_id}]},
                ("R5",),
            )
        )

    raw_foods = [ctx.foods[f] for f in (finding.evidence.get("protease_foods") or [])
                 if f in ctx.foods]
    if raw_foods:
        names = ", ".join(f.name for f in raw_foods)
        out.append(
            Suggestion(
                SuggestionType.RECIPE_NOTE,
                f"{names} brings its own protease into the jar. Cooking it would destroy "
                f"that protease (KB §4j) and suppress the conflict, but it changes the "
                f"recipe and the taste — your call, not a formulation switch.",
                None,
                ("R5",),
            )
        )
    return out


def _r6(ctx: EvalContext, finding: RuleFinding) -> list[Suggestion]:
    if finding.verdict is not Verdict.RED:
        return []
    return _format_changes(ctx, "R6")


def _r7(ctx: EvalContext, finding: RuleFinding) -> list[Suggestion]:
    if finding.verdict is not Verdict.AMBER:
        return []
    enzyme = ctx.enzymes.get(finding.enzyme_id or "")
    threshold = finding.evidence.get("evidence_threshold")
    if enzyme is None or threshold is None:
        return []

    out = [
        Suggestion(
            SuggestionType.RAISE_DOSE,
            f"Raise {enzyme.name} to {threshold} {enzyme.dose_unit}, the dose the "
            f"evidence covers. Below it the enzyme behaves like placebo, so a half "
            f"dose is not half a result.",
            {
                "ops": [
                    {
                        "op": "set_enzyme_dose",
                        "enzyme_id": enzyme.id,
                        "value": float(threshold),
                    }
                ]
            },
            ("R7",),
        )
    ]

    for food_id in ctx.formulation.target_trigger_food_ids:
        food = ctx.foods.get(food_id)
        if food is None or enzyme.substrate_id not in food.contains_substrate_ids:
            continue
        out.append(
            Suggestion(
                SuggestionType.DROP_TRIGGER_FOOD,
                f"Or declare a smaller meal: drop {food.name} from the trigger foods "
                f"this is meant to cover, which lowers the load the dose has to clear. "
                f"That narrows the claim rather than improving the formulation.",
                {"ops": [{"op": "remove_trigger_food", "food_id": food_id}]},
                ("R7",),
            )
        )
    return out


def _r10(ctx: EvalContext, finding: RuleFinding) -> list[Suggestion]:
    """R10 emits PASS advisories; the pairing suggestion is the point of the rule."""
    enzyme = ctx.enzymes.get(finding.enzyme_id or "")
    if enzyme is None:
        return []

    covered = {r.id for r in active_regions(enzyme, ctx.gi_regions)}
    reachable = {r.id for r in regions_before_deadline(enzyme.deadline, ctx.gi_regions)}
    selected = {s.enzyme_id for s in ctx.selected_enzymes()}

    complements: list[Enzyme] = []
    unrecorded: list[Enzyme] = []
    for other in sorted(ctx.enzymes.values(), key=lambda e: e.id):
        if other.id in selected or other.substrate_id != enzyme.substrate_id:
            continue
        if not (other.ph_min.usable and other.ph_max.usable):
            unrecorded.append(other)
            continue
        gained = {r.id for r in active_regions(other, ctx.gi_regions)} & reachable - covered
        if gained:
            complements.append(other)

    if complements:
        partner = complements[0]
        return [
            Suggestion(
                SuggestionType.ADD_ENZYME,
                f"Pair {enzyme.name} with {partner.name}. Blending an acid variant with "
                f"a neutral one — the Enzymedica pattern in KB §4k — widens the active "
                f"window across more of the tract than either covers alone.",
                {
                    "ops": [
                        {
                            "op": "add_enzyme",
                            "enzyme_id": partner.id,
                            "dose": proposed_dose(partner),
                        }
                    ]
                },
                ("R10",),
            )
        ]

    if unrecorded:
        partner = unrecorded[0]
        return [
            Suggestion(
                SuggestionType.SUPPLIER_QUESTION,
                f"{partner.name} would be the complementary source for {enzyme.name} "
                f"under KB §4k, but its pH window is not recorded, so the tool cannot "
                f"tell whether it widens anything. Ask the supplier for the range.",
                None,
                ("R10",),
            )
        ]
    return []


def _supplier_question(ctx: EvalContext, finding: RuleFinding) -> list[Suggestion]:
    """R11 and R12 cannot_assess — §7: no formulation patch, an open question."""
    if finding.verdict is not Verdict.CANNOT_ASSESS:
        return []
    return [
        Suggestion(
            SuggestionType.SUPPLIER_QUESTION,
            finding.message,
            None,
            (finding.rule_id,),
        )
    ]


def _r14(ctx: EvalContext, finding: RuleFinding) -> list[Suggestion]:
    if finding.verdict is not Verdict.RED:
        return []
    substrate_id = finding.evidence.get("substrate")
    enzyme = enzyme_for_substrate(str(substrate_id), ctx.enzymes)
    if enzyme is None:
        return []
    dose = proposed_dose(enzyme)
    dose_text = (
        f" at its benchmark dose of {dose} {enzyme.dose_unit}"
        if dose is not None
        else " — no benchmark dose is recorded for it, so R7 will ask you for one"
    )
    return [
        Suggestion(
            SuggestionType.ADD_ENZYME,
            f"Add {enzyme.name}{dose_text}. It is the catalogue's enzyme for the "
            f"substrate this formulation leaves uncovered.",
            {"ops": [{"op": "add_enzyme", "enzyme_id": enzyme.id, "dose": dose}]},
            ("R14",),
        )
    ]


def _r15(ctx: EvalContext, finding: RuleFinding) -> list[Suggestion]:
    if finding.verdict is Verdict.PASS:
        return []
    out: list[Suggestion] = []

    enzyme = ctx.enzymes.get(finding.enzyme_id or "")
    if enzyme is not None:
        out.append(
            Suggestion(
                SuggestionType.DROP_ENZYME,
                f"Narrow the blend: drop {enzyme.name}. It is the enzyme acting on the "
                f"structure the food depends on, so removing it removes the intersection "
                f"rather than managing it — at the cost of whatever it was covering.",
                {"ops": [{"op": "remove_enzyme", "enzyme_id": enzyme.id}]},
                ("R15",),
            )
        )

    envelope = r15_applied_texture.envelope(ctx)
    passing = [p for p in DwellProfile if envelope.get(p) is Verdict.PASS]
    if passing:
        longest = passing[-1]
        out.append(
            Suggestion(
                SuggestionType.RESTRICT_OCCASIONS,
                f"Support only the '{longest.value}' occasion and say so on the label. "
                f"That is an honest narrowing of the claim; the occasions you drop are "
                f"still listed in the envelope so nothing is hidden.",
                {"ops": [{"op": "set_dwell_profile", "value": longest.value}]},
                ("R15",),
            )
        )

    out.append(
        Suggestion(
            SuggestionType.BEHAVIOUR_NOTE,
            "Dress immediately before eating. A format change is deliberately not "
            "offered here: a dual chamber governs when the dressing is mixed, not how "
            "long it then sits on the food, so it moves none of these occasions.",
            None,
            ("R15",),
        )
    )
    return out


_PRODUCERS = {
    "R1": _r1,
    "R3": _r3,
    "R4": _r4,
    "R5": _r5,
    "R6": _r6,
    "R7": _r7,
    "R10": _r10,
    "R11": _supplier_question,
    "R12": _supplier_question,
    "R14": _r14,
    "R15": _r15,
}


# --------------------------------------------------------------------------- #
# Assembly
# --------------------------------------------------------------------------- #

def _leaves_an_evaluable_formulation(ctx: EvalContext, suggestion: Suggestion) -> bool:
    """Spec §6.2 R14 refuses zero enzymes with zero trigger foods (decision #13).

    Applying the patch here also proves it is well-formed, so a producer that
    emitted a broken op is caught at generation rather than at the button.
    """
    if suggestion.patch is None:
        return True
    try:
        result = apply_patch(ctx.formulation, suggestion.patch)
    except ValidationRejection:
        return False
    return bool(result.enzymes or result.target_trigger_food_ids)


def _rule_order(rule_id: str) -> int:
    try:
        return int(rule_id[1:])
    except ValueError:  # pragma: no cover - rule ids are R<n> by construction
        return 99


def suggest(ctx: EvalContext, findings: Sequence[RuleFinding]) -> tuple[Suggestion, ...]:
    """Spec §7 — the fix catalogue for one evaluation's findings.

    Deduplicated by (type, patch) with the triggering rules merged, so the
    founder sees one dual-chamber button rather than the three that R1, R4 and
    R6 each asked for; ordered by first triggering rule so a re-run of the same
    inputs produces the same rows in the same order (plan decision #14).
    """
    produced: list[Suggestion] = []
    for finding in findings:
        producer = _PRODUCERS.get(finding.rule_id)
        if producer is not None:
            produced.extend(producer(ctx, finding))

    merged: dict[tuple[str, str], Suggestion] = {}
    for suggestion in produced:
        if not _leaves_an_evaluable_formulation(ctx, suggestion):
            continue
        identity = canonical(suggestion.patch) or suggestion.description
        key = (suggestion.suggestion_type.value, identity)
        existing = merged.get(key)
        if existing is None:
            merged[key] = suggestion
        else:
            merged[key] = dataclasses.replace(
                existing,
                triggered_by=tuple(
                    dict.fromkeys(existing.triggered_by + suggestion.triggered_by)
                ),
            )

    return tuple(
        sorted(
            merged.values(),
            key=lambda s: (
                _rule_order(s.triggered_by[0] if s.triggered_by else "R99"),
                s.suggestion_type.value,
                s.description,
            ),
        )
    )
```

- [ ] **Step 3: Test it, one §7 row at a time**

`tests/engine/test_variants.py`:

```python
"""Spec §7, row by row, plus the three constraints plan decisions #4, #13 and
#14 put on the table.
"""

import dataclasses

import pytest

from foodbrew.engine.evaluate import evaluate
from foodbrew.engine.patch import apply_patch
from foodbrew.engine.types import (
    DwellProfile,
    Format,
    Phase,
    ProcessStep,
    Tracked,
    TruthLabel,
    Verdict,
)
from foodbrew.engine.variants import SuggestionType, suggest


def _suggest(ctx):
    return suggest(ctx, evaluate(ctx).findings)


def _types(suggestions):
    return {s.suggestion_type for s in suggestions}


def _of(suggestions, kind):
    return [s for s in suggestions if s.suggestion_type is kind]


# --- §7 row 1: R1 RED ------------------------------------------------------ #

def test_r1_red_offers_a_separated_format(make_ctx):
    ctx = make_ctx(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    formats = _of(_suggest(ctx), SuggestionType.FORMAT_CHANGE)
    targets = {s.patch["ops"][0]["value"] for s in formats}
    assert targets == {"dual_chamber", "dry_sachet"}


def test_r1_red_names_the_ingredient_holding_the_pH_down_and_offers_no_patch(
    make_ctx, seed
):
    """Plan decision #4 — the engine has no mixing model, so this is a note."""
    foods = dict(seed.foods)
    for food_id, ph, water in (("olive_oil", 6.0, 0.0), ("white_vinegar", 2.6, 95.0)):
        foods[food_id] = dataclasses.replace(
            foods[food_id],
            ph=Tracked(ph, TruthLabel.USER_PROVIDED, "fixture"),
            water_content_pct=Tracked(water, TruthLabel.USER_PROVIDED, "fixture"),
        )
    ctx = make_ctx(
        fmt=Format.PREMIXED_WET,
        recipe=(("olive_oil", 100.0), ("white_vinegar", 50.0)),
        trigger_foods=("milk",),
        foods=foods,
    )
    notes = _of(_suggest(ctx), SuggestionType.RECIPE_NOTE)
    assert notes and notes[0].patch is None
    assert "White vinegar" in notes[0].description or "vinegar" in notes[0].description
    assert "measured rather than predicted" in notes[0].description


def test_r1_red_offers_a_swap_when_the_catalogue_holds_one_that_clears(make_ctx, seed):
    catalog = dict(seed.enzymes)
    catalog["lactase_yeast_neutral"] = dataclasses.replace(
        catalog["lactase_yeast_neutral"],
        ph_shelf_stable_min=Tracked(2.0, TruthLabel.CONFIRMED, "supplier spec"),
    )
    ctx = make_ctx(
        fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",),
        enzyme_catalog=catalog,
    )
    swaps = _of(_suggest(ctx), SuggestionType.SWAP_ENZYME)
    assert [s.patch["ops"][0]["replacement_id"] for s in swaps] == ["lactase_yeast_neutral"]


def test_an_unconfirmed_alternative_is_surfaced_as_a_candidate_not_a_patch(make_ctx):
    """§7: 'surfaced even when unconfirmed, labeled candidate — confirm with supplier'."""
    ctx = make_ctx(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    questions = _of(_suggest(ctx), SuggestionType.SUPPLIER_QUESTION)
    candidate = [q for q in questions if "Candidate" in q.description]
    assert candidate and candidate[0].patch is None


# --- §7 row 2: R3 RED ------------------------------------------------------ #

def test_r3_red_moves_the_enzyme_past_the_last_heat_step(make_ctx):
    ctx = make_ctx(
        process_steps=(
            ProcessStep(1, "whisk", False),
            ProcessStep(2, "warm the base", True),
            ProcessStep(3, "cool", False),
        ),
        enzyme_addition_index=1,
        trigger_foods=("milk",),
        measured_ph=6.0,
    )
    moves = _of(_suggest(ctx), SuggestionType.MOVE_ENZYME_ADDITION)
    assert moves and moves[0].patch["ops"][0] == {
        "op": "set_enzyme_addition_index", "value": 3
    }


# --- §7 row 3: R4 AMBER / R6 RED ------------------------------------------- #

def test_r4_amber_offers_separation_and_individual_encapsulation(make_ctx):
    ctx = make_ctx(fmt=Format.PREMIXED_WET, measured_ph=6.0, trigger_foods=("milk",))
    kinds = _types(_suggest(ctx))
    assert SuggestionType.FORMAT_CHANGE in kinds
    assert SuggestionType.ENCAPSULATE_ENZYME in kinds


def test_the_encapsulation_suggestion_carries_the_R6_caveat(make_ctx):
    ctx = make_ctx(fmt=Format.PREMIXED_WET, measured_ph=6.0, trigger_foods=("milk",))
    caps = _of(_suggest(ctx), SuggestionType.ENCAPSULATE_ENZYME)
    assert "delays exposure rather than preventing it" in caps[0].description


# --- §7 row 4: R5 RED ------------------------------------------------------ #

def test_r5_red_offers_separation_and_dropping_the_protease(make_ctx):
    ctx = make_ctx(
        fmt=Format.PREMIXED_WET, measured_ph=6.0, trigger_foods=("milk",),
        enzymes=(
            ("lactase_fungal_acid", 9000.0, Phase.WET),
            ("protease_bromelain", 500.0, Phase.WET),
        ),
    )
    suggestions = _suggest(ctx)
    separate = _of(suggestions, SuggestionType.SEPARATE_ENZYME)
    drop = _of(suggestions, SuggestionType.DROP_ENZYME)
    assert separate[0].patch["ops"][0]["enzyme_id"] == "protease_bromelain"
    assert any(s.patch["ops"][0]["enzyme_id"] == "protease_bromelain" for s in drop)
    assert "additive rather than gap-filling" in drop[0].description


# --- §7 row 5: R7 AMBER ---------------------------------------------------- #

def test_r7_amber_offers_the_evidence_threshold_and_a_narrower_claim(make_ctx, with_load):
    ctx = make_ctx(
        fmt=Format.DRY_SACHET,
        enzymes=(("alpha_galactosidase", 150.0, Phase.DRY),),
        trigger_foods=("black_beans",),
        foods=with_load(black_beans=6.0),
    )
    suggestions = _suggest(ctx)
    raise_dose = _of(suggestions, SuggestionType.RAISE_DOSE)
    assert raise_dose[0].patch["ops"][0]["value"] == 300.0
    drop_food = _of(suggestions, SuggestionType.DROP_TRIGGER_FOOD)
    assert drop_food[0].patch["ops"][0]["food_id"] == "black_beans"


# --- §7 row 7: R11 / R12 cannot_assess ------------------------------------- #

def test_unassessable_sourcing_rules_become_open_questions_with_no_patch(make_ctx):
    ctx = make_ctx(fmt=Format.DRY_SACHET, trigger_foods=("milk",))
    questions = _of(_suggest(ctx), SuggestionType.SUPPLIER_QUESTION)
    assert questions, "R12 is cannot_assess for every shipped enzyme (spec §9.1)"
    assert all(q.patch is None for q in questions)
    assert any("R12" in q.triggered_by for q in questions)


# --- §7 row 8: R14 RED ----------------------------------------------------- #

def test_r14_red_adds_the_enzyme_for_the_uncovered_substrate(make_ctx):
    ctx = make_ctx(
        fmt=Format.DRY_SACHET,
        enzymes=(("lactase_fungal_acid", 9000.0, Phase.DRY),),
        trigger_foods=("milk", "black_beans"),
    )
    adds = _of(_suggest(ctx), SuggestionType.ADD_ENZYME)
    assert any(s.patch["ops"][0]["enzyme_id"] == "alpha_galactosidase" for s in adds)


def test_a_polyol_trigger_food_never_produces_an_enzyme_suggestion(make_ctx):
    """§6.2 R14: the tool never maps polyols to an enzyme."""
    ctx = make_ctx(
        fmt=Format.DRY_SACHET,
        enzymes=(("lactase_fungal_acid", 9000.0, Phase.DRY),),
        trigger_foods=("milk", "mushroom"),
    )
    for suggestion in _of(_suggest(ctx), SuggestionType.ADD_ENZYME):
        added = suggestion.patch["ops"][0]["enzyme_id"]
        assert ctx.enzymes[added].substrate_id != "polyol"


# --- §7 row 9: R15 envelope non-pass --------------------------------------- #

def test_r15_offers_dropping_the_degrader_restricting_occasions_and_a_note(make_ctx):
    ctx = make_ctx(
        fmt=Format.DRY_SACHET,
        enzymes=(("cellulase", None, Phase.DRY),),
        trigger_foods=("broccoli",),
        application_foods=("mixed_greens",),
    )
    suggestions = _suggest(ctx)
    kinds = _types(suggestions)
    assert SuggestionType.DROP_ENZYME in kinds
    assert SuggestionType.RESTRICT_OCCASIONS in kinds
    assert SuggestionType.BEHAVIOUR_NOTE in kinds

    restrict = _of(suggestions, SuggestionType.RESTRICT_OCCASIONS)[0]
    assert restrict.patch["ops"][0]["value"] == DwellProfile.IMMEDIATE.value


def test_r15_never_offers_a_format_change_for_texture(make_ctx):
    """§7: a dual chamber does not move how long dressing sits on the food."""
    ctx = make_ctx(
        fmt=Format.DRY_SACHET,
        enzymes=(("cellulase", None, Phase.DRY),),
        trigger_foods=("broccoli",),
        application_foods=("mixed_greens",),
    )
    for suggestion in _of(_suggest(ctx), SuggestionType.FORMAT_CHANGE):
        assert "R15" not in suggestion.triggered_by


# --- Assembly rules -------------------------------------------------------- #

def test_the_dual_chamber_button_appears_once_and_names_every_rule(make_ctx):
    """Plan decision #14 — R1, R4 and R6 all ask for it."""
    ctx = make_ctx(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    dual = [
        s for s in _of(_suggest(ctx), SuggestionType.FORMAT_CHANGE)
        if s.patch["ops"][0]["value"] == "dual_chamber"
    ]
    assert len(dual) == 1
    assert set(dual[0].triggered_by) >= {"R1", "R4"}


def test_the_order_is_stable_across_runs(make_ctx):
    ctx = make_ctx(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    first = [(s.suggestion_type, s.description) for s in _suggest(ctx)]
    second = [(s.suggestion_type, s.description) for s in _suggest(ctx)]
    assert first == second


def test_a_drop_that_would_empty_the_formulation_is_suppressed(make_ctx):
    """Plan decision #13 — §6.2 R14 would refuse the result."""
    ctx = make_ctx(
        fmt=Format.PREMIXED_WET,
        measured_ph=6.0,
        enzymes=(("protease_bromelain", 500.0, Phase.WET),),
        trigger_foods=(),
        recipe=(("olive_oil", 100.0),),
        application_foods=("chicken_cooked",),
    )
    for suggestion in _of(_suggest(ctx), SuggestionType.DROP_ENZYME):
        pytest.fail(f"emitted a drop that empties the formulation: {suggestion.description}")


def test_every_applicable_patch_re_evaluates_without_error(make_ctx):
    """Spec §13's contract test, at the engine level. Task 20 repeats it over HTTP."""
    contexts = [
        make_ctx(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",)),
        make_ctx(
            fmt=Format.PREMIXED_WET, measured_ph=6.0, trigger_foods=("milk",),
            enzymes=(
                ("lactase_fungal_acid", 9000.0, Phase.WET),
                ("protease_bromelain", 500.0, Phase.WET),
            ),
        ),
        make_ctx(
            fmt=Format.DRY_SACHET,
            enzymes=(("cellulase", None, Phase.DRY),),
            trigger_foods=("broccoli",),
            application_foods=("mixed_greens",),
        ),
        make_ctx(
            fmt=Format.DRY_SACHET,
            enzymes=(("lactase_fungal_acid", 9000.0, Phase.DRY),),
            trigger_foods=("milk", "black_beans"),
        ),
    ]
    applied = 0
    for ctx in contexts:
        for suggestion in _suggest(ctx):
            if not suggestion.is_applicable:
                continue
            patched = apply_patch(ctx.formulation, suggestion.patch)
            result = evaluate(dataclasses.replace(ctx, formulation=patched))
            assert result.overall in set(Verdict)
            applied += 1
    assert applied >= 8, "the sweep applied suspiciously few patches"


def test_notes_never_carry_a_patch(make_ctx):
    note_kinds = {
        SuggestionType.RECIPE_NOTE,
        SuggestionType.BEHAVIOUR_NOTE,
        SuggestionType.SUPPLIER_QUESTION,
    }
    ctx = make_ctx(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    for suggestion in _suggest(ctx):
        if suggestion.suggestion_type in note_kinds:
            assert suggestion.patch is None
        else:
            assert suggestion.patch is not None
```

Run: `.venv/bin/pytest tests/engine/test_variants.py -q`
Expected: 20 passed.

- [ ] **Step 4: Run the whole engine suite**

Run: `.venv/bin/pytest tests/engine -q && .venv/bin/ruff check src tests`
Expected: green, including `test_selection.py` unchanged.

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/engine/variants.py src/foodbrew/engine/selection.py tests/engine/test_variants.py
git commit -m "feat(engine): generate the auto-variant suggestions from spec 7"
```

---

## Task 6: `engine/compare.py` — the side-by-side table

Workflow B: "one column per variant, one row per rule + dose + format call + occasion envelope, changed cells highlighted." Pure, and it takes reduced inputs rather than stored rows so it never learns what a database is.

**Files:**
- Create: `src/foodbrew/engine/compare.py`
- Create: `tests/engine/test_compare.py`

- [ ] **Step 1: Write the module**

```python
"""Spec §3 Workflow B — the variant comparison table. Pure.

Rows are the UNION across columns, not the intersection. Variants legitimately
differ in which enzymes they select, and a row present on one side and absent on
another is exactly the difference the founder opened this screen to see — so an
absent cell renders "not in this variant" and is never dropped (plan decision
#10).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from foodbrew.engine.rules.r14_substrate_coverage import ValidationRejection
from foodbrew.engine.types import DwellProfile, RuleFinding, Verdict
from foodbrew.engine.views import RULE_TITLES

#: A readability cap and a bound on the query behind it (plan decision #10).
MAX_COLUMNS = 6

MISSING = "not in this variant"

_SECTION_ORDER = ("Verdict", "Setup", "Rules", "Dose per serving", "Occasion envelope")


@dataclass(frozen=True, slots=True)
class ComparisonSide:
    """One evaluation, reduced to what a comparison row can read."""

    evaluation_id: str
    label: str
    headline: str
    format: str
    dwell_profile: str | None
    findings: tuple[RuleFinding, ...]
    envelope: Mapping[DwellProfile, Verdict]
    #: enzyme_id -> (dose, unit, enzyme name)
    doses: Mapping[str, tuple[float | None, str, str]]


@dataclass(frozen=True, slots=True)
class Column:
    evaluation_id: str
    label: str
    headline: str


@dataclass(frozen=True, slots=True)
class Cell:
    text: str
    #: The verdict this cell reports, when it reports one, for colouring.
    verdict: str | None
    present: bool


@dataclass(frozen=True, slots=True)
class Row:
    section: str
    key: str
    label: str
    cells: tuple[Cell, ...]
    changed: bool


@dataclass(frozen=True, slots=True)
class Comparison:
    columns: tuple[Column, ...]
    rows: tuple[Row, ...]


def _finding_key(finding: RuleFinding) -> tuple[str, str, str]:
    return (finding.rule_id, finding.enzyme_id or "", finding.food_id or "")


def _finding_label(key: tuple[str, str, str]) -> str:
    rule_id, enzyme_id, food_id = key
    parts = [f"{rule_id} — {RULE_TITLES.get(rule_id, rule_id)}"]
    subject = " / ".join(p for p in (enzyme_id, food_id) if p)
    if subject:
        parts.append(subject)
    return " · ".join(parts)


def _absent() -> Cell:
    return Cell(MISSING, None, False)


def _row(section: str, key: str, label: str, cells: Sequence[Cell]) -> Row:
    signature = {(c.text, c.verdict, c.present) for c in cells}
    return Row(section, key, label, tuple(cells), changed=len(signature) > 1)


def compare(sides: Sequence[ComparisonSide]) -> Comparison:
    if len(sides) < 2:
        raise ValidationRejection("Pick at least two evaluations to compare.")
    if len(sides) > MAX_COLUMNS:
        raise ValidationRejection(
            f"Compare up to {MAX_COLUMNS} evaluations at a time — you picked {len(sides)}."
        )

    lookups = [{_finding_key(f): f for f in side.findings} for side in sides]
    rows: list[Row] = []

    rows.append(_row("Verdict", "headline", "Headline", [
        Cell(side.headline, None, True) for side in sides
    ]))
    rows.append(_row("Setup", "format", "Format", [
        Cell(side.format, None, True) for side in sides
    ]))
    rows.append(_row("Setup", "dwell_profile", "Declared use occasion", [
        Cell(side.dwell_profile or "not declared", None, True) for side in sides
    ]))

    finding_keys: list[tuple[str, str, str]] = []
    for lookup in lookups:
        for key in lookup:
            if key not in finding_keys:
                finding_keys.append(key)
    finding_keys.sort(key=lambda k: (int(k[0][1:]), k[1], k[2]))

    for key in finding_keys:
        cells = []
        for lookup in lookups:
            finding = lookup.get(key)
            cells.append(
                Cell(finding.message, str(finding.verdict), True)
                if finding is not None
                else _absent()
            )
        rows.append(_row("Rules", ":".join(key), _finding_label(key), cells))

    enzyme_ids: list[str] = []
    for side in sides:
        for enzyme_id in side.doses:
            if enzyme_id not in enzyme_ids:
                enzyme_ids.append(enzyme_id)
    enzyme_ids.sort()

    for enzyme_id in enzyme_ids:
        cells = []
        label = enzyme_id
        for side in sides:
            entry = side.doses.get(enzyme_id)
            if entry is None:
                cells.append(_absent())
                continue
            dose, unit, name = entry
            label = name
            cells.append(
                Cell("no dose set" if dose is None else f"{dose} {unit}".strip(), None, True)
            )
        rows.append(_row("Dose per serving", f"dose:{enzyme_id}", label, cells))

    for profile in DwellProfile:
        cells = []
        for side in sides:
            verdict = side.envelope.get(profile)
            cells.append(
                Cell(str(verdict), str(verdict), True) if verdict is not None else _absent()
            )
        rows.append(
            _row("Occasion envelope", f"envelope:{profile.value}", profile.value, cells)
        )

    # Rows are appended in `_SECTION_ORDER` already; the constant exists so the
    # renderer can group by it, not so this function can re-sort. Sorting here
    # would need `rows.index`, which compares frozen dataclasses by value and
    # would collapse two genuinely identical rows onto one position.
    return Comparison(
        columns=tuple(
            Column(side.evaluation_id, side.label, side.headline) for side in sides
        ),
        rows=tuple(rows),
    )
```

The final `rows.sort` is a stable sort keyed on section order first, so rows keep the order they were appended within a section. Because `rows.index(r)` is O(n), and n is bounded by roughly (findings + enzymes + 3 + 3) for at most six columns, this stays negligible; if that ever stops being true, enumerate the list instead.

- [ ] **Step 2: Test it**

`tests/engine/test_compare.py`:

```python
"""Spec §3 Workflow B."""

import pytest

from foodbrew.engine import ValidationRejection
from foodbrew.engine.compare import MAX_COLUMNS, MISSING, ComparisonSide, compare
from foodbrew.engine.types import DwellProfile, RuleFinding, Verdict


def _side(evaluation_id, headline, fmt, findings, envelope=None, doses=None, dwell=None):
    return ComparisonSide(
        evaluation_id=evaluation_id,
        label=evaluation_id,
        headline=headline,
        format=fmt,
        dwell_profile=dwell,
        findings=tuple(findings),
        envelope=envelope or dict.fromkeys(DwellProfile, Verdict.PASS),
        doses=doses or {},
    )


def _row(comparison, key):
    return next(r for r in comparison.rows if r.key == key)


def test_a_single_evaluation_is_refused():
    with pytest.raises(ValidationRejection):
        compare([_side("a", "RED", "premixed_wet", [])])


def test_more_than_the_cap_is_refused():
    sides = [_side(str(n), "GREEN", "dry_sachet", []) for n in range(MAX_COLUMNS + 1)]
    with pytest.raises(ValidationRejection) as excinfo:
        compare(sides)
    assert str(MAX_COLUMNS) in str(excinfo.value)


def test_the_headline_row_is_marked_changed_when_it_differs():
    comparison = compare([
        _side("a", "RED", "premixed_wet", []),
        _side("b", "GREEN", "dry_sachet", []),
    ])
    assert _row(comparison, "headline").changed
    assert _row(comparison, "format").changed


def test_an_identical_row_is_not_marked_changed():
    finding = RuleFinding("R4", Verdict.AMBER, "water switches it on")
    comparison = compare([
        _side("a", "AMBER", "premixed_wet", [finding]),
        _side("b", "AMBER", "premixed_wet", [finding]),
    ])
    assert not _row(comparison, "R4::").changed


def test_a_finding_present_on_one_side_only_renders_as_absent_not_dropped():
    comparison = compare([
        _side("a", "RED", "premixed_wet",
              [RuleFinding("R1", Verdict.RED, "denatures", enzyme_id="lactase_fungal_acid")]),
        _side("b", "GREEN", "dry_sachet", []),
    ])
    row = _row(comparison, "R1:lactase_fungal_acid:")
    assert row.changed
    assert [c.present for c in row.cells] == [True, False]
    assert row.cells[1].text == MISSING


def test_rows_are_ordered_by_rule_number_not_lexically():
    findings = [
        RuleFinding("R14", Verdict.RED, "uncovered"),
        RuleFinding("R2", Verdict.PASS, "window fits"),
    ]
    comparison = compare([
        _side("a", "RED", "dry_sachet", findings),
        _side("b", "RED", "dry_sachet", findings),
    ])
    rule_rows = [r.key for r in comparison.rows if r.section == "Rules"]
    assert rule_rows == ["R2::", "R14::"]


def test_dose_rows_union_across_columns_and_label_by_name():
    comparison = compare([
        _side("a", "AMBER", "dry_sachet", [],
              doses={"alpha_galactosidase": (150.0, "GalU", "Alpha-galactosidase")}),
        _side("b", "GREEN", "dry_sachet", [],
              doses={"alpha_galactosidase": (300.0, "GalU", "Alpha-galactosidase")}),
    ])
    row = _row(comparison, "dose:alpha_galactosidase")
    assert row.label == "Alpha-galactosidase"
    assert [c.text for c in row.cells] == ["150.0 GalU", "300.0 GalU"]
    assert row.changed


def test_a_missing_dose_reads_as_not_set_rather_than_blank():
    comparison = compare([
        _side("a", "GRAY", "dry_sachet", [], doses={"cellulase": (None, "", "Cellulase")}),
        _side("b", "GRAY", "dry_sachet", [], doses={"cellulase": (None, "", "Cellulase")}),
    ])
    assert _row(comparison, "dose:cellulase").cells[0].text == "no dose set"


def test_the_envelope_contributes_one_row_per_occasion():
    comparison = compare([
        _side("a", "AMBER", "dry_sachet", [], envelope={
            DwellProfile.IMMEDIATE: Verdict.PASS,
            DwellProfile.PACKED: Verdict.AMBER,
            DwellProfile.MARINADE: Verdict.RED,
        }),
        _side("b", "GREEN", "dry_sachet", []),
    ])
    keys = [r.key for r in comparison.rows if r.section == "Occasion envelope"]
    assert keys == ["envelope:immediate", "envelope:packed", "envelope:marinade"]
    assert not _row(comparison, "envelope:immediate").changed
    assert _row(comparison, "envelope:marinade").changed


def test_sections_come_out_in_reading_order():
    comparison = compare([
        _side("a", "RED", "premixed_wet", [RuleFinding("R1", Verdict.RED, "x")],
              doses={"lactase_fungal_acid": (9000.0, "FCC", "Lactase")}),
        _side("b", "GREEN", "dry_sachet", [], doses={}),
    ])
    seen = []
    for row in comparison.rows:
        if row.section not in seen:
            seen.append(row.section)
    assert seen == ["Verdict", "Setup", "Rules", "Dose per serving", "Occasion envelope"]
```

Run: `.venv/bin/pytest tests/engine/test_compare.py -q`
Expected: 10 passed.

- [ ] **Step 3: Commit**

```bash
git add src/foodbrew/engine/compare.py tests/engine/test_compare.py
git commit -m "feat(engine): add the variant comparison table"
```
---

## Task 7: `engine/report.py` — the report model and the Markdown renderer

§10 screen 8: "inputs, predicted findings, observed results with confidence tiers, the occasion envelope, evidence values, data gaps, sources, engine version, and a fixed footer." Pure, and it owns the footer for the reason plan decision #11 gives.

**Files:**
- Create: `src/foodbrew/engine/report.py`
- Create: `tests/engine/test_report.py`

- [ ] **Step 1: Write the module**

```python
"""Spec §10 screen 8 — the handoff report, rendered as Markdown. Pure.

The renderer lives in the engine rather than beside the endpoint that serves it
because `tests/api/test_contracts.py` greps every file under `api/` for the
prohibited words as substrings, and the §10 footer contains "safety" (plan
decision #11). Keeping the disclaimer here means the api-source lint stays
strict and the footer stays intact.

Observed results are M4's. Until a trial exists they render as an explicit
absence rather than being omitted, so M4 fills a section rather than
restructuring the document (plan decision #12).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from foodbrew.engine.flags import group_findings
from foodbrew.engine.format_search import FORMAT_TITLES, FormatRecommendation
from foodbrew.engine.types import (
    DwellProfile,
    EvalContext,
    RuleFinding,
    Tracked,
    TruthLabel,
    Verdict,
)
from foodbrew.engine.variants import SuggestionType
from foodbrew.engine.views import RULE_TITLES, dose_cards, gi_strip

#: Spec §10 screen 8. Fixed text, on every rendering, at the end.
DISCLAIMER = (
    "Formulation decision support. Not a safety, efficacy, or regulatory determination."
)

_VERDICT_TEXT: Mapping[Verdict, str] = {
    Verdict.RED: "blocker",
    Verdict.CANNOT_ASSESS: "cannot assess",
    Verdict.AMBER: "caution",
    Verdict.PASS: "clear",
}

_LABEL_TEXT: Mapping[TruthLabel, str] = {
    TruthLabel.CONFIRMED: "confirmed",
    TruthLabel.UNCONFIRMED: "not confirmed",
    TruthLabel.USER_PROVIDED: "entered by you",
    TruthLabel.CALCULATED: "calculated",
    TruthLabel.OBSERVED: "observed in a trial",
}

_OCCASION_TEXT: Mapping[DwellProfile, str] = {
    DwellProfile.IMMEDIATE: "Dressed at the table (eaten within the hour)",
    DwellProfile.PACKED: "Packed ahead (dressed 1 to 8 hours before eating)",
    DwellProfile.MARINADE: "Marinade (left 8 hours or more, on purpose)",
}

_NOTE_TYPES = frozenset(
    {
        SuggestionType.RECIPE_NOTE,
        SuggestionType.BEHAVIOUR_NOTE,
        SuggestionType.SUPPLIER_QUESTION,
    }
)


@dataclass(frozen=True, slots=True)
class ReportSuggestion:
    """A suggestion reduced to what the report prints.

    Deliberately not `variants.Suggestion`: the report is rendered from a
    *stored* evaluation, whose suggestions come back as `store.variants
    .StoredSuggestion` rows. Both sides map into this in two lines, and the
    renderer stays ignorant of which one it was handed.
    """

    suggestion_type: str
    description: str
    raised_by: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReportInput:
    """Everything the report needs, already frozen. The renderer derives the rest."""

    evaluation_id: str
    created_at: str
    engine_version: str
    recipe_name: str
    headline: str
    context: EvalContext
    findings: tuple[RuleFinding, ...]
    envelope: Mapping[DwellProfile, Verdict]
    recommendation: FormatRecommendation
    suggestions: tuple[ReportSuggestion, ...] = field(default_factory=tuple)
    #: True when a referenced record has changed since this evaluation ran.
    stale: bool = False


def _tracked(value: Tracked, unit: str = "") -> str:
    if value.value is None:
        shown = "not recorded"
    elif isinstance(value.value, bool):
        shown = "yes" if value.value else "no"
    else:
        shown = f"{value.value}{f' {unit}' if unit else ''}"
    source = f" — {value.source}" if value.source else ""
    return f"{shown} ({_LABEL_TEXT[value.status]}{source})"


def _findings_section(title: str, blurb: str, findings: Sequence[RuleFinding]) -> list[str]:
    if not findings:
        return []
    lines = [f"### {title}", "", blurb, ""]
    for finding in findings:
        rule = f"{finding.rule_id} — {RULE_TITLES.get(finding.rule_id, finding.rule_id)}"
        lines.append(f"- **{rule}** ({_VERDICT_TEXT[finding.verdict]}): {finding.message}")
    lines.append("")
    return lines


def _inputs_section(data: ReportInput) -> list[str]:
    ctx = data.context
    form = ctx.formulation
    lines = ["## What was checked", ""]
    serving = "not set" if form.serving_size_g is None else f"{form.serving_size_g} g"

    lines += [
        f"- **Recipe:** {data.recipe_name}",
        f"- **Format:** {FORMAT_TITLES.get(form.format, form.format.value)}",
        f"- **Serving size:** {serving}",
        f"- **Measured pH:** {_tracked(form.measured_ph)}",
        "- **Declared use occasion:** "
        + (form.dwell_profile.value if form.dwell_profile else "not declared"),
        "",
        "### Recipe",
        "",
        "| Ingredient | Grams | pH | Water content |",
        "| --- | ---: | --- | --- |",
    ]
    for ingredient in form.recipe:
        food = ctx.foods.get(ingredient.food_id)
        name = food.name if food else ingredient.food_id
        ph = _tracked(food.ph) if food else "not recorded"
        water = _tracked(food.water_content_pct, "%") if food else "not recorded"
        lines.append(f"| {name} | {ingredient.amount_g} | {ph} | {water} |")
    lines.append("")

    for title, ids in (
        ("Trigger foods this is meant to cover", form.target_trigger_food_ids),
        ("Foods it will be poured on", form.application_food_ids),
    ):
        names = [
            ctx.foods[i].name if i in ctx.foods else i for i in ids
        ]
        lines += [f"### {title}", "", ", ".join(names) if names else "none selected", ""]

    if form.process_steps:
        lines += ["### How it is made", ""]
        for step in form.process_steps:
            marks = []
            if step.is_heat:
                marks.append("involves heat")
            if form.enzyme_addition_index == step.order:
                marks.append("enzyme goes in here")
            suffix = f" — {', '.join(marks)}" if marks else ""
            lines.append(f"{step.order}. {step.label}{suffix}")
        lines.append("")
    return lines


def _dose_section(data: ReportInput) -> list[str]:
    cards = dose_cards(data.context)
    if not cards:
        return []
    lines = [
        "## Dose per serving",
        "",
        "Dose is driven by how much of the substrate a serving carries, not by the "
        "weight of the food. Below the evidence threshold an enzyme behaves like a "
        "placebo, which is why an under-dose is flagged rather than rounded up.",
        "",
        "| Enzyme | Your dose | Benchmark range | Evidence threshold "
        "| Substrate in a serving | Clears it |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for card in cards:
        clears = (
            "cannot tell"
            if card.meets_threshold is None
            else ("yes" if card.meets_threshold else "no")
        )
        dose = "not set" if card.dose is None else f"{card.dose} {card.dose_unit}".strip()
        low = _tracked(card.dose_min, card.dose_unit)
        high = _tracked(card.dose_max, card.dose_unit)
        lines.append(
            f"| {card.enzyme_name} | {dose} | {low} to {high} "
            f"| {_tracked(card.dose_evidence_threshold, card.dose_unit)} "
            f"| {_tracked(card.substrate_load)} | {clears} |"
        )
    lines.append("")
    return lines


def _gi_section(data: ReportInput) -> list[str]:
    lanes = gi_strip(data.context)
    if not lanes:
        return []
    regions = lanes[0].regions
    header = " | ".join(r.name for r in regions)
    divider = " | ".join("---" for _ in regions)
    lines = [
        "## Where each enzyme can work",
        "",
        "A deadline, not a target: anything left when the food reaches the colon "
        "ferments there. The mouth is dormant for every enzyme because food is there "
        "for seconds.",
        "",
        f"| Enzyme | {header} |",
        f"| --- | {divider} |",
    ]
    for lane in lanes:
        cells = []
        for region in lane.regions:
            if region.dormant:
                cells.append("dormant")
            elif region.active and region.before_deadline:
                cells.append("active")
            elif region.active:
                cells.append("active, past its deadline")
            else:
                cells.append("—")
        lines.append(f"| {lane.enzyme_name} | {' | '.join(cells)} |")
    lines.append("")
    return lines


def _envelope_section(data: ReportInput) -> list[str]:
    lines = [
        "## Which occasions this can support",
        "",
        "What the dressing does to the food it sits on, by how long it sits there. An "
        "occasion you do not intend to sell is still listed, so nothing is hidden.",
        "",
        "| Occasion | Predicted | Observed |",
        "| --- | --- | --- |",
    ]
    for profile in DwellProfile:
        verdict = data.envelope.get(profile)
        predicted = _VERDICT_TEXT[verdict] if verdict is not None else "not evaluated"
        lines.append(f"| {_OCCASION_TEXT[profile]} | {predicted} | no trial yet |")
    lines.append("")
    return lines


def _format_section(data: ReportInput) -> list[str]:
    recommendation = data.recommendation
    lines = ["## Format", "", recommendation.message, "", "| Format | Blockers |", "| --- | --- |"]
    for option in recommendation.options:
        marker = " (current)" if option.is_current else ""
        blockers = ", ".join(option.reds) if option.reds else "none on the rules checked"
        lines.append(f"| {option.title}{marker} | {blockers} |")
    lines.append("")
    return lines


def _suggestions_section(data: ReportInput) -> list[str]:
    actionable = [s for s in data.suggestions if s.suggestion_type not in _NOTE_TYPES]
    if not actionable:
        return []
    lines = [
        "## Changes the rules suggest",
        "",
        "None of these is pre-cleared. Each one is re-run through the whole rule set "
        "when it is applied, and its own flags are reported then.",
        "",
    ]
    for suggestion in actionable:
        rules = ", ".join(suggestion.raised_by)
        lines.append(f"- **{rules}:** {suggestion.description}")
    lines.append("")
    return lines


def _open_questions_section(data: ReportInput) -> list[str]:
    # `==`, not `is`: `suggestion_type` is a plain str here, and StrEnum compares
    # and hashes as its value, so equality and set membership both work — but
    # identity does not.
    questions = [
        s for s in data.suggestions if s.suggestion_type == SuggestionType.SUPPLIER_QUESTION
    ]
    gaps = group_findings(data.findings).data_gaps
    if not questions and not gaps:
        return []
    lines = ["## Open questions", "", "Answers a supplier or a bench run would close.", ""]
    for gap in gaps:
        lines.append(f"- **{gap.rule_id}:** {gap.message}")
    for question in questions:
        lines.append(f"- **{', '.join(question.raised_by)}:** {question.description}")
    lines.append("")
    return lines


def _observed_section() -> list[str]:
    """Spec §10 screen 8 and §6.6 — filled by M4's kitchen trial."""
    return [
        "## What was observed",
        "",
        "No trial has been recorded for this formulation yet. Everything above is a "
        "prediction from the rules and the data behind them; nothing here was measured.",
        "",
    ]


def _provenance_section(data: ReportInput) -> list[str]:
    lines = [
        "## Provenance",
        "",
        f"- **Evaluation:** {data.evaluation_id}",
        f"- **Run at:** {data.created_at}",
        f"- **Engine version:** {data.engine_version}",
        "- **Inputs:** frozen with this evaluation. Editing a record afterwards does "
        "not change it; re-run to see the effect of a change.",
    ]
    if data.stale:
        lines.append(
            "- **Note:** a record this evaluation used has changed since it ran. "
            "Re-run before relying on the numbers above."
        )
    lines.append("")
    return lines


def render_markdown(data: ReportInput) -> str:
    groups = group_findings(data.findings)

    lines = [
        f"# Formulation report — {data.recipe_name}",
        "",
        f"**{data.headline}**",
        "",
    ]
    lines += _inputs_section(data)
    lines += ["## What the rules found", ""]
    lines += _findings_section(
        "Blockers", "These stop the formulation as specified.", groups.blockers
    )
    lines += _findings_section(
        "Data gaps",
        "Missing values. Fill these in and re-run to get a verdict.",
        groups.data_gaps,
    )
    lines += _findings_section(
        "Cautions",
        "Not blockers, but they change over time or with use.",
        groups.cautions,
    )
    lines += _findings_section(
        "Advisory",
        "Notes that never change the headline — decisions that belong to you.",
        groups.advisories,
    )
    lines += _dose_section(data)
    lines += _gi_section(data)
    lines += _envelope_section(data)
    lines += _format_section(data)
    lines += _suggestions_section(data)
    lines += _observed_section()
    lines += _open_questions_section(data)
    lines += _provenance_section(data)
    lines += ["---", "", DISCLAIMER, ""]

    return "\n".join(lines)
```

- [ ] **Step 2: Test it**

`tests/engine/test_report.py`:

```python
"""Spec §10 screen 8 and §13's report lint."""

import pytest

from foodbrew.engine.evaluate import evaluate
from foodbrew.engine.format_search import recommend_format
from foodbrew.engine.language import contains_prohibited
from foodbrew.engine.report import (
    DISCLAIMER,
    ReportInput,
    ReportSuggestion,
    render_markdown,
)
from foodbrew.engine.types import Format, Phase, ProcessStep
from foodbrew.engine.variants import suggest


@pytest.fixture
def rendered(make_ctx):
    def _render(**kwargs):
        ctx = make_ctx(**kwargs)
        result = evaluate(ctx)
        data = ReportInput(
            evaluation_id="eval-1",
            created_at="2026-08-14T12:00:00+00:00",
            engine_version="1.0.0",
            recipe_name="Vinaigrette",
            headline=result.display,
            context=ctx,
            findings=result.findings,
            envelope=result.envelope,
            recommendation=recommend_format(ctx),
            suggestions=tuple(
                ReportSuggestion(
                    s.suggestion_type.value, s.description, s.triggered_by
                )
                for s in suggest(ctx, result.findings)
            ),
        )
        return render_markdown(data)

    return _render


def test_the_disclaimer_is_the_last_thing_on_the_page(rendered):
    text = rendered(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    assert text.rstrip().endswith(DISCLAIMER)


def test_no_prohibited_word_survives_the_report_lint(rendered):
    """Spec §13. Word boundaries, so the footer's 'safety' passes (decision #11)."""
    for kwargs in (
        {"fmt": Format.PREMIXED_WET, "measured_ph": 3.0, "trigger_foods": ("milk",)},
        {"fmt": Format.DRY_SACHET, "trigger_foods": ("milk", "black_beans")},
        {
            "fmt": Format.DRY_SACHET,
            "enzymes": (("cellulase", None, Phase.DRY),),
            "trigger_foods": ("broccoli",),
            "application_foods": ("mixed_greens",),
        },
    ):
        text = rendered(**kwargs)
        assert contains_prohibited(text) == (), kwargs


def test_the_footer_itself_would_fail_a_substring_lint_and_passes_this_one():
    assert "safe" in DISCLAIMER
    assert contains_prohibited(DISCLAIMER) == ()


def test_every_required_section_is_present(rendered):
    text = rendered(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    for heading in (
        "## What was checked",
        "## What the rules found",
        "## Dose per serving",
        "## Where each enzyme can work",
        "## Which occasions this can support",
        "## Format",
        "## What was observed",
        "## Provenance",
    ):
        assert heading in text, heading


def test_the_observed_section_says_there_is_no_trial_rather_than_being_absent(rendered):
    """Plan decision #12 — M4 fills this section, it does not create it."""
    text = rendered(fmt=Format.DRY_SACHET, trigger_foods=("milk",))
    assert "No trial has been recorded for this formulation yet." in text


def test_every_value_travels_with_its_label(rendered):
    text = rendered(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    assert "(entered by you" in text          # the measured pH
    assert "(not confirmed" in text           # the seeded shelf-stable floor


def test_a_blocker_is_reported_with_its_rule_and_its_message(rendered):
    text = rendered(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    assert "### Blockers" in text
    assert "R1 — In-jar pH survival" in text


def test_the_process_sequence_marks_the_heat_step_and_the_addition_point(rendered):
    text = rendered(
        fmt=Format.DRY_SACHET,
        trigger_foods=("milk",),
        process_steps=(ProcessStep(1, "warm", True), ProcessStep(2, "whisk", False)),
        enzyme_addition_index=2,
    )
    assert "1. warm — involves heat" in text
    assert "2. whisk — enzyme goes in here" in text


def test_a_stale_report_says_so_in_provenance(make_ctx):
    ctx = make_ctx(fmt=Format.DRY_SACHET, trigger_foods=("milk",))
    result = evaluate(ctx)
    text = render_markdown(
        ReportInput(
            evaluation_id="eval-1", created_at="t", engine_version="1.0.0",
            recipe_name="R", headline=result.display, context=ctx,
            findings=result.findings, envelope=result.envelope,
            recommendation=recommend_format(ctx), stale=True,
        )
    )
    assert "has changed since it ran" in text
```

Run: `.venv/bin/pytest tests/engine/test_report.py -q`
Expected: 9 passed.

- [ ] **Step 3: Commit**

```bash
git add src/foodbrew/engine/report.py tests/engine/test_report.py
git commit -m "feat(engine): render the handoff report as markdown"
```

---

## Task 8: `store/audit.py` — every reference edit leaves a trace

**Files:**
- Create: `src/foodbrew/store/audit.py`
- Create: `tests/store/test_audit.py`

- [ ] **Step 1: Write the module**

```python
"""Spec §5.2 audit_event. Every write to a reference record leaves one of these.

`record` deliberately does NOT commit. The trace and the change it describes are
one transaction, and a writer that committed here would leave a window where the
audit row exists and the edit does not — or the reverse, if the caller then
failed. The caller commits both together.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass

from foodbrew.store.clock import now_iso

#: Spec §3 — single user, no auth on localhost. Recorded anyway so the column
#: means something the day there is a second actor.
DEFAULT_ACTOR = "founder"


@dataclass(frozen=True, slots=True)
class AuditEvent:
    id: int
    actor: str
    action: str
    entity: str
    before: dict | None
    after: dict | None
    timestamp: str


def _dump(payload: Mapping | None) -> str | None:
    if payload is None:
        return None
    return json.dumps(dict(payload), sort_keys=True, default=str)


def record(
    conn: sqlite3.Connection,
    *,
    action: str,
    entity: str,
    before: Mapping | None = None,
    after: Mapping | None = None,
    actor: str = DEFAULT_ACTOR,
) -> None:
    """`entity` is `<table>:<id>` — the schema has no separate entity_id column."""
    conn.execute(
        "INSERT INTO audit_event (actor, action, entity, before_json, after_json, timestamp)"
        " VALUES (?,?,?,?,?,?)",
        (actor, action, entity, _dump(before), _dump(after), now_iso()),
    )


def list_recent(conn: sqlite3.Connection, limit: int = 50) -> tuple[AuditEvent, ...]:
    rows = conn.execute(
        "SELECT * FROM audit_event ORDER BY timestamp DESC, id DESC LIMIT ?", (limit,)
    ).fetchall()
    return tuple(
        AuditEvent(
            id=row["id"], actor=row["actor"], action=row["action"], entity=row["entity"],
            before=json.loads(row["before_json"]) if row["before_json"] else None,
            after=json.loads(row["after_json"]) if row["after_json"] else None,
            timestamp=row["timestamp"],
        )
        for row in rows
    )
```

- [ ] **Step 2: Test it**

`tests/store/test_audit.py`:

```python
from foodbrew.store import audit


def test_an_event_round_trips_with_both_sides(conn):
    audit.record(
        conn, action="update", entity="enzyme:lactase_fungal_acid",
        before={"ph_min": 2.5}, after={"ph_min": 3.0},
    )
    conn.commit()
    events = audit.list_recent(conn)
    assert len(events) == 1
    assert events[0].entity == "enzyme:lactase_fungal_acid"
    assert events[0].before == {"ph_min": 2.5}
    assert events[0].after == {"ph_min": 3.0}
    assert events[0].actor == "founder"


def test_recording_does_not_commit_on_its_own(db_path):
    """The trace and the change it describes are one transaction."""
    from foodbrew.store.connection import connect

    with connect(db_path) as writer:
        audit.record(writer, action="update", entity="food:milk")
        writer.rollback()

    with connect(db_path) as reader:
        assert audit.list_recent(reader) == ()


def test_the_newest_event_comes_first(conn):
    for n in range(3):
        audit.record(conn, action="update", entity=f"enzyme:e{n}")
    conn.commit()
    assert [e.entity for e in audit.list_recent(conn)][0] == "enzyme:e2"


def test_a_reset_records_no_after_side(conn):
    audit.record(conn, action="reset", entity="food:milk", before={"ph": 7.0})
    conn.commit()
    assert audit.list_recent(conn)[0].after is None
```

There is no `tests/store/conftest.py`: `tests/api/conftest.py` defines `db_path` and `conn` for the API tests, and each existing `tests/store/test_*.py` defines its own local `conn(tmp_path)`. Move the shared pair up into `tests/conftest.py` so the new store tests can use them — the local fixtures in the existing files shadow the root ones and keep working untouched:

```python
@pytest.fixture
def db_path(tmp_path):
    from foodbrew.db import create_database

    return create_database(tmp_path / "foodbrew.db")


@pytest.fixture
def conn(db_path):
    from foodbrew.store.connection import connect

    with connect(db_path) as c:
        yield c
```

and delete the two duplicated fixtures from `tests/api/conftest.py`, keeping `client` and `vinaigrette` there.

Run: `.venv/bin/pytest tests/store tests/api -q`
Expected: green, including every M2 store and API test that used the moved fixtures.

- [ ] **Step 3: Commit**

```bash
git add src/foodbrew/store/audit.py tests/store/test_audit.py tests/conftest.py tests/api/conftest.py
git commit -m "feat(store): record an audit event for every reference change"
```

---

## Task 9: `store/variants.py` — freeze the suggestions with their evaluation

**Files:**
- Create: `src/foodbrew/store/variants.py`
- Modify: `src/foodbrew/store/evaluations.py`
- Create: `tests/store/test_variant_store.py`

- [ ] **Step 1: Write the persistence module**

```python
"""Spec §5.2 variant_suggestion. Written once, with the evaluation, never updated.

A suggestion is an action offered, not a display: pressing the button mutates
the database, so the patch that gets applied has to be the patch the founder was
looking at. That is why these are frozen alongside the findings rather than
recomputed on read the way dose cards are (plan decision #3).

The table has no column for `triggered_by` and plan decision #1 forbids adding
one, so `patch_json` carries the whole machine payload — `{"ops": [...],
"raised_by": [...]}` — rather than only the ops. `patch.apply_patch` reads
`ops` and ignores every other key, so the extra field costs nothing there, and
the report gets the rules that asked for a change without the description
having to spell them out in prose.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from foodbrew.engine.variants import Suggestion


@dataclass(frozen=True, slots=True)
class StoredSuggestion:
    id: int
    evaluation_id: str
    suggestion_type: str
    description: str
    #: The rule ids that asked for this change.
    raised_by: tuple[str, ...]
    #: Empty for a note — there is nothing to apply.
    ops: tuple[dict, ...]
    created_at: str

    @property
    def is_applicable(self) -> bool:
        return bool(self.ops)

    @property
    def patch(self) -> dict | None:
        return {"ops": [dict(op) for op in self.ops]} if self.ops else None


def _payload(suggestion: Suggestion) -> dict:
    return {
        "ops": list(suggestion.patch["ops"]) if suggestion.patch else [],
        "raised_by": list(suggestion.triggered_by),
    }


def write(
    conn: sqlite3.Connection,
    evaluation_id: str,
    suggestions: Sequence[Suggestion],
    created_at: str,
) -> None:
    conn.executemany(
        "INSERT INTO variant_suggestion (evaluation_id, suggestion_type, description,"
        " patch_json, created_at) VALUES (?,?,?,?,?)",
        [
            (
                evaluation_id,
                suggestion.suggestion_type.value,
                suggestion.description,
                json.dumps(_payload(suggestion), sort_keys=True, separators=(",", ":")),
                created_at,
            )
            for suggestion in suggestions
        ],
    )


def _row(row: sqlite3.Row) -> StoredSuggestion:
    payload = json.loads(row["patch_json"]) or {}
    return StoredSuggestion(
        id=row["id"],
        evaluation_id=row["evaluation_id"],
        suggestion_type=row["suggestion_type"],
        description=row["description"],
        raised_by=tuple(payload.get("raised_by", ())),
        ops=tuple(payload.get("ops") or ()),
        created_at=row["created_at"],
    )


def list_for_evaluation(
    conn: sqlite3.Connection, evaluation_id: str
) -> tuple[StoredSuggestion, ...]:
    return tuple(
        _row(row)
        for row in conn.execute(
            "SELECT * FROM variant_suggestion WHERE evaluation_id = ? ORDER BY id",
            (evaluation_id,),
        )
    )


def get(conn: sqlite3.Connection, suggestion_id: int) -> StoredSuggestion | None:
    row = conn.execute(
        "SELECT * FROM variant_suggestion WHERE id = ?", (suggestion_id,)
    ).fetchone()
    return _row(row) if row else None
```

- [ ] **Step 2: Wire it into the run path**

In `store/evaluations.py`, add the imports and one field:

```python
from foodbrew.engine.variants import suggest
from foodbrew.store import variants as variant_store
from foodbrew.store.variants import StoredSuggestion
...
@dataclass(frozen=True, slots=True)
class StoredEvaluation:
    ...
    advisories: tuple[RuleFinding, ...]
    suggestions: tuple[StoredSuggestion, ...] = ()
```

In `run`, between the `rule_finding` insert and the commit:

```python
    variant_store.write(conn, evaluation_id, suggest(ctx, result.findings), created_at)
    conn.commit()

    return _assemble(
        ...,
        suggestions=variant_store.list_for_evaluation(conn, evaluation_id),
    )
```

In `get`, after building `findings`:

```python
        suggestions=variant_store.list_for_evaluation(conn, evaluation_id),
```

and give `_assemble` the extra keyword, defaulting to `()` so `list_recent`'s summary path stays cheap — it goes through `get`, so it gets them anyway; the default exists for callers that do not.

- [ ] **Step 3: Test it**

`tests/store/test_variant_store.py`:

```python
"""Spec §5.2 and plan decision #3."""

from foodbrew.store import evaluations, formulations, recipes, variants


def _vinaigrette(conn, **overrides):
    recipe_id = recipes.create(conn, name="v", notes="", ingredients=[
        {"food_id": "olive_oil", "amount_g": 100.0, "order": 1},
        {"food_id": "white_vinegar", "amount_g": 50.0, "order": 2},
    ])
    payload = dict(
        recipe_id=recipe_id, format="premixed_wet",
        target_trigger_food_ids=["milk"], application_food_ids=[],
        dwell_profile=None,
        enzymes=[{"enzyme_id": "lactase_fungal_acid", "dose": 9000.0, "phase": "wet",
                  "encapsulated": False, "source_choice": ""}],
        serving_size_g=30.0, measured_ph=3.0, process_steps=[],
        enzyme_addition_index=None, parent_formulation_id=None,
    )
    payload.update(overrides)
    return formulations.create(conn, **payload)


def test_running_an_evaluation_freezes_its_suggestions(conn):
    stored = evaluations.run(conn, _vinaigrette(conn))
    assert stored.suggestions
    assert {s.evaluation_id for s in stored.suggestions} == {stored.id}


def test_reading_an_evaluation_returns_the_same_suggestions(conn):
    stored = evaluations.run(conn, _vinaigrette(conn))
    reread = evaluations.get(conn, stored.id)
    assert [s.id for s in reread.suggestions] == [s.id for s in stored.suggestions]
    assert [s.description for s in reread.suggestions] == [
        s.description for s in stored.suggestions
    ]


def test_a_note_is_stored_with_no_patch(conn):
    stored = evaluations.run(conn, _vinaigrette(conn))
    notes = [s for s in stored.suggestions if s.suggestion_type == "supplier_question"]
    assert notes and all(n.patch is None and not n.is_applicable for n in notes)


def test_an_applicable_suggestion_keeps_its_ops(conn):
    stored = evaluations.run(conn, _vinaigrette(conn))
    formats = [s for s in stored.suggestions if s.suggestion_type == "format_change"]
    assert formats
    assert all(f.patch["ops"][0]["op"] == "set_format" for f in formats)


def test_the_rules_that_asked_survive_the_round_trip(conn):
    """There is no column for them, so they ride in patch_json (decision #1)."""
    stored = evaluations.run(conn, _vinaigrette(conn))
    assert any("R1" in s.raised_by for s in stored.suggestions)
    assert all(s.raised_by for s in stored.suggestions)


def test_editing_a_record_does_not_change_a_stored_suggestion(conn):
    """§4: later edits never mutate a stored evaluation, suggestions included."""
    formulation_id = _vinaigrette(conn)
    first = evaluations.run(conn, formulation_id)
    conn.execute(
        "UPDATE enzyme SET ph_shelf_stable_min = 2.5,"
        " ph_shelf_stable_min_status = 'confirmed' WHERE id = 'lactase_fungal_acid'"
    )
    conn.commit()
    second = evaluations.run(conn, formulation_id)
    reread = evaluations.get(conn, first.id)

    assert [s.description for s in reread.suggestions] == [
        s.description for s in first.suggestions
    ]
    assert [s.description for s in second.suggestions] != [
        s.description for s in first.suggestions
    ]


def test_a_suggestion_can_be_fetched_by_id(conn):
    stored = evaluations.run(conn, _vinaigrette(conn))
    one = stored.suggestions[0]
    assert variants.get(conn, one.id) == one
    assert variants.get(conn, 10_000) is None
```

Run: `.venv/bin/pytest tests/store -q`
Expected: green.

- [ ] **Step 4: Commit**

```bash
git add src/foodbrew/store/variants.py src/foodbrew/store/evaluations.py tests/store/test_variant_store.py
git commit -m "feat(store): freeze auto-variant suggestions with their evaluation"
```

---

## Task 10: Snapshot diffing and the stale-evaluation signal

M2 Task 5 made the snapshot byte-stable so that "has this evaluation's input changed" is a string comparison. This is where that gets spent (plan decision #9).

**Files:**
- Modify: `src/foodbrew/store/snapshot.py`, `src/foodbrew/store/evaluations.py`
- Create: `tests/store/test_staleness.py`

- [ ] **Step 1: Add `diff_snapshots` to `store/snapshot.py`**

```python
@dataclass(frozen=True, slots=True)
class SnapshotChange:
    """One field that moved between two snapshots of the same formulation."""

    #: "enzyme" | "food" | "substrate" | "formulation" | "gi_regions" | "latest_trial_ph"
    kind: str
    record_id: str
    field: str
    before: Any
    after: Any


_RECORD_SECTIONS = (("enzymes", "enzyme"), ("foods", "food"), ("substrates", "substrate"))


def _record_changes(kind: str, old: Mapping, new: Mapping) -> list[SnapshotChange]:
    changes: list[SnapshotChange] = []
    for record_id in sorted(set(old) | set(new)):
        before, after = old.get(record_id), new.get(record_id)
        if before is None:
            changes.append(SnapshotChange(kind, record_id, "*", None, "added"))
            continue
        if after is None:
            changes.append(SnapshotChange(kind, record_id, "*", "removed", None))
            continue
        for name in sorted(set(before) | set(after)):
            if before.get(name) != after.get(name):
                changes.append(
                    SnapshotChange(kind, record_id, name, before.get(name), after.get(name))
                )
    return changes


def diff_snapshots(old_json: str, new_json: str) -> tuple[SnapshotChange, ...]:
    """Field-level diff, so a stale banner can name what moved (plan decision #9)."""
    old, new = json.loads(old_json), json.loads(new_json)
    changes: list[SnapshotChange] = []

    for section, kind in _RECORD_SECTIONS:
        changes += _record_changes(kind, old.get(section, {}), new.get(section, {}))

    old_form, new_form = old.get("formulation", {}), new.get("formulation", {})
    for name in sorted(set(old_form) | set(new_form)):
        if old_form.get(name) != new_form.get(name):
            changes.append(
                SnapshotChange(
                    "formulation", old_form.get("id", ""), name,
                    old_form.get(name), new_form.get(name),
                )
            )

    for section in ("gi_regions", "latest_trial_ph"):
        if old.get(section) != new.get(section):
            changes.append(
                SnapshotChange(section, "", "*", old.get(section), new.get(section))
            )

    return tuple(changes)
```

Add `Any` to the `typing` imports and `dataclass` to the `dataclasses` import at the top of the file.

- [ ] **Step 2: Add `freshness` to `store/evaluations.py`**

```python
def freshness(
    conn: sqlite3.Connection, stored: StoredEvaluation
) -> tuple[bool, tuple[SnapshotChange, ...]]:
    """Has anything this evaluation read changed since it ran?

    Cheap because M2 made the snapshot byte-stable: freeze the formulation's
    current context and compare two strings. Called from the evaluation detail
    endpoint only — a list of summaries would otherwise mean one full catalogue
    hydration per row (plan decision #9).
    """
    try:
        ctx = hydrate_context(conn, stored.formulation_id)
    except ValidationRejection:
        # The formulation is gone. Nothing can be re-run, so nothing is fresh.
        return True, ()

    current = snapshot_from_context(ctx)
    if current == stored.input_snapshot_json:
        return False, ()
    return True, diff_snapshots(stored.input_snapshot_json, current)
```

with `from foodbrew.engine import ValidationRejection` and `from foodbrew.store.snapshot import SnapshotChange, diff_snapshots, snapshot_from_context` added to the imports.

- [ ] **Step 3: Test it**

`tests/store/test_staleness.py`:

```python
"""Spec §10 screen 4's banner, and plan decision #9."""

import json

from foodbrew.store import evaluations
from foodbrew.store.snapshot import diff_snapshots

from tests.store.test_variant_store import _vinaigrette


def test_an_untouched_evaluation_is_fresh(conn):
    stored = evaluations.run(conn, _vinaigrette(conn))
    assert evaluations.freshness(conn, stored) == (False, ())


def test_re_running_does_not_make_the_first_run_stale(conn):
    formulation_id = _vinaigrette(conn)
    first = evaluations.run(conn, formulation_id)
    evaluations.run(conn, formulation_id)
    assert evaluations.freshness(conn, first)[0] is False


def test_editing_a_referenced_enzyme_makes_it_stale_and_names_the_field(conn):
    stored = evaluations.run(conn, _vinaigrette(conn))
    conn.execute(
        "UPDATE enzyme SET ph_shelf_stable_min = 2.5,"
        " ph_shelf_stable_min_status = 'confirmed',"
        " ph_shelf_stable_min_source = 'supplier spec' WHERE id = 'lactase_fungal_acid'"
    )
    conn.commit()

    stale, changes = evaluations.freshness(conn, stored)
    assert stale
    assert [(c.kind, c.record_id, c.field) for c in changes] == [
        ("enzyme", "lactase_fungal_acid", "ph_shelf_stable_min")
    ]
    assert changes[0].after["value"] == 2.5


def test_editing_an_unreferenced_record_leaves_it_fresh(conn):
    """The snapshot holds the referenced closure, not the whole catalogue."""
    stored = evaluations.run(conn, _vinaigrette(conn))
    conn.execute("UPDATE enzyme SET notes = 'edited' WHERE id = 'amylase'")
    conn.commit()
    assert evaluations.freshness(conn, stored)[0] is False


def test_editing_a_referenced_food_is_caught(conn):
    stored = evaluations.run(conn, _vinaigrette(conn))
    conn.execute(
        "UPDATE food SET water_content_pct = 95.0,"
        " water_content_pct_status = 'user_provided' WHERE id = 'white_vinegar'"
    )
    conn.commit()
    stale, changes = evaluations.freshness(conn, stored)
    assert stale
    assert changes[0].record_id == "white_vinegar"


def test_the_diff_reports_an_added_record():
    empty = {"enzymes": {}, "foods": {}, "substrates": {}, "formulation": {}}
    added = {**empty, "enzymes": {"amylase": {"name": "Amylase"}}}
    changes = diff_snapshots(json.dumps(empty), json.dumps(added))
    assert (changes[0].kind, changes[0].record_id, changes[0].after) == (
        "enzyme", "amylase", "added"
    )


def test_two_identical_snapshots_report_nothing(conn):
    stored = evaluations.run(conn, _vinaigrette(conn))
    assert diff_snapshots(stored.input_snapshot_json, stored.input_snapshot_json) == ()
```

Run: `.venv/bin/pytest tests/store/test_staleness.py -q`
Expected: 7 passed. If `test_re_running_does_not_make_the_first_run_stale` fails, the snapshot is not byte-stable and M2's exit criteria were not actually met — fix that before going further, because the banner will flap on every page load.

- [ ] **Step 4: Commit**

```bash
git add src/foodbrew/store/snapshot.py src/foodbrew/store/evaluations.py tests/store/test_staleness.py
git commit -m "feat(store): detect and describe stale evaluations from the snapshot"
```
---

## Task 11: `store/records.py` — the database editor's writes and reset to baseline

Workflow D. Two truth labels down two paths (decision #7), a closed column allowlist (decision #16), and a per-record reset that refuses a custom food (decision #8).

**Files:**
- Modify: `src/foodbrew/store/rowmap.py`, `src/foodbrew/db/bootstrap.py`
- Create: `src/foodbrew/store/records.py`
- Create: `tests/store/test_records.py`
- Modify: `tests/store/test_rowmap.py`

- [ ] **Step 1: Give `rowmap` its inverse**

Reset writes the same row seeding writes. Two hand-built row dicts would drift the first time a column is added, so the builders move next to the readers they mirror. Append to `store/rowmap.py`:

```python
def tracked_columns(prefix: str, value: Tracked) -> dict:
    """The inverse of `tracked`. A boolean Tracked stores as SQLite INTEGER."""
    raw = value.value
    if isinstance(raw, bool):
        raw = int(raw)
    return {prefix: raw, f"{prefix}_status": value.status.value, f"{prefix}_source": value.source}


def substrate_to_row(s: Substrate) -> dict:
    return {
        "id": s.id, "name": s.name,
        "native_human_enzyme": int(s.native_human_enzyme),
        "is_prebiotic": int(s.is_prebiotic),
        "no_commercial_enzyme": int(s.no_commercial_enzyme),
        "notes": s.notes,
    }


def gi_region_to_row(r: GIRegion) -> dict:
    return {
        "id": r.id, "name": r.name, "ph_low": r.ph_low, "ph_high": r.ph_high,
        "order": r.order, "dormant": int(r.dormant), "transit_note": r.transit_note,
    }


def enzyme_to_row(e: Enzyme) -> dict:
    row = {
        "id": e.id, "name": e.name, "aliases_json": json.dumps(list(e.aliases)),
        "substrate_id": e.substrate_id, "source_type": e.source_type,
        "priority": e.priority, "deadline": e.deadline.value,
        "site_of_action": e.site_of_action, "dose_unit": e.dose_unit,
        "dose_benchmark_note": e.dose_benchmark_note,
        "is_protease": int(e.is_protease), "is_natural_source": int(e.is_natural_source),
        "food_grade_note": e.food_grade_note, "heat_labile_note": e.heat_labile_note,
        "degrades_structural_json": json.dumps([
            {"structural_class": x.structural_class.value, "tier": x.tier.value}
            for x in e.degrades_structural
        ]),
        "cost_tier": e.cost_tier, "supplier_note": e.supplier_note, "notes": e.notes,
    }
    for prefix in ENZYME_TRACKED:
        row.update(tracked_columns(prefix, getattr(e, prefix)))
    return row


def food_to_row(f: Food) -> dict:
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
    for prefix in FOOD_TRACKED:
        row.update(tracked_columns(prefix, getattr(f, prefix)))
    return row
```

Then rewrite `db/bootstrap.load_reference_data` to use them, deleting the four inline row dicts and the local `_tracked_cols`:

```python
from foodbrew.store.rowmap import (
    enzyme_to_row, food_to_row, gi_region_to_row, substrate_to_row,
)


def load_reference_data(conn: sqlite3.Connection, seed: Seed) -> None:
    for s in seed.substrates.values():
        _insert(conn, "substrate", substrate_to_row(s))
    for r in seed.gi_regions:
        _insert(conn, "gi_region", gi_region_to_row(r))
    for e in seed.enzymes.values():
        _insert(conn, "enzyme", enzyme_to_row(e))
    for f in seed.foods.values():
        _insert(conn, "food", food_to_row(f))
```

`db` importing `store.rowmap` is a new edge and the right direction: `rowmap` is the row↔dataclass mapper and imports nothing but `engine.types`, so there is no cycle and no layering inversion.

Add the round-trip to `tests/store/test_rowmap.py`:

```python
def test_a_seed_record_round_trips_through_its_row(seed):
    """The reader and the writer are inverses, which is what makes reset faithful."""
    import sqlite3

    from foodbrew.store.rowmap import enzyme_from_row, enzyme_to_row, food_from_row, food_to_row

    for record, to_row, from_row in (
        (seed.enzymes["lactase_fungal_acid"], enzyme_to_row, enzyme_from_row),
        (seed.foods["milk"], food_to_row, food_from_row),
    ):
        row = to_row(record)
        # sqlite3.Row is not constructible directly; a plain dict has the same
        # __getitem__ contract the mappers use.
        assert from_row(row) == record
```

If `from_row` needs a real `sqlite3.Row`, insert the dict into a scratch in-memory database and read it back instead — the point of the test is that the pair are inverses, not how the row is obtained.

- [ ] **Step 2: Write `store/records.py`**

```python
"""Workflow D — the database editor's writes, and reset to baseline.

Two truth labels down two paths (plan decision #7). A direct edit here writes
`user_provided`, because §5.4 makes `confirmed` mean "verified against a named
source" and a web form is not one. `set_confirmed` exists for exactly one
caller — an approved proposal, which carries the citation that goes in the
paired `*_source` column.

Column names cannot be bound as SQL parameters, so every name that reaches an
f-string comes from the allowlists below and every value is bound (decision
#16). The same allowlists are the type map `store/proposals.py` parses a
proposal's TEXT value with, so the two writers cannot disagree about what
`ph_min` is.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from typing import Any

from foodbrew.engine import ValidationRejection
from foodbrew.engine.types import TruthLabel
from foodbrew.seedload.loader import load_seed
from foodbrew.store import audit
from foodbrew.store.foods import CUSTOM_SOURCE
from foodbrew.store.rowmap import enzyme_to_row, food_to_row

EDITABLE_TABLES = ("enzyme", "food")

#: Tracked columns: writing one writes its `_status` and `_source` too.
TRACKED_FIELDS: Mapping[str, Mapping[str, type]] = {
    "enzyme": {
        "ph_min": float, "ph_max": float, "ph_opt_low": float, "ph_opt_high": float,
        "ph_shelf_stable_min": float, "temp_min_c": float, "temp_max_c": float,
        "temp_opt_c": float, "dose_min": float, "dose_max": float,
        "dose_evidence_threshold": float, "is_gras": bool,
    },
    "food": {"ph": float, "water_content_pct": float, "typical_load_value": float},
}

#: Plain columns: free text the founder owns, carrying no truth label of its own.
PLAIN_FIELDS: Mapping[str, Mapping[str, type]] = {
    "enzyme": {
        "notes": str, "supplier_note": str, "dose_unit": str,
        "dose_benchmark_note": str, "food_grade_note": str, "cost_tier": str,
    },
    "food": {"notes": str, "category": str, "typical_load_unit": str},
}


def check_table(table: str) -> None:
    if table not in EDITABLE_TABLES:
        raise ValidationRejection(f"'{table}' is not an editable table.")


def field_type(table: str, field: str) -> type:
    check_table(table)
    for group in (TRACKED_FIELDS, PLAIN_FIELDS):
        if field in group[table]:
            return group[table][field]
    raise ValidationRejection(f"'{field}' cannot be edited on a {table} record.")


def coerce(table: str, field: str, raw: Any) -> Any:
    """Parse an incoming value to the column's type, or refuse it in plain English."""
    expected = field_type(table, field)
    if expected is bool:
        if isinstance(raw, str):
            lowered = raw.strip().lower()
            if lowered in {"true", "yes", "1"}:
                return True
            if lowered in {"false", "no", "0"}:
                return False
            raise ValidationRejection(f"'{field}': enter yes or no.")
        return bool(raw)
    if expected is float:
        try:
            return float(raw)
        except (TypeError, ValueError) as exc:
            raise ValidationRejection(f"'{field}': enter a number.") from exc
    # A plain text column is NOT NULL DEFAULT '', and clearing a note through
    # the editor sends null. `str(None)` would put the four characters "None"
    # in the column and the founder would read it back as her own note.
    return "" if raw is None else str(raw)


def _row_snapshot(conn: sqlite3.Connection, table: str, record_id: str) -> dict:
    row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (record_id,)).fetchone()
    if row is None:
        raise ValidationRejection(f"No {table} '{record_id}'.")
    return dict(row)


def _replace(conn: sqlite3.Connection, table: str, row: Mapping) -> None:
    columns = ", ".join(f'"{c}"' for c in row)
    placeholders = ", ".join("?" for _ in row)
    conn.execute(
        f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})",
        tuple(row.values()),
    )


def update(
    conn: sqlite3.Connection, table: str, record_id: str, fields: Mapping[str, Any]
) -> None:
    """A founder edit. Every value written here is `user_provided` (decision #7)."""
    check_table(table)
    before = _row_snapshot(conn, table, record_id)

    assignments: list[str] = []
    values: list[Any] = []
    for field, raw in fields.items():
        if field in TRACKED_FIELDS[table]:
            assignments += [f'"{field}" = ?', f'"{field}_status" = ?', f'"{field}_source" = ?']
            if raw is None:
                values += [None, TruthLabel.UNCONFIRMED.value, ""]
            else:
                parsed = coerce(table, field, raw)
                values += [
                    int(parsed) if isinstance(parsed, bool) else parsed,
                    TruthLabel.USER_PROVIDED.value,
                    CUSTOM_SOURCE,
                ]
        else:
            # Coerce first: `coerce` is what rejects a field outside the
            # allowlist, and it has to raise before anything is appended.
            value = coerce(table, field, raw)
            assignments.append(f'"{field}" = ?')
            values.append(value)

    if not assignments:
        raise ValidationRejection("Nothing to change.")

    conn.execute(
        f"UPDATE {table} SET {', '.join(assignments)} WHERE id = ?",
        (*values, record_id),
    )
    audit.record(
        conn, action="update", entity=f"{table}:{record_id}",
        before=before, after=_row_snapshot(conn, table, record_id),
    )
    conn.commit()


def set_confirmed(
    conn: sqlite3.Connection, table: str, record_id: str, field: str, raw: Any, source: str
) -> None:
    """The only path to `confirmed` — an approved proposal with a citation (§2.3, §5.4)."""
    if field not in TRACKED_FIELDS.get(table, {}):
        raise ValidationRejection(f"'{field}' does not carry a source, so it cannot be confirmed.")
    if not source.strip():
        raise ValidationRejection("A confirmed value needs a source citation.")

    before = _row_snapshot(conn, table, record_id)
    parsed = coerce(table, field, raw)
    conn.execute(
        f'UPDATE {table} SET "{field}" = ?, "{field}_status" = ?, "{field}_source" = ?'
        " WHERE id = ?",
        (
            int(parsed) if isinstance(parsed, bool) else parsed,
            TruthLabel.CONFIRMED.value,
            source,
            record_id,
        ),
    )
    audit.record(
        conn, action="confirm", entity=f"{table}:{record_id}",
        before=before, after=_row_snapshot(conn, table, record_id),
    )


def reset_record(conn: sqlite3.Connection, table: str, record_id: str) -> None:
    """Workflow D's reset-to-baseline, one record at a time (plan decision #8)."""
    check_table(table)
    seed = load_seed()
    catalogue = seed.enzymes if table == "enzyme" else seed.foods
    record = catalogue.get(record_id)
    if record is None:
        raise ValidationRejection(
            f"'{record_id}' is not in the shipped catalogue, so it has no baseline to "
            f"go back to. Edit the values you want to change instead."
        )

    before = _row_snapshot(conn, table, record_id)
    row = enzyme_to_row(record) if table == "enzyme" else food_to_row(record)
    _replace(conn, table, row)
    audit.record(
        conn, action="reset", entity=f"{table}:{record_id}", before=before, after=dict(row)
    )
    conn.commit()


def reset_all(conn: sqlite3.Connection) -> None:
    """Destructive: discards every edit to every enzyme and food row.

    Substrates and GI regions are not editable and are left alone; the boot-time
    `create_database` path is still what refreshes those.
    """
    seed = load_seed()
    for enzyme in seed.enzymes.values():
        _replace(conn, "enzyme", enzyme_to_row(enzyme))
    for food in seed.foods.values():
        _replace(conn, "food", food_to_row(food))
    audit.record(conn, action="reset_all", entity="reference")
    conn.commit()
```

Note `set_confirmed` does **not** commit: `store/proposals.approve` writes the value and the proposal's status in one transaction.

- [ ] **Step 3: Test it**

`tests/store/test_records.py`:

```python
"""Workflow D, and plan decisions #7, #8 and #16."""

import pytest

from foodbrew.engine import ValidationRejection
from foodbrew.store import audit, foods, records
from foodbrew.store.reference import load_catalog


def _enzyme(conn, enzyme_id="lactase_fungal_acid"):
    return load_catalog(conn).enzymes[enzyme_id]


def test_a_founder_edit_is_user_provided_not_confirmed(conn):
    records.update(conn, "enzyme", "lactase_fungal_acid", {"ph_shelf_stable_min": 3.4})
    field = _enzyme(conn).ph_shelf_stable_min
    assert (field.value, field.status.value) == (3.4, "user_provided")
    assert field.source == "entered by founder"


def test_clearing_a_value_returns_it_to_unconfirmed(conn):
    records.update(conn, "enzyme", "lactase_fungal_acid", {"ph_shelf_stable_min": 3.4})
    records.update(conn, "enzyme", "lactase_fungal_acid", {"ph_shelf_stable_min": None})
    field = _enzyme(conn).ph_shelf_stable_min
    assert (field.value, field.status.value, field.source) == (None, "unconfirmed", "")


def test_a_boolean_tracked_field_survives_the_round_trip(conn):
    records.update(conn, "enzyme", "lactase_fungal_acid", {"is_gras": "yes"})
    assert _enzyme(conn).is_gras.value is True


def test_a_plain_field_carries_no_label(conn):
    records.update(conn, "enzyme", "lactase_fungal_acid", {"supplier_note": "Amano quote 08/26"})
    assert _enzyme(conn).supplier_note == "Amano quote 08/26"


def test_clearing_a_note_empties_it_rather_than_writing_the_word_none(conn):
    records.update(conn, "enzyme", "lactase_fungal_acid", {"supplier_note": "Amano quote"})
    records.update(conn, "enzyme", "lactase_fungal_acid", {"supplier_note": None})
    assert _enzyme(conn).supplier_note == ""


@pytest.mark.parametrize("table, field", [
    ("enzyme", "id"),
    ("enzyme", "substrate_id"),
    ("enzyme", "ph_min_status"),
    ("food", "is_trigger_food"),
    ("food", "id"),
])
def test_fields_outside_the_allowlist_are_refused(conn, table, field):
    with pytest.raises(ValidationRejection):
        records.update(conn, table, "lactase_fungal_acid" if table == "enzyme" else "milk",
                       {field: "x"})


def test_an_unknown_table_is_refused(conn):
    with pytest.raises(ValidationRejection):
        records.update(conn, "evaluation", "anything", {"notes": "x"})


def test_a_non_numeric_value_is_refused_in_plain_english(conn):
    with pytest.raises(ValidationRejection) as excinfo:
        records.update(conn, "enzyme", "lactase_fungal_acid", {"ph_min": "acidic"})
    assert "enter a number" in str(excinfo.value)


def test_every_edit_leaves_an_audit_event(conn):
    records.update(conn, "food", "milk", {"ph": 6.7})
    event = audit.list_recent(conn)[0]
    assert (event.action, event.entity) == ("update", "food:milk")
    assert event.before["ph"] != event.after["ph"]


def test_reset_restores_the_shipped_value_and_its_label(conn):
    original = _enzyme(conn).ph_min
    records.update(conn, "enzyme", "lactase_fungal_acid", {"ph_min": 1.0})
    records.reset_record(conn, "enzyme", "lactase_fungal_acid")
    assert _enzyme(conn).ph_min == original
    assert audit.list_recent(conn)[0].action == "reset"


def test_a_custom_food_has_no_baseline_to_reset_to(conn):
    food_id = foods.create_custom(
        conn, name="Her vinaigrette base", category="", is_recipe_ingredient=True,
        is_trigger_food=False, is_application_food=False, ph=3.1, water_content_pct=60.0,
        typical_load_value=None, typical_load_unit="", contains_substrate_ids=[],
        structural=[], contains_protease=False, is_heat_processed=False, notes="",
    )
    with pytest.raises(ValidationRejection) as excinfo:
        records.reset_record(conn, "food", food_id)
    assert "no baseline" in str(excinfo.value)


def test_reset_all_discards_every_edit(conn):
    records.update(conn, "enzyme", "lactase_fungal_acid", {"ph_min": 1.0})
    records.update(conn, "food", "milk", {"ph": 1.0})
    records.reset_all(conn)
    catalog = load_catalog(conn)
    assert catalog.enzymes["lactase_fungal_acid"].ph_min.value != 1.0
    assert catalog.foods["milk"].ph.value != 1.0
    assert audit.list_recent(conn)[0].action == "reset_all"


def test_set_confirmed_needs_a_citation(conn):
    with pytest.raises(ValidationRejection):
        records.set_confirmed(conn, "enzyme", "lactase_fungal_acid", "temp_max_c", 55.0, "  ")


def test_set_confirmed_records_the_citation_as_the_source(conn):
    records.set_confirmed(
        conn, "enzyme", "lactase_fungal_acid", "temp_max_c", 55.0, "Amano datasheet 2026"
    )
    conn.commit()
    field = _enzyme(conn).temp_max_c
    assert (field.value, field.status.value, field.source) == (
        55.0, "confirmed", "Amano datasheet 2026"
    )


def test_a_plain_field_cannot_be_confirmed(conn):
    """Only a tracked field has a paired source column to record the citation in."""
    with pytest.raises(ValidationRejection):
        records.set_confirmed(conn, "enzyme", "lactase_fungal_acid", "notes", "x", "a source")
```

Run: `.venv/bin/pytest tests/store -q`
Expected: green, including the round-trip added to `test_rowmap.py`.

- [ ] **Step 4: Commit**

```bash
git add src/foodbrew/store/records.py src/foodbrew/store/rowmap.py src/foodbrew/db/bootstrap.py tests/store
git commit -m "feat(store): add the database editor's writes and reset to baseline"
```

---

## Task 12: `store/proposals.py` — the inbox, and the only road to `confirmed`

§2.3's research track lands here: a proposal carries a value *and* a citation, and approving it is what flips a field from `unconfirmed` to `confirmed` with provenance recorded (decision #7).

**Files:**
- Create: `src/foodbrew/store/proposals.py`
- Create: `tests/store/test_proposals.py`

- [ ] **Step 1: Write the module**

```python
"""Spec §5.2 proposal, §2.3's parallel research track.

A proposal is a value plus a source. Approving one is the single path by which a
field becomes `confirmed`, which is what §5.4's definition of that label
requires and what makes §13 fixture (h2) — R12's per-enzyme promotion —
reachable through the product rather than only through raw SQL.

Rejecting a proposal changes no data. The row stays, so the answer "we looked at
this and said no" survives, which is worth more than a clean table.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from foodbrew.engine import ValidationRejection
from foodbrew.store import audit, records
from foodbrew.store.ids import new_id

PENDING, APPROVED, REJECTED = "pending", "approved", "rejected"


@dataclass(frozen=True, slots=True)
class Proposal:
    id: str
    table_name: str
    record_id: str
    field: str
    proposed_value: str | None
    source_citation: str
    status: str


def _of(row: sqlite3.Row) -> Proposal:
    return Proposal(
        id=row["id"], table_name=row["table_name"], record_id=row["record_id"],
        field=row["field"], proposed_value=row["proposed_value"],
        source_citation=row["source_citation"], status=row["status"],
    )


def create(
    conn: sqlite3.Connection,
    *,
    table_name: str,
    record_id: str,
    field: str,
    proposed_value: str,
    source_citation: str,
) -> str:
    records.check_table(table_name)
    if field not in records.TRACKED_FIELDS[table_name]:
        raise ValidationRejection(
            f"'{field}' does not carry a source, so there is nothing to confirm about it."
        )
    if conn.execute(
        f"SELECT 1 FROM {table_name} WHERE id = ?", (record_id,)
    ).fetchone() is None:
        raise ValidationRejection(f"No {table_name} '{record_id}'.")
    if not source_citation.strip():
        raise ValidationRejection(
            "A proposal needs a source citation — that citation is what makes the "
            "value confirmed rather than entered."
        )
    # Parse now, so a bad value is refused at the inbox rather than at approval.
    records.coerce(table_name, field, proposed_value)

    proposal_id = new_id()
    conn.execute(
        "INSERT INTO proposal (id, table_name, record_id, field, proposed_value,"
        " source_citation, status) VALUES (?,?,?,?,?,?,?)",
        (proposal_id, table_name, record_id, field, str(proposed_value),
         source_citation, PENDING),
    )
    conn.commit()
    return proposal_id


def get(conn: sqlite3.Connection, proposal_id: str) -> Proposal | None:
    row = conn.execute("SELECT * FROM proposal WHERE id = ?", (proposal_id,)).fetchone()
    return _of(row) if row else None


def list_all(conn: sqlite3.Connection, status: str | None = None) -> tuple[Proposal, ...]:
    if status is None:
        rows = conn.execute("SELECT * FROM proposal ORDER BY status, id")
    else:
        if status not in (PENDING, APPROVED, REJECTED):
            raise ValidationRejection(f"Unknown proposal status '{status}'.")
        rows = conn.execute(
            "SELECT * FROM proposal WHERE status = ? ORDER BY id", (status,)
        )
    return tuple(_of(row) for row in rows)


def _require_pending(conn: sqlite3.Connection, proposal_id: str) -> Proposal:
    proposal = get(conn, proposal_id)
    if proposal is None:
        raise ValidationRejection(f"No proposal '{proposal_id}'.")
    if proposal.status != PENDING:
        raise ValidationRejection(f"This proposal was already {proposal.status}.")
    return proposal


def approve(conn: sqlite3.Connection, proposal_id: str) -> Proposal:
    proposal = _require_pending(conn, proposal_id)
    records.set_confirmed(
        conn,
        proposal.table_name,
        proposal.record_id,
        proposal.field,
        proposal.proposed_value,
        proposal.source_citation,
    )
    conn.execute("UPDATE proposal SET status = ? WHERE id = ?", (APPROVED, proposal_id))
    audit.record(
        conn, action="approve_proposal", entity=f"proposal:{proposal_id}",
        before={"status": PENDING}, after={"status": APPROVED},
    )
    conn.commit()
    return get(conn, proposal_id)


def reject(conn: sqlite3.Connection, proposal_id: str) -> Proposal:
    proposal = _require_pending(conn, proposal_id)
    conn.execute("UPDATE proposal SET status = ? WHERE id = ?", (REJECTED, proposal_id))
    audit.record(
        conn, action="reject_proposal", entity=f"proposal:{proposal_id}",
        before={"status": PENDING}, after={"status": REJECTED},
    )
    conn.commit()
    return get(conn, proposal_id)
```

- [ ] **Step 2: Test it**

`tests/store/test_proposals.py`:

```python
"""Spec §2.3 and §5.2, and plan decision #7."""

import pytest

from foodbrew.engine import ValidationRejection
from foodbrew.store import proposals, records
from foodbrew.store.reference import load_catalog


def _propose(conn, **overrides):
    payload = dict(
        table_name="enzyme", record_id="lactase_fungal_acid",
        field="ph_shelf_stable_min", proposed_value="3.0",
        source_citation="Amano technical datasheet, retrieved 2026-08-14",
    )
    payload.update(overrides)
    return proposals.create(conn, **payload)


def test_a_new_proposal_is_pending(conn):
    proposal_id = _propose(conn)
    assert proposals.get(conn, proposal_id).status == "pending"
    assert [p.id for p in proposals.list_all(conn, "pending")] == [proposal_id]


def test_a_proposal_without_a_citation_is_refused(conn):
    with pytest.raises(ValidationRejection) as excinfo:
        _propose(conn, source_citation="   ")
    assert "citation" in str(excinfo.value)


def test_a_proposal_for_an_untracked_field_is_refused(conn):
    with pytest.raises(ValidationRejection):
        _propose(conn, field="notes")


def test_a_proposal_with_an_unparseable_value_is_refused_at_the_inbox(conn):
    with pytest.raises(ValidationRejection):
        _propose(conn, proposed_value="quite acidic")


def test_approving_writes_the_value_as_confirmed_with_the_citation(conn):
    proposal_id = _propose(conn)
    proposals.approve(conn, proposal_id)

    field = load_catalog(conn).enzymes["lactase_fungal_acid"].ph_shelf_stable_min
    assert (field.value, field.status.value) == (3.0, "confirmed")
    assert field.source == "Amano technical datasheet, retrieved 2026-08-14"
    assert proposals.get(conn, proposal_id).status == "approved"


def test_rejecting_changes_no_data_and_keeps_the_row(conn):
    before = load_catalog(conn).enzymes["lactase_fungal_acid"].ph_shelf_stable_min
    proposal_id = _propose(conn)
    proposals.reject(conn, proposal_id)

    assert load_catalog(conn).enzymes["lactase_fungal_acid"].ph_shelf_stable_min == before
    assert proposals.get(conn, proposal_id).status == "rejected"


def test_a_proposal_cannot_be_decided_twice(conn):
    proposal_id = _propose(conn)
    proposals.approve(conn, proposal_id)
    with pytest.raises(ValidationRejection) as excinfo:
        proposals.reject(conn, proposal_id)
    assert "already approved" in str(excinfo.value)


def test_approving_a_temperature_field_promotes_R12_for_that_enzyme(conn):
    """Spec §13 fixture (h2), reached through the product rather than raw SQL."""
    for field, value in (("temp_min_c", "30"), ("temp_max_c", "45")):
        proposals.approve(conn, _propose(conn, field=field, proposed_value=value))

    enzyme = load_catalog(conn).enzymes["lactase_fungal_acid"]
    assert enzyme.temp_min_c.status.value == "confirmed"
    assert enzyme.temp_max_c.status.value == "confirmed"


def test_a_direct_edit_still_cannot_produce_confirmed(conn):
    records.update(conn, "enzyme", "lactase_fungal_acid", {"ph_shelf_stable_min": 3.0})
    field = load_catalog(conn).enzymes["lactase_fungal_acid"].ph_shelf_stable_min
    assert field.status.value == "user_provided"
```

Run: `.venv/bin/pytest tests/store/test_proposals.py -q`
Expected: 9 passed.

- [ ] **Step 3: Commit**

```bash
git add src/foodbrew/store/proposals.py tests/store/test_proposals.py
git commit -m "feat(store): add the proposals inbox and the confirmed-value path"
```

---

## Task 13: `store/formulations.clone_with_patch` — applying a variant

**Files:**
- Modify: `src/foodbrew/store/formulations.py`
- Create: `tests/store/test_clone.py`

- [ ] **Step 1: Add the clone**

```python
def clone_with_patch(
    conn: sqlite3.Connection, formulation_id: str, patch: Mapping[str, Any] | None
) -> str:
    """Spec §7 — applying a suggestion clones, patches, and re-runs.

    Append-only, exactly like evaluate: the source formulation and every
    evaluation of it are untouched, and the clone records its parent (plan
    decision #15). `create` re-validates, so a patch that produced something
    degenerate is refused here rather than reaching the engine.
    """
    source = get(conn, formulation_id)
    if source is None:
        raise ValidationRejection(f"Unknown formulation '{formulation_id}'.")
    recipe_id = recipe_id_for(conn, formulation_id)
    patched = apply_patch(source, patch)

    return create(
        conn,
        recipe_id=recipe_id,
        format=patched.format.value,
        target_trigger_food_ids=list(patched.target_trigger_food_ids),
        application_food_ids=list(patched.application_food_ids),
        dwell_profile=patched.dwell_profile.value if patched.dwell_profile else None,
        enzymes=[
            {
                "enzyme_id": s.enzyme_id, "dose": s.dose, "phase": s.phase.value,
                "encapsulated": s.encapsulated, "source_choice": s.source_choice,
            }
            for s in patched.enzymes
        ],
        serving_size_g=patched.serving_size_g,
        measured_ph=patched.measured_ph.value,
        process_steps=[
            {"order": s.order, "label": s.label, "is_heat": s.is_heat}
            for s in patched.process_steps
        ],
        enzyme_addition_index=patched.enzyme_addition_index,
        parent_formulation_id=formulation_id,
    )
```

with `from collections.abc import Mapping, Sequence`, `from typing import Any`, and `from foodbrew.engine.patch import apply_patch` added at the top.

Round-tripping `measured_ph` through `create`'s "present means `user_provided`" rule is faithful because a formulation's `measured_ph` is only ever `user_provided` or `unconfirmed` — a trial's measured pH lives in `trial_batch` and reaches the engine through `latest_trial_ph`, never through this column (decision #15).

- [ ] **Step 2: Test it**

`tests/store/test_clone.py`:

```python
"""Plan decision #15 — applying a variant is append-only."""

import pytest

from foodbrew.engine import ValidationRejection
from foodbrew.engine.patch import set_format
from foodbrew.engine.types import Format, Phase
from foodbrew.store import evaluations, formulations

from tests.store.test_variant_store import _vinaigrette


def test_the_clone_carries_the_patch_and_names_its_parent(conn):
    source_id = _vinaigrette(conn)
    clone_id = formulations.clone_with_patch(conn, source_id, set_format(Format.DRY_SACHET))

    clone = formulations.get(conn, clone_id)
    assert clone.format is Format.DRY_SACHET
    assert clone.enzymes[0].phase is Phase.DRY
    assert clone.parent_formulation_id == source_id


def test_the_source_is_untouched(conn):
    source_id = _vinaigrette(conn)
    before = formulations.get(conn, source_id)
    formulations.clone_with_patch(conn, source_id, set_format(Format.DRY_SACHET))
    assert formulations.get(conn, source_id) == before


def test_an_evaluation_of_the_source_is_untouched(conn):
    source_id = _vinaigrette(conn)
    original = evaluations.run(conn, source_id)
    clone_id = formulations.clone_with_patch(conn, source_id, set_format(Format.DRY_SACHET))
    clone_result = evaluations.run(conn, clone_id)

    reread = evaluations.get(conn, original.id)
    assert reread.overall == original.overall
    assert clone_result.overall != original.overall


def test_the_clone_keeps_the_recipe_and_the_measured_pH(conn):
    source_id = _vinaigrette(conn)
    clone_id = formulations.clone_with_patch(conn, source_id, set_format(Format.DRY_SACHET))
    source, clone = formulations.get(conn, source_id), formulations.get(conn, clone_id)
    assert clone.recipe == source.recipe
    assert clone.measured_ph == source.measured_ph


def test_a_patch_the_engine_would_refuse_never_creates_a_row(conn):
    source_id = _vinaigrette(conn, target_trigger_food_ids=[])
    before = conn.execute("SELECT COUNT(*) AS n FROM formulation").fetchone()["n"]
    with pytest.raises(ValidationRejection):
        formulations.clone_with_patch(conn, source_id, {"ops": [
            {"op": "remove_enzyme", "enzyme_id": "lactase_fungal_acid"},
        ]})
    assert conn.execute("SELECT COUNT(*) AS n FROM formulation").fetchone()["n"] == before


def test_an_unknown_formulation_is_refused(conn):
    with pytest.raises(ValidationRejection):
        formulations.clone_with_patch(conn, "nope", set_format(Format.DRY_SACHET))
```

Run: `.venv/bin/pytest tests/store/test_clone.py -q`
Expected: 6 passed.

- [ ] **Step 3: Commit**

```bash
git add src/foodbrew/store/formulations.py tests/store/test_clone.py
git commit -m "feat(store): clone a formulation with a variant patch applied"
```
---

## Task 14: API schemas for M3

Every model below obeys the two rules M2's contract tests already enforce: no request model names a truth label, and no numeric field is serialized bare. One new rule joins them (Task 20): no request model carries a patch.

**Files:**
- Modify: `src/foodbrew/api/schemas.py`

- [ ] **Step 1: Add the wire models**

Append to `schemas.py`:

```python
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
```

and extend `EvaluationOut` with four fields:

```python
class EvaluationOut(BaseModel):
    ...
    dose_cards: list[DoseCardOut]
    suggestions: list[SuggestionOut]
    format_recommendation: FormatRecommendationOut
    #: True when a record this evaluation read has changed since it ran.
    stale: bool = False
    changes: list[SnapshotChangeOut] = Field(default_factory=list)
```

`ProposalIn.source_citation` carries `min_length=1` so a blank citation is refused by the schema as well as by the store — the store's check is the one that matters, and the schema makes the 422 immediate.

- [ ] **Step 2: Check the existing contracts still hold**

Run: `.venv/bin/pytest tests/api/test_contracts.py -q`
Expected: green. `test_no_schema_lets_a_client_choose_a_truth_label` skips `*Out` models and inspects field *names* on the rest — `RecordEditIn.fields` and `ProposalIn.field` contain no `status`, and the values inside them are the store's problem, not the schema's. Task 20 adds the test that closes that gap.

- [ ] **Step 3: Commit**

```bash
git add src/foodbrew/api/schemas.py
git commit -m "feat(api): add the M3 wire models"
```

---

## Task 15: Evaluations router — suggestions, format recommendation, staleness

**Files:**
- Modify: `src/foodbrew/api/routers/evaluations.py`
- Create: `tests/api/test_evaluation_extras.py`

- [ ] **Step 1: Rename `_out` and give it the three new sections**

`routers/variants.py` (Task 16) returns an evaluation too, so the builder becomes public rather than being imported through its underscore.

```python
from foodbrew.engine.format_search import recommend_format
from foodbrew.api.schemas import (
    ...,
    FormatOptionOut,
    FormatRecommendationOut,
    SnapshotChangeOut,
    SuggestionOut,
)


def _recommendation(recommendation) -> FormatRecommendationOut:
    return FormatRecommendationOut(
        current=recommendation.current.value,
        recommended=recommendation.recommended.value if recommendation.recommended else None,
        options=[
            FormatOptionOut(
                format=option.format.value, title=option.title,
                is_current=option.is_current, clears=option.clears, reds=list(option.reds),
            )
            for option in recommendation.options
        ],
        unfixable=list(recommendation.unfixable),
        message=recommendation.message,
    )


def evaluation_out(stored, *, stale: bool = False, changes=()) -> EvaluationOut:
    ctx = context_from_snapshot(stored.input_snapshot_json)
    return EvaluationOut(
        ...,                                    # every M2 field, unchanged
        suggestions=[
            SuggestionOut(
                id=s.id, suggestion_type=s.suggestion_type, description=s.description,
                raised_by=list(s.raised_by), is_applicable=s.is_applicable,
            )
            for s in stored.suggestions
        ],
        format_recommendation=_recommendation(recommend_format(ctx)),
        stale=stale,
        changes=[
            SnapshotChangeOut(
                kind=c.kind, record_id=c.record_id, field=c.field,
                before=c.before, after=c.after,
            )
            for c in changes
        ],
    )
```

Keep `_out = evaluation_out` off the file — rename every call site instead, so there is one name.

- [ ] **Step 2: Compute staleness on the detail read only**

```python
@router.post(
    "/formulations/{formulation_id}/evaluate", response_model=EvaluationOut, status_code=201
)
def run_evaluation(formulation_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    # A run just froze its own inputs, so it cannot be stale.
    return evaluation_out(store.run(conn, formulation_id))


@router.get("/evaluations/{evaluation_id}", response_model=EvaluationOut)
def get_evaluation(evaluation_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    stored = store.get(conn, evaluation_id)
    if stored is None:
        raise HTTPException(status_code=404, detail=f"No evaluation '{evaluation_id}'.")
    stale, changes = store.freshness(conn, stored)
    return evaluation_out(stored, stale=stale, changes=changes)
```

`list_recent` and `list_for_formulation` keep returning summaries with no freshness check — one hydration per row for a banner nobody is reading (plan decision #9).

- [ ] **Step 3: Test it over HTTP**

`tests/api/test_evaluation_extras.py`:

```python
"""The three things M3 adds to an evaluation payload."""


def _evaluate(client, formulation_id):
    return client.post(f"/api/v1/formulations/{formulation_id}/evaluate").json()


def test_a_fresh_run_reports_suggestions(client, vinaigrette):
    payload = _evaluate(client, vinaigrette["formulation_id"])
    assert payload["suggestions"]
    assert {s["is_applicable"] for s in payload["suggestions"]} == {True, False}
    assert all(s["raised_by"] for s in payload["suggestions"])


def test_a_fresh_run_reports_a_format_recommendation(client, vinaigrette):
    recommendation = _evaluate(client, vinaigrette["formulation_id"])["format_recommendation"]
    assert recommendation["current"] == "premixed_wet"
    assert [o["format"] for o in recommendation["options"]] == [
        "premixed_wet", "encapsulated_in_wet", "dual_chamber", "dry_sachet"
    ]
    assert recommendation["recommended"] in ("dual_chamber", "dry_sachet")
    assert "R1" in next(o["reds"] for o in recommendation["options"] if o["is_current"])


def test_a_fresh_run_is_never_stale(client, vinaigrette):
    payload = _evaluate(client, vinaigrette["formulation_id"])
    assert payload["stale"] is False
    assert payload["changes"] == []


def test_editing_a_referenced_record_makes_the_stored_run_stale(client, vinaigrette, conn):
    payload = _evaluate(client, vinaigrette["formulation_id"])
    conn.execute(
        "UPDATE enzyme SET ph_shelf_stable_min = 2.5,"
        " ph_shelf_stable_min_status = 'confirmed' WHERE id = 'lactase_fungal_acid'"
    )
    conn.commit()

    reread = client.get(f"/api/v1/evaluations/{payload['id']}").json()
    assert reread["stale"] is True
    assert reread["changes"][0]["record_id"] == "lactase_fungal_acid"
    assert reread["changes"][0]["field"] == "ph_shelf_stable_min"
    # The verdict itself is unchanged: an evaluation is a frozen record (§4).
    assert reread["headline"] == payload["headline"]


def test_the_summary_list_stays_a_summary(client, vinaigrette):
    _evaluate(client, vinaigrette["formulation_id"])
    summary = client.get("/api/v1/evaluations").json()[0]
    assert "suggestions" not in summary
    assert "stale" not in summary
```

Run: `.venv/bin/pytest tests/api -q`
Expected: green, including every M2 API test.

- [ ] **Step 4: Commit**

```bash
git add src/foodbrew/api/routers/evaluations.py tests/api/test_evaluation_extras.py
git commit -m "feat(api): report suggestions, the format call, and staleness on an evaluation"
```

---

## Task 16: `routers/variants.py` — apply a variant, and compare

**Files:**
- Create: `src/foodbrew/api/routers/variants.py`
- Modify: `src/foodbrew/api/app.py`
- Create: `tests/api/test_variants.py`, `tests/api/test_compare.py`

- [ ] **Step 1: Write the router**

```python
"""Workflows B and C — apply a suggestion, and compare what changed.

Applying takes a stored suggestion id, never a patch body: the server applies
what its own engine wrote (plan decision #2). The result is a new formulation
and a new evaluation; the originals are untouched (decision #15).
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from foodbrew.api.deps import get_conn
from foodbrew.api.routers.evaluations import evaluation_out
from foodbrew.api.schemas import (
    ApplyVariantIn,
    ComparisonCellOut,
    ComparisonColumnOut,
    ComparisonOut,
    ComparisonRowOut,
    EvaluationOut,
)
from foodbrew.engine import ValidationRejection
from foodbrew.engine.compare import ComparisonSide, compare
from foodbrew.engine.views import dose_cards
from foodbrew.store import evaluations as evaluations_store
from foodbrew.store import formulations as formulations_store
from foodbrew.store import variants as variants_store
from foodbrew.store.snapshot import context_from_snapshot

router = APIRouter(tags=["variants"])


@router.post(
    "/evaluations/{evaluation_id}/apply-variant",
    response_model=EvaluationOut,
    status_code=201,
)
def apply_variant(
    evaluation_id: str,
    payload: ApplyVariantIn,
    conn: sqlite3.Connection = Depends(get_conn),
):
    stored = evaluations_store.get(conn, evaluation_id)
    if stored is None:
        raise HTTPException(status_code=404, detail=f"No evaluation '{evaluation_id}'.")

    suggestion = variants_store.get(conn, payload.suggestion_id)
    if suggestion is None or suggestion.evaluation_id != evaluation_id:
        raise HTTPException(
            status_code=404,
            detail=f"No suggestion {payload.suggestion_id} on this evaluation.",
        )
    if not suggestion.is_applicable:
        raise ValidationRejection(
            "This one is a note rather than a change — there is nothing to apply."
        )

    formulation_id = formulations_store.clone_with_patch(
        conn, stored.formulation_id, suggestion.patch
    )
    return evaluation_out(evaluations_store.run(conn, formulation_id))


@router.get("/compare", response_model=ComparisonOut)
def compare_evaluations(
    ids: list[str] = Query(default_factory=list),
    conn: sqlite3.Connection = Depends(get_conn),
):
    """Spec §10 — `GET /compare?ids=…`, by evaluation id (plan decision #10)."""
    sides = []
    for evaluation_id in ids:
        stored = evaluations_store.get(conn, evaluation_id)
        if stored is None:
            raise HTTPException(status_code=404, detail=f"No evaluation '{evaluation_id}'.")
        ctx = context_from_snapshot(stored.input_snapshot_json)
        sides.append(
            ComparisonSide(
                evaluation_id=stored.id,
                label=f"{stored.display} · {stored.created_at[:16].replace('T', ' ')}",
                headline=stored.display,
                format=ctx.formulation.format.value,
                dwell_profile=(
                    ctx.formulation.dwell_profile.value
                    if ctx.formulation.dwell_profile
                    else None
                ),
                findings=stored.findings,
                envelope=stored.envelope,
                doses={
                    card.enzyme_id: (card.dose, card.dose_unit, card.enzyme_name)
                    for card in dose_cards(ctx)
                },
            )
        )

    comparison = compare(sides)
    return ComparisonOut(
        columns=[
            ComparisonColumnOut(
                evaluation_id=c.evaluation_id, label=c.label, headline=c.headline
            )
            for c in comparison.columns
        ],
        rows=[
            ComparisonRowOut(
                section=row.section, key=row.key, label=row.label, changed=row.changed,
                cells=[
                    ComparisonCellOut(text=cell.text, verdict=cell.verdict, present=cell.present)
                    for cell in row.cells
                ],
            )
            for row in comparison.rows
        ],
    )
```

Register it in `app.py`:

```python
from foodbrew.api.routers import catalog, evaluations, formulations, recipes, variants
...
    for router in (
        catalog.router, recipes.router, formulations.router, evaluations.router,
        variants.router,
    ):
```

- [ ] **Step 2: Test applying**

`tests/api/test_variants.py`:

```python
"""Workflow C, and spec §13's contract test over HTTP."""


def _evaluate(client, formulation_id):
    return client.post(f"/api/v1/formulations/{formulation_id}/evaluate").json()


def _apply(client, evaluation_id, suggestion_id):
    return client.post(
        f"/api/v1/evaluations/{evaluation_id}/apply-variant",
        json={"suggestion_id": suggestion_id},
    )


def _first_applicable(payload, suggestion_type=None):
    def wanted(s):
        return s["is_applicable"] and suggestion_type in (None, s["suggestion_type"])

    return next(s for s in payload["suggestions"] if wanted(s))


def test_applying_a_format_change_produces_a_new_evaluation(client, vinaigrette):
    original = _evaluate(client, vinaigrette["formulation_id"])
    suggestion = _first_applicable(original, "format_change")

    response = _apply(client, original["id"], suggestion["id"])
    assert response.status_code == 201
    applied = response.json()
    assert applied["id"] != original["id"]
    assert applied["formulation_id"] != original["formulation_id"]


def test_the_original_evaluation_is_untouched(client, vinaigrette):
    original = _evaluate(client, vinaigrette["formulation_id"])
    _apply(client, original["id"], _first_applicable(original)["id"])
    reread = client.get(f"/api/v1/evaluations/{original['id']}").json()
    assert reread["headline"] == original["headline"]
    assert [f["message"] for f in reread["findings"]] == [
        f["message"] for f in original["findings"]
    ]


def test_the_clone_records_its_parent(client, vinaigrette):
    original = _evaluate(client, vinaigrette["formulation_id"])
    applied = _apply(client, original["id"], _first_applicable(original)["id"]).json()
    formulation = client.get(f"/api/v1/formulations/{applied['formulation_id']}").json()
    assert formulation["parent_formulation_id"] == original["formulation_id"]


def test_moving_the_vinaigrette_to_a_dry_sachet_clears_R1(client, vinaigrette):
    """Golden fixtures (a) and (c), joined by one button."""
    original = _evaluate(client, vinaigrette["formulation_id"])
    assert original["headline"] == "RED"

    dry = next(
        s for s in original["suggestions"]
        if s["suggestion_type"] == "format_change" and "dry sachet" in s["description"]
    )
    applied = _apply(client, original["id"], dry["id"]).json()
    assert applied["headline"] != "RED"
    assert not [f for f in applied["blockers"] if f["rule_id"] == "R1"]


def test_a_note_cannot_be_applied(client, vinaigrette):
    original = _evaluate(client, vinaigrette["formulation_id"])
    note = next(s for s in original["suggestions"] if not s["is_applicable"])
    response = _apply(client, original["id"], note["id"])
    assert response.status_code == 422
    assert "nothing to apply" in response.json()["detail"]


def test_a_suggestion_from_another_evaluation_is_refused(client, vinaigrette):
    first = _evaluate(client, vinaigrette["formulation_id"])
    second = _evaluate(client, vinaigrette["formulation_id"])
    response = _apply(client, second["id"], _first_applicable(first)["id"])
    assert response.status_code == 404


def test_an_unknown_suggestion_is_refused(client, vinaigrette):
    original = _evaluate(client, vinaigrette["formulation_id"])
    assert _apply(client, original["id"], 999_999).status_code == 404


def test_the_endpoint_does_not_accept_a_patch(client, vinaigrette):
    """Plan decision #2 — an extra key is ignored, and a missing id is a 422."""
    original = _evaluate(client, vinaigrette["formulation_id"])
    response = client.post(
        f"/api/v1/evaluations/{original['id']}/apply-variant",
        json={"ops": [{"op": "remove_enzyme", "enzyme_id": "lactase_fungal_acid"}]},
    )
    assert response.status_code == 422


def test_every_applicable_suggestion_re_evaluates_without_error(client, vinaigrette):
    """Spec §13's contract test, end to end through HTTP."""
    original = _evaluate(client, vinaigrette["formulation_id"])
    applied = 0
    for suggestion in original["suggestions"]:
        if not suggestion["is_applicable"]:
            continue
        response = _apply(client, original["id"], suggestion["id"])
        assert response.status_code == 201, (suggestion["description"], response.json())
        assert response.json()["headline"] in {"RED", "GRAY", "AMBER", "GREEN"}
        applied += 1
    assert applied >= 3
```

- [ ] **Step 3: Test comparing**

`tests/api/test_compare.py`:

```python
"""Workflow B over HTTP."""


def _evaluate(client, formulation_id):
    return client.post(f"/api/v1/formulations/{formulation_id}/evaluate").json()


def _two_variants(client, vinaigrette):
    original = _evaluate(client, vinaigrette["formulation_id"])
    dry = next(
        s for s in original["suggestions"]
        if s["suggestion_type"] == "format_change" and "dry sachet" in s["description"]
    )
    applied = client.post(
        f"/api/v1/evaluations/{original['id']}/apply-variant",
        json={"suggestion_id": dry["id"]},
    ).json()
    return original, applied


def test_comparing_two_variants_shows_the_headline_moving(client, vinaigrette):
    original, applied = _two_variants(client, vinaigrette)
    payload = client.get(
        "/api/v1/compare", params={"ids": [original["id"], applied["id"]]}
    ).json()

    assert [c["evaluation_id"] for c in payload["columns"]] == [original["id"], applied["id"]]
    headline = next(r for r in payload["rows"] if r["key"] == "headline")
    assert headline["changed"]
    assert [c["text"] for c in headline["cells"]] == [original["headline"], applied["headline"]]


def test_the_format_row_names_both_formats(client, vinaigrette):
    original, applied = _two_variants(client, vinaigrette)
    payload = client.get(
        "/api/v1/compare", params={"ids": [original["id"], applied["id"]]}
    ).json()
    row = next(r for r in payload["rows"] if r["key"] == "format")
    assert [c["text"] for c in row["cells"]] == ["premixed_wet", "dry_sachet"]


def test_a_rule_that_only_fires_on_one_side_reads_as_absent(client, vinaigrette):
    original, applied = _two_variants(client, vinaigrette)
    payload = client.get(
        "/api/v1/compare", params={"ids": [original["id"], applied["id"]]}
    ).json()
    r1_rows = [r for r in payload["rows"] if r["key"].startswith("R1:")]
    assert r1_rows
    assert any(not row["cells"][1]["present"] for row in r1_rows)


def test_comparing_one_evaluation_is_refused(client, vinaigrette):
    original = _evaluate(client, vinaigrette["formulation_id"])
    response = client.get("/api/v1/compare", params={"ids": [original["id"]]})
    assert response.status_code == 422
    assert "at least two" in response.json()["detail"]


def test_an_unknown_evaluation_is_a_404(client, vinaigrette):
    original = _evaluate(client, vinaigrette["formulation_id"])
    response = client.get("/api/v1/compare", params={"ids": [original["id"], "nope"]})
    assert response.status_code == 404


def test_more_than_six_columns_is_refused(client, vinaigrette):
    ids = [_evaluate(client, vinaigrette["formulation_id"])["id"] for _ in range(7)]
    assert client.get("/api/v1/compare", params={"ids": ids}).status_code == 422
```

Run: `.venv/bin/pytest tests/api -q`
Expected: green.

- [ ] **Step 4: Commit**

```bash
git add src/foodbrew/api/routers/variants.py src/foodbrew/api/app.py tests/api/test_variants.py tests/api/test_compare.py
git commit -m "feat(api): apply a variant and compare evaluations"
```

---

## Task 17: `routers/records.py` — the database editor

**Files:**
- Create: `src/foodbrew/api/routers/records.py`
- Modify: `src/foodbrew/api/app.py`
- Create: `tests/api/test_records.py`

- [ ] **Step 1: Write the router**

```python
"""Workflow D — the enzyme and food editors, and reset to baseline.

Nothing here decides a truth label. `store/records.py` attaches `user_provided`
to a direct edit; the only path to `confirmed` is an approved proposal, in the
router next door (plan decision #7).
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from foodbrew.api.deps import get_conn
from foodbrew.api.schemas import AuditEventOut, EnzymeOut, FoodOut, RecordEditIn
from foodbrew.store import audit as audit_store
from foodbrew.store import foods as foods_store
from foodbrew.store import records as records_store
from foodbrew.store.reference import load_catalog

router = APIRouter(tags=["database"])


def _enzyme(conn: sqlite3.Connection, enzyme_id: str) -> EnzymeOut:
    return EnzymeOut.of(load_catalog(conn).enzymes[enzyme_id])


@router.put("/enzymes/{enzyme_id}", response_model=EnzymeOut)
def update_enzyme(
    enzyme_id: str, payload: RecordEditIn, conn: sqlite3.Connection = Depends(get_conn)
):
    records_store.update(conn, "enzyme", enzyme_id, payload.fields)
    return _enzyme(conn, enzyme_id)


@router.post("/enzymes/{enzyme_id}/reset", response_model=EnzymeOut)
def reset_enzyme(enzyme_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    records_store.reset_record(conn, "enzyme", enzyme_id)
    return _enzyme(conn, enzyme_id)


@router.put("/foods/{food_id}", response_model=FoodOut)
def update_food(
    food_id: str, payload: RecordEditIn, conn: sqlite3.Connection = Depends(get_conn)
):
    records_store.update(conn, "food", food_id, payload.fields)
    return FoodOut.of(foods_store.get(conn, food_id))


@router.post("/foods/{food_id}/reset", response_model=FoodOut)
def reset_food(food_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    records_store.reset_record(conn, "food", food_id)
    return FoodOut.of(foods_store.get(conn, food_id))


@router.post("/reference/reset", status_code=204)
def reset_reference(conn: sqlite3.Connection = Depends(get_conn)) -> None:
    """Discards every edit to every enzyme and food row. There is no undo."""
    records_store.reset_all(conn)


@router.get("/audit", response_model=list[AuditEventOut])
def recent_changes(limit: int = 50, conn: sqlite3.Connection = Depends(get_conn)):
    return [
        AuditEventOut(
            id=event.id, actor=event.actor, action=event.action,
            entity=event.entity, timestamp=event.timestamp,
        )
        for event in audit_store.list_recent(conn, limit)
    ]
```

Register `records.router` in `app.py` alongside the others.

- [ ] **Step 2: Test it**

`tests/api/test_records.py`:

```python
"""Workflow D over HTTP."""


def _enzyme(client, enzyme_id="lactase_fungal_acid"):
    return next(e for e in client.get("/api/v1/enzymes").json() if e["id"] == enzyme_id)


def test_an_edit_is_stored_as_the_founder_s_own_value(client):
    response = client.put(
        "/api/v1/enzymes/lactase_fungal_acid",
        json={"fields": {"ph_shelf_stable_min": 3.4}},
    )
    assert response.status_code == 200
    field = response.json()["ph_shelf_stable_min"]
    assert (field["value"], field["status"]) == (3.4, "user_provided")
    assert field["source"] == "entered by founder"


def test_a_client_cannot_reach_a_status_column_through_the_editor(client):
    """Plan decision #16 — the allowlist is what stops this, not the schema."""
    response = client.put(
        "/api/v1/enzymes/lactase_fungal_acid",
        json={"fields": {"ph_min_status": "confirmed"}},
    )
    assert response.status_code == 422
    assert _enzyme(client)["ph_min"]["status"] != "confirmed"


def test_an_unknown_field_is_refused_in_plain_english(client):
    response = client.put(
        "/api/v1/enzymes/lactase_fungal_acid", json={"fields": {"nonsense": 1}}
    )
    assert response.status_code == 422
    assert "cannot be edited" in response.json()["detail"]


def test_an_unknown_record_is_refused(client):
    response = client.put("/api/v1/enzymes/nope", json={"fields": {"notes": "x"}})
    assert response.status_code == 422


def test_a_food_edit_round_trips(client):
    response = client.put("/api/v1/foods/milk", json={"fields": {"ph": 6.7}})
    assert response.json()["ph"]["value"] == 6.7


def test_reset_puts_the_shipped_value_back(client):
    before = _enzyme(client)["ph_min"]
    client.put("/api/v1/enzymes/lactase_fungal_acid", json={"fields": {"ph_min": 1.0}})
    restored = client.post("/api/v1/enzymes/lactase_fungal_acid/reset").json()
    assert restored["ph_min"] == before


def test_resetting_a_custom_food_is_refused(client):
    created = client.post(
        "/api/v1/foods",
        json={"name": "Her base", "is_recipe_ingredient": True, "ph": 3.1},
    ).json()
    response = client.post(f"/api/v1/foods/{created['id']}/reset")
    assert response.status_code == 422
    assert "no baseline" in response.json()["detail"]


def test_the_global_reset_discards_every_edit(client):
    client.put("/api/v1/enzymes/lactase_fungal_acid", json={"fields": {"ph_min": 1.0}})
    client.put("/api/v1/foods/milk", json={"fields": {"ph": 1.0}})
    assert client.post("/api/v1/reference/reset").status_code == 204
    assert _enzyme(client)["ph_min"]["value"] != 1.0


def test_every_change_shows_up_in_the_audit_feed(client):
    client.put("/api/v1/enzymes/lactase_fungal_acid", json={"fields": {"notes": "asked Amano"}})
    feed = client.get("/api/v1/audit").json()
    assert feed[0]["action"] == "update"
    assert feed[0]["entity"] == "enzyme:lactase_fungal_acid"


def test_an_edit_makes_an_existing_evaluation_stale(client, vinaigrette):
    original = client.post(
        f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
    ).json()
    client.put(
        "/api/v1/enzymes/lactase_fungal_acid", json={"fields": {"ph_shelf_stable_min": 2.5}}
    )
    assert client.get(f"/api/v1/evaluations/{original['id']}").json()["stale"] is True
```

Run: `.venv/bin/pytest tests/api/test_records.py -q`
Expected: 10 passed.

- [ ] **Step 3: Commit**

```bash
git add src/foodbrew/api/routers/records.py src/foodbrew/api/app.py tests/api/test_records.py
git commit -m "feat(api): add the enzyme and food editors with reset to baseline"
```

---

## Task 18: `routers/proposals.py` — the inbox

**Files:**
- Create: `src/foodbrew/api/routers/proposals.py`
- Modify: `src/foodbrew/api/app.py`
- Create: `tests/api/test_proposals.py`

- [ ] **Step 1: Write the router**

```python
"""Spec §2.3's research track — propose a value with a citation, approve, reject."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query

from foodbrew.api.deps import get_conn
from foodbrew.api.schemas import ProposalIn, ProposalOut
from foodbrew.store import proposals as store

router = APIRouter(tags=["proposals"])


def _out(proposal) -> ProposalOut:
    return ProposalOut(**{f: getattr(proposal, f) for f in ProposalOut.model_fields})


@router.get("/proposals", response_model=list[ProposalOut])
def list_proposals(
    status: str | None = Query(default=None, description="pending | approved | rejected"),
    conn: sqlite3.Connection = Depends(get_conn),
):
    return [_out(p) for p in store.list_all(conn, status)]


@router.post("/proposals", response_model=ProposalOut, status_code=201)
def create_proposal(payload: ProposalIn, conn: sqlite3.Connection = Depends(get_conn)):
    proposal_id = store.create(conn, **payload.model_dump())
    return _out(store.get(conn, proposal_id))


@router.post("/proposals/{proposal_id}/approve", response_model=ProposalOut)
def approve_proposal(proposal_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    return _out(store.approve(conn, proposal_id))


@router.post("/proposals/{proposal_id}/reject", response_model=ProposalOut)
def reject_proposal(proposal_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    return _out(store.reject(conn, proposal_id))
```

Register `proposals.router` in `app.py`.

- [ ] **Step 2: Test it**

`tests/api/test_proposals.py`:

```python
"""Spec §2.3 over HTTP, and the only route to a confirmed value."""

PROPOSAL = {
    "table_name": "enzyme",
    "record_id": "lactase_fungal_acid",
    "field": "ph_shelf_stable_min",
    "proposed_value": "3.0",
    "source_citation": "Amano technical datasheet, retrieved 2026-08-14",
}


def _enzyme(client):
    return next(
        e for e in client.get("/api/v1/enzymes").json() if e["id"] == "lactase_fungal_acid"
    )


def test_a_proposal_starts_pending(client):
    created = client.post("/api/v1/proposals", json=PROPOSAL).json()
    assert created["status"] == "pending"
    pending = client.get("/api/v1/proposals", params={"status": "pending"}).json()
    assert [p["id"] for p in pending] == [created["id"]]


def test_a_proposal_without_a_citation_is_refused(client):
    response = client.post("/api/v1/proposals", json={**PROPOSAL, "source_citation": ""})
    assert response.status_code == 422


def test_approving_confirms_the_value_and_records_the_citation(client):
    created = client.post("/api/v1/proposals", json=PROPOSAL).json()
    assert client.post(f"/api/v1/proposals/{created['id']}/approve").json()["status"] == "approved"

    field = _enzyme(client)["ph_shelf_stable_min"]
    assert (field["value"], field["status"]) == (3.0, "confirmed")
    assert field["source"] == PROPOSAL["source_citation"]


def test_rejecting_changes_nothing(client):
    before = _enzyme(client)["ph_shelf_stable_min"]
    created = client.post("/api/v1/proposals", json=PROPOSAL).json()
    client.post(f"/api/v1/proposals/{created['id']}/reject")
    assert _enzyme(client)["ph_shelf_stable_min"] == before


def test_a_decided_proposal_cannot_be_decided_again(client):
    created = client.post("/api/v1/proposals", json=PROPOSAL).json()
    client.post(f"/api/v1/proposals/{created['id']}/approve")
    response = client.post(f"/api/v1/proposals/{created['id']}/reject")
    assert response.status_code == 422
    assert "already approved" in response.json()["detail"]


def test_approving_a_temperature_range_promotes_R12_on_the_next_run(client, vinaigrette):
    """Spec §13 fixture (h2), through the product."""
    before = client.post(
        f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
    ).json()
    assert any(f["rule_id"] == "R12" for f in before["advisories"])

    for field, value in (("temp_min_c", "30"), ("temp_max_c", "45")):
        created = client.post(
            "/api/v1/proposals",
            json={**PROPOSAL, "field": field, "proposed_value": value},
        ).json()
        client.post(f"/api/v1/proposals/{created['id']}/approve")

    after = client.post(
        f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
    ).json()
    r12 = [f for f in after["findings"] if f["rule_id"] == "R12"]
    assert r12 and not any(f["advisory"] for f in r12)
```

Run: `.venv/bin/pytest tests/api/test_proposals.py -q`
Expected: 6 passed. If the R12 promotion test fails because 30–45 °C covers both 25 °C and 37 °C and therefore passes rather than reds, that is correct engine behaviour — the assertion is about the finding no longer being advisory, not about its verdict.

- [ ] **Step 3: Commit**

```bash
git add src/foodbrew/api/routers/proposals.py src/foodbrew/api/app.py tests/api/test_proposals.py
git commit -m "feat(api): add the proposals inbox"
```

---

## Task 19: `routers/export.py` — the Markdown report

**Files:**
- Create: `src/foodbrew/api/routers/export.py`
- Modify: `src/foodbrew/api/app.py`
- Create: `tests/api/test_export.py`

- [ ] **Step 1: Write the router**

Keep it thin. Every sentence the founder reads comes from `engine/report.py`, for the reason plan decision #11 gives.

```python
"""Spec §10 — `GET /export/{evaluation_id}.md`.

The renderer lives in `engine/report.py`; this module only assembles its input
and sets a content type. The route's literal `.md` suffix is matched after the
path parameter's `[^/]+`, which resolves cleanly because evaluation ids are hex.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse

from foodbrew.api.deps import get_conn
from foodbrew.engine.format_search import recommend_format
from foodbrew.engine.report import ReportInput, ReportSuggestion, render_markdown
from foodbrew.store import evaluations as evaluations_store
from foodbrew.store import formulations as formulations_store
from foodbrew.store import recipes as recipes_store
from foodbrew.store.snapshot import context_from_snapshot

router = APIRouter(tags=["export"])


@router.get("/export/{evaluation_id}.md", response_class=PlainTextResponse)
def export_markdown(evaluation_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    stored = evaluations_store.get(conn, evaluation_id)
    if stored is None:
        raise HTTPException(status_code=404, detail=f"No evaluation '{evaluation_id}'.")

    ctx = context_from_snapshot(stored.input_snapshot_json)
    stale, _changes = evaluations_store.freshness(conn, stored)

    recipe_id = formulations_store.recipe_id_for(conn, stored.formulation_id)
    recipe = recipes_store.get(conn, recipe_id) if recipe_id else None

    body = render_markdown(
        ReportInput(
            evaluation_id=stored.id,
            created_at=stored.created_at,
            engine_version=stored.engine_version,
            recipe_name=recipe.name if recipe else "Untitled recipe",
            headline=stored.display,
            context=ctx,
            findings=stored.findings,
            envelope=stored.envelope,
            recommendation=recommend_format(ctx),
            suggestions=tuple(
                ReportSuggestion(s.suggestion_type, s.description, s.raised_by)
                for s in stored.suggestions
            ),
            stale=stale,
        )
    )
    return PlainTextResponse(body, media_type="text/markdown; charset=utf-8")
```

Register `export.router` in `app.py`.

- [ ] **Step 2: Test it**

`tests/api/test_export.py`:

```python
"""Spec §10's export endpoint and §13's report lint, end to end."""

from foodbrew.engine.language import contains_prohibited
from foodbrew.engine.report import DISCLAIMER


def _evaluate(client, formulation_id):
    return client.post(f"/api/v1/formulations/{formulation_id}/evaluate").json()


def test_the_export_is_markdown_with_the_disclaimer_last(client, vinaigrette):
    evaluation = _evaluate(client, vinaigrette["formulation_id"])
    response = client.get(f"/api/v1/export/{evaluation['id']}.md")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert response.text.rstrip().endswith(DISCLAIMER)


def test_the_export_carries_no_prohibited_word(client, vinaigrette):
    evaluation = _evaluate(client, vinaigrette["formulation_id"])
    body = client.get(f"/api/v1/export/{evaluation['id']}.md").text
    assert contains_prohibited(body) == ()


def test_the_export_names_the_recipe_and_the_engine_version(client, vinaigrette):
    evaluation = _evaluate(client, vinaigrette["formulation_id"])
    body = client.get(f"/api/v1/export/{evaluation['id']}.md").text
    assert "# Formulation report — vinaigrette" in body
    assert evaluation["engine_version"] in body
    assert evaluation["id"] in body


def test_the_export_reports_the_blockers_and_the_open_questions(client, vinaigrette):
    evaluation = _evaluate(client, vinaigrette["formulation_id"])
    body = client.get(f"/api/v1/export/{evaluation['id']}.md").text
    assert "### Blockers" in body
    assert "R1 — In-jar pH survival" in body
    assert "## Open questions" in body


def test_the_export_says_no_trial_has_been_recorded(client, vinaigrette):
    evaluation = _evaluate(client, vinaigrette["formulation_id"])
    body = client.get(f"/api/v1/export/{evaluation['id']}.md").text
    assert "No trial has been recorded for this formulation yet." in body


def test_a_stale_export_says_so(client, vinaigrette, conn):
    evaluation = _evaluate(client, vinaigrette["formulation_id"])
    conn.execute("UPDATE enzyme SET notes = 'x' WHERE id = 'lactase_fungal_acid'")
    conn.commit()
    body = client.get(f"/api/v1/export/{evaluation['id']}.md").text
    assert "has changed since it ran" in body


def test_an_unknown_evaluation_is_a_404(client):
    assert client.get("/api/v1/export/nope.md").status_code == 404
```

Run: `.venv/bin/pytest tests/api/test_export.py -q`
Expected: 7 passed.

- [ ] **Step 3: Commit**

```bash
git add src/foodbrew/api/routers/export.py src/foodbrew/api/app.py tests/api/test_export.py
git commit -m "feat(api): export an evaluation as a markdown report"
```

---

## Task 20: M3 contract tests

M2's `tests/api/test_contracts.py` is the file that makes a whole class of mistakes impossible. M3 adds three global properties to it.

**Files:**
- Create: `tests/api/test_contracts_m3.py`

- [ ] **Step 1: Write the tests**

```python
"""Cross-cutting contracts M3 introduces. Cheap, global, and hard to violate by
accident — the same shape as M2's test_contracts.py.
"""

import pathlib

import pytest

from foodbrew.api import schemas
from foodbrew.engine.patch import PatchOp

SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "foodbrew"


def test_no_request_schema_accepts_a_patch():
    """Plan decision #2 — the server applies only what its own engine wrote."""
    banned = {"patch", "patch_json", "ops"}
    for name in dir(schemas):
        model = getattr(schemas, name)
        fields = getattr(model, "model_fields", None)
        if not fields or name.endswith("Out"):
            continue
        assert not (banned & set(fields)), f"{name} accepts a patch from the client"


def test_the_engine_still_imports_no_storage_or_transport():
    """M3 adds five engine modules; the M1 boundary has to survive all of them."""
    for path in (SRC / "engine").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for forbidden in ("foodbrew.store", "foodbrew.api", "foodbrew.db", "fastapi", "sqlite3"):
            assert forbidden not in text, f"{path.name} imports {forbidden}"


def test_the_store_layer_still_imports_no_transport():
    for path in (SRC / "store").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "foodbrew.api" not in text, f"{path.name} imports the API layer"
        assert "fastapi" not in text, f"{path.name} imports FastAPI"


@pytest.mark.parametrize("op", list(PatchOp))
def test_every_patch_op_is_reachable_from_the_engine_not_from_a_route(op):
    """A route that named an op directly would be building patches by hand."""
    for path in (SRC / "api").rglob("*.py"):
        assert op.value not in path.read_text(encoding="utf-8"), f"{path.name} names {op.value}"


def test_no_prohibited_word_appears_in_any_m3_api_source():
    """M2's substring lint, restated because M3 adds four router modules."""
    from foodbrew.engine.language import PROHIBITED_WORDS

    for path in (SRC / "api").rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        for word in PROHIBITED_WORDS:
            assert word not in text, f"{path.name}: '{word}'"


def test_a_suggestion_is_never_offered_without_a_way_to_read_it(client, vinaigrette):
    evaluation = client.post(
        f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
    ).json()
    for suggestion in evaluation["suggestions"]:
        assert suggestion["description"].strip()
        assert suggestion["raised_by"]


def test_an_evaluation_payload_still_carries_valid_labels_everywhere(client, vinaigrette):
    """M3 adds `changes`, whose before/after can hold whole tracked objects."""
    from tests.api.test_contracts import VALID_STATUSES, _tracked_objects

    evaluation = client.post(
        f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
    ).json()
    for tracked in _tracked_objects(evaluation):
        assert tracked["status"] in VALID_STATUSES
```

- [ ] **Step 2: Run the whole suite**

Run: `.venv/bin/pytest -q && .venv/bin/ruff check src tests`
Expected: green. `test_every_patch_op_is_reachable_from_the_engine_not_from_a_route` is the one most likely to fail during development — if a router names `set_format`, move that construction into `engine/variants.py` where it belongs.

- [ ] **Step 3: Commit**

```bash
git add tests/api/test_contracts_m3.py
git commit -m "test(api): assert the patch, layering, and language contracts M3 adds"
```
---

## Task 21: Frontend types and API client

**Files:**
- Modify: `web/src/api/types.ts`, `web/src/api/client.ts`

- [ ] **Step 1: Add the types**

Append to `types.ts`:

```typescript
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
```

and extend `Evaluation`:

```typescript
export interface Evaluation {
  ...
  dose_cards: DoseCard[]
  suggestions: Suggestion[]
  format_recommendation: FormatRecommendation
  stale: boolean
  changes: SnapshotChange[]
}
```

- [ ] **Step 2: Add the client methods**

In `client.ts`, add a `put` helper beside `post` and extend the `api` object:

```typescript
const put = <T,>(path: string, body: unknown) =>
  request<T>(path, { method: 'PUT', body: JSON.stringify(body) })

export const api = {
  ...

  applyVariant: (evaluationId: string, suggestionId: number) =>
    post<Evaluation>(`/evaluations/${evaluationId}/apply-variant`, { suggestion_id: suggestionId }),

  compare: (ids: string[]) => {
    const params = new URLSearchParams()
    ids.forEach((id) => params.append('ids', id))
    return request<Comparison>(`/compare?${params}`)
  },

  updateEnzyme: (id: string, fields: Record<string, unknown>) =>
    put<Enzyme>(`/enzymes/${id}`, { fields }),
  resetEnzyme: (id: string) => post<Enzyme>(`/enzymes/${id}/reset`),
  updateFood: (id: string, fields: Record<string, unknown>) =>
    put<Food>(`/foods/${id}`, { fields }),
  resetFood: (id: string) => post<Food>(`/foods/${id}/reset`),

  proposals: (status?: Proposal['status']) =>
    request<Proposal[]>(`/proposals${status ? `?status=${status}` : ''}`),
  createProposal: (body: unknown) => post<Proposal>('/proposals', body),
  approveProposal: (id: string) => post<Proposal>(`/proposals/${id}/approve`),
  rejectProposal: (id: string) => post<Proposal>(`/proposals/${id}/reject`),

  auditFeed: () => request<AuditEvent[]>('/audit'),

  reportUrl: (evaluationId: string) => `/api/v1/export/${evaluationId}.md`,
}
```

`reportUrl` returns a path rather than fetching: the Report screen renders the same content from the JSON payload, and this is the link for downloading the Markdown the founder emails a food scientist.

- [ ] **Step 3: Typecheck**

Run: `cd web && npm run typecheck`
Expected: clean.

Two settings in `web/tsconfig.json` bind every file this milestone adds, and both are easy to trip:

- `verbatimModuleSyntax: true` — a type-only import must say `import type`. Every component in Tasks 22–26 already does; a plain `import { Suggestion }` fails the build rather than being silently erased.
- `noUncheckedIndexedAccess: true` — indexing an array yields `T | undefined`, so `e[0]!.id` in Task 25 carries its `!` deliberately. Indexing an *object* by a literal union (`enzyme[name]` where `name` comes from the `as const` array) is not affected, which is why those arrays are `as const` rather than `string[]`.

- [ ] **Step 4: Commit**

```bash
git add web/src/api
git commit -m "feat(web): type the variant, compare, database, and report endpoints"
```

---

## Task 22: Shared components — the banner, the format call, the suggestions

**Files:**
- Create: `web/src/components/StaleBanner.tsx`, `web/src/components/FormatRecommendation.tsx`, `web/src/components/VariantSuggestions.tsx`
- Modify: `web/src/styles.css`

- [ ] **Step 1: `StaleBanner.tsx`**

```tsx
import type { SnapshotChange } from '../api/types'

const KIND_TEXT: Record<string, string> = {
  enzyme: 'enzyme',
  food: 'food',
  substrate: 'substrate',
  formulation: 'formulation',
  gi_regions: 'digestive-tract model',
  latest_trial_ph: 'trial pH reading',
}

/** Spec §10 screen 4 — "data changed since this evaluation — re-run to refresh". */
export function StaleBanner({ changes, onRerun }: {
  changes: SnapshotChange[]
  onRerun: () => void
}) {
  return (
    <aside className="banner banner--stale" data-testid="stale-banner">
      <p>
        A record this run used has changed since it ran. What you see below is the
        record of that run and does not update on its own — re-run to see the effect.
      </p>
      {changes.length > 0 && (
        <ul>
          {changes.slice(0, 8).map((change, index) => (
            <li key={`${change.record_id}-${change.field}-${index}`}>
              {KIND_TEXT[change.kind] ?? change.kind} <code>{change.record_id}</code>
              {change.field !== '*' && <> — <code>{change.field}</code></>}
            </li>
          ))}
          {changes.length > 8 && <li>…and {changes.length - 8} more</li>}
        </ul>
      )}
      <button type="button" onClick={onRerun} data-testid="rerun">Re-run the checks</button>
    </aside>
  )
}
```

- [ ] **Step 2: `FormatRecommendation.tsx`**

```tsx
import type { FormatRecommendation as Recommendation } from '../api/types'

/** Spec §6.1 R13 — the least separated format that clears the rules checked. */
export function FormatRecommendationPanel({ recommendation }: {
  recommendation: Recommendation
}) {
  return (
    <section data-testid="format-recommendation">
      <h3>Format</h3>
      <p className="blurb">{recommendation.message}</p>
      <table>
        <thead><tr><th>Format</th><th>Blockers</th></tr></thead>
        <tbody>
          {recommendation.options.map((option) => (
            <tr key={option.format} data-testid={`format-option-${option.format}`}
                className={option.format === recommendation.recommended ? 'row--recommended' : undefined}>
              <th scope="row">
                {option.title}
                {option.is_current && <small> — what you have now</small>}
                {option.format === recommendation.recommended && <small> — recommended</small>}
              </th>
              <td>{option.reds.length === 0 ? 'none on the rules checked' : option.reds.join(', ')}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {recommendation.unfixable.length > 0 && (
        <p className="blurb">
          {recommendation.unfixable.join(', ')} stop the formulation however it is
          packaged, so the fix is in the formulation itself rather than in the pack.
        </p>
      )}
    </section>
  )
}
```

Keep the copy plain and clear of the §10 prohibited words — `tests/test_web_language.py` reads every `.tsx` file under `web/src`, including this one.

- [ ] **Step 3: `VariantSuggestions.tsx`**

```tsx
import { useState } from 'react'

import type { Suggestion } from '../api/types'

const GROUP_TITLES: Record<string, string> = {
  applicable: 'Changes you can apply',
  note: 'Things to decide or to ask a supplier',
}

/** Spec §7 — never presented as pre-cleared: applying one re-runs every rule. */
export function VariantSuggestions({ suggestions, onApply }: {
  suggestions: Suggestion[]
  onApply: (suggestionId: number) => Promise<void>
}) {
  const [busy, setBusy] = useState<number | null>(null)
  const applicable = suggestions.filter((s) => s.is_applicable)
  const notes = suggestions.filter((s) => !s.is_applicable)

  if (suggestions.length === 0) return null

  async function apply(id: number) {
    setBusy(id)
    try {
      await onApply(id)
    } finally {
      setBusy(null)
    }
  }

  return (
    <section data-testid="variant-suggestions">
      <h3>{GROUP_TITLES.applicable}</h3>
      <p className="blurb">
        None of these is pre-cleared. Applying one copies this formulation, makes the
        change, and runs every rule again — its own flags are shown then.
      </p>
      <ul>
        {applicable.map((suggestion) => (
          <li key={suggestion.id} data-testid={`suggestion-${suggestion.id}`}>
            <div>{suggestion.description}</div>
            <small className="blurb">Raised by {suggestion.raised_by.join(', ')}</small>
            <button type="button" disabled={busy !== null}
                    data-testid={`apply-${suggestion.id}`}
                    onClick={() => apply(suggestion.id)}>
              {busy === suggestion.id ? 'Running…' : 'Apply and compare'}
            </button>
          </li>
        ))}
      </ul>

      {notes.length > 0 && (
        <>
          <h3>{GROUP_TITLES.note}</h3>
          <ul data-testid="suggestion-notes">
            {notes.map((suggestion) => (
              <li key={suggestion.id}>
                <div>{suggestion.description}</div>
                <small className="blurb">Raised by {suggestion.raised_by.join(', ')}</small>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
```

- [ ] **Step 4: Styles**

Append to `styles.css`:

```css
.banner { border: 1px solid var(--line); border-left: 4px solid var(--amber);
          background: var(--muted); padding: 0.75rem 1rem; margin: 1rem 0; }
.banner--stale code { font-size: 0.85em; }
.row--recommended { background: var(--muted); }
.cell--changed { background: var(--muted); font-weight: 600; }
.cell--absent { color: var(--gray); font-style: italic; }
.editor-field { display: grid; grid-template-columns: 12rem 1fr auto; gap: 0.5rem;
                align-items: center; margin: 0.25rem 0; }

/* Spec §10 screen 8 — print to PDF. Navigation and controls go; the disclaimer stays. */
@media print {
  header nav, button, .banner, .no-print { display: none !important; }
  .app { max-width: none; padding: 0; }
  a { text-decoration: none; color: inherit; }
  table { page-break-inside: auto; }
  tr { page-break-inside: avoid; }
  footer { border-top: 1px solid #000; }
}
```

- [ ] **Step 5: Typecheck and lint the copy**

Run: `cd web && npm run typecheck && cd .. && .venv/bin/pytest tests/test_web_language.py -q`
Expected: clean, and no prohibited word in the new components.

- [ ] **Step 6: Commit**

```bash
git add web/src/components web/src/styles.css
git commit -m "feat(web): add the stale banner, format panel, and suggestion list"
```

---

## Task 23: Verdict screen — the banner, the format call, the suggestions

**Files:**
- Modify: `web/src/screens/Verdict.tsx`, `web/src/App.tsx`

- [ ] **Step 1: Extend the screen**

```tsx
import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { api } from '../api/client'
import { DoseCards } from '../components/DoseCards'
import { EnvelopePanel } from '../components/EnvelopePanel'
import { FindingGroups } from '../components/FindingGroups'
import { FormatRecommendationPanel } from '../components/FormatRecommendation'
import { GiStrip } from '../components/GiStrip'
import { StaleBanner } from '../components/StaleBanner'
import { VariantSuggestions } from '../components/VariantSuggestions'
import { HeadlineBadge } from '../components/VerdictBadge'
import type { Evaluation } from '../api/types'

export default function Verdict() {
  const { evaluationId } = useParams()
  const navigate = useNavigate()
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!evaluationId) return
    api.evaluation(evaluationId).then(setEvaluation).catch((e) => setError(e.message))
  }, [evaluationId])

  const rerun = useCallback(async () => {
    if (!evaluation) return
    setError(null)
    try {
      const fresh = await api.evaluate(evaluation.formulation_id)
      navigate(`/evaluations/${fresh.id}`)
    } catch (e) {
      setError((e as Error).message)
    }
  }, [evaluation, navigate])

  const applyVariant = useCallback(async (suggestionId: number) => {
    if (!evaluation) return
    setError(null)
    try {
      const applied = await api.applyVariant(evaluation.id, suggestionId)
      // Workflow C: land in the comparison, not on a bare new verdict.
      navigate(`/compare?ids=${evaluation.id}&ids=${applied.id}`)
    } catch (e) {
      setError((e as Error).message)
    }
  }, [evaluation, navigate])

  if (error) return <p className="error">{error}</p>
  if (!evaluation) return <p>Loading…</p>

  return (
    <>
      <h1>Verdict</h1>
      {evaluation.stale && <StaleBanner changes={evaluation.changes} onRerun={rerun} />}
      <HeadlineBadge headline={evaluation.headline} />
      <p className="blurb">
        Run {evaluation.created_at.slice(0, 16).replace('T', ' ')} on engine{' '}
        {evaluation.engine_version}. This is a record of that run: editing a
        record afterwards does not change it. Re-run to see the effect of a change.
      </p>
      <p className="no-print">
        <Link to={`/evaluations/${evaluation.id}/report`}>Open the printable report</Link>
      </p>

      <FindingGroups
        blockers={evaluation.blockers}
        dataGaps={evaluation.data_gaps}
        cautions={evaluation.cautions}
        advisories={evaluation.advisories}
      />

      <DoseCards cards={evaluation.dose_cards} />
      <GiStrip lanes={evaluation.gi_strip} />
      <EnvelopePanel envelope={evaluation.envelope} />
      <FormatRecommendationPanel recommendation={evaluation.format_recommendation} />
      <VariantSuggestions suggestions={evaluation.suggestions} onApply={applyVariant} />
    </>
  )
}
```

- [ ] **Step 2: Add the three routes**

In `App.tsx`:

```tsx
import Compare from './screens/Compare'
import Database from './screens/Database'
import Report from './screens/Report'
...
        <nav>
          <Link to="/recipes/new">New recipe</Link>
          <Link to="/database">Database</Link>
        </nav>
...
          <Route path="/evaluations/:evaluationId" element={<Verdict />} />
          <Route path="/evaluations/:evaluationId/report" element={<Report />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/database" element={<Database />} />
```

The footer stays where it is — `tests/test_web_language.py::test_the_disclaimer_is_in_the_layout_not_a_single_screen` asserts no route can render without it, and three new routes is exactly the situation that test exists for.

- [ ] **Step 3: Commit**

```bash
git add web/src/screens/Verdict.tsx web/src/App.tsx
git commit -m "feat(web): show the stale banner, format call, and suggestions on the verdict"
```

---

## Task 24: Compare screen

**Files:**
- Create: `web/src/components/ComparisonTable.tsx`, `web/src/screens/Compare.tsx`

- [ ] **Step 1: The table**

```tsx
import type { Comparison } from '../api/types'

const SECTIONS = ['Verdict', 'Setup', 'Rules', 'Dose per serving', 'Occasion envelope']

export function ComparisonTable({ comparison, changedOnly }: {
  comparison: Comparison
  changedOnly: boolean
}) {
  const rows = changedOnly ? comparison.rows.filter((r) => r.changed) : comparison.rows

  return (
    <table data-testid="comparison">
      <thead>
        <tr>
          <th />
          {comparison.columns.map((column) => (
            <th key={column.evaluation_id} className={`headline--${column.headline.toLowerCase()}`}>
              {column.label}
            </th>
          ))}
        </tr>
      </thead>
      {SECTIONS.map((section) => {
        const sectionRows = rows.filter((r) => r.section === section)
        if (sectionRows.length === 0) return null
        return (
          <tbody key={section}>
            <tr><th colSpan={comparison.columns.length + 1}>{section}</th></tr>
            {sectionRows.map((row) => (
              <tr key={row.key} data-testid={`row-${row.key}`}
                  className={row.changed ? 'row--changed' : undefined}>
                <th scope="row">{row.label}</th>
                {row.cells.map((cell, index) => (
                  <td key={index}
                      className={[
                        row.changed ? 'cell--changed' : '',
                        cell.present ? '' : 'cell--absent',
                      ].join(' ')}>
                    {cell.text}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        )
      })}
    </table>
  )
}
```

- [ ] **Step 2: The screen**

```tsx
import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { api } from '../api/client'
import { ComparisonTable } from '../components/ComparisonTable'
import type { Comparison } from '../api/types'

/** Spec §3 Workflow B — one column per variant, changed cells highlighted. */
export default function Compare() {
  const [params] = useSearchParams()
  const ids = params.getAll('ids')
  const [comparison, setComparison] = useState<Comparison | null>(null)
  const [changedOnly, setChangedOnly] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (ids.length < 2) {
      setError('Pick at least two evaluations to compare.')
      return
    }
    api.compare(ids).then(setComparison).catch((e) => setError(e.message))
    // ids is a fresh array each render; the joined string is the real dependency.
  }, [ids.join(',')])

  if (error) return <p className="error">{error}</p>
  if (!comparison) return <p>Loading…</p>

  return (
    <>
      <h1>Compare variants</h1>
      <p className="blurb">
        A row that is present on one side and absent on another reads "not in this
        variant" rather than disappearing — that difference is usually the point.
      </p>
      <label>
        <input type="checkbox" checked={changedOnly} data-testid="changed-only"
               onChange={(e) => setChangedOnly(e.target.checked)} />
        Show only what changed
      </label>

      <ComparisonTable comparison={comparison} changedOnly={changedOnly} />

      <ul>
        {comparison.columns.map((column) => (
          <li key={column.evaluation_id}>
            <Link to={`/evaluations/${column.evaluation_id}`}>{column.label}</Link>
          </li>
        ))}
      </ul>
    </>
  )
}
```

- [ ] **Step 3: Typecheck**

Run: `cd web && npm run typecheck && npm run build`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add web/src/components/ComparisonTable.tsx web/src/screens/Compare.tsx
git commit -m "feat(web): add the side-by-side comparison screen"
```

---

## Task 25: Database screen — editors, reset, and the proposals inbox

Workflow D. Every field shows value, status, source, and a reset next to the record.

**Files:**
- Create: `web/src/screens/Database.tsx`

- [ ] **Step 1: Write the screen**

```tsx
import { useEffect, useState } from 'react'

import { api } from '../api/client'
import { TruthValue } from '../components/TruthValue'
import type { Enzyme, Food, Proposal, Tracked } from '../api/types'

/** The fields `store/records.py` will accept. Keep the two lists in step. */
const ENZYME_FIELDS = [
  'ph_min', 'ph_max', 'ph_opt_low', 'ph_opt_high', 'ph_shelf_stable_min',
  'temp_min_c', 'temp_max_c', 'temp_opt_c',
  'dose_min', 'dose_max', 'dose_evidence_threshold',
] as const
const FOOD_FIELDS = ['ph', 'water_content_pct', 'typical_load_value'] as const

function FieldRow({ name, tracked, onSave }: {
  name: string
  tracked: Tracked
  onSave: (value: number | null) => void
}) {
  const [draft, setDraft] = useState(tracked.value === null ? '' : String(tracked.value))
  useEffect(() => { setDraft(tracked.value === null ? '' : String(tracked.value)) },
            [tracked.value])

  return (
    <div className="editor-field">
      <label htmlFor={`field-${name}`}>{name}</label>
      <input id={`field-${name}`} data-testid={`field-${name}`} value={draft}
             onChange={(e) => setDraft(e.target.value)} />
      <span>
        <TruthValue tracked={tracked} />{' '}
        <button type="button" data-testid={`save-${name}`}
                onClick={() => onSave(draft === '' ? null : Number(draft))}>
          Save
        </button>
      </span>
    </div>
  )
}

export default function Database() {
  const [enzymes, setEnzymes] = useState<Enzyme[]>([])
  const [foods, setFoods] = useState<Food[]>([])
  const [proposals, setProposals] = useState<Proposal[]>([])
  const [enzymeId, setEnzymeId] = useState('')
  const [foodId, setFoodId] = useState('')
  const [error, setError] = useState<string | null>(null)

  async function reload() {
    const [e, f, p] = await Promise.all([api.enzymes(), api.foods(), api.proposals()])
    setEnzymes(e); setFoods(f); setProposals(p)
    if (!enzymeId && e.length) setEnzymeId(e[0]!.id)
    if (!foodId && f.length) setFoodId(f[0]!.id)
  }

  useEffect(() => { reload().catch((e) => setError(e.message)) }, [])

  const enzyme = enzymes.find((e) => e.id === enzymeId)
  const food = foods.find((f) => f.id === foodId)

  async function run(work: () => Promise<unknown>) {
    setError(null)
    try { await work(); await reload() } catch (e) { setError((e as Error).message) }
  }

  return (
    <>
      <h1>Database</h1>
      {error && <p className="error" data-testid="database-error">{error}</p>}
      <p className="blurb">
        Anything you type here is stored as your own value and labelled that way. A
        value only becomes confirmed through the inbox below, where it arrives with a
        source. Editing a record never changes an evaluation that has already run —
        those runs will show a banner asking you to re-run.
      </p>

      <fieldset>
        <legend>Enzymes</legend>
        <select value={enzymeId} data-testid="enzyme-picker"
                onChange={(e) => setEnzymeId(e.target.value)}>
          {enzymes.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select>
        {enzyme && (
          <>
            {ENZYME_FIELDS.map((name) => (
              <FieldRow key={name} name={name} tracked={enzyme[name]}
                        onSave={(value) => run(() => api.updateEnzyme(enzyme.id, { [name]: value }))} />
            ))}
            <button type="button" data-testid="reset-enzyme"
                    onClick={() => run(() => api.resetEnzyme(enzyme.id))}>
              Reset this enzyme to the shipped values
            </button>
          </>
        )}
      </fieldset>

      <fieldset>
        <legend>Foods</legend>
        <select value={foodId} data-testid="food-record-picker"
                onChange={(e) => setFoodId(e.target.value)}>
          {foods.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
        </select>
        {food && (
          <>
            {FOOD_FIELDS.map((name) => (
              <FieldRow key={name} name={name} tracked={food[name]}
                        onSave={(value) => run(() => api.updateFood(food.id, { [name]: value }))} />
            ))}
            <button type="button" data-testid="reset-food"
                    onClick={() => run(() => api.resetFood(food.id))}>
              Reset this food to the shipped values
            </button>
          </>
        )}
      </fieldset>

      <fieldset>
        <legend>Proposals waiting on you</legend>
        <p className="blurb">
          Each one carries a source. Approving records the value as confirmed with that
          source attached; rejecting changes nothing and keeps the record of the decision.
        </p>
        {proposals.length === 0 ? (
          <p>Nothing waiting.</p>
        ) : (
          <table>
            <thead>
              <tr><th>Record</th><th>Field</th><th>Value</th><th>Source</th><th>Status</th><th /></tr>
            </thead>
            <tbody>
              {proposals.map((proposal) => (
                <tr key={proposal.id} data-testid={`proposal-${proposal.id}`}>
                  <td>{proposal.table_name} {proposal.record_id}</td>
                  <td>{proposal.field}</td>
                  <td>{proposal.proposed_value}</td>
                  <td>{proposal.source_citation}</td>
                  <td>{proposal.status}</td>
                  <td>
                    {proposal.status === 'pending' && (
                      <>
                        <button type="button" data-testid={`approve-${proposal.id}`}
                                onClick={() => run(() => api.approveProposal(proposal.id))}>
                          Approve
                        </button>
                        <button type="button"
                                onClick={() => run(() => api.rejectProposal(proposal.id))}>
                          Reject
                        </button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </fieldset>
    </>
  )
}
```

`enzyme[name]` and `food[name]` typecheck because every entry in the two constant
arrays is a `Tracked` field on its interface; if a name is added that is not, `tsc`
says so, which is the point of the `as const`.

- [ ] **Step 2: Typecheck and build**

Run: `cd web && npm run typecheck && npm run build`
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add web/src/screens/Database.tsx
git commit -m "feat(web): add the database editor and proposals inbox"
```

---

## Task 26: Report screen — print-friendly

§2.1 asks for a print-friendly report view (browser print → PDF). The Markdown export is the machine-readable sibling; this is the page she prints.

**Files:**
- Create: `web/src/screens/Report.tsx`

- [ ] **Step 1: Write the screen**

```tsx
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

import { api } from '../api/client'
import { DoseCards } from '../components/DoseCards'
import { EnvelopePanel } from '../components/EnvelopePanel'
import { FindingGroups } from '../components/FindingGroups'
import { FormatRecommendationPanel } from '../components/FormatRecommendation'
import { GiStrip } from '../components/GiStrip'
import { HeadlineBadge } from '../components/VerdictBadge'
import type { Evaluation } from '../api/types'

/** Spec §10 screen 8. The footer disclaimer comes from the layout and prints with it. */
export default function Report() {
  const { evaluationId } = useParams()
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!evaluationId) return
    api.evaluation(evaluationId).then(setEvaluation).catch((e) => setError(e.message))
  }, [evaluationId])

  if (error) return <p className="error">{error}</p>
  if (!evaluation) return <p>Loading…</p>

  return (
    <>
      <h1>Formulation report</h1>
      <p className="no-print">
        <button type="button" data-testid="print" onClick={() => window.print()}>
          Print or save as PDF
        </button>
        {' '}
        <a href={api.reportUrl(evaluation.id)} data-testid="download-markdown">
          Download the markdown version
        </a>
      </p>

      <HeadlineBadge headline={evaluation.headline} />
      <p className="blurb">
        Evaluation {evaluation.id}, run {evaluation.created_at.slice(0, 16).replace('T', ' ')}{' '}
        on engine {evaluation.engine_version}.
        {evaluation.stale && ' A record it used has changed since; re-run before relying on it.'}
      </p>

      <FindingGroups
        blockers={evaluation.blockers}
        dataGaps={evaluation.data_gaps}
        cautions={evaluation.cautions}
        advisories={evaluation.advisories}
      />
      <DoseCards cards={evaluation.dose_cards} />
      <GiStrip lanes={evaluation.gi_strip} />
      <EnvelopePanel envelope={evaluation.envelope} />
      <FormatRecommendationPanel recommendation={evaluation.format_recommendation} />

      <section data-testid="observed">
        <h3>What was observed</h3>
        <p>
          No trial has been recorded for this formulation yet. Everything above is a
          prediction from the rules and the data behind them; nothing here was measured.
        </p>
      </section>

      <section>
        <h3>Open questions</h3>
        <ul>
          {evaluation.suggestions
            .filter((s) => s.suggestion_type === 'supplier_question')
            .map((s) => (
              <li key={s.id}>{s.description} <small className="blurb">({s.raised_by.join(', ')})</small></li>
            ))}
        </ul>
      </section>
    </>
  )
}
```

The observed section repeats `engine/report.py`'s wording deliberately: the printed page and the exported Markdown are the same document in two media, and a founder handing over both should not find them saying different things. If that wording changes, change it in both places — Task 29's acceptance walk checks it.

- [ ] **Step 2: Typecheck, build, and lint the copy**

Run: `cd web && npm run typecheck && npm run build && cd .. && .venv/bin/pytest tests/test_web_language.py -q`
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add web/src/screens/Report.tsx
git commit -m "feat(web): add the print-friendly report screen"
```
---

## Task 27: Docker, compose, and build polish

§14's M3 line ends with "Docker compose polish". Four concrete things, each of which is a real defect rather than a tidy-up.

**Files:**
- Create: `.dockerignore`
- Modify: `Dockerfile`, `docker-compose.yml`, `Makefile`

- [ ] **Step 1: Stop shipping the repository into the build context**

There is no `.dockerignore`, so `docker build` uploads `.git`, `.venv`, `data/` (the founder's live database), `web/node_modules`, and every Playwright artefact before the first `COPY` runs. Create `.dockerignore`:

```
.git
.gitignore
.venv
.pytest_cache
.ruff_cache
__pycache__
*.egg-info
data
*.db
web/node_modules
web/dist
web/test-results
web/playwright-report
web/.e2e
.claude
docs
fwbackgroundmaterials
```

`data` matters most: a stale copy of the founder's database in the build context is both slow and a data-handling mistake waiting to happen.

- [ ] **Step 2: Stop shipping the test suite and pytest into the runtime image**

```dockerfile
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/
COPY seed/ ./seed/
# Editable, deliberately: seedload resolves `seed/` as parents[3] of its own
# module path, so a site-packages install would not find the seed JSON.
RUN pip install --no-cache-dir -e .

COPY --from=web /web/dist ./web/dist

ENV FOODBREW_DB_PATH=/data/foodbrew.db \
    FOODBREW_WEB_DIST=/app/web/dist

EXPOSE 8000
CMD ["uvicorn", "foodbrew.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

Nothing runs the suite inside the container — CI installs the project itself and Playwright drives the local `.venv` — so `[dev]` and `COPY tests/` only made the image bigger.

- [ ] **Step 3: Give compose a health check and a restart policy**

```yaml
services:
  foodbrew:
    build: .
    ports:
      - "8000:8000"
    volumes:
      # SQLite lives in a bind mount so backup is a folder copy and the same
      # image deploys to Fly.io later with a volume instead.
      - ./data:/data
    environment:
      FOODBREW_DB_PATH: /data/foodbrew.db
      FOODBREW_WEB_DIST: /app/web/dist
    restart: unless-stopped
    healthcheck:
      test:
        - CMD
        - python
        - -c
        - "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')"
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s
```

The check uses the interpreter that is already in the image rather than adding `curl` to it.

- [ ] **Step 4: One Makefile target**

```makefile
report:
	@test -n "$(EVAL)" || (echo 'usage: make report EVAL=<evaluation id>' && exit 1)
	curl -sf http://localhost:8000/api/v1/export/$(EVAL).md
```

Add `report` to the `.PHONY` line. There is deliberately no `reset` target: the global reset is a button on the Database screen now, and `make db` already exists for the "throw the database away" case.

- [ ] **Step 5: Verify the container still works end to end**

Run: `docker compose up --build -d && sleep 15 && curl -sf localhost:8000/api/v1/health && docker compose ps`
Expected: the health endpoint answers, and `docker compose ps` reports the service healthy. Then check the image shrank and carries no test suite:

Run: `docker compose run --rm foodbrew python -c "import pathlib; print(pathlib.Path('/app/tests').exists())"`
Expected: `False`.

Run: `docker compose down`

- [ ] **Step 6: Commit**

```bash
git add .dockerignore Dockerfile docker-compose.yml Makefile
git commit -m "chore: trim the runtime image and add a compose health check"
```

---

## Task 28: End-to-end — apply a variant, compare, edit, report

**Files:**
- Create: `web/e2e/variants.spec.ts`

- [ ] **Step 1: Write the spec**

```typescript
import { expect, test } from '@playwright/test'

/** Builds the golden-fixture (a) vinaigrette and stops on its RED verdict. */
async function buildAndEvaluate(page: import('@playwright/test').Page) {
  await page.goto('/recipes/new')
  await page.getByTestId('recipe-name').fill('E2E variant vinaigrette')
  await page.getByTestId('food-picker').selectOption({ label: 'Olive oil' })
  await page.getByTestId('food-picker').selectOption({ label: 'White vinegar' })
  await page.getByTestId('amount-olive_oil').fill('100')
  await page.getByTestId('amount-white_vinegar').fill('50')
  await page.getByTestId('save-recipe').click()
  await page.getByTestId('to-formulation').click()

  await page.getByTestId('trigger-milk').check()
  await page.getByTestId('measured-ph').fill('3.0')
  await page.getByTestId('run-evaluation').click()
  await expect(page.getByTestId('headline')).toContainText('RED')
  return page.url()
}

test('the verdict offers a format it can actually reach', async ({ page }) => {
  await buildAndEvaluate(page)
  const recommendation = page.getByTestId('format-recommendation')
  await expect(recommendation).toBeVisible()
  await expect(recommendation).toContainText('R1')
  await expect(page.getByTestId('format-option-dry_sachet')).toContainText(
    'none on the rules checked',
  )
})

test('applying a suggestion lands in the comparison with the headline moved', async ({ page }) => {
  await buildAndEvaluate(page)

  const dry = page
    .getByTestId('variant-suggestions')
    .locator('li', { hasText: 'dry sachet' })
    .first()
  await dry.getByRole('button', { name: 'Apply and compare' }).click()

  await expect(page.getByTestId('comparison')).toBeVisible()
  const headline = page.getByTestId('row-headline')
  await expect(headline).toContainText('RED')
  await expect(headline).toHaveClass(/row--changed/)
  await expect(page.getByTestId('row-format')).toContainText('dry_sachet')
})

test('a note is offered without an apply button', async ({ page }) => {
  await buildAndEvaluate(page)
  const notes = page.getByTestId('suggestion-notes')
  await expect(notes).toBeVisible()
  await expect(notes.getByRole('button')).toHaveCount(0)
})

test('editing a record makes the earlier verdict say so', async ({ page }) => {
  const verdictUrl = await buildAndEvaluate(page)

  await page.goto('/database')
  await page.getByTestId('enzyme-picker').selectOption('lactase_fungal_acid')
  await page.getByTestId('field-ph_shelf_stable_min').fill('2.5')
  await page.getByTestId('save-ph_shelf_stable_min').click()
  await expect(page.getByTestId('field-ph_shelf_stable_min')).toHaveValue('2.5')

  await page.goto(verdictUrl)
  const banner = page.getByTestId('stale-banner')
  await expect(banner).toBeVisible()
  await expect(banner).toContainText('lactase_fungal_acid')

  await page.getByTestId('rerun').click()
  await expect(page.getByTestId('stale-banner')).toHaveCount(0)
})

test('the report prints and offers the markdown', async ({ page }) => {
  await buildAndEvaluate(page)
  await page.getByRole('link', { name: 'Open the printable report' }).click()

  await expect(page.getByTestId('observed')).toContainText('No trial has been recorded')
  await expect(page.getByTestId('download-markdown')).toBeVisible()
  await expect(page.locator('footer')).toContainText(
    'Not a safety, efficacy, or regulatory determination.',
  )

  const href = await page.getByTestId('download-markdown').getAttribute('href')
  const response = await page.request.get(href!)
  expect(response.status()).toBe(200)
  expect(await response.text()).toContain('# Formulation report')
})
```

If the assertion about the headline row's exact text proves brittle, assert on
`row-format` and on the presence of `cell--changed` instead — the behavioural
claim is "the comparison opened and it shows a difference", not the phrasing.

- [ ] **Step 2: Run it**

Run: `cd web && npm run build && npm run e2e`
Expected: 7 passed — the two M2 specs and these five.

- [ ] **Step 3: Commit**

```bash
git add web/e2e/variants.spec.ts
git commit -m "test(web): cover apply-variant, compare, the editor, and the report"
```

---

## Task 29: Full acceptance run

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document what M3 added**

Append to `README.md`:

```markdown
## Working a verdict

From a verdict screen you can:

- **Apply a suggested change.** Each one copies the formulation, makes the change,
  and runs every rule again. Nothing is pre-cleared — you land in the comparison
  with both versions side by side.
- **Compare variants** at `/compare?ids=…`, up to six at a time. A row present on
  one side and absent on another says so rather than disappearing.
- **Print the report** or download the same content as Markdown from
  `/api/v1/export/<evaluation id>.md`.

## The database screen

`/database` edits any enzyme or food field. Anything you type is stored as your
own value and labelled that way. A value becomes *confirmed* only through the
proposals inbox on the same screen, where it arrives with a source citation —
that citation is what the label means.

Editing a record never changes an evaluation that has already run. Those runs
show a banner naming what changed and offering a re-run. "Reset to the shipped
values" restores one record from `seed/*.json`; the reset on the whole
reference set discards every edit to every enzyme and food.

## Checks

    make test    # pytest: engine, store, API, contracts
    make lint    # ruff
    make e2e     # Playwright, against the built app
    make report EVAL=<evaluation id>   # the markdown export, from a running server
```

- [ ] **Step 2: Run everything**

Run: `.venv/bin/ruff check src tests && .venv/bin/pytest -q && cd web && npm run typecheck && npm run build && npm run e2e`
Expected: ruff clean, every test green, no type errors, a `web/dist` build, seven Playwright specs passing.

- [ ] **Step 3: Walk the exit check by hand**

Start `make up`, open `http://localhost:8000`, and complete the whole M3 loop without touching the API directly:

1. Build the vinaigrette, set up a premixed-wet formulation with a dairy trigger food and pH 3.0, and read a RED verdict naming R1.
2. Read the format panel. Confirm it recommends a separated format and names R1 as the blocker under premixed wet.
3. Apply the dry-sachet suggestion. Confirm you land in the comparison, that the headline row is marked changed, and that R1's row reads "not in this variant" on the new side.
4. Apply a note-type suggestion — confirm there is no button to.
5. Open `/database`, set `ph_shelf_stable_min` on the fungal lactase to 2.5, and check the field now reads "you entered this".
6. Go back to the first verdict. Confirm the banner names the enzyme and the field, and that re-running clears it and changes the headline.
7. Create a proposal for the same field with a citation, approve it, and confirm the field now reads "confirmed" with the citation as its source.
8. Reset that enzyme and confirm the shipped value and its label come back.
9. Open the printable report, print to PDF, and confirm the disclaimer is on the printed page and the navigation is not.
10. Download the Markdown export and confirm it says the same things.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document variants, compare, the database screen, and the report"
```

---

## M3 exit criteria

Before declaring M3 done, all of the following must hold:

- [ ] `.venv/bin/pytest -q` passes with zero failures and zero skips.
- [ ] `.venv/bin/ruff check src tests` is clean.
- [ ] `cd web && npm run typecheck && npm run build` succeeds.
- [ ] `cd web && npm run e2e` passes all seven specs against the built app.
- [ ] **Every M1 and M2 test still passes unchanged.** M3 refactors four engine modules (Tasks 1, 2, 5) and changes no verdict; a single moved golden fixture means an extraction was not faithful.
- [ ] `tests/engine/test_variants.py::test_every_applicable_patch_re_evaluates_without_error` and `tests/api/test_variants.py::test_every_applicable_suggestion_re_evaluates_without_error` both pass — spec §13's contract test, at both levels.
- [ ] `tests/engine/test_report.py::test_no_prohibited_word_survives_the_report_lint` and `tests/api/test_export.py::test_the_export_carries_no_prohibited_word` pass — spec §13's report lint over generated output, not just source.
- [ ] `tests/engine/test_language.py::test_no_prohibited_word_appears_in_the_shipped_seed` passes: the report quotes seed text, so the seed complies too.
- [ ] `tests/api/test_contracts_m3.py` passes in full: no request schema accepts a patch, no router names a patch op, and the M1 and M2 layering boundaries survive five new engine modules and four new routers.
- [ ] `tests/store/test_staleness.py::test_re_running_does_not_make_the_first_run_stale` passes — the banner does not flap.
- [ ] `tests/store/test_proposals.py::test_a_direct_edit_still_cannot_produce_confirmed` passes: `confirmed` has exactly one producer.
- [ ] `docker compose up --build` reports the service healthy, and `/app/tests` does not exist in the image.
- [ ] The founder can complete the hand walk in Task 29 step 3 without help, and without opening a terminal.

**Do not begin M4 until these pass.** M4's protocol generation reads an evaluation's findings and data gaps to decide what to watch, which is the same read path the report's open-questions section uses; and M4's `trial_batch.measured_ph` is the third branch of §6.7's pH resolution, which will make an existing evaluation stale the moment it is written — the banner has to be honest before a trial can write to it.

---

## Plan self-review

**Spec coverage.** §2.1's print-friendly report → Tasks 7, 26. §2.3's research track → Tasks 12, 18, 25. §3 Workflow B → Tasks 6, 16, 24. Workflow C → Tasks 3, 5, 13, 16, 23. Workflow D → Tasks 11, 12, 17, 18, 25. §5.2's three unwritten tables — `variant_suggestion`, `proposal`, `audit_event` → Tasks 9, 12, 8. §5.4's truth labels → Tasks 11, 12 (the two write paths, decision #7). §6.1 R13's format recommendation → Tasks 4, 15, 23. §7's fix catalogue, row by row → Task 5. §10's endpoint list: `POST /evaluations/{id}/apply-variant` (Task 16), `GET /compare?ids=…` (Task 16), the proposals inbox (Task 18), `GET /export/{id}.md` (Task 19). §10 screens 5, 7, 8 → Tasks 24, 25, 26; screen 4's stale banner → Tasks 10, 15, 22, 23. §12 items 1 and 5 constrain Task 5 and are why two §7 entries carry no patch. §13's contract test → Tasks 5, 16; its report lint → Tasks 1, 7, 19. §14's M3 line, item by item: auto-variants (Task 5), side-by-side compare (Tasks 6, 24), proposals inbox (Tasks 12, 18, 25), stale-evaluation banner (Tasks 10, 15, 22), print report (Tasks 7, 19, 26), Docker compose polish (Task 27).

**Deliberately not in M3**, consistent with §14 and with M2's self-review: every Workflow E surface — `engine/protocol.py`, the trial/batch/observation/symptom tables, the storage gate in the browser, the live dose math, the predicted-vs-observed column, and §6.6's honesty split in the report. One forward reach is deliberate and named in decision #12: the report's observed section exists and says there is no trial, so M4 fills it instead of restructuring the document.

**Placeholder scan.** There are no stubs. Every module named in the file structure is written in full in the task that creates it, and every test file is written out rather than described. The three note-type suggestions carry `patch = None` by design, not as a TODO — Task 5's `test_notes_never_carry_a_patch` asserts the distinction is deliberate on both sides.

**Type consistency.** `Tracked` remains the single carrier of a value's label, and M3 adds two writers to that chain — `records.update` (always `user_provided`) and `records.set_confirmed` (only from a proposal) — with Tasks 11 and 12 asserting each. `ValidationRejection` continues to be the one refusal type: `engine/patch.py`, `engine/compare.py`, `store/records.py`, and `store/proposals.py` all raise it and it maps to HTTP 422 in the single handler M2 wrote. A patch is `{"ops": [...]}` from the moment `engine/variants.py` builds it to the moment `engine/patch.apply_patch` consumes it, with `store/variants.py` carrying `raised_by` alongside it in the same JSON column; nothing between them reshapes it. `phase_for_format` and `shelf_stable_floor` each have exactly one definition after Task 2, which is the point of that task.

**Known cross-task dependencies.** Task 1 (`language.py`) precedes Task 7, whose lint imports it. Task 2 (`conventions`) precedes Tasks 3 and 5, which import `phase_for_format` and `shelf_stable_floor`. Task 3 (`patch.py`) precedes Task 4, which builds its ladder candidates with `apply_patch`, and Task 5, which uses `apply_patch` as its own guard. Task 5 precedes Task 9, which stores what it produces, and Task 7, which prints it. Task 8 (`audit.py`) precedes Tasks 11 and 12, which both record events. Task 11's column allowlist precedes Task 12, which parses proposal values with it. Tasks 4, 9 and 10 all precede Task 15, whose payload carries all three. Task 15 precedes Task 16, which imports `evaluation_out`. Task 21 (types and client) precedes every other web task. Task 27 precedes Task 28 only in that a broken image would fail the acceptance run, not the Playwright specs, which drive the local `.venv`.

**Where this plan is most likely to be wrong.** Three places, in order:

1. **The format ladder's `encapsulated_in_wet` candidate.** Setting `encapsulated = True` for that position (decision #5) is an interpretation of §6.1 R6, not a quotation of it. If the founder means "encapsulated in wet" to describe a product where only *some* enzymes are in capsules, the ladder is answering a slightly different question than she asked. Task 4's `test_encapsulated_in_wet_is_evaluated_with_the_capsule_on` is where that assumption is written down.
2. **Scanning the ladder from the top rather than from the current format** (decision #6). It can recommend a *less* separated format than the one she has chosen, which is either a useful finding or a confusing one depending on how settled her format decision is. It is one line to change if the review disagrees.
3. **Suggestions stored, format recommendation derived** (decision #3). The split is defensible and the reasons are written down, but it means two things on the same screen have different freshness semantics under an engine-version bump: the suggestions are what the old engine said, the recommendation is what the current one says. That is invisible today because `ENGINE_VERSION` has not moved. The first time it does, this is the thing to re-read.
