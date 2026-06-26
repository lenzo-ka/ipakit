"""IPAFeatures class for IPA feature database."""

from __future__ import annotations

import functools
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path

from ._convert import longest_match
from .analysis import AnalysisMixin
from .constants import (
    DEFAULT_IPA_FEATS,
    DEFAULT_SHORT_NAME_LEN,
    TIE_BAR,
)
from .distance import DistanceMixin
from .hierarchy import HierarchyMixin
from .models import Feature, Phone, Phoneset
from .validation import ValidationMixin


class IPAFeatures(AnalysisMixin, DistanceMixin, HierarchyMixin, ValidationMixin):
    """IPA feature database loaded from ipa.xml."""

    def __init__(self, xml_path: Path = DEFAULT_IPA_FEATS):
        self.xml_path = Path(xml_path)
        self.classes: list[str] = []
        self.types: dict[str, list[str]] = {}
        self.features: dict[str, Feature] = {}
        self.phones: dict[str, Phone] = {}
        self.diacritics: dict[str, Phone] = {}
        self.separators: dict[str, Phone] = {}
        self.ligature_map: dict[str, str] = {}
        self.lookalikes: dict[str, str] = {}  # lookalike char -> IPA char
        self.wiki_base: str = ""  # Base URL for Wikipedia links
        self.references: dict[str, str] = {}  # name -> href (article name)
        self._value_aliases: dict[str, dict[str, str]] = {}
        self._short_to_feature: dict[str, tuple[str, str]] = (
            {}
        )  # short -> (feature, value)
        self._feature_to_short: dict[tuple[str, str], str] = (
            {}
        )  # (feature, value) -> short
        self._type_defaults: dict[str, str | None] = {}
        self._load()
        self._load_lookalikes()

    def _load(self) -> None:
        """Load features and phones from XML."""
        if not self.xml_path.exists():
            raise FileNotFoundError(f"IPA features file not found: {self.xml_path}")

        root = ET.parse(self.xml_path).getroot()
        self.wiki_base = root.get("wiki", "")

        # Load type definitions (values and defaults)
        if (types_elem := root.find("types")) is not None:
            for type_elem in types_elem.findall("type"):
                if type_name := type_elem.get("name"):
                    self.types[type_name] = [
                        name
                        for v in type_elem.findall("value")
                        if (name := v.get("name"))
                    ]
                    self._type_defaults[type_name] = type_elem.get("default")

        # Load class definitions (structural categories, not phonetic features)
        if (classes_elem := root.find("classes")) is not None:
            self.classes = [
                name for c in classes_elem.findall("class") if (name := c.get("name"))
            ]

        # Load feature definitions
        if (features_elem := root.find("features")) is not None:
            for feat_elem in features_elem.findall("feature"):
                if not (name := feat_elem.get("name")):
                    continue
                feat_type = feat_elem.get("type", "ordinal")
                feat_short = feat_elem.get("short", name[:DEFAULT_SHORT_NAME_LEN])
                if feat_type in self.types:
                    values = self.types[feat_type]
                    # Auto-generate shorts for typed features: +feat, -feat, 0feat
                    for val in values:
                        short = f"{val}{feat_short}"
                        self._short_to_feature[short] = (name, val)
                        self._feature_to_short[(name, val)] = short
                else:
                    values = []
                    self._value_aliases[name] = {}
                    for v in feat_elem.findall("value"):
                        if val_name := v.get("name"):
                            values.append(val_name)
                            if alias := v.get("alias"):
                                self._value_aliases[name][alias] = val_name
                            if vshort := v.get("short"):
                                self._short_to_feature[vshort] = (name, val_name)
                                self._feature_to_short[(name, val_name)] = vshort
                # Use feature default, or fall back to type default
                default = feat_elem.get("default") or self._type_defaults.get(feat_type)
                desc = feat_elem.get("desc")
                self.features[name] = Feature(
                    name=name, values=values, default=default, type=feat_type, desc=desc
                )

        # Load elements by class (plural section, singular child = section[:-1])
        for section_name in self.classes:
            if (elem := root.find(section_name)) is not None:
                child_name = section_name[:-1]  # phones -> phone
                for child_elem in elem.findall(child_name):
                    self._load_element(child_elem, child_name)

        # Load references
        if (refs_elem := root.find("references")) is not None:
            for ref in refs_elem.findall("ref"):
                if (name := ref.get("name")) and (href := ref.get("href")):
                    self.references[name] = href

    def _load_lookalikes(self) -> None:
        """Load lookalike character mappings from lookalikes.xml."""
        from .constants import DEFAULT_LOOKALIKES

        if not DEFAULT_LOOKALIKES.exists():
            return
        root = ET.parse(DEFAULT_LOOKALIKES).getroot()
        for elem in root.findall("map"):
            ipa = elem.get("ipa")
            lookalike = elem.get("lookalike")
            if ipa and lookalike:
                self.lookalikes[lookalike] = ipa

    def _load_element(self, elem: ET.Element, element_type: str) -> None:
        """Load a single element into the appropriate dict."""
        if not (symbol := elem.get("name")):
            return
        features = {
            k: self._value_aliases.get(k, {}).get(v, v)
            for k, v in elem.attrib.items()
            if k not in ("name", "alias")
        }
        features["class"] = element_type
        phone = Phone(symbol=symbol, features=features)

        # Route to appropriate dict based on element type
        if element_type == "phone":
            self.phones[symbol] = phone
        elif element_type in ("diacritic", "suprasegmental"):
            self.diacritics[symbol] = phone
        elif element_type == "separator":
            self.separators[symbol] = phone

        # Aliases become normalization entries (alias → canonical)
        # Supports multiple space-separated aliases
        if aliases := elem.get("alias"):
            for alias in aliases.split():
                self.ligature_map[alias] = symbol

    # -------------------------------------------------------------------------
    # Feature access
    # -------------------------------------------------------------------------

    def get_features(self, phone: str, with_defaults: bool = True) -> dict[str, str]:
        """Get features for a phone, optionally filling in defaults."""
        if phone not in self.phones:
            return {}
        feats = dict(self.phones[phone].features)
        if with_defaults:
            for name, feat in self.features.items():
                if name not in feats and feat.default is not None:
                    feats[name] = feat.default
        return feats

    def get_phone(self, symbol: str) -> Phone | None:
        return self.phones.get(symbol)

    def get_diacritic(self, symbol: str) -> Phone | None:
        return self.diacritics.get(symbol)

    def phones_by_feature(self, feature: str, value: str) -> list[str]:
        """Get all phones with a given feature value."""
        return [
            p
            for p, phone in self.phones.items()
            if phone.features.get(feature) == value
        ]

    def phones_by_manner(self, manner: str) -> list[str]:
        return self.phones_by_feature("manner", manner)

    def _resolve_query_term(
        self, term: str, prefix: str = ""
    ) -> tuple[str, str] | None:
        """Resolve a query term (short or long name) to (feature, value).

        For binary features, +featurename means feature='+', -featurename means feature='-'.
        """
        # Try short name first
        if term in self._short_to_feature:
            return self._short_to_feature[term]
        # Try as a feature value (long name)
        for feat_name, feat in self.features.items():
            if term in feat.values:
                return (feat_name, term)
        # Try as a binary feature name (e.g., 'voiced' -> ('voiced', '+' or '-'))
        if term in self.features and self.features[term].type == "binary":
            if prefix == "+":
                return (term, "+")
            elif prefix == "-":
                return (term, "-")
        return None

    def phones_matching(
        self, query: dict[str, str] | list[str] | set[str], with_defaults: bool = True
    ) -> list[str]:
        """Get all phones matching features.

        Accepts dict or list/set of short or long names.
        Names can be prefixed with + (has value) or - (does not have value).
        E.g., ['+aspirated', '-voiced'] or ['+asp', '-voi'].
        """
        positive: dict[str, str] = {}
        negative: dict[str, set[str]] = {}  # feature -> values to exclude

        if isinstance(query, (list, set)):
            for s in query:
                # Whole string is a short name (e.g. '-voi', '+voi', '0trt').
                if s in self._short_to_feature:
                    feat, val = self._short_to_feature[s]
                    positive[feat] = val
                    continue
                # Optional +/-/0 prefix selects a feature value directly.
                prefix = s[0] if s[:1] in ("+", "-", "0") else ""
                term = s[1:] if prefix else s
                if (
                    prefix
                    and term in self.features
                    and prefix in self.features[term].values
                ):
                    positive[term] = prefix
                    continue
                resolved = self._resolve_query_term(term, prefix=prefix)
                if not resolved:
                    continue
                feat, val = resolved
                if prefix == "-":
                    negative.setdefault(feat, set()).add(val)
                else:
                    positive[feat] = val
        else:
            positive = query

        results = []
        for symbol in self.phones:
            feats = self.get_features(symbol, with_defaults=with_defaults)
            if all(feats.get(k) == v for k, v in positive.items()):
                if all(feats.get(k) not in vals for k, vals in negative.items()):
                    results.append(symbol)
        return results

    def features_to_shorts(self, bundle: dict[str, str]) -> list[str]:
        """Convert a feature dict to list of short names."""
        return [
            self._feature_to_short[(k, v)]
            for k, v in bundle.items()
            if (k, v) in self._feature_to_short
        ]

    def shorts_to_features(self, shorts: list[str] | set[str]) -> dict[str, str]:
        """Convert list of short names to feature dict."""
        return dict(
            self._short_to_feature[s] for s in shorts if s in self._short_to_feature
        )

    # -------------------------------------------------------------------------
    # IPA normalization
    # -------------------------------------------------------------------------

    def normalize_lookalikes(self, text: str) -> str:
        """Replace lookalike characters with proper IPA equivalents.

        Converts visually similar keyboard characters to their
        correct IPA Unicode codepoints (e.g., 'g' → 'ɡ', ':' → 'ː').
        """
        for lookalike, ipa in self.lookalikes.items():
            text = text.replace(lookalike, ipa)
        return text

    def expand_ligatures(self, ipa: str) -> str:
        """Expand deprecated IPA ligatures (ʧ, ʤ) to modern tie-bar form."""
        # First normalize any lookalike characters
        ipa = self.normalize_lookalikes(ipa)
        for lig, expanded in self.ligature_map.items():
            ipa = ipa.replace(lig, expanded)
        return ipa

    def add_tie_bars(self, segment: str) -> str:
        """Add tie bars between base phones in a multi-phone segment."""
        if TIE_BAR in segment:
            return segment
        result = []
        prev_was_phone = False
        for char in segment:
            is_phone = char in self.phones
            if is_phone and prev_was_phone:
                result.append(TIE_BAR)
            result.append(char)
            prev_was_phone = is_phone and char not in self.diacritics
        return "".join(result)

    def normalize_ipa(self, segments: str) -> str:
        """Normalize whitespace-separated IPA segments into decodable IPA string."""
        segments = self.expand_ligatures(segments)
        return "".join(self.add_tie_bars(seg) for seg in segments.split())

    # -------------------------------------------------------------------------
    # Stress normalization
    # -------------------------------------------------------------------------

    def normalize_stress_to_nucleus(self, ipa: str) -> str:
        """Move syllable-initial stress markers to immediately before the nucleus.

        IPA-dict style puts stress at syllable boundary: ˈhɛ.ləʊ
        We want stress before the nucleus (vowel): hˈɛ.ləʊ

        Stress markers at syllable boundaries imply a syllable break, so we add
        an explicit break (.) where the stress marker was.

        Examples:
            ˈhɛ.ləʊ → hˈɛ.ləʊ
            ˈɛ.ləʊ → ˈɛ.ləʊ (already before nucleus)
            ˌɪn.təˈnæʃ → ˌɪn.tə.nˈæʃ
        """
        expanded = self.expand_ligatures(ipa)

        result: list[str] = []
        pending_stress = None
        onset_seen = False  # Track if we've seen onset consonants since stress marker
        i = 0

        while i < len(expanded):
            char = expanded[i]

            # Check for stress marker
            if char in self.stress_markers:
                # Stress marker implies syllable boundary - add explicit break
                # (unless at start or already have one)
                if result and result[-1] != self.syllable_break:
                    result.append(self.syllable_break)
                pending_stress = char
                onset_seen = False  # Reset onset tracking
                i += 1
                continue

            # Preserve syllable breaks
            if char == self.syllable_break:
                result.append(char)
                onset_seen = False  # Reset for new syllable
                i += 1
                continue

            # Try to match a phone
            best_phone, best_len = longest_match(
                expanded, i, self.phones, 6, tie_set=self.phones
            )

            if best_phone:
                # Collect any diacritics
                diacritics = []
                j = i + best_len
                while j < len(expanded) and expanded[j] in self.diacritics:
                    if expanded[j] in self.stress_markers:
                        break
                    diacritics.append(expanded[j])
                    j += 1

                # Check if this segment is syllabic (a nucleus)
                is_syllabic = False
                if best_phone in self.phones:
                    feats = self.phones[best_phone].features
                    is_syllabic = (
                        feats.get("manner") == "vowel" or feats.get("syllabic") == "+"
                    )

                if pending_stress and is_syllabic:
                    # Vowel with pending stress
                    if not onset_seen and result:
                        # No onset - syllable starts with nucleus (not at word start)
                        # Add explicit . so we don't lose syllable boundary on output
                        if result[-1] != self.syllable_break:
                            result.append(self.syllable_break)
                    # Put stress BEFORE the nucleus
                    result.append(pending_stress)
                    result.append(best_phone)
                    result.extend(diacritics)
                    pending_stress = None
                    onset_seen = False
                elif is_syllabic:
                    # Vowel without pending stress
                    result.append(best_phone)
                    result.extend(diacritics)
                    onset_seen = False
                else:
                    # Consonant - part of onset if pending stress
                    result.append(best_phone)
                    result.extend(diacritics)
                    if pending_stress:
                        onset_seen = True

                i = j
            elif (
                expanded[i] in self.diacritics
                and expanded[i] not in self.stress_markers
            ):
                result.append(expanded[i])
                i += 1
            else:
                # Unknown character - keep as-is
                result.append(expanded[i])
                i += 1

        # Handle any trailing pending stress (shouldn't happen normally)
        if pending_stress:
            result.append(pending_stress)

        return "".join(result)

    def strip_syllable_breaks(self, ipa: str) -> str:
        """Remove syllable break markers (.) from IPA string."""
        return ipa.replace(self.syllable_break, "")

    def normalize_stress_to_syllable(
        self, ipa: str, keep_syllables: bool = False
    ) -> str:
        """Move nucleus stress markers back to syllable-initial position.

        This is the inverse of normalize_stress_to_nucleus, for output.
        Converts: hˈɛ.ləʊ → ˈhɛləʊ (or ˈhɛ.ləʊ with keep_syllables=True)

        When stress precedes a nucleus, it is moved to just after the preceding
        syllable break (or to the start of the string for the first syllable).

        Args:
            ipa: IPA string in internal format (stress before nucleus)
            keep_syllables: If True, preserve syllable breaks in output.
                           If False (default), strip all syllable breaks.
        """
        result = list(ipa)
        i = 0

        while i < len(result):
            char = result[i]

            if char in self.stress_markers:
                # Check if preceded by syllable break (vowel-initial syllable)
                if i > 0 and result[i - 1] == self.syllable_break:
                    if not keep_syllables:
                        # Remove the redundant . before stress (stress serves as boundary)
                        result.pop(i - 1)
                    # Stress is already at syllable-initial position, skip
                    i += 1
                    continue

                # Check if at word start
                if i == 0:
                    # Already at syllable start, skip
                    i += 1
                    continue

                # Find the preceding syllable break or start
                j = i - 1
                while j >= 0 and result[j] != self.syllable_break:
                    j -= 1

                # Remove stress from current position
                stress = result.pop(i)

                if j >= 0:
                    # There was a preceding syllable break - replace it with stress
                    result[j] = stress
                else:
                    # No preceding break - insert at start
                    result.insert(0, stress)
                    i += 1  # Adjust for the insertion
            else:
                i += 1

        # Remove leading . if followed by stress marker (from word-initial stressed vowel)
        if (
            len(result) >= 2
            and result[0] == self.syllable_break
            and result[1] in self.stress_markers
        ):
            result.pop(0)

        output = "".join(result)

        # Strip syllable breaks unless explicitly kept
        if not keep_syllables:
            output = output.replace(self.syllable_break, "")

        return output

    # -------------------------------------------------------------------------
    # Tokenization & parsing
    # -------------------------------------------------------------------------

    def tokenize_ipa(self, ipa: str, phoneset: Phoneset | None = None) -> list[str]:
        """Parse IPA string into list of segment tokens."""
        ipa = self.expand_ligatures(ipa)
        return [
            base + "".join(diacs) for base, diacs in self.parse(ipa, phoneset=phoneset)
        ]

    def segment_ipa(self, ipa: str, phoneset: Phoneset | None = None) -> str:
        """Parse IPA string and return whitespace-separated segments."""
        return " ".join(self.tokenize_ipa(ipa, phoneset=phoneset))

    def parse(
        self, segment: str, phoneset: Phoneset | None = None
    ) -> list[tuple[str, list[str]]]:
        """Parse an IPA segment string into (base, diacritics) tuples."""
        if not segment:
            return []

        phone_lookup = set(self.phones.keys())
        if phoneset:
            phone_lookup |= set(phoneset.phones)

        if segment in phone_lookup:
            return [(segment, [])]

        result = []
        i = 0
        while i < len(segment):
            best_phone, best_len = longest_match(
                segment, i, phone_lookup, 6, tie_set=phone_lookup
            )

            if best_phone:
                diacritics = []
                j = i + best_len
                while (
                    j < len(segment)
                    and segment[j] in self.diacritics
                    and segment[j] != TIE_BAR
                ):
                    diacritics.append(segment[j])
                    j += 1
                result.append((best_phone, diacritics))
                i = j
            elif segment[i] in self.diacritics:
                result.append((segment[i], []))
                i += 1
            else:
                i += 1

        return result

    def compose(
        self, segment: str, with_defaults: bool = True, phoneset: Phoneset | None = None
    ) -> list[dict[str, str]]:
        """Get features for a segment, composing base phones with diacritics."""
        return [
            feats
            for _, feats in self.compose_segments(
                segment, with_defaults=with_defaults, phoneset=phoneset
            )
        ]

    def compose_segments(
        self, segment: str, with_defaults: bool = True, phoneset: Phoneset | None = None
    ) -> list[tuple[str, dict[str, str]]]:
        """Compose ``segment`` into aligned ``(token, features)`` pairs.

        Same segmentation as :meth:`tokenize_ipa`, but suprasegmentals and
        separators that carry no phonetic features (stress, syllable breaks) are
        dropped, so every token lines up with its composed feature bundle.
        """
        result: list[tuple[str, dict[str, str]]] = []
        for base, diacritics in self.parse(segment, phoneset=phoneset):
            if not (feats := self.get_features(base, with_defaults=with_defaults)):
                continue
            for diac in diacritics:
                if diac in self.diacritics:
                    for k, v in self.diacritics[diac].features.items():
                        if k not in ("class", "manner"):
                            feats[k] = v
            result.append((base + "".join(diacritics), feats))
        return result

    def compose_single(
        self, segment: str, with_defaults: bool = True
    ) -> dict[str, str]:
        """Get features for a single-phone segment."""
        composed = self.compose(segment, with_defaults)
        return composed[0] if len(composed) == 1 else {}

    # -------------------------------------------------------------------------
    # X-SAMPA conversion
    # -------------------------------------------------------------------------

    def ipa_to_xsampa(self, ipa: str, strict: bool = False) -> str:
        """Convert an IPA string to X-SAMPA notation.

        Delegates to :mod:`ipakit.xsampa`, the single source of truth for the
        IPA <-> X-SAMPA table (``data/phonemaps/xsampa.xml``). With
        ``strict=True``, raise ``ValueError`` on unconvertible symbols.
        """
        from .xsampa import ipa_to_xsampa

        return ipa_to_xsampa(ipa, strict=strict)

    def xsampa_to_ipa(self, xsampa: str, strict: bool = False) -> str:
        """Convert an X-SAMPA string to IPA. See :meth:`ipa_to_xsampa`."""
        from .xsampa import xsampa_to_ipa

        return xsampa_to_ipa(xsampa, strict=strict)

    # -------------------------------------------------------------------------
    # Derived properties
    # -------------------------------------------------------------------------

    @property
    def feature_order(self) -> list[str]:
        """Feature names in XML declaration order."""
        return list(self.features.keys())

    @functools.cached_property
    def consonant_manners(self) -> frozenset[str]:
        """Derive consonant manners from the manner feature values."""
        if "manner" not in self.features:
            return frozenset()
        return frozenset(self.features["manner"].values_set - {"silence", "vowel"})

    @functools.cached_property
    def stress_markers(self) -> dict[str, int]:
        """Stress marker chars -> level, from the `stress` feature (short = level)."""
        markers: dict[str, int] = {}
        for sym, supra in self.diacritics.items():
            value = supra.features.get("stress")
            if value is None:
                continue
            short = self._feature_to_short.get(("stress", value))
            if short is not None and short.isdigit():
                markers[sym] = int(short)
        return markers

    @functools.cached_property
    def stress_to_marker(self) -> dict[int, str]:
        """Stress level -> marker char (inverse of stress_markers)."""
        return {level: sym for sym, level in self.stress_markers.items()}

    @functools.cached_property
    def syllable_break(self) -> str:
        """Syllable-boundary char (the separator declared at level 'syllable')."""
        for sym, sep in self.separators.items():
            if sep.features.get("level") == "syllable":
                return sym
        return "."

    # -------------------------------------------------------------------------
    # Dunder methods
    # -------------------------------------------------------------------------

    def __contains__(self, phone: str) -> bool:
        return phone in self.phones

    def __iter__(self) -> Iterator[str]:
        return iter(self.phones.keys())

    def __len__(self) -> int:
        return len(self.phones)
