"""Distance calculation mixin for IPAFeatures."""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

from ._base import IPAFeaturesBase
from .constants import METADATA_ATTRS

# One alignment step pairs a token from each word; None marks an insertion/deletion.
Alignment = list[tuple[str | None, str | None]]


@dataclass
class WordDistanceResult:
    """Result of a word-level comparison.

    ``edit_cost`` is the summed alignment cost and is **not** bounded to
    [0, 1] -- it grows with word length. ``similarity`` is the normalized
    [0, 1] figure and is what compares across word pairs. The unbounded
    quantity is named distinctly because the [0, 1] ``distance`` of
    :func:`distance` and the percentile of :func:`normalized_distance`
    already share that word.

    ``coverage`` is ``min(n, m) / max(n, m)`` over the two token counts.
    It is reported beside the score and deliberately **not** folded into
    it: length is already charged once, as the gaps the alignment pays
    for, and a second multiplicative term would charge it twice. What it
    adds is a diagnosis rather than a magnitude -- it separates "these
    differ throughout" from "one is a truncation of the other", which a
    single number cannot say.
    """

    edit_cost: float
    similarity: float
    coverage: float
    alignment: Alignment | None = None


def _substitution_cost(
    dissimilarity: float, insert_cost: float, delete_cost: float
) -> float:
    """Price a [0, 1] dissimilarity as an edit cost.

    A substitution is a deletion and an insertion, discounted by what the
    two tokens share: at 0 the position is free, and at 1 -- nothing in
    common -- it costs exactly ``delete + insert``, which is what removing
    one token and supplying the other costs. The standard constraint
    ``sub(a, b) <= delete(a) + insert(b)`` is then met with equality at the
    top rather than with room to spare, so a chain of substitutions is
    preferred to a pair of gaps exactly when the tokens along it really do
    share something.

    The metric answers a proportion and the aligner charges a price; this
    is the one place the first is turned into the second, so the two
    word-distance paths cannot put them on different scales.
    """
    return (insert_cost + delete_cost) * dissimilarity


def _word_result(
    n: int,
    m: int,
    edit_cost: float,
    alignment: Alignment | None,
    insert_cost: float,
    delete_cost: float,
) -> WordDistanceResult:
    """Normalize an alignment cost -- one read for both word-distance paths.

    The denominator is ``n * delete + m * insert``: the cost of the null
    alignment, which deletes every token of the first word and inserts
    every token of the second. That path is one the DP minimizes over, so
    it is also the most any alignment can cost, and ``similarity`` spans
    [0, 1] with both ends attainable -- 1 on identity, 0 when the two
    words share nothing at any position. ``max(n, m)`` was the other
    reading, and it is a different claim: it charges a truncation once,
    where this charges the material that went missing and the material
    that replaced it apart.
    """
    denom = n * delete_cost + m * insert_cost
    similarity = 1.0 - edit_cost / denom if denom else 1.0
    return WordDistanceResult(
        edit_cost=edit_cost,
        similarity=similarity,
        coverage=(min(n, m) / max(n, m)) if max(n, m) else 1.0,
        alignment=alignment,
    )


def _empty_pair_result(return_alignment: bool) -> WordDistanceResult:
    """Result for two empty token sequences: identical, zero cost."""
    return WordDistanceResult(
        edit_cost=0.0,
        similarity=1.0,
        coverage=1.0,
        alignment=[] if return_alignment else None,
    )


class DistanceMixin(IPAFeaturesBase):
    """Mixin providing phonetic distance calculations."""

    def _feature_dict_distance(self, f1: dict[str, str], f2: dict[str, str]) -> float:
        """Compute distance between two feature dictionaries.

        An empty union of comparable keys scores 0.0, not 1.0. The
        branch reads as "nothing to compare on", but it is reachable
        only when *both* sides carry no comparable key, and then neither
        holds anything the other lacks -- which is identity, not maximal
        difference. The case that actually is maximally different, one
        side comparable and the other not, never reaches here: its keys
        are all present on one side only, each scores 1, and 1.0 falls
        out of the mean rather than being asserted.
        """
        all_keys = (set(f1) | set(f2)) - METADATA_ATTRS
        if not all_keys:
            return 0.0
        total = sum(
            (
                self.features[k].value_distance(f1.get(k), f2.get(k))
                if k in self.features
                else (0.0 if f1.get(k) == f2.get(k) else 1.0)
            )
            for k in all_keys
        )
        return total / len(all_keys)

    def distance(self, phone1: str, phone2: str) -> float:
        """Structural distance between two phones/units (0.0-1.0).

        Routed through the Segment metric (design spec section 7):
        constituents compare as whole bundles, alignment follows the unit
        kinds, junctures carry the binding-sense term, and secondary
        articulations contribute weighted place components. An unknown
        phone yields the sentinel ``1.0`` (maximally different).

        Both arguments must be a single unit. Multi-unit input raises
        rather than returning the sentinel: reporting two identical words
        as maximally different is worse than refusing to answer. Use
        :meth:`word_distance` for words, :meth:`segment_distance` for
        segment strings.

        An input the metric cannot read is maximally different from
        anything else, but not from itself: identity is checked before
        the sentinel, over NFC forms, since string identity is the only
        basis left once the segment cannot be built. ``distance("", "")``
        is 0.0 for the same reason.
        """
        for arg in (phone1, phone2):
            units = self.segments(arg)  # type: ignore[attr-defined]
            if len(units) > 1:
                raise ValueError(
                    f"distance() compares single units; {arg!r} is "
                    f"{len(units)} units. Use word_distance() for words, "
                    "or segment_distance() for segment strings."
                )
        try:
            s1 = self.segment(phone1)  # type: ignore[attr-defined]
            s2 = self.segment(phone2)  # type: ignore[attr-defined]
        except ValueError:
            same = unicodedata.normalize("NFC", phone1) == unicodedata.normalize(
                "NFC", phone2
            )
            return 0.0 if same else 1.0
        from .metric import segment_metric

        return segment_metric(self, s1, s2)  # type: ignore[arg-type]

    def segment_distance(self, seg1: str, seg2: str) -> float:
        """Distance between two segment strings (potentially multi-unit).

        One flat positional mean over ``max(len(t1), len(t2))`` terms:
        a position where both sides carry a unit costs the Segment
        metric, a position only one side reaches costs ``GAP_COST``.
        This is the normalization :func:`~ipakit.metric.segment_metric`
        already uses over a unit's parts (docs/distance.md section 4),
        applied one level up, and it is what keeps the three costs in
        one currency: a substitution prices the same whether the pair
        stands alone or sits inside a longer string, and an unmatched
        unit prices exactly what a gap costs in :meth:`word_distance`.
        This is a dissimilarity, in [0, 1]; :meth:`word_distance` takes
        it as its substitution *cost* by pricing it as the delete and
        the insert it stands in for, so a maximally different pair costs
        both and an identical one costs neither.

        Length is not a second, separately normalized term. It was one,
        summed with the positional mean and halved, which charged an
        unmatched unit its full 1.0 twice -- once positionally and once
        as length -- and paid for it by halving every ordinary
        substitution. Length enters here the way it enters every other
        alignment in the library: as positions that cost a gap.

        Two empty inputs are identical and score 0.0. An empty input
        against a non-empty one needs no special case: every position is
        unmatched, so the mean is exactly 1.0.
        """
        from .metric import GAP_COST, segment_metric

        t1 = self.segments(seg1)  # type: ignore[attr-defined]
        t2 = self.segments(seg2)  # type: ignore[attr-defined]
        max_len = max(len(t1), len(t2))
        if max_len == 0:
            return 0.0
        total = sum(
            (
                segment_metric(self, t1[i], t2[i])  # type: ignore[arg-type,misc]
                if i < len(t1) and i < len(t2)
                else GAP_COST
            )
            for i in range(max_len)
        )
        return total / max_len

    def pairwise_distances(self, phones: list[str]) -> list[list[float]]:
        """Compute pairwise distance matrix for a list of phones.

        Returns a 2D list where matrix[i][j] is the distance between phones[i] and phones[j].
        """
        n = len(phones)
        matrix = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                d = self.distance(phones[i], phones[j])
                matrix[i][j] = d
                matrix[j][i] = d
        return matrix

    def _align(
        self,
        tokens1: list[str],
        tokens2: list[str],
        sub_cost: Callable[[str, str], float],
        insert_cost: float = 1.0,
        delete_cost: float = 1.0,
        return_alignment: bool = False,
    ) -> tuple[float, Alignment | None]:
        """Weighted-Levenshtein DP shared by word_distance and DistanceModel.

        Costs are parameterized so callers choose unit indel (default) or a
        weighted/di-mode policy. Returns (distance, alignment).
        """
        n, m = len(tokens1), len(tokens2)
        dp = [[0.0] * (m + 1) for _ in range(n + 1)]
        for i in range(n + 1):
            dp[i][0] = i * delete_cost
        for j in range(m + 1):
            dp[0][j] = j * insert_cost
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                dp[i][j] = min(
                    dp[i - 1][j] + delete_cost,
                    dp[i][j - 1] + insert_cost,
                    dp[i - 1][j - 1] + sub_cost(tokens1[i - 1], tokens2[j - 1]),
                )

        alignment: Alignment | None = None
        if return_alignment:
            alignment = []
            i, j = n, m
            while i > 0 or j > 0:
                if (
                    i > 0
                    and j > 0
                    and dp[i][j]
                    == dp[i - 1][j - 1] + sub_cost(tokens1[i - 1], tokens2[j - 1])
                ):
                    alignment.append((tokens1[i - 1], tokens2[j - 1]))
                    i -= 1
                    j -= 1
                    continue
                if i > 0 and dp[i][j] == dp[i - 1][j] + delete_cost:
                    alignment.append((tokens1[i - 1], None))
                    i -= 1
                elif j > 0:
                    alignment.append((None, tokens2[j - 1]))
                    j -= 1
            alignment.reverse()

        return dp[n][m], alignment

    def _reject_unconvertible(self, *texts: str) -> None:
        """Raise if any text contains symbols the tokenizer would drop.

        Conversion may reasonably be lossy; measurement may not. Silently
        dropping a symbol turns "these words differ" into a plausible
        number computed from truncated input.
        """
        for text in texts:
            self.parse(text, strict=True)  # type: ignore[attr-defined]

    def word_distance(
        self,
        ipa1: str,
        ipa2: str,
        weighted: bool = True,
        return_alignment: bool = False,
        strict: bool = True,
    ) -> WordDistanceResult:
        """Compute phonetic edit distance between two IPA words.

        Uses Levenshtein-style dynamic programming with phonetic feature costs
        for substitutions when weighted=True.

        A caller wanting its own substitution policy passes it to
        :meth:`_align`, which is the parameterized one and is what
        :class:`~ipakit.distance_model.DistanceModel` calls. This method
        used to take a ``sub_cost`` of its own documented as the route
        ``DistanceModel`` took, and no caller ever passed it.

        A gap costs ``GAP_COST``, which is what an unmatched position costs
        one level down in :meth:`segment_distance` and inside
        :func:`~ipakit.metric.segment_metric`. A substitution costs the
        token pair's dissimilarity priced by :func:`_substitution_cost`, so
        a position where the two words share nothing costs exactly the
        delete and the insert it stands for. That is what puts the two
        operations in one currency: without it every substitution, however
        unlike the tokens, is cheaper than a single gap, and an alignment
        that should read "this was dropped and that one added" is always
        reported as a substitution.

        Args:
            ipa1: First IPA string
            ipa2: Second IPA string
            weighted: If True, use feature distance for substitution costs (0-1).
                      If False, every mismatch is maximally different, which
                      is Levenshtein's substitution policy.
            return_alignment: If True, include the alignment path in result.
            strict: Reject input containing symbols the tokenizer cannot
                convert (the default). Pass ``False`` to measure over
                whatever survives tokenization.

        Returns:
            WordDistanceResult with the summed edit cost, the similarity
            normalized by :func:`_word_result`, the length coverage, and an
            optional alignment.

        Examples:
            word_distance("kæt", "kæd")   # Small (minimal pair, ~0.04)
            word_distance("kæt", "dɒɡ")   # Large (different word)
        """
        from .metric import GAP_COST

        if strict:
            self._reject_unconvertible(ipa1, ipa2)
        tokens1 = [
            t for t in self.tokenize(ipa1) if not self.is_structural_token(t)  # type: ignore[attr-defined]
        ]
        tokens2 = [
            t for t in self.tokenize(ipa2) if not self.is_structural_token(t)  # type: ignore[attr-defined]
        ]
        n, m = len(tokens1), len(tokens2)

        def raw_cost(t1: str, t2: str) -> float:
            if t1 == t2:
                return 0.0
            d = self.segment_distance(t1, t2) if weighted else 1.0
            return _substitution_cost(d, GAP_COST, GAP_COST)

        # Memoize per call: _align evaluates the cost for every DP cell (and
        # again during backtrace), so without a cache each identical token pair
        # is re-tokenized and re-composed O(n*m) times. The cost is a pure
        # function of (t1, t2), so caching is exact.
        _cost_cache: dict[tuple[str, str], float] = {}

        def cost_fn(t1: str, t2: str) -> float:
            key = (t1, t2)
            cached = _cost_cache.get(key)
            if cached is None:
                cached = raw_cost(t1, t2)
                _cost_cache[key] = cached
            return cached

        if n == 0 and m == 0:
            return _empty_pair_result(return_alignment)

        distance, alignment = self._align(
            tokens1, tokens2, cost_fn, GAP_COST, GAP_COST, return_alignment
        )
        return _word_result(n, m, distance, alignment, GAP_COST, GAP_COST)

    def word_similarity(
        self,
        ipa1: str,
        ipa2: str,
        weighted: bool = True,
        strict: bool = True,
    ) -> float:
        """Compute phonetic similarity between two IPA words.

        Returns a value from 0.0 (completely different) to 1.0 (identical):
        the alignment's cost against the cost of the null alignment, which
        deletes every token of one word and inserts every token of the
        other. See :func:`_word_result`.

        Args:
            ipa1: First IPA string
            ipa2: Second IPA string
            weighted: If True, use feature distance for substitution costs.

        Examples:
            word_similarity("kæt", "kæd")   # ~0.99 (minimal pair)
            word_similarity("kæt", "dɒɡ")   # Low (different word)
        """
        return self.word_distance(
            ipa1, ipa2, weighted=weighted, strict=strict
        ).similarity
