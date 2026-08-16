"""§2.3 end to end for a structured field: propose, approve, re-evaluate."""

def test_a_structured_proposal_is_accepted_and_validated(client):
    good = client.post(
        "/api/v1/proposals",
        json={"table_name": "enzyme", "record_id": "inulinase",
              "field": "degrades_structural_json",
              "proposed_value": '[{"structural_class": "pectin_cellulose", "tier": "gradual"}]',
              "source_citation": "Supplier spec sheet, 2026-08"},
    )
    assert good.status_code == 201, good.text

    bad = client.post(
        "/api/v1/proposals",
        json={"table_name": "enzyme", "record_id": "inulinase",
              "field": "degrades_structural_json",
              "proposed_value": '[{"structural_class": "pectin_cellulose", "tier": "quick"}]',
              "source_citation": "a guess"},
    )
    assert bad.status_code == 422
    assert "gradual" in bad.json()["detail"]


def test_approving_it_writes_the_value_and_keeps_the_citation(client, conn):
    created = client.post(
        "/api/v1/proposals",
        json={"table_name": "enzyme", "record_id": "inulinase",
              "field": "degrades_structural_json",
              "proposed_value": '[{"structural_class": "pectin_cellulose", "tier": "gradual"}]',
              "source_citation": "Supplier spec sheet, 2026-08"},
    ).json()

    approved = client.post(f"/api/v1/proposals/{created['id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    enzyme = next(
        e for e in client.get("/api/v1/enzymes").json() if e["id"] == "inulinase"
    )
    assert {"structural_class": "pectin_cellulose", "tier": "gradual"} in enzyme[
        "degrades_structural"
    ]


def test_a_direct_structured_edit_is_labelled_as_the_founder_not_as_confirmed(client, conn):
    client.put(
        "/api/v1/enzymes/inulinase/structured/degrades_structural_json",
        json={"value": [{"structural_class": "pectin_cellulose", "tier": "gradual"}]},
    )
    row = conn.execute(
        "SELECT * FROM audit_event WHERE entity = 'enzyme:inulinase' ORDER BY id DESC"
    ).fetchone()
    assert row is not None


def test_the_scalar_proposal_path_is_unchanged(client):
    created = client.post(
        "/api/v1/proposals",
        json={"table_name": "enzyme", "record_id": "lactase_fungal_acid",
              "field": "ph_shelf_stable_min", "proposed_value": "3.2",
              "source_citation": "Amano technical data sheet"},
    ).json()
    client.post(f"/api/v1/proposals/{created['id']}/approve")
    enzyme = next(
        e for e in client.get("/api/v1/enzymes").json() if e["id"] == "lactase_fungal_acid"
    )
    assert enzyme["ph_shelf_stable_min"]["value"] == 3.2
    assert enzyme["ph_shelf_stable_min"]["status"] == "confirmed"
