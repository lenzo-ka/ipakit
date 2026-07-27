"""Typed ties at the parse layer: sense-preserving ingest and resolution.

The over-tie (U+0361) marks simultaneous fusion; the under-tie (U+035C)
marks a sequential unit. The old global rewrite of under-tie to over-tie is
retired: tie-bearing aliases resolve token-locally to their registered
entries, unregistered under-tie chains keep their sense through the
tokenizer, and every entry point resolves the same bytes the same way.
"""

import pytest
from ipakit import IPAFeatures
from ipakit.constants import SEQ_TIE, TIE_BAR


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


# Registered names and their tie-bearing alias spellings (the legacy
# collision set: the alias glyph contradicts the registered sense, and the
# registered sense wins).
ALIAS_COLLISIONS = [
    ("t͡s", "t͜s"),
    ("d͡ʒ", "d͜ʒ"),
    ("k͡p", "k͜p"),
    ("ŋ͡m", "ŋ͜m"),
    ("a͡ɪ", "a͜ɪ"),
    ("o͡ʊ", "o͜ʊ"),
    ("ʊ͡ə", "ʊ͜ə"),
]


class TestAliasResolution:
    def test_aliases_resolve_at_every_entry_point(self, ipa: IPAFeatures) -> None:
        for canonical, alias in ALIAS_COLLISIONS:
            assert ipa.get_features(alias) == ipa.get_features(canonical)
            assert ipa.get_features(alias), f"{alias!r} should resolve"
            phone = ipa.get_phone(alias)
            assert phone is not None and phone.symbol == canonical
            assert alias in ipa
            assert ipa.tokenize_ipa(alias) == [canonical]
            assert ipa.parse(alias) == [(canonical, [])]

    def test_alias_resolves_inside_a_word(self, ipa: IPAFeatures) -> None:
        assert ipa.tokenize_ipa("at͜sa") == ["a", "t͡s", "a"]


class TestUnderTieSequences:
    def test_unregistered_under_tie_chain_keeps_its_sense(
        self, ipa: IPAFeatures
    ) -> None:
        # No global rewrite: the under-tie survives tokenization.
        assert ipa.tokenize_ipa("u͜i") == ["u͜i"]
        assert SEQ_TIE in ipa.tokenize_ipa("u͜i")[0]

    def test_sequential_scalar_projects_first_element(self, ipa: IPAFeatures) -> None:
        # The flat projection of a sequential chain is its first element,
        # matching how the registered diphthongs are encoded.
        u = ipa.get_features("u", with_defaults=False)
        seq = ipa.get_features("u͜i", with_defaults=False)
        assert seq == {k: v for k, v in u.items() if k != "href"}

    def test_sequential_chain_is_n_ary(self, ipa: IPAFeatures) -> None:
        assert ipa.tokenize_ipa("a͜ɪ͜ə") == ["a͜ɪ͜ə"]
        a = ipa.get_features("a", with_defaults=False)
        assert ipa.get_features("a͜ɪ͜ə", with_defaults=False) == {
            k: v for k, v in a.items() if k != "href"
        }

    def test_over_tie_composition_unchanged(self, ipa: IPAFeatures) -> None:
        feats = ipa.get_features("q͡χ")
        assert feats["manner"] == "affricate"
        assert feats["place"] == "uvular"

    def test_under_tie_consonant_chain_projects_first(self, ipa: IPAFeatures) -> None:
        # q͜χ is a sequential unit now (it was globally rewritten to the
        # over-tie before): first-element projection, not an affricate merge.
        feats = ipa.get_features("q͜χ", with_defaults=False)
        assert feats["manner"] == "plosive"
        assert "q͜χ" in ipa


class TestMixedChains:
    def test_fused_onset_in_sequential_chain(self, ipa: IPAFeatures) -> None:
        # t͡s͜a: the over-tie binds tighter; the unit's flat projection is
        # its first top-level part, the registered affricate.
        assert ipa.tokenize_ipa("t͡s͜a") == ["t͡s͜a"]
        feats = ipa.get_features("t͡s͜a", with_defaults=False)
        assert feats["manner"] == "affricate"
        assert feats["place"] == "alveolar"
        assert "t͡s͜a" in ipa

    def test_alias_spelled_fused_onset(self, ipa: IPAFeatures) -> None:
        # The first part may itself arrive as an alias spelling.
        feats = ipa.get_features("t͡s͜a")
        assert feats["manner"] == "affricate"


class TestDoubleTieCollapse:
    def test_double_tie_collapses_to_fuse(self, ipa: IPAFeatures) -> None:
        # Both ties on one juncture assert contradictory timing; the
        # simultaneous reading wins on ingest (either written order).
        for stacked in (TIE_BAR + SEQ_TIE, SEQ_TIE + TIE_BAR):
            text = "t" + stacked + "s"
            assert ipa.canonicalize_unicode(text) == "t" + TIE_BAR + "s"
            assert ipa.tokenize_ipa(text) == ["t͡s"]


class TestTielessNormalizationHeuristic:
    def test_consonants_fuse_vowels_sequence(self, ipa: IPAFeatures) -> None:
        assert ipa.add_tie_bars("ts") == "t" + TIE_BAR + "s"
        assert ipa.add_tie_bars("ai") == "a" + SEQ_TIE + "i"

    def test_explicit_tie_wins_over_heuristic(self, ipa: IPAFeatures) -> None:
        assert ipa.add_tie_bars("a͡i") == "a͡i"
        assert ipa.add_tie_bars("t͜s") == "t͜s"

    def test_normalized_vowel_pair_resolves_via_alias(self, ipa: IPAFeatures) -> None:
        # normalize emits e͜ɪ; ingest resolves it to the registered e͡ɪ.
        out = ipa.normalize_ipa("eɪ")
        assert out == "e" + SEQ_TIE + "ɪ"
        assert ipa.tokenize_ipa(out) == ["e͡ɪ"]
