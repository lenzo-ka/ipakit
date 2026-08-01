"""A metric view of the phonetic distance, for callers that need one.

:func:`ipakit.distance` is a dissimilarity, not a metric: it is symmetric,
zero exactly on identity, and bounded, but it does not satisfy the
triangle inequality (see docs/distance.md). Algorithms whose correctness
rests on the inequality -- metric trees and ball trees for
nearest-neighbor search, some clustering and embedding methods -- are
wrong on it.

:class:`MetricClosure` is the shortest-path closure over an inventory:
the largest metric that is nowhere greater than the distance it is built
from. It satisfies the inequality by construction, and it is **not** the
default, for a reason worth stating plainly. Closure shortens a pair
whenever some third phone offers a cheaper path, and over the shipped
inventory those paths are usually artifacts rather than similarities: a
double articulation shares one constituent with each endpoint, so
``ɡ -> ɡ͡b -> b͡v`` is cheap while a voiced velar plosive and a voiced
labiodental affricate are not alike. Roughly a fifth of pairs shorten,
and the largest shortcuts land on some of the least similar pairs.

So this is a tool for the caller who needs the inequality and knows what
they are trading for it, not a correction of the metric.
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .features import IPAFeatures


class MetricClosure:
    """Shortest-path closure of the phonetic distance over an inventory.

    Satisfies the triangle inequality, symmetry, and identity. Unlike
    :func:`ipakit.distance` it is **inventory-relative**: a pair's value
    depends on which other phones are present, because they are the
    possible intermediate steps. Adding a phone can only shorten
    distances, never lengthen them.

    Only pairs drawn from :attr:`phones` are defined. Composed units
    outside the inventory have no closure, since there is no graph to
    take a path through; use :func:`ipakit.distance` for those.
    """

    def __init__(self, features: IPAFeatures, phones: list[str] | None = None):
        self.phones: list[str] = list(phones) if phones else list(features.phones)
        self._index = {p: i for i, p in enumerate(self.phones)}
        self._matrix = self._close(features)

    def _close(self, features: IPAFeatures) -> list[list[float]]:
        """Floyd-Warshall over the distance graph."""
        n = len(self.phones)
        rows = [[0.0] * n for _ in range(n)]
        for i, a in enumerate(self.phones):
            for j in range(i + 1, n):
                value = features.distance(a, self.phones[j])
                rows[i][j] = rows[j][i] = value
        for k in range(n):
            through = rows[k]
            for i in range(n):
                step = rows[i][k]
                row = rows[i]
                for j in range(n):
                    candidate = step + through[j]
                    if candidate < row[j]:
                        row[j] = candidate
        return rows

    def distance(self, phone1: str, phone2: str) -> float:
        """Closure distance between two phones of the inventory.

        Raises ``KeyError`` naming the phone if either is outside it --
        an unclosed pair has no answer here, and silently falling back to
        the open distance would break the inequality this exists to
        provide.
        """
        try:
            i, j = self._index[phone1], self._index[phone2]
        except KeyError as exc:
            raise KeyError(
                f"{exc.args[0]!r} is not in this closure's inventory; "
                "closure is defined only over the phones it was built from"
            ) from None
        return self._matrix[i][j]

    def shortened(self, features: IPAFeatures) -> list[tuple[str, str, float, float]]:
        """Pairs the closure moved, as ``(a, b, open, closed)``.

        The diagnostic that says what a closure cost you: each entry is a
        pair the inequality forced closer than the phonetic comparison
        put it.
        """
        moved = []
        for i, a in enumerate(self.phones):
            for j in range(i + 1, len(self.phones)):
                b = self.phones[j]
                opened = features.distance(a, b)
                closed = self._matrix[i][j]
                if opened - closed > 1e-9:
                    moved.append((a, b, opened, closed))
        return moved

    def __len__(self) -> int:
        return len(self.phones)

    def __repr__(self) -> str:
        return f"MetricClosure({len(self.phones)} phones)"


@functools.lru_cache(maxsize=4)
def _cached_closure(
    features: IPAFeatures, phones: tuple[str, ...] | None
) -> MetricClosure:
    return MetricClosure(features, list(phones) if phones else None)


def metric_closure(
    features: IPAFeatures, phones: list[str] | None = None
) -> MetricClosure:
    """Build a :class:`MetricClosure` over ``phones`` (default: the whole
    inventory). Memoized per inventory, since the closure is O(n^3)."""
    return _cached_closure(features, tuple(phones) if phones else None)
