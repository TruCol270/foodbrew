"""The lint that guards every other lint."""

import json
import pathlib

import pytest

from foodbrew.engine.language import PROHIBITED_WORDS, contains_prohibited

SEED_DIR = pathlib.Path(__file__).resolve().parents[2] / "seed"


@pytest.mark.parametrize("word", PROHIBITED_WORDS)
def test_each_word_is_caught_on_its_own(word):
    # Membership, not equality: "clinically proven" legitimately also contains
    # the whole word "proven", so both entries fire and that is correct, not
    # a false positive.
    assert word in contains_prohibited(f"this result is {word} to use")


def test_safety_is_not_safe():
    """The §10 footer has to survive its own lint (plan decision #11)."""
    assert contains_prohibited("Not a safety, efficacy, or regulatory determination.") == ()


def test_matching_ignores_case_and_reports_in_list_order():
    found = contains_prohibited("PROVEN and Validated")
    assert found == ("validated", "proven")


def test_clean_text_reports_nothing():
    assert contains_prohibited("flags formulation risks and knowledge gaps") == ()


def test_no_prohibited_word_appears_in_the_shipped_seed():
    """Spec §13 report lint: the report quotes seed notes verbatim, so the seed
    is tool copy and has to comply. Founder free text does not — see Task 7."""
    offenders: list[str] = []
    for path in sorted(SEED_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for word in contains_prohibited(json.dumps(payload)):
            offenders.append(f"{path.name}: {word}")
    assert not offenders, ", ".join(offenders)
