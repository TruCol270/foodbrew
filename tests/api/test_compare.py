"""Workflow B over HTTP."""


def _evaluate(client, formulation_id):
    return client.post(f"/api/v1/formulations/{formulation_id}/evaluate").json()


def _two_variants(client, vinaigrette):
    original = _evaluate(client, vinaigrette["formulation_id"])
    dry = next(
        s for s in original["suggestions"]
        if s["suggestion_type"] == "format_change" and "dry sachet" in s["description"]
    )
    applied = client.post(
        f"/api/v1/evaluations/{original['id']}/apply-variant",
        json={"suggestion_id": dry["id"]},
    ).json()
    return original, applied


def test_comparing_two_variants_shows_the_headline_moving(client, vinaigrette):
    original, applied = _two_variants(client, vinaigrette)
    payload = client.get(
        "/api/v1/compare", params={"ids": [original["id"], applied["id"]]}
    ).json()

    assert [c["evaluation_id"] for c in payload["columns"]] == [original["id"], applied["id"]]
    headline = next(r for r in payload["rows"] if r["key"] == "headline")
    assert headline["changed"]
    assert [c["text"] for c in headline["cells"]] == [original["headline"], applied["headline"]]


def test_the_format_row_names_both_formats(client, vinaigrette):
    original, applied = _two_variants(client, vinaigrette)
    payload = client.get(
        "/api/v1/compare", params={"ids": [original["id"], applied["id"]]}
    ).json()
    row = next(r for r in payload["rows"] if r["key"] == "format")
    assert [c["text"] for c in row["cells"]] == ["premixed_wet", "dry_sachet"]


def test_a_rule_that_only_fires_on_one_side_reads_as_absent(client, vinaigrette):
    original, applied = _two_variants(client, vinaigrette)
    payload = client.get(
        "/api/v1/compare", params={"ids": [original["id"], applied["id"]]}
    ).json()
    r1_rows = [r for r in payload["rows"] if r["key"].startswith("R1:")]
    assert r1_rows
    assert any(not row["cells"][1]["present"] for row in r1_rows)


def test_comparing_one_evaluation_is_refused(client, vinaigrette):
    original = _evaluate(client, vinaigrette["formulation_id"])
    response = client.get("/api/v1/compare", params={"ids": [original["id"]]})
    assert response.status_code == 422
    assert "at least two" in response.json()["detail"]


def test_an_unknown_evaluation_is_a_404(client, vinaigrette):
    original = _evaluate(client, vinaigrette["formulation_id"])
    response = client.get("/api/v1/compare", params={"ids": [original["id"], "nope"]})
    assert response.status_code == 404


def test_more_than_six_columns_is_refused(client, vinaigrette):
    ids = [_evaluate(client, vinaigrette["formulation_id"])["id"] for _ in range(7)]
    assert client.get("/api/v1/compare", params={"ids": ids}).status_code == 422
