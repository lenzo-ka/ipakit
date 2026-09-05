"""Relate one phoneset to another: nearest-neighbor, and one-to-one.

Two operations, and they answer different questions. Asking for "the
mapping" between two phonesets is ambiguous between them, so both are
named rather than one being the default.

``nearest_mapping`` is DIRECTIONAL and MANY-TO-ONE. Every source phone
gets the closest target phone, whether or not the target set holds
anything like it. Several sources may land on one target, and that is
not a defect -- it is the answer to "what does this target set do to my
distinctions", which is usually why the question was asked. Mapping A
onto B and B onto A give different results, so the direction is part of
the request and never inferred.

``one_to_one_mapping`` is a MATCHING. Each phone is used at most once, and
the pairing chosen is the one minimizing TOTAL distance over the whole
set -- not the one you get by taking each phone's nearest in turn.
**Greedy nearest-first is not optimal and the difference is silent**: a
phone that grabs its favourite target can force a later phone onto a much
worse one, and the total is worse than a pairing where the first phone
settles for second best. Nothing in the output would show it, which is
why this solves the assignment problem properly instead. Where the sets
differ in size, the surplus phones on the larger side are unmatched
rather than being forced onto a partner.

Neither operation invents a threshold. Pass ``max_distance`` to refuse a
correspondence past some distance, and the phone is reported unmapped
instead of silently paired with whatever happened to be least bad.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from .models import Phoneset

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from .features import IPAFeatures
    from .inventories import Inventory, Style

__all__ = [
    "Correspondence",
    "PhonesetMapping",
    "nearest_mapping",
    "read_inventory_entry",
    "tie_delimited_entry",
    "one_to_one_mapping",
]


@dataclass(frozen=True)
class Correspondence:
    """One source phone and what it was paired with, if anything."""

    source: str
    target: str | None
    distance: float | None
    #: Other targets at exactly the same distance as ``target``. A tie is
    #: reported rather than resolved by sort order, because which of two
    #: equidistant targets is "the" answer is not a fact this library
    #: holds -- an order is declared or it does not exist.
    ties: tuple[str, ...] = ()
    source_spelling: str | None = None
    target_spelling: str | None = None
    reason: str | None = None

    @property
    def mapped(self) -> bool:
        """Whether this source phone found a partner."""
        return self.target is not None


@dataclass(frozen=True)
class PhonesetMapping:
    """The result of relating two phonesets, with what it cost."""

    source: Phoneset
    target: Phoneset
    #: ``"nearest"`` or ``"one-to-one"``. Carried because the two answer
    #: different questions and a bare table of pairs does not say which.
    kind: str
    correspondences: tuple[Correspondence, ...]
    source_inventory: Inventory | None = None
    target_inventory: Inventory | None = None
    source_style: Style | None = field(default=None, repr=False, compare=False)
    target_style: Style | None = field(default=None, repr=False, compare=False)

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.correspondences)

    def __len__(self) -> int:
        return len(self.correspondences)

    @property
    def mapped(self) -> tuple[Correspondence, ...]:
        """Correspondences that found a partner."""
        return tuple(c for c in self.correspondences if c.mapped)

    @property
    def unmapped(self) -> tuple[str, ...]:
        """Source phones with no partner, in source order."""
        return tuple(c.source for c in self.correspondences if not c.mapped)

    @property
    def unused_targets(self) -> tuple[str, ...]:
        """Target phones nothing was mapped onto, in target order."""
        taken = {c.target for c in self.correspondences if c.target is not None}
        return tuple(p for p in self.target.phones if p not in taken)

    @property
    def total_distance(self) -> float:
        """Summed distance over mapped correspondences."""
        return sum(c.distance or 0.0 for c in self.mapped)

    @property
    def exact(self) -> tuple[Correspondence, ...]:
        """Correspondences at distance zero -- the phone survived the move."""
        return tuple(c for c in self.mapped if c.distance == 0.0)

    @property
    def collapses(self) -> dict[str, tuple[str, ...]]:
        """Targets that more than one source landed on, and which sources.

        This is the part worth reading. A many-to-one mapping merges
        distinctions, and each entry here is a contrast the source set
        drew that the target set cannot: after the mapping, those source
        phones are indistinguishable. Empty for a one-to-one mapping by
        construction.
        """
        onto: dict[str, list[str]] = {}
        for correspondence in self.correspondences:
            if correspondence.target is not None:
                onto.setdefault(correspondence.target, []).append(correspondence.source)
        return {
            target: tuple(sources)
            for target, sources in onto.items()
            if len(sources) > 1
        }

    @property
    def ambiguous(self) -> tuple[Correspondence, ...]:
        """Correspondences where some other target was equally close."""
        return tuple(c for c in self.correspondences if c.ties)


def _as_phoneset(value: Phoneset | Iterable[str], name: str) -> Phoneset:
    """Accept a Phoneset or any iterable of phone strings."""
    if isinstance(value, Phoneset):
        return value
    return Phoneset.from_list(list(value), name=name)


def _features(ipa: IPAFeatures | None) -> IPAFeatures:
    if ipa is not None:
        return ipa
    from . import _get_ipa

    return _get_ipa()


def tie_delimited_entry(phone: str, ipa: IPAFeatures) -> str:
    """Supply the ties a delimited inventory entry left out.

    NOT a wild read, and that decides where it may be applied. ``g`` is
    not IPA and ``from_wild`` repairs it; ``t͜s`` and ``t͡s`` are one
    phone under two tie conventions and ``from_wild`` canonicalizes
    between them. ``aɪ`` is neither -- well-formed IPA meaning a SEQUENCE
    of two vowels, against ``a͜ɪ`` meaning ONE diphthong. Both are
    legitimate and denote different things, so nothing in the text
    licenses a rewrite.

    THE DELIMITER LICENSES IT: one phone per line, so a line parsing to
    more than one segment is missing its ties. Which is also why this is
    opt-in -- it trusts the file's claim, and a file that holds
    orthography rather than phones makes that claim falsely.

    WHICH TIE is :meth:`IPAFeatures.add_ties`, not a rule kept here: the
    over-tie claims simultaneity, so only consonant to consonant takes
    it, and everything else binds sequentially. One rule, one place.

    An entry already readable as one phone is returned byte-identical,
    whatever convention it used, and a base carrying modifiers (``tʰ``,
    ``ˈʌ``, ``aː``) is one segment and is left alone.
    """
    if len(ipa.segments(phone)) <= 1:
        return phone
    tied = ipa.add_ties(phone)
    return tied if len(ipa.segments(tied)) == 1 else phone


def read_inventory_entry(
    phone: str, ipa: IPAFeatures, *, wild: bool = False, tie: bool = True
) -> tuple[str, list[tuple[str, str, str]]]:
    """One inventory entry in house style, and what it took to get there.

    Returns the entry and the steps that changed it, each as
    ``(kind, before, after)`` with ``kind`` either ``"wild"`` or
    ``"tied"``. Callers report those however suits them -- a line per
    change while streaming, or a tally at the end -- which is why this
    returns them rather than printing: two commands wanted the same
    reading and different reporting, and writing it twice is how the two
    readings drift apart.

    The two steps are not the same kind of act. ``wild`` repairs text
    that is not house-style IPA, and is off by default because a valid
    tied construction must not be silently rewritten. ``tie`` supplies
    the ties a delimited entry left out, which the file's one-phone-per-
    line claim licenses -- see :func:`tie_delimited_entry`.

    An entry that still will not read as one phone is returned as it
    stands, with the steps that were tried, for the caller to refuse.
    """
    steps: list[tuple[str, str, str]] = []
    house = phone
    if wild:
        canonical = ipa.from_wild(house)
        if canonical != house:
            steps.append(("wild", house, canonical))
            house = canonical
    if tie:
        tied = tie_delimited_entry(house, ipa)
        if tied != house:
            steps.append(("tied", house, tied))
            house = tied
    return house, steps


def _tied(phoneset: Phoneset, ipa: IPAFeatures) -> Phoneset:
    """Every entry read as one phone, changing only what needs it."""
    return Phoneset.from_list(
        [tie_delimited_entry(p, ipa) for p in phoneset.phones], name=phoneset.name
    )


def _prepare(
    source: Phoneset | Iterable[str],
    target: Phoneset | Iterable[str],
    ipa: IPAFeatures | None,
    tied: bool,
) -> tuple[IPAFeatures, Phoneset, Phoneset]:
    """Resolve both sides the same way, whichever operation asked.

    Shared so the two cannot drift: reading an entry differently on the
    nearest path than on the matching path would make their results
    incomparable for a reason nothing in the output would show.
    """
    features = _features(ipa)
    left = _as_phoneset(source, "source")
    right = _as_phoneset(target, "target")
    if tied:
        left, right = _tied(left, features), _tied(right, features)
    return features, left, right


def _unmapped(phone: str) -> Correspondence:
    """A source phone that found no partner."""
    return Correspondence(phone, None, None)


def _styled(
    result: PhonesetMapping,
    source_style: Style | None,
    target_style: Style | None,
) -> PhonesetMapping:
    """Attach spellings where an operation was given notation styles."""

    def spell(style: Style | None, phone: str | None) -> str | None:
        if style is None or phone is None:
            return None
        try:
            return style.spell(phone)
        except ValueError:
            return None

    return replace(
        result,
        correspondences=tuple(
            replace(
                item,
                source_spelling=spell(source_style, item.source),
                target_spelling=spell(target_style, item.target),
            )
            for item in result
        ),
        source_style=source_style,
        target_style=target_style,
    )


def _refused(cost: float, max_distance: float | None) -> bool:
    """Whether a pairing at this cost is declined.

    Two reasons, one test: an unreadable entry costs infinity, and a
    caller's threshold rejects anything past it. Both mean unmapped, and
    keeping them together is what stops one path checking only one.
    """
    return cost == float("inf") or (max_distance is not None and cost > max_distance)


def _cost_rows(
    source: Phoneset, target: Phoneset, ipa: IPAFeatures
) -> list[list[float]]:
    """Distance from every source phone to every target phone.

    Computed once and reused: both operations need the whole matrix, and
    the metric is the expensive part.
    """

    def cost(a: str, b: str) -> float:
        """Distance, or infinity where an entry cannot be read as one phone.

        Reported as unmapped rather than raised: one unreadable line in a
        phoneset should not deny an answer about the other forty.
        """
        try:
            return ipa.distance(a, b)
        except ValueError:
            return float("inf")

    return [[cost(a, b) for b in target.phones] for a in source.phones]


def nearest_mapping(
    source: Phoneset | Iterable[str],
    target: Phoneset | Iterable[str],
    *,
    ipa: IPAFeatures | None = None,
    max_distance: float | None = None,
    tied: bool = False,
    source_style: Style | None = None,
    target_style: Style | None = None,
) -> PhonesetMapping:
    """Map each source phone onto its closest target phone.

    Directional and many-to-one: several source phones may land on the
    same target, which is how the mapping reports a distinction the
    target set does not carry. See :attr:`PhonesetMapping.collapses`.

    Args:
        source: the phones being mapped, as a Phoneset or any iterable
        target: the phones being mapped onto
        ipa: feature system to measure with; the shipped one by default
        max_distance: refuse a pairing past this distance and report the
            source phone unmapped, rather than pairing it with whatever
            was least bad

    Examples:
        >>> m = nearest_mapping(["p", "b"], ["t", "d"])
        >>> [(c.source, c.target) for c in m]
        [('p', 't'), ('b', 'd')]
    """
    features, left, right = _prepare(source, target, ipa, tied)
    if not left.phones or not right.phones:
        return _styled(
            PhonesetMapping(left, right, "nearest", tuple(_unmapped(p) for p in left)),
            source_style,
            target_style,
        )

    rows = _cost_rows(left, right, features)
    found: list[Correspondence] = []
    for phone, row in zip(left.phones, rows, strict=True):
        best = min(row)
        if _refused(best, max_distance):
            found.append(_unmapped(phone))
            continue
        at = [right.phones[i] for i, value in enumerate(row) if value == best]
        found.append(Correspondence(phone, at[0], best, tuple(at[1:])))
    return _styled(
        PhonesetMapping(left, right, "nearest", tuple(found)),
        source_style,
        target_style,
    )


def _assign(rows: Sequence[Sequence[float]], n_targets: int) -> list[int | None]:
    """Minimum-total-cost one-to-one assignment, by the Hungarian method.

    Returns, for each row, the column it is assigned to, or None where the
    row is left unassigned because there were more rows than columns.

    This is O(n^3) and phonesets are tens to low hundreds of phones, so
    the cost is not worth avoiding -- and the greedy alternative gives a
    different, worse answer without saying so.
    """
    n_rows = len(rows)
    size = max(n_rows, n_targets)
    # Square the matrix with zero-cost padding. Padding is what makes the
    # surplus rows come back unassigned rather than distorting the pairing
    # the real rows get.
    cost = [
        [rows[r][c] if r < n_rows and c < n_targets else 0.0 for c in range(size)]
        for r in range(size)
    ]

    # Jonker-Volgenant style shortest augmenting path, one row at a time.
    INF = float("inf")
    u = [0.0] * (size + 1)
    v = [0.0] * (size + 1)
    p = [0] * (size + 1)
    way = [0] * (size + 1)
    for i in range(1, size + 1):
        p[0] = i
        j0 = 0
        minv = [INF] * (size + 1)
        used = [False] * (size + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = INF
            j1 = 0
            for j in range(1, size + 1):
                if used[j]:
                    continue
                cur = cost[i0 - 1][j - 1] - u[i0] - v[j]
                if cur < minv[j]:
                    minv[j] = cur
                    way[j] = j0
                if minv[j] < delta:
                    delta = minv[j]
                    j1 = j
            for j in range(size + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1

    assignment: list[int | None] = [None] * n_rows
    for j in range(1, size + 1):
        row = p[j] - 1
        col = j - 1
        if row < n_rows and col < n_targets:
            assignment[row] = col
    return assignment


def one_to_one_mapping(
    source: Phoneset | Iterable[str],
    target: Phoneset | Iterable[str],
    *,
    ipa: IPAFeatures | None = None,
    max_distance: float | None = None,
    tied: bool = False,
    source_style: Style | None = None,
    target_style: Style | None = None,
) -> PhonesetMapping:
    """Pair the phonesets one-to-one, minimizing total distance.

    Each phone is used at most once. The pairing is the one with the
    smallest summed distance over the whole set, which is NOT what taking
    each phone's nearest in turn produces: a greedy pass lets an early
    phone claim a target that a later phone needed more, and the total
    comes out worse with nothing in the result to show it.

    Where the sets differ in size the surplus is unmatched, and where
    ``max_distance`` is given a pair further apart than that is broken
    rather than kept.

    Args:
        source: one phoneset, as a Phoneset or any iterable
        target: the other
        ipa: feature system to measure with; the shipped one by default
        max_distance: break any pair further apart than this

    Examples:
        >>> m = one_to_one_mapping(["p", "b"], ["b", "p"])
        >>> sorted((c.source, c.target) for c in m)
        [('b', 'b'), ('p', 'p')]
    """
    features, left, right = _prepare(source, target, ipa, tied)
    if not left.phones or not right.phones:
        return _styled(
            PhonesetMapping(
                left, right, "one-to-one", tuple(_unmapped(p) for p in left)
            ),
            source_style,
            target_style,
        )

    rows = _cost_rows(left, right, features)
    assignment = _assign(rows, len(right.phones))
    found: list[Correspondence] = []
    for index, phone in enumerate(left.phones):
        column = assignment[index]
        if column is None or _refused(rows[index][column], max_distance):
            found.append(_unmapped(phone))
            continue
        found.append(Correspondence(phone, right.phones[column], rows[index][column]))
    return _styled(
        PhonesetMapping(left, right, "one-to-one", tuple(found)),
        source_style,
        target_style,
    )
