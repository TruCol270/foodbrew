"""Spec §10 screen 8 as data — everything the printable page needs.

The screen used to render less than the markdown export because it consumed the
evaluation payload, which carries no recipe. This endpoint serves the same
assembly the export renders (plan decision #8), so the two cannot drift; the
contract test in tests/api/test_report_endpoint.py is what proves it.
"""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from foodbrew.api.deps import get_conn
from foodbrew.api.routers.export import report_input
from foodbrew.api.schemas import (
    AllergenDeclarationOut,
    AllergenEntryOut,
    BatchRecordOut,
    FormulaLineOut,
    FormulaOut,
    ProcessLineOut,
    ReportOut,
    TrackedOut,
)
from foodbrew.engine.allergens import ALLERGEN_TEXT, Allergen, declare
from foodbrew.engine.formula import build as build_formula
from foodbrew.engine.formula import process_lines

router = APIRouter(tags=["report"])


def _allergen_names(food) -> list[str]:
    return [ALLERGEN_TEXT[Allergen(a)] for a in getattr(food, "allergens", ()) or ()]


@router.get("/evaluations/{evaluation_id}/report", response_model=ReportOut)
def get_report(evaluation_id: str, conn: sqlite3.Connection = Depends(get_conn)):
    data = report_input(conn, evaluation_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No evaluation '{evaluation_id}'.")

    ctx = data.context
    form = ctx.formulation
    formula = build_formula(form.recipe, ctx.foods)
    declaration = declare([i.food_id for i in form.recipe], ctx.foods)

    return ReportOut(
        evaluation_id=data.evaluation_id, recipe_id=data.recipe_id,
        recipe_name=data.recipe_name, created_at=data.created_at,
        engine_version=data.engine_version, headline=data.headline, stale=data.stale,
        formula=FormulaOut(
            lines=[
                FormulaLineOut(
                    position=position, food_id=line.food_id, food_name=line.food_name,
                    amount_g=line.amount_g, percent_of_total=line.percent_of_total,
                    ph=TrackedOut.of(line.ph),
                    water_content_pct=TrackedOut.of(line.water_content_pct),
                    allergens=_allergen_names(ctx.foods.get(line.food_id)),
                )
                for position, line in enumerate(formula.lines, start=1)
            ],
            total_g=formula.total_g,
            printed_percent_total=formula.printed_percent_total,
        ),
        process=[
            ProcessLineOut(
                order=step.order, label=step.label, is_heat=step.is_heat,
                is_enzyme_addition_point=step.is_enzyme_addition_point,
            )
            for step in process_lines(form.process_steps, form.enzyme_addition_index)
        ],
        allergens=AllergenDeclarationOut(
            entries=[
                AllergenEntryOut(
                    allergen=str(e.allergen), text=e.text,
                    from_food_names=list(e.from_food_names),
                )
                for e in declaration.entries
            ],
            unrecorded_food_names=list(declaration.unrecorded_food_names),
        ),
        batches=[
            BatchRecordOut(
                made_at=b.made_at, batch_size_g=b.batch_size_g, measured_ph=b.measured_ph,
                ph_method=b.ph_method, make_minutes=b.make_minutes,
                difficulty_score=b.difficulty_score,
                enzyme_source_note=b.enzyme_source_note,
                enzyme_addition_step=b.enzyme_addition_step,
                storage_mode=b.storage_mode, process_notes=b.process_notes,
            )
            for b in data.batches
        ],
        serving_size_g=form.serving_size_g,
        measured_ph=TrackedOut.of(form.measured_ph),
        dwell_profile=form.dwell_profile.value if form.dwell_profile else None,
        format=form.format.value,
        trigger_food_names=[
            ctx.foods[i].name if i in ctx.foods else i for i in form.target_trigger_food_ids
        ],
        application_food_names=[
            ctx.foods[i].name if i in ctx.foods else i for i in form.application_food_ids
        ],
    )
