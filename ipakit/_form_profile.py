"""Current Form admission over native TierGraph facts and explicit bindings."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, replace
from typing import Any, cast

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
TIER_ROLE = tg.QualifiedName(NS, "tier-role")
RELATION_ROLE = tg.QualifiedName(NS, "relation-role")
SOURCE_EVENTS = tg.QualifiedName(NS, "source-events")
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


class _ProviderIdentityState:
    """One provider's cached declaration identity and mutation generation."""

    def __init__(self) -> None:
        self.revision = 0
        self.cached_revision = -1
        self.cached_identity: str | None = None
        self.root_names = frozenset((*_PROVIDER_FIELDS, "supplements"))

    def invalidate(self) -> None:
        self.revision += 1
        self.cached_identity = None

    def wrap(self, value: Any) -> Any:
        """Make mutable declaration containers invalidate this state."""
        from .models import Feature, Phone

        if isinstance(value, (_TrackedDict, _TrackedList, _TrackedSet)):
            if value._identity_state is self:
                return value
        if isinstance(value, dict):
            return _TrackedDict(value, self)
        if isinstance(value, list):
            return _TrackedList(value, self)
        if isinstance(value, set):
            return _TrackedSet(value, self)
        if isinstance(value, tuple):
            return tuple(self.wrap(item) for item in value)
        if isinstance(value, (Feature, Phone)):
            for field in fields(value):
                object.__setattr__(
                    value, field.name, self.wrap(getattr(value, field.name))
                )
            object.__setattr__(value, "_ipakit_form_identity_state", self)
        return value


class _TrackedDict(dict[Any, Any]):
    """Declaration mapping that invalidates its provider identity on writes."""

    def __init__(self, value: Mapping[Any, Any], state: _ProviderIdentityState):
        self._identity_state = state
        dict.__init__(self, ((key, state.wrap(item)) for key, item in value.items()))

    def __setitem__(self, key: Any, value: Any) -> None:
        dict.__setitem__(self, key, self._identity_state.wrap(value))
        self._identity_state.invalidate()

    def __delitem__(self, key: Any) -> None:
        dict.__delitem__(self, key)
        self._identity_state.invalidate()

    def clear(self) -> None:
        if self:
            dict.clear(self)
            self._identity_state.invalidate()

    def pop(self, key: Any, *default: Any) -> Any:
        present = key in self
        value = dict.pop(self, key, *default)
        if present:
            self._identity_state.invalidate()
        return value

    def popitem(self) -> tuple[Any, Any]:
        value = dict.popitem(self)
        self._identity_state.invalidate()
        return value

    def setdefault(self, key: Any, default: Any = None) -> Any:
        if key in self:
            return dict.__getitem__(self, key)
        value = self._identity_state.wrap(default)
        dict.__setitem__(self, key, value)
        self._identity_state.invalidate()
        return value

    def update(self, *args: Any, **kwargs: Any) -> None:
        incoming = dict(*args, **kwargs)
        if not incoming:
            return
        for key, value in incoming.items():
            dict.__setitem__(self, key, self._identity_state.wrap(value))
        self._identity_state.invalidate()

    def __ior__(self, other: Any) -> _TrackedDict:  # type: ignore[misc]
        self.update(other)
        return self


class _TrackedList(list[Any]):
    """Declaration sequence that invalidates its provider identity on writes."""

    def __init__(self, value: list[Any], state: _ProviderIdentityState):
        self._identity_state = state
        list.__init__(self, (state.wrap(item) for item in value))

    def __setitem__(self, key: Any, value: Any) -> None:
        if isinstance(key, slice):
            value = [self._identity_state.wrap(item) for item in value]
        else:
            value = self._identity_state.wrap(value)
        list.__setitem__(self, key, value)
        self._identity_state.invalidate()

    def __delitem__(self, key: Any) -> None:
        list.__delitem__(self, key)
        self._identity_state.invalidate()

    def append(self, value: Any) -> None:
        list.append(self, self._identity_state.wrap(value))
        self._identity_state.invalidate()

    def extend(self, value: Any) -> None:
        held = [self._identity_state.wrap(item) for item in value]
        if held:
            list.extend(self, held)
            self._identity_state.invalidate()

    def insert(self, index: int, value: Any) -> None:  # type: ignore[override]
        list.insert(self, index, self._identity_state.wrap(value))
        self._identity_state.invalidate()

    def pop(self, index: int = -1) -> Any:  # type: ignore[override]
        value = list.pop(self, index)
        self._identity_state.invalidate()
        return value

    def remove(self, value: Any) -> None:
        list.remove(self, value)
        self._identity_state.invalidate()

    def clear(self) -> None:
        if self:
            list.clear(self)
            self._identity_state.invalidate()

    def reverse(self) -> None:
        list.reverse(self)
        self._identity_state.invalidate()

    def sort(self, *args: Any, **kwargs: Any) -> None:
        list.sort(self, *args, **kwargs)
        self._identity_state.invalidate()

    def __iadd__(self, value: Any) -> _TrackedList:  # type: ignore[misc]
        self.extend(value)
        return self

    def __imul__(self, value: int) -> _TrackedList:  # type: ignore[override,misc]
        list.__imul__(self, value)
        self._identity_state.invalidate()
        return self


class _TrackedSet(set[Any]):
    """Declaration set that invalidates its provider identity on writes."""

    def __init__(self, value: set[Any], state: _ProviderIdentityState):
        self._identity_state = state
        set.__init__(self, value)

    def add(self, value: Any) -> None:
        before = len(self)
        set.add(self, value)
        if len(self) != before:
            self._identity_state.invalidate()

    def discard(self, value: Any) -> None:
        before = len(self)
        set.discard(self, value)
        if len(self) != before:
            self._identity_state.invalidate()

    def remove(self, value: Any) -> None:
        set.remove(self, value)
        self._identity_state.invalidate()

    def pop(self) -> Any:
        value = set.pop(self)
        self._identity_state.invalidate()
        return value

    def clear(self) -> None:
        if self:
            set.clear(self)
            self._identity_state.invalidate()

    def update(self, *others: Any) -> None:
        before = set(self)
        set.update(self, *others)
        if self != before:
            self._identity_state.invalidate()

    def intersection_update(self, *others: Any) -> None:
        before = set(self)
        set.intersection_update(self, *others)
        if self != before:
            self._identity_state.invalidate()

    def difference_update(self, *others: Any) -> None:
        before = set(self)
        set.difference_update(self, *others)
        if self != before:
            self._identity_state.invalidate()

    def symmetric_difference_update(self, other: Any) -> None:
        before = set(self)
        set.symmetric_difference_update(self, other)
        if self != before:
            self._identity_state.invalidate()

    def __ior__(self, other: Any) -> _TrackedSet:  # type: ignore[misc]
        self.update(other)
        return self

    def __iand__(self, other: Any) -> _TrackedSet:  # type: ignore[misc]
        self.intersection_update(other)
        return self

    def __isub__(self, other: Any) -> _TrackedSet:  # type: ignore[misc]
        self.difference_update(other)
        return self

    def __ixor__(self, other: Any) -> _TrackedSet:  # type: ignore[misc]
        self.symmetric_difference_update(other)
        return self


def _provider_identity_state(inventory: Any) -> _ProviderIdentityState:
    state = inventory.__dict__.get("_ipakit_form_identity_state")
    if state is not None:
        return cast(_ProviderIdentityState, state)
    state = _ProviderIdentityState()
    for name in (*_PROVIDER_FIELDS, "supplements"):
        object.__setattr__(inventory, name, state.wrap(getattr(inventory, name)))
    object.__setattr__(inventory, "_ipakit_form_identity_state", state)
    return state


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
    state = _provider_identity_state(inventory)
    if state.cached_identity is not None and state.cached_revision == state.revision:
        return state.cached_identity
    material = {name: _snapshot(getattr(inventory, name)) for name in _PROVIDER_FIELDS}
    material["supplements"] = list(inventory.supplements)
    # The shared identity encoder refuses nonfinite numbers. Snapshot traversal
    # admits only the known declaration types and strict JSON primitive domain.
    identity = identity_fingerprint(material)
    state.cached_identity = identity
    state.cached_revision = state.revision
    return identity


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


def _json_attribute_fact(
    graph: tg.Graph, owner: tg.ItemRef, name: str, value: Any
) -> tuple[tg.Graph, tg.QualifiedName]:
    """Attach one owned JSON fact without inventing a value subgraph."""
    qualified = tg.QualifiedName(NS, f"fact-{name}-json")
    editor = graph.edit()
    if not any(a.name == qualified for a in graph.attribute_declarations):
        editor.declare(
            tg.AttributeDeclaration(
                qualified, tg.AttributeDomain.ITEM, tg.JsonType.JSON
            )
        )
    editor.set_attribute(owner, tg.JsonAttributeValue(qualified, value))
    return editor.freeze(), qualified


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
    """Extend the native core with one JSON profile and explicit native roles."""
    from .form import Unit
    from .segment import Segment

    core = ContainmentProjection.from_input(source)
    graph = core.graph
    if any(
        binding.namespace == NS or binding.namespace.startswith(NS + ":")
        for binding in graph.namespaces
    ):
        raise ValueError("Form profile namespace is reserved")
    if any(
        declaration.name.local_name in {TIER_ROLE.local_name, RELATION_ROLE.local_name}
        for declaration in graph.attribute_declarations
    ):
        raise ValueError("foreign-qualified Form role declaration shadows house role")

    editor = graph.edit().declare(tg.NamespaceDeclaration("form", NS))
    editor.declare(tg.TierDeclaration(POINT, "Form profile metadata"))
    editor.insert_item(POINT, 0, tg.Item())
    for profile_declaration in (
        tg.AttributeDeclaration(PROFILE, tg.AttributeDomain.ITEM, tg.JsonType.JSON),
        tg.AttributeDeclaration(
            ORDER, tg.AttributeDomain.RELATION_INSTANCE, tg.XsdType.INTEGER
        ),
        tg.AttributeDeclaration(
            CONSTRUCTION, tg.AttributeDomain.ITEM, tg.XsdType.STRING
        ),
        tg.AttributeDeclaration(TIER_ROLE, tg.AttributeDomain.TIER, tg.XsdType.STRING),
        tg.AttributeDeclaration(
            RELATION_ROLE,
            tg.AttributeDomain.RELATION_DECLARATION,
            tg.XsdType.STRING,
        ),
    ):
        editor.declare(profile_declaration)
    editor.declare(
        tg.PolyadicRelationDeclaration(
            SOURCE_EVENTS,
            tg.RelationSideDeclaration((tg.RelationEndpointKind.ITEM,), (POINT,), 1, 1),
            tg.RelationSideDeclaration(
                (tg.RelationEndpointKind.ITEM,),
                tuple(core.tier_names.values()),
                0,
                None,
                allow_empty=True,
            ),
            unique_sources=True,
            distinct_targets=True,
        )
    )
    for tier_role, tier_name in core.tier_names.items():
        editor.set_attribute(
            tier_name, tg.AttributeValue(TIER_ROLE, tg.XsdType.STRING, tier_role)
        )
    for relation_role, relation_name in core.relation_names.items():
        editor.set_attribute(
            relation_name,
            tg.AttributeValue(RELATION_ROLE, tg.XsdType.STRING, relation_role),
        )
    editor.add_relation(
        tg.PolyadicRelationInstance(
            SOURCE_EVENTS,
            (tg.ItemRef(POINT, 0),),
            tuple(core.old_to_new[path] for path in source.refs),
        )
    )
    graph = editor.freeze()

    # Source order annotates the actual native instances; endpoints stay there.
    ordered = list(graph.polyadic_relations)
    used: set[int] = set()
    for rank, relation in enumerate(source.relations):
        native_name = core.relation_names[relation.name]
        matches = [
            i
            for i, candidate in enumerate(ordered)
            if i not in used and candidate.declaration == native_name
        ]
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
    for path in source.refs:
        event = source.events[path]
        house_event = replace(event, features=source.house_features(event))
        owner = core.old_to_new[path]
        if event.durable_id is not None:
            editor = graph.edit()
            editor.set_attribute(
                owner,
                tg.AttributeValue(CONSTRUCTION, tg.XsdType.STRING, event.durable_id),
            )
            graph = editor.freeze()
        encoded: dict[str, Any] = {}
        unit = house_event.features.get("unit")
        attributes = {
            name: (kind, value) for name, kind, value in _event_payload(house_event)
        }
        for feature_name in sorted(event.features):
            value = event.features[feature_name]
            source_feature = next(
                d for d in source.declarations.features if d.name == feature_name
            )
            if source_feature.value_name is not None:
                encoded[feature_name] = ["declared", list(source_feature.value_name)]
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
            if (
                feature_name == "unit"
                and isinstance(value, Unit)
                and unit_time == event_time
            ):
                encoded[feature_name] = ["unit"]
                continue
            if (
                feature_name == "value"
                and isinstance(unit, Unit)
                and value == (unit.segment if unit.segment is not None else unit.text)
            ):
                encoded[feature_name] = ["unit-value"]
                continue
            if (
                feature_name in attributes
                and type(value) in (str, bool, int)
                and attributes[feature_name][0]
                == {
                    str: tg.XsdType.STRING,
                    bool: tg.XsdType.BOOLEAN,
                    int: tg.XsdType.INTEGER,
                }[type(value)]
            ):
                encoded[feature_name] = ["attribute", type(value).__name__]
                continue
            if isinstance(value, Segment):
                graph, qualified = _json_attribute_fact(
                    graph, owner, feature_name + "-segment", value.to_dict()
                )
                encoded[feature_name] = ["segment", qualified.to_data()]
                continue
            if isinstance(value, Unit):
                held = _event_payload(
                    Event(
                        {"unit": value, "input": True, "unit-index": 0},
                        timing=(
                            Timing(value.timing.start, value.timing.duration)
                            if value.timing
                            else None
                        ),
                    )
                )
                payload: Any = {key: item for key, _, item in held}
                codec = "unit-json"
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
                graph, qualified = _attribute_fact(
                    graph, owner, feature_name, kind, lexical
                )
                encoded[feature_name] = ["scalar", qualified.to_data()]
                continue
            else:
                payload = _thaw(value)
                codec = "json"
            try:
                graph, qualified = _json_attribute_fact(
                    graph, owner, f"{feature_name}-{len(encoded)}", payload
                )
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    f"unrepresentable Form feature {feature_name!r} at {path}: {exc}"
                ) from exc
            encoded[feature_name] = [codec, qualified.to_data()]
        codecs[path] = encoded

    codec_table: list[dict[str, Any]] = []
    codec_indices: list[int] = []
    codec_keys: dict[str, int] = {}
    for path in source.refs:
        encoded = codecs[path]
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
        "codecs": {"table": codec_table, "indices": codec_indices},
        "endpoint-kinds": [
            [source.endpoint_kinds[p].value for p in (*r.sources, *r.targets)]
            for r in source.relations
        ],
    }
    editor = graph.edit()
    editor.set_attribute(tg.ItemRef(POINT, 0), tg.JsonAttributeValue(PROFILE, metadata))
    return editor.freeze()


def restore(
    graph: tg.Graph, inventory: Any
) -> tuple[ContainmentProjectionInput, str | None]:
    """Validate the native Form profile and decode its actual source facts."""
    from ._scalar_attribute import scalar_lexical
    from .segment import Segment

    for local_name, exact in (
        (TIER_ROLE.local_name, TIER_ROLE),
        (RELATION_ROLE.local_name, RELATION_ROLE),
    ):
        shadows = [
            declaration.name
            for declaration in graph.attribute_declarations
            if declaration.name.local_name == local_name and declaration.name != exact
        ]
        if shadows:
            raise ValueError(f"foreign-qualified Form role shadows {exact.local_name}")

    required_declarations = {
        PROFILE: (tg.AttributeDomain.ITEM, tg.JsonType.JSON),
        TIER_ROLE: (tg.AttributeDomain.TIER, tg.XsdType.STRING),
        RELATION_ROLE: (
            tg.AttributeDomain.RELATION_DECLARATION,
            tg.XsdType.STRING,
        ),
    }
    for required_name, (domain, value_type) in required_declarations.items():
        matches = [
            attribute_declaration
            for attribute_declaration in graph.attribute_declarations
            if attribute_declaration.name == required_name
        ]
        if (
            len(matches) != 1
            or matches[0].domain != domain
            or matches[0].value_type != value_type
        ):
            raise ValueError(
                "missing or schema-inconsistent Form profile "
                f"{required_name.local_name}"
            )

    point = next((tier for tier in graph.tiers if tier.declaration.name == POINT), None)
    if point is None or len(point.items) != 1:
        raise ValueError(
            "native graph requires one current Form profile metadata point"
        )
    profile_values = [
        attribute
        for attribute in point.items[0].attributes
        if attribute.name == PROFILE
    ]
    if len(profile_values) != 1 or not isinstance(
        profile_values[0], tg.JsonAttributeValue
    ):
        raise ValueError("Form profile metadata must be one JSON attribute")
    raw_metadata = profile_values[0].to_value()
    expected_keys = {
        "profile",
        "schema",
        "inventory",
        "spelling",
        "codecs",
        "endpoint-kinds",
    }
    if (
        not isinstance(raw_metadata, dict)
        or set(raw_metadata) != expected_keys
        or raw_metadata["profile"] != "ipakit-form"
    ):
        raise ValueError("malformed current Form profile metadata")
    metadata = cast(dict[str, Any], raw_metadata)
    if metadata["inventory"] != provider_identity(inventory):
        raise ValueError("Form restoring inventory declaration identity mismatch")
    spelling = metadata["spelling"]
    if spelling is not None and not isinstance(spelling, str):
        raise ValueError("Form source spelling must be string or null")
    declarations = _declarations(metadata["schema"], inventory)

    def role(attributes: tuple[Any, ...], name: tg.QualifiedName) -> str | None:
        matches = [attribute for attribute in attributes if attribute.name == name]
        if not matches:
            return None
        if len(matches) != 1:
            raise ValueError(f"duplicate {name.local_name} binding")
        return scalar_lexical(matches[0])

    tier_roles: dict[str, tg.QualifiedName] = {}
    for graph_tier in graph.tiers:
        label = role(graph_tier.attributes, TIER_ROLE)
        if label is None:
            continue
        if label in tier_roles:
            raise ValueError("duplicate Form tier role binding")
        tier_roles[label] = graph_tier.declaration.name
    if set(tier_roles) != {declaration.name for declaration in declarations.tiers}:
        raise ValueError("missing or schema-inconsistent Form tier role binding")
    for index, source_tier in enumerate(declarations.tiers):
        expected_tier_name = (
            tg.QualifiedName(*source_tier.native_name)
            if source_tier.native_name is not None
            else tg.QualifiedName(
                "https://ipakit.dev/tiergraph/containment-projection/v1",
                f"tier-{index}",
            )
        )
        if tier_roles[source_tier.name] != expected_tier_name:
            raise ValueError("Form tier role binding disagrees with source schema")

    relation_roles: dict[str, tg.QualifiedName] = {}
    for graph_relation_declaration in graph.relation_declarations:
        label = role(graph_relation_declaration.attributes, RELATION_ROLE)
        if label is None:
            continue
        if label in relation_roles:
            raise ValueError("duplicate Form relation role binding")
        relation_roles[label] = graph_relation_declaration.name
    if set(relation_roles) != {
        declaration.name for declaration in declarations.relations
    }:
        raise ValueError("missing or schema-inconsistent Form relation role binding")
    for source_relation_declaration in declarations.relations:
        if source_relation_declaration.native_name is not None and relation_roles[
            source_relation_declaration.name
        ] != tg.QualifiedName(*source_relation_declaration.native_name):
            raise ValueError("Form relation role binding disagrees with source schema")

    source_event_declarations = [
        declaration
        for declaration in graph.relation_declarations
        if declaration.name == SOURCE_EVENTS
    ]
    source_event_relations = [
        relation
        for relation in graph.polyadic_relations
        if relation.declaration == SOURCE_EVENTS
    ]
    if len(source_event_declarations) != 1 or len(source_event_relations) != 1:
        raise ValueError("Form requires exactly one source-events association")
    source_events = source_event_relations[0]
    if source_events.sources != (tg.ItemRef(POINT, 0),):
        raise ValueError("Form source-events must source the metadata item")
    if len(source_events.targets) != len(set(source_events.targets)):
        raise ValueError("Form source-events targets must be distinct")

    refs: dict[str, tg.ItemRef] = {}
    for endpoint in source_events.targets:
        if not isinstance(endpoint, (tg.ItemRef, tg.DurableItemRef)):
            raise ValueError("Form source-events targets must be items")
        owner = graph.resolve_item(endpoint)
        item = next(
            tier for tier in graph.tiers if tier.declaration.name == owner.tier
        ).items[owner.index]
        path = item.durable_id
        if path is None or path in refs:
            raise ValueError("Form source event identity must be unique and durable")
        refs[path] = owner
    expected_items = {
        tg.ItemRef(tier.declaration.name, index)
        for tier in graph.tiers
        if tier.declaration.name in set(tier_roles.values())
        for index in range(len(tier.items))
    }
    if set(refs.values()) != expected_items:
        raise ValueError("Form source-events order is not exhaustive")

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
    codecs: dict[str, dict[str, Any]] = {
        path: cast(dict[str, Any], table[cast(int, i)])
        for path, i in zip(refs, indices, strict=True)
    }

    reverse = {item: path for path, item in refs.items()}
    clock_name = tg.QualifiedName(
        "https://ipakit.dev/tiergraph/containment-projection/v1", "clock"
    )
    positions: dict[int, tuple[int, int]] = {}
    for position in graph.boundary_values:
        boundary = graph.resolve_boundary(position.reference)
        if boundary.tier == clock_name:
            position_attrs = {
                attribute.name.local_name: scalar_lexical(attribute)
                for attribute in position.attributes
            }
            positions[boundary.index] = (
                int(position_attrs["tick"]),
                int(position_attrs["gap"]),
            )
    if not positions:
        raise ValueError("Form input clock is missing")
    tick_count = max(tick for tick, _ in positions.values()) + 1
    groups: list[dict[str, list[Event]]] = [{} for _ in range(tick_count)]

    for path, owner in refs.items():
        parts = path.split("/")
        if len(parts) != 5 or parts[1] != "clock":
            raise ValueError("Form event identity is not an input-clock coordinate")
        tick, source_tier_role, index = (
            int(parts[2]),
            parts[3].replace("~1", "/").replace("~0", "~"),
            int(parts[4]),
        )
        if (
            source_tier_role not in tier_roles
            or owner.tier != tier_roles[source_tier_role]
        ):
            raise ValueError("Form event tier role mismatch")
        item = next(t for t in graph.tiers if t.declaration.name == owner.tier).items[
            owner.index
        ]
        attrs: dict[str, Any] = {
            attribute.name.local_name: (
                attribute.to_value()
                if isinstance(attribute, tg.JsonAttributeValue)
                else scalar_lexical(attribute)
            )
            for attribute in item.attributes
            if attribute.name.namespace
            == "https://ipakit.dev/tiergraph/containment-projection/v1"
        }
        unit = None
        features: dict[str, Any] = {}
        for feature_name, codec in codecs[path].items():
            if (
                not isinstance(codec, list)
                or not codec
                or not isinstance(codec[0], str)
            ):
                raise ValueError("malformed Form feature codec")
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
                raw = attrs[feature_name]
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
            elif kind in ("scalar", "segment", "unit-json", "json"):
                qualified = tg.QualifiedName(**cast(dict[str, str], codec[1]))
                attribute_values = [
                    candidate
                    for candidate in item.attributes
                    if candidate.name == qualified
                ]
                if len(attribute_values) != 1:
                    raise ValueError("Form feature codec attribute is missing")
                attribute = attribute_values[0]
                if kind == "scalar":
                    raw = scalar_lexical(attribute)
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
                else:
                    if not isinstance(attribute, tg.JsonAttributeValue):
                        raise ValueError("Form JSON codec requires JSON attribute")
                    payload = attribute.to_value()
                    if kind == "segment":
                        if not isinstance(payload, dict):
                            raise ValueError("malformed Form Segment payload")
                        value = Segment.from_dict(payload, inventory)
                    elif kind == "unit-json":
                        if not isinstance(payload, dict):
                            raise ValueError("malformed Form Unit payload")
                        value = _unit_from_attributes(payload, inventory)
                    else:
                        value = payload
            else:
                raise ValueError("unsupported Form feature codec")
            features[feature_name] = value
            if feature_name == "unit":
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
        construction_values = [
            attribute for attribute in item.attributes if attribute.name == CONSTRUCTION
        ]
        construction = (
            scalar_lexical(construction_values[0])
            if len(construction_values) == 1
            else None
        )
        if len(construction_values) > 1:
            raise ValueError("duplicate Form construction id")
        event = Event(
            features,
            int(attrs["structural-duration"]) if span is None else None,
            span,
            timing,
            construction,
        )
        entries = groups[tick].setdefault(source_tier_role, [])
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
    roles = {native: local for local, native in relation_roles.items()}
    owned: list[tuple[int, Any]] = []
    for relation in graph.polyadic_relations:
        if relation.declaration not in roles:
            continue
        order_values = [
            attribute for attribute in relation.attributes if attribute.name == ORDER
        ]
        if len(order_values) != 1:
            raise ValueError("Form source relation requires one source-order")
        owned.append((int(scalar_lexical(order_values[0])), relation))
    owned.sort(key=lambda pair: pair[0])
    endpoint_metadata = metadata["endpoint-kinds"]
    if (
        not isinstance(endpoint_metadata, list)
        or [rank for rank, _ in owned] != list(range(len(owned)))
        or len(owned) != len(endpoint_metadata)
    ):
        raise ValueError("Form source relation order is not contiguous")
    relations = []
    for rank, relation in owned:
        endpoint_kinds = endpoint_metadata[rank]
        if not isinstance(endpoint_kinds, list) or len(endpoint_kinds) != len(
            relation.sources
        ) + len(relation.targets):
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
        not isinstance(endpoint, (tg.ItemRef, tg.DurableItemRef))
        for endpoint in roots[0].targets
    ):
        raise ValueError("Form roots must be event endpoints")
    root_endpoints = cast(tuple[tg.ItemRef | tg.DurableItemRef, ...], roots[0].targets)
    source = ContainmentProjectionInput.from_facts(
        declarations,
        clock,
        relations,
        (reverse[graph.resolve_item(endpoint)] for endpoint in root_endpoints),
    )
    if tuple(refs) != source.refs:
        raise ValueError("Form source-events targets are outside codebook order")
    expected_graph = construct(source, inventory, spelling)
    if tg.to_data(expected_graph) != tg.to_data(graph):
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
