"""Distance calculation mixin for IPAFeatures."""

from __future__ import annotations

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
        """Compute distance between two feature dictionaries."""
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
        """Compute feature distance between two phones (0.0-1.0)."""
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
        for i, p1 in enumerate(phones):
            for j, p2 in enumerate(phones):
                if i < j:
                    d = self.distance(p1, p2)
                    matrix[i][j] = d
                    matrix[j][i] = d
        return matrix

    def word_distance(
        self,
        ipa1: str,
        ipa2: str,
        weighted: bool = True,
        return_alignment: bool = False,
    ) -> WordDistanceResult:
        """Compute phonetic edit distance between two IPA words.

        Uses Levenshtein-style dynamic programming with phonetic feature costs
        for substitutions when weighted=True.

        Args:
            ipa1: First IPA string
            ipa2: Second IPA string
            weighted: If True, use feature distance for substitution costs (0-1).
                      If False, use standard Levenshtein (cost=1 for any sub).
            return_alignment: If True, include the alignment path in result.

        Returns:
            WordDistanceResult with distance, similarity, and optional alignment.
            - distance: Total edit distance (insertions + deletions + substitutions)
            - similarity: 1 - (distance / max_len), with lower bound of 0
            - alignment: List of (phone1, phone2) pairs showing the alignment

        Examples:
            word_distance("kæt", "kæd")   # Small (minimal pair, ~0.04)
            word_distance("kæt", "dɒɡ")   # Large (different word)
        """
        # Tokenize both strings into phone segments
        tokens1 = self.tokenize_ipa(ipa1)
        tokens2 = self.tokenize_ipa(ipa2)

        n, m = len(tokens1), len(tokens2)

        # Handle edge cases
        if n == 0 and m == 0:
            return WordDistanceResult(distance=0.0, similarity=1.0, alignment=[])
        if n == 0:
            empty1: Alignment | None = (
                [(None, t) for t in tokens2] if return_alignment else None
            )
            return WordDistanceResult(
                distance=float(m), similarity=0.0, alignment=empty1
            )
        if m == 0:
            empty2: Alignment | None = (
                [(t, None) for t in tokens1] if return_alignment else None
            )
            return WordDistanceResult(
                distance=float(n), similarity=0.0, alignment=empty2
            )

        def sub_cost(t1: str, t2: str) -> float:
            """Cost of substituting t1 with t2 (0 if equal; feature-weighted or flat)."""
            if t1 == t2:
                return 0.0
            if weighted:
                return self.segment_distance(t1, t2)
            return 1.0

        # DP table: dp[i][j] = min cost to align tokens1[:i] with tokens2[:j]
        dp = [[0.0] * (m + 1) for _ in range(n + 1)]

        # Initialize base cases (insertions/deletions cost 1 each)
        for i in range(n + 1):
            dp[i][0] = float(i)
        for j in range(m + 1):
            dp[0][j] = float(j)

        # Fill DP table
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                t1, t2 = tokens1[i - 1], tokens2[j - 1]
                dp[i][j] = min(
                    dp[i - 1][j] + 1.0,  # deletion
                    dp[i][j - 1] + 1.0,  # insertion
                    dp[i - 1][j - 1] + sub_cost(t1, t2),  # substitution
                )

        distance = dp[n][m]
        max_len = max(n, m)
        similarity = max(0.0, 1.0 - (distance / max_len))

        # Backtrace for alignment if requested
        alignment: Alignment | None = None
        if return_alignment:
            alignment = []
            i, j = n, m
            while i > 0 or j > 0:
                if i > 0 and j > 0:
                    t1, t2 = tokens1[i - 1], tokens2[j - 1]
                    if dp[i][j] == dp[i - 1][j - 1] + sub_cost(t1, t2):
                        alignment.append((t1, t2))
                        i -= 1
                        j -= 1
                        continue

                if i > 0 and dp[i][j] == dp[i - 1][j] + 1.0:
                    alignment.append((tokens1[i - 1], None))
                    i -= 1
                elif j > 0:
                    alignment.append((None, tokens2[j - 1]))
                    j -= 1

            alignment.reverse()

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
