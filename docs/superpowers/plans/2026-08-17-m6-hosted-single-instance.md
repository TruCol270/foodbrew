# M6 — A Hosted Single Instance the Founder Can Open on Her Phone

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put the tool on the internet at a URL the founder can open, behind a password she can type, with her bench data backed up twice — so she can use it, play with it, and send feedback.

**Architecture:** One Fly.io Machine, one Fly volume holding the SQLite file, the existing Dockerfile unchanged. Because there is no custom domain, there is nowhere "in front" of the app to put access control, so it goes *in* the app as HTTP Basic auth — stdlib only, one shared password from a Fly secret, the health check exempt. Durability is two independent mechanisms: Fly's automatic volume snapshots, plus a daily `VACUUM INTO` copy pulled by CI and pushed to R2.

**Tech Stack:** Unchanged in the app: Python 3.12, FastAPI, stdlib `sqlite3`, React 19 built to static files. New infrastructure only: `fly.toml`, one GitHub Actions scheduled workflow, `tomllib` (stdlib) for a config contract test. **No new runtime dependency and no new package in the image.**

**Prior milestones:** M1–M5 are merged. `main` is at `3d1319d`, 754 python tests, 21 Playwright cases.

---

## What M6 is not

- **Not multi-user.** No `user` column, no per-user isolation, no signup, no sessions, no password reset. One shared credential for one person. If a second person ever needs access, that is a different plan and it starts with a schema change.
- **Not a schema change.** Nothing in `schema.sql` moves, so M5's migration list gains no entry.
- **Not high availability.** One machine and one volume means a host incident is real downtime — Fly says "an hour, a day, or sometimes longer" — until a new volume is restored from a snapshot. This is the deliberate price of SQLite's single writer, and the founder should be told it in plain words so an outage does not read to her as lost work.
- **Not a rules, report, or UI change.** `ENGINE_VERSION` stays `1.0.0`. No golden fixture moves. If a task changes a verdict, that task is wrong.
- **Not WAL mode.** WAL is only needed for Litestream, which decision #4 rejects. Turning it on would add `-wal` and `-shm` sidecar files next to the database for no benefit here.

---

## Decisions

**1. Access control lives in the app, because there is no domain to put it in front of.** The original §11 sketch said "Cloudflare Access in front," and that requires a Cloudflare-proxied custom domain — Access cannot protect a bare `*.fly.dev` hostname. The founder has no domain and does not want to register one for a feedback build. So the gate moves inside: HTTP Basic auth as ASGI middleware, `hmac.compare_digest` against one password held in a Fly secret. The browser prompts natively, which is the only login flow that needs no app install, no CLI, and no email round-trip on a phone. This reverses the "access control belongs in front of the app" constraint from earlier discussion — that constraint was correct for a domain-backed multi-user deploy and is inapplicable here.

**2. The username is ignored on purpose.** There is one credential, not one account. Validating a username would imply an identity model the app does not have and cannot enforce. The middleware compares the password only, in constant time, and the docs tell her to type anything in the first box.

**3. The health check is the only unauthenticated path, and it must stay boring.** Fly's HTTP check has no credentials, so `/api/v1/health` is exempt. It returns a status, the engine version, and whether the database reads — nothing about a formulation, a trial, or a food. `/robots.txt` is also exempt because a crawler must be able to read the refusal without a password.

**4. Litestream is rejected; two boring mechanisms replace it.** Litestream is alive and maintained (0.5.x shipped this year), but it is the wrong size here: it needs WAL mode on, a Go binary baked into the image, the entrypoint rewritten to wrap uvicorn, and it **fails silently** — you discover a broken replication stream at restore time. For a database taking a few dozen writes a day from one person, continuous seconds-level RPO buys nothing. Instead: Fly's automatic volume snapshots (already on, free under 10 GB, retention raised to 30 days) cover host and volume failure with a one-command restore, and a daily `VACUUM INTO` copy pushed to R2 covers what snapshots cannot — a Fly account or region incident, wanting the data outside Fly, or a bad state quietly baked into the snapshot chain. `VACUUM INTO` is SQLite's own recommendation for this size and profile.

**5. The backup job runs from CI, not from the image.** Pushing to R2 needs an S3 client. Putting `boto3` or `rclone` in the container would break the no-new-runtime-dependency rule that M3, M4 and M5 all held. GitHub Actions already exists, its runners ship the AWS CLI, and R2 speaks the S3 API — so the snapshot is *taken* inside the machine by a stdlib-only module, and *moved* by CI. The image stays exactly as clean as it is today.

**6. `VACUUM INTO` writes to `/tmp`, not to the volume.** The copy is the same size as the database. Writing it beside the original would double volume usage during every backup and risk filling a small volume. `/tmp` is on the machine's ephemeral rootfs, which is the correct place for a file that exists for thirty seconds.

**7. The health endpoint now touches the database, and returns 503 when it cannot.** Today it reports `ok` without reading anything, so a full volume, a corrupted file, or a permissions problem would leave the machine serving healthy 200s while every write failed. A cheap `SELECT 1 FROM enzyme LIMIT 1` closes that blind spot and lets Fly's check restart a machine that is actually broken. The failure response deliberately carries the sqlite error text: the operator reads it in `fly logs` without needing a shell.

**8. `fly.toml` is checked in and contract-tested, because the dangerous settings are invisible at runtime.** Fly volumes are 1:1 with machines — a volume physically cannot attach to two machines, and Fly refuses to try, so the two-writers-on-one-file corruption I first worried about is impossible by construction. `canary` and `bluegreen` are likewise refused outright for volume-backed apps. **The real hazard is a second machine with its own new volume** (`fly scale count 2`, a region add, or an HA default at launch), which silently forks the SQLite file into two unsynchronised copies with no error and no visible symptom. A test that parses `fly.toml` with `tomllib` and asserts the safe values is the only automated guard available for that, and it costs twenty lines.

**9. `--ha=false` is used at launch and then verified, not trusted.** There is at least one unresolved Fly community report of `--ha=false` still starting two machines. The deploy checklist therefore requires reading `fly status` and confirming exactly one machine before the founder is given the URL.

**10. `auto_stop_machines = "off"` rather than autostop plus `min_machines_running = 1`.** There is a documented, unresolved report of machines being autostopped below `min_machines_running`. For one always-warm instance the simpler setting is also the more predictable one, and it removes cold-start latency that a non-technical user would read as the app being broken.

**11. The instance is marked `noindex` and disallowed to crawlers.** The gate already refuses unauthenticated requests, but a `fly.dev` URL appearing in a search index is an invitation to password-guessing traffic and a needless disclosure that the tool exists. `X-Robots-Tag: noindex, nofollow` on every response and a `/robots.txt` of `Disallow: /` cost nothing.

**12. Every existing test keeps passing untouched, because the gate is off when no password is set.** `FOODBREW_ACCESS_PASSWORD` unset means no middleware is installed, so the 754-test suite, the 21 Playwright cases and local `make run` are unaffected. The risk this creates — a production deploy silently public because the secret was never set — is closed by a deploy-checklist smoke test that asserts an unauthenticated request gets **401**, and by a contract test asserting the gate installs when the setting is present.

---

## File structure

```
foodbrew/
├── fly.toml                              # NEW: one machine, one volume, health check, rolling
├── src/foodbrew/
│   ├── api/
│   │   ├── access.py                     # NEW: Basic auth middleware, open-path set, challenge header
│   │   ├── settings.py                    #   + access_password (env FOODBREW_ACCESS_PASSWORD)
│   │   └── app.py                         #   installs the gate; health reads the DB; robots.txt; noindex
│   └── tools/
│       ├── __init__.py                    # NEW
│       └── snapshot.py                    # NEW: VACUUM INTO, stdlib only, runnable as python -m
├── .github/workflows/backup.yml           # NEW: daily snapshot -> R2
├── docs/DEPLOY.md                         # NEW: the deploy and day-2 runbook
├── README.md                              #   + a hosted-instance section
└── tests/
    ├── api/test_access.py                 # NEW
    ├── api/test_health.py                 # NEW
    ├── api/test_contracts_m6.py           # NEW
    ├── test_fly_config.py                 # NEW
    └── tools/test_snapshot.py             # NEW
```

**Boundary rules.** M1–M5's hold unchanged, plus:

- `src/foodbrew/tools/snapshot.py` imports **stdlib only**. It runs inside a container with no app context and must not depend on FastAPI, the engine, or the store.
- `api/access.py` reads no database and touches no store. It is a request gate, not a policy engine.
- No secret value appears in any tracked file. `tests/api/test_contracts_m6.py` asserts it.

---

# Task 1: `Settings` learns the access password

**Files:**
- Modify: `src/foodbrew/api/settings.py`
- Test: `tests/api/test_settings.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_settings.py
import pytest

from foodbrew.api.settings import load_settings


def test_the_access_password_is_none_when_unset(monkeypatch):
    monkeypatch.delenv("FOODBREW_ACCESS_PASSWORD", raising=False)
    assert load_settings().access_password is None


def test_the_access_password_is_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("FOODBREW_ACCESS_PASSWORD", "hunter2")
    assert load_settings().access_password == "hunter2"


@pytest.mark.parametrize("value", ["", "   "])
def test_a_blank_password_is_treated_as_unset(monkeypatch, value):
    """An empty secret must not install a gate that accepts an empty password."""
    monkeypatch.setenv("FOODBREW_ACCESS_PASSWORD", value)
    assert load_settings().access_password is None
```

- [ ] **Step 2: Run it and watch it fail**

Run: `.venv/bin/pytest tests/api/test_settings.py -v`
Expected: FAIL — `Settings` has no attribute `access_password`.

- [ ] **Step 3: Implement**

Replace the whole of `src/foodbrew/api/settings.py`:

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
    #: The one shared password for the hosted single instance (M6 decision #1).
    #: None means no gate is installed at all, which is what local development
    #: and the test suite want. A blank or whitespace-only value is treated as
    #: None rather than as a password that anything could match.
    access_password: str | None = None


def load_settings() -> Settings:
    supplied = os.environ.get("FOODBREW_ACCESS_PASSWORD", "").strip()
    return Settings(
        db_path=Path(os.environ.get("FOODBREW_DB_PATH", "data/foodbrew.db")),
        web_dist=Path(os.environ.get("FOODBREW_WEB_DIST", "web/dist")),
        access_password=supplied or None,
    )
```

- [ ] **Step 4: Run it and watch it pass**

Run: `.venv/bin/pytest tests/api/test_settings.py -v`
Expected: 4 passed.

- [ ] **Step 5: Confirm nothing else broke**

`Settings` is constructed positionally in several tests. The new field has a default, so those keep working.

Run: `.venv/bin/pytest -q > /tmp/t1.txt 2>&1; grep -E "passed|failed" /tmp/t1.txt | tail -1`
Expected: `758 passed` (754 + 4).

- [ ] **Step 6: Commit**

```bash
git add src/foodbrew/api/settings.py tests/api/test_settings.py
git commit -m "feat(api): read the hosted instance access password from the environment"
```

---

# Task 2: The Basic auth gate

**Files:**
- Create: `src/foodbrew/api/access.py`
- Test: `tests/api/test_access.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_access.py
import base64

import pytest
from fastapi.testclient import TestClient

from foodbrew.api.app import create_app
from foodbrew.api.settings import Settings

PASSWORD = "correct horse battery staple"


def _auth(password: str, user: str = "founder") -> dict:
    raw = f"{user}:{password}".encode("utf-8")
    return {"Authorization": "Basic " + base64.b64encode(raw).decode("ascii")}


@pytest.fixture
def gated(tmp_path):
    app = create_app(
        Settings(
            db_path=tmp_path / "foodbrew.db",
            web_dist=tmp_path / "no-dist",
            access_password=PASSWORD,
        )
    )
    with TestClient(app) as client:
        yield client


def test_an_unauthenticated_request_is_refused(gated):
    response = gated.get("/api/v1/enzymes")
    assert response.status_code == 401


def test_the_refusal_asks_the_browser_to_prompt(gated):
    """Without this header a phone shows a bare error instead of a login box."""
    header = gated.get("/api/v1/enzymes").headers["www-authenticate"]
    assert header.lower().startswith("basic")
    assert "foodbrew" in header.lower()


def test_the_refusal_is_plain_english_and_leaks_nothing(gated):
    body = gated.get("/api/v1/enzymes").json()
    assert "private" in body["detail"].lower()
    assert PASSWORD not in body["detail"]


def test_the_right_password_gets_in(gated):
    response = gated.get("/api/v1/enzymes", headers=_auth(PASSWORD))
    assert response.status_code == 200
    assert response.json()


def test_the_username_is_ignored_on_purpose(gated):
    """One credential, not one account (decision #2)."""
    assert gated.get("/api/v1/enzymes", headers=_auth(PASSWORD, "anything")).status_code == 200


def test_a_wrong_password_is_refused(gated):
    assert gated.get("/api/v1/enzymes", headers=_auth("nope")).status_code == 401


def test_a_password_that_is_a_prefix_of_the_real_one_is_refused(gated):
    assert gated.get("/api/v1/enzymes", headers=_auth(PASSWORD[:-1])).status_code == 401


@pytest.mark.parametrize(
    "header",
    ["", "Bearer abc", "Basic", "Basic !!!not-base64!!!", "Basic " + base64.b64encode(b"\xff\xfe").decode()],
)
def test_a_malformed_authorization_header_is_refused_not_crashed(gated, header):
    """A bad header must be a 401, never a 500 — this endpoint is on the internet."""
    response = gated.get("/api/v1/enzymes", headers={"Authorization": header} if header else {})
    assert response.status_code == 401


def test_a_write_is_refused_too(gated):
    """The gate is not a read-only curtain; POST is the dangerous verb."""
    response = gated.post("/api/v1/recipes", json={"name": "x", "ingredients": []})
    assert response.status_code == 401


def test_the_health_check_needs_no_password(gated):
    """Fly's HTTP check has no credentials (decision #3)."""
    assert gated.get("/api/v1/health").status_code == 200


def test_the_health_check_leaks_no_founder_data(gated):
    body = gated.get("/api/v1/health").json()
    assert set(body) <= {"status", "engine_version", "database"}


def test_robots_needs_no_password(gated):
    assert gated.get("/robots.txt").status_code == 200


def test_no_gate_is_installed_when_no_password_is_set(client):
    """The existing suite and local dev must be untouched (decision #12)."""
    assert client.get("/api/v1/enzymes").status_code == 200
```

- [ ] **Step 2: Run it and watch it fail**

Run: `.venv/bin/pytest tests/api/test_access.py -v`
Expected: FAIL — `Settings` accepts `access_password` after Task 1, but no gate exists, so every 401 test fails with 200.

- [ ] **Step 3: Implement the gate**

Create `src/foodbrew/api/access.py`:

```python
"""The access gate for the hosted single instance (M6 decisions #1, #2, #3).

This is HTTP Basic auth and nothing more. It is not an identity system: there
is one password for one person, so there is no user table, no session, and no
username check. It exists because the hosted instance has no custom domain and
therefore nothing in front of it to hold a policy — see the plan's decision #1
for why that reverses the usual arrangement.
"""

from __future__ import annotations

import base64
import binascii
import hmac

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

#: Reachable without credentials. The platform health check arrives with no
#: password and must still get an answer, and a crawler has to be able to read
#: the refusal in robots.txt. Neither returns founder data.
OPEN_PATHS = frozenset({"/api/v1/health", "/robots.txt"})

#: Without this header a browser shows a bare error page instead of a login box,
#: which on a phone is indistinguishable from the app being broken.
CHALLENGE = {"WWW-Authenticate": 'Basic realm="FoodBrew", charset="UTF-8"'}

REFUSAL = "This instance is private. Ask for the password."


def supplied_password(header: str | None) -> str | None:
    """The password from an Authorization header, or None if there isn't one.

    Every malformed shape returns None rather than raising: this runs on the
    open internet, and a decoding error must be a 401, never a 500.
    """
    if not header:
        return None
    scheme, _, encoded = header.partition(" ")
    if scheme.lower() != "basic" or not encoded.strip():
        return None
    try:
        raw = base64.b64decode(encoded.strip(), validate=True).decode("utf-8")
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None
    if ":" not in raw:
        return None
    _, _, password = raw.partition(":")
    return password


def install_access_gate(app: FastAPI, password: str) -> None:
    """Refuse every request that does not carry `password`, except OPEN_PATHS."""

    @app.middleware("http")
    async def gate(request: Request, call_next):
        if request.url.path in OPEN_PATHS:
            return await call_next(request)
        offered = supplied_password(request.headers.get("authorization"))
        # compare_digest, not ==: a short-circuiting comparison leaks the length
        # of the shared prefix to anyone who can time the response.
        if offered is None or not hmac.compare_digest(offered, password):
            return JSONResponse(status_code=401, content={"detail": REFUSAL}, headers=CHALLENGE)
        return await call_next(request)
```

- [ ] **Step 4: Wire it into the app factory**

In `src/foodbrew/api/app.py`, add to the imports:

```python
from foodbrew.api.access import install_access_gate
```

and immediately after `app.state.settings = settings`, add:

```python
    # Only when a password is configured (decision #12): local development and
    # the test suite run open, and the deploy checklist's 401 smoke test is what
    # catches a production instance whose secret was never set.
    if settings.access_password:
        install_access_gate(app, settings.access_password)
```

- [ ] **Step 5: Run the new tests**

Run: `.venv/bin/pytest tests/api/test_access.py -v`
Expected: all pass except the two `robots.txt` cases and `test_the_health_check_leaks_no_founder_data`'s `database` key, which Task 3 and Task 4 add. Mark those two expected failures and move on — do **not** weaken them.

Run: `.venv/bin/pytest tests/api/test_access.py -v -k "not robots and not leaks_no_founder"`
Expected: 12 passed.

- [ ] **Step 6: Commit**

```bash
git add src/foodbrew/api/access.py src/foodbrew/api/app.py tests/api/test_access.py
git commit -m "feat(api): gate the hosted instance behind one shared password"
```

---

# Task 3: `robots.txt` and `noindex`

**Files:**
- Modify: `src/foodbrew/api/app.py`
- Test: `tests/api/test_access.py` (the two robots cases from Task 2)

- [ ] **Step 1: The tests already exist**

`test_robots_needs_no_password` from Task 2 is currently failing. Confirm it:

Run: `.venv/bin/pytest tests/api/test_access.py -k robots -v`
Expected: FAIL — `/robots.txt` falls through to the SPA catch-all or 404s.

- [ ] **Step 2: Add the route and the header**

In `src/foodbrew/api/app.py`, add `PlainTextResponse` to the responses import:

```python
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
```

Add this route immediately after the `health` endpoint, **before** `_mount_web(app, settings)` is called — the SPA catch-all matches `/{full_path:path}` and would otherwise swallow it:

```python
    @app.get("/robots.txt", include_in_schema=False)
    def robots() -> PlainTextResponse:
        # Decision #11: the gate refuses crawlers anyway, but a fly.dev URL in a
        # search index attracts password-guessing traffic and needlessly
        # advertises that the instance exists.
        return PlainTextResponse("User-agent: *\nDisallow: /\n")

    @app.middleware("http")
    async def _noindex(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response
```

**Ordering note that matters:** Starlette runs `@app.middleware` handlers in reverse registration order, outermost last-registered. This one is registered after the gate in Task 2, so it wraps the gate and stamps the header on the 401 too. That is what we want — an unauthenticated crawler hit is exactly the response that should carry `noindex`.

- [ ] **Step 3: Run the tests**

Run: `.venv/bin/pytest tests/api/test_access.py -k "robots" -v`
Expected: 2 passed.

- [ ] **Step 4: Assert the header lands on both a refusal and a success**

Append to `tests/api/test_access.py`:

```python
def test_the_noindex_header_is_on_a_refusal(gated):
    assert "noindex" in gated.get("/api/v1/enzymes").headers["x-robots-tag"]


def test_the_noindex_header_is_on_a_success(gated):
    response = gated.get("/api/v1/enzymes", headers=_auth(PASSWORD))
    assert "noindex" in response.headers["x-robots-tag"]


def test_robots_disallows_everything(gated):
    assert "Disallow: /" in gated.get("/robots.txt").text
```

Run: `.venv/bin/pytest tests/api/test_access.py -v -k "not leaks_no_founder"`
Expected: 17 passed.

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/api/app.py tests/api/test_access.py
git commit -m "feat(api): keep the hosted instance out of search indexes"
```

---

# Task 4: The health check tells the truth about the database

**Files:**
- Modify: `src/foodbrew/api/app.py`
- Test: `tests/api/test_health.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_health.py
from fastapi.testclient import TestClient

from foodbrew.api.app import create_app
from foodbrew.api.settings import Settings


def test_health_reports_the_database_is_readable(client):
    body = client.get("/api/v1/health").json()
    assert body["status"] == "ok"
    assert body["engine_version"] == "1.0.0"
    assert body["database"] == "ok"


def test_health_is_503_when_the_database_cannot_be_read(tmp_path):
    """Decision #7: a machine serving 200 while every write fails is the blind
    spot this closes. Fly's HTTP check restarts on a non-200, so the status code
    is the load-bearing part, not the body.
    """
    path = tmp_path / "foodbrew.db"
    app = create_app(Settings(db_path=path, web_dist=tmp_path / "none"))
    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 200
        # Replace the file with something that is not a database at all, which is
        # what a truncated or half-restored volume looks like.
        path.write_bytes(b"this is not a sqlite file")
        response = client.get("/api/v1/health")
        assert response.status_code == 503
        assert response.json()["status"] == "unavailable"


def test_the_failure_names_the_sqlite_error_for_the_operator(tmp_path):
    """So the cause is readable in `fly logs` without opening a shell."""
    path = tmp_path / "foodbrew.db"
    app = create_app(Settings(db_path=path, web_dist=tmp_path / "none"))
    with TestClient(app) as client:
        client.get("/api/v1/health")
        path.write_bytes(b"not a database")
        detail = client.get("/api/v1/health").json()["database"]
        assert "ok" != detail
        assert detail
```

- [ ] **Step 2: Run it and watch it fail**

Run: `.venv/bin/pytest tests/api/test_health.py -v`
Expected: FAIL — no `database` key; the broken-file case returns 200.

- [ ] **Step 3: Implement**

In `src/foodbrew/api/app.py`, add to the imports:

```python
import sqlite3

from foodbrew.store.connection import connect
```

Replace the existing `health` endpoint:

```python
    @app.get("/api/v1/health")
    def health() -> JSONResponse:
        # Decision #7: this endpoint is what Fly restarts the machine on, so it
        # has to fail when the database is unusable rather than only when the
        # process is dead. One indexed read is cheap enough for a 30s check.
        try:
            with connect(app.state.settings.db_path) as conn:
                conn.execute("SELECT 1 FROM enzyme LIMIT 1").fetchone()
        except sqlite3.Error as exc:
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unavailable",
                    "engine_version": ENGINE_VERSION,
                    "database": str(exc),
                },
            )
        return JSONResponse(
            content={"status": "ok", "engine_version": ENGINE_VERSION, "database": "ok"}
        )
```

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/pytest tests/api/test_health.py tests/api/test_access.py tests/api/test_app.py -v`
Expected: all pass, including `test_the_health_check_leaks_no_founder_data` and the pre-existing `test_health_reports_the_engine_version`.

- [ ] **Step 5: Full suite**

Run: `.venv/bin/pytest -q > /tmp/t4.txt 2>&1; grep -E "passed|failed" /tmp/t4.txt | tail -1`
Expected: `778 passed`.

- [ ] **Step 6: Commit**

```bash
git add src/foodbrew/api/app.py tests/api/test_health.py
git commit -m "feat(api): health fails when the database is unreadable, not just when the process dies"
```

---

# Task 5: `VACUUM INTO`, stdlib only

**Files:**
- Create: `src/foodbrew/tools/__init__.py`, `src/foodbrew/tools/snapshot.py`
- Test: `tests/tools/test_snapshot.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/tools/test_snapshot.py
import sqlite3

import pytest

from foodbrew.tools.snapshot import main, snapshot


def _seeded(path):
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE observation (id TEXT PRIMARY KEY, note TEXT)")
    conn.execute("INSERT INTO observation VALUES ('o1', 'clearly softer')")
    conn.commit()
    conn.close()
    return path


def test_the_copy_carries_the_rows(tmp_path):
    src = _seeded(tmp_path / "live.db")
    out = snapshot(src, tmp_path / "copy.db")
    rows = sqlite3.connect(out).execute("SELECT note FROM observation").fetchall()
    assert rows == [("clearly softer",)]


def test_the_copy_is_a_real_database_not_a_file_copy(tmp_path):
    """VACUUM INTO produces a consistent database even mid-write, which a plain
    shutil.copy of a live file does not.
    """
    src = _seeded(tmp_path / "live.db")
    out = snapshot(src, tmp_path / "copy.db")
    assert sqlite3.connect(out).execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_an_existing_destination_is_replaced(tmp_path):
    """VACUUM INTO refuses to write to a path that exists, and this job runs
    daily onto the same path.
    """
    src = _seeded(tmp_path / "live.db")
    out = tmp_path / "copy.db"
    out.write_bytes(b"yesterday")
    assert snapshot(src, out).exists()
    assert sqlite3.connect(out).execute("SELECT count(*) FROM observation").fetchone()[0] == 1


def test_the_destination_directory_is_created(tmp_path):
    src = _seeded(tmp_path / "live.db")
    out = snapshot(src, tmp_path / "nested" / "deeper" / "copy.db")
    assert out.exists()


def test_a_missing_source_is_a_readable_error(tmp_path):
    with pytest.raises(FileNotFoundError) as caught:
        snapshot(tmp_path / "absent.db", tmp_path / "copy.db")
    assert "absent.db" in str(caught.value)


def test_main_prints_the_path_it_wrote(tmp_path, capsys):
    src = _seeded(tmp_path / "live.db")
    out = tmp_path / "copy.db"
    assert main([str(src), str(out)]) == 0
    assert str(out) in capsys.readouterr().out


def test_the_module_imports_nothing_outside_the_standard_library():
    """It runs inside the container with no app context (boundary rule)."""
    import pathlib

    text = (
        pathlib.Path(__file__).resolve().parents[2]
        / "src" / "foodbrew" / "tools" / "snapshot.py"
    ).read_text(encoding="utf-8")
    for forbidden in ("fastapi", "foodbrew.engine", "foodbrew.store", "foodbrew.api", "boto3"):
        assert forbidden not in text, f"snapshot.py imports {forbidden}"
```

- [ ] **Step 2: Run it and watch it fail**

Run: `.venv/bin/pytest tests/tools/test_snapshot.py -v`
Expected: FAIL — `ModuleNotFoundError: foodbrew.tools`.

- [ ] **Step 3: Implement**

Create `src/foodbrew/tools/__init__.py`:

```python
"""Operational tools. Run inside the container; stdlib only, no app context."""
```

Create `src/foodbrew/tools/snapshot.py`:

```python
"""Take a consistent copy of the live database without stopping the app.

`VACUUM INTO` is SQLite's own supported way to copy a database that is being
written to: it runs inside a read transaction, so the result is a complete
database as of one instant rather than a smear of pages, which is what a plain
file copy of a live database gives you.

Deliberately stdlib only (M6 boundary rule). This runs via `python -m` inside
the deployed container, where there is no FastAPI app and no settings object,
and it must never be the reason the image needs another package.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

DEFAULT_OUT = Path("/tmp/foodbrew-snapshot.db")


def snapshot(db_path: Path | str, out_path: Path | str) -> Path:
    """Write a consistent copy of `db_path` to `out_path` and return the path."""
    db_path, out_path = Path(db_path), Path(out_path)
    if not db_path.exists():
        raise FileNotFoundError(f"no database at {db_path}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # VACUUM INTO refuses a destination that already exists, and this job runs
    # on a schedule onto the same path every day.
    if out_path.exists():
        out_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("VACUUM INTO ?", (str(out_path),))
    finally:
        conn.close()
    return out_path


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    db = Path(args[0]) if args else Path(os.environ.get("FOODBREW_DB_PATH", "data/foodbrew.db"))
    out = Path(args[1]) if len(args) > 1 else DEFAULT_OUT
    print(snapshot(db, out))
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised by the CI backup job
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/pytest tests/tools/test_snapshot.py -v`
Expected: 7 passed.

- [ ] **Step 5: Prove it works against the real seeded database**

```bash
.venv/bin/python -m foodbrew.tools.snapshot data/foodbrew.db /tmp/real-snapshot.db
.venv/bin/python -c "import sqlite3; print(sqlite3.connect('/tmp/real-snapshot.db').execute('select count(*) from food').fetchone())"
```

Expected: prints `/tmp/real-snapshot.db`, then `(53,)`.

- [ ] **Step 6: Commit**

```bash
git add src/foodbrew/tools tests/tools/test_snapshot.py
git commit -m "feat(tools): consistent database snapshot via VACUUM INTO"
```

---

# Task 6: `fly.toml`, and a test that guards the dangerous settings

**Files:**
- Create: `fly.toml`
- Test: `tests/test_fly_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fly_config.py
"""fly.toml holds settings whose failure mode is silent (M6 decision #8).

Fly volumes are 1:1 with machines, so two machines cannot corrupt one file —
Fly refuses to attach a volume twice. The hazard is a SECOND machine with its
OWN volume, which forks the SQLite database into two unsynchronised copies with
no error and no visible symptom. Nothing at runtime detects that, so the config
is asserted here instead.
"""

import pathlib
import tomllib

CONFIG = pathlib.Path(__file__).resolve().parents[1] / "fly.toml"


def _config() -> dict:
    return tomllib.loads(CONFIG.read_text(encoding="utf-8"))


def test_fly_config_exists_and_parses():
    assert CONFIG.is_file()
    assert _config()["app"]


def test_the_volume_is_mounted_where_the_app_expects_the_database():
    config = _config()
    mount = config["mounts"][0] if isinstance(config["mounts"], list) else config["mounts"]
    assert mount["destination"] == "/data"
    assert config["env"]["FOODBREW_DB_PATH"].startswith("/data/")


def test_exactly_one_mount_is_declared():
    mounts = _config()["mounts"]
    assert len(mounts if isinstance(mounts, list) else [mounts]) == 1


def test_the_deploy_strategy_is_one_fly_allows_with_a_volume():
    """canary and bluegreen are refused outright for volume-backed apps, and
    both would mean two machines holding one database if they were not.
    """
    assert _config()["deploy"]["strategy"] in {"rolling", "immediate"}


def test_the_machine_is_never_stopped_out_from_under_her():
    """Decision #10: autostop has a documented report of firing below
    min_machines_running, and a cold start reads as a broken app on a phone.
    """
    service = _config()["http_service"]
    assert service["auto_stop_machines"] == "off"
    assert service["min_machines_running"] == 1


def test_the_service_points_at_the_port_the_app_listens_on():
    assert _config()["http_service"]["internal_port"] == 8000


def test_https_is_forced():
    assert _config()["http_service"]["force_https"] is True


def test_the_health_check_targets_the_real_endpoint():
    checks = _config()["http_service"]["checks"]
    assert any(check["path"] == "/api/v1/health" for check in checks)


def test_no_secret_is_written_into_the_config():
    """The password belongs in `fly secrets set`, never in a tracked file."""
    text = CONFIG.read_text(encoding="utf-8").lower()
    assert "foodbrew_access_password" not in text
    for leaky in ("password =", "secret =", "token ="):
        assert leaky not in text
```

- [ ] **Step 2: Run it and watch it fail**

Run: `.venv/bin/pytest tests/test_fly_config.py -v`
Expected: FAIL — `fly.toml` does not exist.

- [ ] **Step 3: Write the config**

Create `fly.toml` at the repo root. Replace `foodbrew` with the real app name if it is taken, and `iad` with the region nearest the founder.

```toml
# One machine, one volume, one writer. See docs/DEPLOY.md before changing
# anything here, and tests/test_fly_config.py for what must stay true.
app = "foodbrew"
primary_region = "iad"

[build]

[env]
  FOODBREW_DB_PATH = "/data/foodbrew.db"
  FOODBREW_WEB_DIST = "/app/web/dist"

# A Fly volume lives on one physical host and attaches to exactly one machine.
# `fly scale count 2` would create a SECOND volume, not share this one, and the
# database would silently fork. Do not scale this app.
[[mounts]]
  source = "foodbrew_data"
  destination = "/data"

[http_service]
  internal_port = 8000
  force_https = true
  # Always warm: decision #10.
  auto_stop_machines = "off"
  auto_start_machines = true
  min_machines_running = 1

  [[http_service.checks]]
    interval = "30s"
    timeout = "5s"
    grace_period = "10s"
    method = "GET"
    path = "/api/v1/health"

# rolling takes the machine fully down before starting its replacement, so the
# old and new processes never hold the database at the same time. canary and
# bluegreen are refused by Fly for volume-backed apps.
[deploy]
  strategy = "rolling"

[[vm]]
  size = "shared-cpu-1x"
  memory = "512mb"
```

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/pytest tests/test_fly_config.py -v`
Expected: 9 passed.

- [ ] **Step 5: Confirm the TOML matches what Fly will read**

```bash
.venv/bin/python -c "import tomllib,pathlib; print(tomllib.loads(pathlib.Path('fly.toml').read_text())['http_service'])"
```

Expected: a dict with `internal_port: 8000`, `auto_stop_machines: 'off'`, `min_machines_running: 1`.

- [ ] **Step 6: Commit**

```bash
git add fly.toml tests/test_fly_config.py
git commit -m "feat(deploy): fly config pinned to one machine and one volume, with a contract test"
```

---

# Task 7: The daily backup job

**Files:**
- Create: `.github/workflows/backup.yml`
- Modify: `.github/workflows/` — read the existing CI workflow first to match its style

- [ ] **Step 1: Read the existing workflow so this one matches it**

```bash
ls .github/workflows/
sed -n '1,30p' .github/workflows/*.yml | head -40
```

`.github/workflows/ci.yml` pins its actions to tags — `actions/checkout@v5`, `actions/setup-python@v6`, `actions/setup-node@v5`. Match that discipline: **replace the `@master` in the flyctl action below with the newest release tag** you can confirm exists (check `https://github.com/superfly/flyctl-actions/releases`). A workflow that holds a token and can read the founder's database is the last place to track a moving branch. If no tag can be confirmed, pin the commit SHA instead and note it in the commit message.

- [ ] **Step 2: Write the workflow**

Create `.github/workflows/backup.yml`:

```yaml
# A daily copy of the founder's bench data, independent of Fly's own snapshots
# (M6 decision #4). The snapshot is TAKEN inside the machine by a stdlib-only
# module and MOVED by this job, so the container image never needs an S3 client
# (decision #5).
name: Backup

on:
  schedule:
    # 07:17 UTC — off the hour, so it does not collide with every other cron.
    - cron: "17 7 * * *"
  workflow_dispatch:

concurrency:
  group: foodbrew-backup
  cancel-in-progress: false

jobs:
  snapshot:
    runs-on: ubuntu-latest
    env:
      FLY_API_TOKEN: ${{ secrets.FLY_API_TOKEN }}
      FLY_APP: foodbrew
    steps:
      - uses: superfly/flyctl-actions/setup-flyctl@master

      - name: Take a consistent snapshot inside the machine
        # /tmp, not /data: the copy is the size of the database, and writing it
        # onto the volume would double usage during every backup (decision #6).
        run: |
          flyctl ssh console -a "$FLY_APP" -C \
            "python -m foodbrew.tools.snapshot /data/foodbrew.db /tmp/foodbrew-snapshot.db"

      - name: Pull it down
        run: flyctl ssh sftp get /tmp/foodbrew-snapshot.db foodbrew-snapshot.db -a "$FLY_APP"

      - name: Verify it is a real database before trusting it
        # An unverified backup is not a backup. A truncated transfer would
        # otherwise be uploaded and sit there looking like protection.
        run: |
          python -c "
          import sqlite3, sys
          conn = sqlite3.connect('foodbrew-snapshot.db')
          assert conn.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'integrity check failed'
          rows = conn.execute('SELECT count(*) FROM food').fetchone()[0]
          assert rows > 0, 'no rows in food'
          print(f'integrity ok, {rows} foods')
          "

      - name: Name it and compress it
        run: |
          stamp="$(date -u +%Y%m%dT%H%M%SZ)"
          gzip -9 foodbrew-snapshot.db
          mv foodbrew-snapshot.db.gz "foodbrew-${stamp}.db.gz"
          ls -la foodbrew-*.db.gz

      - name: Upload to R2
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.R2_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.R2_SECRET_ACCESS_KEY }}
          AWS_DEFAULT_REGION: auto
          R2_BUCKET: ${{ secrets.R2_BUCKET }}
          R2_ENDPOINT: ${{ secrets.R2_ENDPOINT }}
        run: |
          aws s3 cp foodbrew-*.db.gz "s3://${R2_BUCKET}/daily/" --endpoint-url "$R2_ENDPOINT"
          aws s3 ls "s3://${R2_BUCKET}/daily/" --endpoint-url "$R2_ENDPOINT" | tail -5

      - name: Remove the in-machine copy
        if: always()
        run: flyctl ssh console -a "$FLY_APP" -C "rm -f /tmp/foodbrew-snapshot.db"
```

- [ ] **Step 3: Validate the YAML parses**

```bash
.venv/bin/python -c "
import sys
try:
    import yaml
except ModuleNotFoundError:
    sys.exit('pyyaml absent — skip, GitHub will validate on push')
print(sorted(yaml.safe_load(open('.github/workflows/backup.yml'))))
"
```

Expected: either the key list, or the skip message. Do **not** add `pyyaml` as a dependency for this.

- [ ] **Step 4: Assert no secret is inlined**

Append to `tests/test_fly_config.py`:

```python
def test_the_backup_workflow_reads_every_credential_from_secrets():
    workflow = (
        pathlib.Path(__file__).resolve().parents[1]
        / ".github" / "workflows" / "backup.yml"
    ).read_text(encoding="utf-8")
    for name in (
        "FLY_API_TOKEN",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "R2_BUCKET",
        "R2_ENDPOINT",
    ):
        assert f"secrets.{name}" in workflow, f"{name} is not read from secrets"


def test_the_backup_verifies_the_copy_before_uploading_it():
    """An unverified backup is not a backup."""
    workflow = (
        pathlib.Path(__file__).resolve().parents[1]
        / ".github" / "workflows" / "backup.yml"
    ).read_text(encoding="utf-8")
    assert "integrity_check" in workflow
    assert workflow.index("integrity_check") < workflow.index("aws s3 cp")
```

Run: `.venv/bin/pytest tests/test_fly_config.py -v`
Expected: 11 passed.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/backup.yml tests/test_fly_config.py
git commit -m "feat(ops): daily verified database backup to R2, taken in-machine and moved by CI"
```

---

# Task 8: M6 contract tests

**Files:**
- Create: `tests/api/test_contracts_m6.py`

- [ ] **Step 1: Write the tests**

```python
# tests/api/test_contracts_m6.py
"""Cheap global guards for the hosted deploy, in the style of test_contracts.py."""

import pathlib

from fastapi.testclient import TestClient

from foodbrew.api.access import OPEN_PATHS
from foodbrew.api.app import create_app
from foodbrew.api.settings import Settings

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "foodbrew"


def test_the_gate_is_installed_whenever_a_password_is_configured(tmp_path):
    """The one thing that must never silently stop being true in production."""
    app = create_app(
        Settings(db_path=tmp_path / "db.sqlite", web_dist=tmp_path / "none", access_password="pw")
    )
    with TestClient(app) as client:
        assert client.get("/api/v1/enzymes").status_code == 401


def test_every_open_path_returns_no_founder_data(tmp_path):
    """OPEN_PATHS is the attack surface. Anything added to it must be inert."""
    app = create_app(
        Settings(db_path=tmp_path / "db.sqlite", web_dist=tmp_path / "none", access_password="pw")
    )
    with TestClient(app) as client:
        for path in OPEN_PATHS:
            body = client.get(path).text.lower()
            for leak in ("vinaigrette", "lactase", "recipe", "formulation", "trial"):
                assert leak not in body, f"{path} leaks '{leak}'"


def test_the_open_path_set_is_small_and_explicit():
    assert OPEN_PATHS == {"/api/v1/health", "/robots.txt"}


def test_the_access_gate_reads_no_database():
    text = (SRC / "api" / "access.py").read_text(encoding="utf-8")
    for forbidden in ("sqlite3", "foodbrew.store", "foodbrew.engine", "connect("):
        assert forbidden not in text, f"access.py touches {forbidden}"


def test_the_gate_compares_in_constant_time():
    """A `==` here leaks the shared prefix length to a timing attack."""
    text = (SRC / "api" / "access.py").read_text(encoding="utf-8")
    assert "compare_digest" in text


def test_no_tracked_file_contains_an_obvious_secret():
    for name in ("fly.toml", "docker-compose.yml", "Dockerfile", "README.md"):
        text = (ROOT / name).read_text(encoding="utf-8").lower()
        assert "foodbrew_access_password=" not in text
        assert "foodbrew_access_password:" not in text


def test_the_image_gained_no_python_dependency_for_the_deploy():
    """Decision #5: the S3 client lives in CI, never in the image."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()
    for forbidden in ("boto3", "botocore", "litestream", "s3fs"):
        assert forbidden not in pyproject, f"{forbidden} crept into the image"
```

- [ ] **Step 2: Run them**

Run: `.venv/bin/pytest tests/api/test_contracts_m6.py -v`
Expected: 7 passed.

- [ ] **Step 3: Mutation-check the two that matter**

Prove the guards actually catch the thing they name, then revert each change:

1. In `access.py`, change `hmac.compare_digest(offered, password)` to `offered == password`. Run `.venv/bin/pytest tests/api/test_contracts_m6.py -k constant_time`. Expected: FAIL. Revert.
2. In `access.py`, add `"/api/v1/enzymes"` to `OPEN_PATHS`. Run `.venv/bin/pytest tests/api/test_contracts_m6.py -k "open_path"`. Expected: both FAIL. Revert.

Confirm the revert is clean: `git diff --stat` shows nothing in `src/`.

- [ ] **Step 4: Full suite**

Run: `.venv/bin/pytest -q > /tmp/t8.txt 2>&1; grep -E "passed|failed" /tmp/t8.txt | tail -1`
Expected: `796 passed`.

- [ ] **Step 5: Commit**

```bash
git add tests/api/test_contracts_m6.py
git commit -m "test: contract guards for the hosted deploy"
```

---

# Task 9: The runbook

**Files:**
- Create: `docs/DEPLOY.md`
- Modify: `README.md`

- [ ] **Step 1: Write `docs/DEPLOY.md`**

```markdown
# Deploying the hosted instance

One Fly Machine, one volume, one password. This is a private instance for one
person, not a multi-user service — see
`docs/superpowers/plans/2026-08-17-m6-hosted-single-instance.md` for why each
choice is what it is.

## What she gets

A URL (`https://<app>.fly.dev`) and a password. Her browser prompts for it; any
username works. Nothing to install.

## First deploy

```bash
# 1. Create the app WITHOUT deploying, and without high availability.
fly launch --no-deploy --ha=false --copy-config

# 2. Create the volume. One volume, one machine, same region as fly.toml.
fly volumes create foodbrew_data --region iad --size 1

# 3. Set the password. Pick something long; she will paste it once and let the
#    browser remember it.
fly secrets set FOODBREW_ACCESS_PASSWORD="$(python -c 'import secrets;print(secrets.token_urlsafe(24))')"
fly secrets list          # confirm it is set; the value is never shown again

# 4. Deploy.
fly deploy --ha=false

# 5. VERIFY ONE MACHINE. `--ha=false` has a community report of starting two
#    anyway, and a second machine means a second volume and a forked database.
fly status
# Expect exactly one machine in the list. If there are two, destroy the extra
# NOW, before she enters any data:
#   fly machine destroy <id> --force

# 6. Raise snapshot retention from the 5-day default.
fly volumes list
fly volumes update <volume-id> --snapshot-retention 30

# 7. Smoke-test the gate. This is what catches a deploy whose secret never got
#    set — without it the instance is a public read/write endpoint.
curl -s -o /dev/null -w '%{http_code}\n' https://<app>.fly.dev/api/v1/enzymes
# Expect: 401

curl -s -u "founder:<the password>" https://<app>.fly.dev/api/v1/health
# Expect: {"status":"ok","engine_version":"1.0.0","database":"ok"}
```

## Backups

Two independent mechanisms:

1. **Fly volume snapshots** — automatic and free, retention set to 30 days
   above. Restore: `fly volumes snapshots list <volume-id>`, then
   `fly volumes create foodbrew_data --snapshot-id <id> --region iad`, then
   attach a machine to the new volume.
2. **A daily copy in R2** — `.github/workflows/backup.yml`, 07:17 UTC. It runs
   `VACUUM INTO` inside the machine, pulls the copy down, **verifies
   `PRAGMA integrity_check` and a non-zero row count before uploading**, then
   gzips it to `s3://<bucket>/daily/`.

Required GitHub Actions secrets: `FLY_API_TOKEN`, `R2_ACCESS_KEY_ID`,
`R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_ENDPOINT`.

Run it by hand any time from the Actions tab (`workflow_dispatch`). **Do that
once immediately after the first deploy** — an untested backup path is not a
backup.

### Restoring from R2

```bash
aws s3 cp s3://<bucket>/daily/foodbrew-<stamp>.db.gz . --endpoint-url <endpoint>
gunzip foodbrew-<stamp>.db.gz
python -c "import sqlite3;print(sqlite3.connect('foodbrew-<stamp>.db').execute('PRAGMA integrity_check').fetchone())"
fly ssh sftp shell -a <app>      # put the file at /data/foodbrew.db, then:
fly machine restart <id>
```

## Day 2

```bash
fly logs -a <app>                       # live logs
fly ssh console -a <app>                # shell in the machine
fly ssh sftp get /data/foodbrew.db      # pull her database down to inspect
fly status -a <app>                     # machine count and health
fly releases -a <app>                   # deploy history with image refs
fly deploy --image <previous-image-ref>  # roll back
```

## Things that will bite

- **Never `fly scale count 2`**, never add a region, never re-run
  `fly launch` without `--ha=false`. A second machine gets its own new volume
  and the database forks silently — no error, no symptom, two divergent copies.
  `tests/test_fly_config.py` guards the config; nothing can guard a CLI typo.
- **One machine means real downtime on deploy**, and a host incident can mean
  hours. Tell her that upfront so an outage does not read as lost work.
- **A failed migration leaves the app unbootable**, and Fly's smoke check stops
  the rollout but leaves the machine down. Recovery is
  `fly deploy --image <last-good>`, so know the last-good ref before deploying.
  `fly releases` has it.
- **Health is now a database read.** A 503 with a sqlite message in `fly logs`
  means the volume, not the process.
- **Rotating the password:** `fly secrets set FOODBREW_ACCESS_PASSWORD=...`
  restarts the machine. Tell her before you do it, or the app will simply stop
  letting her in.
```

- [ ] **Step 2: Add a README section**

Append to `README.md` after the local-development section:

```markdown
## The hosted instance

One private Fly.io instance for the founder: one machine, one volume, one shared
password (`FOODBREW_ACCESS_PASSWORD`). Unset that variable and the app runs open,
which is what local development and the test suite do.

Deploy steps, backup and restore, and the day-2 runbook are in
[docs/DEPLOY.md](docs/DEPLOY.md).
```

- [ ] **Step 3: Check the docs against the code**

Every command and env var in `DEPLOY.md` must exist. Verify the two that are easy to get wrong:

```bash
grep -n "FOODBREW_ACCESS_PASSWORD" src/foodbrew/api/settings.py
.venv/bin/python -m foodbrew.tools.snapshot --help 2>&1 | head -2 || true
grep -n "api/v1/health" fly.toml
```

- [ ] **Step 4: Commit**

```bash
git add docs/DEPLOY.md README.md
git commit -m "docs: the deploy and day-2 runbook for the hosted instance"
```

---

# Task 10: Full acceptance, and a container run

**Files:** none — this task only runs things.

- [ ] **Step 1: The whole suite**

```bash
.venv/bin/pytest -q > /tmp/accept.txt 2>&1; grep -E "passed|failed" /tmp/accept.txt | tail -1
.venv/bin/ruff check src tests
```

Expected: `796 passed`, `All checks passed!`.

- [ ] **Step 2: Frontend untouched**

```bash
cd web && npm run typecheck && npm run build && cd ..
```

Expected: both clean. M6 changes no frontend file; if this fails, something is wrong.

- [ ] **Step 3: Playwright, still 21**

```bash
rm -rf web/.e2e && make e2e
```

Expected: `21 passed`. The e2e server sets no `FOODBREW_ACCESS_PASSWORD`, so the gate is absent and the specs are unaffected — that is decision #12 working.

- [ ] **Step 4: Prove the gate works in a real container**

This is the step that catches a wiring mistake the test suite cannot: the image, the env var, and uvicorn together.

```bash
docker build -t foodbrew:m6 .
docker run --rm -d --name foodbrew-m6 -p 8010:8000 \
  -e FOODBREW_ACCESS_PASSWORD=letmein \
  -v "$PWD/.docker-data:/data" foodbrew:m6
sleep 6

curl -s -o /dev/null -w 'no password: %{http_code}\n' http://localhost:8010/api/v1/enzymes
curl -s -o /dev/null -w 'wrong password: %{http_code}\n' -u founder:nope http://localhost:8010/api/v1/enzymes
curl -s -o /dev/null -w 'right password: %{http_code}\n' -u founder:letmein http://localhost:8010/api/v1/enzymes
curl -s http://localhost:8010/api/v1/health
curl -s http://localhost:8010/robots.txt

docker stop foodbrew-m6
```

Expected: `401`, `401`, `200`, the health JSON with `"database":"ok"`, and `Disallow: /`.

If the Docker daemon is unavailable, **say so and leave this box unchecked** — do not mark it done on the strength of the test suite. It is the one check that exercises the image.

- [ ] **Step 5: Prove the snapshot works in the container**

```bash
docker run --rm -d --name foodbrew-m6 -p 8010:8000 \
  -e FOODBREW_ACCESS_PASSWORD=letmein -v "$PWD/.docker-data:/data" foodbrew:m6
sleep 6
docker exec foodbrew-m6 python -m foodbrew.tools.snapshot /data/foodbrew.db /tmp/snap.db
docker exec foodbrew-m6 python -c "import sqlite3;print(sqlite3.connect('/tmp/snap.db').execute('select count(*) from food').fetchone())"
docker stop foodbrew-m6 && rm -rf .docker-data
```

Expected: the printed path, then `(53,)`. This is the exact command the CI backup job runs, so a failure here means the backup would fail silently at 07:17 UTC.

- [ ] **Step 6: Commit anything the run corrected, then stop**

Everything after this is a human action against real infrastructure. Do **not** run `fly launch`, `fly deploy`, or `fly secrets set` from a plan-execution agent — those create billable resources and hold the founder's data. Hand back with the acceptance numbers and let the operator work through `docs/DEPLOY.md`.

---

## M6 exit criteria

- [x] `.venv/bin/pytest` passes with zero failures and zero skips — **813** (the plan estimated 796; the extra 17 are Task 3's added header assertions and the seven non-ASCII regressions).
- [x] `.venv/bin/ruff check src tests` is clean.
- [x] `cd web && npm run typecheck && npm run build` succeeds, with no frontend file changed by this milestone.
- [x] `make e2e` still passes all 21 specs — the gate is absent without the env var.
- [x] **Every M1–M5 test still passes untouched.** M6 changes no rule, no verdict, no schema, and no golden fixture. The only pre-existing test file that may change is none; every new assertion lives in a new file. `tests/api/test_app.py`'s health test keeps passing because the new `database` key is additive.
- [x] `tests/api/test_access.py` passes: unauthenticated 401 with a browser challenge, right password 200, malformed headers 401 rather than 500, health and robots open, no gate when unset.
- [x] `tests/api/test_contracts_m6.py` passes, and its two mutation checks were performed by hand and reverted. The constant-time guard itself had to be fixed first: a bare substring scan also matched the explanatory comment above the code, so it could not have detected `==`.
- [x] `tests/test_fly_config.py` passes — one mount at `/data`, `auto_stop_machines = "off"`, a volume-safe deploy strategy, no secret in the file, and the backup job verifies integrity before uploading.
- [x] `tests/tools/test_snapshot.py` passes, and `python -m foodbrew.tools.snapshot` produced a valid copy of the real 53-food database.
- [x] The container run in Task 10 step 4 returned 401 / 401 / 200 and `{"status":"ok","engine_version":"1.0.0","database":"ok"}`, against a real `docker build` of this branch on 2026-08-17.
- [x] The in-container snapshot in Task 10 step 5 returned `(53,)`, and `PRAGMA integrity_check` on the copy returned `ok`.

### Container verification, run 2026-08-17

Docker was unavailable during execution, so Task 10 steps 4 and 5 were left
unchecked rather than inferred. They were run afterwards against a real
`docker build` of this branch, and both passed:

```
no password:    401
wrong password: 401
right password: 200
health:         {"status":"ok","engine_version":"1.0.0","database":"ok"}
robots:         User-agent: * Disallow: /

python -m foodbrew.tools.snapshot /data/foodbrew.db /tmp/snap.db  ->  (53,)
PRAGMA integrity_check on the copy                                ->  ok
```

Three checks beyond what the plan asked for, because each covers a property the
unit tests assert but the image had never demonstrated:

- **The non-ASCII fix holds in the image.** An accented guess and an emoji guess
  both return 401, and an instance configured with `café-au-lait` as its password
  admits that password with a 200. Before the fix in `09d822c` the first two were
  500s and the third would have locked the founder out permanently.
- **Fail-open is real and looks exactly as documented.** A container started with
  no `FOODBREW_ACCESS_PASSWORD` serves `/api/v1/enzymes` with a **200** to an
  unauthenticated request. This is decision #12 behaving as designed, and it is
  the reason the deploy checklist's 401 `curl` is an exit criterion rather than a
  suggestion — it is the only thing standing between a mis-set secret and a
  public read/write endpoint holding her bench data.
- **The snapshot command is the one CI runs**, verbatim, so a failure here would
  have meant backups failing silently at 07:17 UTC.

**Operator steps, done by a human against real infrastructure (not by an agent):**

- [ ] `fly launch --no-deploy --ha=false`, volume created, secret set, deployed.
- [ ] `fly status` shows **exactly one machine**.
- [ ] Snapshot retention raised to 30 days.
- [ ] `curl` against the live URL returns 401 without a password and 200 with it.
- [ ] The backup workflow has been run once by hand and a `.db.gz` is in R2.
- [ ] A restore has been rehearsed once — download from R2, gunzip, `integrity_check` ok.
- [ ] The founder has the URL and the password, and has been told: one machine means occasional downtime, and downtime is not data loss.

---

## Plan self-review

**Coverage against what was asked.** "Hosted on a cloud server with a URL she can access" → Tasks 6, 9, 10 plus the operator steps. "Single instance, not real multi-user" → decisions #1 and #2; no schema change, no user column, and `test_the_open_path_set_is_small_and_explicit` keeps the surface honest. "Snapshots + daily copy to R2" → decision #4, Tasks 5 and 7. §11's original sketch is challenged in three places and each divergence is argued: Cloudflare Access is impossible without a domain (#1), Litestream is the wrong size (#4), and the S3 client stays out of the image (#5).

**What this plan deliberately leaves undone.** No password rotation UI — it is a `fly secrets set` away and building a settings screen for one credential is the kind of feature that grows into an auth system. No rate limiting on the gate: Fly terminates TLS and the password is 24 bytes of `token_urlsafe`, so online guessing is not the threat model; if the URL ever leaks widely, that changes. No uptime monitoring — the operator learns of an outage from the founder, which is honest for a feedback build and would not be for a production one. No `docker compose` change: the local compose file has never set a password and should keep not setting one.

**The two riskiest things here.** First, decision #12's fail-open default: an instance deployed without the secret is a public read/write endpoint, and only the checklist's `curl` catches it. That is why the 401 smoke test is an exit criterion and not a suggestion, and why Task 10 step 4 runs it against a real container. Second, the single-machine constraint is enforced by a CLI flag with a known bug, so `fly status` verification is a hard step — a forked database would be discovered weeks later as missing trials, which is unrecoverable in the way that matters.

**Placeholder scan.** No stubs. Every code block is complete and every command has an expected output. Task 7 step 1 tells the engineer to read the existing workflow before writing a new one, because the runner image and pinned action versions must match what CI already uses rather than what I guessed.

**Type consistency.** `Settings.access_password` (Task 1) is the name used in Tasks 2, 8 and 10. `install_access_gate(app, password)` (Task 2) is called with exactly that signature in `app.py`. `snapshot(db_path, out_path) -> Path` and `main(argv) -> int` (Task 5) are the names used by the workflow in Task 7 and the container check in Task 10. `OPEN_PATHS` is imported by name in Task 8.
