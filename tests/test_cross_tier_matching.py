"""TierGraph-backed matching over selected Form tiers."""

import ipakit
import pytest
from ipakit._cross_tier import CrossTierQuery, _cell, match_payloads
from ipakit.corpus import QueryParseError, find
from tiergraph.match import AtomPattern, RepeatPattern
from tiergraph.predicate import Equals

from tiergraph import wire


def observed(form, query):
    return [(match.text, match.output_ranges) for match in find(form, query)]


def test_required_cross_tier_witness_and_mutation():
    query = (
        "on(tier:segment): [vowel]{@feature:tone{tone=top} & "
        "@tier:syllable{@feature:stress{stress=primary}}} [consonant]"
    )
    high = ipakit.syllabify("ˈa˥t", "english").form
    low = ipakit.syllabify("ˈa˩t", "english").form
    assert observed(high, query) == [("ˈa˥t", ((0, 4),))]
    assert observed(low, query) == []


def test_break_selection_crosses_the_prosodic_break():
    query = "on(tier:segment,feature:break): " "[vowel] [break=minor] [consonant]"
    assert observed("a|b", query) == [("a|b", ((0, 3),))]
    assert observed("a#b", query) == []


def test_tone_tier_is_directly_queryable():
    query = "on(feature:tone): [tone=top]"
    assert observed("a˥b˩", query) == [("˥", ((1, 2),))]
    assert observed("a˩b˩", query) == []


def test_projection_keeps_parse_order_and_exact_ranges():
    query = "on(tier:segment): a b"
    assert observed("a|b", query) == [("ab", ((0, 1), (2, 3)))]
    assert (
        observed(
            "a|b",
            "on(tier:segment,feature:break): a b",
        )
        == []
    )


def test_missing_empty_and_boolean_value_list_are_distinct():
    missing = "on(tier:segment): a{tone=none}"
    empty = 'on(tier:segment): a{tone=""}'
    assert observed("a", missing) == [("a", ((0, 1),))]
    assert observed("a", empty) == []
    assert observed("a˥", missing) == []
    assert observed("a˥", "on(tier:segment): a{tone=top|bottom}")


def test_missing_inside_a_value_list_matches_a_missing_cell():
    assert observed("a", "on(tier:segment): a{tone=none|top}") == [("a", ((0, 1),))]
    assert observed("a", 'on(tier:segment): a{tone=none|""}') == [("a", ((0, 1),))]
    assert observed("a˥", "on(tier:segment): a{tone=none|top}") == [("a˥", ((0, 2),))]


def test_on_unit_excludes_unwritten_outer_edges():
    assert list(find("kæt", "on(unit): #")) == list(find("kæt", "#")) == []
    matches = list(find("kæt", "on(unit): *"))
    assert [match.text for match in matches] == ["k", "æ", "t"]
    assert all(match.paths and match.output_ranges for match in matches)
    assert observed("kæt", "on(unit): t / _ #") == observed("kæt", "t / _ #")


def test_form_graph_materializes_one_linear_next_chain():
    form = ipakit.Form.parse("a˥|b")
    names = {relation.name.local_name for relation in form.graph.relation_declarations}
    assert "linear-next" in names
    positions = next(
        tier
        for tier in form.graph.tiers
        if tier.declaration.name.local_name == "position"
    )
    assert len(positions.items) == 6


def test_prosody_position_is_associated_with_its_host():
    graph = ipakit.Form.parse("a˥").graph
    associations = [
        relation
        for relation in graph.polyadic_relations
        if relation.declaration.local_name == "associates-with"
        and relation.declaration.namespace == "urn:ipakit:form:matching"
    ]
    assert len(associations) == 1


def test_matching_successor_is_not_auto_detected_as_containment():
    from scripts.containment_oracle import _NativeContainment

    adapter = _NativeContainment.build(ipakit.Form.parse("a˥").graph)
    assert "linear-next" not in {
        name.local_name for name, _traversal in adapter.traversals
    }


def test_slash_context_focuses_only_the_target():
    assert observed("ata", "on(tier:segment): t / a _ a") == [("t", ((1, 2),))]
    assert observed("ata", "on(tier:segment): t / a _ b") == []


def test_focusless_nullable_query_keeps_focus_refusal_first():
    query = CrossTierQuery(
        "focusless-nullable",
        ("tier:segment",),
        RepeatPattern(
            AtomPattern(Equals(_cell("selectors", "tier:segment"), (True,))),
            0,
            None,
        ),
    )
    with pytest.raises(ValueError) as caught:
        list(match_payloads(ipakit.Form.parse("kæt"), query))
    assert str(caught.value) == (
        "pattern has no focus; mark one with FocusPattern or write T / L _ R"
    )


def test_legacy_form_profile_upgrades_to_deterministic_matching_graph():
    from ipakit._form_profile import construct, restore

    inventory = ipakit.IPAFeatures()
    current = ipakit.Form.parse("a˥|b", inventory)
    source, spelling = restore(current.graph, inventory)
    legacy = construct(
        source, inventory, spelling, _profile_version=None, _matching=False
    )
    legacy_json = wire.dump_compact(legacy)
    restored = ipakit.Form.from_json(legacy_json, inventory)
    encoded = restored.to_json()
    assert ipakit.Form.from_json(encoded, inventory).to_json() == encoded
    assert "linear-next" in encoded
    assert observed(restored, "on(tier:segment): a b") == [("a˥b", ((0, 2), (3, 4)))]


def test_nonpositional_tier_selection_is_refused():
    with pytest.raises(QueryParseError, match="nonpositional"):
        list(find("a", "on(tier:delivery): *"))


def test_bare_selector_is_refused_when_tier_and_feature_names_collide(tmp_path):
    source = ipakit.load_ipa_features().xml_path.read_text(encoding="utf-8")
    anchor = '<value name="morph" short="mph" href="Morpheme"/>'
    assert source.count(anchor) == 1
    declared = source.replace(
        anchor, f'{anchor}\n      <value name="tone" short="tne"/>'
    )
    path = tmp_path / "ipa.xml"
    path.write_text(declared, encoding="utf-8")
    inventory = ipakit.IPAFeatures(xml_path=path)
    with pytest.raises(
        QueryParseError,
        match="selector 'tone' is ambiguous; qualify tier:tone or feature:tone",
    ):
        list(find("a", "on(tone): *", features=inventory))


def test_inventory_sequence_query_has_the_exact_set_refusal():
    with pytest.raises(
        ValueError,
        match=(
            "inventory queries are predicates over a set; sequence patterns "
            "require a Form"
        ),
    ):
        ipakit.IPAFeatures().phones_matching(  # type: ignore[arg-type]
            "on(tier:segment): p t"
        )


def test_legacy_noncanonical_spelling_offset_is_unchanged():
    form = ipakit.Form.of(ipakit.Form.parse("ab").units)
    object.__setattr__(form, "spelling", "a·b")
    match = next(find(form, "b"))
    assert (match.text, match.offset, match.output_ranges) == ("b", 1, ((2, 3),))


def test_cross_tier_noncanonical_spelling_uses_spelling_codepoints():
    form = ipakit.Form.of(ipakit.Form.parse("ab").units)
    object.__setattr__(form, "spelling", "a·b")
    match = next(find(form, "on(tier:segment): b"))
    assert (match.text, match.offset, match.output_ranges) == ("b", 1, ((2, 3),))


def test_declared_order_validation_is_cached_per_form_and_selector(monkeypatch):
    import tiergraph.match as match_module

    form = ipakit.Form.parse("a˥|b")
    query = CrossTierQuery.parse("on(tier:segment): a b", ipakit.IPAFeatures())
    original = match_module._declared_scope
    calls = 0

    def counted(graph, ordering):
        nonlocal calls
        calls += 1
        return original(graph, ordering)

    monkeypatch.setattr(match_module, "_declared_scope", counted)
    query.spans(form)
    query.focused(form)
    assert calls == 1
