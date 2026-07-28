"""Tests for IPA <-> X-SAMPA conversion (ipakit.xsampa).

The round-trip guarantee: IPA written in ipakit's conventions (tie-bar
affricates, canonical diacritics) survives ipa -> xsampa -> ipa unchanged,
except for the symbols enumerated in the README and pinned below.

`test_round_trip_failures_are_exactly_documented` sweeps the whole inventory
and asserts the failure set *equals* those pins. It is an equality, not a
subset: a symbol that starts failing fails the test, and so does one that stops
-- the README claim and the code cannot drift apart in silence, which is how
`ⱱ` came to vanish mid-string with nothing to notice it.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import ipakit
import pytest
from ipakit import IPAFeatures
from ipakit.constants import SEQ_TIE, TIE_BAR

# IPA symbols that convert but do not come back: the tie bar maps to `_`, and
# `b_v`/`t_T`/`N_m` re-parse as the voicing diacritic / extra-high tone /
# laminal diacritic. Inherent to X-SAMPA (ICU agrees), not an ipakit bug.
KNOWN_NON_ROUNDTRIP = {"b͡v", "t͡θ", "ŋ͡m"}

# The under-tie converts to `_` and reads back as the over-tie: X-SAMPA has a
# single tie encoding, so tie sense does not survive the boundary by design.
TIE_SENSE = {SEQ_TIE}

# Redundant IPA spellings kept out of the (bijective) table: X-SAMPA has one
# encoding where IPA has two, and it belongs to the canonical spelling given
# here, which does round-trip. See EXCLUDE in scripts/xsampa_table.py.
FOLDED_SPELLINGS = {"˞": "ʴ", "̀": "˨", "́": "˦", "̄": "˧", "ʻ": "ʰ"}

# Symbols X-SAMPA cannot spell at all -- no notation exists for the labiodental
# flap, glottalization or schwa release, and inventing one would collide with
# notation already in use. See UNMAPPABLE in scripts/xsampa_table.py.
UNENCODABLE = {"ⱱ", "ˀ", "ᵊ"}

# Conversion drops both groups (or raises, under `strict=True`).
DROPPED = set(FOLDED_SPELLINGS) | UNENCODABLE


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
        """Every atomic (non-tie) phone/diacritic round-trips.

        Both tie characters are excluded: X-SAMPA has a single tie
        encoding, so the under-tie projects onto the over-tie at the
        conversion boundary and returns as the over-tie by design.
        """
        failures = []
        for sym in list(ipa.phones) + list(ipa.diacritics):
            if TIE_BAR in sym or SEQ_TIE in sym or sym in DROPPED:
                continue
            xs = ipakit.ipa_to_xsampa(sym)
            if ipakit.xsampa_to_ipa(xs) != sym:
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

    @pytest.mark.parametrize("word", ["kæt", "t͡ʃe͜ɪnd͡ʒ", "θɪŋk", "wˈɔtɚ", "pʃɑ"])
    def test_convention_words_round_trip(self, word: str) -> None:
        """IPA written in ipakit conventions round-trips through X-SAMPA."""
        assert ipakit.xsampa_to_ipa(ipakit.ipa_to_xsampa(word)) == word

    def test_round_trip_failures_are_exactly_documented(self, ipa: IPAFeatures) -> None:
        """The whole inventory round-trips but for the documented exceptions.

        Equality, not containment: this is the guard that keeps the README's
        enumerated exception list and the shipped table in step.
        """
        dropped, collided = set(), set()
        for sym in list(ipa.phones) + list(ipa.diacritics):
            xs = ipakit.ipa_to_xsampa(sym)
            if not xs:
                dropped.add(sym)
            elif ipakit.xsampa_to_ipa(xs) != sym:
                collided.add(sym)
        assert dropped == DROPPED
        assert collided == KNOWN_NON_ROUNDTRIP | TIE_SENSE

    def test_an_alias_spelling_cannot_join_the_dropped_set(
        self, ipa: IPAFeatures
    ) -> None:
        """The sweep above walks the registered inventory, and the accepted
        alias spellings are not in it -- so they could join the dropped set
        without the equality noticing, and had: `ipa_to_xsampa("ʧ")` was
        `""`, deleting the affricate mid-word. An alias converts as the
        thing it spells; coming back it yields the canonical spelling,
        which is the documented alias loss (docs/ties.md), not a drop.
        """
        for alias, canonical in ipa.ligature_map.items():
            xs = ipakit.ipa_to_xsampa(alias)
            assert xs == ipakit.ipa_to_xsampa(canonical) != ""
            assert ipakit.xsampa_to_ipa(xs) == canonical

    @pytest.mark.parametrize("sym,canonical", sorted(FOLDED_SPELLINGS.items()))
    def test_canonical_spelling_of_a_folded_symbol_round_trips(
        self, sym: str, canonical: str
    ) -> None:
        """The sound survives; only the redundant spelling of it does not."""
        assert ipakit.ipa_to_xsampa(sym) == ""
        xs = ipakit.ipa_to_xsampa(canonical)
        assert xs and ipakit.xsampa_to_ipa(xs) == canonical


class TestUnconvertible:
    """A symbol X-SAMPA cannot spell is dropped leniently, or raises strictly."""

    def test_dropped_symbol_takes_its_neighbours_adjacency(self) -> None:
        # Lenient conversion deletes `ⱱ` and closes the gap, so `k` and `t`
        # come out adjacent. Documented, and the reason `strict` exists.
        assert ipakit.ipa_to_xsampa("kⱱt") == "kt"

    @pytest.mark.parametrize("sym", sorted(DROPPED))
    def test_strict_raises_naming_the_symbol(self, sym: str) -> None:
        with pytest.raises(ValueError, match="unknown symbols"):
            ipakit.ipa_to_xsampa(f"k{sym}t", strict=True)

    def test_strict_names_the_offending_symbol(self) -> None:
        with pytest.raises(ValueError) as exc:
            ipakit.ipa_to_xsampa("kⱱt", strict=True)
        assert "ⱱ" in str(exc.value)


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
        pytest.importorskip("icu")
        xt = _load_script()
        assert xt.canonical_pairs() == xt.shipped_pairs()

    def test_validate_subcommand_exit_zero(self) -> None:
        pytest.importorskip("icu")
        result = subprocess.run(
            [sys.executable, str(_SCRIPT), "validate"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_unlisted_icu_passthrough_is_an_error(self) -> None:
        """A symbol ICU cannot map must be declared, never silently omitted.

        Omission is invisible at runtime -- the symbol just disappears from
        every conversion -- so the generator refuses to produce a table with an
        undeclared gap in it.
        """
        pytest.importorskip("icu")
        xt = _load_script()
        xt.UNMAPPABLE = {}
        with pytest.raises(ValueError, match="EXCLUDE nor UNMAPPABLE"):
            xt.canonical_pairs()

    def test_generate_reproduces_shipped(self) -> None:
        pytest.importorskip("icu")
        xt = _load_script()
        import xml.etree.ElementTree as ET

        rendered = xt.render(xt.canonical_pairs())
        pairs = {
            m.get("ipa"): m.get("xsampa")
            for m in ET.fromstring(rendered).findall("map")
        }
        assert pairs == xt.shipped_pairs()
