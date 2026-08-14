"""Spec §4: an evaluation is a frozen record. These are the three ways that can
break in a system with a database, tested end to end through HTTP.
"""


def _evaluate(client, formulation_id):
    return client.post(f"/api/v1/formulations/{formulation_id}/evaluate").json()


def test_re_evaluating_unchanged_inputs_produces_an_identical_verdict(client, vinaigrette):
    first = _evaluate(client, vinaigrette["formulation_id"])
    second = _evaluate(client, vinaigrette["formulation_id"])
    assert first["id"] != second["id"]
    assert first["headline"] == second["headline"]
    assert [f["message"] for f in first["findings"]] == [
        f["message"] for f in second["findings"]
    ]


def test_the_stored_snapshot_is_byte_identical_across_two_runs(client, vinaigrette, conn):
    first = _evaluate(client, vinaigrette["formulation_id"])
    second = _evaluate(client, vinaigrette["formulation_id"])
    rows = {
        r["id"]: r["input_snapshot_json"]
        for r in conn.execute("SELECT id, input_snapshot_json FROM evaluation")
    }
    assert rows[first["id"]] == rows[second["id"]]


def test_editing_an_enzyme_changes_the_next_run_but_not_the_stored_one(client, vinaigrette, conn):
    before = _evaluate(client, vinaigrette["formulation_id"])
    assert before["headline"] == "RED"

    # A supplier confirms a shelf-stable floor below the recipe's pH 3.0, which
    # is exactly the answer §15 question 1 exists to collect.
    conn.execute(
        "UPDATE enzyme SET ph_shelf_stable_min = 2.5,"
        " ph_shelf_stable_min_status = 'confirmed',"
        " ph_shelf_stable_min_source = 'supplier spec' WHERE id = 'lactase_fungal_acid'"
    )
    conn.commit()

    after = _evaluate(client, vinaigrette["formulation_id"])
    reread = client.get(f"/api/v1/evaluations/{before['id']}").json()

    assert after["headline"] != before["headline"]
    assert reread["headline"] == before["headline"]
    assert [f["message"] for f in reread["findings"]] == [
        f["message"] for f in before["findings"]
    ]


def test_a_stored_evaluation_survives_editing_the_formulation_itself(client, vinaigrette, conn):
    before = _evaluate(client, vinaigrette["formulation_id"])
    conn.execute(
        "UPDATE formulation SET measured_ph = 6.0 WHERE id = ?",
        (vinaigrette["formulation_id"],),
    )
    conn.commit()
    reread = client.get(f"/api/v1/evaluations/{before['id']}").json()
    snapshot = client.get(f"/api/v1/evaluations/{before['id']}/snapshot").json()
    assert reread["headline"] == before["headline"]
    assert snapshot["formulation"]["measured_ph"]["value"] == 3.0
