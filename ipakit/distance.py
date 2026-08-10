"""Distance calculation mixin for IPAFeatures."""

from __future__ import annotations

import math
import unicodedata
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import TYPE_CHECKING, overload

from ._base import IPAFeaturesBase
from .constants import METADATA_ATTRS

if TYPE_CHECKING:
    from .features import IPAFeatures
    from .rules import RuleSet


@dataclass(frozen=True)
class AlignmentStep:
    """One ordered operation in a pairwise comparison.

    Event references are optional because the long-standing string APIs align
    tokens, while graph-aware callers can name the canonical events those
    tokens came from.  ``terms`` is deliberately plain data so an alignment
    can cross a JSON/API boundary without importing the metric implementation.
    """

    op: str
    left: str | None
    right: str | None
    cost: float
    terms: tuple[Mapping[str, object], ...] = ()
    left_event: str | None = None
    right_event: str | None = None

    def __post_init__(self) -> None:
        if self.op not in {"match", "sub", "insert", "delete"}:
            raise ValueError(f"unknown alignment operation: {self.op!r}")

    @property
    def pair(self) -> tuple[str | None, str | None]:
        return self.left, self.right

    def to_data(self) -> dict[str, object]:
        data: dict[str, object] = {
            "op": self.op,
            "a": self.left,
            "b": self.right,
            "cost": self.cost,
            "terms": [dict(term) for term in self.terms],
        }
        if self.left_event is not None:
            data["left_event"] = self.left_event
        if self.right_event is not None:
            data["right_event"] = self.right_event
        return data


@dataclass(frozen=True)
class Alignment(Sequence[tuple[str | None, str | None]]):
    """Canonical pairwise alignment, distinct from rewrite provenance.

    Iteration and indexing retain the historical pair surface, so existing
    callers that wrote ``for left, right in result.alignment`` keep working.
    Rich operation data lives in :attr:`steps`.
    """

    steps: tuple[AlignmentStep, ...]
    edit_cost: float = 0.0
    similarity: float = 1.0
    coverage: float = 1.0
    costs: str = ""

    def __len__(self) -> int:
        return len(self.steps)

    @overload
    def __getitem__(self, index: int) -> tuple[str | None, str | None]: ...

    @overload
    def __getitem__(self, index: slice) -> list[tuple[str | None, str | None]]: ...

    def __getitem__(
        self, index: int | slice
    ) -> tuple[str | None, str | None] | list[tuple[str | None, str | None]]:
        if isinstance(index, slice):
            return [step.pair for step in self.steps[index]]
        return self.steps[index].pair

    def __iter__(self) -> Iterator[tuple[str | None, str | None]]:
        return (step.pair for step in self.steps)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Alignment):
            return (
                self.steps,
                self.edit_cost,
                self.similarity,
                self.coverage,
                self.costs,
            ) == (
                other.steps,
                other.edit_cost,
                other.similarity,
                other.coverage,
                other.costs,
            )
        if isinstance(other, list):
            return list(self) == other
        return NotImplemented

    def to_data(self) -> dict[str, object]:
        return {
            "steps": [step.to_data() for step in self.steps],
            "edit_cost": self.edit_cost,
            "similarity": self.similarity,
            "coverage": self.coverage,
            "costs": self.costs,
        }


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
            f"{label} must be a non-negative finite price; got {value!r} for {phone!r}"
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


#: The scoring vocabulary's version. Bump it when the fields of
#: :class:`ScoringParameters` change meaning, so a pinned identity from an
#: older release is recognizably not this one. It is the scoring analogue of
#: ``MATRIX_VERSION``, which versions the matrix file's shape.
SCORING_VERSION = "1.0"


@dataclass(frozen=True)
class ScoringParameters:
    """The scoring configuration a word-distance number was computed under.

    Named and versioned so a published score can say which configuration
    produced it, the way :func:`~ipakit.metric.metric_fingerprint` says which
    feature space a saved matrix means its numbers in. The fingerprint covers
    the *space*; this covers the *scoring* laid on top of it, and the two
    together name a number completely. Without it, ``docs/distance.md`` can
    only tell a caller who tuned a threshold to re-tune after an upgrade,
    because nothing pins what they tuned against; this is the object that
    sentence wanted to point at.

    The costs are stored as their :func:`cost_name` identities, not as the
    callables themselves. A callable cost cannot be compared by value across
    two processes, and a configuration that could not be compared would
    defeat the purpose: a flat cost round-trips exactly, a named schedule
    reports its name, and an unnamed lambda reports ``<lambda>`` -- the
    honest admission that it named nothing a reader could pin.

    ``threshold`` and ``max_length_ratio`` are deliberately absent. They gate
    a *verdict* (:meth:`~ipakit.distance_model.DistanceModel.is_similar`)
    without changing the score, so they are what a caller tunes *against* a
    configuration rather than part of it. Pinning the configuration is
    exactly what lets a tuned threshold be re-used instead of re-derived.

    Frozen, so it is hashable and compares by value: two models built with
    the same numbers report equal configurations, and a difference in
    ``gamma`` or either cost is a difference here.
    """

    gamma: float
    insert: str
    delete: str
    version: str = SCORING_VERSION

    @classmethod
    def of(
        cls,
        *,
        gamma: float,
        insert_cost: PhoneCost,
        delete_cost: PhoneCost,
    ) -> ScoringParameters:
        """Read a configuration off the arguments a model was built with.

        Runs the costs through :func:`cost_name` so a callable is captured by
        the identity it reports, not by object identity.
        """
        return cls(
            gamma=float(gamma),
            insert=cost_name(insert_cost),
            delete=cost_name(delete_cost),
        )

    @property
    def identity(self) -> str:
        """One line naming this configuration, version and all.

        Shares the ``insert=... delete=...`` spelling :func:`costs_identity`
        already reports in a result, with ``gamma`` and the version added, so
        a reader sees one vocabulary in both places.
        """
        return (
            f"scoring/{self.version} gamma={self.gamma!r} "
            f"insert={self.insert} delete={self.delete}"
        )


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

    @classmethod
    def from_rules(
        cls,
        ruleset: RuleSet,
        side: str,
        features: IPAFeatures,
        *,
        price: float,
        default: float,
        name: str | None = None,
    ) -> CostSchedule:
        """Read which phones a rule set deletes, or inserts, and price those.

        **Which phones** is derived; **what they cost** is the caller's, and
        both arguments are required. That split is the whole design. A
        hand-maintained per-language list of droppable phones is the pattern
        this repository refuses -- it is a second copy of something already
        declared, and it goes stale in silence -- while a schedule read off
        a rule set regenerates, is checkable against the file, and moves
        when the file moves. Prices, on the other hand, are not stated
        anywhere in the data and cannot be derived from it; inventing them
        here would be a fitted table.

        **Scope, stated plainly: a schedule built this way is a claim about
        the rule set, not about the language.** ``french-liaison`` deletes
        the latent final consonants and the schwa because those are the
        phenomena that file was written to state, and a French speaker
        drops other things it says nothing about. That is a true and narrow
        claim, which is the only kind available; read it as "the phones
        this cascade removes are cheaper to lose than the ones it does
        not", and name the schedule after the rule set so the result says
        so too.

        ``side`` is ``"delete"`` -- the phones some rule rewrites to zero,
        resolved by matching each deleting rule's target against the
        inventory, so a rule written over a natural class contributes every
        phone in it -- or ``"insert"``, the phones some rule writes where
        there was nothing.

        A rule set that states none of the requested side is refused rather
        than answered with a schedule that prices nothing. Such a schedule
        is a flat price wearing a name, it would report a name in every
        result computed under it, and nothing downstream could tell it from
        a schedule that was doing something.
        """
        from .form import units

        if side not in ("delete", "insert"):
            raise ValueError(f"side must be 'delete' or 'insert', got {side!r}")
        # Built once, and only where a target has to be matched against it.
        inventory = (
            [(p, units(p, features)) for p in features.phones]
            if side == "delete"
            else []
        )
        named: set[str] = set()
        for rule in ruleset.rules:
            if side == "delete" and rule.deletes and rule.target is not None:
                named.update(
                    p
                    for p, u in inventory
                    if len(u) == 1 and rule.target.matches(u[0], features)
                )
            elif side == "insert" and rule.inserts and isinstance(rule.becomes, str):
                named.update(
                    t
                    for t in features.tokenize(rule.becomes)
                    if not features.is_structural_token(t)
                )
        if not named:
            raise ValueError(
                f"rule set {ruleset.name!r} states no {side}s, so a schedule "
                f"read off it would price every phone at {default!r} while "
                "reporting a name. Read the other side, or write the "
                "schedule directly."
            )
        return cls(
            name or f"{ruleset.name}/{side}",
            dict.fromkeys(sorted(named), price),
            default,
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
    result = WordDistanceResult(
        edit_cost=edit_cost,
        similarity=similarity,
        coverage=(min(n, m) / max(n, m)) if max(n, m) else 1.0,
        costs=costs_identity(insert_cost, delete_cost),
        alignment=None,
    )
    if alignment is not None:
        result.alignment = replace(
            alignment,
            edit_cost=edit_cost,
            similarity=similarity,
            coverage=result.coverage,
            costs=result.costs,
        )
    return result


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
        alignment=(
            Alignment((), 0.0, 1.0, 1.0, costs_identity(insert_cost, delete_cost))
            if return_alignment
            else None
        ),
    )


@dataclass(frozen=True)
class PronunciationMatch:
    """The nearest acceptable pronunciation in a set, and which pair won.

    Answers "is this an acceptable pronunciation of the word?" -- the best
    match over a set of acceptable variants (``iːðɚ``/``aɪðɚ``, a homograph's
    two readings, a regional vowel). ``similarity`` is that best, ``form`` and
    ``accepted`` are the two members that produced it, and ``result`` is the
    full winning comparison.

    It is the wrong tool for "how far is this word from that word." A maximum
    over variants makes the answer depend on how many each side happens to
    list, which is a property of the lexicon and not of the pair -- a word
    with more listed variants would look closer for no phonetic reason. Use
    :meth:`DistanceMixin.word_distance` for the symmetric pairwise question,
    which is why that one is named for distance and this one for acceptability.
    """

    similarity: float
    form: str
    accepted: str
    result: WordDistanceResult


@dataclass(frozen=True)
class SequenceMatch:
    """The best-matching candidate for an observed phone sequence, and its score.

    Like :class:`PronunciationMatch`, but over pre-tokenized phone sequences
    (each element one phone unit) rather than IPA strings, so the caller's
    phone boundaries are authoritative and nothing is re-tokenized. ``observed``
    and ``candidate`` are the two token tuples that produced ``similarity``;
    ``result`` is the full comparison.
    """

    similarity: float
    observed: tuple[str, ...]
    candidate: tuple[str, ...]
    result: WordDistanceResult


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
            units = self.read(arg).segments
            if len(units) > 1:
                raise ValueError(
                    f"distance() compares single units; {arg!r} is "
                    f"{len(units)} units. Use word_distance() for words, "
                    "or segment_distance() for segment strings."
                )
        try:
            (s1,) = self.read(phone1).segments
            (s2,) = self.read(phone2).segments
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

        t1 = self.read(seg1).segments
        t2 = self.read(seg2).segments
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
        term_fn: Callable[[str, str], tuple[Mapping[str, object], ...]] | None = None,
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
            aligned_steps: list[AlignmentStep] = []
            i, j = n, m
            while i > 0 or j > 0:
                if (
                    i > 0
                    and j > 0
                    and dp[i][j]
                    == dp[i - 1][j - 1] + sub_cost(tokens1[i - 1], tokens2[j - 1])
                ):
                    left, right = tokens1[i - 1], tokens2[j - 1]
                    step_cost = sub_cost(left, right)
                    aligned_steps.append(
                        AlignmentStep(
                            "match" if left == right else "sub",
                            left,
                            right,
                            step_cost,
                            (
                                ()
                                if left == right or term_fn is None
                                else term_fn(left, right)
                            ),
                        )
                    )
                    i -= 1
                    j -= 1
                    continue
                if i > 0 and dp[i][j] == dp[i - 1][j] + dels[i - 1]:
                    aligned_steps.append(
                        AlignmentStep("delete", tokens1[i - 1], None, dels[i - 1])
                    )
                    i -= 1
                elif j > 0:
                    aligned_steps.append(
                        AlignmentStep("insert", None, tokens2[j - 1], ins[j - 1])
                    )
                    j -= 1
            aligned_steps.reverse()
            alignment = Alignment(tuple(aligned_steps))

        return dp[n][m], alignment

    def _reject_unconvertible(self, *texts: str) -> None:
        """Raise if any text contains symbols the tokenizer would drop.

        Conversion may reasonably be lossy; measurement may not. Silently
        dropping a symbol turns "these words differ" into a plausible
        number computed from truncated input.
        """
        for text in texts:
            self.read(text, strict=True)

    def _word_units(self, text: str) -> list[str]:
        """The units a word aligns over: one per segment, each with its prosody
        (stress, tone, length) bound to it, so a prosodic mark rides on the
        unit it scopes rather than floating as its own token. Boundaries are
        dropped -- transparent to distance. Identical to the former glyph
        tokenization for any word carrying no prosodic mark."""
        return [s.to_ipa() for s in self.read(text).segments]

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

        **Symmetric, and it takes no cost schedule so that it stays that
        way.** ``d(x, y) == d(y, x)`` is property-tested here and callers
        rely on it; per-phone prices are what would break it, so they live
        on :meth:`directional_word_distance`, which names its reference
        side and promises nothing about symmetry.

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
        tokens1 = self._word_units(ipa1)
        tokens2 = self._word_units(ipa2)
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
        mode: str = "global",
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

        def term_fn(t1: str, t2: str) -> tuple[Mapping[str, object], ...]:
            if not weighted or t1 == t2:
                return ()
            from .metric import segment_terms

            s1, s2 = self.segment(t1), self.segment(t2)  # type: ignore[attr-defined]
            return tuple(
                {"label": label, "a": a, "b": b, "cost": round(cost, 4)}
                for label, a, b, cost in segment_terms(self, s1, s2)  # type: ignore[arg-type]
            )

        if n == 0 and m == 0:
            return _empty_pair_result(return_alignment, insert_cost, delete_cost)

        if mode == "local":
            return self._fit_result(tokens1, tokens2, cost_fn, insert_cost, delete_cost)

        distance, alignment = self._align(
            tokens1,
            tokens2,
            cost_fn,
            insert_cost,
            delete_cost,
            return_alignment,
            term_fn,
        )
        return _word_result(
            tokens1, tokens2, distance, alignment, insert_cost, delete_cost
        )

    def _fit_result(
        self,
        haystack: list[str],
        needle: list[str],
        cost_fn: Callable[[str, str], float],
        insert_cost: PhoneCost,
        delete_cost: PhoneCost,
    ) -> WordDistanceResult:
        """Semi-global FIT: ``needle`` must align fully, but leading and
        trailing material on the ``haystack`` side is free, so a target
        embedded in a longer, noisier sequence is scored on how well it is
        realized rather than penalized for the surrounding tokens. The needle
        is not free-ended, so a truncated target is still penalized. The score
        is normalized by the needle's own insertion cost -- the cost of the
        needle matching nothing -- so it reads as "how much of the needle is
        present". Directional by construction: the two sides are not
        interchangeable, which is why this is not offered on the symmetric
        :meth:`word_distance`.
        """
        n, m = len(haystack), len(needle)
        ins = _prices(insert_cost, needle, "insert_cost")
        dels = _prices(delete_cost, haystack, "delete_cost")
        denom = sum(ins)
        if m == 0:
            similarity = 1.0
            best = 0.0
        else:
            dp = [[0.0] * (m + 1) for _ in range(n + 1)]
            for j in range(1, m + 1):
                dp[0][j] = dp[0][j - 1] + ins[j - 1]
            for i in range(1, n + 1):
                dp[i][0] = 0.0  # free leading gap on the haystack
                hi = haystack[i - 1]
                for j in range(1, m + 1):
                    dp[i][j] = min(
                        dp[i - 1][j] + dels[i - 1],
                        dp[i][j - 1] + ins[j - 1],
                        dp[i - 1][j - 1] + cost_fn(hi, needle[j - 1]),
                    )
            best = min(dp[i][m] for i in range(n + 1))  # free trailing gap
            similarity = max(0.0, 1.0 - best / denom) if denom else 1.0
        coverage = m / max(n, m) if max(n, m) else 1.0
        return WordDistanceResult(
            edit_cost=best,
            similarity=similarity,
            coverage=coverage,
            costs=costs_identity(insert_cost, delete_cost),
            alignment=None,
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
        tokens1 = self._word_units(reference)
        tokens2 = self._word_units(hypothesis)
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

    def explain_word_distance(
        self,
        ipa1: str,
        ipa2: str,
        *,
        weighted: bool = True,
        strict: bool = True,
    ) -> list[dict[str, object]]:
        """A per-position trace of a word comparison, for debugging and detail.

        One step per aligned position of the two words' units, in order:
        ``op`` is ``match``/``sub``/``insert``/``delete``, ``a``/``b`` are the
        units (one is ``None`` for a gap), ``cost`` is that position's
        contribution, and for a substitution ``terms`` lists the
        ``(label, a, b, cost)`` rows behind it -- each comparable feature, the
        tract coordinates, and every prosodic rider (stress, tone, length). The
        mean of the position costs over ``max(len)`` is the word distance.
        """
        result = self.word_distance(
            ipa1, ipa2, weighted=weighted, return_alignment=True, strict=strict
        )
        explained = []
        for step in result.alignment.steps if result.alignment else ():
            # ``AlignmentStep.cost`` is the price paid by the edit DP.  The
            # public explanation predates priced substitutions and reports
            # the segment metric itself; keep those two currencies distinct.
            metric_cost = (
                self.segment_distance(step.left, step.right)
                if step.op == "sub" and step.left is not None and step.right is not None
                else step.cost
            )
            explained.append({**step.to_data(), "cost": round(metric_cost, 4)})
        return explained

    def nearest_pronunciation(
        self,
        forms: str | Iterable[str],
        acceptable: str | Iterable[str],
        weighted: bool = True,
        strict: bool = True,
        *,
        mode: str = "global",
    ) -> PronunciationMatch:
        """The best match between an observed form and a set of acceptable ones.

        ``forms`` is what was said -- one string, or several if the
        observation itself has variants -- and ``acceptable`` is the set a
        lexicon lists for the word: free variants (``iːðɚ``/``aɪðɚ``, the flap
        or not), or a homograph's readings (``record`` the noun ``ˈɹɛkɚd`` and
        the verb ``ɹɪˈkɔɹd``, ``wind`` the breeze ``wɪnd`` and the turn
        ``waɪnd``). Returns the nearest pair by :meth:`word_similarity`, and
        *which* pair: a caller learns their form matched the ``aɪ`` variant,
        not only how close it was.

        The maximum is over the full cross product, and the earliest listed
        member breaks a tie, so the answer does not depend on iteration order.
        This is the acceptability question, not distance -- see
        :class:`PronunciationMatch` for why a maximum over variants must not be
        read as a distance between two words.
        """
        return self.rank_pronunciations(
            forms, acceptable, n=1, weighted=weighted, strict=strict, mode=mode
        )[0]

    def sequence_distance(
        self,
        seq1: Sequence[str],
        seq2: Sequence[str],
        *,
        weighted: bool = True,
        mode: str = "global",
        return_alignment: bool = False,
    ) -> WordDistanceResult:
        """Distance between two **pre-tokenized** phone sequences.

        Each element of ``seq1``/``seq2`` is one phone unit (possibly
        multi-character, like ``d͡ʒ`` or ``o͡ʊ``). The sequences are aligned
        exactly as given -- unlike :meth:`word_distance`, which tokenizes a
        string and so may join or split units -- so a caller who already has
        phone tokens keeps their boundaries.

        ``mode="global"`` is the symmetric whole-sequence alignment;
        ``mode="local"`` is a fit in which ``seq2`` is the target that must
        align fully and ``seq1``'s ends are free, for a target embedded in a
        longer, noisier sequence (see :meth:`_fit_result`).
        """
        from .metric import GAP_COST

        return self._aligned_words(
            list(seq1),
            list(seq2),
            weighted,
            return_alignment,
            GAP_COST,
            GAP_COST,
            mode,
        )

    def sequence_similarity(
        self,
        seq1: Sequence[str],
        seq2: Sequence[str],
        *,
        weighted: bool = True,
        mode: str = "global",
    ) -> float:
        """The ``similarity`` of :meth:`sequence_distance`, in [0, 1]."""
        return self.sequence_distance(
            seq1, seq2, weighted=weighted, mode=mode
        ).similarity

    def rank_sequences(
        self,
        observed: Sequence[str],
        candidates: Iterable[Sequence[str]],
        *,
        n: int | None = None,
        weighted: bool = True,
        mode: str = "global",
    ) -> list[SequenceMatch]:
        """Candidate phone sequences ranked by similarity to ``observed``.

        Best first; a tie keeps the earliest-listed candidate, so the ranking
        is deterministic. ``n`` truncates to the n-best. ``mode="local"`` fits
        each candidate as the target inside ``observed`` (see
        :meth:`sequence_distance`). No lexicon is involved -- the candidates
        are simply the phone sequences the caller supplies.
        """
        obs = list(observed)
        cands = [list(c) for c in candidates]
        if not cands:
            raise ValueError("rank_sequences needs at least one candidate")
        scored = [
            SequenceMatch(
                similarity=(
                    r := self.sequence_distance(obs, c, weighted=weighted, mode=mode)
                ).similarity,
                observed=tuple(obs),
                candidate=tuple(c),
                result=r,
            )
            for c in cands
        ]
        scored.sort(key=lambda x: -x.similarity)
        return scored if n is None else scored[:n]

    def _score_pronunciation(
        self, form: str, candidate: str, weighted: bool, strict: bool, mode: str
    ) -> WordDistanceResult:
        if mode == "global":
            return self.word_distance(form, candidate, weighted=weighted, strict=strict)
        t1 = self._word_units(form)
        t2 = self._word_units(candidate)
        return self.sequence_distance(t1, t2, weighted=weighted, mode=mode)

    def rank_pronunciations(
        self,
        forms: str | Iterable[str],
        acceptable: str | Iterable[str],
        *,
        n: int | None = None,
        weighted: bool = True,
        strict: bool = True,
        mode: str = "global",
    ) -> list[PronunciationMatch]:
        """:meth:`nearest_pronunciation`, but the whole ranking, best first.

        The n-best acceptable pronunciations for the observed form(s), each a
        :class:`PronunciationMatch`; ``n`` truncates. ``mode="local"`` matches
        each acceptable pronunciation as a target embedded in the form. A tie
        keeps the earliest-listed, so the order is deterministic.
        """
        fs = [forms] if isinstance(forms, str) else list(forms)
        accs = [acceptable] if isinstance(acceptable, str) else list(acceptable)
        if not fs or not accs:
            raise ValueError(
                "rank_pronunciations needs at least one form and one "
                "acceptable pronunciation"
            )
        scored = [
            PronunciationMatch(
                similarity=(
                    r := self._score_pronunciation(form, cand, weighted, strict, mode)
                ).similarity,
                form=form,
                accepted=cand,
                result=r,
            )
            for form in fs
            for cand in accs
        ]
        scored.sort(key=lambda x: -x.similarity)
        return scored if n is None else scored[:n]
