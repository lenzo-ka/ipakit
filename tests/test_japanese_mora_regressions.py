"""Linguistic counterexamples from the Japanese mora audit."""

import ipakit
import pytest
from ipakit._rewrite_graph import derive_morae

import tiergraph


@pytest.mark.parametrize(
    "text,expected",
    [
        ("hotːo", ("ho", "t", "to")),
        ("kapːa", ("ka", "p", "pa")),
        ("kakːa", ("ka", "k", "ka")),
        ("kiɕːa", ("ki", "ɕ", "ɕa")),
        ("mat͡ɕːa", ("ma", "t", "t͡ɕa")),
        ("at̪͡sːu", ("a", "t̪", "t̪͡su")),
        ("apʲːa", ("a", "pʲ", "pʲa")),
        ("akʲːa", ("a", "kʲ", "kʲa")),
        ("ãː", ("ã", "ã")),
        ("ko͜i", ("ko", "i")),
        ("honːa", ("ho", "n", "na")),
        ("kuɾisumasu", ("ku", "ɾi", "su", "ma", "su")),
    ],
)
def test_shared_mora_analysis_retains_material(text, expected):
    features = ipakit.IPAFeatures()
    form = features.read(text, strict=True)
    result = ipakit.syllabify(form, "japanese")
    assert result.spelled("mora") == expected
    assert tuple(m.spelling for m in derive_morae(form.units, features)) == expected
    assert result.unsyllabified == ()
    assert result.form.to_ipa() == form.to_ipa()


@pytest.mark.parametrize("text", ["ka͡i", "ka͜iː", "tːa", "atː", "atːjːa", "atːɾa"])
def test_undeclared_phase_timing_is_refused(text):
    features = ipakit.IPAFeatures()
    with pytest.raises(ValueError, match="mora"):
        ipakit.syllabify(text, "japanese")
    with pytest.raises(ValueError, match="mora"):
        derive_morae(features.read(text).units, features)


def test_nasal_hold_retains_its_declared_kind():
    features = ipakit.IPAFeatures()
    analyses = derive_morae(features.read("honːa").units, features)
    assert [(m.spelling, m.kind) for m in analyses] == [
        ("ho", "ordinary"),
        ("n", "nasal"),
        ("na", "ordinary"),
    ]
    assert ipakit.syllabify("honːa", "japanese").spelled() == ("hon", "na")


def _members(form):
    source = form.__dict__["_tiergraph_index"].containment_input
    return source, {
        relation.sources[0]: relation.targets
        for relation in source.relations
        if relation.name == "contains"
    }


def test_geminate_graph_shares_one_occurrence_across_two_syllables():
    result = ipakit.syllabify("hotːo", "japanese")
    assert result.spelled() == ("hot", "to")
    assert [(i.start, i.end) for i in result.syllables] == [(0, 3), (2, 4)]
    with pytest.raises(ValueError, match="shared syllable"):
        result.marks()
    graph = result.form._graph
    restored = tiergraph.wire.loads(tiergraph.wire.dumps(graph))
    assert restored == graph
    assert restored.polyadic_relations == graph.polyadic_relations
    for form in (result.form,):
        source, members = _members(form)
        syllables = [
            path for path in source.refs if source.event_tiers[path] == "syllable"
        ]
        morae = [child for parent in syllables for child in members[parent]]
        assert [source.events[path].features["spelling"] for path in morae] == [
            "ho",
            "t",
            "to",
        ]
        assert len(members[syllables[0]]) == 2
        assert len(members[syllables[1]]) == 1
        held = members[morae[1]][0]
        assert held == members[morae[2]][0]
        assert source.events[held].features["compatibility-unit"].text == "tː"
        assert source.events[held].timing is None


def test_generic_rewrite_projection_assigns_no_implicit_language():
    features = ipakit.IPAFeatures()
    derivation = ipakit.rules.RuleSet.parse("t -> d", features).derive("sta", features)
    form = derivation.to_form(features)
    assert form.to_ipa() == "sda"
    assert form.tier_events("mora") == ()
    with pytest.raises(ValueError, match="unlicensed"):
        derivation.to_form(features, mora_language="japanese")
    with pytest.raises(ValueError, match="only explicit"):
        derivation.to_form(features, mora_language="unknown")


def test_japanese_rewrite_analysis_is_explicit():
    derivation = ipakit.ruleset("japanese-moraic").derive("hɑt")
    form = derivation.to_form(mora_language="japanese")
    assert tuple(event["value"] for event in form.tier_events("mora")) == (
        "ho",
        "t",
        "to",
    )


def test_long_vowel_graph_shares_one_vowel_between_two_morae():
    source, members = _members(ipakit.syllabify("ãː", "japanese").form)
    syllable = next(
        path for path in source.refs if source.event_tiers[path] == "syllable"
    )
    first, second = members[syllable]
    assert first != second
    assert members[first] == members[second]


@pytest.mark.parametrize("boundary", ["#", " ", "."])
def test_boundaries_do_not_carry_onsets_into_the_next_region(boundary):
    features = ipakit.IPAFeatures()
    text = "at" + boundary + "a"
    result = ipakit.syllabify(text, "japanese")
    assert result.spelled("mora") == ("a", "a")
    assert result.unsyllabified == ((1, 2),)
    with pytest.raises(ValueError, match="unlicensed"):
        derive_morae(features.read(text).units, features)
