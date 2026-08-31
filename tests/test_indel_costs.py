"""Per-phone insertion and deletion costs, and the directional distance.

Every test here is a predicate about the *shape* of the arithmetic rather
than a pinned value, because the defect this change is guarding against is a
well-formed number computed the wrong way, under a green suite. The two
shapes at risk are a base row built as an index times a constant and a
denominator built as a length times a price. Both are correct whenever every
phone costs the same, which is the case the whole suite was written under,
so neither would announce itself.

Each zero-valued assertion here is paired with a control that shares its
code path. A sweep that reports "nothing moved" is worth nothing until the
same sweep has been shown to report movement.
"""

from __future__ import annotations

import itertools
import math

import ipakit
import pytest
from ipakit import IPAFeatures
from ipakit.distance import CostSchedule, cost_name, costs_identity, price
from ipakit.distance_model import DistanceModel
from ipakit.metric import GAP_COST

from .corpus import self_spelling_phones

#: Words built from windows over the self-spelling phones, kept when they
#: tokenize to exactly the phones they were built from. Deterministic, and
#: not a hand-picked list, so a pair that would expose a defect is not
#: excluded by the person who wrote the test.
WORD_LENGTHS = (1, 2, 3, 4)


def _words(ipa: IPAFeatures) -> list[str]:
    phones = self_spelling_phones()
    out: list[str] = []
    for k in WORD_LENGTHS:
        for i in range(0, len(phones) - k + 1, 3):
            w = "".join(phones[i : i + k])
            if len(ipa.segments(w)) == k:
                out.append(w)
    return out


def _pairs(ipa: IPAFeatures) -> list[tuple[str, str]]:
    """Word pairs at two strides. The short one pairs words of like length,
    the long one crosses the length blocks, so a sweep over these sees both
    equal-length alignments and ones that must spend gaps."""
    ws = _words(ipa)
    n = len(ws)
    return [(ws[i], ws[(i + stride) % n]) for stride in (17, 211) for i in range(n)]


def _tokens(ipa: IPAFeatures, word: str) -> list[str]:
    return [t for t in ipa.tokenize(word) if not ipa.is_structural_token(t)]


def _varied(ipa: IPAFeatures, name: str, lo: float, hi: float) -> CostSchedule:
    """A schedule that prices phones apart, spread over the inventory.

    The prices are a deterministic spread and mean nothing phonetically --
    they are here to make "sum over phones" and "count times price"
    different numbers, which is the only thing these tests need of them.
    A schedule that meant something would be a fitted table, which is what
    the library refuses to ship.
    """
    phones = self_spelling_phones()
    n = len(phones)
    # Deliberately not a linear ramp. A linear spread attains its own mean
    # at some phone, so ``n * price(that phone)`` equals the sum over any
    # window centered on it and a length-multiplied normalizer would agree
    # with the summed one by accident on a share of the corpus. The squared
    # index makes that coincidence rare rather than systematic.
    return CostSchedule(
        name,
        {p: lo + (hi - lo) * ((i * i) % (n + 1)) / n for i, p in enumerate(phones)},
        default=hi,
    )


class TestFlatCostsAreUnchanged:
    """A flat price must behave exactly as the scalar did -- and the check
    that says so must be able to say the opposite."""

    def test_a_flat_schedule_equals_the_scalar_it_spells(
        self, ipa: IPAFeatures
    ) -> None:
        """A CostSchedule whose every answer is ``GAP_COST`` is ``GAP_COST``.

        This is the zero. The control below shares its code path exactly --
        same sweep, same comparison, same entry points -- and differs only
        in the number the schedule answers with.
        """
        flat = CostSchedule("test/flat", {}, default=GAP_COST)
        moved = 0
        checked = 0
        for a, b in _pairs(ipa):
            plain = ipa.word_distance(a, b, strict=False)
            named = ipa.directional_word_distance(
                a, b, insert_cost=flat, delete_cost=flat, strict=False
            )
            if (plain.edit_cost, plain.similarity, plain.coverage) != (
                named.edit_cost,
                named.similarity,
                named.coverage,
            ):
                moved += 1
            checked += 1
        assert checked > 150, f"sweep checked only {checked} pairs"
        assert moved == 0, f"{moved} of {checked} pairs moved under a flat schedule"

    def test_the_same_sweep_sees_a_price_that_is_not_flat(
        self, ipa: IPAFeatures
    ) -> None:
        """The control for the zero above.

        Identical sweep and identical comparison, with the schedule
        answering something other than ``GAP_COST``. If this does not move
        a large share of the corpus, the zero above is a blind instrument
        rather than a result.
        """
        off = CostSchedule("test/not-flat", {}, default=GAP_COST * 1.2)
        moved = 0
        checked = 0
        for a, b in _pairs(ipa):
            plain = ipa.word_distance(a, b, strict=False)
            named = ipa.directional_word_distance(
                a, b, insert_cost=off, delete_cost=off, strict=False
            )
            if (plain.edit_cost, plain.similarity, plain.coverage) != (
                named.edit_cost,
                named.similarity,
                named.coverage,
            ):
                moved += 1
            checked += 1
        assert checked > 150, f"sweep checked only {checked} pairs"
        assert moved > 0.9 * checked, f"only {moved} of {checked} pairs moved"

    def test_a_model_reads_a_flat_schedule_as_its_scalar(
        self, ipa: IPAFeatures
    ) -> None:
        scalar = DistanceModel.global_(ipa, insert_cost=0.8, delete_cost=0.3)
        schedule = DistanceModel.global_(
            ipa,
            insert_cost=CostSchedule("test/i", {}, default=0.8),
            delete_cost=CostSchedule("test/d", {}, default=0.3),
        )
        checked = 0
        for a, b in _pairs(ipa):
            x = scalar.word_distance(a, b)
            y = schedule.word_distance(a, b)
            assert x.edit_cost == pytest.approx(y.edit_cost), (a, b)
            assert x.similarity == pytest.approx(y.similarity), (a, b)
            checked += 1
        assert checked > 150, f"sweep checked only {checked} pairs"


class TestTheNormalizerSumsOverPhones:
    """The denominator is the null alignment's cost, summed over the phones
    it actually removes and supplies -- never a token count times a price."""

    def test_no_length_times_price_reproduces_the_denominator(
        self, ipa: IPAFeatures
    ) -> None:
        """The test that fails if ``n * delete + m * insert`` comes back.

        The predicate is stated over *every* price the schedule could have
        been read at, not over one: the denominator recovered from the
        result must equal the sum over the phones, and on most pairs it
        must differ from ``n * delete(x) + m * insert(y)`` for **every** x
        in the first word and y in the second. A length-multiplied
        normalizer necessarily equals one of those readings -- whichever
        phone it happened to sample -- so on those pairs it cannot pass
        this, however the sampling is written.

        Not every pair can discriminate, and the count is asserted rather
        than assumed: two one-phone words make every reading the sum, and
        a longer pair can coincide by arithmetic accident. What makes this
        a test rather than a hope is that the summed identity is asserted
        on every pair and the discriminating ones are counted.
        """
        dele = _varied(ipa, "test/delete", 0.2, 1.0)
        ins = _varied(ipa, "test/insert", 0.4, 1.6)
        checked = 0
        discriminating = 0
        for a, b in _pairs(ipa):
            t1, t2 = _tokens(ipa, a), _tokens(ipa, b)
            r = ipa.directional_word_distance(
                a, b, insert_cost=ins, delete_cost=dele, strict=False
            )
            summed = sum(dele(t) for t in t1) + sum(ins(t) for t in t2)
            assert r.similarity == pytest.approx(1.0 - r.edit_cost / summed), (a, b)
            multiplied = [len(t1) * dele(x) + len(t2) * ins(y) for x in t1 for y in t2]
            if not any(math.isclose(summed, v, rel_tol=1e-12) for v in multiplied):
                discriminating += 1
            checked += 1
        assert checked > 150, f"sweep checked only {checked} pairs"
        assert discriminating > 100, (
            f"only {discriminating} of {checked} pairs could tell a sum "
            "from a length times a price"
        )

    def test_a_flat_price_makes_the_two_readings_agree(self, ipa: IPAFeatures) -> None:
        """The control for the test above: it is sharp only where it should be.

        With a flat price the summed denominator and the length-multiplied
        one are the same number, so the predicate above would pass a
        length-multiplied implementation. Asserting that here is what keeps
        the previous test's strength attributable to the varying prices
        rather than to something incidental about the corpus.
        """
        flat = CostSchedule("test/flat", {}, default=0.7)
        checked = 0
        for a, b in _pairs(ipa):
            t1, t2 = _tokens(ipa, a), _tokens(ipa, b)
            summed = sum(flat(t) for t in t1) + sum(flat(t) for t in t2)
            assert summed == pytest.approx(len(t1) * 0.7 + len(t2) * 0.7)
            checked += 1
        assert checked > 150, f"sweep checked only {checked} pairs"

    def test_a_pure_deletion_costs_the_phones_it_removes(
        self, ipa: IPAFeatures
    ) -> None:
        """The base row, from the other end.

        A word against the empty string has exactly one alignment: delete
        every phone. Its cost is therefore the sum of the schedule's prices
        for those phones, and ``i * delete_cost`` cannot produce that for
        any word whose phones are priced apart.
        """
        dele = _varied(ipa, "test/delete", 0.2, 1.0)
        checked = 0
        varying = 0
        for word in _words(ipa):
            t1 = _tokens(ipa, word)
            r = ipa.directional_word_distance(word, "", delete_cost=dele, strict=False)
            assert r.edit_cost == pytest.approx(sum(dele(t) for t in t1)), word
            assert r.similarity == pytest.approx(0.0), word
            if len({dele(t) for t in t1}) > 1:
                varying += 1
            checked += 1
        assert checked > 150, f"sweep checked only {checked} words"
        assert varying > 100, f"only {varying} words priced their phones apart"

    def test_a_pure_insertion_costs_the_phones_it_supplies(
        self, ipa: IPAFeatures
    ) -> None:
        ins = _varied(ipa, "test/insert", 0.3, 1.4)
        checked = 0
        for word in _words(ipa):
            t2 = _tokens(ipa, word)
            r = ipa.directional_word_distance("", word, insert_cost=ins, strict=False)
            assert r.edit_cost == pytest.approx(sum(ins(t) for t in t2)), word
            checked += 1
        assert checked > 150, f"sweep checked only {checked} words"

    def test_similarity_stays_in_range_under_a_schedule(self, ipa: IPAFeatures) -> None:
        """What the denominator is *for*. The null alignment is the most any
        alignment can cost, so a sum over the phones bounds the score at 0
        from below and 1 from above however far apart the prices are."""
        dele = _varied(ipa, "test/delete", 0.05, 2.0)
        ins = _varied(ipa, "test/insert", 2.0, 0.05)
        checked = 0
        for a, b in _pairs(ipa):
            r = ipa.directional_word_distance(
                a, b, insert_cost=ins, delete_cost=dele, strict=False
            )
            assert -1e-9 <= r.similarity <= 1.0 + 1e-9, (a, b, r.similarity)
            checked += 1
        assert checked > 150, f"sweep checked only {checked} pairs"


class TestDirection:
    """A reference and a hypothesis are not interchangeable."""

    def test_the_score_is_asymmetric_under_an_asymmetric_schedule(
        self, ipa: IPAFeatures
    ) -> None:
        dele = _varied(ipa, "test/delete", 0.2, 0.6)
        ins = _varied(ipa, "test/insert", 0.9, 1.8)
        asymmetric = 0
        checked = 0
        for a, b in _pairs(ipa):
            if a == b:
                continue
            fwd = ipa.directional_word_distance(
                a, b, insert_cost=ins, delete_cost=dele, strict=False
            )
            rev = ipa.directional_word_distance(
                b, a, insert_cost=ins, delete_cost=dele, strict=False
            )
            if fwd.edit_cost != pytest.approx(rev.edit_cost):
                asymmetric += 1
            checked += 1
        assert checked > 150, f"sweep checked only {checked} pairs"
        assert (
            asymmetric > 100
        ), f"only {asymmetric} of {checked} pairs were directional"

    def test_word_distance_stays_symmetric_on_the_same_pairs(
        self, ipa: IPAFeatures
    ) -> None:
        """The promise the separate entry point exists to keep.

        The same corpus that the directional score splits on, measured
        through ``word_distance``, which takes no schedule and must not
        have acquired one. If this ever fails while the test above passes,
        the asymmetry has leaked into the symmetric function.
        """
        checked = 0
        for a, b in _pairs(ipa):
            fwd = ipa.word_distance(a, b, strict=False)
            rev = ipa.word_distance(b, a, strict=False)
            assert fwd.edit_cost == pytest.approx(rev.edit_cost), (a, b)
            assert fwd.similarity == pytest.approx(rev.similarity), (a, b)
            checked += 1
        assert checked > 150, f"sweep checked only {checked} pairs"

    def test_flat_costs_make_the_two_entry_points_agree(self, ipa: IPAFeatures) -> None:
        """The asymmetry comes from the schedule, not from the entry point."""
        checked = 0
        for a, b in _pairs(ipa):
            plain = ipa.word_distance(a, b, strict=False)
            directional = ipa.directional_word_distance(a, b, strict=False)
            assert plain.edit_cost == pytest.approx(directional.edit_cost), (a, b)
            assert plain.similarity == pytest.approx(directional.similarity), (a, b)
            checked += 1
        assert checked > 150, f"sweep checked only {checked} pairs"

    def test_a_cheap_deletion_prefers_losing_the_reference_phone(
        self, ipa: IPAFeatures
    ) -> None:
        """The phenomenon, in one worked pair. A schwa the schedule says is
        cheap to lose makes ``kætə`` -> ``kæt`` a small edit, while the same
        schedule says nothing about supplying one, so ``kæt`` -> ``kætə``
        stays expensive."""
        drop = CostSchedule("test/schwa-drops", {"ə": 0.1}, default=1.0)
        lost = ipa.directional_word_distance("kætə", "kæt", delete_cost=drop)
        gained = ipa.directional_word_distance("kæt", "kætə", delete_cost=drop)
        assert lost.edit_cost == pytest.approx(0.1)
        assert gained.edit_cost == pytest.approx(1.0)
        assert lost.similarity > gained.similarity

    def test_the_model_names_its_reference_side(self, ipa: IPAFeatures) -> None:
        model = DistanceModel.global_(ipa, insert_cost=1.5, delete_cost=0.25)
        a = model.directional_word_distance("kætəloɡ", "kæt")
        b = model.word_distance("kætəloɡ", "kæt")
        assert a.edit_cost == pytest.approx(b.edit_cost)
        assert a.edit_cost != pytest.approx(
            model.directional_word_distance("kæt", "kætəloɡ").edit_cost
        )


class TestTheResultSaysWhatProducedIt:
    """A caller-supplied schedule must not vanish from the result."""

    def test_every_path_reports_a_parameterization(self, ipa: IPAFeatures) -> None:
        named = CostSchedule("test/named", {"a": 0.5}, default=1.0)
        results = [
            ipa.word_distance("kæt", "kæd"),
            ipa.word_distance("", ""),
            ipa.directional_word_distance("kæt", "kæd"),
            ipa.directional_word_distance("", ""),
            ipa.directional_word_distance("kæt", "kæd", delete_cost=named),
            DistanceModel.global_(ipa).word_distance("kæt", "kæd"),
            DistanceModel.global_(ipa).word_distance("", ""),
            DistanceModel.global_(ipa, delete_cost=named).word_distance("kæt", "kæd"),
        ]
        for r in results:
            assert r.costs, r
            assert r.costs.startswith("insert=")
            assert " delete=" in r.costs

    def test_a_schedule_travels_by_name(self, ipa: IPAFeatures) -> None:
        named = CostSchedule("french-ish/deletion", {"ə": 0.2}, default=1.0)
        r = ipa.directional_word_distance("kætə", "kæt", delete_cost=named)
        assert r.costs == "insert=1.0 delete=french-ish/deletion"

    def test_an_unnamed_callable_says_it_is_unnamed(self, ipa: IPAFeatures) -> None:
        r = ipa.directional_word_distance("kætə", "kæt", delete_cost=lambda p: 0.5)
        assert "<lambda>" in r.costs

    def test_identity_distinguishes_the_schedules_it_names(self) -> None:
        one = CostSchedule("a", {}, default=1.0)
        two = CostSchedule("b", {}, default=1.0)
        assert costs_identity(one, two) != costs_identity(two, one)
        assert cost_name(1.0) == "1.0"
        assert cost_name(one) == "a"

    def test_a_schedule_must_be_named(self) -> None:
        with pytest.raises(ValueError, match="must be named"):
            CostSchedule("", {}, default=1.0)


class TestRefusals:
    """A price that would make the dynamic program answer nonsense."""

    @pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf")])
    def test_a_malformed_price_is_refused_at_construction(self, bad: float) -> None:
        with pytest.raises(ValueError, match="non-negative finite"):
            CostSchedule("test/bad", {"a": bad}, default=1.0)
        with pytest.raises(ValueError, match="non-negative finite"):
            CostSchedule("test/bad", {}, default=bad)

    @pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf")])
    def test_a_callable_answering_a_malformed_price_is_refused(
        self, ipa: IPAFeatures, bad: float
    ) -> None:
        """A bare callable escapes the constructor's check, so the aligner
        makes the same check where it resolves the price. The message names
        the argument and the phone, because a caller with a schedule of
        hundreds of phones has nothing else to find it by."""
        with pytest.raises(ValueError, match="delete_cost"):
            ipa.directional_word_distance("kæt", "kæd", delete_cost=lambda p: bad)


class TestSchedulesDerivedFromRuleSets:
    """``CostSchedule.from_rules``: which phones is read off declared data,
    what they cost is the caller's, and the scope of the claim is the rule
    set rather than the language.

    A hand-maintained per-language list of droppable phones is the pattern
    ``test_declared_not_hardcoded.py`` exists to reject -- a second copy of
    something already declared, going stale in silence. These check that
    the derived membership really does come from the file, by a route that
    does not go through the same machinery that produced it: the phones a
    schedule prices must all appear literally in the rule text.
    """

    def _rules_text(self, name: str) -> str:
        from ipakit.constants import DATA_DIR

        return (DATA_DIR / "rules" / f"{name}.rules").read_text(encoding="utf-8")

    def test_the_french_set_prices_what_it_deletes(self, ipa: IPAFeatures) -> None:
        from ipakit import rules

        schedule = CostSchedule.from_rules(
            rules.shipped("french-liaison", ipa),
            "delete",
            ipa,
            price=0.25,
            default=1.0,
        )
        assert schedule.name == "french-liaison/delete"
        assert len(schedule.prices) >= 5, dict(schedule.prices)
        text = self._rules_text("french-liaison")
        for phone in schedule.prices:
            assert f"{phone} -> ∅" in text, phone
        assert schedule("k") == 1.0

    def test_the_japanese_set_prices_what_it_inserts(self, ipa: IPAFeatures) -> None:
        from ipakit import rules

        schedule = CostSchedule.from_rules(
            rules.shipped("japanese-moraic", ipa),
            "insert",
            ipa,
            price=0.25,
            default=1.0,
        )
        assert schedule.name == "japanese-moraic/insert"
        assert len(schedule.prices) >= 3, dict(schedule.prices)
        text = self._rules_text("japanese-moraic")
        for phone in schedule.prices:
            assert f"∅ -> {phone}" in text, phone
        assert schedule("k") == 1.0

    def test_a_set_stating_no_such_edit_is_refused(self, ipa: IPAFeatures) -> None:
        """A schedule that prices nothing is a flat price wearing a name.
        Returning one would report a schedule in every result computed under
        it while doing nothing, which nothing downstream could detect."""
        from ipakit import rules

        with pytest.raises(ValueError, match="states no deletes"):
            CostSchedule.from_rules(
                rules.shipped("japanese-moraic", ipa),
                "delete",
                ipa,
                price=0.25,
                default=1.0,
            )
        with pytest.raises(ValueError, match="must be 'delete' or 'insert'"):
            CostSchedule.from_rules(
                rules.shipped("french-liaison", ipa),
                "sideways",
                ipa,
                price=0.25,
                default=1.0,
            )

    def test_a_derived_schedule_moves_exactly_the_words_it_names(
        self, ipa: IPAFeatures
    ) -> None:
        """What a schedule moves, and why those are the right movers.

        A deletion schedule prices the reference side, so a pair moves if
        and only if the reference contains a phone the schedule names. The
        second count is the one that matters: movers whose reference holds no
        priced phone must be zero, or the schedule is reaching somewhere it
        does not name.
        """
        from ipakit import rules

        schedule = CostSchedule.from_rules(
            rules.shipped("french-liaison", ipa),
            "delete",
            ipa,
            price=0.25,
            default=1.0,
        )
        priced = set(schedule.prices)
        moved = 0
        unexplained = 0
        checked = 0
        for a, b in _pairs(ipa):
            flat = ipa.word_distance(a, b, strict=False)
            under = ipa.directional_word_distance(
                a, b, delete_cost=schedule, strict=False
            )
            if flat.edit_cost != pytest.approx(under.edit_cost) or flat.similarity != (
                pytest.approx(under.similarity)
            ):
                moved += 1
                if not (priced & set(_tokens(ipa, a))):
                    unexplained += 1
            checked += 1
        assert checked > 150, f"sweep checked only {checked} pairs"
        assert moved > 20, f"a schedule that moves {moved} pairs is not a schedule"
        assert (
            unexplained == 0
        ), f"{unexplained} of {moved} movers hold no phone the schedule names"


class TestTheBoundaryWithTheFeatureSpace:
    """The feature space, the comparison bundle and therefore ``distance``
    are not language-relative, whatever tiers a language declares. A cost
    schedule parameterizes a comparison and is not a term in it, and this
    is the measurement that says so rather than the claim that says so."""

    def test_no_schedule_moves_a_phone_distance(self, ipa: IPAFeatures) -> None:
        wild = _varied(ipa, "test/wild", 0.01, 9.0)
        flat = DistanceModel.global_(ipa)
        scheduled = DistanceModel.global_(ipa, insert_cost=wild, delete_cost=wild)
        phones = self_spelling_phones()[:60]
        moved = 0
        checked = 0
        for a, b in itertools.combinations(phones, 2):
            if flat.distance(a, b) != scheduled.distance(a, b):
                moved += 1
            if ipa.distance(a, b) != ipa.distance(b, a):
                moved += 1
            checked += 1
        assert checked > 1000, f"sweep checked only {checked} pairs"
        assert moved == 0, f"{moved} of {checked} phone pairs moved under a schedule"

    def test_the_same_sweep_sees_a_model_parameter_that_does_reach_distance(
        self, ipa: IPAFeatures
    ) -> None:
        """The control. ``gamma`` is a model parameter that *is* on the
        phone-level path, so the sweep above must be able to see one move.
        A control on a different code path would prove nothing about
        whether that zero can fail."""
        flat = DistanceModel.global_(ipa)
        sharp = DistanceModel.global_(ipa, gamma=3.0)
        phones = self_spelling_phones()[:60]
        moved = 0
        checked = 0
        for a, b in itertools.combinations(phones, 2):
            if flat.distance(a, b) != sharp.distance(a, b):
                moved += 1
            checked += 1
        assert checked > 1000, f"sweep checked only {checked} pairs"
        assert moved > 0.5 * checked, f"only {moved} of {checked} pairs moved"


class TestSubstitutionStaysInOneCurrency:
    def test_a_substitution_costs_at_most_this_pair_s_delete_and_insert(
        self, ipa: IPAFeatures
    ) -> None:
        """The constraint ``sub(a, b) <= delete(a) + insert(b)``, attached to
        the pair rather than to a constant. Under per-phone prices the bound
        is the two prices of the two tokens in hand, and a substitution of a
        dear phone by a cheap one is priced by what it stands in for."""
        dele = _varied(ipa, "test/delete", 0.2, 1.0)
        ins = _varied(ipa, "test/insert", 0.4, 1.6)
        model = DistanceModel.global_(ipa, insert_cost=ins, delete_cost=dele)
        phones = self_spelling_phones()[:60]
        checked = 0
        closest = 0.0
        for a, b in itertools.combinations(phones, 2):
            bound = dele(a) + ins(b)
            cost = model.sub_cost(a, b)
            assert cost <= bound + 1e-12, (a, b, cost, bound)
            closest = max(closest, cost / bound)
            checked += 1
        assert checked > 1000, f"sweep checked only {checked} pairs"
        # The bound is not slack by construction: some pair in the sweep is
        # priced near the whole of its own delete-plus-insert. It does not
        # reach it exactly here because a percentile of 0 needs the least
        # similar pair in the whole reference inventory, and this sweep is
        # a slice of it. Equality at the top is pinned directly below.
        assert closest > 0.8, f"the bound is slack everywhere; closest was {closest}"

    def test_a_maximally_different_pair_costs_exactly_delete_plus_insert(
        self,
    ) -> None:
        """Equality at the top, at the one place the pricing happens."""
        from ipakit.distance import _substitution_cost

        assert _substitution_cost(1.0, 1.6, 0.2) == pytest.approx(1.8)
        assert _substitution_cost(0.0, 1.6, 0.2) == 0.0
        assert _substitution_cost(0.5, 1.6, 0.2) == pytest.approx(0.9)


class TestLengthGating:
    def test_the_bound_still_bounds_under_a_schedule(self, ipa: IPAFeatures) -> None:
        """``is_similar`` skips the dynamic program when a pair cannot reach
        the threshold. The bound it skips on must be an upper bound on the
        score the program would have produced, or the short circuit answers
        ``False`` for a pair that clears the threshold -- silently, since
        nothing else runs."""
        dele = _varied(ipa, "test/delete", 0.2, 1.0)
        ins = _varied(ipa, "test/insert", 0.4, 1.6)
        model = DistanceModel.global_(ipa, insert_cost=ins, delete_cost=dele)
        checked = 0
        unequal = 0
        for a, b in _pairs(ipa):
            t1, t2 = _tokens(ipa, a), _tokens(ipa, b)
            bound = model._max_word_similarity(t1, t2)
            actual = model.word_similarity(a, b)
            assert actual <= bound + 1e-12, (a, b, actual, bound)
            if len(t1) != len(t2):
                unequal += 1
            checked += 1
        assert checked > 150, f"sweep checked only {checked} pairs"
        assert unequal > 100, f"only {unequal} pairs differed in length"

    def test_a_structural_mark_is_not_charged_a_length(self, ipa: IPAFeatures) -> None:
        """``word_distance("lez‿ami", "lezami")`` is 0, and the gate in front
        of it must agree. It counted every token the tokenizer emitted, so
        the linking undertie made the two forms differ in length and the
        short circuit refused the pair at any threshold above 12/13 --
        for two forms the aligner scores identical."""
        model = DistanceModel.global_(ipa)
        assert model.word_similarity("lez‿ami", "lezami") == pytest.approx(1.0)
        assert model.is_similar("lez‿ami", "lezami", threshold=0.999) is True
        assert (
            model.is_similar("lez‿ami", "lezami", threshold=0.999, max_length_ratio=1.0)
            is True
        )


class TestTheDocumentedExample:
    def test_the_readme_and_docs_example_runs(self) -> None:
        drop = ipakit.CostSchedule("my-english/deletion", {"ə": 0.25}, default=1.0)
        r = ipakit.directional_word_distance("kætə", "kæt", delete_cost=drop)
        assert r.costs == "insert=1.0 delete=my-english/deletion"
        assert r.edit_cost == pytest.approx(0.25)
        assert price(drop, "ə") == 0.25
        assert price(drop, "k") == 1.0
        assert price(1.0, "k") == 1.0
