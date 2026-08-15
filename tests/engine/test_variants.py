"""Spec §7, row by row, plus the three constraints plan decisions #4, #13 and
#14 put on the table.
"""

import dataclasses

import pytest

from foodbrew.engine.evaluate import evaluate
from foodbrew.engine.patch import apply_patch
from foodbrew.engine.types import (
    DwellProfile,
    Format,
    Phase,
    ProcessStep,
    Tracked,
    TruthLabel,
    Verdict,
)
from foodbrew.engine.variants import SuggestionType, suggest


def _suggest(ctx):
    return suggest(ctx, evaluate(ctx).findings)


def _types(suggestions):
    return {s.suggestion_type for s in suggestions}


def _of(suggestions, kind):
    return [s for s in suggestions if s.suggestion_type is kind]


# --- §7 row 1: R1 RED ------------------------------------------------------ #

def test_r1_red_offers_a_separated_format(make_ctx):
    ctx = make_ctx(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    formats = _of(_suggest(ctx), SuggestionType.FORMAT_CHANGE)
    targets = {s.patch["ops"][0]["value"] for s in formats}
    assert targets == {"dual_chamber", "dry_sachet"}


def test_r1_red_names_the_ingredient_holding_the_pH_down_and_offers_no_patch(
    make_ctx, seed
):
    """Plan decision #4 — the engine has no mixing model, so this is a note."""
    foods = dict(seed.foods)
    for food_id, ph, water in (("olive_oil", 6.0, 0.0), ("white_vinegar", 2.6, 95.0)):
        foods[food_id] = dataclasses.replace(
            foods[food_id],
            ph=Tracked(ph, TruthLabel.USER_PROVIDED, "fixture"),
            water_content_pct=Tracked(water, TruthLabel.USER_PROVIDED, "fixture"),
        )
    ctx = make_ctx(
        fmt=Format.PREMIXED_WET,
        recipe=(("olive_oil", 100.0), ("white_vinegar", 50.0)),
        trigger_foods=("milk",),
        foods=foods,
    )
    notes = _of(_suggest(ctx), SuggestionType.RECIPE_NOTE)
    assert notes and notes[0].patch is None
    assert "White vinegar" in notes[0].description or "vinegar" in notes[0].description
    assert "measured rather than predicted" in notes[0].description


def test_r1_red_offers_a_swap_when_the_catalogue_holds_one_that_clears(make_ctx, seed):
    catalog = dict(seed.enzymes)
    catalog["lactase_yeast_neutral"] = dataclasses.replace(
        catalog["lactase_yeast_neutral"],
        ph_shelf_stable_min=Tracked(2.0, TruthLabel.CONFIRMED, "supplier spec"),
    )
    ctx = make_ctx(
        fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",),
        enzyme_catalog=catalog,
    )
    swaps = _of(_suggest(ctx), SuggestionType.SWAP_ENZYME)
    assert [s.patch["ops"][0]["replacement_id"] for s in swaps] == ["lactase_yeast_neutral"]


def test_an_unconfirmed_alternative_is_surfaced_as_a_candidate_not_a_patch(make_ctx):
    """§7: 'surfaced even when unconfirmed, labeled candidate — confirm with supplier'."""
    ctx = make_ctx(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    questions = _of(_suggest(ctx), SuggestionType.SUPPLIER_QUESTION)
    candidate = [q for q in questions if "Candidate" in q.description]
    assert candidate and candidate[0].patch is None


# --- §7 row 2: R3 RED ------------------------------------------------------ #

def test_r3_red_moves_the_enzyme_past_the_last_heat_step(make_ctx):
    ctx = make_ctx(
        process_steps=(
            ProcessStep(1, "whisk", False),
            ProcessStep(2, "warm the base", True),
            ProcessStep(3, "cool", False),
        ),
        enzyme_addition_index=1,
        trigger_foods=("milk",),
        measured_ph=6.0,
    )
    moves = _of(_suggest(ctx), SuggestionType.MOVE_ENZYME_ADDITION)
    assert moves and moves[0].patch["ops"][0] == {
        "op": "set_enzyme_addition_index", "value": 3
    }


# --- §7 row 3: R4 AMBER / R6 RED ------------------------------------------- #

def test_r4_amber_offers_separation_and_individual_encapsulation(make_ctx):
    ctx = make_ctx(fmt=Format.PREMIXED_WET, measured_ph=6.0, trigger_foods=("milk",))
    kinds = _types(_suggest(ctx))
    assert SuggestionType.FORMAT_CHANGE in kinds
    assert SuggestionType.ENCAPSULATE_ENZYME in kinds


def test_the_encapsulation_suggestion_carries_the_R6_caveat(make_ctx):
    ctx = make_ctx(fmt=Format.PREMIXED_WET, measured_ph=6.0, trigger_foods=("milk",))
    caps = _of(_suggest(ctx), SuggestionType.ENCAPSULATE_ENZYME)
    assert "delays exposure rather than preventing it" in caps[0].description


# --- §7 row 4: R5 RED ------------------------------------------------------ #

def test_r5_red_offers_separation_and_dropping_the_protease(make_ctx):
    ctx = make_ctx(
        fmt=Format.PREMIXED_WET, measured_ph=6.0, trigger_foods=("milk",),
        enzymes=(
            ("lactase_fungal_acid", 9000.0, Phase.WET),
            ("protease_bromelain", 500.0, Phase.WET),
        ),
    )
    suggestions = _suggest(ctx)
    separate = _of(suggestions, SuggestionType.SEPARATE_ENZYME)
    drop = _of(suggestions, SuggestionType.DROP_ENZYME)
    assert separate[0].patch["ops"][0]["enzyme_id"] == "protease_bromelain"
    assert any(s.patch["ops"][0]["enzyme_id"] == "protease_bromelain" for s in drop)
    assert "additive rather than gap-filling" in drop[0].description


# --- §7 row 5: R7 AMBER ---------------------------------------------------- #

def test_r7_amber_offers_the_evidence_threshold_and_a_narrower_claim(make_ctx, with_load):
    ctx = make_ctx(
        fmt=Format.DRY_SACHET,
        enzymes=(("alpha_galactosidase", 150.0, Phase.DRY),),
        trigger_foods=("black_beans",),
        foods=with_load(black_beans=6.0),
    )
    suggestions = _suggest(ctx)
    raise_dose = _of(suggestions, SuggestionType.RAISE_DOSE)
    assert raise_dose[0].patch["ops"][0]["value"] == 300.0
    drop_food = _of(suggestions, SuggestionType.DROP_TRIGGER_FOOD)
    assert drop_food[0].patch["ops"][0]["food_id"] == "black_beans"


# --- §7 row 7: R11 / R12 cannot_assess ------------------------------------- #

def test_unassessable_sourcing_rules_become_open_questions_with_no_patch(make_ctx):
    ctx = make_ctx(fmt=Format.DRY_SACHET, trigger_foods=("milk",))
    questions = _of(_suggest(ctx), SuggestionType.SUPPLIER_QUESTION)
    assert questions, "R12 is cannot_assess for every shipped enzyme (spec §9.1)"
    assert all(q.patch is None for q in questions)
    assert any("R12" in q.triggered_by for q in questions)


# --- §7 row 8: R14 RED ----------------------------------------------------- #

def test_r14_red_adds_the_enzyme_for_the_uncovered_substrate(make_ctx):
    ctx = make_ctx(
        fmt=Format.DRY_SACHET,
        enzymes=(("lactase_fungal_acid", 9000.0, Phase.DRY),),
        trigger_foods=("milk", "black_beans"),
    )
    adds = _of(_suggest(ctx), SuggestionType.ADD_ENZYME)
    assert any(s.patch["ops"][0]["enzyme_id"] == "alpha_galactosidase" for s in adds)


def test_a_polyol_trigger_food_never_produces_an_enzyme_suggestion(make_ctx):
    """§6.2 R14: the tool never maps polyols to an enzyme."""
    ctx = make_ctx(
        fmt=Format.DRY_SACHET,
        enzymes=(("lactase_fungal_acid", 9000.0, Phase.DRY),),
        trigger_foods=("milk", "mushroom"),
    )
    for suggestion in _of(_suggest(ctx), SuggestionType.ADD_ENZYME):
        added = suggestion.patch["ops"][0]["enzyme_id"]
        assert ctx.enzymes[added].substrate_id != "polyol"


# --- §7 row 9: R15 envelope non-pass --------------------------------------- #

def test_r15_offers_dropping_the_degrader_restricting_occasions_and_a_note(make_ctx):
    ctx = make_ctx(
        fmt=Format.DRY_SACHET,
        enzymes=(("cellulase", None, Phase.DRY),),
        trigger_foods=("broccoli",),
        application_foods=("mixed_greens",),
    )
    suggestions = _suggest(ctx)
    kinds = _types(suggestions)
    assert SuggestionType.DROP_ENZYME in kinds
    assert SuggestionType.RESTRICT_OCCASIONS in kinds
    assert SuggestionType.BEHAVIOUR_NOTE in kinds

    restrict = _of(suggestions, SuggestionType.RESTRICT_OCCASIONS)[0]
    assert restrict.patch["ops"][0]["value"] == DwellProfile.IMMEDIATE.value


def test_r15_never_offers_a_format_change_for_texture(make_ctx):
    """§7: a dual chamber does not move how long dressing sits on the food."""
    ctx = make_ctx(
        fmt=Format.DRY_SACHET,
        enzymes=(("cellulase", None, Phase.DRY),),
        trigger_foods=("broccoli",),
        application_foods=("mixed_greens",),
    )
    for suggestion in _of(_suggest(ctx), SuggestionType.FORMAT_CHANGE):
        assert "R15" not in suggestion.triggered_by


# --- Assembly rules -------------------------------------------------------- #

def test_the_dual_chamber_button_appears_once_and_names_every_rule(make_ctx):
    """Plan decision #14 — R1, R4 and R6 all ask for it."""
    ctx = make_ctx(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    dual = [
        s for s in _of(_suggest(ctx), SuggestionType.FORMAT_CHANGE)
        if s.patch["ops"][0]["value"] == "dual_chamber"
    ]
    assert len(dual) == 1
    assert set(dual[0].triggered_by) >= {"R1", "R4"}


def test_the_order_is_stable_across_runs(make_ctx):
    ctx = make_ctx(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    first = [(s.suggestion_type, s.description) for s in _suggest(ctx)]
    second = [(s.suggestion_type, s.description) for s in _suggest(ctx)]
    assert first == second


def test_a_drop_that_would_empty_the_formulation_is_suppressed(make_ctx):
    """Plan decision #13 — §6.2 R14 would refuse the result."""
    ctx = make_ctx(
        fmt=Format.PREMIXED_WET,
        measured_ph=6.0,
        enzymes=(("protease_bromelain", 500.0, Phase.WET),),
        trigger_foods=(),
        recipe=(("olive_oil", 100.0),),
        application_foods=("chicken_cooked",),
    )
    for suggestion in _of(_suggest(ctx), SuggestionType.DROP_ENZYME):
        pytest.fail(f"emitted a drop that empties the formulation: {suggestion.description}")


def test_every_applicable_patch_re_evaluates_without_error(make_ctx):
    """Spec §13's contract test, at the engine level. Task 20 repeats it over HTTP."""
    contexts = [
        make_ctx(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",)),
        make_ctx(
            fmt=Format.PREMIXED_WET, measured_ph=6.0, trigger_foods=("milk",),
            enzymes=(
                ("lactase_fungal_acid", 9000.0, Phase.WET),
                ("protease_bromelain", 500.0, Phase.WET),
            ),
        ),
        make_ctx(
            fmt=Format.DRY_SACHET,
            enzymes=(("cellulase", None, Phase.DRY),),
            trigger_foods=("broccoli",),
            application_foods=("mixed_greens",),
        ),
        make_ctx(
            fmt=Format.DRY_SACHET,
            enzymes=(("lactase_fungal_acid", 9000.0, Phase.DRY),),
            trigger_foods=("milk", "black_beans"),
        ),
    ]
    applied = 0
    for ctx in contexts:
        for suggestion in _suggest(ctx):
            if not suggestion.is_applicable:
                continue
            patched = apply_patch(ctx.formulation, suggestion.patch)
            result = evaluate(dataclasses.replace(ctx, formulation=patched))
            assert result.overall in set(Verdict)
            applied += 1
    assert applied >= 8, "the sweep applied suspiciously few patches"


def test_notes_never_carry_a_patch(make_ctx):
    note_kinds = {
        SuggestionType.RECIPE_NOTE,
        SuggestionType.BEHAVIOUR_NOTE,
        SuggestionType.SUPPLIER_QUESTION,
    }
    ctx = make_ctx(fmt=Format.PREMIXED_WET, measured_ph=3.0, trigger_foods=("milk",))
    for suggestion in _suggest(ctx):
        if suggestion.suggestion_type in note_kinds:
            assert suggestion.patch is None
        else:
            assert suggestion.patch is not None
