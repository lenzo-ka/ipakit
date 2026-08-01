"""Typed ties: strict house semantics and the wild-import boundary.

The over-tie (U+0361) marks simultaneous fusion; the under-tie (U+035C)
marks a sequential unit. The glyph is authoritative everywhere in default
parsing -- canonical spellings are sense-correct, no alias rewrites tie
glyphs -- and text from other conventions (where the glyphs are
typographic variants) imports explicitly via from_wild().
"""

import pytest
from ipakit import IPAFeatures


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


# House-canonical spellings and their glyph-variant "wild" spellings.
WILD_VARIANTS = [
    ("t͡s", "t͜s"),
    ("d͡ʒ", "d͜ʒ"),
    ("k͡p", "k͜p"),
    ("ŋ͡m", "ŋ͜m"),
    ("a͜ɪ", "a͡ɪ"),
    ("o͜ʊ", "o͡ʊ"),
    ("ʊ͜ə", "ʊ͡ə"),
]


class TestStrictGlyphAuthority:
    def test_variant_spellings_are_not_the_registered_entry(
        self, ipa: IPAFeatures
    ) -> None:
        # The glyph is authoritative: a variant spelling is a different
        # object, not an alias of the canonical entry.
        for canonical, variant in WILD_VARIANTS:
            assert ipa.get_phone(variant) is None
            assert ipa.get_features(variant) != ipa.get_features(canonical)

    def test_under_tie_variant_reads_sequential(self, ipa: IPAFeatures) -> None:
        # t͜s is a sequential chain: first-element projection.
        assert ipa.get_features("t͜s", with_defaults=False)["manner"] == "plosive"
        assert ipa.segment("t͜s").sense.value == "seq"

    def test_over_tie_variant_reads_simultaneous(self, ipa: IPAFeatures) -> None:
        # a͡ɪ is a fused vowel overlay, not the registered diphthong.
        seg = ipa.segment("a͡ɪ")
        assert seg.sense.value == "fuse"

    def test_from_wild_imports_variants(self, ipa: IPAFeatures) -> None:
        for canonical, variant in WILD_VARIANTS:
            assert ipa.from_wild(variant) == canonical

    def test_from_wild_heuristic_for_unregistered(self, ipa: IPAFeatures) -> None:
        assert ipa.from_wild("u͡i") == "u͜i"  # vocalic pair: sequential
        assert ipa.from_wild("q͜χ") == "q͡χ"  # obstruents: simultaneous

    def test_from_wild_preserves_house_input(self, ipa: IPAFeatures) -> None:
        for text in ["t͡s͜a", "a͜ɪ͜ə", "n͡d͡ʒ͜a͜ɪ", "t͡ɬ"]:
            assert ipa.from_wild(text) == text

    def test_import_phoneset(self, ipa: IPAFeatures) -> None:
        from ipakit import Phoneset

        wild = Phoneset.from_list(["p", "t͜s", "e͡ɪ", "a͡ɪ", "XX"], name="w")
        imported = ipa.import_phoneset(wild)
        assert imported.phones == ["p", "t͡s", "e͜ɪ", "a͜ɪ", "XX"]
        assert imported.name == "w"

    def test_for_phoneset_warns_on_wild_spellings(self, ipa: IPAFeatures) -> None:
        import warnings

        import ipakit
        from ipakit import Phoneset

        wild = Phoneset.from_list(["p", "b", "e͡ɪ"], name="w")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            model = ipakit.distance_model(wild)
        assert any("import_phoneset" in str(w.message) for w in caught)
        # The wild diphthong was dropped from the reference, not respelled.
        assert len(model.reference_phones) == 2

    def test_imported_phoneset_keeps_its_compounds(self, ipa: IPAFeatures) -> None:
        import warnings

        import ipakit
        from ipakit import Phoneset

        imported = ipa.import_phoneset(Phoneset.from_list(["p", "b", "e͡ɪ"], name="w"))
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            model = ipakit.distance_model(imported)
        assert not caught
        assert len(model.reference_phones) == 3

    def test_wild_word(self, ipa: IPAFeatures) -> None:
        assert ipa.from_wild("t͜sa͡ɪ") == "t͡sa͜ɪ"
        assert ipa.tokenize(ipa.from_wild("at͜sa")) == ["a", "t͡s", "a"]


class TestUnderTieSequences:
    def test_unregistered_under_tie_chain_keeps_its_sense(
        self, ipa: IPAFeatures
    ) -> None:
        # No global rewrite: the under-tie survives tokenization.
        assert ipa.tokenize("u͜i") == ["u͜i"]
        assert ipa.seq_tie in ipa.tokenize("u͜i")[0]

    def test_sequential_scalar_projects_first_element(self, ipa: IPAFeatures) -> None:
        # The flat projection of a sequential chain is its first element,
        # matching how the registered diphthongs are encoded.
        u = ipa.get_features("u", with_defaults=False)
        seq = ipa.get_features("u͜i", with_defaults=False)
        assert seq == {k: v for k, v in u.items() if k != "href"}

    def test_sequential_chain_is_n_ary(self, ipa: IPAFeatures) -> None:
        assert ipa.tokenize("a͜ɪ͜ə") == ["a͜ɪ͜ə"]
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
        assert ipa.tokenize("t͡s͜a") == ["t͡s͜a"]
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
        for stacked in (ipa.tie_bar + ipa.seq_tie, ipa.seq_tie + ipa.tie_bar):
            text = "t" + stacked + "s"
            assert ipa.canonicalize_unicode(text) == "t" + ipa.tie_bar + "s"
            assert ipa.tokenize(text) == ["t͡s"]


class TestPhonesetBoundary:
    """X-SAMPA has one tie encoding, so both glyphs write as `_` and the
    sense is carried by nothing at the boundary. Coming back, `_` reads as
    a tie and the result is canonicalized through from_wild: registered
    compounds return in house spelling with their correct sense; the rest
    get the heuristic."""

    def test_both_ties_encode_as_underscore(self) -> None:
        import ipakit

        assert ipakit.ipa_to_xsampa("t͡s") == "t_s"
        assert ipakit.ipa_to_xsampa("a͜ɪ") == "a_I"
        assert ipakit.ipa_to_xsampa("u͜i") == ipakit.ipa_to_xsampa("u͡i") == "u_i"

    def test_round_trips_return_house_canonicals(self) -> None:
        import ipakit

        assert ipakit.xsampa_to_ipa(ipakit.ipa_to_xsampa("t͡s")) == "t͡s"
        assert ipakit.xsampa_to_ipa(ipakit.ipa_to_xsampa("a͜ɪ")) == "a͜ɪ"
        assert ipakit.xsampa_to_ipa(ipakit.ipa_to_xsampa("u͜i")) == "u͜i"
        # Wild spellings canonicalize on the way through.
        assert ipakit.xsampa_to_ipa(ipakit.ipa_to_xsampa("a͡ɪ")) == "a͜ɪ"


class TestTielessNormalizationHeuristic:
    def test_consonants_fuse_vowels_sequence(self, ipa: IPAFeatures) -> None:
        assert ipa.add_ties("ts") == "t" + ipa.tie_bar + "s"
        assert ipa.add_ties("ai") == "a" + ipa.seq_tie + "i"

    def test_explicit_tie_wins_over_heuristic(self, ipa: IPAFeatures) -> None:
        assert ipa.add_ties("a͡i") == "a͡i"
        assert ipa.add_ties("t͜s") == "t͜s"

    def test_normalized_vowel_pair_is_canonical(self, ipa: IPAFeatures) -> None:
        # normalize emits the canonical sequential spelling directly.
        out = ipa.normalize("eɪ")
        assert out == "e" + ipa.seq_tie + "ɪ"
        assert ipa.tokenize(out) == ["e͜ɪ"]
        assert ipa.get_phone(out) is not None


class TestTheTwoEntryPointsSenseATieTheSameWay:
    """``add_ties`` and ``from_wild`` are one vowel test, not two.

    They held byte-identical private copies of it, with nothing pinning
    the equality: correcting the vowel test in either -- to reach a
    syllabic consonant, say, or to resolve an alias -- would have made an
    under-tie mean one thing when ipakit writes it and another when it
    reads imported text back. They call one read now, and this is the
    consequence swept rather than the call asserted.
    """

    def test_every_base_pair_agrees_across_the_two(self, ipa: IPAFeatures) -> None:
        """Over every ordered pair of single-glyph bases the inventory
        spells: what add_ties writes between them is what from_wild
        re-senses the other glyph into."""
        bases = sorted(
            symbol
            for symbol in ipa.phones
            if len(symbol) == 1 and symbol not in ipa.diacritics
        )
        assert len(bases) > 50, "sweep did not run"
        checked, disagreed = 0, []
        for first in bases:
            for second in bases:
                written = ipa.add_ties(first + second)
                if len(written) != 3:
                    continue  # not a two-base group; nothing was inserted
                checked += 1
                # The wild spelling is the same chain under the other
                # glyph, which from_wild must re-sense to the same thing.
                other = ipa.seq_tie if written[1] == ipa.tie_bar else ipa.tie_bar
                resensed = ipa.from_wild(first + other + second)
                if resensed != written:
                    disagreed.append((first, second, written, resensed))
        assert checked > 1000, "sweep did not run"
        assert not disagreed, disagreed[:5]
