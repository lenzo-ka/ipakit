"""CMUMapper class for IPA to CMU ARPABET conversion.

ARPABET is a **phone set**: every row of ``cmu.xml`` spells one segment,
and a conversion is therefore one lookup per segment. So this module does
not tokenize. It asks :meth:`~ipakit.IPAFeatures.segments` where the
segments are and maps what comes back, which is what keeps ``to_cmu`` and
``segments`` from being two tokenizers with two answers -- they were, and
they disagreed on 31 of CMUdict's 135,166 entries, because a greedy walk
over the table's keys read the untied ``ɔɪ`` of ``N AO1 IH0 NG`` as the
one segment ``OY1``. The tie is what says whether two vowels are one
segment, and only the tokenizer reads it.
"""

from __future__ import annotations

import functools
import warnings
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from ._convert import ipa_features, report_unconvertible
from .constants import DEFAULT_CMU_MAP
from .models import PhoneMapping
from .segment import Segment


@functools.lru_cache(maxsize=1)
def _stress_markers() -> dict[str, int]:
    """IPA stress marker -> ARPABET level digit, from ipa.xml.

    The stress inventory is declared there and the value shorts *are* the
    levels (``<value name="primary" short="1"/>``), which is the same 1/2
    ARPABET uses. This module used to keep its own ``{"ˈ": 1, "ˌ": 2}``
    beside a comment saying the canonical one lived in the data: two
    copies of one fact, and the Python one keyed off the glyph.
    """
    from .features import IPAFeatures

    return IPAFeatures().stress_markers


@functools.lru_cache(maxsize=1)
def _stress_to_marker() -> dict[int, str]:
    """ARPABET level digit -> IPA stress marker (the inverse read)."""
    return {level: sym for sym, level in _stress_markers().items()}


@dataclass
class _Read:
    """One pass of an IPA string against the CMU table.

    ``ipa_to_cmu`` and ``validate_ipa_for_cmu`` are the same walk asked
    two questions, so they are one walk: the pair used to be two loops
    that agreed by habit, which is the arrangement this module's own
    defect came out of.
    """

    #: (unit, its row, the stress mark standing on it) per segment read;
    #: the row is None for a unit the table has no spelling for.
    units: list[tuple[Segment, PhoneMapping | None, str | None]] = field(
        default_factory=list
    )
    #: What ARPABET cannot carry: a unit with no row, spelled whole, and
    #: each mark a row was matched without.
    lost: list[str] = field(default_factory=list)


class CMUMapper:
    """Bidirectional mapper between IPA and CMU ARPABET."""

    def __init__(self, xml_path: Path = DEFAULT_CMU_MAP):
        self._cmu_to_ipa: dict[str, dict[int, str]] = {}
        self._extras_cmu_to_ipa: dict[str, dict[int, str]] = {}
        self._extras_ipa_to_cmu: dict[str, PhoneMapping] = {}
        self._ipa_to_cmu: dict[str, PhoneMapping] = {}
        self._tie_variants: dict[str, str] = {}
        self._load(xml_path)

    def _load(self, xml_path: Path) -> None:
        root = ET.parse(xml_path).getroot()

        def load_section(
            section: ET.Element,
            ipa_map: dict[str, PhoneMapping],
            cmu_map: dict[str, dict[int, str]],
        ) -> None:
            for elem in section.findall("map"):
                ipa, cmu = elem.get("ipa", ""), elem.get("cmu", "")
                stress_str = elem.get("stress", "")
                stress = {int(s) for s in stress_str.split()} if stress_str else set()
                mapping = PhoneMapping(cmu=cmu, ipa=ipa, stress=stress)

                if ipa not in ipa_map:
                    ipa_map[ipa] = mapping
                if cmu not in cmu_map:
                    cmu_map[cmu] = {}
                for s in stress or {-1}:
                    if s not in cmu_map[cmu]:
                        cmu_map[cmu][s] = ipa

        load_section(root, self._ipa_to_cmu, self._cmu_to_ipa)
        if (extras := root.find("extras")) is not None:
            load_section(extras, self._extras_ipa_to_cmu, self._extras_cmu_to_ipa)

        # A tied row is reachable under either tie glyph, because ARPABET
        # has no way to say which one was written: `CH` is the affricate
        # and there is no second symbol for a sequential `t͜ʃ`, so a table
        # keyed on one glyph and silent about the other refuses half of
        # what a front end emits -- and it refused opposite halves for
        # affricates and diphthongs, since cmu.xml spells the affricates
        # with the over-tie and the diphthongs with the under-tie. Which
        # spellings those are is `IPAFeatures.tie_glyph_variants`'s
        # answer, the same read `from_wild` uses.
        features = ipa_features()
        for ipa in (*self._ipa_to_cmu, *self._extras_ipa_to_cmu):
            for variant in features.tie_glyph_variants(ipa):
                self._tie_variants.setdefault(variant, ipa)

    def _ipa_lookup(self, include_extras: bool) -> dict[str, PhoneMapping]:
        """IPA->mapping lookup; extras are a fallback, the main map wins."""
        if include_extras:
            return {**self._extras_ipa_to_cmu, **self._ipa_to_cmu}
        return self._ipa_to_cmu

    def _row(
        self, spelling: str, lookup: dict[str, PhoneMapping]
    ) -> PhoneMapping | None:
        """The table row a unit's spelling names, under either tie glyph."""
        return lookup.get(spelling) or lookup.get(
            self._tie_variants.get(spelling, spelling)
        )

    def _read(
        self, ipa_string: str, include_extras: bool = False, strict: bool = False
    ) -> _Read:
        """Read an IPA string as segments and match each against the table.

        The tokenizer speaks for the input -- an unregistered character is
        its report to make, and ``strict`` is handed straight to it -- and
        this speaks for the table. Two layers, two voices, neither of them
        guessing on the other's behalf.

        A unit whose whole spelling names no row is tried again unmarked,
        because a diacritic is a distinction ARPABET does not draw at all:
        ``ɛː`` and ``ɛ̃`` are ``EH``, and the mark that could not come
        with them is named in the report rather than passed over. What is
        *not* retried is the unit boundary. A boundary is the tokenizer's
        answer and this makes no second one.
        """
        features = ipa_features()
        lookup = self._ipa_lookup(include_extras)
        markers = _stress_markers()
        read = _Read()
        for unit in features.read(ipa_string, strict=strict).segments:
            stress = next((m for m in unit.prosody if m in markers), None)
            carried = [m for m in unit.prosody if m not in markers]
            if (row := self._row(unit.spelling, lookup)) is None:
                unmarked = unit.unmarked()
                if (row := self._row(unmarked.spelling, lookup)) is not None:
                    carried += [m for c in unit.constituents for m in c.modifiers]
            if row is None:
                read.lost.append(unit.spelling)
            else:
                read.lost += carried
            read.units.append((unit, row, stress))
        return read

    def ipa_to_cmu(
        self,
        ipa_string: str,
        with_stress: bool = True,
        include_extras: bool = False,
        strict: bool = False,
    ) -> list[str]:
        """Convert IPA string to list of CMU symbols.

        One symbol per segment :meth:`~ipakit.IPAFeatures.segments` reads,
        so the two never disagree about how many phones a word has. An
        untied vowel pair is two segments and converts as two: ``ɔɪ`` is
        ``AO IH`` and only ``ɔ͜ɪ`` is ``OY``, which is what ``from_cmu``
        writes for it. Untied input from a front end goes through
        :meth:`~ipakit.IPAFeatures.from_wild` or ``add_ties`` first --
        espeak's ``--ipa=2`` and phonemizer's ``tie=True`` need neither.

        Args:
            ipa_string: IPA string to convert
            with_stress: Include stress numbers on vowels
            include_extras: Include extra/non-standard mappings
            strict: If True, raise ValueError for unconvertible phones;
                otherwise they are dropped with a warning naming them.

        Returns:
            List of CMU phone symbols

        Raises:
            ValueError: If strict=True and unconvertible phones are found
        """
        read = self._read(ipa_string, include_extras, strict)
        markers = _stress_markers()
        result = []
        pending_stress = None

        for _, row, mark in read.units:
            if mark is not None:
                pending_stress = markers[mark]
            if row is None:
                continue
            cmu = row.cmu
            # A mark binds the unit after it, and that unit is often a
            # consonant -- `ˈkæt` stresses `k` -- while ARPABET writes the
            # level on the vowel. So the level waits for a row that has
            # somewhere to put it.
            if with_stress and row.stress:
                stress = pending_stress if pending_stress is not None else 0
                if stress not in row.stress:
                    stress = (
                        0
                        if 0 in row.stress
                        else (1 if 1 in row.stress else min(row.stress))
                    )
                cmu = f"{cmu}{stress}"
                pending_stress = None
            result.append(cmu)

        report_unconvertible(read.lost, "to CMU ARPABET", strict=strict)

        return result

    def validate_ipa_for_cmu(
        self, ipa_string: str, include_extras: bool = False
    ) -> list[str]:
        """Everything in ``ipa_string`` that a CMU conversion cannot carry.

        Empty means :meth:`ipa_to_cmu` loses nothing. The two layers are
        asked in the order the conversion meets them -- what the inventory
        cannot read (:meth:`~ipakit.IPAFeatures.validate_ipa`'s errors,
        each of which is a symbol that reaches no unit), then what the
        table has no row for -- and the second is the conversion's own
        walk rather than a copy of it, so a verdict here and an answer
        there cannot come apart.

        Asked silently: a validator that warns about what it was asked to
        report leaves a caller nothing to do with the warning.
        """
        features = ipa_features()
        unreadable = [
            item["symbol"]
            for item in features.validate_ipa(ipa_string)
            if item["type"] == "error" and "symbol" in item
        ]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            read = self._read(ipa_string, include_extras)
        return unreadable + read.lost

    def cmu_to_ipa(
        self,
        cmu_symbols: list[str],
        include_extras: bool = True,
        strict: bool = False,
    ) -> str:
        """Convert list of CMU symbols to IPA string.

        With ``strict=True``, raise ``ValueError`` on unknown CMU symbols
        instead of skipping them.
        """
        result = []
        skipped = []
        for symbol in cmu_symbols:
            stress, base = -1, symbol
            if symbol and symbol[-1].isdigit():
                stress, base = int(symbol[-1]), symbol[:-1]

            stress_map = self._cmu_to_ipa.get(base)
            if stress_map is None and include_extras:
                stress_map = self._extras_cmu_to_ipa.get(base)
            if stress_map is None:
                skipped.append(symbol)
                continue

            ipa = (
                stress_map.get(stress)
                or stress_map.get(-1)
                or stress_map.get(0)
                or next(iter(stress_map.values()))
            )
            if marker := _stress_to_marker().get(stress):
                result.append(f"{marker}{ipa}")
            else:
                result.append(ipa)

        report_unconvertible(skipped, "CMU ARPABET -> IPA", strict=strict)
        return "".join(result)

    def get_cmu_symbols(self, include_extras: bool = False) -> set[str]:
        result = set(self._cmu_to_ipa.keys())
        if include_extras:
            result |= set(self._extras_cmu_to_ipa.keys())
        return result

    def get_ipa_phones(self, include_extras: bool = False) -> set[str]:
        result = set(self._ipa_to_cmu.keys())
        if include_extras:
            result |= set(self._extras_ipa_to_cmu.keys())
        return result
