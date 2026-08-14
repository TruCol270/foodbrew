import pytest

from foodbrew.engine.types import RuleFinding, Tracked, TruthLabel, Verdict, worst


def test_tracked_confirmed_is_usable():
    t = Tracked(value=2.5, status=TruthLabel.CONFIRMED, source="KB Table B")
    assert t.usable is True


def test_tracked_unconfirmed_is_not_usable():
    t = Tracked(value=None, status=TruthLabel.UNCONFIRMED, source="")
    assert t.usable is False


def test_tracked_with_value_but_unconfirmed_is_still_not_usable():
    # A seeded estimate is not evidence. Status decides, not presence of a number.
    t = Tracked(value=4.0, status=TruthLabel.UNCONFIRMED, source="estimate")
    assert t.usable is False


@pytest.mark.parametrize(
    "label", [TruthLabel.CONFIRMED, TruthLabel.USER_PROVIDED, TruthLabel.OBSERVED]
)
def test_all_evidence_labels_are_usable(label):
    assert Tracked(value=1.0, status=label, source="x").usable is True


def test_worst_orders_red_above_cannot_assess_above_amber_above_pass():
    assert worst([Verdict.PASS, Verdict.AMBER]) is Verdict.AMBER
    assert worst([Verdict.AMBER, Verdict.CANNOT_ASSESS]) is Verdict.CANNOT_ASSESS
    assert worst([Verdict.CANNOT_ASSESS, Verdict.RED]) is Verdict.RED
    assert worst([]) is Verdict.PASS


def test_rule_finding_is_frozen():
    f = RuleFinding(rule_id="R1", verdict=Verdict.RED, message="m", evidence={})
    with pytest.raises(Exception):
        f.verdict = Verdict.PASS
