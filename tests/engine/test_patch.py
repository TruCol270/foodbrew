"""The patch vocabulary is closed, so its tests can be exhaustive."""

import pytest

from foodbrew.engine import ValidationRejection
from foodbrew.engine.patch import PatchOp, apply_patch, canonical, set_format
from foodbrew.engine.types import DwellProfile, Format, Phase


def test_every_op_has_a_handler():
    """A new member of the enum with no handler would raise KeyError at runtime."""
    from foodbrew.engine.patch import _HANDLERS

    assert set(_HANDLERS) == set(PatchOp)


def test_setting_a_dry_format_moves_every_enzyme_out_of_the_liquid(make_ctx):
    form = make_ctx(fmt=Format.PREMIXED_WET).formulation
    patched = apply_patch(form, set_format(Format.DRY_SACHET))
    assert patched.format is Format.DRY_SACHET
    assert all(s.phase is Phase.DRY for s in patched.enzymes)
    assert all(not s.encapsulated for s in patched.enzymes)


def test_setting_encapsulated_in_wet_actually_encapsulates(make_ctx):
    """Otherwise R6, whose subject is the capsule, never fires (plan decision #5)."""
    form = make_ctx(fmt=Format.PREMIXED_WET).formulation
    patched = apply_patch(form, set_format(Format.ENCAPSULATED_IN_WET))
    assert all(s.phase is Phase.WET and s.encapsulated for s in patched.enzymes)


def test_premixed_wet_leaves_the_encapsulation_choice_alone(make_ctx):
    form = make_ctx(
        fmt=Format.DRY_SACHET,
        enzymes=(("lactase_fungal_acid", 9000.0, Phase.DRY, True),),
    )
    patched = apply_patch(form.formulation, set_format(Format.PREMIXED_WET))
    assert patched.enzymes[0].encapsulated is True


def test_applying_a_patch_does_not_mutate_the_original(make_ctx):
    form = make_ctx(fmt=Format.PREMIXED_WET).formulation
    apply_patch(form, set_format(Format.DRY_SACHET))
    assert form.format is Format.PREMIXED_WET
    assert form.enzymes[0].phase is Phase.WET


def test_ops_apply_in_order(make_ctx):
    form = make_ctx(fmt=Format.PREMIXED_WET).formulation
    patched = apply_patch(form, {"ops": [
        {"op": "set_format", "value": "dual_chamber"},
        {"op": "set_enzyme_phase", "enzyme_id": "lactase_fungal_acid", "value": "wet"},
    ]})
    assert patched.format is Format.DUAL_CHAMBER
    assert patched.enzymes[0].phase is Phase.WET


def test_add_enzyme_takes_the_phase_the_format_implies(make_ctx):
    form = make_ctx(fmt=Format.PREMIXED_WET).formulation
    patched = apply_patch(form, {"ops": [
        {"op": "add_enzyme", "enzyme_id": "alpha_galactosidase", "dose": 300.0},
    ]})
    added = patched.enzymes[-1]
    assert (added.enzyme_id, added.dose, added.phase) == (
        "alpha_galactosidase", 300.0, Phase.WET
    )


def test_add_enzyme_is_idempotent(make_ctx):
    form = make_ctx().formulation
    patched = apply_patch(form, {"ops": [
        {"op": "add_enzyme", "enzyme_id": "lactase_fungal_acid"},
    ]})
    assert len(patched.enzymes) == len(form.enzymes)


def test_swap_replaces_in_place_and_keeps_the_position(make_ctx):
    form = make_ctx(enzymes=(
        ("lactase_fungal_acid", 9000.0, Phase.WET),
        ("alpha_galactosidase", 300.0, Phase.WET),
    )).formulation
    patched = apply_patch(form, {"ops": [{
        "op": "swap_enzyme", "enzyme_id": "lactase_fungal_acid",
        "replacement_id": "lactase_yeast_neutral", "dose": 9000.0,
    }]})
    assert [s.enzyme_id for s in patched.enzymes] == [
        "lactase_yeast_neutral", "alpha_galactosidase"
    ]


def test_swapping_onto_an_enzyme_already_selected_just_removes_the_old_one(make_ctx):
    form = make_ctx(enzymes=(
        ("lactase_fungal_acid", 9000.0, Phase.WET),
        ("lactase_yeast_neutral", 9000.0, Phase.WET),
    )).formulation
    patched = apply_patch(form, {"ops": [{
        "op": "swap_enzyme", "enzyme_id": "lactase_fungal_acid",
        "replacement_id": "lactase_yeast_neutral",
    }]})
    assert [s.enzyme_id for s in patched.enzymes] == ["lactase_yeast_neutral"]


def test_dwell_profile_round_trips_including_back_to_undeclared(make_ctx):
    form = make_ctx().formulation
    declared = apply_patch(form, {"ops": [
        {"op": "set_dwell_profile", "value": "immediate"},
    ]})
    assert declared.dwell_profile is DwellProfile.IMMEDIATE
    assert apply_patch(declared, {"ops": [
        {"op": "set_dwell_profile", "value": None},
    ]}).dwell_profile is None


def test_removing_a_trigger_food_leaves_the_rest(make_ctx):
    form = make_ctx(trigger_foods=("milk", "black_beans")).formulation
    patched = apply_patch(form, {"ops": [
        {"op": "remove_trigger_food", "food_id": "milk"},
    ]})
    assert patched.target_trigger_food_ids == ("black_beans",)


@pytest.mark.parametrize("patch, fragment", [
    (None, "nothing to apply"),
    ({}, "no change"),
    ({"ops": []}, "no change"),
    ({"ops": "set_format"}, "no change"),
    ({"ops": [{"value": "dry_sachet"}]}, "Malformed"),
    ({"ops": [{"op": "drop_the_database"}]}, "Unknown change"),
    ({"ops": [{"op": "set_format", "value": "sachet"}]}, "Unknown format"),
    ({"ops": [{"op": "remove_enzyme", "enzyme_id": "amylase"}]}, "not selected"),
    ({"ops": [{"op": "set_enzyme_dose", "enzyme_id": "lactase_fungal_acid", "value": -1}]},
     "cannot be negative"),
])
def test_malformed_patches_are_refused_in_plain_english(make_ctx, patch, fragment):
    form = make_ctx().formulation
    with pytest.raises(ValidationRejection) as excinfo:
        apply_patch(form, patch)
    assert fragment in str(excinfo.value)


def test_canonical_is_stable_across_key_order():
    a = {"ops": [{"op": "set_format", "value": "dry_sachet"}]}
    b = {"ops": [{"value": "dry_sachet", "op": "set_format"}]}
    assert canonical(a) == canonical(b)
    assert canonical(None) == ""
