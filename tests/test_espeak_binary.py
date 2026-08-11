"""Black-box agreement with the pinned eSpeak NG phoneme renderer."""

from __future__ import annotations

import os
import shutil
import subprocess

import pytest
from ipakit.bridges import EspeakBridge

ESPEAK = os.environ.get("ESPEAK_NG_BINARY") or shutil.which("espeak-ng")


def _output(language: str, mode: str, word: str) -> str:
    assert ESPEAK is not None
    return subprocess.run(
        [ESPEAK, "-v", language, mode, "-q", word],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.mark.skipif(ESPEAK is None, reason="eSpeak NG binary is absent")
@pytest.mark.parametrize(
    ("language", "word"),
    [
        pytest.param("fr", "bonjour", id="french-nasal-vowel"),
        pytest.param("de", "hallo", id="german-long-vowel"),
        pytest.param("en", "hello", id="english-fixture-language"),
        pytest.param("hi", "हवा", id="hindi-imported-h-and-v"),
        pytest.param("ml", "മരം", id="malayalam-imported-r"),
        pytest.param("kk", "ға", id="kazakh-imported-uvular-r"),
        pytest.param("hr", "r", id="croatian-imported-trill"),
        pytest.param("it", "gli", id="italian-imported-palatal-lateral"),
        pytest.param("gd", "ruadh", id="gaelic-unqualified-same-table-import"),
        pytest.param("el", "γεια", id="greek-script"),
        pytest.param("sw", "habari", id="swahili-rhotic"),
    ],
)
def test_pinned_binary_mnemonics_render_as_its_ipa(language: str, word: str) -> None:
    version = subprocess.run(
        [ESPEAK, "--version"], check=True, capture_output=True, text=True
    ).stdout
    assert "1.52.0" in version
    mnemonic = _output(language, "-x", word)
    expected = _output(language, "--ipa", word)
    assert EspeakBridge(language).read(mnemonic).to_ipa() == expected


@pytest.mark.skipif(ESPEAK is None, reason="eSpeak NG binary is absent")
def test_pinned_binary_tone_language_x_output_round_trips() -> None:
    # For tone phonemes eSpeak 1.52.0's --ipa prints mnemonic digits through
    # the default character table, so it is not IPA ground truth.  Validate
    # only that the pinned binary's -x output is readable and byte-exact.
    mnemonic = _output("cmn", "-x", "妈麻马骂")
    bridge = EspeakBridge("cmn")
    assert bridge.emit(bridge.read(mnemonic)) == mnemonic

    # A category-6 Cantonese tone is real tonal content even though its label
    # lies outside the old, erroneous 1..5 contour-digit gate.
    cantonese = _output("yue", "-x", "事")
    assert cantonese == "s'i6_|"
    yue = EspeakBridge("yue")
    assert yue.emit(yue.read(cantonese)) == cantonese
