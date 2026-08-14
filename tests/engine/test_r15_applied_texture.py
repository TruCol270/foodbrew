from foodbrew.engine.rules import r15_applied_texture as r15
from foodbrew.engine.types import (
    Deadline,
    DwellProfile,
    Enzyme,
    EvalContext,
    Food,
    Format,
    Formulation,
    Phase,
    SelectedEnzyme,
    SeverityTier,
    StructuralClass,
    StructuralEntry,
    Tracked,
    TruthLabel,
    Verdict,
)


def _enzyme(eid, entries):
    return Enzyme(
        id=eid, name=eid, substrate_id="lactose", source_type="fungal", priority="high",
        deadline=Deadline.BEFORE_COLON,
        ph_min=Tracked(3.0, TruthLabel.CONFIRMED, "t"),
        ph_max=Tracked(7.0, TruthLabel.CONFIRMED, "t"),
        ph_opt_low=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
        ph_opt_high=Tracked(5.0, TruthLabel.CONFIRMED, "t"),
        ph_shelf_stable_min=Tracked(None, TruthLabel.UNCONFIRMED), dose_unit="FCC",
        degrades_structural=entries,
    )


GREENS = Food(id="mixed_greens", name="Mixed greens", category="green",
              is_application_food=True, structural=(StructuralClass.PECTIN_CELLULOSE,))
CHICKEN = Food(id="chicken_cooked", name="Cooked chicken", category="protein",
               is_application_food=True, structural=(StructuralClass.STRUCTURAL_PROTEIN,))

LACTASE = _enzyme("lactase", ())
CELLULASE = _enzyme("cellulase", (StructuralEntry(StructuralClass.PECTIN_CELLULOSE,
                                                  SeverityTier.GRADUAL),))
RAPID_PROTEASE = _enzyme("synthetic_rapid",
                         (StructuralEntry(StructuralClass.STRUCTURAL_PROTEIN,
                                          SeverityTier.RAPID),))
INULINASE = _enzyme("inulinase", (StructuralEntry(StructuralClass.PECTIN_CELLULOSE,
                                                  SeverityTier.UNCONFIRMED),))


def _ctx(enzymes, foods, dwell=None):
    emap = {e.id: e for e in enzymes}
    return EvalContext(
        formulation=Formulation(
            id="f", format=Format.DUAL_CHAMBER, recipe=(),
            enzymes=tuple(SelectedEnzyme(e.id, 100.0, Phase.DRY) for e in enzymes),
            application_food_ids=tuple(f.id for f in foods), dwell_profile=dwell,
        ),
        enzymes=emap, foods={f.id: f for f in foods}, substrates={},
    )


def test_narrow_blend_passes_every_profile():
    # Spec §13 fixture (k).
    env = r15.envelope(_ctx([LACTASE], [GREENS]))
    assert all(v is Verdict.PASS for v in env.values())


def test_gradual_degrader_worsens_with_dwell():
    # Spec §13 fixture (l).
    env = r15.envelope(_ctx([CELLULASE], [GREENS]))
    assert env[DwellProfile.IMMEDIATE] is Verdict.PASS
    assert env[DwellProfile.PACKED] is Verdict.AMBER
    assert env[DwellProfile.MARINADE] is Verdict.RED


def test_rapid_tier_reds_every_profile():
    # Spec §13 fixture (m) — synthetic record by design.
    env = r15.envelope(_ctx([RAPID_PROTEASE], [CHICKEN]))
    assert all(v is Verdict.RED for v in env.values())


def test_unconfirmed_tier_is_cannot_assess_everywhere():
    # Spec §13 fixture (o).
    env = r15.envelope(_ctx([INULINASE], [GREENS]))
    assert all(v is Verdict.CANNOT_ASSESS for v in env.values())


def test_no_intersection_when_structural_classes_differ():
    env = r15.envelope(_ctx([CELLULASE], [CHICKEN]))
    assert all(v is Verdict.PASS for v in env.values())


def test_multiple_pairs_take_the_worst_never_compound():
    # Spec §6.2 R15: overlap never compounds beyond the worst single pair.
    env = r15.envelope(_ctx([CELLULASE, RAPID_PROTEASE], [GREENS, CHICKEN]))
    assert env[DwellProfile.IMMEDIATE] is Verdict.RED  # from the rapid pair alone


def test_findings_name_the_enzyme_and_food():
    findings = r15.evaluate(_ctx([CELLULASE], [GREENS]))
    pair = [f for f in findings if f.enzyme_id == "cellulase" and f.food_id == "mixed_greens"]
    assert pair
    assert "mixed greens" in pair[0].message.lower()


def test_no_application_foods_produces_no_findings():
    assert r15.evaluate(_ctx([CELLULASE], [])) == []
