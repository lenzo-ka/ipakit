"""Sentinels a caller cannot tell from a real answer.

Each case here returned something that reads as a result -- a phone, a
feature bundle -- for input the library had in fact failed to
understand. A wrong answer delivered confidently is worse than an error,
and worse than an empty one.
"""

import ipakit
import pytest
from ipakit import IPAFeatures


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


class TestEmptyBundleDoesNotNameAPhone:
    """`to_phone({})` returned '␣'. Every phone satisfies a bundle that
    asks nothing, and the fewest-extras tie-break then picks silence -- so
    any failed read upstream came back as a confident phone."""

    def test_empty_bundle_raises(self, ipa: IPAFeatures) -> None:
        with pytest.raises(ValueError, match="empty feature bundle"):
            ipa.to_phone({})

    def test_metadata_only_bundle_raises(self, ipa: IPAFeatures) -> None:
        # Metadata keys are stripped before matching, so a bundle of
        # nothing but metadata is empty by the same argument.
        with pytest.raises(ValueError, match="empty feature bundle"):
            ipa.to_phone({"class": "phone", "href": "Whatever"})

    def test_silence_is_still_reachable_when_asked_for(self, ipa: IPAFeatures) -> None:
        # Refusing the empty bundle must not make silence unnameable.
        assert ipa.to_phone({"manner": "silence"}) == "␣"

    def test_a_real_bundle_still_realizes(self, ipa: IPAFeatures) -> None:
        assert ipa.to_phone({"manner": "plosive", "place": "alveolar"}) == "t"


class TestRealizationResolvesAliases:
    """`to_phone` was the one query path that compared raw strings, so a
    friendly alias every other entry point accepts returned a silent
    None -- indistinguishable from 'unattested combination'."""

    def test_alias_and_canonical_agree(self, ipa: IPAFeatures) -> None:
        alias = ipa.to_phone(
            {"place": "labial-velar", "manner": "plosive", "voiced": "-"}
        )
        canonical = ipa.to_phone(
            {"place": "bilabial^velar", "manner": "plosive", "voiced": "-"}
        )
        assert alias == canonical == "k͡p"

    def test_realization_agrees_with_the_query_paths(self, ipa: IPAFeatures) -> None:
        # phones_matching, find and respell all took the alias already.
        bundle = {"place": "labial-velar", "manner": "plosive", "voiced": "-"}
        assert ipa.to_phone(bundle) in ipa.phones_matching(
            {"place": "labial-velar", "manner": "plosive"}
        )

    def test_an_unattested_bundle_still_returns_none(self, ipa: IPAFeatures) -> None:
        # None must keep meaning "nothing matches", not "spelling problem".
        assert ipa.to_phone({"manner": "vowel", "place": "velar"}) is None


class TestNaturalClassRefusesWhatItCannotRead:
    """It filtered out members it failed to resolve and reported the
    shared features of the rest -- asserting of the unread member
    something it never checked."""

    def test_unresolvable_member_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot resolve"):
            ipakit.natural_class(["p", "NOTAPHONE"])

    def test_the_error_names_the_offender(self) -> None:
        with pytest.raises(ValueError, match="NOTAPHONE"):
            ipakit.natural_class(["p", "NOTAPHONE"])

    def test_real_classes_are_unaffected(self) -> None:
        assert ipakit.natural_class(["p", "t", "k"])["manner"] == "plosive"
        assert ipakit.natural_class(["i", "e", "ɛ"])["backness"] == "front"

    def test_an_empty_set_is_still_empty_not_an_error(self) -> None:
        # Asking for the class of nothing is a question with an answer.
        assert ipakit.natural_class([]) == {}

    def test_a_genuinely_shared_nothing_is_not_an_error(self) -> None:
        # Resolvable phones sharing no feature value differ from
        # unresolvable ones: the empty result is the true answer.
        shared = ipakit.natural_class(["p", "a"])
        assert shared.get("manner") is None
