"""Spec §9.2 — R9's trigger set is exactly three substrates."""

from foodbrew.seedload.loader import load_seed

PREBIOTIC = {"gos", "inulin_fructan", "graminan_fructan"}


def test_exactly_the_spec_named_substrates_are_prebiotic():
    seed = load_seed()
    flagged = {s.id for s in seed.substrates.values() if s.is_prebiotic}
    assert flagged == PREBIOTIC


def test_r9_no_longer_fires_for_a_cellulase_only_blend(make_ctx, seed):
    """The observable consequence: a structure-degrading blend with no fructan
    or GOS target raises no prebiotic-tension advisory."""
    from foodbrew.engine.rules import r09_prebiotic_tension
    from foodbrew.engine.types import Phase

    ctx = make_ctx(enzymes=(("cellulase", None, Phase.DRY),), recipe=(("olive_oil", 100.0),))
    assert r09_prebiotic_tension.evaluate(ctx) == []
