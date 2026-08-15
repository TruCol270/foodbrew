"""Spec §10's export endpoint and §13's report lint, end to end."""

from foodbrew.engine.language import contains_prohibited
from foodbrew.engine.report import DISCLAIMER


def _evaluate(client, formulation_id):
    return client.post(f"/api/v1/formulations/{formulation_id}/evaluate").json()


def test_the_export_is_markdown_with_the_disclaimer_last(client, vinaigrette):
    evaluation = _evaluate(client, vinaigrette["formulation_id"])
    response = client.get(f"/api/v1/export/{evaluation['id']}.md")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert response.text.rstrip().endswith(DISCLAIMER)


def test_the_export_carries_no_prohibited_word(client, vinaigrette):
    evaluation = _evaluate(client, vinaigrette["formulation_id"])
    body = client.get(f"/api/v1/export/{evaluation['id']}.md").text
    assert contains_prohibited(body) == ()


def test_the_export_names_the_recipe_and_the_engine_version(client, vinaigrette):
    evaluation = _evaluate(client, vinaigrette["formulation_id"])
    body = client.get(f"/api/v1/export/{evaluation['id']}.md").text
    assert "# Formulation report — vinaigrette" in body
    assert evaluation["engine_version"] in body
    assert evaluation["id"] in body


def test_the_export_reports_the_blockers_and_the_open_questions(client, vinaigrette):
    evaluation = _evaluate(client, vinaigrette["formulation_id"])
    body = client.get(f"/api/v1/export/{evaluation['id']}.md").text
    assert "### Blockers" in body
    assert "R1 — In-jar pH survival" in body
    assert "## Open questions" in body


def test_the_export_says_no_trial_has_been_recorded(client, vinaigrette):
    evaluation = _evaluate(client, vinaigrette["formulation_id"])
    body = client.get(f"/api/v1/export/{evaluation['id']}.md").text
    assert "No trial has been recorded for this formulation yet." in body


def test_a_stale_export_says_so(client, vinaigrette, conn):
    evaluation = _evaluate(client, vinaigrette["formulation_id"])
    conn.execute("UPDATE enzyme SET notes = 'x' WHERE id = 'lactase_fungal_acid'")
    conn.commit()
    body = client.get(f"/api/v1/export/{evaluation['id']}.md").text
    assert "has changed since it ran" in body


def test_an_unknown_evaluation_is_a_404(client):
    assert client.get("/api/v1/export/nope.md").status_code == 404
