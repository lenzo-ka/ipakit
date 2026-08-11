"""Realizing features as symbols: the inverse direction of the feature level.

``get_features`` reads a symbol into a bundle; ``to_phone`` reads a bundle
back into a symbol and ``respell`` composes the two into a feature-changing
rule. These tests pin the matching rule, the tie order that keeps the
inverse deterministic, and the errors that must not pass silently.
"""

import pytest
from ipakit import IPAFeatures, Kind
from ipakit.constants import METADATA_ATTRS


class TestInverse:
    def test_round_trip_over_the_inventory(self, ipa: IPAFeatures) -> None:
        # Every registered phone realizes back from its own bundle, except
        # the sequential compounds: their flat bundle is by construction the
        # projection of the first constituent (docs/ties.md), so the atom is
        # the honest answer -- and the one the tie rule must pick.
        for symbol in ipa.phones:
            realized = ipa.to_phone(ipa.get_features(symbol))
            expected = symbol.split(ipa.seq_tie)[0]
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


class TestRespellNeverSubstitutesADifferentUnit:
    """Asking for what a unit already says gives that unit back, or nothing.

    Two ways it did not. A **tied** unit went through its flat bundle, and
    the flat read of an under-tie chain is its first constituent
    (docs/ties.md), so ``respell("a͜ɪ", voiced="+")`` was ``"a"`` -- a
    diphthong replaced by its first half in the name of a change that
    moved nothing. And **prosody** is outside the bundle by design, so
    respelling from the bundle alone spent it: ``respell("tː",
    voiced="+")`` was ``"d"``, with a length nobody asked about gone.

    Both are the same wrong answer: a plausible different unit, returned
    confidently, where the honest answers are the unit itself or ``None``.
    """

    def test_a_tied_unit_survives_a_change_it_already_satisfies(
        self, ipa: IPAFeatures
    ) -> None:
        assert ipa.respell("a͜ɪ", voiced="+") == "a͜ɪ"

    def test_a_tied_unit_takes_the_change_on_each_constituent(
        self, ipa: IPAFeatures
    ) -> None:
        # Not a no-op: rounding a diphthong rounds both halves of it.
        assert ipa.respell("a͜ɪ", rounded="+") == "ɶ͜ʏ"

    def test_an_over_tie_compound_keeps_the_flat_path(self, ipa: IPAFeatures) -> None:
        # Its flat read is a fusion of both constituents and not a
        # projection of one, so realizing the bundle is the right answer.
        assert ipa.respell("t͡s", voiced="+") == "d͡z"

    def test_prosody_is_carried_across(self, ipa: IPAFeatures) -> None:
        assert ipa.respell("tː", voiced="+") == "dː"
        assert ipa.respell("ˈaː", rounded="+") == "ˈɶː"
        assert ipa.respell("t͡sː", voiced="+") == "d͡zː"

    def test_a_prosodic_change_is_refused_rather_than_swallowed(
        self, ipa: IPAFeatures
    ) -> None:
        """It has nowhere to land: the key would sit in a bundle prosody is
        defined to be outside of. ``respell("a", length="long")`` answered
        ``None`` only because ``to_phone`` happened to match nothing, and
        ``respell("a", length="normal")`` answered ``"a"`` -- a no-op that
        looks like a write."""
        for value in ("long", "normal"):
            with pytest.raises(ValueError, match="respell cannot write"):
                ipa.respell("a", length=value)
        with pytest.raises(ValueError, match="respell cannot write"):
            ipa.respell("a", stress="primary")

    #: One prosody-bearing unit in this many. A deliberate sample: what
    #: this sweep exercises is the *carrying*, and a unit's prosody is
    #: carried by the same two lines whichever mark wrote it, while
    #: `to_phone` scans the whole inventory per call and the unstrided
    #: corpus is minutes rather than seconds. Every registered phone is
    #: swept unstrided, because that half is the inventory claim.
    PROSODY_STRIDE = 13

    def test_it_holds_over_the_corpus(self, ipa: IPAFeatures) -> None:
        """Swept over every registered phone and a sample of the prosody
        the data declares, against every key the unit's own constituents
        agree on.

        Agreement is what makes the request a no-op *for the unit*. The
        flat bundle of a tied unit reports one constituent's value for the
        whole, so a key the constituents disagree about is a real change
        to the other one and has no business in this sweep.
        """
        import warnings

        from tests.corpus import prosody_bearing_units, self_spelling_phones

        corpus = (
            self_spelling_phones() + prosody_bearing_units()[:: self.PROSODY_STRIDE]
        )
        prosodic = set(ipa.features_by_mode.get("prosodic", ()))
        checked, wrong = 0, []
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for unit in corpus:
                parts = [
                    ipa.get_features(str(c)) for c in ipa.segment(unit).constituents
                ]
                agreed = {
                    key: value
                    for key, value in parts[0].items()
                    if key not in METADATA_ATTRS
                    and key not in prosodic
                    and all(part.get(key) == value for part in parts)
                }
                for key, value in agreed.items():
                    got = ipa.respell(unit, **{key.replace("-", "_"): value})
                    checked += 1
                    if got is not None and got != unit:
                        wrong.append((unit, key, value, got))
        assert len(corpus) > 200, f"corpus collapsed: {len(corpus)}"
        assert checked > 3000, f"sweep did not run: {checked}"
        assert not wrong, f"{len(wrong)} substituted, first: {wrong[:5]}"


class TestToPhoneIsACanonicalizerAndNotAnInverse:
    """It said it was the inverse of ``get_features``, and it is not.

    The claim holds where the projection loses nothing and fails where it
    does. ``to_phone(get_features("a͜ɪ"))`` is ``"a"``, and correctly:
    the phonetic keys of the two are identical, the second constituent
    contributes nothing to the flat read, and the one key that differs is
    ``href`` -- a documentation link, not a fact about the sound, and not
    something that may pick a spelling.

    What holds instead is idempotence on the answer, which is what a
    canonicalizer promises.
    """

    def test_the_inverse_claim_fails_on_a_tied_unit(self, ipa: IPAFeatures) -> None:
        assert ipa.to_phone(ipa.get_features("a͜ɪ")) == "a"
        flat, atom = ipa.get_features("a͜ɪ"), ipa.get_features("a")
        assert {k: v for k, v in flat.items() if k not in METADATA_ATTRS} == {
            k: v for k, v in atom.items() if k not in METADATA_ATTRS
        }
        assert flat["href"] != atom["href"], "the only difference is metadata"

    def test_it_is_idempotent_over_the_inventory(self, ipa: IPAFeatures) -> None:
        checked = 0
        for symbol in ipa.phones:
            once = ipa.to_phone(ipa.get_features(symbol))
            assert once is not None, symbol
            assert ipa.to_phone(ipa.get_features(once)) == once, symbol
            checked += 1
        assert checked > 100, f"sweep did not run: {checked}"
