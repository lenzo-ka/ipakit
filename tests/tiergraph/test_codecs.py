from __future__ import annotations

import pytest
from ipakit import Form, IPAFeatures
from ipakit._codecs import (
    DeliverySelectionError,
    RenderLane,
    RenderProfile,
    apply_signature,
    render_delivery,
    render_graph,
    render_pinyin,
)
from ipakit._ipa_graph import declarations, parse_signature, render_signature
from ipakit._tiergraph import (
    Declarations,
    FeatureDeclaration,
    RelationDeclaration,
    TierDeclaration,
)
from ipakit._tiergraph_builder import GraphBuilder


def test_exact_and_canonical_spelling_are_distinct_contracts() -> None:
    form = Form.parse("kæt.ˈ.dɒɡ")
    assert form.to_ipa() == "kæt.ˈ.dɒɡ"
    assert form.to_ipa("exact") == "kæt.ˈ.dɒɡ"
    assert form.to_ipa("canonical") == "kæt..ˈdɒɡ"


def test_renderer_only_emits_codec_declared_tiers() -> None:
    declared = Declarations(
        (
            TierDeclaration("atoms", frozenset({"spelling"})),
            TierDeclaration("gesture", frozenset({"spelling"})),
        ),
        (FeatureDeclaration("spelling"),),
        (),
    )
    builder = GraphBuilder(declared)
    builder.append_input_atom("atoms", {"spelling": "a"})
    builder.add_event("gesture", 0, {"spelling": "INVENTED"}, duration=0)
    graph = builder.build()
    assert render_graph(graph, RenderProfile((RenderLane("atoms", "spelling"),))) == "a"


def test_pinyin_tone_surface_does_not_move_semantic_attachment() -> None:
    declared = Declarations(
        (
            TierDeclaration("syllable", frozenset({"spelling"})),
            TierDeclaration("tone", frozenset({"value"})),
        ),
        (FeatureDeclaration("spelling"), FeatureDeclaration("value")),
        (
            RelationDeclaration(
                "associates-with",
                source_tiers=frozenset({"tone"}),
                target_tiers=frozenset({"syllable"}),
            ),
        ),
    )
    builder = GraphBuilder(declared)
    syllable = builder.append_input_atom("syllable", {"spelling": "shui"})
    tone = builder.add_event("tone", 0, {"value": 3}, duration=0)
    builder.relate((tone,), "associates-with", (syllable,))
    graph = builder.build()
    assert render_pinyin(graph) == "shuǐ"
    assert graph.relations[0].targets == ("/clock/0/syllable/0",)


def _delivery_graph(stress: tuple[str, ...]):
    builder = GraphBuilder(declarations(IPAFeatures()))
    hosts = tuple(
        builder.append_input_atom("syllable", {"spelling": value})
        for value in ("you", "were", "en", "gaged")
    )
    words = (
        builder.add_event("word", 0, {"spelling": "you"}, duration=1),
        builder.add_event("word", 1, {"spelling": "were"}, duration=1),
        builder.add_event("word", 2, {"spelling": "engaged"}, duration=2),
    )
    for word, children in zip(
        words, ((hosts[0],), (hosts[1],), hosts[2:]), strict=True
    ):
        builder.contain(word, children)
    for tick, level, glyph in (
        (1, "word", "#"),
        (2, "word", "#"),
        (4, "utterance", "‖"),
    ):
        builder.add_event(
            "boundary", tick, {"level": level, "symbol": glyph}, duration=0
        )
    analysis = builder.add_event(
        "analysis", 0, {"value": "licensed readings"}, duration=0
    )
    delivery = builder.add_event("delivery", 0, {"value": "reading"}, duration=0)
    builder.relate((analysis,), "alternatives", (delivery,))
    builder.relate((analysis,), "selects", (delivery,))
    prosody = []
    for host, value in zip(hosts, stress, strict=True):
        event = builder.add_event("prosody", 0, {"stress": value}, duration=0)
        builder.relate((event,), "associates-with", (host,))
        prosody.append(event)
    builder.contain(delivery, prosody)
    return builder.build(), hosts


def test_one_analysis_projects_into_all_three_notations_without_base_mutation() -> None:
    graph, _ = _delivery_graph(("primary", "none", "none", "primary"))
    before = graph.to_data()
    rendered = render_delivery(graph)
    assert rendered.prosodic_signature == "ˈ#.#.ˈ‖"
    assert rendered.segmental_signature == "ˈyou # .were # .enˈgaged ‖"
    assert rendered.orthographic_delivery == "YOU were enGAGED"
    assert graph.to_data() == before


def test_delivery_refuses_unselected_mutually_exclusive_alternatives() -> None:
    graph, _ = _delivery_graph(("primary", "none", "none", "primary"))
    relations = tuple(r for r in graph.relations if r.name != "selects")
    graph = type(graph)(graph.declarations, graph.clock, relations)
    candidate = next(r.targets[0] for r in relations if r.name == "alternatives")
    with pytest.raises(
        DeliverySelectionError,
        match=rf"delivery alternatives require a selection; candidates are \['{candidate}'\]",
    ):
        render_delivery(graph)


@pytest.mark.parametrize("selected", [object(), "stray", "/clock/0/analysis/0"])
def test_delivery_refuses_selection_that_is_not_a_candidate(selected: object) -> None:
    graph, _ = _delivery_graph(("primary", "none", "none", "primary"))
    candidate = next(r.targets[0] for r in graph.relations if r.name == "alternatives")
    with pytest.raises(DeliverySelectionError) as caught:
        render_delivery(graph, selected=selected)
    assert str(caught.value).endswith(
        f"is not a candidate; candidates are {[candidate]!r}"
    )


def test_signature_round_trip_and_edit_provenance() -> None:
    inventory = IPAFeatures()
    signature = parse_signature(".ˈˌ#", inventory)
    assert render_signature(signature, inventory) == ".ˈˌ#"
    graph, handles = _delivery_graph(("none", "primary", "secondary", "none"))
    host_refs = tuple(f"/clock/{index}/syllable/0" for index in range(4))
    edited = apply_signature(graph, ".ˈˌ.# #‖".replace(" ", ""), inventory, host_refs)
    assert len(edited.hosts) == 4
    assert all(
        any(
            relation.name == "associates-with" and ref in relation.sources
            for relation in edited.graph.relations
        )
        for ref in edited.created
        if "/prosody/" in ref
    )
    assert any(relation.name == "derived-from" for relation in edited.graph.relations)
    assert edited.graph.declarations.tier("signature") is None
    with pytest.raises(ValueError, match="slot count 3 does not equal host count 4"):
        apply_signature(graph, ".ˈˌ", inventory, host_refs)
