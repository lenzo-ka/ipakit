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


def test_every_event_is_defined_once_and_every_relation_is_labelled() -> None:
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
    assert dot.count("[shape=box, label=") == len(graph.event_references())
    for reference in graph.event_references():
        identifier = ipakit.tiergraph_dot._event_id(reference)
        assert dot.count(f"{identifier} [shape=box") == 1
    for relation in graph.relations:
        assert dot.count(f'label="{relation.name}"') >= 1


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
        r"^  (\S+) -> (tier_label_\S+) \[style=invis, weight=100\];$", dot, re.M
    )

    assert ordering == list(zip(["clock_0", *labels[:-1]], labels, strict=True))


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
