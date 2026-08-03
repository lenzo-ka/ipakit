"""Tests for phonetic distance calculation."""

import pytest
from ipakit import IPAFeatures

from .corpus import assert_swept, self_spelling_phones, single_mark_units


class TestPhoneDistance:
    """Tests for distance between individual phones."""

    def test_distance_identical(self, ipa: IPAFeatures) -> None:
        assert ipa.distance("p", "p") == 0.0
        assert ipa.distance("a", "a") == 0.0

    def test_distance_voicing_pair(self, ipa: IPAFeatures) -> None:
        # p and b differ only in voicing
        d = ipa.distance("p", "b")
        assert 0 < d < 0.5

    def test_distance_unknown_phone_is_max(self, ipa: IPAFeatures) -> None:
        # An unknown phone has no features; distance returns the sentinel 1.0.
        assert ipa.distance("p", "@") == 1.0
        assert ipa.distance("@", "p") == 1.0

    def test_an_unreadable_input_is_not_far_from_itself(self, ipa: IPAFeatures) -> None:
        # The sentinel says "no basis for comparison". That is true of an
        # unknown symbol against a phone and false of one against itself.
        # String identity is the only basis left once the segment cannot be
        # built, so it is what identity is decided on here, over NFC forms.
        assert ipa.distance("@", "@") == 0.0
        assert ipa.distance("X", "X") == 0.0
        assert ipa.distance("", "") == 0.0

    def test_distance_different_place(self, ipa: IPAFeatures) -> None:
        # p and t differ in place
        d = ipa.distance("p", "t")
        assert 0 < d < 0.5

    def test_distance_vowel_consonant(self, ipa: IPAFeatures) -> None:
        # Vowel vs consonant should be more distant than voicing pairs
        d_vowel_cons = ipa.distance("a", "p")
        d_voicing = ipa.distance("p", "b")
        assert d_vowel_cons > d_voicing

    def test_distance_unknown(self, ipa: IPAFeatures) -> None:
        assert ipa.distance("p", "X") == 1.0

    def test_distance_symmetric(self, ipa: IPAFeatures) -> None:
        assert ipa.distance("p", "b") == ipa.distance("b", "p")
        assert ipa.distance("s", "z") == ipa.distance("z", "s")

    def test_distance_affricates(self, ipa: IPAFeatures) -> None:
        d = ipa.distance("t͡ʃ", "d͡ʒ")
        assert 0 < d < 0.5  # differ in voicing

    def test_distance_excludes_metadata_attrs(self, ipa: IPAFeatures) -> None:
        # Regression for I13: every phone carries a unique `href` (wiki slug),
        # so distinct phones always differ on it. If href/xsampa were counted as
        # features, distance("p","b") would be inflated by those metadata keys.
        # p and b differ in exactly one feature (voicing), so the distance is
        # 1 / (comparable non-metadata features). Derive that denominator from
        # the phones' own feature dicts so the test survives feature changes.
        from ipakit.metric import _metric_bundle

        c1 = ipa.segment("p").constituents[0]
        c2 = ipa.segment("b").constituents[0]
        f1, p1 = _metric_bundle(ipa, c1)
        f2, p2 = _metric_bundle(ipa, c2)
        assert "href" not in f1 and "xsampa" not in f1 and "class" not in f1
        # p and b differ in exactly one term (voicing); the denominator is
        # the comparable feature keys plus the place-components term plus
        # the two sagittal bridge terms (x, y).
        n_terms = len(set(f1) | set(f2)) + 3
        d = ipa.distance("p", "b")
        assert d == pytest.approx(1 / n_terms, abs=1e-4)


class TestSegmentDistance:
    """Tests for distance between segments (phones with diacritics)."""

    def test_segment_distance_simple(self, ipa: IPAFeatures) -> None:
        d = ipa.segment_distance("p", "b")
        assert 0 < d < 1.0

    def test_segment_distance_with_diacritics(self, ipa: IPAFeatures) -> None:
        d = ipa.segment_distance("pʰ", "p")
        assert 0 < d < 1.0

    def test_segment_distance_identical(self, ipa: IPAFeatures) -> None:
        assert ipa.segment_distance("pʰ", "pʰ") == 0.0


class TestPairwiseDistances:
    """Tests for pairwise distance matrix."""

    def test_pairwise_distances_shape(self, ipa: IPAFeatures) -> None:
        phones = ["p", "b", "t"]
        matrix = ipa.pairwise_distances(phones)
        assert len(matrix) == 3
        assert all(len(row) == 3 for row in matrix)

    def test_pairwise_distances_diagonal_zero(self, ipa: IPAFeatures) -> None:
        phones = ["p", "b", "t"]
        matrix = ipa.pairwise_distances(phones)
        assert matrix[0][0] == 0.0
        assert matrix[1][1] == 0.0
        assert matrix[2][2] == 0.0

    def test_pairwise_distances_symmetric(self, ipa: IPAFeatures) -> None:
        phones = ["p", "b", "t"]
        matrix = ipa.pairwise_distances(phones)
        assert matrix[0][1] == matrix[1][0]
        assert matrix[0][2] == matrix[2][0]
        assert matrix[1][2] == matrix[2][1]

    def test_pairwise_distances_positive(self, ipa: IPAFeatures) -> None:
        phones = ["p", "b", "t"]
        matrix = ipa.pairwise_distances(phones)
        # Off-diagonal should be positive
        assert matrix[0][1] > 0
        assert matrix[0][2] > 0


class TestOneCurrency:
    """``segment_distance`` is a flat mean over positions, and the terms it
    means over are the same ones every other alignment in the library uses.

    Written as predicates over the shape rather than as a list of pairs: the
    defect these replace halved *every* multi-unit substitution, and a list
    of today's pairs would have documented the halving rather than caught it.
    """

    #: One unit in this many. The sweep pairs adjacent units and appends
    #: shared suffixes to each pair, so a stride keeps it inside the default
    #: run. Sampling is defensible here because what is under test is the
    #: *normalizer*, which reads only the per-position costs and the two
    #: lengths; the identity sweep below is the one that has to reach every
    #: unit, and it does.
    STRIDE = 11

    def _grown(self, ipa: IPAFeatures, left: str, parts: list[str]) -> str | None:
        """``left`` with ``parts`` appended, if it still reads as those units.

        A mark can bind backwards and a sequence can recompose, either of
        which makes the grown string a different sequence of units than the
        one appended. That is not the case under test, and admitting it
        silently would let the sweep assert something other than what it
        claims.
        """
        grown = left + "".join(parts)
        spelled = [unit.to_ipa() for unit in ipa.segments(grown)]
        return grown if spelled == [left, *parts] else None

    def test_appending_a_shared_unit_does_not_reprice_the_pair(
        self, ipa: IPAFeatures
    ) -> None:
        """Appending a unit identical on both sides adds one term worth 0 and
        nothing else, so the *summed* positional cost is unchanged and the
        mean falls by exactly the factor the new position introduces.

        The defect was the opposite: an unmatched unit was counted once
        positionally and once as length, and the two normalized quantities
        were then averaged, so every ordinary substitution came back at half
        its declared cost.
        """
        units = single_mark_units()[:: self.STRIDE]
        checked = 0
        nonzero = 0
        for left, right in zip(units, units[1:], strict=False):
            # Anchored on ``distance`` -- the Segment metric itself -- and not
            # on ``segment_distance`` of the ungrown pair. Against the latter
            # the property is scale-invariant: a normalizer that halved every
            # multi-unit answer would halve both sides and pass. Measured:
            # reinstating the halving leaves this green if the base is taken
            # through the same call being tested.
            base = ipa.distance(left, right)
            for suffix in ("a", "s"):
                for count in (1, 2):
                    parts = [suffix] * count
                    grown_left = self._grown(ipa, left, parts)
                    grown_right = self._grown(ipa, right, parts)
                    if grown_left is None or grown_right is None:
                        continue
                    grown = ipa.segment_distance(grown_left, grown_right)
                    assert grown * (1 + count) == pytest.approx(base, abs=1e-12)
                    checked += 1
                    nonzero += base > 0
        assert checked > 500, f"sweep checked only {checked} pairs"
        assert nonzero > 100, (
            f"only {nonzero} of {checked} pairs cost anything; the invariant "
            "holds trivially over zeros, so this sweep would prove nothing"
        )

    def test_a_string_prices_as_the_mean_of_its_positions(
        self, ipa: IPAFeatures
    ) -> None:
        """The general statement the two properties around this one are cases
        of: over equal-length strings, ``segment_distance`` is the mean of
        ``distance`` taken position by position.

        Anchoring the right-hand side on ``distance`` is what makes this a
        statement about the normalizer rather than about itself.
        """
        units = single_mark_units()[:: self.STRIDE]
        checked = 0
        nonzero = 0
        for index in range(0, len(units) - 5, 3):
            for width in (2, 3):
                left = list(units[index : index + width])
                right = list(units[index + 3 : index + 3 + width])
                if len(right) < width:
                    continue
                joined_left = self._grown(ipa, left[0], left[1:])
                joined_right = self._grown(ipa, right[0], right[1:])
                if joined_left is None or joined_right is None:
                    continue
                expected = sum(
                    ipa.distance(a, b) for a, b in zip(left, right, strict=True)
                ) / len(left)
                measured = ipa.segment_distance(joined_left, joined_right)
                assert measured == pytest.approx(expected, abs=1e-12)
                checked += 1
                nonzero += expected > 0
        assert checked > 100, f"sweep checked only {checked} strings"
        assert nonzero > 50, (
            f"only {nonzero} of {checked} string pairs cost anything; the "
            "invariant holds trivially over zeros"
        )

    def test_a_single_unit_pair_prices_the_same_through_either_entry(
        self, ipa: IPAFeatures
    ) -> None:
        """``segment_distance`` over one unit a side is ``distance``.

        Not a separate branch that happens to agree: the positional mean over
        one position *is* the Segment metric, so the two cannot drift apart.
        """
        checked = 0
        for unit in single_mark_units()[:: self.STRIDE]:
            for other in ("a", "s", "n"):
                assert ipa.segment_distance(unit, other) == ipa.distance(unit, other)
                checked += 1
        assert checked > 500, f"sweep checked only {checked} pairs"

    def test_an_unmatched_unit_costs_exactly_a_gap(self, ipa: IPAFeatures) -> None:
        """A position only one side reaches costs ``GAP_COST``, which is what
        an indel costs in ``word_distance`` and what a gap costs inside
        :func:`~ipakit.metric.segment_metric`. So one unmatched unit against
        nothing is exactly ``GAP_COST``, and n of them still are: length is
        positions, not a second normalized quantity summed beside them.
        """
        from ipakit.metric import GAP_COST

        checked = 0
        for unit in single_mark_units()[:: self.STRIDE]:
            assert ipa.segment_distance(unit, "") == GAP_COST
            for count in (2, 3):
                grown = self._grown(ipa, unit, ["a"] * (count - 1))
                if grown is None:
                    continue
                assert ipa.segment_distance(grown, "") == GAP_COST
            checked += 1
        assert checked > 500, f"sweep checked only {checked} units"


class TestTheWordScaleIsOneCurrency:
    """The same currency at the level above: a substitution is priced against
    the gap pair it stands in for, and length is charged once.

    The defect these replace was that the aligner's two operations were never
    related. A substitution cost the pair's dissimilarity, bounded by 1, and a
    gap cost 1, so every substitution was at worst as cheap as one gap and
    always cheaper than the two an omission-plus-addition really is. The DP
    then bought a chain of substitutions wherever it could, and an alignment
    that should have read "this was dropped and that was added" reported
    unlike tokens paired up instead.

    Written as predicates over every phone rather than as named pairs, since
    what is under test is a relation between two scales and a list of today's
    numbers would document the scales instead of relating them.
    """

    def _indel(self) -> float:
        from ipakit.metric import GAP_COST

        return GAP_COST

    def test_a_substitution_is_priced_as_the_delete_and_the_insert_it_stands_for(
        self, ipa: IPAFeatures
    ) -> None:
        """One token a side: the alignment has one choice, and its cost is the
        pair's dissimilarity times ``delete + insert``.

        The ceiling matters more than the factor. A pair sharing nothing costs
        exactly a delete plus an insert, so the standard constraint
        ``sub(a, b) <= delete(a) + insert(b)`` is met with equality at the top
        rather than with room to spare.
        """
        indel = self._indel()
        phones = self_spelling_phones()
        checked = 0
        for left, right in zip(phones, phones[1:], strict=False):
            d = ipa.segment_distance(left, right)
            cost = ipa.word_distance(left, right).edit_cost
            assert cost == pytest.approx(2 * indel * d), (left, right)
            assert cost <= 2 * indel + 1e-12, (left, right)
            checked += 1
        assert_swept(checked + 1, phones)

    def test_a_pair_sharing_nothing_costs_exactly_a_delete_and_an_insert(
        self, ipa: IPAFeatures
    ) -> None:
        """Silence is the reachable top of the scale: ``d(␣, X) = 1`` for every
        speech sound, so the position costs both operations and no more."""
        indel = self._indel()
        phones = [p for p in self_spelling_phones() if p != "␣"]
        checked = 0
        for phone in phones:
            assert ipa.segment_distance(phone, "␣") == 1.0, phone
            assert ipa.word_distance(phone, "␣").edit_cost == pytest.approx(2 * indel)
            checked += 1
        assert_swept(checked, phones + ["␣"])

    def test_the_aligner_can_prefer_a_gap_pair_to_a_pair_of_substitutions(
        self, ipa: IPAFeatures
    ) -> None:
        """``X␣`` against ``␣X`` is one token moved past a silence, and the
        alignment that says so -- match the token, delete one silence, insert
        the other -- is what the DP must choose.

        Under the old scale the two readings tied at 2.0 and the substitution
        chain won the tie, so this reported ``(X, ␣), (␣, X)``: two pairs of
        tokens with nothing in common, and no insertion or deletion anywhere.
        """
        phones = [p for p in self_spelling_phones() if p != "␣"]
        checked = 0
        for phone in phones:
            alignment = ipa.word_distance(
                phone + "␣", "␣" + phone, return_alignment=True
            ).alignment
            assert alignment is not None
            assert (phone, phone) in alignment, (phone, alignment)
            assert alignment.count((None, "␣")) == 1, (phone, alignment)
            assert alignment.count(("␣", None)) == 1, (phone, alignment)
            checked += 1
        assert_swept(checked, phones + ["␣"])

    def test_similarity_is_the_cost_against_the_null_alignment(
        self, ipa: IPAFeatures
    ) -> None:
        """The denominator is what deleting one word and inserting the other
        costs. That path is one the DP minimizes over, so it bounds every
        alignment, and the similarity lands in [0, 1] by construction rather
        than by being clamped.

        Both ends are reachable, which is the point of the denominator: a word
        against itself scores 1, and a word against the same number of
        silences scores 0.
        """
        indel = self._indel()
        phones = [p for p in self_spelling_phones() if p != "␣"]
        checked = 0
        for phone in phones:
            for word, other in ((phone * 3, phone * 3), (phone * 3, "␣␣␣")):
                n, m = len(ipa.segments(word)), len(ipa.segments(other))
                denom = (n + m) * indel
                r = ipa.word_distance(word, other)
                assert r.edit_cost <= denom + 1e-12, (word, other)
                assert r.similarity == pytest.approx(1.0 - r.edit_cost / denom)
                assert 0.0 <= r.similarity <= 1.0, (word, other)
            assert ipa.word_similarity(phone * 3, phone * 3) == 1.0, phone
            assert ipa.word_similarity(phone * 3, "␣␣␣") == pytest.approx(0.0), phone
            checked += 1
        assert_swept(checked, phones + ["␣"])

    def test_a_gap_costs_what_it_costs_one_level_down(self, ipa: IPAFeatures) -> None:
        """A word against nothing is every token deleted, at ``GAP_COST`` each
        -- the same price an unmatched position pays inside
        ``segment_distance``. Substitution is what was rescaled; the gap is the
        fixed point the two levels share.
        """
        indel = self._indel()
        phones = self_spelling_phones()
        checked = 0
        for phone in phones:
            for count in (1, 2, 3):
                word = phone * count
                if len(ipa.segments(word)) != count:
                    continue
                r = ipa.word_distance(word, "")
                assert r.edit_cost == pytest.approx(count * indel), word
                assert r.similarity == pytest.approx(0.0), word
                assert r.coverage == 0.0, word
            checked += 1
        assert_swept(checked, phones)

    def test_coverage_is_reported_and_never_multiplied_in(
        self, ipa: IPAFeatures
    ) -> None:
        """``coverage`` is ``min(n, m) / max(n, m)`` and the score does not read
        it. Length is already charged once, as the gaps the alignment pays for;
        multiplying a length ratio into the similarity would charge it twice --
        the defect ``segment_distance`` had, with its separate length penalty --
        and would destroy the one thing the ratio says.

        The predicate is that the similarity is exactly the cost against the
        null alignment *without* a coverage factor, asserted where coverage is
        not 1 so that the two formulas differ.
        """
        indel = self._indel()
        phones = self_spelling_phones()
        checked = 0
        asymmetric = 0
        for phone in phones:
            for other in ("a", "kat"):
                word = phone * 2
                if len(ipa.segments(word)) != 2:
                    continue
                n, m = len(ipa.segments(word)), len(ipa.segments(other))
                r = ipa.word_distance(word, other)
                assert r.coverage == pytest.approx(min(n, m) / max(n, m))
                assert r.similarity == pytest.approx(
                    1.0 - r.edit_cost / ((n + m) * indel)
                )
                if r.coverage != 1.0 and r.similarity > 0.0:
                    asymmetric += 1
                    assert r.similarity != pytest.approx(r.similarity * r.coverage)
                checked += 1
        assert checked > 200, f"sweep checked only {checked} pairs"
        assert asymmetric > 100, f"only {asymmetric} pairs differed in length"

    def test_coverage_separates_a_truncation_from_a_difference(
        self, ipa: IPAFeatures
    ) -> None:
        """The diagnosis the score cannot make. Two pairs at a similar score,
        one of them a prefix of the other and one of them different
        throughout, and coverage is what tells them apart.
        """
        truncated = ipa.word_distance("kætəloɡ", "kæt")
        differing = ipa.word_distance("kætəloɡ", "␣␣␣␣␣␣␣")
        assert truncated.coverage < 0.5 < differing.coverage
        assert differing.coverage == 1.0
        assert truncated.similarity > differing.similarity


class TestIdentityHolds:
    """``d(x, x) == 0`` for every x the library can build, including the ones
    it cannot read and the empty one.

    Stated over the corpus rather than over named pairs because the defect it
    replaces was reachable only at the edges of the input space, which is
    where named cases are exactly what nobody writes.
    """

    def test_every_unit_is_at_zero_from_itself_through_every_entry_point(
        self, ipa: IPAFeatures
    ) -> None:
        bare = self_spelling_phones()
        checked = 0
        for unit in [*bare, *single_mark_units()]:
            assert ipa.distance(unit, unit) == 0.0, unit
            assert ipa.segment_distance(unit, unit) == 0.0, unit
            assert ipa.word_distance(unit, unit).edit_cost == 0.0, unit
            assert ipa.word_similarity(unit, unit) == 1.0, unit
            checked += 1
        assert_swept(checked, bare)

    def test_identity_holds_where_the_metric_cannot_read_the_input(
        self, ipa: IPAFeatures
    ) -> None:
        """The edges the sweep above cannot spell: the empty string, a symbol
        no inventory declares, and a multi-unit string.

        Pinned as their own case so a sweep restricted to well-formed units
        cannot be mistaken for coverage of these.
        """
        for text in ("", "@", "X"):
            assert ipa.distance(text, text) == 0.0, repr(text)
            assert ipa.segment_distance(text, text) == 0.0, repr(text)
            assert ipa.word_distance(text, text, strict=False).edit_cost == 0.0
        for text in ("kat", "aps", "a"):
            assert ipa.segment_distance(text, text) == 0.0, text
            assert ipa.word_distance(text, text).edit_cost == 0.0, text

    def test_the_bundle_metric_is_zero_on_a_repeated_constituent(
        self, ipa: IPAFeatures
    ) -> None:
        """The same property one level down."""
        from ipakit.metric import bundle_distance

        checked = 0
        for unit in single_mark_units()[::11]:
            for constituent in ipa.segment(unit).constituents:
                assert bundle_distance(ipa, constituent, constituent) == 0.0
                checked += 1
        assert checked > 500, f"sweep checked only {checked} constituents"

    def test_the_guard_states_what_it_cannot_see(self, ipa: IPAFeatures) -> None:
        """``bundle_distance``'s other copy of the sentinel -- its answer when
        it has no terms to mean over -- is **not** covered by the sweep above.

        Measured: flipping that branch back to 1.0 leaves the whole suite
        green, because no constituent reaches it. Every bundle is assembled
        ``with_defaults=True`` and the inventory declares enough defaulting
        features that even an unregistered base comes back with a dozen keys,
        so the branch is unreachable today. This asserts the reason rather
        than the consequence: if a constituent ever does present an empty
        comparable form, this fails and the branch starts being observed --
        at which point it answers 0.0, because having nothing to compare on
        is what identity looks like from inside, not maximal difference.
        """
        from ipakit.metric import _metric_bundle

        checked = 0
        for unit in single_mark_units()[::11]:
            for constituent in ipa.segment(unit).constituents:
                feats, components = _metric_bundle(ipa, constituent)
                assert feats or components, f"{unit} has no comparable form"
                checked += 1
        assert checked > 500, f"sweep checked only {checked} constituents"

    def test_an_empty_comparable_bundle_is_identity_not_maximal(
        self, ipa: IPAFeatures
    ) -> None:
        """The sentinel branch itself, reached directly.

        It fires only when *both* sides carry no comparable key, and then
        neither holds anything the other lacks. The case it used to be
        written for -- one side comparable and the other not -- never reaches
        it: those keys are present on one side only, each scores 1, and the
        mean is 1.0 without anything being asserted.
        """
        assert ipa._feature_dict_distance({}, {}) == 0.0
        assert ipa._feature_dict_distance({}, {"voiced": "+"}) == 1.0
        assert ipa._feature_dict_distance({"voiced": "+"}, {}) == 1.0
        assert ipa._feature_dict_distance({"voiced": "+"}, {"voiced": "+"}) == 0.0
