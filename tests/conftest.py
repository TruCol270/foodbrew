"""Builders for the golden fixtures.

Per the plan's stated boundary: fixtures take every ENZYME record from the real
shipped seed, and supply recipe pH and per-food substrate loads as explicit
user_provided test inputs — because every seeded food pH and load is unconfirmed
by design (spec §9.3).
"""

from __future__ import annotations

import dataclasses

import pytest

from foodbrew.engine.types import (
    EvalContext,
    Format,
    Formulation,
    Phase,
    RecipeIngredient,
    SelectedEnzyme,
    SeverityTier,
    StructuralClass,
    StructuralEntry,
    Tracked,
    TruthLabel,
)
from foodbrew.seedload.loader import load_seed


@pytest.fixture(scope="session")
def seed():
    return load_seed()


@pytest.fixture
def db_path(tmp_path):
    from foodbrew.db import create_database

    return create_database(tmp_path / "foodbrew.db")


@pytest.fixture
def conn(db_path):
    from foodbrew.store.connection import connect

    with connect(db_path) as c:
        yield c


@pytest.fixture
def with_load(seed):
    """Return a foods mapping where the named foods carry a confirmed load."""

    def _apply(**loads_by_food_id):
        foods = dict(seed.foods)
        for food_id, value in loads_by_food_id.items():
            foods[food_id] = dataclasses.replace(
                foods[food_id],
                typical_load_value=Tracked(value, TruthLabel.USER_PROVIDED, "fixture"),
            )
        return foods

    return _apply


@pytest.fixture
def make_ctx(seed):
    """Build an EvalContext with sensible fixture defaults."""

    def _build(
        *,
        fmt=Format.PREMIXED_WET,
        enzymes=(("lactase_fungal_acid", 9000.0, Phase.WET),),
        recipe=(),
        measured_ph=None,
        trigger_foods=(),
        application_foods=(),
        dwell_profile=None,
        process_steps=(),
        enzyme_addition_index=None,
        foods=None,
        enzyme_catalog=None,
    ):
        selections = tuple(
            SelectedEnzyme(eid, dose, phase, encapsulated=(len(rest) > 0 and rest[0]))
            for eid, dose, phase, *rest in
            [(e if len(e) > 3 else (*e, False)) for e in enzymes]
        )
        form = Formulation(
            id="fixture", format=fmt,
            recipe=tuple(RecipeIngredient(f, g) for f, g in recipe),
            enzymes=selections,
            target_trigger_food_ids=tuple(trigger_foods),
            application_food_ids=tuple(application_foods),
            dwell_profile=dwell_profile,
            measured_ph=(
                Tracked(measured_ph, TruthLabel.USER_PROVIDED, "fixture bench reading")
                if measured_ph is not None
                else Tracked(None, TruthLabel.UNCONFIRMED)
            ),
            process_steps=tuple(process_steps),
            enzyme_addition_index=enzyme_addition_index,
        )
        return EvalContext(
            formulation=form,
            enzymes=enzyme_catalog or seed.enzymes,
            foods=foods or seed.foods,
            substrates=seed.substrates,
            gi_regions=seed.gi_regions,
        )

    return _build


@pytest.fixture
def synthetic_rapid_enzyme(seed):
    """Spec §6.3.1 / fixture (m) — a test-only record claiming the rapid tier.

    Deliberately synthetic: no shipped enzyme claims rapid, because no source
    supports a minutes-scale rate claim about a real enzyme.
    """
    catalog = dict(seed.enzymes)
    base = catalog["protease_bromelain"]
    catalog["synthetic_rapid_protease"] = dataclasses.replace(
        base,
        id="synthetic_rapid_protease",
        name="Synthetic rapid protease (test only)",
        degrades_structural=(
            StructuralEntry(StructuralClass.STRUCTURAL_PROTEIN, SeverityTier.RAPID),
        ),
    )
    return catalog
