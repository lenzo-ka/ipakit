"""Stress: which unit a mark binds, and moving marks between conventions.

Two things live here. ``normalize_stress_to_nucleus`` moves IPA-dict-style
syllable-initial stress (``ˈhɛ.ləʊ``) to ipakit's nucleus convention
(``hˈɛ.ləʊ``) and ``normalize_stress_to_syllable`` is the inverse, for
output; these are standalone utilities -- the CMU mapper resolves stress
placement on its own, so they are not part of the conversion pipeline.

Below them is the positional sweep. A stress mark binds the unit that
*follows* it, and it used to do so only at the start of a string: anywhere
else the parser swept it up as a trailing modifier of the base just read,
and ``Segment.to_ipa`` then re-emitted it in front of *that* base, walking
the mark one unit to the left. In ``ˌɪntəˈneɪʃənəl`` that moved primary
stress onto a different syllable. Every named stress test in the suite was
either word-initial -- the one position where a leftward bind is invisible,
there being no unit to the left -- or a normalization fixture that compared
strings and never asked which unit carried the mark. Hence a sweep over
positions rather than another named case.
"""

from __future__ import annotations

import warnings

import pytest
from ipakit import IPAFeatures


class TestStressToNucleus:
    @pytest.mark.parametrize(
        "src,expected",
        [
            ("ˈhɛ.ləʊ", "hˈɛ.ləʊ"),  # stress moves onto the nucleus, break kept
            ("ˈɛ.ləʊ", "ˈɛ.ləʊ"),  # already before the nucleus (no onset)
            ("ˌɪn.təˈnæʃ", "ˌɪn.tə.nˈæʃ"),  # secondary + primary
            ("ˈkæt", "kˈæt"),  # single syllable
            ("ˈpi.tsə", "pˈi.tsə"),
        ],
    )
    def test_examples(self, ipa: IPAFeatures, src: str, expected: str) -> None:
        assert ipa.normalize_stress_to_nucleus(src) == expected

    def test_no_stress_unchanged(self, ipa: IPAFeatures) -> None:
        assert ipa.normalize_stress_to_nucleus("kæt") == "kæt"
        assert ipa.normalize_stress_to_nucleus("wɔtɚ") == "wɔtɚ"


class TestStressToSyllable:
    def test_strips_breaks_by_default(self, ipa: IPAFeatures) -> None:
        assert ipa.normalize_stress_to_syllable("hˈɛ.ləʊ") == "ˈhɛləʊ"
        assert ipa.normalize_stress_to_syllable("kˈæt") == "ˈkæt"

    def test_keep_syllables(self, ipa: IPAFeatures) -> None:
        assert (
            ipa.normalize_stress_to_syllable("hˈɛ.ləʊ", keep_syllables=True)
            == "ˈhɛ.ləʊ"
        )

    def test_no_stress(self, ipa: IPAFeatures) -> None:
        assert ipa.normalize_stress_to_syllable("kæt") == "kæt"


class TestStressRoundTrip:
    @pytest.mark.parametrize(
        "src", ["ˈhɛ.ləʊ", "ˈɛ.ləʊ", "ˌɪn.təˈnæʃ", "ˈkæt", "ˈpi.tsə"]
    )
    def test_nucleus_then_syllable_recovers_source(
        self, ipa: IPAFeatures, src: str
    ) -> None:
        # Syllable-initial stress survives a round trip when breaks are kept.
        nucleus = ipa.normalize_stress_to_nucleus(src)
        assert ipa.normalize_stress_to_syllable(nucleus, keep_syllables=True) == src


class TestStressBindsTheFollowingNucleus:
    """Written position is spelling; the first following nucleus is scope."""

    @pytest.mark.parametrize(
        "text,index,mark",
        [
            ("ˈkæt", 1, "ˈ"),
            ("ˈæt", 0, "ˈ"),  # initial, onto a bare nucleus
            ("kˈæt", 1, "ˈ"),  # medial -- the house nucleus spelling
            ("abaˈba", 4, "ˈ"),
            ("ˈt͡ʃe͜ɪnd͡ʒ", 1, "ˈ"),
            ("t͡ʃˈe͜ɪnd͡ʒ", 1, "ˈ"),  # before a tie chain
            ("t̪ˈa", 1, "ˈ"),  # after a diacritic-bearing base
            ("aˈt̪a", 2, "ˈ"),
            ("ˌkæt", 1, "ˌ"),
            ("kˌæt", 1, "ˌ"),  # secondary, medial
            ("aˌt͡ʃa", 2, "ˌ"),
            ("ˈn̩", 0, "ˈ"),  # a syllabic consonant is a nucleus
        ],
    )
    def test_the_mark_lands_on_the_first_following_nucleus(
        self, ipa: IPAFeatures, text: str, index: int, mark: str
    ) -> None:
        form = ipa.read(text, strict=True)
        carriers = [
            i for i, unit in enumerate(form.units) if mark in unit.segment.prosody
        ]
        assert carriers == [index], [unit.text for unit in form.units]
        assert form.to_ipa() == text

    def test_both_marks_in_one_word(self, ipa: IPAFeatures) -> None:
        # The reported case. Primary stress belongs to the "neɪ" syllable;
        # binding leftward put it on the schwa of "-tə-", a different
        # syllable, while to_cmu (which routes through
        # normalize_stress_to_nucleus) had it right all along.
        word = "ˌɪntəˈneɪʃənəl"
        segs = ipa.segments(word, strict=True)
        spelled = [s.to_ipa() for s in segs]
        assert spelled[0] == "ˌɪ"
        assert spelled[4] == "n"
        assert spelled[5] == "ˈe"
        assert [s.prosody for s in segs].count(("ˈ",)) == 1
        assert ipa.read(word, strict=True).to_ipa() == word

    def test_a_nearer_mark_supersedes_before_the_nucleus(
        self, ipa: IPAFeatures
    ) -> None:
        with pytest.warns(UserWarning, match="superseded"):
            segs = ipa.segments("ˌbˈa")
        assert [s.prosody for s in segs] == [(), ("ˈ",)]


class TestOnlyStressBindsRightward:
    """The crux: stopping the modifier run at *stress* is not the same as
    stopping it at every prosodic mark. Length, tone and contour are
    written after the segment they scope, so they are trailing modifiers
    of the unit just read; stress is the one written before its domain."""

    @pytest.mark.parametrize(
        "text,mark", [("eː", "ː"), ("aˑ", "ˑ"), ("a˥", "˥"), ("ǎ", "̌")]
    )
    def test_the_other_prosody_still_binds_leftward(
        self, ipa: IPAFeatures, text: str, mark: str
    ) -> None:
        segs = ipa.segments(text, strict=True)
        assert len(segs) == 1, [s.to_ipa() for s in segs]
        assert mark in segs[0].prosody
        assert ipa.to_ipa(segs) == text

    def test_a_leftward_mark_is_not_split_off_its_base(self, ipa: IPAFeatures) -> None:
        # If the modifier run stopped at every prosodic mark, the length
        # of "eː" would become a token of its own, carry no unit, and be
        # dropped -- so "eː" would read as plain "e".
        assert ipa.tokenize("eː") == ["eː"]
        assert ipa.compose("eː")[0]["length"] == "long"

    def test_both_directions_in_one_unit(self, ipa: IPAFeatures) -> None:
        seg = ipa.segment("ˈeː", strict=True)
        assert seg.prosody == ("ˈ", "ː")
        assert seg.to_ipa() == "ˈeː"


class TestAStressMarkThatReachesNoUnit:
    """A registered mark that binds nothing is reported, never dropped in
    silence -- the contract an unbound tie already has."""

    def test_a_unit_bears_one_stress_level_and_the_nearest_binds(
        self, ipa: IPAFeatures
    ) -> None:
        with pytest.warns(UserWarning, match="superseded"):
            segs = ipa.segments("ˌˈa")
        assert [s.prosody for s in segs] == [("ˈ",)]
        with pytest.warns(UserWarning, match="superseded"):
            segs = ipa.segments("ˈˌa")
        assert [s.prosody for s in segs] == [("ˌ",)]

    def test_a_trailing_mark_binds_nothing(self, ipa: IPAFeatures) -> None:
        with pytest.warns(UserWarning, match="unbound"):
            segs = ipa.segments("aˈ")
        assert [s.prosody for s in segs] == [()]

    def test_a_leading_mark_with_no_nucleus_binds_nothing(
        self, ipa: IPAFeatures
    ) -> None:
        with pytest.warns(UserWarning, match="unbound"):
            form = ipa.read("ˈpst")
        assert [s.prosody for s in form.segments] == [(), (), ()]
        assert form.to_ipa() == "ˈpst"
        with pytest.raises(ValueError, match="unbound stress"):
            ipa.read("ˈpst", strict=True)

    @pytest.mark.parametrize("text", ["ˌˈa", "ˈˌa", "aˈ"])
    def test_strict_raises_instead(self, ipa: IPAFeatures, text: str) -> None:
        with pytest.raises(ValueError, match="stress"):
            ipa.segments(text, strict=True)

    @pytest.mark.parametrize(
        "text,code", [("ˌˈa", "superseded_stress"), ("aˈ", "unbound_stress")]
    )
    def test_the_validator_names_the_same_two_mistakes(
        self, ipa: IPAFeatures, text: str, code: str
    ) -> None:
        assert code in [i["code"] for i in ipa.validate_ipa(text)]

    def test_a_well_formed_string_reports_nothing(self, ipa: IPAFeatures) -> None:
        for text in ("ˈkæt", "kˈæt", "ˌɪntəˈneɪʃənəl", "ˈ.a", "ˈ a"):
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                ipa.segments(text, strict=True)
            assert not ipa.validate_ipa(text), text

    def test_the_unit_level_refuses_two_stress_levels(self, ipa: IPAFeatures) -> None:
        # Same rule where a Segment is built from intent rather than parsed.
        with pytest.raises(ValueError, match="one stress level"):
            ipa.build_segment(["a"], prosody=("ˈ", "ˌ"))


class TestTheNormalizersAndTheBindingAgree:
    """The library moves stress marks about deliberately; the unit a mark
    lands on has to be the unit it was moved to."""

    @pytest.mark.parametrize("src", ["ˈhɛloʊ", "ˈkæt", "ˌɪntəˈneɪʃənəl", "ˈpitsə"])
    def test_nucleus_form_puts_the_mark_on_a_nucleus(
        self, ipa: IPAFeatures, src: str
    ) -> None:
        # The house form's own claim. Before the fix
        # normalize_stress_to_nucleus("ˈhɛloʊ") gave "hˈɛloʊ" and the very
        # next parse bound the mark to the onset "h".
        moved = ipa.strip_syllable_breaks(ipa.normalize_stress_to_nucleus(src))
        for seg in ipa.segments(moved, strict=True):
            if not any(m in ipa.stress_markers for m in seg.prosody):
                continue
            # Spelled out rather than asking IPAFeatures.is_nucleus,
            # deliberately: this is the independent statement the
            # normalizer is checked against, and reading it back out of
            # the code under test would make the check agree with itself.
            feats = seg.scalar()
            assert feats.get("manner") == "vowel" or feats.get("syllabic") == "+", (
                src,
                seg.to_ipa(),
            )

    def test_the_normalizer_and_the_derived_class_are_one_read(
        self, ipa: IPAFeatures
    ) -> None:
        """What a nucleus is decides two different things -- where a
        stress mark lands, and which features a description reads out --
        and until now each decided it from its own copy of the predicate.
        Nothing pinned the equality, so a correction to either (a
        syllabic consonant reached, a manner added) would have moved one
        answer and left the other.

        Swept over the inventory, through the two public answers rather
        than through the shared call, so this still measures something if
        one of them grows a special case.
        """
        nucleus_only = [
            name
            for name, feature in ipa.features.items()
            if feature.applies == frozenset({"nucleus"})
        ]
        assert nucleus_only, "no feature declares applies='nucleus'; sweep is vacuous"
        verdicts, disagreed = [], []
        for symbol, phone in ipa.phones.items():
            if len(symbol) != 1 or symbol in ipa.diacritics:
                continue
            # The normalizer's answer: a syllable-initial mark walks
            # across the onset and stops on the nucleus.
            moved = ipa.normalize_stress_to_nucleus("ˈb" + symbol)
            by_normalizer = moved == "bˈ" + symbol
            verdicts.append(by_normalizer)
            for feature in nucleus_only:
                if ipa.feature_applies(feature, phone.features) != by_normalizer:
                    disagreed.append((symbol, feature, moved))
        assert len(verdicts) > 50, "sweep did not run"
        # Both answers occur, so agreement is not two constants agreeing.
        assert any(verdicts) and not all(verdicts)
        assert not disagreed, disagreed[:5]

    @pytest.mark.parametrize("src", ["ˈhɛloʊ", "ˈkæt", "ˌɪntəˈneɪʃənəl"])
    def test_the_normalizers_still_round_trip(self, ipa: IPAFeatures, src: str) -> None:
        nucleus = ipa.normalize_stress_to_nucleus(src)
        assert ipa.normalize_stress_to_syllable(nucleus) == src
        # Form retains the written position independently of the carrier.
        assert ipa.read(src, strict=True).to_ipa() == src
        stripped = ipa.strip_syllable_breaks(nucleus)
        assert ipa.to_ipa(ipa.segments(stripped, strict=True)) == stripped
