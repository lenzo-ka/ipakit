"""Internal constructor-layout source profile; not public Form admission.

Resolution records are supplied by an explicitly bound caller, never obtained
or repaired here. Native TierGraph is the only persisted representation. This
profile refuses other graph layouts rather than dropping their extra content.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
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
from ._source_receipt import (
    RECEIPT_SCHEMA_ID,
    RECEIPT_SCHEMA_VERSION,
    loads_receipt,
    validate_receipt,
)
from .clts import (
    DATA,
    EXTRACTOR_VERSION,
    ArtifactInvalid,
    Snapshot,
    read_snapshot,
    source_policy,
)

NAMESPACE = "https://ipakit.dev/tiergraph/clts-source/v1"
CORE_BIPA_NAMESPACE = "https://ipakit.dev/tiergraph/clts-core-bipa/v1"
HOUSE_NAMESPACE = "https://ipakit.dev/tiergraph/house-projection/v1"
PROFILE = "ipakit-clts-source"
TIERS = ("source-token", "source-sound", "house-projection", "metadata")
ORDER = tg.QualifiedName(NAMESPACE, "source-order")
type _RelationEndpoint = tg.ItemRef | tg.DurableItemRef | tg.DurableBoundaryRef
type _RestoredSourceProfile = tuple[
    dict[str, Any],
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
]
FINAL_MANIFEST_KIND = "final"
ADAPTER_SCHEMA = {"id": "ipakit-clts-core-bipa-resolution", "version": 1}
ADAPTER_OUTCOMES: dict[str, Any] = {
    "entry": "resolved",
    "excluded": {
        "marker": "marker",
        "unknown-source-spelling": "unknown-sound",
    },
    "absent": "outside-artifact-domain",
}
PROJECTION_POLICY = {"name": "explicit-only", "version": 1, "unsupported": "error"}
PROFILE_FAMILY = {"id": PROFILE, "version": 1}
_MANIFEST_FIELDS = (
    "schema",
    "kind",
    "domain",
    "source-policy",
    "extractor",
    "artifacts",
    "license",
    "house-declarations",
    "adapter",
    "projection-policy",
    "profile-family",
)
DECIDES = (
    "constructor-layout source retention and declared schema",
    "input clock, timings and caller tone-host links",
    "caller-supplied house facts, coverage and mapping identity",
)
UNDECIDED = (
    "external resolver truth and house projection computation",
    "public Form and downstream consumer admission",
)


def name(local: str) -> tg.QualifiedName:
    return tg.QualifiedName(NAMESPACE, local)


def _owned_json(value: Any) -> Any:
    """Own every container accepted by the native JSON value constructor."""
    _, profile, root = tg.json_value_graph(value)
    return _freeze(profile.value(root))


@dataclass(frozen=True, eq=False)
class SourceProfileSpec:
    """Explicit supplied provider binding and complete qualified claim schema."""

    source: SourceMetadata
    provider_fingerprint: str
    manifest_fingerprint: str
    mapping_identity: str
    kinds: tuple[str, ...]
    fields: tuple[FeatureDeclaration, ...] = ()
    house_fields: tuple[FeatureDeclaration, ...] = ()
    domains: Mapping[str, tuple[Any, ...]] = field(default_factory=dict)
    manifest_kind: str = field(kw_only=True)
    identity: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.source, SourceMetadata):
            raise ValueError("source metadata must use the shared declaration")
        if any(not isinstance(v, str) or not v for v in self.source.to_dict().values()):
            raise ValueError("source metadata fields must be nonempty strings")
        object.__setattr__(self, "fields", tuple(self.fields))
        if any(
            not isinstance(v, str) or not v
            for v in (
                self.provider_fingerprint,
                self.manifest_fingerprint,
                self.manifest_kind,
                self.mapping_identity,
            )
        ):
            raise ValueError(
                "explicit provider, manifest and mapping identities are required"
            )
        object.__setattr__(self, "kinds", tuple(self.kinds))
        if (
            not self.kinds
            or any(not isinstance(k, str) or not k for k in self.kinds)
            or len(set(self.kinds)) != len(self.kinds)
        ):
            raise ValueError("provider must declare its distinct resolved sound kinds")
        object.__setattr__(self, "house_fields", tuple(self.house_fields))
        reserved = {
            "raw",
            "time",
            "resolution",
            "projection",
            "kind",
            "canonical",
            "profile",
            "coverage",
        }
        declared_fields = (*self.fields, *self.house_fields)
        if any(
            f.value_name is None or f.name in reserved for f in declared_fields
        ) or len({f.name for f in declared_fields}) != len(declared_fields):
            raise ValueError(
                "source and house fields require distinct qualified identities"
            )
        domains = {
            key: tuple(_owned_json(value) for value in values)
            for key, values in self.domains.items()
        }
        if domains.keys() - {f.name for f in self.fields} or any(
            not values for values in domains.values()
        ):
            raise ValueError("domains must name declared fields and be nonempty")
        object.__setattr__(self, "domains", MappingProxyType(domains))
        declarations(self)
        object.__setattr__(self, "identity", metadata(self)["fingerprint"])

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SourceProfileSpec):
            return NotImplemented
        return self.identity == other.identity

    def __hash__(self) -> int:
        return hash(self.identity)

    def roles(self) -> dict[str, Any]:
        return {tier: name(tier) for tier in TIERS}


def declarations(spec: SourceProfileSpec) -> Declarations:
    """Declare roles and source claims independently of observed events."""
    own = tuple(
        FeatureDeclaration(key, (NAMESPACE, key))
        for key in (
            "raw",
            "time",
            "resolution",
            "projection",
            "kind",
            "canonical",
            "profile",
            "coverage",
        )
    )
    admitted: tuple[set[str], ...] = (
        {"raw", "time", "resolution", "projection"},
        {"kind", "canonical", *(f.name for f in spec.fields)},
        {f.name for f in spec.house_fields},
        {"profile", "coverage"},
    )
    return Declarations(
        tuple(
            TierDeclaration(tier, frozenset(keys), (NAMESPACE, tier))
            for tier, keys in zip(TIERS, admitted, strict=True)
        ),
        own + spec.fields + spec.house_fields,
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
            RelationDeclaration(
                "projects",
                source_tiers=frozenset({"source-sound"}),
                target_tiers=frozenset({"house-projection"}),
                source_arity=(1, None),
                target_arity=(1, None),
                native_name=(NAMESPACE, "projects"),
                unique_sources=True,
            ),
        ),
    )


def _schema(spec: SourceProfileSpec) -> dict[str, Any]:
    empty = ContainmentProjection.from_input(
        FactBuilder(declarations(spec)).build_input()
    ).graph
    empty = _declare_relation_order(empty)
    return {
        "namespaces": [item.to_data() for item in empty.namespaces],
        "tiers": [tier.declaration.to_data() for tier in empty.tiers],
        "relations": [item.to_data() for item in empty.relation_declarations],
        "attributes": [item.to_data() for item in empty.attribute_declarations],
    }


def _profile_material(spec: SourceProfileSpec) -> dict[str, Any]:
    """Return all fingerprint material, including the mapping edge."""
    return {
        "id": PROFILE,
        "version": 1,
        "roles": {key: value.to_data() for key, value in spec.roles().items()},
        "schema": _schema(spec),
        "fields": {item.name: list(item.value_name or ()) for item in spec.fields},
        "house-fields": {
            item.name: list(item.value_name or ()) for item in spec.house_fields
        },
        "domains": {
            key: [_thaw(v) for v in values] for key, values in spec.domains.items()
        },
        "kinds": list(spec.kinds),
        "source": spec.source.to_dict(),
        "provider": spec.provider_fingerprint,
        "manifest": {
            "kind": spec.manifest_kind,
            "fingerprint": spec.manifest_fingerprint,
        },
        "mapping": spec.mapping_identity,
        "coverage": {
            "source_complete": "one retained resolution record per input occurrence",
            "house_complete": (
                "true exactly when every input occurrence is supported; true for empty input"
            ),
        },
        "invalidation": (
            "stored projection mapping identity must equal the profile mapping identity"
        ),
        "decides": list(DECIDES),
        "undecided": list(UNDECIDED),
    }


def profile_basis(spec: SourceProfileSpec) -> str:
    """Fingerprint the complete source-profile material except its mapping."""
    material = _profile_material(spec)
    del material["mapping"]
    return identity_fingerprint(material)


def metadata(spec: SourceProfileSpec) -> dict[str, Any]:
    """Fingerprint declarations/conditions, not the digest or instance values."""
    material = _profile_material(spec)
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
            status
            not in (
                "resolved",
                "unknown-sound",
                "marker",
                "outside-artifact-domain",
            )
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


def projection_coverage(
    projections: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Derive the declared transaction flags from per-occurrence outcomes."""
    house_complete = all(item.get("status") == "supported" for item in projections)
    return {
        "status": "complete" if house_complete else "preserved",
        "source_complete": True,
        "house_complete": house_complete,
    }


def _projections(
    spec: SourceProfileSpec,
    values: Sequence[Mapping[str, Any]],
    resolutions: Sequence[Mapping[str, Any]],
    count: int,
) -> list[dict[str, Any]]:
    if (
        not isinstance(values, Sequence)
        or isinstance(values, (str, bytes))
        or len(values) != count
    ):
        raise InputError(
            "invalid-projection",
            "",
            "one supplied projection per source token is required",
        )
    output = []
    fields = {item.name for item in spec.house_fields}
    for index, (value, resolution) in enumerate(zip(values, resolutions, strict=True)):
        path = f"/tokens/{index}/projection"
        if not isinstance(value, Mapping):
            raise InputError("invalid-projection", path, "projection must be a record")
        status = value.get("status")
        expected = (
            {
                "supported": {"mapping", "status", "facts"},
                "unsupported": {"mapping", "status", "code"},
                "not-attempted": {"mapping", "status"},
            }.get(status)
            if isinstance(status, str)
            else None
        )
        if expected is None or set(value) != expected:
            raise InputError(
                "invalid-projection", path, "status and projection fields disagree"
            )
        if value["mapping"] != spec.mapping_identity:
            raise InputError(
                "mapping-mismatch", path, "projection belongs to another mapping"
            )
        if status == "unsupported":
            if not isinstance(value["code"], str) or not value["code"]:
                raise InputError(
                    "invalid-projection", path, "unsupported projection needs a code"
                )
            output.append(
                {
                    "mapping": spec.mapping_identity,
                    "status": status,
                    "code": value["code"],
                }
            )
            continue
        if status == "not-attempted":
            output.append({"mapping": spec.mapping_identity, "status": status})
            continue
        facts = value["facts"]
        if (
            not resolution["sounds"]
            or not isinstance(facts, (list, tuple))
            or not facts
        ):
            raise InputError(
                "invalid-projection",
                path,
                "supported projection needs a resolved source and house facts",
            )
        copied = []
        for fact in facts:
            if not isinstance(fact, Mapping) or not fact or set(fact) - fields:
                raise InputError(
                    "invalid-projection", path, "undeclared or empty house fact"
                )
            for claim in fact.values():
                try:
                    tg.json_value_graph(claim)
                except (TypeError, ValueError) as error:
                    raise InputError("invalid-value", path, str(error)) from error
            copied.append(dict(fact))
        output.append(
            {"mapping": spec.mapping_identity, "status": status, "facts": copied}
        )
    return output


def _declare_relation_order(graph: tg.Graph) -> tg.Graph:
    """Declare ORDER in the schema graph before caller relations are stored."""
    declaration = tg.AttributeDeclaration(
        ORDER, tg.AttributeDomain.RELATION_INSTANCE, tg.XsdType.INTEGER
    )
    if declaration in graph.attribute_declarations:
        return graph
    return graph.edit().declare(declaration).freeze()


def _store_relation_order(
    graph: tg.Graph,
    document: Mapping[str, Any],
    projections: Sequence[Mapping[str, Any]],
) -> tg.Graph:
    """Annotate host and projection instances with caller order after lowering."""
    relations = graph.polyadic_relations
    editor = graph.edit()
    declaration = tg.AttributeDeclaration(
        ORDER, tg.AttributeDomain.RELATION_INSTANCE, tg.XsdType.INTEGER
    )
    if declaration not in graph.attribute_declarations:
        editor.declare(declaration)

    host_indices: dict[
        tuple[tuple[_RelationEndpoint, ...], tuple[_RelationEndpoint, ...]], list[int]
    ] = {}
    resolves_by_source: dict[
        tuple[_RelationEndpoint, ...], list[tg.PolyadicRelationInstance]
    ] = {}
    project_indices: dict[tuple[_RelationEndpoint, ...], list[int]] = {}
    for index, relation in enumerate(relations):
        if relation.declaration == name("source-tone-host"):
            host_indices.setdefault((relation.sources, relation.targets), []).append(
                index
            )
        elif relation.declaration == name("resolves"):
            resolves_by_source.setdefault(relation.sources, []).append(relation)
        elif relation.declaration == name("projects"):
            project_indices.setdefault(relation.sources, []).append(index)

    used: set[int] = set()
    for rank, relation in enumerate(document.get("relations", [])):
        source_index = endpoint(
            relation["source"], len(document["tokens"]), f"/relations/{rank}/source"
        )
        target_index = endpoint(
            relation["target"], len(document["tokens"]), f"/relations/{rank}/target"
        )
        source = tg.ItemRef(name("source-token"), source_index)
        target = tg.ItemRef(name("source-token"), target_index)
        matches = [
            index
            for index in host_indices.get(((source,), (target,)), ())
            if index not in used
        ]
        if len(matches) != 1:
            raise ValueError("source host relation order cannot be represented")
        index = matches[0]
        used.add(index)
        editor.set_attribute(
            tg.PolyadicInstanceRef(index),
            tg.AttributeValue(ORDER, tg.XsdType.INTEGER, str(rank)),
        )
    project_rank = 0
    for token_index, projection in enumerate(projections):
        if projection["status"] != "supported":
            continue
        token = tg.ItemRef(name("source-token"), token_index)
        resolves = resolves_by_source.get((token,), ())
        if len(resolves) != 1:
            raise ValueError("projection source order cannot be represented")
        matches = [
            index
            for index in project_indices.get(resolves[0].targets, ())
            if index not in used
        ]
        if len(matches) != 1:
            raise ValueError("projection relation order cannot be represented")
        index = matches[0]
        used.add(index)
        editor.set_attribute(
            tg.PolyadicInstanceRef(index),
            tg.AttributeValue(ORDER, tg.XsdType.INTEGER, str(project_rank)),
        )
        project_rank += 1
    return editor.freeze()


def _file_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ArtifactInvalid(
            f"required CLTS manifest input is unavailable: {path.name}"
        ) from exc


def manifest_metadata(
    data_dir: Path = DATA,
    *,
    inventory: Any | None = None,
    snapshot: Snapshot | None = None,
) -> dict[str, Any]:
    """Recompute the final core-BIPA receipt from shipped bytes and declarations."""
    from . import load_ipa_features
    from ._form_profile import provider_identity

    snapshot_path = data_dir / "core.json"
    if snapshot is None:
        snapshot = read_snapshot(snapshot_path)
        snapshot_bytes = snapshot_path.read_bytes()
    else:
        snapshot_bytes = snapshot.dumps().encode("utf-8")
    snapshot_data = snapshot.to_data()
    if snapshot_data["domain"] != "core-bipa":
        raise ArtifactInvalid("the final CLTS manifest requires the core-BIPA artifact")
    if inventory is None:
        inventory = load_ipa_features()
    policy = source_policy()
    material = {
        "schema": {"id": RECEIPT_SCHEMA_ID, "version": RECEIPT_SCHEMA_VERSION},
        "kind": FINAL_MANIFEST_KIND,
        "domain": "core-bipa",
        "source-policy": policy,
        "extractor": {
            "id": "ipakit.clts.extract_snapshot",
            "version": EXTRACTOR_VERSION,
        },
        "artifacts": {
            "ipakit/data/clts/core.json": {
                "sha256": hashlib.sha256(snapshot_bytes).hexdigest(),
                "identity": snapshot.identity,
                "schema": {
                    "id": snapshot_data["schema"],
                    "version": snapshot_data["version"],
                },
            }
        },
        "license": {
            "id": policy["source"]["license"],
            "notices": {
                name: _file_sha256(data_dir / name)
                for name in ("NOTICE.txt", "MAPPING-NOTICE.txt")
            },
        },
        "house-declarations": {"fingerprint": provider_identity(inventory)},
        "adapter": {
            "schema": dict(ADAPTER_SCHEMA),
            "outcomes": json.loads(json.dumps(ADAPTER_OUTCOMES)),
        },
        "projection-policy": dict(PROJECTION_POLICY),
        "profile-family": dict(PROFILE_FAMILY),
    }
    manifest = {**material, "fingerprint": identity_fingerprint(material)}
    try:
        validate_receipt(manifest)
    except ValueError as exc:
        raise ArtifactInvalid(f"invalid generated CLTS manifest: {exc}") from exc
    return manifest


def dumps_manifest(data_dir: Path = DATA, *, snapshot: Snapshot | None = None) -> str:
    """Render the deterministic offline CLTS manifest."""
    return (
        json.dumps(
            manifest_metadata(data_dir, snapshot=snapshot),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )


def verify_manifest(
    path: Path | None = None,
    *,
    data_dir: Path = DATA,
    inventory: Any | None = None,
) -> str:
    """Verify the committed receipt against the bytes and declarations it binds."""
    manifest_path = path or data_dir / "manifest.json"
    try:
        actual = loads_receipt(manifest_path.read_bytes())
        if not set(_MANIFEST_FIELDS) <= set(actual):
            raise ValueError("CLTS manifest lacks required final fields")
        expected = manifest_metadata(data_dir, inventory=inventory)
        for field in _MANIFEST_FIELDS:
            if actual[field] != expected[field]:
                raise ArtifactInvalid(f"stale CLTS manifest field: {field}")
        return str(actual["fingerprint"])
    except (OSError, ValueError) as exc:
        if isinstance(exc, ArtifactInvalid):
            raise
        raise ArtifactInvalid(f"invalid CLTS manifest: {exc}") from exc


def require_manifest_kind(spec: SourceProfileSpec, expected: str) -> None:
    """Require an explicit manifest kind."""
    if not isinstance(expected, str) or not expected:
        raise ValueError("expected manifest kind must be a nonempty string")
    if spec.manifest_kind != expected:
        raise ValueError(
            f"manifest kind mismatch: expected {expected!r}, "
            f"found {spec.manifest_kind!r}"
        )


def require_final_manifest(spec: SourceProfileSpec) -> None:
    """Require the verified shipped final receipt bound by this profile."""
    require_manifest_kind(spec, FINAL_MANIFEST_KIND)
    fingerprint = verify_manifest()
    if spec.manifest_fingerprint != fingerprint:
        raise ArtifactInvalid("source profile does not bind the verified CLTS manifest")


def _core_bipa_spec(
    snapshot: Snapshot, manifest_fingerprint: str, mapping_identity: str
) -> SourceProfileSpec:
    data = snapshot.to_data()
    if data["domain"] != "core-bipa":
        raise ValueError("core-BIPA profile requires the finite core snapshot")
    source = data["source"]["source"]
    return SourceProfileSpec(
        SourceMetadata(
            source["upstream"],
            source["upstream-url"],
            source["artifact"],
            source["version"],
            source["license"],
            source["kind"],
        ),
        snapshot.identity,
        manifest_fingerprint,
        mapping_identity,
        ("consonant", "vowel", "tone"),
        tuple(
            FeatureDeclaration(field, (CORE_BIPA_NAMESPACE, field))
            for field in ("features", "alias", "normalized", "declaration")
        ),
        (
            FeatureDeclaration("house-symbol", (HOUSE_NAMESPACE, "symbol")),
            FeatureDeclaration("house-kind", (HOUSE_NAMESPACE, "kind")),
        ),
        manifest_kind=FINAL_MANIFEST_KIND,
    )


def core_bipa_basis(snapshot: Snapshot | None = None) -> str:
    """Recompute the acyclic profile basis from shipped declarations and bytes."""
    snapshot = read_snapshot() if snapshot is None else snapshot
    manifest = manifest_metadata(snapshot=snapshot)
    spec = _core_bipa_spec(
        snapshot,
        str(manifest["fingerprint"]),
        "profile-basis-excludes-mapping",
    )
    return profile_basis(spec)


def core_bipa_spec(
    snapshot: Snapshot | None = None, mapping_identity: str | None = None
) -> SourceProfileSpec:
    """Bind the internal source profile to the shipped finite core snapshot."""
    snapshot = read_snapshot() if snapshot is None else snapshot
    if mapping_identity is None:
        from .clts_mapping import read_authority

        mapping_identity = read_authority().identity
    shipped = read_snapshot()
    if snapshot.identity != shipped.identity:
        raise ArtifactInvalid(
            "core-BIPA profile requires the manifested shipped snapshot"
        )
    manifest_fingerprint = verify_manifest()
    return _core_bipa_spec(snapshot, manifest_fingerprint, mapping_identity)


def core_bipa_resolutions(
    snapshot: Snapshot, raws: Sequence[str]
) -> tuple[dict[str, Any], ...]:
    """Resolve exact core keys without normalization or productive fallback."""
    data = snapshot.to_data()
    if data["domain"] != "core-bipa":
        raise ValueError("core-BIPA adapter requires the finite core snapshot")
    entries, excluded = data["entries"], data["excluded"]
    records = []
    for raw in raws:
        if not isinstance(raw, str) or not raw:
            raise ValueError("core-BIPA lookup keys must be nonempty strings")
        if raw in entries:
            entry = entries[raw]
            records.append(
                {
                    "provider": snapshot.identity,
                    "status": ADAPTER_OUTCOMES["entry"],
                    "sounds": [
                        {
                            "kind": entry["kind"],
                            "canonical": entry["canonical"],
                            "values": {
                                key: entry[key]
                                for key in (
                                    "features",
                                    "alias",
                                    "normalized",
                                    "declaration",
                                )
                            },
                        }
                    ],
                }
            )
            continue
        reason = excluded.get(raw)
        status = ADAPTER_OUTCOMES["excluded"].get(reason, ADAPTER_OUTCOMES["absent"])
        records.append({"provider": snapshot.identity, "status": status, "sounds": []})
    return tuple(records)


def _construct(
    document: dict[str, Any],
    resolutions: list[dict[str, Any]],
    projections: list[dict[str, Any]],
    spec: SourceProfileSpec,
) -> tg.Graph:
    builder = FactBuilder(declarations(spec))
    tokens = []
    for index, (token, resolution, projection) in enumerate(
        zip(document["tokens"], resolutions, projections, strict=True)
    ):
        features = {
            "raw": token["raw"],
            "resolution": {key: resolution[key] for key in ("provider", "status")},
            "projection": {
                key: projection[key]
                for key in ("mapping", "status", "code")
                if key in projection
            },
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
        if projection["status"] == "supported":
            house = builder.add_ordered_sequence(
                "house-projection",
                index,
                [EventSpec(fact, duration=0) for fact in projection["facts"]],
                derivation_step=1,
                source_site_order=index,
                application_order=0,
            )
            builder.relate(children, "projects", house)
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
        {
            "profile": {
                **metadata(spec),
                "relations-present": "relations" in document,
                "relation-count": len(document.get("relations", [])),
            },
            "coverage": projection_coverage(projections),
        },
        duration=0,
    )
    graph = ContainmentProjection.from_input(builder.build_input()).graph
    return _store_relation_order(graph, document, projections)


def construct(
    value: Any,
    resolutions: Sequence[Mapping[str, Any]],
    projections: Sequence[Mapping[str, Any]],
    spec: SourceProfileSpec,
) -> tg.Graph:
    """Lower strict ingress and caller-supplied source/house outcomes."""
    document = decode(value)
    records = _resolutions(spec, resolutions, len(document["tokens"]))
    projected = _projections(spec, projections, records, len(document["tokens"]))
    try:
        return _construct(document, records, projected, spec)
    except InputError:
        raise
    except ValueError as error:
        raise InputError("invalid-source-graph", "", str(error)) from error


def _items(graph: tg.Graph, tier: str) -> tuple[tg.ItemRef, ...]:
    tiers = [entry for entry in graph.tiers if entry.declaration.name == name(tier)]
    if len(tiers) != 1:
        raise ValueError("source profile role tier missing")
    return tuple(tg.ItemRef(name(tier), index) for index in range(len(tiers[0].items)))


def restore(graph: tg.Graph, spec: SourceProfileSpec) -> _RestoredSourceProfile:
    """Validate and restore this constructor layout, without live resolution.

    Extra content or alternate equivalent layouts are refused, never discarded.
    Native reconstruction checks the complete clock, declarations and relations.
    """
    points = _items(graph, "metadata")
    if len(points) != 1:
        raise ValueError("expected one source profile metadata point")
    held = declared_value(graph, points[0], name("profile"))
    if (
        not isinstance(held, dict)
        or type(held.get("relations-present")) is not bool
        or type(held.get("relation-count")) is not int
        or held["relation-count"] < 0
    ):
        raise ValueError("malformed source profile metadata")
    present = held.pop("relations-present")
    relation_count = held.pop("relation-count")
    if not present and relation_count != 0:
        raise ValueError("malformed source relation presence metadata")
    if identity_fingerprint(held) != identity_fingerprint(metadata(spec)):
        raise ValueError("source profile declaration or provider fingerprint mismatch")
    stored_coverage = declared_value(graph, points[0], name("coverage"))
    tokens: list[dict[str, Any]] = []
    resolutions: list[dict[str, Any]] = []
    stored_projections: list[dict[str, Any]] = []
    sound_refs: list[tuple[tg.ItemRef, ...]] = []
    refs = _items(graph, "source-token")
    for ref in refs:
        token = {"raw": declared_value(graph, ref, name("raw"))}
        resolved = graph.resolve_item(ref)
        item = next(
            tier for tier in graph.tiers if tier.declaration.name == resolved.tier
        ).items[resolved.index]
        if any(attribute.name == name("time") for attribute in item.attributes):
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
        current_sound_refs = tuple(
            child for child in links[0].targets if isinstance(child, tg.ItemRef)
        )
        if len(current_sound_refs) != len(links[0].targets):
            raise ValueError("invalid resolution child")
        sounds = []
        for child in current_sound_refs:
            if child.tier != name("source-sound"):
                raise ValueError("invalid resolution child")
            values = {}
            for declared in spec.fields:
                assert declared.value_name is not None
                qualified = tg.QualifiedName(*declared.value_name)
                resolved_child = graph.resolve_item(child)
                child_item = next(
                    tier
                    for tier in graph.tiers
                    if tier.declaration.name == resolved_child.tier
                ).items[resolved_child.index]
                if any(
                    attribute.name == qualified for attribute in child_item.attributes
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
        projection = declared_value(graph, ref, name("projection"))
        if not isinstance(projection, dict):
            raise ValueError("malformed stored projection status")
        stored_projections.append(projection)
        sound_refs.append(current_sound_refs)
    from ._scalar_attribute import scalar_lexical

    projections = []
    ordered_projects = []
    used_projects: set[int] = set()
    project_relations = [
        relation
        for relation in graph.polyadic_relations
        if relation.declaration == name("projects")
    ]
    supported_tokens = []
    for token_index, (projection, source_children) in enumerate(
        zip(stored_projections, sound_refs, strict=True)
    ):
        if projection.get("status") != "supported":
            projections.append(projection)
            continue
        supported_tokens.append(token_index)
        matches = [
            (index, relation)
            for index, relation in enumerate(project_relations)
            if index not in used_projects and relation.sources == source_children
        ]
        if len(matches) != 1:
            raise ValueError("supported projection requires one projects relation")
        project_index, relation = matches[0]
        used_projects.add(project_index)
        if not relation.targets or any(
            not isinstance(target, tg.ItemRef)
            or target.tier != name("house-projection")
            for target in relation.targets
        ):
            raise ValueError("invalid house projection child")
        house_children = tuple(
            target for target in relation.targets if isinstance(target, tg.ItemRef)
        )
        order_values = [
            attribute for attribute in relation.attributes if attribute.name == ORDER
        ]
        if len(order_values) != 1:
            raise ValueError("projects relation requires one source-order")
        rank = int(scalar_lexical(order_values[0]))
        ordered_projects.append((rank, token_index))
        facts = []
        for child in house_children:
            fact = {}
            resolved_child = graph.resolve_item(child)
            child_item = next(
                tier
                for tier in graph.tiers
                if tier.declaration.name == resolved_child.tier
            ).items[resolved_child.index]
            for declared in spec.house_fields:
                assert declared.value_name is not None
                qualified = tg.QualifiedName(*declared.value_name)
                if any(
                    attribute.name == qualified for attribute in child_item.attributes
                ):
                    fact[declared.name] = declared_value(graph, child, qualified)
            facts.append(fact)
        projections.append({**projection, "facts": facts})
    if len(used_projects) != len(project_relations):
        raise ValueError("house fact is not owned by a supported projection")
    ordered_projects.sort()
    if [rank for rank, _ in ordered_projects] != list(range(len(ordered_projects))) or [
        token for _, token in ordered_projects
    ] != supported_tokens:
        raise ValueError("projects relation order does not match supplied token order")
    document: dict[str, Any] = {"format": FORMAT, "version": 1, "tokens": tokens}
    if present:
        ordered = []
        host_relations = [
            relation
            for relation in graph.polyadic_relations
            if relation.declaration == name("source-tone-host")
        ]
        if len(host_relations) != relation_count:
            raise ValueError("stored source relation count mismatch")
        for relation in host_relations:
            if (
                len(relation.sources) != 1
                or len(relation.targets) != 1
                or relation.sources[0] not in refs
                or relation.targets[0] not in refs
            ):
                raise ValueError("malformed stored host relation")
            order_values = [
                attribute
                for attribute in relation.attributes
                if attribute.name == ORDER
            ]
            if len(order_values) != 1:
                raise ValueError("source host relation requires one source-order")
            ordered.append((int(scalar_lexical(order_values[0])), relation))
        ordered.sort(key=lambda pair: pair[0])
        if [rank for rank, _ in ordered] != list(range(relation_count)):
            raise ValueError("source host relation order is not contiguous")
        relations = []
        for _, relation in ordered:
            relations.append(
                {
                    "type": HOST,
                    "source": f"/tokens/{refs.index(relation.sources[0])}",
                    "target": f"/tokens/{refs.index(relation.targets[0])}",
                }
            )
        document["relations"] = relations
    elif relation_count != 0 or any(
        relation.declaration == name("source-tone-host")
        for relation in graph.polyadic_relations
    ):
        raise ValueError("stored source relation count mismatch")
    document = decode(document)
    validated = _resolutions(spec, resolutions, len(tokens))
    validated_projections = _projections(spec, projections, validated, len(tokens))
    if stored_coverage != projection_coverage(validated_projections):
        raise ValueError(
            "stored projection coverage does not match occurrence outcomes"
        )
    expected = _construct(document, validated, validated_projections, spec)
    if tg.to_data(expected) != tg.to_data(graph):
        raise ValueError("graph is outside the declared source constructor layout")
    return document, tuple(validated), tuple(validated_projections)


def graph_profile(spec: SourceProfileSpec) -> type[tg.GraphProfile]:
    """Create a native, explicitly partial profile bound to this declaration."""

    class SourceProfile(tg.GraphProfile):
        name = f"{PROFILE}:{spec.identity}"
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
            return construct([], [], [], spec), spec.roles()

        @classmethod
        def refusal_witness(cls) -> tuple[tg.Graph, tg.RoleBinding]:
            graph, roles = cls.satisfaction_witness()
            return graph, {**roles, "source-token": name("source-sound")}

    return SourceProfile
