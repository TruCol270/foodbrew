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
