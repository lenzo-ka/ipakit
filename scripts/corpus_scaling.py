#!/usr/bin/env python3
"""Measure directory-corpus put/get/query scaling and emit a run report."""

from __future__ import annotations

import argparse
import json
import platform
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ipakit


def measure(count: int) -> dict[str, int | float]:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "corpus"
        corpus = ipakit.corpus.create(root)
        form = ipakit.read("ana")
        started = time.perf_counter()
        for index in range(count):
            corpus.add(f"entry-{index:07d}", {}, {"cited": form})
        put = time.perf_counter() - started
        started = time.perf_counter()
        for entry_id in corpus.ids():
            corpus.read(entry_id)
        get = time.perf_counter() - started
        started = time.perf_counter()
        matches = sum(1 for _ in ipakit.corpus.query(corpus, "[nasal]", role="cited"))
        query = time.perf_counter() - started
        size = sum(path.stat().st_size for path in root.rglob("*") if path.is_file())
        return {
            "entries": count,
            "put_seconds": round(put, 6),
            "get_seconds": round(get, 6),
            "query_seconds": round(query, 6),
            "bytes": size,
            "matches": matches,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--counts", nargs="+", type=int, default=[100, 500, 1000])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [measure(count) for count in args.counts]
    document = {
        "type": "ipakit.corpus.scaling-report",
        "v": 1,
        "generated": date.today().isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "rows": rows,
    }
    args.output.write_text(
        json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
