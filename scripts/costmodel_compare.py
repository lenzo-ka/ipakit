#!/usr/bin/env python3
"""Run one corpus through two cost models and print the rows.

The surface for this landed before its consumer did. ``compare`` builds a
``ComparisonRow`` carrying the policy, the pack, the geometry, the budget
ratio, the edit cost, the normalized cost and what was dropped -- and it
was called from tests and nowhere else, so there was no way to obtain a
table anyone could look at. This is that way.

Two arms, one interface. ``house_pack`` reads ipakit's own geometry;
``pack_from_declaration`` reads a declared feature table -- panphon's,
restated as data by ``scripts/panphon_geometry.py`` -- through a reader
that takes no branch on whose declaration it is. Both return a
``CostPack``, so the same corpus and the same policy run through either,
which is what makes the comparison a measurement rather than two
programs.

The policies are the experiment. ``--policy faithful`` reproduces each
model as it stands; ``--policy conserving`` doubles the substitution
scale, which is the one-line repair for panphon's substitution ceiling
sitting at half its indel pair. Running both and diffing the columns is
the 1-versus-2 substitution question, asked of a corpus rather than
argued.

Usage:
    python scripts/costmodel_compare.py --corpus tests/panphon/shared-corpus.txt
    python scripts/costmodel_compare.py --policy faithful --policy conserving
    python scripts/costmodel_compare.py --format tsv > rows.tsv
"""

from __future__ import annotations

import argparse
import itertools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import ipakit  # noqa: E402
from ipakit.bridges.costmodel import (  # noqa: E402
    PANPHON_CONSERVING,
    CostPack,
    CostPolicy,
    compare,
    house_pack,
    pack_from_declaration,
)

DECLARATION = ROOT / "tests" / "panphon" / "panphon.xml"
CORPUS = ROOT / "tests" / "panphon" / "shared-corpus.txt"

#: The policies this script knows how to name. `faithful` is each model as
#: it stands -- the default every measurement is stated against, because a
#: finding about a silently repaired baseline is a finding about nothing.
POLICIES: dict[str, CostPolicy] = {
    "faithful": CostPolicy(),
    "conserving": PANPHON_CONSERVING,
}


def _packs(ipa: ipakit.IPAFeatures, policy: CostPolicy) -> list[CostPack]:
    """Both arms under one policy, or the house arm alone if the declared
    table is absent -- a checkout without the generated declaration should
    still be able to run half the comparison rather than none of it."""
    packs = [house_pack(ipa, policy)]
    if DECLARATION.exists():
        packs.append(pack_from_declaration(DECLARATION, policy))
    return packs


def _pairs(words: list[str], *, all_pairs: bool) -> list[tuple[str, str]]:
    """Every ordered pair, or the consecutive ones.

    Ordered rather than unordered on purpose: a cost model may be
    asymmetric, and one that is not loses nothing by being asked twice.
    """
    if all_pairs:
        return [(a, b) for a, b in itertools.permutations(words, 2)]
    return list(zip(words, words[1:], strict=False))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.formatter_class = argparse.RawDescriptionHelpFormatter
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    parser.add_argument(
        "--policy",
        action="append",
        choices=sorted(POLICIES),
        help="repeatable; defaults to every known policy",
    )
    parser.add_argument(
        "--all-pairs",
        action="store_true",
        help="every ordered pair rather than consecutive ones",
    )
    parser.add_argument("--format", choices=("table", "tsv"), default="table")
    args = parser.parse_args()

    words = [
        line.strip()
        for line in args.corpus.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    if len(words) < 2:
        sys.exit(f"{args.corpus} holds fewer than two forms")

    ipa = ipakit.IPAFeatures()
    names = args.policy or sorted(POLICIES)
    pairs = _pairs(words, all_pairs=args.all_pairs)

    header = (
        "policy",
        "pack",
        "geometry",
        "source",
        "target",
        "edit_cost",
        "normalized",
        "budget_ratio",
        "dropped",
    )
    rows: list[tuple[str, ...]] = []
    for name in names:
        policy = POLICIES[name]
        for pack in _packs(ipa, policy):
            for source, target in pairs:
                row = compare(ipa, pack, source, target)
                rows.append(
                    (
                        row.policy,
                        row.pack,
                        row.geometry,
                        source,
                        target,
                        f"{row.edit_cost:.6f}",
                        f"{row.normalized:.6f}",
                        f"{row.budget_ratio:.6f}",
                        ",".join(row.dropped),
                    )
                )

    if args.format == "tsv":
        print("\t".join(header))
        for row in rows:
            print("\t".join(row))
        return 0

    widths = [
        max(len(header[i]), max((len(r[i]) for r in rows), default=0))
        for i in range(len(header))
    ]
    print("  ".join(h.ljust(w) for h, w in zip(header, widths, strict=True)))
    print("  ".join("-" * w for w in widths))
    for row in rows:
        print("  ".join(c.ljust(w) for c, w in zip(row, widths, strict=True)))
    print(f"\n{len(rows)} rows: {len(pairs)} pair(s) x {len(names)} policy(ies)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
