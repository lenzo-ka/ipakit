"""CMUMapper class for IPA to CMU ARPABET conversion."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from ._convert import longest_match, require_convertible
from .constants import DEFAULT_CMU_MAP, TIE_BAR
from .models import PhoneMapping

# CMU/ARPABET stress: IPA marker -> level digit (0/1/2). ARPABET-specific; the
# canonical stress inventory lives in ipa.xml's `stress` feature.
_STRESS_MARKERS = {"ˈ": 1, "ˌ": 2}
_STRESS_TO_MARKER = {level: marker for marker, level in _STRESS_MARKERS.items()}


class CMUMapper:
    """Bidirectional mapper between IPA and CMU ARPABET."""

    def __init__(self, xml_path: Path = DEFAULT_CMU_MAP):
        self._cmu_to_ipa: dict[str, dict[int, str]] = {}
        self._extras_cmu_to_ipa: dict[str, dict[int, str]] = {}
        self._extras_ipa_to_cmu: dict[str, PhoneMapping] = {}
        self._ipa_to_cmu: dict[str, PhoneMapping] = {}
        self._tie_normalizations: list[tuple[str, str]] = []
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

        # Derive tie normalizations from IPA phones with tie bars
        for ipa in self._ipa_to_cmu:
            if TIE_BAR in ipa:
                self._tie_normalizations.append((ipa.replace(TIE_BAR, ""), ipa))

    def _normalize_ipa(self, ipa: str) -> str:
        for old, new in self._tie_normalizations:
            ipa = ipa.replace(old, new)
        return ipa

    def _ipa_lookup(self, include_extras: bool) -> dict[str, PhoneMapping]:
        """IPA->mapping lookup; extras are a fallback, the main map wins."""
        if include_extras:
            return {**self._extras_ipa_to_cmu, **self._ipa_to_cmu}
        return self._ipa_to_cmu

    def ipa_to_cmu(
        self,
        ipa_string: str,
        with_stress: bool = True,
        include_extras: bool = False,
        strict: bool = False,
    ) -> list[str]:
        """Convert IPA string to list of CMU symbols.

        Args:
            ipa_string: IPA string to convert
            with_stress: Include stress numbers on vowels
            include_extras: Include extra/non-standard mappings
            strict: If True, raise ValueError for unconvertible phones

        Returns:
            List of CMU phone symbols

        Raises:
            ValueError: If strict=True and unconvertible phones are found
        """
        result = []
        skipped = []
        ipa_string = self._normalize_ipa(ipa_string)
        i = 0
        pending_stress = None

        lookup = self._ipa_lookup(include_extras)

        while i < len(ipa_string):
            char = ipa_string[i]
            if char in _STRESS_MARKERS:
                pending_stress = _STRESS_MARKERS[char]
                i += 1
                continue

            key, match_len = longest_match(ipa_string, i, lookup, 5)
            match = lookup[key] if key else None

            if match:
                cmu = match.cmu
                if with_stress and match.stress:
                    stress = pending_stress if pending_stress is not None else 0
                    if stress not in match.stress:
                        stress = (
                            0
                            if 0 in match.stress
                            else (1 if 1 in match.stress else min(match.stress))
                        )
                    cmu = f"{cmu}{stress}"
                    pending_stress = None
                result.append(cmu)
                i += match_len
            else:
                # Track skipped character
                skipped.append(ipa_string[i])
                i += 1

        if strict:
            require_convertible(skipped, "to CMU ARPABET")

        return result

    def validate_ipa_for_cmu(
        self, ipa_string: str, include_extras: bool = False
    ) -> list[str]:
        """Check if IPA string can be fully converted to CMU.

        Returns list of unconvertible characters (empty if all convertible).
        """
        skipped = []
        ipa_string = self._normalize_ipa(ipa_string)
        i = 0

        lookup = self._ipa_lookup(include_extras)

        while i < len(ipa_string):
            char = ipa_string[i]
            if char in _STRESS_MARKERS:
                i += 1
                continue

            key, match_len = longest_match(ipa_string, i, lookup, 5)
            if key:
                i += match_len
            else:
                skipped.append(ipa_string[i])
                i += 1

        return skipped

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
            if marker := _STRESS_TO_MARKER.get(stress):
                result.append(f"{marker}{ipa}")
            else:
                result.append(ipa)

        if strict:
            require_convertible(skipped, "CMU ARPABET -> IPA")
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
