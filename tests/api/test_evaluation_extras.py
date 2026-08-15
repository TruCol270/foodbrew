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
