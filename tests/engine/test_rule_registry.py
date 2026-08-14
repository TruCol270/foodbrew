from foodbrew.engine.rules import ADVISORY_RULE_IDS, ALL_RULES, HEADLINE_RULE_IDS


def test_registry_is_ordered_r1_through_r16_without_r13():
    # R13 is aggregation itself (spec §6.1), not a finding-producing rule.
    ids = [m.RULE_ID for m in ALL_RULES]
    assert ids == [f"R{n}" for n in range(1, 17) if n != 13]


def test_every_rule_module_exposes_the_contract():
    for module in ALL_RULES:
        assert isinstance(module.RULE_ID, str)
        assert isinstance(module.ADVISORY, bool)
        assert callable(module.evaluate)


def test_headline_and_advisory_sets_match_spec_6_4():
    # Spec §6.4: headline = R1-R7, R11, R14, plus R15. Advisory = R8, R9, R10, R12, R16.
    assert HEADLINE_RULE_IDS == frozenset(
        {"R1", "R2", "R3", "R4", "R5", "R6", "R7", "R11", "R14", "R15"}
    )
    assert ADVISORY_RULE_IDS == frozenset({"R8", "R9", "R10", "R12", "R16"})


def test_sets_are_disjoint_and_cover_every_rule():
    ids = {m.RULE_ID for m in ALL_RULES}
    assert HEADLINE_RULE_IDS & ADVISORY_RULE_IDS == frozenset()
    assert HEADLINE_RULE_IDS | ADVISORY_RULE_IDS == ids
