"""Distance calculation mixin for IPAFeatures."""

from __future__ import annotations

import math
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from ._base import IPAFeaturesBase
from .constants import METADATA_ATTRS

# One alignment step pairs a token from each word; None marks an insertion/deletion.
Alignment = list[tuple[str | None, str | None]]

#: What one insertion or one deletion costs: a flat price for every phone,
#: or a price read per phone.
#:
#: The flat reading is a claim, not a neutral starting point -- that every
#: phone is equally droppable -- and it is false of every language anyone
#: has counted. A schwa goes missing in English and French without anyone
#: noticing; a released final stop does not go missing in the same way, and
#: in a language with no final clusters it goes missing for different
#: reasons again. What varies by phone should be read from something that
#: states it per phone, which is the justification the feature metric
#: already rests on, applied to the other half of the alignment.
#:
#: A callable is asked for one phone and answers a non-negative finite
#: price. It is called once per token, not once per DP cell, so it may be
#: a dictionary read; it must be a pure function of the phone, because the
#: aligner reuses its answer across the whole grid.
PhoneCost = float | Callable[[str], float]


def price(cost: PhoneCost, phone: str) -> float:
    """What ``cost`` charges for ``phone``. Flat costs ignore the phone."""
    return cost(phone) if callable(cost) else cost


def _checked_price(value: float, phone: str, label: str) -> float:
    """A price the aligner can use, or a refusal naming what produced it.

    A negative price pays the dynamic program to insert material, so the
    minimum is no longer the alignment anyone asked for and the score is a
    well-formed number computed from an unbounded search. A NaN propagates
    through the ``min`` silently. Both are caller errors that produce a
    plausible float, which is the shape of defect this library refuses at
    the point of entry rather than downstream.
    """
    v = float(value)
    if not math.isfinite(v) or v < 0.0:
        raise ValueError(
            f"{label} must be a non-negative finite price; "
            f"got {value!r} for {phone!r}"
        )
    return v


def _prices(cost: PhoneCost, tokens: list[str], label: str) -> list[float]:
    """Resolve one indel cost against a token sequence, once per token."""
    return [_checked_price(price(cost, t), t, label) for t in tokens]


def cost_name(cost: PhoneCost) -> str:
    """A short identity for one indel cost, for a result to report.

    A flat cost is its own name. A :class:`CostSchedule` answers with the
    name it was given. Any other callable answers with its qualified name,
    so an unnamed lambda reports ``<lambda>`` -- which is the honest
    answer, and the reason to pass a named schedule rather than a lambda
    when the number is going anywhere a reader will see it.
    """
    if not callable(cost):
        return repr(float(cost))
    named = getattr(cost, "name", None)
    if isinstance(named, str) and named:
        return named
    return str(getattr(cost, "__qualname__", None) or repr(cost))


def costs_identity(insert_cost: PhoneCost, delete_cost: PhoneCost) -> str:
    """What parameterization a word-distance result was computed under.

    A score is a function of the universal feature space **given** a stated
    parameterization, and the parameterization is language-relative where
    the feature space is not (docs/distance.md section 10). A number that
    is comparable across neither versions nor languages, and says so
    nowhere, is the failure mode; this is what keeps it from saying so
    nowhere.
    """
    return f"insert={cost_name(insert_cost)} delete={cost_name(delete_cost)}"


@dataclass(frozen=True)
class CostSchedule:
    """A named per-phone indel cost: what a loss is worth, in one language.

    The mechanism, with no table. ``prices`` is what the caller says it
    is, ``default`` is what an unlisted phone costs, and ``name`` is what
    a :class:`WordDistanceResult` reports so a score can say what produced
    it. Nothing here is fitted, because nothing here is supplied.

    **A schedule is language-relative, and a score computed under one is
    not comparable to a score computed under another.** That is not a
    defect and it is not a retreat from the commitment in
    ``docs/design/tiers.md`` section 7 that the feature space, the
    comparison bundle and therefore ``distance`` are universal. A schedule
    is not a term in the comparison: it adds no feature, changes no
    bundle, and moves no value ``distance`` returns. It parameterizes what
    a comparison charges. The bundle stays universal; how much a loss is
    worth to you does not, and never did.

    Prices are refused at construction if negative or not finite, for the
    reason :func:`_checked_price` gives.

    Example -- a schedule that says a schwa is cheap to lose::

        CostSchedule("my-english/deletion", {"ə": 0.3}, default=1.0)
    """

    #: What the schedule is, said in one string. It travels into every
    #: result computed under it, so name it after the thing it is a
    #: schedule *for* -- the language, the corpus, the rule set -- rather
    #: than after the phone it happens to price.
    name: str
    #: Price per phone. Read by the spelling the tokenizer produces, so a
    #: key must be a unit as ``IPAFeatures.tokenize`` spells it.
    prices: Mapping[str, float]
    #: What a phone the schedule does not list costs.
    default: float

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("a CostSchedule must be named")
        checked = {
            p: _checked_price(v, p, f"CostSchedule({self.name!r})")
            for p, v in self.prices.items()
        }
        _checked_price(self.default, "<default>", f"CostSchedule({self.name!r})")
        object.__setattr__(self, "prices", MappingProxyType(checked))
        object.__setattr__(self, "default", float(self.default))

    def __call__(self, phone: str) -> float:
        return self.prices.get(phone, self.default)

    def __repr__(self) -> str:
        return (
            f"CostSchedule({self.name!r}, {len(self.prices)} priced, "
            f"default={self.default})"
        )


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

    ``costs`` is the indel parameterization the score was computed under,
    as :func:`costs_identity` spells it. It is a required field rather
    than an optional one because a caller-supplied schedule that vanishes
    from the result leaves a number nothing can say the provenance of, and
    a schedule is language-relative where the feature space is not.
    """

    edit_cost: float
    similarity: float
    coverage: float
    costs: str
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

    The two arguments are the prices of **this pair**: the deletion the
    left token would pay and the insertion the right token would pay, both
    already resolved. That is what keeps the constraint attached to the
    pair rather than to a constant once the prices vary by phone -- a
    substitution of a dear token by a cheap one is priced by the two it
    stands in for, not by whatever the inventory's average is.

    The metric answers a proportion and the aligner charges a price; this
    is the one place the first is turned into the second, so the two
    word-distance paths cannot put them on different scales.
    """
    return (insert_cost + delete_cost) * dissimilarity


def _word_result(
    tokens1: list[str],
    tokens2: list[str],
    edit_cost: float,
    alignment: Alignment | None,
    insert_cost: PhoneCost,
    delete_cost: PhoneCost,
) -> WordDistanceResult:
    """Normalize an alignment cost -- one read for both word-distance paths.

    The denominator is the cost of the null alignment, which deletes every
    token of the first word and inserts every token of the second: the sum
    of ``delete`` over ``tokens1`` plus the sum of ``insert`` over
    ``tokens2``. That path is one the DP minimizes over, so it is also the
    most any alignment can cost, and ``similarity`` spans [0, 1] with both
    ends attainable -- 1 on identity, 0 when the two words share nothing
    at any position. ``max(n, m)`` was the other reading, and it is a
    different claim: it charges a truncation once, where this charges the
    material that went missing and the material that replaced it apart.

    **It is a sum over the actual tokens and not a length times a price.**
    ``n * delete + m * insert`` is the same number whenever the price is
    flat and a different number as soon as it is not, and the version that
    multiplies would quietly charge every word its token count at whatever
    price the last caller happened to pass. The denominator has to be the
    null alignment's cost or ``similarity`` is not bounded by 1 from
    below, and the null alignment pays for the phones it actually removes.
    """
    n, m = len(tokens1), len(tokens2)
    denom = sum(_prices(delete_cost, tokens1, "delete_cost")) + sum(
        _prices(insert_cost, tokens2, "insert_cost")
    )
    similarity = 1.0 - edit_cost / denom if denom else 1.0
    return WordDistanceResult(
        edit_cost=edit_cost,
        similarity=similarity,
        coverage=(min(n, m) / max(n, m)) if max(n, m) else 1.0,
        costs=costs_identity(insert_cost, delete_cost),
        alignment=alignment,
    )


def _empty_pair_result(
    return_alignment: bool,
    insert_cost: PhoneCost = 1.0,
    delete_cost: PhoneCost = 1.0,
) -> WordDistanceResult:
    """Result for two empty token sequences: identical, zero cost.

    The costs still travel: two empty words are identical under every
    schedule, but the result says which one it was asked under, so a
    caller collecting results does not get one row that reports no
    parameterization.
    """
    return WordDistanceResult(
        edit_cost=0.0,
        similarity=1.0,
        coverage=1.0,
        costs=costs_identity(insert_cost, delete_cost),
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
        insert_cost: PhoneCost = 1.0,
        delete_cost: PhoneCost = 1.0,
        return_alignment: bool = False,
    ) -> tuple[float, Alignment | None]:
        """Weighted-Levenshtein DP shared by word_distance and DistanceModel.

        Costs are parameterized so callers choose unit indel (default) or a
        weighted/di-mode policy. Returns (distance, alignment).

        ``delete_cost`` prices the tokens of ``tokens1`` and ``insert_cost``
        the tokens of ``tokens2``, which is what makes the two sides
        distinguishable: a deletion is material the first sequence has and
        the second lacks. Each is resolved **once per token** rather than
        once per cell, so a schedule may be an arbitrary callable without
        the grid paying for it, and the base row is the running sum of the
        prices of the phones actually being removed rather than an index
        times a constant.
        """
        n, m = len(tokens1), len(tokens2)
        dels = _prices(delete_cost, tokens1, "delete_cost")
        ins = _prices(insert_cost, tokens2, "insert_cost")
        dp = [[0.0] * (m + 1) for _ in range(n + 1)]
        for i in range(1, n + 1):
            dp[i][0] = dp[i - 1][0] + dels[i - 1]
        for j in range(1, m + 1):
            dp[0][j] = dp[0][j - 1] + ins[j - 1]
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                dp[i][j] = min(
                    dp[i - 1][j] + dels[i - 1],
                    dp[i][j - 1] + ins[j - 1],
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
                if i > 0 and dp[i][j] == dp[i - 1][j] + dels[i - 1]:
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
        return self._aligned_words(
            tokens1, tokens2, weighted, return_alignment, GAP_COST, GAP_COST
        )

    def _aligned_words(
        self,
        tokens1: list[str],
        tokens2: list[str],
        weighted: bool,
        return_alignment: bool,
        insert_cost: PhoneCost,
        delete_cost: PhoneCost,
    ) -> WordDistanceResult:
        """Align two token sequences under one indel parameterization.

        The body :meth:`word_distance` and :meth:`directional_word_distance`
        share, so the symmetric entry point and the directional one cannot
        answer the same question two ways. The only thing that differs
        between them is what they pass here, and what they promise about it.
        """
        n, m = len(tokens1), len(tokens2)

        def raw_cost(t1: str, t2: str) -> float:
            if t1 == t2:
                return 0.0
            d = self.segment_distance(t1, t2) if weighted else 1.0
            # The pair's own prices: what deleting the left token and
            # supplying the right one would cost. See _substitution_cost.
            return _substitution_cost(d, price(insert_cost, t2), price(delete_cost, t1))

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
            return _empty_pair_result(return_alignment, insert_cost, delete_cost)

        distance, alignment = self._align(
            tokens1, tokens2, cost_fn, insert_cost, delete_cost, return_alignment
        )
        return _word_result(
            tokens1, tokens2, distance, alignment, insert_cost, delete_cost
        )

    def directional_word_distance(
        self,
        reference: str,
        hypothesis: str,
        *,
        insert_cost: PhoneCost | None = None,
        delete_cost: PhoneCost | None = None,
        weighted: bool = True,
        return_alignment: bool = False,
        strict: bool = True,
    ) -> WordDistanceResult:
        """Edit distance from a **reference** to a **hypothesis**, named sides.

        "Did the speaker omit something the target has" and "did the speaker
        add something the target lacks" are different questions, and a
        symmetric metric cannot express either. Here they come apart:
        ``delete_cost`` prices the phones of ``reference`` -- the material
        that went missing -- and ``insert_cost`` prices the phones of
        ``hypothesis`` -- the material that was supplied. Swap the two
        arguments and, unless the two schedules agree everywhere, you get a
        different number, which is the point. A reference and a hypothesis
        are not interchangeable, and every evaluation, scoring or diagnostic
        use has a reference.

        This is a separate entry point rather than an option on
        :meth:`word_distance` on purpose. ``word_distance``'s symmetry is
        property-tested and callers rely on it; a function that is symmetric
        on Tuesday and not on Wednesday is worse than two honest functions.

        The costs default to the flat ``GAP_COST`` both sides, under which
        this **is** :meth:`word_distance` -- a directional reading of a
        symmetric measurement, which is an honest thing to want and is what
        makes the schedule, not the entry point, the thing that introduces
        the asymmetry. Pass a :class:`CostSchedule` to say what a loss is
        worth in the language you are measuring; there is no default
        schedule and there will not be one, for the reason
        :class:`CostSchedule` gives.

        Args:
            reference: The target form. Its phones are priced by ``delete_cost``.
            hypothesis: The observed form. Its phones are priced by ``insert_cost``.
            insert_cost: Flat price, or per-phone schedule, for supplying a
                phone of ``hypothesis``. Defaults to ``GAP_COST``.
            delete_cost: Flat price, or per-phone schedule, for losing a
                phone of ``reference``. Defaults to ``GAP_COST``.
            weighted: If True, use feature distance for substitution costs.
            return_alignment: If True, include the alignment path in result.
            strict: Reject input the tokenizer cannot convert (the default).

        Returns:
            A :class:`WordDistanceResult` whose ``costs`` names the
            parameterization the score was computed under.
        """
        from .metric import GAP_COST

        if strict:
            self._reject_unconvertible(reference, hypothesis)
        tokens1 = [
            t for t in self.tokenize(reference) if not self.is_structural_token(t)  # type: ignore[attr-defined]
        ]
        tokens2 = [
            t for t in self.tokenize(hypothesis) if not self.is_structural_token(t)  # type: ignore[attr-defined]
        ]
        return self._aligned_words(
            tokens1,
            tokens2,
            weighted,
            return_alignment,
            GAP_COST if insert_cost is None else insert_cost,
            GAP_COST if delete_cost is None else delete_cost,
        )

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
