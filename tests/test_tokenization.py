"""Tests for IPA tokenization and normalization."""

import unicodedata
import warnings

import ipakit
import pytest
from ipakit import IPAFeatures
from ipakit.constants import MAX_MATCH_LEN

from tests.corpus import TIES


class TestTokenizerRobustness:
    """The tokenizer must never raise on adversarial input (non-strict)."""

    _ADVERSARIAL = [
        "",
        " ",
        "͡",  # lone tie bar
        "͡͡͡",  # stacked tie bars
        "̃",  # lone combining mark (nasalization)
        "ppppp͡",  # trailing tie bar
        "kæt" * 500,  # long input
        "k͡͡t",  # ties mid-word
        "4@#$%",  # all non-IPA
        "p̃̃̃",  # stacked diacritics
        "ǃǂǀ",  # clicks (may be unknown)
        "\U0001f600",  # emoji
    ]

    def test_tokenize_never_raises(self, ipa: IPAFeatures) -> None:
        for s in self._ADVERSARIAL:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                tokens = ipa.tokenize(s)
            assert isinstance(tokens, list)

    def test_parse_never_raises_nonstrict(self, ipa: IPAFeatures) -> None:
        for s in self._ADVERSARIAL:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result = ipa.parse(s)
            assert isinstance(result, list)


class TestParseStrict:
    """Tests for the strict= policy on parse()."""

    def test_parse_drops_unknown_by_default(self, ipa: IPAFeatures) -> None:
        # Non-strict: unmatched '4' is dropped -- but audibly, not silently.
        with pytest.warns(UserWarning, match=r"unregistered symbol\(s\) \['4'\]"):
            assert ipa.parse("k4t") == [("k", []), ("t", [])]

    def test_separators_are_known_not_unknown(self, ipa: IPAFeatures) -> None:
        # The syllable break and whitespace are registered marks that carry
        # no unit. They are not "unknown symbols" and must not trip strict.
        assert ipa.parse("kæ.t", strict=True) == ipa.parse("kæt", strict=True)
        assert ipa.tokenize("kæt dɒɡ", strict=True) == list("kætdɒɡ")
        assert ipakit.word_distance("kæ.t", "kæt").edit_cost == 0.0

    def test_parse_strict_raises_on_unknown(self, ipa: IPAFeatures) -> None:
        with pytest.raises(ValueError, match="4"):
            ipa.parse("k4t", strict=True)

    def test_parse_strict_ok_on_valid(self, ipa: IPAFeatures) -> None:
        # Valid input parses identically with strict=True.
        assert ipa.parse("kat", strict=True) == ipa.parse("kat")


class TestTokenization:
    """Tests for IPA tokenization."""

    def test_tokenize_simple(self, ipa: IPAFeatures) -> None:
        tokens = ipa.tokenize("pat")
        assert tokens == ["p", "a", "t"]

    def test_tokenize_with_diacritics(self, ipa: IPAFeatures) -> None:
        tokens = ipa.tokenize("pʰat")
        assert tokens == ["pʰ", "a", "t"]

    def test_tokenize_affricates(self, ipa: IPAFeatures) -> None:
        tokens = ipa.tokenize("t͡ʃ")
        assert tokens == ["t͡ʃ"]

    def test_tokenize_legacy_affricate(self, ipa: IPAFeatures) -> None:
        # Legacy ligature should be expanded then tokenized as single unit
        tokens = ipa.tokenize("ʧ")
        assert tokens == ["t͡ʃ"]

    def test_tokenize_multiple_diacritics(self, ipa: IPAFeatures) -> None:
        # Phone with multiple diacritics
        tokens = ipa.tokenize("pʰʲ")
        assert len(tokens) == 1
        assert tokens[0] == "pʰʲ"

    def test_tokenize_long_vowel(self, ipa: IPAFeatures) -> None:
        tokens = ipa.tokenize("iː")
        assert tokens == ["iː"]

    def test_tokenize_nasalized_vowel(self, ipa: IPAFeatures) -> None:
        # IPA nasalization uses combining tilde (U+0303); tokens are emitted
        # in NFC, so both input forms yield the precomposed token.
        nasalized_a = "a\u0303"  # a + combining tilde
        precomposed_a = "\u00e3"  # \u00e3
        assert ipa.tokenize(nasalized_a) == [precomposed_a]
        assert ipa.tokenize(precomposed_a) == [precomposed_a]


class TestSegmentation:
    """Tests for IPA segmentation (space-separated output)."""

    def test_segment_simple(self, ipa: IPAFeatures) -> None:
        result = ipa.segmented("pat")
        assert result == "p a t"

    def test_segment_with_diacritics(self, ipa: IPAFeatures) -> None:
        result = ipa.segmented("pʰat")
        assert result == "pʰ a t"

    def test_segment_affricates(self, ipa: IPAFeatures) -> None:
        result = ipa.segmented("t͡ʃat")
        assert "t͡ʃ" in result


class TestLigatureExpansion:
    """Tests for legacy ligature expansion."""

    def test_expand_legacy_ligatures(self, ipa: IPAFeatures) -> None:
        assert ipa.expand_ligatures("ʧ") == "t͡ʃ"
        assert ipa.expand_ligatures("ʤ") == "d͡ʒ"
        assert ipa.expand_ligatures("ʦ") == "t͡s"

    def test_expand_preserves_modern(self, ipa: IPAFeatures) -> None:
        assert ipa.expand_ligatures("t͡ʃ") == "t͡ʃ"

    def test_under_tie_spelling_is_its_own_object(self, ipa: IPAFeatures) -> None:
        # Strict glyph authority: t͜s is a sequential chain, not a spelling
        # of the affricate. Wild text imports via from_wild.
        assert ipa.expand_ligatures("t͜s") == "t͜s"
        assert ipa.tokenize("t͜s") == ["t͜s"]
        assert ipa.from_wild("t͜s") == "t͡s"


class TestNormalization:
    """Tests for IPA normalization."""

    def test_normalize_adds_ties(self, ipa: IPAFeatures) -> None:
        # Consonant pairs fuse (over-tie); adjacent vowels bind sequentially
        # (under-tie) - which is the canonical diphthong spelling directly.
        result = ipa.normalize(["tʃ", "eɪ", "n", "dʒ"])
        assert "t͡ʃ" in result
        assert "e͜ɪ" in result
        assert "d͡ʒ" in result
        # The same phones as one string are NOT split on the spaces: a
        # space here is the word separator, so reading it as a phone
        # separator would invent ties and eat a boundary.
        assert ipa.normalize("tʃ eɪ n dʒ") == "tʃ eɪ n dʒ"
        # Naming the delimiter makes that claim explicitly, and is then
        # the same request as handing over the sequence.
        assert ipa.normalize("tʃ eɪ n dʒ", delimiter=" ") == result
        assert ipa.get_phone("e͜ɪ") is not None

    def test_add_tie_bars(self, ipa: IPAFeatures) -> None:
        assert ipa.add_ties("ts") == "t͡s"
        assert ipa.add_ties("dz") == "d͡z"

    def test_add_tie_bars_preserves_existing(self, ipa: IPAFeatures) -> None:
        assert ipa.add_ties("t͡s") == "t͡s"


class TestLookalikes:
    """The ASCII soft reads: explicit tool, never the default path."""

    def test_lookalikes_loaded(self, ipa: IPAFeatures) -> None:
        assert ipa.lookalikes == {"g": "ɡ", ":": "ː", "?": "ʔ", "'": "ˈ"}

    def test_normalize_g(self, ipa: IPAFeatures) -> None:
        # Keyboard g (U+0067) should become IPA ɡ (U+0261)
        result = ipa.normalize_lookalikes("gat")
        assert result == "ɡat"
        assert result[0] == "\u0261"  # IPA script g

    def test_normalize_colon(self, ipa: IPAFeatures) -> None:
        # Keyboard : should become IPA ː (triangular colon)
        result = ipa.normalize_lookalikes("pa:t")
        assert "ː" in result

    def test_normalize_apostrophe_is_stress_not_ejective(
        self, ipa: IPAFeatures
    ) -> None:
        # ASCII ' reads as PRIMARY STRESS (U+02C8), the dominant wild
        # convention (kirshenbaum.xml agrees), not the ejective U+02BC.
        assert ipa.normalize_lookalikes("p'a") == "pˈa"
        assert "ʼ" not in ipa.normalize_lookalikes("p'a")

    def test_normalize_question_mark(self, ipa: IPAFeatures) -> None:
        # Keyboard ? should become IPA ʔ (glottal stop)
        result = ipa.normalize_lookalikes("a?a")
        assert "ʔ" in result

    def test_exclamation_is_not_soft_read(self, ipa: IPAFeatures) -> None:
        # Click, downstep and punctuation are all live readings; ipakit
        # refuses to pick one, so "!" is not in the table at all.
        assert "!" not in ipa.lookalikes
        assert ipa.normalize_lookalikes("kæt!") == "kæt!"
        assert ipa.from_wild("kæt!") == "kæt!"
        # Both readings stay writable, and are distinct.
        assert ipa.get_phone("ǃ") is not None
        assert "ꜜ" in ipa.diacritics

    def test_expand_ligatures_leaves_soft_reads_alone(self, ipa: IPAFeatures) -> None:
        # Default parsing is strict house style: no soft reads applied.
        assert ipa.expand_ligatures("gat") == "gat"
        assert ipa.expand_ligatures("pa:t") == "pa:t"


class TestSoftReadsAreExplicit:
    """Default parsing never rewrites ASCII; from_wild is the door."""

    @pytest.mark.parametrize("char", ["g", "'", ":", "?", "!"])
    def test_default_parsing_does_not_rewrite(self, char: str) -> None:
        text = f"kæt{char}"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            tokens = ipakit.tokenize(text)
        assert char not in "".join(tokens)  # dropped, never substituted
        for wrong in ("ɡ", "ʼ", "ˈ", "ː", "ʔ", "ǃ"):
            assert wrong not in "".join(tokens)

    def test_punctuation_is_not_a_consonant(self) -> None:
        # The defect this fixes: ASCII "!" became U+01C3 RETROFLEX CLICK.
        with pytest.warns(UserWarning):
            assert ipakit.tokenize("kæt!") == ["k", "æ", "t"]
        assert not ipakit.is_valid_ipa("kæt!")
        with pytest.raises(ValueError, match="!"):
            ipakit.tokenize("kæt!", strict=True)

    def test_from_wild_applies_the_soft_reads(self) -> None:
        assert ipakit.from_wild("'gu:d") == "ˈɡuːd"
        assert ipakit.from_wild("a?a") == "aʔa"
        assert ipakit.is_valid_ipa(ipakit.from_wild("'gu:d"))

    def test_from_wild_leaves_house_style_alone(self) -> None:
        for text in ["ˈɡuːd", "t͡ʃa͜ɪ", "kæt"]:
            assert ipakit.from_wild(text) == text


class TestUnknownSymbolsAreNotSilent:
    """A stray character never vanishes without a word."""

    def test_unknown_warns_by_default(self) -> None:
        with pytest.warns(UserWarning, match=r"unregistered symbol\(s\) \['Q'\]"):
            assert ipakit.tokenize("kæQt") == ["k", "æ", "t"]

    def test_unknown_raises_when_strict(self) -> None:
        for call in (
            lambda: ipakit.tokenize("kæQt", strict=True),
            lambda: ipakit.segmented("kæQt", strict=True),
            lambda: ipakit.segments("kæQt", strict=True),
            lambda: ipakit.segment("Q", strict=True),
        ):
            with pytest.raises(ValueError, match=r"unknown symbols \['Q'\]"):
                call()

    def test_whole_word_of_non_ipa_does_not_return_empty_quietly(self) -> None:
        with pytest.warns(UserWarning):
            assert ipakit.tokenize("NOTAPHONE") == []
        with pytest.raises(ValueError):
            ipakit.tokenize("NOTAPHONE", strict=True)

    def test_round_trip_holds_or_fails_loudly(self) -> None:
        # Holds for house-style input...
        for text in ["kæt", "t͡ʃe͜ɪnd͡ʒ", "ɡˈuːd"]:
            assert ipakit.to_ipa(ipakit.segments(text, strict=True)) == text
        # ...and where it cannot hold, strict says so rather than
        # returning a shorter, well-formed-looking string.
        with pytest.raises(ValueError):
            ipakit.segments("kæQt", strict=True)
        with pytest.warns(UserWarning):
            assert ipakit.to_ipa(ipakit.segments("kæQt")) != "kæQt"


class TestCompose:
    """Tests for composing features from phone + diacritics."""

    def test_compose_simple(self, ipa: IPAFeatures) -> None:
        bundles = ipa.compose("p")
        assert len(bundles) == 1
        assert bundles[0]["manner"] == "plosive"

    def test_compose_with_diacritic(self, ipa: IPAFeatures) -> None:
        bundles = ipa.compose("pʰ")
        assert len(bundles) == 1
        assert bundles[0]["manner"] == "plosive"
        assert bundles[0]["release"] == "aspirated"

    def test_compose_multi_segment(self, ipa: IPAFeatures) -> None:
        bundles = ipa.compose("pat")
        assert len(bundles) == 3
        assert bundles[0]["manner"] == "plosive"
        assert bundles[1]["manner"] == "vowel"
        assert bundles[2]["manner"] == "plosive"

    def test_compose_preserves_class(self, ipa: IPAFeatures) -> None:
        # Composed segment should retain phone class, not diacritic class
        bundles = ipa.compose("pʰ")
        assert bundles[0]["class"] == "phone"

    def test_compose_voicing_diacritics(self, ipa: IPAFeatures) -> None:
        # Devoicing diacritic should set voiced to -
        bundles = ipa.compose("b̥")  # devoiced b
        assert bundles[0]["voiced"] == "-"

    def test_compose_segments_aligns_tokens(self, ipa: IPAFeatures) -> None:
        # Featureless markers (stress, syllable break) are dropped, so each
        # token lines up with its own feature bundle -- not the next one.
        segs = ipa.compose_segments("ˈkæt.dɒɡ")
        assert [t for t, _ in segs] == ["k", "æ", "t", "d", "ɒ", "ɡ"]
        by_token = dict(segs)
        assert by_token["k"]["manner"] == "plosive"
        assert by_token["æ"]["manner"] == "vowel"
        # Features stay in sync with compose().
        assert [f for _, f in segs] == ipa.compose("ˈkæt.dɒɡ")


# A spread of modifier marks across the contribution modes: place shifts,
# release marks, secondary articulations, overriding marks, additive marks
# and one prosodic mark. Written after a base, each makes a constituent that
# is not itself a registered phone -- which is exactly what used to break a
# following tie.
MODIFIERS = [
    "\u032a",  # dental (place override)
    "\u02b0",  # aspirated (release)
    "\u02b7",  # labialized (secondary)
    "\u02b2",  # palatalized (secondary)
    "\u0303",  # nasalized (additive)
    "\u0325",  # voiceless ring (overriding)
    "\u02e0",  # velarized (secondary)
    "\u032f",  # non-syllabic (overriding)
    "\u02d0",  # length (prosodic)
    "\u02bc",  # ejective
    "\u0320",  # retracted
    "\u031f",  # advanced
    "\u02de",  # rhoticity
    "\u0324",  # breathy voice
    "\u0330",  # creaky voice
    "\u033c",  # linguolabial
    "\u02e4",  # pharyngealized
]

TIE_CASES = [
    (mark, tie, pair)
    for mark in MODIFIERS
    for tie in sorted(TIES)
    for pair in (("t", "s"), ("k", "p"), ("a", "i"))
]


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


class TestTieBindsTheWholeUnit:
    """A tie joins the unit before it to the unit after it.

    A base plus the modifiers written on it is one constituent, so a tie
    that follows a diacritic binds just as one that follows a bare base
    does. It used to be dropped instead -- silently, because the tie is a
    registered diacritic and so never counted as an unknown symbol --
    turning ``t̪͡s`` into the two-segment cluster ``t̪s``.
    """

    @pytest.mark.parametrize("mark,tie,pair", TIE_CASES)
    def test_modifier_then_tie_is_one_unit(
        self, ipa: IPAFeatures, mark: str, tie: str, pair: tuple[str, str]
    ) -> None:
        left, right = pair
        text = left + mark + tie + right
        assert ipa.tokenize(text, strict=True) == [_nfc(text)]
        assert len(ipa.segment(text, strict=True).constituents) == 2

    @pytest.mark.parametrize("mark,tie,pair", TIE_CASES)
    def test_control_tie_then_modifier_is_one_unit(
        self, ipa: IPAFeatures, mark: str, tie: str, pair: tuple[str, str]
    ) -> None:
        # The shape that always worked: the tie sits between bare bases.
        left, right = pair
        text = left + tie + right + mark
        assert ipa.tokenize(text, strict=True) == [_nfc(text)]
        assert len(ipa.segment(text, strict=True).constituents) == 2

    @pytest.mark.parametrize("mark,tie,pair", TIE_CASES)
    def test_round_trip_under_strict(
        self, ipa: IPAFeatures, mark: str, tie: str, pair: tuple[str, str]
    ) -> None:
        # The advertised guarantee: to_ipa(segments(x, strict=True)) == x.
        text = pair[0] + mark + tie + pair[1]
        assert _nfc(ipakit.to_ipa(ipa.segments(text, strict=True))) == _nfc(text)

    @pytest.mark.parametrize("text", ["t̪͡s", "kʷ͡p", "ã͜i", "tʰ͡s"])
    def test_levels_agree_on_one_string(self, ipa: IPAFeatures, text: str) -> None:
        # The flat and structured reads must describe the same object.
        assert ipa.tokenize(text, strict=True) == [_nfc(text)]
        assert len(ipa.segments(text, strict=True)) == 1
        assert _nfc(ipa.segment(text, strict=True).to_ipa()) == _nfc(text)
        assert text in ipa
        assert ipa.get_features(text)
        assert ipa.compose(text) == [ipa.get_features(text)]

    def test_the_modifier_stays_on_its_own_constituent(self, ipa: IPAFeatures) -> None:
        unit = ipa.segment("kʷ͡p", strict=True)
        assert [str(c) for c in unit.constituents] == ["kʷ", "p"]
        assert unit.bag()["labialized"] == ("+", "-")
        assert ipa.segment("t̪͡s", strict=True).left_features()["place"] == "dental"

    def test_dental_affricate_is_not_a_cluster(self, ipa: IPAFeatures) -> None:
        assert ipa.tokenize("t̪͡s", strict=True) != ipa.tokenize("t̪s", strict=True)
        assert ipa.segment("t̪͡s", strict=True).kind == "affricate"

    def test_modifiers_bind_through_an_n_ary_chain(self, ipa: IPAFeatures) -> None:
        unit = ipa.segment("t̪͡s̪͜a", strict=True)
        assert [str(c) for c in unit.constituents] == ["t̪", "s̪", "a"]
        assert _nfc(unit.to_ipa()) == _nfc("t̪͡s̪͜a")

    def test_double_tie_after_a_modifier_still_collapses(
        self, ipa: IPAFeatures
    ) -> None:
        # Both ties on one juncture assert contradictory timing; the
        # over-tie wins, whether or not a diacritic precedes the pair.
        assert ipa.tokenize("t̪͜͡s", strict=True) == ipa.tokenize("t̪͡s", strict=True)

    def test_from_wild_re_senses_across_a_modifier(self, ipa: IPAFeatures) -> None:
        # The wild re-sensing already looked past diacritics; now the
        # result it produces is also parseable as one unit.
        assert _nfc(ipa.from_wild("t̪͜s")) == _nfc("t̪͡s")
        assert _nfc(ipa.from_wild("ã͡i")) == _nfc("ã͜i")
        assert ipa.tokenize(ipa.from_wild("t̪͜s"), strict=True) == [_nfc("t̪͡s")]


class TestUnboundTieIsNotSilent:
    """A structural mark that cannot be carried must be audible.

    A tie that binds nothing carries no juncture, so it is dropped -- and
    dropping it is reported on the same terms as an unregistered
    character, which is what ``strict=`` is for. It used to be emitted as
    a token of its own and then discarded by the structured layer, so
    ``strict=True`` never saw it.
    """

    UNBOUND = ["t͡", "͡s", "t͡ s", "k͡͡t", "t͡s͜", "ppppp͡"]

    @pytest.mark.parametrize("text", UNBOUND)
    def test_unbound_tie_raises_under_strict(self, ipa: IPAFeatures, text: str) -> None:
        with pytest.raises(ValueError, match="malformed tie"):
            ipa.tokenize(text, strict=True)

    @pytest.mark.parametrize("text", UNBOUND)
    def test_unbound_tie_warns_by_default(self, ipa: IPAFeatures, text: str) -> None:
        with pytest.warns(UserWarning, match=r"unbound tie glyph"):
            ipa.tokenize(text)

    @pytest.mark.parametrize("text", UNBOUND)
    def test_validation_agrees_with_the_parser(
        self, ipa: IPAFeatures, text: str
    ) -> None:
        codes = [i["code"] for i in ipa.validate_ipa(text)]
        assert "malformed_tie" in codes

    @pytest.mark.parametrize("text", ["t̪͡s", "t͡s", "a͜ɪ", "t͡s͜a", "kʷ͡p"])
    def test_bound_ties_stay_clean(self, ipa: IPAFeatures, text: str) -> None:
        assert ipa.validate_ipa(text) == []
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            ipa.tokenize(text, strict=True)

    def test_strict_segments_refuses_rather_than_dropping(
        self, ipa: IPAFeatures
    ) -> None:
        with pytest.raises(ValueError, match="malformed tie"):
            ipa.segments("t͡", strict=True)

    @pytest.mark.parametrize("text", ["a|͡s", "a‖͜s", "a‿͡s", "a.͡s", "a͡͡s", "a͜͜s"])
    def test_a_break_on_the_left_leaves_the_tie_unbound(
        self, ipa: IPAFeatures, text: str
    ) -> None:
        # A break, the linking mark and a second stacked tie all end the
        # unit, so the tie that follows has nothing on its left.
        assert "malformed_tie" in [i["code"] for i in ipa.validate_ipa(text)]
        with pytest.raises(ValueError, match="malformed tie"):
            ipa.tokenize(text, strict=True)

    @pytest.mark.parametrize("text", ["aː͡s", "aˑ͜s", "a˥͡s"])
    def test_a_prosodic_mark_does_not_end_the_unit(
        self, ipa: IPAFeatures, text: str
    ) -> None:
        # Length and tone ride on the unit they follow, so the tie after
        # them still has a left side. The validator and the parser have to
        # agree about that, or one of them is lying about the same string.
        assert ipa.validate_ipa(text) == []
        assert ipa.tokenize(text, strict=True) == [_nfc(text)]

    def test_validator_and_parser_count_the_same_unbound_ties(
        self, ipa: IPAFeatures
    ) -> None:
        corpus = [
            "t͡s",
            "t̪͡s",
            "aː͡s",
            "a|͡s",
            "a͡͡s",
            "t͡",
            "͡s",
            "t͡ s",
            "k͡͡t",
            "t͡s͜",
            "lez‿ami",
            "ˈhɛ.ləʊ",
            "ŋ͡m͡ɡ͡b",
        ]
        for text in corpus:
            reported = sum(
                1 for i in ipa.validate_ipa(text) if i["code"] == "malformed_tie"
            )
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                ipa.parse(text)
            dropped = sum(
                int(str(w.message).split()[1])
                for w in caught
                if "unbound tie" in str(w.message)
            )
            assert reported == dropped, text


class TestTheMatchWindow:
    """What ``MAX_MATCH_LEN`` is for, and what it is not for.

    Two justifications used to sit stacked on the constant, disagreeing
    with each other: that it spans a tie-bar composite, and that it is
    wide enough for a five-constituent chain -- which is nine characters,
    not eleven. Nothing read the value, so neither could be checked.
    """

    def test_the_window_reaches_the_longest_registered_spelling(
        self, ipa: IPAFeatures
    ) -> None:
        """The floor, derived from the inventory rather than asserted.

        ``longest_match`` scans prefixes down from the window, so a key
        longer than it can never be matched whole -- and the longest
        registered spelling is a tie composite, not a single letter.
        """
        assert ipa.phones, "no phone registered: the bound would be vacuous"
        assert MAX_MATCH_LEN >= max(len(key) for key in ipa.phones)

    def test_the_window_does_not_bound_a_tie_chain(self, ipa: IPAFeatures) -> None:
        """The claim the stale comment made, measured.

        ``parse`` grows a chain a juncture at a time after the window has
        done its work, so a chain longer than the window is still one
        unit. If that stops being true, the constant becomes a limit on
        how long a tied unit may be, which is a policy nobody chose.
        """
        longest = "͡".join(["t"] * (MAX_MATCH_LEN + 2))
        assert len(longest) > MAX_MATCH_LEN
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assert ipa.tokenize(longest) == [longest]
            assert [u.to_ipa() for u in ipa.segments(longest)] == [longest]
