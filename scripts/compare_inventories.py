#!/usr/bin/env python3
"""Cluster and draw the similarity matrix for two phone inventories.

The library preserves declaration order because that is meaningful source data,
but declaration order hides structure in a figure. This example clusters the
shared and side-only groups independently while using one shared-phone order on
both axes, making exact matches a visible leading diagonal without discarding
the inventories' unmatched phones.
"""

from __future__ import annotations

import argparse
import csv
import sys
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
    argument_parser.add_argument("a", nargs="?", default="cmudict")
    argument_parser.add_argument("b", nargs="?", default="mfa:english_us")
    argument_parser.add_argument(
        "--output",
        type=Path,
        default=Path("phoneset-comparison.svg"),
        help="SVG destination; the ordered TSV uses the same stem (default: %(default)s)",
    )
    return argument_parser


def main() -> int:
    """Compare the selected inventories and write both views."""
    args = parser().parse_args()
    svg_path = args.output
    tsv_path = svg_path.with_suffix(".tsv")
    result = ipakit.phoneset_comparison(args.a, args.b)
    rows, columns, matrix = ordered_comparison(result)
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    write_tsv(tsv_path, rows, columns, matrix)
    write_heatmap(svg_path, result, rows, columns, matrix, args.a, args.b)
    print(tsv_path)
    print(svg_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
