"""Pins eSpeak NG's source-level mnemonic-to-IPA rules."""

from collections import OrderedDict

from scripts.espeak_vocabularies import Phone, default_ipa, spelling, tone_spellings


def test_default_ipa_matches_pinned_write_ph_mnemonic_rules() -> None:
    assert default_ipa(Phone("O~", ("vwl",))) == "ɔ̃"
    assert default_ipa(Phone("o:", ("vwl",))) == "oː"
    assert default_ipa(Phone("p#", ("vls blb stp",))) == "pʰ"
    assert default_ipa(Phone("I2#", ("vwl",))) == "ɪ"
    assert default_ipa(Phone("l/3", ("liquid",))) == "l"


def test_explicit_ipa_wins_and_embedded_codepoints_decode() -> None:
    assert spelling(Phone("m-", ("ipa mU+0329",))) == ("m̩", None)
    assert spelling(Phone("O~", ("ipa ɒ", "vwl"))) == ("ɒ", None)


def test_non_ipa_source_phonemes_remain_declared_refusals() -> None:
    assert spelling(Phone("#a", ("virtual",))) == (None, "control-or-virtual")
    assert spelling(Phone(";", ("ipa NULL",))) == (None, "conditional-null")


def test_tone_directive_derives_chao_letters_and_word_pause_is_boundary() -> None:
    inventory = OrderedDict(
        (
            ("35", Phone("35", ("stress", "Tone(30, 50, envelope/p_rise, NULL)"))),
            ("214", Phone("214", ("stress", "Tone(18, 42, envelope/p_214, NULL)"))),
            ("51", Phone("51", ("stress", "Tone(50, 10, envelope/p_fall, NULL)"))),
        )
    )
    tones = tone_spellings(inventory)
    assert spelling(inventory["35"], tones) == (
        "˧˥",
        None,
    )
    assert spelling(inventory["214"], tones) == (
        "˨˩˦",
        None,
    )
    assert spelling(Phone("_|", ("pause", "length 1"))) == ("#", None)
    assert spelling(Phone("_:", ("pause", "length 75"))) == (None, "control-or-virtual")


def test_tone_labels_do_not_determine_pitch_and_all_tone_content_maps() -> None:
    inventory = OrderedDict(
        (
            ("1", Phone("1", ("stress", "Tone(50, 50, envelope/p_level, NULL)"))),
            ("4", Phone("4", ("stress", "Tone(20, 10, envelope/p_fall, NULL)"))),
            ("5", Phone("5", ("stress", "Tone(10, 30, envelope/p_rise, NULL)"))),
            ("6", Phone("6", ("stress", "Tone(20, 20, envelope/p_level, NULL)"))),
            ("˥", Phone("˥", ("stress", "Tone(50, 50, envelope/p_level, NULL)"))),
        )
    )
    tones = tone_spellings(inventory)
    levels = dict(zip("˩˨˧˦˥", range(5), strict=True))
    # Chao band boundaries are a transcription judgment.  What the source
    # fixes unequivocally is high-level 1, falling 4, rising 5, and their
    # relative pitch ordering, so assert those relations rather than a
    # particular quantizer's absolute letters.
    assert tones["1"][0] == tones["1"][-1]
    assert levels[tones["1"][0]] > levels[tones["4"][0]] > levels[tones["4"][-1]]
    assert levels[tones["5"][0]] < levels[tones["5"][-1]] < levels[tones["1"][0]]
    assert spelling(inventory["6"], tones)[0] is not None
    assert tones["˥"] == "˥"
