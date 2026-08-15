"""Spec §3 Workflow B."""

import pytest

from foodbrew.engine import ValidationRejection
from foodbrew.engine.compare import MAX_COLUMNS, MISSING, ComparisonSide, compare
from foodbrew.engine.types import DwellProfile, RuleFinding, Verdict


def _side(evaluation_id, headline, fmt, findings, envelope=None, doses=None, dwell=None):
    return ComparisonSide(
        evaluation_id=evaluation_id,
        label=evaluation_id,
        headline=headline,
        format=fmt,
        dwell_profile=dwell,
        findings=tuple(findings),
        envelope=envelope or dict.fromkeys(DwellProfile, Verdict.PASS),
        doses=doses or {},
    )


def _row(comparison, key):
    return next(r for r in comparison.rows if r.key == key)


def test_a_single_evaluation_is_refused():
    with pytest.raises(ValidationRejection):
        compare([_side("a", "RED", "premixed_wet", [])])


def test_more_than_the_cap_is_refused():
    sides = [_side(str(n), "GREEN", "dry_sachet", []) for n in range(MAX_COLUMNS + 1)]
    with pytest.raises(ValidationRejection) as excinfo:
        compare(sides)
    assert str(MAX_COLUMNS) in str(excinfo.value)


def test_the_headline_row_is_marked_changed_when_it_differs():
    comparison = compare([
        _side("a", "RED", "premixed_wet", []),
        _side("b", "GREEN", "dry_sachet", []),
    ])
    assert _row(comparison, "headline").changed
    assert _row(comparison, "format").changed


def test_an_identical_row_is_not_marked_changed():
    finding = RuleFinding("R4", Verdict.AMBER, "water switches it on")
    comparison = compare([
        _side("a", "AMBER", "premixed_wet", [finding]),
        _side("b", "AMBER", "premixed_wet", [finding]),
    ])
    assert not _row(comparison, "R4::").changed


def test_a_finding_present_on_one_side_only_renders_as_absent_not_dropped():
    comparison = compare([
        _side("a", "RED", "premixed_wet",
              [RuleFinding("R1", Verdict.RED, "denatures", enzyme_id="lactase_fungal_acid")]),
        _side("b", "GREEN", "dry_sachet", []),
    ])
    row = _row(comparison, "R1:lactase_fungal_acid:")
    assert row.changed
    assert [c.present for c in row.cells] == [True, False]
    assert row.cells[1].text == MISSING


def test_rows_are_ordered_by_rule_number_not_lexically():
    findings = [
        RuleFinding("R14", Verdict.RED, "uncovered"),
        RuleFinding("R2", Verdict.PASS, "window fits"),
    ]
    comparison = compare([
        _side("a", "RED", "dry_sachet", findings),
        _side("b", "RED", "dry_sachet", findings),
    ])
    rule_rows = [r.key for r in comparison.rows if r.section == "Rules"]
    assert rule_rows == ["R2::", "R14::"]


def test_dose_rows_union_across_columns_and_label_by_name():
    comparison = compare([
        _side("a", "AMBER", "dry_sachet", [],
              doses={"alpha_galactosidase": (150.0, "GalU", "Alpha-galactosidase")}),
        _side("b", "GREEN", "dry_sachet", [],
              doses={"alpha_galactosidase": (300.0, "GalU", "Alpha-galactosidase")}),
    ])
    row = _row(comparison, "dose:alpha_galactosidase")
    assert row.label == "Alpha-galactosidase"
    assert [c.text for c in row.cells] == ["150.0 GalU", "300.0 GalU"]
    assert row.changed


def test_a_missing_dose_reads_as_not_set_rather_than_blank():
    comparison = compare([
        _side("a", "GRAY", "dry_sachet", [], doses={"cellulase": (None, "", "Cellulase")}),
        _side("b", "GRAY", "dry_sachet", [], doses={"cellulase": (None, "", "Cellulase")}),
    ])
    assert _row(comparison, "dose:cellulase").cells[0].text == "no dose set"


def test_the_envelope_contributes_one_row_per_occasion():
    comparison = compare([
        _side("a", "AMBER", "dry_sachet", [], envelope={
            DwellProfile.IMMEDIATE: Verdict.PASS,
            DwellProfile.PACKED: Verdict.AMBER,
            DwellProfile.MARINADE: Verdict.RED,
        }),
        _side("b", "GREEN", "dry_sachet", []),
    ])
    keys = [r.key for r in comparison.rows if r.section == "Occasion envelope"]
    assert keys == ["envelope:immediate", "envelope:packed", "envelope:marinade"]
    assert not _row(comparison, "envelope:immediate").changed
    assert _row(comparison, "envelope:marinade").changed


def test_sections_come_out_in_reading_order():
    comparison = compare([
        _side("a", "RED", "premixed_wet", [RuleFinding("R1", Verdict.RED, "x")],
              doses={"lactase_fungal_acid": (9000.0, "FCC", "Lactase")}),
        _side("b", "GREEN", "dry_sachet", [], doses={}),
    ])
    seen = []
    for row in comparison.rows:
        if row.section not in seen:
            seen.append(row.section)
    assert seen == ["Verdict", "Setup", "Rules", "Dose per serving", "Occasion envelope"]
