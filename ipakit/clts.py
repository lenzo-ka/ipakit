"""CLTS finite geometry, declaration audits, and development extraction.

Frozen reads and declaration censuses require no pyclts. Explicit development
extraction loads the pinned oracle lazily. This is not a full CLTS Form
importer or semantic correspondence table.
"""

from __future__ import annotations

import collections
import csv
import hashlib
import io
import itertools
import json
import subprocess
import unicodedata
from collections.abc import Sequence
from importlib import metadata
from pathlib import Path
from typing import Any, cast

from . import load_ipa_features
from ._identity import identity_fingerprint
from ._provenance import SourceMetadata
from .extraction import (
    BuildResult,
    SourceContentError,
    SourceError,
    SourceIdentity,
    SourceMissingError,
    SourceVersionError,
)
from .feature_sets import FeatureSets

SOUNDS_TSV = ("data", "sounds.tsv")
FEATURES_TSV = ("data", "features.tsv")
MASTER_FEATURES = ("pkg", "transcriptionsystems", "features.json")

DATA = Path(__file__).parent / "data" / "clts"
SNAPSHOT_VERSION = 1
EXTRACTOR_VERSION = "1"


class ArtifactInvalid(ValueError):
    """An artifact is malformed or not bound to the selected source policy."""

    code = "artifact-invalid"


class ResolverUnavailable(SourceError):
    """An explicitly requested development resolver is not installed."""

    code = "resolver-unavailable"


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """JSON must not silently overwrite duplicate declaration keys."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _audit_tsv(
    data: bytes, columns: set[str], *, identity: str = "ID"
) -> list[dict[str, str]]:
    reader = csv.DictReader(
        io.StringIO(data.decode("utf-8"), newline=""), delimiter="\t", strict=True
    )
    try:
        header = reader.fieldnames or []
        rows = list(reader)
    except csv.Error as exc:
        raise ValueError(f"invalid TSV quoting: {exc}") from exc
    if len(header) != len(set(header)) or not (columns | {identity}).issubset(header):
        raise ValueError(f"invalid TSV header; required columns: {sorted(columns)}")
    ids: set[str] = set()
    for row in rows:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("ragged TSV row")
        if not row[identity].strip() or row[identity] in ids:
            raise ValueError(f"empty or duplicate TSV {identity}: {row[identity]!r}")
        ids.add(row[identity])
    if not rows:
        raise ValueError("empty TSV population")
    return rows


def declaration_audit(root: Path) -> dict[str, Any]:
    """Census declarations, not semantic mappings; no pyclts required.

    Master domains are independent of the derived feature catalog and sound
    observations. Qualified triples retain context even when values share a
    spelling. Every queue entry is explicitly unclassified, in each direction.
    """
    paths = [MASTER_FEATURES, FEATURES_TSV, SOUNDS_TSV]
    inputs = {"/".join(p): root.joinpath(*p).read_bytes() for p in paths}
    master = json.loads(
        inputs["/".join(MASTER_FEATURES)], object_pairs_hook=_unique_object
    )
    declared: set[tuple[str, str, str]] = set()
    if not isinstance(master, dict) or not master:
        raise ValueError("master declarations must be a nonempty object")
    for kind, domains in master.items():
        if not kind.strip() or not isinstance(domains, dict) or not domains:
            raise ValueError(f"invalid unit declaration: {kind!r}")
        for feature, values in domains.items():
            if (
                not feature.strip()
                or not isinstance(values, list)
                or not values
                or any(not isinstance(v, str) or not v.strip() for v in values)
            ):
                raise ValueError(f"invalid domain: {kind}/{feature}")
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate value: {kind}/{feature}")
            declared.update((kind, feature, value) for value in values)
    catalog = _audit_tsv(
        inputs["/".join(FEATURES_TSV)], {"ID", "TYPE", "FEATURE", "VALUE"}
    )
    sounds = _audit_tsv(
        inputs["/".join(SOUNDS_TSV)], {"ID", "TYPE", "FEATURES", "GRAPHEME"}
    )
    catalog_ids: dict[str, tuple[str, str, str]] = {}
    catalog_triples: set[tuple[str, str, str]] = set()
    for row in catalog:
        triple = (row["TYPE"], row["FEATURE"], row["VALUE"])
        if any(not part.strip() for part in triple) or triple in catalog_triples:
            raise ValueError(f"empty or duplicate qualified catalog feature: {triple}")
        catalog_triples.add(triple)
        catalog_ids[row["ID"]] = triple
    witnesses: dict[tuple[str, str, str], list[str]] = collections.defaultdict(list)
    contexts: dict[tuple[str, str, str], collections.Counter[str]] = (
        collections.defaultdict(collections.Counter)
    )
    kinds: collections.Counter[str] = collections.Counter()
    occurrences: collections.Counter[tuple[str, str, str]] = collections.Counter()
    for row in sounds:
        if not row["TYPE"].strip() or not row["GRAPHEME"].strip():
            raise ValueError(f"empty sound type or grapheme: {row['ID']}")
        refs = row["FEATURES"].split()
        if not refs:
            raise ValueError(
                f"featureless sound row is outside this census: {row['ID']}"
            )
        kinds[row["TYPE"]] += 1
        for ref in refs:
            if ref not in catalog_ids:
                raise ValueError(f"unknown feature reference: {ref}")
            occurrences[catalog_ids[ref]] += 1
        # Composite sounds can repeat a feature in multiple constituents.
        # Keep occurrence counts, but a sound remains one catalog witness.
        for ref in set(refs):
            triple = catalog_ids[ref]
            witnesses[triple].append(row["ID"])
            contexts[triple][row["TYPE"]] += 1
    ipa = load_ipa_features()
    native = []
    for name, feature in sorted(ipa.features.items()):
        for index, value in enumerate(feature.values):
            native.append(
                {
                    "source": ["ipakit", name, value],
                    "status": "unclassified",
                    "direction": "ipakit-to-clts",
                    "targets": [],
                    "context": {
                        "applies": sorted(feature.applies),
                        "mode": feature.mode,
                        "locus": feature.locus,
                        "type": feature.type,
                        "sequence": feature.sequence,
                        "axis": feature.axis,
                        "default": feature.default,
                        "center": feature.center,
                        "offscale": value in feature.offscale,
                        "value_index": index,
                        "vocabulary": feature.vocabulary,
                    },
                }
            )
    if not native:
        raise ValueError("empty native declaration population")
    records = []
    for triple in sorted(declared | catalog_triples):
        records.append(
            {
                "source": ["clts", *triple],
                "status": "unclassified",
                "direction": "clts-to-ipakit",
                "targets": [],
                "declared": triple in declared,
                "cataloged": triple in catalog_triples,
                "observed_count": len(witnesses[triple]),
                "observed_occurrences": occurrences[triple],
                "observed_unit_kinds": dict(sorted(contexts[triple].items())),
                "witness_ids": sorted(witnesses[triple])[:5],
            }
        )
    return {
        "schema": "ipakit-clts-declaration-census",
        "version": 1,
        "audit_status": "unclassified",
        "semantic_correspondences_audited": 0,
        "sources": {
            "clts": {
                name: hashlib.sha256(data).hexdigest()
                for name, data in sorted(inputs.items())
            },
            "ipakit": {
                "ipa.xml": hashlib.sha256(ipa.xml_path.read_bytes()).hexdigest()
            },
        },
        "scope": {
            "modeled": "finite feature/value declarations and catalog feature observations",
            "witness_limit_per_declaration": 5,
            "outside": [
                "semantic correspondences",
                "productive composite-unit rules",
                "tier/host relationships",
                "native combined and sequence-valued expressions",
            ],
            "catalog_unit_kinds_without_master_domains": sorted(
                set(kinds) - set(master)
            ),
        },
        "catalog": {"sounds": len(sounds), "unit_kinds": dict(sorted(kinds.items()))},
        "clts_to_ipakit": records,
        "ipakit_to_clts": native,
    }


def source_policy() -> dict[str, Any]:
    """The one accepted source/content/license tuple, packaged beside the data."""
    return cast(
        dict[str, Any],
        json.loads(
            (DATA / "source.json").read_bytes(), object_pairs_hook=_unique_object
        ),
    )


def _source_metadata(pin: dict[str, Any]) -> SourceMetadata:
    source = pin["source"]
    return SourceMetadata(
        source["upstream"],
        source["upstream-url"],
        source["artifact"],
        source["version"],
        source["license"],
        source["kind"],
    )


def validate_source(root: Path) -> SourceIdentity:
    """Refuse unavailable, wrong-revision or changed accepted inputs offline."""
    pin = source_policy()
    try:
        run = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise SourceMissingError(
            "git is required to validate the pinned CLTS checkout"
        ) from exc
    if run.returncode:
        raise SourceMissingError(f"supply a CLTS Git checkout: {root}")
    if run.stdout.strip() != pin["source"]["version"]:
        raise SourceVersionError(f"CLTS must be at {pin['source']['version']}")
    hashes = {}
    for name, expected in pin["inputs"].items():
        try:
            hashes[name] = hashlib.sha256((root / name).read_bytes()).hexdigest()
        except OSError as exc:
            raise SourceMissingError(
                f"required CLTS source is unavailable: {name}"
            ) from exc
        if hashes[name] != expected:
            raise SourceContentError(f"CLTS input differs from accepted bytes: {name}")
    dirty = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain", "--", *hashes],
        check=False,
        capture_output=True,
        text=True,
    )
    if dirty.returncode or dirty.stdout:
        raise SourceContentError("accepted CLTS input paths must have clean Git state")
    return SourceIdentity(_source_metadata(pin), hashes)


def _resolver(root: Path) -> Any:
    pin = source_policy()
    try:
        version = metadata.version("pyclts")
    except metadata.PackageNotFoundError as exc:
        raise ResolverUnavailable(
            "install ipakit[interop] for explicit CLTS extraction"
        ) from exc
    if version != pin["resolver"]["version"]:
        raise SourceVersionError(
            f"CLTS extraction requires pyclts=={pin['resolver']['version']}; found {version}"
        )
    try:
        import pyclts
        from pyclts.datatypes import TranscriptionSystem
    except ImportError as exc:
        raise ResolverUnavailable(
            "install the complete ipakit[interop] development extra"
        ) from exc
    provider_root = Path(pyclts.__file__).parent
    for name, expected in pin["resolver"]["inputs"].items():
        try:
            actual = hashlib.sha256((provider_root / name).read_bytes()).hexdigest()
        except OSError as exc:
            raise ResolverUnavailable(
                f"pyclts installation lacks pinned source: {name}"
            ) from exc
        if actual != expected:
            raise SourceContentError(
                f"pyclts source differs from accepted content: {name}"
            )
    validate_source(root)
    systems = root / "pkg/transcriptionsystems"
    return TranscriptionSystem(
        systems / "bipa", systems / "transcription-system-metadata.json"
    )


class Snapshot:
    """Validated finite CLTS sound features; not a productive resolver or Form."""

    def __init__(self, data: dict[str, Any]) -> None:
        try:
            self._validate(data)
        except (KeyError, TypeError, ValueError) as exc:
            raise ArtifactInvalid(f"invalid CLTS feature snapshot: {exc}") from exc
        # Copy through the one JSON encoding so caller mutation cannot change identity.
        self._data = json.loads(json.dumps(data, ensure_ascii=False, allow_nan=False))
        self._geometry = FeatureSets(
            f"clts/{data['domain']}/{data['identity']}",
            {key: frozenset(row["features"]) for key, row in data["entries"].items()},
        )

    @staticmethod
    def _validate(data: dict[str, Any]) -> None:
        keys = {
            "schema",
            "version",
            "extractor_version",
            "source",
            "domain",
            "requested",
            "entries",
            "excluded",
            "identity",
        }
        if not isinstance(data, dict) or set(data) != keys:
            raise ValueError("unexpected snapshot fields")
        if (
            data["schema"] != "ipakit-clts-feature-snapshot"
            or type(data["version"]) is not int
            or data["version"] != SNAPSHOT_VERSION
        ):
            raise ValueError("unsupported snapshot schema/version")
        if (
            data["extractor_version"] != EXTRACTOR_VERSION
            or data["source"] != source_policy()
        ):
            raise ValueError("source/resolver/content pin mismatch")
        if data["domain"] not in ("core-bipa", "supplied-tokens"):
            raise ValueError("unsupported finite domain")
        if (
            identity_fingerprint({k: v for k, v in data.items() if k != "identity"})
            != data["identity"]
        ):
            raise ValueError("snapshot content identity mismatch")
        requested = data["requested"]
        if (
            not isinstance(requested, list)
            or not requested
            or any(not isinstance(k, str) or not k for k in requested)
            or requested != sorted(set(requested))
        ):
            raise ValueError("requested keys must be sorted, unique nonempty strings")
        entries, excluded = data["entries"], data["excluded"]
        if (
            not isinstance(entries, dict)
            or not entries
            or not isinstance(excluded, dict)
        ):
            raise ValueError(
                "snapshot requires a nonempty scored domain and excluded accounting"
            )
        if set(entries) & set(excluded) or set(entries) | set(excluded) != set(
            requested
        ):
            raise ValueError(
                "requested domain is not partitioned into scored/excluded keys"
            )
        for key, row in entries.items():
            if set(row) != {
                "canonical",
                "kind",
                "features",
                "alias",
                "normalized",
                "declaration",
            }:
                raise ValueError(f"unexpected entry fields: {key}")
            kinds = (
                ("consonant", "vowel", "tone")
                if data["domain"] == "core-bipa"
                else ("consonant", "vowel", "tone", "cluster", "diphthong")
            )
            if (
                row["kind"] not in kinds
                or not isinstance(row["canonical"], str)
                or not row["canonical"]
            ):
                raise ValueError(f"unsupported sound kind or canonical spelling: {key}")
            labels = row["features"]
            if (
                not isinstance(labels, list)
                or any(not isinstance(x, str) or not x for x in labels)
                or labels != sorted(set(labels))
                or row["kind"] not in labels
            ):
                raise ValueError(f"invalid raw feature set: {key}")
            if type(row["alias"]) is not bool or type(row["normalized"]) is not bool:
                raise ValueError(f"invalid spelling-change metadata: {key}")
            if (
                row["declaration"] is not None
                and (not isinstance(row["declaration"], str) or not row["declaration"])
            ) or (data["domain"] == "core-bipa" and row["declaration"] is None):
                raise ValueError(f"invalid declaration spelling: {key}")
        for key, reason in excluded.items():
            permitted = (
                ("marker", "unknown-source-spelling")
                if data["domain"] == "core-bipa"
                else ("marker", "unknown-sound")
            )
            if reason not in permitted:
                raise ValueError(f"invalid excluded reason: {key}")

    @property
    def geometry(self) -> FeatureSets:
        return self._geometry

    @property
    def identity(self) -> str:
        return str(self._data["identity"])

    def to_data(self) -> dict[str, Any]:
        return cast(dict[str, Any], json.loads(self.dumps()))

    def dumps(self) -> str:
        """Deterministic portable JSON; no Python objects or local paths."""
        return (
            json.dumps(
                self._data,
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )

    def features(self, token: str) -> frozenset[str]:
        return self.geometry.features(token)

    def similarity(self, left: str, right: str) -> float:
        return self.geometry.similarity(left, right)


def read_snapshot(path: Path | None = None) -> Snapshot:
    """Read the shipped finite core by default, without provider imports."""
    try:
        data = json.loads(
            (path or DATA / "core.json").read_bytes(), object_pairs_hook=_unique_object
        )
        snapshot = Snapshot(data)
        if path is None and data["domain"] != "core-bipa":
            raise ArtifactInvalid("the default artifact must be the finite core")
        return snapshot
    except (OSError, ValueError) as exc:
        if isinstance(exc, ArtifactInvalid):
            raise
        raise ArtifactInvalid(str(exc)) from exc


def extract_snapshot(root: Path, *, tokens: Sequence[str] | None = None) -> Snapshot:
    """Extract exact upstream sets from core declarations or explicit research tokens.

    Core keys include the upstream dictionary and literal source spellings
    whose actual resolution matches their declared Sound. Unresolved literal
    source spellings are reported, never trimmed into scored keys. Canonical
    renderings remain separate. Research extraction never enlarges shipping.
    """
    if tokens is not None and (
        isinstance(tokens, str)
        or not tokens
        or any(not isinstance(k, str) or not k for k in tokens)
        or len(tokens) != len(set(tokens))
    ):
        raise SourceError("supply a nonempty, unique sequence of token strings")
    resolver = _resolver(root)
    from pyclts.models import Marker, Sound
    from pyclts.util import itertable

    declared, raw_to_key = {}, {}
    for kind in ("consonants", "vowels", "tones", "markers"):
        rows = _audit_tsv(
            (root / f"pkg/transcriptionsystems/bipa/{kind}.tsv").read_bytes(),
            {"GRAPHEME"},
            identity="GRAPHEME",
        )
        parsed = list(itertable(resolver.system.tabledict[f"{kind}.tsv"]))
        for row, normalized_row in zip(rows, parsed, strict=True):
            raw = row["GRAPHEME"]
            key = normalized_row["grapheme"]
            if key in declared:
                raise SourceContentError(f"duplicate normalized declaration: {key!r}")
            declared[key] = raw
            raw_to_key[raw] = key
    keys = (
        sorted(set(resolver.sounds) | set(raw_to_key))
        if tokens is None
        else sorted(tokens)
    )
    entries, excluded = {}, {}
    for key in keys:
        sound = resolver.sounds[key] if key in resolver.sounds else resolver[key]
        if isinstance(sound, Marker):
            excluded[key] = "marker"
        elif isinstance(sound, Sound):
            declaration_key = raw_to_key.get(key, key)
            if tokens is None and (
                sound.featureset != resolver.sounds[declaration_key].featureset
                or sound.name != resolver.sounds[declaration_key].name
            ):
                raise SourceContentError(
                    f"literal source spelling resolves to a different sound: {key!r}"
                )
            entries[key] = {
                "canonical": str(sound),
                "kind": sound.type(),
                "features": sorted(sound.featureset),
                "alias": bool(sound.alias),
                "normalized": bool(sound.normalized)
                or key != unicodedata.normalize("NFD", key)
                or (key in declared and declared[key] != key),
                "declaration": declared.get(declaration_key),
            }
        else:
            excluded[key] = (
                "unknown-source-spelling" if tokens is None else "unknown-sound"
            )
    validate_source(root)
    data = {
        "schema": "ipakit-clts-feature-snapshot",
        "version": SNAPSHOT_VERSION,
        "extractor_version": EXTRACTOR_VERSION,
        "source": source_policy(),
        "domain": "core-bipa" if tokens is None else "supplied-tokens",
        "requested": keys,
        "entries": entries,
        "excluded": excluded,
    }
    return Snapshot({**data, "identity": identity_fingerprint(data)})


def build_core(root: Path) -> BuildResult:
    """Build the sole approved shipping domain using shared extraction contracts."""
    snapshot = extract_snapshot(root)
    target = Path("ipakit/data/clts/core.json")
    return BuildResult(
        {target: snapshot.dumps().encode("utf-8")}, (target,), validate_source(root)
    )


def validate_parity(root: Path, snapshot: Snapshot) -> dict[str, Any]:
    """Exhaust every emitted set and all unordered unique-set pairs + diagonal."""
    resolver = _resolver(root)
    unique: dict[frozenset[str], tuple[str, Any]] = {}
    data = snapshot.to_data()
    for token in snapshot.geometry.values:
        sound = resolver[token]
        if (
            not hasattr(sound, "similarity")
            or snapshot.features(token) != sound.featureset
        ):
            raise SourceContentError(f"feature-set parity failed: {token!r}")
        record = data["entries"][token]
        if record["canonical"] != str(sound) or record["kind"] != sound.type():
            raise SourceContentError(f"sound-identity parity failed: {token!r}")
        unique.setdefault(sound.featureset, (token, sound))
    for token, reason in data["excluded"].items():
        kind = resolver[token].type()
        if (reason == "marker" and kind != "marker") or (
            reason != "marker" and kind != "unknownsound"
        ):
            raise SourceContentError(f"exclusion parity failed: {token!r}")
    pairs = 0
    for (left, a), (right, b) in itertools.combinations_with_replacement(
        unique.values(), 2
    ):
        if snapshot.similarity(left, right) != a.similarity(b):
            raise SourceContentError(f"score parity failed: {left!r}, {right!r}")
        pairs += 1
    return {
        "status": "matched",
        "identity": snapshot.identity,
        "keys": len(snapshot.geometry.values),
        "excluded": len(data["excluded"]),
        "unique_sets": len(unique),
        "pairs_including_diagonal": pairs,
    }
