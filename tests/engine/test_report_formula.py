"""Package A — the report in the shape a food scientist reads."""

import pytest

from foodbrew.engine.format_search import recommend_format
from foodbrew.engine.language import contains_prohibited
from foodbrew.engine.report import ReportBatch, ReportInput, render_markdown
from foodbrew.engine.rules import r15_applied_texture
from foodbrew.engine.types import Phase


@pytest.fixture
def report(make_ctx):
    def _build(**kw):
        ctx = make_ctx(
            enzymes=(("lactase_fungal_acid", 9000.0, Phase.WET),),
            recipe=(("olive_oil", 150.0), ("white_vinegar", 50.0)),
            trigger_foods=("milk",),
            application_foods=("romaine",),
            measured_ph=3.0,
            process_steps=kw.pop("process_steps", ()),
            enzyme_addition_index=kw.pop("enzyme_addition_index", None),
        )
        return render_markdown(
            ReportInput(
                evaluation_id="e1", created_at="2026-08-16T09:00:00+00:00",
                engine_version="1.0.0", recipe_name="vinaigrette", headline="RED",
                context=ctx, findings=(), envelope=r15_applied_texture.envelope(ctx),
                recommendation=recommend_format(ctx), recipe_id="r-001", **kw,
            )
        )

    return _build


def test_the_identity_block_names_the_product_recipe_and_basis(report):
    body = report()
    assert "## Product and formula identity" in body
    assert "| Product | vinaigrette |" in body
    assert "| Recipe id | r-001 |" in body
    assert "percent of total batch weight (sums to 100)" in body


def test_the_formula_table_carries_percent_grams_and_a_total(report):
    body = report()
    assert "| # | Ingredient | % of total | Grams | pH | Water content | Allergens |" in body
    assert "| 1 | Olive oil | 75 | 150 |" in body
    assert "| 2 | White vinegar | 25 | 50 |" in body
    assert "| | **Total** | **100** | **200** | | | |" in body


def test_the_process_table_marks_heat_and_the_enzyme_point(report):
    body = report(
        process_steps=(
            __import__("foodbrew.engine.types", fromlist=["ProcessStep"]).ProcessStep(
                1, "warm the base", True
            ),
            __import__("foodbrew.engine.types", fromlist=["ProcessStep"]).ProcessStep(
                2, "whisk in the enzyme"
            ),
        ),
        enzyme_addition_index=2,
    )
    assert "## Process" in body
    assert "| 1 | warm the base | yes | no |" in body
    assert "| 2 | whisk in the enzyme | no | yes |" in body


def test_unmeasured_parameters_are_listed_rather_than_omitted(report):
    body = report()
    assert "| Water activity | not measured |" in body
    assert "| Nutrition | not calculated |" in body


def test_an_ingredient_with_no_allergen_record_is_named_as_a_gap(report):
    body = report()
    assert "## Allergens" in body
    assert "not recorded for this ingredient" in body
    assert "Olive oil" in body


def test_batch_records_print_every_captured_parameter(report):
    body = report(
        batches=(
            ReportBatch(
                made_at="2026-08-16T10:30:00+00:00", batch_size_g=200.0, measured_ph=3.4,
                ph_method="meter", make_minutes=12, difficulty_score=2,
                enzyme_source_note="two Lactaid capsules", enzyme_addition_step=2,
                storage_mode="refrigerated", process_notes="split when I rushed it",
            ),
        )
    )
    assert "## Batch records" in body
    assert (
        "| 2026-08-16 10:30 | 200 g | 3.4 (meter) | 12 | 2 of 5 | 2 "
        "| two Lactaid capsules | refrigerated |"
    ) in body
    assert "> split when I rushed it" in body


def test_no_batch_means_no_batch_section(report):
    assert "## Batch records" not in report()


def test_the_reformatted_report_still_passes_the_language_lint(report):
    body = report(
        batches=(
            ReportBatch(
                made_at="2026-08-16T10:30:00+00:00", batch_size_g=200.0, measured_ph=4.1,
                ph_method="strip", make_minutes=9, difficulty_score=1,
                enzyme_source_note="Beano", enzyme_addition_step=1, storage_mode="ambient",
            ),
        )
    )
    assert contains_prohibited(body) == ()
