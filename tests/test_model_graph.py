"""Model-relative rewrites retain actual graph facts and source clock anchors."""

from dataclasses import replace

import pytest
from ipakit._containment_projection import ContainmentProjection, _name, declared_value
from ipakit._fact_builder import FactBuilder
from ipakit._graph_facts import (
    Declarations,
    FeatureDeclaration,
    RelationDeclaration,
    TierDeclaration,
    Timing,
)
from ipakit.finite_model import FeatureSchema, FiniteModel, InvalidFeature, MissingToken
from ipakit.model_graph import GraphBinding
from ipakit.rules import Action, LiteralTokens, ModelRuleError, RuleSet, parse

import tiergraph as tg

NS = "urn:test:finite-source"


def q(name):
    return tg.QualifiedName(NS, name)


def fixture(tokens=("a", "sil", "b"), *, claims=None):
    model = FiniteModel(
        "test",
        FeatureSchema({"x": (False, 0, 1)}),
        {"a": (False,), "b": (0,), "sil": (1,)},
    )
    names = ("token", "model", "x")
    builder = FactBuilder(
        Declarations(
            (
                TierDeclaration("source", frozenset(names)),
                TierDeclaration("word", frozenset()),
            ),
            tuple(FeatureDeclaration(name, (NS, name)) for name in names),
            (
                RelationDeclaration(
                    "contains",
                    containment=True,
                    acyclic=True,
                    source_tiers=frozenset({"word"}),
                    target_tiers=frozenset({"source"}),
                    source_arity=(1, 1),
                ),
            ),
        )
    )
    handles = []
    for index, token in enumerate(tokens):
        features = {"token": token, "model": model.identity}
        if claims is not None:
            features["x"] = claims[index]
        handles.append(
            builder.append_input_atom(
                "source", features, timing=Timing(1.25, 0.4) if index == 0 else None
            )
        )
    if len(handles) == 3:
        word = builder.add_event("word", 0, {}, duration=3)
        builder.contain(word, (handles[0], handles[2]))
        builder.add_root(word)
    facts = builder.build_input()
    projection = ContainmentProjection.from_input(facts)
    graph = projection.graph
    refs = tuple(
        projection.old_to_new[ref]
        for ref in facts.refs
        if facts.event_tiers[ref] == "source"
    )
    clock = next(t for t in graph.tiers if t.declaration.name == _name("clock"))
    editor = graph.edit()
    # Declared source roles survive even when there are no occurrences.
    assert sum(ns.namespace == NS for ns in graph.namespaces) == 1
    assert {q(name) for name in names} <= {
        declaration.name for declaration in graph.relation_declarations
    }
    editor.declare(
        tg.AttributeDeclaration(
            q("extra"), tg.AttributeDomain.DOCUMENT, tg.XsdType.STRING
        )
    )
    editor.set_attribute(
        None, tg.AttributeValue(q("extra"), tg.XsdType.STRING, "retain me")
    )
    item = tg.RelationSideDeclaration(
        (tg.RelationEndpointKind.ITEM,), minimum=1, maximum=1
    )
    editor.declare(
        tg.PolyadicRelationDeclaration(
            q("starts"),
            item,
            tg.RelationSideDeclaration(
                (tg.RelationEndpointKind.BOUNDARY,),
                tiers=(_name("clock"),),
                minimum=1,
                maximum=1,
            ),
            unique_sources=True,
        )
    )
    for index, ref in enumerate(refs):
        anchor = tg.DurableBoundaryRef(
            tg.DurableItemRef(clock.items[2 * index].durable_id), tg.BoundarySide.BEFORE
        )
        editor.add_relation(tg.PolyadicRelationInstance(q("starts"), (ref,), (anchor,)))
    graph = editor.freeze()
    binding = GraphBinding(
        graph,
        model,
        refs,
        q("token"),
        q("model"),
        q("starts"),
        _name("clock"),
        {} if claims is None else {"x": q("x")},
    )
    return binding


def rules(model):
    split = replace(
        parse("a -> b", model=model),
        action=Action(finite=LiteralTokens(("b", "a"))),
        _model=None,
        binding=None,
    ).bind(model)
    return RuleSet((split, parse("b -> ∅", model=model)))


def test_graph_decoration_split_deletion_preservation_and_reconstructed_restore():
    binding = fixture(claims=(False, 1, 0))
    original = tg.dump_bytes(binding.graph)
    assert any(
        relation.targets == (binding.refs[0], binding.refs[2])
        and len(relation.sources) == 1
        and relation.sources[0] not in binding.refs
        for relation in binding.graph.polyadic_relations
    )
    result = binding.derive(rules(binding.model))
    assert result.trace.tokens == ("a", "sil")
    assert [ref.index for ref in result.final_refs] == [0, 1]
    assert [ref.tier.local_name for ref in result.final_refs] == ["step-1", "step-1"]
    namespace = result.final_refs[0].tier.namespace
    value_role = tg.QualifiedName(namespace, "value")
    payloads = [
        declared_value(result.graph, ref, value_role) for ref in result.final_refs
    ]
    assert [payload["token"] for payload in payloads] == ["a", "sil"]
    assert [payload["features"]["x"] for payload in payloads] == [False, 1]
    assert type(payloads[0]["features"]["x"]) is bool
    assert [payload["order"] for payload in payloads] == [[1, 1, 1, 0], [1, 2, 2, 0]]
    histories = [
        relation
        for relation in result.graph.polyadic_relations
        if relation.declaration == tg.QualifiedName(namespace, "rewrites-to")
    ]
    assert [len(relation.targets) for relation in histories] == [2, 1, 1, 0, 1, 1, 0]
    assert histories[0].sources == (binding.refs[0],)
    assert histories[3].sources == (histories[0].targets[0],)
    assert histories[6].sources == histories[2].targets
    starts = [
        relation
        for relation in result.graph.polyadic_relations
        if relation.declaration == tg.QualifiedName(namespace, "starts-at")
    ]
    assert [relation.targets[0] for relation in starts] == [
        binding.anchors[0],
        binding.anchors[0],
        binding.anchors[1],
        binding.anchors[2],
        binding.anchors[0],
        binding.anchors[1],
    ]
    for carrier in (
        "tiers",
        "relations",
        "attributes",
        "boundary_values",
        "polyadic_relations",
        "attribute_declarations",
        "relation_declarations",
        "seals",
        "layers",
    ):
        assert all(
            item in getattr(result.graph, carrier)
            for item in getattr(binding.graph, carrier)
        )
    assert result.graph.attributes == binding.graph.attributes
    assert tg.dump_bytes(binding.graph) == original
    # Timing remains exactly source-owned; no target seconds or duration is inferred.
    assert all(
        "timing" not in payload and "duration" not in payload for payload in payloads
    )
    rebuilt = fixture(claims=(False, 1, 0))
    assert rebuilt is not binding and rebuilt.model is not binding.model
    assert rebuilt.identity == binding.identity
    restored = rebuilt.derive(rules(rebuilt.model)).restore(
        tg.loads(tg.dump_bytes(result.graph))
    )
    assert restored.identity == result.identity
    assert tg.dump_bytes(restored.graph) == tg.dump_bytes(result.graph)


@pytest.mark.parametrize("tokens", [(), ("sil",)])
def test_empty_and_no_match_validate_and_return_exact_original_graph(tokens):
    binding = fixture(tokens)
    result = binding.derive(RuleSet((parse("a -> b", model=binding.model),)))
    assert tg.dump_bytes(result.graph) == tg.dump_bytes(binding.graph)
    assert result.final_refs == binding.refs
    assert (
        result.restore(tg.loads(tg.dump_bytes(result.graph))).identity
        == result.identity
    )
    with pytest.raises(ModelRuleError, match="migration"):
        binding.derive(RuleSet(()), migration="copy-target-timing")
    wrong = FiniteModel("wrong", binding.model.schema, binding.model.rows)
    with pytest.raises(ModelRuleError):
        binding.derive(RuleSet((parse("a -> b", model=wrong),)))


def test_binding_refuses_wrong_graph_trace_reference_roles_and_typed_claims():
    binding = fixture()
    result = binding.derive(rules(binding.model))
    with pytest.raises(ModelRuleError):
        replace(binding, refs=(binding.refs[0], binding.refs[0]))
    with pytest.raises(ModelRuleError):
        replace(binding, refs=(tg.ItemRef(binding.refs[0].tier, 999),))
    with pytest.raises(ModelRuleError):
        replace(binding, clock=q("not-a-clock"))
    with pytest.raises(ModelRuleError):
        replace(binding, token_value=q("not-a-value"))
    with pytest.raises(InvalidFeature):
        fixture(claims=(2, 1, 0))
    with pytest.raises(ModelRuleError, match="disagree"):
        fixture(claims=(0, 1, 0))  # false is not integer zero
    with pytest.raises(MissingToken):
        fixture(("unknown",))
    changed_graph = (
        binding.graph.edit()
        .set_attribute(
            None, tg.AttributeValue(q("extra"), tg.XsdType.STRING, "changed graph")
        )
        .freeze()
    )
    changed = replace(binding, graph=changed_graph)
    assert changed.tokens == binding.tokens and changed.identity != binding.identity
    with pytest.raises(ModelRuleError):
        changed.derive(rules(changed.model)).restore(result.graph)
    with pytest.raises(ModelRuleError):
        replace(result, trace=replace(result.trace, tokens=("b",))).restore(
            result.graph
        )
    with pytest.raises(ModelRuleError):
        replace(result, final_refs=tuple(reversed(result.final_refs))).restore(
            result.graph
        )
    with pytest.raises(ModelRuleError):
        result.restore(binding.graph)


def test_caller_order_is_retained_not_sorted_by_graph_storage():
    original = fixture()
    binding = replace(original, refs=tuple(reversed(original.refs)))
    assert binding.tokens == ("b", "sil", "a")
    result = binding.derive(RuleSet(()))
    assert result.final_refs == binding.refs
    assert result.graph == original.graph


def test_empty_binding_validates_role_domains_and_nonempty_requires_actual_anchor():
    empty = fixture(())
    bad_declarations = tuple(
        (
            replace(
                declaration,
                targets=tg.RelationSideDeclaration(
                    (tg.RelationEndpointKind.ITEM,), minimum=1, maximum=1
                ),
            )
            if declaration.name == empty.starts_at
            else declaration
        )
        for declaration in empty.graph.relation_declarations
    )
    with pytest.raises(ModelRuleError, match="single-item"):
        replace(
            empty, graph=replace(empty.graph, relation_declarations=bad_declarations)
        )
    binding = fixture()
    absent = replace(
        binding.graph,
        polyadic_relations=tuple(
            relation
            for relation in binding.graph.polyadic_relations
            if not (
                relation.declaration == binding.starts_at
                and relation.sources == (binding.refs[1],)
            )
        ),
    )
    with pytest.raises(ModelRuleError, match="exactly one clock anchor"):
        replace(binding, graph=absent)
    with pytest.raises(ModelRuleError):
        replace(binding, clock=binding.refs[0].tier)


def test_both_writers_call_the_same_trace_traversal(monkeypatch):
    import ipakit
    from ipakit import _rewrite_graph, model_graph

    actual = _rewrite_graph._walk_projection
    assert model_graph._walk_projection is actual
    calls = []

    def record(current, steps, writer):
        calls.append(type(writer).__name__)
        return actual(current, steps, writer)

    monkeypatch.setattr(_rewrite_graph, "_walk_projection", record)
    monkeypatch.setattr(model_graph, "_walk_projection", record)
    binding = fixture()
    binding.derive(rules(binding.model))
    inventory = ipakit.load_ipa_features()
    native = RuleSet.parse("t -> s", inventory).derive("ta", inventory)
    _rewrite_graph.project_derivation(native, inventory)
    assert calls == ["_GraphWriter", "_NativeWriter"]
