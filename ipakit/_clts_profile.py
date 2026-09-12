"""Internal constructor-layout source profile; not public Form admission.

Resolution records are supplied by an explicitly bound caller, never obtained
or repaired here. Native TierGraph is the only persisted representation. This
profile refuses other graph layouts rather than dropping their extra content.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

import tiergraph as tg

from ._clts_input import FORMAT, HOST, InputError, decode, endpoint
from ._containment_projection import ContainmentProjection, declared_value
from ._fact_builder import EventSpec, FactBuilder
from ._graph_facts import (
    Declarations,
    FeatureDeclaration,
    RelationDeclaration,
    TierDeclaration,
    Timing,
    _freeze,
    _thaw,
)
from ._identity import identity_fingerprint
from ._provenance import SourceMetadata

NAMESPACE = "https://ipakit.dev/tiergraph/clts-source/v1"
PROFILE = "ipakit-clts-source"
TIERS = ("source-token", "source-sound", "house-projection", "metadata")
DECIDES = (
    "constructor-layout source retention and declared schema",
    "input clock, timings and caller tone-host links",
)
UNDECIDED = (
    "external resolver truth and house semantic coverage",
    "public Form and downstream consumer admission",
)


def name(local: str) -> tg.QualifiedName:
    return tg.QualifiedName(NAMESPACE, local)


@dataclass(frozen=True)
class SourceProfileSpec:
    """Explicit supplied provider binding and complete qualified claim schema."""

    source: SourceMetadata
    provider_fingerprint: str
    manifest_fingerprint: str
    kinds: tuple[str, ...]
    fields: tuple[FeatureDeclaration, ...] = ()
    domains: Mapping[str, tuple[Any, ...]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.source, SourceMetadata):
            raise ValueError("source metadata must use the shared declaration")
        object.__setattr__(self, "fields", tuple(self.fields))
        if any(
            not isinstance(v, str) or not v
            for v in (self.provider_fingerprint, self.manifest_fingerprint)
        ):
            raise ValueError("explicit provider and manifest identities are required")
        object.__setattr__(self, "kinds", tuple(self.kinds))
        if (
            not self.kinds
            or any(not isinstance(k, str) or not k for k in self.kinds)
            or len(set(self.kinds)) != len(self.kinds)
        ):
            raise ValueError("provider must declare its distinct resolved sound kinds")
        reserved = {"raw", "time", "resolution", "kind", "canonical", "profile"}
        if any(f.value_name is None or f.name in reserved for f in self.fields):
            raise ValueError("source fields require distinct qualified identities")
        domains = {
            key: tuple(_freeze(value) for value in values)
            for key, values in self.domains.items()
        }
        if domains.keys() - {f.name for f in self.fields} or any(
            not values for values in domains.values()
        ):
            raise ValueError("domains must name declared fields and be nonempty")
        # The native JSON value constructor validates domain entries too.
        for values in domains.values():
            for value in values:
                tg.json_value_graph(_thaw(value))
        object.__setattr__(self, "domains", MappingProxyType(domains))
        declarations(self)

    def roles(self) -> dict[str, Any]:
        return {tier: name(tier) for tier in TIERS}


def declarations(spec: SourceProfileSpec) -> Declarations:
    """Declare roles and source claims independently of observed events."""
    own = tuple(
        FeatureDeclaration(key, (NAMESPACE, key))
        for key in ("raw", "time", "resolution", "kind", "canonical", "profile")
    )
    admitted: tuple[set[str], ...] = (
        {"raw", "time", "resolution"},
        {"kind", "canonical", *(f.name for f in spec.fields)},
        set(),
        {"profile"},
    )
    return Declarations(
        tuple(
            TierDeclaration(tier, frozenset(keys), (NAMESPACE, tier))
            for tier, keys in zip(TIERS, admitted, strict=True)
        ),
        own + spec.fields,
        (
            RelationDeclaration(
                "resolves",
                source_tiers=frozenset({"source-token"}),
                target_tiers=frozenset({"source-sound"}),
                source_arity=(1, 1),
                target_arity=(0, None),
                allow_empty_target=True,
                native_name=(NAMESPACE, "resolves"),
                unique_sources=True,
            ),
            RelationDeclaration(
                HOST,
                acyclic=True,
                source_tiers=frozenset({"source-token"}),
                target_tiers=frozenset({"source-token"}),
                source_arity=(1, 1),
                target_arity=(1, 1),
                native_name=(NAMESPACE, "source-tone-host"),
                unique_sources=True,
            ),
        ),
    )


def _schema(spec: SourceProfileSpec) -> dict[str, Any]:
    empty = ContainmentProjection.from_input(
        FactBuilder(declarations(spec)).build_input()
    ).graph
    return {
        "namespaces": [item.to_data() for item in empty.namespaces],
        "tiers": [tier.declaration.to_data() for tier in empty.tiers],
        "relations": [item.to_data() for item in empty.relation_declarations],
        "attributes": [item.to_data() for item in empty.attribute_declarations],
    }


def metadata(spec: SourceProfileSpec) -> dict[str, Any]:
    """Fingerprint declarations/conditions, not the digest or instance values."""
    material = {
        "id": PROFILE,
        "version": 1,
        "roles": {key: value.to_data() for key, value in spec.roles().items()},
        "schema": _schema(spec),
        "domains": {
            key: [_thaw(v) for v in values] for key, values in spec.domains.items()
        },
        "kinds": list(spec.kinds),
        "source": spec.source.to_dict(),
        "provider": spec.provider_fingerprint,
        "manifest": spec.manifest_fingerprint,
        "decides": list(DECIDES),
        "undecided": list(UNDECIDED),
    }
    return {**material, "fingerprint": identity_fingerprint(material)}


def _resolutions(
    spec: SourceProfileSpec, values: Sequence[Mapping[str, Any]], count: int
) -> list[dict[str, Any]]:
    if (
        not isinstance(values, Sequence)
        or isinstance(values, (str, bytes))
        or len(values) != count
    ):
        raise InputError(
            "invalid-resolution",
            "",
            "one supplied resolution per source token is required",
        )
    output = []
    fields = {item.name for item in spec.fields}
    for index, value in enumerate(values):
        path = f"/tokens/{index}/resolution"
        if not isinstance(value, Mapping) or set(value) != {
            "provider",
            "status",
            "sounds",
        }:
            raise InputError(
                "invalid-resolution", path, "expected provider, status and sounds"
            )
        if value["provider"] != spec.provider_fingerprint:
            raise InputError(
                "provider-mismatch", path, "resolution belongs to another provider"
            )
        status, sounds = value["status"], value["sounds"]
        if (
            status not in ("resolved", "unknown", "outside-artifact-domain")
            or not isinstance(sounds, (list, tuple))
            or bool(sounds) != (status == "resolved")
        ):
            raise InputError(
                "invalid-resolution", path, "status and sound records disagree"
            )
        copied = []
        for sound in sounds:
            if not isinstance(sound, Mapping) or set(sound) != {
                "kind",
                "canonical",
                "values",
            }:
                raise InputError("invalid-resolution", path, "malformed sound record")
            if (
                sound["kind"] not in spec.kinds
                or not isinstance(sound["canonical"], str)
                or not sound["canonical"]
            ):
                raise InputError(
                    "invalid-resolution",
                    path,
                    "sound needs a declared kind and canonical string",
                )
            claims = sound["values"]
            if not isinstance(claims, Mapping) or set(claims) - fields:
                raise InputError("invalid-resolution", path, "undeclared source claim")
            for key, claim in claims.items():
                try:
                    tg.json_value_graph(claim)
                except (TypeError, ValueError) as error:
                    raise InputError("invalid-value", path, str(error)) from error
                if key in spec.domains and identity_fingerprint(claim) not in {
                    identity_fingerprint(_thaw(v)) for v in spec.domains[key]
                }:
                    raise InputError(
                        "invalid-value", path, "claim outside declared source domain"
                    )
            copied.append(
                {
                    "kind": sound["kind"],
                    "canonical": sound["canonical"],
                    "values": dict(claims),
                }
            )
        output.append(
            {"provider": spec.provider_fingerprint, "status": status, "sounds": copied}
        )
    return output


def _construct(
    document: dict[str, Any], resolutions: list[dict[str, Any]], spec: SourceProfileSpec
) -> tg.Graph:
    builder = FactBuilder(declarations(spec))
    tokens = []
    for index, (token, resolution) in enumerate(
        zip(document["tokens"], resolutions, strict=True)
    ):
        features = {
            "raw": token["raw"],
            "resolution": {key: resolution[key] for key in ("provider", "status")},
        }
        timing = None
        if "time" in token:
            features["time"] = token["time"]
            timing = Timing(**token["time"])
        handle = builder.append_input_atom("source-token", features, timing=timing)
        tokens.append(handle)
        children = builder.add_ordered_sequence(
            "source-sound",
            index,
            [
                EventSpec(
                    {
                        "kind": sound["kind"],
                        "canonical": sound["canonical"],
                        **sound["values"],
                    },
                    duration=1,
                )
                for sound in resolution["sounds"]
            ],
            derivation_step=0,
            source_site_order=index,
            application_order=0,
        )
        builder.relate([handle], "resolves", children)
    for index, relation in enumerate(document.get("relations", [])):
        left = endpoint(relation["source"], len(tokens), f"/relations/{index}/source")
        right = endpoint(relation["target"], len(tokens), f"/relations/{index}/target")
        source, target = resolutions[left]["sounds"], resolutions[right]["sounds"]
        if (
            not source
            or any(s["kind"] != "tone" for s in source)
            or not target
            or any(s["kind"] == "tone" for s in target)
        ):
            raise InputError(
                "invalid-host",
                f"/relations/{index}",
                "host requires resolved tone source and resolved non-tone target",
            )
        builder.relate([tokens[left]], HOST, [tokens[right]])
    builder.add_event(
        "metadata",
        0,
        {"profile": {**metadata(spec), "relations-present": "relations" in document}},
        duration=0,
    )
    return ContainmentProjection.from_input(builder.build_input()).graph


def construct(
    value: Any, resolutions: Sequence[Mapping[str, Any]], spec: SourceProfileSpec
) -> tg.Graph:
    """Lower strict ingress and explicitly supplied outcomes to native facts."""
    document = decode(value)
    records = _resolutions(spec, resolutions, len(document["tokens"]))
    try:
        return _construct(document, records, spec)
    except InputError:
        raise
    except ValueError as error:
        raise InputError("invalid-source-graph", "", str(error)) from error


def _items(graph: tg.Graph, tier: str) -> tuple[tg.ItemRef, ...]:
    tiers = [entry for entry in graph.tiers if entry.declaration.name == name(tier)]
    if len(tiers) != 1:
        raise ValueError("source profile role tier missing")
    return tuple(tg.ItemRef(name(tier), index) for index in range(len(tiers[0].items)))


def restore(
    graph: tg.Graph, spec: SourceProfileSpec
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    """Validate and restore this constructor layout, without live resolution.

    Extra content or alternate equivalent layouts are refused, never discarded.
    Native reconstruction checks the complete clock, declarations and relations.
    """
    points = _items(graph, "metadata")
    if len(points) != 1:
        raise ValueError("expected one source profile metadata point")
    held = declared_value(graph, points[0], name("profile"))
    if not isinstance(held, dict) or type(held.get("relations-present")) is not bool:
        raise ValueError("malformed source profile metadata")
    present = held.pop("relations-present")
    if identity_fingerprint(held) != identity_fingerprint(metadata(spec)):
        raise ValueError("source profile declaration or provider fingerprint mismatch")
    tokens, resolutions = [], []
    refs = _items(graph, "source-token")
    for ref in refs:
        token = {"raw": declared_value(graph, ref, name("raw"))}
        if any(
            r.declaration == name("time") and r.sources == (ref,)
            for r in graph.polyadic_relations
        ):
            token["time"] = declared_value(graph, ref, name("time"))
        tokens.append(token)
        status = declared_value(graph, ref, name("resolution"))
        links = [
            r
            for r in graph.polyadic_relations
            if r.declaration == name("resolves") and r.sources == (ref,)
        ]
        if len(links) != 1:
            raise ValueError("expected one ordered resolution relation")
        sounds = []
        for child in links[0].targets:
            if not isinstance(child, tg.ItemRef) or child.tier != name("source-sound"):
                raise ValueError("invalid resolution child")
            values = {}
            for declared in spec.fields:
                assert declared.value_name is not None
                qualified = tg.QualifiedName(*declared.value_name)
                if any(
                    r.declaration == qualified and r.sources == (child,)
                    for r in graph.polyadic_relations
                ):
                    values[declared.name] = declared_value(graph, child, qualified)
            sounds.append(
                {
                    "kind": declared_value(graph, child, name("kind")),
                    "canonical": declared_value(graph, child, name("canonical")),
                    "values": values,
                }
            )
        if not isinstance(status, dict) or set(status) != {"provider", "status"}:
            raise ValueError("malformed stored resolution status")
        resolutions.append({**status, "sounds": sounds})
    document: dict[str, Any] = {"format": FORMAT, "version": 1, "tokens": tokens}
    if present:
        relations = []
        for relation in graph.polyadic_relations:
            if relation.declaration != name("source-tone-host"):
                continue
            if (
                len(relation.sources) != 1
                or len(relation.targets) != 1
                or relation.sources[0] not in refs
                or relation.targets[0] not in refs
            ):
                raise ValueError("malformed stored host relation")
            relations.append(
                {
                    "type": HOST,
                    "source": f"/tokens/{refs.index(relation.sources[0])}",
                    "target": f"/tokens/{refs.index(relation.targets[0])}",
                }
            )
        document["relations"] = relations
    document = decode(document)
    validated = _resolutions(spec, resolutions, len(tokens))
    expected = _construct(document, validated, spec)
    if tg.to_data(expected) != tg.to_data(graph):
        raise ValueError("graph is outside the declared source constructor layout")
    return document, tuple(validated)


def graph_profile(spec: SourceProfileSpec) -> type[tg.GraphProfile]:
    """Create a native, explicitly partial profile bound to this declaration."""

    class SourceProfile(tg.GraphProfile):
        name = PROFILE
        required_roles = TIERS
        decides = DECIDES
        leaves_undecided = UNDECIDED

        @classmethod
        def check(cls, graph: tg.Graph, roles: tg.RoleBinding) -> None:
            if roles != spec.roles():
                raise ValueError("source profile role binding mismatch")
            restore(graph, spec)

        @classmethod
        def satisfaction_witness(cls) -> tuple[tg.Graph, tg.RoleBinding]:
            return construct([], [], spec), spec.roles()

        @classmethod
        def refusal_witness(cls) -> tuple[tg.Graph, tg.RoleBinding]:
            graph, roles = cls.satisfaction_witness()
            return graph, {**roles, "source-token": name("source-sound")}

    return SourceProfile
