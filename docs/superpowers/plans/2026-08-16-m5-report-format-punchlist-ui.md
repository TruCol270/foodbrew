# M5 — Scientist-Standard Report, v1 Punch List, Spec Amendments, and the UI Pass

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish v1. M4 closed the prediction-to-reality loop; what remains is everything that stands between "the tool works" and "the founder hands its output to a food scientist and it reads like a document that profession already uses." Four work packages: **A** reformats the report to match the conventions of a real bench sheet and product specification (percent-of-total formula, order of addition, batch records, an allergen declaration); **B** closes the four gaps a full spec-vs-code audit found; **C** writes four milestones of accepted deviations into the spec so the document stops lying about the build; **D** takes the UI from a bare 32/100 to something usable in a kitchen, on a phone, by someone holding a whisk.

**Architecture:** Layers unchanged — `api → store → engine`, engine pure. The one structural first: **M5 is the milestone that adds the repo's first schema migration**, because `CREATE TABLE IF NOT EXISTS` is a no-op against an existing database and `ensure_database` has never checked columns (decision #1). Everything else is additive: one new engine section-builder, one new read endpoint, one enum-validated edit path, one stylesheet.

**Tech Stack:** Unchanged. Python 3.12, FastAPI, Uvicorn, Pydantic v2, stdlib `sqlite3`, pytest + httpx `TestClient`, React 19 + TypeScript + Vite, react-router-dom, Playwright, Docker multi-stage. **No new runtime dependency, no CSS framework, no component library** (decisions #12 and #9).

**Spec:** `docs/superpowers/specs/2026-08-13-enzyme-rules-engine-design.md` — read §2.3 (the research track), §3 Workflow D, §5.1 (the `food` table), §5.4 (truth labels), §6.3.1 (the severity tiers, which matter more here than they look), §10 (the API, screens 6-8, and the language policy), §12 (the limitations the report must keep visible), §14, §15 items 4 and 7.

**External research this plan is based on:** the formula/bench-sheet and specification conventions food scientists actually use — percent-of-total ingredient tables summing to 100 with weights beside them, ingredients ordered by addition, physico-chemical targets expressed as ranges, and an allergen declaration. Sources are listed in Task 3, and the conventions are quoted where they drive a decision. Baker's percentage is deliberately **not** used: it is a flour-basis convention and a dressing has no flour.

**Prior milestones:**
- M1 `docs/superpowers/plans/2026-08-13-m1-engine-and-seed.md` — merged `cc0ed27`.
- M2 `docs/superpowers/plans/2026-08-14-m2-api-and-core-ui.md` — merged `58a7c3f`.
- M3 `docs/superpowers/plans/2026-08-14-m3-variants-compare-database-report.md` — merged `519ba01`.
- M4 `docs/superpowers/plans/2026-08-15-m4-kitchen-trial.md` — PR #4, branch `claude/m4-implementation-plan`, 664 python tests and 15 Playwright cases green. **M5 branches from that branch** and must be executed on top of it.

---

## What M5 is not

- **Not new science.** No rule changes, no verdict changes, no new engine decision. `ENGINE_VERSION` stays `1.0.0` and every golden fixture keeps its current verdict. If a task moves a fixture, that task is wrong.
- **Not the deferred features.** Cost modelling, the numeric solver, the LLM layer, hosted multi-user, blinded or multi-subject trials, and consumer timing guidance all stay out (§2.2, §11).
- **Not a nutrition panel, a water-activity target, or a viscosity spec.** Real specification sheets carry these; this product has no data source for any of them, and inventing target ranges would violate the no-orphan-numbers rule the whole tool exists to enforce. The report names them as *not measured* instead — which is itself the scientist-facing convention for an incomplete spec.
- **Not a redesign.** Package D is tokens, states, hierarchy, and mobile. Same screens, same components, same data flow, same test ids.
- **Not a rewrite of the trial or the rules.** M4's surfaces are finished; M5 touches them only where the audit found a gap.

---

## Spec deviations and decisions this plan resolves

Found by auditing the shipped code against every section of the spec, and by researching what the report is supposed to look like. Items 1, 2, 4, 5 and 8 are the load-bearing ones.

**1. M5 adds the repo's first migration, because the current boot check cannot see a new column.** `db/bootstrap.py`'s `ensure_database` compares table *names* against `sqlite_master` and nothing else, and `create_database` runs `executescript(schema.sql)` whose `CREATE TABLE IF NOT EXISTS` is a **no-op against an existing table**. So adding a column to `schema.sql` today gives you a database that boots clean and then raises `sqlite3.OperationalError: no such column` on the first write. M3 and M4 both dodged this by fitting inside the existing schema; M5 cannot, because an allergen declaration has nowhere to live. **This plan adds an explicit, ordered, idempotent migration list to `bootstrap.py`** — each entry a `(table, column, ddl)` triple applied with `ALTER TABLE ... ADD COLUMN` when `PRAGMA table_info` says it is absent — plus a column-level check that raises the same plain-English error `ensure_database` already raises for a missing table. It is twenty lines, it is testable against a database created by M1's schema, and it is the smallest honest thing that makes the next four columns possible.

**2. Allergens are a list column with a closed vocabulary, not a free-text note.** The established pattern for a multi-valued field on `food` is `<field>_json TEXT NOT NULL DEFAULT '[]'` (`contains_substrate_ids_json`, `structural_json`), so this is `allergens_json`. The vocabulary is the nine US major allergens — milk, egg, fish, crustacean shellfish, tree nut, peanut, wheat, soy, sesame — as a closed `StrEnum`, because an allergen declaration built from free text is a declaration nobody can lint. **No rule reads it.** `Food.notes` is the precedent: a catalogue field that travels with the evaluation and influences no verdict. Flag to the spec owner: §5.1's `food` table has an `allergen_note` field in the *original* tomato-sauce spec's data model but not in this one; M5 introduces it properly and §5.1 needs the row.

**3. The allergen list travels in the snapshot, and one stale banner is the price.** The report renders from the evaluation's frozen snapshot, so an allergen declaration that is *not* in the snapshot would describe today's catalogue rather than the evaluation's. It goes in `_food_out`/`_food_in` (`store/snapshot.py:107`), with `_food_in` reading it through `raw.get("allergens", [])` so **every pre-M5 snapshot still thaws**. `SNAPSHOT_VERSION` stays `1` — its docstring says it bumps only when old snapshots become unreadable, and these stay readable. The visible consequence: every evaluation that ran before M5 shows M3's "data changed since this evaluation" banner once. That is honest, and Task 9 makes `diff_snapshots` say *why* — "a field was added by an upgrade" rather than implying the founder edited something.

**4. `degrades_structural` and `structural` do NOT become `Tracked`, because the tier already carries the provenance.** §15 item 4 — *does inulinase degrade the structure of inulin-rich vegetables?* — needs an in-product way to record its answer, and today neither column is editable or proposable. The obvious move is to add them to `records.TRACKED_FIELDS`, and it is wrong: they are bare JSON columns with no `_status`/`_source` pair, their dataclass fields are plain tuples, and `r15_applied_texture.py` reads them directly (`for entry in enzyme.degrades_structural`, `entry.structural_class in food.structural`). Wrapping them in `Tracked` means editing the rule, the snapshot, `rowmap`, and both API serializers to chase a label that **already exists inside the value**: `SeverityTier.UNCONFIRMED` *is* the unconfirmed state, and §6.3.1 maps it to `cannot_assess` on every profile. So M5 adds a **structured-field edit path** — enum-validated JSON, its own allowlist, its own proposal kind — and leaves R15, the snapshot shape, and the `Tracked` machinery untouched. Answering §15 item 4 is then exactly what it should be: flipping inulinase's `pectin_cellulose` entry from `unconfirmed` to `gradual`, with a citation, through the proposals inbox.

**5. Last-edited is derived from `audit_event`, with no new column.** Workflow D asks each field to show "value, unit, status, source note, last-edited". The first four are data the record already has; the fifth is history, and history already exists — `store/audit.py` writes an `audit_event` per edit with `entity` set to `"<table>:<id>"`. A `MAX(timestamp) GROUP BY entity` query gives per-record last-edited for free. **Per-field** last-edited would need a column and is not what the screen needs. One honest caveat the plan implements rather than hides: `reset_all` writes `entity = 'reference'`, so a global reset does not stamp individual records — the editor says "shipped value" for a record with no edit history rather than inventing a date.

**6. Percent-of-total is calculated at render time and labelled `calculated`.** The formula table's percent column is `amount_g / total_g × 100`, derived from data the snapshot already carries. It is not stored, not a new `Tracked` field, and not user-editable — a stored percent that could disagree with the weights beside it is exactly the orphan number this tool refuses to print. Order of addition is `RecipeIngredient.order`, which has existed since M1 and has never been shown to anyone.

**7. True percent, not baker's percent.** Baker's percentage sets flour at 100% and lets the column sum past 100. It is the right convention for a bakery formula and the wrong one for a dressing, which has no flour basis. The table sums to 100% and says so in its caption, because a scientist reading a column that sums to 137 will assume a flour basis that is not there.

**8. The web report reaches parity through one new read endpoint, not by re-implementing the renderer.** The printable screen is missing what the audit found: the recipe, the formula, the process steps, the batch records. The wrong fix is a React component that rebuilds them from `EvaluationOut` — two renderers drifting apart, and the markdown export is the one a food scientist actually receives. **`GET /api/v1/evaluations/{id}/report` returns the same structured payload `render_markdown` consumes**, assembled by the same function; the screen renders that payload, and Task 8's contract test asserts the two agree on every section they both show.

**9. The UI pass is tokens and states, not a framework.** No Tailwind, no component library, no new dependency. One `:root` token block (4px spacing scale, 1.25 type scale, radius, shadow, line, and the existing verdict colours), a `prefers-color-scheme: dark` variant of that block, and rules for the states nothing has today: hover, focus-visible, disabled, loading, empty. `styles.css` grows from 64 lines to a few hundred; nothing else changes shape.

**10. Verdict meaning never depends on colour alone.** Today RED/AMBER/GRAY/GREEN differ only by hue, and `GiStrip`'s past-deadline state differs only by `opacity: 0.55` — a colour-blind or low-vision founder reads the single most important signal in the product wrong. Every verdict surface gains a glyph and a word alongside the colour (`✕` blocker, `?` cannot assess, `!` caution, `✓` clear), and the past-deadline cell gains text. This is the one place package D changes what the UI *says* rather than how it looks, and it is a correctness fix, not a style preference.

**11. Every existing `data-testid` survives verbatim, on the element it is on now.** The three Playwright spec files select 76 distinct test ids, several parameterised (`amount-olive_oil`, `field-ph_shelf_stable_min`, `cell-lactase_fungal_acid-mouth`). A restyle may add ids; it may never rename one, and it may never move one onto a different element — `observed-immediate` must stay on its `<td>`. The Playwright suite is the regression gate for every task in package D.

**12. No new runtime dependency and no new npm package.** Same constraint M3 and M4 held. The dark-mode block, the token set, and the responsive rules are plain CSS.

**13. Spec amendments are edits in place plus an amendments log.** Four milestones have accumulated accepted deviations that the spec still contradicts. They are written into the sections they belong to, and a new §16 records each one with its milestone, so a reader can tell which sentences are original and which were amended after contact with real data.

---

## File structure

```
foodbrew/
├── src/foodbrew/
│   ├── db/
│   │   ├── schema.sql                    #   + food.allergens_json
│   │   └── bootstrap.py                  #   + MIGRATIONS, column verification, apply_migrations()
│   ├── engine/
│   │   ├── allergens.py                  # NEW: the closed nine-allergen vocabulary + declaration builder
│   │   ├── formula.py                    # NEW: percent-of-total, order of addition, batch-record shaping
│   │   ├── structural.py                 # NEW: enum validation for the structured-field edit path
│   │   ├── types.py                      #   + Food.allergens (inert, like notes)
│   │   └── report.py                     #   _inputs_section replaced by the formula/spec-sheet block;
│   │                                     #     + _batch_record_section; ReportInput gains formula/allergens/batches
│   ├── store/
│   │   ├── snapshot.py                   #   + allergens in _food_out/_food_in; diff labels added fields
│   │   ├── records.py                    #   + STRUCTURED_FIELDS allowlist and its writer
│   │   ├── proposals.py                  #   + json-valued proposals for structured fields
│   │   ├── audit.py                      #   + last_edited_for()
│   │   └── rowmap.py                     #   + allergens round-trip
│   ├── seedload/loader.py                #   + allergens parsing
│   └── api/
│       ├── schemas.py                    #   + ReportOut and its parts; FoodOut.allergens; last_edited
│       └── routers/
│           ├── report.py                 # NEW: GET /evaluations/{id}/report
│           ├── records.py                #   + structured-field edits, last_edited on record payloads
│           └── export.py                 #   assembles the new sections
├── seed/foods.json                       #   + allergens on 15 records (Task 4)
├── web/src/
│   ├── api/{client.ts,types.ts}          #   + report payload, structured fields, last_edited
│   ├── components/
│   │   ├── FormulaTable.tsx              # NEW
│   │   ├── BatchRecord.tsx               # NEW
│   │   ├── AllergenDeclaration.tsx       # NEW
│   │   ├── StructuralEditor.tsx          # NEW
│   │   ├── VerdictBadge.tsx              #   glyph + word + colour
│   │   ├── GiStrip.tsx                   #   past-deadline gains text
│   │   ├── FindingGroups.tsx             #   collapsible, count badges
│   │   ├── DoseCards.tsx                 #   threshold meter
│   │   └── EnvelopePanel.tsx             #   shared verdict iconography
│   ├── screens/
│   │   ├── Report.tsx                    #   renders the report payload; parity with the export
│   │   └── Database.tsx                  #   unit, visible source, last-edited, structured editor
│   └── styles.css                        #   tokens, states, dark mode, responsive, print
├── docs/superpowers/specs/2026-08-13-enzyme-rules-engine-design.md   #   amended (Task 15)
└── tests/
    ├── engine/test_{allergens,formula,structural}.py, test_report_formula.py
    ├── store/test_{migrations,structured_records,last_edited}.py
    └── api/test_{report_endpoint,structured_fields,contracts_m5}.py
```

**Boundary rules to enforce in review.** M1–M4's hold unchanged, plus:

- `engine/allergens.py`, `engine/formula.py` and `engine/structural.py` are pure: no store, no api, no sqlite3, no fastapi, no clock.
- No rule module may import `engine/allergens.py`. An allergen never influences a verdict (decision #2), and Task 16's contract test asserts it.
- `bootstrap.py` may import `store/rowmap.py` (it already does) but nothing else from `store/`.
- No web file may hardcode a colour outside `styles.css`'s token block.

---

# Package A — the report a food scientist recognises

## Task 1: `db/bootstrap.py` — column verification and the first migration

Decision #1. Everything else in package A depends on a column that cannot exist yet.

**Files:**
- Modify: `src/foodbrew/db/bootstrap.py`
- Modify: `src/foodbrew/db/schema.sql`
- Create: `tests/store/test_migrations.py`

- [ ] **Step 1: Add the column to the schema**

In `src/foodbrew/db/schema.sql`, inside `CREATE TABLE IF NOT EXISTS food (...)`, immediately after the `structural_json` line:

```sql
    allergens_json TEXT NOT NULL DEFAULT '[]',
```

This covers a database created fresh. Step 2 covers every database that already exists.

- [ ] **Step 2: Add the migration machinery to `bootstrap.py`**

Add below `EXPECTED_TABLES`:

```python
#: Ordered, additive migrations. Each entry is (table, column, DDL fragment).
#:
#: `CREATE TABLE IF NOT EXISTS` is a no-op against a table that already exists,
#: so schema.sql alone cannot add a column to a database created by an earlier
#: milestone — it would boot clean and then fail on the first write. Every entry
#: here is applied with ALTER TABLE ... ADD COLUMN when PRAGMA table_info says
#: the column is absent, which makes the whole list idempotent: applying it to a
#: fresh database created from schema.sql is a no-op, and applying it twice is a
#: no-op. Columns are only ever ADDED. A migration that drops or retypes a
#: column is a different problem and this list is deliberately unable to express
#: one (plan decision #1).
MIGRATIONS: tuple[tuple[str, str, str], ...] = (
    ("food", "allergens_json", "TEXT NOT NULL DEFAULT '[]'"),
)


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def apply_migrations(conn: sqlite3.Connection) -> tuple[str, ...]:
    """Add any missing column from MIGRATIONS. Returns what it added."""
    applied: list[str] = []
    for table, column, ddl in MIGRATIONS:
        if column in _columns(conn, table):
            continue
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
        applied.append(f"{table}.{column}")
    if applied:
        conn.commit()
    return tuple(applied)


def missing_columns(conn: sqlite3.Connection) -> tuple[str, ...]:
    """Columns MIGRATIONS expects that are still absent — the boot check."""
    return tuple(
        f"{table}.{column}"
        for table, column, _ddl in MIGRATIONS
        if column not in _columns(conn, table)
    )
```

- [ ] **Step 3: Run migrations from both entry points**

In `create_database`, after `load_reference_data(conn, seed or load_seed())`, add:

```python
        apply_migrations(conn)
```

and replace `ensure_database`'s body after the missing-table check with:

```python
    conn = sqlite3.connect(path)
    try:
        present = {
            r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        missing = EXPECTED_TABLES - present
        if missing:
            raise ValueError(
                f"{path} exists but its schema is missing: {', '.join(sorted(missing))}"
            )
        # A database from an earlier milestone is missing columns, not tables —
        # the check above cannot see that, which is why this runs (decision #1).
        apply_migrations(conn)
        still_missing = missing_columns(conn)
        if still_missing:
            raise ValueError(
                f"{path} could not be upgraded; still missing: {', '.join(still_missing)}"
            )
    finally:
        conn.close()
    return path
```

Note the whole function now opens one connection and closes it in a `finally`, which is how it was already written — keep that shape.

- [ ] **Step 4: Write the tests**

```python
"""Plan decision #1 — the first migration, and the boot check that needed it."""

import sqlite3

import pytest

from foodbrew.db import create_database, ensure_database
from foodbrew.db.bootstrap import MIGRATIONS, apply_migrations, missing_columns


def _columns(path, table):
    conn = sqlite3.connect(path)
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


def test_a_fresh_database_already_has_every_migrated_column(db_path):
    for table, column, _ddl in MIGRATIONS:
        assert column in _columns(db_path, table)


def test_applying_migrations_to_a_fresh_database_changes_nothing(db_path):
    conn = sqlite3.connect(db_path)
    try:
        assert apply_migrations(conn) == ()
    finally:
        conn.close()


def test_a_pre_migration_database_is_upgraded_on_boot(tmp_path):
    """The M1-M4 case: a real database whose food table predates the column."""
    path = create_database(tmp_path / "old.db")
    conn = sqlite3.connect(path)
    try:
        conn.execute("ALTER TABLE food DROP COLUMN allergens_json")
        conn.commit()
    finally:
        conn.close()
    assert "allergens_json" not in _columns(path, "food")

    ensure_database(path)
    assert "allergens_json" in _columns(path, "food")


def test_the_upgrade_preserves_the_rows_it_finds(tmp_path):
    path = create_database(tmp_path / "old.db")
    conn = sqlite3.connect(path)
    try:
        before = conn.execute("SELECT COUNT(*) FROM food").fetchone()[0]
        conn.execute("ALTER TABLE food DROP COLUMN allergens_json")
        conn.commit()
    finally:
        conn.close()

    ensure_database(path)
    conn = sqlite3.connect(path)
    try:
        after = conn.execute("SELECT COUNT(*) FROM food").fetchone()[0]
        defaulted = conn.execute(
            "SELECT COUNT(*) FROM food WHERE allergens_json = '[]'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert after == before > 0
    assert defaulted == after, "an added column takes its default on existing rows"


def test_migrating_twice_is_a_no_op(tmp_path):
    path = create_database(tmp_path / "twice.db")
    conn = sqlite3.connect(path)
    try:
        assert apply_migrations(conn) == ()
        assert apply_migrations(conn) == ()
        assert missing_columns(conn) == ()
    finally:
        conn.close()


def test_a_database_missing_a_table_still_fails_loudly(tmp_path):
    path = create_database(tmp_path / "broken.db")
    conn = sqlite3.connect(path)
    try:
        conn.execute("DROP TABLE trial_observation")
        conn.commit()
    finally:
        conn.close()
    with pytest.raises(ValueError) as exc:
        ensure_database(path)
    assert "trial_observation" in str(exc.value)
```

- [ ] **Step 5: Run them**

Run: `.venv/bin/pytest tests/store/test_migrations.py tests/test_db_bootstrap.py -q`
Expected: all pass. `ALTER TABLE ... DROP COLUMN` needs SQLite 3.35+; Python 3.12 on macOS ships well past that. If your SQLite is older, build the pre-migration database by running M1's schema text with the column line removed instead — but check `sqlite3.sqlite_version` first and only change the test if it is genuinely too old.

- [ ] **Step 6: Commit**

```bash
git add src/foodbrew/db/bootstrap.py src/foodbrew/db/schema.sql tests/store/test_migrations.py
git commit -m "feat(db): verify columns on boot and add the first forward migration"
```

---

## Task 2: `engine/allergens.py` — the closed vocabulary and the declaration

Decision #2. Pure, and deliberately unreachable from any rule.

**Files:**
- Create: `src/foodbrew/engine/allergens.py`
- Create: `tests/engine/test_allergens.py`

- [ ] **Step 1: Write the module**

```python
"""The allergen vocabulary and the declaration the report prints.

Pure, and inert by design: **no rule imports this module** (plan decision #2,
asserted by tests/api/test_contracts_m5.py). An allergen never changes a
verdict — it is catalogue reference data that travels with the evaluation so the
report can state what is in the jar, exactly as `Food.notes` already does.

The vocabulary is closed because a declaration assembled from free text is a
declaration nothing can lint. These are the nine major allergens named in US
labelling law; a founder who needs a tenth is making a product decision, not
filling in a field.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum


class Allergen(StrEnum):
    MILK = "milk"
    EGG = "egg"
    FISH = "fish"
    CRUSTACEAN_SHELLFISH = "crustacean_shellfish"
    TREE_NUT = "tree_nut"
    PEANUT = "peanut"
    WHEAT = "wheat"
    SOY = "soy"
    SESAME = "sesame"


#: Label-facing wording. The report prints these, not the enum values.
ALLERGEN_TEXT: Mapping[Allergen, str] = {
    Allergen.MILK: "milk",
    Allergen.EGG: "egg",
    Allergen.FISH: "fish",
    Allergen.CRUSTACEAN_SHELLFISH: "crustacean shellfish",
    Allergen.TREE_NUT: "tree nuts",
    Allergen.PEANUT: "peanuts",
    Allergen.WHEAT: "wheat",
    Allergen.SOY: "soy",
    Allergen.SESAME: "sesame",
}

#: Spec §12's discipline applied to allergens: an empty list on a food means
#: "nothing recorded", NOT "contains no allergen". The report says which.
NOTHING_RECORDED = "not recorded for this ingredient"


def parse(values: Sequence[str]) -> tuple[Allergen, ...]:
    """Closed-vocabulary parse. An unknown token is an error, never a passthrough."""
    out: list[Allergen] = []
    for raw in values:
        try:
            allergen = Allergen(raw)
        except ValueError as exc:
            allowed = ", ".join(a.value for a in Allergen)
            raise ValueError(f"unknown allergen '{raw}'; allowed: {allowed}") from exc
        if allergen not in out:
            out.append(allergen)
    return tuple(out)


@dataclass(frozen=True, slots=True)
class DeclarationEntry:
    allergen: Allergen
    text: str
    #: Names of the recipe ingredients that carry it, in recipe order.
    from_food_names: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Declaration:
    entries: tuple[DeclarationEntry, ...]
    #: Recipe ingredients with no allergen record at all — a gap, not a clearance.
    unrecorded_food_names: tuple[str, ...]

    @property
    def is_empty(self) -> bool:
        return not self.entries


def declare(
    ingredient_food_ids: Sequence[str], foods: Mapping[str, object]
) -> Declaration:
    """Build the declaration for one recipe, in recipe order.

    `foods` is the evaluation's frozen food map. A food the snapshot does not
    carry is reported as unrecorded rather than skipped: the whole point of the
    declaration is that a silent omission is indistinguishable from a clearance.
    """
    carried: dict[Allergen, list[str]] = {}
    unrecorded: list[str] = []

    for food_id in ingredient_food_ids:
        food = foods.get(food_id)
        if food is None:
            unrecorded.append(food_id)
            continue
        allergens = tuple(getattr(food, "allergens", ()) or ())
        if not allergens:
            unrecorded.append(food.name)
            continue
        for allergen in allergens:
            names = carried.setdefault(Allergen(allergen), [])
            if food.name not in names:
                names.append(food.name)

    entries = tuple(
        DeclarationEntry(
            allergen=allergen,
            text=ALLERGEN_TEXT[allergen],
            from_food_names=tuple(carried[allergen]),
        )
        for allergen in Allergen
        if allergen in carried
    )
    return Declaration(entries=entries, unrecorded_food_names=tuple(unrecorded))
```

- [ ] **Step 2: Write the tests**

```python
"""The closed vocabulary, and the difference between 'none' and 'not recorded'."""

import dataclasses

import pytest

from foodbrew.engine.allergens import (
    NOTHING_RECORDED,
    Allergen,
    declare,
    parse,
)


class FakeFood:
    def __init__(self, name, allergens=()):
        self.name = name
        self.allergens = allergens


def test_every_enum_member_has_label_text():
    from foodbrew.engine.allergens import ALLERGEN_TEXT

    assert set(ALLERGEN_TEXT) == set(Allergen)


def test_parse_accepts_the_vocabulary_and_dedupes():
    assert parse(["milk", "milk", "egg"]) == (Allergen.MILK, Allergen.EGG)


def test_parse_refuses_an_unknown_token_and_names_the_allowed_set():
    with pytest.raises(ValueError) as exc:
        parse(["dairy"])
    assert "unknown allergen 'dairy'" in str(exc.value)
    assert "milk" in str(exc.value)


def test_a_declaration_groups_ingredients_by_allergen_in_vocabulary_order():
    foods = {
        "yogurt": FakeFood("Yogurt", ("milk",)),
        "croutons": FakeFood("Croutons", ("wheat",)),
        "parmesan": FakeFood("Parmesan", ("milk",)),
    }
    declaration = declare(["yogurt", "croutons", "parmesan"], foods)
    assert [e.allergen for e in declaration.entries] == [Allergen.MILK, Allergen.WHEAT]
    assert declaration.entries[0].from_food_names == ("Yogurt", "Parmesan")
    assert declaration.unrecorded_food_names == ()


def test_a_food_with_no_allergen_record_is_a_gap_not_a_clearance():
    foods = {"olive_oil": FakeFood("Olive oil"), "yogurt": FakeFood("Yogurt", ("milk",))}
    declaration = declare(["olive_oil", "yogurt"], foods)
    assert declaration.unrecorded_food_names == ("Olive oil",)
    assert [e.allergen for e in declaration.entries] == [Allergen.MILK]


def test_a_food_absent_from_the_snapshot_is_reported_not_skipped():
    declaration = declare(["ghost"], {})
    assert declaration.unrecorded_food_names == ("ghost",)
    assert declaration.is_empty


def test_an_empty_recipe_declares_nothing_and_says_so():
    declaration = declare([], {})
    assert declaration.is_empty
    assert declaration.unrecorded_food_names == ()
    assert NOTHING_RECORDED  # the wording exists for the report to use
```

- [ ] **Step 3: Run them**

Run: `.venv/bin/pytest tests/engine/test_allergens.py -q`
Expected: 7 passed.

- [ ] **Step 4: Commit**

```bash
git add src/foodbrew/engine/allergens.py tests/engine/test_allergens.py
git commit -m "feat(engine): closed allergen vocabulary and the recipe declaration"
```

---

## Task 3: `engine/formula.py` — percent of total, order of addition, batch records

Decisions #6 and #7. The arithmetic a bench sheet is built on, as pure functions.

**Research this task implements.** A working formula is expressed as **percent of total, summing to 100**, with **weights for one batch beside it**; ingredients are listed **in order of addition** rather than alphabetically; process steps carry their parameters; and the batch record is the first document reviewed when a batch misses spec. Sources: [ISU Food Product Development Lab Manual — batch sheets for scale-up](https://iastate.pressbooks.pub/foodproductdevelopment/chapter/batch-sheets-for-scale-up/), [ISU — finished product specifications](https://iastate.pressbooks.pub/foodproductdevelopment/chapter/finished-product-specifications/), [FoodDocs — product specification sheet template](https://www.fooddocs.com/food-safety-templates/product-specification-sheet), [MAE Innovation — NPD methodology](https://mae-innovation.com/en/how-to-develop-a-new-food-product-methodology-and-essential-stages/). Baker's percentage is not used, and decision #7 says why.

**Files:**
- Create: `src/foodbrew/engine/formula.py`
- Create: `tests/engine/test_formula.py`

- [ ] **Step 1: Write the module**

```python
"""The formula table's arithmetic: percent of total, in order of addition.

Pure. Percent is CALCULATED at render time from the weights the snapshot already
carries (plan decision #6) — never stored, never editable. A stored percent that
could disagree with the grams beside it is the orphan number this tool exists to
refuse.

True percent, not baker's percent (plan decision #7): the column sums to 100
because a dressing has no flour basis, and a scientist reading a column that
sums past 100 will assume one.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from foodbrew.engine.types import Food, ProcessStep, RecipeIngredient, Tracked

#: Percentages are rounded for display only; the sum check uses the raw values.
PERCENT_DECIMALS = 2


@dataclass(frozen=True, slots=True)
class FormulaLine:
    order: int
    food_id: str
    food_name: str
    amount_g: float
    #: None when the batch total is zero — a percentage of nothing is not zero.
    percent_of_total: float | None
    ph: Tracked
    water_content_pct: Tracked
    allergen_text: str
    #: True when this is the step the enzyme goes in after (§5.2).
    is_enzyme_addition_point: bool = False


@dataclass(frozen=True, slots=True)
class Formula:
    lines: tuple[FormulaLine, ...]
    total_g: float
    #: The rounded percentages as printed, summed — for the caption's honesty.
    printed_percent_total: float | None

    @property
    def is_empty(self) -> bool:
        return not self.lines


@dataclass(frozen=True, slots=True)
class ProcessLine:
    order: int
    label: str
    is_heat: bool
    is_enzyme_addition_point: bool


def build(
    recipe: Sequence[RecipeIngredient],
    foods: Mapping[str, Food],
    *,
    allergen_text_for=lambda food: "",
) -> Formula:
    """One formula table, ordered by `RecipeIngredient.order` then by id.

    Order of addition is `order`, which has existed since M1 and has never been
    shown to anyone. Ties break on food id so the table is deterministic, which
    is what keeps a re-rendered report byte-identical.
    """
    ordered = sorted(recipe, key=lambda i: (i.order, i.food_id))
    total = sum(float(i.amount_g) for i in ordered)

    lines: list[FormulaLine] = []
    for ingredient in ordered:
        food = foods.get(ingredient.food_id)
        percent = (
            round(float(ingredient.amount_g) / total * 100, PERCENT_DECIMALS)
            if total > 0
            else None
        )
        lines.append(
            FormulaLine(
                order=ingredient.order,
                food_id=ingredient.food_id,
                food_name=food.name if food else ingredient.food_id,
                amount_g=float(ingredient.amount_g),
                percent_of_total=percent,
                ph=food.ph if food else Tracked(None, _unconfirmed()),
                water_content_pct=(
                    food.water_content_pct if food else Tracked(None, _unconfirmed())
                ),
                allergen_text=allergen_text_for(food) if food else "",
            )
        )

    printed = (
        round(sum(line.percent_of_total for line in lines if line.percent_of_total), 2)
        if total > 0
        else None
    )
    return Formula(lines=tuple(lines), total_g=total, printed_percent_total=printed)


def _unconfirmed():
    from foodbrew.engine.types import TruthLabel

    return TruthLabel.UNCONFIRMED


def process_lines(
    steps: Sequence[ProcessStep], enzyme_addition_index: int | None
) -> tuple[ProcessLine, ...]:
    """Process steps in order, flagging where the enzyme goes in (§5.2, R3)."""
    return tuple(
        ProcessLine(
            order=step.order,
            label=step.label,
            is_heat=step.is_heat,
            is_enzyme_addition_point=(enzyme_addition_index == step.order),
        )
        for step in sorted(steps, key=lambda s: s.order)
    )
```

- [ ] **Step 2: Write the tests**

```python
"""Decisions #6 and #7 — the formula arithmetic, and what it refuses to guess."""

import pytest

from foodbrew.engine.formula import build, process_lines
from foodbrew.engine.types import ProcessStep, RecipeIngredient, TruthLabel


def test_percent_is_of_the_total_and_sums_to_one_hundred(seed):
    formula = build(
        [RecipeIngredient("olive_oil", 150.0, 1), RecipeIngredient("white_vinegar", 50.0, 2)],
        seed.foods,
    )
    assert formula.total_g == 200.0
    assert [line.percent_of_total for line in formula.lines] == [75.0, 25.0]
    assert formula.printed_percent_total == 100.0


def test_lines_come_back_in_order_of_addition_not_input_order(seed):
    formula = build(
        [RecipeIngredient("white_vinegar", 50.0, 2), RecipeIngredient("olive_oil", 150.0, 1)],
        seed.foods,
    )
    assert [line.food_id for line in formula.lines] == ["olive_oil", "white_vinegar"]


def test_ties_in_order_break_deterministically_on_id(seed):
    first = build(
        [RecipeIngredient("white_vinegar", 50.0, 0), RecipeIngredient("olive_oil", 50.0, 0)],
        seed.foods,
    )
    second = build(
        [RecipeIngredient("olive_oil", 50.0, 0), RecipeIngredient("white_vinegar", 50.0, 0)],
        seed.foods,
    )
    assert [line.food_id for line in first.lines] == [line.food_id for line in second.lines]


def test_a_zero_total_reports_no_percentage_rather_than_zero(seed):
    formula = build([RecipeIngredient("olive_oil", 0.0, 1)], seed.foods)
    assert formula.total_g == 0
    assert formula.lines[0].percent_of_total is None
    assert formula.printed_percent_total is None


def test_rounding_is_reported_so_a_99_99_total_is_visible(seed):
    formula = build(
        [
            RecipeIngredient("olive_oil", 100.0, 1),
            RecipeIngredient("white_vinegar", 100.0, 2),
            RecipeIngredient("lemon_juice", 100.0, 3),
        ],
        seed.foods,
    )
    assert [line.percent_of_total for line in formula.lines] == [33.33, 33.33, 33.33]
    assert formula.printed_percent_total == 99.99


def test_an_unknown_food_keeps_its_line_and_reports_unconfirmed_values(seed):
    formula = build([RecipeIngredient("ghost", 10.0, 1)], seed.foods)
    assert formula.lines[0].food_name == "ghost"
    assert formula.lines[0].ph.status is TruthLabel.UNCONFIRMED


def test_the_empty_recipe_is_empty_rather_than_a_zero_row():
    formula = build([], {})
    assert formula.is_empty
    assert formula.total_g == 0


def test_process_lines_are_ordered_and_flag_the_enzyme_point():
    lines = process_lines(
        [ProcessStep(2, "whisk in oil"), ProcessStep(1, "combine acids", is_heat=True)],
        enzyme_addition_index=2,
    )
    assert [line.order for line in lines] == [1, 2]
    assert lines[0].is_heat is True
    assert lines[1].is_enzyme_addition_point is True
    assert lines[0].is_enzyme_addition_point is False


def test_no_enzyme_point_flags_nothing():
    lines = process_lines([ProcessStep(1, "whisk")], enzyme_addition_index=None)
    assert lines[0].is_enzyme_addition_point is False
```

- [ ] **Step 3: Run them**

Run: `.venv/bin/pytest tests/engine/test_formula.py -q`
Expected: 9 passed. `lemon_juice` and the other ids are real seed foods; if one is not present, `grep '"id"' seed/foods.json` and use one that is rather than inventing it.

- [ ] **Step 4: Commit**

```bash
git add src/foodbrew/engine/formula.py tests/engine/test_formula.py
git commit -m "feat(engine): formula percentages, order of addition, and process lines"
```

---

## Task 4: Thread `allergens` through the food record, seed to snapshot

Decisions #2 and #3. Six files plus the seed, in one commit, because a half-threaded field is worse than none.

**Files:**
- Modify: `src/foodbrew/engine/types.py`, `src/foodbrew/store/rowmap.py`, `src/foodbrew/seedload/loader.py`, `src/foodbrew/store/snapshot.py`, `src/foodbrew/api/schemas.py`, `seed/foods.json`
- Create: `tests/store/test_allergen_roundtrip.py`

- [ ] **Step 1: The dataclass field**

In `src/foodbrew/engine/types.py`, add to `Food`, immediately after `structural`:

```python
    #: Spec §5.1 / plan decision #2. Inert: no rule reads this, exactly like
    #: `notes`. It travels with the evaluation so the report can declare what is
    #: in the jar without consulting a catalogue that may have moved since.
    allergens: tuple[str, ...] = ()
```

A default is required — every existing `Food(...)` construction in tests and seed code must keep working untouched.

- [ ] **Step 2: Row mapping**

In `src/foodbrew/store/rowmap.py`, in `food_to_row` (line 168), add after the `structural_json` entry:

```python
        "allergens_json": json.dumps(list(f.allergens)),
```

and in `food_from_row` (line 105), add the matching read beside the `structural` line:

```python
        allergens=tuple(json.loads(row["allergens_json"])),
```

- [ ] **Step 3: Seed loading**

In `src/foodbrew/seedload/loader.py`, above the `foods[fid] = Food(` call (line 161), parse and validate through the closed vocabulary so a typo in the seed fails at load rather than at render:

```python
        try:
            allergens = tuple(a.value for a in parse_allergens(r.get("allergens", ())))
        except ValueError as exc:
            raise SeedError(f"{fid}: {exc}") from exc
```

and pass it into the constructor after `structural=structural,`:

```python
            allergens=allergens,
```

with the import at the top of the file:

```python
from foodbrew.engine.allergens import parse as parse_allergens
```

- [ ] **Step 4: The snapshot**

In `src/foodbrew/store/snapshot.py`, in `_food_out` (line 107), add after `"structural"`:

```python
        "allergens": list(f.allergens),
```

and in `_food_in` (line 126), add after `structural=...`:

```python
        allergens=tuple(raw.get("allergens", ())),
```

`raw.get`, not `raw[...]` — decision #3. Every snapshot written before M5 lacks the key and must still thaw. `SNAPSHOT_VERSION` stays `1`.

- [ ] **Step 5: The API**

In `src/foodbrew/api/schemas.py`, add to `FoodOut` after `structural: list[str]`:

```python
    allergens: list[str]
```

and in `FoodOut.of`, after `structural=[str(s) for s in f.structural],`:

```python
            allergens=list(f.allergens),
```

`FoodOut.of` is hand-written rather than reflective, so this line is required or the field silently never reaches the browser.

Also add to `CustomFoodIn`, so a founder-created food can declare its allergens:

```python
    allergens: list[str] = Field(default_factory=list)
```

and thread it in `store/foods.create_custom` the same way `structural` is already threaded — read that function and mirror it exactly, validating through `engine.allergens.parse` so a bad token is a `ValidationRejection`, not a stored typo.

- [ ] **Step 6: Seed the fifteen records that carry an allergen**

In `seed/foods.json`, add an `"allergens"` key to exactly these records. Every id below was verified present in the shipped catalogue; the other 37 foods get no key at all, which reads as *not recorded* rather than *none* (decision #2).

| food id | allergens |
|---|---|
| `milk` | `["milk"]` |
| `yogurt` | `["milk"]` |
| `buttermilk` | `["milk"]` |
| `ice_cream` | `["milk"]` |
| `aged_cheese` | `["milk"]` |
| `feta` | `["milk"]` |
| `parmesan` | `["milk"]` |
| `boiled_egg` | `["egg"]` |
| `mayonnaise` | `["egg"]` |
| `wheat_bread` | `["wheat"]` |
| `cooked_pasta` | `["wheat"]` |
| `croutons` | `["wheat"]` |
| `farro` | `["wheat"]` |
| `tofu` | `["soy"]` |
| `canned_tuna` | `["fish"]` |
| `nuts_seeds` | *(leave the key off — see below)* |

`nuts_seeds` is a generic catalogue entry that could be tree nut, peanut, sesame, or all three, and guessing would put a wrong declaration in a document handed to a food scientist. It stays unrecorded, and Task 15's spec amendment lists it as an open question for the founder to close through the database editor.

Add a note to each seeded record so the provenance is visible in the editor, following the seed's existing style, e.g. for `mayonnaise`:

```json
"allergens": ["egg"],
```

Do not add a `_status`/`_source` pair — allergens are a plain list column (decision #2), not a `Tracked` triple.

- [ ] **Step 7: Write the round-trip tests**

```python
"""Decision #2 and #3 — allergens survive every boundary they cross."""

import json

from foodbrew.engine.allergens import Allergen
from foodbrew.store import snapshot
from foodbrew.store.rowmap import food_from_row, food_to_row


def test_the_seed_carries_the_dairy_and_wheat_declarations(seed):
    assert Allergen.MILK.value in seed.foods["yogurt"].allergens
    assert Allergen.WHEAT.value in seed.foods["croutons"].allergens
    assert Allergen.EGG.value in seed.foods["mayonnaise"].allergens
    assert Allergen.FISH.value in seed.foods["canned_tuna"].allergens


def test_a_food_with_no_allergen_record_has_an_empty_tuple(seed):
    assert seed.foods["olive_oil"].allergens == ()


def test_nuts_seeds_is_left_unrecorded_rather_than_guessed(seed):
    """A generic nut/seed entry could be tree nut, peanut or sesame; the seed
    declines to choose and the report reports it as a gap."""
    assert seed.foods["nuts_seeds"].allergens == ()


def test_the_row_round_trip_preserves_allergens(conn, seed):
    row_dict = food_to_row(seed.foods["yogurt"])
    assert json.loads(row_dict["allergens_json"]) == ["milk"]

    conn.execute("DELETE FROM food WHERE id = 'yogurt'")
    cols = ", ".join(f'"{c}"' for c in row_dict)
    placeholders = ", ".join("?" for _ in row_dict)
    conn.execute(f"INSERT INTO food ({cols}) VALUES ({placeholders})", tuple(row_dict.values()))
    conn.commit()

    back = food_from_row(conn.execute("SELECT * FROM food WHERE id = 'yogurt'").fetchone())
    assert back.allergens == ("milk",)


def test_the_snapshot_round_trip_preserves_allergens(conn, vinaigrette_rows):
    from foodbrew.store import evaluations as evaluations_store

    stored = evaluations_store.run(conn, vinaigrette_rows["formulation_id"])
    payload = json.loads(stored.input_snapshot_json)
    milk = next(f for f in payload["foods"] if f["id"] == "milk")
    assert milk["allergens"] == ["milk"]

    ctx = snapshot.context_from_snapshot(stored.input_snapshot_json)
    assert ctx.foods["milk"].allergens == ("milk",)


def test_a_pre_m5_snapshot_without_the_key_still_thaws(conn, vinaigrette_rows):
    """Decision #3 — every evaluation that ran before M5 must still open."""
    from foodbrew.store import evaluations as evaluations_store

    stored = evaluations_store.run(conn, vinaigrette_rows["formulation_id"])
    payload = json.loads(stored.input_snapshot_json)
    for food in payload["foods"]:
        food.pop("allergens", None)

    ctx = snapshot.context_from_snapshot(json.dumps(payload, sort_keys=True))
    assert ctx.foods["milk"].allergens == ()


def test_the_api_serialises_allergens(client):
    foods = client.get("/api/v1/foods").json()
    yogurt = next(f for f in foods if f["id"] == "yogurt")
    assert yogurt["allergens"] == ["milk"]


def test_a_custom_food_cannot_declare_an_unknown_allergen(client):
    response = client.post(
        "/api/v1/foods",
        json={"name": "Test dressing base", "allergens": ["dairy"]},
    )
    assert response.status_code == 422
    assert "dairy" in response.json()["detail"]
```

- [ ] **Step 8: Run the affected suites**

Run: `.venv/bin/pytest tests/store/test_allergen_roundtrip.py tests/store/test_rowmap.py tests/test_seed_integrity.py tests/api/test_catalog.py tests/store/test_snapshot.py -q`
Expected: all pass. `test_seed_integrity.py` may assert a field set on food records — if it fails because it did not expect a new key, extend its expected set rather than removing the assertion.

Run: `.venv/bin/pytest -q`
Expected: the full suite still green, and **no golden fixture moved** — an allergen changes no verdict.

- [ ] **Step 9: Commit**

```bash
git add src/foodbrew/engine/types.py src/foodbrew/store/rowmap.py src/foodbrew/seedload/loader.py src/foodbrew/store/snapshot.py src/foodbrew/api/schemas.py src/foodbrew/store/foods.py seed/foods.json tests/store/test_allergen_roundtrip.py
git commit -m "feat: carry allergen declarations on food records, seed to snapshot"
```

---

## Task 5: `engine/report.py` — the formula block, the batch record, the declaration

The centre of package A. `_inputs_section` becomes a specification header plus a formula table; a batch-record section joins it; the allergen declaration goes where a scientist looks for it.

**Files:**
- Modify: `src/foodbrew/engine/report.py`
- Create: `tests/engine/test_report_formula.py`

- [ ] **Step 1: Extend `ReportInput` and add the batch model**

In `report.py`, add to the imports:

```python
from foodbrew.engine.allergens import NOTHING_RECORDED, Declaration, declare
from foodbrew.engine.formula import Formula, build as build_formula, process_lines
```

Add above `ReportInput`:

```python
@dataclass(frozen=True, slots=True)
class ReportBatch:
    """One `trial_batch` as a batch record — the document reviewed first when a
    batch misses spec, which is why every parameter it captured is printed."""

    made_at: str
    batch_size_g: float | None
    measured_ph: float | None
    ph_method: str
    make_minutes: int | None
    difficulty_score: int | None
    enzyme_source_note: str
    enzyme_addition_step: int | None
    storage_mode: str
    process_notes: str = ""
```

and add to `ReportInput`, after `trial`:

```python
    #: Identity of the recipe this formula belongs to, for the header block.
    recipe_id: str = ""
    #: Batch records from the trial, newest last. Empty until a batch is logged.
    batches: tuple[ReportBatch, ...] = field(default_factory=tuple)
```

- [ ] **Step 2: Replace `_inputs_section`**

Replace the whole function (currently lines 184-231) with a specification header, the formula table, the allergen declaration, and the process sequence:

```python
def _identity_block(data: ReportInput) -> list[str]:
    """The header a specification sheet opens with: what this is, and which run."""
    form = data.context.formulation
    serving = "not set" if form.serving_size_g is None else f"{form.serving_size_g} g"
    return [
        "## Product and formula identity",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Product | {data.recipe_name} |",
        f"| Recipe id | {data.recipe_id or 'not recorded'} |",
        f"| Formula basis | percent of total batch weight (sums to 100) |",
        f"| Format | {FORMAT_TITLES.get(form.format, form.format.value)} |",
        f"| Serving size | {serving} |",
        f"| Declared use occasion | "
        f"{form.dwell_profile.value if form.dwell_profile else 'not declared'} |",
        f"| Measured pH | {_tracked(form.measured_ph)} |",
        f"| Evaluation | {data.evaluation_id} |",
        f"| Engine version | {data.engine_version} |",
        "",
    ]


def _formula_section(formula: Formula) -> list[str]:
    """Percent of total beside weights, in order of addition (decisions #6, #7)."""
    if formula.is_empty:
        return ["## Formula", "", "No ingredients are recorded for this recipe.", ""]

    lines = [
        "## Formula",
        "",
        "Percent of total batch weight, in the order the ingredients go in. The "
        "percentages are the formula; the grams are one batch of it. Percent is "
        "calculated from the weights, so the two cannot disagree.",
        "",
        "| # | Ingredient | % of total | Grams | pH | Water content | Allergens |",
        "| ---: | --- | ---: | ---: | --- | --- | --- |",
    ]
    for position, line in enumerate(formula.lines, start=1):
        percent = "—" if line.percent_of_total is None else f"{line.percent_of_total:g}"
        allergens = line.allergen_text or "not recorded"
        lines.append(
            f"| {position} | {line.food_name} | {percent} | {line.amount_g:g} "
            f"| {_tracked(line.ph)} | {_tracked(line.water_content_pct, '%')} | {allergens} |"
        )

    total_percent = (
        "—" if formula.printed_percent_total is None else f"{formula.printed_percent_total:g}"
    )
    lines += [
        f"| | **Total** | **{total_percent}** | **{formula.total_g:g}** | | | |",
        "",
    ]
    if formula.printed_percent_total is not None and formula.printed_percent_total != 100:
        lines += [
            f"The printed percentages total {total_percent} rather than 100 because each "
            "is rounded to two decimals. The grams are exact.",
            "",
        ]
    return lines


def _allergen_section(declaration: Declaration) -> list[str]:
    lines = ["## Allergens", ""]
    if declaration.is_empty:
        lines += [
            "No allergen is recorded for any ingredient in this recipe. That is a gap "
            "in the ingredient records, not a statement that the product is free of "
            "allergens.",
            "",
        ]
    else:
        lines += ["| Allergen | From |", "| --- | --- |"]
        for entry in declaration.entries:
            lines.append(f"| {entry.text} | {', '.join(entry.from_food_names)} |")
        lines.append("")
    if declaration.unrecorded_food_names:
        lines += [
            "Allergens are "
            + NOTHING_RECORDED
            + " for: "
            + ", ".join(declaration.unrecorded_food_names)
            + ". Fill these in before anyone relies on the declaration above.",
            "",
        ]
    return lines


def _process_section(data: ReportInput) -> list[str]:
    form = data.context.formulation
    steps = process_lines(form.process_steps, form.enzyme_addition_index)
    if not steps:
        return []
    lines = [
        "## Process",
        "",
        "| Step | Operation | Heat | Enzyme added here |",
        "| ---: | --- | --- | --- |",
    ]
    for step in steps:
        lines.append(
            f"| {step.order} | {step.label} | {'yes' if step.is_heat else 'no'} "
            f"| {'yes' if step.is_enzyme_addition_point else 'no'} |"
        )
    lines.append("")
    return lines


def _targets_section(data: ReportInput) -> list[str]:
    """What a specification sheet carries that this tool cannot measure.

    Stating the absence is the convention: an incomplete spec says which
    parameters are outstanding rather than omitting the rows (spec §12).
    """
    return [
        "## Finished-product parameters",
        "",
        "| Parameter | Value | Basis |",
        "| --- | --- | --- |",
        f"| pH | {_tracked(data.context.formulation.measured_ph)} | measured, or "
        "estimated from the lowest-pH wet ingredient |",
        "| Water activity | not measured | needs a lab instrument this tool does not model |",
        "| Viscosity | not measured | outside the rules this tool evaluates |",
        "| Nutrition | not calculated | no nutrient data is held for these ingredients |",
        "",
    ]


def _selected_foods_section(data: ReportInput) -> list[str]:
    ctx = data.context
    form = ctx.formulation
    lines: list[str] = []
    for title, ids in (
        ("Trigger foods this is meant to cover", form.target_trigger_food_ids),
        ("Foods it will be poured on", form.application_food_ids),
    ):
        names = [ctx.foods[i].name if i in ctx.foods else i for i in ids]
        lines += [f"### {title}", "", ", ".join(names) if names else "none selected", ""]
    return lines


def _inputs_section(data: ReportInput) -> list[str]:
    """Spec §10 screen 8, in the shape a bench sheet and a spec sheet use."""
    formula = build_formula(
        data.context.formulation.recipe,
        data.context.foods,
        allergen_text_for=_allergen_text,
    )
    declaration = declare(
        [i.food_id for i in data.context.formulation.recipe], data.context.foods
    )
    return (
        _identity_block(data)
        + _formula_section(formula)
        + _allergen_section(declaration)
        + _process_section(data)
        + _targets_section(data)
        + _selected_foods_section(data)
    )


def _allergen_text(food) -> str:
    from foodbrew.engine.allergens import ALLERGEN_TEXT, Allergen

    return ", ".join(ALLERGEN_TEXT[Allergen(a)] for a in getattr(food, "allergens", ()) or ())
```

- [ ] **Step 3: Add the batch-record section**

Add below `_observed_section`:

```python
def _batch_record_section(data: ReportInput) -> list[str]:
    """The batch record. First document reviewed when a batch misses spec, so it
    prints every parameter the trial captured rather than summarising them."""
    if not data.batches:
        return []
    lines = [
        "## Batch records",
        "",
        "What was actually made, as it was made. Blank cells are parameters that "
        "were not recorded for that batch.",
        "",
        "| Made | Size | pH (method) | Minutes | Difficulty | Enzyme added after step "
        "| Enzyme source | Storage |",
        "| --- | ---: | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for batch in data.batches:
        ph = (
            "not measured"
            if batch.measured_ph is None
            else f"{batch.measured_ph:g} ({batch.ph_method})"
        )
        lines.append(
            f"| {batch.made_at[:16].replace('T', ' ')} "
            f"| {'' if batch.batch_size_g is None else f'{batch.batch_size_g:g} g'} "
            f"| {ph} "
            f"| {'' if batch.make_minutes is None else batch.make_minutes} "
            f"| {'' if batch.difficulty_score is None else f'{batch.difficulty_score} of 5'} "
            f"| {'' if batch.enzyme_addition_step is None else batch.enzyme_addition_step} "
            f"| {batch.enzyme_source_note or 'not recorded'} "
            f"| {batch.storage_mode} |"
        )
    lines.append("")
    for batch in data.batches:
        if batch.process_notes:
            lines += [
                f"**Notes on the batch made {batch.made_at[:16].replace('T', ' ')}:**",
                "",
            ]
            lines += _quote(batch.process_notes)
    return lines
```

and splice it into `render_markdown` immediately after `lines += _observed_section(data)`:

```python
    lines += _batch_record_section(data)
```

- [ ] **Step 4: Write the tests**

```python
"""Package A — the report in the shape a food scientist reads."""

import pytest

from foodbrew.engine.format_search import recommend_format
from foodbrew.engine.language import contains_prohibited
from foodbrew.engine.report import ReportBatch, ReportInput, render_markdown
from foodbrew.engine.rules import r15_applied_texture
from foodbrew.engine.types import Phase


@pytest.fixture
def report(make_ctx):
    def _build(**kw):
        ctx = make_ctx(
            enzymes=(("lactase_fungal_acid", 9000.0, Phase.WET),),
            recipe=(("olive_oil", 150.0), ("white_vinegar", 50.0)),
            trigger_foods=("milk",),
            application_foods=("romaine",),
            measured_ph=3.0,
            process_steps=kw.pop("process_steps", ()),
            enzyme_addition_index=kw.pop("enzyme_addition_index", None),
        )
        return render_markdown(
            ReportInput(
                evaluation_id="e1", created_at="2026-08-16T09:00:00+00:00",
                engine_version="1.0.0", recipe_name="vinaigrette", headline="RED",
                context=ctx, findings=(), envelope=r15_applied_texture.envelope(ctx),
                recommendation=recommend_format(ctx), recipe_id="r-001", **kw,
            )
        )

    return _build


def test_the_identity_block_names_the_product_recipe_and_basis(report):
    body = report()
    assert "## Product and formula identity" in body
    assert "| Product | vinaigrette |" in body
    assert "| Recipe id | r-001 |" in body
    assert "percent of total batch weight (sums to 100)" in body


def test_the_formula_table_carries_percent_grams_and_a_total(report):
    body = report()
    assert "| # | Ingredient | % of total | Grams | pH | Water content | Allergens |" in body
    assert "| 1 | Olive oil | 75 | 150 |" in body
    assert "| 2 | White vinegar | 25 | 50 |" in body
    assert "| | **Total** | **100** | **200** | | | |" in body


def test_the_process_table_marks_heat_and_the_enzyme_point(report):
    body = report(
        process_steps=(
            __import__("foodbrew.engine.types", fromlist=["ProcessStep"]).ProcessStep(
                1, "warm the base", True
            ),
            __import__("foodbrew.engine.types", fromlist=["ProcessStep"]).ProcessStep(
                2, "whisk in the enzyme"
            ),
        ),
        enzyme_addition_index=2,
    )
    assert "## Process" in body
    assert "| 1 | warm the base | yes | no |" in body
    assert "| 2 | whisk in the enzyme | no | yes |" in body


def test_unmeasured_parameters_are_listed_rather_than_omitted(report):
    body = report()
    assert "| Water activity | not measured |" in body
    assert "| Nutrition | not calculated |" in body


def test_an_ingredient_with_no_allergen_record_is_named_as_a_gap(report):
    body = report()
    assert "## Allergens" in body
    assert "not recorded for this ingredient" in body
    assert "Olive oil" in body


def test_batch_records_print_every_captured_parameter(report):
    body = report(
        batches=(
            ReportBatch(
                made_at="2026-08-16T10:30:00+00:00", batch_size_g=200.0, measured_ph=3.4,
                ph_method="meter", make_minutes=12, difficulty_score=2,
                enzyme_source_note="two Lactaid capsules", enzyme_addition_step=2,
                storage_mode="refrigerated", process_notes="split when I rushed it",
            ),
        )
    )
    assert "## Batch records" in body
    assert "| 2026-08-16 10:30 | 200 g | 3.4 (meter) | 12 | 2 of 5 | 2 | two Lactaid capsules | refrigerated |" in body
    assert "> split when I rushed it" in body


def test_no_batch_means_no_batch_section(report):
    assert "## Batch records" not in report()


def test_the_reformatted_report_still_passes_the_language_lint(report):
    body = report(
        batches=(
            ReportBatch(
                made_at="2026-08-16T10:30:00+00:00", batch_size_g=200.0, measured_ph=4.1,
                ph_method="strip", make_minutes=9, difficulty_score=1,
                enzyme_source_note="Beano", enzyme_addition_step=1, storage_mode="ambient",
            ),
        )
    )
    assert contains_prohibited(body) == ()
```

- [ ] **Step 5: Run them, plus every earlier report test**

Run: `.venv/bin/pytest tests/engine/test_report_formula.py tests/engine/test_report.py tests/engine/test_report_trial.py -q`
Expected: the new file passes and **M3's and M4's report tests still pass**. Two of M3's assert on the old `## What was checked` heading and its grams-only table; those two assertions are now wrong about a report that deliberately changed shape, so update *those assertions* to the new headings — and say so in the commit message. Do not delete them, and do not touch any assertion about findings, doses, occasions, or the disclaimer.

- [ ] **Step 6: Commit**

```bash
git add src/foodbrew/engine/report.py tests/engine/test_report_formula.py tests/engine/test_report.py
git commit -m "feat(engine): formula table, allergen declaration, process and batch records"
```

---

## Task 6: `GET /evaluations/{id}/report` and the export that feeds it

Decision #8. One assembler, two renderers, and a contract test that stops them drifting.

**Files:**
- Create: `src/foodbrew/api/routers/report.py`
- Modify: `src/foodbrew/api/routers/export.py`, `src/foodbrew/api/app.py`, `src/foodbrew/api/schemas.py`
- Create: `tests/api/test_report_endpoint.py`

- [ ] **Step 1: Extract the assembler**

`export.py` currently builds `ReportInput` inline in its route and builds `TrialReport` in `_trial_report`. Move both into a module-level function so a second caller can reuse them verbatim:

```python
def report_input(conn: sqlite3.Connection, evaluation_id: str) -> ReportInput | None:
    """Assemble everything both renderers consume. The single source of the
    report's content (plan decision #8) — the markdown export and the printable
    screen are two renderings of this one value, never two assemblies."""
    stored = evaluations_store.get(conn, evaluation_id)
    if stored is None:
        return None

    ctx = context_from_snapshot(stored.input_snapshot_json)
    stale, _changes = evaluations_store.freshness(conn, stored)
    recipe_id = formulations_store.recipe_id_for(conn, stored.formulation_id)
    recipe = recipes_store.get(conn, recipe_id) if recipe_id else None
    trial = _trial_report(conn, evaluation_id)

    return ReportInput(
        evaluation_id=stored.id,
        created_at=stored.created_at,
        engine_version=stored.engine_version,
        recipe_name=recipe.name if recipe else "Untitled recipe",
        recipe_id=recipe_id or "",
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
        trial=trial,
        batches=_batch_records(conn, evaluation_id),
    )


def _batch_records(conn: sqlite3.Connection, evaluation_id: str) -> tuple[ReportBatch, ...]:
    """Every batch of every trial on this evaluation, oldest first."""
    records: list[ReportBatch] = []
    for trial in trials_store.list_for_evaluation(conn, evaluation_id):
        for batch in trial.batches:
            records.append(
                ReportBatch(
                    made_at=batch.made_at, batch_size_g=batch.batch_size_g,
                    measured_ph=batch.measured_ph, ph_method=batch.ph_method,
                    make_minutes=batch.make_minutes,
                    difficulty_score=batch.difficulty_score,
                    enzyme_source_note=batch.enzyme_source_note,
                    enzyme_addition_step=batch.enzyme_addition_step,
                    storage_mode=batch.storage_mode, process_notes=batch.process_notes,
                )
            )
    return tuple(sorted(records, key=lambda r: r.made_at))
```

and reduce the route to:

```python
@router.get("/export/{evaluation_id}.md", response_class=PlainTextResponse)
def export_markdown(evaluation_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    data = report_input(conn, evaluation_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No evaluation '{evaluation_id}'.")
    return PlainTextResponse(render_markdown(data), media_type="text/markdown; charset=utf-8")
```

with `ReportBatch` added to the `report` import and `from foodbrew.store import trials as trials_store` at the top.

- [ ] **Step 2: The wire models**

Append to `schemas.py`:

```python
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
```

- [ ] **Step 3: The router**

```python
"""Spec §10 screen 8 as data — everything the printable page needs.

The screen used to render less than the markdown export because it consumed the
evaluation payload, which carries no recipe. This endpoint serves the same
assembly the export renders (plan decision #8), so the two cannot drift; the
contract test in tests/api/test_report_endpoint.py is what proves it.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from foodbrew.api.deps import get_conn
from foodbrew.api.routers.export import report_input
from foodbrew.api.schemas import (
    AllergenDeclarationOut,
    AllergenEntryOut,
    BatchRecordOut,
    FormulaLineOut,
    FormulaOut,
    ProcessLineOut,
    ReportOut,
    TrackedOut,
)
from foodbrew.engine.allergens import ALLERGEN_TEXT, Allergen, declare
from foodbrew.engine.formula import build as build_formula
from foodbrew.engine.formula import process_lines

router = APIRouter(tags=["report"])


def _allergen_names(food) -> list[str]:
    return [ALLERGEN_TEXT[Allergen(a)] for a in getattr(food, "allergens", ()) or ()]


@router.get("/evaluations/{evaluation_id}/report", response_model=ReportOut)
def get_report(evaluation_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    data = report_input(conn, evaluation_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No evaluation '{evaluation_id}'.")

    ctx = data.context
    form = ctx.formulation
    formula = build_formula(form.recipe, ctx.foods)
    declaration = declare([i.food_id for i in form.recipe], ctx.foods)

    return ReportOut(
        evaluation_id=data.evaluation_id, recipe_id=data.recipe_id,
        recipe_name=data.recipe_name, created_at=data.created_at,
        engine_version=data.engine_version, headline=data.headline, stale=data.stale,
        formula=FormulaOut(
            lines=[
                FormulaLineOut(
                    position=position, food_id=line.food_id, food_name=line.food_name,
                    amount_g=line.amount_g, percent_of_total=line.percent_of_total,
                    ph=TrackedOut.of(line.ph),
                    water_content_pct=TrackedOut.of(line.water_content_pct),
                    allergens=_allergen_names(ctx.foods.get(line.food_id)),
                )
                for position, line in enumerate(formula.lines, start=1)
            ],
            total_g=formula.total_g,
            printed_percent_total=formula.printed_percent_total,
        ),
        process=[
            ProcessLineOut(
                order=step.order, label=step.label, is_heat=step.is_heat,
                is_enzyme_addition_point=step.is_enzyme_addition_point,
            )
            for step in process_lines(form.process_steps, form.enzyme_addition_index)
        ],
        allergens=AllergenDeclarationOut(
            entries=[
                AllergenEntryOut(
                    allergen=str(e.allergen), text=e.text,
                    from_food_names=list(e.from_food_names),
                )
                for e in declaration.entries
            ],
            unrecorded_food_names=list(declaration.unrecorded_food_names),
        ),
        batches=[
            BatchRecordOut(
                made_at=b.made_at, batch_size_g=b.batch_size_g, measured_ph=b.measured_ph,
                ph_method=b.ph_method, make_minutes=b.make_minutes,
                difficulty_score=b.difficulty_score,
                enzyme_source_note=b.enzyme_source_note,
                enzyme_addition_step=b.enzyme_addition_step,
                storage_mode=b.storage_mode, process_notes=b.process_notes,
            )
            for b in data.batches
        ],
        serving_size_g=form.serving_size_g,
        measured_ph=TrackedOut.of(form.measured_ph),
        dwell_profile=form.dwell_profile.value if form.dwell_profile else None,
        format=form.format.value,
        trigger_food_names=[
            ctx.foods[i].name if i in ctx.foods else i for i in form.target_trigger_food_ids
        ],
        application_food_names=[
            ctx.foods[i].name if i in ctx.foods else i for i in form.application_food_ids
        ],
    )
```

Register it in `app.py` exactly as `trials` was: add `report` to the router import list and to the tuple in `create_app`.

- [ ] **Step 4: Write the tests**

```python
"""Decision #8 — one assembly, two renderings, and the proof they agree."""

import pytest


@pytest.fixture
def evaluated(client, vinaigrette):
    return client.post(
        f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
    ).json()


def test_the_report_endpoint_returns_the_formula_with_percentages(client, evaluated):
    payload = client.get(f"/api/v1/evaluations/{evaluated['id']}/report").json()
    percents = [line["percent_of_total"] for line in payload["formula"]["lines"]]
    assert sum(p for p in percents if p) == pytest.approx(100.0, abs=0.02)
    assert payload["formula"]["total_g"] == 150.0
    assert payload["recipe_name"] == "vinaigrette"


def test_the_lines_are_in_order_of_addition(client, evaluated):
    payload = client.get(f"/api/v1/evaluations/{evaluated['id']}/report").json()
    positions = [line["position"] for line in payload["formula"]["lines"]]
    assert positions == sorted(positions)


def test_the_declaration_names_the_gap_not_a_clearance(client, evaluated):
    payload = client.get(f"/api/v1/evaluations/{evaluated['id']}/report").json()
    assert payload["allergens"]["unrecorded_food_names"]


def test_a_batch_reaches_both_renderings(client, evaluated):
    trial = client.post(f"/api/v1/evaluations/{evaluated['id']}/trial").json()
    client.post(
        f"/api/v1/trials/{trial['id']}/batches",
        json={"batch_size_g": 200.0, "measured_ph": 3.4, "ph_method": "meter",
              "make_minutes": 12, "difficulty_score": 2,
              "enzyme_source_note": "two Lactaid capsules"},
    )
    payload = client.get(f"/api/v1/evaluations/{evaluated['id']}/report").json()
    markdown = client.get(f"/api/v1/export/{evaluated['id']}.md").text

    assert len(payload["batches"]) == 1
    assert payload["batches"][0]["make_minutes"] == 12
    assert "## Batch records" in markdown
    assert "two Lactaid capsules" in markdown


def test_the_two_renderings_agree_on_every_shared_number(client, evaluated):
    """The contract of decision #8: the screen and the file are one assembly."""
    payload = client.get(f"/api/v1/evaluations/{evaluated['id']}/report").json()
    markdown = client.get(f"/api/v1/export/{evaluated['id']}.md").text

    assert payload["recipe_name"] in markdown
    assert payload["engine_version"] in markdown
    assert payload["evaluation_id"] in markdown
    for line in payload["formula"]["lines"]:
        assert line["food_name"] in markdown
        assert f"{line['amount_g']:g}" in markdown
    assert f"{payload['formula']['total_g']:g}" in markdown


def test_a_missing_evaluation_is_a_404(client):
    assert client.get("/api/v1/evaluations/nope/report").status_code == 404
```

- [ ] **Step 5: Run them**

Run: `.venv/bin/pytest tests/api/test_report_endpoint.py tests/api/test_export.py tests/api/test_trial_export.py -q`
Expected: all pass. `test_export.py` asserts `"# Formulation report — vinaigrette"` — the title line is unchanged by this task, so that assertion stands.

- [ ] **Step 6: Commit**

```bash
git add src/foodbrew/api/routers/report.py src/foodbrew/api/routers/export.py src/foodbrew/api/app.py src/foodbrew/api/schemas.py tests/api/test_report_endpoint.py
git commit -m "feat(api): serve the report as data so the screen and the export cannot drift"
```

---

# Package B — the four gaps the audit found

## Task 7: `engine/structural.py` and the structured-field write path

Decision #4. §15 item 4 — *does inulinase degrade the structure of inulin-rich vegetables?* — currently has no in-product answer. This gives it one without dragging `Tracked` into a rule that reads plain tuples.

**Files:**
- Create: `src/foodbrew/engine/structural.py`
- Modify: `src/foodbrew/store/records.py`
- Create: `tests/engine/test_structural.py`, `tests/store/test_structured_records.py`

- [ ] **Step 1: The validator**

```python
"""Validation for the two structured catalogue fields (plan decision #4).

`enzyme.degrades_structural` and `food.structural` are JSON lists over closed
enums, not `Tracked` scalars, and `r15_applied_texture` reads them directly.
Their provenance lives INSIDE the value: `SeverityTier.UNCONFIRMED` is the
unconfirmed state, and §6.3.1 maps it to cannot_assess on every profile. So
answering §15 item 4 is flipping a tier from `unconfirmed` to `gradual` with a
citation — not attaching a truth label to a list.

Pure. This module validates; it never writes.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from foodbrew.engine.types import SeverityTier, StructuralClass


class StructuralError(ValueError):
    """Invalid structured payload. The store turns this into a ValidationRejection."""


def parse_enzyme_entries(raw: Sequence | str) -> tuple[dict, ...]:
    """`[{"structural_class": ..., "tier": ...}, ...]`, both closed enums."""
    entries = _as_list(raw)
    out: list[dict] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise StructuralError(
                "each entry is an object with a structural_class and a tier"
            )
        cls = _enum(StructuralClass, entry.get("structural_class"), "structural_class")
        tier = _enum(SeverityTier, entry.get("tier"), "tier")
        if cls.value in seen:
            raise StructuralError(f"'{cls.value}' appears twice; keep one entry per class")
        seen.add(cls.value)
        out.append({"structural_class": cls.value, "tier": tier.value})
    return tuple(out)


def parse_food_classes(raw: Sequence | str) -> tuple[str, ...]:
    """`["pectin_cellulose", ...]` — a food carries classes, not tiers."""
    out: list[str] = []
    for value in _as_list(raw):
        cls = _enum(StructuralClass, value, "structural class")
        if cls.value not in out:
            out.append(cls.value)
    return tuple(out)


def _as_list(raw: Sequence | str) -> list:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise StructuralError("that is not valid JSON") from exc
    if not isinstance(raw, list):
        raise StructuralError("expected a list")
    return raw


def _enum(enum_cls, value, what: str):
    try:
        return enum_cls(value)
    except ValueError as exc:
        allowed = ", ".join(m.value for m in enum_cls)
        raise StructuralError(f"unknown {what} '{value}'; allowed: {allowed}") from exc
```

- [ ] **Step 2: The store allowlist and writer**

In `src/foodbrew/store/records.py`, add below `PLAIN_FIELDS`:

```python
#: JSON list columns over closed enums (plan decision #4). Separate from
#: TRACKED_FIELDS because they carry no _status/_source pair — their provenance
#: is the tier inside the value — and separate from PLAIN_FIELDS because a free
#: string is not a legal value for either of them.
STRUCTURED_FIELDS: Mapping[str, Mapping[str, str]] = {
    "enzyme": {"degrades_structural_json": "enzyme_entries"},
    "food": {"structural_json": "food_classes"},
}


def structured_kind(table: str, field: str) -> str | None:
    return STRUCTURED_FIELDS.get(table, {}).get(field)


def coerce_structured(table: str, field: str, raw) -> str:
    """Validate through the engine and return the JSON text to store."""
    kind = structured_kind(table, field)
    if kind is None:
        raise ValidationRejection(f"'{field}' is not a structured field on {table}.")
    try:
        if kind == "enzyme_entries":
            return json.dumps(list(structural.parse_enzyme_entries(raw)))
        return json.dumps(list(structural.parse_food_classes(raw)))
    except structural.StructuralError as exc:
        raise ValidationRejection(f"'{field}': {exc}") from exc


def update_structured(
    conn: sqlite3.Connection, table: str, record_id: str, field: str, raw
) -> None:
    """A founder edit to a structured field. Audited like every other edit."""
    check_table(table)
    payload = coerce_structured(table, field, raw)
    before = conn.execute(
        f"SELECT {field} FROM {table} WHERE id = ?", (record_id,)
    ).fetchone()
    if before is None:
        raise ValidationRejection(f"No {table} '{record_id}'.")

    conn.execute(f"UPDATE {table} SET {field} = ? WHERE id = ?", (payload, record_id))
    audit.record(
        conn, action="edit", entity=f"{table}:{record_id}",
        before={field: before[field]}, after={field: payload},
    )
    conn.commit()
```

with `import json`, `from foodbrew.engine import structural`, and `from foodbrew.store import audit` at the top if they are not already there. Read the existing `update` function first and mirror its audit call signature exactly rather than the sketch above — the real one is the authority.

Note what is deliberately absent: **no `set_confirmed` path for structured fields**. There is no `_status` column to write, so approving a structured proposal writes the value and records the citation in the audit trail (Task 8), which is the honest equivalent.

- [ ] **Step 3: Tests for the validator**

```python
"""Decision #4 — the tier inside the value is the provenance."""

import pytest

from foodbrew.engine.structural import (
    StructuralError,
    parse_enzyme_entries,
    parse_food_classes,
)


def test_a_legal_enzyme_entry_round_trips():
    assert parse_enzyme_entries([{"structural_class": "pectin_cellulose", "tier": "gradual"}]) == (
        {"structural_class": "pectin_cellulose", "tier": "gradual"},
    )


def test_json_text_is_accepted_because_a_proposal_stores_text():
    assert parse_enzyme_entries('[{"structural_class": "starch", "tier": "rapid"}]') == (
        {"structural_class": "starch", "tier": "rapid"},
    )


def test_an_unknown_class_is_refused_and_names_the_vocabulary():
    with pytest.raises(StructuralError) as exc:
        parse_enzyme_entries([{"structural_class": "cellulose", "tier": "gradual"}])
    assert "pectin_cellulose" in str(exc.value)


def test_an_unknown_tier_is_refused():
    with pytest.raises(StructuralError) as exc:
        parse_enzyme_entries([{"structural_class": "starch", "tier": "fast"}])
    assert "gradual" in str(exc.value)


def test_a_duplicate_class_is_refused_rather_than_silently_merged():
    with pytest.raises(StructuralError):
        parse_enzyme_entries([
            {"structural_class": "starch", "tier": "gradual"},
            {"structural_class": "starch", "tier": "rapid"},
        ])


def test_unconfirmed_is_a_legal_tier_because_it_is_the_default_state():
    assert parse_enzyme_entries([{"structural_class": "pectin_cellulose", "tier": "unconfirmed"}])


def test_a_food_carries_classes_without_tiers():
    assert parse_food_classes(["starch", "starch", "structural_protein"]) == (
        "starch", "structural_protein",
    )


def test_malformed_json_is_refused_plainly():
    with pytest.raises(StructuralError) as exc:
        parse_enzyme_entries("not json")
    assert "JSON" in str(exc.value)


def test_a_bare_object_is_refused():
    with pytest.raises(StructuralError):
        parse_enzyme_entries({"structural_class": "starch", "tier": "gradual"})
```

- [ ] **Step 4: Tests for the write path**

```python
"""Decision #4 over real SQLite — the §15 item 4 answer, recorded in product."""

import json

import pytest

from foodbrew.engine import ValidationRejection
from foodbrew.store import records


def _entries(conn, enzyme_id):
    row = conn.execute(
        "SELECT degrades_structural_json FROM enzyme WHERE id = ?", (enzyme_id,)
    ).fetchone()
    return json.loads(row["degrades_structural_json"])


def test_inulinase_can_be_moved_off_unconfirmed(conn):
    """Spec §15 item 4: the answer has an in-product home now."""
    before = _entries(conn, "inulinase")
    assert any(e["tier"] == "unconfirmed" for e in before)

    records.update_structured(
        conn, "enzyme", "inulinase", "degrades_structural_json",
        [{"structural_class": "pectin_cellulose", "tier": "gradual"}],
    )
    after = _entries(conn, "inulinase")
    assert after == [{"structural_class": "pectin_cellulose", "tier": "gradual"}]


def test_the_edit_is_audited(conn):
    records.update_structured(
        conn, "enzyme", "inulinase", "degrades_structural_json",
        [{"structural_class": "pectin_cellulose", "tier": "gradual"}],
    )
    row = conn.execute(
        "SELECT * FROM audit_event WHERE entity = 'enzyme:inulinase' ORDER BY id DESC"
    ).fetchone()
    assert row is not None
    assert "gradual" in row["after_json"]


def test_an_illegal_tier_is_refused_before_anything_is_written(conn):
    before = _entries(conn, "inulinase")
    with pytest.raises(ValidationRejection):
        records.update_structured(
            conn, "enzyme", "inulinase", "degrades_structural_json",
            [{"structural_class": "pectin_cellulose", "tier": "quick"}],
        )
    assert _entries(conn, "inulinase") == before


def test_a_scalar_field_cannot_be_written_through_the_structured_door(conn):
    with pytest.raises(ValidationRejection):
        records.update_structured(conn, "enzyme", "inulinase", "ph_min", [])


def test_a_structured_field_cannot_be_written_through_the_scalar_door(conn):
    with pytest.raises(ValidationRejection):
        records.update(conn, "enzyme", "inulinase", {"degrades_structural_json": "[]"})


def test_the_change_reaches_r15_on_the_next_evaluation(conn, vinaigrette_rows):
    """The whole point: a confirmed tier changes what the envelope can say."""
    from foodbrew.store import evaluations as evaluations_store

    records.update_structured(
        conn, "enzyme", "lactase_fungal_acid", "degrades_structural_json",
        [{"structural_class": "pectin_cellulose", "tier": "gradual"}],
    )
    rerun = evaluations_store.run(conn, vinaigrette_rows["formulation_id"])
    r15 = [f for f in rerun.findings if f.rule_id == "R15"]
    assert r15, "R15 now has an intersection to report"
```

- [ ] **Step 5: Run them**

Run: `.venv/bin/pytest tests/engine/test_structural.py tests/store/test_structured_records.py tests/store/test_records.py -q`
Expected: all pass, including M3's existing `test_fields_outside_the_allowlist_are_refused` and `test_a_direct_edit_still_cannot_produce_confirmed` — the structured door is a separate door, not a widening of the scalar allowlist.

- [ ] **Step 6: Commit**

```bash
git add src/foodbrew/engine/structural.py src/foodbrew/store/records.py tests/engine/test_structural.py tests/store/test_structured_records.py
git commit -m "feat: give the structural fields an in-product edit path with enum validation"
```

---

## Task 8: Structured proposals and the API surface for both

The research track (§2.3) must be able to carry the structural answer, not just the scalar ones.

**Files:**
- Modify: `src/foodbrew/store/proposals.py`, `src/foodbrew/api/routers/records.py`, `src/foodbrew/api/routers/proposals.py`, `src/foodbrew/api/schemas.py`
- Create: `tests/api/test_structured_fields.py`

- [ ] **Step 1: Let a proposal carry a structured value**

In `store/proposals.py`, `create` validates the proposed value through `records.coerce`. Extend it so a structured field validates through `records.coerce_structured` instead — read the function and add the branch at the top of its validation, keeping everything else identical:

```python
    if records.structured_kind(table_name, field) is not None:
        # Stored as the canonical JSON text the writer will apply verbatim.
        proposed_value = records.coerce_structured(table_name, field, proposed_value)
    else:
        records.coerce(table_name, field, proposed_value)  # existing behaviour
```

and in `approve`, branch the same way so approving writes through `records.update_structured` (which audits with the citation) rather than `records.set_confirmed` (which needs a `_status` column that does not exist):

```python
    if records.structured_kind(proposal.table_name, proposal.field) is not None:
        records.update_structured(
            conn, proposal.table_name, proposal.record_id, proposal.field,
            proposal.proposed_value,
        )
        # There is no _status column to flip; the citation lives in the audit
        # trail and in the proposal row, which stays as the record of who said so.
    else:
        records.set_confirmed(...)  # existing call, unchanged
```

Read the real `approve` before editing — it holds the TOCTOU fix from M3 (`a81dba6`) and that locking must not be disturbed.

- [ ] **Step 2: The API**

In `api/schemas.py`:

```python
class StructuredEditIn(BaseModel):
    """A structured catalogue field. `value` is a list, validated server-side
    against the closed enums (plan decision #4); no truth label is accepted."""

    value: list[dict] | list[str]
```

In `api/routers/records.py`, add a route beside the existing editors:

```python
@router.put("/{table}/{record_id}/structured/{field}", response_model=dict)
def edit_structured(
    table: str, record_id: str, field: str, payload: StructuredEditIn,
    conn: sqlite3.Connection = Depends(get_conn),
):
    records_store.update_structured(conn, table, record_id, field, payload.value)
    return {"ok": True}
```

matching the module's existing path shape — read the file and follow whatever prefix its enzyme/food routes already use rather than inventing `/{table}`. If those routes are `/enzymes/{id}` and `/foods/{id}`, write two explicit routes instead of a generic one, because the rest of the router is explicit and consistency beats cleverness here.

- [ ] **Step 3: Write the tests**

```python
"""§2.3 end to end for a structured field: propose, approve, re-evaluate."""

def test_a_structured_proposal_is_accepted_and_validated(client):
    good = client.post(
        "/api/v1/proposals",
        json={"table_name": "enzyme", "record_id": "inulinase",
              "field": "degrades_structural_json",
              "proposed_value": '[{"structural_class": "pectin_cellulose", "tier": "gradual"}]',
              "source_citation": "Supplier spec sheet, 2026-08"},
    )
    assert good.status_code == 201, good.text

    bad = client.post(
        "/api/v1/proposals",
        json={"table_name": "enzyme", "record_id": "inulinase",
              "field": "degrades_structural_json",
              "proposed_value": '[{"structural_class": "pectin_cellulose", "tier": "quick"}]',
              "source_citation": "a guess"},
    )
    assert bad.status_code == 422
    assert "gradual" in bad.json()["detail"]


def test_approving_it_writes_the_value_and_keeps_the_citation(client, conn):
    created = client.post(
        "/api/v1/proposals",
        json={"table_name": "enzyme", "record_id": "inulinase",
              "field": "degrades_structural_json",
              "proposed_value": '[{"structural_class": "pectin_cellulose", "tier": "gradual"}]',
              "source_citation": "Supplier spec sheet, 2026-08"},
    ).json()

    approved = client.post(f"/api/v1/proposals/{created['id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    enzyme = next(
        e for e in client.get("/api/v1/enzymes").json() if e["id"] == "inulinase"
    )
    assert {"structural_class": "pectin_cellulose", "tier": "gradual"} in enzyme[
        "degrades_structural"
    ]


def test_a_direct_structured_edit_is_labelled_as_the_founder_not_as_confirmed(client, conn):
    client.put(
        "/api/v1/enzymes/inulinase/structured/degrades_structural_json",
        json={"value": [{"structural_class": "pectin_cellulose", "tier": "gradual"}]},
    )
    row = conn.execute(
        "SELECT * FROM audit_event WHERE entity = 'enzyme:inulinase' ORDER BY id DESC"
    ).fetchone()
    assert row is not None


def test_the_scalar_proposal_path_is_unchanged(client):
    created = client.post(
        "/api/v1/proposals",
        json={"table_name": "enzyme", "record_id": "lactase_fungal_acid",
              "field": "ph_shelf_stable_min", "proposed_value": "3.2",
              "source_citation": "Amano technical data sheet"},
    ).json()
    client.post(f"/api/v1/proposals/{created['id']}/approve")
    enzyme = next(
        e for e in client.get("/api/v1/enzymes").json() if e["id"] == "lactase_fungal_acid"
    )
    assert enzyme["ph_shelf_stable_min"]["value"] == 3.2
    assert enzyme["ph_shelf_stable_min"]["status"] == "confirmed"
```

- [ ] **Step 4: Run them**

Run: `.venv/bin/pytest tests/api/test_structured_fields.py tests/api/test_proposals.py tests/store/test_proposals.py -q`
Expected: all pass. If `test_a_direct_edit_still_cannot_produce_confirmed` fails, the structured branch has leaked into the scalar path — fix the branch, never the test.

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/store/proposals.py src/foodbrew/api/routers/records.py src/foodbrew/api/schemas.py tests/api/test_structured_fields.py
git commit -m "feat: propose and approve structured catalogue fields through the inbox"
```

---

## Task 9: Last-edited, and an honest staleness diff

Decisions #5 and #3.

**Files:**
- Modify: `src/foodbrew/store/audit.py`, `src/foodbrew/store/snapshot.py`, `src/foodbrew/api/routers/records.py`, `src/foodbrew/api/schemas.py`
- Create: `tests/store/test_last_edited.py`

- [ ] **Step 1: Derive last-edited from the audit trail**

Add to `store/audit.py`:

```python
def last_edited_for(conn: sqlite3.Connection, table: str) -> dict[str, str]:
    """Newest edit timestamp per record of `table`, keyed by record id.

    Derived, not stored (plan decision #5): every edit already writes an
    audit_event whose entity is "<table>:<id>". A global reset writes
    entity='reference' and therefore does NOT stamp individual records — a
    record with no row here has never been edited, and the editor says
    "shipped value" rather than inventing a date.
    """
    prefix = f"{table}:"
    return {
        row["entity"][len(prefix):]: row["last_edited"]
        for row in conn.execute(
            "SELECT entity, MAX(timestamp) AS last_edited FROM audit_event"
            " WHERE entity LIKE ? GROUP BY entity",
            (prefix + "%",),
        )
    }
```

- [ ] **Step 2: Surface it on the record payloads**

In `api/schemas.py`, add to both `EnzymeOut` and `FoodOut`:

```python
    #: ISO-8601 of the newest founder edit, or None if this record is untouched.
    last_edited: str | None = None
```

and in `api/routers/records.py`'s list endpoints, look the map up once per request and pass it in — never once per record, which would be a query per row. Read the router and follow its existing shape; the pattern is:

```python
    edits = audit.last_edited_for(conn, "enzyme")
    return [
        EnzymeOut.of(e).model_copy(update={"last_edited": edits.get(e.id)})
        for e in catalog.enzymes.values()
    ]
```

- [ ] **Step 3: Make the staleness diff tell the truth about an upgrade**

Decision #3: after Task 4, every pre-M5 evaluation is stale because a *field was added*, not because the founder changed anything. In `store/snapshot.py`'s `diff_snapshots`, a key present in the new payload and absent from the old must be reported as an upgrade rather than an edit. Read the function, then add the branch that emits:

```python
            SnapshotChange(
                kind="field_added", record_id=record_id, field=field,
                before=None, after=new_value,
            )
```

and make sure `SnapshotChange`'s existing `kind` values are unchanged for every other case, because M3's `StaleBanner.tsx` switches on them.

In the banner copy (Task 14 restyles it, but the string lives in the component), a `field_added` change reads: *"this evaluation predates a catalogue upgrade — re-run to pick up the new fields"*.

- [ ] **Step 4: Write the tests**

```python
"""Decisions #5 and #3 — history without a column, and an honest banner."""

from foodbrew.store import audit, records


def test_an_untouched_record_has_no_last_edited(conn):
    assert audit.last_edited_for(conn, "enzyme").get("lactase_fungal_acid") is None


def test_an_edit_stamps_that_record_only(conn):
    records.update(conn, "enzyme", "lactase_fungal_acid", {"ph_shelf_stable_min": 3.2})
    edits = audit.last_edited_for(conn, "enzyme")
    assert edits["lactase_fungal_acid"]
    assert "inulinase" not in edits


def test_the_newest_edit_wins(conn):
    records.update(conn, "enzyme", "lactase_fungal_acid", {"ph_shelf_stable_min": 3.2})
    first = audit.last_edited_for(conn, "enzyme")["lactase_fungal_acid"]
    records.update(conn, "enzyme", "lactase_fungal_acid", {"ph_shelf_stable_min": 3.4})
    second = audit.last_edited_for(conn, "enzyme")["lactase_fungal_acid"]
    assert second >= first


def test_a_global_reset_does_not_pretend_to_be_a_per_record_edit(conn):
    records.reset_all(conn)
    assert audit.last_edited_for(conn, "enzyme") == {}


def test_a_record_edited_then_reset_keeps_its_history(conn):
    """Reset-to-baseline is itself an edit of that record, so it stamps it."""
    records.update(conn, "enzyme", "lactase_fungal_acid", {"ph_shelf_stable_min": 3.2})
    records.reset_enzyme(conn, "lactase_fungal_acid")
    assert audit.last_edited_for(conn, "enzyme")["lactase_fungal_acid"]


def test_an_added_field_is_reported_as_an_upgrade_not_an_edit(conn, vinaigrette_rows):
    import json

    from foodbrew.store import evaluations as evaluations_store
    from foodbrew.store.snapshot import diff_snapshots

    stored = evaluations_store.run(conn, vinaigrette_rows["formulation_id"])
    old = json.loads(stored.input_snapshot_json)
    for food in old["foods"]:
        food.pop("allergens", None)

    changes = diff_snapshots(json.dumps(old, sort_keys=True), stored.input_snapshot_json)
    assert changes
    assert all(c.kind == "field_added" for c in changes if c.field == "allergens")
```

- [ ] **Step 5: Run them**

Run: `.venv/bin/pytest tests/store/test_last_edited.py tests/store/test_staleness.py tests/store/test_audit.py tests/api/test_records.py -q`
Expected: all pass. `test_re_running_does_not_make_the_first_run_stale` must still hold — the banner still must not flap.

- [ ] **Step 6: Commit**

```bash
git add src/foodbrew/store/audit.py src/foodbrew/store/snapshot.py src/foodbrew/api/routers/records.py src/foodbrew/api/schemas.py tests/store/test_last_edited.py
git commit -m "feat: derive per-record last-edited, and say when staleness is an upgrade"
```

---

## Task 10: Seed correction — `is_prebiotic` back to the three the spec names

The audit's fourth gap. §9.2 names GOS, inulin-type fructans and graminan-type fructans as the prebiotic substrates R9 exists for; the seed also flags `fiber` and `pectin`, so R9 fires advisory findings for cellulase and pectinase that no source supports.

**Files:**
- Modify: `seed/substrates.json`
- Create: `tests/test_seed_prebiotic_scope.py`

- [ ] **Step 1: Correct the seed**

In `seed/substrates.json`, set `"is_prebiotic": false` on `fiber` and `pectin`, leaving `gos`, `inulin_fructan` and `graminan_fructan` true. Add a source note on each corrected record in the seed's existing style:

```json
"notes": "Not flagged prebiotic: §9.2 scopes R9 to GOS and the two fructan classes."
```

- [ ] **Step 2: Lock the scope with a test**

```python
"""Spec §9.2 — R9's trigger set is exactly three substrates."""

from foodbrew.seedload.loader import load_seed

PREBIOTIC = {"gos", "inulin_fructan", "graminan_fructan"}


def test_exactly_the_spec_named_substrates_are_prebiotic():
    seed = load_seed()
    flagged = {s.id for s in seed.substrates.values() if s.is_prebiotic}
    assert flagged == PREBIOTIC


def test_r9_no_longer_fires_for_a_cellulase_only_blend(make_ctx, seed):
    """The observable consequence: a structure-degrading blend with no fructan
    or GOS target raises no prebiotic-tension advisory."""
    from foodbrew.engine.rules import r09_prebiotic_tension
    from foodbrew.engine.types import Phase

    ctx = make_ctx(enzymes=(("cellulase", None, Phase.DRY),), recipe=(("olive_oil", 100.0),))
    assert r09_prebiotic_tension.evaluate(ctx) == []
```

- [ ] **Step 3: Run the affected suites**

Run: `.venv/bin/pytest tests/test_seed_prebiotic_scope.py tests/engine/test_r08_r09_r10.py tests/test_golden_fixtures.py -q`
Expected: all pass. Golden fixture (g) asserts R9 fires for inulinase and for alpha-galactosidase — both keep their prebiotic substrates, so (g) is untouched. If (g) fails, the wrong substrates were edited.

- [ ] **Step 4: Commit**

```bash
git add seed/substrates.json tests/test_seed_prebiotic_scope.py
git commit -m "fix(seed): scope is_prebiotic to the three substrates §9.2 names"
```

---

# Package C — make the spec describe what was built

## Task 11: Amend the spec, and log every amendment

Decision #13. Four milestones each flagged deviations "to the spec owner"; none were ever written down, so the spec now contradicts the code in eleven places. This task closes that. It changes no code — but a spec that lies is a defect, and the next person to read §6.4 and believe it will build the wrong thing.

**Files:**
- Modify: `docs/superpowers/specs/2026-08-13-enzyme-rules-engine-design.md`
- Create: `tests/test_spec_amendments.py`

- [ ] **Step 1: The eleven edits, in spec order**

Make each edit in the section named. The spec already has a house style for exceptions — R12's row carries a bolded **Promotion condition** sentence and R1's carries its **stated fallback margin** — so extend that style rather than inventing a new one.

**§4 (architecture, the seed-loading sentence).** Today: *"Loaded on first boot; founder edits go to SQLite only; seeds stay pristine for reset and git-diffable review."* Replace with:

> Loaded on first boot only — a later boot opens the existing database unchanged, verifies its tables, and applies any additive column migration it is missing. Founder edits go to SQLite only and are never overwritten by a restart; re-seeding happens exclusively through the reset-to-baseline action (Workflow D). Every read after boot goes through SQLite, never back to `seed/*.json`.

**§5.1 (the `food` table row).** Add to the field list, after `structural_json`:

> **`allergens_json`** (list over a closed nine-value vocabulary: milk, egg, fish, crustacean shellfish, tree nut, peanut, wheat, soy, sesame). Catalogue reference data, carried into the evaluation snapshot and printed as a declaration on the report. **No rule reads it** — an allergen never changes a verdict. An empty list means *not recorded*, never *contains none*.

**§5.4 (truth labels, the `confirmed` bullet).** Today: *"`confirmed` — verified against a named source, recorded in the paired `*_source` field."* Append:

> Only an approved research-track proposal (§2.3) may write `confirmed`, using the proposal's `source_citation` as the `*_source` value. A direct founder edit in the database editor always writes `user_provided` with source "entered by founder", however well-sourced the value is in her head — the form is not a named source. Structured fields (§6.3.1's `degrades_structural_json`, and `structural_json`) carry no `*_status` pair at all: their provenance is the tier inside the value, so an approved proposal writes the value and the citation is kept in the proposal row and the audit trail.

**§6.1, rows R2, R7 and R11 (M1's deviation #4 — the highest-impact amendment).** Add to each row, in R12's bolded style. For R7:

> **Per-field advisory exception:** a `cannot_assess` caused solely by the enzyme's own permanently-unconfirmed static catalogue field (`dose_evidence_threshold`, unconfirmed for 11 of the 12 shipped enzymes) is **advisory** and does not gray the headline. Every other `cannot_assess` this rule can produce — a missing food load, a missing dose on the formulation — stays headline-capable, because those are gaps the founder can close.

Same sentence for **R2** naming `ph_min`/`ph_max` (unconfirmed for 6 of 12), and for **R11** naming `is_gras` (unconfirmed for 10 of 12). The rationale is R12's, verbatim in spirit: headline-capable against a catalogue that seeds unconfirmed would gray every formulation regardless of merit, which makes the tool useless and the §4m fixtures unreachable.

**§6.1, row R13 (M3's decision #6).** Append:

> The ladder is always scanned from the top — `premixed_wet` first — never from the formulation's current format, so a formulation already on `dry_sachet` that would also clear as `premixed_wet` is told so. When no position clears, the recommendation is none, with a note naming the rules no format change can fix (an R14 uncovered substrate, for instance).

**§6.3 (the occasion envelope) — M4's decision #9, the invented scale.** Add after the severity table:

> **Observed texture scale (engineering convention, not a measurement).** The Observed column is filled from `trial_observation.score`, a 1–5 scale scored against an undressed control: 1 indistinguishable, 2 slightly softer, 3 clearly softer, 4 limp or watery, 5 badly broken down. Scores map to verdicts as 1–2 pass, 3 amber, 4–5 red. This mapping is a stated convention with the same standing as R1's fallback margin — it exists so the column is computable, it is labelled wherever it is shown, and it is not a scientific claim. Revisit it once the founder has scored real trials against it.

**§6.5 (protocol generation).** Add a **Cadence** column to the table, marking taste, texture and storage rows `scheduled` and the make-it capture, usability log, symptom logging and pH entry rows `per_use`, then add below it:

> Per-use items are never overdue: they are listed under "log these as they happen" rather than on the due-checkpoint clock. Scheduled items are due when the elapsed time since the batch was made reaches their offset and no observation of that type, in that dwell bucket, for that food has been recorded.

**§7 (the auto-variant table, R1 row) — M3's decision #4.** Append to the "raise recipe pH" entry:

> — this middle suggestion is a note, not a machine-applicable patch. §12 item 1 says recipe pH is a worst-case minimum over wet ingredients, not a mixing model, so an engine that removed the vinegar and reported the result would be publishing the second-lowest ingredient pH as if it were a measurement. It names the ingredient currently setting the floor and asks her to measure what she makes. The other two entries in this row remain machine-applicable.

**§10 (screens, screen 8).** Replace the report screen's description with the format package A implements:

> 8. **Report** — print-friendly page and Markdown export, rendered from one assembly so the two cannot disagree. Carries: product and formula identity (product, recipe id, format, serving size, declared occasion, evaluation id, engine version); the **formula** as percent of total batch weight in order of addition, with grams beside each line and a total row; the **allergen declaration**, naming ingredients whose allergens are not recorded rather than implying they carry none; the **process** sequence with heat flags and the enzyme-addition point; **finished-product parameters**, listing water activity, viscosity and nutrition as not measured rather than omitting them; findings by group; dose, GI window and occasion envelope with observed columns; **batch records** for every trial batch, with the parameters captured as it was made; observed results under §6.6's three headings; open questions; provenance; and the fixed footer.

**§13 (testing).** Two edits. Add the fixture-input policy as a paragraph before fixture (a):

> Golden fixtures take every **enzyme** record from the real shipped seed. They supply `measured_ph` and per-food `typical_load_value` as explicit `user_provided` test inputs, because every seeded food pH and load is `unconfirmed` by design (§9.3) and a fixture that depended on them would assert the seed's gaps rather than the rules. Fixture (m) is the one deliberately synthetic record.

and correct fixture (b), which the code has always contradicted:

> (b) Creamy dressing, recipe pH 4.4 (explicit test input, not asserted as any real food's pH), same enzymes → AMBER: **R1 AMBER** (4.4 is inside the activity range but below the 5.0 optimum — sluggish and recoverable, per §6.1 R1), R4 AMBER, R8 AMBER with a dairy substrate present.

Also amend the report-lint line to state the matching rule:

> **Report lint:** the prohibited-words list (§10) is asserted absent from every generated report and every engine message, including trial output, matched on **word boundaries** — "safety" is permitted, "safe" is not, which is what lets the §10 footer survive its own lint. A separate, stricter **substring** lint runs over `api/` source, where no prohibited word has any legitimate reason to appear.

**§14 (milestones).** Add the M5 line after M4:

> - **M5 — Report format, punch list, and the UI pass:** the report in the shape a food scientist reads it (percent-of-total formula in order of addition, allergen declaration, process table, batch records, unmeasured parameters stated rather than omitted); the first schema migration; structured catalogue fields made editable and proposable so §15 item 4 has an in-product answer; per-record last-edited; and a design-token, accessibility and mobile pass over the whole UI.

**§15 (open questions).** Add two:

> 9. Which allergen does the generic `nuts_seeds` catalogue entry carry — tree nut, peanut, sesame, or several? Seeded as *not recorded* rather than guessed; closable through the database editor.
> 10. Is the observed texture scale of §6.3 calibrated the way the founder actually scores? It is an engineering convention until she has scored real trials against it.

- [ ] **Step 2: Add the amendments log**

Append a new section at the end of the spec:

```markdown
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
```

- [ ] **Step 3: Lock the amendments that the code can check**

```python
"""Spec §16 — the amendments that are assertions about behaviour, not prose.

A spec sentence nothing checks drifts again. These four are checkable, so they
are checked; the rest live in §16's table and in review.
"""

import pathlib

SPEC = (
    pathlib.Path(__file__).resolve().parents[1]
    / "docs/superpowers/specs/2026-08-13-enzyme-rules-engine-design.md"
)


def spec_text() -> str:
    return SPEC.read_text(encoding="utf-8")


def test_the_spec_documents_the_per_field_advisory_exception():
    """M1 deviation #4 — the one that changes what a headline says."""
    text = spec_text()
    assert "Per-field advisory exception" in text
    for field in ("dose_evidence_threshold", "is_gras", "ph_min"):
        assert field in text


def test_the_advisory_exception_matches_the_rules_as_built():
    """The spec now claims R2/R7/R11 have an advisory branch. Prove they do."""
    import inspect

    from foodbrew.engine.rules import r02_gi_window, r07_dosing, r11_food_grade

    for module in (r02_gi_window, r07_dosing, r11_food_grade):
        assert "advisory=True" in inspect.getsource(module), module.RULE_ID


def test_the_spec_states_the_observed_texture_scale():
    text = spec_text()
    assert "Observed texture scale" in text
    assert "indistinguishable" in text


def test_the_scale_in_the_spec_matches_the_scale_in_the_engine():
    from foodbrew.engine.observations import TEXTURE_SCALE

    text = spec_text()
    for wording in TEXTURE_SCALE.values():
        assert wording.split(" —")[0].split(",")[0][:18] in text, wording


def test_the_spec_has_an_amendments_log_covering_every_milestone():
    text = spec_text()
    assert "# 16. Amendments" in text
    for milestone in ("M1", "M2", "M3", "M4", "M5"):
        assert milestone in text.split("# 16. Amendments")[1]


def test_the_spec_lists_m5_in_the_milestones():
    assert "M5 —" in spec_text()
```

- [ ] **Step 4: Run them**

Run: `.venv/bin/pytest tests/test_spec_amendments.py -q`
Expected: 6 passed. If `test_the_scale_in_the_spec_matches_the_scale_in_the_engine` fails, the spec's wording drifted from `engine/observations.py` — copy the engine's wording, since that is what the founder scores against.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-08-13-enzyme-rules-engine-design.md tests/test_spec_amendments.py
git commit -m "docs(spec): write four milestones of accepted deviations into the spec"
```

---

# Package D — the UI pass

Audit baseline, scored against the ten dimensions of the design-system skill: colour 6, typography 3, spacing 3, component consistency 4, responsive 2, dark mode 0, animation 2, accessibility 4, density 6, polish 2 — **32/100**. No AI slop; the problem is the opposite. The skeleton is sound (semantic HTML, 76 test ids, a print stylesheet, one 64-line stylesheet), so this is tokens and states, not a rebuild.

Design direction, stated once so no task drifts: **a lab instrument, not a landing page.** The verdict reads like a panel; the trial screens work one-handed on a phone with dressing on the other hand; nothing animates for decoration.

## Task 12: `styles.css` — the token system, states, and dark mode

**Files:**
- Modify: `web/src/styles.css`

- [ ] **Step 1: Replace the `:root` block with a token set**

```css
:root {
  /* Verdict palette — unchanged hues, now named as roles (§6.4). */
  --red: #b3261e; --amber: #9a6700; --gray: #5c5f66; --green: #1a7f37;
  --red-bg: #fdf0ef; --amber-bg: #fdf6e6; --gray-bg: #f2f3f4; --green-bg: #eef8f1;

  --bg: #ffffff; --surface: #ffffff; --muted: #f5f6f7;
  --ink: #1b1c1e; --ink-soft: #5c5f66; --line: #d7d9dd; --line-strong: #b9bcc2;
  --accent: #17527a; --accent-bg: #eaf2f8;

  /* 4px spacing scale. Every margin and pad in this file uses one of these. */
  --s1: 0.25rem; --s2: 0.5rem; --s3: 0.75rem; --s4: 1rem;
  --s5: 1.5rem; --s6: 2rem; --s7: 3rem;

  /* 1.25 type scale off a 1rem body. */
  --t-xs: 0.78rem; --t-sm: 0.875rem; --t-base: 1rem;
  --t-lg: 1.25rem; --t-xl: 1.563rem; --t-2xl: 1.953rem;

  --radius: 6px; --radius-sm: 4px;
  --shadow: 0 1px 2px rgb(0 0 0 / 0.06), 0 2px 8px rgb(0 0 0 / 0.04);
  --focus: 0 0 0 3px var(--accent-bg), 0 0 0 5px var(--accent);
  --touch: 44px;   /* minimum interactive target — the trial screens are used on a phone */

  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  font-size: 16px;
  line-height: 1.5;
  color-scheme: light dark;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #16181a; --surface: #1d2022; --muted: #24282b;
    --ink: #e9eaec; --ink-soft: #a8adb4; --line: #33383d; --line-strong: #474d54;
    --red: #f2837b; --amber: #e0b341; --gray: #a8adb4; --green: #6cc48a;
    --red-bg: #2a1917; --amber-bg: #29220f; --gray-bg: #24282b; --green-bg: #14251a;
    --accent: #7db8e0; --accent-bg: #16303f;
    --shadow: 0 1px 2px rgb(0 0 0 / 0.4), 0 2px 8px rgb(0 0 0 / 0.3);
  }
}
```

- [ ] **Step 2: Typography, numerals, and layout rhythm**

```css
body { margin: 0; color: var(--ink); background: var(--bg); }
.app { max-width: 64rem; margin: 0 auto; padding: var(--s4); }

h1 { font-size: var(--t-2xl); line-height: 1.2; margin: 0 0 var(--s4); }
h2 { font-size: var(--t-xl); line-height: 1.25; margin: var(--s6) 0 var(--s3); }
h3 { font-size: var(--t-lg); margin: var(--s5) 0 var(--s2); }
h4 { font-size: var(--t-base); margin: var(--s4) 0 var(--s2); }
small, .blurb { font-size: var(--t-sm); color: var(--ink-soft); }

/* Numbers line up in every table that carries a dose, a pH, or a percentage. */
table { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; }
th, td { text-align: left; padding: var(--s2) var(--s3); border-bottom: 1px solid var(--line); }
thead th { font-size: var(--t-sm); color: var(--ink-soft); font-weight: 600; }
td:has(+ td), td { vertical-align: top; }
section { margin: var(--s5) 0; }
```

- [ ] **Step 3: Interactive states — the whole of dimension 10**

```css
button, .button {
  font: inherit; min-height: var(--touch); padding: var(--s2) var(--s4);
  border: 1px solid var(--line-strong); border-radius: var(--radius);
  background: var(--surface); color: var(--ink); cursor: pointer;
  transition: background 120ms ease, border-color 120ms ease;
}
button:hover:not(:disabled) { background: var(--muted); }
button:disabled { opacity: 0.55; cursor: not-allowed; }
button[type='submit'], .button--primary {
  background: var(--accent); border-color: var(--accent); color: #fff;
}
button[type='submit']:hover:not(:disabled) { filter: brightness(1.08); }

input, select, textarea {
  font: inherit; min-height: var(--touch); width: 100%; box-sizing: border-box;
  padding: var(--s2) var(--s3); border: 1px solid var(--line-strong);
  border-radius: var(--radius-sm); background: var(--surface); color: var(--ink);
}
input:disabled, select:disabled { background: var(--muted); cursor: not-allowed; }
label { display: block; margin: var(--s3) 0; font-size: var(--t-sm); color: var(--ink-soft); }
label input[type='checkbox'] { width: auto; min-height: auto; margin-right: var(--s2); }

/* Nothing had a focus style. Keyboard users could not see where they were. */
:focus-visible { outline: none; box-shadow: var(--focus); border-radius: var(--radius-sm); }

.skeleton {
  background: linear-gradient(90deg, var(--muted), var(--line), var(--muted));
  background-size: 200% 100%; animation: shimmer 1.2s linear infinite;
  border-radius: var(--radius-sm); height: 1rem; margin: var(--s2) 0;
}
@keyframes shimmer { to { background-position: -200% 0; } }
@media (prefers-reduced-motion: reduce) { .skeleton { animation: none; } }

.empty {
  border: 1px dashed var(--line-strong); border-radius: var(--radius);
  padding: var(--s5); text-align: center; color: var(--ink-soft);
}
```

- [ ] **Step 4: The verdict surfaces (decision #10)**

```css
.headline {
  display: flex; align-items: center; gap: var(--s3);
  font-size: var(--t-lg); font-weight: 700;
  padding: var(--s3) var(--s4); border-radius: var(--radius);
  border: 1px solid currentColor; box-shadow: var(--shadow);
}
.headline__glyph {
  font-size: var(--t-xl); line-height: 1; width: 1.5em; text-align: center;
}
.headline--red { color: var(--red); background: var(--red-bg); }
.headline--amber { color: var(--amber); background: var(--amber-bg); }
.headline--gray { color: var(--gray); background: var(--gray-bg); }
.headline--green { color: var(--green); background: var(--green-bg); }

.verdict { display: inline-flex; align-items: center; gap: var(--s1); font-weight: 600; }
.verdict--red { color: var(--red); } .verdict--amber { color: var(--amber); }
.verdict--cannot_assess { color: var(--gray); } .verdict--pass { color: var(--green); }

.finding-group { border: 1px solid var(--line); border-radius: var(--radius); margin: var(--s3) 0; }
.finding-group > summary {
  cursor: pointer; padding: var(--s3) var(--s4); font-weight: 600;
  display: flex; align-items: center; gap: var(--s2);
}
.count-badge {
  font-size: var(--t-xs); font-weight: 700; padding: 0 var(--s2);
  border-radius: 999px; background: var(--muted); color: var(--ink-soft);
}
```

- [ ] **Step 5: Mobile — the kitchen screens**

```css
@media (max-width: 48rem) {
  .app { padding: var(--s3); }
  header { flex-wrap: wrap; gap: var(--s2); }
  h1 { font-size: var(--t-xl); }

  /* A wide table becomes a scroller rather than a squeeze. */
  .table-scroll { overflow-x: auto; -webkit-overflow-scrolling: touch; }
  .table-scroll table { min-width: 34rem; }

  /* The editor's three-column grid stacks. */
  .editor-field { grid-template-columns: 1fr; gap: var(--s1); }

  /* Trial forms: one column, full-width controls, thumb-sized targets. */
  [data-testid='batch-form'] label,
  [data-testid='observation-form'] label,
  [data-testid='symptom-form'] label { margin: var(--s4) 0; }
  [data-testid='batch-form'] button,
  [data-testid='observation-form'] button,
  [data-testid='symptom-form'] button { width: 100%; }
}
```

- [ ] **Step 6: Keep the print stylesheet working, and extend it**

```css
@media print {
  header nav, button, .banner, .no-print { display: none !important; }
  .app { max-width: none; padding: 0; }
  a { text-decoration: none; color: inherit; }
  table { page-break-inside: auto; }
  tr { page-break-inside: avoid; }
  h2 { page-break-after: avoid; }
  .finding-group { break-inside: avoid; }
  .finding-group > summary { list-style: none; }
  details:not([open]) > *:not(summary) { display: revert; }  /* print collapsed groups too */
  footer { border-top: 1px solid #000; }
  :root { --shadow: none; }
}
```

The `details:not([open])` rule matters: Task 14 makes finding groups collapsible, and a group the founder collapsed on screen must still print — a report that silently omits the advisory findings because a disclosure triangle was shut is a report that lies.

- [ ] **Step 7: Verify nothing regressed**

Run: `cd web && npm run typecheck && npm run build && npm run e2e`
Expected: build clean, all 15 Playwright cases pass. CSS alone cannot break a selector, but this is the gate for every task in package D and it runs after each one.

- [ ] **Step 8: Commit**

```bash
git add web/src/styles.css
git commit -m "feat(web): design tokens, interactive states, dark mode, and a mobile pass"
```

---

## Task 13: Verdict meaning without colour (decision #10)

The one place package D changes what the UI *says*. Today RED and GREEN differ only in hue, and a past-deadline GI cell differs only by `opacity: 0.55` — a colour-blind founder reads the product's most important signal wrong.

**Files:**
- Modify: `web/src/components/VerdictBadge.tsx`, `web/src/components/GiStrip.tsx`

- [ ] **Step 1: Glyph and word on every verdict surface**

Replace `VerdictBadge.tsx` with:

```tsx
import type { Headline, Verdict } from '../api/types'

/** Spec §6.4 — the one-to-one headline mapping, and what each state means. */
const HEADLINE_TEXT: Record<Headline, string> = {
  RED: 'RED — blocker',
  GRAY: 'GRAY — gaps block a verdict',
  AMBER: 'AMBER — caution',
  GREEN: 'GREEN — clear on the rules evaluated',
}

/**
 * Meaning never rides on colour alone (plan decision #10): every verdict
 * carries a glyph and a word as well as a hue, so the headline reads the same
 * to someone who cannot distinguish red from green.
 */
const HEADLINE_GLYPH: Record<Headline, string> = {
  RED: '✕', GRAY: '?', AMBER: '!', GREEN: '✓',
}

const VERDICT_TEXT: Record<Verdict, string> = {
  red: 'blocker',
  cannot_assess: 'cannot assess',
  amber: 'caution',
  pass: 'clear',
}

const VERDICT_GLYPH: Record<Verdict, string> = {
  red: '✕', cannot_assess: '?', amber: '!', pass: '✓',
}

export function HeadlineBadge({ headline }: { headline: Headline }) {
  return (
    <p className={`headline headline--${headline.toLowerCase()}`} data-testid="headline">
      <span className="headline__glyph" aria-hidden="true">{HEADLINE_GLYPH[headline]}</span>
      <span>{HEADLINE_TEXT[headline]}</span>
    </p>
  )
}

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  return (
    <span className={`verdict verdict--${verdict}`}>
      <span aria-hidden="true">{VERDICT_GLYPH[verdict]}</span>
      {VERDICT_TEXT[verdict]}
    </span>
  )
}
```

`data-testid="headline"` stays on the same `<p>`, and the Playwright assertion `toContainText('RED')` still passes because the word is still in the element's text.

- [ ] **Step 2: Give the past-deadline cell words**

In `GiStrip.tsx`, replace the cell body so the state is written, not implied by opacity:

```tsx
                  {r.dormant
                    ? 'dormant'
                    : r.active
                      ? (r.before_deadline ? 'active' : 'active — past deadline')
                      : '—'}
```

The `data-testid={`cell-${lane.enzyme_id}-${r.region_id}`}` and both class names stay exactly as they are.

- [ ] **Step 3: Verify**

Run: `cd web && npm run typecheck && npm run build && npm run e2e`
Expected: 15 passed. `verdict.spec.ts` asserts on headline text containing `RED`; if it fails, the glyph replaced the word instead of joining it.

- [ ] **Step 4: Commit**

```bash
git add web/src/components/VerdictBadge.tsx web/src/components/GiStrip.tsx
git commit -m "fix(web): stop verdict meaning riding on colour alone"
```

---

## Task 14: Grouped findings that collapse, and a dose meter

Dimension 9 (density) and dimension 10 (polish). The verdict screen stacks seven sections flat; blockers and advisories deserve different weight.

**Files:**
- Modify: `web/src/components/FindingGroups.tsx`, `web/src/components/DoseCards.tsx`

- [ ] **Step 1: Collapsible groups with counts**

Replace `Group` in `FindingGroups.tsx`:

```tsx
function Group({ title, blurb, findings, open }: {
  title: string; blurb: string; findings: Finding[]; open: boolean
}) {
  if (findings.length === 0) return null
  return (
    <details
      className="finding-group"
      open={open}
      data-testid={`group-${title.toLowerCase().replace(/\s/g, '-')}`}
    >
      <summary>
        {title}
        <span className="count-badge">{findings.length}</span>
      </summary>
      <div className="finding-group__body">
        <p className="blurb">{blurb}</p>
        <ul>
          {findings.map((f, i) => (
            <li key={`${f.rule_id}-${f.enzyme_id ?? ''}-${f.food_id ?? ''}-${i}`}>
              <strong>{f.rule_id} — {f.rule_title}</strong> <VerdictBadge verdict={f.verdict} />
              <div>{f.message}</div>
            </li>
          ))}
        </ul>
      </div>
    </details>
  )
}
```

and set the defaults in `FindingGroups` so the two groups that stop a formulation are open and the two that do not are shut:

```tsx
      <Group title="Blockers" open blurb="These stop the formulation as specified."
             findings={blockers} />
      <Group title="Data gaps" open
             blurb="Missing values. Fill these in and re-run to get a verdict."
             findings={dataGaps} />
      <Group title="Cautions" open={false}
             blurb="Not blockers, but they change over time or with use."
             findings={cautions} />
      <Group title="Advisory" open={false}
             blurb="Notes that never change the headline — your call to make."
             findings={advisories} />
```

The test id moves from `<section>` to `<details>` — the same element the spec queries, so `getByTestId('group-blockers')` is unaffected. Two things make this safe rather than clever: Task 12's print rule forces collapsed groups open on paper, and Playwright's `toContainText` reads text inside a closed `<details>`.

- [ ] **Step 2: A meter on the dose card**

In `DoseCards.tsx`, add a visual ratio beside the existing numbers. Read the file first; it already renders `meets_threshold` and `ratio`. Add, inside the card and after the existing threshold line:

```tsx
      {card.ratio !== null && (
        <div className="meter" data-testid={`meter-${card.enzyme_id}`}>
          <div
            className={`meter__fill meter__fill--${card.meets_threshold ? 'over' : 'under'}`}
            style={{ width: `${Math.min(100, Math.round(card.ratio * 100))}%` }}
          />
          <span className="meter__label">
            {card.meets_threshold ? 'clears the evidence threshold' : 'below the evidence threshold'}
          </span>
        </div>
      )}
```

with the styles appended to `styles.css`:

```css
.meter { position: relative; height: 1.5rem; background: var(--muted);
         border-radius: var(--radius-sm); overflow: hidden; margin: var(--s2) 0; }
.meter__fill { position: absolute; inset: 0 auto 0 0; }
.meter__fill--over { background: var(--green-bg); border-right: 2px solid var(--green); }
.meter__fill--under { background: var(--amber-bg); border-right: 2px solid var(--amber); }
.meter__label { position: relative; font-size: var(--t-xs); line-height: 1.5rem;
                padding-left: var(--s2); color: var(--ink); }
```

The label is text, not a colour — decision #10 again. A `null` ratio renders nothing, because "cannot tell" is not a zero-width bar.

- [ ] **Step 3: Verify**

Run: `cd web && npm run typecheck && npm run build && npm run e2e`
Expected: 15 passed.

- [ ] **Step 4: Commit**

```bash
git add web/src/components/FindingGroups.tsx web/src/components/DoseCards.tsx web/src/styles.css
git commit -m "feat(web): collapsible finding groups with counts, and a dose threshold meter"
```

---

## Task 15: Frontend types and client for the report and the editor

**Files:**
- Modify: `web/src/api/types.ts`, `web/src/api/client.ts`

- [ ] **Step 1: Types**

Append to `types.ts`:

```ts
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
```

Add `allergens: string[]` and `last_edited: string | null` to the existing `Food` interface, and `last_edited: string | null` to `Enzyme`.

- [ ] **Step 2: Client calls**

In `client.ts`, extend the type import with `Report` and add above `reportUrl`:

```ts
  report: (evaluationId: string) => request<Report>(`/evaluations/${evaluationId}/report`),
  updateStructured: (table: 'enzymes' | 'foods', id: string, field: string, value: unknown) =>
    put<{ ok: boolean }>(`/${table}/${id}/structured/${field}`, { value }),
```

matching whatever route shape Task 8 actually implemented — read `api/routers/records.py` before writing this line rather than trusting the sketch.

- [ ] **Step 3: Typecheck and commit**

Run: `cd web && npm run typecheck`
Expected: clean.

```bash
git add web/src/api/types.ts web/src/api/client.ts
git commit -m "feat(web): types and client for the report payload and structured edits"
```

---

## Task 16: The printable report reaches parity

The audit's third gap: the button labelled "Print or save as PDF" prints less than the file it links to.

**Files:**
- Create: `web/src/components/FormulaTable.tsx`, `web/src/components/AllergenDeclaration.tsx`, `web/src/components/BatchRecords.tsx`
- Modify: `web/src/screens/Report.tsx`

- [ ] **Step 1: `FormulaTable.tsx`**

```tsx
import type { Formula, ProcessLine } from '../api/types'
import { TruthValue } from './TruthValue'

/** Percent of total batch weight, in order of addition (plan decisions #6, #7). */
export function FormulaTable({ formula, process }: {
  formula: Formula
  process: ProcessLine[]
}) {
  return (
    <section data-testid="formula">
      <h3>Formula</h3>
      <p className="blurb">
        Percent of total batch weight, in the order the ingredients go in. The
        percentages are the formula; the grams are one batch of it. Percent is
        calculated from the weights, so the two cannot disagree.
      </p>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>#</th><th>Ingredient</th><th>% of total</th><th>Grams</th>
              <th>pH</th><th>Water</th><th>Allergens</th>
            </tr>
          </thead>
          <tbody>
            {formula.lines.map((line) => (
              <tr key={line.food_id} data-testid={`formula-${line.food_id}`}>
                <td>{line.position}</td>
                <th scope="row">{line.food_name}</th>
                <td>{line.percent_of_total === null ? '—' : line.percent_of_total}</td>
                <td>{line.amount_g}</td>
                <td><TruthValue tracked={line.ph} /></td>
                <td><TruthValue tracked={line.water_content_pct} unit="%" /></td>
                <td>{line.allergens.length ? line.allergens.join(', ') : 'not recorded'}</td>
              </tr>
            ))}
            <tr data-testid="formula-total">
              <td /><th scope="row">Total</th>
              <td><strong>{formula.printed_percent_total ?? '—'}</strong></td>
              <td><strong>{formula.total_g}</strong></td>
              <td /><td /><td />
            </tr>
          </tbody>
        </table>
      </div>
      {formula.printed_percent_total !== null && formula.printed_percent_total !== 100 && (
        <p className="blurb">
          The printed percentages total {formula.printed_percent_total} rather than 100
          because each is rounded to two decimals. The grams are exact.
        </p>
      )}

      {process.length > 0 && (
        <>
          <h4>Process</h4>
          <div className="table-scroll">
            <table data-testid="process">
              <thead>
                <tr><th>Step</th><th>Operation</th><th>Heat</th><th>Enzyme added here</th></tr>
              </thead>
              <tbody>
                {process.map((step) => (
                  <tr key={step.order}>
                    <td>{step.order}</td>
                    <th scope="row">{step.label}</th>
                    <td>{step.is_heat ? 'yes' : 'no'}</td>
                    <td>{step.is_enzyme_addition_point ? 'yes' : 'no'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  )
}
```

- [ ] **Step 2: `AllergenDeclaration.tsx`**

```tsx
import type { AllergenDeclaration as Declaration } from '../api/types'

/** An empty declaration is a gap in the records, never a clearance (decision #2). */
export function AllergenDeclarationPanel({ declaration }: { declaration: Declaration }) {
  return (
    <section data-testid="allergens">
      <h3>Allergens</h3>
      {declaration.entries.length === 0 ? (
        <p>
          No allergen is recorded for any ingredient in this recipe. That is a gap in
          the ingredient records, not a statement that the product is free of allergens.
        </p>
      ) : (
        <table>
          <thead><tr><th>Allergen</th><th>From</th></tr></thead>
          <tbody>
            {declaration.entries.map((entry) => (
              <tr key={entry.allergen} data-testid={`allergen-${entry.allergen}`}>
                <th scope="row">{entry.text}</th>
                <td>{entry.from_food_names.join(', ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {declaration.unrecorded_food_names.length > 0 && (
        <p className="blurb" data-testid="allergens-unrecorded">
          Allergens are not recorded for: {declaration.unrecorded_food_names.join(', ')}.
          Fill these in before anyone relies on the declaration above.
        </p>
      )}
    </section>
  )
}
```

- [ ] **Step 3: `BatchRecords.tsx`**

```tsx
import type { BatchRecord } from '../api/types'

/** The batch record — the first document reviewed when a batch misses spec. */
export function BatchRecords({ batches }: { batches: BatchRecord[] }) {
  if (batches.length === 0) return null
  return (
    <section data-testid="batch-records">
      <h3>Batch records</h3>
      <p className="blurb">
        What was actually made, as it was made. Blank cells are parameters that were
        not recorded for that batch.
      </p>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Made</th><th>Size</th><th>pH</th><th>Minutes</th><th>Difficulty</th>
              <th>Enzyme after step</th><th>Enzyme source</th><th>Storage</th>
            </tr>
          </thead>
          <tbody>
            {batches.map((b) => (
              <tr key={b.made_at}>
                <th scope="row">{b.made_at.slice(0, 16).replace('T', ' ')}</th>
                <td>{b.batch_size_g === null ? '' : `${b.batch_size_g} g`}</td>
                <td>{b.measured_ph === null ? 'not measured' : `${b.measured_ph} (${b.ph_method})`}</td>
                <td>{b.make_minutes ?? ''}</td>
                <td>{b.difficulty_score === null ? '' : `${b.difficulty_score} of 5`}</td>
                <td>{b.enzyme_addition_step ?? ''}</td>
                <td>{b.enzyme_source_note || 'not recorded'}</td>
                <td>{b.storage_mode}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {batches.filter((b) => b.process_notes).map((b) => (
        <blockquote key={`${b.made_at}-notes`}>{b.process_notes}</blockquote>
      ))}
    </section>
  )
}
```

- [ ] **Step 4: Wire them into `Report.tsx`**

Add a second fetch beside the evaluation one:

```tsx
  const [report, setReport] = useState<ReportType | null>(null)

  useEffect(() => {
    if (!evaluationId) return
    api.report(evaluationId).then(setReport).catch((e) => setError(e.message))
  }, [evaluationId])
```

and render the new sections between the headline blurb and `FindingGroups`, so the document opens the way a specification sheet does — identity, formula, allergens, process — before it gets to findings:

```tsx
      {report && (
        <>
          <section data-testid="identity">
            <h3>Product and formula identity</h3>
            <table>
              <tbody>
                <tr><th scope="row">Product</th><td>{report.recipe_name}</td></tr>
                <tr><th scope="row">Recipe id</th><td>{report.recipe_id || 'not recorded'}</td></tr>
                <tr><th scope="row">Format</th><td>{report.format}</td></tr>
                <tr><th scope="row">Serving size</th>
                    <td>{report.serving_size_g === null ? 'not set' : `${report.serving_size_g} g`}</td></tr>
                <tr><th scope="row">Declared occasion</th>
                    <td>{report.dwell_profile ?? 'not declared'}</td></tr>
                <tr><th scope="row">Measured pH</th>
                    <td><TruthValue tracked={report.measured_ph} /></td></tr>
              </tbody>
            </table>
          </section>
          <FormulaTable formula={report.formula} process={report.process} />
          <AllergenDeclarationPanel declaration={report.allergens} />
        </>
      )}
```

and `<BatchRecords batches={report.batches} />` immediately after the observed section, matching the markdown's order.

- [ ] **Step 5: Verify parity by hand and by build**

Run: `cd web && npm run typecheck && npm run build && npm run e2e`
Expected: 15 passed.

- [ ] **Step 6: Commit**

```bash
git add web/src/components/FormulaTable.tsx web/src/components/AllergenDeclaration.tsx web/src/components/BatchRecords.tsx web/src/screens/Report.tsx
git commit -m "feat(web): print the formula, allergens, process and batch records"
```

---

## Task 17: The database editor shows unit, source, last-edited — and structured fields

Workflow D's sentence, finally true.

**Files:**
- Create: `web/src/components/StructuralEditor.tsx`
- Modify: `web/src/components/TruthValue.tsx`, `web/src/screens/Database.tsx`

- [ ] **Step 1: Make the source visible**

`TruthValue.tsx` puts the source in a `title` attribute, which is invisible on a phone and to a screen reader that does not announce it. Add an optional visible variant:

```tsx
export function TruthValue({ tracked, unit = '', showSource = false }: {
  tracked: Tracked
  unit?: string
  showSource?: boolean
}) {
```

keeping every existing prop and class name, and rendering below the value when asked:

```tsx
      {showSource && tracked.source && (
        <small className="truth__source">{tracked.source}</small>
      )}
```

with:

```css
.truth__source { display: block; color: var(--ink-soft); font-size: var(--t-xs); }
```

The editor passes `showSource`; every other caller keeps today's compact rendering.

- [ ] **Step 2: Unit and last-edited in the editor**

In `Database.tsx`'s field list, add the unit each field is measured in — read the existing `ENZYME_FIELDS` shape and extend each entry rather than parallel-arraying it:

```tsx
const ENZYME_FIELDS = [
  { field: 'ph_min', label: 'Active pH floor', unit: '' },
  { field: 'ph_shelf_stable_min', label: 'Shelf-stable pH floor', unit: '' },
  { field: 'temp_min_c', label: 'Minimum temperature', unit: '°C' },
  { field: 'temp_max_c', label: 'Maximum temperature', unit: '°C' },
  { field: 'dose_evidence_threshold', label: 'Evidence threshold', unit: 'per serving' },
  // …keep every field already listed, adding a unit where one exists
]
```

pass `unit` and `showSource` through `FieldRow` to `TruthValue`, and render the record's last edit under its heading:

```tsx
        <p className="blurb" data-testid={`last-edited-${record.id}`}>
          {record.last_edited
            ? `You last edited this on ${record.last_edited.slice(0, 10)}`
            : 'Shipped value — you have not edited this record'}
        </p>
```

- [ ] **Step 3: `StructuralEditor.tsx`**

```tsx
import { useState } from 'react'

const CLASSES = ['pectin_cellulose', 'structural_protein', 'starch'] as const
const TIERS = ['unconfirmed', 'gradual', 'rapid'] as const

const CLASS_TEXT: Record<string, string> = {
  pectin_cellulose: 'plant cell wall and pectin',
  structural_protein: 'structural protein',
  starch: 'starch',
}

const TIER_TEXT: Record<string, string> = {
  unconfirmed: 'not established — reports cannot assess',
  gradual: 'gradual — fine at the table, softening over hours',
  rapid: 'rapid — softening within the hour',
}

/**
 * Spec §15 item 4's answer, enterable. The tier IS the provenance (decision
 * #4): moving an entry off `unconfirmed` is what turns R15's cannot_assess into
 * a verdict, so this editor is the shortest path between a supplier's answer
 * and a formulation the tool can judge.
 */
export function StructuralEditor({ entries, onSave }: {
  entries: { structural_class: string; tier: string }[]
  onSave: (value: { structural_class: string; tier: string }[]) => Promise<void>
}) {
  const [draft, setDraft] = useState(entries)
  const [busy, setBusy] = useState(false)

  function setTier(structuralClass: string, tier: string) {
    setDraft((current) => {
      const without = current.filter((e) => e.structural_class !== structuralClass)
      return tier === '' ? without : [...without, { structural_class: structuralClass, tier }]
    })
  }

  return (
    <div data-testid="structural-editor">
      <p className="blurb">
        What this enzyme does to the structure of the food it lands on. Leave a class
        unset if it does not act on it at all; mark it <em>not established</em> if
        nobody has told you yet — the tool then declines to judge rather than guessing.
      </p>
      {CLASSES.map((structuralClass) => {
        const current = draft.find((e) => e.structural_class === structuralClass)
        return (
          <label key={structuralClass}>
            {CLASS_TEXT[structuralClass]}
            <select
              data-testid={`structural-${structuralClass}`}
              value={current?.tier ?? ''}
              onChange={(e) => setTier(structuralClass, e.target.value)}
            >
              <option value="">does not act on this</option>
              {TIERS.map((tier) => (
                <option key={tier} value={tier}>{TIER_TEXT[tier]}</option>
              ))}
            </select>
          </label>
        )
      })}
      <button
        type="button"
        data-testid="save-structural"
        disabled={busy}
        onClick={async () => {
          setBusy(true)
          try {
            await onSave(draft)
          } finally {
            setBusy(false)
          }
        }}
      >
        {busy ? 'Saving…' : 'Save what it degrades'}
      </button>
    </div>
  )
}
```

Wire it into `Database.tsx`'s enzyme editor, calling `api.updateStructured('enzymes', id, 'degrades_structural_json', value)` and refreshing the record afterwards the way the existing field save does.

- [ ] **Step 4: Verify**

Run: `cd web && npm run typecheck && npm run build && npm run e2e`
Expected: 15 passed — `variants.spec.ts` drives this screen and its `field-*` test ids are untouched.

Run: `.venv/bin/pytest tests/test_web_language.py -q`
Expected: pass — no prohibited word in the new copy. "not established" is deliberate; "unproven" would fail the lint and would also be the wrong word.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/StructuralEditor.tsx web/src/components/TruthValue.tsx web/src/screens/Database.tsx web/src/styles.css
git commit -m "feat(web): unit, visible source, last-edited, and the structural editor"
```

---

# Package E — prove it, document it, ship it

## Task 18: M5 contract tests

The invariants packages A–D introduced, asserted rather than reviewed.

**Files:**
- Create: `tests/api/test_contracts_m5.py`

- [ ] **Step 1: Write them**

```python
"""M5's boundaries, asserted rather than trusted to review."""

import pathlib
import re

import pytest

SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "foodbrew"
WEB = pathlib.Path(__file__).resolve().parents[2] / "web" / "src"


def _files(root, suffix):
    return sorted(p for p in root.rglob(f"*{suffix}") if "__pycache__" not in p.parts)


def test_no_rule_module_imports_the_allergen_vocabulary():
    """Plan decision #2 — an allergen never changes a verdict."""
    offenders = [
        p.name
        for p in _files(SRC / "engine" / "rules", ".py")
        if "allergens" in p.read_text(encoding="utf-8")
    ]
    assert not offenders, ", ".join(offenders)


def test_the_new_engine_modules_are_pure():
    for name in ("allergens.py", "formula.py", "structural.py"):
        text = (SRC / "engine" / name).read_text(encoding="utf-8")
        for forbidden in (
            "foodbrew.store", "foodbrew.api", "foodbrew.db", "sqlite3", "fastapi",
            "now_iso", "datetime.now", "time.time", "utcnow",
        ):
            assert forbidden not in text, f"{name}: {forbidden}"


def test_percent_is_never_stored():
    """Decision #6 — a stored percent could disagree with the grams beside it."""
    schema = (SRC / "db" / "schema.sql").read_text(encoding="utf-8")
    assert "percent" not in schema.lower()


def test_the_migration_list_only_adds_columns():
    """Decision #1 — this machinery is deliberately unable to drop or retype."""
    text = (SRC / "db" / "bootstrap.py").read_text(encoding="utf-8")
    assert "ADD COLUMN" in text
    for destructive in ("DROP COLUMN", "DROP TABLE", "RENAME COLUMN"):
        assert destructive not in text


def test_every_migrated_column_is_also_in_the_shipped_schema():
    """A fresh database and a migrated one must end up identical."""
    from foodbrew.db.bootstrap import MIGRATIONS

    schema = (SRC / "db" / "schema.sql").read_text(encoding="utf-8")
    for _table, column, _ddl in MIGRATIONS:
        assert column in schema, f"{column} is migrated but missing from schema.sql"


def test_no_web_file_hardcodes_a_colour_outside_the_stylesheet():
    """Decision #9 — one token block, no stray hex."""
    hex_colour = re.compile(r"#[0-9a-fA-F]{3,8}\b")
    offenders = []
    for path in _files(WEB, ".tsx") + _files(WEB, ".ts"):
        for match in hex_colour.findall(path.read_text(encoding="utf-8")):
            offenders.append(f"{path.name}: {match}")
    assert not offenders, ", ".join(offenders)


def test_the_stylesheet_declares_a_dark_scheme_and_a_reduced_motion_rule():
    css = (WEB / "styles.css").read_text(encoding="utf-8")
    assert "prefers-color-scheme: dark" in css
    assert "prefers-reduced-motion" in css
    assert ":focus-visible" in css


def test_every_verdict_state_carries_a_glyph_as_well_as_a_colour():
    """Decision #10 — meaning never rides on hue alone."""
    badge = (WEB / "components" / "VerdictBadge.tsx").read_text(encoding="utf-8")
    for glyph in ("✕", "?", "!", "✓"):
        assert glyph in badge


def test_the_report_screen_and_the_export_come_from_one_assembly():
    """Decision #8 — the router imports the assembler; it does not rebuild it."""
    router = (SRC / "api" / "routers" / "report.py").read_text(encoding="utf-8")
    assert "from foodbrew.api.routers.export import report_input" in router
    assert "render_markdown" not in router


def test_structured_fields_are_not_in_the_scalar_allowlists():
    """Decision #4 — a separate door, not a widened one."""
    from foodbrew.store.records import PLAIN_FIELDS, STRUCTURED_FIELDS, TRACKED_FIELDS

    for table, fields in STRUCTURED_FIELDS.items():
        for field in fields:
            assert field not in TRACKED_FIELDS.get(table, {})
            assert field not in PLAIN_FIELDS.get(table, {})


def test_the_allergen_vocabulary_is_closed_on_the_wire():
    from foodbrew.api import schemas
    from foodbrew.engine.allergens import Allergen

    # A client may send allergens only on a custom food, and the server parses
    # them through the enum — no schema accepts an arbitrary allergen string
    # that reaches the database unvalidated.
    assert "allergens" in schemas.CustomFoodIn.model_fields
    assert len(list(Allergen)) == 9
```

- [ ] **Step 2: Run the whole suite**

Run: `.venv/bin/pytest -q && .venv/bin/ruff check src tests`
Expected: everything green, ruff clean. `test_no_web_file_hardcodes_a_colour_outside_the_stylesheet` is the one most likely to fire — M4 left `#888` and `#ccc` in `styles.css` (fine, it is the stylesheet) but check no component picked one up.

- [ ] **Step 3: Commit**

```bash
git add tests/api/test_contracts_m5.py
git commit -m "test(api): M5 contract tests for migrations, purity, tokens and parity"
```

---

## Task 19: End-to-end — the report a scientist reads, and the answer to §15 item 4

**Files:**
- Create: `web/e2e/report.spec.ts`

- [ ] **Step 1: Write the spec**

```ts
import { expect, test } from '@playwright/test'

async function buildAndEvaluate(page: import('@playwright/test').Page) {
  await page.goto('/recipes/new')
  await page.getByTestId('recipe-name').fill('E2E formula vinaigrette')
  await page.getByTestId('food-picker').selectOption({ label: 'Olive oil' })
  await page.getByTestId('food-picker').selectOption({ label: 'White vinegar' })
  await page.getByTestId('food-picker').selectOption({ label: 'Yogurt' })
  await page.getByTestId('amount-olive_oil').fill('150')
  await page.getByTestId('amount-white_vinegar').fill('50')
  await page.getByTestId('amount-yogurt').fill('100')
  await page.getByTestId('save-recipe').click()
  await page.getByTestId('to-formulation').click()
  await page.getByTestId('trigger-milk').check()
  await page.getByTestId('run-evaluation').click()
  await expect(page.getByTestId('headline')).toBeVisible()
}

test('the report opens with identity, formula and allergens', async ({ page }) => {
  await buildAndEvaluate(page)
  await page.getByRole('link', { name: /printable report/i }).click()

  await expect(page.getByTestId('identity')).toContainText('E2E formula vinaigrette')

  const formula = page.getByTestId('formula')
  await expect(formula).toBeVisible()
  await expect(page.getByTestId('formula-olive_oil')).toContainText('50')   // 150 of 300 g
  await expect(page.getByTestId('formula-total')).toContainText('100')

  await expect(page.getByTestId('allergen-milk')).toContainText('Yogurt')
  await expect(page.getByTestId('allergens-unrecorded')).toContainText('Olive oil')
})

test('the formula is in order of addition, not the order foods were picked', async ({ page }) => {
  await buildAndEvaluate(page)
  await page.getByRole('link', { name: /printable report/i }).click()
  const positions = await page.getByTestId('formula').locator('tbody tr td:first-child').allInnerTexts()
  const numbered = positions.filter((t) => /^\d+$/.test(t.trim())).map(Number)
  expect(numbered).toEqual([...numbered].sort((a, b) => a - b))
})

test('the markdown export carries the same formula the screen shows', async ({ page, request }) => {
  await buildAndEvaluate(page)
  const evaluationId = page.url().split('/evaluations/')[1]
  const markdown = await (await request.get(`/api/v1/export/${evaluationId}.md`)).text()

  expect(markdown).toContain('## Product and formula identity')
  expect(markdown).toContain('## Formula')
  expect(markdown).toContain('| **Total** |')
  expect(markdown).toContain('## Allergens')
  expect(markdown).toContain('| Water activity | not measured |')
})

test('a supplier answer to the inulinase question can be recorded', async ({ page }) => {
  await page.goto('/database')
  await page.getByTestId('record-inulinase').click()
  await page.getByTestId('structural-pectin_cellulose').selectOption('gradual')
  await page.getByTestId('save-structural').click()
  await expect(page.getByTestId('structural-pectin_cellulose')).toHaveValue('gradual')

  await page.reload()
  await page.getByTestId('record-inulinase').click()
  await expect(page.getByTestId('structural-pectin_cellulose')).toHaveValue('gradual')
})

test('the editor says whether a record has been edited', async ({ page }) => {
  await page.goto('/database')
  await expect(page.getByTestId('last-edited-lactase_fungal_acid')).toContainText(
    /shipped value|last edited/i,
  )
})

test('the trial screen is usable at a phone width', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await buildAndEvaluate(page)
  await page.getByTestId('start-trial').click()
  await expect(page.getByTestId('protocol')).toBeVisible()

  const button = page.getByTestId('save-batch')
  const box = await button.boundingBox()
  expect(box!.height).toBeGreaterThanOrEqual(44)
})

test.afterEach(async ({ request }) => {
  await request.post('/api/v1/enzymes/inulinase/reset')
})
```

`record-inulinase` is a test id `Database.tsx` may not have; if it does not, add it in Task 17 to whatever element selects a record, rather than changing this spec to select on text.

- [ ] **Step 2: Run the whole browser suite**

Run: `cd web && npm run build && npm run e2e`
Expected: 21 passed — M3's nine, M4's six, and these six.

- [ ] **Step 3: Commit**

```bash
git add web/e2e/report.spec.ts
git commit -m "test(web): end-to-end formula, allergens, structural editing and phone layout"
```

---

## Task 20: Documentation and the full acceptance run

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document what M5 changed**

Append to `README.md`:

```markdown
## The report

The report is written in the shape a food scientist expects to receive:

- **Product and formula identity** — what this is, which recipe, which evaluation,
  which engine version.
- **Formula** — percent of total batch weight, in the order the ingredients go in,
  with the grams for one batch beside each line and a total row. The percentages
  are the formula; the grams are one instance of it. Percent is calculated from
  the weights, so the two can never disagree.
- **Allergens** — a declaration built from the ingredient records, naming the
  ingredients whose allergens are *not recorded* rather than implying they carry
  none.
- **Process** — the step sequence, which steps involve heat, and where the enzyme
  goes in.
- **Finished-product parameters** — pH, plus water activity, viscosity and
  nutrition listed as *not measured*. A spec sheet that omits them looks complete;
  one that names them tells the truth about what still needs a lab.
- **Batch records** — every batch you logged, with the parameters as you made it.
- Findings, doses, GI windows, the occasion envelope with observed columns, open
  questions, and provenance.

The printable page and the Markdown download are two renderings of one assembly,
so they cannot drift.

## The database screen

Every field shows its value, its unit, its truth label, its source, and when you
last edited it. A record you have never touched says "shipped value" rather than
inventing a date.

Two fields are structured rather than numeric — what an enzyme degrades, and what
a food's texture depends on. Both are edited from dropdowns over a closed
vocabulary. Moving an entry off *not established* is how a supplier's answer
turns one of R15's "cannot assess" verdicts into a real one.

## Checks

    make test    # pytest: engine, store, API, contracts, migrations
    make lint    # ruff
    make e2e     # Playwright, against the built app
    make report EVAL=<evaluation id>   # the markdown export, from a running server
    make trial TRIAL=<trial id>        # the trial as JSON, from a running server
```

- [ ] **Step 2: Run everything**

Run: `.venv/bin/ruff check src tests && .venv/bin/pytest -q && cd web && npm run typecheck && npm run build && npm run e2e`
Expected: ruff clean, every python test green, no type errors, a `web/dist` build, 21 Playwright cases passing.

- [ ] **Step 3: Verify the migration against a real pre-M5 database**

This is the one thing no unit test can fully simulate — an actual database written by M4.

```bash
git stash list >/dev/null   # nothing to stash; this is a note, not a command
cp -r data data.backup 2>/dev/null || true
```

If you have a `data/foodbrew.db` from the M4 hand-walk, back it up, then start the app (`make run`) and confirm three things: it boots without error, `/database` still shows your edits, and an evaluation you ran before M5 now shows the banner reading *"this evaluation predates a catalogue upgrade"* rather than claiming you changed a record. If you have no such database, create one from the M4 branch first — this check is the reason Task 1 exists.

- [ ] **Step 4: Walk the report by hand**

Start `make up` (or `make run`), and:

1. Build the vinaigrette with a dairy ingredient and evaluate it.
2. Open the printable report. Confirm it opens with identity, then formula, then allergens — and that the formula's percentages total 100.
3. Confirm the allergen section names milk from the dairy ingredient *and* lists the ingredients whose allergens are not recorded.
4. Print to PDF. Confirm the collapsed finding groups still print, the navigation does not, and the disclaimer is on the page.
5. Download the Markdown and diff it against what you just read. Every number should match.
6. Open `/database`, set inulinase's plant-cell-wall entry to *gradual*, and confirm the enzyme's R15 findings change on the next evaluation.
7. Open the trial screen on a phone-width window. Confirm the buttons are thumb-sized and nothing needs a horizontal scroll except the wide tables, which scroll on purpose.
8. Switch your OS to dark mode and reload. Confirm the verdict colours still read and nothing is white-on-white.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: document the report format, the database screen, and the checks"
```

---

## M5 exit criteria

- [x] `.venv/bin/pytest -q` passes with zero failures and zero skips.
- [x] `.venv/bin/ruff check src tests` is clean.
- [x] `cd web && npm run typecheck && npm run build` succeeds.
- [x] `cd web && npm run e2e` passes all 21 specs against the built app.
- [x] **Every M1–M4 test still passes.** M5 changes no rule and no verdict. The only pre-existing assertions that may move are three, all in `tests/engine/test_report.py` and all caused by Task 5: one section-name entry that names the old `## What was checked` heading, and the two in `test_the_process_sequence_marks_the_heat_step_and_the_addition_point` that name the old numbered-list process format (`"1. warm — involves heat"`) and become table-row assertions (`"| 1 | warm | yes | no |"`) when the process section becomes a table. Each is replaced by an equal-or-stricter assertion against real rendered output; none is deleted, and no other pre-existing assertion anywhere may change.
- [x] `tests/store/test_migrations.py` passes in full, including `test_a_pre_migration_database_is_upgraded_on_boot` and `test_the_upgrade_preserves_the_rows_it_finds` — the migration is the one change that can destroy the founder's data, and these are what say it does not.
- [x] `tests/api/test_report_endpoint.py::test_the_two_renderings_agree_on_every_shared_number` passes — decision #8's contract.
- [x] `tests/store/test_structured_records.py::test_inulinase_can_be_moved_off_unconfirmed` passes — §15 item 4 has an in-product answer.
- [x] `tests/test_spec_amendments.py` passes — the spec now describes what was built, and two of its claims are checked against the code rather than asserted in prose.
- [x] `tests/api/test_contracts_m5.py` passes in full: no rule reads an allergen, the new engine modules are pure and clockless, the migration list cannot drop a column, no component hardcodes a colour, every verdict carries a glyph, and the report has one assembler.
- [x] `tests/test_seed_prebiotic_scope.py` passes — R9's trigger set is the three §9.2 names.
- [x] A database created by the M4 branch boots under M5, keeps its edits, and reports its pre-M5 evaluations as *upgraded* rather than *edited*.
- [x] The founder completes the hand walk in Task 20 step 4, including the dark-mode and phone-width checks.

---

## Plan self-review

**Spec coverage.** §2.3's research track finally reaches every field it names → Tasks 7, 8. §3 Workflow D's "value, unit, status, source note, last-edited" → Tasks 9, 17. §5.1's food record → Tasks 1, 4. §5.4's "who may write confirmed" → Task 11's amendment plus Task 8's implementation. §6.3's observed scale, §6.5's cadence, §7's note-not-patch, §6.1's advisory exceptions and ladder direction → Task 11. §9.2's prebiotic scope → Task 10. §10 screen 8 → Tasks 5, 6, 16. §12's limitations stay visible: the unmeasured-parameters table states what the tool cannot measure rather than omitting the rows. §13's fixture policy and lint semantics → Task 11. §14 gains its M5 line; §15 gains two questions the build surfaced rather than answered.

**What this plan deliberately leaves undone.** Water activity, viscosity and nutrition are named as not measured, not modelled — there is no data source and inventing target ranges would be the exact failure the tool exists to prevent. `nuts_seeds` keeps no allergen because guessing one would put a wrong declaration in a document handed to a professional. Per-*field* last-edited is not built; per-record is what the screen needs. The deferred §11 features stay deferred.

**Placeholder scan.** No stubs. Every module named in the file structure is written out in the task that creates it; every test file is written rather than described. Four tasks (8, 9, 15, 17) tell the implementer to read an existing function before editing it and mirror its real shape rather than the sketch — that is deliberate, because those four touch code M3 and M4 wrote whose exact signatures matter more than my recollection of them, and each says which file is the authority.

**Type consistency.** `Formula`/`FormulaLine` are produced only by `engine/formula.build` and consumed by `report.py` and `routers/report.py`; nothing else constructs one. `Declaration` likewise from `engine/allergens.declare`. `ReportBatch` is built only in `routers/export._batch_records` and read only by `report.py` and `routers/report.py`. `Allergen` is the single vocabulary, used by the loader, the store, the report and the API; `Food.allergens` stays `tuple[str, ...]` at the dataclass boundary (values, not enum members) exactly as `Food.contains_substrate_ids` already does, so `snapshot`, `rowmap` and `schemas` need no enum imports. `StructuralError` is raised only by `engine/structural` and is converted to `ValidationRejection` at the store boundary — the engine never raises the store's exception type, and the API never sees the engine's.

**Known cross-task dependencies.** Task 1 precedes Task 4 (the column must exist). Task 2 precedes Tasks 4 and 5. Task 3 precedes Tasks 5 and 6. Task 4 precedes Tasks 5, 6 and 16. Task 5 precedes Task 6, which imports `ReportBatch` and `report_input`. Task 7 precedes Task 8. Tasks 12 and 13 precede 14, 16 and 17 (the tokens and the glyph set are what those style against). Task 15 precedes 16 and 17. Task 19 depends on every web task and on Task 4's seeded allergens. Task 18 should run last of the python tasks because it lints what the others wrote.

**Where this plan is most likely to be wrong.** Four places, in order:

1. **The migration.** It is the only change in M5 that can lose data, and the only one whose failure mode is silent — a database that boots and then behaves oddly. Task 1's tests build a real pre-migration database and check both the upgrade and the row count, and Task 20 step 3 repeats it against the founder's actual file. If any part of M5 deserves a second reviewer, it is this.
2. **The allergen seeding.** Sixteen assignments made from ingredient identity, not from a supplier document. `mayonnaise` → egg is safe; a founder who buys a vegan mayonnaise makes it wrong. The declaration is only ever as good as the catalogue behind it, which is why every unrecorded ingredient is named in the output rather than passed over.
3. **Collapsing finding groups by default.** Cautions and advisories start shut. That is a density judgement, and it is exactly the kind of judgement that hides something the founder needed to see. The print rule forces them open on paper specifically because a report is the artefact where hiding is unacceptable — but on screen, this is worth watching during the hand walk.
4. **The observed texture scale, again.** M4 invented it; Task 11 writes it into the spec, which makes it harder to change later. If the founder's hand walk suggests the mapping is wrong, change it *before* Task 11 lands rather than after — the spec amendment is the point of no return.







---

## M5 sign-off

All thirteen exit criteria met. Verified on `main` at `7f39a76` (merge of PR #5):

```
pytest              754 passed, 0 failed, 0 skipped
ruff check          All checks passed!
npm run typecheck   clean
npm run build       clean
npm run e2e         21 passed
```

The founder completed the hand walk on 2026-08-16, including the print, dark-mode
and phone-width checks, and reported no defects.

**Two caveats on how two of the criteria were discharged, so the record is not
stronger than the evidence.**

1. *"A database created by the M4 branch boots under M5."* Discharged against a
   database built through M4's own HTTP API at the M4 branch tip (`826bc68`), with
   a real founder edit and a real evaluation, then booted under M5's
   `ensure_database`: it boots clean, the edit survives, and the pre-M5 evaluation
   reports `field_added` only, which the UI renders as *predates a catalogue
   upgrade* rather than an edit banner. This is a faithful proxy, not the founder's
   own `data/foodbrew.db` from a live session, which was not available.
2. *The migration test* builds a pre-migration database from the current schema and
   drops the column, rather than from M1's literal schema text. Verified equivalent
   for this migration — `sqlite_master.sql` and `PRAGMA table_info` are
   byte-identical between the two constructions — but the technique assumes
   current-schema-minus-column equals old-schema, which stops holding once a second
   column lands. Tighten it when the next migration is written.

**Not an exit criterion, and still unverified:** `docker compose up --build`. The
Docker daemon was unavailable throughout M5, so the container boot path has never
been exercised. `make e2e` runs uvicorn directly, which proves the app but not the
image.

**Two open questions M5 surfaced rather than answered**, now §15 items 9 and 10:
which allergen the generic `nuts_seeds` entry carries, and whether the 1-5 observed
texture scale is calibrated the way the founder actually scores. The second matters
more after this milestone than before it, because Task 11 wrote the scale into the
spec, making it the reference rather than a plan decision.
