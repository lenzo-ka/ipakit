"""Distance calculation mixin for IPAFeatures."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ._base import IPAFeaturesBase
from .constants import METADATA_ATTRS

# One alignment step pairs a token from each word; None marks an insertion/deletion.
Alignment = list[tuple[str | None, str | None]]


@dataclass
class WordDistanceResult:
    """Result of word distance calculation."""

    distance: float
    similarity: float
    alignment: Alignment | None = None


class DistanceMixin(IPAFeaturesBase):
    """Mixin providing phonetic distance calculations."""

    def _feature_dict_distance(self, f1: dict[str, str], f2: dict[str, str]) -> float:
        """Compute distance between two feature dictionaries.

        Returns the sentinel ``1.0`` (maximally different) when the two dicts
        share no non-metadata feature keys -- there is nothing to compare on.
        """
        all_keys = (set(f1) | set(f2)) - METADATA_ATTRS
        if not all_keys:
            return 1.0
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
        """Compute feature distance between two phones (0.0-1.0).

        An unknown phone (no features) yields the sentinel ``1.0`` (maximally
        different). Note the package uses several "not found" idioms:
        ``get_features`` returns ``{}``, ``get_phone`` returns ``None``, and
        ``DistanceModel.confusability`` returns ``0.0`` for out-of-inventory
        phones.
        """
        f1 = self.get_features(phone1, with_defaults=True)
        f2 = self.get_features(phone2, with_defaults=True)
        if not f1 or not f2:
            return 1.0
        return self._feature_dict_distance(f1, f2)

    def segment_distance(self, seg1: str, seg2: str) -> float:
        """Compute distance between two segments (potentially multi-phone)."""
        f1, f2 = self.compose(seg1), self.compose(seg2)
        if not f1 or not f2:
            return 1.0
        if len(f1) == 1 and len(f2) == 1:
            return self._feature_dict_distance(f1[0], f2[0])

        len_penalty = abs(len(f1) - len(f2)) / max(len(f1), len(f2))
        max_len = max(len(f1), len(f2))
        total = sum(
            (
                self._feature_dict_distance(f1[i], f2[i])
                if i < len(f1) and i < len(f2)
                else 1.0
            )
            for i in range(max_len)
        )
        return (total / max_len + len_penalty) / 2

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

    def word_distance(
        self,
        ipa1: str,
        ipa2: str,
        weighted: bool = True,
        return_alignment: bool = False,
        sub_cost: Callable[[str, str], float] | None = None,
    ) -> WordDistanceResult:
        """Compute phonetic edit distance between two IPA words.

        Uses Levenshtein-style dynamic programming with phonetic feature costs
        for substitutions when weighted=True. Pass ``sub_cost`` to inject a
        custom substitution policy (used by DistanceModel); otherwise the
        default feature-distance policy applies.

        Args:
            ipa1: First IPA string
            ipa2: Second IPA string
            weighted: If True, use feature distance for substitution costs (0-1).
                      If False, use standard Levenshtein (cost=1 for any sub).
            return_alignment: If True, include the alignment path in result.
            sub_cost: Optional substitution-cost callable overriding ``weighted``.

        Returns:
            WordDistanceResult with distance, similarity (1 - distance/max_len,
            floored at 0), and optional alignment.

        Examples:
            word_distance("kæt", "kæd")   # Small (minimal pair, ~0.04)
            word_distance("kæt", "dɒɡ")   # Large (different word)
        """
        tokens1 = self.tokenize_ipa(ipa1)
        tokens2 = self.tokenize_ipa(ipa2)
        n, m = len(tokens1), len(tokens2)

        if sub_cost is None:

            def _default_sub(t1: str, t2: str) -> float:
                if t1 == t2:
                    return 0.0
                return self.segment_distance(t1, t2) if weighted else 1.0

            raw_cost: Callable[[str, str], float] = _default_sub
        else:
            raw_cost = sub_cost

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
            return WordDistanceResult(
                distance=0.0,
                similarity=1.0,
                alignment=[] if return_alignment else None,
            )

        distance, alignment = self._align(
            tokens1, tokens2, cost_fn, return_alignment=return_alignment
        )
        max_len = max(n, m)
        similarity = max(0.0, 1.0 - (distance / max_len))
        return WordDistanceResult(
            distance=distance, similarity=similarity, alignment=alignment
        )

    def word_similarity(
        self,
        ipa1: str,
        ipa2: str,
        weighted: bool = True,
    ) -> float:
        """Compute phonetic similarity between two IPA words.

        Returns a value from 0.0 (completely different) to 1.0 (identical).
        Similarity = 1 - (edit_distance / max_length), with lower bound of 0.

        Args:
            ipa1: First IPA string
            ipa2: Second IPA string
            weighted: If True, use feature distance for substitution costs.

        Examples:
            word_similarity("kæt", "kæd")   # ~0.99 (minimal pair)
            word_similarity("kæt", "dɒɡ")   # Low (different word)
        """
        return self.word_distance(ipa1, ipa2, weighted=weighted).similarity
