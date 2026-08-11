"""Pins for variable-width recognition shared by rules and corpus queries."""

import ipakit
import pytest
from ipakit import _corpus_query as corpus_query
from ipakit import rules

FEATURES = ipakit.load_ipa_features()


class TestOptionalElements:
    @pytest.mark.parametrize(
        ("element", "present", "absent"),
        [
            ("d", "cdae", "cae"),
            ("[-vowel]", "ctae", "cae"),
            ("t{place=alveolar}", "ctae", "cae"),
            ("*", "ctae", "cae"),
        ],
    )
    def test_every_unit_pattern_composes(self, element: str, present: str, absent: str):
        spec = f"a -> b / c ({element}) _ e"
        assert ipakit.rewrite(present, spec) == present.replace("a", "b")
        assert ipakit.rewrite(absent, spec) == absent.replace("a", "b")

    def test_both_widths_are_distinct_sites_but_one_target_edit(self):
        rule = ipakit.rule("t -> d / (a) a _")
        sites = rule.recognize("aat")
        assert [site.left for site in sites] == [(1, None), (1, 0)]
        assert len(rule.edits("aat")) == 1
        assert ipakit.rewrite("aat", "t -> d / (a) a _") == "aad"

    def test_corpus_query_uses_the_same_readings(self):
        query = corpus_query.context("t / (a) a _", FEATURES)
        assert query.sites(FEATURES.read("aat").units, FEATURES) == ipakit.rule(
            "t -> d / (a) a _"
        ).recognize("aat")

    @pytest.mark.parametrize("target", ["(t)", "([vowel])", "(*)"])
    def test_optional_target_is_refused(self, target: str):
        with pytest.raises(rules.RuleError, match="target.*optional"):
            rules.parse(f"{target} -> d", FEATURES)

    @pytest.mark.parametrize("target", ["(t)*", "([vowel])*", "(*)*"])
    def test_repeated_target_is_refused(self, target: str):
        with pytest.raises(rules.RuleError, match="target.*repeated"):
            rules.parse(f"{target} -> d", FEATURES)

    @pytest.mark.parametrize("target", ["(t)", "(t)*"])
    def test_variable_width_query_target_is_refused_at_its_position(self, target: str):
        with pytest.raises(corpus_query.QueryParseError) as caught:
            corpus_query.parse_query(f"{target} / a _", FEATURES)
        assert caught.value.position == 0
        assert f"target {'optional' if target == '(t)' else 'repeated'}" in str(
            caught.value
        )

    def test_nested_optionality_is_refused_by_name(self):
        with pytest.raises(rules.RuleError, match="Nested optionality is refused"):
            rules.parse("t -> d / _ ((a))", FEATURES)

    def test_optional_only_binding_cannot_feed_a_change(self):
        with pytest.raises(rules.RuleError, match="absent binding cannot feed"):
            rules.parse("n -> [place=α] / _ ([place=α])", FEATURES)

    def test_optional_binding_is_absent_only_on_the_absent_reading(self):
        query = corpus_query.context("a / _ ([place=α])", FEATURES)
        sites = query.sites(FEATURES.read("ap").units, FEATURES)
        assert [site.bindings for site in sites] == [(), (("α", "bilabial"),)]


class TestBoundedSpans:
    def test_zero_to_form_length_units(self):
        rule = ipakit.rule("a -> [stress=primary] / # ([-vowel])* _")
        assert ipakit.rewrite("a", "a -> [stress=primary] / # ([-vowel])* _") == "ˈa"
        assert (
            ipakit.rewrite("stra", "a -> [stress=primary] / # ([-vowel])* _") == "strˈa"
        )
        assert len(rule.recognize("stra")[0].left) == len("stra")

    def test_wildcard_and_brace_constraints_compose(self):
        assert ipakit.rewrite("stra", "a -> e / # (*)* _") == "stre"
        assert ipakit.rewrite("tta", "a -> e / # (t{place=alveolar})* _") == "tte"

    def test_repeated_agreement_checks_every_present_unit(self):
        query = corpus_query.context("a / # ([place=α])* _ [place=α]", FEATURES)
        assert len(query.sites(FEATURES.read("ppap").units, FEATURES)) == 1
        assert query.sites(FEATURES.read("ptap").units, FEATURES) == []

    def test_span_only_binding_cannot_feed_a_change(self):
        with pytest.raises(rules.RuleError, match="absent binding cannot feed"):
            rules.parse("n -> [place=α] / _ ([place=α])*", FEATURES)

    def test_nested_variable_width_is_refused(self):
        with pytest.raises(rules.RuleError, match="Nested optionality is refused"):
            rules.parse("t -> d / _ ((a)*)", FEATURES)

    def test_identical_match_records_from_span_widths_are_deduplicated(self):
        assert len(list(corpus_query.find("stra", "a / ([-vowel])* _"))) == 1

    def test_span_widths_with_distinct_bindings_remain_distinct(self):
        matches = list(corpus_query.find("ppa", "a / ([place=α])* _"))
        assert [match.bindings for match in matches] == [
            (),
            (("α", "bilabial"),),
        ]


@pytest.mark.parametrize("null", ["∅", "[zero]", "0", "Ø"])
def test_rules_and_queries_refuse_null_environments(null: str):
    message = "environment names what stands there"
    with pytest.raises(rules.RuleError, match=message):
        rules.parse(f"a -> b / {null} _ #", FEATURES)
    with pytest.raises(rules.RuleError, match=message):
        corpus_query.context(f"a / {null} _ #", FEATURES)
