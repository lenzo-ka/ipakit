"""Realizing features as symbols: the inverse direction of the feature level.

``get_features`` reads a symbol into a bundle; ``to_phone`` reads a bundle
back into a symbol and ``respell`` composes the two into a feature-changing
rule. These tests pin the matching rule, the tie order that keeps the
inverse deterministic, and the errors that must not pass silently.
"""

import pytest
from ipakit import IPAFeatures, Kind
from ipakit.constants import SEQ_TIE


class TestInverse:
    def test_round_trip_over_the_inventory(self, ipa: IPAFeatures) -> None:
        # Every registered phone realizes back from its own bundle, except
        # the sequential compounds: their flat bundle is by construction the
        # projection of the first constituent (docs/ties.md), so the atom is
        # the honest answer -- and the one the tie rule must pick.
        for symbol in ipa.phones:
            realized = ipa.to_phone(ipa.get_features(symbol))
            expected = symbol.split(SEQ_TIE)[0] if SEQ_TIE in symbol else symbol
            assert realized == expected, symbol

    def test_round_trip_without_defaults(self, ipa: IPAFeatures) -> None:
        for symbol in ("p", "ʃ", "ɡ", "y", "t͡ʃ", "k͡p"):
            assert ipa.to_phone(ipa.get_features(symbol, with_defaults=False)) == symbol

    def test_unmatched_bundle_is_none(self, ipa: IPAFeatures) -> None:
        assert ipa.to_phone({"manner": "vowel", "place": "velar"}) is None

    def test_omitted_keys_are_free(self, ipa: IPAFeatures) -> None:
        assert ipa.to_phone({"manner": "plosive", "place": "bilabial"}) == "p"

    def test_metadata_keys_do_not_constrain(self, ipa: IPAFeatures) -> None:
        bundle = dict(ipa.get_features("p"), href="Nonsense", **{"class": "phone"})
        assert ipa.to_phone(bundle) == "p"


class TestTieResolution:
    def test_defaults_beat_declared_extras(self, ipa: IPAFeatures) -> None:
        # d, ɖ and ɗ all satisfy this bundle; d declares nothing beyond it,
        # ɖ adds retroflex and ɗ adds an implosive airstream.
        query = {"manner": "plosive", "place": "alveolar", "voiced": "+"}
        assert set(ipa.phones_matching(query)) >= {"d", "ɖ", "ɗ"}
        assert ipa.to_phone(query) == "d"

    def test_underspecified_takes_the_default_valued_phone(
        self, ipa: IPAFeatures
    ) -> None:
        # voiced is unstated, so both t and d match; t is the one that takes
        # the feature's default rather than declaring against it.
        assert ipa.to_phone({"manner": "plosive", "place": "alveolar"}) == "t"

    def test_atom_outranks_compound(self, ipa: IPAFeatures) -> None:
        assert ipa.to_phone(ipa.get_features("a͜ɪ")) == "a"

    def test_result_is_independent_of_key_order(self, ipa: IPAFeatures) -> None:
        bundle = ipa.get_features("e")
        reversed_bundle = dict(reversed(list(bundle.items())))
        assert ipa.to_phone(reversed_bundle) == ipa.to_phone(bundle) == "e"


class TestRespell:
    @pytest.mark.parametrize(
        "phone,changes,expected",
        [
            ("t", {"voiced": "+"}, "d"),
            ("d", {"voiced": "-"}, "t"),
            ("s", {"voiced": "+"}, "z"),
            ("k", {"voiced": "+"}, "ɡ"),
            ("p", {"place": "velar"}, "k"),
            ("k", {"place": "bilabial"}, "p"),
            ("s", {"place": "postalveolar"}, "ʃ"),
            ("m", {"place": "velar"}, "ŋ"),
            ("d", {"manner": "nasal"}, "n"),
            ("n", {"manner": "plosive"}, "d"),
            ("k", {"manner": "fricative"}, "x"),
            ("u", {"rounded": "-"}, "ɯ"),
            ("i", {"backness": "back"}, "ɯ"),
        ],
    )
    def test_changes(
        self, ipa: IPAFeatures, phone: str, changes: dict[str, str], expected: str
    ) -> None:
        assert ipa.respell(phone, **changes) == expected

    def test_composed_phone_respells(self, ipa: IPAFeatures) -> None:
        assert ipa.respell("t͡s", voiced="+") == "d͡z"

    def test_value_alias_resolves(self, ipa: IPAFeatures) -> None:
        assert ipa.respell("k", place="labial-velar") == "k͡p"

    def test_hyphenated_feature_reachable_with_underscore(
        self, ipa: IPAFeatures
    ) -> None:
        # A hyphen cannot be a keyword, so the name must still be sayable.
        assert ipa.respell("i", tongue_root="+") is None
        with pytest.raises(ValueError, match="unknown feature"):
            ipa.respell("i", tongue_root_x="+")

    @pytest.mark.parametrize(
        "phone,changes",
        [
            ("t", {"manner": "vowel"}),  # a plosive-turned-vowel is nothing
            ("p", {"manner": "trill"}),  # voiceless bilabial trill: unattested
            ("t", {"manner": "nasal"}),  # voiceless alveolar nasal: unattested
        ],
    )
    def test_unrealizable_is_none(
        self, ipa: IPAFeatures, phone: str, changes: dict[str, str]
    ) -> None:
        assert ipa.respell(phone, **changes) is None

    def test_identity_change(self, ipa: IPAFeatures) -> None:
        assert ipa.respell("t", voiced="-") == "t"

    def test_unresolvable_phone_raises(self, ipa: IPAFeatures) -> None:
        with pytest.raises(ValueError, match="cannot resolve phone"):
            ipa.respell("%", voiced="+")

    def test_unknown_feature_raises(self, ipa: IPAFeatures) -> None:
        # The whole point: a misspelled feature must not quietly do nothing.
        with pytest.raises(ValueError, match="unknown feature"):
            ipa.respell("t", voicing="+")

    def test_unknown_value_raises(self, ipa: IPAFeatures) -> None:
        with pytest.raises(ValueError, match="is not a value of feature"):
            ipa.respell("t", voiced="maybe")
        with pytest.raises(ValueError, match="is not a value of feature"):
            ipa.respell("t", place="uvular+nowhere")


class TestBuildFromBundles:
    def test_bundles_build_a_segment(self, ipa: IPAFeatures) -> None:
        seg = ipa.build_segment(
            [
                {"manner": "plosive", "place": "alveolar"},
                {"manner": "fricative", "place": "alveolar", "channel": "grooved"},
            ]
        )
        assert seg.to_ipa() == "t͡s"
        assert seg.kind is Kind.AFFRICATE

    def test_bundles_and_symbols_mix(self, ipa: IPAFeatures) -> None:
        seg = ipa.build_segment([{"manner": "plosive", "place": "alveolar"}, "ʃ"])
        assert seg.to_ipa() == "t͡ʃ"

    def test_symbol_only_signature_still_works(self, ipa: IPAFeatures) -> None:
        assert ipa.build_segment(["t", "ʃ"]).to_ipa() == "t͡ʃ"

    def test_unrealizable_bundle_raises(self, ipa: IPAFeatures) -> None:
        with pytest.raises(ValueError, match="no registered phone matches"):
            ipa.build_segment([{"manner": "vowel", "place": "velar"}])


class TestModuleAPI:
    def test_wrappers_are_exported(self) -> None:
        import ipakit

        assert {"to_phone", "respell"} <= set(ipakit.__all__)
        assert ipakit.to_phone(ipakit.features("m")) == "m"
        assert ipakit.respell("m", place="velar") == "ŋ"
