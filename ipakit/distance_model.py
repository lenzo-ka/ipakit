"""Distribution-aware phonetic distance over a fixed reference inventory.

One canonical object -- a symmetric phone x phone matrix of pairwise values --
underlies everything. The matrix is inventory-independent (feature-derived, or
an empirical confusion matrix); the empirical CDF is the inventory-relative view
derived from whichever sub-matrix a reference inventory selects. Output is a
PERCENTILE within that reference (a normalized confusability / its complementary
distance), not an absolute distance, and is not comparable across inventories.

The global matrix is built at dev time and shipped (data/confusion.json, guarded
by scripts/confusion.py). Per-phoneset models reuse the shipped values and only
re-slice the CDF. External confusion matrices load via from_matrix_file (TSV/JSON).

Raw absolute distance stays on IPAFeatures.distance(); this layer never changes it.
"""

from __future__ import annotations

import bisect
import functools
import json
from pathlib import Path
from typing import TYPE_CHECKING, Self

from .constants import DEFAULT_CONFUSION
from .distance import WordDistanceResult
from .models import Phoneset

if TYPE_CHECKING:
    from .features import IPAFeatures

Matrix = list[list[float]]


def _load_matrix_json(path: Path) -> tuple[list[str], Matrix, str]:
    """Shipped/derived model: phones + upper triangle -> full symmetric matrix."""
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    phones: list[str] = d["phones"]
    tri: list[float] = d["triangle"]
    space: str = d["space"]
    n = len(phones)
    diag = 0.0 if space == "distance" else 1.0
    m: Matrix = [[diag] * n for _ in range(n)]
    k = 0
    for i in range(n):
        for j in range(i + 1, n):
            m[i][j] = m[j][i] = tri[k]
            k += 1
    return phones, m, space


def _load_matrix_tsv(
    path: Path, space: str = "similarity"
) -> tuple[list[str], Matrix, str]:
    """External confusion matrix: labeled phone x phone grid; symmetrized
    (non-zero wins; both present -> average). Default space is 'similarity'."""
    lines = [
        ln for ln in Path(path).read_text(encoding="utf-8").splitlines() if ln.strip()
    ]
    phones = lines[0].split("\t")[1:]
    idx = {p: i for i, p in enumerate(phones)}
    n = len(phones)
    raw: dict[tuple[str, str], float] = {}
    for ln in lines[1:]:
        cells = ln.split("\t")
        row = cells[0]
        for c, val in enumerate(cells[1:]):
            raw[(row, phones[c])] = float(val)
    diag = 1.0 if space == "similarity" else 0.0
    m: Matrix = [[diag] * n for _ in range(n)]
    for a in phones:
        for b in phones:
            if a == b:
                continue
            ab = raw.get((a, b), 0.0)
            ba = raw.get((b, a), 0.0)
            m[idx[a]][idx[b]] = (ab + ba) / 2 if (ab and ba) else (ab or ba)
    return phones, m, space


@functools.lru_cache(maxsize=1)
def _global_matrix() -> tuple[list[str], Matrix, str]:
    """Shipped global IPA matrix, loaded once."""
    return _load_matrix_json(DEFAULT_CONFUSION)


class DistanceModel:
    """CDF-renormalized phonetic distance over a reference inventory."""

    def __init__(
        self,
        ipa: IPAFeatures,
        reference_name: str,
        phones: list[str],
        matrix: Matrix,
        space: str,
        *,
        ref_phones: list[str] | None = None,
        gamma: float = 1.0,
        insert_cost: float = 1.0,
        delete_cost: float = 1.0,
        sub_mode: str = "simple",
        threshold: float | None = None,
        max_length_ratio: float | None = None,
    ) -> None:
        """Construct a model from a phone x phone ``matrix``.

        Prefer the :meth:`global_`, :meth:`for_phoneset`, and
        :meth:`from_matrix_file` constructors over calling this directly.

        Args:
            ipa: IPAFeatures, used to tokenize words and as a fallback metric.
            reference_name: Label for the reference inventory (used in repr).
            phones: Phones indexing ``matrix`` rows/columns.
            matrix: Symmetric phone x phone values.
            space: ``"distance"`` or ``"similarity"`` -- how to read ``matrix``.
            ref_phones: Sub-inventory the CDF is built over (default: ``phones``).
            gamma: Exponent applied to the percentile (>1 spreads dissimilar pairs).
            insert_cost: Per-token insertion cost in word alignment.
            delete_cost: Per-token deletion cost in word alignment.
            sub_mode: ``"simple"`` or ``"di"`` (scale substitution by indel costs).
            threshold: Default similarity threshold for :meth:`is_similar`.
            max_length_ratio: Default length-ratio gate for :meth:`is_similar`.
        """
        if sub_mode not in ("simple", "di"):
            raise ValueError(f"sub_mode must be 'simple' or 'di', got {sub_mode!r}")
        if space not in ("distance", "similarity"):
            raise ValueError(f"space must be 'distance' or 'similarity', got {space!r}")
        self._ipa = ipa
        self._name = reference_name
        self._m = matrix
        self._space = space
        self._gamma = gamma
        self._insert = insert_cost
        self._delete = delete_cost
        self._sub_mode = sub_mode
        self._threshold = threshold
        self._max_length_ratio = max_length_ratio
        self._index = {p: i for i, p in enumerate(phones)}
        self._ref = list(ref_phones) if ref_phones is not None else list(phones)
        self._cdf = self._build_cdf()

    # -- construction ---------------------------------------------------------

    @classmethod
    def global_(
        cls,
        ipa: IPAFeatures,
        *,
        gamma: float = 1.0,
        insert_cost: float = 1.0,
        delete_cost: float = 1.0,
        sub_mode: str = "simple",
        threshold: float | None = None,
        max_length_ratio: float | None = None,
    ) -> Self:
        """Default model: shipped global IPA matrix, CDF over all its pairs."""
        phones, m, space = _global_matrix()
        return cls(
            ipa,
            "ipa",
            phones,
            m,
            space,
            gamma=gamma,
            insert_cost=insert_cost,
            delete_cost=delete_cost,
            sub_mode=sub_mode,
            threshold=threshold,
            max_length_ratio=max_length_ratio,
        )

    @classmethod
    def for_phoneset(
        cls,
        ipa: IPAFeatures,
        phoneset: Phoneset,
        *,
        gamma: float = 1.0,
        insert_cost: float = 1.0,
        delete_cost: float = 1.0,
        sub_mode: str = "simple",
        threshold: float | None = None,
        max_length_ratio: float | None = None,
    ) -> Self:
        """Reuse the shipped global matrix values; re-slice the CDF to `phoneset`."""
        phones, m, space = _global_matrix()
        index = {p: i for i, p in enumerate(phones)}
        ref = [p for p in phoneset.phones if p in index]
        return cls(
            ipa,
            phoneset.name,
            phones,
            m,
            space,
            ref_phones=ref,
            gamma=gamma,
            insert_cost=insert_cost,
            delete_cost=delete_cost,
            sub_mode=sub_mode,
            threshold=threshold,
            max_length_ratio=max_length_ratio,
        )

    @classmethod
    def from_matrix_file(
        cls,
        ipa: IPAFeatures,
        path: str | Path,
        *,
        space: str | None = None,
        gamma: float = 1.0,
        insert_cost: float = 1.0,
        delete_cost: float = 1.0,
        sub_mode: str = "simple",
        threshold: float | None = None,
        max_length_ratio: float | None = None,
    ) -> Self:
        """External confusion matrix (TSV grid or JSON model). CDF over its pairs."""
        p = Path(path)
        if p.suffix == ".tsv":
            phones, m, sp = _load_matrix_tsv(p, space=space or "similarity")
        else:
            phones, m, sp = _load_matrix_json(p)
        return cls(
            ipa,
            p.stem,
            phones,
            m,
            sp,
            gamma=gamma,
            insert_cost=insert_cost,
            delete_cost=delete_cost,
            sub_mode=sub_mode,
            threshold=threshold,
            max_length_ratio=max_length_ratio,
        )

    # -- introspection --------------------------------------------------------

    @property
    def reference_name(self) -> str:
        """Name of the reference inventory the CDF is built over."""
        return self._name

    @property
    def reference_phones(self) -> list[str]:
        """Copy of the reference inventory the percentiles are relative to."""
        return list(self._ref)

    @property
    def gamma(self) -> float:
        """Percentile exponent (>1 spreads dissimilar pairs apart)."""
        return self._gamma

    @property
    def sub_mode(self) -> str:
        """Substitution-cost mode for word alignment ('simple' or 'di')."""
        return self._sub_mode

    # -- internals ------------------------------------------------------------

    def _cell_sim(self, i: int, j: int) -> float:
        """Single normalization point: read any matrix as similarity."""
        v = self._m[i][j]
        return v if self._space == "similarity" else 1.0 - v

    def _build_cdf(self) -> list[float]:
        idxs = [self._index[p] for p in self._ref if p in self._index]
        cdf = [
            self._cell_sim(idxs[a], idxs[b])
            for a in range(len(idxs))
            for b in range(a + 1, len(idxs))
        ]
        cdf.sort()
        return cdf

    def _norm_conf(self, sim: float) -> float:
        """Percentile of a raw similarity within the reference distribution (+ gamma)."""
        if not self._cdf:
            return sim
        p = bisect.bisect_right(self._cdf, sim) / len(self._cdf)
        return p**self._gamma if self._gamma != 1.0 else p

    # -- phone-level API ------------------------------------------------------

    def confusability(self, a: str, b: str) -> float:
        """Normalized confusability of two phones, in [0, 1].

        The percentile of the pair's raw similarity within the reference
        inventory's distribution (then raised to ``gamma``). 1.0 for identical
        phones; 0.0 if either phone is outside the model's matrix.
        """
        if a == b:
            return 1.0
        i = self._index.get(a)
        j = self._index.get(b)
        if i is None or j is None:
            return 0.0
        return self._norm_conf(self._cell_sim(i, j))

    def similarity(self, a: str, b: str) -> float:
        """Alias for :meth:`confusability`."""
        return self.confusability(a, b)

    def distance(self, a: str, b: str) -> float:
        """Renormalized phone distance: ``1 - confusability(a, b)``."""
        return 1.0 - self.confusability(a, b)

    def nearest(self, phone: str, n: int = 10) -> list[tuple[str, float]]:
        """The ``n`` reference phones closest to ``phone``.

        Returns ``(phone, distance)`` pairs sorted by ascending distance; empty
        if ``phone`` is outside the model's matrix.
        """
        if phone not in self._index:
            return []
        ds = [(p, self.distance(phone, p)) for p in self._ref if p != phone]
        ds.sort(key=lambda x: (x[1], x[0]))
        return ds[:n]

    # -- word-level API -------------------------------------------------------

    def sub_cost(self, t1: str, t2: str) -> float:
        """Substitution cost between two tokens for the edit-distance DP.

        ``1 - confusability`` for in-inventory pairs, falling back to the
        feature distance for out-of-inventory tokens. In ``sub_mode='di'`` the
        cost is scaled by ``insert + delete``.
        """
        if t1 == t2:
            return 0.0
        i = self._index.get(t1)
        j = self._index.get(t2)
        if i is not None and j is not None:
            sim = self._cell_sim(i, j)
        else:
            sim = 1.0 - self._ipa.segment_distance(t1, t2)
        cost = 1.0 - self._norm_conf(sim)
        if self._sub_mode == "di":
            return (self._insert + self._delete) * cost
        return cost

    def word_distance(
        self, ipa1: str, ipa2: str, *, return_alignment: bool = False
    ) -> WordDistanceResult:
        """Phonetic edit distance between two IPA words under this model.

        Uses the model's renormalized substitution costs (and indel costs) in a
        weighted-Levenshtein alignment. Returns a :class:`WordDistanceResult`;
        pass ``return_alignment=True`` to include the aligned token pairs.
        """
        t1 = self._ipa.tokenize_ipa(ipa1)
        t2 = self._ipa.tokenize_ipa(ipa2)
        n, m = len(t1), len(t2)
        if n == 0 and m == 0:
            return WordDistanceResult(
                distance=0.0,
                similarity=1.0,
                alignment=[] if return_alignment else None,
            )
        dist, alignment = self._ipa._align(
            t1, t2, self.sub_cost, self._insert, self._delete, return_alignment
        )
        # Consistent denominator across modes keeps similarity in [0, 1] and lets
        # di-mode separate dissimilar pairs more than simple-mode.
        denom = n * self._delete + m * self._insert
        similarity = max(0.0, 1.0 - dist / denom) if denom else 1.0
        return WordDistanceResult(
            distance=dist, similarity=similarity, alignment=alignment
        )

    def word_similarity(self, ipa1: str, ipa2: str) -> float:
        """The ``similarity`` field of :meth:`word_distance` (in [0, 1])."""
        return self.word_distance(ipa1, ipa2).similarity

    def _max_word_similarity(self, n: int, m: int) -> float:
        """True content-independent upper bound: only |n-m| forced indels."""
        denom = n * self._delete + m * self._insert
        if not denom:
            return 1.0
        dmin = abs(n - m) * min(self._insert, self._delete)
        return 1.0 - dmin / denom

    def is_similar(
        self,
        ipa1: str,
        ipa2: str,
        *,
        threshold: float | None = None,
        max_length_ratio: float | None = None,
    ) -> bool:
        """Whether two words' similarity meets ``threshold``.

        ``threshold`` (and optional ``max_length_ratio``) fall back to the
        model defaults; a missing threshold raises ``ValueError``. Words whose
        length ratio exceeds ``max_length_ratio``, or that cannot reach the
        threshold given an upper-bound check, short-circuit before the DP runs.
        """
        th = threshold if threshold is not None else self._threshold
        if th is None:
            raise ValueError(
                "threshold required (pass threshold= or set a model default)"
            )
        mr = (
            max_length_ratio if max_length_ratio is not None else self._max_length_ratio
        )
        n = len(self._ipa.tokenize_ipa(ipa1))
        m = len(self._ipa.tokenize_ipa(ipa2))
        if n == 0 or m == 0:
            return n == m
        if mr is not None and max(n, m) / min(n, m) > mr:
            return False
        if self._max_word_similarity(n, m) < th:  # skip DP: can't reach threshold
            return False
        return self.word_similarity(ipa1, ipa2) >= th

    def __repr__(self) -> str:
        return (
            f"DistanceModel(reference={self._name!r}, phones={len(self._ref)}, "
            f"space={self._space!r}, sub_mode={self._sub_mode!r}, gamma={self._gamma})"
        )
