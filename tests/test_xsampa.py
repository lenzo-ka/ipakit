"""Tests for IPA <-> X-SAMPA conversion (ipakit.xsampa).

The round-trip guarantee: IPA written in ipakit's conventions (tie-bar
affricates, canonical diacritics) survives ipa -> xsampa -> ipa unchanged,
except for the symbols enumerated in the README and pinned below.

`test_round_trip_failures_are_exactly_documented` sweeps the whole inventory
and asserts the failure set *equals* those pins. It is an equality, not a
subset: a symbol that starts failing fails the test, and so does one that stops
-- the README claim and the code cannot drift apart in silence, which is how
`ⱱ` came to vanish mid-string with nothing to notice it.

That sweep walks `ipa.phones + ipa.diacritics`, which is the *registered*
inventory: a base carrying a mark, and two bases side by side, are composed on
the fly and are members of neither list. `TestComposedRoundTrip` is the same
equality over that product space. It pins seventeen collisions, none of them
reachable from the registered inventory the atomic sweep walks. Fourteen change
the sound; the other three fold onto a registered spelling of the same sound.
Nothing in the suite converted such a string before it.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import ipakit
import pytest
from ipakit import IPAFeatures

from tests.corpus import FEATURES, TIES, self_spelling_phones, single_mark_units

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "xsampa_table.py"


def _load_script():  # type: ignore[no-untyped-def]
    """A fresh instance of the generator, which is not an importable module.

    Fresh each call on purpose: one test below mutates ``UNMAPPABLE`` to
    check that an undeclared passthrough is an error, and must not leave
    that behind for anything else. ICU is imported lazily inside the
    script, so loading it needs no dev dependency.
    """
    spec = importlib.util.spec_from_file_location("xsampa_table", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_TABLE = _load_script()

# IPA symbols that convert but do not come back: the tie bar maps to `_`, and
# `b_v`/`t_T`/`N_m` re-parse as the voicing diacritic / extra-high tone /
# laminal diacritic. Inherent to X-SAMPA (ICU agrees), not an ipakit bug.
KNOWN_NON_ROUNDTRIP = {"b͡v", "t͡θ", "ŋ͡m"}

# The under-tie converts to `_` and reads back as the over-tie: X-SAMPA has a
# single tie encoding, so tie sense does not survive the boundary by design.
TIE_SENSE = {FEATURES.seq_tie}

# Redundant IPA spellings kept out of the (bijective) table: X-SAMPA has one
# encoding where IPA has two, and it belongs to the canonical spelling given
# here, which does round-trip.
#
# Read from the generator rather than restated. These two used to be a
# hand copy with a comment naming what they were a copy of, in a file
# that already loads the script for the tests below -- and the ICU
# cross-check that would have caught the drift is skipped wherever the
# dev dependency is absent, which is everywhere it usually matters.
FOLDED_SPELLINGS = _TABLE.EXCLUDE

# Symbols X-SAMPA cannot spell at all -- no notation exists for the labiodental
# flap, glottalization or schwa release, and inventing one would collide with
# notation already in use. The script keeps the reason beside each.
UNENCODABLE = set(_TABLE.UNMAPPABLE)

# Conversion drops both groups (or raises, under `strict=True`).
DROPPED = set(FOLDED_SPELLINGS) | UNENCODABLE

# Everything above is a failure an *atomic* symbol already has. A composed form
# containing one inherits it, which says nothing about composition, so the
# sweeps below are run over forms whose every part round-trips alone.
ATOMIC_FAILURES = DROPPED | KNOWN_NON_ROUNDTRIP | TIE_SENSE

# Composed forms that do not come back, keyed to what comes back instead. The
# cause is one property of the shipped table: it is not prefix-free, so a join
# between two encodings can spell a key a third entry already claims, and
# longest-match reads that one. `to_xsampa` is compositional over this whole
# space (`test_composition_is_lossless_on_the_way_out`), so the loss is in the
# re-reading every time, never in the writing.

# `ʴ` encodes as `` ` ``, which is also X-SAMPA's retroflex suffix, so a base
# plus the rhotacized modifier spells the retroflex phone: X-SAMPA has one
# notation where IPA has two sounds. Inherent to X-SAMPA, not an ipakit bug,
# and the same shape as the tie collisions docs/ties.md names. Ten of these
# change the sound (`rhotacized` out, `retroflex` in); `əʴ`/`ɜʴ` do not --
# `ɚ` and `ɝ` are the registered spellings of exactly those, so those two
# are `from_wild` canonicalizing, which ties.md says it will.
RHOTIC_SUFFIX_COLLISION = {
    "dʴ": "ɖ",
    "d͡zʴ": "d͡ʐ",
    "lʴ": "ɭ",
    "nʴ": "ɳ",
    "rʴ": "ɽ",
    "sʴ": "ʂ",
    "tʴ": "ʈ",
    "t͡sʴ": "t͡ʂ",
    "zʴ": "ʐ",
    "ɹʴ": "ɻ",
    "əʴ": "ɚ",
    "ɜʴ": "ɝ",
}

# `ʱ` had a curated encoding, `_hh`, which X-SAMPA does not define. It extended
# `_h` (`ʰ`), so pre-aspiration written before a glottal fricative spelled it and
# `ʰh`/`ʰɦ` both read back as `ʱ`. That ambiguity was ipakit's own rather than one
# X-SAMPA handed it -- the sixteen below are the standard's -- and the pin said
# it would be what reported the collision ending. It ended by the encoding being
# dropped rather than re-chosen: `ʱ` is unmappable now, declined rather than
# impossible, which is why its reason in the generator reads differently from the
# four marks X-SAMPA genuinely cannot spell.

# `|\|\` (ǁ) is two `|\` (ǀ), so a doubled dental click spells the alveolar
# lateral one and `ǀǁ` re-splits after the first two. Standard X-SAMPA on both
# sides; adjacent clicks are the only base pair in the inventory whose
# encodings run together.
CLICK_RUN_COLLISION = {"ǀǀ": "ǁ", "ǀǁ": "ǁǀ"}

# `t_>` belongs to `ť`, which is registered (the legacy caron ejective), so the
# composed spelling folds onto it. The two differ in `href` and in nothing
# phonetic: the same fold as FOLDED_SPELLINGS, one level up, and the same
# behavior docs/ties.md describes for a registered compound coming back
# through `from_wild` -- expected, not a loss.
EJECTIVE_FOLD = {"tʼ": "ť"}

#: Base + one mark, in either position. The pairs are elsewhere.
COMPOSED_NON_ROUNDTRIP = {
    **RHOTIC_SUFFIX_COLLISION,
    **EJECTIVE_FOLD,
}

#: Two bases written side by side.
ADJACENT_PAIR_NON_ROUNDTRIP = CLICK_RUN_COLLISION


def _composes_from_survivors(form: str) -> bool:
    """True if every part of ``form`` round-trips on its own.

    Stated as a substring test over the atomic failure set rather than a
    membership test, because the parts of a composed form are not
    themselves in the sweep -- a diphthong carrying a mark holds a
    sequential tie somewhere inside it.
    """
    return not any(failure in form for failure in ATOMIC_FAILURES)


def _round_trip_failures(forms: list[str]) -> tuple[set[str], dict[str, str]]:
    """The forms that convert to nothing, and those that come back changed."""
    dropped: set[str] = set()
    collided: dict[str, str] = {}
    for form in forms:
        xsampa = ipakit.to_xsampa(form)
        if not xsampa:
            dropped.add(form)
            continue
        back = ipakit.from_xsampa(xsampa)
        if back != form:
            collided[form] = back
    return dropped, collided


class TestBasicConversion:
    def test_to_xsampa(self) -> None:
        assert ipakit.to_xsampa("pʃɑ") == "pSA"
        assert ipakit.to_xsampa("kæt") == "k{t"
        assert ipakit.to_xsampa("θɪŋk") == "TINk"

    def test_from_xsampa(self) -> None:
        assert ipakit.from_xsampa("pSA") == "pʃɑ"
        assert ipakit.from_xsampa("k{t") == "kæt"
        assert ipakit.from_xsampa("TINk") == "θɪŋk"

    def test_affricate_tie_bar(self) -> None:
        # tie bar maps to `_`; t͡ʃ <-> t_S round-trips cleanly
        assert ipakit.to_xsampa("t͡ʃ") == "t_S"
        assert ipakit.from_xsampa("t_S") == "t͡ʃ"

    def test_unknown_chars_skipped(self) -> None:
        # digits are not IPA; they are skipped, not emitted
        assert ipakit.to_xsampa("p4") == "p"
        assert ipakit.from_xsampa("") == ""

    def test_methods_match_module_functions(self, ipa: IPAFeatures) -> None:
        assert ipa.to_xsampa("t͡ʃ") == ipakit.to_xsampa("t͡ʃ") == "t_S"
        assert ipa.from_xsampa("t_S") == ipakit.from_xsampa("t_S") == "t͡ʃ"


class TestRoundTrip:
    def test_atomic_symbols_round_trip(self, ipa: IPAFeatures) -> None:
        """Every atomic (non-tie) phone/diacritic round-trips.

        Both tie characters are excluded: X-SAMPA has a single tie
        encoding, so the under-tie projects onto the over-tie at the
        conversion boundary and returns as the over-tie by design.
        """
        failures = []
        for sym in list(ipa.phones) + list(ipa.diacritics):
            if TIES & set(sym) or sym in DROPPED:
                continue
            xs = ipakit.to_xsampa(sym)
            if ipakit.from_xsampa(xs) != sym:
                failures.append((sym, xs, ipakit.from_xsampa(xs)))
        assert failures == []

    def test_tie_bar_affricates_round_trip(self, ipa: IPAFeatures) -> None:
        """Tie-bar affricates round-trip, except the known X-SAMPA collisions."""
        for sym in [p for p in ipa.phones if ipa.tie_bar in p]:
            xs = ipakit.to_xsampa(sym)
            back = ipakit.from_xsampa(xs)
            if sym in KNOWN_NON_ROUNDTRIP:
                assert back != sym  # pinned: documented ambiguity
            else:
                assert back == sym, f"{sym!r} -> {xs!r} -> {back!r}"

    @pytest.mark.parametrize("word", ["kæt", "t͡ʃe͜ɪnd͡ʒ", "θɪŋk", "wˈɔtɚ", "pʃɑ"])
    def test_convention_words_round_trip(self, word: str) -> None:
        """IPA written in ipakit conventions round-trips through X-SAMPA."""
        assert ipakit.from_xsampa(ipakit.to_xsampa(word)) == word

    def test_round_trip_failures_are_exactly_documented(self, ipa: IPAFeatures) -> None:
        """The whole inventory round-trips but for the documented exceptions.

        Equality, not containment: this is the guard that keeps the README's
        enumerated exception list and the shipped table in step. What it
        quantifies over is the *registered* inventory; `TestComposedRoundTrip`
        is the same equality over the forms composed from it.
        """
        dropped, collided = _round_trip_failures(
            list(ipa.phones) + list(ipa.diacritics)
        )
        assert dropped == DROPPED
        assert set(collided) == KNOWN_NON_ROUNDTRIP | TIE_SENSE

    def test_an_alias_spelling_cannot_join_the_dropped_set(
        self, ipa: IPAFeatures
    ) -> None:
        """The sweep above walks the registered inventory, and the accepted
        alias spellings are not in it -- so they could join the dropped set
        without the equality noticing, and had: `to_xsampa("ʧ")` was
        `""`, deleting the affricate mid-word. An alias converts as the
        thing it spells; coming back it yields the canonical spelling,
        which is the documented alias loss (docs/ties.md), not a drop.
        """
        for alias, canonical in ipa.ligature_map.items():
            xs = ipakit.to_xsampa(alias)
            assert xs == ipakit.to_xsampa(canonical) != ""
            assert ipakit.from_xsampa(xs) == canonical

    @pytest.mark.parametrize("sym,canonical", sorted(FOLDED_SPELLINGS.items()))
    def test_canonical_spelling_of_a_folded_symbol_round_trips(
        self, sym: str, canonical: str
    ) -> None:
        """The sound survives; only the redundant spelling of it does not."""
        assert ipakit.to_xsampa(sym) == ""
        xs = ipakit.to_xsampa(canonical)
        assert xs and ipakit.from_xsampa(xs) == canonical


class TestComposedRoundTrip:
    """The same equality as `TestRoundTrip`, over composed forms.

    **The space.** Two extents, both swept whole -- neither is sampled.

    * ``tests.corpus.single_mark_units()``: every registered base plus one
      registered mark, in **either** position, kept when it spells itself
      back. About 7300 forms of the 9111 in the canonical corpus, the rest
      dropping out under the filter below.
    * every ordered pair of registered bases written side by side, about
      16100 of them.

    **The filter.** A form is swept only when every part of it round-trips
    alone (``_composes_from_survivors``). A form holding `ⱱ` loses it
    whatever it is joined to, which is `TestRoundTrip`'s finding restated,
    not composition's. What is left asks the one question the atomic sweep
    cannot: does *joining two survivors* lose something?

    It does, seventeen times -- fourteen of them changing the sound, three
    folding onto a registered spelling of the same sound. All seventeen are
    the same mechanism: the shipped table is not prefix-free, so a key can
    span the join. Each is pinned above with the reason it collides.

    **What a pin here means.** X-SAMPA is an ASCII convention for writing
    IPA, not a peer alphabet -- `from_xsampa` hands its result to
    ``from_wild`` to canonicalize (`ipakit/xsampa.py`), and
    [docs/ties.md](../docs/ties.md) "Ties across phoneset conversions" is
    the governing text. So a form that comes back as the *registered*
    spelling of the same sound is that document's behavior working, not a
    defect: `əʴ → ɚ`, `ɜʴ → ɝ` and `tʼ → ť` are pinned as expected. The
    other fourteen are losses the convention itself imposes -- X-SAMPA has
    one notation where IPA has two sounds -- with `ʰh`/`ʰɦ` the single
    exception, where the ambiguity comes from ipakit's own `_hh` and its
    pin says so.

    **What is out of the space, and why.** Tie sense and the three
    collisions ties.md names (`b͡v`, `t͡θ`, `ŋ͡m`) are excluded by the
    filter: they are `TestRoundTrip`'s pins, and a composed form carrying
    one inherits it. So are *unregistered* tie chains written between two
    bases -- coming back, ties.md gives those to the sense heuristic
    rather than to a round trip, so sweeping them would measure that
    heuristic and not composition. Registered compounds are in the space,
    as bases.
    """

    def _marked_units(self) -> list[str]:
        return [unit for unit in single_mark_units() if _composes_from_survivors(unit)]

    def _bases(self) -> list[str]:
        return [
            phone for phone in self_spelling_phones() if _composes_from_survivors(phone)
        ]

    def _marked_joins(self) -> list[tuple[str, str]]:
        """The marked corpus as the two parts each form was written from."""
        corpus = set(self._marked_units())
        joins = [
            parts
            for base in self._bases()
            for mark in FEATURES.diacritics
            for parts in ((base, mark), (mark, base))
            if "".join(parts) in corpus
        ]
        assert len(joins) == len(corpus), "a marked form was not a base and one mark"
        return joins

    def test_the_swept_space_has_not_collapsed(self) -> None:
        """A floor and a shape, so neither sweep can go quietly vacuous.

        The floor alone cannot tell that a whole class has dropped out, and
        one class matters here: the tie-bar compounds are the forms whose
        encoding already contains a `_`, which is where the table stops
        being prefix-free.
        """
        marked, bases = self._marked_units(), self._bases()
        assert len(marked) > 5000, f"marked sweep covered only {len(marked)} forms"
        assert len(bases) > 100, f"pair sweep covered only {len(bases)} bases"
        tied = [unit for unit in marked if FEATURES.tie_bar in unit]
        assert len(tied) > 100, f"only {len(tied)} tied forms in the marked sweep"

    def test_composed_round_trip_failures_are_exactly_documented(self) -> None:
        """Base + mark, both positions. Equality, not containment."""
        dropped, collided = _round_trip_failures(self._marked_units())
        assert dropped == set()
        assert collided == COMPOSED_NON_ROUNDTRIP

    def test_adjacent_pair_round_trip_failures_are_exactly_documented(self) -> None:
        """Base + base. Same equality over the other half of the product."""
        bases = self._bases()
        pairs = [left + right for left in bases for right in bases]
        dropped, collided = _round_trip_failures(pairs)
        assert dropped == set()
        assert collided == ADJACENT_PAIR_NON_ROUNDTRIP

    def test_composition_is_lossless_on_the_way_out(self) -> None:
        """`to_xsampa` of a join is the join of the `to_xsampa`s, always.

        This is what makes the pins above a statement about the *table*
        rather than a list of strings that happen to fail. Writing loses
        nothing at a boundary over either extent, so every failure pinned
        here is the reader re-segmenting -- and a future failure that is
        *not* that shape breaks this test instead of quietly joining the
        list, which is the distinction between one more X-SAMPA ambiguity
        and a defect in the encoder.
        """
        bases = self._bases()
        joins = [*self._marked_joins(), *((a, b) for a in bases for b in bases)]
        encoded = {part: ipakit.to_xsampa(part) for pair in joins for part in pair}
        for left, right in joins:
            assert encoded[left] + encoded[right] == ipakit.to_xsampa(left + right), (
                left + right
            )
        assert len(joins) > 20000, f"sweep covered only {len(joins)} joins"


def test_the_readme_enumerates_every_pinned_exception() -> None:
    """Every symbol and form pinned here is written down in the README.

    The equality sweeps hold the *code* half of "every other exception is
    enumerated here": they say the failure set is exactly these pins. The
    document half was unguarded, and had drifted -- `^` sat in
    ``UNMAPPABLE`` while the README's unencodable bullet named three
    symbols, so a reader was told an enumeration that was short by one.
    """
    readme = (_SCRIPT.parent.parent / "README.md").read_text(encoding="utf-8")
    pinned = {
        *DROPPED,
        *KNOWN_NON_ROUNDTRIP,
        *COMPOSED_NON_ROUNDTRIP,
        *COMPOSED_NON_ROUNDTRIP.values(),
        *ADJACENT_PAIR_NON_ROUNDTRIP,
        *ADJACENT_PAIR_NON_ROUNDTRIP.values(),
    }
    missing = sorted(form for form in pinned if form not in readme)
    assert missing == [], f"pinned but not enumerated in the README: {missing}"


class TestUnconvertible:
    """A symbol X-SAMPA cannot spell is dropped leniently, or raises strictly."""

    def test_dropped_symbol_takes_its_neighbors_adjacency(self) -> None:
        # Lenient conversion deletes `ⱱ` and closes the gap, so `k` and `t`
        # come out adjacent. Documented, and the reason `strict` exists.
        assert ipakit.to_xsampa("kⱱt") == "kt"

    @pytest.mark.parametrize("sym", sorted(DROPPED))
    def test_strict_raises_naming_the_symbol(self, sym: str) -> None:
        with pytest.raises(ValueError, match="unknown symbols"):
            ipakit.to_xsampa(f"k{sym}t", strict=True)

    def test_strict_names_the_offending_symbol(self) -> None:
        with pytest.raises(ValueError) as exc:
            ipakit.to_xsampa("kⱱt", strict=True)
        assert "ⱱ" in str(exc.value)


# --- ICU cross-check (dev dependency) ----------------------------------------


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
