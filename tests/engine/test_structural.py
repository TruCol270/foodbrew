"""Decision #4 — the tier inside the value is the provenance."""

import pytest

from foodbrew.engine.structural import (
    StructuralError,
    parse_enzyme_entries,
    parse_food_classes,
)


def test_a_legal_enzyme_entry_round_trips():
    assert parse_enzyme_entries([{"structural_class": "pectin_cellulose", "tier": "gradual"}]) == (
        {"structural_class": "pectin_cellulose", "tier": "gradual"},
    )


def test_json_text_is_accepted_because_a_proposal_stores_text():
    assert parse_enzyme_entries('[{"structural_class": "starch", "tier": "rapid"}]') == (
        {"structural_class": "starch", "tier": "rapid"},
    )


def test_an_unknown_class_is_refused_and_names_the_vocabulary():
    with pytest.raises(StructuralError) as exc:
        parse_enzyme_entries([{"structural_class": "cellulose", "tier": "gradual"}])
    assert "pectin_cellulose" in str(exc.value)


def test_an_unknown_tier_is_refused():
    with pytest.raises(StructuralError) as exc:
        parse_enzyme_entries([{"structural_class": "starch", "tier": "fast"}])
    assert "gradual" in str(exc.value)


def test_a_duplicate_class_is_refused_rather_than_silently_merged():
    with pytest.raises(StructuralError):
        parse_enzyme_entries([
            {"structural_class": "starch", "tier": "gradual"},
            {"structural_class": "starch", "tier": "rapid"},
        ])


def test_unconfirmed_is_a_legal_tier_because_it_is_the_default_state():
    assert parse_enzyme_entries([{"structural_class": "pectin_cellulose", "tier": "unconfirmed"}])


def test_a_food_carries_classes_without_tiers():
    assert parse_food_classes(["starch", "starch", "structural_protein"]) == (
        "starch", "structural_protein",
    )


def test_malformed_json_is_refused_plainly():
    with pytest.raises(StructuralError) as exc:
        parse_enzyme_entries("not json")
    assert "JSON" in str(exc.value)


def test_a_bare_object_is_refused():
    with pytest.raises(StructuralError):
        parse_enzyme_entries({"structural_class": "starch", "tier": "gradual"})
