from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from ipakit import IPAFeatures
from ipakit._ipa_graph import assign_signature
from ipakit._ipa_graph import declarations as ipa_declarations
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
            RelationDeclaration("contains", acyclic=True, containment=True),
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
    assert Graph.from_data(declared, current.to_data()).event_references() == (
        "/clock/0/a~1b~0c/0",
    )
    for pointer in ("clock/0", "/clock/x", "/clock/9", "/clock/0/~2/0"):
        with pytest.raises(GraphValidationError):
            current.resolve(pointer)


def test_structural_tier_names_are_reserved() -> None:
    with pytest.raises(GraphValidationError, match="reserved"):
        Declarations((TierDeclaration("gaps"),), (), ())


def test_nested_feature_mappings_serialize_canonically() -> None:
    left = Event({"value": {"b": {"d": 4, "c": 3}, "a": 1}})
    right = Event({"value": {"a": 1, "b": {"c": 3, "d": 4}}})
    left_graph = graph(node(unit=(left,)), node())
    right_graph = graph(node(unit=(right,)), node())
    assert left_graph == right_graph
    assert json.dumps(left_graph.to_data()) == json.dumps(right_graph.to_data())


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


def test_member_of_declaration_requires_exactly_one_target() -> None:
    with pytest.raises(GraphValidationError, match="target arity 1"):
        RelationDeclaration("selects", member_of="alternatives")


def test_containment_declaration_requires_acyclic() -> None:
    with pytest.raises(GraphValidationError, match="containment.*acyclic"):
        RelationDeclaration("contains", containment=True)


@pytest.mark.parametrize(
    "relation",
    [
        Relation(("/clock/0/top/0",), "contains", ("/clock/0/unit/0",)),
        Relation(("/clock/1",), "inserts", ("/clock/0/unit/0",)),
    ],
)
def test_duplicate_relations_are_rejected_at_construction(relation: Relation) -> None:
    with pytest.raises(GraphValidationError, match="duplicate relation"):
        graph(
            node(top=(event(),), unit=(event(),)),
            node(),
            links=(relation, relation),
        )


def test_containment_source_has_one_ordered_sequence() -> None:
    source = "/clock/0/top/0"
    with pytest.raises(GraphValidationError, match=f"containment source {source}"):
        graph(
            node(top=(event(),), unit=(event(), event())),
            node(),
            links=(
                Relation((source,), "contains", ("/clock/0/unit/1",)),
                Relation((source,), "contains", ("/clock/0/unit/0",)),
            ),
        )


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


def test_containment_traversal_uses_declared_property_across_relations() -> None:
    declared = Declarations(
        declarations().tiers,
        declarations().features,
        (
            RelationDeclaration("owns", containment=True, acyclic=True),
            RelationDeclaration("groups", containment=True, acyclic=True),
        ),
    )
    parent, middle, child = (
        "/clock/0/top/0",
        "/clock/0/group/0",
        "/clock/0/unit/0",
    )
    current = Graph(
        declared,
        (node(top=(event(),), group=(event(),), unit=(event(),)), node()),
        (
            Relation((parent,), "owns", (middle,)),
            Relation((middle,), "groups", (child,)),
        ),
    )
    assert current.descendants(parent) == (middle, child)
    assert current.parents(child) == (middle,)


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


PROFILE_FIXTURE_OWNERS = {
    # Lane C owns input interpretation, compatibility coordinates, and builders.
    "clock-consumption": "C",
    "builder-lane-order": "C",
    "chained-phantom-scan-order": "C",
    "a-dot-dot-b-mora": "C",
    "boundary-zero-whitespace-units": "C",
    "inserted-site": "C",
    "deleted-boundary-run-site": "C",
    "interval-crosses-tier-boundary": "C",
    # Lane D owns signature parsing, host assignment, and prosodic semantics.
    "prosodic-deliveries": "D",
    "exact-syllable-host-count": "D",
    "exact-nucleus-host-count": "D",
    "slot-host-count-mismatch": "D",
    "nucleus-stress-associated-with-later-syllable": "D",
}


def _fixture_cases() -> list[dict[str, object]]:
    index = json.loads((FIXTURES / "index.json").read_text())
    result = []
    for name in index["fixtures"]:
        data = json.loads((FIXTURES / name).read_text())
        if "cases" in data:
            result.extend(data["cases"])
        else:
            result.append({"id": "prosodic-deliveries", **data})
    return result


@pytest.mark.parametrize("case", _fixture_cases(), ids=lambda case: str(case["id"]))
def test_lane_a_fixture_kernel_verdicts(case: dict[str, object]) -> None:
    """Execute kernel pins and explicitly enumerate profile-owned exclusions."""
    case_id = str(case["id"])
    if PROFILE_FIXTURE_OWNERS.get(case_id) == "D":
        expected = case["expected"]
        assert isinstance(expected, dict)
        inventory = IPAFeatures()
        if case_id == "prosodic-deliveries":
            assert expected["verdict"] == "valid"
            deliveries = case["deliveries"]
            assert isinstance(deliveries, list)
            stress = {value for delivery in deliveries for value in delivery["stress"]}
            segment_events = tuple(
                Event({"value": word}) for word in case["shared_input"]["words"]
            )  # type: ignore[index,union-attr]
            segment_refs = tuple(
                f"/clock/{i}/segment/0" for i in range(len(segment_events))
            )
            slot_hosts = segment_refs + (segment_refs[-1],)
            prosody_events = tuple(
                tuple(Event({"stress": value}) for value in delivery["stress"])
                for delivery in deliveries
            )
            associations = tuple(
                Relation(
                    (f"/clock/{slot}/prosody/{delivery_index}",),
                    "associates-with",
                    (slot_hosts[slot],),
                )
                for delivery_index in range(len(deliveries))
                for slot in range(len(slot_hosts))
            )
            current = Graph(
                ipa_declarations(inventory),
                (
                    ClockNode(
                        groups=(
                            EventGroup("segment", (segment_events[0],)),
                            EventGroup(
                                "prosody",
                                tuple(events[0] for events in prosody_events),
                            ),
                            EventGroup(
                                "delivery",
                                tuple(
                                    Event({"value": delivery["id"]})
                                    for delivery in deliveries
                                ),
                            ),
                            EventGroup("analysis", (Event({"value": "choice"}),)),
                        )
                    ),
                    ClockNode(
                        groups=(
                            EventGroup("segment", (segment_events[1],)),
                            EventGroup(
                                "prosody",
                                tuple(events[1] for events in prosody_events),
                            ),
                        )
                    ),
                    ClockNode(
                        groups=(
                            EventGroup("segment", (segment_events[2],)),
                            EventGroup(
                                "prosody",
                                tuple(events[2] for events in prosody_events),
                            ),
                        )
                    ),
                    ClockNode(
                        groups=(
                            EventGroup(
                                "prosody",
                                tuple(events[3] for events in prosody_events),
                            ),
                        )
                    ),
                    ClockNode(),
                ),
                (
                    Relation(
                        ("/clock/0/analysis/0",),
                        "alternatives",
                        tuple(f"/clock/0/delivery/{i}" for i in range(3)),
                    ),
                    *associations,
                ),
            )
            assert case["shared_input"]["segmental_material_duplicated"] is False  # type: ignore[index]
            assert stress == set(expected["stress_values_covered"])
            assigned_hosts = tuple(
                tuple(
                    host
                    for host, _ in assign_signature(
                        delivery["house_signature"],
                        slot_hosts,
                        inventory,
                    )
                )
                for delivery in deliveries
            )
            assert all(hosts == slot_hosts for hosts in assigned_hosts)
            referenced_segments = tuple(
                tuple(current.resolve(host).event for host in hosts)
                for hosts in assigned_hosts
            )
            assert all(
                all(
                    actual is shared
                    for actual, shared in zip(
                        events, referenced_segments[0], strict=True
                    )
                )
                for events in referenced_segments[1:]
            )
        else:
            hosts = tuple(case["hosts"]) if "hosts" in case else ()
            if expected["verdict"] == "rejected-with-reason":
                with pytest.raises(ValueError, match=str(expected["reason"])):
                    assign_signature(str(case["signature"]), hosts, inventory)
            elif case_id == "nucleus-stress-associated-with-later-syllable":
                assert expected["verdict"] == "valid"
                current = Graph(
                    ipa_declarations(inventory),
                    (
                        ClockNode(groups=(EventGroup("syllable", (event(),)),)),
                        ClockNode(
                            groups=(
                                EventGroup("segment", (event(),)),
                                EventGroup("prosody", (Event({"stress": "primary"}),)),
                            )
                        ),
                        ClockNode(),
                    ),
                    (
                        Relation(
                            ("/clock/1/prosody/0",),
                            "associates-with",
                            ("/clock/1/segment/0", "/clock/0/syllable/0"),
                        ),
                    ),
                )
                fixture_relation = case["links"][0]
                relation = current.relations[0]
                assert list(relation.sources) == fixture_relation[0]
                assert relation.name == fixture_relation[1]
                assert list(relation.targets) == fixture_relation[2]
                assert relation.sources == (case["stress_event"],)
                assert case["original_host"] in relation.targets
                assert case["later_host"] in relation.targets
                assert len(current.relations) == expected["stress_facts"]
                assert expected["moved_or_duplicated"] is False
            else:
                assigned = assign_signature(str(case["signature"]), hosts, inventory)
                assert len(assigned) == expected["slots"] == expected["hosts"]
        return
    if case_id in PROFILE_FIXTURE_OWNERS:
        assert PROFILE_FIXTURE_OWNERS[case_id] in {"C", "D"}
        return
    expected = case["expected"]  # type: ignore[index]
    assert isinstance(expected, dict)

    if case_id == "n-plus-one-clock":
        current = graph(*(node(unit=(event(),)) for _ in case["input_atoms"]), node())  # type: ignore[union-attr]
        assert len(current.to_data()["clock"]) == expected["clock_entries"]  # type: ignore[arg-type]
        return
    if case_id == "final-tick-insertion-anchor":
        current = graph(
            node(),
            node(),
            node(),
            node(target=(event(duration=0),)),
            links=(Relation(("/clock/3",), "inserts", ("/clock/3/target/0",)),),
        )
        assert current.resolve(str(expected["anchor"])).kind is EndpointKind.COARSE_TICK
        return
    if "input" in case or "span" in case:
        gaps = len(case.get("refiners", {}).get("1", ())) + 1  # type: ignore[union-attr]
        if "span" in case:
            raw_span = case["span"]
            assert isinstance(raw_span, dict)

            def build() -> object:
                return graph(
                    node(),
                    node(
                        gaps,
                        unit=(
                            event(
                                span=RefinedSpan(
                                    str(raw_span["start"]), str(raw_span["end"])
                                )
                            ),
                        ),
                    ),
                    node(),
                )

        else:
            current = graph(node(), node(gaps), node())

            def build() -> object:
                return current.canonical_endpoint(str(case["input"]))

        if expected["verdict"] == "rejected-with-reason":
            with pytest.raises(GraphValidationError, match=str(expected["reason"])):
                build()
        else:
            assert build() == expected["endpoint"]
        return
    if "links" in case and case_id != "heterogeneous-phrase-contains-silence":

        def replace(value: str) -> str:
            return value.replace("/analysis/", "/top/").replace(
                "/delivery/", "/variant/"
            )

        links = tuple(
            Relation(tuple(map(replace, x[0])), x[1], tuple(map(replace, x[2])))
            for x in case["links"]
        )  # type: ignore[union-attr]

        def build() -> object:
            return choice_graph(links)

        if expected["verdict"] == "rejected-with-reason":
            with pytest.raises(GraphValidationError, match=str(expected["reason"])):
                build()
        else:
            assert build()
        return
    if case_id == "heterogeneous-phrase-contains-silence":
        declared = Declarations(
            tuple(
                TierDeclaration(name, frozenset({"class"}))
                for name in ("phrase", "segment", "word")
            ),
            (FeatureDeclaration("class"),),
            (RelationDeclaration("contains", containment=True, acyclic=True),),
        )
        nodes = [ClockNode() for _ in range(9)]
        nodes[0] = ClockNode(
            groups=(
                EventGroup("phrase", (event(),)),
                EventGroup("segment", (Event({"class": "silence"}),)),
            )
        )
        nodes[1] = ClockNode(groups=(EventGroup("word", (event(),)),))
        nodes[4] = ClockNode(groups=(EventGroup("word", (event(),)),))
        nodes[7] = ClockNode(
            groups=(EventGroup("segment", (Event({"class": "silence"}),)),)
        )
        raw_link = case["links"][0]  # type: ignore[index]
        current = Graph(
            declared,
            tuple(nodes),
            (Relation(tuple(raw_link[0]), raw_link[1], tuple(raw_link[2])),),
        )
        assert [
            current.resolve(ref).tier
            for ref in current.direct_children("/clock/0/phrase/0")
        ] == expected["direct_child_tiers"]
        return
    if "event" in case:
        raw = case["event"]
        assert isinstance(raw, dict)
        tick = int(str(raw["path"]).split("/")[2])
        tier = str(raw["path"]).split("/")[3]
        features = raw.get("features", {})
        item = Event(
            features,
            raw.get("duration"),
            RefinedSpan(**raw["span"]) if "span" in raw else None,
            Timing(**raw["timing"]) if "timing" in raw else None,
        )  # type: ignore[arg-type]
        nodes = [
            ClockNode()
            for _ in range(max(tick + (item.structural_duration or 0) + 1, 3))
        ]
        nodes[tick] = ClockNode(groups=(EventGroup(tier, (item,)),))
        if item.span is not None:
            nodes[1] = ClockNode(2)
        declared = Declarations(
            (TierDeclaration(tier, frozenset(features)),),
            tuple(FeatureDeclaration(name) for name in features),
            (),
        )
        current = Graph(declared, tuple(nodes))
        restored = Graph.from_data(declared, current.to_data())
        assert restored.resolve(str(raw["path"])).event is not None
        return
    if "link" in case:
        raw_link = case["link"]
        assert isinstance(raw_link, list)
        constraints = case["endpoint_constraints"]
        assert isinstance(constraints, dict)
        kind_map = {kind.value: kind for kind in EndpointKind}
        relation_declaration = RelationDeclaration(
            str(raw_link[1]),
            source_kinds=frozenset(kind_map[name] for name in constraints["source"]),
            target_kinds=frozenset(kind_map[name] for name in constraints["target"]),
        )
        tiers = sorted(
            {
                parts[3]
                for pointer in raw_link[0] + raw_link[2]
                if len(parts := pointer.split("/")) == 5 and parts[3] != "gaps"
            }
        )
        declared = Declarations(
            tuple(TierDeclaration(name) for name in tiers), (), (relation_declaration,)
        )
        nodes = [ClockNode(), ClockNode(2), ClockNode()]
        for tick in (0, 1):
            groups = []
            for tier in tiers:
                maximum = max(
                    (
                        int(pointer.rsplit("/", 1)[1])
                        for pointer in raw_link[0] + raw_link[2]
                        if pointer.startswith(f"/clock/{tick}/{tier}/")
                    ),
                    default=-1,
                )
                if maximum >= 0:
                    groups.append(
                        EventGroup(tier, tuple(event() for _ in range(maximum + 1)))
                    )
            nodes[tick] = ClockNode(2 if tick == 1 else 1, tuple(groups))

        def build() -> object:
            return Graph(
                declared,
                tuple(nodes),
                (Relation(tuple(raw_link[0]), raw_link[1], tuple(raw_link[2])),),
            )

        if expected["verdict"] == "rejected-with-reason":
            with pytest.raises(GraphValidationError, match="coarse-tick"):
                build()
        else:
            assert build()
        return
    raise AssertionError(f"fixture case lacks an owner or kernel adapter: {case_id}")


def test_kernel_contains_no_profile_vocabulary() -> None:
    source = (Path(__file__).parents[2] / "ipakit" / "_tiergraph.py").read_text()
    forbidden = ("phoneset", "renderer", "rule-engine", "syllable", "phoneme")
    assert not any(word in source for word in forbidden)
