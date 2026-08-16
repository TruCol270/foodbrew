"""Decision #8 — one assembly, two renderings, and the proof they agree."""

import pytest


@pytest.fixture
def evaluated(client, vinaigrette):
    return client.post(
        f"/api/v1/formulations/{vinaigrette['formulation_id']}/evaluate"
    ).json()


def test_the_report_endpoint_returns_the_formula_with_percentages(client, evaluated):
    payload = client.get(f"/api/v1/evaluations/{evaluated['id']}/report").json()
    percents = [line["percent_of_total"] for line in payload["formula"]["lines"]]
    assert sum(p for p in percents if p) == pytest.approx(100.0, abs=0.02)
    assert payload["formula"]["total_g"] == 150.0
    assert payload["recipe_name"] == "vinaigrette"


def test_the_lines_are_in_order_of_addition(client, evaluated):
    payload = client.get(f"/api/v1/evaluations/{evaluated['id']}/report").json()
    positions = [line["position"] for line in payload["formula"]["lines"]]
    assert positions == sorted(positions)


def test_the_declaration_names_the_gap_not_a_clearance(client, evaluated):
    payload = client.get(f"/api/v1/evaluations/{evaluated['id']}/report").json()
    assert payload["allergens"]["unrecorded_food_names"]


def test_a_batch_reaches_both_renderings(client, evaluated):
    trial = client.post(f"/api/v1/evaluations/{evaluated['id']}/trial").json()
    client.post(
        f"/api/v1/trials/{trial['id']}/batches",
        json={"batch_size_g": 200.0, "measured_ph": 3.4, "ph_method": "meter",
              "make_minutes": 12, "difficulty_score": 2,
              "enzyme_source_note": "two Lactaid capsules"},
    )
    payload = client.get(f"/api/v1/evaluations/{evaluated['id']}/report").json()
    markdown = client.get(f"/api/v1/export/{evaluated['id']}.md").text

    assert len(payload["batches"]) == 1
    assert payload["batches"][0]["make_minutes"] == 12
    assert "## Batch records" in markdown
    assert "two Lactaid capsules" in markdown


def test_the_two_renderings_agree_on_every_shared_number(client, evaluated):
    """The contract of decision #8: the screen and the file are one assembly."""
    payload = client.get(f"/api/v1/evaluations/{evaluated['id']}/report").json()
    markdown = client.get(f"/api/v1/export/{evaluated['id']}.md").text

    assert payload["recipe_name"] in markdown
    assert payload["engine_version"] in markdown
    assert payload["evaluation_id"] in markdown
    for line in payload["formula"]["lines"]:
        assert line["food_name"] in markdown
        assert f"{line['amount_g']:g}" in markdown
    assert f"{payload['formula']['total_g']:g}" in markdown


def test_a_missing_evaluation_is_a_404(client):
    assert client.get("/api/v1/evaluations/nope/report").status_code == 404
