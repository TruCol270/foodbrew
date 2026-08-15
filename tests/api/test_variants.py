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
