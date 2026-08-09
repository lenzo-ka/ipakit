from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from ipakit._tiergraph import (
    ClockNode,
    Declarations,
    EndpointKind,
    Event,
    EventGroup,
    FeatureDeclaration,
    Graph,
    GraphValidationError,
    RefinedSpan,
    Relation,
    RelationDeclaration,
    TierDeclaration,
    Timing,
)

FIXTURES = Path(__file__).parent / "fixtures"
TIERS = ("top", "group", "unit", "variant", "mark", "target")


def declarations() -> Declarations:
    kinds = frozenset({EndpointKind.EVENT})
    return Declarations(
        tuple(TierDeclaration(name, frozenset({"value", "class"})) for name in TIERS),
        (FeatureDeclaration("value"), FeatureDeclaration("class")),
        (
            RelationDeclaration("contains", acyclic=True),
            RelationDeclaration(
                "rewrites-to", allow_empty_target=True, target_arity=(0, None)
            ),
            RelationDeclaration(
                "inserts",
                source_kinds=frozenset({EndpointKind.COARSE_TICK}),
                target_kinds=kinds,
                source_arity=(1, 1),
            ),
            RelationDeclaration(
                "associates-with",
                source_kinds=frozenset({EndpointKind.EVENT, EndpointKind.REFINED_GAP}),
            ),
            RelationDeclaration("realized-by"),
            RelationDeclaration(
                "alternatives", ordered=False, choice=True, target_arity=(1, None)
            ),
            RelationDeclaration(
                "selects",
                ordered=False,
                source_arity=(1, 1),
                target_arity=(1, 1),
                member_of="alternatives",
            ),
        ),
    )


def event(**kwargs: object) -> Event:
    return Event({}, **kwargs)  # type: ignore[arg-type]


def node(gaps: int = 1, **groups: tuple[Event, ...]) -> ClockNode:
    ordered = tuple(EventGroup(name, groups[name]) for name in TIERS if name in groups)
    return ClockNode(gaps, ordered)


def graph(
    *clock: ClockNode,
    links: tuple[Relation, ...] = (),
    roots: tuple[str, ...] = (),
) -> Graph:
    return Graph(declarations(), clock or (ClockNode(),), links, roots)


def test_empty_graph_and_n_plus_one_clock_round_trip() -> None:
    empty = graph(ClockNode())
    assert Graph.from_data(declarations(), empty.to_data()) == empty
    three_spans = graph(
        node(unit=(event(),)),
        node(unit=(event(),)),
        node(unit=(event(),)),
        node(),
    )
    assert len(three_spans.clock) == 4
    assert (
        Graph.from_data(declarations(), three_spans.to_data()).to_data()
        == three_spans.to_data()
    )


def test_duration_and_physical_timing_contract() -> None:
    ordinary = event()
    point = event(duration=0)
    long = event(duration=3)
    timed_point = event(duration=0, timing=Timing(0.125, 0.0))
    assert ordinary.structural_duration == 1
    assert point.structural_duration == 0
    assert long.structural_duration == 3
    value = graph(
        node(unit=(ordinary, point, timed_point)), node(), node(), node()
    ).to_data()
    events = value["clock"][0]["unit"]  # type: ignore[index]
    assert "duration" not in events[0]  # type: ignore[operator]
    assert events[1]["duration"] == 0  # type: ignore[index]
    assert events[2]["timing"] == {"start": 0.125, "duration": 0.0}  # type: ignore[index]


@pytest.mark.parametrize(
    "bad_event, reason",
    [
        (event(duration=-1), "negative structural duration"),
        (event(timing=Timing(0.0, -0.1)), "negative physical duration"),
        (event(timing=Timing(math.inf, 0.1)), "non-finite physical timing"),
    ],
)
def test_invalid_durations_are_rejected(bad_event: Event, reason: str) -> None:
    with pytest.raises(GraphValidationError, match=reason):
        graph(node(unit=(bad_event,)), node())


def test_extent_past_final_tick_and_dual_extent_are_rejected() -> None:
    with pytest.raises(GraphValidationError, match="past final tick"):
        graph(node(unit=(event(duration=2),)), node())
    with pytest.raises(GraphValidationError, match="mutually exclusive"):
        event(duration=0, span=RefinedSpan("/clock/0", "/clock/0"))


def test_every_boundary_gap_round_trips_without_adding_ticks() -> None:
    for refiners in range(6):
        current = graph(node(), node(refiners + 1), node())
        assert len(current.clock) == 3
        for gap in range(refiners + 1):
            pointer = f"/clock/1/gaps/{gap}"
            if refiners:
                assert current.position(pointer).gap == gap
                assert current.canonical_endpoint(pointer) == pointer
            else:
                assert current.canonical_endpoint(pointer) == "/clock/1"


def test_refined_span_order_and_canonical_endpoints() -> None:
    valid = event(span=RefinedSpan("/clock/0", "/clock/1/gaps/1"))
    current = graph(node(unit=(valid,)), node(3), node())
    assert current.position("/clock/1/gaps/2").gap == 2
    with pytest.raises(GraphValidationError, match="must name a gap"):
        graph(
            node(),
            node(2, unit=(event(span=RefinedSpan("/clock/1", "/clock/2")),)),
            node(),
        )
    with pytest.raises(GraphValidationError, match="precedes start"):
        graph(
            node(),
            node(
                3,
                unit=(event(span=RefinedSpan("/clock/1/gaps/2", "/clock/1/gaps/1")),),
            ),
            node(),
        )
    with pytest.raises(GraphValidationError, match="gap does not belong"):
        current.resolve("/clock/1/gaps/3")


def test_pointer_escaping_resolution_and_failures() -> None:
    declared = Declarations(
        (TierDeclaration("a/b~c"),), (), declarations().relations, closed=True
    )
    current = Graph(
        declared,
        (ClockNode(groups=(EventGroup("a/b~c", (event(),)),)), ClockNode()),
    )
    assert current.event_references() == ("/clock/0/a~1b~0c/0",)
    assert current.resolve(current.event_references()[0]).event is not None
    for pointer in ("clock/0", "/clock/x", "/clock/9", "/clock/0/~2/0"):
        with pytest.raises(GraphValidationError):
            current.resolve(pointer)


def test_endpoint_kinds_and_relation_constraints() -> None:
    current = graph(
        node(unit=(event(),), variant=(event(), event())),
        node(2),
        links=(
            Relation(("/clock/0",), "inserts", ("/clock/0/variant/0",)),
            Relation(
                ("/clock/1/gaps/1",),
                "associates-with",
                ("/clock/0/unit/0",),
            ),
        ),
    )
    assert current.resolve("/clock/0").kind is EndpointKind.COARSE_TICK
    with pytest.raises(GraphValidationError, match="coarse-tick"):
        graph(
            node(unit=(event(),), variant=(event(),)),
            node(),
            links=(Relation(("/clock/0/unit/0",), "inserts", ("/clock/0/variant/0",)),),
        )


def test_relation_arity_empty_tiers_and_undeclared_values() -> None:
    restricted = Declarations(
        declarations().tiers,
        declarations().features,
        (
            RelationDeclaration(
                "r",
                source_tiers=frozenset({"unit"}),
                target_tiers=frozenset({"target"}),
                source_arity=(1, 1),
                target_arity=(0, 1),
                allow_empty_target=True,
            ),
        ),
    )
    base = (node(unit=(event(),), target=(event(),)), node())
    Graph(restricted, base, (Relation(("/clock/0/unit/0",), "r", ()),))
    with pytest.raises(GraphValidationError, match="target tier"):
        Graph(
            restricted,
            base,
            (Relation(("/clock/0/unit/0",), "r", ("/clock/0/unit/0",)),),
        )
    with pytest.raises(GraphValidationError, match="undeclared relation"):
        graph(*base, links=(Relation(("/clock/0/unit/0",), "unknown", ()),))


def choice_graph(links: tuple[Relation, ...]) -> Graph:
    return graph(node(top=(event(),), variant=(event(), event())), node(), links=links)


def test_choice_validation() -> None:
    source = "/clock/0/top/0"
    first, second = "/clock/0/variant/0", "/clock/0/variant/1"
    choice_graph((Relation((source,), "alternatives", (first, second)),))
    choice_graph(
        (
            Relation((source,), "alternatives", (first, second)),
            Relation((source,), "selects", (second,)),
        )
    )
    bad = (
        ((Relation((source,), "alternatives", (first, first)),), "distinct"),
        (
            (
                Relation((source,), "alternatives", (first,)),
                Relation((source,), "alternatives", (second,)),
            ),
            "at most one alternatives",
        ),
        (
            (
                Relation((source,), "alternatives", (first, second)),
                Relation((source,), "selects", (first,)),
                Relation((source,), "selects", (second,)),
            ),
            "at most one selects",
        ),
        (
            (
                Relation((source,), "alternatives", (first,)),
                Relation((source,), "selects", (second,)),
            ),
            "not a member",
        ),
        ((Relation((source,), "selects", (first,)),), "owns no alternatives"),
    )
    for links, reason in bad:
        with pytest.raises(GraphValidationError, match=reason):
            choice_graph(links)


def test_heterogeneous_containment_traversal_and_cycles() -> None:
    parent, subgroup = "/clock/0/top/0", "/clock/0/group/0"
    first, second = "/clock/0/unit/0", "/clock/1/unit/0"
    current = graph(
        node(top=(event(),), group=(event(),), unit=(event(),)),
        node(unit=(event(),)),
        node(),
        links=(
            Relation((parent,), "contains", (first, subgroup)),
            Relation((subgroup,), "contains", (second,)),
        ),
        roots=(parent,),
    )
    assert current.direct_children(parent) == (first, subgroup)
    assert current.descendants(parent, "unit") == (first, second)
    assert current.leaves(parent) == (first, second)
    assert current.parents(second) == (subgroup,)
    assert current.ancestors(second) == (subgroup, parent)
    with pytest.raises(GraphValidationError, match="cycle"):
        graph(
            node(top=(event(),), group=(event(),)),
            node(),
            links=(
                Relation((parent,), "contains", (subgroup,)),
                Relation((subgroup,), "contains", (parent,)),
            ),
        )


def test_roots_must_resolve_to_events() -> None:
    with pytest.raises(GraphValidationError, match="root"):
        graph(node(), roots=("/clock/0",))
    with pytest.raises(GraphValidationError, match="dangling"):
        graph(node(), roots=("/clock/0/unit/0",))


def test_immutable_structures_and_input_owned_gaps() -> None:
    features = {"value": "x"}
    item = Event(features)
    features["value"] = "changed"
    current = graph(node(3, unit=(item,)), node())
    assert item.features["value"] == "x"
    with pytest.raises(TypeError):
        item.features["value"] = "no"  # type: ignore[index]
    assert current.clock[0].gap_count == 3
    assert len(current.clock[0].groups[0].events) == 1


def test_all_lane_a_fixture_cases_are_accounted_for() -> None:
    """Keep profile pins visible without teaching their vocabulary to the kernel."""
    exercised = {
        "n-plus-one-clock",
        "final-tick-insertion-anchor",
        "clock-consumption",
        "builder-lane-order",
        "chained-phantom-scan-order",
        "a-dot-dot-b-mora",
        "boundary-zero-whitespace-units",
        "inserted-site",
        "deleted-boundary-run-site",
        "interval-crosses-tier-boundary",
        "coarse-unrefined",
        "gap-zero-refined",
        "gap-interior-refined",
        "gap-k-refined",
        "gap-zero-unrefined-alias",
        "coarse-refined-span-endpoint",
        "reversed-refined-span",
        "gap-outside-named-tick",
        "choice-no-selection",
        "choice-one-selection",
        "duplicate-candidate",
        "multiple-alternatives-links",
        "multiple-selects-links",
        "selection-outside-candidates",
        "selects-without-alternatives",
        "heterogeneous-phrase-contains-silence",
        "exact-syllable-host-count",
        "exact-nucleus-host-count",
        "slot-host-count-mismatch",
        "nucleus-stress-associated-with-later-syllable",
        "ordinary-one-span-omits-duration",
        "point-writes-zero-duration",
        "multi-span-writes-duration",
        "refined-span-excludes-duration",
        "physical-time-is-independent",
        "timed-point-distinct-from-untimed",
        "input-silence-consumes-span",
        "derived-silence-is-phantom",
        "tick-source-insertion",
        "event-source-rewrite",
        "gap-endpoint-association",
        "wrong-endpoint-kind",
    }
    found: set[str] = set()
    index = json.loads((FIXTURES / "index.json").read_text())
    for name in index["fixtures"]:
        data = json.loads((FIXTURES / name).read_text())
        found.update(case["id"] for case in data.get("cases", ()))
    assert found == exercised


def test_kernel_contains_no_profile_vocabulary() -> None:
    source = (Path(__file__).parents[2] / "ipakit" / "_tiergraph.py").read_text()
    forbidden = ("phoneset", "renderer", "rule-engine", "syllable", "phoneme")
    assert not any(word in source for word in forbidden)
