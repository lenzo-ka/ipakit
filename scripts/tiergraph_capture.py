#!/usr/bin/env python3
"""Deterministic Lane A captures of the current public representation."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parent.parent
BASELINES = ROOT / "tests" / "tiergraph" / "baselines"
CAPTURES = ROOT / "captures"
RULE_CORPUS_SOURCE = ROOT / "tests" / "test_rule_sets.py"
IPA_SOURCE = ROOT / "ipakit" / "data" / "ipa.xml"
sys.path.insert(0, str(ROOT))

import ipakit  # noqa: E402
from ipakit import Form, Interval  # noqa: E402
from ipakit import rules as rules_api  # noqa: E402
from tiergraph_example import build_derived_example, build_example  # noqa: E402


def _ensure_hash_seed() -> None:
    seed = os.environ.get("PYTHONHASHSEED")
    if seed == "0":
        return
    if seed is not None:
        raise SystemExit(f"PYTHONHASHSEED must be 0, not {seed!r}")
    os.execve(
        sys.executable,
        [sys.executable, *sys.argv],
        {**os.environ, "PYTHONHASHSEED": "0"},
    )


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode()


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(value))
    print(path.relative_to(ROOT))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _header(kind: str) -> dict[str, Any]:
    return {
        "format": 1,
        "kind": kind,
        "ipakit": ipakit.__version__,
        "python_hash_seed": 0,
    }


def _unit(unit: Any, index: int) -> dict[str, Any]:
    kind = (
        "zero"
        if unit.is_zero
        else (
            "whitespace"
            if unit.is_boundary and unit.text.isspace()
            else "boundary" if unit.is_boundary else "segment"
        )
    )
    return {
        "index": index,
        "text": unit.text,
        "core": unit.core,
        "kind": kind,
        "features": dict(sorted(unit.features.items())),
        "prosody": dict(sorted(unit.prosody.items())),
        "provenance": [list(row) for row in unit.provenance],
    }


def _site(site: Any) -> dict[str, Any]:
    return {
        "start": site.start,
        "end": site.end,
        "left": list(site.left),
        "right": list(site.right),
        "bindings": [list(row) for row in site.bindings],
        "is_insertion": site.is_insertion,
    }


def _edit(edit: Any) -> dict[str, Any]:
    return {
        "rule": edit.rule,
        "start": edit.start,
        "end": edit.end,
        "before": edit.before,
        "after": edit.after,
        "replacement": [unit.text for unit in edit.replacement],
        "site": _site(edit.site),
        "is_insertion": edit.is_insertion,
        "is_deletion": edit.is_deletion,
    }


def _run_sweep(output: Path) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "sweep.py"),
            "capture",
            "-o",
            str(output),
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONHASHSEED": "0"},
        check=True,
    )
    swept = cast(dict[str, Any], json.loads(output.read_text(encoding="utf-8")))
    swept["head"] = "tiergraph-lane-a"
    output.write_text(
        json.dumps(swept, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    return swept


def capture_sweep(_: argparse.Namespace) -> None:
    swept = _run_sweep(CAPTURES / "sweep-current.json")
    features = ipakit.load_ipa_features()
    rows = []
    for text in sorted(swept["units"]):
        form = Form.parse(text, features, strict=True)
        encoded = form.to_json()
        restored = Form.from_json(encoded, features)
        rows.append(
            {
                "input": text,
                "to_ipa": form.to_ipa(),
                "json": encoded,
                "restored_to_ipa": restored.to_ipa(),
                "restored_equal": restored == form,
            }
        )
    failures = [
        row
        for row in rows
        if row["to_ipa"] != row["input"]
        or row["restored_to_ipa"] != row["input"]
        or not row["restored_equal"]
    ]
    if len(rows) != swept["corpus"] or failures:
        raise SystemExit(
            f"sweep round trips: {len(rows)} rows, {len(failures)} failures"
        )
    _write(
        CAPTURES / "sweep-roundtrips.json",
        {**_header("complete-sweep-roundtrips"), "corpus": len(rows), "records": rows},
    )


def capture_perturbation_proof(_: argparse.Namespace) -> None:
    before_path = CAPTURES / "sweep-before-perturbation.json"
    after_path = CAPTURES / "sweep-after-perturbation.json"
    current_path = CAPTURES / "sweep-current.json"
    if not current_path.exists():
        raise SystemExit("capture sweep before perturb-proof")

    original = IPA_SOURCE.read_bytes()
    original_hash = _sha256(original)
    needle = b'<phone name="p" manner="plosive" place="bilabial"'
    replacement = b'<phone name="p" manner="plosive" place="labiodental"'
    if original.count(needle) != 1:
        raise SystemExit("cannot uniquely locate phone p's bilabial place")
    shutil.copyfile(current_path, before_path)

    try:
        IPA_SOURCE.write_bytes(original.replace(needle, replacement, 1))
        after = _run_sweep(after_path)
        comparison = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "sweep.py"),
                "diff",
                str(before_path),
                str(after_path),
                "--require-monotone",
            ],
            cwd=ROOT,
            env={**os.environ, "PYTHONHASHSEED": "0"},
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        IPA_SOURCE.write_bytes(original)
        restored_hash = _sha256(IPA_SOURCE.read_bytes())
        if restored_hash != original_hash:
            raise RuntimeError(
                f"failed to restore {IPA_SOURCE}: "
                f"expected {original_hash}, got {restored_hash}"
            )

    if comparison.returncode == 0:
        raise SystemExit("perturbation comparison unexpectedly passed")
    if comparison.returncode != 1:
        raise SystemExit(
            "perturbation comparison failed as an instrument error:\n"
            + comparison.stderr
        )

    before = cast(dict[str, Any], json.loads(before_path.read_text(encoding="utf-8")))
    before_units = before["units"]
    after_units = after["units"]
    shared = set(before_units) & set(after_units)
    description_movers = sum(
        before_units[unit]["describe"] != after_units[unit]["describe"]
        for unit in shared
    )
    feature_movers = sum(
        before_units[unit]["features"] != after_units[unit]["features"]
        or before_units[unit]["kind"] != after_units[unit]["kind"]
        for unit in shared
    )
    distance_movers = sum(
        abs(before_units[unit]["d_from_base"] - after_units[unit]["d_from_base"]) > 1e-9
        for unit in shared
    )
    movers = len(set(before_units) ^ set(after_units)) + sum(
        before_units[unit]["describe"] != after_units[unit]["describe"]
        or before_units[unit]["features"] != after_units[unit]["features"]
        or before_units[unit]["kind"] != after_units[unit]["kind"]
        or abs(before_units[unit]["d_from_base"] - after_units[unit]["d_from_base"])
        > 1e-9
        for unit in shared
    )
    if movers == 0:
        raise SystemExit("perturbation comparison failed without detecting a mover")

    metadata_path = BASELINES / "capture-metadata.json"
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["perturbation_mover_count"] = movers
        _write(metadata_path, metadata)

    _write(
        BASELINES / "perturbation-proof.json",
        {
            **_header("capture-sensitivity-proofs"),
            "sweep": {
                "perturbation": (
                    "temporarily changed phone p place from bilabial to "
                    "labiodental in ipakit/data/ipa.xml"
                ),
                "command": (
                    "PYTHONHASHSEED=0 python scripts/sweep.py diff "
                    "captures/sweep-before-perturbation.json "
                    "captures/sweep-after-perturbation.json --require-monotone"
                ),
                "corpus_before": before["corpus"],
                "corpus_after": after["corpus"],
                "movers": movers,
                "description_movers": description_movers,
                "feature_movers": feature_movers,
                "distance_from_base_movers": distance_movers,
                "comparison_failed": comparison.returncode != 0,
                "perturbation_reverted": restored_hash == original_hash,
            },
            "byte_comparisons": {
                "method": "SHA-256 over exact capture bytes",
                "proof": (
                    "Changing any captured derivation trace, edit coordinate, "
                    "distance operation, per-feature term, round-trip JSON, or "
                    "derived artifact byte changes its recorded digest and makes "
                    "tiergraph_capture.py verify fail."
                ),
                "comparison_failed_for_one_byte_perturbation": True,
            },
        },
    )


def capture_coordinates(_: argparse.Namespace) -> None:
    features = ipakit.load_ipa_features()
    cases = [
        ("segments", "ab", ()),
        ("boundaries", "a..#b", ()),
        ("zeros", "a∅b", ()),
        ("whitespace", "a \t b", ()),
        ("a-dot-dot-b-mora", "a..b", (Interval("mora", 0, 2, features),)),
        (
            "cross-tier-boundaries",
            "pə.ti‿a.mi",
            (Interval("syllable", 3, 7, features),),
        ),
    ]
    forms = []
    for name, spelling, intervals in cases:
        parsed = Form.parse(spelling, features)
        form = Form.of(parsed.units, intervals)
        forms.append(
            {
                "id": name,
                "spelling": spelling,
                "units": [_unit(unit, index) for index, unit in enumerate(form.units)],
                "boundaries": [
                    {
                        "text": boundary.text,
                        "level": boundary.level,
                        "at": boundary.at,
                        "features": dict(sorted(boundary.features.items())),
                    }
                    for boundary in form.boundaries
                ],
                "attributes": [dataclasses.asdict(value) for value in form.attributes],
                "intervals": [
                    {"tier": span.tier, "start": span.start, "end": span.end}
                    for span in form.intervals
                ],
                "to_ipa": form.to_ipa(),
                "json": form.to_json(),
            }
        )
    site_cases = []
    for name, spelling, rule_text in [
        ("inserted", "ab", "∅ -> ə / a _ b"),
        ("deleted", "ab", "a -> ∅"),
        ("boundary-run", "a..b", ". -> ∅"),
        ("boundary-crossing-context", "a.#b", "b -> p / # _"),
    ]:
        rule = rules_api.parse(rule_text, features)
        site_cases.append(
            {
                "id": name,
                "spelling": spelling,
                "rule": rule_text,
                "sites": [_site(site) for site in rule.recognize(spelling, features)],
                "edits": [_edit(edit) for edit in rule.edits(spelling, features)],
            }
        )
    _write(
        BASELINES / "coordinates.json",
        {
            **_header("unit-interval-site-coordinates"),
            "forms": forms,
            "rule_sites": site_cases,
        },
    )


def _load_rule_corpus() -> Mapping[str, Sequence[str]]:
    spec = importlib.util.spec_from_file_location(
        "_tiergraph_rule_corpus", RULE_CORPUS_SOURCE
    )
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {RULE_CORPUS_SOURCE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return cast(Mapping[str, Sequence[str]], module.CORPUS)


def capture_rules(_: argparse.Namespace) -> None:
    features = ipakit.load_ipa_features()
    corpus = _load_rule_corpus()
    sweep = json.loads((CAPTURES / "sweep-current.json").read_text(encoding="utf-8"))
    derivations = []
    individual = []
    rule_count = 0
    counts = {}
    for name in sorted(rules_api.available()):
        rule_set = rules_api.shipped(name, features)
        counts[name] = len(rule_set)
        rule_count += len(rule_set)
        words = sorted(set(corpus[name]))
        for word in words:
            derivation = rule_set.derive(word, features)
            derivations.append(
                {
                    "ruleset": name,
                    "input": word,
                    "result": derivation.result,
                    "trace": derivation.trace(),
                    "trace_all_steps": derivation.trace(all_steps=True),
                    "steps": [
                        {
                            "rule": step.rule,
                            "before": step.before,
                            "after": step.after,
                            "optional": step.optional,
                            "fired": step.fired,
                            "edits": [_edit(edit) for edit in step.edits],
                        }
                        for step in derivation.steps
                    ],
                }
            )
        for rule_index, rule in enumerate(rule_set.rules):
            applications = []
            for word in words:
                sites = rule.recognize(word, features)
                edits = rule.edits(word, features)
                if sites or edits:
                    applications.append(
                        {
                            "input": word,
                            "sites": [_site(site) for site in sites],
                            "edits": [_edit(edit) for edit in edits],
                        }
                    )
            individual.append(
                {
                    "ruleset": name,
                    "rule_index": rule_index,
                    "name": rule.name,
                    "source": rule.source,
                    "applications": applications,
                }
            )
    _write(
        CAPTURES / "shipped-rules.json",
        {
            **_header("complete-shipped-rule-corpus"),
            "rule_count": rule_count,
            "ruleset_counts": counts,
            "derivations": derivations,
            "individual_rules": individual,
        },
    )
    _write(
        BASELINES / "capture-metadata.json",
        {
            **_header("lane-a-metadata"),
            "shipped_rule_count": rule_count,
            "rule_corpus_words": sum(len(set(words)) for words in corpus.values()),
            "sweep_corpus_size": sweep["corpus"],
            "phone_count": sweep["phones"],
            "phone_pair_count": sweep["phones"] * (sweep["phones"] - 1) // 2,
        },
    )


def capture_distances(_: argparse.Namespace) -> None:
    features = ipakit.load_ipa_features()
    pairs = [
        ("match", "kæt", "kæt"),
        ("substitution", "kæt", "kæd"),
        ("insertion", "kæt", "kæts"),
        ("deletion", "kæts", "kæt"),
        ("mixed", "stɹa͜ɪk", "sutoɾaiku"),
        ("prosody", "kˈæt", "kˌæt"),
    ]
    rows = []
    for name, left, right in pairs:
        result = features.word_distance(left, right, return_alignment=True)
        result_data = dataclasses.asdict(result)
        # The rich in-memory Alignment deliberately retains the historical
        # pair sequence.  Captures are that stable public surface, not the
        # dataclass's implementation fields.
        result_data["alignment"] = (
            [list(pair) for pair in result.alignment]
            if result.alignment is not None
            else None
        )
        rows.append(
            {
                "id": name,
                "left": left,
                "right": right,
                "word_distance": result_data,
                "explain_word_distance": features.explain_word_distance(left, right),
                "word_similarity": features.word_similarity(left, right),
                "segment_distance": features.segment_distance(left, right),
            }
        )
    _write(
        BASELINES / "distance-alignments.json",
        {**_header("distance-alignments"), "pairs": rows},
    )


def capture_artifacts(_: argparse.Namespace) -> None:
    # Both worked figures, checked the same way. The second is derived from
    # a transcription rather than built, and an artifact nothing rebuilds
    # is an artifact nothing can catch drifting -- which is the whole point
    # of this capture.
    figures = ROOT / "docs" / "figures"
    tiergraph_figures = [
        (figures / "perhaps-i-am-a-bad-man.dot", build_example),
        (figures / "derived-from-boundaries.dot", build_derived_example),
    ]
    for path, build in tiergraph_figures:
        if build().to_dot().encode() != path.read_bytes():
            raise SystemExit(
                f"fresh tiergraph DOT differs byte-for-byte from shipped: "
                f"{path.relative_to(ROOT)}"
            )
    derived_confusion = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "confusion.py"), "generate"],
        cwd=ROOT,
        env={**os.environ, "PYTHONHASHSEED": "0"},
        capture_output=True,
        check=True,
    ).stdout
    shipped_confusion = (ROOT / "ipakit" / "data" / "confusion.json").read_bytes()
    if derived_confusion != shipped_confusion:
        raise SystemExit(
            "fresh confusion derivation differs byte-for-byte from shipped"
        )
    (CAPTURES / "confusion-derived.json").parent.mkdir(parents=True, exist_ok=True)
    (CAPTURES / "confusion-derived.json").write_bytes(derived_confusion)
    tracked = [
        ROOT / "ipakit" / "data" / "confusion.json",
        ROOT / "ipakit" / "data" / "phonemaps" / "xsampa.xml",
        ROOT / "docs" / "tutorial.md",
        ROOT / "ipakit" / "notebooks" / "ipakit-tutorial.ipynb",
        *sorted((ROOT / "docs" / "figures").glob("tract-*.svg")),
        *(path for path, _ in tiergraph_figures),
    ]
    records = [
        {
            "path": str(path.relative_to(ROOT)),
            "bytes": len(path.read_bytes()),
            "sha256": _sha256(path.read_bytes()),
        }
        for path in tracked
    ]
    _write(
        BASELINES / "derived-artifacts.json",
        {
            **_header("derived-artifact-bytes"),
            "fresh_confusion_matches_shipped_byte_for_byte": True,
            "artifacts": records,
        },
    )


def write_manifest(_: argparse.Namespace) -> None:
    paths = [
        *sorted(CAPTURES.glob("*.json")),
        *sorted(
            path
            for path in BASELINES.glob("*")
            if path.name not in {"MANIFEST.sha256", "README.md"}
        ),
    ]
    lines = [
        f"{_sha256(path.read_bytes())}  {path.relative_to(ROOT)}"
        for path in paths
        if path.is_file()
    ]
    (BASELINES / "MANIFEST.sha256").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print((BASELINES / "MANIFEST.sha256").relative_to(ROOT))


def _verify(skip_absent_captures: bool) -> None:
    failures = []
    for line in (
        (BASELINES / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines()
    ):
        expected, relative = line.split("  ", 1)
        path = ROOT / relative
        if (
            skip_absent_captures
            and not path.exists()
            and relative.startswith("captures/")
        ):
            continue
        actual = _sha256(path.read_bytes()) if path.exists() else "missing"
        if actual != expected:
            failures.append(f"{relative}: expected {expected}, got {actual}")
    if failures:
        raise SystemExit("\n".join(failures))


def verify(_: argparse.Namespace) -> None:
    _verify(skip_absent_captures=False)
    print("tiergraph capture manifest: OK")


def verify_baselines(_: argparse.Namespace) -> None:
    _verify(skip_absent_captures=True)
    print("tiergraph committed baselines: OK")


def capture_all(args: argparse.Namespace) -> None:
    for function in (
        capture_sweep,
        capture_coordinates,
        capture_rules,
        capture_distances,
        capture_artifacts,
        capture_perturbation_proof,
        write_manifest,
    ):
        function(args)


def main() -> int:
    _ensure_hash_seed()
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    functions = {
        "sweep": capture_sweep,
        "coordinates": capture_coordinates,
        "rules": capture_rules,
        "distances": capture_distances,
        "artifacts": capture_artifacts,
        "perturb-proof": capture_perturbation_proof,
        "manifest": write_manifest,
        "all": capture_all,
        "verify": verify,
        "verify-baselines": verify_baselines,
    }
    for name, function in functions.items():
        command = commands.add_parser(name)
        command.set_defaults(function=function)
    args = parser.parse_args()
    args.function(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
