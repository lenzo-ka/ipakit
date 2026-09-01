"""Which symbols in ``ipa.xml`` are not on the IPA chart.

The file is otherwise a faithful record of the chart, so an unmarked
convention makes it misrepresent its own provenance. `<notations>` lists
the exceptions, unlisted meaning `chart`, and the distinction is then
queryable instead of being a comment nobody can test.

It is a block rather than an attribute on each symbol's own element
because an attribute there lands in that symbol's *feature bundle*, and
a key in a bundle is a term in the metric: measured, marking `␣` that
way moved 58 of the 8060 sweep units' features and 37 of their distances
(`d(␣ʰ, ␣)` 0.5 -> 0.333), with `confusion.json` byte-identical only
because `␣` is already 1.0 from every registered phone.

The set is asserted rather than counted, and the negative controls below
rebuild the inventory from a mutated copy of the file, because "three
symbols are marked" keeps passing when the wrong three are.

The block is read through the library -- ``IPAFeatures.notations``,
``.notation_of``, ``ipakit.extensions_in``, ``.is_pure_ipa`` -- and not
through ``scripts/invariants.py``, which used to *define* all four. A
script is not an API, and while it was the only definition the invariant
was checking itself.

The ``samprosa`` notation two tests below build is **deliberately
fictional**: a stand-in for any second notation, so the loader's
behavior when one exists is pinned whichever notation ever arrives.
ipakit does not ship one and none is planned -- SAMPROSA was assessed
for that slot and declined -- so the name here is a fixture, not a commitment.
"""

from __future__ import annotations

import sys
from pathlib import Path

import ipakit
import pytest
from ipakit import IPAFeatures
from ipakit.constants import DEFAULT_IPA_FEATS
from ipakit.form import zeros

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from invariants import CHART, NON_CHART, check_notation, declared_symbols

FEATURES = IPAFeatures()

#: Chart-proper marks that look like candidates for the extension mark and
#: are not. Named individually as well as covered by the set equality,
#: because over-marking is the failure mode here and a named case says
#: which ones were checked.
CHART_PROPER = [
    ".",  # IPA syllable break
    "|",  # IPA minor (foot) group
    "‖",  # IPA major (intonation) group
    "‿",  # IPA linking mark, absence of a break
    "˥",  # tone letters
    "˩",
    "́",  # diacritic tones
    "̀",
    "↗",  # global rise / fall
    "↘",
    "ꜛ",  # upstep / downstep
    "ꜜ",
    "ˈ",  # stress
    "ˌ",
    "ː",  # length
    "ˑ",
    "̆",
    "͡",  # the two ties
    "͜",
]


#: A unique anchor in the shipped file, for the mutations below.
_SILENCE = '<symbol name="␣" desc="the chart has no symbol for silence"/>'


def _inventory(tmp_path: Path, old: str, new: str) -> IPAFeatures:
    """The shipped inventory with one substitution, loaded from a copy."""
    text = DEFAULT_IPA_FEATS.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"{old!r} is not a unique anchor"
    path = tmp_path / "ipa.xml"
    path.write_text(text.replace(old, new), encoding="utf-8")
    return IPAFeatures(path)


class TestTheMarkedSet:
    """Exactly the non-chart symbols carry the mark."""

    def test_the_marked_set_is_the_non_chart_set(self) -> None:
        assert FEATURES.default_notation == CHART
        marked = {
            s for s, n in FEATURES.notations.items() if n != FEATURES.default_notation
        }
        assert marked == set(NON_CHART) == {"␣", "#", "∅"}

    def test_every_listed_symbol_is_one_the_inventory_declares(self) -> None:
        assert set(FEATURES.notations) <= set(declared_symbols(FEATURES))

    def test_the_scan_covers_the_whole_inventory(self) -> None:
        # A set equality over an empty scan is vacuously true, so the
        # corpus size is asserted the way the sweeps assert theirs.
        declared = declared_symbols(FEATURES)
        assert len(declared) > 200
        for table in (
            FEATURES.phones,
            FEATURES.diacritics,
            FEATURES.separators,
            FEATURES.zeros,
        ):
            assert set(table) <= set(declared)
        assert set(zeros(FEATURES)) <= set(declared)

    @pytest.mark.parametrize("symbol", CHART_PROPER)
    def test_chart_proper_marks_are_not_marked(self, symbol: str) -> None:
        assert FEATURES.notation_of(symbol) == CHART

    def test_every_phone_but_silence_is_chart_proper(self) -> None:
        off = {p for p in FEATURES.phones if FEATURES.notation_of(p) != CHART}
        assert off == {"␣"}
        assert len(FEATURES.phones) == 139

    def test_provenance_never_reaches_a_feature_bundle(self) -> None:
        # The whole reason it is a block. Nothing in <notations> may show
        # up in what a symbol declares, or it becomes a term in the metric.
        for bundle in declared_symbols(FEATURES).values():
            assert "notation" not in bundle
        assert "notation" not in FEATURES.features
        assert FEATURES.notation_of("a") == CHART
        assert FEATURES.notation_of("␣") != CHART

    def test_an_unknown_symbol_is_not_an_extension(self) -> None:
        # Not registered is not the same as off the chart; validate_ipa is
        # what reports unknown characters.
        assert FEATURES.notation_of("Q") == CHART
        assert FEATURES.extensions_in("Q") == []


class TestTheGuardGuards:
    """Negative controls: the invariant fails when the data is wrong."""

    def test_an_unlisted_extension_fails(self, tmp_path: Path) -> None:
        ipa = _inventory(tmp_path, _SILENCE, "")
        assert ipa.notation_of("␣") == CHART
        assert not check_notation(ipa)

    def test_an_over_listed_chart_symbol_fails(self, tmp_path: Path) -> None:
        ipa = _inventory(tmp_path, _SILENCE, _SILENCE + '<symbol name="."/>')
        assert ipa.notation_of(".") != CHART
        assert not check_notation(ipa)

    def test_listing_a_symbol_the_inventory_does_not_declare_fails(
        self, tmp_path: Path
    ) -> None:
        ipa = _inventory(tmp_path, _SILENCE, _SILENCE + '<symbol name="Ø"/>')
        assert not check_notation(ipa)

    def test_the_shipped_inventory_passes(self) -> None:
        assert check_notation(FEATURES)

    def test_a_symbol_listed_under_two_notations_fails_to_load(
        self, tmp_path: Path
    ) -> None:
        # Otherwise the last block listing it wins, so which convention a
        # symbol comes from depends on the order the blocks happen to be
        # in and nothing says so.
        with pytest.raises(ValueError, match="two"):
            _inventory(
                tmp_path,
                "</notations>",
                '<notation name="samprosa"><symbol name="␣"/></notation></notations>',
            )

    def test_a_default_no_notation_declares_fails_to_load(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="not.*declared in <notations>"):
            _inventory(
                tmp_path, '<notations default="chart">', '<notations default="ipa">'
            )


class TestPureIPA:
    """The practical payoff: which transcriptions use only the chart."""

    def test_a_chart_only_transcription_is_pure(self) -> None:
        assert FEATURES.is_pure_ipa("ˈkæt.dɒɡ")
        assert FEATURES.is_pure_ipa("lez‿ami")
        assert FEATURES.is_pure_ipa("t͡ʃiːz|a‖b")

    @pytest.mark.parametrize(
        ("text", "found"),
        [
            ("#kæt#", ["#", "#"]),
            ("a␣b", ["␣"]),
            ("le∅ʃ", ["∅"]),
            ("#a∅b␣", list("#∅␣")),
        ],
    )
    def test_an_extension_is_named(self, text: str, found: list[str]) -> None:
        assert not FEATURES.is_pure_ipa(text)
        assert FEATURES.extensions_in(text) == found

    def test_the_question_survives_a_further_convention(self, tmp_path: Path) -> None:
        # The point of one block rather than one flag per system: a symbol
        # from a further notation answers the same question, with no
        # second marker invented for it and no phone bundle touched.
        ipa = _inventory(
            tmp_path,
            "</notations>",
            '<notation name="samprosa" desc="SAM prosodic transcription">'
            '<symbol name="."/></notation></notations>',
        )
        assert ipa.notation_of(".") == "samprosa"
        assert not ipa.is_pure_ipa("a.b")
        for bundle in declared_symbols(ipa).values():
            assert "notation" not in bundle


class TestTheModuleLevelPair:
    """`extensions_in` / `is_pure_ipa`, in the shape of the validate pair.

    The informative one is primary and the boolean is a convenience over
    it, which is `validate_ipa` / `is_valid_ipa`'s shape exactly. Both
    are on the package, not only on the inventory, because "which
    non-chart symbols are in this?" is a caller's question.
    """

    def test_the_pair_is_exported(self) -> None:
        for name in ("extensions_in", "is_pure_ipa"):
            assert name in ipakit.__all__
            assert hasattr(ipakit, name)

    def test_the_boolean_is_the_negation_of_the_informative_one(self) -> None:
        # Swept rather than spot-checked: the two must not be able to
        # disagree about any string, which is the whole point of one
        # being defined over the other.
        texts = ["ˈkæt.dɒɡ", "#kæt#", "a␣b", "le∅ʃ", "", "Q", "t͡ʃiːz|a‖b"]
        texts += [f"a{p}a" for p in FEATURES.phones]
        checked = 0
        for text in texts:
            checked += 1
            assert ipakit.is_pure_ipa(text) is (ipakit.extensions_in(text) == [])
            assert ipakit.extensions_in(text) == FEATURES.extensions_in(text)
        assert checked > 100, "sweep did not run"

    def test_only_silence_makes_a_framed_phone_impure(self) -> None:
        impure = {p for p in FEATURES.phones if not ipakit.is_pure_ipa(f"a{p}a")}
        assert impure == {"␣"}
        assert len(FEATURES.phones) == 139
