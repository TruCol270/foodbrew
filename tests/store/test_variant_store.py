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
