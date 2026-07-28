"""Tests for analysis functions: describe, natural_class, minimal_pairs, validate_ipa."""

import warnings
from collections import defaultdict

import ipakit
import pytest
from ipakit import IPAFeatures
from ipakit.analysis import _PRIMARY_SLOTS
from ipakit.segment import Kind


def _reads_back(ipa: IPAFeatures, text: str) -> bool:
    """Whether the inventory can spell this, strictly and unchanged."""
    try:
        return ipa.segment(text, strict=True).to_ipa() == text
    except ValueError:
        return False


class TestDescribe:
    """Tests for describe() function."""

    def test_describe_voiceless_plosive(self, ipa: IPAFeatures) -> None:
        desc = ipa.describe("p")
        assert "voiceless" in desc
        assert "bilabial" in desc
        assert "plosive" in desc

    def test_describe_voiced_plosive(self, ipa: IPAFeatures) -> None:
        desc = ipa.describe("b")
        assert "voiced" in desc
        assert "bilabial" in desc
        assert "plosive" in desc

    def test_describe_vowel(self, ipa: IPAFeatures) -> None:
        desc = ipa.describe("ɛ")
        assert "open-mid" in desc
        assert "front" in desc
        assert "vowel" in desc

    def test_describe_rounded_vowel(self, ipa: IPAFeatures) -> None:
        desc = ipa.describe("u")
        assert "rounded" in desc
        assert "vowel" in desc

    def test_describe_affricate(self, ipa: IPAFeatures) -> None:
        desc = ipa.describe("t͡ʃ")
        assert "voiceless" in desc
        assert "affricate" in desc

    def test_describe_lateral(self, ipa: IPAFeatures) -> None:
        desc = ipa.describe("l")
        assert "lateral" in desc
        assert "approximant" in desc

    def test_describe_nasal(self, ipa: IPAFeatures) -> None:
        desc = ipa.describe("n")
        assert "nasal" in desc
        assert "alveolar" in desc

    def test_describe_secondary_articulation(self, ipa: IPAFeatures) -> None:
        # ɫ carries velarized as a base feature; the description has to
        # render it, or dark l and clear l read as the same sound.
        desc = ipa.describe("ɫ")
        assert desc == "voiced velarized lateral alveolar approximant"
        assert desc != ipa.describe("l")

    def test_describe_modifiers_reach_vowels(self, ipa: IPAFeatures) -> None:
        # The vowel branch used to return before reading any modifier out,
        # so a nasalized vowel -- ordinary transcription -- was named as
        # its oral counterpart.
        assert ipa.describe("ã") == "nasalized open front unrounded vowel"
        assert ipa.describe("ã") != ipa.describe("a")
        assert ipa.describe("aˤ") == "pharyngealized open front unrounded vowel"

    def test_describe_r_colored_vowel(self, ipa: IPAFeatures) -> None:
        # ɚ/ɝ carry retroflex as a base feature; on a vowel that is named
        # for its acoustic effect, as the phones' own reference is.
        assert ipa.describe("ɚ") == "r-colored mid central unrounded vowel"
        assert ipa.describe("ɚ") != ipa.describe("ə")
        assert ipa.describe("ɝ") != ipa.describe("ɜ")

    def test_describe_syllabic_consonant(self, ipa: IPAFeatures) -> None:
        assert ipa.describe("l̩") == "voiced syllabic lateral alveolar approximant"
        assert ipa.describe("l̩") != ipa.describe("l")

    def test_describe_omits_what_a_phone_does_not_carry(self, ipa: IPAFeatures) -> None:
        # Reading modifiers out must stay silent on the phones that have
        # none. A plain vowel says nothing about its voicing either: every
        # vowel letter declares voiced="+", so reading the slot out
        # unconditionally would put "voiced" in front of all of them, and
        # no conventional name does that.
        assert ipa.describe("a") == "open front unrounded vowel"
        assert ipa.describe("p") == "voiceless bilabial plosive"
        assert ipa.describe("l") == "voiced lateral alveolar approximant"

    def test_describe_reads_a_slot_a_mark_states_on_a_vowel(
        self, ipa: IPAFeatures
    ) -> None:
        # Voicing, place and airstream are slots the vowel sentence never
        # looked at, so a mark that stated one moved the feature bag and
        # the metric while leaving the name word for word the bare
        # letter's. All three of these read "open front unrounded vowel".
        assert ipa.describe("ḁ") == "voiceless open front unrounded vowel"
        assert ipa.describe("a̪") == "dental open front unrounded vowel"
        assert ipa.describe("aʼ") == "open front unrounded vowel ejective"
        for unit in ("ḁ", "a̪", "aʼ"):
            assert ipa.describe(unit) != ipa.describe("a")

    def test_the_two_sentences_are_one_sentence(self, ipa: IPAFeatures) -> None:
        # A vowel's name is the consonant's with its own three slots
        # standing where the manner's modifiers would: "[voice]
        # [modifiers] [place] [height backness round] [manner]
        # [airstream]" reads both, because a vowel's manner is the word
        # "vowel" and a consonant states no height or backness.
        assert ipa.describe("t̪ʼ") == "voiceless dental plosive ejective"
        assert ipa.describe("a̪ʼ") == "dental open front unrounded vowel ejective"
        assert ipa.describe("ã̪") == "nasalized dental open front unrounded vowel"

    def test_every_vowel_letter_declares_its_own_voicing(
        self, ipa: IPAFeatures
    ) -> None:
        """The premise the conditional voicing read stands on.

        ``describe`` says "voiceless" of a vowel that has arrived at the
        *declared* default, on the grounds that no vowel letter can put it
        there -- only a mark can. That is a property of the inventory, so
        it is asserted rather than assumed: a vowel added without its
        voicing would silently turn the read-out on for its whole column.
        """
        default = ipa.features["voiced"].default
        vowels = [s for s in ipa.phones if ipa.get_features(s).get("manner") == "vowel"]
        assert len(vowels) > 30, "sweep did not run"
        assert [s for s in vowels if ipa.get_features(s).get("voiced") == default] == []

    def test_no_two_phones_share_a_description(self, ipa: IPAFeatures) -> None:
        """Distinct registered phones get distinct names.

        The guard for the whole class of bug that l/ɫ and a/ã were in: a
        feature the metric can see but the description drops leaves two
        sounds sharing one name. The one standing exception is structural
        and separately tracked -- describe reads the flat projection,
        which collapses a diphthong onto its first element, so each
        registered diphthong still shares its nucleus's description. That
        is a lost constituent, not a lost feature, so a collision group is
        allowed only when it is exactly one nucleus and its diphthongs.
        """
        groups: dict[str, list[str]] = defaultdict(list)
        for phone in ipa.phones:
            groups[ipa.describe(phone)].append(phone)
        for desc, group in groups.items():
            if len(group) == 1:
                continue
            kinds = [ipa.segment(phone).kind for phone in group]
            assert kinds.count(Kind.ATOMIC) == 1 and set(kinds) == {
                Kind.ATOMIC,
                Kind.DIPHTHONG,
            }, f"{desc!r} names more than one distinct phone: {group}"

    def test_no_slot_goes_unread_because_of_the_segment_class(
        self, ipa: IPAFeatures
    ) -> None:
        """A slot a mark moves has to move the name.

        The predicate, not the four marks that exposed it. The vowel
        sentence rendered three slots and the consonant sentence four,
        and the four were simply not looked at on a vowel -- so "a̪",
        "aʼ" and "ḁ" each carried a slot the bare letter does not and
        each was named "open front unrounded vowel" all the same. Any
        future sentence that skips a slot on account of the segment's
        class fails here, whichever slot and whichever class.

        A manner the data marks ``offscale`` is out of scope, and only
        silence is: it holds no position on the constriction continuum,
        so it fills no slot and renders none. A marked pause is still a
        pause, and "␣ʼ" is correctly named "silence".
        """
        offscale = ipa.features["manner"].offscale
        silent: list[tuple[str, str]] = []
        checked = 0
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for base in ipa.phones:
                bare = ipa.get_features(base)
                if bare.get("manner") in offscale:
                    continue
                name = ipa.describe(base)
                for mark in ipa.diacritics:
                    unit = base + mark
                    if not _reads_back(ipa, unit):
                        continue
                    checked += 1
                    marked = ipa.get_features(unit)
                    moved = sorted(
                        slot
                        for slot in _PRIMARY_SLOTS
                        if marked.get(slot) != bare.get(slot)
                    )
                    if moved and ipa.describe(unit) == name:
                        silent.append((unit, ", ".join(moved)))
        assert checked > 3000, "sweep did not run"
        assert silent == []

    def test_describe_unknown(self, ipa: IPAFeatures) -> None:
        desc = ipa.describe("X")
        assert "unknown" in desc

    def test_describe_module_function(self) -> None:
        desc = ipakit.describe("p")
        assert "voiceless" in desc
        assert "bilabial" in desc
        assert "plosive" in desc


class TestNaturalClass:
    """Tests for natural_class() function."""

    def test_voiceless_plosives(self, ipa: IPAFeatures) -> None:
        shared = ipa.natural_class(["p", "t", "k"])
        assert shared.get("manner") == "plosive"
        assert shared.get("voiced") == "-"

    def test_voiced_plosives(self, ipa: IPAFeatures) -> None:
        shared = ipa.natural_class(["b", "d", "ɡ"])
        assert shared.get("manner") == "plosive"
        assert shared.get("voiced") == "+"

    def test_front_vowels(self, ipa: IPAFeatures) -> None:
        shared = ipa.natural_class(["i", "e", "ɛ"])
        assert shared.get("manner") == "vowel"
        assert shared.get("backness") == "front"

    def test_nasals(self, ipa: IPAFeatures) -> None:
        shared = ipa.natural_class(["m", "n", "ŋ"])
        assert shared.get("manner") == "nasal"
        assert shared.get("voiced") == "+"

    def test_bilabials(self, ipa: IPAFeatures) -> None:
        shared = ipa.natural_class(["p", "b", "m"])
        assert shared.get("place") == "bilabial"

    def test_empty_list(self, ipa: IPAFeatures) -> None:
        shared = ipa.natural_class([])
        assert shared == {}

    def test_single_phone(self, ipa: IPAFeatures) -> None:
        shared = ipa.natural_class(["p"])
        # Single phone returns all its features
        assert "manner" in shared
        assert "place" in shared

    def test_module_function(self) -> None:
        shared = ipakit.natural_class(["p", "t", "k"])
        assert shared.get("manner") == "plosive"


class TestMinimalPairs:
    """Tests for minimal_pairs() function."""

    def test_minimal_pairs_p(self, ipa: IPAFeatures) -> None:
        pairs = ipa.minimal_pairs("p")
        phones = [p for p, _, _ in pairs]
        # b should be a minimal pair (differs in voicing)
        assert "b" in phones

    def test_minimal_pairs_s(self, ipa: IPAFeatures) -> None:
        pairs = ipa.minimal_pairs("s")
        phones = [p for p, _, _ in pairs]
        # z should be a minimal pair (differs in voicing)
        assert "z" in phones

    def test_minimal_pairs_returns_tuples(self, ipa: IPAFeatures) -> None:
        pairs = ipa.minimal_pairs("p")
        assert len(pairs) > 0
        for item in pairs:
            assert len(item) == 3
            phone, feat, val = item
            assert isinstance(phone, str)
            assert isinstance(feat, str)
            assert isinstance(val, str)

    def test_minimal_pairs_unknown_phone(self, ipa: IPAFeatures) -> None:
        pairs = ipa.minimal_pairs("X")
        assert pairs == []

    def test_module_function(self) -> None:
        pairs = ipakit.minimal_pairs("p")
        phones = [p for p, _, _ in pairs]
        assert "b" in phones


class TestNearestPhones:
    """Tests for nearest_phones() function."""

    def test_nearest_returns_list(self, ipa: IPAFeatures) -> None:
        nearest = ipa.nearest_phones("p", n=5)
        assert isinstance(nearest, list)
        assert len(nearest) <= 5

    def test_nearest_sorted_by_distance(self, ipa: IPAFeatures) -> None:
        nearest = ipa.nearest_phones("p", n=10)
        distances = [d for _, d in nearest]
        assert distances == sorted(distances)

    def test_nearest_includes_similar(self, ipa: IPAFeatures) -> None:
        nearest = ipa.nearest_phones("p", n=10)
        phones = [p for p, _ in nearest]
        # Similar phones should include other bilabial/plosive sounds
        # Note: voiced pair "b" may not be top 5 due to voicing weight
        assert len(phones) > 0
        # At least check that we get plosives or bilabials
        assert any(p in phones for p in ["t", "k", "b", "ɸ", "f"])

    def test_nearest_unresolvable_phone_raises(self, ipa: IPAFeatures) -> None:
        # An empty list would read as "no neighbours" rather than
        # "unsupported input".
        with pytest.raises(ValueError, match="cannot resolve"):
            ipa.nearest_phones("X")

    def test_nearest_accepts_composed_units(self, ipa: IPAFeatures) -> None:
        # describe() and distance() accept these; nearest must too.
        assert "q͡χ" not in ipa.phones
        assert len(ipa.nearest_phones("q͡χ", n=3)) == 3

    def test_module_function(self) -> None:
        nearest = ipakit.nearest_phones("p", n=3)
        assert len(nearest) == 3
        # Check structure: list of (phone, distance) tuples
        for phone, dist in nearest:
            assert isinstance(phone, str)
            assert isinstance(dist, float)
            assert 0 <= dist <= 1


class TestValidateIPA:
    """Tests for validate_ipa() function."""

    def test_valid_simple(self, ipa: IPAFeatures) -> None:
        issues = ipa.validate_ipa("kæt")
        assert issues == []

    def test_valid_with_diacritics(self, ipa: IPAFeatures) -> None:
        # Dental diacritic on t
        issues = ipa.validate_ipa("t̪")
        assert issues == []

    def test_valid_affricate(self, ipa: IPAFeatures) -> None:
        issues = ipa.validate_ipa("t͡ʃ")
        assert issues == []

    def test_valid_with_stress(self, ipa: IPAFeatures) -> None:
        issues = ipa.validate_ipa("ˈkæt")
        assert issues == []

    def test_valid_with_syllable_break(self, ipa: IPAFeatures) -> None:
        issues = ipa.validate_ipa("hɛ.loʊ")
        assert issues == []

    def test_valid_with_word_boundary(self, ipa: IPAFeatures) -> None:
        # '#' is a word separator in ipa.xml (data-driven; was rejected before).
        assert ipa.validate_ipa("kæt#dɒɡ") == []

    def test_valid_tone_letter(self, ipa: IPAFeatures) -> None:
        # Spacing tone letters are standalone suprasegmentals.
        assert ipa.validate_ipa("ma˥") == []

    def test_unknown_symbol(self, ipa: IPAFeatures) -> None:
        # Use actual non-IPA characters (note: x, y, z ARE valid IPA)
        issues = ipa.validate_ipa("k@t")  # @ is not IPA
        assert len(issues) >= 1
        codes = [i["code"] for i in issues]
        assert "unknown_symbol" in codes

    def test_unknown_symbol_details(self, ipa: IPAFeatures) -> None:
        issues = ipa.validate_ipa("@")  # @ is not IPA
        assert len(issues) == 1
        issue = issues[0]
        assert issue["type"] == "error"
        assert issue["code"] == "unknown_symbol"
        assert issue["symbol"] == "@"
        assert issue["position"] == "0"

    def test_orphan_diacritic(self, ipa: IPAFeatures) -> None:
        # Nasal diacritic at start (no base phone)
        issues = ipa.validate_ipa("̃a")
        codes = [i["code"] for i in issues]
        assert "orphan_diacritic" in codes

    def test_malformed_tie_at_boundary(self, ipa: IPAFeatures) -> None:
        # A tie bar with nothing to tie on one side is malformed. Covers a lone
        # tie, a leading tie, and a trailing tie -- none is a valid composite.
        tie = "͡"
        for bad in (tie, tie + "a", "a" + tie):
            codes = [i["code"] for i in ipa.validate_ipa(bad)]
            assert "malformed_tie" in codes, f"{bad!r} should flag malformed_tie"

    def test_valid_tie_composite_is_clean(self, ipa: IPAFeatures) -> None:
        # A well-formed affricate must NOT be flagged.
        assert ipa.validate_ipa("t͡ʃ") == []

    def test_duplicate_diacritic_warning(self, ipa: IPAFeatures) -> None:
        # Same diacritic twice on one segment
        issues = ipa.validate_ipa("t̪̪")
        codes = [i["code"] for i in issues]
        assert "duplicate_diacritic" in codes
        # Should be a warning, not error
        dupe_issue = next(i for i in issues if i["code"] == "duplicate_diacritic")
        assert dupe_issue["type"] == "warning"

    def test_strict_mode(self, ipa: IPAFeatures) -> None:
        # In strict mode, warnings become errors
        issues = ipa.validate_ipa("t̪̪", strict=True)
        dupe_issue = next(i for i in issues if i["code"] == "duplicate_diacritic")
        assert dupe_issue["type"] == "error"

    def test_is_valid_ipa_true(self, ipa: IPAFeatures) -> None:
        assert ipa.is_valid_ipa("kæt") is True

    def test_is_valid_ipa_false(self, ipa: IPAFeatures) -> None:
        assert ipa.is_valid_ipa("k@t") is False  # @ is not IPA

    def test_is_valid_ipa_with_warning(self, ipa: IPAFeatures) -> None:
        # Warnings don't make it invalid
        assert ipa.is_valid_ipa("t̪̪") is True

    def test_module_function_valid(self) -> None:
        issues = ipakit.validate_ipa("kæt")
        assert issues == []

    def test_module_function_invalid(self) -> None:
        issues = ipakit.validate_ipa("k@t")  # @ is not IPA
        assert len(issues) >= 1

    def test_is_valid_module_function(self) -> None:
        assert ipakit.is_valid_ipa("kæt") is True
        assert ipakit.is_valid_ipa("k@t") is False  # @ is not IPA
