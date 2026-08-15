from foodbrew.engine.selection import propose_enzymes
from foodbrew.engine.types import Format, Phase


def test_proposes_an_enzyme_for_a_targeted_substrate(seed):
    proposed = propose_enzymes(
        trigger_food_ids=("milk",), format=Format.DRY_SACHET,
        foods=seed.foods, substrates=seed.substrates, enzymes=seed.enzymes,
    )
    assert any(s.enzyme_id.startswith("lactase") for s in proposed)


def test_never_proposes_an_enzyme_for_a_polyol_food(seed):
    """Spec §6.2 R14 — the tool never maps polyols to an enzyme."""
    polyol_foods = [
        f.id for f in seed.foods.values()
        if any(
            seed.substrates[sid].no_commercial_enzyme
            for sid in f.contains_substrate_ids
            if sid in seed.substrates
        )
    ]
    assert polyol_foods, "the seed carries at least one polyol trigger food"
    proposed = propose_enzymes(
        trigger_food_ids=tuple(polyol_foods), format=Format.DRY_SACHET,
        foods=seed.foods, substrates=seed.substrates, enzymes=seed.enzymes,
    )
    for selected in proposed:
        substrate = seed.substrates[seed.enzymes[selected.enzyme_id].substrate_id]
        assert substrate.no_commercial_enzyme is False


def test_phase_follows_the_format(seed):
    dry = propose_enzymes(
        trigger_food_ids=("milk",), format=Format.DUAL_CHAMBER,
        foods=seed.foods, substrates=seed.substrates, enzymes=seed.enzymes,
    )
    wet = propose_enzymes(
        trigger_food_ids=("milk",), format=Format.PREMIXED_WET,
        foods=seed.foods, substrates=seed.substrates, enzymes=seed.enzymes,
    )
    assert all(s.phase is Phase.DRY for s in dry)
    assert all(s.phase is Phase.WET for s in wet)


def test_dose_is_never_invented(seed):
    """A proposed dose comes from the record or is left None for R7 to flag."""
    proposed = propose_enzymes(
        trigger_food_ids=("milk",), format=Format.DRY_SACHET,
        foods=seed.foods, substrates=seed.substrates, enzymes=seed.enzymes,
    )
    for selected in proposed:
        enzyme = seed.enzymes[selected.enzyme_id]
        if selected.dose is None:
            continue
        assert selected.dose in {
            enzyme.dose_evidence_threshold.value, enzyme.dose_min.value
        }


def test_proposal_is_deterministic_and_deduplicated(seed):
    args = dict(
        trigger_food_ids=("milk", "milk"), format=Format.DRY_SACHET,
        foods=seed.foods, substrates=seed.substrates, enzymes=seed.enzymes,
    )
    first = propose_enzymes(**args)
    assert first == propose_enzymes(**args)
    assert len({s.enzyme_id for s in first}) == len(first)


def test_unknown_food_ids_are_ignored_rather_than_raising(seed):
    assert propose_enzymes(
        trigger_food_ids=("no_such_food",), format=Format.DRY_SACHET,
        foods=seed.foods, substrates=seed.substrates, enzymes=seed.enzymes,
    ) == ()
