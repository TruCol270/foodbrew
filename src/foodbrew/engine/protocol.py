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
