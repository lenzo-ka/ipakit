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
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Self

from .constants import DEFAULT_CONFUSION
from .distance import WordDistanceResult, _empty_pair_result
from .metric import metric_fingerprint
from .models import Phoneset

if TYPE_CHECKING:
    from .features import IPAFeatures

Matrix = list[list[float]]

#: Format version written into a saved matrix. One spelling, read by
#: :meth:`DistanceModel.save` and by ``scripts/confusion.py``, which writes
#: the same object for the shipped inventory.
MATRIX_VERSION = "1.0"


def _load_matrix_json(path: Path) -> tuple[list[str], Matrix, str, str | None]:
    """Shipped/derived model: phones + upper triangle -> full symmetric matrix.

    The fourth element is the ``metric`` fingerprint the file records, or
    ``None`` where it records none.
    """
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    phones: list[str] = d["phones"]
    tri: list[float] = d["triangle"]
    space: str = d["space"]
    fingerprint: str | None = d.get("metric")
    n = len(phones)
    diag = 0.0 if space == "distance" else 1.0
    m: Matrix = [[diag] * n for _ in range(n)]
    k = 0
    for i in range(n):
        for j in range(i + 1, n):
            m[i][j] = m[j][i] = tri[k]
            k += 1
    return phones, m, space, fingerprint


def _load_matrix_tsv(
    path: Path, space: str = "similarity"
) -> tuple[list[str], Matrix, str]:
    """External confusion matrix: labeled phone x phone grid; symmetrized.

    A cell that is genuinely ``0`` is a real value, not "missing": when both
    directions are present the value is their average (so a ``0``/``x`` pair
    averages to ``x/2``, not ``x``); only a truly absent cell falls back to the
    other direction. Default space is 'similarity'.
    """
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
            ab = raw.get((a, b))
            ba = raw.get((b, a))
            if ab is not None and ba is not None:
                m[idx[a]][idx[b]] = (ab + ba) / 2
            elif ab is not None:
                m[idx[a]][idx[b]] = ab
            elif ba is not None:
                m[idx[a]][idx[b]] = ba
            # else: both absent -> keep the initialized default
    return phones, m, space


@functools.lru_cache(maxsize=1)
def _global_matrix() -> tuple[list[str], Matrix, str, str | None]:
    """Shipped global IPA matrix, loaded once."""
    return _load_matrix_json(DEFAULT_CONFUSION)


def _checked_global(ipa: IPAFeatures) -> tuple[list[str], Matrix, str]:
    """The shipped matrix, refused unless ``ipa`` is the space it came from.

    Every reader of ``data/confusion.json`` comes through here --
    :meth:`DistanceModel.global_`, which ``ipakit.distance_model()``
    builds on, and :meth:`DistanceModel.for_phoneset`, which re-slices the
    same values and does not go through ``global_``. Editing the shipped
    inventory and not regenerating is the case the fingerprint exists for,
    and this is the path that edit is actually read on.
    """
    phones, m, space, fingerprint = _global_matrix()
    _check_fingerprint(ipa, phones, fingerprint, DEFAULT_CONFUSION)
    return phones, m, space


def _check_fingerprint(
    ipa: IPAFeatures, phones: list[str], recorded: str | None, path: Path
) -> None:
    """Refuse a matrix derived in a feature space this inventory is not.

    Silent where ``recorded`` is ``None``. A TSV grid of empirical
    confusion data is not derived from the metric at all and has nothing
    to agree with, and refusing those would refuse the mechanism's main
    external use. Every matrix ipakit writes carries the key, so the
    silent case is exactly the case that should be silent.

    A disagreement is a refusal rather than a warning because the wrong
    answer is well formed and the caller has nothing to notice it by: a
    percentile from another inventory's reference distribution is a
    perfectly reasonable-looking number, and both readings of ``s``/``ʃ``
    look like a confusability.
    """
    if recorded is None:
        return
    derived = metric_fingerprint(ipa, phones)
    if derived == recorded:
        return
    raise ValueError(
        f"{path.name} was derived in a different feature space than "
        f"{ipa.xml_path.name} declares: the file records metric {recorded}, "
        f"this inventory gives {derived}. Percentiles read from it would be "
        "relative to a distribution this inventory did not produce. If you "
        "edited the inventory, regenerate the matrix: "
        "'python scripts/confusion.py generate --write' for the shipped one, "
        "or DistanceModel.derive(ipa).save(path) for your own."
    )


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
        """Default model: shipped global IPA matrix, CDF over all its pairs.

        Refuses if the shipped matrix was derived in a feature space
        ``ipa`` is not; see :func:`_checked_global`.
        """
        phones, m, space = _checked_global(ipa)
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
    def derive(
        cls,
        ipa: IPAFeatures,
        *,
        phones: list[str] | None = None,
        gamma: float = 1.0,
        insert_cost: float = 1.0,
        delete_cost: float = 1.0,
        sub_mode: str = "simple",
        threshold: float | None = None,
        max_length_ratio: float | None = None,
    ) -> Self:
        """Build the matrix from the inventory in hand, not from the shipped file.

        :meth:`global_` reads ``data/confusion.json``, which is derived from
        the bare shipped inventory and is a fixed object of exactly its
        phones. An inventory built with supplements has phones that file has
        no row for, and :meth:`for_phoneset` cannot help: it re-slices the
        shipped matrix, so a member outside it is dropped from the reference
        CDF with a warning. This is the constructor that gives a
        supplemented inventory its **own** derived data -- every pair
        recomputed through :meth:`IPAFeatures.pairwise_distances`, so the
        reference distribution is the one the caller actually declared.

        It costs a full pairwise pass, about a second at inventory scale.
        :meth:`save` writes the result in the format
        :meth:`from_matrix_file` reads, so a caller pays it once.

        The reference name is the files the inventory was built from, so a
        model's ``repr`` says which distribution its percentiles are
        relative to. They are not comparable across inventories.
        """
        ph = list(phones) if phones is not None else list(ipa.phones)
        matrix = ipa.pairwise_distances(ph)
        name = "+".join([ipa.xml_path.stem, *ipa.supplements])
        return cls(
            ipa,
            name,
            ph,
            matrix,
            "distance",
            gamma=gamma,
            insert_cost=insert_cost,
            delete_cost=delete_cost,
            sub_mode=sub_mode,
            threshold=threshold,
            max_length_ratio=max_length_ratio,
        )

    def save(self, path: str | Path) -> Path:
        """Write this model's matrix where :meth:`from_matrix_file` can read it.

        The upper triangle only, which is the shape ``data/confusion.json``
        ships in and :func:`_load_matrix_json` reads. What is written is the
        matrix, not the model: ``gamma`` and the alignment costs are
        arguments to a constructor, and baking them into the file would put
        one number in two places.

        Only the reference sub-inventory is written, so a model already
        sliced to a phoneset saves that slice.

        ``metric`` is :func:`~ipakit.metric.metric_fingerprint` over the
        phones written, so the file says which feature space its numbers
        mean something in and :meth:`from_matrix_file` can refuse a
        reader that is not in it.
        """
        ref = [p for p in self._ref if p in self._index]
        idxs = [self._index[p] for p in ref]
        n = len(idxs)
        model = {
            "version": MATRIX_VERSION,
            "reference": self._name,
            "space": self._space,
            "metric": metric_fingerprint(self._ipa, ref),
            "phones": ref,
            "triangle": [
                self._m[idxs[i]][idxs[j]] for i in range(n) for j in range(i + 1, n)
            ],
        }
        out = Path(path)
        out.write_text(
            json.dumps(model, ensure_ascii=False, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        return out

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
        """Reuse the shipped global matrix values; re-slice the CDF to `phoneset`.

        Members absent from the matrix are dropped from the reference CDF
        with a warning -- never silently. A member whose house-canonical
        spelling (via ``from_wild``) IS in the matrix is called out
        specifically: the phoneset is written in another tie convention
        and should be imported with :meth:`IPAFeatures.import_phoneset`.
        """
        phones, m, space = _checked_global(ipa)
        index = {p: i for i, p in enumerate(phones)}
        ref = [p for p in phoneset.phones if p in index]
        dropped = [p for p in phoneset.phones if p not in index]
        if dropped:
            respellable = [p for p in dropped if ipa.from_wild(p) in index]
            message = (
                f"phoneset {phoneset.name!r}: {len(dropped)} member(s) not in "
                f"the distance matrix were dropped from the reference CDF: "
                f"{' '.join(dropped)}."
            )
            if respellable:
                message += (
                    f" Of these, {' '.join(respellable)} are tie-convention "
                    "spellings of known compounds; import the phoneset with "
                    "IPAFeatures.import_phoneset() to canonicalize them."
                )
            warnings.warn(message, stacklevel=3)
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
            phones, m, sp, fingerprint = _load_matrix_json(p)
            _check_fingerprint(ipa, phones, fingerprint, p)
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

    def _resolves(self, token: str) -> bool:
        """Whether the wrapped IPAFeatures can derive features for ``token``."""
        return bool(self._ipa.compose(token, with_defaults=False))

    def confusability(self, a: str, b: str) -> float:
        """Normalized confusability of two phones, in [0, 1].

        The percentile of the pair's raw similarity within the reference
        inventory's distribution (then raised to ``gamma``). 1.0 for identical
        phones. A phone outside the model's matrix falls back to
        feature-derived similarity through the same CDF, matching
        :meth:`sub_cost` (and sharing its calibration caveat); 0.0 if a
        phone's features cannot be derived at all.
        """
        if a == b:
            return 1.0
        i = self._index.get(a)
        j = self._index.get(b)
        if i is not None and j is not None:
            return self._norm_conf(self._cell_sim(i, j))
        if not (self._resolves(a) and self._resolves(b)):
            return 0.0
        return self._norm_conf(1.0 - self._ipa.segment_distance(a, b))

    def similarity(self, a: str, b: str) -> float:
        """Alias for :meth:`confusability`."""
        return self.confusability(a, b)

    def distance(self, a: str, b: str) -> float:
        """Renormalized phone distance: ``1 - confusability(a, b)``."""
        return 1.0 - self.confusability(a, b)

    def nearest(self, phone: str, n: int = 10) -> list[tuple[str, float]]:
        """The ``n`` reference phones closest to ``phone``.

        Returns ``(phone, distance)`` pairs sorted by ascending distance.
        A phone outside the model's matrix is scored against the reference
        inventory via the :meth:`confusability` fallback; empty if its
        features cannot be derived at all.
        """
        if phone not in self._index and not self._resolves(phone):
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

        Note: the OOV fallback similarity is feature-derived and is currently
        routed through the same CDF (``_norm_conf``) as matrix-derived
        similarities, even though the two live on different scales. This keeps
        in-inventory and OOV costs in one [0, 1] range for the DP, but the
        percentile is only strictly meaningful for in-inventory pairs. Left as
        a deliberate modeling choice pending empirical calibration.
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
        t1 = [
            t for t in self._ipa.tokenize(ipa1) if not self._ipa.is_structural_token(t)
        ]
        t2 = [
            t for t in self._ipa.tokenize(ipa2) if not self._ipa.is_structural_token(t)
        ]
        n, m = len(t1), len(t2)
        if n == 0 and m == 0:
            return _empty_pair_result(return_alignment)
        dist, alignment = self._ipa._align(
            t1, t2, self.sub_cost, self._insert, self._delete, return_alignment
        )
        # Consistent denominator across modes keeps similarity in [0, 1] and lets
        # di-mode separate dissimilar pairs more than simple-mode.
        denom = n * self._delete + m * self._insert
        similarity = max(0.0, 1.0 - dist / denom) if denom else 1.0
        return WordDistanceResult(
            edit_cost=dist, similarity=similarity, alignment=alignment
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
        n = len(self._ipa.tokenize(ipa1))
        m = len(self._ipa.tokenize(ipa2))
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
