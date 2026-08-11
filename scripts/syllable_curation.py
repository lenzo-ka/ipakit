#!/usr/bin/env python3
"""Harvest, classify, curate, and measure English onset declarations.

The manner-derived sonority order is a model used to expose the curation
queue, not a phonetic fact and not the source of the shipped inventory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

# Make the package importable when run from a source checkout.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ipakit
from ipakit.bridges.ipa_dict import IPADictReader
from ipakit.corpus import Corpus
from ipakit.form import Form, Unit
from ipakit.mapper import CMUMapper
from ipakit.syllable import Language, syllabifier


@dataclass(frozen=True)
class Evidence:
    onset: str
    count: int
    exemplars: tuple[str, ...]
    legal: bool
    ranks: tuple[int, ...]


def _segments(form: Form) -> tuple[Unit, ...]:
    return tuple(unit for unit in form.units if unit.segment is not None)


def _onset(form: Form) -> tuple[Unit, ...]:
    out: list[Unit] = []
    for unit in _segments(form):
        if unit.features.get("manner") == "vowel" or "stress" in unit.prosody:
            break
        out.append(unit)
    return tuple(out)


def sonority() -> dict[str, int]:
    """Derive the model from manner constriction and its obstruent class."""
    manner = ipakit.IPAFeatures().features["manner"]
    obstruents = manner.value_classes["obstruent"]
    ranked = sorted(
        (name for name in manner.coordinates if name != "vowel"),
        key=lambda name: (
            name not in obstruents,
            -manner.coordinates[name]["offset"],
        ),
    )
    ranked.append("vowel")
    return {name: rank for rank, name in enumerate(ranked)}


def harvest(corpus: Corpus) -> tuple[Evidence, ...]:
    scale = sonority()
    counts: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    ranks: dict[str, tuple[int, ...]] = {}
    for entry in corpus:
        form = entry.forms.get("cited")
        if form is None:
            continue
        units = _onset(form)
        text = " ".join(unit.core for unit in units)
        counts[text] += 1
        word = str(entry.meta.get("word", entry.id))
        if word not in examples[text] and len(examples[text]) < 5:
            examples[text].append(word)
        ranks[text] = tuple(scale[unit.features["manner"]] for unit in units)
    return tuple(
        Evidence(
            onset,
            count,
            tuple(examples[onset]),
            len(rank) <= 1
            or (
                rank[-1] == scale["approximant"]
                and all(a < b for a, b in zip(rank, rank[1:], strict=False))
            ),
            rank,
        )
        for onset, count in sorted(counts.items())
        if onset
        for rank in (ranks[onset],)
    )


def classify_exception(onset: str) -> tuple[str | None, str]:
    phones = onset.split()
    if onset in {"f s", "l k s", "θ s"}:
        return None, "refuse an initialism spelling as transcription noise"
    if phones[:2] == ["ʃ", "m"]:
        return "borrowing", "retain the productive Yiddish/German borrowing pattern"
    if phones and phones[0] == "s":
        return "native", "retain the English s-cluster sonority exception"
    return "marginal", "retain attested proper-name, clipping, or loan evidence"


def _span_xml(parent: ET.Element, evidence: Evidence) -> None:
    attributes = {
        "span": evidence.onset,
        "harvested-count": str(evidence.count),
        "exemplar": evidence.exemplars[0],
        "decision": "confirm constraint-legal word onset",
        "curation-provenance": "CMUdict word-initial harvest, iteration 1",
    }
    if not evidence.legal:
        stratum, decision = classify_exception(evidence.onset)
        attributes.update(
            stratum=stratum or "marginal",
            decision=decision,
            **{"curation-provenance": "CMUdict curation queue, iteration 2"},
        )
    ET.SubElement(parent, "onset", attributes)


def declaration(evidence: tuple[Evidence, ...], provenance: str) -> ET.Element:
    root = ET.Element(
        "syllabification",
        {
            "language": "english",
            "version": "1",
            "mode": "constraints",
            "provenance": provenance,
        },
    )
    ET.SubElement(root, "nucleus", {"span": "[vowel]"})
    ET.SubElement(root, "nucleus", {"span": "[syllabic=+]"})
    ET.SubElement(
        root,
        "onset",
        {
            "span": "[-vowel]",
            "decision": "admit every singleton as a constraint-derived gap",
            "curation-provenance": "English curation policy, iteration 1",
        },
    )
    for item in evidence:
        if len(item.onset.split()) > 1:
            if not item.legal and classify_exception(item.onset)[0] is None:
                continue
            _span_xml(root, item)
    ET.indent(root, space="  ")
    return root


def _language(root: ET.Element, path: Path) -> Language:
    _write_xml(root, path)
    return ipakit.syllable.read_language(path)


def _write_xml(root: ET.Element, path: Path) -> None:
    path.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True) + b"\n")


def _filtered(language: Language, strata: frozenset[str]) -> Language:
    return Language(
        language.name,
        language.mode,
        language.provenance,
        language.nuclei,
        tuple(
            span
            for span in language.onsets
            if span.stratum is None or span.stratum in strata
        ),
        language.morae,
        language.syllables,
        language.codas,
    )


def _signature(built: Any, form: Form) -> tuple[Any, ...]:
    result = built(form)
    return result.spelled(), result.unsyllabified


def iterations(corpus: Corpus, language: Language) -> list[dict[str, Any]]:
    stages = (
        ("constraint baseline", frozenset()),
        ("admit native exceptions", frozenset({"native"})),
        ("admit borrowings", frozenset({"native", "borrowing"})),
        (
            "admit marginal evidence",
            frozenset({"native", "borrowing", "marginal"}),
        ),
    )
    forms = [entry.forms["cited"] for entry in corpus if "cited" in entry.forms]
    previous: list[tuple[Any, ...]] | None = None
    out: list[dict[str, Any]] = []
    previous_onsets = 0
    for number, (decision, strata) in enumerate(stages):
        selected = _filtered(language, strata)
        current = [_signature(syllabifier(selected), form) for form in forms]
        onset_count = len(selected.onsets)
        out.append(
            {
                "iteration": number,
                "decision": decision,
                "admitted_strata": sorted(strata),
                "inventory_delta": onset_count - previous_onsets,
                "forms_changed": (
                    0
                    if previous is None
                    else sum(a != b for a, b in zip(previous, current, strict=True))
                ),
            }
        )
        previous = current
        previous_onsets = onset_count
    return out


def cross_check(
    corpus: Corpus | Mapping[str, Form | str],
    language: Language,
    ipa_dict: Path | None,
    source_version: str | None,
) -> dict[str, Any]:
    if ipa_dict is None:
        return {"status": "not run", "reason": "no ipa-dict en_US source supplied"}
    reader = IPADictReader(ipa_dict, language="en_US")
    cmu = (
        {str(entry.meta.get("word")): entry.forms["cited"] for entry in corpus}
        if isinstance(corpus, Corpus)
        else corpus
    )
    built = syllabifier(language)
    features = ipakit.IPAFeatures()
    agreement = disagreement = shared = 0
    stress_normalized = 0
    refusals = 0
    buckets: dict[str, dict[str, Any]] = {
        name: {"count": 0, "examples": []}
        for name in (
            "stress_seat",
            "untied_diphthong_nucleation",
            "genuine_boundary_difference",
            "other",
        )
    }
    with ipa_dict.open(encoding="utf-8-sig") as source:
        for line_number, raw in enumerate(source, 1):
            line = raw.rstrip("\r\n")
            if not line or line.startswith("#"):
                continue
            try:
                word, field = line.split("\t", 1)
                written = [part.strip() for part in field.split(",")]
                if any(
                    len(value) < 2
                    or not value.startswith("/")
                    or not value.endswith("/")
                    for value in written
                ):
                    raise ValueError("invalid ipa-dict pronunciation field")
                raw_forms = [value[1:-1] for value in written]
                normalized = [
                    features.normalize_stress_to_nucleus(value) for value in raw_forms
                ]
                touched = sum(
                    before != after
                    for before, after in zip(raw_forms, normalized, strict=True)
                )
                normalized_line = (
                    word + "\t" + ", ".join(f"/{value}/" for value in normalized)
                )
                entry = reader.read_line(normalized_line, line_number=line_number)
            except (UnicodeError, ValueError):
                refusals += 1
                continue
            if entry.word not in cmu:
                continue
            shared += 1
            stress_normalized += touched
            left = built(cmu[entry.word]).spelled()
            normalized_forms = [pron.form for pron in entry.pronunciations]
            alternatives = [built(form).spelled() for form in normalized_forms]
            if left in alternatives:
                agreement += 1
            else:
                disagreement += 1
                tied = [
                    built(_tie_registered_diphthongs(form, features)).spelled()
                    for form in normalized_forms
                ]
                if left in tied:
                    bucket = "untied_diphthong_nucleation"
                elif any(
                    _without_breaks(left) == _without_breaks(value)
                    for value in alternatives
                ):
                    bucket = "genuine_boundary_difference"
                else:
                    bucket = "other"
                row = buckets[bucket]
                row["count"] += 1
                if len(row["examples"]) < 5:
                    row["examples"].append(
                        {
                            "word": entry.word,
                            "cmudict": ".".join(left),
                            "ipa_dict": " | ".join(
                                ".".join(value) for value in alternatives
                            ),
                        }
                    )
    return {
        "source": {
            **_source_identity(ipa_dict),
            **({"version": source_version} if source_version else {}),
        },
        "shared_words": shared,
        "agreements": agreement,
        "disagreements": disagreement,
        "normalizations": {
            "stress_to_nucleus": {
                "applied_to_forms": stress_normalized,
                "operation": "IPAFeatures.normalize_stress_to_nucleus",
            },
            "registered_diphthong_tying": {
                "applied_to_forms": 0,
                "operation": "not applied: normalize() treats whitespace as asserted unit grouping and is not a word-level diphthong detector",
            },
        },
        "disagreement_buckets": buckets,
        "notes": [
            "ipa-dict syllable-initial stress was re-seated on the following nucleus for this comparison only; stored bridge forms are unchanged.",
            "Whether read() should globally seat standard leading-stress IPA on the following nucleus is an engine question recorded here and left outside this lane.",
            "Registered-diphthong tying remains the normalize tie-report follow-up; diagnostic tying is used only to identify the untied-diphthong bucket.",
        ],
        "refusals": refusals,
    }


def _without_breaks(syllables: tuple[str, ...]) -> str:
    return "".join(syllables).replace(".", "")


def _tie_registered_diphthongs(form: Form, features: ipakit.IPAFeatures) -> Form:
    """Tie only adjacent nuclei whose under-tied spelling is registered.

    This is a diagnostic counterfactual for bucketing, not a normalization
    applied to the compared ipa-dict form.
    """
    output: list[str] = []
    units = form.units
    index = 0
    while index < len(units):
        unit = units[index]
        if index + 1 < len(units):
            following = units[index + 1]
            candidate = unit.core + features.seq_tie + following.core
            if (
                unit.segment is not None
                and following.segment is not None
                and features.is_nucleus(unit.features)
                and features.is_nucleus(following.features)
                and candidate in features.phones
            ):
                output.append(unit.text + features.seq_tie + following.text)
                index += 2
                continue
        output.append(unit.text)
        index += 1
    return features.read("".join(output), strict=True)


def _source_identity(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"path": path.name, "sha256": digest}


def _cmudict_forms(path: Path) -> dict[str, str]:
    """Read the final ID-ordered pronunciation per CMUdict headword."""
    mapper = CMUMapper()
    selected: dict[str, tuple[str, str]] = {}
    with path.open(encoding="utf-8") as source:
        for raw in source:
            content = raw.split("#", 1)[0].strip()
            if not content or content.startswith(";;;"):
                continue
            spelling, *phones = content.split()
            match = re.fullmatch(
                r"(?P<word>\S+?)(?:\((?P<variant>[1-9][0-9]*)\))?", spelling
            )
            if match is None or not phones:
                continue
            word = match.group("word").lower()
            variant = int(match.group("variant") or "1")
            entry_id = word if variant == 1 else f"{word}.{variant}"
            try:
                transcription = mapper.cmu_to_ipa(phones, strict=True)
            except ValueError:
                continue
            if word not in selected or entry_id > selected[word][0]:
                selected[word] = (entry_id, transcription)
    return {word: transcription for word, (_, transcription) in selected.items()}


def run(args: argparse.Namespace) -> dict[str, Any]:
    reused = (
        json.loads(args.reuse_measurements.read_text(encoding="utf-8"))
        if args.reuse_measurements
        else None
    )
    with tempfile.TemporaryDirectory(prefix="ipakit-syllables-") as temporary:
        if reused and args.cmudict:
            corpus = None
            comparison_source: Corpus | Mapping[str, Form | str] = _cmudict_forms(
                args.cmudict
            )
            ingest = None
            evidence = tuple(
                Evidence(
                    item["onset"],
                    item["count"],
                    tuple(item["exemplars"]),
                    item["constraint_legal"],
                    tuple(item["sonority_ranks"]),
                )
                for item in reused["onsets"]
            )
        elif args.corpus:
            corpus = ipakit.corpus.open(args.corpus)
            comparison_source = corpus
            ingest = None
            evidence = harvest(corpus)
        else:
            corpus = ipakit.corpus.create(Path(temporary) / "corpus")
            comparison_source = corpus
            ingest = ipakit.corpus.ingest_cmudict(corpus, args.cmudict)
            evidence = harvest(corpus)
        source = (
            {
                "corpus": args.source_name,
                **_source_identity(args.cmudict),
                **({"version": args.source_version} if args.source_version else {}),
            }
            if reused and args.cmudict and args.source_name
            else (
                reused["source"]
                if reused
                else (
                    {
                        **_source_identity(args.cmudict),
                        **(
                            {"version": args.source_version}
                            if args.source_version
                            else {}
                        ),
                    }
                    if args.cmudict
                    else {
                        "corpus": args.corpus.name,
                        **({"path": args.source_name} if args.source_name else {}),
                        **(
                            {"sha256": args.source_sha256} if args.source_sha256 else {}
                        ),
                        **(
                            {"version": args.source_version}
                            if args.source_version
                            else {}
                        ),
                    }
                )
            )
        )
        provenance = (
            "Generated by scripts/syllable_curation.py from CMUdict "
            f"{json.dumps(source, sort_keys=True)}; generated {args.date}; "
            "do not edit by hand."
        )
        root = declaration(evidence, provenance)
        language = _language(root, Path(temporary) / "english.xml")
        queue = [item for item in evidence if not item.legal]
        strata = Counter(
            stratum
            for item in queue
            for stratum, _ in (classify_exception(item.onset),)
            if stratum is not None
        )
        report = {
            "artifact": "ipakit English syllable curation report",
            "generated": args.date,
            "generator": "scripts/syllable_curation.py",
            "source": source,
            "corpus": {
                "forms": reused["corpus"]["forms"] if corpus is None else len(corpus),
                "ingest_refusals": (
                    reused["corpus"]["ingest_refusals"]
                    if corpus is None
                    else len(ingest.refusals) if ingest else None
                ),
            },
            "grid": {
                "constraint_legal_attested": sum(item.legal for item in evidence),
                "constraint_legal_unattested": 1,
                "constraint_illegal_attested": len(queue),
            },
            "curation_queue": {
                "size": len(queue),
                "resolution_by_stratum": dict(sorted(strata.items())),
                "entries": [
                    {
                        "onset": item.onset,
                        "count": item.count,
                        "exemplars": item.exemplars,
                        "stratum": classify_exception(item.onset)[0],
                        "decision": classify_exception(item.onset)[1],
                    }
                    for item in queue
                ],
                "refusals": [
                    *[
                        {
                            "onset": item.onset,
                            "count": item.count,
                            "exemplars": item.exemplars,
                            "reason": classify_exception(item.onset)[1],
                        }
                        for item in queue
                        if classify_exception(item.onset)[0] is None
                    ],
                    *(
                        [
                            {
                                "line": refusal.line_number,
                                "word": refusal.word,
                                "reason": refusal.reason,
                            }
                            for refusal in ingest.refusals
                        ]
                        if ingest
                        else []
                    ),
                ],
            },
            "iterations": (
                reused["iterations"] if reused else iterations(corpus, language)
            ),
            "cross_check": (
                cross_check(
                    comparison_source,
                    language,
                    args.ipa_dict,
                    args.ipa_dict_version,
                )
                if args.ipa_dict or not reused
                else reused["cross_check"]
            ),
            "onsets": [
                {
                    "onset": item.onset,
                    "count": item.count,
                    "exemplars": item.exemplars,
                    "constraint_legal": item.legal,
                    "sonority_ranks": item.ranks,
                }
                for item in evidence
            ],
        }
        args.declaration.parent.mkdir(parents=True, exist_ok=True)
        _write_xml(root, args.declaration)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return report


def parser() -> argparse.ArgumentParser:
    built = argparse.ArgumentParser(description=__doc__)
    source = built.add_mutually_exclusive_group(required=True)
    source.add_argument("--corpus", type=Path, help="CMUdict-ingested corpus")
    source.add_argument("--cmudict", type=Path, help="raw CMUdict source to ingest")
    built.add_argument("--ipa-dict", type=Path, help="ipa-dict en_US.txt cross-check")
    built.add_argument("--source-version", help="CMUdict commit or release identity")
    built.add_argument("--source-name", help="external source basename for a corpus")
    built.add_argument("--source-sha256", help="external source digest for a corpus")
    built.add_argument("--ipa-dict-version", help="ipa-dict commit or release identity")
    built.add_argument("--date", default=date.today().isoformat())
    built.add_argument("--declaration", type=Path, required=True)
    built.add_argument("--report", type=Path, required=True)
    built.add_argument(
        "--reuse-measurements",
        type=Path,
        help="reuse iterations and, unless --ipa-dict is supplied, cross-checks",
    )
    return built


if __name__ == "__main__":
    run(parser().parse_args())
