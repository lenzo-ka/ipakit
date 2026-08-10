"""Lane K containment navigation and heterogeneous silence fixtures."""

from __future__ import annotations

from dataclasses import dataclass

from ipakit._navigation import (
    ancestor_routes,
    descendants_on_tier,
    direct_children,
    expand_phrase,
    expanded_leaves,
    lexical_projection,
    parents,
)
from ipakit._tiergraph import (
    Declarations,
    FeatureDeclaration,
    Graph,
    RelationDeclaration,
    TierDeclaration,
)
from ipakit._tiergraph_builder import EventHandle, GraphBuilder


@dataclass(frozen=True)
class Fixture:
    graph: Graph
    refs: dict[str, str]


def declarations() -> Declarations:
    return Declarations(
        tuple(
            TierDeclaration(name, frozenset({"label"}))
            for name in ("utterance", "phrase", "word", "syllable", "segment")
        ),
        (FeatureDeclaration("label"),),
        (RelationDeclaration("includes", containment=True, acyclic=True),),
    )


def phrase_fixture() -> Fixture:
    builder = GraphBuilder(declarations())
    handles: dict[str, EventHandle] = {}

    handles["utterance"] = builder.begin("utterance", {"label": "u"})
    handles["phrase"] = builder.begin("phrase", {"label": "p"})
    handles["initial_pause"] = builder.append_input_atom(
        "segment", {"label": "initial-pause"}
    )
    handles["word_one"] = builder.begin("word", {"label": "one"})
    handles["syllable_one"] = builder.begin("syllable", {"label": "one"})
    handles["one_a"] = builder.append_input_atom("segment", {"label": "one-a"})
    handles["one_b"] = builder.append_input_atom("segment", {"label": "one-b"})
    builder.end(handles["syllable_one"])
    builder.end(handles["word_one"])
    handles["medial_pause"] = builder.append_input_atom(
        "segment", {"label": "medial-pause"}
    )
    handles["word_two"] = builder.begin("word", {"label": "two"})
    handles["two_a"] = builder.append_input_atom("segment", {"label": "two-a"})
    builder.end(handles["word_two"])
    handles["final_pause"] = builder.append_input_atom(
        "segment", {"label": "final-pause"}
    )
    builder.end(handles["phrase"])
    builder.end(handles["utterance"])

    builder.contain(handles["utterance"], (handles["phrase"],), relation="includes")
    builder.contain(
        handles["phrase"],
        (
            handles["initial_pause"],
            handles["word_one"],
            handles["medial_pause"],
            handles["word_two"],
            handles["final_pause"],
        ),
        relation="includes",
    )
    builder.contain(handles["word_two"], (handles["two_a"],), relation="includes")
    # The same segment events also participate in a separate syllable analysis.
    builder.contain(
        handles["syllable_one"],
        (handles["one_a"], handles["one_b"]),
        relation="includes",
    )
    builder.contain(
        handles["word_one"], (handles["syllable_one"],), relation="includes"
    )
    builder.add_root(handles["utterance"])

    graph = builder.build()
    refs = {
        name: next(
            ref
            for ref in graph.event_references()
            if graph.resolve(ref).event.features["label"] == graph_label
            and graph.resolve(ref).tier == tier
        )
        for name, graph_label, tier in (
            ("utterance", "u", "utterance"),
            ("phrase", "p", "phrase"),
            ("initial_pause", "initial-pause", "segment"),
            ("word_one", "one", "word"),
            ("syllable_one", "one", "syllable"),
            ("one_a", "one-a", "segment"),
            ("one_b", "one-b", "segment"),
            ("medial_pause", "medial-pause", "segment"),
            ("word_two", "two", "word"),
            ("two_a", "two-a", "segment"),
            ("final_pause", "final-pause", "segment"),
        )
    }
    return Fixture(graph, refs)


def test_heterogeneous_phrase_projection_and_expansion() -> None:
    fixture = phrase_fixture()
    graph, ref = fixture.graph, fixture.refs

    assert direct_children(graph, ref["phrase"]) == (
        ref["initial_pause"],
        ref["word_one"],
        ref["medial_pause"],
        ref["word_two"],
        ref["final_pause"],
    )
    assert lexical_projection(graph, ref["phrase"], lexical_tier="word") == (
        ref["word_one"],
        ref["word_two"],
    )
    expected = (
        ref["initial_pause"],
        ref["one_a"],
        ref["one_b"],
        ref["medial_pause"],
        ref["two_a"],
        ref["final_pause"],
    )
    assert expanded_leaves(graph, ref["phrase"]) == expected
    assert expand_phrase(graph, ref["phrase"]) == expected


def test_deep_descendants_follow_declared_routes_without_tier_adjacency() -> None:
    fixture = phrase_fixture()
    graph, ref = fixture.graph, fixture.refs

    assert descendants_on_tier(graph, ref["utterance"], tier="segment") == (
        ref["initial_pause"],
        ref["one_a"],
        ref["one_b"],
        ref["medial_pause"],
        ref["two_a"],
        ref["final_pause"],
    )
    assert descendants_on_tier(graph, ref["phrase"], tier="syllable") == (
        ref["syllable_one"],
    )
    assert ref["initial_pause"] not in descendants_on_tier(
        graph, ref["phrase"], tier="syllable"
    )


def test_parent_and_ancestor_navigation_preserves_every_dag_route() -> None:
    builder = GraphBuilder(declarations())
    utterance = builder.begin("utterance", {"label": "u"})
    phrase = builder.begin("phrase", {"label": "p"})
    word = builder.begin("word", {"label": "w"})
    syllable = builder.begin("syllable", {"label": "s"})
    shared = builder.append_input_atom("segment", {"label": "shared"})
    builder.end(syllable)
    builder.end(word)
    builder.end(phrase)
    builder.end(utterance)
    builder.contain(utterance, (phrase,), relation="includes")
    builder.contain(phrase, (word,), relation="includes")
    builder.contain(word, (shared,), relation="includes")
    builder.contain(syllable, (shared,), relation="includes")
    graph = builder.build()
    by_label = {
        graph.resolve(ref).event.features["label"]: ref
        for ref in graph.event_references()
    }

    assert parents(graph, by_label["shared"]) == (by_label["s"], by_label["w"])
    assert ancestor_routes(graph, by_label["shared"]) == (
        (by_label["s"],),
        (by_label["w"], by_label["p"], by_label["u"]),
    )
    assert expanded_leaves(graph, by_label["w"]) == (by_label["shared"],)


def test_declared_child_sequence_never_resorts_by_clock() -> None:
    builder = GraphBuilder(declarations())
    phrase = builder.begin("phrase", {"label": "phrase"})
    clock_first = builder.append_input_atom("segment", {"label": "A"})
    clock_last = builder.append_input_atom("segment", {"label": "Z"})
    builder.end(phrase)
    builder.contain(phrase, (clock_last, clock_first), relation="includes")
    graph = builder.build()
    refs = {
        graph.resolve(ref).event.features["label"]: ref
        for ref in graph.event_references()
    }
    declared = (refs["Z"], refs["A"])

    assert direct_children(graph, refs["phrase"]) == declared
    assert expanded_leaves(graph, refs["phrase"]) == declared
    assert lexical_projection(graph, refs["phrase"], lexical_tier="segment") == declared
    assert expand_phrase(graph, refs["phrase"]) == declared


def test_shared_child_is_emitted_once_in_downward_walks() -> None:
    builder = GraphBuilder(declarations())
    phrase = builder.begin("phrase", {"label": "phrase"})
    first = builder.begin("word", {"label": "first"})
    builder.end(first)
    second = builder.begin("syllable", {"label": "second"})
    shared = builder.append_input_atom("segment", {"label": "shared"})
    builder.end(second)
    builder.end(phrase)
    builder.contain(phrase, (first, second), relation="includes")
    builder.contain(first, (shared,), relation="includes")
    builder.contain(second, (shared,), relation="includes")
    graph = builder.build()
    refs = {
        graph.resolve(ref).event.features["label"]: ref
        for ref in graph.event_references()
    }

    assert expanded_leaves(graph, refs["phrase"]) == (refs["shared"],)
    assert descendants_on_tier(graph, refs["phrase"], tier="segment") == (
        refs["shared"],
    )
