#!/usr/bin/env python3
"""Measure corpus-v2 storage, restoration, query, routing, and memory."""

from __future__ import annotations

import argparse
import json
import platform
import resource
import sys
import tempfile
import time
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ipakit
from ipakit.form import Form

ROOT = Path(__file__).resolve().parent.parent


def _cmudict_transcriptions() -> list[str]:
    from ipakit._corpus_cmudict import read_cmudict_dictionary_line

    mapper = ipakit.CMUMapper()
    result = []
    source = ROOT / "tests" / "fixtures" / "cmudict_excerpt.dict"
    for line in source.read_text(encoding="utf-8").splitlines():
        try:
            item = read_cmudict_dictionary_line(line)
            if item is not None:
                result.append(mapper.cmu_to_ipa(list(item.phones), strict=True))
        except ValueError:
            pass
    return list(dict.fromkeys(result))


def _workload(name: str, count: int) -> Iterator[Form]:
    inventory = ipakit.load_ipa_features()
    if name == "repeated":
        form = inventory.read("ana", strict=True)
        yield from (form for _ in range(count))
        return

    from ipakit._rewrite_graph import japanese_moraic_fixture, japanese_moraic_fixtures
    from ipakit.form import Interval

    source = _cmudict_transcriptions()
    spellings = list(
        dict.fromkeys(f"{left} {right}" for left in source for right in source)
    )
    if len(spellings) < count:
        raise ValueError(f"CMUdict sample yields only {len(spellings)} distinct pairs")
    for text in spellings[:count]:
        yield inventory.read(text, strict=True)
    for fixture_name in japanese_moraic_fixtures():
        yield japanese_moraic_fixture(fixture_name, inventory)
    parsed = inventory.read("pə.ti.t‿a.mi", strict=True)
    yield Form.of(
        parsed.units,
        (
            Interval("syllable", 0, 2, inventory),
            Interval("syllable", 3, 5, inventory),
            Interval("syllable", 6, 9, inventory),
            Interval("syllable", 10, 12, inventory),
        ),
    )


def _peak_rss_mb() -> float:
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    divisor = 1024**2 if sys.platform == "darwin" else 1024
    return round(value / divisor, 3)


def measure(workload: str, count: int) -> dict[str, object]:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "corpus"
        corpus = ipakit.corpus.create(root)
        started = time.perf_counter()
        for index, form in enumerate(_workload(workload, count)):
            corpus.add(f"entry-{index:07d}", {}, {"cited": form})
        put = time.perf_counter() - started

        entry_paths = sorted((root / "entries").glob("*.json"))
        c1_entries = sum(path.read_bytes()[:1] == b"N" for path in entry_paths)
        started = time.perf_counter()
        for entry_id in corpus.ids():
            corpus.read(entry_id)
        get = time.perf_counter() - started
        started = time.perf_counter()
        matches = sum(1 for _ in ipakit.corpus.query(corpus, "[nasal]", role="cited"))
        query = time.perf_counter() - started
        size = sum(path.stat().st_size for path in entry_paths)
        entries = len(entry_paths)
        return {
            "workload": workload,
            "requested_entries": count,
            "entries": entries,
            "bytes": size,
            "put_seconds": round(put, 6),
            "get_seconds": round(get, 6),
            "query_seconds": round(query, 6),
            "matches": matches,
            "c1_entries": c1_entries,
            "c1_share": round(c1_entries / entries, 6),
            "peak_rss_mb": _peak_rss_mb(),
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--counts", nargs="+", type=int, default=[500, 5000])
    parser.add_argument(
        "--workloads",
        nargs="+",
        choices=("repeated", "varied"),
        default=["repeated", "varied"],
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [
        measure(workload, count) for count in args.counts for workload in args.workloads
    ]
    repeated_5000 = next(
        (
            row
            for row in rows
            if row["workload"] == "repeated" and row["requested_entries"] == 5000
        ),
        None,
    )
    targets = {
        "storage_bytes": 12_640_000,
        "get_seconds": 0.66,
        "query_seconds": 1.57,
    }
    target_results = (
        None
        if repeated_5000 is None
        else {
            "storage": cast(int, repeated_5000["bytes"]) < 12_640_000,
            "get": cast(float, repeated_5000["get_seconds"]) < 0.66,
            "query": cast(float, repeated_5000["query_seconds"]) < 1.57,
        }
    )
    document = {
        "type": "ipakit.corpus.scaling-report",
        "v": 2,
        "generated": date.today().isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "targets": targets,
        "target_workload": {
            "workload": "repeated",
            "requested_entries": 5000,
        },
        "target_results": target_results,
        "rows": rows,
    }
    args.output.write_text(
        json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
