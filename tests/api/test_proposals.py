"""Spec §2.3 over HTTP, and the only route to a confirmed value."""

PROPOSAL = {
    "table_name": "enzyme",
    "record_id": "lactase_fungal_acid",
    "field": "ph_shelf_stable_min",
    "proposed_value": "3.0",
    "source_citation": "Amano technical datasheet, retrieved 2026-08-14",
}


def _enzyme(client):
    return next(
        e for e in client.get("/api/v1/enzymes").json() if e["id"] == "lactase_fungal_acid"
    )


def test_a_proposal_starts_pending(client):
    created = client.post("/api/v1/proposals", json=PROPOSAL).json()
    assert created["status"] == "pending"
    pending = client.get("/api/v1/proposals", params={"status": "pending"}).json()
    assert [p["id"] for p in pending] == [created["id"]]


def test_a_proposal_without_a_citation_is_refused(client):
    response = client.post("/api/v1/proposals", json={**PROPOSAL, "source_citation": ""})
    assert response.status_code == 422


def test_approving_confirms_the_value_and_records_the_citation(client):
    created = client.post("/api/v1/proposals", json=PROPOSAL).json()
    assert client.post(f"/api/v1/proposals/{created['id']}/approve").json()["status"] == "approved"

    field = _enzyme(client)["ph_shelf_stable_min"]
    assert (field["value"], field["status"]) == (3.0, "confirmed")
    assert field["source"] == PROPOSAL["source_citation"]


def test_rejecting_changes_nothing(client):
    before = _enzyme(client)["ph_shelf_stable_min"]
    created = client.post("/api/v1/proposals", json=PROPOSAL).json()
    client.post(f"/api/v1/proposals/{created['id']}/reject")
    assert _enzyme(client)["ph_shelf_stable_min"] == before


def test_a_decided_proposal_cannot_be_decided_again(client):
    created = client.post("/api/v1/proposals", json=PROPOSAL).json()
    client.post(f"/api/v1/proposals/{created['id']}/approve")
    response = client.post(f"/api/v1/proposals/{created['id']}/reject")
    assert response.status_code == 422
    assert "already approved" in response.json()["detail"]


def test_approving_a_temperature_range_promotes_R12_on_the_next_run(client, vinaigrette):
    """Spec §13 fixture (h2), through the product."""
    before = client.post(
        f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
    ).json()
    assert any(f["rule_id"] == "R12" for f in before["advisories"])

    for field, value in (("temp_min_c", "30"), ("temp_max_c", "45")):
        created = client.post(
            "/api/v1/proposals",
            json={**PROPOSAL, "field": field, "proposed_value": value},
        ).json()
        client.post(f"/api/v1/proposals/{created['id']}/approve")

    after = client.post(
        f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
    ).json()
    r12 = [f for f in after["findings"] if f["rule_id"] == "R12"]
    assert r12 and not any(f["advisory"] for f in r12)
