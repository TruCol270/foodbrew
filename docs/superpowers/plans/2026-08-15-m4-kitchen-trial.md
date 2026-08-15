# M4 — Kitchen Trial Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the last loop in v1 — the one between a prediction and reality. M3 ends with the founder holding a verdict and a report full of predictions, and no way to say what actually happened when she made the thing. M4 delivers Workflow E: a protocol generated from the evaluation's own open risks (§6.5), batch logging with the 21 CFR 114 storage gate, the four observation types, symptom entry that shows the computed dose against the evidence threshold as she types, an Observed column beside every prediction it tests, and the §6.6 honesty split in the report — her taste judgement exported as a finding, an uncontrolled texture note exported as an observation, and a symptom result exported as a hypothesis for a food scientist with the dose arithmetic attached.

**Architecture:** The three layers hold and the arrow still points one way — `api → store → engine`. Everything new that decides anything is a **pure engine module**: `protocol.py` (the trial protocol), `observations.py` (the observed envelope and the score convention), `symptoms.py` (the dose math), plus report sections. `store/` gains writers for the four tables M1 created and nobody has written to yet — `trial`, `trial_batch`, `trial_observation`, `trial_symptom_entry` — and one read that already exists (`formulations.latest_trial_ph`) finally has rows to find. `api/` gains one router and no logic. The React app gains one screen, four forms, and an Observed column on two existing panels.

**Tech Stack:** Unchanged. Python 3.12, FastAPI, Uvicorn, Pydantic v2, stdlib `sqlite3`, pytest + httpx `TestClient`, React 19 + TypeScript + Vite, react-router-dom, Playwright, Docker multi-stage. **M4 adds no runtime dependency and no database column** — see decision #1.

**Spec:** `docs/superpowers/specs/2026-08-13-enzyme-rules-engine-design.md` — read §1.3 items 8–10, §2.2 (what a v1 trial is deliberately not), §3 Workflow E, §5.3 (the four trial tables), §5.4 (`observed`), §6.3 (the envelope and the dwell table), §6.5 (protocol generation — this milestone's centre of gravity), §6.6 (the confidence tiers and the honesty split), §6.7 (measured-pH resolution, whose second branch M4 finally populates), §10 (screen 6 and the trial endpoints), §12 items 6 and 7, §13 (fixtures (p) and (q), the report lint "including trial output", the pH resolution test, the property "recording an observation never mutates a prediction"), §14's M4 line, before starting.

**Prior milestones:**
- `docs/superpowers/plans/2026-08-13-m1-engine-and-seed.md` — merged as `cc0ed27`. R1–R16, seed catalogue, golden fixtures, the pure trial helpers in `engine/trial_rules.py`.
- `docs/superpowers/plans/2026-08-14-m2-api-and-core-ui.md` — merged as `58a7c3f`. API, persistence, recipe builder, formulation setup, verdict screen.
- `docs/superpowers/plans/2026-08-14-m3-variants-compare-database-report.md` — merged to `main` as `519ba01` (PR #3). Variants, compare, database editor, proposals inbox, stale banner, report and Markdown export. **M4 branches from `main` at or after that merge**, because M4 fills two sections M3 wrote as explicit absences (M3 decision #12) and imports four modules M3 created.

---

## What M4 is not

M4 is the last v1 milestone, so the boundary is the v1 boundary (§2.2). None of the following is in scope, and no task may quietly add it:

- **Blinded or multi-subject trials.** `was_blinded` is a per-observation flag she ticks when someone happened to hand her the cup (§6.6). There is no taster table, no blind-key generation, no inter-taster agreement, and the confidence ceiling stays `suggestive`. Nothing recorded at home is ever labelled demonstrated, proven, or validated.
- **Any measurement a kitchen cannot make.** Enzyme activity, percent substrate hydrolysed, and shelf stability need a lab assay (§12 item 6). The protocol never asks for them and the report never implies them.
- **Ambient shelf-stability testing of a low-acid product.** The gate in §3 Workflow E is a refusal, not a warning — see decision #5.
- **Calibration.** Observations never retrain, adjust, or override a rule, a coefficient, or a stored prediction (§4, §13's property test). They are stored beside predictions and displayed beside them.
- **Cost modelling, the numeric solver, the LLM layer, hosted multi-user, consumer timing guidance** (§2.2 and §11 in full).

---

## Spec deviations and decisions this plan resolves

Found by tracing §5.3's columns, §6.5's table, and §6.6's tiers against `main` as merged at `519ba01`. All fifteen are approved as written — implement them as described rather than re-deciding them mid-task.

**1. M4 changes no table and no column.** `db/schema.sql` already creates `trial`, `trial_batch`, `trial_observation`, and `trial_symptom_entry` with every column §5.3 lists, including the `CHECK (storage_mode != 'ambient' OR (measured_ph IS NOT NULL AND measured_ph < 4.6))` constraint and the `type IN ('taste','usability','food_texture','storage')` constraint that keeps symptoms off the observation table. `bootstrap.EXPECTED_TABLES` already lists all four. M3 decision #1's reasoning applies unchanged: `ensure_database` compares table *names* against `sqlite_master` and never checks columns, so a column added now would leave every M1/M2/M3 database booting fine and failing on the first `INSERT`. **Every M4 feature fits the existing schema**, which forces decisions #2 and #6.

**2. Derived facts are derived, never stored — `dwell_bucket` is the one exception, and the schema is why.** `trial_observation.dwell_bucket` is a real column (§5.3), so it is written, but it is **computed on the server** from `elapsed_minutes` by `texture.dwell_bucket` and by nothing else (§6.3), and no request schema has a field for it. The confidence tier has no column, which is right: it is a pure function of `was_blinded` and `had_undressed_control` (`trial_rules.confidence_tier`, already shipped in M1) and is computed on read. A client can neither send a bucket nor send a tier. Task 17's contract test asserts both.

**3. The protocol is frozen at trial creation and never regenerates.** §5.3 says `protocol_json` is "generated, frozen at creation" and this plan reads that strictly: re-running the evaluation, editing a record, or applying a variant produces a *new* evaluation, and a new evaluation gets a *new* trial. A protocol that silently re-derived itself would move checkpoints out from under observations already recorded against them, and a checkpoint list is the one thing in the app the founder plans her week around. A trial whose evaluation has gone stale says so on the screen and offers a new trial; it does not rewrite itself. Approved by the founder on 2026-08-15; recorded because it is an interpretation, not a quotation: §5.3's "frozen at creation" is unambiguous, but §3 Workflow D's stale-evaluation banner might read as though a trial should follow its evaluation. It does not.

**4. A protocol checkpoint is either scheduled or per-use, and per-use ones are never "overdue".** §6.5 mixes two shapes in one table: things that happen on a clock (taste at day 0/3/7; texture at 0 min / 1 hr / 4 hr / overnight) and things that happen whenever she uses the product (usability log entries "per use", symptom logging "per use", make-it capture once per batch, pH entry once per batch). Modelling both as due-dated would produce a screen nagging her about a meal she has not eaten yet. **`Checkpoint.due_elapsed_minutes` is `None` for a per-use item**, and `due_checkpoints` never returns one; the screen lists them under "log these as they happen" instead. Approved by the founder on 2026-08-15; recorded because it is an interpretation, not a quotation: §6.5's table does not distinguish these, and the distinction is the difference between a useful checklist and an alarm clock.

**5. The storage gate refuses, in three places, and the refusal is the product behaviour.** §3 Workflow E: an ambient storage watch is offered "only when a measured pH below 4.6 has been entered for that batch". This plan enforces it at all three layers, deliberately redundantly, because the failure mode is a founder leaving a low-acid dressing on the counter for a week on the tool's implied authority: the `CHECK` constraint in the schema (already there), `store/trials.add_batch` raising `ValidationRejection` with the founder-facing sentence (HTTP 422), and the browser refusing to enable the ambient control until a qualifying pH is in the form (§10 screen 6 asks for exactly this: "the 4.6 gate enforced in the UI, not just the API"). A missing pH is not a permissive case: `trial_rules.ambient_storage_allowed(None)` is already `False`.

**6. Symptom capture has exactly one door, and the schema is the lock.** §5.3 says `trial_observation` "deliberately has no `symptom` type, so per-meal dose linkage is never bypassed". The schema's `CHECK` already enforces it. M4 adds the matching API-level guard: `ObservationIn.type` is a `Literal` of the four allowed values, so a `symptom` observation is a 422 from Pydantic before it reaches SQLite, and Task 17 asserts that no schema anywhere accepts it.

**7. The dose math is computed against the evaluation's frozen snapshot, not against current records, and it is frozen into the entry.** §5.3's `computed_dose_json` is "engine-calculated units delivered vs `dose_evidence_threshold`". Which threshold? The one the founder was looking at when she planned the trial, or today's? **This plan uses the evaluation's own `input_snapshot_json`** — the same `context_from_snapshot` path M3's report and dose cards use — and freezes the result into the row. The alternative reads a threshold she may have edited last night and attaches it to a meal she ate last week, which is the same class of error as recomputing a stored evaluation. Approved by the founder on 2026-08-15; recorded because it is an interpretation, not a quotation: §5.3 does not say which snapshot; this plan answers it.

**8. The live dose preview is a POST that writes nothing.** §10 screen 6: "symptom entry showing computed dose against threshold as she types". The engine is the sole source of every number (§4, §12), so the browser cannot do this arithmetic itself. `POST /trial-batches/{id}/symptom-preview` runs the same pure function `add_symptom_entry` runs and returns the same payload without touching the database; the form debounces it at 300 ms. One function, two callers, so the preview cannot disagree with what gets stored.

**9. An observed texture score maps to a verdict through a stated convention, and that convention lives beside `FALLBACK_MARGIN_PH`.** §6.3 says the envelope "carries a predicted verdict per profile and, once a trial exists, an observed one beside it", and §5.3 gives observations a `score`, not a verdict. Something has to map one to the other. `engine/observations.py` defines a documented 1–5 scale ("1 — indistinguishable from the undressed portion" … "5 — badly broken down") and maps 1–2 → pass, 3 → amber, 4–5 → red, exactly as `FALLBACK_MARGIN_PH` states its own convention: an engineering convention that makes the column computable, labelled as such wherever it is shown, **not** a scientific claim. Approved by the founder on 2026-08-15; recorded because it is an interpretation, not a quotation: this scale is invented by this plan. It is the first thing to review with the founder, because she is the one who will be scoring against it.

**10. An observation never changes a headline, an envelope, or a finding.** The observed envelope is a second column, computed on read from that evaluation's trial rows. `Evaluation.overall`, `Evaluation.envelope`, and every stored `rule_finding` are untouched, forever. This is §4's rule ("trial observations never mutate an evaluation's predictions") and §13's property test, and it is why the observed column is assembled in the *router* from two independent reads rather than being folded into `store/evaluations.get`.

**11. A trial batch's pH does change the *next* evaluation, and that is the point.** §6.7's resolution order puts `trial_batch.measured_ph` second, and `store/formulations.hydrate_context` already reads it via `latest_trial_ph`. So logging a batch pH makes existing evaluations of that formulation stale — the M3 banner fires, naming the change — and a re-run picks the measurement up labelled `observed`. That is not a bug to suppress; it is the loop the whole milestone exists to close, and M3's exit note said the banner had to be honest before a trial could write to it. Task 9 asserts the whole chain.

**12. Trial status is a small state machine, and writes stop at the terminals.** §5.3 gives four statuses and §3 Workflow E describes abandonment. `planned` → `running` on the first batch (which also sets `started_at`) → `complete` or `abandoned` when the founder says so. **A `complete` or `abandoned` trial accepts no further batches, observations, or symptom entries** — it is refused with a plain sentence offering a new trial — while everything already recorded stays visible and exported, because it was real. Approved by the founder on 2026-08-15; recorded because it is an interpretation, not a quotation: §3 says abandoning stops unmet checkpoints being due; it does not say whether late observations may still be added. This plan says no, because "abandoned after N observations" has to mean a fixed N for the report line to be true.

**13. The report's honesty split is three sections with three different words, and free text is quoted, not authored.** §6.6 splits her four questions by how much her own judgement counts as evidence: taste/make/use → **findings**; applied-food texture → **findings** with a control, **observations** without; symptom response → **hypotheses**, always with the dose math attached. The report uses those three headings literally. Her free text is reproduced verbatim inside a blockquote under a heading that names it as her words — M3's report lint (`contains_prohibited` over generated output) covers **tool-authored copy**, and Task 6 keeps that true by asserting the lint against reports built from tool copy while a separate test asserts founder free text round-trips unaltered. The tool does not edit what she wrote and does not adopt it either.

**14. "Overdue" is computed from a clock the store owns, and the engine never sees one.** `protocol.due_checkpoints(protocol, elapsed_minutes, satisfied_ids)` is pure and takes the elapsed minutes as an argument; `store/trials.py` computes them from `batch.made_at` and `clock.now_iso()`. `tests/engine/test_purity.py` stays green and the due list is testable without freezing time.

**15. One checkpoint is satisfied by one observation of the right type, in the right dwell bucket, on the right food.** The match rule is explicit so the checklist cannot drift from the data: a scheduled checkpoint is satisfied when an observation exists whose `type` equals the checkpoint's observation type, whose `dwell_bucket` equals the bucket the checkpoint's due time falls in, and whose `application_food_id` equals the checkpoint's (both empty counts as equal). Two texture checkpoints inside one bucket — 1 hr and 4 hr are both `packed` — are therefore satisfied together by one 4-hour observation. That is deliberate: the envelope she is filling is bucketed, so a second reading inside the same bucket adds nothing the envelope can show, and pretending otherwise would leave a permanently unticked box.

---

## File structure

```
foodbrew/
├── Makefile                                   #   + trial helper target
├── README.md                                  #   + the kitchen trial section
├── src/foodbrew/
│   ├── engine/                                # every new module here is pure
│   │   ├── protocol.py                        # NEW: §6.5 protocol generation, due/satisfied logic
│   │   ├── observations.py                    # NEW: the observed envelope, the score convention,
│   │   │                                      #      the §6.6 honesty split classifier
│   │   ├── symptoms.py                        # NEW: the per-meal dose math (§5.3 computed_dose_json)
│   │   ├── trial_rules.py                     #   unchanged — M1 shipped it; M4 is its first caller
│   │   └── report.py                          #   + the observed sections, the honesty split,
│   │                                          #     the envelope's Observed column
│   ├── store/
│   │   ├── trials.py                          # NEW: trial + batch writes, the status machine,
│   │   │                                      #      the storage gate, due-checkpoint assembly
│   │   ├── observations.py                    # NEW: observation and symptom-entry writes
│   │   └── evaluations.py                     #   unchanged
│   └── api/
│       ├── schemas.py                         #   + M4 wire models
│       └── routers/
│           ├── trials.py                      # NEW: §10's five trial endpoints + the preview
│           ├── evaluations.py                 #   + the observed envelope on the detail payload
│           └── export.py                      #   + trial data into ReportInput
├── web/
│   ├── e2e/trial.spec.ts                      # NEW
│   └── src/
│       ├── api/{client.ts,types.ts}           #   + trial calls and types
│       ├── components/
│       │   ├── ProtocolChecklist.tsx          # NEW
│       │   ├── BatchForm.tsx                  # NEW (owns the 4.6 gate in the browser)
│       │   ├── ObservationForm.tsx            # NEW
│       │   ├── SymptomForm.tsx                # NEW (owns the live dose preview)
│       │   ├── ObservedList.tsx               # NEW
│       │   └── EnvelopePanel.tsx              #   + the Observed column
│       ├── screens/
│       │   ├── Trial.tsx                      # NEW — §10 screen 6
│       │   ├── Home.tsx                       #   + active trials
│       │   ├── Verdict.tsx                    #   + start/open trial, observed envelope
│       │   └── Report.tsx                     #   + the observed sections
│       ├── App.tsx                            #   + /trials/:trialId
│       └── styles.css                         #   + the observed column and checklist styles
└── tests/
    ├── engine/test_{protocol,observations,symptoms}.py, test_report_trial.py
    ├── store/test_{trials,observations,trial_ph}.py
    └── api/test_{trials,trial_export,contracts_m4}.py
```

**Boundary rules to enforce in review.** M1's, M2's and M3's hold unchanged, and Task 17 adds two:

- Nothing under `engine/` imports `foodbrew.store`, `foodbrew.api`, `foodbrew.db`, `fastapi`, or `sqlite3`. `engine/protocol.py` and `engine/symptoms.py` import `json` for the same reason `engine/patch.py` does — the canonical text of a frozen payload. `tests/engine/test_purity.py` stays green.
- Nothing under `store/` imports `fastapi` or `foodbrew.api`.
- **New:** no module under `engine/` calls `now_iso`, `datetime.now`, or any clock. Time enters the engine as an argument (decision #14).
- **New:** no request schema anywhere carries `dwell_bucket`, `confidence_tier`, `status` on an observation, or an observation `type` of `symptom` (decisions #2 and #6).

---

## Task 1: `engine/observations.py` — what an observation means

The trial's vocabulary, defined before anything can write one: the four observation types, the 1–5 texture scale and its verdict mapping (decision #9), the observed envelope (§6.3), and §6.6's export classifier. Pure, and it imports M1's already-shipped `trial_rules.confidence_tier` rather than re-deriving a tier.

**Files:**
- Create: `src/foodbrew/engine/observations.py`
- Create: `tests/engine/test_observations.py`

- [ ] **Step 1: Write the module**

```python
"""Spec §6.6 and §6.3 — what a trial observation means, and what it does not.

Pure, and deliberately inert: nothing here mutates a prediction. The observed
envelope is a second column computed beside the stored one (plan decision #10),
and no function in this module can change a verdict, a finding, or a headline.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from foodbrew.engine.texture import dwell_bucket
from foodbrew.engine.trial_rules import ConfidenceTier, confidence_tier
from foodbrew.engine.types import DwellProfile, TruthLabel, Verdict, worst


class ObservationType(StrEnum):
    """Spec §5.3. Closed, and deliberately without `symptom`: symptoms are their
    own table so per-meal dose linkage is never bypassed (plan decision #6)."""

    TASTE = "taste"
    USABILITY = "usability"
    FOOD_TEXTURE = "food_texture"
    STORAGE = "storage"


#: Plan decision #9. An engineering convention that makes §6.3's Observed column
#: computable, stated wherever it is shown, NOT a scientific claim — the same
#: standing as conventions.FALLBACK_MARGIN_PH. The founder scores against this
#: wording, so the wording is the interface.
TEXTURE_SCALE: Mapping[int, str] = {
    1: "indistinguishable from the undressed portion",
    2: "slightly softer — would not notice without comparing",
    3: "clearly softer than the undressed portion",
    4: "limp, wilted, or watery",
    5: "badly broken down",
}

_TEXTURE_VERDICT: Mapping[int, Verdict] = {
    1: Verdict.PASS,
    2: Verdict.PASS,
    3: Verdict.AMBER,
    4: Verdict.RED,
    5: Verdict.RED,
}

#: Shown next to every observed verdict, so the column never reads as a measurement.
TEXTURE_SCALE_NOTE = (
    "Observed texture is scored 1 to 5 against the undressed portion and mapped to "
    "a verdict by a stated convention, not by a measurement."
)


def texture_verdict(score: int) -> Verdict:
    """Spec §6.3's Observed column, via the decision #9 convention."""
    if score not in _TEXTURE_VERDICT:
        raise ValueError(f"texture score must be 1 to 5, got {score}")
    return _TEXTURE_VERDICT[score]


@dataclass(frozen=True, slots=True)
class ObservationRecord:
    """One row of `trial_observation` (§5.3), as the engine sees it."""

    id: str
    type: ObservationType
    observed_at: str
    elapsed_minutes: int
    score: int | None = None
    free_text: str = ""
    was_blinded: bool = False
    had_undressed_control: bool = False
    application_food_id: str = ""

    @property
    def dwell_bucket(self) -> DwellProfile:
        """Spec §6.3 — derived from elapsed minutes and from nothing else."""
        return dwell_bucket(self.elapsed_minutes)

    @property
    def tier(self) -> ConfidenceTier:
        """Spec §6.6 — rigor captured opportunistically, per observation."""
        return confidence_tier(
            was_blinded=self.was_blinded,
            had_undressed_control=self.had_undressed_control,
        )

    @property
    def status(self) -> TruthLabel:
        """Every trial value is `observed` (§5.4). The tier qualifies it; nothing
        upgrades it, and no prediction ever overwrites it."""
        return TruthLabel.OBSERVED


@dataclass(frozen=True, slots=True)
class ObservedProfile:
    """One cell of §6.3's Observed column."""

    #: None means nothing was recorded in this bucket — never a pass by default.
    verdict: Verdict | None
    tier: ConfidenceTier | None
    observation_count: int
    #: The observation that set the verdict, for "why does it say that".
    driving_observation_id: str = ""


def observed_envelope(
    observations: Sequence[ObservationRecord],
) -> dict[DwellProfile, ObservedProfile]:
    """Spec §6.3 — the worst scored texture observation in each dwell bucket.

    Only `food_texture` observations with a score contribute: taste and
    usability answer different questions, and an unscored note is a comment,
    not a reading. An empty bucket reports None, because "she has not looked
    yet" and "she looked and it was fine" are different facts.
    """
    out: dict[DwellProfile, ObservedProfile] = {}
    for profile in DwellProfile:
        scored = [
            o
            for o in observations
            if o.type is ObservationType.FOOD_TEXTURE
            and o.score is not None
            and o.dwell_bucket is profile
        ]
        if not scored:
            out[profile] = ObservedProfile(None, None, 0)
            continue

        verdict = worst(texture_verdict(o.score) for o in scored)
        drivers = [o for o in scored if texture_verdict(o.score) is verdict]
        # Weakest tier among the drivers: one blinded reading does not lend its
        # rigor to an unblinded one that reached the same verdict.
        tier = (
            ConfidenceTier.SUGGESTIVE
            if all(o.tier is ConfidenceTier.SUGGESTIVE for o in drivers)
            else ConfidenceTier.ANECDOTE
        )
        out[profile] = ObservedProfile(
            verdict=verdict,
            tier=tier,
            observation_count=len(scored),
            driving_observation_id=drivers[0].id,
        )
    return out


class ExportClass(StrEnum):
    """Spec §6.6 — how much the founder's own judgement counts as evidence."""

    FINDING = "finding"
    OBSERVATION = "observation"
    HYPOTHESIS = "hypothesis"


#: Spec §6.6 — symptom response is the weakest measurement available: unblinded
#: self-report on a product she is invested in. It is never anything but a
#: hypothesis, whatever flags the entry carries.
SYMPTOM_EXPORT_CLASS = ExportClass.HYPOTHESIS


def export_class(record: ObservationRecord) -> ExportClass:
    """Spec §6.6's split, applied per observation.

    Taste and usability are subjective questions by nature, so her answer *is*
    the data. Applied-food texture is partly objective and cheaply controlled,
    so it is a finding when she used the undressed control and an observation
    when she did not. Storage is uncontrolled watching, so it is an observation;
    §6.6 does not name it, and calling it a finding would be the generous read.
    """
    if record.type in {ObservationType.TASTE, ObservationType.USABILITY}:
        return ExportClass.FINDING
    if record.type is ObservationType.FOOD_TEXTURE and record.had_undressed_control:
        return ExportClass.FINDING
    return ExportClass.OBSERVATION
```

- [ ] **Step 2: Write the tests**

```python
"""Spec §6.3's Observed column, §6.6's tiers and split, and decision #9's convention."""

import pytest

from foodbrew.engine.observations import (
    SYMPTOM_EXPORT_CLASS,
    TEXTURE_SCALE,
    ExportClass,
    ObservationRecord,
    ObservationType,
    export_class,
    observed_envelope,
    texture_verdict,
)
from foodbrew.engine.trial_rules import ConfidenceTier
from foodbrew.engine.types import DwellProfile, TruthLabel, Verdict


def obs(**kw) -> ObservationRecord:
    base = dict(
        id="o1", type=ObservationType.FOOD_TEXTURE, observed_at="2026-08-15T12:00:00+00:00",
        elapsed_minutes=0, score=1,
    )
    return ObservationRecord(**{**base, **kw})


@pytest.mark.parametrize(
    "score,expected",
    [(1, Verdict.PASS), (2, Verdict.PASS), (3, Verdict.AMBER), (4, Verdict.RED), (5, Verdict.RED)],
)
def test_the_stated_scale_maps_to_a_verdict(score, expected):
    assert texture_verdict(score) is expected


def test_the_scale_has_wording_for_every_score_it_maps():
    assert sorted(TEXTURE_SCALE) == [1, 2, 3, 4, 5]


def test_a_score_off_the_scale_is_refused_rather_than_clamped():
    with pytest.raises(ValueError):
        texture_verdict(6)


def test_an_observation_derives_its_bucket_from_elapsed_minutes(): 
    assert obs(elapsed_minutes=59).dwell_bucket is DwellProfile.IMMEDIATE
    assert obs(elapsed_minutes=60).dwell_bucket is DwellProfile.PACKED
    assert obs(elapsed_minutes=480).dwell_bucket is DwellProfile.MARINADE


def test_every_observation_is_labelled_observed():
    assert obs().status is TruthLabel.OBSERVED


def test_the_default_tier_is_anecdote_and_either_flag_lifts_it():
    assert obs().tier is ConfidenceTier.ANECDOTE
    assert obs(was_blinded=True).tier is ConfidenceTier.SUGGESTIVE
    assert obs(had_undressed_control=True).tier is ConfidenceTier.SUGGESTIVE


def test_an_empty_bucket_reports_nothing_rather_than_a_pass():
    envelope = observed_envelope([])
    assert set(envelope) == set(DwellProfile)
    assert all(cell.verdict is None and cell.observation_count == 0 for cell in envelope.values())


def test_the_worst_scored_observation_in_a_bucket_sets_that_cell():
    envelope = observed_envelope([
        obs(id="a", elapsed_minutes=60, score=1),
        obs(id="b", elapsed_minutes=200, score=4),
        obs(id="c", elapsed_minutes=300, score=3),
    ])
    cell = envelope[DwellProfile.PACKED]
    assert cell.verdict is Verdict.RED
    assert cell.observation_count == 3
    assert cell.driving_observation_id == "b"
    assert envelope[DwellProfile.IMMEDIATE].verdict is None


def test_a_rigorous_reading_does_not_lend_its_tier_to_an_unblinded_one():
    envelope = observed_envelope([
        obs(id="a", score=4, had_undressed_control=True),
        obs(id="b", score=4),
    ])
    assert envelope[DwellProfile.IMMEDIATE].tier is ConfidenceTier.ANECDOTE

    controlled_only = observed_envelope([obs(id="a", score=4, had_undressed_control=True)])
    assert controlled_only[DwellProfile.IMMEDIATE].tier is ConfidenceTier.SUGGESTIVE


def test_taste_and_usability_never_reach_the_envelope():
    envelope = observed_envelope([
        obs(type=ObservationType.TASTE, score=5),
        obs(type=ObservationType.USABILITY, score=5),
        obs(type=ObservationType.STORAGE, score=5),
    ])
    assert all(cell.verdict is None for cell in envelope.values())


def test_an_unscored_texture_note_is_a_comment_not_a_reading():
    envelope = observed_envelope([obs(score=None, free_text="looked fine")])
    assert envelope[DwellProfile.IMMEDIATE].verdict is None


def test_the_export_split_follows_6_6():
    assert export_class(obs(type=ObservationType.TASTE)) is ExportClass.FINDING
    assert export_class(obs(type=ObservationType.USABILITY)) is ExportClass.FINDING
    assert export_class(obs(had_undressed_control=True)) is ExportClass.FINDING
    assert export_class(obs(had_undressed_control=False)) is ExportClass.OBSERVATION
    assert export_class(obs(type=ObservationType.STORAGE)) is ExportClass.OBSERVATION
    assert SYMPTOM_EXPORT_CLASS is ExportClass.HYPOTHESIS


def test_blinding_alone_does_not_promote_texture_to_a_finding():
    """§6.6: the texture question is promoted by the control, which is the thing
    that makes it partly objective. Blinding lifts the tier, not the class."""
    record = obs(was_blinded=True, had_undressed_control=False)
    assert record.tier is ConfidenceTier.SUGGESTIVE
    assert export_class(record) is ExportClass.OBSERVATION


def test_no_observation_type_is_symptom():
    assert "symptom" not in {str(t) for t in ObservationType}
```

- [ ] **Step 3: Run them**

Run: `.venv/bin/pytest tests/engine/test_observations.py -q`
Expected: 17 passed.

- [ ] **Step 4: Commit**

```bash
git add src/foodbrew/engine/observations.py tests/engine/test_observations.py
git commit -m "feat(engine): observation vocabulary, the observed envelope, and the 6.6 split"
```

---

## Task 2: `engine/protocol.py` — the protocol generated from the evaluation's own gaps

Spec §6.5, in full. She never faces a blank form: the engine already knows what it is uncertain about, so the checklist is derived from the non-pass findings and the envelope. Pure — no clock (decision #14), no persistence (decision #3).

**Files:**
- Create: `src/foodbrew/engine/protocol.py`
- Create: `tests/engine/test_protocol.py`

- [ ] **Step 1: Write the module**

```python
"""Spec §6.5 — the kitchen-trial protocol, generated from an evaluation's findings.

Pure. It returns a protocol structure; it does not persist one, and it never
reads a clock — elapsed time arrives as an argument (plan decisions #3 and #14).
`store/trials.py` freezes what `generate` returns into `trial.protocol_json` at
creation and never regenerates it.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from foodbrew.engine.observations import ObservationRecord, ObservationType
from foodbrew.engine.texture import dwell_bucket
from foodbrew.engine.types import DwellProfile, EvalContext, RuleFinding, Verdict

HOUR = 60
DAY = 24 * 60


class CheckpointKind(StrEnum):
    """What the founder is being asked to do, not which table it lands in."""

    MAKE_IT = "make_it"
    PH = "ph"
    TASTE = "taste"
    USABILITY = "usability"
    FOOD_TEXTURE = "food_texture"
    STORAGE = "storage"
    SYMPTOM = "symptom"


#: Which `trial_observation.type` fills a checkpoint. MAKE_IT and PH are batch
#: fields and SYMPTOM has its own table (§5.3), so those three map to nothing.
_OBSERVATION_TYPE: Mapping[CheckpointKind, ObservationType | None] = {
    CheckpointKind.TASTE: ObservationType.TASTE,
    CheckpointKind.USABILITY: ObservationType.USABILITY,
    CheckpointKind.FOOD_TEXTURE: ObservationType.FOOD_TEXTURE,
    CheckpointKind.STORAGE: ObservationType.STORAGE,
    CheckpointKind.MAKE_IT: None,
    CheckpointKind.PH: None,
    CheckpointKind.SYMPTOM: None,
}

#: Spec §6.5 — the fixed schedules. Taste and storage watch the jar over a week;
#: texture watches the plate across the three dwell buckets of §6.3.
_TASTE_SCHEDULE = (0, 3 * DAY, 7 * DAY)
_STORAGE_SCHEDULE = (0, 3 * DAY, 7 * DAY)
_TEXTURE_SCHEDULE = (0, 1 * HOUR, 4 * HOUR, 24 * HOUR)

#: Spec §3 Workflow E and §12 item 6. Fixed copy, on every protocol.
STANDING_NOTES: tuple[str, ...] = (
    "Get the enzyme by opening capsules of a product you can already buy — Lactaid "
    "or Beano. It is food grade and it is labelled in the same units the doses here "
    "use, so the arithmetic is exact rather than estimated. Do not eat bulk "
    "technical-grade enzyme.",
    "A kitchen cannot measure enzyme activity, how much of the substrate was broken "
    "down, or shelf stability. Those need a lab. What this trial can record is "
    "taste, how it was to make, how it was to use, what it did to the food it sat "
    "on, and pH.",
    "Room-temperature storage is only offered for a batch with a measured pH below "
    "4.6. Without that measurement the schedule stays refrigerated, because an "
    "unknown pH is not an argument for leaving it on the counter.",
)


@dataclass(frozen=True, slots=True)
class Checkpoint:
    id: str
    kind: CheckpointKind
    prompt: str
    raised_by: tuple[str, ...]
    #: None means per-use: logged when it happens, never overdue (decision #4).
    due_elapsed_minutes: int | None = None
    application_food_id: str = ""

    @property
    def observation_type(self) -> ObservationType | None:
        return _OBSERVATION_TYPE[self.kind]

    @property
    def is_scheduled(self) -> bool:
        return self.due_elapsed_minutes is not None

    @property
    def dwell_bucket(self) -> DwellProfile | None:
        if self.due_elapsed_minutes is None:
            return None
        return dwell_bucket(self.due_elapsed_minutes)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": str(self.kind),
            "prompt": self.prompt,
            "raised_by": list(self.raised_by),
            "due_elapsed_minutes": self.due_elapsed_minutes,
            "application_food_id": self.application_food_id,
        }

    @classmethod
    def from_dict(cls, payload: Mapping) -> Checkpoint:
        return cls(
            id=payload["id"],
            kind=CheckpointKind(payload["kind"]),
            prompt=payload["prompt"],
            raised_by=tuple(payload.get("raised_by", ())),
            due_elapsed_minutes=payload.get("due_elapsed_minutes"),
            application_food_id=payload.get("application_food_id", ""),
        )


@dataclass(frozen=True, slots=True)
class Protocol:
    engine_version: str
    checkpoints: tuple[Checkpoint, ...]
    notes: tuple[str, ...] = STANDING_NOTES

    def as_dict(self) -> dict:
        return {
            "engine_version": self.engine_version,
            "checkpoints": [c.as_dict() for c in self.checkpoints],
            "notes": list(self.notes),
        }

    def to_json(self) -> str:
        """Frozen text, sorted keys — the same discipline as the input snapshot."""
        return json.dumps(self.as_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, text: str) -> Protocol:
        payload = json.loads(text)
        return cls(
            engine_version=payload["engine_version"],
            checkpoints=tuple(Checkpoint.from_dict(c) for c in payload["checkpoints"]),
            notes=tuple(payload.get("notes", ())),
        )


def _non_pass(findings: Sequence[RuleFinding], rule_id: str) -> tuple[RuleFinding, ...]:
    return tuple(
        f for f in findings if f.rule_id == rule_id and f.verdict is not Verdict.PASS
    )


def _checkpoint(
    kind: CheckpointKind,
    prompt: str,
    raised_by: Sequence[str],
    due: int | None = None,
    application_food_id: str = "",
) -> Checkpoint:
    slot = "per_use" if due is None else str(due)
    return Checkpoint(
        id=f"{kind}:{slot}:{application_food_id}",
        kind=kind,
        prompt=prompt,
        raised_by=tuple(raised_by),
        due_elapsed_minutes=due,
        application_food_id=application_food_id,
    )


def generate(
    *,
    context: EvalContext,
    findings: Sequence[RuleFinding],
    envelope: Mapping[DwellProfile, Verdict],
    engine_version: str,
) -> Protocol:
    """Spec §6.5 — map an evaluation's findings and gaps to things to watch."""
    checkpoints: list[Checkpoint] = []

    # Every trial, whatever the findings say (§6.5's last two rows).
    checkpoints.append(
        _checkpoint(
            CheckpointKind.MAKE_IT,
            "Log the batch as you make it: total minutes, how hard it was out of 5, "
            "what went wrong, and where in the sequence the enzyme went in.",
            ("every trial",),
        )
    )
    checkpoints.append(
        _checkpoint(
            CheckpointKind.USABILITY,
            "Each time you use it: did one squeeze do it, did you reach for a second, "
            "did it feel natural?",
            ("every trial",),
        )
    )

    # R8 AMBER — in-jar drift predicted (§6.5 row 1).
    drift = _non_pass(findings, "R8")
    if drift:
        for due in _TASTE_SCHEDULE:
            checkpoints.append(
                _checkpoint(
                    CheckpointKind.TASTE,
                    "Taste it and smell it. Sweeter than when you made it? Any off "
                    "smell? Has it separated or changed colour?",
                    ("R8",),
                    due=due,
                )
            )

    # R1 non-pass, or no measured pH on the formulation (§6.5 row 2).
    if _non_pass(findings, "R1") or not context.formulation.measured_ph.usable:
        raised = ("R1",) if _non_pass(findings, "R1") else ("no measured pH",)
        checkpoints.append(
            _checkpoint(
                CheckpointKind.PH,
                "Measure the pH of the batch with a strip or a meter and enter it. "
                "Optional — and it is the reading that unlocks a room-temperature "
                "storage watch, and that later evaluations will use in place of the "
                "estimate.",
                raised,
            )
        )

    # R7 AMBER or cannot_assess — dose against the evidence threshold (§6.5 row 3).
    if _non_pass(findings, "R7"):
        checkpoints.append(
            _checkpoint(
                CheckpointKind.SYMPTOM,
                "Each meal: log which trigger food you ate, how much, and how many "
                "doses you used. The dose you actually delivered is worked out and "
                "compared with the evidence threshold, so a result that means "
                "nothing can be told apart from one that does.",
                ("R7",),
            )
        )

    # R4 AMBER — wet premix, so the jar is worth watching (§6.5 row 4).
    if _non_pass(findings, "R4"):
        for due in _STORAGE_SCHEDULE:
            checkpoints.append(
                _checkpoint(
                    CheckpointKind.STORAGE,
                    "Storage watch: look at the jar. Separation, colour, smell, "
                    "pressure in the bottle, anything that has moved.",
                    ("R4",),
                    due=due,
                )
            )

    # R15 envelope non-pass — the plate, against an undressed control (§6.5 row 5).
    if any(v is not Verdict.PASS for v in envelope.values()):
        for food_id in context.formulation.application_food_ids:
            for due in _TEXTURE_SCHEDULE:
                food = context.foods.get(food_id)
                name = food.name if food else food_id
                checkpoints.append(
                    _checkpoint(
                        CheckpointKind.FOOD_TEXTURE,
                        f"Dress some {name} and leave an equal portion undressed in "
                        f"the same fridge. Compare them and score the dressed one "
                        f"from 1 (indistinguishable) to 5 (badly broken down).",
                        ("R15",),
                        due=due,
                        application_food_id=food_id,
                    )
                )

    checkpoints.sort(
        key=lambda c: (
            c.due_elapsed_minutes is None,
            c.due_elapsed_minutes if c.due_elapsed_minutes is not None else 0,
            str(c.kind),
            c.application_food_id,
        )
    )
    return Protocol(engine_version=engine_version, checkpoints=tuple(checkpoints))


def satisfied_checkpoint_ids(
    protocol: Protocol, observations: Sequence[ObservationRecord]
) -> frozenset[str]:
    """Plan decision #15 — type, dwell bucket, and food all have to line up.

    Two checkpoints inside one bucket (1 hr and 4 hr are both `packed`) are
    satisfied together, because the envelope they fill is bucketed and a second
    reading in the same bucket cannot change it.
    """
    done: set[str] = set()
    for checkpoint in protocol.checkpoints:
        if not checkpoint.is_scheduled:
            continue
        for record in observations:
            if (
                record.type is checkpoint.observation_type
                and record.dwell_bucket is checkpoint.dwell_bucket
                and record.application_food_id == checkpoint.application_food_id
            ):
                done.add(checkpoint.id)
                break
    return frozenset(done)


def due_checkpoints(
    protocol: Protocol,
    *,
    elapsed_minutes: int,
    satisfied_ids: frozenset[str],
) -> tuple[Checkpoint, ...]:
    """Scheduled, reached, and not yet answered. Per-use items are never due."""
    return tuple(
        c
        for c in protocol.checkpoints
        if c.is_scheduled
        and c.due_elapsed_minutes <= elapsed_minutes
        and c.id not in satisfied_ids
    )


def per_use_checkpoints(protocol: Protocol) -> tuple[Checkpoint, ...]:
    """The other half of decision #4 — logged as they happen, listed separately."""
    return tuple(c for c in protocol.checkpoints if not c.is_scheduled)
```

- [ ] **Step 2: Write the tests**

```python
"""Spec §6.5's mapping, and the due/satisfied logic of plan decisions #4 and #15."""

import pytest

from foodbrew.engine.language import contains_prohibited
from foodbrew.engine.observations import ObservationRecord, ObservationType
from foodbrew.engine.protocol import (
    DAY,
    CheckpointKind,
    Protocol,
    due_checkpoints,
    generate,
    per_use_checkpoints,
    satisfied_checkpoint_ids,
)
from foodbrew.engine.types import DwellProfile, Format, Phase, RuleFinding, Verdict

VERSION = "test-engine"


def finding(rule_id, verdict=Verdict.AMBER):
    return RuleFinding(rule_id=rule_id, verdict=verdict, message=f"{rule_id} says so")


def kinds(protocol):
    return {c.kind for c in protocol.checkpoints}


@pytest.fixture
def ctx(make_ctx):
    return make_ctx(
        fmt=Format.PREMIXED_WET,
        enzymes=(("lactase_fungal_acid", 9000.0, Phase.WET),),
        recipe=(("olive_oil", 100.0), ("white_vinegar", 50.0)),
        trigger_foods=("milk",),
        application_foods=("romaine",),
    )


PASS_ENVELOPE = {p: Verdict.PASS for p in DwellProfile}


def test_every_protocol_carries_the_make_it_and_usability_items(ctx):
    protocol = generate(context=ctx, findings=(), envelope=PASS_ENVELOPE, engine_version=VERSION)
    assert kinds(protocol) == {CheckpointKind.MAKE_IT, CheckpointKind.USABILITY, CheckpointKind.PH}


def test_a_formulation_with_a_measured_ph_and_a_passing_r1_is_not_asked_for_ph(make_ctx):
    ctx = make_ctx(measured_ph=4.2, recipe=(("olive_oil", 100.0),), trigger_foods=("milk",))
    protocol = generate(context=ctx, findings=(), envelope=PASS_ENVELOPE, engine_version=VERSION)
    assert CheckpointKind.PH not in kinds(protocol)


def test_r8_amber_schedules_taste_at_day_0_3_and_7(ctx):
    protocol = generate(
        context=ctx, findings=(finding("R8"),), envelope=PASS_ENVELOPE, engine_version=VERSION
    )
    taste = [c for c in protocol.checkpoints if c.kind is CheckpointKind.TASTE]
    assert [c.due_elapsed_minutes for c in taste] == [0, 3 * DAY, 7 * DAY]
    assert all(c.raised_by == ("R8",) for c in taste)


def test_r4_amber_schedules_the_storage_watch(ctx):
    protocol = generate(
        context=ctx, findings=(finding("R4"),), envelope=PASS_ENVELOPE, engine_version=VERSION
    )
    assert CheckpointKind.STORAGE in kinds(protocol)


def test_r7_non_pass_adds_the_per_meal_symptom_item_and_it_is_never_due(ctx):
    protocol = generate(
        context=ctx,
        findings=(finding("R7", Verdict.CANNOT_ASSESS),),
        envelope=PASS_ENVELOPE,
        engine_version=VERSION,
    )
    symptom = [c for c in protocol.checkpoints if c.kind is CheckpointKind.SYMPTOM]
    assert len(symptom) == 1
    assert symptom[0].due_elapsed_minutes is None
    assert symptom[0] in per_use_checkpoints(protocol)
    assert due_checkpoints(protocol, elapsed_minutes=10**6, satisfied_ids=frozenset()) == ()


def test_a_passing_rule_asks_for_nothing(ctx):
    protocol = generate(
        context=ctx,
        findings=(finding("R8", Verdict.PASS), finding("R4", Verdict.PASS)),
        envelope=PASS_ENVELOPE,
        engine_version=VERSION,
    )
    assert CheckpointKind.TASTE not in kinds(protocol)
    assert CheckpointKind.STORAGE not in kinds(protocol)


def test_an_envelope_non_pass_schedules_texture_per_application_food(ctx):
    envelope = {**PASS_ENVELOPE, DwellProfile.MARINADE: Verdict.RED}
    protocol = generate(context=ctx, findings=(), envelope=envelope, engine_version=VERSION)
    texture = [c for c in protocol.checkpoints if c.kind is CheckpointKind.FOOD_TEXTURE]
    assert [c.due_elapsed_minutes for c in texture] == [0, 60, 240, 1440]
    assert {c.application_food_id for c in texture} == {"romaine"}
    assert "undressed" in texture[0].prompt


def test_a_passing_envelope_schedules_no_texture_checkpoint(ctx):
    protocol = generate(context=ctx, findings=(), envelope=PASS_ENVELOPE, engine_version=VERSION)
    assert CheckpointKind.FOOD_TEXTURE not in kinds(protocol)


def test_checkpoint_ids_are_unique_and_the_order_is_deterministic(ctx):
    envelope = {**PASS_ENVELOPE, DwellProfile.PACKED: Verdict.AMBER}
    args = dict(
        context=ctx,
        findings=(finding("R8"), finding("R4"), finding("R7")),
        envelope=envelope,
        engine_version=VERSION,
    )
    first, second = generate(**args), generate(**args)
    ids = [c.id for c in first.checkpoints]
    assert len(ids) == len(set(ids))
    assert first.to_json() == second.to_json()


def test_a_protocol_round_trips_through_json(ctx):
    protocol = generate(
        context=ctx, findings=(finding("R8"),), envelope=PASS_ENVELOPE, engine_version=VERSION
    )
    assert Protocol.from_json(protocol.to_json()) == protocol


def test_due_returns_reached_and_unanswered_scheduled_items_only(ctx):
    protocol = generate(
        context=ctx, findings=(finding("R8"),), envelope=PASS_ENVELOPE, engine_version=VERSION
    )
    day_zero = due_checkpoints(protocol, elapsed_minutes=0, satisfied_ids=frozenset())
    assert [c.due_elapsed_minutes for c in day_zero] == [0]

    later = due_checkpoints(protocol, elapsed_minutes=4 * DAY, satisfied_ids=frozenset())
    assert [c.due_elapsed_minutes for c in later] == [0, 3 * DAY]

    answered = frozenset({day_zero[0].id})
    assert day_zero[0] not in due_checkpoints(
        protocol, elapsed_minutes=4 * DAY, satisfied_ids=answered
    )


def test_an_observation_satisfies_a_checkpoint_by_type_bucket_and_food(ctx):
    envelope = {**PASS_ENVELOPE, DwellProfile.MARINADE: Verdict.RED}
    protocol = generate(context=ctx, findings=(), envelope=envelope, engine_version=VERSION)

    wrong_food = ObservationRecord(
        id="a", type=ObservationType.FOOD_TEXTURE, observed_at="t", elapsed_minutes=0,
        score=2, application_food_id="cucumber",
    )
    assert satisfied_checkpoint_ids(protocol, [wrong_food]) == frozenset()

    right = ObservationRecord(
        id="b", type=ObservationType.FOOD_TEXTURE, observed_at="t", elapsed_minutes=0,
        score=2, application_food_id="romaine",
    )
    satisfied = satisfied_checkpoint_ids(protocol, [right])
    assert satisfied == frozenset({"food_texture:0:romaine"})


def test_one_reading_satisfies_both_checkpoints_in_its_bucket(ctx):
    """Decision #15: 1 hr and 4 hr are both `packed`, and the envelope is bucketed."""
    envelope = {**PASS_ENVELOPE, DwellProfile.MARINADE: Verdict.RED}
    protocol = generate(context=ctx, findings=(), envelope=envelope, engine_version=VERSION)
    four_hours = ObservationRecord(
        id="c", type=ObservationType.FOOD_TEXTURE, observed_at="t", elapsed_minutes=240,
        score=3, application_food_id="romaine",
    )
    satisfied = satisfied_checkpoint_ids(protocol, [four_hours])
    assert satisfied == frozenset({"food_texture:60:romaine", "food_texture:240:romaine"})


def test_no_protocol_copy_uses_a_prohibited_word(ctx):
    """§13's report lint covers trial output, and the protocol is trial output."""
    envelope = {**PASS_ENVELOPE, DwellProfile.MARINADE: Verdict.RED}
    protocol = generate(
        context=ctx,
        findings=(finding("R1", Verdict.RED), finding("R4"), finding("R7"), finding("R8")),
        envelope=envelope,
        engine_version=VERSION,
    )
    assert contains_prohibited(protocol.to_json()) == ()


def test_the_standing_notes_state_the_storage_gate_and_the_sourcing_advice(ctx):
    protocol = generate(context=ctx, findings=(), envelope=PASS_ENVELOPE, engine_version=VERSION)
    text = " ".join(protocol.notes)
    assert "4.6" in text
    assert "Lactaid" in text
    assert "lab" in text
```

- [ ] **Step 3: Run them**

Run: `.venv/bin/pytest tests/engine/test_protocol.py -q`
Expected: 15 passed.

- [ ] **Step 4: Check the engine is still pure**

Run: `.venv/bin/pytest tests/engine/test_purity.py -q`
Expected: unchanged — `protocol.py` imports `json` and nothing else outside the engine.

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/engine/protocol.py tests/engine/test_protocol.py
git commit -m "feat(engine): generate the kitchen-trial protocol from an evaluation's own gaps"
```

---

## Task 3: `engine/symptoms.py` — the per-meal dose math

Spec §5.3's `computed_dose_json` and §10 screen 6's "computed dose against threshold as she types". One pure function, two callers: the live preview and the stored entry (decision #8). It reuses `dosing.assess_dose` so R7's arithmetic and the meal's arithmetic cannot diverge.

**Files:**
- Create: `src/foodbrew/engine/symptoms.py`
- Create: `tests/engine/test_symptoms.py`

- [ ] **Step 1: Write the module**

```python
"""Spec §5.3 / §10 screen 6 — what a meal actually delivered, against the threshold.

Pure. The same function backs the live preview and the stored entry, so what she
watched while typing is what gets frozen into the row (plan decision #8).

This is not a kinetics model and does not pretend to be one: it multiplies the
per-serving dose she chose by the number of doses she used, and compares that
with the enzyme's evidence threshold. §12 item 2 already says dose guidance is
benchmark-based; this is the same arithmetic applied to one meal.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from foodbrew.engine.dosing import assess_dose
from foodbrew.engine.types import EvalContext, Tracked, TruthLabel

#: The one amount unit the substrate-load arithmetic understands. A trigger
#: food's `typical_load_value` is a per-serving figure (§9.3), so servings is
#: the only unit that can be multiplied by it without inventing a conversion.
SERVINGS = "servings"


@dataclass(frozen=True, slots=True)
class EnzymeDose:
    enzyme_id: str
    enzyme_name: str
    dose_unit: str
    #: Dose per serving of dressing, as selected on the formulation.
    dose_per_serving: float | None
    units_delivered: float | None
    threshold: Tracked
    #: None whenever any input is unusable — never a guess, exactly as R7.
    meets_threshold: bool | None
    ratio: float | None
    blocking_field: str = ""

    def as_dict(self) -> dict:
        return {
            "enzyme_id": self.enzyme_id,
            "enzyme_name": self.enzyme_name,
            "dose_unit": self.dose_unit,
            "dose_per_serving": self.dose_per_serving,
            "units_delivered": self.units_delivered,
            "threshold": {
                "value": self.threshold.value,
                "status": str(self.threshold.status),
                "source": self.threshold.source,
            },
            "meets_threshold": self.meets_threshold,
            "ratio": self.ratio,
            "blocking_field": self.blocking_field,
        }


@dataclass(frozen=True, slots=True)
class SymptomDoseMath:
    trigger_food_id: str
    trigger_food_name: str
    amount_value: float | None
    amount_unit: str
    doses_used: float | None
    substrate_ids: tuple[str, ...]
    enzymes: tuple[EnzymeDose, ...]
    #: The substrate this meal presented, when it can be worked out at all.
    substrate_load: Tracked
    #: Plain-English statement of what could not be worked out, if anything.
    note: str = ""

    def as_dict(self) -> dict:
        return {
            "trigger_food_id": self.trigger_food_id,
            "trigger_food_name": self.trigger_food_name,
            "amount_value": self.amount_value,
            "amount_unit": self.amount_unit,
            "doses_used": self.doses_used,
            "substrate_ids": list(self.substrate_ids),
            "enzymes": [e.as_dict() for e in self.enzymes],
            "substrate_load": {
                "value": self.substrate_load.value,
                "status": str(self.substrate_load.status),
                "source": self.substrate_load.source,
            },
            "note": self.note,
        }


def _load_for_meal(food, amount_value: float | None, amount_unit: str) -> tuple[Tracked, str]:
    if not food.typical_load_value.usable:
        return (
            Tracked(None, TruthLabel.UNCONFIRMED, f"{food.id}.typical_load_value"),
            f"How much substrate a serving of {food.name} carries is not recorded, so "
            f"the amount you ate cannot be turned into a load.",
        )
    if amount_value is None:
        return (
            Tracked(None, TruthLabel.UNCONFIRMED, "no amount entered"),
            "Enter how much you ate to see the load this meal presented.",
        )
    if amount_unit != SERVINGS:
        return (
            Tracked(None, TruthLabel.UNCONFIRMED, f"amount unit '{amount_unit}'"),
            f"Amounts are counted in servings here, because the recorded load for "
            f"{food.name} is a per-serving figure. Convert what you ate to servings "
            f"to see the load.",
        )
    value = float(food.typical_load_value.value) * float(amount_value)
    return (
        Tracked(
            value,
            TruthLabel.CALCULATED,
            f"{food.typical_load_value.value} {food.typical_load_unit} per serving "
            f"× {amount_value} servings",
        ),
        "",
    )


def computed_dose(
    *,
    context: EvalContext,
    trigger_food_id: str,
    amount_value: float | None,
    amount_unit: str,
    doses_used: float | None,
) -> SymptomDoseMath:
    """Spec §5.3 — units delivered vs `dose_evidence_threshold`, for one meal.

    `context` is the evaluation's own frozen snapshot (plan decision #7), so a
    later edit to an enzyme's threshold cannot retroactively change what a meal
    already eaten is judged against.
    """
    food = context.foods.get(trigger_food_id)
    if food is None:
        return SymptomDoseMath(
            trigger_food_id=trigger_food_id, trigger_food_name=trigger_food_id,
            amount_value=amount_value, amount_unit=amount_unit, doses_used=doses_used,
            substrate_ids=(), enzymes=(),
            substrate_load=Tracked(None, TruthLabel.UNCONFIRMED, "unknown food"),
            note=f"'{trigger_food_id}' is not a food this evaluation knew about.",
        )

    substrate_ids = tuple(food.contains_substrate_ids)
    load, note = _load_for_meal(food, amount_value, amount_unit)

    doses: list[EnzymeDose] = []
    for selected in context.selected_enzymes():
        enzyme = context.enzyme_for(selected)
        if enzyme.substrate_id not in substrate_ids:
            continue

        threshold = enzyme.dose_evidence_threshold
        delivered = (
            float(selected.dose) * float(doses_used)
            if selected.dose is not None and doses_used is not None
            else None
        )
        blocking = ""
        if selected.dose is None:
            blocking = f"{enzyme.id}: no dose is set on this formulation"
        elif doses_used is None:
            blocking = "no number of doses entered"
        elif not threshold.usable:
            blocking = f"{enzyme.id}.dose_evidence_threshold"

        if delivered is not None and threshold.usable:
            assessment = assess_dose(delivered, float(threshold.value), None)
            meets, ratio = assessment.meets_threshold, assessment.ratio
        else:
            meets = ratio = None

        doses.append(
            EnzymeDose(
                enzyme_id=enzyme.id, enzyme_name=enzyme.name, dose_unit=enzyme.dose_unit,
                dose_per_serving=selected.dose, units_delivered=delivered,
                threshold=threshold, meets_threshold=meets, ratio=ratio,
                blocking_field=blocking,
            )
        )

    if not doses:
        covered = ", ".join(substrate_ids) if substrate_ids else "no recorded substrate"
        note = (
            f"No enzyme on this formulation targets what {food.name} carries "
            f"({covered}). Whatever happened at this meal, the blend was not "
            f"working on it."
        )

    return SymptomDoseMath(
        trigger_food_id=food.id, trigger_food_name=food.name,
        amount_value=amount_value, amount_unit=amount_unit, doses_used=doses_used,
        substrate_ids=substrate_ids, enzymes=tuple(doses),
        substrate_load=load, note=note,
    )
```

- [ ] **Step 2: Write the tests**

```python
"""Spec §5.3's computed_dose_json — one meal's arithmetic, and its refusals."""

import dataclasses

import pytest

from foodbrew.engine.language import contains_prohibited
from foodbrew.engine.symptoms import SERVINGS, computed_dose
from foodbrew.engine.types import Phase, Tracked, TruthLabel


@pytest.fixture
def ctx(make_ctx, with_load):
    return make_ctx(
        enzymes=(("lactase_fungal_acid", 9000.0, Phase.WET),),
        recipe=(("olive_oil", 100.0),),
        trigger_foods=("milk",),
        foods=with_load(milk=6.0),
    )


def test_units_delivered_is_the_dose_times_the_doses_used(ctx):
    math = computed_dose(
        context=ctx, trigger_food_id="milk", amount_value=1.0,
        amount_unit=SERVINGS, doses_used=2.0,
    )
    entry = math.enzymes[0]
    assert entry.enzyme_id == "lactase_fungal_acid"
    assert entry.units_delivered == 18000.0


def test_the_load_scales_with_servings_and_says_how(ctx):
    math = computed_dose(
        context=ctx, trigger_food_id="milk", amount_value=2.0,
        amount_unit=SERVINGS, doses_used=1.0,
    )
    assert math.substrate_load.value == 12.0
    assert math.substrate_load.status is TruthLabel.CALCULATED
    assert "per serving" in math.substrate_load.source
    assert math.note == ""


def test_an_unrecognised_unit_refuses_the_load_rather_than_converting(ctx):
    math = computed_dose(
        context=ctx, trigger_food_id="milk", amount_value=250.0,
        amount_unit="ml", doses_used=1.0,
    )
    assert math.substrate_load.value is None
    assert "servings" in math.note
    # The dose arithmetic is independent of the amount and still works.
    assert math.enzymes[0].units_delivered == 9000.0


def test_an_unconfirmed_threshold_reports_cannot_tell_and_names_the_field(ctx, seed):
    catalog = dict(seed.enzymes)
    catalog["lactase_fungal_acid"] = dataclasses.replace(
        catalog["lactase_fungal_acid"],
        dose_evidence_threshold=Tracked(None, TruthLabel.UNCONFIRMED),
    )
    context = dataclasses.replace(ctx, enzymes=catalog)
    math = computed_dose(
        context=context, trigger_food_id="milk", amount_value=1.0,
        amount_unit=SERVINGS, doses_used=1.0,
    )
    entry = math.enzymes[0]
    assert entry.meets_threshold is None
    assert entry.ratio is None
    assert entry.blocking_field.endswith("dose_evidence_threshold")


def test_no_doses_entered_yet_is_a_gap_not_a_zero(ctx):
    math = computed_dose(
        context=ctx, trigger_food_id="milk", amount_value=1.0,
        amount_unit=SERVINGS, doses_used=None,
    )
    entry = math.enzymes[0]
    assert entry.units_delivered is None
    assert entry.meets_threshold is None
    assert entry.blocking_field == "no number of doses entered"


def test_a_meal_no_selected_enzyme_covers_says_so_plainly(ctx):
    math = computed_dose(
        context=ctx, trigger_food_id="romaine", amount_value=1.0,
        amount_unit=SERVINGS, doses_used=1.0,
    )
    assert math.enzymes == ()
    assert "was not working on it" in math.note


def test_an_unknown_food_is_refused_rather_than_guessed(ctx):
    math = computed_dose(
        context=ctx, trigger_food_id="nope", amount_value=1.0,
        amount_unit=SERVINGS, doses_used=1.0,
    )
    assert math.enzymes == ()
    assert "not a food this evaluation knew about" in math.note


def test_meeting_the_threshold_is_reported_both_ways(ctx, seed):
    under = dataclasses.replace(
        ctx,
        formulation=dataclasses.replace(
            ctx.formulation,
            enzymes=(dataclasses.replace(ctx.formulation.enzymes[0], dose=100.0),),
        ),
    )
    assert computed_dose(
        context=under, trigger_food_id="milk", amount_value=1.0,
        amount_unit=SERVINGS, doses_used=1.0,
    ).enzymes[0].meets_threshold is False

    assert computed_dose(
        context=ctx, trigger_food_id="milk", amount_value=1.0,
        amount_unit=SERVINGS, doses_used=1.0,
    ).enzymes[0].meets_threshold is True


def test_the_payload_round_trips_as_plain_json(ctx):
    import json

    math = computed_dose(
        context=ctx, trigger_food_id="milk", amount_value=1.0,
        amount_unit=SERVINGS, doses_used=1.0,
    )
    text = json.dumps(math.as_dict(), sort_keys=True)
    assert json.loads(text)["enzymes"][0]["units_delivered"] == 9000.0
    assert contains_prohibited(text) == ()
```

- [ ] **Step 3: Run them**

Run: `.venv/bin/pytest tests/engine/test_symptoms.py -q`
Expected: 9 passed. If `test_meeting_the_threshold_is_reported_both_ways` fails, check the seeded `dose_evidence_threshold` for `lactase_fungal_acid` — it is the FCC figure from §6.1 R7 and 9,000 clears it.

- [ ] **Step 4: Commit**

```bash
git add src/foodbrew/engine/symptoms.py tests/engine/test_symptoms.py
git commit -m "feat(engine): per-meal dose math against the evidence threshold"
```

---

## Task 4: `engine/report.py` — the observed sections and the §6.6 honesty split

M3 wrote `_observed_section()` as an explicit absence and left the envelope's Observed column reading "no trial yet" (M3 decision #12). M4 fills both. The renderer stays pure and stays ignorant of SQLite: the caller hands it a `TrialReport` already assembled.

**Files:**
- Modify: `src/foodbrew/engine/report.py`
- Create: `tests/engine/test_report_trial.py`

- [ ] **Step 1: Add the trial model to `report.py`**

Add to the imports at the top of the file:

```python
from foodbrew.engine.observations import ExportClass
```

Then insert these dataclasses immediately above `ReportInput`:

```python
_OCCASION_SHORT: Mapping[DwellProfile, str] = {
    DwellProfile.IMMEDIATE: "within the hour",
    DwellProfile.PACKED: "1 to 8 hours",
    DwellProfile.MARINADE: "8 hours or more",
}


@dataclass(frozen=True, slots=True)
class ReportObservation:
    """One `trial_observation`, already classified by §6.6."""

    observation_type: str
    export_class: ExportClass
    tier: str
    occasion: str
    observed_at: str
    elapsed_minutes: int
    application_food_name: str = ""
    score: int | None = None
    #: The founder's own words. Quoted, never adopted (plan decision #13).
    free_text: str = ""


@dataclass(frozen=True, slots=True)
class ReportSymptomEntry:
    """One `trial_symptom_entry`, with its frozen dose math already rendered."""

    eaten_at: str
    trigger_food_name: str
    amount: str
    doses_used: float | None
    outcome_score: int | None
    #: One line per enzyme: delivered vs threshold, or what blocked the sum.
    dose_lines: tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""


@dataclass(frozen=True, slots=True)
class TrialReport:
    """Everything §6.6 needs about one trial, assembled by the caller."""

    trial_id: str
    status: str
    batch_count: int
    observations: tuple[ReportObservation, ...] = field(default_factory=tuple)
    symptoms: tuple[ReportSymptomEntry, ...] = field(default_factory=tuple)
    #: Display text per dwell profile, e.g. "clearly softer (anecdote)".
    observed_envelope: Mapping[DwellProfile, str] = field(default_factory=dict)
    #: The batch pH, when one was measured, phrased for the report.
    measured_ph_note: str = ""

    @property
    def observation_count(self) -> int:
        return len(self.observations) + len(self.symptoms)

    def of_class(self, export_class: ExportClass) -> tuple[ReportObservation, ...]:
        return tuple(o for o in self.observations if o.export_class is export_class)
```

Add one field to `ReportInput`, after `stale`:

```python
    #: None until the founder has run a trial against this evaluation (§6.6).
    trial: TrialReport | None = None
```

- [ ] **Step 2: Give the envelope section its Observed column**

Replace the body of `_envelope_section` with:

```python
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
    observed = data.trial.observed_envelope if data.trial else {}
    for profile in DwellProfile:
        verdict = data.envelope.get(profile)
        predicted = _VERDICT_TEXT[verdict] if verdict is not None else "not evaluated"
        seen = observed.get(profile) or ("no trial yet" if data.trial is None else "not looked at")
        lines.append(f"| {_OCCASION_TEXT[profile]} | {predicted} | {seen} |")
    lines.append("")
    if data.trial and observed:
        lines += [TEXTURE_SCALE_NOTE, ""]
    return lines
```

and add the import it needs, beside the `ExportClass` one:

```python
from foodbrew.engine.observations import TEXTURE_SCALE_NOTE, ExportClass
```

- [ ] **Step 3: Replace `_observed_section` with the honesty split**

Replace the whole function:

```python
def _quote(text: str) -> list[str]:
    """Her words, reproduced and attributed — never rewritten (plan decision #13)."""
    return [f"> {line}" for line in text.strip().splitlines()] + [""]


def _observation_lines(records: Sequence[ReportObservation]) -> list[str]:
    lines: list[str] = []
    for record in records:
        subject = f" on {record.application_food_name}" if record.application_food_name else ""
        score = f", scored {record.score} of 5" if record.score is not None else ""
        lines.append(
            f"- **{record.observation_type.replace('_', ' ')}**{subject} — "
            f"{record.occasion} after making it{score} ({record.tier}, "
            f"observed {record.observed_at[:16].replace('T', ' ')})"
        )
        if record.free_text:
            lines += _quote(record.free_text)
    lines.append("")
    return lines


def _observed_section(data: ReportInput) -> list[str]:
    """Spec §10 screen 8 and §6.6 — the split by how much her judgement counts."""
    trial = data.trial
    if trial is None:
        return [
            "## What was observed",
            "",
            "No trial has been recorded for this formulation yet. Everything above is a "
            "prediction from the rules and the data behind them; nothing here was measured.",
            "",
        ]

    lines = [
        "## What was observed",
        "",
        f"Trial {trial.trial_id}, {trial.status}. {trial.batch_count} "
        f"batch(es), {trial.observation_count} record(s). This was one person, in a "
        "kitchen, mostly unblinded — so each section below says how much weight its "
        "contents carry.",
        "",
    ]
    if trial.status == "abandoned":
        lines += [
            f"This trial was abandoned after {trial.observation_count} record(s). What "
            "is below was really recorded; what is missing was never run.",
            "",
        ]
    if trial.measured_ph_note:
        lines += [trial.measured_ph_note, ""]

    findings = trial.of_class(ExportClass.FINDING)
    lines += ["### Findings", ""]
    if findings:
        lines += [
            "Taste, how it was to make, how it was to use — subjective questions where "
            "her answer is the data — plus any applied-food texture she compared "
            "against an undressed portion.",
            "",
        ]
        lines += _observation_lines(findings)
    else:
        lines += ["Nothing in this trial reached this bar yet.", ""]

    observations = trial.of_class(ExportClass.OBSERVATION)
    lines += ["### Observations", ""]
    if observations:
        lines += [
            "Watched, not controlled. Applied-food texture with no undressed portion to "
            "compare against, and storage watching.",
            "",
        ]
        lines += _observation_lines(observations)
    else:
        lines += ["Nothing recorded in this class.", ""]

    lines += ["### Hypotheses for a food scientist to test", ""]
    if trial.symptoms:
        lines += [
            "Symptom response, unblinded, single subject, on a product she has a stake "
            "in. This is the weakest measurement here and is listed so a real test can "
            "be designed around it. The dose arithmetic is attached to every entry, so "
            "a null result can be read as an under-dose rather than as a failure.",
            "",
        ]
        for entry in trial.symptoms:
            outcome = (
                f"outcome scored {entry.outcome_score} of 5"
                if entry.outcome_score is not None
                else "no outcome score"
            )
            doses = "not recorded" if entry.doses_used is None else f"{entry.doses_used}"
            lines.append(
                f"- **{entry.trigger_food_name}**, {entry.amount}, {doses} dose(s) — "
                f"{outcome} ({entry.eaten_at[:16].replace('T', ' ')})"
            )
            for line in entry.dose_lines:
                lines.append(f"  - {line}")
            if entry.notes:
                lines += _quote(entry.notes)
        lines.append("")
    else:
        lines += ["No meal was logged in this trial.", ""]

    return lines
```

and change its one call site in `render_markdown` from `_observed_section()` to `_observed_section(data)`.

- [ ] **Step 4: Write the tests**

```python
"""Spec §6.6's split, rendered. The absence path is M3's and must stay intact."""

import pytest

from foodbrew.engine.format_search import recommend_format
from foodbrew.engine.language import contains_prohibited
from foodbrew.engine.observations import ExportClass
from foodbrew.engine.report import (
    ReportInput,
    ReportObservation,
    ReportSymptomEntry,
    TrialReport,
    render_markdown,
)
from foodbrew.engine.rules import r15_applied_texture
from foodbrew.engine.types import DwellProfile, Phase, Verdict


@pytest.fixture
def base(make_ctx):
    ctx = make_ctx(
        enzymes=(("lactase_fungal_acid", 9000.0, Phase.WET),),
        recipe=(("olive_oil", 100.0), ("white_vinegar", 50.0)),
        trigger_foods=("milk",),
        application_foods=("romaine",),
        measured_ph=3.0,
    )

    def _input(trial=None):
        return ReportInput(
            evaluation_id="e1", created_at="2026-08-15T09:00:00+00:00",
            engine_version="test-engine", recipe_name="vinaigrette", headline="RED",
            context=ctx, findings=(), envelope=r15_applied_texture.envelope(ctx),
            recommendation=recommend_format(ctx), trial=trial,
        )

    return _input


def observation(**kw):
    defaults = dict(
        observation_type="food_texture", export_class=ExportClass.FINDING,
        tier="suggestive", occasion="1 to 8 hours",
        observed_at="2026-08-16T13:00:00+00:00", elapsed_minutes=240,
        application_food_name="Romaine", score=3, free_text="",
    )
    return ReportObservation(**{**defaults, **kw})


def test_without_a_trial_the_report_says_so_exactly_as_m3_did(base):
    body = render_markdown(base())
    assert "No trial has been recorded for this formulation yet." in body
    assert "| no trial yet |" in body


def test_a_trial_fills_the_three_sections_with_their_own_words(base):
    trial = TrialReport(
        trial_id="t1", status="running", batch_count=1,
        observations=(
            observation(observation_type="taste", export_class=ExportClass.FINDING,
                        application_food_name="", score=2, free_text="sweeter on day 3"),
            observation(export_class=ExportClass.OBSERVATION, tier="anecdote"),
        ),
        symptoms=(
            ReportSymptomEntry(
                eaten_at="2026-08-16T19:00:00+00:00", trigger_food_name="Milk",
                amount="1 servings", doses_used=1.0, outcome_score=2,
                dose_lines=("Lactase (fungal, acid): 9000 FCC delivered against a "
                            "3000 FCC threshold — clears it",),
                notes="no bloating this time",
            ),
        ),
        observed_envelope={DwellProfile.PACKED: "clearly softer (anecdote)"},
    )
    body = render_markdown(base(trial))

    assert "### Findings" in body
    assert "### Observations" in body
    assert "### Hypotheses for a food scientist to test" in body
    assert "> sweeter on day 3" in body
    assert "> no bloating this time" in body
    assert "9000 FCC delivered" in body
    assert "| clearly softer (anecdote) |" in body
    assert "| not looked at |" in body  # the buckets she has not filled


def test_an_empty_class_says_nothing_rather_than_being_dropped(base):
    trial = TrialReport(trial_id="t1", status="planned", batch_count=0)
    body = render_markdown(base(trial))
    assert "Nothing in this trial reached this bar yet." in body
    assert "No meal was logged in this trial." in body


def test_an_abandoned_trial_is_named_as_abandoned_with_its_count(base):
    trial = TrialReport(
        trial_id="t1", status="abandoned", batch_count=1, observations=(observation(),)
    )
    body = render_markdown(base(trial))
    assert "abandoned after 1 record(s)" in body


def test_the_symptom_section_never_reads_as_evidence(base):
    trial = TrialReport(
        trial_id="t1", status="complete", batch_count=1,
        symptoms=(ReportSymptomEntry(
            eaten_at="2026-08-16T19:00:00+00:00", trigger_food_name="Milk",
            amount="1 servings", doses_used=1.0, outcome_score=5,
        ),),
    )
    body = render_markdown(base(trial))
    assert "weakest measurement" in body
    assert contains_prohibited(body) == ()


def test_founder_free_text_is_reproduced_unaltered(base):
    """Decision #13 — the lint covers tool copy; her words are quoted and attributed."""
    trial = TrialReport(
        trial_id="t1", status="running", batch_count=1,
        observations=(observation(free_text="tastes fine to me, texture held up"),),
    )
    body = render_markdown(base(trial))
    assert "> tastes fine to me, texture held up" in body


def test_the_texture_scale_note_travels_with_the_observed_column(base):
    trial = TrialReport(
        trial_id="t1", status="running", batch_count=1,
        observed_envelope={DwellProfile.IMMEDIATE: "indistinguishable (anecdote)"},
    )
    body = render_markdown(base(trial))
    assert "stated convention, not by a measurement" in body
```

- [ ] **Step 5: Run them, and the M3 report tests with them**

Run: `.venv/bin/pytest tests/engine/test_report_trial.py tests/engine/test_report.py -q`
Expected: all pass. M3's `test_report.py` must be untouched and green — the absence path is unchanged when `trial is None`.

- [ ] **Step 6: Commit**

```bash
git add src/foodbrew/engine/report.py tests/engine/test_report_trial.py
git commit -m "feat(engine): render the observed sections and the 6.6 honesty split"
```

---

## Task 5: `store/trials.py` — trials, batches, and the storage gate

The first writer for `trial` and `trial_batch`. It owns the status machine (decision #12), the storage refusal (decision #5), and the clock the engine is not allowed to read (decision #14).

**Files:**
- Create: `src/foodbrew/store/trials.py`
- Create: `tests/store/test_trials.py`

- [ ] **Step 1: Write the module**

```python
"""Spec §5.3 and Workflow E — trial and batch persistence.

The protocol is generated once, from the evaluation this trial tests, and frozen
into `trial.protocol_json` (plan decision #3). Nothing here ever writes to
`evaluation` or `rule_finding`: an observation never mutates a prediction (§4).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from foodbrew import ENGINE_VERSION
from foodbrew.engine import ValidationRejection
from foodbrew.engine.observations import ObservationRecord
from foodbrew.engine.protocol import Protocol, due_checkpoints, generate
from foodbrew.engine.protocol import satisfied_checkpoint_ids as _satisfied
from foodbrew.engine.trial_rules import ACIDIFIED_FOOD_PH_LIMIT, ambient_storage_allowed
from foodbrew.store import evaluations as evaluations_store
from foodbrew.store.clock import now_iso
from foodbrew.store.ids import new_id
from foodbrew.store.snapshot import context_from_snapshot

PLANNED, RUNNING, COMPLETE, ABANDONED = "planned", "running", "complete", "abandoned"
STATUSES = (PLANNED, RUNNING, COMPLETE, ABANDONED)
#: Spec §3 Workflow E — a terminal trial keeps everything it recorded and takes
#: nothing more (plan decision #12).
TERMINAL = (COMPLETE, ABANDONED)

PH_METHODS = ("strip", "meter", "none")
STORAGE_MODES = ("refrigerated", "ambient")


@dataclass(frozen=True, slots=True)
class StoredBatch:
    id: str
    trial_id: str
    made_at: str
    batch_size_g: float | None
    measured_ph: float | None
    ph_method: str
    make_minutes: int | None
    difficulty_score: int | None
    enzyme_source_note: str
    enzyme_addition_step: int | None
    process_notes: str
    storage_mode: str
    observations: tuple[ObservationRecord, ...] = ()
    symptom_entry_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StoredTrial:
    id: str
    evaluation_id: str
    formulation_id: str
    status: str
    started_at: str | None
    notes: str
    protocol: Protocol
    batches: tuple[StoredBatch, ...] = ()

    @property
    def observations(self) -> tuple[ObservationRecord, ...]:
        return tuple(o for b in self.batches for o in b.observations)

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL


def create(conn: sqlite3.Connection, evaluation_id: str) -> str:
    """Generate the protocol from this evaluation's findings and freeze it."""
    stored = evaluations_store.get(conn, evaluation_id)
    if stored is None:
        raise ValidationRejection(f"Unknown evaluation '{evaluation_id}'.")

    context = context_from_snapshot(stored.input_snapshot_json)
    protocol = generate(
        context=context,
        findings=stored.findings,
        envelope=stored.envelope,
        engine_version=ENGINE_VERSION,
    )
    trial_id = new_id()
    conn.execute(
        "INSERT INTO trial (id, evaluation_id, protocol_json, status, started_at, notes)"
        " VALUES (?,?,?,?,?,?)",
        (trial_id, evaluation_id, protocol.to_json(), PLANNED, None, ""),
    )
    conn.commit()
    return trial_id


def _require_writable(trial: StoredTrial) -> None:
    if trial.is_terminal:
        raise ValidationRejection(
            f"This trial is {trial.status}. Start a new trial to record anything else — "
            "what is already here stays as it is."
        )


def add_batch(
    conn: sqlite3.Connection,
    trial_id: str,
    *,
    batch_size_g: float | None = None,
    measured_ph: float | None = None,
    ph_method: str = "none",
    make_minutes: int | None = None,
    difficulty_score: int | None = None,
    enzyme_source_note: str = "",
    enzyme_addition_step: int | None = None,
    process_notes: str = "",
    storage_mode: str = "refrigerated",
) -> str:
    """Spec §5.3's `trial_batch`, with the 21 CFR 114 gate of §3 Workflow E."""
    trial = get(conn, trial_id)
    if trial is None:
        raise ValidationRejection(f"Unknown trial '{trial_id}'.")
    _require_writable(trial)

    if ph_method not in PH_METHODS:
        raise ValidationRejection(f"pH method must be one of: {', '.join(PH_METHODS)}.")
    if measured_ph is not None and ph_method == "none":
        raise ValidationRejection("Say whether you used a strip or a meter for that pH.")
    if measured_ph is not None and not 0 <= measured_ph <= 14:
        raise ValidationRejection("A pH reading has to be between 0 and 14.")
    if difficulty_score is not None and not 1 <= difficulty_score <= 5:
        raise ValidationRejection("Score how hard it was from 1 to 5.")
    if storage_mode not in STORAGE_MODES:
        raise ValidationRejection(f"Storage has to be one of: {', '.join(STORAGE_MODES)}.")
    if storage_mode == "ambient" and not ambient_storage_allowed(measured_ph):
        raise ValidationRejection(
            "Room-temperature storage needs a measured pH below "
            f"{ACIDIFIED_FOOD_PH_LIMIT} for this batch. Keep it refrigerated, or "
            "measure the pH first."
        )

    batch_id = new_id()
    made_at = now_iso()
    conn.execute(
        "INSERT INTO trial_batch (id, trial_id, made_at, batch_size_g, measured_ph,"
        " ph_method, make_minutes, difficulty_score, enzyme_source_note,"
        " enzyme_addition_step, process_notes, storage_mode)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            batch_id, trial_id, made_at, batch_size_g, measured_ph, ph_method,
            make_minutes, difficulty_score, enzyme_source_note, enzyme_addition_step,
            process_notes, storage_mode,
        ),
    )
    if trial.status == PLANNED:
        conn.execute(
            "UPDATE trial SET status = ?, started_at = ? WHERE id = ?",
            (RUNNING, made_at, trial_id),
        )
    conn.commit()
    return batch_id


def set_status(conn: sqlite3.Connection, trial_id: str, status: str) -> StoredTrial:
    """Spec §5.3 — only the two terminals are settable by hand (decision #12)."""
    trial = get(conn, trial_id)
    if trial is None:
        raise ValidationRejection(f"Unknown trial '{trial_id}'.")
    if status not in TERMINAL:
        raise ValidationRejection(
            "A trial can be marked complete or abandoned; the rest happens on its own."
        )
    if trial.is_terminal:
        raise ValidationRejection(f"This trial is already {trial.status}.")
    conn.execute("UPDATE trial SET status = ? WHERE id = ?", (status, trial_id))
    conn.commit()
    return get(conn, trial_id)


def elapsed_minutes(made_at: str, now: str) -> int:
    """Whole minutes between two ISO-8601 stamps; the engine gets the number only."""
    from datetime import datetime

    delta = datetime.fromisoformat(now) - datetime.fromisoformat(made_at)
    return max(0, int(delta.total_seconds() // 60))


def due_now(trial: StoredTrial, batch: StoredBatch, *, now: str | None = None):
    """Which scheduled checkpoints this batch has reached and not answered."""
    return due_checkpoints(
        trial.protocol,
        elapsed_minutes=elapsed_minutes(batch.made_at, now or now_iso()),
        satisfied_ids=_satisfied(trial.protocol, batch.observations),
    )


def get(conn: sqlite3.Connection, trial_id: str) -> StoredTrial | None:
    row = conn.execute("SELECT * FROM trial WHERE id = ?", (trial_id,)).fetchone()
    if row is None:
        return None
    from foodbrew.store import observations as observations_store

    formulation_row = conn.execute(
        "SELECT formulation_id FROM evaluation WHERE id = ?", (row["evaluation_id"],)
    ).fetchone()
    batches = tuple(
        StoredBatch(
            id=b["id"], trial_id=b["trial_id"], made_at=b["made_at"],
            batch_size_g=b["batch_size_g"], measured_ph=b["measured_ph"],
            ph_method=b["ph_method"], make_minutes=b["make_minutes"],
            difficulty_score=b["difficulty_score"],
            enzyme_source_note=b["enzyme_source_note"],
            enzyme_addition_step=b["enzyme_addition_step"],
            process_notes=b["process_notes"], storage_mode=b["storage_mode"],
            observations=observations_store.list_for_batch(conn, b["id"]),
            symptom_entry_ids=observations_store.symptom_ids_for_batch(conn, b["id"]),
        )
        for b in conn.execute(
            "SELECT * FROM trial_batch WHERE trial_id = ? ORDER BY made_at, id", (trial_id,)
        )
    )
    return StoredTrial(
        id=row["id"], evaluation_id=row["evaluation_id"],
        formulation_id=formulation_row["formulation_id"] if formulation_row else "",
        status=row["status"], started_at=row["started_at"], notes=row["notes"],
        protocol=Protocol.from_json(row["protocol_json"]), batches=batches,
    )


def list_for_evaluation(conn, evaluation_id: str) -> tuple[StoredTrial, ...]:
    ids = [
        r["id"]
        for r in conn.execute(
            "SELECT id FROM trial WHERE evaluation_id = ? ORDER BY rowid DESC",
            (evaluation_id,),
        )
    ]
    return tuple(get(conn, i) for i in ids)


def list_active(conn) -> tuple[StoredTrial, ...]:
    """Spec §10 screen 1 — the Home screen's active trials."""
    ids = [
        r["id"]
        for r in conn.execute(
            "SELECT id FROM trial WHERE status IN (?, ?) ORDER BY rowid DESC",
            (PLANNED, RUNNING),
        )
    ]
    return tuple(get(conn, i) for i in ids)
```

- [ ] **Step 2: Write the tests**

```python
"""Spec §5.3, §3 Workflow E — the status machine and the storage gate, over real SQLite."""

import pytest

from foodbrew.engine import ValidationRejection
from foodbrew.engine.protocol import CheckpointKind
from foodbrew.store import evaluations as evaluations_store
from foodbrew.store import trials


@pytest.fixture
def evaluation(conn, vinaigrette_rows):
    return evaluations_store.run(conn, vinaigrette_rows["formulation_id"])


def test_a_new_trial_is_planned_and_carries_a_frozen_protocol(conn, evaluation):
    trial_id = trials.create(conn, evaluation.id)
    trial = trials.get(conn, trial_id)
    assert trial.status == trials.PLANNED
    assert trial.started_at is None
    assert trial.protocol.checkpoints
    assert CheckpointKind.MAKE_IT in {c.kind for c in trial.protocol.checkpoints}


def test_the_protocol_does_not_change_when_the_evaluation_is_re_run(
    conn, evaluation, vinaigrette_rows
):
    trial_id = trials.create(conn, evaluation.id)
    before = trials.get(conn, trial_id).protocol.to_json()
    conn.execute("UPDATE enzyme SET notes = 'edited' WHERE id = 'lactase_fungal_acid'")
    conn.commit()
    evaluations_store.run(conn, vinaigrette_rows["formulation_id"])
    assert trials.get(conn, trial_id).protocol.to_json() == before


def test_the_first_batch_starts_the_trial(conn, evaluation):
    trial_id = trials.create(conn, evaluation.id)
    trials.add_batch(conn, trial_id, batch_size_g=200.0, make_minutes=12, difficulty_score=2)
    trial = trials.get(conn, trial_id)
    assert trial.status == trials.RUNNING
    assert trial.started_at is not None
    assert len(trial.batches) == 1


def test_ambient_storage_without_a_measured_ph_is_refused(conn, evaluation):
    trial_id = trials.create(conn, evaluation.id)
    with pytest.raises(ValidationRejection) as exc:
        trials.add_batch(conn, trial_id, storage_mode="ambient")
    assert "4.6" in str(exc.value)


def test_ambient_storage_above_the_line_is_refused(conn, evaluation):
    trial_id = trials.create(conn, evaluation.id)
    with pytest.raises(ValidationRejection):
        trials.add_batch(conn, trial_id, measured_ph=5.2, ph_method="meter", storage_mode="ambient")


def test_ambient_storage_below_the_line_is_permitted(conn, evaluation):
    trial_id = trials.create(conn, evaluation.id)
    batch_id = trials.add_batch(
        conn, trial_id, measured_ph=4.1, ph_method="meter", storage_mode="ambient"
    )
    assert trials.get(conn, trial_id).batches[0].id == batch_id


def test_a_ph_reading_has_to_say_how_it_was_taken(conn, evaluation):
    trial_id = trials.create(conn, evaluation.id)
    with pytest.raises(ValidationRejection):
        trials.add_batch(conn, trial_id, measured_ph=4.1, ph_method="none")


def test_a_difficulty_score_off_the_scale_is_refused(conn, evaluation):
    trial_id = trials.create(conn, evaluation.id)
    with pytest.raises(ValidationRejection):
        trials.add_batch(conn, trial_id, difficulty_score=9)


@pytest.mark.parametrize("terminal", [trials.COMPLETE, trials.ABANDONED])
def test_a_terminal_trial_takes_no_more_batches_but_keeps_what_it_has(
    conn, evaluation, terminal
):
    trial_id = trials.create(conn, evaluation.id)
    trials.add_batch(conn, trial_id, batch_size_g=200.0)
    trials.set_status(conn, trial_id, terminal)

    with pytest.raises(ValidationRejection) as exc:
        trials.add_batch(conn, trial_id, batch_size_g=200.0)
    assert "new trial" in str(exc.value)
    assert len(trials.get(conn, trial_id).batches) == 1


def test_only_the_two_terminals_can_be_set_by_hand(conn, evaluation):
    trial_id = trials.create(conn, evaluation.id)
    with pytest.raises(ValidationRejection):
        trials.set_status(conn, trial_id, trials.RUNNING)


def test_a_terminal_trial_leaves_the_active_list(conn, evaluation):
    trial_id = trials.create(conn, evaluation.id)
    assert [t.id for t in trials.list_active(conn)] == [trial_id]
    trials.set_status(conn, trial_id, trials.ABANDONED)
    assert trials.list_active(conn) == ()


def test_elapsed_minutes_is_whole_minutes_and_never_negative():
    assert trials.elapsed_minutes(
        "2026-08-15T09:00:00+00:00", "2026-08-15T13:30:40+00:00"
    ) == 270
    assert trials.elapsed_minutes(
        "2026-08-15T09:00:00+00:00", "2026-08-15T08:00:00+00:00"
    ) == 0


def test_due_now_reports_reached_and_unanswered_checkpoints(conn, evaluation):
    trial_id = trials.create(conn, evaluation.id)
    batch_id = trials.add_batch(conn, trial_id, batch_size_g=200.0)
    trial = trials.get(conn, trial_id)
    batch = trial.batches[0]
    due = trials.due_now(trial, batch, now=batch.made_at)
    assert all(c.due_elapsed_minutes == 0 for c in due)
    assert all(c.is_scheduled for c in due)
```

- [ ] **Step 3: Add the shared fixture the store tests need**

Append to `tests/conftest.py`:

```python
@pytest.fixture
def vinaigrette_rows(conn):
    """The golden fixture (a) vinaigrette, persisted. Mirrors tests/api/conftest.py's
    `vinaigrette`, which is scoped to the API suite and cannot be reused here."""
    from foodbrew.store import formulations, recipes

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

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/pytest tests/store/test_trials.py -q`
Expected: 14 passed. They will fail on the `observations_store` import until Task 6 exists — run this task's tests again at the end of Task 6 if you are executing strictly in order, or write Task 6's module first and come back. The import is at call time inside `get`, so only the tests that read a trial are affected.

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/store/trials.py tests/store/test_trials.py tests/conftest.py
git commit -m "feat(store): trials, batches, the status machine, and the storage gate"
```

---

## Task 6: `store/observations.py` — observations and symptom entries

The other two writers. The dwell bucket is derived here and nowhere else (decision #2); the dose math is frozen against the evaluation's own snapshot (decision #7); the preview runs the identical code path and writes nothing (decision #8).

`store/trials.py` imports this module *inside* `get` while this module imports `store/trials` at the top — that asymmetry is deliberate and is what keeps the pair importable in either order.

**Files:**
- Create: `src/foodbrew/store/observations.py`
- Create: `tests/store/test_observations.py`

- [ ] **Step 1: Write the module**

```python
"""Spec §5.3 — `trial_observation` and `trial_symptom_entry`.

Two invariants live here and are asserted in tests/api/test_contracts_m4.py:

* `dwell_bucket` is derived from `elapsed_minutes` by `texture.dwell_bucket` and
  by nothing else — no caller may supply one (plan decision #2).
* `computed_dose_json` is frozen against the evaluation's own input snapshot, so
  a later edit to a threshold cannot change what an eaten meal is judged against
  (plan decision #7).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from foodbrew.engine import ValidationRejection
from foodbrew.engine.observations import ObservationRecord, ObservationType
from foodbrew.engine.symptoms import SERVINGS, SymptomDoseMath, computed_dose
from foodbrew.engine.texture import dwell_bucket
from foodbrew.store import trials as trials_store
from foodbrew.store.clock import now_iso
from foodbrew.store.ids import new_id
from foodbrew.store.snapshot import context_from_snapshot


@dataclass(frozen=True, slots=True)
class StoredSymptomEntry:
    id: str
    trial_batch_id: str
    eaten_at: str
    trigger_food_id: str
    amount_value: float | None
    amount_unit: str
    doses_used: float | None
    computed_dose: dict
    outcome_score: int | None
    notes: str


def _batch_context(conn: sqlite3.Connection, batch_id: str):
    """The trial, and the EvalContext frozen into the evaluation it tests."""
    row = conn.execute(
        "SELECT b.trial_id AS trial_id, e.input_snapshot_json AS snapshot"
        " FROM trial_batch b"
        " JOIN trial t ON t.id = b.trial_id"
        " JOIN evaluation e ON e.id = t.evaluation_id"
        " WHERE b.id = ?",
        (batch_id,),
    ).fetchone()
    if row is None:
        raise ValidationRejection(f"Unknown batch '{batch_id}'.")
    trial = trials_store.get(conn, row["trial_id"])
    return trial, context_from_snapshot(row["snapshot"])


def add_observation(
    conn: sqlite3.Connection,
    batch_id: str,
    *,
    type: str,
    elapsed_minutes: int,
    score: int | None = None,
    free_text: str = "",
    was_blinded: bool = False,
    had_undressed_control: bool = False,
    application_food_id: str = "",
) -> str:
    trial, context = _batch_context(conn, batch_id)
    if trial.is_terminal:
        raise ValidationRejection(
            f"This trial is {trial.status}. Start a new trial to record anything else — "
            "what is already here stays as it is."
        )
    try:
        observation_type = ObservationType(type)
    except ValueError as exc:
        allowed = ", ".join(str(t) for t in ObservationType)
        raise ValidationRejection(f"An observation has to be one of: {allowed}.") from exc

    if elapsed_minutes < 0:
        raise ValidationRejection("Time since you made it cannot be negative.")
    if score is not None and not 1 <= score <= 5:
        raise ValidationRejection("Scores run from 1 to 5.")
    if application_food_id:
        food = context.foods.get(application_food_id)
        if food is None:
            raise ValidationRejection(f"Unknown food '{application_food_id}'.")
        if application_food_id not in context.formulation.application_food_ids:
            raise ValidationRejection(
                f"{food.name} is not one of the foods this formulation said it would "
                "be poured on."
            )
    if observation_type is ObservationType.FOOD_TEXTURE and not application_food_id:
        raise ValidationRejection("Say which food you looked at.")

    observation_id = new_id()
    conn.execute(
        "INSERT INTO trial_observation (id, trial_batch_id, observed_at, elapsed_minutes,"
        " type, dwell_bucket, score, free_text, was_blinded, application_food_id,"
        " had_undressed_control) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            observation_id, batch_id, now_iso(), int(elapsed_minutes),
            str(observation_type), str(dwell_bucket(int(elapsed_minutes))), score,
            free_text, int(was_blinded), application_food_id or None,
            int(had_undressed_control),
        ),
    )
    conn.commit()
    return observation_id


def list_for_batch(conn: sqlite3.Connection, batch_id: str) -> tuple[ObservationRecord, ...]:
    return tuple(
        ObservationRecord(
            id=r["id"], type=ObservationType(r["type"]), observed_at=r["observed_at"],
            elapsed_minutes=r["elapsed_minutes"], score=r["score"],
            free_text=r["free_text"], was_blinded=bool(r["was_blinded"]),
            had_undressed_control=bool(r["had_undressed_control"]),
            application_food_id=r["application_food_id"] or "",
        )
        for r in conn.execute(
            "SELECT * FROM trial_observation WHERE trial_batch_id = ?"
            " ORDER BY elapsed_minutes, id",
            (batch_id,),
        )
    )


def preview_symptom(
    conn: sqlite3.Connection,
    batch_id: str,
    *,
    trigger_food_id: str,
    amount_value: float | None,
    amount_unit: str = SERVINGS,
    doses_used: float | None,
) -> SymptomDoseMath:
    """The live dose math (plan decision #8). Reads; writes nothing."""
    _trial, context = _batch_context(conn, batch_id)
    return computed_dose(
        context=context, trigger_food_id=trigger_food_id, amount_value=amount_value,
        amount_unit=amount_unit, doses_used=doses_used,
    )


def add_symptom_entry(
    conn: sqlite3.Connection,
    batch_id: str,
    *,
    trigger_food_id: str,
    amount_value: float | None = None,
    amount_unit: str = SERVINGS,
    doses_used: float | None = None,
    outcome_score: int | None = None,
    notes: str = "",
    eaten_at: str | None = None,
) -> str:
    """Spec §5.3 — the sole route for symptom capture (plan decision #6)."""
    trial, context = _batch_context(conn, batch_id)
    if trial.is_terminal:
        raise ValidationRejection(
            f"This trial is {trial.status}. Start a new trial to record anything else — "
            "what is already here stays as it is."
        )
    if trigger_food_id not in context.foods:
        raise ValidationRejection(f"Unknown food '{trigger_food_id}'.")
    if outcome_score is not None and not 1 <= outcome_score <= 5:
        raise ValidationRejection("Scores run from 1 to 5.")
    if amount_value is not None and amount_value < 0:
        raise ValidationRejection("An amount cannot be negative.")
    if doses_used is not None and doses_used < 0:
        raise ValidationRejection("A number of doses cannot be negative.")

    math = computed_dose(
        context=context, trigger_food_id=trigger_food_id, amount_value=amount_value,
        amount_unit=amount_unit, doses_used=doses_used,
    )
    entry_id = new_id()
    conn.execute(
        "INSERT INTO trial_symptom_entry (id, trial_batch_id, eaten_at, trigger_food_id,"
        " amount_value, amount_unit, doses_used, computed_dose_json, outcome_score, notes)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            entry_id, batch_id, eaten_at or now_iso(), trigger_food_id, amount_value,
            amount_unit, doses_used, json.dumps(math.as_dict(), sort_keys=True),
            outcome_score, notes,
        ),
    )
    conn.commit()
    return entry_id


def symptoms_for_batch(conn, batch_id: str) -> tuple[StoredSymptomEntry, ...]:
    return tuple(
        StoredSymptomEntry(
            id=r["id"], trial_batch_id=r["trial_batch_id"], eaten_at=r["eaten_at"],
            trigger_food_id=r["trigger_food_id"], amount_value=r["amount_value"],
            amount_unit=r["amount_unit"], doses_used=r["doses_used"],
            computed_dose=json.loads(r["computed_dose_json"]),
            outcome_score=r["outcome_score"], notes=r["notes"],
        )
        for r in conn.execute(
            "SELECT * FROM trial_symptom_entry WHERE trial_batch_id = ? ORDER BY eaten_at, id",
            (batch_id,),
        )
    )


def symptom_ids_for_batch(conn, batch_id: str) -> tuple[str, ...]:
    return tuple(e.id for e in symptoms_for_batch(conn, batch_id))


def symptoms_for_trial(conn, trial_id: str) -> tuple[StoredSymptomEntry, ...]:
    batch_ids = [
        r["id"]
        for r in conn.execute(
            "SELECT id FROM trial_batch WHERE trial_id = ? ORDER BY made_at, id", (trial_id,)
        )
    ]
    return tuple(e for b in batch_ids for e in symptoms_for_batch(conn, b))
```

- [ ] **Step 2: Write the tests**

```python
"""Spec §5.3's two capture tables, over real SQLite."""

import json

import pytest

from foodbrew.engine import ValidationRejection
from foodbrew.engine.trial_rules import ConfidenceTier
from foodbrew.engine.types import DwellProfile
from foodbrew.store import evaluations as evaluations_store
from foodbrew.store import observations, trials


@pytest.fixture
def batch(conn, vinaigrette_rows):
    evaluation = evaluations_store.run(conn, vinaigrette_rows["formulation_id"])
    trial_id = trials.create(conn, evaluation.id)
    return trial_id, trials.add_batch(conn, trial_id, batch_size_g=200.0)


def test_the_server_derives_the_dwell_bucket_from_elapsed_minutes(conn, batch):
    _trial_id, batch_id = batch
    observations.add_observation(
        conn, batch_id, type="food_texture", elapsed_minutes=240,
        score=3, application_food_id="romaine",
    )
    row = conn.execute("SELECT dwell_bucket FROM trial_observation").fetchone()
    assert row["dwell_bucket"] == str(DwellProfile.PACKED)


def test_an_observation_reads_back_with_its_tier(conn, batch):
    _trial_id, batch_id = batch
    observations.add_observation(
        conn, batch_id, type="food_texture", elapsed_minutes=0, score=2,
        application_food_id="romaine", had_undressed_control=True,
    )
    record = observations.list_for_batch(conn, batch_id)[0]
    assert record.tier is ConfidenceTier.SUGGESTIVE
    assert record.dwell_bucket is DwellProfile.IMMEDIATE


def test_symptom_is_not_an_observation_type(conn, batch):
    _trial_id, batch_id = batch
    with pytest.raises(ValidationRejection) as exc:
        observations.add_observation(conn, batch_id, type="symptom", elapsed_minutes=0)
    assert "taste" in str(exc.value)


def test_a_texture_observation_has_to_name_the_food(conn, batch):
    _trial_id, batch_id = batch
    with pytest.raises(ValidationRejection):
        observations.add_observation(
            conn, batch_id, type="food_texture", elapsed_minutes=0, score=2
        )


def test_a_food_the_formulation_never_claimed_is_refused(conn, batch):
    _trial_id, batch_id = batch
    with pytest.raises(ValidationRejection) as exc:
        observations.add_observation(
            conn, batch_id, type="food_texture", elapsed_minutes=0, score=2,
            application_food_id="cucumber",
        )
    assert "poured on" in str(exc.value)


def test_a_symptom_entry_freezes_the_dose_math(conn, batch):
    _trial_id, batch_id = batch
    entry_id = observations.add_symptom_entry(
        conn, batch_id, trigger_food_id="milk", amount_value=1.0,
        amount_unit="servings", doses_used=2.0, outcome_score=2, notes="fine",
    )
    stored = observations.symptoms_for_batch(conn, batch_id)[0]
    assert stored.id == entry_id
    assert stored.computed_dose["enzymes"][0]["units_delivered"] == 18000.0


def test_editing_the_threshold_afterwards_does_not_change_a_recorded_meal(conn, batch):
    _trial_id, batch_id = batch
    observations.add_symptom_entry(
        conn, batch_id, trigger_food_id="milk", amount_value=1.0, doses_used=1.0
    )
    before = observations.symptoms_for_batch(conn, batch_id)[0].computed_dose
    conn.execute(
        "UPDATE enzyme SET dose_evidence_threshold = 999999,"
        " dose_evidence_threshold_status = 'user_provided' WHERE id = 'lactase_fungal_acid'"
    )
    conn.commit()
    after = observations.symptoms_for_batch(conn, batch_id)[0].computed_dose
    assert json.dumps(after, sort_keys=True) == json.dumps(before, sort_keys=True)


def test_the_preview_matches_what_a_write_would_store_and_writes_nothing(conn, batch):
    _trial_id, batch_id = batch
    preview = observations.preview_symptom(
        conn, batch_id, trigger_food_id="milk", amount_value=1.0, doses_used=1.0
    )
    assert conn.execute("SELECT COUNT(*) c FROM trial_symptom_entry").fetchone()["c"] == 0

    observations.add_symptom_entry(
        conn, batch_id, trigger_food_id="milk", amount_value=1.0, doses_used=1.0
    )
    stored = observations.symptoms_for_batch(conn, batch_id)[0].computed_dose
    assert stored == preview.as_dict()


def test_a_terminal_trial_takes_no_observations_and_no_meals(conn, batch):
    trial_id, batch_id = batch
    trials.set_status(conn, trial_id, trials.COMPLETE)
    with pytest.raises(ValidationRejection):
        observations.add_observation(conn, batch_id, type="taste", elapsed_minutes=0, score=3)
    with pytest.raises(ValidationRejection):
        observations.add_symptom_entry(conn, batch_id, trigger_food_id="milk")


def test_recording_an_observation_never_touches_the_evaluation(conn, vinaigrette_rows):
    evaluation = evaluations_store.run(conn, vinaigrette_rows["formulation_id"])
    trial_id = trials.create(conn, evaluation.id)
    batch_id = trials.add_batch(conn, trial_id, batch_size_g=200.0)
    observations.add_observation(
        conn, batch_id, type="food_texture", elapsed_minutes=1440, score=5,
        application_food_id="romaine",
    )
    after = evaluations_store.get(conn, evaluation.id)
    assert after.overall is evaluation.overall
    assert after.envelope == evaluation.envelope
    assert [f.message for f in after.findings] == [f.message for f in evaluation.findings]
```

- [ ] **Step 3: Run both store suites**

Run: `.venv/bin/pytest tests/store/test_trials.py tests/store/test_observations.py -q`
Expected: 24 passed.

- [ ] **Step 4: Commit**

```bash
git add src/foodbrew/store/observations.py tests/store/test_observations.py
git commit -m "feat(store): trial observations and symptom entries with frozen dose math"
```

---

## Task 7: The pH loop — a batch measurement reaches the next evaluation

§6.7's second resolution branch has been dead code since M2 (`formulations.latest_trial_ph`, written against an empty table). This task proves the whole chain now that rows exist: batch pH → stale banner → re-run → R1 reads it as `observed`. No production code changes; if any of it fails, an earlier task is wrong.

**Files:**
- Create: `tests/store/test_trial_ph.py`

- [ ] **Step 1: Write the tests**

```python
"""Spec §6.7's resolution order, end to end, and §13's pH resolution test."""

import pytest

from foodbrew.engine.conventions import resolve_recipe_ph
from foodbrew.engine.types import TruthLabel
from foodbrew.store import evaluations as evaluations_store
from foodbrew.store import formulations, observations, recipes, trials


@pytest.fixture
def unmeasured(conn):
    """The same vinaigrette with no measured pH — so the fallback is in play."""
    recipe_id = recipes.create(conn, name="vinaigrette", notes="", ingredients=[
        {"food_id": "olive_oil", "amount_g": 100.0, "order": 1},
        {"food_id": "white_vinegar", "amount_g": 50.0, "order": 2},
    ])
    return formulations.create(
        conn, recipe_id=recipe_id, format="premixed_wet",
        target_trigger_food_ids=["milk"], application_food_ids=["romaine"],
        dwell_profile=None,
        enzymes=[{"enzyme_id": "lactase_fungal_acid", "dose": 9000.0, "phase": "wet",
                  "encapsulated": False, "source_choice": ""}],
        serving_size_g=30.0, measured_ph=None,
        process_steps=[{"order": 1, "label": "whisk", "is_heat": False}],
        enzyme_addition_index=1, parent_formulation_id=None,
    )


def _log_batch_ph(conn, formulation_id, ph):
    evaluation = evaluations_store.run(conn, formulation_id)
    trial_id = trials.create(conn, evaluation.id)
    trials.add_batch(conn, trial_id, measured_ph=ph, ph_method="meter")
    return evaluation


def test_a_batch_ph_becomes_the_next_evaluations_input_labelled_observed(conn, unmeasured):
    _log_batch_ph(conn, unmeasured, 3.4)
    context = formulations.hydrate_context(conn, unmeasured)
    resolution = resolve_recipe_ph(context.formulation, context.foods, context.latest_trial_ph)
    assert resolution.value == 3.4
    assert resolution.status is TruthLabel.OBSERVED
    assert resolution.origin == "trial_batch.measured_ph"


def test_a_formulation_measurement_still_wins_over_a_batch_one(conn, vinaigrette_rows):
    _log_batch_ph(conn, vinaigrette_rows["formulation_id"], 3.4)
    context = formulations.hydrate_context(conn, vinaigrette_rows["formulation_id"])
    resolution = resolve_recipe_ph(context.formulation, context.foods, context.latest_trial_ph)
    assert resolution.value == 3.0
    assert resolution.origin == "formulation.measured_ph"


def test_logging_a_batch_ph_makes_the_earlier_evaluation_stale(conn, unmeasured):
    evaluation = _log_batch_ph(conn, unmeasured, 3.4)
    stale, changes = evaluations_store.freshness(conn, evaluations_store.get(conn, evaluation.id))
    assert stale is True
    assert changes  # the banner names what moved rather than saying "something"


def test_the_re_run_carries_the_measurement_into_r1s_evidence(conn, unmeasured):
    _log_batch_ph(conn, unmeasured, 3.4)
    rerun = evaluations_store.run(conn, unmeasured)
    r1 = next(f for f in rerun.findings if f.rule_id == "R1")
    assert "3.4" in str(r1.evidence) or r1.evidence.get("recipe_ph") == 3.4


def test_the_most_recent_batch_measurement_is_the_one_used(conn, unmeasured):
    evaluation = evaluations_store.run(conn, unmeasured)
    trial_id = trials.create(conn, evaluation.id)
    trials.add_batch(conn, trial_id, measured_ph=3.9, ph_method="strip")
    trials.add_batch(conn, trial_id, measured_ph=3.2, ph_method="meter")
    context = formulations.hydrate_context(conn, unmeasured)
    assert context.latest_trial_ph.value == 3.2
```

- [ ] **Step 2: Run them**

Run: `.venv/bin/pytest tests/store/test_trial_ph.py -q`
Expected: 5 passed. If `test_the_re_run_carries_the_measurement_into_r1s_evidence` fails, read `rules/r01_ph_survival.py`'s evidence keys and assert the one it actually writes — do not change the rule.

- [ ] **Step 3: Commit**

```bash
git add tests/store/test_trial_ph.py
git commit -m "test(store): prove the batch-pH loop reaches the next evaluation"
```

---

## Task 8: API schemas for M4

Wire models only. Note what is absent as much as what is present: no `dwell_bucket`, no `confidence_tier`, no observation `type` of `symptom`, and no client-settable trial status other than the two terminals (decisions #2, #6, #12).

**Files:**
- Modify: `src/foodbrew/api/schemas.py`

- [ ] **Step 1: Append the models**

Add at the end of `schemas.py`, and add `Literal` to the `typing` import at the top:

```python
class CheckpointOut(BaseModel):
    id: str
    kind: str
    prompt: str
    raised_by: list[str]
    due_elapsed_minutes: int | None
    application_food_id: str
    #: Empty when no observation fills this one (make-it, pH, symptom).
    observation_type: str


class ProtocolOut(BaseModel):
    engine_version: str
    checkpoints: list[CheckpointOut]
    notes: list[str]


class TrackedDoseOut(BaseModel):
    enzyme_id: str
    enzyme_name: str
    dose_unit: str
    dose_per_serving: float | None
    units_delivered: float | None
    threshold: TrackedOut
    meets_threshold: bool | None
    ratio: float | None
    blocking_field: str


class SymptomDoseOut(BaseModel):
    """Spec §5.3's computed_dose_json, and §10 screen 6's live preview."""

    trigger_food_id: str
    trigger_food_name: str
    amount_value: float | None
    amount_unit: str
    doses_used: float | None
    substrate_ids: list[str]
    enzymes: list[TrackedDoseOut]
    substrate_load: TrackedOut
    note: str


class ObservationIn(BaseModel):
    """No `dwell_bucket` and no tier: the server derives both (plan decision #2).
    No `symptom` in the Literal: symptoms have their own endpoint (decision #6)."""

    type: Literal["taste", "usability", "food_texture", "storage"]
    elapsed_minutes: int = Field(ge=0)
    score: int | None = Field(default=None, ge=1, le=5)
    free_text: str = ""
    was_blinded: bool = False
    had_undressed_control: bool = False
    application_food_id: str = ""


class ObservationOut(BaseModel):
    id: str
    type: str
    observed_at: str
    elapsed_minutes: int
    dwell_bucket: str
    score: int | None
    free_text: str
    was_blinded: bool
    had_undressed_control: bool
    application_food_id: str
    #: Spec §6.6 — derived, never stored, never sent by a client.
    confidence_tier: str
    export_class: str


class SymptomEntryIn(BaseModel):
    trigger_food_id: str
    amount_value: float | None = Field(default=None, ge=0)
    amount_unit: str = "servings"
    doses_used: float | None = Field(default=None, ge=0)
    outcome_score: int | None = Field(default=None, ge=1, le=5)
    notes: str = ""


class SymptomPreviewIn(BaseModel):
    trigger_food_id: str
    amount_value: float | None = Field(default=None, ge=0)
    amount_unit: str = "servings"
    doses_used: float | None = Field(default=None, ge=0)


class SymptomEntryOut(BaseModel):
    id: str
    eaten_at: str
    trigger_food_id: str
    amount_value: float | None
    amount_unit: str
    doses_used: float | None
    outcome_score: int | None
    notes: str
    computed_dose: SymptomDoseOut


class BatchIn(BaseModel):
    batch_size_g: float | None = Field(default=None, ge=0)
    measured_ph: float | None = Field(default=None, ge=0, le=14)
    ph_method: Literal["strip", "meter", "none"] = "none"
    make_minutes: int | None = Field(default=None, ge=0)
    difficulty_score: int | None = Field(default=None, ge=1, le=5)
    enzyme_source_note: str = ""
    enzyme_addition_step: int | None = None
    process_notes: str = ""
    storage_mode: Literal["refrigerated", "ambient"] = "refrigerated"


class BatchOut(BaseModel):
    id: str
    made_at: str
    batch_size_g: float | None
    measured_ph: float | None
    ph_method: str
    make_minutes: int | None
    difficulty_score: int | None
    enzyme_source_note: str
    enzyme_addition_step: int | None
    process_notes: str
    storage_mode: str
    observations: list[ObservationOut]
    symptom_entries: list[SymptomEntryOut]
    #: Scheduled checkpoints this batch has reached and not answered.
    due_checkpoint_ids: list[str]
    satisfied_checkpoint_ids: list[str]
    #: True when this batch's pH permits an ambient watch (§3 Workflow E).
    ambient_storage_allowed: bool


class TrialOut(BaseModel):
    id: str
    evaluation_id: str
    formulation_id: str
    status: str
    started_at: str | None
    notes: str
    protocol: ProtocolOut
    batches: list[BatchOut]


class TrialSummaryOut(BaseModel):
    id: str
    evaluation_id: str
    formulation_id: str
    status: str
    started_at: str | None
    batch_count: int
    observation_count: int
    due_checkpoint_count: int


class TrialStatusIn(BaseModel):
    """Only the two terminals — the rest of the machine runs itself (decision #12)."""

    status: Literal["complete", "abandoned"]


class ObservedProfileOut(BaseModel):
    verdict: str | None
    confidence_tier: str | None
    observation_count: int
    driving_observation_id: str


class ObservedEnvelopeOut(BaseModel):
    """Spec §6.3's second column. Computed on read; it changes no prediction."""

    trial_id: str | None
    profiles: dict[str, ObservedProfileOut]
    scale_note: str
```

Finally, add one field to `EvaluationOut`, after `changes`:

```python
    #: Spec §6.3 — the Observed column, when a trial exists (plan decision #10).
    observed: ObservedEnvelopeOut | None = None
    trial_ids: list[str] = Field(default_factory=list)
```

- [ ] **Step 2: Check the app still boots and the schema is well-formed**

Run: `.venv/bin/pytest tests/api/test_schemas.py tests/api/test_app.py -q`
Expected: unchanged results — every new model is additive and every new `EvaluationOut` field has a default.

- [ ] **Step 3: Commit**

```bash
git add src/foodbrew/api/schemas.py
git commit -m "feat(api): wire models for trials, observations, and the dose preview"
```

---

## Task 9: `routers/trials.py` — §10's trial endpoints

Five endpoints from §10 plus the preview of decision #8. No logic: assembly and content types only, exactly like M3's routers.

**Files:**
- Create: `src/foodbrew/api/routers/trials.py`
- Modify: `src/foodbrew/api/app.py`
- Create: `tests/api/test_trials.py`

- [ ] **Step 1: Write the router**

```python
"""Spec §10 — Workflow E over HTTP.

Every refusal in here comes from the store as a `ValidationRejection` and is
turned into a 422 by the single handler in `app.py`, so the founder-facing
sentence the rule wrote is the sentence she reads (M2's pattern, unchanged).
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from foodbrew.api.deps import get_conn
from foodbrew.api.schemas import (
    BatchIn,
    BatchOut,
    CheckpointOut,
    ObservationIn,
    ObservationOut,
    ProtocolOut,
    SymptomDoseOut,
    SymptomEntryIn,
    SymptomEntryOut,
    SymptomPreviewIn,
    TrackedDoseOut,
    TrackedOut,
    TrialOut,
    TrialStatusIn,
    TrialSummaryOut,
)
from foodbrew.engine.observations import export_class
from foodbrew.engine.protocol import satisfied_checkpoint_ids
from foodbrew.engine.symptoms import SymptomDoseMath
from foodbrew.engine.trial_rules import ambient_storage_allowed
from foodbrew.engine.types import Tracked, TruthLabel
from foodbrew.store import observations as observations_store
from foodbrew.store import trials as trials_store

router = APIRouter(tags=["trials"])


def _tracked(payload) -> TrackedOut:
    """A dose payload's tracked value, whether it arrived as a dataclass or a dict."""
    if isinstance(payload, Tracked):
        return TrackedOut.of(payload)
    return TrackedOut(
        value=payload["value"], status=payload["status"], source=payload.get("source", "")
    )


def _dose(math: SymptomDoseMath | dict) -> SymptomDoseOut:
    payload = math.as_dict() if isinstance(math, SymptomDoseMath) else math
    return SymptomDoseOut(
        trigger_food_id=payload["trigger_food_id"],
        trigger_food_name=payload["trigger_food_name"],
        amount_value=payload["amount_value"], amount_unit=payload["amount_unit"],
        doses_used=payload["doses_used"], substrate_ids=payload["substrate_ids"],
        enzymes=[
            TrackedDoseOut(
                enzyme_id=e["enzyme_id"], enzyme_name=e["enzyme_name"],
                dose_unit=e["dose_unit"], dose_per_serving=e["dose_per_serving"],
                units_delivered=e["units_delivered"], threshold=_tracked(e["threshold"]),
                meets_threshold=e["meets_threshold"], ratio=e["ratio"],
                blocking_field=e["blocking_field"],
            )
            for e in payload["enzymes"]
        ],
        substrate_load=_tracked(payload["substrate_load"]),
        note=payload["note"],
    )


def _observation(record) -> ObservationOut:
    return ObservationOut(
        id=record.id, type=str(record.type), observed_at=record.observed_at,
        elapsed_minutes=record.elapsed_minutes, dwell_bucket=str(record.dwell_bucket),
        score=record.score, free_text=record.free_text, was_blinded=record.was_blinded,
        had_undressed_control=record.had_undressed_control,
        application_food_id=record.application_food_id,
        confidence_tier=str(record.tier), export_class=str(export_class(record)),
    )


def _symptom(entry) -> SymptomEntryOut:
    return SymptomEntryOut(
        id=entry.id, eaten_at=entry.eaten_at, trigger_food_id=entry.trigger_food_id,
        amount_value=entry.amount_value, amount_unit=entry.amount_unit,
        doses_used=entry.doses_used, outcome_score=entry.outcome_score,
        notes=entry.notes, computed_dose=_dose(entry.computed_dose),
    )


def _protocol(protocol) -> ProtocolOut:
    return ProtocolOut(
        engine_version=protocol.engine_version,
        checkpoints=[
            CheckpointOut(
                id=c.id, kind=str(c.kind), prompt=c.prompt, raised_by=list(c.raised_by),
                due_elapsed_minutes=c.due_elapsed_minutes,
                application_food_id=c.application_food_id,
                observation_type=str(c.observation_type) if c.observation_type else "",
            )
            for c in protocol.checkpoints
        ],
        notes=list(protocol.notes),
    )


def trial_out(conn, trial) -> TrialOut:
    return TrialOut(
        id=trial.id, evaluation_id=trial.evaluation_id,
        formulation_id=trial.formulation_id, status=trial.status,
        started_at=trial.started_at, notes=trial.notes,
        protocol=_protocol(trial.protocol),
        batches=[
            BatchOut(
                id=b.id, made_at=b.made_at, batch_size_g=b.batch_size_g,
                measured_ph=b.measured_ph, ph_method=b.ph_method,
                make_minutes=b.make_minutes, difficulty_score=b.difficulty_score,
                enzyme_source_note=b.enzyme_source_note,
                enzyme_addition_step=b.enzyme_addition_step,
                process_notes=b.process_notes, storage_mode=b.storage_mode,
                observations=[_observation(o) for o in b.observations],
                symptom_entries=[
                    _symptom(e) for e in observations_store.symptoms_for_batch(conn, b.id)
                ],
                due_checkpoint_ids=[c.id for c in trials_store.due_now(trial, b)],
                satisfied_checkpoint_ids=sorted(
                    satisfied_checkpoint_ids(trial.protocol, b.observations)
                ),
                ambient_storage_allowed=ambient_storage_allowed(b.measured_ph),
            )
            for b in trial.batches
        ],
    )


def _summary(conn, trial) -> TrialSummaryOut:
    return TrialSummaryOut(
        id=trial.id, evaluation_id=trial.evaluation_id,
        formulation_id=trial.formulation_id, status=trial.status,
        started_at=trial.started_at, batch_count=len(trial.batches),
        observation_count=len(trial.observations)
        + len(observations_store.symptoms_for_trial(conn, trial.id)),
        due_checkpoint_count=sum(
            len(trials_store.due_now(trial, b)) for b in trial.batches
        ),
    )


def _require(conn, trial_id: str):
    trial = trials_store.get(conn, trial_id)
    if trial is None:
        raise HTTPException(status_code=404, detail=f"No trial '{trial_id}'.")
    return trial


@router.post("/evaluations/{evaluation_id}/trial", response_model=TrialOut, status_code=201)
def start_trial(evaluation_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    trial_id = trials_store.create(conn, evaluation_id)
    return trial_out(conn, trials_store.get(conn, trial_id))


@router.get("/trials", response_model=list[TrialSummaryOut])
def list_active(conn: sqlite3.Connection = Depends(get_conn)):
    return [_summary(conn, t) for t in trials_store.list_active(conn)]


@router.get("/evaluations/{evaluation_id}/trials", response_model=list[TrialSummaryOut])
def list_for_evaluation(evaluation_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    return [_summary(conn, t) for t in trials_store.list_for_evaluation(conn, evaluation_id)]


@router.get("/trials/{trial_id}", response_model=TrialOut)
def get_trial(trial_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    return trial_out(conn, _require(conn, trial_id))


@router.post("/trials/{trial_id}/status", response_model=TrialOut)
def set_status(
    trial_id: str, payload: TrialStatusIn, conn: sqlite3.Connection = Depends(get_conn)
):
    _require(conn, trial_id)
    return trial_out(conn, trials_store.set_status(conn, trial_id, payload.status))


@router.post("/trials/{trial_id}/batches", response_model=TrialOut, status_code=201)
def add_batch(trial_id: str, payload: BatchIn, conn: sqlite3.Connection = Depends(get_conn)):
    _require(conn, trial_id)
    trials_store.add_batch(conn, trial_id, **payload.model_dump())
    return trial_out(conn, trials_store.get(conn, trial_id))


@router.post("/trial-batches/{batch_id}/observations", response_model=TrialOut, status_code=201)
def add_observation(
    batch_id: str, payload: ObservationIn, conn: sqlite3.Connection = Depends(get_conn)
):
    observations_store.add_observation(conn, batch_id, **payload.model_dump())
    return trial_out(conn, trials_store.get(conn, _trial_id_for_batch(conn, batch_id)))


@router.post(
    "/trial-batches/{batch_id}/symptom-entries", response_model=TrialOut, status_code=201
)
def add_symptom_entry(
    batch_id: str, payload: SymptomEntryIn, conn: sqlite3.Connection = Depends(get_conn)
):
    observations_store.add_symptom_entry(conn, batch_id, **payload.model_dump())
    return trial_out(conn, trials_store.get(conn, _trial_id_for_batch(conn, batch_id)))


@router.post("/trial-batches/{batch_id}/symptom-preview", response_model=SymptomDoseOut)
def preview_symptom(
    batch_id: str, payload: SymptomPreviewIn, conn: sqlite3.Connection = Depends(get_conn)
):
    """Plan decision #8 — a POST because it carries a body, and it writes nothing."""
    return _dose(observations_store.preview_symptom(conn, batch_id, **payload.model_dump()))


def _trial_id_for_batch(conn, batch_id: str) -> str:
    row = conn.execute(
        "SELECT trial_id FROM trial_batch WHERE id = ?", (batch_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No batch '{batch_id}'.")
    return row["trial_id"]
```

- [ ] **Step 2: Register it**

In `src/foodbrew/api/app.py`, add `trials` to the router import list and to the tuple in `create_app`:

```python
from foodbrew.api.routers import (
    catalog,
    evaluations,
    export,
    formulations,
    proposals,
    recipes,
    records,
    trials,
    variants,
)
```

```python
    for router in (
        catalog.router, recipes.router, formulations.router, evaluations.router,
        variants.router, records.router, proposals.router, export.router, trials.router,
    ):
```

- [ ] **Step 3: Write the tests**

```python
"""Spec §10's trial endpoints, over the real app."""

import pytest


@pytest.fixture
def trial(client, vinaigrette):
    evaluation = client.post(
        f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
    ).json()
    response = client.post(f"/api/v1/evaluations/{evaluation['id']}/trial")
    assert response.status_code == 201
    return evaluation, response.json()


def _batch(client, trial_id, **body):
    response = client.post(f"/api/v1/trials/{trial_id}/batches", json=body)
    assert response.status_code == 201, response.text
    return response.json()["batches"][-1]


def test_starting_a_trial_returns_a_protocol_built_from_the_findings(trial):
    _evaluation, payload = trial
    assert payload["status"] == "planned"
    kinds = {c["kind"] for c in payload["protocol"]["checkpoints"]}
    assert {"make_it", "usability"} <= kinds
    assert payload["protocol"]["notes"]


def test_starting_a_trial_on_a_missing_evaluation_is_refused(client):
    assert client.post("/api/v1/evaluations/nope/trial").status_code == 422


def test_logging_a_batch_starts_the_trial_and_reports_due_checkpoints(client, trial):
    _evaluation, payload = trial
    batch = _batch(client, payload["id"], batch_size_g=200.0, make_minutes=10, difficulty_score=2)
    refreshed = client.get(f"/api/v1/trials/{payload['id']}").json()
    assert refreshed["status"] == "running"
    assert refreshed["started_at"]
    assert batch["ambient_storage_allowed"] is False


def test_the_storage_gate_refuses_ambient_without_a_qualifying_ph(client, trial):
    _evaluation, payload = trial
    response = client.post(
        f"/api/v1/trials/{payload['id']}/batches", json={"storage_mode": "ambient"}
    )
    assert response.status_code == 422
    assert "4.6" in response.json()["detail"]


def test_the_storage_gate_permits_ambient_below_the_line(client, trial):
    _evaluation, payload = trial
    batch = _batch(
        client, payload["id"], measured_ph=4.1, ph_method="meter", storage_mode="ambient"
    )
    assert batch["storage_mode"] == "ambient"
    assert batch["ambient_storage_allowed"] is True


def test_an_observation_comes_back_with_a_derived_bucket_and_tier(client, trial):
    _evaluation, payload = trial
    batch = _batch(client, payload["id"], batch_size_g=200.0)
    response = client.post(
        f"/api/v1/trial-batches/{batch['id']}/observations",
        json={
            "type": "food_texture", "elapsed_minutes": 240, "score": 3,
            "application_food_id": "romaine", "had_undressed_control": True,
        },
    )
    assert response.status_code == 201
    observation = response.json()["batches"][0]["observations"][0]
    assert observation["dwell_bucket"] == "packed"
    assert observation["confidence_tier"] == "suggestive"
    assert observation["export_class"] == "finding"


def test_a_client_cannot_send_a_symptom_observation(client, trial):
    _evaluation, payload = trial
    batch = _batch(client, payload["id"], batch_size_g=200.0)
    response = client.post(
        f"/api/v1/trial-batches/{batch['id']}/observations",
        json={"type": "symptom", "elapsed_minutes": 0},
    )
    assert response.status_code == 422


def test_a_client_cannot_choose_the_dwell_bucket(client, trial):
    _evaluation, payload = trial
    batch = _batch(client, payload["id"], batch_size_g=200.0)
    response = client.post(
        f"/api/v1/trial-batches/{batch['id']}/observations",
        json={
            "type": "food_texture", "elapsed_minutes": 0, "score": 2,
            "application_food_id": "romaine", "dwell_bucket": "marinade",
        },
    )
    assert response.status_code == 201
    assert response.json()["batches"][0]["observations"][0]["dwell_bucket"] == "immediate"


def test_the_preview_returns_the_dose_math_and_writes_nothing(client, trial):
    _evaluation, payload = trial
    batch = _batch(client, payload["id"], batch_size_g=200.0)
    response = client.post(
        f"/api/v1/trial-batches/{batch['id']}/symptom-preview",
        json={"trigger_food_id": "milk", "amount_value": 1.0, "doses_used": 2.0},
    )
    assert response.status_code == 200
    assert response.json()["enzymes"][0]["units_delivered"] == 18000.0
    refreshed = client.get(f"/api/v1/trials/{payload['id']}").json()
    assert refreshed["batches"][0]["symptom_entries"] == []


def test_a_symptom_entry_stores_the_same_math_the_preview_showed(client, trial):
    _evaluation, payload = trial
    batch = _batch(client, payload["id"], batch_size_g=200.0)
    body = {"trigger_food_id": "milk", "amount_value": 1.0, "doses_used": 2.0}
    preview = client.post(
        f"/api/v1/trial-batches/{batch['id']}/symptom-preview", json=body
    ).json()
    stored = client.post(
        f"/api/v1/trial-batches/{batch['id']}/symptom-entries",
        json={**body, "outcome_score": 2, "notes": "fine"},
    ).json()["batches"][0]["symptom_entries"][0]
    assert stored["computed_dose"] == preview


def test_a_trial_can_be_completed_and_then_takes_nothing_more(client, trial):
    _evaluation, payload = trial
    batch = _batch(client, payload["id"], batch_size_g=200.0)
    done = client.post(f"/api/v1/trials/{payload['id']}/status", json={"status": "complete"})
    assert done.status_code == 200
    assert done.json()["status"] == "complete"

    refused = client.post(
        f"/api/v1/trial-batches/{batch['id']}/observations",
        json={"type": "taste", "elapsed_minutes": 0, "score": 3},
    )
    assert refused.status_code == 422
    assert "new trial" in refused.json()["detail"]


def test_an_abandoned_trial_keeps_its_records_and_leaves_the_active_list(client, trial):
    _evaluation, payload = trial
    batch = _batch(client, payload["id"], batch_size_g=200.0)
    client.post(
        f"/api/v1/trial-batches/{batch['id']}/observations",
        json={"type": "taste", "elapsed_minutes": 0, "score": 4, "free_text": "odd"},
    )
    client.post(f"/api/v1/trials/{payload['id']}/status", json={"status": "abandoned"})

    assert client.get("/api/v1/trials").json() == []
    kept = client.get(f"/api/v1/trials/{payload['id']}").json()
    assert kept["batches"][0]["observations"][0]["free_text"] == "odd"


def test_the_active_list_summarises_what_is_outstanding(client, trial):
    _evaluation, payload = trial
    _batch(client, payload["id"], batch_size_g=200.0)
    summary = client.get("/api/v1/trials").json()[0]
    assert summary["id"] == payload["id"]
    assert summary["batch_count"] == 1
    assert summary["due_checkpoint_count"] >= 0
```

- [ ] **Step 4: Run them**

Run: `.venv/bin/pytest tests/api/test_trials.py -q`
Expected: 13 passed.

- [ ] **Step 5: Commit**

```bash
git add src/foodbrew/api/routers/trials.py src/foodbrew/api/app.py tests/api/test_trials.py
git commit -m "feat(api): Workflow E endpoints — trials, batches, observations, symptoms"
```

---

## Task 10: The Observed column on the evaluation payload

Spec §6.3's second column, assembled in the router from two independent reads so that nothing in the store's evaluation path can ever be tempted to fold an observation into a prediction (decision #10).

**Files:**
- Modify: `src/foodbrew/api/routers/evaluations.py`
- Create: `tests/api/test_evaluation_observed.py`

- [ ] **Step 1: Assemble the column**

In `routers/evaluations.py`, add the imports:

```python
from foodbrew.api.schemas import ObservedEnvelopeOut, ObservedProfileOut
from foodbrew.engine.observations import TEXTURE_SCALE_NOTE, observed_envelope
from foodbrew.store import trials as trials_store
```

Add this function above `evaluation_out`:

```python
def _observed(conn, evaluation_id: str) -> tuple[ObservedEnvelopeOut | None, list[str]]:
    """Spec §6.3 — the Observed column, from the trials that test this evaluation.

    Read-only and additive: the stored envelope, the findings, and the headline
    are untouched (plan decision #10). The newest trial with any observation
    wins; earlier ones stay readable on their own screens.
    """
    stored_trials = trials_store.list_for_evaluation(conn, evaluation_id)
    if not stored_trials:
        return None, []

    with_records = [t for t in stored_trials if t.observations]
    source = with_records[0] if with_records else stored_trials[0]
    envelope = observed_envelope(source.observations)
    return (
        ObservedEnvelopeOut(
            trial_id=source.id,
            profiles={
                str(profile): ObservedProfileOut(
                    verdict=str(cell.verdict) if cell.verdict is not None else None,
                    confidence_tier=str(cell.tier) if cell.tier is not None else None,
                    observation_count=cell.observation_count,
                    driving_observation_id=cell.driving_observation_id,
                )
                for profile, cell in envelope.items()
            },
            scale_note=TEXTURE_SCALE_NOTE,
        ),
        [t.id for t in stored_trials],
    )
```

Change `evaluation_out`'s signature and the two fields at the end of its return:

```python
def evaluation_out(
    stored, *, stale: bool = False, changes=(), observed=None, trial_ids=()
) -> EvaluationOut:
```

```python
        observed=observed,
        trial_ids=list(trial_ids),
    )
```

And in `get_evaluation`, pass them:

```python
    stale, changes = store.freshness(conn, stored)
    observed, trial_ids = _observed(conn, evaluation_id)
    return evaluation_out(stored, stale=stale, changes=changes, observed=observed, trial_ids=trial_ids)
```

`run_evaluation` and the apply-variant path keep calling `evaluation_out(stored)` — a run that has just happened has no trial, and the defaults say so.

- [ ] **Step 2: Write the tests**

```python
"""Spec §6.3's Observed column and §13's "an observation never mutates a prediction"."""

import pytest


@pytest.fixture
def evaluated(client, vinaigrette):
    return client.post(
        f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
    ).json()


def _trial_with(client, evaluation_id, **observation):
    trial = client.post(f"/api/v1/evaluations/{evaluation_id}/trial").json()
    batch = client.post(
        f"/api/v1/trials/{trial['id']}/batches", json={"batch_size_g": 200.0}
    ).json()["batches"][0]
    if observation:
        client.post(f"/api/v1/trial-batches/{batch['id']}/observations", json=observation)
    return trial


def test_without_a_trial_the_observed_column_is_absent(client, evaluated):
    payload = client.get(f"/api/v1/evaluations/{evaluated['id']}").json()
    assert payload["observed"] is None
    assert payload["trial_ids"] == []


def test_an_observation_fills_its_bucket_and_leaves_the_others_empty(client, evaluated):
    _trial_with(
        client, evaluated["id"], type="food_texture", elapsed_minutes=240, score=4,
        application_food_id="romaine",
    )
    payload = client.get(f"/api/v1/evaluations/{evaluated['id']}").json()
    profiles = payload["observed"]["profiles"]
    assert profiles["packed"]["verdict"] == "red"
    assert profiles["packed"]["confidence_tier"] == "anecdote"
    assert profiles["immediate"]["verdict"] is None
    assert "convention" in payload["observed"]["scale_note"]


def test_the_observed_column_never_moves_the_headline_or_the_prediction(client, evaluated):
    before = client.get(f"/api/v1/evaluations/{evaluated['id']}").json()
    _trial_with(
        client, evaluated["id"], type="food_texture", elapsed_minutes=1440, score=5,
        application_food_id="romaine",
    )
    after = client.get(f"/api/v1/evaluations/{evaluated['id']}").json()
    assert after["headline"] == before["headline"]
    assert after["overall"] == before["overall"]
    assert after["envelope"] == before["envelope"]
    assert after["findings"] == before["findings"]


def test_a_trial_with_no_observations_still_lists_its_id(client, evaluated):
    trial = _trial_with(client, evaluated["id"])
    payload = client.get(f"/api/v1/evaluations/{evaluated['id']}").json()
    assert payload["trial_ids"] == [trial["id"]]
    assert all(p["verdict"] is None for p in payload["observed"]["profiles"].values())
```

- [ ] **Step 3: Run them, with M3's evaluation tests**

Run: `.venv/bin/pytest tests/api/test_evaluation_observed.py tests/api/test_evaluations.py tests/api/test_evaluation_extras.py -q`
Expected: all pass; M3's assertions are untouched because every new field defaults.

- [ ] **Step 4: Commit**

```bash
git add src/foodbrew/api/routers/evaluations.py tests/api/test_evaluation_observed.py
git commit -m "feat(api): the observed envelope beside the predicted one"
```

---

## Task 11: The export carries the trial

`routers/export.py` assembles the `TrialReport` Task 4 renders. This is where §6.6's classification meets real rows.

**Files:**
- Modify: `src/foodbrew/api/routers/export.py`
- Create: `tests/api/test_trial_export.py`

- [ ] **Step 1: Assemble the trial in the export route**

Replace the imports and body of `export.py`'s route with:

```python
from foodbrew.engine.observations import (
    TEXTURE_SCALE,
    ExportClass,
    export_class,
    observed_envelope,
)
from foodbrew.engine.report import (
    ReportInput,
    ReportObservation,
    ReportSuggestion,
    ReportSymptomEntry,
    TrialReport,
    render_markdown,
)
from foodbrew.store import observations as observations_store
from foodbrew.store import trials as trials_store
```

Add these helpers above the route:

```python
_OCCASION_SHORT = {
    "immediate": "within the hour",
    "packed": "1 to 8 hours",
    "marinade": "8 hours or more",
}


def _dose_lines(payload: dict) -> tuple[str, ...]:
    """One line per enzyme, from the math frozen with the entry (§6.6)."""
    lines = []
    for entry in payload.get("enzymes", ()):
        unit = entry["dose_unit"]
        if entry["units_delivered"] is None or entry["threshold"]["value"] is None:
            lines.append(
                f"{entry['enzyme_name']}: the delivered dose could not be worked out "
                f"({entry['blocking_field'] or 'missing input'})."
            )
            continue
        verdict = "clears it" if entry["meets_threshold"] else "below it"
        lines.append(
            f"{entry['enzyme_name']}: {entry['units_delivered']:g} {unit} delivered "
            f"against a {entry['threshold']['value']:g} {unit} evidence threshold — "
            f"{verdict}."
        )
    if payload.get("note"):
        lines.append(payload["note"])
    return tuple(lines)


def _trial_report(conn, evaluation_id: str) -> TrialReport | None:
    stored_trials = trials_store.list_for_evaluation(conn, evaluation_id)
    if not stored_trials:
        return None
    trial = next((t for t in stored_trials if t.observations), stored_trials[0])

    records = []
    for batch in trial.batches:
        for record in batch.observations:
            food = record.application_food_id
            records.append(
                ReportObservation(
                    observation_type=str(record.type),
                    export_class=export_class(record),
                    tier=str(record.tier),
                    occasion=_OCCASION_SHORT[str(record.dwell_bucket)],
                    observed_at=record.observed_at,
                    elapsed_minutes=record.elapsed_minutes,
                    application_food_name=food,
                    score=record.score,
                    free_text=record.free_text,
                )
            )

    symptoms = [
        ReportSymptomEntry(
            eaten_at=entry.eaten_at,
            trigger_food_name=entry.computed_dose.get("trigger_food_name", entry.trigger_food_id),
            amount=(
                f"{entry.amount_value:g} {entry.amount_unit}"
                if entry.amount_value is not None
                else "amount not recorded"
            ),
            doses_used=entry.doses_used,
            outcome_score=entry.outcome_score,
            dose_lines=_dose_lines(entry.computed_dose),
            notes=entry.notes,
        )
        for entry in observations_store.symptoms_for_trial(conn, trial.id)
    ]

    envelope = observed_envelope(trial.observations)
    observed = {
        profile: (
            f"{TEXTURE_SCALE[_score_for(trial, cell)]} ({cell.tier})"
            if cell.verdict is not None
            else ""
        )
        for profile, cell in envelope.items()
    }

    measured = [b.measured_ph for b in trial.batches if b.measured_ph is not None]
    note = (
        f"Measured pH of the batch: {measured[-1]}. Later evaluations of this "
        "formulation use that reading in place of the estimate."
        if measured
        else ""
    )
    return TrialReport(
        trial_id=trial.id, status=trial.status, batch_count=len(trial.batches),
        observations=tuple(records), symptoms=tuple(symptoms),
        observed_envelope=observed, measured_ph_note=note,
    )


def _score_for(trial, cell) -> int:
    """The score behind an observed cell, for the scale wording the report prints."""
    for record in trial.observations:
        if record.id == cell.driving_observation_id and record.score is not None:
            return record.score
    return 1
```

and pass it into `ReportInput` in the route, after `stale=stale`:

```python
            trial=_trial_report(conn, evaluation_id),
```

- [ ] **Step 2: Write the tests**

```python
"""§6.6's split and §13's report lint, over an exported trial."""

import pytest

from foodbrew.engine.language import contains_prohibited


@pytest.fixture
def exported(client, vinaigrette):
    def _run():
        evaluation = client.post(
            f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
        ).json()
        return evaluation, client.get(f"/api/v1/export/{evaluation['id']}.md").text

    return _run


def _trial_with_everything(client, evaluation_id):
    trial = client.post(f"/api/v1/evaluations/{evaluation_id}/trial").json()
    batch = client.post(
        f"/api/v1/trials/{trial['id']}/batches",
        json={"batch_size_g": 200.0, "measured_ph": 3.4, "ph_method": "meter",
              "make_minutes": 12, "difficulty_score": 2},
    ).json()["batches"][0]
    client.post(
        f"/api/v1/trial-batches/{batch['id']}/observations",
        json={"type": "taste", "elapsed_minutes": 0, "score": 4, "free_text": "sharper than expected"},
    )
    client.post(
        f"/api/v1/trial-batches/{batch['id']}/observations",
        json={"type": "food_texture", "elapsed_minutes": 240, "score": 3,
              "application_food_id": "romaine", "had_undressed_control": True},
    )
    client.post(
        f"/api/v1/trial-batches/{batch['id']}/observations",
        json={"type": "food_texture", "elapsed_minutes": 1440, "score": 4,
              "application_food_id": "romaine"},
    )
    client.post(
        f"/api/v1/trial-batches/{batch['id']}/symptom-entries",
        json={"trigger_food_id": "milk", "amount_value": 1.0, "doses_used": 1.0,
              "outcome_score": 2, "notes": "no bloating"},
    )
    return trial


def test_before_a_trial_the_export_is_unchanged_from_m3(exported):
    _evaluation, body = exported()
    assert "No trial has been recorded for this formulation yet." in body


def test_the_exported_trial_splits_findings_observations_and_hypotheses(client, exported):
    evaluation, _body = exported()
    _trial_with_everything(client, evaluation["id"])
    body = client.get(f"/api/v1/export/{evaluation['id']}.md").text

    assert "### Findings" in body
    assert "> sharper than expected" in body           # taste — a finding
    assert "### Observations" in body                   # texture with no control
    assert "### Hypotheses for a food scientist to test" in body
    assert "evidence threshold" in body                 # dose math attached
    assert "> no bloating" in body


def test_the_exported_trial_reports_the_measured_ph_and_what_it_does(client, exported):
    evaluation, _body = exported()
    _trial_with_everything(client, evaluation["id"])
    body = client.get(f"/api/v1/export/{evaluation['id']}.md").text
    assert "Measured pH of the batch: 3.4" in body


def test_the_observed_column_appears_in_the_occasion_table(client, exported):
    evaluation, _body = exported()
    _trial_with_everything(client, evaluation["id"])
    body = client.get(f"/api/v1/export/{evaluation['id']}.md").text
    assert "| Occasion | Predicted | Observed |" in body
    assert "anecdote" in body or "suggestive" in body


def test_the_exported_trial_still_passes_the_report_lint(client, exported):
    evaluation, _body = exported()
    _trial_with_everything(client, evaluation["id"])
    body = client.get(f"/api/v1/export/{evaluation['id']}.md").text
    assert contains_prohibited(body) == ()


def test_an_abandoned_trial_says_so_in_the_export(client, exported):
    evaluation, _body = exported()
    trial = _trial_with_everything(client, evaluation["id"])
    client.post(f"/api/v1/trials/{trial['id']}/status", json={"status": "abandoned"})
    body = client.get(f"/api/v1/export/{evaluation['id']}.md").text
    assert "abandoned after" in body
```

- [ ] **Step 3: Run them, with M3's export tests**

Run: `.venv/bin/pytest tests/api/test_trial_export.py tests/api/test_export.py -q`
Expected: all pass. M3's `test_the_export_says_no_trial_has_been_recorded` still passes because it never creates a trial.

- [ ] **Step 4: Commit**

```bash
git add src/foodbrew/api/routers/export.py tests/api/test_trial_export.py
git commit -m "feat(api): export the trial with its 6.6 honesty split"
```

---

## Task 12: M4 contract tests

The guards for decisions #2, #6, #10, #12 and #14, asserted against source and behaviour rather than trusted to review.

**Files:**
- Create: `tests/api/test_contracts_m4.py`

- [ ] **Step 1: Write them**

```python
"""M4's boundaries, asserted rather than reviewed."""

import pathlib

import pytest

from foodbrew.api import schemas
from foodbrew.engine.language import contains_prohibited

SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "foodbrew"
ENGINE = SRC / "engine"


def _python_files(root):
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def test_no_engine_module_reads_a_clock():
    """Plan decision #14 — time enters the engine as an argument."""
    offenders = []
    for path in _python_files(ENGINE):
        text = path.read_text(encoding="utf-8")
        for needle in ("now_iso", "datetime.now", "time.time", "utcnow"):
            if needle in text:
                offenders.append(f"{path.name}: {needle}")
    assert not offenders, ", ".join(offenders)


def test_no_engine_module_imports_the_store_or_the_api():
    offenders = []
    for path in _python_files(ENGINE):
        text = path.read_text(encoding="utf-8")
        for needle in ("foodbrew.store", "foodbrew.api", "foodbrew.db", "import sqlite3", "fastapi"):
            if needle in text:
                offenders.append(f"{path.name}: {needle}")
    assert not offenders, ", ".join(offenders)


def test_no_store_module_imports_the_api():
    offenders = [
        p.name
        for p in _python_files(SRC / "store")
        if "fastapi" in p.read_text(encoding="utf-8")
        or "foodbrew.api" in p.read_text(encoding="utf-8")
    ]
    assert not offenders, ", ".join(offenders)


@pytest.mark.parametrize("field", ["dwell_bucket", "confidence_tier", "export_class"])
def test_no_request_schema_lets_a_client_supply_a_derived_value(field):
    """Plan decision #2 — derived facts are derived on the server."""
    offenders = [
        name
        for name, model in vars(schemas).items()
        if isinstance(model, type)
        and issubclass(model, schemas.BaseModel)
        and name.endswith("In")
        and field in model.model_fields
    ]
    assert not offenders, ", ".join(offenders)


def test_no_request_schema_accepts_a_symptom_observation():
    """Plan decision #6 — one door for symptoms, and the schema is the lock."""
    assert "symptom" not in str(schemas.ObservationIn.model_fields["type"].annotation)


def test_only_the_two_terminal_statuses_are_settable():
    """Plan decision #12."""
    annotation = str(schemas.TrialStatusIn.model_fields["status"].annotation)
    assert "complete" in annotation and "abandoned" in annotation
    assert "planned" not in annotation and "running" not in annotation


def test_no_trial_endpoint_writes_to_an_evaluation_table():
    """Plan decision #10 — the router that serves trials cannot touch a prediction."""
    text = (SRC / "api" / "routers" / "trials.py").read_text(encoding="utf-8")
    for statement in ("UPDATE evaluation", "UPDATE rule_finding", "INSERT INTO evaluation"):
        assert statement not in text


def test_no_prohibited_word_appears_in_m4_source_copy():
    """M3's api-source lint, extended to the two new store modules and the router."""
    offenders = []
    for path in (
        SRC / "api" / "routers" / "trials.py",
        SRC / "store" / "trials.py",
        SRC / "store" / "observations.py",
        ENGINE / "protocol.py",
        ENGINE / "observations.py",
        ENGINE / "symptoms.py",
    ):
        for word in contains_prohibited(path.read_text(encoding="utf-8")):
            offenders.append(f"{path.name}: {word}")
    assert not offenders, ", ".join(offenders)
```

- [ ] **Step 2: Run the whole suite**

Run: `.venv/bin/pytest -q && .venv/bin/ruff check src tests`
Expected: every test green, ruff clean. `test_no_engine_module_reads_a_clock` is the one most likely to fail — if it does, the fix is to pass the time in, never to weaken the test.

- [ ] **Step 3: Commit**

```bash
git add tests/api/test_contracts_m4.py
git commit -m "test(api): M4 contract tests for the derived-value and clock boundaries"
```

---

## Task 13: Frontend types and API client

Types first — every later web task imports them.

**Files:**
- Modify: `web/src/api/types.ts`, `web/src/api/client.ts`

- [ ] **Step 1: Add the types**

Append to `web/src/api/types.ts`:

```ts
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
```

and add the two fields to the existing `Evaluation` interface, after `changes`:

```ts
  observed: ObservedEnvelope | null
  trial_ids: string[]
```

- [ ] **Step 2: Add the client calls**

In `web/src/api/client.ts`, extend the type import with `Trial, TrialSummary, SymptomDose` and add to the `api` object, above `reportUrl`:

```ts
  startTrial: (evaluationId: string) => post<Trial>(`/evaluations/${evaluationId}/trial`),
  trial: (id: string) => request<Trial>(`/trials/${id}`),
  activeTrials: () => request<TrialSummary[]>('/trials'),
  trialsForEvaluation: (evaluationId: string) =>
    request<TrialSummary[]>(`/evaluations/${evaluationId}/trials`),
  setTrialStatus: (id: string, status: 'complete' | 'abandoned') =>
    post<Trial>(`/trials/${id}/status`, { status }),

  addBatch: (trialId: string, body: unknown) => post<Trial>(`/trials/${trialId}/batches`, body),
  addObservation: (batchId: string, body: unknown) =>
    post<Trial>(`/trial-batches/${batchId}/observations`, body),
  addSymptomEntry: (batchId: string, body: unknown) =>
    post<Trial>(`/trial-batches/${batchId}/symptom-entries`, body),
  previewSymptom: (batchId: string, body: unknown) =>
    post<SymptomDose>(`/trial-batches/${batchId}/symptom-preview`, body),
```

- [ ] **Step 3: Typecheck**

Run: `cd web && npm run typecheck`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add web/src/api/types.ts web/src/api/client.ts
git commit -m "feat(web): types and client calls for the kitchen trial"
```

---

## Task 14: The trial components — checklist, batch form, observation form

Three of the four forms on §10 screen 6. The batch form owns the 4.6 gate in the browser (decision #5).

**Files:**
- Create: `web/src/components/ProtocolChecklist.tsx`, `web/src/components/BatchForm.tsx`, `web/src/components/ObservationForm.tsx`

- [ ] **Step 1: `ProtocolChecklist.tsx`**

```tsx
import type { Checkpoint, TrialBatch } from '../api/types'

const KIND_TITLES: Record<string, string> = {
  make_it: 'Making it',
  ph: 'pH',
  taste: 'Taste',
  usability: 'Using it',
  food_texture: 'What it did to the food',
  storage: 'Storage watch',
  symptom: 'Meals',
}

function when(minutes: number | null): string {
  if (minutes === null) return 'as it happens'
  if (minutes === 0) return 'straight away'
  if (minutes < 60) return `${minutes} min after making it`
  if (minutes < 60 * 24) return `${minutes / 60} hr after making it`
  return `day ${minutes / (60 * 24)}`
}

/** Spec §6.5 — generated from the evaluation's own gaps, never a blank form. */
export function ProtocolChecklist({ checkpoints, batch, notes }: {
  checkpoints: Checkpoint[]
  batch: TrialBatch | null
  notes: string[]
}) {
  const due = new Set(batch?.due_checkpoint_ids ?? [])
  const done = new Set(batch?.satisfied_checkpoint_ids ?? [])
  const scheduled = checkpoints.filter((c) => c.due_elapsed_minutes !== null)
  const perUse = checkpoints.filter((c) => c.due_elapsed_minutes === null)

  return (
    <section data-testid="protocol">
      <h3>What to watch</h3>
      <p className="blurb">
        Every item here comes from something this formulation could not settle on
        paper. Nothing was invented to fill a form.
      </p>

      <table>
        <thead><tr><th>When</th><th>What</th><th>Because of</th><th /></tr></thead>
        <tbody>
          {scheduled.map((c) => {
            const state = done.has(c.id) ? 'done' : due.has(c.id) ? 'due' : 'later'
            return (
              <tr key={c.id} data-testid={`checkpoint-${c.id}`} className={`checkpoint--${state}`}>
                <td>{when(c.due_elapsed_minutes)}</td>
                <td><strong>{KIND_TITLES[c.kind] ?? c.kind}</strong><br />{c.prompt}</td>
                <td>{c.raised_by.join(', ')}</td>
                <td data-testid={`checkpoint-state-${c.id}`}>
                  {state === 'done' ? 'recorded' : state === 'due' ? 'due now' : 'not yet'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>

      <h4>Log these as they happen</h4>
      <ul data-testid="per-use-checkpoints">
        {perUse.map((c) => (
          <li key={c.id}>
            <strong>{KIND_TITLES[c.kind] ?? c.kind}</strong> — {c.prompt}{' '}
            <small className="blurb">({c.raised_by.join(', ')})</small>
          </li>
        ))}
      </ul>

      <h4>Before you start</h4>
      <ul data-testid="protocol-notes">
        {notes.map((note) => <li key={note}>{note}</li>)}
      </ul>
    </section>
  )
}
```

- [ ] **Step 2: `BatchForm.tsx` — the gate in the browser**

```tsx
import { useState } from 'react'

const AMBIENT_LIMIT = 4.6

/**
 * Spec §3 Workflow E and §10 screen 6 — the ambient control stays disabled until
 * a measured pH below 4.6 is in the form. The API refuses it too (plan decision
 * #5); this is the half that stops her filling a form she cannot submit.
 */
export function BatchForm({ onSubmit }: { onSubmit: (body: unknown) => Promise<void> }) {
  const [ph, setPh] = useState('')
  const [phMethod, setPhMethod] = useState<'none' | 'strip' | 'meter'>('none')
  const [ambient, setAmbient] = useState(false)
  const [sizeG, setSizeG] = useState('')
  const [minutes, setMinutes] = useState('')
  const [difficulty, setDifficulty] = useState('3')
  const [step, setStep] = useState('')
  const [sourceNote, setSourceNote] = useState('')
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)

  const phValue = ph === '' ? null : Number(ph)
  const ambientAllowed = phValue !== null && phValue < AMBIENT_LIMIT && phMethod !== 'none'
  const storageMode = ambient && ambientAllowed ? 'ambient' : 'refrigerated'

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    try {
      await onSubmit({
        batch_size_g: sizeG === '' ? null : Number(sizeG),
        measured_ph: phValue,
        ph_method: phMethod,
        make_minutes: minutes === '' ? null : Number(minutes),
        difficulty_score: Number(difficulty),
        enzyme_source_note: sourceNote,
        enzyme_addition_step: step === '' ? null : Number(step),
        process_notes: notes,
        storage_mode: storageMode,
      })
      setPh(''); setPhMethod('none'); setAmbient(false); setSizeG('')
      setMinutes(''); setStep(''); setSourceNote(''); setNotes('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} data-testid="batch-form">
      <h3>Log a batch</h3>
      <label>How much did you make? (g)
        <input data-testid="batch-size" value={sizeG} onChange={(e) => setSizeG(e.target.value)} />
      </label>
      <label>How many minutes did it take?
        <input data-testid="batch-minutes" value={minutes}
               onChange={(e) => setMinutes(e.target.value)} />
      </label>
      <label>How hard was it? (1 easy — 5 hard)
        <select data-testid="batch-difficulty" value={difficulty}
                onChange={(e) => setDifficulty(e.target.value)}>
          {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
      </label>
      <label>Which step did the enzyme go in after?
        <input data-testid="batch-step" value={step} onChange={(e) => setStep(e.target.value)} />
      </label>
      <label>Where did the enzyme come from?
        <input data-testid="batch-source" value={sourceNote}
               placeholder="e.g. two Lactaid Fast Act capsules opened"
               onChange={(e) => setSourceNote(e.target.value)} />
      </label>

      <fieldset>
        <legend>pH (optional)</legend>
        <label>Reading
          <input data-testid="batch-ph" value={ph} onChange={(e) => setPh(e.target.value)} />
        </label>
        <label>Measured with
          <select data-testid="batch-ph-method" value={phMethod}
                  onChange={(e) => setPhMethod(e.target.value as typeof phMethod)}>
            <option value="none">not measured</option>
            <option value="strip">a strip</option>
            <option value="meter">a meter</option>
          </select>
        </label>
      </fieldset>

      <label>
        <input type="checkbox" data-testid="batch-ambient" checked={ambient && ambientAllowed}
               disabled={!ambientAllowed} onChange={(e) => setAmbient(e.target.checked)} />
        Watch a jar at room temperature
      </label>
      {!ambientAllowed && (
        <p className="blurb" data-testid="ambient-gate">
          Room-temperature watching needs a measured pH below {AMBIENT_LIMIT} for this
          batch. Without that reading the schedule stays refrigerated.
        </p>
      )}

      <label>Anything go wrong?
        <textarea data-testid="batch-notes" value={notes}
                  onChange={(e) => setNotes(e.target.value)} />
      </label>
      <button type="submit" data-testid="save-batch" disabled={busy}>
        {busy ? 'Saving…' : 'Save this batch'}
      </button>
    </form>
  )
}
```

- [ ] **Step 3: `ObservationForm.tsx`**

```tsx
import { useState } from 'react'

import type { Food, ObservationType } from '../api/types'

const TYPES: { value: ObservationType; label: string }[] = [
  { value: 'taste', label: 'Taste and smell' },
  { value: 'usability', label: 'Using it' },
  { value: 'food_texture', label: 'What it did to the food' },
  { value: 'storage', label: 'The jar in storage' },
]

/** Spec §6.6 — the two rigor flags are per observation, ticked when they apply. */
const SCALE = [
  '1 — indistinguishable from the undressed portion',
  '2 — slightly softer, would not notice without comparing',
  '3 — clearly softer than the undressed portion',
  '4 — limp, wilted, or watery',
  '5 — badly broken down',
]

export function ObservationForm({ applicationFoods, onSubmit }: {
  applicationFoods: Food[]
  onSubmit: (body: unknown) => Promise<void>
}) {
  const [type, setType] = useState<ObservationType>('taste')
  const [minutes, setMinutes] = useState('0')
  const [score, setScore] = useState('3')
  const [foodId, setFoodId] = useState(applicationFoods[0]?.id ?? '')
  const [text, setText] = useState('')
  const [blinded, setBlinded] = useState(false)
  const [control, setControl] = useState(false)
  const [busy, setBusy] = useState(false)

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    try {
      await onSubmit({
        type,
        elapsed_minutes: Number(minutes),
        score: Number(score),
        free_text: text,
        was_blinded: blinded,
        had_undressed_control: control,
        application_food_id: type === 'food_texture' ? foodId : '',
      })
      setText(''); setBlinded(false); setControl(false)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} data-testid="observation-form">
      <h3>Record what you saw</h3>
      <label>What are you recording?
        <select data-testid="observation-type" value={type}
                onChange={(e) => setType(e.target.value as ObservationType)}>
          {TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
        </select>
      </label>
      <label>How long after you made it? (minutes)
        <input data-testid="observation-minutes" value={minutes}
               onChange={(e) => setMinutes(e.target.value)} />
      </label>
      {type === 'food_texture' && (
        <label>Which food?
          <select data-testid="observation-food" value={foodId}
                  onChange={(e) => setFoodId(e.target.value)}>
            {applicationFoods.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
          </select>
        </label>
      )}
      <label>Score
        <select data-testid="observation-score" value={score}
                onChange={(e) => setScore(e.target.value)}>
          {SCALE.map((label, index) => (
            <option key={label} value={index + 1}>{label}</option>
          ))}
        </select>
      </label>
      <label>In your words
        <textarea data-testid="observation-text" value={text}
                  onChange={(e) => setText(e.target.value)} />
      </label>
      <label>
        <input type="checkbox" data-testid="observation-control" checked={control}
               onChange={(e) => setControl(e.target.checked)} />
        I compared it against an undressed portion
      </label>
      <label>
        <input type="checkbox" data-testid="observation-blinded" checked={blinded}
               onChange={(e) => setBlinded(e.target.checked)} />
        Someone else handed it to me without telling me which was which
      </label>
      <p className="blurb">
        Either box makes this record a little stronger — it is still one person in a
        kitchen, and the report says so.
      </p>
      <button type="submit" data-testid="save-observation" disabled={busy}>
        {busy ? 'Saving…' : 'Save this record'}
      </button>
    </form>
  )
}
```

- [ ] **Step 4: Typecheck and commit**

Run: `cd web && npm run typecheck`
Expected: no errors.

```bash
git add web/src/components/ProtocolChecklist.tsx web/src/components/BatchForm.tsx web/src/components/ObservationForm.tsx
git commit -m "feat(web): protocol checklist, batch form with the 4.6 gate, observation form"
```

---

## Task 15: `SymptomForm.tsx` — the live dose math, and `ObservedList.tsx`

§10 screen 6's "computed dose against threshold as she types", debounced onto the preview endpoint (decision #8).

**Files:**
- Create: `web/src/components/SymptomForm.tsx`, `web/src/components/ObservedList.tsx`

- [ ] **Step 1: `SymptomForm.tsx`**

```tsx
import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { Food, SymptomDose } from '../api/types'

function doseLine(entry: SymptomDose['enzymes'][number]): string {
  if (entry.units_delivered === null || entry.threshold.value === null) {
    return `${entry.enzyme_name}: cannot work the dose out yet — ${
      entry.blocking_field || 'something is missing'
    }.`
  }
  const verdict = entry.meets_threshold ? 'clears the evidence threshold' : 'is below it'
  return `${entry.enzyme_name}: ${entry.units_delivered} ${entry.dose_unit} delivered against ` +
    `${entry.threshold.value} ${entry.dose_unit} — ${verdict}.`
}

/** Spec §5.3 — the only route for symptom capture, so the dose is always attached. */
export function SymptomForm({ batchId, triggerFoods, onSubmit }: {
  batchId: string
  triggerFoods: Food[]
  onSubmit: (body: unknown) => Promise<void>
}) {
  const [foodId, setFoodId] = useState(triggerFoods[0]?.id ?? '')
  const [amount, setAmount] = useState('1')
  const [doses, setDoses] = useState('1')
  const [outcome, setOutcome] = useState('3')
  const [notes, setNotes] = useState('')
  const [preview, setPreview] = useState<SymptomDose | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!foodId) return
    const handle = setTimeout(() => {
      api
        .previewSymptom(batchId, {
          trigger_food_id: foodId,
          amount_value: amount === '' ? null : Number(amount),
          amount_unit: 'servings',
          doses_used: doses === '' ? null : Number(doses),
        })
        .then(setPreview)
        .catch(() => setPreview(null))
    }, 300)
    return () => clearTimeout(handle)
  }, [batchId, foodId, amount, doses])

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    try {
      await onSubmit({
        trigger_food_id: foodId,
        amount_value: amount === '' ? null : Number(amount),
        amount_unit: 'servings',
        doses_used: doses === '' ? null : Number(doses),
        outcome_score: Number(outcome),
        notes,
      })
      setNotes('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} data-testid="symptom-form">
      <h3>Log a meal</h3>
      <label>What did you eat?
        <select data-testid="symptom-food" value={foodId}
                onChange={(e) => setFoodId(e.target.value)}>
          {triggerFoods.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
        </select>
      </label>
      <label>How many servings?
        <input data-testid="symptom-amount" value={amount}
               onChange={(e) => setAmount(e.target.value)} />
      </label>
      <label>How many doses of the dressing?
        <input data-testid="symptom-doses" value={doses}
               onChange={(e) => setDoses(e.target.value)} />
      </label>

      <div data-testid="dose-preview" className="blurb">
        {preview === null ? (
          'Working out the dose…'
        ) : (
          <>
            <ul>
              {preview.enzymes.map((entry) => (
                <li key={entry.enzyme_id}>{doseLine(entry)}</li>
              ))}
            </ul>
            {preview.note && <p>{preview.note}</p>}
          </>
        )}
      </div>

      <label>How did it go? (1 fine — 5 bad)
        <select data-testid="symptom-outcome" value={outcome}
                onChange={(e) => setOutcome(e.target.value)}>
          {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
      </label>
      <label>Notes
        <textarea data-testid="symptom-notes" value={notes}
                  onChange={(e) => setNotes(e.target.value)} />
      </label>
      <p className="blurb">
        One person, not blinded, on a product you have a stake in. The report carries
        these as questions for a food scientist, with this dose arithmetic attached —
        so a result that means nothing can be told apart from one that does.
      </p>
      <button type="submit" data-testid="save-symptom" disabled={busy}>
        {busy ? 'Saving…' : 'Save this meal'}
      </button>
    </form>
  )
}
```

- [ ] **Step 2: `ObservedList.tsx`**

```tsx
import type { Observation, SymptomEntry } from '../api/types'

const CLASS_TITLES: Record<string, string> = {
  finding: 'Findings — your answer is the data',
  observation: 'Observations — watched, not controlled',
  hypothesis: 'Hypotheses — for a food scientist to test properly',
}

/** Spec §6.6, on screen: the same three words the report uses. */
export function ObservedList({ observations, symptoms }: {
  observations: Observation[]
  symptoms: SymptomEntry[]
}) {
  const grouped = {
    finding: observations.filter((o) => o.export_class === 'finding'),
    observation: observations.filter((o) => o.export_class === 'observation'),
  }

  return (
    <section data-testid="observed-list">
      <h3>What you have recorded</h3>
      {(['finding', 'observation'] as const).map((key) => (
        <div key={key}>
          <h4>{CLASS_TITLES[key]}</h4>
          {grouped[key].length === 0 ? (
            <p className="blurb">Nothing in this group yet.</p>
          ) : (
            <ul data-testid={`observed-${key}`}>
              {grouped[key].map((o) => (
                <li key={o.id}>
                  <strong>{o.type.replace('_', ' ')}</strong>
                  {o.application_food_id && ` on ${o.application_food_id}`} —{' '}
                  {o.dwell_bucket}
                  {o.score !== null && `, scored ${o.score} of 5`}{' '}
                  <small className="blurb">({o.confidence_tier})</small>
                  {o.free_text && <blockquote>{o.free_text}</blockquote>}
                </li>
              ))}
            </ul>
          )}
        </div>
      ))}

      <h4>{CLASS_TITLES.hypothesis}</h4>
      {symptoms.length === 0 ? (
        <p className="blurb">No meal logged yet.</p>
      ) : (
        <ul data-testid="observed-hypothesis">
          {symptoms.map((entry) => (
            <li key={entry.id}>
              <strong>{entry.computed_dose.trigger_food_name}</strong>
              {entry.amount_value !== null && ` — ${entry.amount_value} ${entry.amount_unit}`}
              {entry.outcome_score !== null && `, outcome ${entry.outcome_score} of 5`}
              <ul>
                {entry.computed_dose.enzymes.map((dose) => (
                  <li key={dose.enzyme_id}>
                    {dose.units_delivered === null
                      ? `${dose.enzyme_name}: dose could not be worked out`
                      : `${dose.enzyme_name}: ${dose.units_delivered} ${dose.dose_unit} delivered` +
                        (dose.meets_threshold === null
                          ? ' — no threshold recorded to compare with'
                          : dose.meets_threshold
                            ? ' — clears the evidence threshold'
                            : ' — below the evidence threshold')}
                  </li>
                ))}
              </ul>
              {entry.notes && <blockquote>{entry.notes}</blockquote>}
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
```

- [ ] **Step 3: Typecheck and commit**

Run: `cd web && npm run typecheck`
Expected: no errors.

```bash
git add web/src/components/SymptomForm.tsx web/src/components/ObservedList.tsx
git commit -m "feat(web): symptom form with live dose math, and the 6.6 grouped record list"
```

---

## Task 16: The Trial screen, and the Observed column everywhere else

§10 screen 6, plus the three places a trial has to become visible: Home's active trials, the verdict's start/open button and Observed column, and the report's observed sections.

**Files:**
- Create: `web/src/screens/Trial.tsx`
- Modify: `web/src/App.tsx`, `web/src/screens/Home.tsx`, `web/src/screens/Verdict.tsx`, `web/src/screens/Report.tsx`, `web/src/components/EnvelopePanel.tsx`, `web/src/styles.css`

- [ ] **Step 1: `Trial.tsx`**

```tsx
import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { api } from '../api/client'
import { BatchForm } from '../components/BatchForm'
import { ObservationForm } from '../components/ObservationForm'
import { ObservedList } from '../components/ObservedList'
import { ProtocolChecklist } from '../components/ProtocolChecklist'
import { SymptomForm } from '../components/SymptomForm'
import type { Food, Formulation, Trial as TrialType } from '../api/types'

/** Spec §10 screen 6 — protocol, batch log, quick-entry forms, meals. */
export default function Trial() {
  const { trialId } = useParams()
  const [trial, setTrial] = useState<TrialType | null>(null)
  const [formulation, setFormulation] = useState<Formulation | null>(null)
  const [foods, setFoods] = useState<Food[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!trialId) return
    api.trial(trialId).then(setTrial).catch((e) => setError(e.message))
  }, [trialId])

  useEffect(() => {
    if (!trial) return
    Promise.all([api.formulation(trial.formulation_id), api.foods()])
      .then(([f, all]) => { setFormulation(f); setFoods(all) })
      .catch((e) => setError(e.message))
  }, [trial])

  const batch = trial?.batches.at(-1) ?? null

  const applicationFoods = useMemo(
    () => foods.filter((f) => formulation?.application_food_ids.includes(f.id)),
    [foods, formulation],
  )
  const triggerFoods = useMemo(
    () => foods.filter((f) => formulation?.target_trigger_food_ids.includes(f.id)),
    [foods, formulation],
  )

  const guard = useCallback(async (run: () => Promise<TrialType>) => {
    setError(null)
    try {
      setTrial(await run())
    } catch (e) {
      setError((e as Error).message)
    }
  }, [])

  if (error) return <p className="error" data-testid="trial-error">{error}</p>
  if (!trial) return <p>Loading…</p>

  const terminal = trial.status === 'complete' || trial.status === 'abandoned'

  return (
    <>
      <h1>Kitchen trial</h1>
      <p className="blurb">
        Testing <Link to={`/evaluations/${trial.evaluation_id}`}>this verdict</Link>.
        Status: <span data-testid="trial-status">{trial.status}</span>. Nothing you
        record here changes what the rules predicted — it is stored beside it.
      </p>

      <ProtocolChecklist
        checkpoints={trial.protocol.checkpoints}
        batch={batch}
        notes={trial.protocol.notes}
      />

      {terminal ? (
        <p data-testid="trial-closed">
          This trial is {trial.status}. Everything recorded stays here; start a new
          trial from the verdict screen to record anything else.
        </p>
      ) : (
        <>
          <BatchForm onSubmit={(body) => guard(() => api.addBatch(trial.id, body))} />
          {batch && (
            <>
              <ObservationForm
                applicationFoods={applicationFoods}
                onSubmit={(body) => guard(() => api.addObservation(batch.id, body))}
              />
              <SymptomForm
                batchId={batch.id}
                triggerFoods={triggerFoods}
                onSubmit={(body) => guard(() => api.addSymptomEntry(batch.id, body))}
              />
            </>
          )}
          <p className="no-print">
            <button type="button" data-testid="complete-trial"
                    onClick={() => guard(() => api.setTrialStatus(trial.id, 'complete'))}>
              Mark this trial complete
            </button>{' '}
            <button type="button" data-testid="abandon-trial"
                    onClick={() => guard(() => api.setTrialStatus(trial.id, 'abandoned'))}>
              Stop this trial
            </button>
          </p>
        </>
      )}

      <ObservedList
        observations={trial.batches.flatMap((b) => b.observations)}
        symptoms={trial.batches.flatMap((b) => b.symptom_entries)}
      />

      <p className="no-print">
        <Link to={`/evaluations/${trial.evaluation_id}/report`}>
          Open the report with these results in it
        </Link>
      </p>
    </>
  )
}
```

- [ ] **Step 2: Route it**

In `web/src/App.tsx`, import `Trial` and add the route beside the evaluation routes:

```tsx
import Trial from './screens/Trial'
```

```tsx
          <Route path="/trials/:trialId" element={<Trial />} />
```

- [ ] **Step 3: The Observed column on `EnvelopePanel`**

Replace `EnvelopePanel.tsx`'s component with:

```tsx
import type { DwellProfile, ObservedEnvelope, Verdict } from '../api/types'
import { VerdictBadge } from './VerdictBadge'

/** Spec §6.3 — the three occasions, with the dwell ranges that define them. */
const OCCASIONS: { profile: DwellProfile; title: string; blurb: string }[] = [
  { profile: 'immediate', title: 'Dressed at the table', blurb: 'Eaten within the hour' },
  { profile: 'packed', title: 'Packed ahead', blurb: 'Dressed 1 to 8 hours before eating' },
  { profile: 'marinade', title: 'Marinade', blurb: 'Left 8 hours or more, on purpose' },
]

export function EnvelopePanel({ envelope, observed }: {
  envelope: Record<DwellProfile, Verdict>
  observed?: ObservedEnvelope | null
}) {
  return (
    <section data-testid="envelope-panel">
      <h3>Which occasions this can support</h3>
      <p className="blurb">
        What the dressing does to the food it sits on, by how long it sits there.
        An occasion you do not intend to sell is still shown, so nothing is hidden.
      </p>
      <table>
        <thead>
          <tr><th /><th>Predicted</th><th>Observed</th></tr>
        </thead>
        <tbody>
          {OCCASIONS.map(({ profile, title, blurb }) => {
            const cell = observed?.profiles[profile]
            return (
              <tr key={profile} data-testid={`occasion-${profile}`}>
                <th scope="row">{title}<br /><small>{blurb}</small></th>
                <td><VerdictBadge verdict={envelope[profile]} /></td>
                <td data-testid={`observed-${profile}`}>
                  {!observed ? (
                    <small className="blurb">no trial yet</small>
                  ) : cell && cell.verdict ? (
                    <>
                      <VerdictBadge verdict={cell.verdict} />{' '}
                      <small className="blurb">({cell.confidence_tier})</small>
                    </>
                  ) : (
                    <small className="blurb">not looked at</small>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      {observed && <p className="blurb">{observed.scale_note}</p>}
    </section>
  )
}
```

- [ ] **Step 4: Verdict screen — start or open a trial, and pass the observed column**

In `web/src/screens/Verdict.tsx`, add `useNavigate`-based handler after `applyVariant`:

```tsx
  const startTrial = useCallback(async () => {
    if (!evaluation) return
    setError(null)
    try {
      const trial = await api.startTrial(evaluation.id)
      navigate(`/trials/${trial.id}`)
    } catch (e) {
      setError((e as Error).message)
    }
  }, [evaluation, navigate])
```

change the envelope render to pass the column:

```tsx
      <EnvelopePanel envelope={evaluation.envelope} observed={evaluation.observed} />
```

and add the trial controls under the report link:

```tsx
      <p className="no-print">
        {evaluation.trial_ids.length === 0 ? (
          <button type="button" data-testid="start-trial" onClick={startTrial}>
            Plan a kitchen trial for this
          </button>
        ) : (
          <>
            <Link to={`/trials/${evaluation.trial_ids[0]}`} data-testid="open-trial">
              Open the kitchen trial
            </Link>{' '}
            <button type="button" data-testid="start-trial" onClick={startTrial}>
              Start another trial
            </button>
          </>
        )}
      </p>
```

- [ ] **Step 5: Home screen — active trials (§10 screen 1)**

In `web/src/screens/Home.tsx`, add `TrialSummary` to the type import, a `trials` state, `api.activeTrials()` to the `Promise.all`, and this section under "Recent verdicts":

```tsx
      <h2>Trials running</h2>
      {trials.length === 0 ? (
        <p>No kitchen trial is open. Start one from a verdict.</p>
      ) : (
        <table data-testid="active-trials">
          <thead><tr><th>Trial</th><th>Batches</th><th>Recorded</th><th>Due now</th></tr></thead>
          <tbody>
            {trials.map((t) => (
              <tr key={t.id}>
                <td><Link to={`/trials/${t.id}`}>{t.status}</Link></td>
                <td>{t.batch_count}</td>
                <td>{t.observation_count}</td>
                <td>{t.due_checkpoint_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
```

- [ ] **Step 6: Report screen — the observed sections**

In `web/src/screens/Report.tsx`, add state for the trial:

```tsx
  const [trial, setTrial] = useState<TrialType | null>(null)

  useEffect(() => {
    const id = evaluation?.trial_ids[0]
    if (!id) return
    api.trial(id).then(setTrial).catch(() => setTrial(null))
  }, [evaluation])
```

pass the observed column to the envelope:

```tsx
      <EnvelopePanel envelope={evaluation.envelope} observed={evaluation.observed} />
```

and replace the `data-testid="observed"` section body:

```tsx
      <section data-testid="observed">
        <h3>What was observed</h3>
        {trial === null ? (
          <p>
            No trial has been recorded for this formulation yet. Everything above is a
            prediction from the rules and the data behind them; nothing here was measured.
          </p>
        ) : (
          <>
            <p className="blurb">
              Trial {trial.id}, {trial.status}. One person, in a kitchen, mostly
              unblinded — each group below says how much weight it carries.
            </p>
            <ObservedList
              observations={trial.batches.flatMap((b) => b.observations)}
              symptoms={trial.batches.flatMap((b) => b.symptom_entries)}
            />
          </>
        )}
      </section>
```

with the matching imports (`ObservedList`, `Trial as TrialType`).

- [ ] **Step 7: Styles**

Append to `web/src/styles.css`:

```css
/* Spec §6.5 — the checklist reads at a glance: due now, done, not yet. */
.checkpoint--due { font-weight: 600; }
.checkpoint--done { opacity: 0.6; }
.checkpoint--later { opacity: 0.8; }

[data-testid='dose-preview'] { border-left: 3px solid #888; padding-left: 0.75rem; }
[data-testid='observed-list'] blockquote {
  margin: 0.25rem 0 0.5rem 1rem;
  border-left: 2px solid #ccc;
  padding-left: 0.5rem;
}
```

- [ ] **Step 8: Typecheck, build, and run the web language lint**

Run: `cd web && npm run typecheck && npm run build`
Expected: no type errors, a `web/dist` build.

Run: `.venv/bin/pytest tests/test_web_language.py -q`
Expected: pass — no prohibited word in any new component copy.

- [ ] **Step 9: Commit**

```bash
git add web/src/screens/Trial.tsx web/src/App.tsx web/src/screens/Home.tsx web/src/screens/Verdict.tsx web/src/screens/Report.tsx web/src/components/EnvelopePanel.tsx web/src/styles.css
git commit -m "feat(web): the trial screen, and the observed column beside every prediction"
```

---

## Task 17: End-to-end — build, evaluate, trial, record, report

§13's E2E line, completed: build recipe → evaluate → apply variant → compare → **generate trial → log batch and observations → export report showing predicted and observed**. M3's spec covers the first four; this one covers the rest against the real container path.

**Files:**
- Create: `web/e2e/trial.spec.ts`

- [ ] **Step 1: Write the spec**

```ts
import { expect, test } from '@playwright/test'

/** Builds golden-fixture (a)'s vinaigrette and stops on its verdict. */
async function buildAndEvaluate(page: import('@playwright/test').Page) {
  await page.goto('/recipes/new')
  await page.getByTestId('recipe-name').fill('E2E trial vinaigrette')
  await page.getByTestId('food-picker').selectOption({ label: 'Olive oil' })
  await page.getByTestId('food-picker').selectOption({ label: 'White vinegar' })
  await page.getByTestId('amount-olive_oil').fill('100')
  await page.getByTestId('amount-white_vinegar').fill('50')
  await page.getByTestId('save-recipe').click()
  await page.getByTestId('to-formulation').click()

  await page.getByTestId('trigger-milk').check()
  await page.getByTestId('run-evaluation').click()
  await expect(page.getByTestId('headline')).toBeVisible()
}

async function startTrial(page: import('@playwright/test').Page) {
  await buildAndEvaluate(page)
  await expect(page.getByTestId('observed-immediate')).toContainText('no trial yet')
  await page.getByTestId('start-trial').click()
  await expect(page.getByTestId('trial-status')).toHaveText('planned')
}

test('the protocol is generated from the verdict, not from a blank form', async ({ page }) => {
  await startTrial(page)
  const protocol = page.getByTestId('protocol')
  await expect(protocol).toBeVisible()
  await expect(protocol).toContainText('Making it')
  await expect(page.getByTestId('protocol-notes')).toContainText('4.6')
})

test('room-temperature storage stays locked until a qualifying pH is entered', async ({ page }) => {
  await startTrial(page)
  await expect(page.getByTestId('batch-ambient')).toBeDisabled()
  await expect(page.getByTestId('ambient-gate')).toContainText('4.6')

  await page.getByTestId('batch-ph').fill('5.2')
  await page.getByTestId('batch-ph-method').selectOption('meter')
  await expect(page.getByTestId('batch-ambient')).toBeDisabled()

  await page.getByTestId('batch-ph').fill('4.1')
  await expect(page.getByTestId('batch-ambient')).toBeEnabled()
})

test('a logged observation lands in the observed column and the report', async ({ page }) => {
  await startTrial(page)

  await page.getByTestId('batch-size').fill('200')
  await page.getByTestId('batch-minutes').fill('12')
  await page.getByTestId('batch-source').fill('two Lactaid capsules opened')
  await page.getByTestId('save-batch').click()
  await expect(page.getByTestId('trial-status')).toHaveText('running')

  await page.getByTestId('observation-type').selectOption('food_texture')
  await page.getByTestId('observation-minutes').fill('240')
  await page.getByTestId('observation-score').selectOption('4')
  await page.getByTestId('observation-control').check()
  await page.getByTestId('observation-text').fill('noticeably limper than the plain leaves')
  await page.getByTestId('save-observation').click()
  await expect(page.getByTestId('observed-finding')).toContainText('suggestive')

  const url = page.url()
  const trialId = url.split('/trials/')[1]
  expect(trialId).toBeTruthy()

  await page.getByRole('link', { name: /report with these results/i }).click()
  await expect(page.getByTestId('observed')).toContainText('Findings')
  await expect(page.getByTestId('observed-packed')).toContainText('anecdote')
    .catch(async () => {
      // The tier shown is the driver's; with a control it reads suggestive.
      await expect(page.getByTestId('observed-packed')).toContainText('suggestive')
    })
})

test('a meal shows its dose against the threshold before it is saved', async ({ page }) => {
  await startTrial(page)
  await page.getByTestId('batch-size').fill('200')
  await page.getByTestId('save-batch').click()

  await page.getByTestId('symptom-food').selectOption({ label: 'Milk' })
  await page.getByTestId('symptom-amount').fill('1')
  await page.getByTestId('symptom-doses').fill('1')
  await expect(page.getByTestId('dose-preview')).toContainText('delivered', { timeout: 5000 })

  await page.getByTestId('symptom-notes').fill('no bloating this time')
  await page.getByTestId('save-symptom').click()
  await expect(page.getByTestId('observed-hypothesis')).toContainText('Milk')
})

test('stopping a trial keeps what was recorded and takes nothing more', async ({ page }) => {
  await startTrial(page)
  await page.getByTestId('batch-size').fill('200')
  await page.getByTestId('save-batch').click()
  await page.getByTestId('observation-type').selectOption('taste')
  await page.getByTestId('observation-minutes').fill('0')
  await page.getByTestId('observation-text').fill('sharper than expected')
  await page.getByTestId('save-observation').click()

  await page.getByTestId('abandon-trial').click()
  await expect(page.getByTestId('trial-closed')).toContainText('abandoned')
  await expect(page.getByTestId('batch-form')).toHaveCount(0)
  await expect(page.getByTestId('observed-list')).toContainText('sharper than expected')
})

test('the markdown export carries predicted and observed', async ({ page, request }) => {
  await startTrial(page)
  await page.getByTestId('batch-size').fill('200')
  await page.getByTestId('batch-ph').fill('3.4')
  await page.getByTestId('batch-ph-method').selectOption('meter')
  await page.getByTestId('save-batch').click()
  await page.getByTestId('observation-type').selectOption('taste')
  await page.getByTestId('observation-minutes').fill('0')
  await page.getByTestId('observation-text').fill('sharp, drinkable')
  await page.getByTestId('save-observation').click()

  const trialId = page.url().split('/trials/')[1]
  const trial = await (await request.get(`/api/v1/trials/${trialId}`)).json()
  const markdown = await (await request.get(`/api/v1/export/${trial.evaluation_id}.md`)).text()

  expect(markdown).toContain('## What was observed')
  expect(markdown).toContain('sharp, drinkable')
  expect(markdown).toContain('Measured pH of the batch: 3.4')
  expect(markdown).toContain('| Occasion | Predicted | Observed |')
})
```

- [ ] **Step 2: Run it against the built app**

Run: `cd web && npm run build && npm run e2e`
Expected: every spec passes — M3's seven plus these six.

- [ ] **Step 3: Commit**

```bash
git add web/e2e/trial.spec.ts
git commit -m "test(web): end-to-end kitchen trial, from protocol to exported report"
```

---

## Task 18: Full acceptance run

**Files:**
- Modify: `README.md`, `Makefile`

- [ ] **Step 1: Document what M4 added**

Append to `README.md`:

```markdown
## The kitchen trial

From a verdict, "Plan a kitchen trial for this" generates a protocol from that
verdict's own open questions — the rules that could not settle, and the values
that are missing. You never face a blank form.

- **Log a batch** as you make it: size, minutes, difficulty, where the enzyme went
  in the sequence, and an optional measured pH.
- **Room-temperature storage** is offered only for a batch measured below pH 4.6.
  Without that reading the schedule stays refrigerated, and the tool says why.
- **Record what you saw** — taste, using it, what it did to the food, the jar in
  storage. Tick "compared against an undressed portion" or "someone handed it to
  me" when they are true; each makes that one record a little stronger.
- **Log a meal** to capture symptoms. The dose you actually delivered is worked
  out against the evidence threshold as you type, so a null result can be read as
  an under-dose rather than as a failure.
- **Stop a trial** at any point. Everything recorded stays; the report says the
  trial was stopped rather than presenting part of a run as a whole one.

Nothing recorded at home changes a prediction. Observations are stored beside the
verdict they test and shown in a second column, and the report splits them by how
much weight they carry: your taste and usability answers as findings, uncontrolled
texture notes as observations, and symptom results as questions for a food
scientist with the dose arithmetic attached.

A measured batch pH does feed forward: later evaluations of that formulation use
it in place of the estimate, and any earlier evaluation shows the "data changed"
banner until you re-run it.

## Checks

    make test    # pytest: engine, store, API, contracts
    make lint    # ruff
    make e2e     # Playwright, against the built app
    make report EVAL=<evaluation id>   # the markdown export, from a running server
    make trial TRIAL=<trial id>        # the trial as JSON, from a running server
```

- [ ] **Step 2: Add the Makefile target**

```make
trial:
	@test -n "$(TRIAL)" || (echo 'usage: make trial TRIAL=<trial id>' && exit 1)
	curl -sf http://localhost:8000/api/v1/trials/$(TRIAL)
```

and add `trial` to the `.PHONY` line.

- [ ] **Step 3: Run everything**

Run: `.venv/bin/ruff check src tests && .venv/bin/pytest -q && cd web && npm run typecheck && npm run build && npm run e2e`
Expected: ruff clean, every test green, no type errors, a `web/dist` build, thirteen Playwright specs passing.

- [ ] **Step 4: Walk the §14 exit check by hand**

Start `make up`, open `http://localhost:8000`, and do the whole v1 loop without touching the API directly:

1. Build the vinaigrette and the creamy candidate, and read verdicts matching the KB §4m expectations — vinaigrette RED through R1, creamy AMBER, dry/separated GREEN.
2. From the vinaigrette verdict, plan a kitchen trial. Confirm the checklist names R1, R4, R7 or R8 against the items they raised, and that nothing on it is generic.
3. Try to tick room-temperature storage with no pH. Confirm it is disabled and the reason is on screen.
4. Log a batch with a measured pH of 3.4 on a meter. Confirm the trial flips to running and the ambient option unlocks.
5. Record a texture observation at 4 hours with the undressed control ticked. Confirm the verdict screen's Observed column fills for "Packed ahead" and reads `suggestive`, and that the Predicted column has not moved.
6. Log a meal with one serving of milk and one dose. Confirm the dose line appears before you save and matches what is stored afterwards.
7. Go back to the verdict you started from. Confirm the "data changed" banner names the pH, re-run, and confirm R1 now cites an observed measurement.
8. Open the report. Confirm the three headings — Findings, Observations, Hypotheses — carry the right records, that your own words appear as quotes, and that the dose arithmetic is attached to the meal.
9. Print the report to PDF. Confirm the disclaimer is on the printed page and the navigation is not.
10. Stop the trial. Confirm the forms disappear, the records stay, and the report says the trial was stopped after N records.

- [ ] **Step 5: Commit**

```bash
git add README.md Makefile
git commit -m "docs: document the kitchen trial and the honesty split"
```

---

## M4 exit criteria

Before declaring M4 — and v1 — done, all of the following must hold:

- [ ] `.venv/bin/pytest -q` passes with zero failures and zero skips.
- [ ] `.venv/bin/ruff check src tests` is clean.
- [ ] `cd web && npm run typecheck && npm run build` succeeds.
- [ ] `cd web && npm run e2e` passes all thirteen specs against the built app.
- [ ] **Every M1, M2 and M3 test still passes unchanged.** M4 modifies exactly three shipped files that anything else depends on — `engine/report.py`, `routers/evaluations.py`, `routers/export.py` — and every change to them is additive with a default. A moved golden fixture means something was not additive.
- [ ] `tests/store/test_observations.py::test_recording_an_observation_never_touches_the_evaluation` and `tests/api/test_evaluation_observed.py::test_the_observed_column_never_moves_the_headline_or_the_prediction` both pass — §13's property, at both levels.
- [ ] `tests/store/test_trial_ph.py` passes in full — §6.7's second branch is live and §13's pH resolution test is satisfied end to end.
- [ ] `tests/store/test_trials.py::test_ambient_storage_without_a_measured_ph_is_refused` and `::test_ambient_storage_below_the_line_is_permitted` pass — §13 fixture (q), through the product.
- [ ] `tests/engine/test_observations.py::test_the_default_tier_is_anecdote_and_either_flag_lifts_it` passes — §13 fixture (p), and no path produces a stronger tier than `suggestive`.
- [ ] `tests/api/test_trial_export.py::test_the_exported_trial_still_passes_the_report_lint` passes — §13's report lint over trial output, not just source.
- [ ] `tests/api/test_contracts_m4.py` passes in full: no engine module reads a clock, no request schema carries a derived value, no schema accepts a `symptom` observation, and no trial endpoint writes to an evaluation table.
- [ ] `tests/store/test_trials.py::test_the_protocol_does_not_change_when_the_evaluation_is_re_run` passes — decision #3, asserted rather than assumed.
- [ ] `docker compose up --build` reports the service healthy.
- [ ] The founder completes the hand walk in Task 18 step 4 unassisted, and exports a report she would hand to a food scientist. That is §14's exit check and the v1 definition of done.

---

## Plan self-review

**Spec coverage.** §1.3 item 8 (a trial generated from the formulation's own open risks) → Tasks 2, 5. Item 9 (observations stored `observed`, displayed beside the prediction, never overwriting it) → Tasks 1, 6, 10. Item 10 (the report separates measured from assumed and states what she could not answer) → Tasks 4, 11. §3 Workflow E, step by step: generate protocol (Tasks 2, 5), log a batch (Task 5), observe on schedule (Tasks 2, 6), results attach to the evaluation (Task 10), export both (Task 11); abandonment (Tasks 5, 9, 11). §5.3's four tables → Tasks 5, 6. §5.4's `observed` label → Task 1. §6.3's Observed column → Tasks 1, 10, 16. §6.5's mapping table, row by row → Task 2. §6.6's tiers and split → Tasks 1, 4, 11, 15. §6.7's second resolution branch → Task 7. §10's endpoint list: `POST /evaluations/{id}/trial`, `POST /trials/{id}/batches`, `POST /trial-batches/{id}/observations`, `POST /trial-batches/{id}/symptom-entries` (Task 9), plus the preview of decision #8. §10 screen 6 → Tasks 14, 15, 16; screen 1's active trials → Task 16; screen 4's Observed column → Tasks 10, 16; screen 8's observed results → Tasks 11, 16. §12 items 6 and 7 are the standing notes and the hypotheses framing (Tasks 2, 4). §13: fixture (p) → Task 1; fixture (q) → Tasks 5, 9; the pH resolution test → Task 7; the report lint over trial output → Tasks 2, 11; "recording an observation never mutates a prediction" → Tasks 6, 10; the E2E line → Task 17. §14's M4 line, item by item: protocol generation (Task 2), batch and observation capture (Tasks 5, 6, 14), storage gate (Tasks 5, 9, 14), symptom entry with live dose math (Tasks 3, 6, 9, 15), predicted-vs-observed on the verdict screen (Tasks 10, 16), report honesty split (Tasks 4, 11).

**Deliberately not in M4**, consistent with §2.2: blinded or multi-subject infrastructure (the two flags are per observation and the ceiling stays `suggestive`), any lab measurement, calibration from observed runs, cost, the solver, the LLM layer, hosted multi-user, and consumer timing guidance.

**Placeholder scan.** No stubs. Every module named in the file structure is written out in the task that creates it, every test file is written rather than described, and the two "no code change" tasks (7 and 12) are tests only and say so. `_score_for` in Task 11 falls back to 1 rather than raising, which is a display fallback for an impossible case (a driving observation always has a score, by construction in `observed_envelope`) — deliberate, not a TODO.

**Type consistency.** `ObservationRecord` is the single carrier of an observation from `store/observations.list_for_batch` through `protocol.satisfied_checkpoint_ids`, `observations.observed_envelope`, the router's `_observation`, and the report's classifier; nothing reshapes it in between. `ConfidenceTier` and `ambient_storage_allowed` come from M1's `trial_rules.py` and are never re-implemented. `Protocol.to_json`/`from_json` are the only serialization path for a protocol, and `SymptomDoseMath.as_dict` the only one for the dose math — the preview and the stored entry are the same dict, which is what Task 6's `test_the_preview_matches_what_a_write_would_store_and_writes_nothing` asserts. `ValidationRejection` remains the one refusal type and still maps to 422 in M2's single handler. `trials.py` names its statuses through module constants (`PLANNED`, `RUNNING`, `COMPLETE`, `ABANDONED`), so no string literal decides a state machine transition.

**Known cross-task dependencies.** Task 1 precedes Task 2 (which imports `ObservationRecord`), Task 4, and Task 10. Task 2 precedes Task 5, which freezes what it generates. Task 3 precedes Task 6, which freezes what it computes. Tasks 5 and 6 are mutually referential by design — `store/trials.get` imports `store/observations` at call time while `store/observations` imports `store/trials` at module level — so write Task 5's module, then Task 6's, then run both suites. Task 7 depends on 5 and 6 and changes no production code. Task 8 precedes Tasks 9, 10 and 11. Task 12 should be run last of the Python tasks, because it lints the files the others create. Task 13 precedes every other web task. Task 16 depends on 14 and 15. Task 17 depends on all of them and on a `web/dist` build.

**Where this plan is most likely to be wrong.** Four places, in order:

1. **The 1–5 texture scale and its verdict mapping** (decision #9). It is invented here to make §6.3's Observed column computable, and the founder is the one scoring against it. If she reads "3 — clearly softer" as already unacceptable, the mapping should move, not the wording. One dict in `engine/observations.py`.
2. **Which trial fills the Observed column when there is more than one** (Task 10: the newest with any observation). A second trial on the same evaluation is a real case — she remakes the batch — and "newest wins" silently hides the first one's readings on the verdict screen, though both stay readable on their own screens and in `trial_ids`. The other defensible reading is to merge every trial's observations into one envelope, which would mix two different batches into one cell.
3. **Refusing late observations on an abandoned trial** (decision #12). It makes "abandoned after N records" true, and it will annoy her the first time she remembers something the next morning. The escape hatch is a new trial, which is one click, but it is an extra trial row for what she thinks of as the same experiment.
4. **The dose math's servings-only basis** (Task 3). Real logging is "a bowl of pasta", "a glass of milk", and the engine refuses to convert those because the seeded loads are per-serving figures. The refusal is honest and it puts the conversion in her head. If that turns out to be the thing that stops her logging meals, the fix is per-food serving sizes in the catalogue — a seed change, not an engine change.






