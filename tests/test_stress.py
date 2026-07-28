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

import unicodedata
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


class TestStressBindsTheUnitThatFollowsIt:
    """The mark binds rightward, in every position, not only initially."""

    @pytest.mark.parametrize(
        "text,index,mark",
        [
            ("ˈkæt", 0, "ˈ"),  # initial, onto an onset consonant
            ("ˈæt", 0, "ˈ"),  # initial, onto a bare nucleus
            ("kˈæt", 1, "ˈ"),  # medial -- the house nucleus spelling
            ("hˈɛloʊ", 1, "ˈ"),  # medial, what normalize_stress_to_nucleus emits
            ("abaˈba", 3, "ˈ"),  # medial, deep in the string
            ("ˈt͡ʃe͜ɪnd͡ʒ", 0, "ˈ"),  # initial, onto a tie chain
            ("t͡ʃˈe͜ɪnd͡ʒ", 1, "ˈ"),  # before a tie chain
            ("t̪ˈa", 1, "ˈ"),  # after a diacritic-bearing base
            ("aˈt̪a", 1, "ˈ"),  # before a diacritic-bearing base
            ("ˌkæt", 0, "ˌ"),  # secondary, initial
            ("kˌæt", 1, "ˌ"),  # secondary, medial
            ("aˌt͡ʃa", 1, "ˌ"),  # secondary, before a tie chain
        ],
    )
    def test_the_mark_lands_on_the_next_unit(
        self, ipa: IPAFeatures, text: str, index: int, mark: str
    ) -> None:
        segs = ipa.segments(text, strict=True)
        carriers = [i for i, s in enumerate(segs) if mark in s.prosody]
        assert carriers == [index], [s.to_ipa() for s in segs]
        # And the join puts it back where it was written.
        assert ipa.to_ipa(segs) == text

    # Words that round-trip with no stress in them, so inserting a mark at
    # a boundary is the only difference the assertions can see.
    WORDS = [
        "kæt",
        "hɛloʊ",
        "t͡ʃe͜ɪnd͡ʒ",
        "ɪntəneɪʃənəl",
        "t̪at̪a",
        "aeːo",
        "wɔtɚ",
        "pʃɑ",
        "ka˥ta",
        "sɪstəmætɪk",
        "ɡɹæmpəs",
        "fəʊnɛtɪk",
    ]

    def test_every_boundary_in_every_word(self, ipa: IPAFeatures) -> None:
        """A mark inserted at each unit boundary binds the unit after it.

        The sweep the named cases above are a readable sample of: the
        defect was positional, so the guard has to be too.
        """
        checked = 0
        for word in self.WORDS:
            units = ipa.segments(word, strict=True)
            spellings = [u.to_ipa() for u in units]
            assert "".join(spellings) == word, word
            for mark in ("ˈ", "ˌ"):
                for k in range(len(units)):
                    text = unicodedata.normalize(
                        "NFC", "".join(spellings[:k]) + mark + "".join(spellings[k:])
                    )
                    segs = ipa.segments(text, strict=True)
                    assert [s.to_ipa() for s in segs] == [
                        mark + sp if i == k else sp for i, sp in enumerate(spellings)
                    ], text
                    assert [s.prosody for s in segs] == [
                        (mark,) + u.prosody if i == k else u.prosody
                        for i, u in enumerate(units)
                    ], text
                    assert ipa.to_ipa(segs) == text, text
                    checked += 1
        assert checked > 100, "sweep did not run"

    def test_both_marks_in_one_word(self, ipa: IPAFeatures) -> None:
        # The reported case. Primary stress belongs to the "neɪ" syllable;
        # binding leftward put it on the schwa of "-tə-", a different
        # syllable, while to_cmu (which routes through
        # normalize_stress_to_nucleus) had it right all along.
        word = "ˌɪntəˈneɪʃənəl"
        segs = ipa.segments(word, strict=True)
        spelled = [s.to_ipa() for s in segs]
        assert spelled[0] == "ˌɪ"
        assert spelled[4] == "ˈn"
        assert [s.prosody for s in segs].count(("ˈ",)) == 1
        assert ipa.to_ipa(segs) == word

    def test_the_two_marks_do_not_pile_onto_one_unit(self, ipa: IPAFeatures) -> None:
        segs = ipa.segments("ˌaˈb", strict=True)
        assert [s.prosody for s in segs] == [("ˌ",), ("ˈ",)]
        assert ipa.to_ipa(segs) == "ˌaˈb"


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
            feats = seg.scalar()
            assert feats.get("manner") == "vowel" or feats.get("syllabic") == "+", (
                src,
                seg.to_ipa(),
            )

    @pytest.mark.parametrize("src", ["ˈhɛloʊ", "ˈkæt", "ˌɪntəˈneɪʃənəl"])
    def test_the_normalizers_still_round_trip(self, ipa: IPAFeatures, src: str) -> None:
        nucleus = ipa.normalize_stress_to_nucleus(src)
        assert ipa.normalize_stress_to_syllable(nucleus) == src
        # And each spelling survives segments -> to_ipa as written.
        assert ipa.to_ipa(ipa.segments(src, strict=True)) == src
        stripped = ipa.strip_syllable_breaks(nucleus)
        assert ipa.to_ipa(ipa.segments(stripped, strict=True)) == stripped
