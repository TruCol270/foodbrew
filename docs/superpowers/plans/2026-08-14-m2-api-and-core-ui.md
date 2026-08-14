# M2 — API + Core UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put the M1 engine behind a FastAPI JSON API backed by SQLite, and give the founder the four screens she needs to reach a verdict unassisted: Home, Recipe builder, Formulation setup, and Verdict (with the GI strip, the four headline states, per-enzyme dose cards, and the occasion envelope panel).

**Architecture:** Three layers, strictly ordered. `engine/` stays pure and untouched except for two additive pure modules (`selection.py`, `views.py`) and one refactor-in-place (`flags.group_findings`). A new `store/` layer owns every SQLite read and write, hydrates an `EvalContext` from the database, and freezes an evaluation's inputs into a JSON snapshot. A new `api/` layer owns HTTP: Pydantic schemas, routers, error mapping, and static hosting of the React build. The React app talks only to `/api/v1`. Data flows one way — `api → store → engine` — and the purity test from M1 keeps the arrow from ever reversing.

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, Pydantic v2, stdlib `sqlite3`, pytest + httpx `TestClient`, React 19 + TypeScript + Vite, react-router-dom, Playwright (one smoke spec), Docker multi-stage.

**Spec:** `docs/superpowers/specs/2026-08-13-enzyme-rules-engine-design.md` — read §3 (workflows A), §4 (architecture, versioning), §5 (data model), §6.4 (aggregation), §6.7 (conventions), §10 (API & UI), §13 (testing), §14 (M2 line) before starting.

**Prior milestone:** `docs/superpowers/plans/2026-08-13-m1-engine-and-seed.md` — merged as `cc0ed27`. 226 tests green, ruff clean, 36 golden-fixture assertions passing against the real shipped seed.

---

## What M2 is not

Restated from the spec's §14 sequencing so no task drifts:

- **M3:** auto-variants (§7), R13's least-invasive format-recommendation search, side-by-side compare, the enzyme/food database editors and proposals inbox, the stale-evaluation banner, the print report.
- **M4:** everything under Workflow E — protocol generation, batch/observation/symptom capture, the predicted-vs-observed column.

M2 builds the read/write plumbing those milestones stand on, and nothing else. Two places where M2 deliberately reaches one step forward, because not doing so would force a rewrite later, are named in decisions #5 and #8 below.

---

## Spec deviations and decisions this plan resolves

Found by tracing §10's endpoint list and §4's reproducibility requirement against the M1 code as merged. Implement as described here; flag items 1, 2, and 6 to the spec owner at M2 review.

**1. `create_database()` as shipped would silently overwrite founder edits on every boot.** `db/bootstrap.py` populates `substrate`, `enzyme`, `food`, and `gi_region` with `INSERT OR REPLACE`. That is correct for a first boot and correct for M3's explicit "reset to baseline" action, but wrong as a startup hook: from M3 onward the founder's edits live in exactly those rows, and a container restart would revert them without a word. **This plan adds `ensure_database(path)`, which calls `create_database()` only when the database file does not yet exist, and otherwise opens the existing file and verifies its schema.** The API startup path calls `ensure_database`. `create_database` keeps its current destructive-refresh semantics and becomes the implementation of M3's reset button. Flag to the spec owner: §4's "loaded on first boot" is doing load-bearing work that the M1 code did not yet enforce.

**2. The API must hydrate reference data from SQLite, never from `load_seed()`.** `seedload/loader.py` reads `seed/*.json`; from M3 the founder's edits exist only in the database. An API that hydrated from JSON would ignore every edit she makes and would disagree with the database editor screen. **This plan adds `store/rowmap.py` (rows → the same frozen engine dataclasses) and asserts equivalence with a round-trip test: `load_seed()` → `create_database()` → `load_catalog(conn)` must produce catalogs that compare equal, record for record.** That test is the only thing preventing two readers of the same data from drifting, so it is written before the reader it tests.

**3. Recipes with zero ingredients are rejected at validation — and nothing in M1 enforces it.** Spec §6.7 requires "add at least one ingredient", but the engine only owns the *other* degenerate case (R14's zero-enzymes-and-zero-trigger-foods `ValidationRejection`). Because §6.7 places this one "at validation" rather than in a rule, **this plan enforces it at the API boundary in `POST/PUT /recipes` and again at evaluate time**, raising the same `ValidationRejection` type so both degenerate inputs map to one HTTP status and one error shape. `ValidationRejection` is re-exported from `foodbrew.engine` so the API never imports a rule module directly.

**4. The input snapshot stores the referenced closure, not the whole catalogue.** §4 requires "a snapshot of all inputs" such that re-running reproduces byte-identical results. Snapshotting all 12 enzymes and 53 foods on every evaluation would be ~40× larger than needed and would make a diff of two evaluations unreadable. **The snapshot stores exactly the records the formulation references** — selected enzymes, foods appearing as recipe ingredients / trigger foods / application foods, the substrates those enzymes and foods name, and all six GI regions — which is a closure over everything any rule can read, given that every rule reaches records only through ids on the formulation. Task 5's test proves the closure is sufficient by re-running from the snapshot and asserting byte-identical output, and Task 20 proves it is *isolating* by mutating the source rows and re-running.

**5. `GET /evaluations/{id}` never re-runs the engine.** §4: later edits never mutate a stored evaluation. The read path deserializes the stored findings, envelope, and overall flag; the derived views (dose cards, GI strip) are built from the *snapshot's* context, not from current rows, so an evaluation looks exactly as it looked when it was run. Producing a fresh verdict is always `POST /formulations/{id}/evaluate`, which writes a new `evaluation` row — evaluations are append-only. This is also why the derived views are pure functions of an `EvalContext` (`engine/views.py`) rather than serializer-layer code.

**6. Two headline-capable derivations that §10 lists on the verdict screen are not implemented in M1, and only one of them belongs to M2.** The per-enzyme dose card and the GI-tract strip are pure derivations over records the engine already reads, so they are built here as `engine/views.py`. The format recommendation is a *search* — re-running R1–R7, R11, R12, R14, R15 under each candidate format — which is the same machinery §7's auto-variants need, so it stays in M3 exactly as the M1 plan's self-review stated. The M2 verdict screen therefore shows the headline, the grouped findings, the dose cards, the GI strip, and the envelope panel, and shows no format recommendation.

**7. The wire format for any `Tracked` field is an object, never a bare number.** Success criterion §1.3.2 ("every number traces to a database record with a status label") is enforceable only if the label travels with the value. Every tracked field serializes as `{"value": …, "status": …, "source": …}`, and Task 19 asserts it schema-wide, so no future endpoint can flatten one to a float without a test failing.

**8. `hydrate_context` queries `trial_batch` for the latest measured pH now, even though M4 writes the first row.** §6.7's resolution order is formulation → latest trial batch → wet-ingredient fallback, and `EvalContext.latest_trial_ph` already exists from M1. Implementing the query now costs four lines, returns `None` against an empty table, and means M4 adds a writer rather than reworking hydration. Task 8 tests it against a hand-inserted trial batch row.

**9. Custom foods are `user_provided` by construction; the client cannot choose a status.** §10 screen 2 requires it and §5.4 makes `confirmed` mean "verified against a named source", which a form cannot be. The create-food schema therefore accepts bare values, and the server wraps each in `Tracked(value, USER_PROVIDED, "entered by founder")`. There is no code path by which an HTTP client sets a truth label.

**10. Sync endpoints only; one SQLite connection per request.** `sqlite3` connections are thread-confined, and FastAPI runs `def` endpoints in a worker thread. Every endpoint in M2 is a plain `def` and takes its connection from a dependency that opens and closes it inside that same thread. No `async def`, no connection pool, no global connection. `PRAGMA foreign_keys = ON` is set per connection — the pragma in `schema.sql` applies only to the connection that ran the script, which is a real M1 footgun this plan closes.

**11. No CORS middleware.** The Vite dev server proxies `/api` to `127.0.0.1:8000`, and in production FastAPI serves the built assets from its own origin. Adding CORS would open a browser-facing surface that nothing needs.

---

## File structure

```
foodbrew/
├── pyproject.toml                    # + fastapi, uvicorn, pydantic; + httpx (dev)
├── Dockerfile                        # multi-stage: node build → python runtime, uvicorn CMD
├── docker-compose.yml                # + ports 8000:8000
├── Makefile                          # + run, web, web-build, e2e
├── src/foodbrew/
│   ├── engine/                       # M1 — untouched except:
│   │   ├── flags.py                  #   + group_findings() extracted from aggregate()
│   │   ├── selection.py              #   NEW: propose_enzymes() (pure)
│   │   └── views.py                  #   NEW: gi_strip, dose_cards, substrate_summary (pure)
│   ├── db/bootstrap.py               #   + ensure_database()
│   ├── store/                        # NEW — every SQLite read and write
│   │   ├── __init__.py
│   │   ├── clock.py                  # now_iso()
│   │   ├── ids.py                    # new_id()
│   │   ├── connection.py             # connect(): row_factory + foreign_keys pragma
│   │   ├── rowmap.py                 # rows → engine dataclasses
│   │   ├── reference.py              # load_catalog(conn) -> Catalog
│   │   ├── snapshot.py               # EvalContext ⇄ deterministic JSON
│   │   ├── foods.py                  # custom-food create/read
│   │   ├── recipes.py                # recipe CRUD + substrate summary source
│   │   ├── formulations.py           # formulation CRUD + hydrate_context()
│   │   └── evaluations.py            # append-only evaluation persistence
│   └── api/                          # NEW — HTTP only
│       ├── __init__.py
│       ├── settings.py               # FOODBREW_DB_PATH, FOODBREW_WEB_DIST
│       ├── deps.py                   # get_conn()
│       ├── schemas.py                # Pydantic v2 wire models
│       ├── app.py                    # factory, error handlers, SPA mount
│       └── routers/
│           ├── catalog.py            # foods, enzymes, substrates, gi-model
│           ├── recipes.py
│           ├── formulations.py
│           └── evaluations.py
├── web/                              # NEW — React + TS + Vite
│   ├── package.json / tsconfig.json / vite.config.ts / index.html
│   ├── playwright.config.ts
│   ├── e2e/verdict.spec.ts
│   └── src/
│       ├── main.tsx, App.tsx, styles.css
│       ├── api/{client.ts,types.ts}
│       ├── components/{TruthValue,VerdictBadge,FindingGroups,GiStrip,EnvelopePanel,DoseCards}.tsx
│       └── screens/{Home,RecipeBuilder,FormulationSetup,Verdict}.tsx
└── tests/
    ├── store/test_{rowmap,snapshot,recipes,formulations,evaluations}.py
    ├── engine/test_{selection,views}.py
    ├── api/conftest.py               # temp-DB TestClient
    ├── api/test_{catalog,recipes,formulations,evaluations,contracts}.py
    └── test_web_language.py          # prohibited words in frontend copy
```

**Boundary rules to enforce in review** (M1's `tests/engine/test_purity.py` already covers the first; Task 26 adds the second):
- nothing under `engine/` imports `sqlite3`, `json`, `pathlib`, `foodbrew.db`, `foodbrew.store`, `foodbrew.api`, or `fastapi`;
- nothing under `store/` imports `fastapi` or `foodbrew.api`.

---

## Task 1: Add API dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add runtime and dev dependencies**

Replace the `dependencies` and `optional-dependencies` blocks:

```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.32",
    "pydantic>=2.9",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "hypothesis>=6.100", "ruff>=0.5", "httpx>=0.27"]
```

The engine gains no dependency: `engine/` still imports nothing outside the stdlib, and `tests/engine/test_purity.py` still proves it.

- [ ] **Step 2: Install and verify**

Run: `.venv/bin/pip install -e '.[dev]' -q && .venv/bin/python -c "import fastapi, httpx; print(fastapi.__version__)"`
Expected: a version prints, no errors.

- [ ] **Step 3: Confirm M1 is still green**

Run: `.venv/bin/pytest -q && .venv/bin/ruff check src tests`
Expected: all M1 tests pass, ruff clean.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add fastapi, uvicorn, pydantic, and httpx"
```

---

## Task 2: Connection, ids, and clock

Three tiny modules the whole store layer depends on. Isolated here so that every later test can control time and identity.

**Files:**
- Create: `src/foodbrew/store/__init__.py`
- Create: `src/foodbrew/store/connection.py`
- Create: `src/foodbrew/store/ids.py`
- Create: `src/foodbrew/store/clock.py`
- Test: `tests/store/__init__.py`, `tests/store/test_connection.py`

- [ ] **Step 1: Write the failing test**

Create `tests/store/__init__.py` (empty) and `tests/store/test_connection.py`:

```python
import sqlite3

import pytest

from foodbrew.db import create_database
from foodbrew.store.clock import now_iso
from foodbrew.store.connection import connect
from foodbrew.store.ids import new_id


def test_foreign_keys_are_enforced_on_every_connection(tmp_path):
    # schema.sql's own PRAGMA applies only to the connection that ran it, so a
    # fresh connection must set it again or every FK in the schema is decorative.
    db = create_database(tmp_path / "foodbrew.db")
    with connect(db) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO recipe_ingredient (recipe_id, food_id, amount_g)"
                " VALUES ('nope', 'also-nope', 1.0)"
            )


def test_rows_are_addressable_by_column_name(tmp_path):
    db = create_database(tmp_path / "foodbrew.db")
    with connect(db) as conn:
        row = conn.execute("SELECT id, name FROM enzyme LIMIT 1").fetchone()
    assert row["id"]
    assert row["name"]


def test_connection_closes_on_exit(tmp_path):
    db = create_database(tmp_path / "foodbrew.db")
    with connect(db) as conn:
        pass
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")


def test_new_id_is_unique_and_urlsafe():
    ids = {new_id() for _ in range(500)}
    assert len(ids) == 500
    assert all(i.isalnum() for i in ids)


def test_now_iso_is_utc_and_sortable():
    a, b = now_iso(), now_iso()
    assert a.endswith("+00:00")
    assert a <= b
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/store/test_connection.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'foodbrew.store'`

- [ ] **Step 3: Write the implementation**

`src/foodbrew/store/__init__.py`:

```python
"""SQLite persistence. The only layer that touches the database."""
```

`src/foodbrew/store/connection.py`:

```python
"""Connection handling. One connection per request, thread-confined."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def connect(path: Path | str) -> Iterator[sqlite3.Connection]:
    """Open a connection with row access by name and foreign keys enforced.

    schema.sql's `PRAGMA foreign_keys = ON` binds to the connection that ran
    the script and to nothing else, so it is re-issued here. Without it every
    REFERENCES clause in the schema is documentation rather than a constraint.
    """
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()
```

`src/foodbrew/store/ids.py`:

```python
"""Identifier generation. Separated so tests can monkeypatch one symbol."""

from __future__ import annotations

import uuid


def new_id() -> str:
    """A URL-safe opaque id. Hex, so it needs no escaping in a path segment."""
    return uuid.uuid4().hex
```

`src/foodbrew/store/clock.py`:

```python
"""Time. Separated so tests can monkeypatch one symbol."""

from __future__ import annotations

from datetime import UTC, datetime


def now_iso() -> str:
    """UTC, ISO-8601, offset-suffixed — lexicographically sortable as stored."""
    return datetime.now(UTC).isoformat()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/store/test_connection.py -q`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/store tests/store
git commit -m "feat(store): add connection, id, and clock primitives"
```

---

## Task 3: Row mapping — database rows into engine dataclasses

The riskiest module in M2: a second reader of the same data as `seedload/loader.py`. The test is written first and is an equality assertion against the loader, so drift fails loudly.

**Files:**
- Create: `src/foodbrew/store/rowmap.py`
- Create: `src/foodbrew/store/reference.py`
- Test: `tests/store/test_rowmap.py`

- [ ] **Step 1: Write the failing test**

`tests/store/test_rowmap.py`:

```python
from foodbrew.db import create_database
from foodbrew.seedload.loader import load_seed
from foodbrew.store.connection import connect
from foodbrew.store.reference import load_catalog


def test_catalog_from_db_equals_catalog_from_seed(tmp_path):
    """The two readers of the same data must not drift (plan decision #2)."""
    seed = load_seed()
    db = create_database(tmp_path / "foodbrew.db", seed)
    with connect(db) as conn:
        catalog = load_catalog(conn)

    assert catalog.enzymes == dict(seed.enzymes)
    assert catalog.foods == dict(seed.foods)
    assert catalog.substrates == dict(seed.substrates)
    assert catalog.gi_regions == seed.gi_regions


def test_tracked_status_and_source_survive_the_round_trip(tmp_path):
    seed = load_seed()
    db = create_database(tmp_path / "foodbrew.db", seed)
    with connect(db) as conn:
        catalog = load_catalog(conn)

    lactase = catalog.enzymes["lactase_fungal_acid"]
    assert lactase.ph_min.value == 2.5
    assert lactase.ph_min.status == "confirmed"
    assert "KB Table B" in lactase.ph_min.source
    # The field R1's fallback margin exists for stays unusable, as seeded.
    assert lactase.ph_shelf_stable_min.usable is False


def test_boolean_tracked_fields_come_back_as_booleans(tmp_path):
    seed = load_seed()
    db = create_database(tmp_path / "foodbrew.db", seed)
    with connect(db) as conn:
        catalog = load_catalog(conn)

    gras = [e.is_gras.value for e in catalog.enzymes.values() if e.is_gras.usable]
    assert gras, "at least one enzyme seeds a confirmed GRAS status"
    assert all(isinstance(v, bool) for v in gras)


def test_gi_regions_come_back_in_order(tmp_path):
    db = create_database(tmp_path / "foodbrew.db")
    with connect(db) as conn:
        regions = load_catalog(conn).gi_regions
    assert [r.order for r in regions] == sorted(r.order for r in regions)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/store/test_rowmap.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'foodbrew.store.reference'`

- [ ] **Step 3: Write `rowmap.py`**

```python
"""Rows → engine dataclasses. The mirror of seedload/loader.py's JSON path.

The Tracked triple (<field>, <field>_status, <field>_source) written by
db/bootstrap.py is read back here. tests/store/test_rowmap.py asserts the two
readers agree record-for-record; that test is the only thing keeping them from
drifting, so change one and run it.
"""

from __future__ import annotations

import json
import sqlite3

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

#: Enzyme columns stored as a Tracked triple.
ENZYME_TRACKED = (
    "ph_min", "ph_max", "ph_opt_low", "ph_opt_high", "ph_shelf_stable_min",
    "temp_min_c", "temp_max_c", "temp_opt_c",
    "dose_min", "dose_max", "dose_evidence_threshold", "is_gras",
)
#: Food columns stored as a Tracked triple.
FOOD_TRACKED = ("ph", "water_content_pct", "typical_load_value")

#: Tracked columns whose SQLite INTEGER is a boolean, not a number.
_BOOLEAN_TRACKED = frozenset({"is_gras"})


def tracked(row: sqlite3.Row, prefix: str) -> Tracked:
    value = row[prefix]
    if value is not None and prefix in _BOOLEAN_TRACKED:
        value = bool(value)
    return Tracked(
        value=value,
        status=TruthLabel(row[f"{prefix}_status"]),
        source=row[f"{prefix}_source"],
    )


def substrate_from_row(row: sqlite3.Row) -> Substrate:
    return Substrate(
        id=row["id"],
        name=row["name"],
        native_human_enzyme=bool(row["native_human_enzyme"]),
        is_prebiotic=bool(row["is_prebiotic"]),
        no_commercial_enzyme=bool(row["no_commercial_enzyme"]),
        notes=row["notes"],
    )


def gi_region_from_row(row: sqlite3.Row) -> GIRegion:
    return GIRegion(
        id=row["id"],
        name=row["name"],
        ph_low=float(row["ph_low"]),
        ph_high=float(row["ph_high"]),
        order=int(row["order"]),
        dormant=bool(row["dormant"]),
        transit_note=row["transit_note"],
    )


def enzyme_from_row(row: sqlite3.Row) -> Enzyme:
    structural = tuple(
        StructuralEntry(
            structural_class=StructuralClass(entry["structural_class"]),
            tier=SeverityTier(entry["tier"]),
        )
        for entry in json.loads(row["degrades_structural_json"])
    )
    return Enzyme(
        id=row["id"],
        name=row["name"],
        aliases=tuple(json.loads(row["aliases_json"])),
        substrate_id=row["substrate_id"],
        source_type=row["source_type"],
        priority=row["priority"],
        deadline=Deadline(row["deadline"]),
        site_of_action=row["site_of_action"],
        dose_unit=row["dose_unit"],
        dose_benchmark_note=row["dose_benchmark_note"],
        is_protease=bool(row["is_protease"]),
        is_natural_source=bool(row["is_natural_source"]),
        food_grade_note=row["food_grade_note"],
        heat_labile_note=row["heat_labile_note"],
        degrades_structural=structural,
        cost_tier=row["cost_tier"],
        supplier_note=row["supplier_note"],
        notes=row["notes"],
        **{name: tracked(row, name) for name in ENZYME_TRACKED},
    )


def food_from_row(row: sqlite3.Row) -> Food:
    return Food(
        id=row["id"],
        name=row["name"],
        category=row["category"],
        is_recipe_ingredient=bool(row["is_recipe_ingredient"]),
        is_trigger_food=bool(row["is_trigger_food"]),
        is_application_food=bool(row["is_application_food"]),
        contains_substrate_ids=tuple(json.loads(row["contains_substrate_ids_json"])),
        typical_load_unit=row["typical_load_unit"],
        contains_protease=bool(row["contains_protease"]),
        is_heat_processed=bool(row["is_heat_processed"]),
        structural=tuple(StructuralClass(s) for s in json.loads(row["structural_json"])),
        notes=row["notes"],
        **{name: tracked(row, name) for name in FOOD_TRACKED},
    )
```

- [ ] **Step 4: Write `reference.py`**

```python
"""Read the reference catalogue out of SQLite."""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass

from foodbrew.engine.types import Enzyme, Food, GIRegion, Substrate
from foodbrew.store.rowmap import (
    enzyme_from_row,
    food_from_row,
    gi_region_from_row,
    substrate_from_row,
)


@dataclass(frozen=True, slots=True)
class Catalog:
    """Shape-compatible with seedload.Seed, read from the database instead."""

    enzymes: Mapping[str, Enzyme]
    foods: Mapping[str, Food]
    substrates: Mapping[str, Substrate]
    gi_regions: tuple[GIRegion, ...]


def load_catalog(conn: sqlite3.Connection) -> Catalog:
    substrates = {
        r["id"]: substrate_from_row(r) for r in conn.execute("SELECT * FROM substrate")
    }
    enzymes = {r["id"]: enzyme_from_row(r) for r in conn.execute("SELECT * FROM enzyme")}
    foods = {r["id"]: food_from_row(r) for r in conn.execute("SELECT * FROM food")}
    regions = tuple(
        gi_region_from_row(r)
        for r in conn.execute('SELECT * FROM gi_region ORDER BY "order"')
    )
    return Catalog(
        enzymes=enzymes, foods=foods, substrates=substrates, gi_regions=regions
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/store/test_rowmap.py -q`
Expected: 4 passed. If the equality assertion fails, the mismatch is the bug — fix `rowmap.py` or `bootstrap.py`, never the assertion.

- [ ] **Step 6: Commit**

```bash
git add src/foodbrew/store/rowmap.py src/foodbrew/store/reference.py tests/store/test_rowmap.py
git commit -m "feat(store): read the reference catalogue from SQLite"
```

---

## Task 4: `ensure_database` — boot without clobbering edits

**Files:**
- Modify: `src/foodbrew/db/bootstrap.py`
- Modify: `src/foodbrew/db/__init__.py`
- Test: `tests/test_db_bootstrap.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_db_bootstrap.py`:

```python
from foodbrew.db import ensure_database
from foodbrew.store.connection import connect


def test_ensure_database_creates_a_missing_database(tmp_path):
    path = tmp_path / "foodbrew.db"
    ensure_database(path)
    with connect(path) as conn:
        count = conn.execute("SELECT COUNT(*) AS n FROM enzyme").fetchone()["n"]
    assert count == 12


def test_ensure_database_preserves_edits_to_an_existing_database(tmp_path):
    """Plan decision #1: a restart must not revert the founder's edits."""
    path = tmp_path / "foodbrew.db"
    ensure_database(path)
    with connect(path) as conn:
        conn.execute(
            "UPDATE enzyme SET temp_min_c = 20.0, temp_min_c_status = 'user_provided'"
            " WHERE id = 'lactase_fungal_acid'"
        )
        conn.commit()

    ensure_database(path)  # a second boot

    with connect(path) as conn:
        row = conn.execute(
            "SELECT temp_min_c, temp_min_c_status FROM enzyme WHERE id = 'lactase_fungal_acid'"
        ).fetchone()
    assert row["temp_min_c"] == 20.0
    assert row["temp_min_c_status"] == "user_provided"


def test_create_database_still_refreshes_reference_data(tmp_path):
    """The destructive path is kept deliberately — it is M3's reset-to-baseline."""
    path = tmp_path / "foodbrew.db"
    create_database(path)
    with connect(path) as conn:
        conn.execute("UPDATE enzyme SET temp_min_c = 20.0 WHERE id = 'lactase_fungal_acid'")
        conn.commit()

    create_database(path)

    with connect(path) as conn:
        row = conn.execute(
            "SELECT temp_min_c FROM enzyme WHERE id = 'lactase_fungal_acid'"
        ).fetchone()
    assert row["temp_min_c"] is None


def test_ensure_database_raises_on_a_file_missing_tables(tmp_path):
    path = tmp_path / "not-a-foodbrew.db"
    sqlite3.connect(path).close()
    with pytest.raises(ValueError, match="schema"):
        ensure_database(path)
```

Add `import sqlite3` and `import pytest` to that file's imports if absent.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_db_bootstrap.py -q`
Expected: FAIL — `ImportError: cannot import name 'ensure_database'`

- [ ] **Step 3: Write the implementation**

Append to `src/foodbrew/db/bootstrap.py`:

```python
def ensure_database(path: Path | str, seed: Seed | None = None) -> Path:
    """Create the database on first boot; otherwise leave its contents alone.

    `create_database` refreshes reference rows with INSERT OR REPLACE, which is
    right for a first boot and right for M3's reset-to-baseline button, and
    wrong for a restart: from M3 the founder's edits live in those same rows.
    """
    path = Path(path)
    if not path.exists():
        return create_database(path, seed)

    conn = sqlite3.connect(path)
    try:
        present = {
            r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        conn.close()
    missing = EXPECTED_TABLES - present
    if missing:
        raise ValueError(
            f"{path} exists but its schema is missing: {', '.join(sorted(missing))}"
        )
    return path
```

Update `src/foodbrew/db/__init__.py`:

```python
from foodbrew.db.bootstrap import create_database, ensure_database

__all__ = ["create_database", "ensure_database"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_db_bootstrap.py -q`
Expected: all pass, including M1's existing bootstrap tests.

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/db tests/test_db_bootstrap.py
git commit -m "feat(db): add non-destructive ensure_database for API startup"
```

---

## Task 5: Input snapshots — freeze the referenced closure

**Files:**
- Create: `src/foodbrew/store/snapshot.py`
- Test: `tests/store/test_snapshot.py`

- [ ] **Step 1: Write the failing test**

`tests/store/test_snapshot.py`:

```python
import dataclasses
import json

from foodbrew.engine import evaluate
from foodbrew.engine.types import (
    Format,
    Formulation,
    Phase,
    ProcessStep,
    RecipeIngredient,
    SelectedEnzyme,
    Tracked,
    TruthLabel,
)
from foodbrew.engine.types import EvalContext
from foodbrew.seedload.loader import load_seed
from foodbrew.store.snapshot import context_from_snapshot, snapshot_from_context


def _ctx(seed):
    form = Formulation(
        id="f1",
        format=Format.PREMIXED_WET,
        recipe=(RecipeIngredient("olive_oil", 100.0), RecipeIngredient("white_vinegar", 50.0)),
        enzymes=(SelectedEnzyme("lactase_fungal_acid", 9000.0, Phase.WET),),
        target_trigger_food_ids=("milk",),
        application_food_ids=("romaine",),
        measured_ph=Tracked(3.0, TruthLabel.USER_PROVIDED, "bench reading"),
        process_steps=(ProcessStep(1, "whisk", False),),
        enzyme_addition_index=1,
    )
    return EvalContext(
        formulation=form,
        enzymes=seed.enzymes,
        foods=seed.foods,
        substrates=seed.substrates,
        gi_regions=seed.gi_regions,
    )


def test_snapshot_round_trips_to_an_equivalent_context():
    seed = load_seed()
    ctx = _ctx(seed)
    restored = context_from_snapshot(snapshot_from_context(ctx))
    assert restored.formulation == ctx.formulation


def test_rerunning_a_snapshot_reproduces_the_evaluation_exactly():
    """Spec §4: same snapshot + same engine version → byte-identical result."""
    seed = load_seed()
    ctx = _ctx(seed)
    first = evaluate(ctx)
    second = evaluate(context_from_snapshot(snapshot_from_context(ctx)))
    assert second == first


def test_snapshot_holds_only_the_referenced_closure():
    """Plan decision #4 — the whole catalogue is not copied per evaluation."""
    seed = load_seed()
    payload = json.loads(snapshot_from_context(_ctx(seed)))
    assert set(payload["enzymes"]) == {"lactase_fungal_acid"}
    assert set(payload["foods"]) == {"olive_oil", "white_vinegar", "milk", "romaine"}
    assert len(payload["gi_regions"]) == 6
    # Substrates reachable from those enzymes and foods, and no others.
    assert "lactose" in payload["substrates"]
    assert len(payload["substrates"]) < len(seed.substrates)


def test_snapshot_is_byte_stable():
    seed = load_seed()
    ctx = _ctx(seed)
    assert snapshot_from_context(ctx) == snapshot_from_context(ctx)


def test_snapshot_carries_the_latest_trial_ph():
    seed = load_seed()
    ctx = dataclasses.replace(
        _ctx(seed), latest_trial_ph=Tracked(4.1, TruthLabel.OBSERVED, "trial batch")
    )
    restored = context_from_snapshot(snapshot_from_context(ctx))
    assert restored.latest_trial_ph == ctx.latest_trial_ph
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/store/test_snapshot.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'foodbrew.store.snapshot'`

- [ ] **Step 3: Write the implementation**

`src/foodbrew/store/snapshot.py`:

```python
"""Freeze an EvalContext into JSON and thaw it back.

Spec §4: an evaluation stores a snapshot of all its inputs, and re-running that
snapshot on the same engine version must reproduce byte-identical results. The
snapshot holds the *referenced closure* rather than the whole catalogue (plan
decision #4): every rule reaches a record through an id on the formulation, so
the records named by those ids, plus the substrates they name, plus every GI
region, is everything any rule can read.

JSON is emitted with sorted keys and no incidental whitespace so that two
snapshots of the same inputs are byte-identical strings, which is what makes
"has this evaluation's input changed" a string comparison.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

from foodbrew.engine.types import (
    Deadline,
    DwellProfile,
    Enzyme,
    EvalContext,
    Food,
    Format,
    Formulation,
    GIRegion,
    Phase,
    ProcessStep,
    RecipeIngredient,
    SelectedEnzyme,
    SeverityTier,
    StructuralClass,
    StructuralEntry,
    Substrate,
    Tracked,
    TruthLabel,
)

#: Bumped if this file's JSON shape changes in a way old snapshots cannot read.
SNAPSHOT_VERSION = 1


def _t(tracked: Tracked) -> dict:
    return {"value": tracked.value, "status": str(tracked.status), "source": tracked.source}


def _untracked(raw: Mapping | None) -> Tracked:
    if raw is None:
        return Tracked(None, TruthLabel.UNCONFIRMED, "")
    return Tracked(raw["value"], TruthLabel(raw["status"]), raw.get("source", ""))


def _enzyme_out(e: Enzyme) -> dict:
    return {
        "id": e.id, "name": e.name, "aliases": list(e.aliases),
        "substrate_id": e.substrate_id, "source_type": e.source_type,
        "priority": e.priority, "deadline": str(e.deadline),
        "site_of_action": e.site_of_action, "dose_unit": e.dose_unit,
        "dose_benchmark_note": e.dose_benchmark_note,
        "is_protease": e.is_protease, "is_natural_source": e.is_natural_source,
        "food_grade_note": e.food_grade_note, "heat_labile_note": e.heat_labile_note,
        "cost_tier": e.cost_tier, "supplier_note": e.supplier_note, "notes": e.notes,
        "degrades_structural": [
            {"structural_class": str(x.structural_class), "tier": str(x.tier)}
            for x in e.degrades_structural
        ],
        **{
            name: _t(getattr(e, name))
            for name in (
                "ph_min", "ph_max", "ph_opt_low", "ph_opt_high", "ph_shelf_stable_min",
                "temp_min_c", "temp_max_c", "temp_opt_c",
                "dose_min", "dose_max", "dose_evidence_threshold", "is_gras",
            )
        },
    }


def _enzyme_in(raw: Mapping) -> Enzyme:
    return Enzyme(
        id=raw["id"], name=raw["name"], aliases=tuple(raw["aliases"]),
        substrate_id=raw["substrate_id"], source_type=raw["source_type"],
        priority=raw["priority"], deadline=Deadline(raw["deadline"]),
        site_of_action=raw["site_of_action"], dose_unit=raw["dose_unit"],
        dose_benchmark_note=raw["dose_benchmark_note"],
        is_protease=raw["is_protease"], is_natural_source=raw["is_natural_source"],
        food_grade_note=raw["food_grade_note"], heat_labile_note=raw["heat_labile_note"],
        cost_tier=raw["cost_tier"], supplier_note=raw["supplier_note"], notes=raw["notes"],
        degrades_structural=tuple(
            StructuralEntry(StructuralClass(x["structural_class"]), SeverityTier(x["tier"]))
            for x in raw["degrades_structural"]
        ),
        **{
            name: _untracked(raw.get(name))
            for name in (
                "ph_min", "ph_max", "ph_opt_low", "ph_opt_high", "ph_shelf_stable_min",
                "temp_min_c", "temp_max_c", "temp_opt_c",
                "dose_min", "dose_max", "dose_evidence_threshold", "is_gras",
            )
        },
    )


def _food_out(f: Food) -> dict:
    return {
        "id": f.id, "name": f.name, "category": f.category,
        "is_recipe_ingredient": f.is_recipe_ingredient,
        "is_trigger_food": f.is_trigger_food,
        "is_application_food": f.is_application_food,
        "contains_substrate_ids": list(f.contains_substrate_ids),
        "typical_load_unit": f.typical_load_unit,
        "contains_protease": f.contains_protease,
        "is_heat_processed": f.is_heat_processed,
        "structural": [str(s) for s in f.structural],
        "notes": f.notes,
        **{name: _t(getattr(f, name)) for name in ("ph", "water_content_pct", "typical_load_value")},
    }


def _food_in(raw: Mapping) -> Food:
    return Food(
        id=raw["id"], name=raw["name"], category=raw["category"],
        is_recipe_ingredient=raw["is_recipe_ingredient"],
        is_trigger_food=raw["is_trigger_food"],
        is_application_food=raw["is_application_food"],
        contains_substrate_ids=tuple(raw["contains_substrate_ids"]),
        typical_load_unit=raw["typical_load_unit"],
        contains_protease=raw["contains_protease"],
        is_heat_processed=raw["is_heat_processed"],
        structural=tuple(StructuralClass(s) for s in raw["structural"]),
        notes=raw["notes"],
        **{
            name: _untracked(raw.get(name))
            for name in ("ph", "water_content_pct", "typical_load_value")
        },
    )


def _formulation_out(f: Formulation) -> dict:
    return {
        "id": f.id, "format": str(f.format),
        "recipe": [
            {"food_id": i.food_id, "amount_g": i.amount_g, "order": i.order} for i in f.recipe
        ],
        "enzymes": [
            {
                "enzyme_id": s.enzyme_id, "dose": s.dose, "phase": str(s.phase),
                "encapsulated": s.encapsulated, "source_choice": s.source_choice,
            }
            for s in f.enzymes
        ],
        "target_trigger_food_ids": list(f.target_trigger_food_ids),
        "application_food_ids": list(f.application_food_ids),
        "dwell_profile": str(f.dwell_profile) if f.dwell_profile else None,
        "serving_size_g": f.serving_size_g,
        "measured_ph": _t(f.measured_ph),
        "process_steps": [
            {"order": s.order, "label": s.label, "is_heat": s.is_heat} for s in f.process_steps
        ],
        "enzyme_addition_index": f.enzyme_addition_index,
        "parent_formulation_id": f.parent_formulation_id,
    }


def _formulation_in(raw: Mapping) -> Formulation:
    return Formulation(
        id=raw["id"], format=Format(raw["format"]),
        recipe=tuple(
            RecipeIngredient(i["food_id"], i["amount_g"], i["order"]) for i in raw["recipe"]
        ),
        enzymes=tuple(
            SelectedEnzyme(
                s["enzyme_id"], s["dose"], Phase(s["phase"]),
                s["encapsulated"], s["source_choice"],
            )
            for s in raw["enzymes"]
        ),
        target_trigger_food_ids=tuple(raw["target_trigger_food_ids"]),
        application_food_ids=tuple(raw["application_food_ids"]),
        dwell_profile=DwellProfile(raw["dwell_profile"]) if raw["dwell_profile"] else None,
        serving_size_g=raw["serving_size_g"],
        measured_ph=_untracked(raw["measured_ph"]),
        process_steps=tuple(
            ProcessStep(s["order"], s["label"], s["is_heat"]) for s in raw["process_steps"]
        ),
        enzyme_addition_index=raw["enzyme_addition_index"],
        parent_formulation_id=raw["parent_formulation_id"],
    )


def referenced_ids(ctx: EvalContext) -> tuple[set[str], set[str], set[str]]:
    """The closure of records this formulation can reach: enzymes, foods, substrates."""
    form = ctx.formulation
    enzyme_ids = {s.enzyme_id for s in form.enzymes}
    food_ids = (
        {i.food_id for i in form.recipe}
        | set(form.target_trigger_food_ids)
        | set(form.application_food_ids)
    )
    substrate_ids = {
        ctx.enzymes[eid].substrate_id for eid in enzyme_ids if eid in ctx.enzymes
    }
    for fid in food_ids:
        food = ctx.foods.get(fid)
        if food is not None:
            substrate_ids |= set(food.contains_substrate_ids)
    return enzyme_ids, food_ids, substrate_ids


def snapshot_from_context(ctx: EvalContext) -> str:
    enzyme_ids, food_ids, substrate_ids = referenced_ids(ctx)
    payload = {
        "snapshot_version": SNAPSHOT_VERSION,
        "formulation": _formulation_out(ctx.formulation),
        "enzymes": {
            eid: _enzyme_out(ctx.enzymes[eid]) for eid in sorted(enzyme_ids) if eid in ctx.enzymes
        },
        "foods": {
            fid: _food_out(ctx.foods[fid]) for fid in sorted(food_ids) if fid in ctx.foods
        },
        "substrates": {
            sid: {
                "id": s.id, "name": s.name,
                "native_human_enzyme": s.native_human_enzyme,
                "is_prebiotic": s.is_prebiotic,
                "no_commercial_enzyme": s.no_commercial_enzyme,
                "notes": s.notes,
            }
            for sid, s in (
                (sid, ctx.substrates[sid]) for sid in sorted(substrate_ids) if sid in ctx.substrates
            )
        },
        "gi_regions": [
            {
                "id": r.id, "name": r.name, "ph_low": r.ph_low, "ph_high": r.ph_high,
                "order": r.order, "dormant": r.dormant, "transit_note": r.transit_note,
            }
            for r in ctx.gi_regions
        ],
        "latest_trial_ph": _t(ctx.latest_trial_ph) if ctx.latest_trial_ph else None,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def context_from_snapshot(raw: str) -> EvalContext:
    payload = json.loads(raw)
    version = payload.get("snapshot_version")
    if version != SNAPSHOT_VERSION:
        raise ValueError(f"unsupported snapshot_version {version!r}")
    return EvalContext(
        formulation=_formulation_in(payload["formulation"]),
        enzymes={eid: _enzyme_in(e) for eid, e in payload["enzymes"].items()},
        foods={fid: _food_in(f) for fid, f in payload["foods"].items()},
        substrates={
            sid: Substrate(
                id=s["id"], name=s["name"],
                native_human_enzyme=s["native_human_enzyme"],
                is_prebiotic=s["is_prebiotic"],
                no_commercial_enzyme=s["no_commercial_enzyme"],
                notes=s["notes"],
            )
            for sid, s in payload["substrates"].items()
        },
        gi_regions=tuple(
            GIRegion(
                id=r["id"], name=r["name"], ph_low=r["ph_low"], ph_high=r["ph_high"],
                order=r["order"], dormant=r["dormant"], transit_note=r["transit_note"],
            )
            for r in payload["gi_regions"]
        ),
        latest_trial_ph=_untracked(payload["latest_trial_ph"])
        if payload["latest_trial_ph"]
        else None,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/store/test_snapshot.py -q`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/store/snapshot.py tests/store/test_snapshot.py
git commit -m "feat(store): snapshot an evaluation's referenced input closure"
```

---

## Task 6: Re-export `ValidationRejection` and extract `group_findings`

Two small refactors in place, both consumed by later tasks. Doing them here keeps the API layer from importing a rule module and keeps finding-grouping defined once.

**Files:**
- Modify: `src/foodbrew/engine/__init__.py`
- Modify: `src/foodbrew/engine/flags.py`
- Test: `tests/engine/test_flags.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/engine/test_flags.py`:

```python
from foodbrew.engine import ValidationRejection
from foodbrew.engine.flags import group_findings


def test_validation_rejection_is_importable_from_the_engine_package():
    assert issubclass(ValidationRejection, ValueError)


def test_group_findings_splits_by_verdict_and_excludes_advisories():
    findings = (
        RuleFinding("R1", Verdict.RED, "blocker"),
        RuleFinding("R7", Verdict.CANNOT_ASSESS, "gap"),
        RuleFinding("R4", Verdict.AMBER, "caution"),
        RuleFinding("R3", Verdict.PASS, "fine"),
        RuleFinding("R9", Verdict.AMBER, "advice", advisory=True),
    )
    groups = group_findings(findings)
    assert [f.rule_id for f in groups.blockers] == ["R1"]
    assert [f.rule_id for f in groups.data_gaps] == ["R7"]
    assert [f.rule_id for f in groups.cautions] == ["R4"]
    assert [f.rule_id for f in groups.advisories] == ["R9"]


def test_aggregate_reports_the_same_groups_as_group_findings():
    findings = (
        RuleFinding("R1", Verdict.RED, "blocker"),
        RuleFinding("R9", Verdict.AMBER, "advice", advisory=True),
    )
    envelope = {p: Verdict.PASS for p in DwellProfile}
    agg = aggregate(findings, envelope, None)
    groups = group_findings(findings)
    assert (agg.blockers, agg.data_gaps, agg.cautions, agg.advisories) == (
        groups.blockers, groups.data_gaps, groups.cautions, groups.advisories,
    )
```

Add any missing imports (`DwellProfile`, `RuleFinding`, `Verdict`, `aggregate`) to that file.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/engine/test_flags.py -q`
Expected: FAIL — `ImportError: cannot import name 'ValidationRejection'`

- [ ] **Step 3: Write the implementation**

`src/foodbrew/engine/__init__.py`:

```python
"""Pure rules engine. No I/O, no persistence — see tests/engine/test_purity.py."""

from foodbrew.engine.evaluate import Evaluation, evaluate
from foodbrew.engine.rules.r14_substrate_coverage import ValidationRejection

__all__ = ["Evaluation", "ValidationRejection", "evaluate"]
```

In `src/foodbrew/engine/flags.py`, add a `FindingGroups` dataclass and `group_findings`, and have `aggregate` call it rather than repeat the predicates:

```python
@dataclass(frozen=True, slots=True)
class FindingGroups:
    """Spec §10 screen 4 — Blockers / Data gaps / Cautions / Advisory."""

    blockers: tuple[RuleFinding, ...]
    data_gaps: tuple[RuleFinding, ...]
    cautions: tuple[RuleFinding, ...]
    advisories: tuple[RuleFinding, ...]


def group_findings(findings: Sequence[RuleFinding]) -> FindingGroups:
    """Split findings the way the verdict screen and the stored evaluation both need.

    Defined once here because the read path (store/evaluations.py) reconstructs
    the groups from stored rows without re-running aggregation.
    """
    non_advisory = [f for f in findings if not f.advisory]
    return FindingGroups(
        blockers=tuple(f for f in non_advisory if f.verdict is Verdict.RED),
        data_gaps=tuple(f for f in non_advisory if f.verdict is Verdict.CANNOT_ASSESS),
        cautions=tuple(f for f in non_advisory if f.verdict is Verdict.AMBER),
        advisories=tuple(f for f in findings if f.advisory),
    )
```

and inside `aggregate`, replace the four tuple comprehensions with:

```python
    groups = group_findings(findings)

    return Aggregation(
        overall=overall,
        display=HEADLINE_DISPLAY[overall],
        blockers=groups.blockers,
        data_gaps=groups.data_gaps,
        cautions=groups.cautions,
        advisories=groups.advisories,
    )
```

- [ ] **Step 4: Run the whole suite**

Run: `.venv/bin/pytest -q`
Expected: every M1 test still passes — this refactor must not change a single verdict.

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/engine/__init__.py src/foodbrew/engine/flags.py tests/engine/test_flags.py
git commit -m "refactor(engine): extract group_findings and re-export ValidationRejection"
```

---

## Task 7: `engine/selection.py` — propose the enzyme set

Workflow A step 5. Pure, so M3's R14 auto-variant ("add the enzyme targeting the uncovered substrate") reuses it rather than reimplementing it.

**Files:**
- Create: `src/foodbrew/engine/selection.py`
- Test: `tests/engine/test_selection.py`

- [ ] **Step 1: Write the failing test**

`tests/engine/test_selection.py`:

```python
from foodbrew.engine.selection import propose_enzymes
from foodbrew.engine.types import Format, Phase


def test_proposes_an_enzyme_for_a_targeted_substrate(seed):
    proposed = propose_enzymes(
        trigger_food_ids=("milk",), format=Format.DRY_SACHET,
        foods=seed.foods, substrates=seed.substrates, enzymes=seed.enzymes,
    )
    assert any(s.enzyme_id.startswith("lactase") for s in proposed)


def test_never_proposes_an_enzyme_for_a_polyol_food(seed):
    """Spec §6.2 R14 — the tool never maps polyols to an enzyme."""
    polyol_foods = [
        f.id for f in seed.foods.values()
        if any(
            seed.substrates[sid].no_commercial_enzyme
            for sid in f.contains_substrate_ids
            if sid in seed.substrates
        )
    ]
    assert polyol_foods, "the seed carries at least one polyol trigger food"
    proposed = propose_enzymes(
        trigger_food_ids=tuple(polyol_foods), format=Format.DRY_SACHET,
        foods=seed.foods, substrates=seed.substrates, enzymes=seed.enzymes,
    )
    for selected in proposed:
        substrate = seed.substrates[seed.enzymes[selected.enzyme_id].substrate_id]
        assert substrate.no_commercial_enzyme is False


def test_phase_follows_the_format(seed):
    dry = propose_enzymes(
        trigger_food_ids=("milk",), format=Format.DUAL_CHAMBER,
        foods=seed.foods, substrates=seed.substrates, enzymes=seed.enzymes,
    )
    wet = propose_enzymes(
        trigger_food_ids=("milk",), format=Format.PREMIXED_WET,
        foods=seed.foods, substrates=seed.substrates, enzymes=seed.enzymes,
    )
    assert all(s.phase is Phase.DRY for s in dry)
    assert all(s.phase is Phase.WET for s in wet)


def test_dose_is_never_invented(seed):
    """A proposed dose comes from the record or is left None for R7 to flag."""
    proposed = propose_enzymes(
        trigger_food_ids=("milk",), format=Format.DRY_SACHET,
        foods=seed.foods, substrates=seed.substrates, enzymes=seed.enzymes,
    )
    for selected in proposed:
        enzyme = seed.enzymes[selected.enzyme_id]
        if selected.dose is None:
            continue
        assert selected.dose in {
            enzyme.dose_evidence_threshold.value, enzyme.dose_min.value
        }


def test_proposal_is_deterministic_and_deduplicated(seed):
    args = dict(
        trigger_food_ids=("milk", "milk"), format=Format.DRY_SACHET,
        foods=seed.foods, substrates=seed.substrates, enzymes=seed.enzymes,
    )
    first = propose_enzymes(**args)
    assert first == propose_enzymes(**args)
    assert len({s.enzyme_id for s in first}) == len(first)


def test_unknown_food_ids_are_ignored_rather_than_raising(seed):
    assert propose_enzymes(
        trigger_food_ids=("no_such_food",), format=Format.DRY_SACHET,
        foods=seed.foods, substrates=seed.substrates, enzymes=seed.enzymes,
    ) == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/engine/test_selection.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'foodbrew.engine.selection'`

- [ ] **Step 3: Write the implementation**

```python
"""Workflow A step 5 — propose an enzyme set from the substrate map.

A proposal, not a decision: the founder adds and removes enzymes afterwards,
and removing one does not remove the finding (R14 still reports the uncovered
substrate). Pure, so M3's R14 auto-variant reuses it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from foodbrew.engine.types import (
    Enzyme,
    Food,
    Format,
    Phase,
    SelectedEnzyme,
    Substrate,
)

#: Formats where the enzyme sits in the liquid; everything else keeps it dry.
_WET_FORMATS = frozenset({Format.PREMIXED_WET, Format.ENCAPSULATED_IN_WET})

#: Proposal order within one substrate. Anything unlisted sorts last, then by id,
#: so the proposal is stable rather than dictionary-ordered.
_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _proposed_dose(enzyme: Enzyme) -> float | None:
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

    phase = Phase.WET if format in _WET_FORMATS else Phase.DRY
    candidates = [e for e in enzymes.values() if e.substrate_id in wanted]
    candidates.sort(key=lambda e: (_PRIORITY_ORDER.get(e.priority, 99), e.id))

    chosen: dict[str, Enzyme] = {}
    for enzyme in candidates:
        chosen.setdefault(enzyme.substrate_id, enzyme)

    return tuple(
        SelectedEnzyme(
            enzyme_id=enzyme.id, dose=_proposed_dose(enzyme), phase=phase, encapsulated=False
        )
        for _, enzyme in sorted(chosen.items())
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/engine/test_selection.py -q`
Expected: 6 passed. `tests/engine/test_purity.py` must also still pass — `selection.py` imports nothing outside `engine.types`.

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/engine/selection.py tests/engine/test_selection.py
git commit -m "feat(engine): propose an enzyme set from the substrate map"
```

---

## Task 8: `engine/views.py` — GI strip, dose cards, substrate summary

The three derivations §10 puts on screen. Pure functions of an `EvalContext`, which is what lets `GET /evaluations/{id}` build them from the frozen snapshot instead of from current rows (plan decision #5).

**Files:**
- Create: `src/foodbrew/engine/views.py`
- Test: `tests/engine/test_views.py`

- [ ] **Step 1: Write the failing test**

`tests/engine/test_views.py`:

```python
from foodbrew.engine.types import Format, Phase, TruthLabel, Verdict
from foodbrew.engine.views import RULE_TITLES, dose_cards, gi_strip, substrate_summary


def test_gi_strip_marks_the_mouth_dormant_and_inactive(make_ctx):
    strip = gi_strip(make_ctx())
    regions = {r.region_id: r for r in strip[0].regions}
    assert regions["mouth"].dormant is True
    assert regions["mouth"].active is False


def test_gi_strip_marks_the_fed_stomach_active_for_fungal_lactase(make_ctx):
    """Seeded lactase is 2.5–5.4; the fed stomach is 4.0–6.0 (spec §8)."""
    strip = gi_strip(make_ctx())
    regions = {r.region_id: r for r in strip[0].regions}
    assert regions["stomach_fed"].active is True
    assert regions["stomach_fasting"].active is False


def test_gi_strip_marks_regions_at_or_before_the_deadline(make_ctx):
    strip = gi_strip(make_ctx())
    regions = {r.region_id: r for r in strip[0].regions}
    assert regions["stomach_fed"].before_deadline is True
    assert regions["colon"].before_deadline is False


def test_gi_strip_is_empty_when_the_ph_range_is_unconfirmed(make_ctx):
    ctx = make_ctx(enzymes=(("fructan_hydrolase", None, Phase.DRY),))
    lane = gi_strip(ctx)[0]
    assert all(r.active is False for r in lane.regions)
    assert lane.ph_min.status == TruthLabel.UNCONFIRMED


def test_dose_card_reports_the_threshold_comparison(make_ctx, with_load):
    ctx = make_ctx(
        enzymes=(("alpha_galactosidase", 150.0, Phase.DRY),),
        trigger_foods=("black_beans",),
        foods=with_load(black_beans=6.0),
    )
    card = dose_cards(ctx)[0]
    assert card.dose == 150.0
    assert card.meets_threshold is False  # 300 GALU threshold, spec §6.1 R7


def test_dose_card_leaves_the_comparison_none_when_the_threshold_is_unconfirmed(make_ctx):
    card = dose_cards(make_ctx())[0]
    assert card.dose_evidence_threshold.usable is False
    assert card.meets_threshold is None
    assert card.ratio is None


def test_dose_card_carries_the_summed_substrate_load(make_ctx, with_load):
    ctx = make_ctx(
        enzymes=(("alpha_galactosidase", 800.0, Phase.DRY),),
        trigger_foods=("black_beans", "lentils"),
        foods=with_load(black_beans=6.0, lentils=4.0),
    )
    card = dose_cards(ctx)[0]
    assert card.substrate_load.value == 10.0


def test_substrate_summary_names_the_substrates_a_recipe_carries(make_ctx):
    ctx = make_ctx(recipe=(("garlic_fresh", 5.0), ("olive_oil", 100.0)))
    summary = {row.substrate_id: row for row in substrate_summary(ctx.formulation.recipe, ctx.foods, ctx.substrates)}
    assert "inulin_fructan" in summary
    assert summary["inulin_fructan"].from_food_names == ("Garlic (fresh)",)
    assert summary["inulin_fructan"].is_prebiotic is True


def test_every_rule_has_a_title():
    for rule_id in [f"R{n}" for n in range(1, 17)]:
        assert RULE_TITLES[rule_id]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/engine/test_views.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'foodbrew.engine.views'`

- [ ] **Step 3: Write the implementation**

```python
"""Derived views the verdict screen renders. Pure, so a stored snapshot renders
exactly as it did when it was evaluated (plan decision #5).

These are derivations, not rules: they compute nothing a rule does not already
read, and they never produce a verdict. R7's judgement lives in r07_dosing.py;
the dose card here only exposes the same arithmetic so the screen can show the
founder why the rule said what it said.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from foodbrew.engine.conventions import aggregate_substrate_loads
from foodbrew.engine.dosing import assess_dose
from foodbrew.engine.gi_model import active_regions, regions_before_deadline
from foodbrew.engine.types import (
    Deadline,
    EvalContext,
    Food,
    RecipeIngredient,
    Substrate,
    Tracked,
    TruthLabel,
)

#: Plain-English rule names for the screen, so the UI hardcodes no copy (§10).
RULE_TITLES: Mapping[str, str] = {
    "R1": "In-jar pH survival",
    "R2": "GI window vs deadline",
    "R3": "No heat",
    "R4": "Water activation",
    "R5": "Protease co-formulation",
    "R6": "Encapsulation semantics",
    "R7": "Dosing vs substrate load",
    "R8": "In-jar taste and stability over time",
    "R9": "Prebiotic tension",
    "R10": "Strain blending",
    "R11": "Food-grade and GRAS",
    "R12": "Temperature range",
    "R13": "Format flag",
    "R14": "Substrate coverage",
    "R15": "Applied-food texture",
    "R16": "Clean label and natural sourcing",
}


@dataclass(frozen=True, slots=True)
class RegionState:
    region_id: str
    name: str
    ph_low: float
    ph_high: float
    order: int
    dormant: bool
    active: bool
    before_deadline: bool


@dataclass(frozen=True, slots=True)
class GiLane:
    enzyme_id: str
    enzyme_name: str
    deadline: Deadline
    ph_min: Tracked
    ph_max: Tracked
    regions: tuple[RegionState, ...]


@dataclass(frozen=True, slots=True)
class DoseCard:
    enzyme_id: str
    enzyme_name: str
    substrate_id: str
    dose: float | None
    dose_unit: str
    dose_min: Tracked
    dose_max: Tracked
    dose_evidence_threshold: Tracked
    substrate_load: Tracked
    #: None whenever any input is unusable — never a guess, mirroring R7.
    meets_threshold: bool | None
    ratio: float | None
    above_benchmark_max: bool | None


@dataclass(frozen=True, slots=True)
class SubstrateRow:
    substrate_id: str
    substrate_name: str
    from_food_names: tuple[str, ...]
    is_prebiotic: bool
    no_commercial_enzyme: bool


def gi_strip(ctx: EvalContext) -> tuple[GiLane, ...]:
    """One lane per selected enzyme: where along the tract it can act (§8, §10)."""
    lanes: list[GiLane] = []
    for selected in ctx.selected_enzymes():
        enzyme = ctx.enzyme_for(selected)
        active = {r.id for r in active_regions(enzyme, ctx.gi_regions)}
        before = {r.id for r in regions_before_deadline(enzyme.deadline, ctx.gi_regions)}
        lanes.append(
            GiLane(
                enzyme_id=enzyme.id,
                enzyme_name=enzyme.name,
                deadline=enzyme.deadline,
                ph_min=enzyme.ph_min,
                ph_max=enzyme.ph_max,
                regions=tuple(
                    RegionState(
                        region_id=r.id, name=r.name, ph_low=r.ph_low, ph_high=r.ph_high,
                        order=r.order, dormant=r.dormant,
                        active=r.id in active, before_deadline=r.id in before,
                    )
                    for r in ctx.gi_regions
                ),
            )
        )
    return tuple(lanes)


def dose_cards(ctx: EvalContext) -> tuple[DoseCard, ...]:
    """Per-enzyme dose against the summed substrate load and evidence threshold."""
    loads = aggregate_substrate_loads(ctx.formulation.target_trigger_food_ids, ctx.foods)
    cards: list[DoseCard] = []

    for selected in ctx.selected_enzymes():
        enzyme = ctx.enzyme_for(selected)
        load = loads.get(
            enzyme.substrate_id, Tracked(None, TruthLabel.UNCONFIRMED, "no targeted trigger food")
        )
        threshold = enzyme.dose_evidence_threshold

        if selected.dose is not None and threshold.usable:
            assessment = assess_dose(
                float(selected.dose),
                float(threshold.value),
                float(enzyme.dose_max.value) if enzyme.dose_max.usable else None,
            )
            meets, ratio, over = (
                assessment.meets_threshold, assessment.ratio, assessment.above_benchmark_max
            )
        else:
            meets = ratio = over = None

        cards.append(
            DoseCard(
                enzyme_id=enzyme.id, enzyme_name=enzyme.name,
                substrate_id=enzyme.substrate_id,
                dose=selected.dose, dose_unit=enzyme.dose_unit,
                dose_min=enzyme.dose_min, dose_max=enzyme.dose_max,
                dose_evidence_threshold=threshold, substrate_load=load,
                meets_threshold=meets, ratio=ratio, above_benchmark_max=over,
            )
        )
    return tuple(cards)


def substrate_summary(
    recipe: Sequence[RecipeIngredient],
    foods: Mapping[str, Food],
    substrates: Mapping[str, Substrate],
) -> tuple[SubstrateRow, ...]:
    """Spec §10 screen 2 — "this recipe itself contains: GOS (garlic)…"."""
    names: dict[str, list[str]] = {}
    for ingredient in recipe:
        food = foods.get(ingredient.food_id)
        if food is None:
            continue
        for substrate_id in food.contains_substrate_ids:
            names.setdefault(substrate_id, []).append(food.name)

    rows: list[SubstrateRow] = []
    for substrate_id, food_names in sorted(names.items()):
        substrate = substrates.get(substrate_id)
        rows.append(
            SubstrateRow(
                substrate_id=substrate_id,
                substrate_name=substrate.name if substrate else substrate_id,
                from_food_names=tuple(dict.fromkeys(food_names)),
                is_prebiotic=bool(substrate and substrate.is_prebiotic),
                no_commercial_enzyme=bool(substrate and substrate.no_commercial_enzyme),
            )
        )
    return tuple(rows)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/engine/test_views.py tests/engine/test_purity.py -q`
Expected: all pass. If a food id in the tests (`black_beans`, `lentils`, `garlic_fresh`, `romaine`, `milk`) does not exist in `seed/foods.json`, correct the test to the seeded id — do not add a seed record in M2.

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/engine/views.py tests/engine/test_views.py
git commit -m "feat(engine): add GI strip, dose card, and substrate summary views"
```

---

## Task 9: Recipe persistence

**Files:**
- Create: `src/foodbrew/store/recipes.py`
- Test: `tests/store/test_recipes.py`

- [ ] **Step 1: Write the failing test**

`tests/store/test_recipes.py`:

```python
import pytest

from foodbrew.db import create_database
from foodbrew.engine import ValidationRejection
from foodbrew.store import recipes
from foodbrew.store.connection import connect


@pytest.fixture
def conn(tmp_path):
    db = create_database(tmp_path / "foodbrew.db")
    with connect(db) as c:
        yield c


def test_create_and_read_a_recipe(conn):
    rid = recipes.create(conn, name="House vinaigrette", notes="", ingredients=[
        {"food_id": "olive_oil", "amount_g": 100.0, "order": 1},
        {"food_id": "white_vinegar", "amount_g": 50.0, "order": 2},
    ])
    stored = recipes.get(conn, rid)
    assert stored.name == "House vinaigrette"
    assert [i.food_id for i in stored.ingredients] == ["olive_oil", "white_vinegar"]
    assert stored.created_at


def test_ingredients_come_back_in_order(conn):
    rid = recipes.create(conn, name="r", notes="", ingredients=[
        {"food_id": "white_vinegar", "amount_g": 1.0, "order": 9},
        {"food_id": "olive_oil", "amount_g": 1.0, "order": 2},
    ])
    assert [i.order for i in recipes.get(conn, rid).ingredients] == [2, 9]


def test_a_recipe_with_no_ingredients_is_rejected(conn):
    """Spec §6.7 — rejected at validation, not evaluated (plan decision #3)."""
    with pytest.raises(ValidationRejection, match="at least one ingredient"):
        recipes.create(conn, name="empty", notes="", ingredients=[])


def test_an_unknown_food_id_is_rejected(conn):
    with pytest.raises(ValidationRejection, match="no_such_food"):
        recipes.create(conn, name="r", notes="", ingredients=[
            {"food_id": "no_such_food", "amount_g": 1.0, "order": 1},
        ])


def test_a_negative_amount_is_rejected(conn):
    with pytest.raises(ValidationRejection, match="amount"):
        recipes.create(conn, name="r", notes="", ingredients=[
            {"food_id": "olive_oil", "amount_g": -1.0, "order": 1},
        ])


def test_update_replaces_the_ingredient_list(conn):
    rid = recipes.create(conn, name="r", notes="", ingredients=[
        {"food_id": "olive_oil", "amount_g": 100.0, "order": 1},
    ])
    recipes.update(conn, rid, name="r2", notes="n", ingredients=[
        {"food_id": "white_vinegar", "amount_g": 20.0, "order": 1},
    ])
    stored = recipes.get(conn, rid)
    assert stored.name == "r2"
    assert [i.food_id for i in stored.ingredients] == ["white_vinegar"]


def test_get_returns_none_for_an_unknown_id(conn):
    assert recipes.get(conn, "nope") is None


def test_list_is_newest_first(conn):
    a = recipes.create(conn, name="a", notes="", ingredients=[
        {"food_id": "olive_oil", "amount_g": 1.0, "order": 1}])
    b = recipes.create(conn, name="b", notes="", ingredients=[
        {"food_id": "olive_oil", "amount_g": 1.0, "order": 1}])
    listed = [r.id for r in recipes.list_all(conn)]
    assert listed.index(b) <= listed.index(a)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/store/test_recipes.py -q`
Expected: FAIL — `ImportError: cannot import name 'recipes'`

- [ ] **Step 3: Write the implementation**

```python
"""Recipe persistence, plus the validation spec §6.7 places at the boundary."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from foodbrew.engine import ValidationRejection
from foodbrew.engine.types import RecipeIngredient
from foodbrew.store.clock import now_iso
from foodbrew.store.ids import new_id


@dataclass(frozen=True, slots=True)
class StoredRecipe:
    id: str
    name: str
    notes: str
    created_at: str
    ingredients: tuple[RecipeIngredient, ...]


def _validate(conn: sqlite3.Connection, ingredients: Sequence[dict]) -> None:
    """Spec §6.7: a recipe with zero ingredients is rejected, not evaluated.

    Nothing in the engine owns this one — R14 owns the other degenerate case —
    so it is enforced here and again at evaluate time, raising the same type so
    both map to one HTTP status.
    """
    if not ingredients:
        raise ValidationRejection("Add at least one ingredient to this recipe.")

    known = {r["id"] for r in conn.execute("SELECT id FROM food")}
    seen: set[str] = set()
    for item in ingredients:
        food_id = item["food_id"]
        if food_id not in known:
            raise ValidationRejection(f"Unknown food '{food_id}'.")
        if food_id in seen:
            raise ValidationRejection(
                f"'{food_id}' appears twice — combine it into one amount."
            )
        seen.add(food_id)
        if float(item["amount_g"]) < 0:
            raise ValidationRejection(f"'{food_id}': amount cannot be negative.")


def _write_ingredients(conn, recipe_id: str, ingredients: Sequence[dict]) -> None:
    conn.execute("DELETE FROM recipe_ingredient WHERE recipe_id = ?", (recipe_id,))
    conn.executemany(
        'INSERT INTO recipe_ingredient (recipe_id, food_id, amount_g, "order")'
        " VALUES (?, ?, ?, ?)",
        [
            (recipe_id, i["food_id"], float(i["amount_g"]), int(i.get("order", n)))
            for n, i in enumerate(ingredients, start=1)
        ],
    )


def create(conn, *, name: str, notes: str, ingredients: Sequence[dict]) -> str:
    _validate(conn, ingredients)
    recipe_id = new_id()
    conn.execute(
        "INSERT INTO recipe (id, name, notes, created_at) VALUES (?, ?, ?, ?)",
        (recipe_id, name, notes, now_iso()),
    )
    _write_ingredients(conn, recipe_id, ingredients)
    conn.commit()
    return recipe_id


def update(conn, recipe_id: str, *, name: str, notes: str, ingredients: Sequence[dict]) -> None:
    _validate(conn, ingredients)
    conn.execute(
        "UPDATE recipe SET name = ?, notes = ? WHERE id = ?", (name, notes, recipe_id)
    )
    _write_ingredients(conn, recipe_id, ingredients)
    conn.commit()


def get(conn, recipe_id: str) -> StoredRecipe | None:
    row = conn.execute("SELECT * FROM recipe WHERE id = ?", (recipe_id,)).fetchone()
    if row is None:
        return None
    return StoredRecipe(
        id=row["id"], name=row["name"], notes=row["notes"], created_at=row["created_at"],
        ingredients=ingredients_for(conn, recipe_id),
    )


def ingredients_for(conn, recipe_id: str) -> tuple[RecipeIngredient, ...]:
    return tuple(
        RecipeIngredient(r["food_id"], float(r["amount_g"]), int(r["order"]))
        for r in conn.execute(
            'SELECT food_id, amount_g, "order" FROM recipe_ingredient'
            ' WHERE recipe_id = ? ORDER BY "order", food_id',
            (recipe_id,),
        )
    )


def list_all(conn) -> tuple[StoredRecipe, ...]:
    rows = conn.execute("SELECT * FROM recipe ORDER BY created_at DESC, id DESC").fetchall()
    return tuple(
        StoredRecipe(
            id=r["id"], name=r["name"], notes=r["notes"], created_at=r["created_at"],
            ingredients=ingredients_for(conn, r["id"]),
        )
        for r in rows
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/store/test_recipes.py -q`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/store/recipes.py tests/store/test_recipes.py
git commit -m "feat(store): persist recipes with boundary validation"
```

---

## Task 10: Custom foods

**Files:**
- Create: `src/foodbrew/store/foods.py`
- Test: `tests/store/test_foods.py`

- [ ] **Step 1: Write the failing test**

`tests/store/test_foods.py`:

```python
import pytest

from foodbrew.db import create_database
from foodbrew.engine import ValidationRejection
from foodbrew.engine.types import TruthLabel
from foodbrew.store import foods
from foodbrew.store.connection import connect
from foodbrew.store.reference import load_catalog


@pytest.fixture
def conn(tmp_path):
    with connect(create_database(tmp_path / "foodbrew.db")) as c:
        yield c


def test_a_custom_food_is_stored_user_provided(conn):
    """Spec §10 screen 2 / plan decision #9 — no client may claim `confirmed`."""
    fid = foods.create_custom(
        conn, name="Nonna's ricotta", category="dairy",
        is_recipe_ingredient=True, is_trigger_food=True, is_application_food=False,
        ph=5.9, water_content_pct=72.0, typical_load_value=4.0, typical_load_unit="g lactose",
        contains_substrate_ids=["lactose"], structural=[], contains_protease=False,
        is_heat_processed=False, notes="",
    )
    food = load_catalog(conn).foods[fid]
    assert food.ph.status is TruthLabel.USER_PROVIDED
    assert food.water_content_pct.status is TruthLabel.USER_PROVIDED
    assert food.typical_load_value.status is TruthLabel.USER_PROVIDED
    assert food.ph.source


def test_an_omitted_value_stays_unconfirmed_rather_than_user_provided(conn):
    fid = foods.create_custom(
        conn, name="Mystery powder", category="other",
        is_recipe_ingredient=True, is_trigger_food=False, is_application_food=False,
        ph=None, water_content_pct=None, typical_load_value=None, typical_load_unit="",
        contains_substrate_ids=[], structural=[], contains_protease=False,
        is_heat_processed=False, notes="",
    )
    food = load_catalog(conn).foods[fid]
    assert food.ph.status is TruthLabel.UNCONFIRMED


def test_an_unknown_substrate_id_is_rejected(conn):
    with pytest.raises(ValidationRejection, match="substrate"):
        foods.create_custom(
            conn, name="x", category="", is_recipe_ingredient=True,
            is_trigger_food=False, is_application_food=False,
            ph=None, water_content_pct=None, typical_load_value=None, typical_load_unit="",
            contains_substrate_ids=["not_a_substrate"], structural=[],
            contains_protease=False, is_heat_processed=False, notes="",
        )


def test_a_food_with_no_role_is_rejected(conn):
    with pytest.raises(ValidationRejection, match="role"):
        foods.create_custom(
            conn, name="x", category="", is_recipe_ingredient=False,
            is_trigger_food=False, is_application_food=False,
            ph=None, water_content_pct=None, typical_load_value=None, typical_load_unit="",
            contains_substrate_ids=[], structural=[], contains_protease=False,
            is_heat_processed=False, notes="",
        )


def test_listing_filters_by_role(conn):
    ingredients = foods.list_by_role(conn, "recipe_ingredient")
    triggers = foods.list_by_role(conn, "trigger")
    applications = foods.list_by_role(conn, "application")
    assert all(f.is_recipe_ingredient for f in ingredients)
    assert all(f.is_trigger_food for f in triggers)
    assert all(f.is_application_food for f in applications)
    assert len(foods.list_by_role(conn, None)) >= len(ingredients)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/store/test_foods.py -q`
Expected: FAIL — `ImportError: cannot import name 'foods'`

- [ ] **Step 3: Write the implementation**

```python
"""Food catalogue reads, and custom-food creation.

Spec §5.4 makes `confirmed` mean "verified against a named source", which a web
form is not. Custom foods are therefore stored `user_provided` by construction:
the caller supplies bare values and this module attaches the label. There is no
parameter by which a client chooses one (plan decision #9).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence

from foodbrew.engine import ValidationRejection
from foodbrew.engine.types import Food, StructuralClass, TruthLabel
from foodbrew.store.ids import new_id
from foodbrew.store.rowmap import food_from_row

#: What the founder typing a number into the database editor means.
CUSTOM_SOURCE = "entered by founder"

_ROLE_COLUMNS = {
    "recipe_ingredient": "is_recipe_ingredient",
    "trigger": "is_trigger_food",
    "application": "is_application_food",
}


def list_by_role(conn: sqlite3.Connection, role: str | None) -> tuple[Food, ...]:
    if role is None:
        rows = conn.execute("SELECT * FROM food ORDER BY name")
    else:
        column = _ROLE_COLUMNS.get(role)
        if column is None:
            raise ValidationRejection(f"Unknown role '{role}'.")
        rows = conn.execute(f"SELECT * FROM food WHERE {column} = 1 ORDER BY name")
    return tuple(food_from_row(r) for r in rows)


def get(conn: sqlite3.Connection, food_id: str) -> Food | None:
    row = conn.execute("SELECT * FROM food WHERE id = ?", (food_id,)).fetchone()
    return food_from_row(row) if row else None


def _tracked_columns(prefix: str, value) -> dict:
    """A supplied value is user_provided; an omitted one stays unconfirmed."""
    if value is None:
        return {prefix: None, f"{prefix}_status": TruthLabel.UNCONFIRMED.value, f"{prefix}_source": ""}
    return {
        prefix: float(value),
        f"{prefix}_status": TruthLabel.USER_PROVIDED.value,
        f"{prefix}_source": CUSTOM_SOURCE,
    }


def create_custom(
    conn: sqlite3.Connection,
    *,
    name: str,
    category: str,
    is_recipe_ingredient: bool,
    is_trigger_food: bool,
    is_application_food: bool,
    ph: float | None,
    water_content_pct: float | None,
    typical_load_value: float | None,
    typical_load_unit: str,
    contains_substrate_ids: Sequence[str],
    structural: Sequence[str],
    contains_protease: bool,
    is_heat_processed: bool,
    notes: str,
) -> str:
    if not (is_recipe_ingredient or is_trigger_food or is_application_food):
        raise ValidationRejection(
            "Give this food at least one role: recipe ingredient, trigger food, or application food."
        )

    known = {r["id"] for r in conn.execute("SELECT id FROM substrate")}
    for substrate_id in contains_substrate_ids:
        if substrate_id not in known:
            raise ValidationRejection(f"Unknown substrate '{substrate_id}'.")
    for entry in structural:
        try:
            StructuralClass(entry)
        except ValueError as exc:
            raise ValidationRejection(f"Unknown structural class '{entry}'.") from exc

    food_id = f"custom_{new_id()}"
    row = {
        "id": food_id, "name": name, "category": category,
        "is_recipe_ingredient": int(is_recipe_ingredient),
        "is_trigger_food": int(is_trigger_food),
        "is_application_food": int(is_application_food),
        "contains_substrate_ids_json": json.dumps(list(contains_substrate_ids)),
        "typical_load_unit": typical_load_unit,
        "contains_protease": int(contains_protease),
        "is_heat_processed": int(is_heat_processed),
        "structural_json": json.dumps(list(structural)),
        "notes": notes,
        **_tracked_columns("ph", ph),
        **_tracked_columns("water_content_pct", water_content_pct),
        **_tracked_columns("typical_load_value", typical_load_value),
    }
    columns = ", ".join(f'"{c}"' for c in row)
    placeholders = ", ".join("?" for _ in row)
    conn.execute(
        f"INSERT INTO food ({columns}) VALUES ({placeholders})", tuple(row.values())
    )
    conn.commit()
    return food_id
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/store/test_foods.py -q`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/store/foods.py tests/store/test_foods.py
git commit -m "feat(store): create custom foods as user_provided by construction"
```

---

## Task 11: Formulation persistence and context hydration

The join between the database and the engine. `hydrate_context` is the only function in the codebase that builds an `EvalContext` for real use.

**Files:**
- Create: `src/foodbrew/store/formulations.py`
- Test: `tests/store/test_formulations.py`

- [ ] **Step 1: Write the failing test**

`tests/store/test_formulations.py`:

```python
import pytest

from foodbrew.db import create_database
from foodbrew.engine import ValidationRejection, evaluate
from foodbrew.engine.types import DwellProfile, Format, Phase, TruthLabel
from foodbrew.store import formulations, recipes
from foodbrew.store.connection import connect


@pytest.fixture
def conn(tmp_path):
    with connect(create_database(tmp_path / "foodbrew.db")) as c:
        yield c


@pytest.fixture
def recipe_id(conn):
    return recipes.create(conn, name="vinaigrette", notes="", ingredients=[
        {"food_id": "olive_oil", "amount_g": 100.0, "order": 1},
        {"food_id": "white_vinegar", "amount_g": 50.0, "order": 2},
    ])


def _create(conn, recipe_id, **overrides):
    payload = dict(
        recipe_id=recipe_id, format="premixed_wet",
        target_trigger_food_ids=["milk"], application_food_ids=["romaine"],
        dwell_profile=None,
        enzymes=[{"enzyme_id": "lactase_fungal_acid", "dose": 9000.0, "phase": "wet",
                  "encapsulated": False, "source_choice": ""}],
        serving_size_g=30.0, measured_ph=3.0,
        process_steps=[{"order": 1, "label": "whisk", "is_heat": False}],
        enzyme_addition_index=1, parent_formulation_id=None,
    )
    payload.update(overrides)
    return formulations.create(conn, **payload)


def test_create_and_read_a_formulation(conn, recipe_id):
    fid = _create(conn, recipe_id)
    stored = formulations.get(conn, fid)
    assert stored.format is Format.PREMIXED_WET
    assert stored.enzymes[0].enzyme_id == "lactase_fungal_acid"
    assert stored.enzymes[0].phase is Phase.WET
    assert stored.measured_ph.status is TruthLabel.USER_PROVIDED
    assert stored.dwell_profile is None


def test_a_declared_dwell_profile_round_trips(conn, recipe_id):
    fid = _create(conn, recipe_id, dwell_profile="marinade")
    assert formulations.get(conn, fid).dwell_profile is DwellProfile.MARINADE


def test_an_unknown_enzyme_id_is_rejected(conn, recipe_id):
    with pytest.raises(ValidationRejection, match="enzyme"):
        _create(conn, recipe_id, enzymes=[{"enzyme_id": "nope", "dose": None,
                                           "phase": "dry", "encapsulated": False,
                                           "source_choice": ""}])


def test_zero_enzymes_and_zero_trigger_foods_is_rejected(conn, recipe_id):
    """Spec §6.2 R14 — rejected at validation, no evaluation created."""
    with pytest.raises(ValidationRejection, match="trigger food or enzyme"):
        _create(conn, recipe_id, enzymes=[], target_trigger_food_ids=[])


def test_hydrate_builds_a_context_the_engine_can_evaluate(conn, recipe_id):
    fid = _create(conn, recipe_id)
    ctx = formulations.hydrate_context(conn, fid)
    assert ctx.formulation.id == fid
    assert [i.food_id for i in ctx.formulation.recipe] == ["olive_oil", "white_vinegar"]
    assert evaluate(ctx).display in {"RED", "GRAY", "AMBER", "GREEN"}


def test_hydrated_context_reproduces_golden_fixture_a(conn, recipe_id):
    """Spec §13 (a): wet vinaigrette, pH 3.0, fungal lactase → RED via R1."""
    fid = _create(conn, recipe_id, measured_ph=3.0)
    result = evaluate(formulations.hydrate_context(conn, fid))
    r1 = [f for f in result.findings if f.rule_id == "R1"]
    assert any(f.verdict == "red" for f in r1)
    assert result.display == "RED"


def test_hydration_picks_up_the_latest_trial_batch_ph(conn, recipe_id):
    """Spec §6.7 step 2 / plan decision #8 — M4 writes these rows; hydration reads them now."""
    fid = _create(conn, recipe_id, measured_ph=None)
    conn.execute(
        "INSERT INTO evaluation (id, formulation_id, engine_version, input_snapshot_json,"
        " overall_flag, occasion_envelope_json, created_at)"
        " VALUES ('e1', ?, '1.0.0', '{}', 'amber', '{}', '2026-08-14T00:00:00+00:00')",
        (fid,),
    )
    conn.execute(
        "INSERT INTO trial (id, evaluation_id, protocol_json, status)"
        " VALUES ('t1', 'e1', '{}', 'running')"
    )
    conn.execute(
        "INSERT INTO trial_batch (id, trial_id, made_at, measured_ph, ph_method)"
        " VALUES ('b1', 't1', '2026-08-14T01:00:00+00:00', 4.1, 'meter')"
    )
    conn.commit()

    ctx = formulations.hydrate_context(conn, fid)
    assert ctx.latest_trial_ph.value == 4.1
    assert ctx.latest_trial_ph.status is TruthLabel.OBSERVED


def test_hydration_returns_no_trial_ph_when_no_trial_exists(conn, recipe_id):
    fid = _create(conn, recipe_id, measured_ph=None)
    assert formulations.hydrate_context(conn, fid).latest_trial_ph is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/store/test_formulations.py -q`
Expected: FAIL — `ImportError: cannot import name 'formulations'`

- [ ] **Step 3: Write the implementation**

```python
"""Formulation persistence, and the one place an EvalContext is built for real."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence

from foodbrew.engine import ValidationRejection
from foodbrew.engine.types import (
    DwellProfile,
    EvalContext,
    Format,
    Formulation,
    Phase,
    ProcessStep,
    SelectedEnzyme,
    Tracked,
    TruthLabel,
)
from foodbrew.store.clock import now_iso
from foodbrew.store.ids import new_id
from foodbrew.store.recipes import ingredients_for
from foodbrew.store.reference import load_catalog


def _validate(conn, *, recipe_id, enzymes, trigger_food_ids, application_food_ids, format):
    if conn.execute("SELECT 1 FROM recipe WHERE id = ?", (recipe_id,)).fetchone() is None:
        raise ValidationRejection(f"Unknown recipe '{recipe_id}'.")
    if not ingredients_for(conn, recipe_id):
        raise ValidationRejection("Add at least one ingredient to this recipe.")
    # Spec §6.2 R14 — the degenerate case the engine refuses to evaluate at all.
    if not enzymes and not trigger_food_ids:
        raise ValidationRejection(
            "Select at least one trigger food or enzyme before evaluating."
        )
    try:
        Format(format)
    except ValueError as exc:
        raise ValidationRejection(f"Unknown format '{format}'.") from exc

    known_enzymes = {r["id"] for r in conn.execute("SELECT id FROM enzyme")}
    for selected in enzymes:
        if selected["enzyme_id"] not in known_enzymes:
            raise ValidationRejection(f"Unknown enzyme '{selected['enzyme_id']}'.")
        try:
            Phase(selected["phase"])
        except ValueError as exc:
            raise ValidationRejection(f"Unknown phase '{selected['phase']}'.") from exc

    known_foods = {r["id"] for r in conn.execute("SELECT id FROM food")}
    for food_id in (*trigger_food_ids, *application_food_ids):
        if food_id not in known_foods:
            raise ValidationRejection(f"Unknown food '{food_id}'.")


def create(
    conn: sqlite3.Connection,
    *,
    recipe_id: str,
    format: str,
    target_trigger_food_ids: Sequence[str],
    application_food_ids: Sequence[str],
    dwell_profile: str | None,
    enzymes: Sequence[dict],
    serving_size_g: float | None,
    measured_ph: float | None,
    process_steps: Sequence[dict],
    enzyme_addition_index: int | None,
    parent_formulation_id: str | None,
) -> str:
    _validate(
        conn, recipe_id=recipe_id, enzymes=enzymes,
        trigger_food_ids=target_trigger_food_ids,
        application_food_ids=application_food_ids, format=format,
    )
    formulation_id = new_id()
    conn.execute(
        "INSERT INTO formulation (id, recipe_id, format, target_trigger_food_ids_json,"
        " application_food_ids_json, dwell_profile, enzyme_selection_json, serving_size_g,"
        " measured_ph, measured_ph_status, measured_ph_source, process_steps_json,"
        " enzyme_addition_index, parent_formulation_id, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            formulation_id, recipe_id, format,
            json.dumps(list(target_trigger_food_ids)),
            json.dumps(list(application_food_ids)),
            dwell_profile,
            json.dumps(list(enzymes)),
            serving_size_g,
            measured_ph,
            TruthLabel.USER_PROVIDED.value if measured_ph is not None
            else TruthLabel.UNCONFIRMED.value,
            "measured by founder" if measured_ph is not None else "",
            json.dumps(list(process_steps)),
            enzyme_addition_index,
            parent_formulation_id,
            now_iso(),
        ),
    )
    conn.commit()
    return formulation_id


def get(conn: sqlite3.Connection, formulation_id: str) -> Formulation | None:
    row = conn.execute(
        "SELECT * FROM formulation WHERE id = ?", (formulation_id,)
    ).fetchone()
    if row is None:
        return None
    return Formulation(
        id=row["id"],
        format=Format(row["format"]),
        recipe=ingredients_for(conn, row["recipe_id"]),
        enzymes=tuple(
            SelectedEnzyme(
                enzyme_id=s["enzyme_id"], dose=s.get("dose"),
                phase=Phase(s.get("phase", "dry")),
                encapsulated=bool(s.get("encapsulated", False)),
                source_choice=s.get("source_choice", ""),
            )
            for s in json.loads(row["enzyme_selection_json"])
        ),
        target_trigger_food_ids=tuple(json.loads(row["target_trigger_food_ids_json"])),
        application_food_ids=tuple(json.loads(row["application_food_ids_json"])),
        dwell_profile=DwellProfile(row["dwell_profile"]) if row["dwell_profile"] else None,
        serving_size_g=row["serving_size_g"],
        measured_ph=Tracked(
            row["measured_ph"],
            TruthLabel(row["measured_ph_status"]),
            row["measured_ph_source"],
        ),
        process_steps=tuple(
            ProcessStep(int(s["order"]), s["label"], bool(s.get("is_heat", False)))
            for s in json.loads(row["process_steps_json"])
        ),
        enzyme_addition_index=row["enzyme_addition_index"],
        parent_formulation_id=row["parent_formulation_id"],
    )


def recipe_id_for(conn, formulation_id: str) -> str | None:
    row = conn.execute(
        "SELECT recipe_id FROM formulation WHERE id = ?", (formulation_id,)
    ).fetchone()
    return row["recipe_id"] if row else None


def latest_trial_ph(conn, formulation_id: str) -> Tracked | None:
    """Spec §6.7 step 2 — the most recent trial batch's measured pH, labelled observed.

    M4 writes these rows. Reading them now costs nothing against an empty table
    and means M4 adds a writer rather than reworking hydration.
    """
    row = conn.execute(
        "SELECT b.measured_ph AS ph FROM trial_batch b"
        " JOIN trial t ON t.id = b.trial_id"
        " JOIN evaluation e ON e.id = t.evaluation_id"
        " WHERE e.formulation_id = ? AND b.measured_ph IS NOT NULL"
        " ORDER BY b.made_at DESC LIMIT 1",
        (formulation_id,),
    ).fetchone()
    if row is None:
        return None
    return Tracked(float(row["ph"]), TruthLabel.OBSERVED, "trial batch measurement")


def hydrate_context(conn: sqlite3.Connection, formulation_id: str) -> EvalContext:
    """Build the engine's input from the database. The engine never does this itself."""
    formulation = get(conn, formulation_id)
    if formulation is None:
        raise ValidationRejection(f"Unknown formulation '{formulation_id}'.")
    catalog = load_catalog(conn)
    return EvalContext(
        formulation=formulation,
        enzymes=catalog.enzymes,
        foods=catalog.foods,
        substrates=catalog.substrates,
        gi_regions=catalog.gi_regions,
        latest_trial_ph=latest_trial_ph(conn, formulation_id),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/store/test_formulations.py -q`
Expected: 8 passed. The golden-fixture-(a) assertion is the important one: it proves database-hydrated inputs reach the same verdict as M1's seed-hydrated fixtures.

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/store/formulations.py tests/store/test_formulations.py
git commit -m "feat(store): persist formulations and hydrate the engine context"
```

---


## Task 12: Evaluation persistence — append-only

**Files:**
- Create: `src/foodbrew/store/evaluations.py`
- Test: `tests/store/test_evaluations.py`

- [ ] **Step 1: Write the failing test**

`tests/store/test_evaluations.py`:

```python
import pytest

from foodbrew.db import create_database
from foodbrew.engine import evaluate
from foodbrew.engine.types import Verdict
from foodbrew.store import evaluations, formulations, recipes
from foodbrew.store.connection import connect
from foodbrew.store.snapshot import context_from_snapshot


@pytest.fixture
def conn(tmp_path):
    with connect(create_database(tmp_path / "foodbrew.db")) as c:
        yield c


@pytest.fixture
def formulation_id(conn):
    rid = recipes.create(conn, name="vinaigrette", notes="", ingredients=[
        {"food_id": "olive_oil", "amount_g": 100.0, "order": 1},
        {"food_id": "white_vinegar", "amount_g": 50.0, "order": 2},
    ])
    return formulations.create(
        conn, recipe_id=rid, format="premixed_wet",
        target_trigger_food_ids=["milk"], application_food_ids=["romaine"],
        dwell_profile=None,
        enzymes=[{"enzyme_id": "lactase_fungal_acid", "dose": 9000.0, "phase": "wet",
                  "encapsulated": False, "source_choice": ""}],
        serving_size_g=30.0, measured_ph=3.0,
        process_steps=[{"order": 1, "label": "whisk", "is_heat": False}],
        enzyme_addition_index=1, parent_formulation_id=None,
    )


def test_run_persists_an_evaluation_and_its_findings(conn, formulation_id):
    stored = evaluations.run(conn, formulation_id)
    assert stored.id
    assert stored.overall is Verdict.RED
    assert stored.display == "RED"
    assert stored.findings
    count = conn.execute(
        "SELECT COUNT(*) AS n FROM rule_finding WHERE evaluation_id = ?", (stored.id,)
    ).fetchone()["n"]
    assert count == len(stored.findings)


def test_read_returns_the_stored_result_without_re_running(conn, formulation_id):
    """Plan decision #5 — a stored evaluation is a record, not a recomputation."""
    stored = evaluations.run(conn, formulation_id)
    conn.execute("UPDATE rule_finding SET message = 'tampered' WHERE evaluation_id = ?",
                 (stored.id,))
    conn.commit()
    reread = evaluations.get(conn, stored.id)
    assert all(f.message == "tampered" for f in reread.findings)


def test_read_reconstructs_the_four_finding_groups(conn, formulation_id):
    stored = evaluations.run(conn, formulation_id)
    reread = evaluations.get(conn, stored.id)
    assert [f.rule_id for f in reread.blockers] == [f.rule_id for f in stored.blockers]
    assert [f.rule_id for f in reread.advisories] == [f.rule_id for f in stored.advisories]
    assert all(f.advisory for f in reread.advisories)


def test_the_stored_snapshot_reproduces_the_stored_verdict(conn, formulation_id):
    """Spec §4 — re-running the snapshot on the same engine version is identical."""
    stored = evaluations.run(conn, formulation_id)
    replayed = evaluate(context_from_snapshot(stored.input_snapshot_json))
    assert replayed.overall is stored.overall
    assert [f.message for f in replayed.findings] == [f.message for f in stored.findings]


def test_editing_a_source_record_never_mutates_a_stored_evaluation(conn, formulation_id):
    """Spec §4 and §13's property test, now across the database boundary."""
    stored = evaluations.run(conn, formulation_id)
    before = [(f.rule_id, f.verdict, f.message) for f in stored.findings]
    conn.execute(
        "UPDATE enzyme SET ph_min = 1.0, ph_shelf_stable_min = 1.0,"
        " ph_shelf_stable_min_status = 'confirmed' WHERE id = 'lactase_fungal_acid'"
    )
    conn.commit()

    reread = evaluations.get(conn, stored.id)
    assert [(f.rule_id, f.verdict, f.message) for f in reread.findings] == before
    replayed = evaluate(context_from_snapshot(reread.input_snapshot_json))
    assert replayed.overall is stored.overall


def test_evaluations_are_append_only(conn, formulation_id):
    first = evaluations.run(conn, formulation_id)
    second = evaluations.run(conn, formulation_id)
    assert first.id != second.id
    listed = evaluations.list_for_formulation(conn, formulation_id)
    assert [e.id for e in listed][0] == second.id
    assert len(listed) == 2


def test_the_envelope_round_trips(conn, formulation_id):
    stored = evaluations.run(conn, formulation_id)
    reread = evaluations.get(conn, stored.id)
    assert reread.envelope == stored.envelope


def test_get_returns_none_for_an_unknown_id(conn):
    assert evaluations.get(conn, "nope") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/store/test_evaluations.py -q`
Expected: FAIL — `ImportError: cannot import name 'evaluations'`

- [ ] **Step 3: Write the implementation**

```python
"""Evaluation persistence. Append-only: a run writes a new row, never updates one.

Spec §4: later edits to source records never mutate a stored evaluation, and a
stored snapshot re-run on the same engine version reproduces byte-identical
results. Both properties are tested across the database boundary in
tests/store/test_evaluations.py.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from foodbrew.engine import evaluate
from foodbrew.engine.flags import HEADLINE_DISPLAY, group_findings
from foodbrew.engine.types import DwellProfile, RuleFinding, Verdict
from foodbrew.store.clock import now_iso
from foodbrew.store.formulations import hydrate_context
from foodbrew.store.ids import new_id
from foodbrew.store.snapshot import snapshot_from_context


@dataclass(frozen=True, slots=True)
class StoredEvaluation:
    id: str
    formulation_id: str
    engine_version: str
    created_at: str
    overall: Verdict
    display: str
    findings: tuple[RuleFinding, ...]
    envelope: dict[DwellProfile, Verdict]
    input_snapshot_json: str
    blockers: tuple[RuleFinding, ...]
    data_gaps: tuple[RuleFinding, ...]
    cautions: tuple[RuleFinding, ...]
    advisories: tuple[RuleFinding, ...]


def run(conn: sqlite3.Connection, formulation_id: str) -> StoredEvaluation:
    """Hydrate, evaluate, and persist. Raises ValidationRejection on degenerate input."""
    ctx = hydrate_context(conn, formulation_id)
    result = evaluate(ctx)  # ValidationRejection propagates — nothing is written
    snapshot = snapshot_from_context(ctx)

    evaluation_id = new_id()
    created_at = now_iso()
    conn.execute(
        "INSERT INTO evaluation (id, formulation_id, engine_version, input_snapshot_json,"
        " overall_flag, occasion_envelope_json, created_at) VALUES (?,?,?,?,?,?,?)",
        (
            evaluation_id, formulation_id, result.engine_version, snapshot,
            str(result.overall),
            json.dumps({str(k): str(v) for k, v in result.envelope.items()}, sort_keys=True),
            created_at,
        ),
    )
    conn.executemany(
        "INSERT INTO rule_finding (evaluation_id, rule_id, enzyme_id, food_id, verdict,"
        " advisory, message, evidence_json) VALUES (?,?,?,?,?,?,?,?)",
        [
            (
                evaluation_id, f.rule_id, f.enzyme_id, f.food_id, str(f.verdict),
                int(f.advisory), f.message,
                json.dumps(dict(f.evidence), sort_keys=True, default=str),
            )
            for f in result.findings
        ],
    )
    conn.commit()

    return _assemble(
        evaluation_id=evaluation_id, formulation_id=formulation_id,
        engine_version=result.engine_version, created_at=created_at,
        overall=result.overall, findings=result.findings,
        envelope=dict(result.envelope), snapshot=snapshot,
    )


def get(conn: sqlite3.Connection, evaluation_id: str) -> StoredEvaluation | None:
    row = conn.execute(
        "SELECT * FROM evaluation WHERE id = ?", (evaluation_id,)
    ).fetchone()
    if row is None:
        return None
    findings = tuple(
        RuleFinding(
            rule_id=r["rule_id"], verdict=Verdict(r["verdict"]), message=r["message"],
            evidence=json.loads(r["evidence_json"]),
            enzyme_id=r["enzyme_id"], food_id=r["food_id"], advisory=bool(r["advisory"]),
        )
        for r in conn.execute(
            "SELECT * FROM rule_finding WHERE evaluation_id = ? ORDER BY id",
            (evaluation_id,),
        )
    )
    return _assemble(
        evaluation_id=row["id"], formulation_id=row["formulation_id"],
        engine_version=row["engine_version"], created_at=row["created_at"],
        overall=Verdict(row["overall_flag"]), findings=findings,
        envelope={
            DwellProfile(k): Verdict(v)
            for k, v in json.loads(row["occasion_envelope_json"]).items()
        },
        snapshot=row["input_snapshot_json"],
    )


def list_for_formulation(conn, formulation_id: str) -> tuple[StoredEvaluation, ...]:
    ids = [
        r["id"]
        for r in conn.execute(
            "SELECT id FROM evaluation WHERE formulation_id = ?"
            " ORDER BY created_at DESC, id DESC",
            (formulation_id,),
        )
    ]
    return tuple(get(conn, i) for i in ids)


def list_recent(conn, limit: int = 10) -> tuple[StoredEvaluation, ...]:
    ids = [
        r["id"]
        for r in conn.execute(
            "SELECT id FROM evaluation ORDER BY created_at DESC, id DESC LIMIT ?", (limit,)
        )
    ]
    return tuple(get(conn, i) for i in ids)


def _assemble(
    *, evaluation_id, formulation_id, engine_version, created_at, overall, findings,
    envelope, snapshot,
) -> StoredEvaluation:
    groups = group_findings(findings)
    return StoredEvaluation(
        id=evaluation_id, formulation_id=formulation_id, engine_version=engine_version,
        created_at=created_at, overall=overall, display=HEADLINE_DISPLAY[overall],
        findings=tuple(findings), envelope=envelope, input_snapshot_json=snapshot,
        blockers=groups.blockers, data_gaps=groups.data_gaps,
        cautions=groups.cautions, advisories=groups.advisories,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/store/test_evaluations.py -q`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/store/evaluations.py tests/store/test_evaluations.py
git commit -m "feat(store): persist evaluations append-only with input snapshots"
```

---

## Task 13: API settings, dependencies, and schemas

**Files:**
- Create: `src/foodbrew/api/__init__.py`
- Create: `src/foodbrew/api/settings.py`
- Create: `src/foodbrew/api/deps.py`
- Create: `src/foodbrew/api/schemas.py`
- Test: `tests/api/__init__.py`, `tests/api/test_schemas.py`

- [ ] **Step 1: Write the failing test**

`tests/api/test_schemas.py`:

```python
from foodbrew.api import schemas
from foodbrew.engine.types import Tracked, TruthLabel


def test_tracked_serializes_as_value_status_source():
    """Plan decision #7 — a number never travels without its label."""
    out = schemas.TrackedOut.of(Tracked(2.5, TruthLabel.CONFIRMED, "KB Table B"))
    assert out.model_dump() == {
        "value": 2.5, "status": "confirmed", "source": "KB Table B"
    }


def test_tracked_of_none_is_an_unconfirmed_object_not_a_null():
    out = schemas.TrackedOut.of(Tracked(None, TruthLabel.UNCONFIRMED, ""))
    assert out.model_dump() == {"value": None, "status": "unconfirmed", "source": ""}


def test_recipe_create_rejects_a_blank_name():
    import pydantic
    import pytest

    with pytest.raises(pydantic.ValidationError):
        schemas.RecipeIn(name="   ", notes="", ingredients=[])


def test_custom_food_schema_has_no_status_field():
    """Plan decision #9 — a client cannot choose a truth label."""
    fields = set(schemas.CustomFoodIn.model_fields)
    assert not any("status" in f for f in fields)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/api/test_schemas.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'foodbrew.api'`

- [ ] **Step 3: Write settings and deps**

`src/foodbrew/api/__init__.py`:

```python
"""HTTP layer. Imports store and engine; nothing imports it back."""
```

`src/foodbrew/api/settings.py`:

```python
"""Runtime configuration, all environment-driven with local-dev defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    db_path: Path
    web_dist: Path


def load_settings() -> Settings:
    return Settings(
        db_path=Path(os.environ.get("FOODBREW_DB_PATH", "data/foodbrew.db")),
        web_dist=Path(os.environ.get("FOODBREW_WEB_DIST", "web/dist")),
    )
```

`src/foodbrew/api/deps.py`:

```python
"""Request-scoped dependencies.

Every endpoint is a plain `def`, so FastAPI runs it in a worker thread and the
connection opened here is used and closed in that same thread. sqlite3 objects
are thread-confined; an async endpoint sharing a connection would be a bug that
only appears under concurrency (plan decision #10).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

from fastapi import Request

from foodbrew.store.connection import connect


def get_conn(request: Request) -> Iterator[sqlite3.Connection]:
    with connect(request.app.state.settings.db_path) as conn:
        yield conn
```

- [ ] **Step 4: Write `schemas.py`**

```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/api/test_schemas.py -q`
Expected: 4 passed. Create `tests/api/__init__.py` (empty) if pytest cannot import the package.

- [ ] **Step 6: Commit**

```bash
git add src/foodbrew/api tests/api
git commit -m "feat(api): add settings, request dependencies, and wire schemas"
```

---

## Task 14: The app factory, error mapping, and health

**Files:**
- Create: `src/foodbrew/api/app.py`
- Create: `tests/api/conftest.py`
- Test: `tests/api/test_app.py`

- [ ] **Step 1: Write the failing test**

`tests/api/conftest.py`:

```python
import pytest
from fastapi.testclient import TestClient

from foodbrew.api.app import create_app
from foodbrew.api.settings import Settings
from foodbrew.db import create_database
from foodbrew.store import formulations, recipes
from foodbrew.store.connection import connect


@pytest.fixture
def db_path(tmp_path):
    return create_database(tmp_path / "foodbrew.db")


@pytest.fixture
def client(db_path, tmp_path):
    app = create_app(Settings(db_path=db_path, web_dist=tmp_path / "no-web-build"))
    with TestClient(app) as c:
        yield c


@pytest.fixture
def conn(db_path):
    with connect(db_path) as c:
        yield c


@pytest.fixture
def vinaigrette(conn):
    """A recipe and formulation matching golden fixture (a): pH 3.0, wet, lactase."""
    recipe_id = recipes.create(conn, name="vinaigrette", notes="", ingredients=[
        {"food_id": "olive_oil", "amount_g": 100.0, "order": 1},
        {"food_id": "white_vinegar", "amount_g": 50.0, "order": 2},
    ])
    formulation_id = formulations.create(
        conn, recipe_id=recipe_id, format="premixed_wet",
        target_trigger_food_ids=["milk"], application_food_ids=["romaine"],
        dwell_profile=None,
        enzymes=[{"enzyme_id": "lactase_fungal_acid", "dose": 9000.0, "phase": "wet",
                  "encapsulated": False, "source_choice": ""}],
        serving_size_g=30.0, measured_ph=3.0,
        process_steps=[{"order": 1, "label": "whisk", "is_heat": False}],
        enzyme_addition_index=1, parent_formulation_id=None,
    )
    return {"recipe_id": recipe_id, "formulation_id": formulation_id}
```

`tests/api/test_app.py`:

```python
def test_health_reports_the_engine_version(client):
    body = client.get("/api/v1/health").json()
    assert body["status"] == "ok"
    assert body["engine_version"] == "1.0.0"


def test_unknown_resource_is_404(client):
    assert client.get("/api/v1/recipes/nope").status_code == 404


def test_validation_rejection_is_422_with_the_founder_facing_message(client):
    response = client.post("/api/v1/recipes", json={"name": "empty", "ingredients": []})
    assert response.status_code == 422
    assert "at least one ingredient" in response.json()["detail"].lower()


def test_a_missing_web_build_does_not_break_the_api(client):
    """The API must be usable before the frontend has ever been built."""
    assert client.get("/api/v1/health").status_code == 200


def test_startup_creates_the_database_if_it_is_missing(tmp_path):
    from fastapi.testclient import TestClient

    from foodbrew.api.app import create_app
    from foodbrew.api.settings import Settings

    path = tmp_path / "fresh" / "foodbrew.db"
    app = create_app(Settings(db_path=path, web_dist=tmp_path / "none"))
    with TestClient(app) as client:
        assert client.get("/api/v1/enzymes").json()
    assert path.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/api/test_app.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'foodbrew.api.app'`

- [ ] **Step 3: Write the implementation**

```python
"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from foodbrew import ENGINE_VERSION
from foodbrew.api.routers import catalog, evaluations, formulations, recipes
from foodbrew.api.settings import Settings, load_settings
from foodbrew.db import ensure_database
from foodbrew.engine import ValidationRejection


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # ensure_database, not create_database: a restart must never revert the
        # founder's edits to reference rows (plan decision #1).
        ensure_database(app.state.settings.db_path)
        yield

    app = FastAPI(title="FoodBrew", version=ENGINE_VERSION, lifespan=lifespan)
    app.state.settings = settings

    @app.exception_handler(ValidationRejection)
    async def _rejection(_: Request, exc: ValidationRejection) -> JSONResponse:
        # Spec §6.7 / §6.2 R14: degenerate input is refused, and the message is
        # the founder-facing one the rule wrote — not a stack trace.
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/api/v1/health")
    def health() -> dict:
        return {"status": "ok", "engine_version": ENGINE_VERSION}

    for router in (catalog.router, recipes.router, formulations.router, evaluations.router):
        app.include_router(router, prefix="/api/v1")

    _mount_web(app, settings)
    return app


def _mount_web(app: FastAPI, settings: Settings) -> None:
    """Serve the built React app, if there is one.

    Absent (a fresh checkout, or the test suite) the API still works — the
    frontend is a client of this server, not a prerequisite for it.
    """
    dist = settings.web_dist
    if not dist.is_dir():
        return

    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        # Client-side routes fall through to index.html; /api never does,
        # because its routes are registered first and match first.
        candidate = dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(dist / "index.html")


app = create_app()
```

- [ ] **Step 4: Note the ordering constraint**

`_mount_web` registers a catch-all. It runs after every `/api/v1` route is included, and FastAPI matches in registration order, so an API 404 stays a JSON 404 rather than becoming `index.html`. The test `test_unknown_resource_is_404` is what proves it; do not reorder.

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/pytest tests/api/test_app.py -q`
Expected: 5 passed once Tasks 15–17 have created the routers. If running this task alone, stub the four router modules with `router = APIRouter()` and fill them in the next tasks.

- [ ] **Step 6: Commit**

```bash
git add src/foodbrew/api/app.py tests/api/conftest.py tests/api/test_app.py
git commit -m "feat(api): add the app factory, error mapping, and SPA mount"
```

---

## Task 15: Catalog router

**Files:**
- Create: `src/foodbrew/api/routers/__init__.py`
- Create: `src/foodbrew/api/routers/catalog.py`
- Test: `tests/api/test_catalog.py`

- [ ] **Step 1: Write the failing test**

`tests/api/test_catalog.py`:

```python
def test_enzymes_are_listed_with_truth_labels(client):
    body = client.get("/api/v1/enzymes").json()
    assert len(body) == 12
    lactase = next(e for e in body if e["id"] == "lactase_fungal_acid")
    assert lactase["ph_min"] == {
        "value": 2.5, "status": "confirmed",
        "source": lactase["ph_min"]["source"],
    }
    assert lactase["ph_shelf_stable_min"]["status"] == "unconfirmed"


def test_foods_can_be_filtered_by_role(client):
    triggers = client.get("/api/v1/foods", params={"role": "trigger"}).json()
    assert triggers and all(f["is_trigger_food"] for f in triggers)
    everything = client.get("/api/v1/foods").json()
    assert len(everything) >= len(triggers)


def test_an_unknown_role_is_rejected(client):
    assert client.get("/api/v1/foods", params={"role": "nonsense"}).status_code == 422


def test_substrates_and_gi_model_are_available(client):
    assert len(client.get("/api/v1/substrates").json()) == 12
    regions = client.get("/api/v1/gi-model").json()
    assert [r["id"] for r in regions][0] == "mouth"
    assert any(r["dormant"] for r in regions)


def test_a_custom_food_is_created_user_provided_and_appears_in_the_catalog(client):
    created = client.post("/api/v1/foods", json={
        "name": "Nonna's ricotta", "category": "dairy",
        "is_recipe_ingredient": True, "is_trigger_food": True,
        "ph": 5.9, "water_content_pct": 72.0,
        "contains_substrate_ids": ["lactose"],
    })
    assert created.status_code == 201
    body = created.json()
    assert body["ph"]["status"] == "user_provided"
    listed = client.get("/api/v1/foods", params={"role": "trigger"}).json()
    assert body["id"] in {f["id"] for f in listed}


def test_a_custom_food_with_no_role_is_refused(client):
    response = client.post("/api/v1/foods", json={"name": "x"})
    assert response.status_code == 422
    assert "role" in response.json()["detail"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/api/test_catalog.py -q`
Expected: FAIL — module or route missing.

- [ ] **Step 3: Write the implementation**

`src/foodbrew/api/routers/__init__.py`: empty.

`src/foodbrew/api/routers/catalog.py`:

```python
"""Read-only reference data, plus custom-food creation (§10 screen 2)."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, Query

from foodbrew.api.deps import get_conn
from foodbrew.api.schemas import CustomFoodIn, EnzymeOut, FoodOut, GIRegionOut, SubstrateOut
from foodbrew.store import foods as foods_store
from foodbrew.store.reference import load_catalog

router = APIRouter(tags=["catalog"])


@router.get("/enzymes", response_model=list[EnzymeOut])
def list_enzymes(conn: sqlite3.Connection = Depends(get_conn)):
    catalog = load_catalog(conn)
    return [EnzymeOut.of(e) for e in sorted(catalog.enzymes.values(), key=lambda e: e.name)]


@router.get("/substrates", response_model=list[SubstrateOut])
def list_substrates(conn: sqlite3.Connection = Depends(get_conn)):
    catalog = load_catalog(conn)
    return [SubstrateOut.of(s) for s in sorted(catalog.substrates.values(), key=lambda s: s.name)]


@router.get("/gi-model", response_model=list[GIRegionOut])
def gi_model(conn: sqlite3.Connection = Depends(get_conn)):
    return [GIRegionOut.of(r) for r in load_catalog(conn).gi_regions]


@router.get("/foods", response_model=list[FoodOut])
def list_foods(
    role: str | None = Query(default=None, description="recipe_ingredient | trigger | application"),
    conn: sqlite3.Connection = Depends(get_conn),
):
    return [FoodOut.of(f) for f in foods_store.list_by_role(conn, role)]


@router.post("/foods", response_model=FoodOut, status_code=201)
def create_food(payload: CustomFoodIn, conn: sqlite3.Connection = Depends(get_conn)):
    food_id = foods_store.create_custom(conn, **payload.model_dump())
    return FoodOut.of(foods_store.get(conn, food_id))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/api/test_catalog.py -q`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/api/routers tests/api/test_catalog.py
git commit -m "feat(api): serve the reference catalogue and custom foods"
```

---

## Task 16: Recipes router

**Files:**
- Create: `src/foodbrew/api/routers/recipes.py`
- Test: `tests/api/test_recipes.py`

- [ ] **Step 1: Write the failing test**

`tests/api/test_recipes.py`:

```python
def _payload(**overrides):
    body = {
        "name": "House vinaigrette", "notes": "",
        "ingredients": [
            {"food_id": "olive_oil", "amount_g": 100.0, "order": 1},
            {"food_id": "garlic_fresh", "amount_g": 5.0, "order": 2},
        ],
    }
    body.update(overrides)
    return body


def test_create_read_update_and_list(client):
    created = client.post("/api/v1/recipes", json=_payload())
    assert created.status_code == 201
    recipe_id = created.json()["id"]

    fetched = client.get(f"/api/v1/recipes/{recipe_id}").json()
    assert fetched["name"] == "House vinaigrette"
    assert [i["food_id"] for i in fetched["ingredients"]] == ["olive_oil", "garlic_fresh"]

    client.put(f"/api/v1/recipes/{recipe_id}", json=_payload(name="Renamed"))
    assert client.get(f"/api/v1/recipes/{recipe_id}").json()["name"] == "Renamed"

    assert recipe_id in {r["id"] for r in client.get("/api/v1/recipes").json()}


def test_the_substrate_summary_names_what_the_recipe_itself_carries(client):
    """Spec §10 screen 2 — "this recipe itself contains: GOS (garlic)…"."""
    recipe_id = client.post("/api/v1/recipes", json=_payload()).json()["id"]
    summary = client.get(f"/api/v1/recipes/{recipe_id}/substrate-summary").json()
    rows = {row["substrate_id"]: row for row in summary}
    assert "inulin_fructan" in rows
    assert rows["inulin_fructan"]["from_food_names"] == ["Garlic (fresh)"]
    assert rows["inulin_fructan"]["is_prebiotic"] is True


def test_an_empty_recipe_is_refused_with_a_plain_english_message(client):
    response = client.post("/api/v1/recipes", json=_payload(ingredients=[]))
    assert response.status_code == 422
    assert response.json()["detail"] == "Add at least one ingredient to this recipe."


def test_an_unknown_food_is_refused(client):
    response = client.post("/api/v1/recipes", json=_payload(
        ingredients=[{"food_id": "unicorn_tears", "amount_g": 1.0, "order": 1}]
    ))
    assert response.status_code == 422
    assert "unicorn_tears" in response.json()["detail"]


def test_a_negative_amount_is_refused_by_the_schema(client):
    response = client.post("/api/v1/recipes", json=_payload(
        ingredients=[{"food_id": "olive_oil", "amount_g": -5.0, "order": 1}]
    ))
    assert response.status_code == 422


def test_updating_an_unknown_recipe_is_404(client):
    assert client.put("/api/v1/recipes/nope", json=_payload()).status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/api/test_recipes.py -q`

- [ ] **Step 3: Write the implementation**

```python
"""Recipe CRUD and the recipe builder's live substrate summary."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from foodbrew.api.deps import get_conn
from foodbrew.api.schemas import RecipeIn, RecipeOut, SubstrateRowOut
from foodbrew.engine.views import substrate_summary
from foodbrew.store import recipes as recipes_store
from foodbrew.store.reference import load_catalog

router = APIRouter(tags=["recipes"])


def _out(stored) -> dict:
    return {
        "id": stored.id, "name": stored.name, "notes": stored.notes,
        "created_at": stored.created_at,
        "ingredients": [
            {"food_id": i.food_id, "amount_g": i.amount_g, "order": i.order}
            for i in stored.ingredients
        ],
    }


@router.get("/recipes", response_model=list[RecipeOut])
def list_recipes(conn: sqlite3.Connection = Depends(get_conn)):
    return [_out(r) for r in recipes_store.list_all(conn)]


@router.post("/recipes", response_model=RecipeOut, status_code=201)
def create_recipe(payload: RecipeIn, conn: sqlite3.Connection = Depends(get_conn)):
    recipe_id = recipes_store.create(
        conn, name=payload.name, notes=payload.notes,
        ingredients=[i.model_dump() for i in payload.ingredients],
    )
    return _out(recipes_store.get(conn, recipe_id))


@router.get("/recipes/{recipe_id}", response_model=RecipeOut)
def get_recipe(recipe_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    stored = recipes_store.get(conn, recipe_id)
    if stored is None:
        raise HTTPException(status_code=404, detail=f"No recipe '{recipe_id}'.")
    return _out(stored)


@router.put("/recipes/{recipe_id}", response_model=RecipeOut)
def update_recipe(
    recipe_id: str, payload: RecipeIn, conn: sqlite3.Connection = Depends(get_conn)
):
    if recipes_store.get(conn, recipe_id) is None:
        raise HTTPException(status_code=404, detail=f"No recipe '{recipe_id}'.")
    recipes_store.update(
        conn, recipe_id, name=payload.name, notes=payload.notes,
        ingredients=[i.model_dump() for i in payload.ingredients],
    )
    return _out(recipes_store.get(conn, recipe_id))


@router.get("/recipes/{recipe_id}/substrate-summary", response_model=list[SubstrateRowOut])
def recipe_substrate_summary(recipe_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    stored = recipes_store.get(conn, recipe_id)
    if stored is None:
        raise HTTPException(status_code=404, detail=f"No recipe '{recipe_id}'.")
    catalog = load_catalog(conn)
    rows = substrate_summary(stored.ingredients, catalog.foods, catalog.substrates)
    return [SubstrateRowOut.of(row) for row in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/api/test_recipes.py -q`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/api/routers/recipes.py tests/api/test_recipes.py
git commit -m "feat(api): recipe CRUD and live substrate summary"
```

---

## Task 17: Formulations router

**Files:**
- Create: `src/foodbrew/api/routers/formulations.py`
- Test: `tests/api/test_formulations.py`

- [ ] **Step 1: Write the failing test**

`tests/api/test_formulations.py`:

```python
def _payload(recipe_id, **overrides):
    body = {
        "recipe_id": recipe_id, "format": "premixed_wet",
        "target_trigger_food_ids": ["milk"], "application_food_ids": ["romaine"],
        "dwell_profile": None,
        "enzymes": [{"enzyme_id": "lactase_fungal_acid", "dose": 9000.0, "phase": "wet"}],
        "serving_size_g": 30.0, "measured_ph": 3.0,
        "process_steps": [{"order": 1, "label": "whisk", "is_heat": False}],
        "enzyme_addition_index": 1,
    }
    body.update(overrides)
    return body


def test_create_and_read_a_formulation(client, vinaigrette):
    created = client.post("/api/v1/formulations", json=_payload(vinaigrette["recipe_id"]))
    assert created.status_code == 201
    body = created.json()
    assert body["measured_ph"] == {
        "value": 3.0, "status": "user_provided", "source": body["measured_ph"]["source"]
    }
    fetched = client.get(f"/api/v1/formulations/{body['id']}").json()
    assert fetched["enzymes"][0]["enzyme_id"] == "lactase_fungal_acid"


def test_proposed_enzymes_cover_the_selected_trigger_foods(client, vinaigrette):
    proposed = client.get(
        "/api/v1/proposed-enzymes",
        params={"trigger_food_ids": ["milk"], "format": "dry_sachet"},
    ).json()
    assert any(s["enzyme_id"].startswith("lactase") for s in proposed)
    assert all(s["phase"] == "dry" for s in proposed)


def test_no_enzyme_is_ever_proposed_for_a_polyol_food(client):
    """Spec §6.2 R14 — polyols get a stated gap, never a suggested enzyme."""
    foods = client.get("/api/v1/foods", params={"role": "trigger"}).json()
    substrates = {s["id"]: s for s in client.get("/api/v1/substrates").json()}
    polyol_foods = [
        f["id"] for f in foods
        if any(substrates[s]["no_commercial_enzyme"] for s in f["contains_substrate_ids"])
    ]
    assert polyol_foods
    proposed = client.get(
        "/api/v1/proposed-enzymes",
        params={"trigger_food_ids": polyol_foods, "format": "dry_sachet"},
    ).json()
    enzymes = {e["id"]: e for e in client.get("/api/v1/enzymes").json()}
    for selection in proposed:
        substrate_id = enzymes[selection["enzyme_id"]]["substrate_id"]
        assert substrates[substrate_id]["no_commercial_enzyme"] is False


def test_zero_enzymes_and_zero_trigger_foods_is_refused(client, vinaigrette):
    response = client.post("/api/v1/formulations", json=_payload(
        vinaigrette["recipe_id"], enzymes=[], target_trigger_food_ids=[]
    ))
    assert response.status_code == 422
    assert "trigger food or enzyme" in response.json()["detail"]


def test_an_unknown_enzyme_is_refused(client, vinaigrette):
    response = client.post("/api/v1/formulations", json=_payload(
        vinaigrette["recipe_id"], enzymes=[{"enzyme_id": "nope", "phase": "dry"}]
    ))
    assert response.status_code == 422


def test_an_out_of_range_ph_is_refused_by_the_schema(client, vinaigrette):
    response = client.post("/api/v1/formulations", json=_payload(
        vinaigrette["recipe_id"], measured_ph=99.0
    ))
    assert response.status_code == 422


def test_an_unknown_formulation_is_404(client):
    assert client.get("/api/v1/formulations/nope").status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/api/test_formulations.py -q`

- [ ] **Step 3: Write the implementation**

```python
"""Formulation setup (§10 screen 3), including the proposed enzyme set."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from foodbrew.api.deps import get_conn
from foodbrew.api.schemas import (
    FormulationIn,
    FormulationOut,
    ProcessStepIn,
    SelectedEnzymeIn,
    TrackedOut,
)
from foodbrew.engine import ValidationRejection
from foodbrew.engine.selection import propose_enzymes
from foodbrew.engine.types import Format
from foodbrew.store import formulations as store
from foodbrew.store.reference import load_catalog

router = APIRouter(tags=["formulations"])


def _out(formulation, recipe_id: str) -> dict:
    return {
        "id": formulation.id, "recipe_id": recipe_id, "format": str(formulation.format),
        "target_trigger_food_ids": list(formulation.target_trigger_food_ids),
        "application_food_ids": list(formulation.application_food_ids),
        "dwell_profile": str(formulation.dwell_profile) if formulation.dwell_profile else None,
        "enzymes": [
            SelectedEnzymeIn(
                enzyme_id=s.enzyme_id, dose=s.dose, phase=str(s.phase),
                encapsulated=s.encapsulated, source_choice=s.source_choice,
            )
            for s in formulation.enzymes
        ],
        "serving_size_g": formulation.serving_size_g,
        "measured_ph": TrackedOut.of(formulation.measured_ph),
        "process_steps": [
            ProcessStepIn(order=s.order, label=s.label, is_heat=s.is_heat)
            for s in formulation.process_steps
        ],
        "enzyme_addition_index": formulation.enzyme_addition_index,
        "parent_formulation_id": formulation.parent_formulation_id,
    }


@router.post("/formulations", response_model=FormulationOut, status_code=201)
def create_formulation(payload: FormulationIn, conn: sqlite3.Connection = Depends(get_conn)):
    formulation_id = store.create(
        conn,
        recipe_id=payload.recipe_id, format=payload.format,
        target_trigger_food_ids=payload.target_trigger_food_ids,
        application_food_ids=payload.application_food_ids,
        dwell_profile=payload.dwell_profile,
        enzymes=[e.model_dump() for e in payload.enzymes],
        serving_size_g=payload.serving_size_g, measured_ph=payload.measured_ph,
        process_steps=[s.model_dump() for s in payload.process_steps],
        enzyme_addition_index=payload.enzyme_addition_index,
        parent_formulation_id=payload.parent_formulation_id,
    )
    return _out(store.get(conn, formulation_id), payload.recipe_id)


@router.get("/formulations/{formulation_id}", response_model=FormulationOut)
def get_formulation(formulation_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    formulation = store.get(conn, formulation_id)
    if formulation is None:
        raise HTTPException(status_code=404, detail=f"No formulation '{formulation_id}'.")
    return _out(formulation, store.recipe_id_for(conn, formulation_id))


@router.get("/proposed-enzymes", response_model=list[SelectedEnzymeIn])
def proposed_enzymes(
    trigger_food_ids: list[str] = Query(default_factory=list),
    format: str = Query(default="dry_sachet"),
    conn: sqlite3.Connection = Depends(get_conn),
):
    """Workflow A step 5. A proposal the founder edits — never a locked decision."""
    try:
        fmt = Format(format)
    except ValueError as exc:
        raise ValidationRejection(f"Unknown format '{format}'.") from exc
    catalog = load_catalog(conn)
    return [
        SelectedEnzymeIn(
            enzyme_id=s.enzyme_id, dose=s.dose, phase=str(s.phase),
            encapsulated=s.encapsulated, source_choice=s.source_choice,
        )
        for s in propose_enzymes(
            trigger_food_ids=tuple(trigger_food_ids), format=fmt,
            foods=catalog.foods, substrates=catalog.substrates, enzymes=catalog.enzymes,
        )
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/api/test_formulations.py -q`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/api/routers/formulations.py tests/api/test_formulations.py
git commit -m "feat(api): formulation setup and the proposed enzyme set"
```

---

## Task 18: Evaluations router

**Files:**
- Create: `src/foodbrew/api/routers/evaluations.py`
- Test: `tests/api/test_evaluations.py`

- [ ] **Step 1: Write the failing test**

`tests/api/test_evaluations.py`:

```python
def test_evaluating_the_vinaigrette_reproduces_golden_fixture_a(client, vinaigrette):
    """Spec §13 (a): wet, pH 3.0, fungal lactase → RED via R1, R4 AMBER present."""
    body = client.post(
        f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
    ).json()
    assert body["headline"] == "RED"
    assert any(f["rule_id"] == "R1" and f["verdict"] == "red" for f in body["blockers"])
    assert any(f["rule_id"] == "R4" and f["verdict"] == "amber" for f in body["cautions"])


def test_the_four_finding_groups_are_present_and_titled(client, vinaigrette):
    body = client.post(
        f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
    ).json()
    for group in ("blockers", "data_gaps", "cautions", "advisories"):
        assert group in body
    assert all(f["rule_title"] for f in body["findings"])
    assert all(f["advisory"] for f in body["advisories"])


def test_advisory_findings_never_appear_in_the_headline_groups(client, vinaigrette):
    """Spec §6.4 — R8, R9, R10, R12, R16 cannot set the flag."""
    body = client.post(
        f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
    ).json()
    headline_ids = {
        f["rule_id"] for group in ("blockers", "data_gaps", "cautions") for f in body[group]
    }
    assert not (headline_ids & {"R8", "R9", "R10", "R16"})


def test_the_envelope_has_all_three_occasions(client, vinaigrette):
    body = client.post(
        f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
    ).json()
    assert set(body["envelope"]) == {"immediate", "packed", "marinade"}


def test_the_gi_strip_lands_lactase_in_the_fed_stomach(client, vinaigrette):
    body = client.post(
        f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
    ).json()
    lane = body["gi_strip"][0]
    regions = {r["region_id"]: r for r in lane["regions"]}
    assert regions["stomach_fed"]["active"] is True
    assert regions["mouth"]["dormant"] is True and regions["mouth"]["active"] is False


def test_dose_cards_expose_the_threshold_without_guessing(client, vinaigrette):
    body = client.post(
        f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
    ).json()
    card = body["dose_cards"][0]
    assert card["dose"] == 9000.0
    assert card["dose_evidence_threshold"]["status"] == "unconfirmed"
    assert card["meets_threshold"] is None


def test_reading_an_evaluation_returns_the_stored_result(client, vinaigrette, conn):
    created = client.post(
        f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
    ).json()
    conn.execute(
        "UPDATE enzyme SET ph_shelf_stable_min = 1.0, ph_shelf_stable_min_status = 'confirmed'"
        " WHERE id = 'lactase_fungal_acid'"
    )
    conn.commit()
    reread = client.get(f"/api/v1/evaluations/{created['id']}").json()
    assert reread["headline"] == created["headline"]
    assert [f["message"] for f in reread["findings"]] == [
        f["message"] for f in created["findings"]
    ]


def test_evaluations_are_listed_newest_first(client, vinaigrette):
    first = client.post(
        f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
    ).json()
    second = client.post(
        f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
    ).json()
    listed = client.get(
        f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluations"
    ).json()
    assert [e["id"] for e in listed] == [second["id"], first["id"]]
    assert client.get("/api/v1/evaluations").json()[0]["id"] == second["id"]


def test_the_snapshot_is_retrievable_for_audit(client, vinaigrette):
    created = client.post(
        f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
    ).json()
    snapshot = client.get(f"/api/v1/evaluations/{created['id']}/snapshot").json()
    assert snapshot["formulation"]["measured_ph"]["value"] == 3.0
    assert set(snapshot["enzymes"]) == {"lactase_fungal_acid"}


def test_evaluating_an_unknown_formulation_is_422_with_no_row_written(client, conn):
    response = client.post("/api/v1/formulations/nope/evaluate")
    assert response.status_code == 422
    assert conn.execute("SELECT COUNT(*) AS n FROM evaluation").fetchone()["n"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/api/test_evaluations.py -q`

- [ ] **Step 3: Write the implementation**

```python
"""Running and reading evaluations (§10 screen 4).

Running writes a new row; reading returns the stored one, with derived views
rebuilt from that evaluation's own snapshot rather than from current records,
so an evaluation looks exactly as it did when it ran (plan decision #5).
"""

from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from foodbrew.api.deps import get_conn
from foodbrew.api.schemas import (
    DoseCardOut,
    EvaluationOut,
    EvaluationSummaryOut,
    FindingOut,
    GiLaneOut,
    RegionStateOut,
    TrackedOut,
)
from foodbrew.engine.views import RULE_TITLES, dose_cards, gi_strip
from foodbrew.store import evaluations as store
from foodbrew.store.snapshot import context_from_snapshot

router = APIRouter(tags=["evaluations"])


def _finding(f) -> FindingOut:
    return FindingOut(
        rule_id=f.rule_id, rule_title=RULE_TITLES.get(f.rule_id, f.rule_id),
        verdict=str(f.verdict), advisory=f.advisory, message=f.message,
        evidence=dict(f.evidence), enzyme_id=f.enzyme_id, food_id=f.food_id,
    )


def _out(stored) -> EvaluationOut:
    ctx = context_from_snapshot(stored.input_snapshot_json)
    return EvaluationOut(
        id=stored.id, formulation_id=stored.formulation_id,
        engine_version=stored.engine_version, created_at=stored.created_at,
        headline=stored.display, overall=str(stored.overall),
        findings=[_finding(f) for f in stored.findings],
        blockers=[_finding(f) for f in stored.blockers],
        data_gaps=[_finding(f) for f in stored.data_gaps],
        cautions=[_finding(f) for f in stored.cautions],
        advisories=[_finding(f) for f in stored.advisories],
        envelope={str(k): str(v) for k, v in stored.envelope.items()},
        gi_strip=[
            GiLaneOut(
                enzyme_id=lane.enzyme_id, enzyme_name=lane.enzyme_name,
                deadline=str(lane.deadline),
                ph_min=TrackedOut.of(lane.ph_min), ph_max=TrackedOut.of(lane.ph_max),
                regions=[RegionStateOut(**vars(r)) for r in lane.regions],
            )
            for lane in gi_strip(ctx)
        ],
        dose_cards=[
            DoseCardOut(
                enzyme_id=c.enzyme_id, enzyme_name=c.enzyme_name,
                substrate_id=c.substrate_id, dose=c.dose, dose_unit=c.dose_unit,
                dose_min=TrackedOut.of(c.dose_min), dose_max=TrackedOut.of(c.dose_max),
                dose_evidence_threshold=TrackedOut.of(c.dose_evidence_threshold),
                substrate_load=TrackedOut.of(c.substrate_load),
                meets_threshold=c.meets_threshold, ratio=c.ratio,
                above_benchmark_max=c.above_benchmark_max,
            )
            for c in dose_cards(ctx)
        ],
    )


def _summary(stored) -> EvaluationSummaryOut:
    return EvaluationSummaryOut(
        id=stored.id, formulation_id=stored.formulation_id,
        created_at=stored.created_at, headline=stored.display,
        engine_version=stored.engine_version,
    )


@router.post(
    "/formulations/{formulation_id}/evaluate", response_model=EvaluationOut, status_code=201
)
def run_evaluation(formulation_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    return _out(store.run(conn, formulation_id))


@router.get("/formulations/{formulation_id}/evaluations", response_model=list[EvaluationSummaryOut])
def list_for_formulation(formulation_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    return [_summary(e) for e in store.list_for_formulation(conn, formulation_id)]


@router.get("/evaluations", response_model=list[EvaluationSummaryOut])
def list_recent(limit: int = 10, conn: sqlite3.Connection = Depends(get_conn)):
    return [_summary(e) for e in store.list_recent(conn, limit)]


@router.get("/evaluations/{evaluation_id}", response_model=EvaluationOut)
def get_evaluation(evaluation_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    stored = store.get(conn, evaluation_id)
    if stored is None:
        raise HTTPException(status_code=404, detail=f"No evaluation '{evaluation_id}'.")
    return _out(stored)


@router.get("/evaluations/{evaluation_id}/snapshot")
def get_snapshot(evaluation_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    """The frozen inputs, for audit and for M3's compare view."""
    stored = store.get(conn, evaluation_id)
    if stored is None:
        raise HTTPException(status_code=404, detail=f"No evaluation '{evaluation_id}'.")
    return json.loads(stored.input_snapshot_json)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/api/ -q`
Expected: every API test passes, including `test_app.py` now that all four routers exist.

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/api/routers/evaluations.py tests/api/test_evaluations.py
git commit -m "feat(api): run and read evaluations with derived verdict views"
```

---

## Task 19: API contract tests — truth labels, language, and layering

The three properties that must hold for every endpoint, asserted once so a future endpoint cannot quietly break them.

**Files:**
- Test: `tests/api/test_contracts.py`

- [ ] **Step 1: Write the test**

```python
"""Cross-cutting contracts. These are the API-layer equivalents of M1's
tests/engine/test_purity.py: cheap, global, and hard to violate by accident.
"""

import pathlib

import pytest

from foodbrew.api import schemas

#: Spec §10 — prohibited in engine output, report, and anything the founder reads.
PROHIBITED = ("safe", "validated", "guaranteed", "clinically proven", "proven", "demonstrated")

TRACKED_KEYS = {"value", "status", "source"}
VALID_STATUSES = {"confirmed", "unconfirmed", "user_provided", "calculated", "observed"}
SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "foodbrew"


def _tracked_objects(node):
    """Yield every dict that looks like a Tracked triple, at any depth."""
    if isinstance(node, dict):
        if set(node) == TRACKED_KEYS:
            yield node
        for value in node.values():
            yield from _tracked_objects(value)
    elif isinstance(node, list):
        for item in node:
            yield from _tracked_objects(item)


@pytest.fixture
def evaluated(client, vinaigrette):
    return client.post(
        f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
    ).json()


def test_every_tracked_value_on_the_wire_carries_a_valid_status(client, evaluated):
    payloads = [
        evaluated,
        client.get("/api/v1/enzymes").json(),
        client.get("/api/v1/foods").json(),
    ]
    seen = 0
    for payload in payloads:
        for tracked in _tracked_objects(payload):
            assert tracked["status"] in VALID_STATUSES
            seen += 1
    assert seen > 50, "the sweep found suspiciously few tracked values"


def test_no_numeric_enzyme_field_is_serialized_bare(client):
    """Plan decision #7 — a bare float would strand the number from its label."""
    enzyme = next(e for e in client.get("/api/v1/enzymes").json() if e["id"] == "lactase_fungal_acid")
    for field in ("ph_min", "ph_max", "ph_shelf_stable_min", "dose_min", "is_gras"):
        assert isinstance(enzyme[field], dict)
        assert set(enzyme[field]) == TRACKED_KEYS


def test_no_prohibited_word_appears_in_any_engine_or_api_message(evaluated):
    for finding in evaluated["findings"]:
        lowered = finding["message"].lower()
        for word in PROHIBITED:
            assert word not in lowered, f"{finding['rule_id']}: '{word}' in message"


def test_no_prohibited_word_appears_in_api_source_copy():
    """Catches a banned word typed into a docstring, error string, or title."""
    for path in (SRC / "api").rglob("*.py"):
        text = path.read_text(encoding="utf-8").lower()
        for word in PROHIBITED:
            assert word not in text, f"{path.name}: '{word}'"


def test_the_store_layer_never_imports_the_api_layer():
    for path in (SRC / "store").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "foodbrew.api" not in text, f"{path.name} imports the API layer"
        assert "fastapi" not in text, f"{path.name} imports FastAPI"


def test_the_engine_never_imports_the_store_or_api_layers():
    for path in (SRC / "engine").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for forbidden in ("foodbrew.store", "foodbrew.api", "foodbrew.db", "fastapi", "sqlite3"):
            assert forbidden not in text, f"{path.name} imports {forbidden}"


def test_no_schema_lets_a_client_choose_a_truth_label():
    for name in dir(schemas):
        model = getattr(schemas, name)
        fields = getattr(model, "model_fields", None)
        if not fields or name.endswith("Out") or name == "TrackedOut":
            continue
        assert not any("status" in f for f in fields), f"{name} exposes a status field"
```

- [ ] **Step 2: Run the test**

Run: `.venv/bin/pytest tests/api/test_contracts.py -q`
Expected: 7 passed. If `test_no_prohibited_word_appears_in_api_source_copy` fails on a legitimate word — "safe" inside "thread-safe", for instance — reword the comment. The list is deliberately blunt: §10 makes these words prohibited in what the founder reads, and the cheapest way to keep them out is to keep them out of the file.

- [ ] **Step 3: Commit**

```bash
git add tests/api/test_contracts.py
git commit -m "test(api): assert truth-label, language, and layering contracts"
```

---

## Task 20: Reproducibility across the database boundary

Spec §4's guarantee, asserted at the level the founder actually experiences it.

**Files:**
- Test: `tests/api/test_reproducibility.py`

- [ ] **Step 1: Write the test**

```python
"""Spec §4: an evaluation is a frozen record. These are the three ways that can
break in a system with a database, tested end to end through HTTP.
"""


def _evaluate(client, formulation_id):
    return client.post(f"/api/v1/formulations/{formulation_id}/evaluate").json()


def test_re_evaluating_unchanged_inputs_produces_an_identical_verdict(client, vinaigrette):
    first = _evaluate(client, vinaigrette["formulation_id"])
    second = _evaluate(client, vinaigrette["formulation_id"])
    assert first["id"] != second["id"]
    assert first["headline"] == second["headline"]
    assert [f["message"] for f in first["findings"]] == [
        f["message"] for f in second["findings"]
    ]


def test_the_stored_snapshot_is_byte_identical_across_two_runs(client, vinaigrette, conn):
    first = _evaluate(client, vinaigrette["formulation_id"])
    second = _evaluate(client, vinaigrette["formulation_id"])
    rows = {
        r["id"]: r["input_snapshot_json"]
        for r in conn.execute("SELECT id, input_snapshot_json FROM evaluation")
    }
    assert rows[first["id"]] == rows[second["id"]]


def test_editing_an_enzyme_changes_the_next_run_but_not_the_stored_one(client, vinaigrette, conn):
    before = _evaluate(client, vinaigrette["formulation_id"])
    assert before["headline"] == "RED"

    # A supplier confirms a shelf-stable floor below the recipe's pH 3.0, which
    # is exactly the answer §15 question 1 exists to collect.
    conn.execute(
        "UPDATE enzyme SET ph_shelf_stable_min = 2.5,"
        " ph_shelf_stable_min_status = 'confirmed',"
        " ph_shelf_stable_min_source = 'supplier spec' WHERE id = 'lactase_fungal_acid'"
    )
    conn.commit()

    after = _evaluate(client, vinaigrette["formulation_id"])
    reread = client.get(f"/api/v1/evaluations/{before['id']}").json()

    assert after["headline"] != before["headline"]
    assert reread["headline"] == before["headline"]
    assert [f["message"] for f in reread["findings"]] == [
        f["message"] for f in before["findings"]
    ]


def test_a_stored_evaluation_survives_editing_the_formulation_itself(client, vinaigrette, conn):
    before = _evaluate(client, vinaigrette["formulation_id"])
    conn.execute(
        "UPDATE formulation SET measured_ph = 6.0 WHERE id = ?",
        (vinaigrette["formulation_id"],),
    )
    conn.commit()
    reread = client.get(f"/api/v1/evaluations/{before['id']}").json()
    snapshot = client.get(f"/api/v1/evaluations/{before['id']}/snapshot").json()
    assert reread["headline"] == before["headline"]
    assert snapshot["formulation"]["measured_ph"]["value"] == 3.0
```

- [ ] **Step 2: Run the test**

Run: `.venv/bin/pytest tests/api/test_reproducibility.py -q`
Expected: 4 passed. `test_editing_an_enzyme_changes_the_next_run_but_not_the_stored_one` is the load-bearing one — it proves both halves of §4 at once, and it is the test M3's stale-evaluation banner will build on.

- [ ] **Step 3: Run the full backend suite and lint**

Run: `.venv/bin/pytest -q && .venv/bin/ruff check src tests`
Expected: everything green, ruff clean.

- [ ] **Step 4: Commit**

```bash
git add tests/api/test_reproducibility.py
git commit -m "test(api): assert evaluation reproducibility and isolation"
```

---

## Task 21: Frontend scaffold and typed API client

**Files:**
- Create: `web/package.json`, `web/tsconfig.json`, `web/vite.config.ts`, `web/index.html`, `web/.gitignore`
- Create: `web/src/main.tsx`, `web/src/App.tsx`, `web/src/styles.css`
- Create: `web/src/api/types.ts`, `web/src/api/client.ts`

- [ ] **Step 1: Create `web/package.json`**

```json
{
  "name": "foodbrew-web",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "typecheck": "tsc -b --noEmit",
    "e2e": "playwright test"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-router-dom": "^7.0.0"
  },
  "devDependencies": {
    "@playwright/test": "^1.48.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.6.0",
    "vite": "^6.0.0"
  }
}
```

No UI library, no data-fetching library, no state manager. Spec §8 of the superseded doc and §10 of this one both say forms and tables before visual investment; every dependency added here is one the founder's machine has to keep working.

- [ ] **Step 2: Create `web/vite.config.ts`**

```ts
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    // The dev server proxies the API so the browser sees one origin, which is
    // why the backend ships no CORS middleware (plan decision #11).
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  build: { outDir: 'dist' },
})
```

- [ ] **Step 3: Create `web/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noEmit": true,
    "skipLibCheck": true,
    "isolatedModules": true,
    "verbatimModuleSyntax": true
  },
  "include": ["src", "e2e"]
}
```

- [ ] **Step 4: Create `web/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>FoodBrew</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Create `web/src/api/types.ts`**

Mirror the Pydantic models exactly. These are the only place the wire shape is written down on the client, so a schema change breaks the build rather than a screen.

```ts
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
```

- [ ] **Step 6: Create `web/src/api/client.ts`**

```ts
import type {
  Enzyme, Evaluation, EvaluationSummary, Food, Formulation, Recipe,
  SelectedEnzyme, Substrate, SubstrateRow,
} from './types'

/** The API's error shape. A rejected formulation is normal traffic, not a crash. */
export class ApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const body = await response.json()
      // FastAPI reports schema errors as a list; ours are a plain string.
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* keep the status line */
    }
    throw new ApiError(response.status, detail)
  }
  return response.json() as Promise<T>
}

const post = <T,>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

export const api = {
  enzymes: () => request<Enzyme[]>('/enzymes'),
  substrates: () => request<Substrate[]>('/substrates'),
  foods: (role?: 'recipe_ingredient' | 'trigger' | 'application') =>
    request<Food[]>(`/foods${role ? `?role=${role}` : ''}`),
  createFood: (body: unknown) => post<Food>('/foods', body),

  recipes: () => request<Recipe[]>('/recipes'),
  recipe: (id: string) => request<Recipe>(`/recipes/${id}`),
  createRecipe: (body: unknown) => post<Recipe>('/recipes', body),
  updateRecipe: (id: string, body: unknown) =>
    request<Recipe>(`/recipes/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  substrateSummary: (id: string) => request<SubstrateRow[]>(`/recipes/${id}/substrate-summary`),

  createFormulation: (body: unknown) => post<Formulation>('/formulations', body),
  formulation: (id: string) => request<Formulation>(`/formulations/${id}`),
  proposedEnzymes: (triggerFoodIds: string[], format: string) => {
    const params = new URLSearchParams({ format })
    triggerFoodIds.forEach((id) => params.append('trigger_food_ids', id))
    return request<SelectedEnzyme[]>(`/proposed-enzymes?${params}`)
  },

  evaluate: (formulationId: string) =>
    post<Evaluation>(`/formulations/${formulationId}/evaluate`),
  evaluation: (id: string) => request<Evaluation>(`/evaluations/${id}`),
  recentEvaluations: () => request<EvaluationSummary[]>('/evaluations'),
}
```

- [ ] **Step 7: Create `main.tsx`, `App.tsx`, and `styles.css`**

`web/src/main.tsx`:

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import App from './App'
import './styles.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
)
```

`web/src/App.tsx`:

```tsx
import { Link, Route, Routes } from 'react-router-dom'

import FormulationSetup from './screens/FormulationSetup'
import Home from './screens/Home'
import RecipeBuilder from './screens/RecipeBuilder'
import Verdict from './screens/Verdict'

export default function App() {
  return (
    <div className="app">
      <header>
        <Link to="/" className="brand">FoodBrew</Link>
        <nav>
          <Link to="/recipes/new">New recipe</Link>
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/recipes/new" element={<RecipeBuilder />} />
          <Route path="/recipes/:recipeId" element={<RecipeBuilder />} />
          <Route path="/recipes/:recipeId/formulation" element={<FormulationSetup />} />
          <Route path="/evaluations/:evaluationId" element={<Verdict />} />
        </Routes>
      </main>
      <footer>
        Formulation decision support. Not a safety, efficacy, or regulatory determination.
      </footer>
    </div>
  )
}
```

The footer text is §10 screen 8's fixed disclaimer. It sits in the layout rather than on one screen so no route can render without it.

`web/src/styles.css`: plain CSS, no framework. Define at minimum:

```css
:root {
  --red: #b3261e; --amber: #9a6700; --gray: #5c5f66; --green: #1a7f37;
  --line: #d7d9dd; --bg: #ffffff; --muted: #f5f6f7;
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
}
body { margin: 0; color: #1b1c1e; background: var(--bg); }
.app { max-width: 60rem; margin: 0 auto; padding: 1rem; }
header { display: flex; gap: 1rem; align-items: baseline; border-bottom: 1px solid var(--line); }
.brand { font-weight: 700; text-decoration: none; color: inherit; }
footer { margin-top: 3rem; padding-top: 1rem; border-top: 1px solid var(--line);
         color: var(--gray); font-size: 0.85rem; }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; padding: 0.4rem 0.5rem; border-bottom: 1px solid var(--line); }
fieldset { border: 1px solid var(--line); margin: 1rem 0; }
label { display: block; margin: 0.4rem 0; }
.error { color: var(--red); border: 1px solid var(--red); padding: 0.75rem; border-radius: 4px; }
```

- [ ] **Step 8: Create `web/.gitignore`**

```
node_modules/
dist/
test-results/
playwright-report/
```

- [ ] **Step 9: Install and verify**

Run: `cd web && npm install && npm run typecheck`
Expected: no type errors. Screens do not exist yet, so create empty placeholder components (`export default function Home() { return null }`) for the four screens to satisfy the build, and replace them in Tasks 23–26.

- [ ] **Step 10: Commit**

```bash
git add web
git commit -m "chore(web): scaffold vite, react, router, and the typed API client"
```

---

## Task 22: Shared components — truth labels, verdicts, findings

Every screen renders these three things. They are built once, before any screen, so the four headline states and the five truth labels have exactly one implementation.

**Files:**
- Create: `web/src/components/TruthValue.tsx`
- Create: `web/src/components/VerdictBadge.tsx`
- Create: `web/src/components/FindingGroups.tsx`

- [ ] **Step 1: `TruthValue.tsx`**

```tsx
import type { Tracked, TruthLabel } from '../api/types'

/** Spec §5.4 — the closed enum. Anything else is a bug, and shows as one. */
const LABEL_TEXT: Record<TruthLabel, string> = {
  confirmed: 'confirmed',
  unconfirmed: 'not confirmed',
  user_provided: 'you entered this',
  calculated: 'calculated',
  observed: 'observed in a trial',
}

export function TruthValue({
  tracked, unit = '', missingText = 'not confirmed',
}: {
  tracked: Tracked
  unit?: string
  missingText?: string
}) {
  const hasValue = tracked.value !== null && tracked.value !== undefined
  const shown =
    typeof tracked.value === 'boolean'
      ? tracked.value ? 'yes' : 'no'
      : hasValue ? String(tracked.value) : missingText

  return (
    <span className={`truth truth--${tracked.status}`} title={tracked.source || undefined}>
      {shown}{hasValue && unit ? ` ${unit}` : ''}
      <small className="truth__label"> ({LABEL_TEXT[tracked.status]})</small>
    </span>
  )
}
```

The `title` attribute carries the `source` string, so §1.3.2's "every number traces to a database record" is one hover away on every number the founder sees. An unconfirmed value renders its label rather than hiding — a blank cell would read as zero.

- [ ] **Step 2: `VerdictBadge.tsx`**

```tsx
import type { Headline, Verdict } from '../api/types'

/** Spec §6.4 — the one-to-one headline mapping, and what each state means. */
const HEADLINE_TEXT: Record<Headline, string> = {
  RED: 'RED — blocker',
  GRAY: 'GRAY — gaps block a verdict',
  AMBER: 'AMBER — caution',
  GREEN: 'GREEN — clear on the rules evaluated',
}

const VERDICT_TEXT: Record<Verdict, string> = {
  red: 'blocker',
  cannot_assess: 'cannot assess',
  amber: 'caution',
  pass: 'clear',
}

export function HeadlineBadge({ headline }: { headline: Headline }) {
  return (
    <p className={`headline headline--${headline.toLowerCase()}`} data-testid="headline">
      {HEADLINE_TEXT[headline]}
    </p>
  )
}

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  return <span className={`verdict verdict--${verdict}`}>{VERDICT_TEXT[verdict]}</span>
}
```

`GRAY` reads "gaps block a verdict", never "unknown" or "pending": §6.4 is explicit that a GRAY headline means the tool is declining to judge, and the wording has to say so.

- [ ] **Step 3: `FindingGroups.tsx`**

```tsx
import type { Finding } from '../api/types'
import { VerdictBadge } from './VerdictBadge'

function Group({ title, blurb, findings }: {
  title: string; blurb: string; findings: Finding[]
}) {
  if (findings.length === 0) return null
  return (
    <section className="finding-group" data-testid={`group-${title.toLowerCase().replace(/\s/g, '-')}`}>
      <h3>{title}</h3>
      <p className="blurb">{blurb}</p>
      <ul>
        {findings.map((f, i) => (
          <li key={`${f.rule_id}-${f.enzyme_id ?? ''}-${f.food_id ?? ''}-${i}`}>
            <strong>{f.rule_id} — {f.rule_title}</strong> <VerdictBadge verdict={f.verdict} />
            <div>{f.message}</div>
          </li>
        ))}
      </ul>
    </section>
  )
}

export function FindingGroups({
  blockers, dataGaps, cautions, advisories,
}: {
  blockers: Finding[]; dataGaps: Finding[]; cautions: Finding[]; advisories: Finding[]
}) {
  return (
    <>
      <Group title="Blockers" blurb="These stop the formulation as specified."
             findings={blockers} />
      <Group title="Data gaps" blurb="Missing values. Fill these in and re-run to get a verdict."
             findings={dataGaps} />
      <Group title="Cautions" blurb="Not blockers, but they change over time or with use."
             findings={cautions} />
      <Group title="Advisory" blurb="Notes that never change the headline — your call to make."
             findings={advisories} />
    </>
  )
}
```

The four group names come straight from §10 screen 4. The advisory blurb states §6.4's rule in plain words, because the founder needs to know why an amber advisory did not turn the headline amber.

- [ ] **Step 4: Typecheck**

Run: `cd web && npm run typecheck`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add web/src/components
git commit -m "feat(web): add truth-label, verdict, and finding-group components"
```

---

## Task 23: Home screen

**Files:**
- Create: `web/src/screens/Home.tsx` (replacing the placeholder)

- [ ] **Step 1: Write the screen**

```tsx
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api/client'
import type { EvaluationSummary, Recipe } from '../api/types'

export default function Home() {
  const [recipes, setRecipes] = useState<Recipe[]>([])
  const [evaluations, setEvaluations] = useState<EvaluationSummary[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.recipes(), api.recentEvaluations()])
      .then(([r, e]) => { setRecipes(r); setEvaluations(e) })
      .catch((err) => setError(err.message))
  }, [])

  if (error) return <p className="error">{error}</p>

  return (
    <>
      <h1>Your recipes</h1>
      {recipes.length === 0 ? (
        <p>Nothing yet. <Link to="/recipes/new">Build your first recipe</Link>.</p>
      ) : (
        <table>
          <thead><tr><th>Recipe</th><th>Ingredients</th><th>Created</th></tr></thead>
          <tbody>
            {recipes.map((r) => (
              <tr key={r.id}>
                <td><Link to={`/recipes/${r.id}`}>{r.name}</Link></td>
                <td>{r.ingredients.length}</td>
                <td>{r.created_at.slice(0, 10)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h2>Recent verdicts</h2>
      {evaluations.length === 0 ? (
        <p>No formulation has been evaluated yet.</p>
      ) : (
        <table>
          <thead><tr><th>Verdict</th><th>Run</th><th>Engine</th></tr></thead>
          <tbody>
            {evaluations.map((e) => (
              <tr key={e.id}>
                <td>
                  <Link to={`/evaluations/${e.id}`} className={`headline--${e.headline.toLowerCase()}`}>
                    {e.headline}
                  </Link>
                </td>
                <td>{e.created_at.slice(0, 16).replace('T', ' ')}</td>
                <td>{e.engine_version}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  )
}
```

§10 screen 1 also lists active trials. Those arrive in M4 with the tables that hold them; the section is deliberately absent rather than stubbed, so nothing renders an empty promise.

- [ ] **Step 2: Verify against a running server**

Run, in two terminals:
```bash
.venv/bin/uvicorn foodbrew.api.app:app --reload
```
```bash
cd web && npm run dev
```
Open the printed Vite URL. Expected: "Nothing yet" on a fresh database, no console errors.

- [ ] **Step 3: Commit**

```bash
git add web/src/screens/Home.tsx
git commit -m "feat(web): add the home screen"
```

---

## Task 24: Recipe builder screen

Spec §10 screen 2: food picker with amounts, custom-food creation, live substrate summary, optional measured pH.

**Files:**
- Create: `web/src/screens/RecipeBuilder.tsx`

- [ ] **Step 1: Write the screen**

```tsx
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { api } from '../api/client'
import { TruthValue } from '../components/TruthValue'
import type { Food, Ingredient, SubstrateRow } from '../api/types'

interface CustomFoodDraft {
  name: string
  category: string
  ph: string
  water_content_pct: string
  contains_substrate_ids: string[]
}

const EMPTY_CUSTOM: CustomFoodDraft = {
  name: '', category: '', ph: '', water_content_pct: '', contains_substrate_ids: [],
}

export default function RecipeBuilder() {
  const { recipeId } = useParams()
  const navigate = useNavigate()

  const [foods, setFoods] = useState<Food[]>([])
  const [name, setName] = useState('')
  const [notes, setNotes] = useState('')
  const [ingredients, setIngredients] = useState<Ingredient[]>([])
  const [summary, setSummary] = useState<SubstrateRow[]>([])
  const [savedId, setSavedId] = useState<string | null>(recipeId ?? null)
  const [custom, setCustom] = useState<CustomFoodDraft | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { api.foods('recipe_ingredient').then(setFoods).catch((e) => setError(e.message)) }, [])

  useEffect(() => {
    if (!recipeId) return
    api.recipe(recipeId).then((r) => {
      setName(r.name); setNotes(r.notes); setIngredients(r.ingredients); setSavedId(r.id)
    }).catch((e) => setError(e.message))
  }, [recipeId])

  useEffect(() => {
    if (!savedId) return
    api.substrateSummary(savedId).then(setSummary).catch(() => setSummary([]))
  }, [savedId, ingredients])

  const byId = new Map(foods.map((f) => [f.id, f]))
  const total = ingredients.reduce((sum, i) => sum + (i.amount_g || 0), 0)

  function addIngredient(foodId: string) {
    if (!foodId || ingredients.some((i) => i.food_id === foodId)) return
    setIngredients([...ingredients, { food_id: foodId, amount_g: 0, order: ingredients.length + 1 }])
  }

  async function save() {
    setError(null)
    const body = { name, notes, ingredients }
    try {
      const saved = savedId
        ? await api.updateRecipe(savedId, body)
        : await api.createRecipe(body)
      setSavedId(saved.id)
      setSummary(await api.substrateSummary(saved.id))
    } catch (e) { setError((e as Error).message) }
  }

  async function saveCustomFood() {
    if (!custom) return
    setError(null)
    try {
      const created = await api.createFood({
        name: custom.name,
        category: custom.category,
        is_recipe_ingredient: true,
        ph: custom.ph === '' ? null : Number(custom.ph),
        water_content_pct:
          custom.water_content_pct === '' ? null : Number(custom.water_content_pct),
        contains_substrate_ids: custom.contains_substrate_ids,
      })
      setFoods([...foods, created])
      setCustom(null)
      addIngredient(created.id)
    } catch (e) { setError((e as Error).message) }
  }

  return (
    <>
      <h1>{savedId ? 'Edit recipe' : 'New recipe'}</h1>
      {error && <p className="error">{error}</p>}

      <label>Name
        <input value={name} onChange={(e) => setName(e.target.value)} data-testid="recipe-name" />
      </label>
      <label>Notes
        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
      </label>

      <fieldset>
        <legend>Ingredients</legend>
        <select
          defaultValue=""
          onChange={(e) => { addIngredient(e.target.value); e.currentTarget.value = '' }}
          data-testid="food-picker"
        >
          <option value="" disabled>Add an ingredient…</option>
          {foods.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
        </select>
        <button type="button" onClick={() => setCustom(EMPTY_CUSTOM)}>
          Add a food that isn't listed
        </button>

        <table>
          <thead>
            <tr><th>Food</th><th>Grams</th><th>pH</th><th>Water</th><th /></tr>
          </thead>
          <tbody>
            {ingredients.map((ing, index) => {
              const food = byId.get(ing.food_id)
              return (
                <tr key={ing.food_id}>
                  <td>{food?.name ?? ing.food_id}</td>
                  <td>
                    <input
                      type="number" min={0} value={ing.amount_g}
                      data-testid={`amount-${ing.food_id}`}
                      onChange={(e) => {
                        const next = [...ingredients]
                        next[index] = { ...ing, amount_g: Number(e.target.value) }
                        setIngredients(next)
                      }}
                    />
                  </td>
                  <td>{food && <TruthValue tracked={food.ph} />}</td>
                  <td>{food && <TruthValue tracked={food.water_content_pct} unit="%" />}</td>
                  <td>
                    <button type="button"
                            onClick={() => setIngredients(ingredients.filter((x) => x !== ing))}>
                      Remove
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <p>Batch total: {total} g</p>
      </fieldset>

      {custom && (
        <fieldset>
          <legend>New food — everything you enter is stored as your own value</legend>
          <label>Name
            <input value={custom.name} onChange={(e) => setCustom({ ...custom, name: e.target.value })} />
          </label>
          <label>Category
            <input value={custom.category}
                   onChange={(e) => setCustom({ ...custom, category: e.target.value })} />
          </label>
          <label>pH (leave blank if you have not measured it)
            <input type="number" step="0.1" value={custom.ph}
                   onChange={(e) => setCustom({ ...custom, ph: e.target.value })} />
          </label>
          <label>Water content %
            <input type="number" step="1" value={custom.water_content_pct}
                   onChange={(e) => setCustom({ ...custom, water_content_pct: e.target.value })} />
          </label>
          <button type="button" onClick={saveCustomFood}>Save food</button>
          <button type="button" onClick={() => setCustom(null)}>Cancel</button>
        </fieldset>
      )}

      {summary.length > 0 && (
        <fieldset>
          <legend>This recipe itself contains</legend>
          <ul>
            {summary.map((row) => (
              <li key={row.substrate_id}>
                {row.substrate_name} ({row.from_food_names.join(', ')})
                {row.is_prebiotic && ' — this one is a prebiotic fibre'}
                {row.no_commercial_enzyme && ' — no commercial enzyme exists for this'}
              </li>
            ))}
          </ul>
        </fieldset>
      )}

      <button type="button" onClick={save} data-testid="save-recipe">Save recipe</button>
      {savedId && (
        <button type="button" data-testid="to-formulation"
                onClick={() => navigate(`/recipes/${savedId}/formulation`)}>
          Set up a formulation
        </button>
      )}
    </>
  )
}
```

The pH and water columns show each ingredient's `TruthValue` inline, unconfirmed and all — §9.3 says every seeded food pH and water content is unconfirmed, and §6.7 makes water content the field R1's fallback depends on. Surfacing them here is what turns "the engine cannot assess this" into "this is the cell to fill in".

- [ ] **Step 2: Verify by hand**

With both servers running: create a recipe with olive oil and garlic, save, and confirm the substrate summary names inulin-type fructans from garlic.

- [ ] **Step 3: Commit**

```bash
git add web/src/screens/RecipeBuilder.tsx
git commit -m "feat(web): add the recipe builder with custom foods and substrate summary"
```

---

## Task 25: Formulation setup screen

Spec §10 screen 3: format picker, trigger-food picker, application-food picker, editable proposed enzyme set, serving size, process steps with heat flags and the enzyme-addition point.

**Files:**
- Create: `web/src/screens/FormulationSetup.tsx`

- [ ] **Step 1: Write the screen**

```tsx
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { api } from '../api/client'
import type { Enzyme, Food, Format, ProcessStep, SelectedEnzyme } from '../api/types'

const FORMATS: { value: Format; label: string }[] = [
  { value: 'premixed_wet', label: 'Premixed wet — enzyme stirred into the dressing' },
  { value: 'encapsulated_in_wet', label: 'Encapsulated in wet — capsule inside the dressing' },
  { value: 'dual_chamber', label: 'Dual chamber — wet one side, dry powder the other' },
  { value: 'dry_sachet', label: 'Dry sachet — powder packaged separately' },
]

export default function FormulationSetup() {
  const { recipeId } = useParams()
  const navigate = useNavigate()

  const [enzymeCatalog, setEnzymeCatalog] = useState<Enzyme[]>([])
  const [triggerFoods, setTriggerFoods] = useState<Food[]>([])
  const [applicationFoods, setApplicationFoods] = useState<Food[]>([])

  const [format, setFormat] = useState<Format>('premixed_wet')
  const [targets, setTargets] = useState<string[]>([])
  const [applications, setApplications] = useState<string[]>([])
  const [enzymes, setEnzymes] = useState<SelectedEnzyme[]>([])
  const [servingSize, setServingSize] = useState('30')
  const [measuredPh, setMeasuredPh] = useState('')
  const [steps, setSteps] = useState<ProcessStep[]>([{ order: 1, label: 'Whisk', is_heat: false }])
  const [additionIndex, setAdditionIndex] = useState(1)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    Promise.all([api.enzymes(), api.foods('trigger'), api.foods('application')])
      .then(([e, t, a]) => { setEnzymeCatalog(e); setTriggerFoods(t); setApplicationFoods(a) })
      .catch((err) => setError(err.message))
  }, [])

  // The proposal follows the trigger foods and the format, and stays editable:
  // spec Workflow A step 5 — removing an enzyme does not remove the finding.
  useEffect(() => {
    if (targets.length === 0) { setEnzymes([]); return }
    api.proposedEnzymes(targets, format).then(setEnzymes).catch((e) => setError(e.message))
  }, [targets, format])

  const enzymeById = new Map(enzymeCatalog.map((e) => [e.id, e]))

  function toggle(list: string[], id: string, set: (next: string[]) => void) {
    set(list.includes(id) ? list.filter((x) => x !== id) : [...list, id])
  }

  async function evaluate() {
    setError(null); setBusy(true)
    try {
      const formulation = await api.createFormulation({
        recipe_id: recipeId,
        format,
        target_trigger_food_ids: targets,
        application_food_ids: applications,
        dwell_profile: null,
        enzymes,
        serving_size_g: servingSize === '' ? null : Number(servingSize),
        measured_ph: measuredPh === '' ? null : Number(measuredPh),
        process_steps: steps,
        enzyme_addition_index: additionIndex,
      })
      const evaluation = await api.evaluate(formulation.id)
      navigate(`/evaluations/${evaluation.id}`)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <h1>Formulation setup</h1>
      {error && <p className="error" data-testid="setup-error">{error}</p>}

      <fieldset>
        <legend>Format</legend>
        {FORMATS.map((f) => (
          <label key={f.value}>
            <input type="radio" name="format" value={f.value} checked={format === f.value}
                   onChange={() => setFormat(f.value)} />
            {f.label}
          </label>
        ))}
      </fieldset>

      <fieldset>
        <legend>Trigger foods you want this to cover</legend>
        {triggerFoods.map((f) => (
          <label key={f.id}>
            <input type="checkbox" checked={targets.includes(f.id)}
                   data-testid={`trigger-${f.id}`}
                   onChange={() => toggle(targets, f.id, setTargets)} />
            {f.name}
          </label>
        ))}
      </fieldset>

      <fieldset>
        <legend>Foods you will pour this on</legend>
        {applicationFoods.map((f) => (
          <label key={f.id}>
            <input type="checkbox" checked={applications.includes(f.id)}
                   onChange={() => toggle(applications, f.id, setApplications)} />
            {f.name}
          </label>
        ))}
      </fieldset>

      <fieldset>
        <legend>Enzymes — proposed from your trigger foods, yours to change</legend>
        <p className="blurb">
          Removing one does not remove the finding: the tool still reports the
          substrate it leaves uncovered.
        </p>
        <table>
          <thead><tr><th>Enzyme</th><th>Dose</th><th>Phase</th><th>Encapsulated</th><th /></tr></thead>
          <tbody>
            {enzymes.map((selected, index) => {
              const enzyme = enzymeById.get(selected.enzyme_id)
              const update = (patch: Partial<SelectedEnzyme>) => {
                const next = [...enzymes]
                next[index] = { ...selected, ...patch }
                setEnzymes(next)
              }
              return (
                <tr key={selected.enzyme_id}>
                  <td>{enzyme?.name ?? selected.enzyme_id}</td>
                  <td>
                    <input type="number" min={0} value={selected.dose ?? ''}
                           data-testid={`dose-${selected.enzyme_id}`}
                           onChange={(e) =>
                             update({ dose: e.target.value === '' ? null : Number(e.target.value) })}
                    /> {enzyme?.dose_unit}
                  </td>
                  <td>
                    <select value={selected.phase}
                            onChange={(e) => update({ phase: e.target.value as 'wet' | 'dry' })}>
                      <option value="wet">wet</option>
                      <option value="dry">dry</option>
                    </select>
                  </td>
                  <td>
                    <input type="checkbox" checked={selected.encapsulated}
                           onChange={(e) => update({ encapsulated: e.target.checked })} />
                  </td>
                  <td>
                    <button type="button"
                            onClick={() => setEnzymes(enzymes.filter((x) => x !== selected))}>
                      Remove
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <select defaultValue="" data-testid="add-enzyme"
                onChange={(e) => {
                  const id = e.target.value
                  if (id && !enzymes.some((x) => x.enzyme_id === id)) {
                    setEnzymes([...enzymes, {
                      enzyme_id: id, dose: null,
                      phase: format === 'premixed_wet' || format === 'encapsulated_in_wet' ? 'wet' : 'dry',
                      encapsulated: false, source_choice: '',
                    }])
                  }
                  e.currentTarget.value = ''
                }}>
          <option value="" disabled>Add an enzyme…</option>
          {enzymeCatalog.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select>
      </fieldset>

      <fieldset>
        <legend>Serving and measured pH</legend>
        <label>Serving size (g)
          <input type="number" min={0} value={servingSize}
                 onChange={(e) => setServingSize(e.target.value)} />
        </label>
        <label>Measured pH — leave blank if you have not measured it
          <input type="number" step="0.1" min={0} max={14} value={measuredPh}
                 data-testid="measured-ph"
                 onChange={(e) => setMeasuredPh(e.target.value)} />
        </label>
      </fieldset>

      <fieldset>
        <legend>How you make it</legend>
        <table>
          <thead><tr><th>#</th><th>Step</th><th>Involves heat</th><th>Enzyme goes in after</th></tr></thead>
          <tbody>
            {steps.map((step, index) => (
              <tr key={step.order}>
                <td>{step.order}</td>
                <td>
                  <input value={step.label} onChange={(e) => {
                    const next = [...steps]
                    next[index] = { ...step, label: e.target.value }
                    setSteps(next)
                  }} />
                </td>
                <td>
                  <input type="checkbox" checked={step.is_heat}
                         data-testid={`heat-${step.order}`}
                         onChange={(e) => {
                           const next = [...steps]
                           next[index] = { ...step, is_heat: e.target.checked }
                           setSteps(next)
                         }} />
                </td>
                <td>
                  <input type="radio" name="addition" checked={additionIndex === step.order}
                         onChange={() => setAdditionIndex(step.order)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <button type="button" onClick={() =>
          setSteps([...steps, { order: steps.length + 1, label: '', is_heat: false }])}>
          Add a step
        </button>
      </fieldset>

      <button type="button" onClick={evaluate} disabled={busy} data-testid="run-evaluation">
        {busy ? 'Running…' : 'Run the checks'}
      </button>
    </>
  )
}
```

The enzyme-addition point is a radio column on the process table rather than a separate number field, because §5.2 defines it as "the `order` value after which the enzyme is added" and R3 compares heat steps against it — a free number input invites an index that matches no step.

- [ ] **Step 2: Verify by hand**

Pick a dairy trigger food and confirm a lactase appears in the proposal; pick a polyol trigger food (mushroom or stone fruit) and confirm no enzyme is proposed for it.

- [ ] **Step 3: Commit**

```bash
git add web/src/screens/FormulationSetup.tsx
git commit -m "feat(web): add formulation setup with the proposed enzyme set"
```

---

## Task 26: Verdict screen — headline, GI strip, envelope, dose cards

**Files:**
- Create: `web/src/components/GiStrip.tsx`
- Create: `web/src/components/EnvelopePanel.tsx`
- Create: `web/src/components/DoseCards.tsx`
- Create: `web/src/screens/Verdict.tsx`

- [ ] **Step 1: `GiStrip.tsx`**

```tsx
import type { GiLane } from '../api/types'
import { TruthValue } from './TruthValue'

/** Spec §10 screen 4 — the deck's slide-3 visual, rendered from live data. */
export function GiStrip({ lanes }: { lanes: GiLane[] }) {
  if (lanes.length === 0) return null
  const regions = lanes[0]!.regions

  return (
    <section data-testid="gi-strip">
      <h3>Where each enzyme can work</h3>
      <p className="blurb">
        A deadline, not a target: anything left when the food reaches the colon
        ferments there. The mouth is shown greyed because food is there for
        seconds — too short for any enzyme to act.
      </p>
      <table>
        <thead>
          <tr>
            <th>Enzyme</th>
            {regions.map((r) => (
              <th key={r.region_id} className={r.dormant ? 'region--dormant' : undefined}>
                {r.name}<br /><small>pH {r.ph_low}–{r.ph_high}</small>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {lanes.map((lane) => (
            <tr key={lane.enzyme_id}>
              <th scope="row">
                {lane.enzyme_name}<br />
                <small>
                  active pH <TruthValue tracked={lane.ph_min} />–<TruthValue tracked={lane.ph_max} />
                </small>
              </th>
              {lane.regions.map((r) => (
                <td
                  key={r.region_id}
                  data-testid={`cell-${lane.enzyme_id}-${r.region_id}`}
                  className={[
                    r.active ? 'cell--active' : 'cell--inactive',
                    r.before_deadline ? '' : 'cell--past-deadline',
                  ].join(' ')}
                >
                  {r.dormant ? 'dormant' : r.active ? 'active' : '—'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
```

- [ ] **Step 2: `EnvelopePanel.tsx`**

```tsx
import type { DwellProfile, Verdict } from '../api/types'
import { VerdictBadge } from './VerdictBadge'

/** Spec §6.3 — the three occasions, with the dwell ranges that define them. */
const OCCASIONS: { profile: DwellProfile; title: string; blurb: string }[] = [
  { profile: 'immediate', title: 'Dressed at the table', blurb: 'Eaten within the hour' },
  { profile: 'packed', title: 'Packed ahead', blurb: 'Dressed 1 to 8 hours before eating' },
  { profile: 'marinade', title: 'Marinade', blurb: 'Left 8 hours or more, on purpose' },
]

export function EnvelopePanel({ envelope }: { envelope: Record<DwellProfile, Verdict> }) {
  return (
    <section data-testid="envelope-panel">
      <h3>Which occasions this can support</h3>
      <p className="blurb">
        What the dressing does to the food it sits on, by how long it sits there.
        An occasion you do not intend to sell is still shown, so nothing is hidden.
      </p>
      <table>
        <tbody>
          {OCCASIONS.map(({ profile, title, blurb }) => (
            <tr key={profile} data-testid={`occasion-${profile}`}>
              <th scope="row">{title}<br /><small>{blurb}</small></th>
              <td><VerdictBadge verdict={envelope[profile]} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
```

- [ ] **Step 3: `DoseCards.tsx`**

```tsx
import type { DoseCard } from '../api/types'
import { TruthValue } from './TruthValue'

export function DoseCards({ cards }: { cards: DoseCard[] }) {
  if (cards.length === 0) return null
  return (
    <section data-testid="dose-cards">
      <h3>Dose per serving</h3>
      <p className="blurb">
        Dose is driven by how much of the substrate a serving carries, not by the
        weight of the food. Below the evidence threshold, an enzyme behaves like a
        placebo — which is why an under-dose is flagged rather than rounded up.
      </p>
      {cards.map((card) => (
        <article key={card.enzyme_id} className="dose-card"
                 data-testid={`dose-card-${card.enzyme_id}`}>
          <h4>{card.enzyme_name}</h4>
          <dl>
            <dt>Your dose</dt>
            <dd>{card.dose === null ? 'not set' : `${card.dose} ${card.dose_unit}`}</dd>
            <dt>Benchmark range</dt>
            <dd>
              <TruthValue tracked={card.dose_min} unit={card.dose_unit} />
              {' – '}
              <TruthValue tracked={card.dose_max} unit={card.dose_unit} />
            </dd>
            <dt>Evidence threshold</dt>
            <dd><TruthValue tracked={card.dose_evidence_threshold} unit={card.dose_unit} /></dd>
            <dt>Substrate in one serving</dt>
            <dd><TruthValue tracked={card.substrate_load} /></dd>
            <dt>Clears the threshold</dt>
            <dd>
              {card.meets_threshold === null
                ? 'cannot tell — see the values above'
                : card.meets_threshold ? 'yes' : 'no'}
              {card.above_benchmark_max && ' — above the benchmark range; it works, but it is an expensive way to solve it'}
            </dd>
          </dl>
        </article>
      ))}
    </section>
  )
}
```

`meets_threshold === null` renders "cannot tell", never "yes" and never a blank. That is the §6 rule — a missing input produces a stated gap — carried all the way to the pixel.

- [ ] **Step 4: `Verdict.tsx`**

```tsx
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'

import { api } from '../api/client'
import { DoseCards } from '../components/DoseCards'
import { EnvelopePanel } from '../components/EnvelopePanel'
import { FindingGroups } from '../components/FindingGroups'
import { GiStrip } from '../components/GiStrip'
import { HeadlineBadge } from '../components/VerdictBadge'
import type { Evaluation } from '../api/types'

export default function Verdict() {
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
      <h1>Verdict</h1>
      <HeadlineBadge headline={evaluation.headline} />
      <p className="blurb">
        Run {evaluation.created_at.slice(0, 16).replace('T', ' ')} on engine{' '}
        {evaluation.engine_version}. This is a record of that run: editing a
        record afterwards does not change it. Re-run to see the effect of a change.
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
    </>
  )
}
```

- [ ] **Step 5: Add the verdict styles to `styles.css`**

```css
.headline { font-size: 1.4rem; font-weight: 700; padding: 0.6rem 0.8rem; border-radius: 4px; }
.headline--red { color: var(--red); border: 2px solid var(--red); }
.headline--amber { color: var(--amber); border: 2px solid var(--amber); }
.headline--gray { color: var(--gray); border: 2px solid var(--gray); }
.headline--green { color: var(--green); border: 2px solid var(--green); }
.verdict--red { color: var(--red); } .verdict--amber { color: var(--amber); }
.verdict--cannot_assess { color: var(--gray); } .verdict--pass { color: var(--green); }
.truth--unconfirmed { color: var(--gray); }
.truth__label { color: var(--gray); }
.blurb { color: var(--gray); font-size: 0.9rem; }
.region--dormant, .cell--inactive { color: var(--gray); background: var(--muted); }
.cell--active { color: var(--green); font-weight: 600; }
.cell--past-deadline { opacity: 0.55; }
.dose-card { border: 1px solid var(--line); padding: 0.75rem; margin: 0.75rem 0; }
```

Colour is never the only signal: every cell also carries a word ("active", "dormant", "—"), and every badge spells its verdict out.

- [ ] **Step 6: Typecheck and verify by hand**

Run: `cd web && npm run typecheck`
Then, with both servers running, walk the whole flow: recipe → formulation → RED verdict on the pH-3.0 vinaigrette.

- [ ] **Step 7: Commit**

```bash
git add web/src/components web/src/screens/Verdict.tsx web/src/styles.css
git commit -m "feat(web): add the verdict screen with GI strip, dose cards, and envelope"
```

---

## Task 27: Frontend language lint

The prohibited-words rule (§10) applies to everything the founder reads, which now includes the React copy.

**Files:**
- Test: `tests/test_web_language.py`

- [ ] **Step 1: Write the test**

```python
"""Spec §10 — prohibited words, extended to the frontend the founder reads.

Kept in pytest rather than a JS linter so one command checks the whole product
and the rule cannot be skipped by not running the web toolchain.
"""

import pathlib

import pytest

PROHIBITED = ("safe", "validated", "guaranteed", "clinically proven", "proven", "demonstrated")
WEB_SRC = pathlib.Path(__file__).resolve().parent.parent / "web" / "src"


def _source_files():
    return sorted(p for p in WEB_SRC.rglob("*.tsx")) + sorted(WEB_SRC.rglob("*.ts"))


@pytest.mark.skipif(not WEB_SRC.is_dir(), reason="frontend not present in this checkout")
@pytest.mark.parametrize("word", PROHIBITED)
def test_no_prohibited_word_appears_in_frontend_source(word):
    offenders = [
        path.relative_to(WEB_SRC)
        for path in _source_files()
        if word in path.read_text(encoding="utf-8").lower()
    ]
    assert not offenders, f"'{word}' appears in: {', '.join(map(str, offenders))}"


@pytest.mark.skipif(not WEB_SRC.is_dir(), reason="frontend not present in this checkout")
def test_the_disclaimer_is_in_the_layout_not_a_single_screen():
    """§10 screen 8's footer must be unskippable — no route may render without it."""
    app = (WEB_SRC / "App.tsx").read_text(encoding="utf-8")
    assert "Not a safety, efficacy, or regulatory determination." in app
```

The disclaimer contains the word "safety", which the prohibited list does not include — the banned token is "safe", and "safety" contains it. Resolve by testing `App.tsx` separately and excluding it from the sweep, or by matching whole words with a regex; take the regex, since a future screen may legitimately need the phrase "food safety regulations":

```python
import re

def _contains(text: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", text) is not None
```

and use `_contains(path.read_text(...).lower(), word)` in the sweep. Whole-word matching still catches "this is safe" and still permits "food safety".

- [ ] **Step 2: Run the test**

Run: `.venv/bin/pytest tests/test_web_language.py -q`
Expected: all pass. If a screen's copy trips it, reword the copy — the words are prohibited, not discouraged.

- [ ] **Step 3: Commit**

```bash
git add tests/test_web_language.py
git commit -m "test(web): assert prohibited words are absent from frontend copy"
```

---

## Task 28: Serve the build — Docker, compose, Makefile

**Files:**
- Modify: `Dockerfile`, `docker-compose.yml`, `Makefile`, `.gitignore`

- [ ] **Step 1: Rewrite the `Dockerfile` as a multi-stage build**

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
RUN pip install --no-cache-dir -e '.[dev]'

COPY tests/ ./tests/
COPY --from=web /web/dist ./web/dist

ENV FOODBREW_DB_PATH=/data/foodbrew.db \
    FOODBREW_WEB_DIST=/app/web/dist

EXPOSE 8000
CMD ["uvicorn", "foodbrew.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

M1's placeholder comment ("M2 replaces this with the uvicorn entrypoint") is now discharged. The database is still created on first boot — by `ensure_database` in the app's lifespan, not by the CMD.

- [ ] **Step 2: Update `docker-compose.yml`**

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
```

- [ ] **Step 3: Update the `Makefile`**

```makefile
.PHONY: test lint fmt db docker-db run web web-build e2e up

test:
	.venv/bin/pytest -q

lint:
	.venv/bin/ruff check src tests

fmt:
	.venv/bin/ruff format src tests

db:
	.venv/bin/python -c "from foodbrew.db import create_database; print(create_database('data/foodbrew.db'))"

docker-db:
	docker compose run --rm foodbrew python -c "from foodbrew.db import ensure_database; print(ensure_database('/data/foodbrew.db'))"

run:
	.venv/bin/uvicorn foodbrew.api.app:app --reload

web:
	cd web && npm run dev

web-build:
	cd web && npm run build

e2e:
	cd web && npm run e2e

up:
	docker compose up --build
```

- [ ] **Step 4: Append to `.gitignore`**

```
data/
web/node_modules/
web/dist/
web/test-results/
web/playwright-report/
```

- [ ] **Step 5: Verify the container serves both the API and the app**

Run: `docker compose up --build -d && sleep 5 && curl -s localhost:8000/api/v1/health && curl -sI localhost:8000/ | head -1`
Expected: the health JSON, then `HTTP/1.1 200 OK` for the SPA index. Then `docker compose down`.

- [ ] **Step 6: Commit**

```bash
git add Dockerfile docker-compose.yml Makefile .gitignore
git commit -m "chore: build the frontend and serve it from uvicorn in one container"
```

---

## Task 29: End-to-end smoke test

Spec §13's Playwright line, covering the M2 slice. M4 extends this same spec through the trial and report.

**Files:**
- Create: `web/playwright.config.ts`
- Create: `web/e2e/verdict.spec.ts`

- [ ] **Step 1: Create `web/playwright.config.ts`**

```ts
import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  use: { baseURL: 'http://127.0.0.1:8000', trace: 'retain-on-failure' },
  // Runs the real container path: uvicorn serving the built assets, one origin,
  // against a throwaway database so a local run never touches ./data.
  webServer: {
    command:
      'FOODBREW_DB_PATH=.e2e/foodbrew.db FOODBREW_WEB_DIST=dist ' +
      '../.venv/bin/uvicorn foodbrew.api.app:app --port 8000',
    url: 'http://127.0.0.1:8000/api/v1/health',
    reuseExistingServer: false,
    timeout: 60_000,
  },
})
```

- [ ] **Step 2: Create `web/e2e/verdict.spec.ts`**

```ts
import { expect, test } from '@playwright/test'

test('build a recipe, evaluate it, and read the verdict', async ({ page }) => {
  await page.goto('/recipes/new')

  await page.getByTestId('recipe-name').fill('E2E vinaigrette')
  await page.getByTestId('food-picker').selectOption({ label: 'Olive oil' })
  await page.getByTestId('food-picker').selectOption({ label: 'White vinegar' })
  await page.getByTestId('amount-olive_oil').fill('100')
  await page.getByTestId('amount-white_vinegar').fill('50')
  await page.getByTestId('save-recipe').click()
  await page.getByTestId('to-formulation').click()

  // A dairy trigger food, so a lactase is proposed automatically.
  await page.getByTestId('trigger-milk').check()
  await page.getByTestId('measured-ph').fill('3.0')
  await page.getByTestId('run-evaluation').click()

  // Golden fixture (a): wet, pH 3.0, standard fungal lactase → RED via R1.
  await expect(page.getByTestId('headline')).toContainText('RED')
  await expect(page.getByTestId('group-blockers')).toContainText('R1')
  await expect(page.getByTestId('gi-strip')).toBeVisible()
  await expect(page.getByTestId('envelope-panel')).toBeVisible()
  await expect(page.getByTestId('cell-lactase_fungal_acid-stomach_fed')).toContainText('active')
  await expect(page.getByTestId('cell-lactase_fungal_acid-mouth')).toContainText('dormant')
})

test('an empty recipe is refused in plain English', async ({ page }) => {
  await page.goto('/recipes/new')
  await page.getByTestId('recipe-name').fill('Empty')
  await page.getByTestId('save-recipe').click()
  await expect(page.getByText('Add at least one ingredient to this recipe.')).toBeVisible()
})
```

If the seeded display names differ from `Olive oil` / `White vinegar`, use the seeded names — the selector is by label, and the seed is the source of truth.

- [ ] **Step 3: Run it**

Run: `cd web && npm run build && npx playwright install chromium && npm run e2e`
Expected: 2 passed. Add `.e2e/` to `web/.gitignore`.

- [ ] **Step 4: Commit**

```bash
git add web/playwright.config.ts web/e2e web/.gitignore
git commit -m "test(web): add the end-to-end recipe-to-verdict smoke test"
```

---

## Task 30: Full acceptance run

**Files:**
- Modify: `README.md` (create if absent)

- [ ] **Step 1: Write the run instructions**

Add to `README.md`:

```markdown
## Running the workbench

Local development, two terminals:

    make run     # FastAPI on :8000
    make web     # Vite dev server, proxying /api to :8000

Everything in one container:

    make up      # builds the frontend, serves it from uvicorn on :8000

The database is created on first boot at `FOODBREW_DB_PATH` (default
`data/foodbrew.db`) and is never overwritten afterwards. `make db` forces a
refresh of the reference tables from `seed/*.json` and discards edits to them.

## Checks

    make test    # pytest: engine, store, API, contracts
    make lint    # ruff
    make e2e     # Playwright, against the built app
```

- [ ] **Step 2: Run everything**

Run: `.venv/bin/ruff check src tests && .venv/bin/pytest -q && cd web && npm run typecheck && npm run build`
Expected: ruff clean, every test green, no type errors, a `web/dist` build.

- [ ] **Step 3: Walk the exit check by hand**

Start `make up`, open `http://localhost:8000`, and complete: build the vinaigrette → set up a premixed-wet formulation with a dairy trigger food and pH 3.0 → read a RED verdict naming R1 → change the format to dry sachet, re-run, and confirm the headline moves. Confirm the footer disclaimer is present on every screen.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document how to run the workbench and its checks"
```

---

## M2 exit criteria

Before declaring M2 done, all of the following must hold:

- [ ] `.venv/bin/pytest -q` passes with zero failures and zero skips (the two web-language tests skip only when `web/` is absent, which it is not).
- [ ] `.venv/bin/ruff check src tests` is clean.
- [ ] `cd web && npm run typecheck && npm run build` succeeds.
- [ ] `cd web && npm run e2e` passes both specs against the built app.
- [ ] Every M1 test still passes unchanged — M2 adds two engine modules and one in-place refactor, and changes no verdict.
- [ ] `tests/store/test_rowmap.py::test_catalog_from_db_equals_catalog_from_seed` passes: the database reader and the seed reader agree record-for-record.
- [ ] `tests/api/test_reproducibility.py` passes in full: editing a source record changes the next run and does not change any stored one.
- [ ] `tests/api/test_contracts.py` passes: every tracked value on the wire carries a valid status, no prohibited word appears in engine, API, or frontend copy, and the layering holds (`engine` imports neither `store` nor `api`; `store` imports neither `fastapi` nor `api`).
- [ ] `docker compose up --build` serves the API at `/api/v1/health` and the app at `/`, and a restart preserves an edit made to an enzyme row.
- [ ] The founder can complete Workflow A end to end in the browser without help: recipe → formulation → verdict, with the GI strip, dose cards, and envelope panel all rendering.

**Do not begin M3 until these pass.** M3's compare view reads two stored snapshots and diffs them, and its stale-evaluation banner compares a stored snapshot against a freshly hydrated one — both are built directly on Task 5's byte-stable snapshot and Task 20's isolation guarantee. A snapshot that is not byte-stable makes the banner flap, and a snapshot that is not isolating makes the compare view lie.

---

## Plan self-review

**Spec coverage.** §3 Workflow A → Tasks 7, 16, 17, 18, 24, 25, 26. §4 architecture and versioning → Tasks 5, 12, 20; the dependency rule is enforced by Task 19. §5.1–5.2 data model → Tasks 3, 9, 10, 11, 12 (every table M2 touches; the trial tables are read-only here, per decision #8). §5.4 truth labels → Tasks 10, 13, 19, 22. §6.4 aggregation and the four headline states → Tasks 6, 12, 22, 26. §6.7 conventions → Tasks 9, 11 (the zero-ingredient rule and the pH resolution order). §8 GI model → Tasks 8, 26. §10 API endpoint list → Tasks 15–18; §10 screens 1–4 → Tasks 23–26; the §10 language rule → Tasks 19, 27. §13 testing → Tasks 19, 20, 27, 29. §14's M2 line, item by item: recipe builder with custom foods (Task 24), measured-pH entry (Task 25), formulation setup with application foods (Task 25), verdict screen with the GI strip (Task 26), four headline states (Task 22), envelope panel (Task 26).

**Deliberately not in M2**, consistent with §14 and with the M1 plan's own self-review: R13's format-recommendation search, §7 auto-variants, Workflow B compare, Workflow D's editors and proposals inbox, the stale-evaluation banner, and the §10 screen 8 report (all M3); every Workflow E surface (M4). Two forward reaches are deliberate and justified in decisions #5 and #8: the snapshot machinery M3's compare and banner require, and the trial-pH query M4's capture will fill.

**Placeholder scan.** The four screen placeholders created in Task 21 step 9 are the only intentional stubs, and each is replaced by name in Tasks 23–26. The four router stubs mentioned in Task 14 step 5 are replaced in Tasks 15–18. No TODOs, no "and so on", no task that says "similar to the previous one".

**Type consistency.** `Tracked` is the single carrier of a value's label from the seed JSON (M1) through `rowmap` → `snapshot` → `TrackedOut` → the `Tracked<T>` TypeScript interface → `TruthValue`; Task 19 asserts the chain holds on the wire. `ValidationRejection` is raised in `store.recipes`, `store.foods`, `store.formulations`, and `engine.rules.r14`, imported everywhere from `foodbrew.engine`, and mapped to HTTP 422 in exactly one handler. `group_findings` is defined once in `flags.py` and called by both `aggregate` (run path) and `store.evaluations._assemble` (read path), so a finding cannot be grouped one way when run and another way when re-read. `EvalContext` is constructed in exactly two places — `store.formulations.hydrate_context` for a live run and `store.snapshot.context_from_snapshot` for a replay — and Task 12 asserts they agree.

**Known cross-task dependencies.** Task 3 (`rowmap`) precedes Task 11 (`hydrate_context`) and Task 10 (`foods`), both of which import it. Task 5 (`snapshot`) and Task 6 (`group_findings`) both precede Task 12 (`store.evaluations`), which imports both. Task 8 (`views`) precedes Tasks 16 and 18, which serialize its output. Tasks 15–18 (routers) precede Task 14's test run, though `app.py` itself is written first — the note in Task 14 step 5 covers running that task standalone. Task 21 (scaffold) precedes every other web task. Task 28 (build wiring) precedes Task 29 (Playwright), which drives the built app rather than the dev server.
