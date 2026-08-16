"""Spec §16 — the amendments that are assertions about behaviour, not prose.

A spec sentence nothing checks drifts again. These four are checkable, so they
are checked; the rest live in §16's table and in review.
"""

import pathlib

SPEC = (
    pathlib.Path(__file__).resolve().parents[1]
    / "docs/superpowers/specs/2026-08-13-enzyme-rules-engine-design.md"
)


def spec_text() -> str:
    return SPEC.read_text(encoding="utf-8")


def test_the_spec_documents_the_per_field_advisory_exception():
    """M1 deviation #4 — the one that changes what a headline says."""
    text = spec_text()
    assert "Per-field advisory exception" in text
    for field in ("dose_evidence_threshold", "is_gras", "ph_min"):
        assert field in text


def test_the_advisory_exception_matches_the_rules_as_built():
    """The spec now claims R2/R7/R11 have an advisory branch. Prove they do."""
    import inspect

    from foodbrew.engine.rules import r02_gi_window, r07_dosing, r11_food_grade

    for module in (r02_gi_window, r07_dosing, r11_food_grade):
        assert "advisory=True" in inspect.getsource(module), module.RULE_ID


def test_the_spec_states_the_observed_texture_scale():
    text = spec_text()
    assert "Observed texture scale" in text
    assert "indistinguishable" in text


def test_the_scale_in_the_spec_matches_the_scale_in_the_engine():
    from foodbrew.engine.observations import TEXTURE_SCALE

    text = spec_text()
    for wording in TEXTURE_SCALE.values():
        assert wording.split(" —")[0].split(",")[0][:18] in text, wording


def test_the_spec_has_an_amendments_log_covering_every_milestone():
    text = spec_text()
    assert "# 16. Amendments" in text
    for milestone in ("M1", "M2", "M3", "M4", "M5"):
        assert milestone in text.split("# 16. Amendments")[1]


def test_the_spec_lists_m5_in_the_milestones():
    assert "M5 —" in spec_text()
