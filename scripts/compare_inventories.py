#!/usr/bin/env python3
"""Draw two inventories, then show three answers to "how do they map?"

The library preserves declaration order because that is meaningful source data,
but declaration order hides structure in a figure. This example clusters the
shared and side-only groups independently while using one shared-phone order on
both axes, making exact matches a visible leading diagonal without discarding
the inventories' unmatched phones.

The mapping display fixes every shared phone to its identity first.  It then
compares the side-only phones in three ways: an unconstrained cover (a source
may be reused), an optimal one-to-one matching, and a partition of all sources
onto all targets, with globally optimal seeding of the uncovered targets.
Cover and matching make sense in either direction.  A partition does not: it
is a surjection, so it is refused when there are fewer side-only sources than
side-only targets.

For the default pair this matters twice.  ``ʊ`` and ``ə`` are shared and
therefore cannot also stand in for ``u`` and ``ʌ``.  The best eligible rows are
``ʉ → u`` and ``ɐ → ʌ`` instead: ʉ and ɐ are how MFA spells the vowels
CMU writes ``u`` and ``ʌ``.  With identities fixed, the partition recovers a
notational correspondence between the projects, not an acoustic near-miss.
"""

from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    import matplotlib
    import numpy as np
    from scipy.cluster.hierarchy import (
        leaves_list,
        linkage,
        optimal_leaf_ordering,
    )
    from scipy.optimize import linear_sum_assignment
    from scipy.spatial.distance import squareform
except ImportError as error:
    raise SystemExit(
        'inventory comparison extras are required; install with: pip install -e ".[compare]"'
    ) from error

matplotlib.use("svg")
import ipakit  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from scripts._comparison_order import aligned_orders  # noqa: E402

DEFAULT_CUTOFF = 0.75


@dataclass(frozen=True)
class Selection:
    """One selected from-phone for a to-phone."""

    source: str
    target: str
    similarity: float
    extra_cost: float = 0.0


def side_similarities(
    result: ipakit.PhonesetComparison,
) -> dict[tuple[str, str], float]:
    """Measure side-only sources against every target without source reuse."""
    row = {phone: i for i, phone in enumerate(result.a.phones)}
    column = {phone: i for i, phone in enumerate(result.b.phones)}
    return {
        (source, target): result.matrix[row[source]][column[target]]
        for source in result.only_a
        for target in result.b.phones
    }


def cover_selections(
    sources: tuple[str, ...],
    targets: tuple[str, ...],
    scores: dict[tuple[str, str], float],
) -> tuple[Selection, ...]:
    """Best source for each target, with reuse permitted."""
    return tuple(
        Selection(source, target, scores[source, target])
        for target in targets
        for source in [max(sources, key=lambda item: scores[item, target])]
    )


def matching_selections(
    sources: tuple[str, ...],
    targets: tuple[str, ...],
    scores: dict[tuple[str, str], float],
) -> tuple[Selection, ...]:
    """Globally optimal one-to-one selection, never greedy nearest-first."""
    rows, columns = linear_sum_assignment(
        np.asarray(
            [[-scores[source, target] for source in sources] for target in targets]
        )
    )
    by_target = {
        targets[row]: sources[column] for row, column in zip(rows, columns, strict=True)
    }
    return tuple(
        Selection(
            by_target[target],
            target,
            scores[by_target[target], target],
            max(scores[source, target] for source in sources)
            - scores[by_target[target], target],
        )
        for target in targets
    )


def partition_selections(
    sources: tuple[str, ...],
    uncovered_targets: tuple[str, ...],
    targets: tuple[str, ...],
    scores: dict[tuple[str, str], float],
) -> tuple[Selection, ...] | str:
    """Optimally seeded surjection, or the reason that no surjection exists.

    Surjectivity binds targets: every target must receive a source.  It does not
    bind sources to uncovered targets; after coverage is secured, every other
    source may join any target, including one already covered by an identity or
    another source, and therefore keeps its unconstrained best target.

    Choosing distinct representatives that maximize their total similarity to
    the uncovered targets is a linear assignment problem.  Solving it makes the
    seeding globally optimal (unlike filling targets greedily, which can spend
    another target's only good source).  It does not minimize total regret from
    every source's nearest target; that is a different objective.  Once seeded,
    each remaining source independently takes its nearest target.
    """
    if len(sources) < len(uncovered_targets):
        return (
            f"refused: partition has {len(sources)} side-only sources and "
            f"{len(uncovered_targets)} side-only targets; a surjection requires at least "
            "as many sources as targets"
        )
    best = {
        source: max(targets, key=lambda target: scores[source, target])
        for source in sources
    }
    seed_costs = np.asarray(
        [
            [-scores[source, target] for source in sources]
            for target in uncovered_targets
        ]
    )
    rows, columns = linear_sum_assignment(seed_costs)
    representative = {
        sources[column]: uncovered_targets[row]
        for row, column in zip(rows, columns, strict=True)
    }
    return tuple(
        Selection(
            source,
            representative.get(source, best[source]),
            scores[source, representative.get(source, best[source])],
            scores[source, best[source]]
            - scores[source, representative.get(source, best[source])],
        )
        for source in sources
    )


def print_mapping_table(
    title: str,
    sources: tuple[str, ...],
    targets: tuple[str, ...],
    scores: dict[tuple[str, str], float],
    selections: tuple[Selection, ...],
    cutoff: float,
) -> None:
    """Print target-first candidate rows, selected first and visibly marked."""
    print(f"\n{title}")
    print("to phone  candidates (descending similarity; * selected)")
    for target in targets:
        selected = [item for item in selections if item.target == target]
        selected_sources = {item.source for item in selected}
        candidates = sorted(
            (
                (source, scores[source, target])
                for source in sources
                if scores[source, target] >= cutoff or source in selected_sources
            ),
            key=lambda item: (-item[1], sources.index(item[0])),
        )
        selected_by_source = {item.source: item for item in selected}
        ordered = [item for item in candidates if item[0] in selected_sources]
        ordered.extend(item for item in candidates if item[0] not in selected_sources)
        rendered = []
        for source, similarity in ordered:
            choice = selected_by_source.get(source)
            mark = "*" if choice is not None else " "
            cost = (
                f", cost +{choice.extra_cost:.4f}"
                if choice is not None and choice.extra_cost > 5e-13
                else ""
            )
            rendered.append(f"{mark}{source} {similarity:.4f}{cost}")
        print(f"{target:<8}  {', '.join(rendered) or '—'}")


def print_mappings(result: ipakit.PhonesetComparison, cutoff: float) -> None:
    """Print fixed identities, three forward modes, and reverse refusal."""
    sources, targets = result.only_a, result.only_b
    scores = side_similarities(result)
    print(
        f"\nfixed identities: {len(result.intersection)} shared phones "
        "(reported as one block; each maps to itself)"
    )
    print(f"candidate cutoff: similarity >= {cutoff:.2f}")
    print_mapping_table(
        "unconstrained cover",
        sources,
        targets,
        scores,
        cover_selections(sources, targets, scores),
        cutoff,
    )
    print_mapping_table(
        "optimal one-to-one matching",
        sources,
        targets,
        scores,
        matching_selections(sources, targets, scores),
        cutoff,
    )
    partition = partition_selections(sources, targets, result.b.phones, scores)
    assert not isinstance(partition, str)
    print_mapping_table(
        "partition (globally optimal seeding; surjection)",
        sources,
        result.b.phones,
        scores,
        partition,
        cutoff,
    )
    by_pair = {(item.source, item.target): item for item in partition}
    if ("ʉ", "u") in by_pair and ("ɐ", "ʌ") in by_pair:
        high = by_pair["ʉ", "u"]
        low = by_pair["ɐ", "ʌ"]
        print(
            "fixed-identity rows: "
            f"*ʉ → u {high.similarity:.4f}, cost +{high.extra_cost:.4f}; "
            f"*ɐ → ʌ {low.similarity:.4f}, cost +{low.extra_cost:.4f}"
        )
    reverse = partition_selections(
        targets,
        sources,
        result.a.phones,
        {(target, source): value for (source, target), value in scores.items()},
    )
    assert isinstance(reverse, str)
    print(f"\nreverse partition\n{reverse}")


def clustered(phones: tuple[str, ...]) -> tuple[str, ...]:
    """Order one phone group by average linkage and optimal adjacent leaves."""
    if len(phones) < 2:
        return phones
    similarities = np.asarray(
        ipakit.phoneset_comparison(phones, phones).matrix, dtype=float
    )
    distances = 1.0 - similarities
    # The phone metric is symmetric, so this is a valid square distance matrix.
    distances = (distances + distances.T) / 2.0
    np.fill_diagonal(distances, 0.0)
    condensed = squareform(distances)
    tree = linkage(condensed, method="average")
    tree = optimal_leaf_ordering(tree, condensed)
    return tuple(phones[index] for index in leaves_list(tree))


def ordered_comparison(
    result: ipakit.PhonesetComparison,
) -> tuple[tuple[str, ...], tuple[str, ...], np.ndarray]:
    """Return aligned axes and the source matrix permuted onto them."""
    rows, columns = aligned_orders(
        result.intersection,
        result.only_a,
        result.only_b,
        clustered(result.intersection),
        clustered(result.only_a),
        clustered(result.only_b),
    )
    row_index = {phone: index for index, phone in enumerate(result.a.phones)}
    column_index = {phone: index for index, phone in enumerate(result.b.phones)}
    source = np.asarray(result.matrix, dtype=float)
    matrix = source[
        np.ix_(
            [row_index[phone] for phone in rows],
            [column_index[phone] for phone in columns],
        )
    ]
    return rows, columns, matrix


def write_tsv(
    path: Path,
    rows: tuple[str, ...],
    columns: tuple[str, ...],
    matrix: np.ndarray,
) -> None:
    """Write a labeled similarity matrix."""
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerow(("", *columns))
        for phone, values in zip(rows, matrix, strict=True):
            writer.writerow((phone, *(f"{value:.12g}" for value in values)))


def axis_label(phone: str, spelling: str | None) -> str:
    """Label a house phone and its inventory spelling when one is available."""
    return phone if spelling is None else f"{phone} · {spelling}"


def write_heatmap(
    path: Path,
    result: ipakit.PhonesetComparison,
    rows: tuple[str, ...],
    columns: tuple[str, ...],
    matrix: np.ndarray,
    a_name: str,
    b_name: str,
) -> None:
    """Write a self-contained SVG heatmap with the exact-match diagonal marked."""
    width = max(9.0, 3.5 + 0.23 * len(columns))
    height = max(7.0, 2.5 + 0.23 * len(rows))
    figure, axis = plt.subplots(figsize=(width, height), constrained_layout=True)
    image = axis.imshow(matrix, cmap="Blues", vmin=0.0, vmax=1.0, aspect="equal")
    axis.set_xticks(range(len(columns)))
    axis.set_yticks(range(len(rows)))
    axis.set_xticklabels(
        [axis_label(phone, result.spellings[phone][1]) for phone in columns],
        rotation=90,
        fontsize=7,
    )
    axis.set_yticklabels(
        [axis_label(phone, result.spellings[phone][0]) for phone in rows],
        fontsize=7,
    )
    axis.set_xlabel(b_name)
    axis.set_ylabel(a_name)
    axis.set_title("Phone inventory similarity (shared phones lead both axes)")
    for index in range(len(result.intersection)):
        axis.add_patch(
            Rectangle(
                (index - 0.5, index - 0.5),
                1,
                1,
                fill=False,
                edgecolor="#d95f02",
                linewidth=1.4,
            )
        )
    colorbar = figure.colorbar(image, ax=axis, shrink=0.7)
    colorbar.set_label("similarity")
    figure.savefig(path, format="svg", metadata={"Date": None})
    plt.close(figure)


def parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    argument_parser = argparse.ArgumentParser(description=__doc__)
    argument_parser.add_argument("a", nargs="?", default="mfa:english_us")
    argument_parser.add_argument("b", nargs="?", default="cmudict")
    argument_parser.add_argument(
        "--output",
        type=Path,
        default=Path("phoneset-comparison.svg"),
        help="SVG destination; the ordered TSV uses the same stem (default: %(default)s)",
    )
    argument_parser.add_argument(
        "--cutoff",
        type=float,
        default=DEFAULT_CUTOFF,
        help="minimum similarity shown in candidate lists (default: %(default)s)",
    )
    return argument_parser


def main() -> int:
    """Compare the selected inventories and write both views."""
    args = parser().parse_args()
    svg_path = args.output
    tsv_path = svg_path.with_suffix(".tsv")
    result = ipakit.phoneset_comparison(args.a, args.b)
    if not 0.0 <= args.cutoff <= 1.0:
        raise SystemExit("--cutoff must be between 0 and 1")
    rows, columns, matrix = ordered_comparison(result)
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    write_tsv(tsv_path, rows, columns, matrix)
    write_heatmap(svg_path, result, rows, columns, matrix, args.a, args.b)
    print(tsv_path)
    print(svg_path)
    print_mappings(result, args.cutoff)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
