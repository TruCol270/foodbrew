"""Formulation persistence, and the one place an EvalContext is built for real."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence

from foodbrew.engine import ValidationRejection
from foodbrew.engine.types import (
    DwellProfile,
    EvalContext,
    Format,
    Formulation,
    Phase,
    ProcessStep,
    SelectedEnzyme,
    Tracked,
    TruthLabel,
)
from foodbrew.store.clock import now_iso
from foodbrew.store.ids import new_id
from foodbrew.store.recipes import ingredients_for
from foodbrew.store.reference import load_catalog


def _validate(conn, *, recipe_id, enzymes, trigger_food_ids, application_food_ids, format):
    if conn.execute("SELECT 1 FROM recipe WHERE id = ?", (recipe_id,)).fetchone() is None:
        raise ValidationRejection(f"Unknown recipe '{recipe_id}'.")
    if not ingredients_for(conn, recipe_id):
        raise ValidationRejection("Add at least one ingredient to this recipe.")
    # Spec §6.2 R14 — the degenerate case the engine refuses to evaluate at all.
    if not enzymes and not trigger_food_ids:
        raise ValidationRejection(
            "Select at least one trigger food or enzyme before evaluating."
        )
    try:
        Format(format)
    except ValueError as exc:
        raise ValidationRejection(f"Unknown format '{format}'.") from exc

    known_enzymes = {r["id"] for r in conn.execute("SELECT id FROM enzyme")}
    for selected in enzymes:
        if selected["enzyme_id"] not in known_enzymes:
            raise ValidationRejection(f"Unknown enzyme '{selected['enzyme_id']}'.")
        try:
            Phase(selected["phase"])
        except ValueError as exc:
            raise ValidationRejection(f"Unknown phase '{selected['phase']}'.") from exc

    known_foods = {r["id"] for r in conn.execute("SELECT id FROM food")}
    for food_id in (*trigger_food_ids, *application_food_ids):
        if food_id not in known_foods:
            raise ValidationRejection(f"Unknown food '{food_id}'.")


def create(
    conn: sqlite3.Connection,
    *,
    recipe_id: str,
    format: str,
    target_trigger_food_ids: Sequence[str],
    application_food_ids: Sequence[str],
    dwell_profile: str | None,
    enzymes: Sequence[dict],
    serving_size_g: float | None,
    measured_ph: float | None,
    process_steps: Sequence[dict],
    enzyme_addition_index: int | None,
    parent_formulation_id: str | None,
) -> str:
    _validate(
        conn, recipe_id=recipe_id, enzymes=enzymes,
        trigger_food_ids=target_trigger_food_ids,
        application_food_ids=application_food_ids, format=format,
    )
    formulation_id = new_id()
    conn.execute(
        "INSERT INTO formulation (id, recipe_id, format, target_trigger_food_ids_json,"
        " application_food_ids_json, dwell_profile, enzyme_selection_json, serving_size_g,"
        " measured_ph, measured_ph_status, measured_ph_source, process_steps_json,"
        " enzyme_addition_index, parent_formulation_id, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            formulation_id, recipe_id, format,
            json.dumps(list(target_trigger_food_ids)),
            json.dumps(list(application_food_ids)),
            dwell_profile,
            json.dumps(list(enzymes)),
            serving_size_g,
            measured_ph,
            TruthLabel.USER_PROVIDED.value if measured_ph is not None
            else TruthLabel.UNCONFIRMED.value,
            "measured by founder" if measured_ph is not None else "",
            json.dumps(list(process_steps)),
            enzyme_addition_index,
            parent_formulation_id,
            now_iso(),
        ),
    )
    conn.commit()
    return formulation_id


def get(conn: sqlite3.Connection, formulation_id: str) -> Formulation | None:
    row = conn.execute(
        "SELECT * FROM formulation WHERE id = ?", (formulation_id,)
    ).fetchone()
    if row is None:
        return None
    return Formulation(
        id=row["id"],
        format=Format(row["format"]),
        recipe=ingredients_for(conn, row["recipe_id"]),
        enzymes=tuple(
            SelectedEnzyme(
                enzyme_id=s["enzyme_id"], dose=s.get("dose"),
                phase=Phase(s.get("phase", "dry")),
                encapsulated=bool(s.get("encapsulated", False)),
                source_choice=s.get("source_choice", ""),
            )
            for s in json.loads(row["enzyme_selection_json"])
        ),
        target_trigger_food_ids=tuple(json.loads(row["target_trigger_food_ids_json"])),
        application_food_ids=tuple(json.loads(row["application_food_ids_json"])),
        dwell_profile=DwellProfile(row["dwell_profile"]) if row["dwell_profile"] else None,
        serving_size_g=row["serving_size_g"],
        measured_ph=Tracked(
            row["measured_ph"],
            TruthLabel(row["measured_ph_status"]),
            row["measured_ph_source"],
        ),
        process_steps=tuple(
            ProcessStep(int(s["order"]), s["label"], bool(s.get("is_heat", False)))
            for s in json.loads(row["process_steps_json"])
        ),
        enzyme_addition_index=row["enzyme_addition_index"],
        parent_formulation_id=row["parent_formulation_id"],
    )


def recipe_id_for(conn, formulation_id: str) -> str | None:
    row = conn.execute(
        "SELECT recipe_id FROM formulation WHERE id = ?", (formulation_id,)
    ).fetchone()
    return row["recipe_id"] if row else None


def latest_trial_ph(conn, formulation_id: str) -> Tracked | None:
    """Spec §6.7 step 2 — the most recent trial batch's measured pH, labelled observed.

    M4 writes these rows. Reading them now costs nothing against an empty table
    and means M4 adds a writer rather than reworking hydration.
    """
    row = conn.execute(
        "SELECT b.measured_ph AS ph FROM trial_batch b"
        " JOIN trial t ON t.id = b.trial_id"
        " JOIN evaluation e ON e.id = t.evaluation_id"
        " WHERE e.formulation_id = ? AND b.measured_ph IS NOT NULL"
        " ORDER BY b.made_at DESC LIMIT 1",
        (formulation_id,),
    ).fetchone()
    if row is None:
        return None
    return Tracked(float(row["ph"]), TruthLabel.OBSERVED, "trial batch measurement")


def hydrate_context(conn: sqlite3.Connection, formulation_id: str) -> EvalContext:
    """Build the engine's input from the database. The engine never does this itself."""
    formulation = get(conn, formulation_id)
    if formulation is None:
        raise ValidationRejection(f"Unknown formulation '{formulation_id}'.")
    catalog = load_catalog(conn)
    return EvalContext(
        formulation=formulation,
        enzymes=catalog.enzymes,
        foods=catalog.foods,
        substrates=catalog.substrates,
        gi_regions=catalog.gi_regions,
        latest_trial_ph=latest_trial_ph(conn, formulation_id),
    )
