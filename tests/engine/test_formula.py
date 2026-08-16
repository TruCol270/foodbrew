"""Decisions #6 and #7 — the formula arithmetic, and what it refuses to guess."""

from foodbrew.engine.formula import build, process_lines
from foodbrew.engine.types import ProcessStep, RecipeIngredient, TruthLabel


def test_percent_is_of_the_total_and_sums_to_one_hundred(seed):
    formula = build(
        [RecipeIngredient("olive_oil", 150.0, 1), RecipeIngredient("white_vinegar", 50.0, 2)],
        seed.foods,
    )
    assert formula.total_g == 200.0
    assert [line.percent_of_total for line in formula.lines] == [75.0, 25.0]
    assert formula.printed_percent_total == 100.0


def test_lines_come_back_in_order_of_addition_not_input_order(seed):
    formula = build(
        [RecipeIngredient("white_vinegar", 50.0, 2), RecipeIngredient("olive_oil", 150.0, 1)],
        seed.foods,
    )
    assert [line.food_id for line in formula.lines] == ["olive_oil", "white_vinegar"]


def test_ties_in_order_break_deterministically_on_id(seed):
    first = build(
        [RecipeIngredient("white_vinegar", 50.0, 0), RecipeIngredient("olive_oil", 50.0, 0)],
        seed.foods,
    )
    second = build(
        [RecipeIngredient("olive_oil", 50.0, 0), RecipeIngredient("white_vinegar", 50.0, 0)],
        seed.foods,
    )
    assert [line.food_id for line in first.lines] == [line.food_id for line in second.lines]


def test_a_zero_total_reports_no_percentage_rather_than_zero(seed):
    formula = build([RecipeIngredient("olive_oil", 0.0, 1)], seed.foods)
    assert formula.total_g == 0
    assert formula.lines[0].percent_of_total is None
    assert formula.printed_percent_total is None


def test_rounding_is_reported_so_a_99_99_total_is_visible(seed):
    formula = build(
        [
            RecipeIngredient("olive_oil", 100.0, 1),
            RecipeIngredient("white_vinegar", 100.0, 2),
            RecipeIngredient("lemon_juice", 100.0, 3),
        ],
        seed.foods,
    )
    assert [line.percent_of_total for line in formula.lines] == [33.33, 33.33, 33.33]
    assert formula.printed_percent_total == 99.99


def test_an_unknown_food_keeps_its_line_and_reports_unconfirmed_values(seed):
    formula = build([RecipeIngredient("ghost", 10.0, 1)], seed.foods)
    assert formula.lines[0].food_name == "ghost"
    assert formula.lines[0].ph.status is TruthLabel.UNCONFIRMED


def test_the_empty_recipe_is_empty_rather_than_a_zero_row():
    formula = build([], {})
    assert formula.is_empty
    assert formula.total_g == 0


def test_process_lines_are_ordered_and_flag_the_enzyme_point():
    lines = process_lines(
        [ProcessStep(2, "whisk in oil"), ProcessStep(1, "combine acids", is_heat=True)],
        enzyme_addition_index=2,
    )
    assert [line.order for line in lines] == [1, 2]
    assert lines[0].is_heat is True
    assert lines[1].is_enzyme_addition_point is True
    assert lines[0].is_enzyme_addition_point is False


def test_no_enzyme_point_flags_nothing():
    lines = process_lines([ProcessStep(1, "whisk")], enzyme_addition_index=None)
    assert lines[0].is_enzyme_addition_point is False
