#!/usr/bin/env python
"""Measure the geometry of the shipped distance matrix.

``docs/distance.md`` quotes what this prints. The numbers are a
*measurement of one commit*, not a live invariant, and nothing in
``make check`` recomputes them: the eigendecomposition needs numpy,
which is declared in the ``compare`` extra so the test jobs stay lean,
and a gate no CI job can run is not a gate. So the document names the
commit it measured and this script is how the next reader checks it::

    pip install -e ".[compare]"
    python scripts/geometry.py

The figures answer one question -- how far the dissimilarity is from
being a Euclidean metric, and what the leading axis encodes. Classical
multidimensional scaling double-centers the squared distances into a
Gram matrix; that matrix is positive semidefinite exactly when the
distances embed in Euclidean space, so the mass sitting on negative
eigenvalues is the amount by which they do not.

Two definitions are stated here rather than left to the reader, because
a correlation against an unstated predicate cannot be reproduced:
a phone is COMPOSITE when its segment reports more than one
constituent, and a VOWEL when its description ends in the word.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def measure() -> dict[str, object]:
    """The geometry of the shipped matrix, silence excluded.

    Silence is excluded because it is a declared zero carrying no
    phonetic features, so it sits at a constant distance from
    everything and dominates the leading axis without saying anything
    about phones.
    """
    import ipakit
    import numpy as np

    ipa = ipakit.IPAFeatures()
    phones = [p for p in ipa.phones if not ipa.describe(p).startswith("silence")]
    size = len(phones)

    distances = np.zeros((size, size))
    for i in range(size):
        for j in range(i + 1, size):
            distances[i, j] = distances[j, i] = ipakit.distance(phones[i], phones[j])

    centering = np.eye(size) - np.ones((size, size)) / size
    gram = -0.5 * centering @ (distances**2) @ centering
    values, vectors = np.linalg.eigh(gram)
    order = np.argsort(values)[::-1]
    values, vectors = values[order], vectors[:, order]

    positive = values[values > 0]
    leading = vectors[:, 0] * np.sqrt(values[0])

    composite = np.array(
        [float(len(ipakit.segment(p).constituents) > 1) for p in phones]
    )
    vowel = np.array([float(ipa.describe(p).endswith("vowel")) for p in phones])

    mask = composite.astype(bool)
    within = distances[np.ix_(mask, mask)][np.triu_indices(int(mask.sum()), 1)]
    across = distances[np.ix_(mask, ~mask)]

    return {
        "phones": size,
        "negative eigenvalue mass": _pct(
            abs(values[values < 0].sum()) / np.abs(values).sum()
        ),
        "leading positive variance": _pct(positive[0] / positive.sum()),
        "leading-axis/compositeness correlation": _round(
            abs(np.corrcoef(leading, composite)[0, 1])
        ),
        "leading-axis/vowelhood correlation": _round(
            abs(np.corrcoef(leading, vowel)[0, 1])
        ),
        "mean distance within composites": _round(within.mean()),
        "mean distance composites to atomics": _round(across.mean()),
    }


def _pct(fraction: float) -> str:
    return f"{100 * fraction:.1f}%"


def _round(value: float) -> float:
    return round(float(value), 3)


def main() -> int:
    try:
        measured = measure()
    except ImportError:
        print(
            "numpy is required: pip install -e '.[compare]'",
            file=sys.stderr,
        )
        return 2
    width = max(len(key) for key in measured)
    for key, value in measured.items():
        print(f"{key:<{width}}  {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
