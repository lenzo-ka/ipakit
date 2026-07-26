"""Unicode canonicalization at ingest.

Input may arrive precomposed (NFC, e.g. "ã" U+00E3) or decomposed (base +
combining mark). Matching must be independent of the form: the parser works
on NFD internally, except that registered symbols stored precomposed in
ipa.xml (ä, ç, ť) are recomposed to match their inventory keys. Output
tokens are emitted in NFC so both input forms yield identical results.
"""

import unicodedata

import pytest
from ipakit import IPAFeatures


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


# (precomposed, decomposed) pairs; the registered forms differ per symbol:
# ã is unregistered (parses as a + nasalization), ä/ç/ť are registered phones.
NFC_NFD_PAIRS = [
    ("ã", "ã"),  # ã: unregistered, base + diacritic
    ("ä", "ä"),  # ä: registered precomposed
    ("ç", "ç"),  # ç: registered precomposed
    ("ť", "ť"),  # ť: registered precomposed
]


class TestCanonicalization:
    def test_precomposed_and_decomposed_parse_identically(
        self, ipa: IPAFeatures
    ) -> None:
        for pre, dec in NFC_NFD_PAIRS:
            assert ipa.parse(pre) == ipa.parse(dec), f"{pre!r} vs {dec!r}"

    def test_precomposed_nasalized_vowel_not_dropped(self, ipa: IPAFeatures) -> None:
        # Regression: precomposed ã parsed to [] and was silently dropped.
        assert ipa.parse("ã") == [("a", ["̃"])]
        assert ipa.tokenize_ipa("ã") != []

    def test_registered_precomposed_phones_resolve_from_both_forms(
        self, ipa: IPAFeatures
    ) -> None:
        for pre, dec in NFC_NFD_PAIRS[1:]:  # the registered ones
            feats_pre = ipa.get_features(pre)
            feats_dec = ipa.get_features(dec)
            assert feats_pre, f"{pre!r} should resolve"
            assert feats_pre == feats_dec

    def test_decomposed_cedilla_no_longer_misparses_as_bare_c(
        self, ipa: IPAFeatures
    ) -> None:
        # Decomposed ç used to parse as bare "c" with the cedilla skipped.
        assert ipa.parse("ç") == [("ç", [])]

    def test_canonicalize_unicode_idempotent(self, ipa: IPAFeatures) -> None:
        for pre, dec in NFC_NFD_PAIRS:
            once = ipa.canonicalize_unicode(pre)
            assert ipa.canonicalize_unicode(once) == once
            assert ipa.canonicalize_unicode(dec) == once


class TestEmissionForm:
    def test_tokens_are_nfc(self, ipa: IPAFeatures) -> None:
        for pre, dec in NFC_NFD_PAIRS:
            for form in (pre, dec):
                for token in ipa.tokenize_ipa(form):
                    assert token == unicodedata.normalize("NFC", token)

    def test_both_forms_tokenize_to_same_output(self, ipa: IPAFeatures) -> None:
        for pre, dec in NFC_NFD_PAIRS:
            assert ipa.tokenize_ipa(pre) == ipa.tokenize_ipa(dec)

    def test_tie_bar_tokens_unaffected(self, ipa: IPAFeatures) -> None:
        # Tie-bar sequences have no precomposed forms; NFC emission must not
        # alter them.
        assert ipa.tokenize_ipa("t͡sa") == ["t͡s", "a"]

    def test_normalize_ipa_emits_nfc(self, ipa: IPAFeatures) -> None:
        out = ipa.normalize_ipa("ä")
        assert out == unicodedata.normalize("NFC", out)


class TestDownstreamConsistency:
    def test_segment_distance_form_independent(self, ipa: IPAFeatures) -> None:
        for pre, dec in NFC_NFD_PAIRS:
            assert ipa.segment_distance(pre, "a") == ipa.segment_distance(dec, "a")

    def test_contains_form_independent(self, ipa: IPAFeatures) -> None:
        for pre, dec in NFC_NFD_PAIRS[1:]:
            assert (pre in ipa) and (dec in ipa)

    def test_get_phone_form_independent(self, ipa: IPAFeatures) -> None:
        for pre, dec in NFC_NFD_PAIRS[1:]:
            p1, p2 = ipa.get_phone(pre), ipa.get_phone(dec)
            assert p1 is not None and p1 is p2
