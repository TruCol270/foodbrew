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
