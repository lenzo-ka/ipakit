"""Current Form admission over native TierGraph facts and explicit bindings."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import fields, replace
from typing import Any

import tiergraph as tg

from ._containment_projection import (
    ContainmentProjection,
    ContainmentProjectionInput,
    _event_payload,
    _unit_from_attributes,
    declared_value,
)
from ._graph_facts import (
    ClockNode,
    Declarations,
    Event,
    EventGroup,
    FeatureDeclaration,
    RefinedSpan,
    Relation,
    RelationDeclaration,
    TierDeclaration,
    Timing,
    _thaw,
)
from ._identity import identity_fingerprint

NS = "urn:ipakit:form"
POINT = tg.QualifiedName(NS, "metadata")
PROFILE = tg.QualifiedName(NS, "profile")
ORDER = tg.QualifiedName(NS, "source-order")
CONSTRUCTION = tg.QualifiedName(NS, "construction-id")
_PROVIDER_FIELDS = (
    "classes",
    "modes",
    "default_mode",
    "bridges",
    "bridge_apertures",
    "projections",
    "types",
    "features",
    "phones",
    "diacritics",
    "separators",
    "zeros",
    "notations",
    "default_notation",
    "ligature_map",
    "lookalikes",
    "wiki_base",
    "references",
    "_value_aliases",
    "_short_to_feature",
    "_feature_to_short",
    "_type_defaults",
    "_arc_landmarks",
    "_nfd_to_registered",
    "derived_phones",
    "supplement_of",
)


def _snapshot(value: Any) -> Any:
    """Own declared provider structure without paths, caches, or repr codecs."""
    from .models import Feature, Phone

    if isinstance(value, (Feature, Phone)):
        return {
            field.name: _snapshot(getattr(value, field.name)) for field in fields(value)
        }
    if isinstance(value, Mapping):
        return [[_snapshot(key), _snapshot(item)] for key, item in value.items()]
    if isinstance(value, (set, frozenset)):
        return sorted((_snapshot(item) for item in value), key=identity_fingerprint)
    if isinstance(value, (tuple, list)):
        return [_snapshot(item) for item in value]
    if value is None or type(value) in (bool, int, float, str):
        return value
    raise ValueError(f"unsupported provider declaration value: {type(value).__name__}")


def provider_identity(inventory: Any) -> str:
    material = {name: _snapshot(getattr(inventory, name)) for name in _PROVIDER_FIELDS}
    material["supplements"] = list(inventory.supplements)
    # The shared identity encoder refuses nonfinite numbers. Snapshot traversal
    # admits only the known declaration types and strict JSON primitive domain.
    return identity_fingerprint(material)


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


def _schema(source: ContainmentProjectionInput, inventory: Any) -> Any:
    """Bind house declarations explicitly and store only declaration differences."""
    from ._ipa_graph import declarations

    base = declarations(inventory)
    if source.declarations == base:
        return "house"
    result: dict[str, Any] = {"closed": source.declarations.closed}
    for key in ("tiers", "features", "relations"):
        baseline = {item.name: item for item in getattr(base, key)}
        records = []
        for item in getattr(source.declarations, key):
            default = baseline.get(item.name, type(item)(item.name))
            changes = {}
            for field in fields(item):
                value, previous = getattr(item, field.name), getattr(
                    default, field.name
                )
                if value != previous:
                    if isinstance(value, frozenset) and isinstance(previous, frozenset):
                        changes[field.name] = {
                            "add": sorted(value - previous),
                            "remove": sorted(previous - value),
                        }
                    else:
                        changes[field.name] = _plain(value)
            records.append([item.name, changes])
        result[key] = records
    return result


def _declarations(schema: Any, inventory: Any) -> Declarations:
    from ._ipa_graph import declarations

    base = declarations(inventory)
    if schema == "house":
        return base
    if (
        not isinstance(schema, dict)
        or set(schema) != {"closed", "tiers", "features", "relations"}
        or type(schema["closed"]) is not bool
    ):
        raise ValueError("malformed Form source declarations")
    result: dict[str, Any] = {}
    for key, cls in (
        ("tiers", TierDeclaration),
        ("features", FeatureDeclaration),
        ("relations", RelationDeclaration),
    ):
        baseline = {item.name: item for item in getattr(base, key)}
        names = {field.name for field in fields(cls)} - {"name"}
        restored = []
        if not isinstance(schema[key], list):
            raise ValueError("Form declaration order must be a sequence")
        for raw in schema[key]:
            if (
                not isinstance(raw, list)
                or len(raw) != 2
                or not isinstance(raw[0], str)
                or not isinstance(raw[1], dict)
                or not set(raw[1]) <= names
            ):
                raise ValueError(f"malformed Form {key} declaration")
            default = baseline.get(raw[0], cls(raw[0]))
            item: dict[str, Any] = {
                field.name: getattr(default, field.name) for field in fields(default)
            }
            for name, value in raw[1].items():
                previous = item[name]
                if isinstance(previous, frozenset) and isinstance(value, dict):
                    if set(value) != {"add", "remove"}:
                        raise ValueError("malformed Form declaration set difference")
                    item[name] = (previous - frozenset(value["remove"])) | frozenset(
                        value["add"]
                    )
                elif (
                    name
                    in {
                        "features",
                        "source_tiers",
                        "target_tiers",
                        "source_kinds",
                        "target_kinds",
                    }
                    and value is not None
                ):
                    item[name] = frozenset(value)
                elif (
                    name
                    in {"native_name", "value_name", "source_arity", "target_arity"}
                    and value is not None
                ):
                    item[name] = tuple(value)
                else:
                    if type(previous) is bool and type(value) is not bool:
                        raise ValueError("Form declaration flags must be booleans")
                    item[name] = value
            restored.append(cls(**item))
        result[key] = tuple(restored)
    return Declarations(**result, closed=schema["closed"])


def _attach(
    graph: tg.Graph,
    owner: tg.ItemRef,
    relation: tg.QualifiedName,
    value: Any,
    index: int,
) -> tg.Graph:
    graph, _, root = tg.embed_json_value(
        graph,
        value,
        namespace=tg.NamespaceDeclaration(f"form-value-{index}", f"{NS}:value:{index}"),
    )
    editor = graph.edit()
    if not any(d.name == relation for d in graph.relation_declarations):
        editor.declare(
            tg.PolyadicRelationDeclaration(
                relation,
                tg.RelationSideDeclaration((tg.RelationEndpointKind.ITEM,), None, 1, 1),
                tg.RelationSideDeclaration((tg.RelationEndpointKind.ITEM,), None, 1, 1),
                unique_sources=True,
            )
        )
    editor.add_relation(tg.PolyadicRelationInstance(relation, (owner,), (root,)))
    return editor.freeze()


def _attribute_fact(
    graph: tg.Graph, owner: tg.ItemRef, name: str, kind: tg.XsdType, lexical: str
) -> tuple[tg.Graph, tg.QualifiedName]:
    """Use native scalar attributes for scalar/known structured domain facts."""
    qualified = tg.QualifiedName(NS, f"fact-{name}-{kind.value}")
    editor = graph.edit()
    if not any(a.name == qualified for a in graph.attribute_declarations):
        editor.declare(
            tg.AttributeDeclaration(qualified, tg.AttributeDomain.ITEM, kind)
        )
    editor.set_attribute(owner, tg.AttributeValue(qualified, kind, lexical))
    return editor.freeze(), qualified


def construct(
    source: ContainmentProjectionInput, inventory: Any, spelling: str | None
) -> tg.Graph:
    """Extend the native core with missing typed facts and profile concerns."""
    from .form import Unit
    from .segment import Segment

    core = ContainmentProjection.from_input(source)
    graph = core.graph
    if any(
        binding.namespace == NS or binding.namespace.startswith(NS + ":")
        for binding in graph.namespaces
    ):
        raise ValueError("Form profile namespace is reserved")
    editor = graph.edit().declare(tg.NamespaceDeclaration("form", NS))
    editor.declare(tg.TierDeclaration(POINT, "Form profile metadata"))
    editor.insert_item(POINT, 0, tg.Item())
    editor.declare(
        tg.AttributeDeclaration(
            ORDER, tg.AttributeDomain.RELATION_INSTANCE, tg.XsdType.INTEGER
        )
    )
    editor.declare(
        tg.AttributeDeclaration(
            CONSTRUCTION, tg.AttributeDomain.ITEM, tg.XsdType.STRING
        )
    )
    graph = editor.freeze()
    # Source order concerns annotate actual native instances; endpoints stay there.
    ordered = list(graph.polyadic_relations)
    used = set()
    for rank, relation in enumerate(source.relations):
        native_name = core.relation_names[relation.name]
        matches = [
            i
            for i, r in enumerate(ordered)
            if i not in used and r.declaration == native_name
        ]
        # Forward construction groups declarations but preserves order within one role.
        if not matches:
            raise ValueError("Form relation source order cannot be represented")
        index = matches[0]
        used.add(index)
        ordered[index] = replace(
            ordered[index],
            attributes=(
                *ordered[index].attributes,
                tg.AttributeValue(ORDER, tg.XsdType.INTEGER, str(rank)),
            ),
        )
    graph = replace(graph, polyadic_relations=tuple(ordered))
    codecs: dict[str, dict[str, Any]] = {}
    value_index = 0
    for path in source.refs:
        event = source.events[path]
        owner = core.old_to_new[path]
        if event.durable_id is not None:
            editor = graph.edit()
            editor.set_attribute(
                owner,
                tg.AttributeValue(CONSTRUCTION, tg.XsdType.STRING, event.durable_id),
            )
            graph = editor.freeze()
        encoded: dict[str, Any] = {}
        unit = event.features.get("unit")
        attributes = dict(
            (name, (kind, lexical)) for name, kind, lexical in _event_payload(event)
        )
        for name in sorted(event.features):
            value = event.features[name]
            declaration = next(
                d for d in source.declarations.features if d.name == name
            )
            if declaration.value_name is not None:
                encoded[name] = ["declared", list(declaration.value_name)]
                continue
            unit_time = (
                (value.timing.start, value.timing.duration)
                if isinstance(value, Unit) and value.timing is not None
                else None
            )
            event_time = (
                (event.timing.start, event.timing.duration)
                if event.timing is not None
                else None
            )
            if name == "unit" and isinstance(value, Unit) and unit_time == event_time:
                encoded[name] = ["unit"]
                continue
            if (
                name == "value"
                and isinstance(unit, Unit)
                and value == (unit.segment if unit.segment is not None else unit.text)
            ):
                encoded[name] = ["unit-value"]
                continue
            if (
                name in attributes
                and type(value) in (str, bool, int)
                and attributes[name][0]
                == {
                    str: tg.XsdType.STRING,
                    bool: tg.XsdType.BOOLEAN,
                    int: tg.XsdType.INTEGER,
                }[type(value)]
            ):
                encoded[name] = ["attribute", type(value).__name__]
                continue
            payload: Any
            if isinstance(value, Segment):
                graph, qualified = _attribute_fact(
                    graph, owner, name + "-segment", tg.XsdType.STRING, value.to_json()
                )
                encoded[name] = ["segment", qualified.to_data()]
                continue
            elif isinstance(value, Unit):
                held = _event_payload(
                    Event(
                        {
                            "unit": value,
                            "input": True,
                            "unit-index": 0,
                        },
                        timing=(
                            Timing(value.timing.start, value.timing.duration)
                            if value.timing
                            else None
                        ),
                    )
                )
                payload = {
                    "kind": "unit",
                    "data": {k: lexical for k, _, lexical in held},
                }
            elif type(value) in (str, bool, int, float):
                kind = {
                    str: tg.XsdType.STRING,
                    bool: tg.XsdType.BOOLEAN,
                    int: tg.XsdType.INTEGER,
                    float: tg.XsdType.DOUBLE,
                }[type(value)]
                lexical = (
                    ("true" if value else "false")
                    if type(value) is bool
                    else str(value)
                )
                graph, qualified = _attribute_fact(graph, owner, name, kind, lexical)
                encoded[name] = ["scalar", qualified.to_data()]
                continue
            else:
                payload = {"kind": "json", "data": _thaw(value)}
            relation_name = tg.QualifiedName(NS, f"fact-{len(codecs)}-{len(encoded)}")
            try:
                graph = _attach(graph, owner, relation_name, payload, value_index)
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    f"unrepresentable Form feature {name!r} at {path}: {exc}"
                ) from exc
            value_index += 1
            encoded[name] = ["native", relation_name.to_data()]
        codecs[path] = encoded
    codec_table: list[dict[str, Any]] = []
    codec_indices: list[int] = []
    codec_keys: dict[str, int] = {}
    for encoded in codecs.values():
        key = identity_fingerprint(encoded)
        if key not in codec_keys:
            codec_keys[key] = len(codec_table)
            codec_table.append(encoded)
        codec_indices.append(codec_keys[key])
    metadata = {
        "profile": "ipakit-form",
        "schema": _schema(source, inventory),
        "inventory": provider_identity(inventory),
        "spelling": spelling,
        "tiers": {k: v.to_data() for k, v in core.tier_names.items()},
        "relations": {k: v.to_data() for k, v in core.relation_names.items()},
        "events": list(source.refs),
        "codecs": {"table": codec_table, "indices": codec_indices},
        "endpoint-kinds": [
            [source.endpoint_kinds[p].value for p in (*r.sources, *r.targets)]
            for r in source.relations
        ],
    }
    return _attach(graph, tg.ItemRef(POINT, 0), PROFILE, metadata, value_index)


def restore(
    graph: tg.Graph, inventory: Any
) -> tuple[ContainmentProjectionInput, str | None]:
    """Validate current native Form layout and decode actual Form source facts."""
    from .segment import Segment

    point = next((tier for tier in graph.tiers if tier.declaration.name == POINT), None)
    if point is None or len(point.items) != 1:
        raise ValueError(
            "native graph requires one current Form profile metadata point"
        )
    metadata = declared_value(graph, tg.ItemRef(POINT, 0), PROFILE)
    expected_keys = {
        "profile",
        "schema",
        "inventory",
        "spelling",
        "tiers",
        "relations",
        "events",
        "codecs",
        "endpoint-kinds",
    }
    if (
        not isinstance(metadata, dict)
        or set(metadata) != expected_keys
        or metadata["profile"] != "ipakit-form"
    ):
        raise ValueError("malformed current Form profile metadata")
    if metadata["inventory"] != provider_identity(inventory):
        raise ValueError("Form restoring inventory declaration identity mismatch")
    spelling = metadata["spelling"]
    if spelling is not None and not isinstance(spelling, str):
        raise ValueError("Form source spelling must be string or null")
    declarations = _declarations(metadata["schema"], inventory)
    refs = {
        path: graph.resolve_item(tg.DurableItemRef(path)) for path in metadata["events"]
    }
    codec_data = metadata["codecs"]
    if not isinstance(codec_data, dict) or set(codec_data) != {"table", "indices"}:
        raise ValueError("Form codec table requires descriptors and event indices")
    table, indices = codec_data["table"], codec_data["indices"]
    if (
        not isinstance(table, list)
        or not all(isinstance(entry, dict) for entry in table)
        or not isinstance(indices, list)
        or len(indices) != len(refs)
        or any(type(i) is not int or i < 0 or i >= len(table) for i in indices)
    ):
        raise ValueError("Form codec indices are not valid and complete")
    codecs = {path: table[i] for path, i in zip(refs, indices, strict=True)}
    if len(refs) != len(metadata["events"]):
        raise ValueError("Form event identity/codecs are not unique and complete")
    reverse = {item: path for path, item in refs.items()}
    clock_name = tg.QualifiedName(
        "https://ipakit.dev/tiergraph/containment-projection/v1", "clock"
    )
    positions = {}
    for position in graph.boundary_values:
        boundary = graph.resolve_boundary(position.reference)
        if boundary.tier == clock_name:
            attrs = {a.name.local_name: a.lexical for a in position.attributes}
            positions[boundary.index] = (int(attrs["tick"]), int(attrs["gap"]))
    if not positions:
        raise ValueError("Form input clock is missing")
    tick_count = max(tick for tick, _ in positions.values()) + 1
    groups: list[dict[str, list[Event]]] = [{} for _ in range(tick_count)]
    for path, owner in refs.items():
        parts = path.split("/")
        if len(parts) != 5 or parts[1] != "clock":
            raise ValueError("Form event identity is not an input-clock coordinate")
        tick, tier, index = (
            int(parts[2]),
            parts[3].replace("~1", "/").replace("~0", "~"),
            int(parts[4]),
        )
        native_tier = tg.QualifiedName(**metadata["tiers"][tier])
        if owner.tier != native_tier:
            raise ValueError("Form event tier role mismatch")
        item = next(t for t in graph.tiers if t.declaration.name == owner.tier).items[
            owner.index
        ]
        attrs = {
            a.name.local_name: a.lexical
            for a in item.attributes
            if a.name.namespace
            == "https://ipakit.dev/tiergraph/containment-projection/v1"
        }
        unit = None
        features = {}
        for name, codec in codecs[path].items():
            kind = codec[0]
            if kind in ("unit", "unit-value"):
                if unit is None:
                    unit = _unit_from_attributes(attrs, inventory)
                value = (
                    unit
                    if kind == "unit"
                    else unit.segment if unit.segment is not None else unit.text
                )
            elif kind == "attribute":
                raw = attrs[name]
                value = (
                    raw
                    if codec[1] == "str"
                    else (
                        int(raw)
                        if codec[1] == "int"
                        else {"true": True, "false": False}[raw]
                    )
                )
            elif kind == "declared":
                value = declared_value(graph, owner, tg.QualifiedName(*codec[1]))
            elif kind in ("scalar", "segment"):
                qualified = tg.QualifiedName(**codec[1])
                attribute = next(a for a in item.attributes if a.name == qualified)
                if kind == "segment":
                    if attribute.value_type != tg.XsdType.STRING:
                        raise ValueError("Form Segment codec requires string attribute")
                    value = Segment.from_dict(json.loads(attribute.lexical), inventory)
                else:
                    raw = attribute.lexical
                    if attribute.value_type == tg.XsdType.STRING:
                        value = raw
                    elif attribute.value_type == tg.XsdType.BOOLEAN:
                        value = {"true": True, "false": False}[raw]
                    elif attribute.value_type == tg.XsdType.INTEGER:
                        value = int(raw)
                    elif attribute.value_type == tg.XsdType.DOUBLE:
                        value = float(raw)
                    else:
                        raise ValueError("unsupported Form scalar domain")
            elif kind == "native":
                payload = declared_value(graph, owner, tg.QualifiedName(**codec[1]))
                if not isinstance(payload, dict) or set(payload) != {"kind", "data"}:
                    raise ValueError("malformed typed Form value")
                value = (
                    Segment.from_dict(payload["data"], inventory)
                    if payload["kind"] == "segment"
                    else (
                        _unit_from_attributes(payload["data"], inventory)
                        if payload["kind"] == "unit"
                        else payload["data"] if payload["kind"] == "json" else None
                    )
                )
                if payload["kind"] not in {"segment", "unit", "json"}:
                    raise ValueError("unsupported Form value codec")
            else:
                raise ValueError("unsupported Form feature codec")
            features[name] = value
            if name == "unit":
                unit = value
        span = (
            RefinedSpan(attrs["span-start"], attrs["span-end"])
            if "span-start" in attrs
            else None
        )
        timing = (
            Timing(float(attrs["timing-start"]), float(attrs["timing-duration"]))
            if "timing-start" in attrs
            else None
        )
        construction = next(
            (a.lexical for a in item.attributes if a.name == CONSTRUCTION), None
        )
        event = Event(
            features,
            int(attrs["structural-duration"]) if span is None else None,
            span,
            timing,
            construction,
        )
        entries = groups[tick].setdefault(tier, [])
        if index != len(entries):
            raise ValueError("Form event order is not contiguous")
        entries.append(event)
    clock = tuple(
        ClockNode(
            max(gap for tick, gap in positions.values() if tick == i),
            tuple(
                EventGroup(t.name, tuple(group[t.name]))
                for t in declarations.tiers
                if t.name in group
            ),
        )
        for i, group in enumerate(groups)
    )
    roles = {
        tg.QualifiedName(**native): local
        for local, native in metadata["relations"].items()
    }
    owned = [
        (int(next(a.lexical for a in r.attributes if a.name == ORDER)), r)
        for r in graph.polyadic_relations
        if r.declaration in roles
    ]
    owned.sort(key=lambda pair: pair[0])
    if [rank for rank, _ in owned] != list(range(len(owned))) or len(owned) != len(
        metadata["endpoint-kinds"]
    ):
        raise ValueError("Form source relation order is not contiguous")
    relations = []
    for rank, relation in owned:
        endpoint_kinds = metadata["endpoint-kinds"][rank]
        if len(endpoint_kinds) != len(relation.sources) + len(relation.targets):
            raise ValueError("Form endpoint kinds do not match relation arity")
        decoded = []
        for endpoint, kind in zip(
            (*relation.sources, *relation.targets), endpoint_kinds, strict=True
        ):
            if kind == "event":
                if not isinstance(endpoint, (tg.ItemRef, tg.DurableItemRef)):
                    raise ValueError("Form event role has a boundary endpoint")
                decoded.append(reverse[graph.resolve_item(endpoint)])
            else:
                if not isinstance(endpoint, tg.DurableBoundaryRef):
                    raise ValueError("Form clock role has an item endpoint")
                boundary = graph.resolve_boundary(endpoint)
                if boundary.tier != clock_name or kind not in {
                    "coarse-tick",
                    "refined-gap",
                }:
                    raise ValueError(
                        "Form endpoint is not a declared input clock position"
                    )
                tick, gap = positions[boundary.index]
                if kind == "coarse-tick" and gap != 0:
                    raise ValueError("Form coarse clock endpoint has a refined gap")
                decoded.append(
                    f"/clock/{tick}"
                    if kind == "coarse-tick"
                    else f"/clock/{tick}/gaps/{gap}"
                )
        relations.append(
            Relation(
                tuple(decoded[: len(relation.sources)]),
                roles[relation.declaration],
                tuple(decoded[len(relation.sources) :]),
            )
        )
    roots_name = tg.QualifiedName(
        "https://ipakit.dev/tiergraph/containment-projection/v1", "roots"
    )
    roots = [r for r in graph.polyadic_relations if r.declaration == roots_name]
    if len(roots) != 1:
        raise ValueError("Form requires exactly one roots instance")
    if any(
        not isinstance(p, (tg.ItemRef, tg.DurableItemRef)) for p in roots[0].targets
    ):
        raise ValueError("Form roots must be event endpoints")
    root_events = [
        p for p in roots[0].targets if isinstance(p, (tg.ItemRef, tg.DurableItemRef))
    ]
    source = ContainmentProjectionInput.from_facts(
        declarations,
        clock,
        relations,
        (reverse[graph.resolve_item(p)] for p in root_events),
    )
    # Reuse the same native constructor as the complete-layout consistency check.
    expected = construct(source, inventory, spelling)
    if tg.to_data(expected) != tg.to_data(graph):
        raise ValueError("native graph is outside the current Form constructor profile")
    return source, spelling


def graph_profile(inventory: Any) -> type[tg.GraphProfile]:
    """Bind a native profile check to an explicit restoring inventory."""

    class FormProfile(tg.GraphProfile):
        name = "ipakit-form:" + provider_identity(inventory)
        required_roles = ("metadata",)
        decides = (
            "current constructor profile and typed role incidence",
            "complete reconstructible Form coordinates and source order",
            "restoring inventory identity and projection consistency",
        )
        leaves_undecided = (
            "linguistic validity of supplied assertions",
            "external provider and alignment truth",
        )

        @classmethod
        def check(cls, graph: tg.Graph, roles: tg.RoleBinding) -> None:
            try:
                if roles["metadata"] != POINT:
                    raise ValueError("Form metadata role binding mismatch")
                restore(graph, inventory)
            except (KeyError, TypeError, IndexError, StopIteration) as exc:
                raise ValueError(f"invalid current Form profile: {exc}") from exc

        @classmethod
        def satisfaction_witness(cls) -> tuple[tg.Graph, tg.RoleBinding]:
            from .form import Form

            return Form.parse("a", inventory).graph, {"metadata": POINT}

        @classmethod
        def refusal_witness(cls) -> tuple[tg.Graph, tg.RoleBinding]:
            return tg.Graph((), (), ()), {"metadata": POINT}

    return FormProfile
