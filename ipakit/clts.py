"""CLTS declaration compatibility tools, independent of the command line.

This census is not a full CLTS importer or semantic correspondence table.
It reads explicit source files and does not import pyclts.
"""

from __future__ import annotations

import collections
import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

from . import load_ipa_features

SOUNDS_TSV = ("data", "sounds.tsv")
FEATURES_TSV = ("data", "features.tsv")
MASTER_FEATURES = ("pkg", "transcriptionsystems", "features.json")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """JSON must not silently overwrite duplicate declaration keys."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _audit_tsv(data: bytes, columns: set[str]) -> list[dict[str, str]]:
    reader = csv.DictReader(
        io.StringIO(data.decode("utf-8"), newline=""), delimiter="\t", strict=True
    )
    try:
        header = reader.fieldnames or []
        rows = list(reader)
    except csv.Error as exc:
        raise ValueError(f"invalid TSV quoting: {exc}") from exc
    if len(header) != len(set(header)) or not columns.issubset(header):
        raise ValueError(f"invalid TSV header; required columns: {sorted(columns)}")
    ids: set[str] = set()
    for row in rows:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("ragged TSV row")
        if not row["ID"].strip() or row["ID"] in ids:
            raise ValueError(f"empty or duplicate TSV ID: {row['ID']!r}")
        ids.add(row["ID"])
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
