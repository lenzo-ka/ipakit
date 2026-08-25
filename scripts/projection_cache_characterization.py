#!/usr/bin/env python3
"""Characterize the bounded projection memo; not wired into build targets."""

from __future__ import annotations

import argparse
import itertools
import json
import platform
import sys
import time
import warnings
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ipakit
import ipakit._containment_projection as cp

CONSONANTS = ("p", "t", "k", "b", "d", "g", "m", "n", "s", "f", "l")
VOWELS = ("a", "i", "u", "e", "o", "æ", "ɒ", "ɪ")


def containment_input(ipa: ipakit.IPAFeatures, text: str) -> Any:
    """Read one form and return the containment input captured by ipakit."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        form = ipa.read(text)
    return form.__dict__["_tiergraph_index"].containment_input


def workloads() -> tuple[list[Any], list[Any]]:
    """Build deterministic repeated and cache-exceeding distinct workloads."""
    ipa = ipakit.IPAFeatures()
    cv = [consonant + vowel for consonant in CONSONANTS for vowel in VOWELS]
    cvc = [
        onset + vowel + coda
        for onset in CONSONANTS
        for vowel in VOWELS
        for coda in CONSONANTS
    ]
    building_blocks = cv + cvc
    candidates = itertools.chain(
        building_blocks,
        (first + second for first in building_blocks for second in building_blocks),
    )

    target = max(1201, cp._PROJECTION_CACHE_MAXSIZE + 1)
    distinct: list[Any] = []
    signatures: set[tuple[object, ...]] = set()
    for text in candidates:
        source = containment_input(ipa, text)
        signature = cp._projection_signature(source, frozenset())
        if signature in signatures:
            continue
        signatures.add(signature)
        distinct.append(source)
        if len(distinct) == target:
            break
    if len(distinct) != target:
        raise RuntimeError(f"could only construct {len(distinct)} distinct keys")
    return distinct[:12] * 50, distinct


def characterize(sources: list[Any]) -> dict[str, int | float]:
    """Time signatures and cached projection construction for one profile."""
    started = time.perf_counter()
    signatures = [cp._projection_signature(source, frozenset()) for source in sources]
    signature_seconds = time.perf_counter() - started

    cp._projection_cache_clear()
    started = time.perf_counter()
    for source in sources:
        cp.ContainmentProjection.from_input(source)
    total_seconds = time.perf_counter() - started
    hits, misses, evictions, _size, _maxsize = cp._projection_cache_info()
    return {
        "calls": len(sources),
        "distinct_keys": len(set(signatures)),
        "hits": hits,
        "misses": misses,
        "hit_rate": round(hits / len(sources), 6),
        "evictions": evictions,
        "total_seconds": round(total_seconds, 6),
        "key_construction_seconds": round(signature_seconds, 6),
        "key_construction_fraction": round(
            signature_seconds / total_seconds if total_seconds else 0.0, 6
        ),
    }


def repeated_speedup(sources: list[Any]) -> float:
    """Compare a persistent warm memo with clearing before every call."""
    cp._projection_cache_clear()
    started = time.perf_counter()
    for source in sources:
        cp.ContainmentProjection.from_input(source)
    warm = time.perf_counter() - started

    started = time.perf_counter()
    for source in sources:
        cp._projection_cache_clear()
        cp.ContainmentProjection.from_input(source)
    cold = time.perf_counter() - started
    return round(cold / warm, 6)


def print_profile(name: str, profile: dict[str, int | float]) -> None:
    print(f"{name}:")
    print(
        f"  calls={profile['calls']} distinct_keys={profile['distinct_keys']} "
        f"hits={profile['hits']} misses={profile['misses']} "
        f"hit_rate={profile['hit_rate']:.6f} evictions={profile['evictions']}"
    )
    print(
        f"  total_seconds={profile['total_seconds']:.6f} "
        f"key_construction_seconds={profile['key_construction_seconds']:.6f} "
        f"key_construction_fraction={profile['key_construction_fraction']:.6f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    repeated_sources, no_repeat_sources = workloads()
    repeated = characterize(repeated_sources)
    no_repeat = characterize(no_repeat_sources)
    speedup = repeated_speedup(repeated_sources)
    document = {
        "type": "ipakit.projection-cache.characterization",
        "v": 1,
        "generated": date.today().isoformat(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "repeated": repeated,
        "no_repeat": no_repeat,
        "repeated_speedup": speedup,
    }

    print("ipakit projection-cache characterization")
    print_profile("REPEATED", repeated)
    print_profile("NON-REPEATING", no_repeat)
    print(f"repeated warm-cache speedup={speedup:.6f}x")
    if args.output is not None:
        args.output.write_text(
            json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
