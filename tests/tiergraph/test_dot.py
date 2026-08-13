from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import ipakit
import pytest
from ipakit._tiergraph import (
    ClockNode,
    Declarations,
    Event,
    EventGroup,
    Graph,
    Relation,
    RelationDeclaration,
    TierDeclaration,
)

ROOT = Path(__file__).parents[2]
FIGURE = ROOT / "docs" / "figures" / "perhaps-i-am-a-bad-man.dot"


def _example() -> ipakit.Form:
    sys.path.insert(0, str(ROOT / "scripts"))
    from tiergraph_example import build_example

    return build_example()


def test_dot_is_byte_identical_in_process_and_across_hash_seeds() -> None:
    form = _example()
    assert form.to_dot().encode() == form.to_dot().encode()
    program = (
        "import sys; sys.path.insert(0, 'scripts'); "
        "from tiergraph_example import build_example; "
        "sys.stdout.write(build_example().to_dot())"
    )
    outputs = []
    for seed in ("0", "12345", "999"):
        outputs.append(
            subprocess.run(
                [sys.executable, "-c", program],
                cwd=ROOT,
                env={**os.environ, "PYTHONHASHSEED": seed},
                check=True,
                capture_output=True,
            ).stdout
        )
    assert outputs == [form.to_dot().encode()] * 3


def test_every_event_is_defined_once_triggered_and_every_relation_is_exact() -> None:
    declared = Declarations(
        (TierDeclaration("first"), TierDeclaration("second")),
        (),
        (RelationDeclaration("links"), RelationDeclaration("answers")),
    )
    graph = Graph(
        declared,
        (
            ClockNode(groups=(EventGroup("first", (Event({}), Event({}))),)),
            ClockNode(groups=(EventGroup("second", (Event({}),)),)),
            ClockNode(),
        ),
        (
            Relation(("/clock/0/first/0",), "links", ("/clock/1/second/0",)),
            Relation(("/clock/0/first/1",), "answers", ("/clock/1/second/0",)),
        ),
    )
    dot = ipakit.tiergraph_dot.dumps(graph)
    assert dot.count("[shape=box, group=") == len(graph.event_references())
    for reference in graph.event_references():
        identifier = ipakit.tiergraph_dot._event_id(reference)
        assert dot.count(f"{identifier} [shape=box") == 1
        assert (
            len(
                re.findall(
                    rf"^  clock_\S+ -> {re.escape(identifier)} "
                    r'\[color="#2f6f9f", penwidth=1\.35',
                    dot,
                    re.M,
                )
            )
            == 1
        )
    for relation in graph.relations:
        for source in relation.sources:
            for target in relation.targets:
                edge = (
                    f"{ipakit.tiergraph_dot._endpoint_id(graph, source)} -> "
                    f"{ipakit.tiergraph_dot._endpoint_id(graph, target)} "
                    f'[label="{relation.name}"'
                )
                assert dot.count(edge) == 1


def test_tier_rows_are_exactly_the_tiers_with_events_in_declaration_order() -> None:
    form = _example()
    graph = form._graph
    event_tiers = {
        group.tier
        for clock_node in graph.clock
        for group in clock_node.groups
        if group.events
    }
    expected = [
        tier.name for tier in graph.declarations.tiers if tier.name in event_tiers
    ]

    assert re.findall(r"^  subgraph tier_([^ ]+) \{$", form.to_dot(), re.M) == expected
    assert re.findall(
        r"^  subgraph tier_([^ ]+) \{$",
        form.to_dot(include_empty_tiers=True),
        re.M,
    ) == [tier.name for tier in graph.declarations.tiers]


def test_clock_and_populated_tier_rows_are_ordered_vertically() -> None:
    dot = _example().to_dot()
    labels = re.findall(r"^    (tier_label_\S+) \[shape=plaintext", dot, re.M)
    ordering = re.findall(
        r'^  (\S+) -> (tier_label_\S+) \[dir=none, color="#333333", '
        r"penwidth=2\.4, weight=100\];$",
        dot,
        re.M,
    )

    assert ordering == list(
        zip(["score_start_clock", *labels[:-1]], labels, strict=True)
    )


def test_successive_events_in_each_tier_have_visible_quiet_links() -> None:
    form = _example()
    dot = form.to_dot()
    for tier in form._graph.declarations.tiers:
        references = [
            reference
            for reference in form._graph.event_references()
            if form._graph.resolve(reference).tier == tier.name
        ]
        for left, right in zip(references, references[1:], strict=False):
            edge = (
                f"{ipakit.tiergraph_dot._event_id(left)} -> "
                f"{ipakit.tiergraph_dot._event_id(right)} "
                '[color="#888888", penwidth=0.8, arrowsize=0.55, constraint=false];'
            )
            assert dot.count(edge) == 1


def test_rendered_lanes_are_distinct_and_events_align_with_trigger_ticks() -> None:
    if shutil.which("dot") is None:
        pytest.skip("graphviz dot is not installed")
    plain = subprocess.run(
        ["dot", "-Tplain", FIGURE], check=True, text=True, capture_output=True
    ).stdout
    nodes = {
        fields[1]: (float(fields[2]), float(fields[3]))
        for line in plain.splitlines()
        if line.startswith("node ")
        for fields in (line.split(),)
    }
    labels = [
        "score_start_clock",
        *re.findall(
            r"^    (tier_label_\S+) \[shape=plaintext", _example().to_dot(), re.M
        ),
    ]
    lane_y = [nodes[label][1] for label in labels]
    assert all(upper > lower for upper, lower in zip(lane_y, lane_y[1:], strict=False))
    for reference in _example()._graph.event_references():
        start_id, _ = ipakit.tiergraph_dot._event_position_ids(
            _example()._graph, reference
        )
        assert nodes[ipakit.tiergraph_dot._event_id(reference)][0] == pytest.approx(
            nodes[start_id][0], abs=0.0001
        )


def test_blank_spelling_falls_back_to_a_visible_event_label() -> None:
    assert (
        ipakit.tiergraph_dot._event_label("boundary", {"spelling": " "}) == "boundary"
    )


def test_clock_spine_is_strictly_ascending() -> None:
    dot = _example().to_dot()
    spine = dot.split("// The clock spine is the total order.", 1)[1].split("  }", 1)[0]
    nodes = re.findall(r"^    (clock_\d+(?:_gap_\d+)?) \[shape=circle", spine, re.M)
    expected = [
        (f"clock_{tick}" if node.gap_count == 1 else f"clock_{tick}_gap_{gap}")
        for tick, node in enumerate(_example()._graph.clock)
        for gap in range(node.gap_count)
    ]
    assert nodes == expected
    edges = re.findall(r"^    (clock_\S+) -> (clock_\S+) \[weight=100\]", spine, re.M)
    assert edges == list(zip(expected, expected[1:], strict=False))


def test_example_is_current_and_graphviz_parses_it(tmp_path: Path) -> None:
    assert FIGURE.read_text(encoding="utf-8") == _example().to_dot()
    if shutil.which("dot") is None:
        pytest.skip("graphviz dot is not installed")
    subprocess.run(["dot", "-Tsvg", FIGURE, "-o", tmp_path / "figure.svg"], check=True)


def test_example_is_one_phrase_and_a_is_reduced_without_stress() -> None:
    graph = _example()._graph
    utterance = graph.roots[0]
    assert graph.resolve(utterance).tier == "utterance"
    assert len(graph.direct_children(utterance, "phrase")) == 1
    phrase = graph.direct_children(utterance, "phrase")[0]
    words = graph.direct_children(phrase, "word")
    assert [graph.resolve(word).event.features["spelling"] for word in words] == [
        "perhaps",
        "I",
        "am",
        "a",
        "bad",
        "man",
    ]
    am_word = graph.resolve(words[2]).event
    assert am_word is not None and am_word.features["prominence"] == "emphatic"
    assert 'label="am\\nprominence: emphatic"' in _example().to_dot()
    a_word = words[3]
    segments = graph.direct_children(a_word, "segment")
    assert len(segments) == 1
    event = graph.resolve(segments[0]).event
    assert event is not None and event.features["spelling"] == "ə"
    assert "stress" not in event.features
    assert not any(relation.name == "derived-from" for relation in graph.relations)


def test_cli_renders_ipa_and_form_json(tmp_path: Path) -> None:
    raw = subprocess.run(
        [sys.executable, "-m", "ipakit", "tiergraph", "kæt"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    ).stdout
    assert raw == ipakit.read("kæt").to_dot()
    source = tmp_path / "form.json"
    source.write_text(_example().to_json(), encoding="utf-8")
    restored = subprocess.run(
        [sys.executable, "-m", "ipakit", "tiergraph", "--from-json", str(source)],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    ).stdout
    assert restored == ipakit.read_json(source.read_text()).to_dot()
