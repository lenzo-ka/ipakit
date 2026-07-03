"""Tests for IPA <-> X-SAMPA conversion (ipakit.xsampa).

The round-trip guarantee: IPA written in ipakit's conventions (tie-bar
affricates, canonical diacritics) survives ipa -> xsampa -> ipa unchanged. The
only exceptions are inherent X-SAMPA ambiguities where the tie-bar encoding `_`
collides with a diacritic/tone encoding (`_v`, `_T`); ICU's own transliterator
has the identical limitation. Those are pinned explicitly below.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import ipakit
import pytest
from ipakit import IPAFeatures
from ipakit.constants import TIE_BAR

# IPA symbols that cannot round-trip through X-SAMPA: the tie bar maps to `_`,
# but `b_v`/`t_T` re-parse as the voicing diacritic / extra-high tone. Inherent
# to X-SAMPA (ICU agrees), not an ipakit bug.
KNOWN_NON_ROUNDTRIP = {"b͡v", "t͡θ"}


class TestBasicConversion:
    def test_ipa_to_xsampa(self) -> None:
        assert ipakit.ipa_to_xsampa("pʃɑ") == "pSA"
        assert ipakit.ipa_to_xsampa("kæt") == "k{t"
        assert ipakit.ipa_to_xsampa("θɪŋk") == "TINk"

    def test_xsampa_to_ipa(self) -> None:
        assert ipakit.xsampa_to_ipa("pSA") == "pʃɑ"
        assert ipakit.xsampa_to_ipa("k{t") == "kæt"
        assert ipakit.xsampa_to_ipa("TINk") == "θɪŋk"

    def test_affricate_tie_bar(self) -> None:
        # tie bar maps to `_`; t͡ʃ <-> t_S round-trips cleanly
        assert ipakit.ipa_to_xsampa("t͡ʃ") == "t_S"
        assert ipakit.xsampa_to_ipa("t_S") == "t͡ʃ"

    def test_unknown_chars_skipped(self) -> None:
        # digits are not IPA; they are skipped, not emitted
        assert ipakit.ipa_to_xsampa("p4") == "p"
        assert ipakit.xsampa_to_ipa("") == ""

    def test_methods_match_module_functions(self, ipa: IPAFeatures) -> None:
        assert ipa.ipa_to_xsampa("t͡ʃ") == ipakit.ipa_to_xsampa("t͡ʃ") == "t_S"
        assert ipa.xsampa_to_ipa("t_S") == ipakit.xsampa_to_ipa("t_S") == "t͡ʃ"


class TestRoundTrip:
    def test_atomic_symbols_round_trip(self, ipa: IPAFeatures) -> None:
        """Every atomic (non-tie-bar) phone/diacritic round-trips."""
        failures = []
        for sym in list(ipa.phones) + list(ipa.diacritics):
            if TIE_BAR in sym:
                continue
            xs = ipakit.ipa_to_xsampa(sym)
            if xs and ipakit.xsampa_to_ipa(xs) != sym:
                failures.append((sym, xs, ipakit.xsampa_to_ipa(xs)))
        assert failures == []

    def test_tie_bar_affricates_round_trip(self, ipa: IPAFeatures) -> None:
        """Tie-bar affricates round-trip, except the known X-SAMPA collisions."""
        for sym in [p for p in ipa.phones if TIE_BAR in p]:
            xs = ipakit.ipa_to_xsampa(sym)
            back = ipakit.xsampa_to_ipa(xs)
            if sym in KNOWN_NON_ROUNDTRIP:
                assert back != sym  # pinned: documented ambiguity
            else:
                assert back == sym, f"{sym!r} -> {xs!r} -> {back!r}"

    @pytest.mark.parametrize("word", ["kæt", "t͡ʃe͡ɪnd͡ʒ", "θɪŋk", "wˈɔtɚ", "pʃɑ"])
    def test_convention_words_round_trip(self, word: str) -> None:
        """IPA written in ipakit conventions round-trips through X-SAMPA."""
        assert ipakit.xsampa_to_ipa(ipakit.ipa_to_xsampa(word)) == word


# --- ICU cross-check (dev dependency) ----------------------------------------

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "xsampa_table.py"


def _load_script():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("xsampa_table", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestICUCrossCheck:
    def test_shipped_table_matches_icu(self) -> None:
        """The shipped table equals what ICU + curated overrides produce."""
        pytest.importorskip("icukit")
        xt = _load_script()
        assert xt.canonical_pairs() == xt.shipped_pairs()

    def test_validate_subcommand_exit_zero(self) -> None:
        pytest.importorskip("icukit")
        result = subprocess.run(
            [sys.executable, str(_SCRIPT), "validate"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_generate_reproduces_shipped(self) -> None:
        pytest.importorskip("icukit")
        xt = _load_script()
        import xml.etree.ElementTree as ET

        rendered = xt.render(xt.canonical_pairs())
        pairs = {
            m.get("ipa"): m.get("xsampa")
            for m in ET.fromstring(rendered).findall("map")
        }
        assert pairs == xt.shipped_pairs()
