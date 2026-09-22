"""Finite-model rewrites decorating an explicitly bound native source graph.

This is bound-operation validation, not a graph-only operation-profile reader,
house Form importer, or policy for migrating target timing and containment.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from types import MappingProxyType
from typing import Any

import tiergraph as tg

from ._containment_projection import declared_value
from ._identity import identity_fingerprint
from ._rewrite_graph import _Token, _walk_projection
from ._rule_model import ModelRuleError, TokenDerivation, read_tokens
from .finite_model import FiniteModel
from .rules import RuleSet


@dataclass(frozen=True)
class GraphBinding:
    """Ordered unique source occurrences and explicit finite value/clock roles.

    References may cross tiers; their caller-provided order is authoritative.
    Values are existing qualified native JSON attributes, never inferred from
    tier labels or concatenated spelling. Optional feature claims are validated
    against the model's typed domains and exact token rows.
    """

    graph: tg.Graph
    model: FiniteModel
    refs: tuple[tg.ItemRef, ...]
    token_value: tg.QualifiedName
    model_value: tg.QualifiedName
    starts_at: tg.QualifiedName
    clock: tg.QualifiedName
    feature_values: Mapping[str, tg.QualifiedName] = field(default_factory=dict)
    identity: str = field(init=False)
    tokens: tuple[str, ...] = field(init=False)
    anchors: tuple[tg.DurableBoundaryRef, ...] = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.graph, tg.Graph) or not isinstance(
            self.model, FiniteModel
        ):
            raise ModelRuleError(
                "invalid-binding", "binding requires a native Graph and finite model"
            )
        object.__setattr__(self, "refs", tuple(self.refs))
        object.__setattr__(
            self, "feature_values", MappingProxyType(dict(self.feature_values))
        )
        if len(set(self.refs)) != len(self.refs):
            raise ModelRuleError("invalid-binding", "source references must be unique")
        roles = (
            self.token_value,
            self.model_value,
            self.starts_at,
            self.clock,
            *self.feature_values.values(),
        )
        if any(not isinstance(role, tg.QualifiedName) for role in roles):
            raise ModelRuleError(
                "invalid-binding", "graph roles require qualified names"
            )
        attribute_names = {
            declaration.name for declaration in self.graph.attribute_declarations
        }
        value_roles = (
            self.token_value,
            self.model_value,
            *self.feature_values.values(),
        )
        if any(role not in attribute_names for role in value_roles):
            raise ModelRuleError(
                "invalid-binding", "source value attribute is undeclared"
            )
        relation_names = {
            declaration.name for declaration in self.graph.relation_declarations
        }
        if self.starts_at not in relation_names:
            raise ModelRuleError(
                "invalid-binding", "source start relation is undeclared"
            )
        if not any(t.declaration.name == self.clock for t in self.graph.tiers):
            raise ModelRuleError("invalid-binding", "source clock tier is undeclared")
        for role in value_roles:
            declaration = next(
                d for d in self.graph.attribute_declarations if d.name == role
            )
            if (
                declaration.domain is not tg.AttributeDomain.ITEM
                or declaration.value_type is not tg.JsonType.JSON
            ):
                raise ModelRuleError(
                    "invalid-binding",
                    "source value roles require item-domain JSON attributes",
                )
        start_declaration = next(
            d for d in self.graph.relation_declarations if d.name == self.starts_at
        )
        if (
            not isinstance(start_declaration, tg.PolyadicRelationDeclaration)
            or start_declaration.sources.endpoint_kinds
            != (tg.RelationEndpointKind.ITEM,)
            or start_declaration.targets.endpoint_kinds
            != (tg.RelationEndpointKind.BOUNDARY,)
            or start_declaration.sources.minimum != 1
            or start_declaration.sources.maximum != 1
            or start_declaration.targets.minimum != 1
            or start_declaration.targets.maximum != 1
            or (
                start_declaration.targets.tiers is not None
                and self.clock not in start_declaration.targets.tiers
            )
        ):
            raise ModelRuleError(
                "invalid-binding",
                "source start role requires a single-item clock relation",
            )
        self.model.schema.validate({name: None for name in self.feature_values})
        tokens: list[str] = []
        anchors: list[tg.DurableBoundaryRef] = []
        for ref in self.refs:
            if not isinstance(ref, tg.ItemRef):
                raise ModelRuleError(
                    "invalid-binding", "source selection requires ItemRefs"
                )
            try:
                self.graph.resolve_item(ref)
            except ValueError as error:
                raise ModelRuleError("invalid-binding", str(error)) from error
            token = declared_value(self.graph, ref, self.token_value)
            if type(token) is not str:
                raise ModelRuleError(
                    "invalid-binding", "source token must be an exact string"
                )
            if declared_value(self.graph, ref, self.model_value) != self.model.identity:
                raise ModelRuleError(
                    "model-mismatch", "source occurrence has a different model"
                )
            bundle = self.model.read(token)
            values = dict(zip(self.model.schema.features, bundle.values, strict=True))
            claims = {
                name: declared_value(self.graph, ref, role)
                for name, role in self.feature_values.items()
            }
            self.model.schema.validate(claims)
            if any(
                type(value) is not type(values[name]) or value != values[name]
                for name, value in claims.items()
            ):
                raise ModelRuleError(
                    "invalid-binding", "source feature claims disagree with token"
                )
            starts = [
                relation
                for relation in self.graph.polyadic_relations
                if relation.declaration == self.starts_at and relation.sources == (ref,)
            ]
            if len(starts) != 1 or len(starts[0].targets) != 1:
                raise ModelRuleError(
                    "invalid-binding", "each source requires exactly one clock anchor"
                )
            anchor = starts[0].targets[0]
            if (
                not isinstance(anchor, tg.DurableBoundaryRef)
                or self.graph.resolve_boundary(anchor).tier != self.clock
            ):
                raise ModelRuleError(
                    "invalid-binding",
                    "source anchor must resolve on the declared clock",
                )
            tokens.append(token)
            anchors.append(anchor)
        object.__setattr__(self, "tokens", tuple(tokens))
        object.__setattr__(self, "anchors", tuple(anchors))
        object.__setattr__(
            self,
            "identity",
            identity_fingerprint(
                {
                    "format": "finite-graph-binding/1",
                    "graph": tg.to_data(self.graph),
                    "model": self.model.identity,
                    "refs": [ref.to_data() for ref in self.refs],
                    "roles": [role.to_data() for role in roles[:4]],
                    "features": {
                        name: role.to_data()
                        for name, role in self.feature_values.items()
                    },
                }
            ),
        )

    def derive(
        self, rules: RuleSet, *, migration: str = "preserve-source"
    ) -> GraphDerivation:
        """Run the shared token engine and append source-anchored trace history."""
        if migration != "preserve-source":
            raise ModelRuleError(
                "unsupported-operation",
                "target timing/attachment migration is not implemented",
            )
        # Reconstruct admission before empty/no-match success; no cached identity
        # or joined spelling substitutes for the actual source/model objects.
        checked = GraphBinding(
            self.graph,
            self.model,
            self.refs,
            self.token_value,
            self.model_value,
            self.starts_at,
            self.clock,
            self.feature_values,
        )
        if checked.identity != self.identity:
            raise ModelRuleError("invalid-binding", "source binding changed")
        trace = rules.derive_tokens(checked.tokens, model=checked.model)
        identity = _operation_identity(checked, rules, trace)
        writer = _GraphWriter(checked, identity)
        initial = [
            _Token(unit, ref, anchor)
            for unit, ref, anchor in zip(
                read_tokens(checked.tokens, checked.model),
                checked.refs,
                checked.anchors,
                strict=True,
            )
        ]
        final = _walk_projection(
            initial, tuple(step for step in trace.steps if step.fired), writer
        )
        return GraphDerivation(
            checked,
            rules,
            trace,
            writer.graph,
            tuple(item.handle for item in final),
            identity,
        )


def _operation_identity(
    binding: GraphBinding, rules: RuleSet, trace: TokenDerivation
) -> str:
    return identity_fingerprint(
        {
            "format": "finite-graph-operation/1",
            "binding": binding.identity,
            "policy": "source-clock/no-target-timing/no-attachment-migration/1",
            "rules": [
                {"binding": rule.binding, "name": rule.name, "optional": rule.optional}
                for rule in rules.rules
            ],
            "trace": [
                {
                    "rule": step.rule,
                    "before": step.before_tokens,
                    "after": step.after_tokens,
                    "optional": step.optional,
                    "edits": [
                        {
                            "start": edit.start,
                            "end": edit.end,
                            "rule": edit.rule,
                            "targets": [unit.text for unit in edit.replacement],
                            "site": asdict(edit.site),
                        }
                        for edit in step.edits
                    ],
                }
                for step in trace.steps
            ],
            "start": trace.start,
            "result": trace.tokens,
            "model": trace.model_id,
        }
    )


@dataclass(frozen=True)
class GraphDerivation:
    """Extended native graph plus explicit, reconstructible execution authority."""

    binding: GraphBinding
    rules: RuleSet
    trace: TokenDerivation
    graph: tg.Graph
    final_refs: tuple[tg.ItemRef, ...]
    identity: str

    def restore(self, graph: tg.Graph) -> GraphDerivation:
        """Validate a native-decoded graph against this bound operation.

        A freshly rebuilt equivalent binding/execution works identically; no
        object identity or process-local token authenticates a result. A graph
        alone does not supply model/rules authority. Extra or missing facts
        refuse, without weakening any other profile's restoration contract.
        """
        expected = self.binding.derive(self.rules)
        if (
            self.identity != expected.identity
            or self.trace != expected.trace
            or self.final_refs != expected.final_refs
            or tg.dump_bytes(self.graph) != tg.dump_bytes(expected.graph)
            or tg.dump_bytes(graph) != tg.dump_bytes(expected.graph)
        ):
            raise ModelRuleError(
                "invalid-binding", "graph or trace differs from the bound execution"
            )
        return GraphDerivation(
            expected.binding,
            expected.rules,
            expected.trace,
            graph,
            expected.final_refs,
            expected.identity,
        )


class _GraphWriter:
    def __init__(self, binding: GraphBinding, identity: str):
        self.binding = binding
        self.graph = binding.graph
        self.namespace = "urn:ipakit:finite-rewrite:" + identity.removeprefix("sha256:")
        self.prefix = "rewrite-" + identity.removeprefix("sha256:")
        self.count = 0
        self.tiers: dict[int, tg.QualifiedName] = {}

    def q(self, name: str) -> tg.QualifiedName:
        return tg.QualifiedName(self.namespace, name)

    def insertion_anchor(self, index: int) -> Any:
        raise ModelRuleError(
            "unsupported-operation",
            "finite graph insertion requires an explicit anchor policy",
        )

    def _tier(self, step: int) -> tg.QualifiedName:
        if step in self.tiers:
            return self.tiers[step]
        editor = self.graph.edit()
        if not self.tiers:
            if any(
                ns.namespace == self.namespace or ns.prefix == self.prefix
                for ns in self.graph.namespaces
            ):
                raise ModelRuleError(
                    "invalid-binding", "derived operation namespace already exists"
                )
            editor.declare(tg.NamespaceDeclaration(self.prefix, self.namespace))
            item = tg.RelationSideDeclaration(
                (tg.RelationEndpointKind.ITEM,), minimum=1, maximum=1
            )
            targets = tg.RelationSideDeclaration(
                (tg.RelationEndpointKind.ITEM,), minimum=0, allow_empty=True
            )
            editor.declare(
                tg.PolyadicRelationDeclaration(
                    self.q("rewrites-to"),
                    tg.RelationSideDeclaration(
                        (tg.RelationEndpointKind.ITEM,), minimum=1
                    ),
                    targets,
                )
            )
            editor.declare(
                tg.AttributeDeclaration(
                    self.q("value"), tg.AttributeDomain.ITEM, tg.JsonType.JSON
                )
            )
            editor.declare(
                tg.PolyadicRelationDeclaration(
                    self.q("starts-at"),
                    item,
                    tg.RelationSideDeclaration(
                        (tg.RelationEndpointKind.BOUNDARY,),
                        tiers=(self.binding.clock,),
                        minimum=1,
                        maximum=1,
                    ),
                    unique_sources=True,
                )
            )
        tier = self.q(f"step-{step}")
        editor.declare(tg.TierDeclaration(tier, f"Finite rewrite step {step}"))
        self.graph = editor.freeze()
        self.tiers[step] = tier
        return tier

    def _write(
        self,
        step: int,
        rule: str,
        trace: str,
        sources: Sequence[_Token],
        units: Sequence[Any],
        anchor: tg.DurableBoundaryRef,
        site: int,
    ) -> tuple[tg.ItemRef, ...]:
        tier = self._tier(step)
        targets = []
        for target_index, unit in enumerate(units):
            payload = {
                "token": unit.text,
                "model": self.binding.model.identity,
                "features": dict(
                    zip(
                        self.binding.model.schema.features,
                        unit.bundle.values,
                        strict=True,
                    )
                ),
                "phantom": True,
                "rule": rule,
                "trace": trace,
                "order": [step, site, site, target_index],
            }
            index = next(
                len(t.items) for t in self.graph.tiers if t.declaration.name == tier
            )
            ref = tg.ItemRef(tier, index)
            editor = self.graph.edit().insert_item(
                tier,
                index,
                tg.Item(
                    f"{self.prefix}-{self.count}",
                    attributes=(tg.JsonAttributeValue(self.q("value"), payload),),
                ),
            )
            editor.add_relation(
                tg.PolyadicRelationInstance(self.q("starts-at"), (ref,), (anchor,))
            )
            self.graph = editor.freeze()
            self.count += 1
            targets.append(ref)
        editor = self.graph.edit()
        editor.add_relation(
            tg.PolyadicRelationInstance(
                self.q("rewrites-to"),
                tuple(token.handle for token in sources),
                tuple(targets),
            )
        )
        self.graph = editor.freeze()
        return tuple(targets)

    def emit(
        self,
        step_index: int,
        step: Any,
        edit: Any,
        sources: Sequence[_Token],
        anchor: Any,
        site_order: int,
    ) -> tuple[tg.ItemRef, ...]:
        return self._write(
            step_index,
            edit.rule,
            str(edit),
            sources,
            edit.replacement,
            anchor,
            site_order,
        )

    def carry(self, step_index: int, step: Any, old: _Token, cursor: int) -> tg.ItemRef:
        return self._write(
            step_index, step.rule, "no-op", (old,), (old.unit,), old.anchor, cursor
        )[0]
