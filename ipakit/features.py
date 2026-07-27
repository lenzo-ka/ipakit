"""IPAFeatures class for IPA feature database."""

from __future__ import annotations

import functools
import re
import unicodedata
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path

from ._convert import longest_match, require_convertible
from .analysis import AnalysisMixin
from .constants import (
    DEFAULT_IPA_FEATS,
    DEFAULT_SHORT_NAME_LEN,
    MAX_MATCH_LEN,
    SEQ_TIE,
    TIE_BAR,
)
from .distance import DistanceMixin
from .hierarchy import HierarchyMixin
from .models import Feature, Phone, Phoneset
from .segment import Constituent, Segment, Sense, modifier_mode
from .validation import ValidationMixin


class IPAFeatures(AnalysisMixin, DistanceMixin, HierarchyMixin, ValidationMixin):
    """IPA feature database loaded from ipa.xml.

    Tie conventions (see docs/ties.md): the over-tie (U+0361) fuses
    constituents into one timing slot (affricates, double articulations);
    the under-tie (U+035C) binds a sequence into one unit (diphthongs,
    morae) and the over-tie binds tighter in mixed chains. The glyph is
    authoritative; canonical spellings are sense-correct, unregistered
    tie-joined sequences of known phones compose on the fly, and text
    from other conventions imports via :meth:`from_wild`.
    """

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
        # Registered symbols whose NFC form differs from NFD (e.g. ä, ç, ť),
        # mapped from their NFD decomposition back to the registered form.
        # Built after loading so canonicalize_unicode can recompose them.
        self._nfd_to_registered: dict[str, str] = {
            decomposed: sym
            for sym in (
                list(self.phones)
                + list(self.diacritics)
                + list(self.separators)
                + list(self.ligature_map)
                + list(self.lookalikes)
            )
            if (decomposed := unicodedata.normalize("NFD", sym)) != sym
        }
        # Tied entries carry only spelling/aliases/href in the data; their
        # features are derived here from the constituents under the entry's
        # sense, so registered and composed can never drift (docs/ties.md).
        self.derived_phones: frozenset[str] = self._derive_compound_features()

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
                    name=name,
                    values=values,
                    default=default,
                    type=feat_type,
                    desc=desc,
                    value_aliases=dict(self._value_aliases.get(name, {})),
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

    def _derive_compound_features(self) -> frozenset[str]:
        """Fill features for tied entries that ship without explicit ones.

        Canonical names are sense-correct (over-tie simultaneous,
        under-tie sequential), so each entry is composed exactly as the
        fallback path would compose the same unregistered chain. The
        convergence guard asserts every tied entry derives.
        """
        derived = set()
        for name in list(self.phones):
            if TIE_BAR not in name and SEQ_TIE not in name:
                continue
            phone = self.phones[name]
            explicit = set(phone.features) - {"class", "href"}
            if explicit:
                continue
            parts = name.replace(SEQ_TIE, TIE_BAR).split(TIE_BAR)
            all_vocalic = all(
                self._part_features(part).get("manner") == "vowel" for part in parts
            )
            spelling = name.replace(TIE_BAR, SEQ_TIE) if all_vocalic else name
            feats = self._compose_tie_bar_features(spelling)
            if feats is None:
                raise ValueError(
                    f"cannot derive features for registered entry {name!r}; "
                    "give it explicit features or fix its constituents"
                )
            merged = dict(feats)
            merged["class"] = phone.features.get("class", "phone")
            if "href" in phone.features:
                merged["href"] = phone.features["href"]
            self.phones[name] = Phone(symbol=name, features=merged)
            derived.add(name)
        return frozenset(derived)

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
        """Get features for a phone, optionally filling in defaults.

        Registered phones win (canonical spellings and single-character
        ligature aliases like ``ʦ``). The tie glyph is authoritative:
        unregistered over-tie (simultaneous) sequences merge; under-tie
        (sequential) sequences project their first element. Text written
        in other tie conventions imports via :meth:`from_wild`.
        """
        phone = self._resolve_token(phone)
        if phone in self.phones:
            feats = dict(self.phones[phone].features)
        elif (composed := self._compose_tie_bar_features(phone)) is not None:
            feats = composed
        else:
            return {}
        if with_defaults:
            for name, feat in self.features.items():
                if name not in feats and feat.default is not None:
                    feats[name] = feat.default
        return feats

    def _resolve_token(self, token: str) -> str:
        """Canonicalize a token: Unicode form, then alias -> registered name."""
        token = self.canonicalize_unicode(token)
        return self.ligature_map.get(token, token)

    def _resolves_part(self, part: str) -> bool:
        """A tie-chain part resolves if it is a registered phone, a base
        phone with known modifiers (``ʊ̯``), or itself a composable run."""
        if not part:
            return False
        part = self._resolve_token(part)
        if part in self.phones:
            return True
        try:
            self._parse_constituent(part)
            return True
        except ValueError:
            return self._is_composable(part)

    def _part_features(self, part: str) -> dict[str, str]:
        """Explicit features of a resolvable part: registered features, or
        the constituent bundle (base + modifier contributions, no
        defaults) for a modifier-bearing part."""
        part = self._resolve_token(part)
        if part in self.phones:
            return dict(self.phones[part].features)
        return self._parse_constituent(part).bundle(self, with_defaults=False)

    def _is_composable(self, phone: str) -> bool:
        """True if ``phone`` is a tie-barred sequence of resolvable parts.

        Cheap membership predicate: does the splitting and lookups of
        :meth:`_compose_tie_bar_features` without building a feature dict.
        Sequential (under-tie) chains are composable when every
        SEQ-separated part resolves (registered, base+modifiers, or a
        composable over-tie run); pure over-tie runs when every part
        resolves as a phone or base+modifiers.
        """
        if SEQ_TIE in phone:
            parts = phone.split(SEQ_TIE)
            return len(parts) >= 2 and all(
                p and (self._resolves_part(p) or self._is_composable(p)) for p in parts
            )
        if TIE_BAR not in phone:
            return False
        parts = phone.split(TIE_BAR)
        return len(parts) >= 2 and all(self._resolves_part(p) for p in parts)

    def _compose_tie_bar_features(self, phone: str) -> dict[str, str] | None:
        """Features for an ad hoc tie-barred sequence of resolvable parts.

        Returns ``None`` if ``phone`` has no tie bar or any part isn't
        resolvable. Sequential (under-tie) chains project their **first
        element** -- the same encoding the registered diphthongs use; the
        chain's other constituents remain recoverable from the token, not
        from this flat projection. Simultaneous (over-tie) runs merge left
        to right; a differing manner across parts collapses to "affricate"
        (e.g. plosive + fricative). Same-manner parts with different places
        are a double articulation (e.g. "ɡ͡b"); when the place pair has a
        dedicated combined value (labial-velar, labial-palatal), that value
        is used instead of just keeping the last part's place. ``href`` is
        dropped since it names a specific Wikipedia article that doesn't
        apply to an ad hoc compound.
        """
        if not self._is_composable(phone):
            return None
        feats: dict[str, str]
        if SEQ_TIE in phone:
            first = self._resolve_token(phone.split(SEQ_TIE)[0])
            if first in self.phones or TIE_BAR not in first:
                feats = self._part_features(first)
            else:
                composed = self._compose_tie_bar_features(first)
                if composed is None:  # pragma: no cover - guarded by _is_composable
                    return None
                feats = composed
            feats.pop("href", None)
            return feats
        parts = phone.split(TIE_BAR)
        feats = {}
        manners = set()
        places = []
        for part in parts:
            part_feats = self._part_features(part)
            manners.add(part_feats.get("manner"))
            if "place" in part_feats:
                places.append(part_feats["place"])
            feats.update(part_feats)
        feats.pop("href", None)
        if len(manners) > 1:
            feats["manner"] = "affricate"
        elif len(set(places)) > 1:
            # A same-manner multi-place fusion is a double articulation; its
            # place is the canonical combining spelling (components ordered
            # by scale position): any pair, not just the pre-named ones.
            place_feature = self.features.get("place")
            if place_feature is not None:
                feats["place"] = place_feature.combine(tuple(places))
        return feats

    def get_phone(self, symbol: str) -> Phone | None:
        return self.phones.get(self._resolve_token(symbol))

    def get_diacritic(self, symbol: str) -> Phone | None:
        return self.diacritics.get(self.canonicalize_unicode(symbol))

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

    def canonicalize_unicode(self, text: str) -> str:
        """Canonicalize Unicode so matching is independent of input form.

        NFD-decomposes the text (so precomposed characters like "ã" expose
        their base + combining mark to the parser), then recomposes the few
        registered symbols that are stored precomposed (e.g. "ç", "ä", "ť")
        so they still match their inventory keys. Idempotent.
        """
        text = unicodedata.normalize("NFD", text)
        for decomposed, sym in self._nfd_to_registered.items():
            text = text.replace(decomposed, sym)
        # Both ties stacked on one juncture assert contradictory timing; the
        # simultaneous reading takes precedence, so the pair collapses to the
        # over-tie. (NFD orders U+035C before U+0361 - ccc 233 < 234 - so one
        # replace covers both written orders.)
        text = text.replace(SEQ_TIE + TIE_BAR, TIE_BAR)
        return text

    def normalize_lookalikes(self, text: str) -> str:
        """Replace lookalike characters with proper IPA equivalents.

        Converts visually similar keyboard characters to their
        correct IPA Unicode codepoints (e.g., 'g' → 'ɡ', ':' → 'ː').
        """
        for lookalike, ipa in self.lookalikes.items():
            text = text.replace(lookalike, ipa)
        return text

    def expand_ligatures(self, ipa: str) -> str:
        """Expand deprecated IPA ligatures (ʧ, ʤ) to modern tie-bar form.

        Only single-character ligature aliases are replaced; tie glyphs are
        never rewritten here (the glyph is the sense; wild-convention text
        imports via :meth:`from_wild`).
        """
        # Canonicalize Unicode form, then normalize lookalike characters
        ipa = self.canonicalize_unicode(ipa)
        ipa = self.normalize_lookalikes(ipa)
        for lig, expanded in self.ligature_map.items():
            if len(lig) > 1 and (TIE_BAR in lig or SEQ_TIE in lig):
                continue
            ipa = ipa.replace(lig, expanded)
        return ipa

    def add_tie_bars(self, segment: str) -> str:
        """Add tie bars between base phones in a multi-phone segment.

        Whitespace grouping asserts unit-hood; the inserted glyph follows a
        documented heuristic: two adjacent vocalic bases bind sequentially
        (under-tie: a trajectory), anything else binds simultaneously
        (over-tie). Write the tie explicitly to override.
        """
        if TIE_BAR in segment or SEQ_TIE in segment:
            return segment

        def _vocalic(ch: str) -> bool:
            phone = self.phones.get(ch)
            return phone is not None and phone.features.get("manner") == "vowel"

        result = []
        prev_phone_char = ""
        for char in segment:
            is_phone = char in self.phones
            if is_phone and prev_phone_char:
                tie = (
                    SEQ_TIE if _vocalic(prev_phone_char) and _vocalic(char) else TIE_BAR
                )
                result.append(tie)
            result.append(char)
            prev_phone_char = char if is_phone and char not in self.diacritics else ""
        return "".join(result)

    def normalize_ipa(self, segments: str) -> str:
        """Normalize whitespace-separated IPA segments into decodable IPA string.

        Each whitespace-separated group is treated as one asserted unit;
        :meth:`add_tie_bars` inserts the tie by sense (adjacent vowels bind
        sequentially, anything else fuses).
        """
        segments = self.expand_ligatures(segments)
        return unicodedata.normalize(
            "NFC", "".join(self.add_tie_bars(seg) for seg in segments.split())
        )

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
                expanded, i, self.phones, MAX_MATCH_LEN, tie_set=self.phones
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

        return unicodedata.normalize("NFC", output)

    # -------------------------------------------------------------------------
    # Tokenization & parsing
    # -------------------------------------------------------------------------

    def tokenize_ipa(self, ipa: str, phoneset: Phoneset | None = None) -> list[str]:
        """Parse IPA string into list of segment tokens.

        Tokens are emitted in NFC so both precomposed and decomposed input
        yield identical output. Tie-joined runs of known phones are one
        token whichever tie binds them; the tie glyph is preserved (it is
        the sense).
        """
        ipa = self.expand_ligatures(ipa)
        return [
            unicodedata.normalize("NFC", base + "".join(diacs))
            for base, diacs in self.parse(ipa, phoneset=phoneset)
        ]

    def segment_ipa(self, ipa: str, phoneset: Phoneset | None = None) -> str:
        """Parse IPA string and return whitespace-separated segments."""
        return " ".join(self.tokenize_ipa(ipa, phoneset=phoneset))

    def parse(
        self,
        segment: str,
        phoneset: Phoneset | None = None,
        strict: bool = False,
    ) -> list[tuple[str, list[str]]]:
        """Parse an IPA segment string into (base, diacritics) tuples.

        Registered symbols match longest-first; tie glyphs are preserved
        as written (the glyph is the sense). Unmatched characters (neither
        a phone nor a diacritic) are skipped. With ``strict=True`` they
        instead raise ``ValueError`` listing the symbols that could not be
        parsed.
        """
        if not segment:
            return []

        segment = self.canonicalize_unicode(segment)
        phone_lookup = set(self.phones.keys())
        if phoneset:
            phone_lookup |= set(phoneset.phones)

        if segment in phone_lookup:
            return [(segment, [])]

        result = []
        skipped: list[str] = []
        i = 0
        while i < len(segment):
            best_phone, best_len = longest_match(
                segment, i, phone_lookup, MAX_MATCH_LEN, tie_set=phone_lookup
            )

            if best_phone:
                diacritics = []
                j = i + best_len
                while (
                    j < len(segment)
                    and segment[j] in self.diacritics
                    and segment[j] not in (TIE_BAR, SEQ_TIE)
                    and modifier_mode(self, segment[j]) != "structural"
                ):
                    diacritics.append(segment[j])
                    j += 1
                result.append((best_phone, diacritics))
                i = j
            elif segment[i] in self.diacritics:
                result.append((segment[i], []))
                i += 1
            else:
                skipped.append(segment[i])
                i += 1

        if strict:
            require_convertible(skipped, "IPA segment")

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
            token = unicodedata.normalize("NFC", base + "".join(diacritics))
            result.append((token, feats))
        return result

    # -------------------------------------------------------------------------
    # Structured segments (docs/ties.md; design spec)
    # -------------------------------------------------------------------------

    def segments(self, text: str) -> list[Segment]:
        """Parse IPA text into structured :class:`Segment` units.

        Same segmentation as :meth:`tokenize_ipa`. Stress marks attach to
        the following unit's prosody; other prosodic marks (length, tone)
        attach to the unit they follow. Structural marks (ties become
        junctures; breaks/linking live between units) never appear in a
        unit's prosody.
        """
        result: list[Segment] = []
        pending_stress: list[str] = []
        for token in self.tokenize_ipa(text):
            if token and all(
                ch in self.diacritics and "stress" in self.diacritics[ch].features
                for ch in token
            ):
                pending_stress.extend(token)
                continue
            seg = self._segment_from_token(token, tuple(pending_stress))
            pending_stress = []
            if seg is not None:
                result.append(seg)
        return result

    def segment(self, text: str) -> Segment:
        """Parse exactly one unit into a :class:`Segment`.

        Raises ``ValueError`` if the text tokenizes to zero or several
        units.
        """
        segs = self.segments(text)
        if len(segs) != 1:
            raise ValueError(
                f"expected exactly one unit, got {len(segs)} from {text!r}"
            )
        return segs[0]

    def build_segment(
        self,
        parts: list[str],
        senses: Sense | list[Sense] | None = None,
        prosody: tuple[str, ...] = (),
    ) -> Segment:
        """Construct a :class:`Segment` from intent, bypassing string-alias
        collisions: each part is a base phone with optional trailing
        modifiers, and ``senses`` gives the junctures explicitly (one
        ``Sense``, repeated, or one per juncture)."""
        constituents = tuple(self._parse_constituent(p) for p in parts)
        n = len(constituents)
        if senses is None:
            junctures: tuple[Sense, ...] = tuple([Sense.FUSE] * (n - 1))
        elif isinstance(senses, Sense):
            junctures = tuple([senses] * (n - 1))
        else:
            junctures = tuple(senses)
        for mark in prosody:
            if modifier_mode(self, mark) == "structural":
                raise ValueError(
                    f"structural mark {mark!r} is not prosody; "
                    "ties are junctures, breaks live between units"
                )
        return Segment(
            constituents=constituents,
            junctures=junctures,
            prosody=prosody,
            _features=self,
        )

    def from_wild(self, text: str) -> str:
        """Import IPA written in other conventions into house style.

        In the wild the two tie glyphs are typographic free variants, so a
        spelling carries no reliable sense. This helper — explicitly, never
        as part of default parsing — rewrites each tied chain to house
        style: a spelling whose glyph-variant names a registered compound
        becomes that canonical spelling (``t͜s`` -> ``t͡s``,
        ``a͡ɪ`` -> ``a͜ɪ``); an unregistered chain gets the sense
        heuristic (all-vocalic -> sequential, else simultaneous). House
        input passes through unchanged.
        """
        text = self.canonicalize_unicode(text)
        for variant, canonical in self._wild_variants().items():
            text = text.replace(variant, canonical)

        # Remaining ties belong to unregistered chains. Wild text uses one
        # tie glyph as a typographic habit, so only uniform-glyph chains are
        # re-sensed (per juncture, from the neighbouring bases -- the
        # add_tie_bars heuristic); a chain already mixing both glyphs is
        # house-authored and passes through untouched.
        def _vocalic_char(ch: str) -> bool:
            phone = self.phones.get(ch)
            return phone is not None and phone.features.get("manner") == "vowel"

        chars = list(text)
        runs: list[list[int]] = []
        current: list[int] = []
        pending_tie = False
        for i, ch in enumerate(chars):
            if ch in (TIE_BAR, SEQ_TIE):
                current.append(i)
                pending_tie = True
            elif ch in self.phones and ch not in self.diacritics:
                if not pending_tie and current:
                    runs.append(current)
                    current = []
                pending_tie = False
            elif ch in self.diacritics:
                continue
            else:
                if current:
                    runs.append(current)
                    current = []
                pending_tie = False
        if current:
            runs.append(current)

        for run in runs:
            glyphs = {chars[i] for i in run}
            if len(glyphs) != 1:
                continue  # mixed-glyph chain: house-authored
            for i in run:
                prev_i = i - 1
                while prev_i >= 0 and chars[prev_i] in self.diacritics:
                    prev_i -= 1
                next_i = i + 1
                if prev_i >= 0 and next_i < len(chars):
                    both_vocalic = _vocalic_char(chars[prev_i]) and _vocalic_char(
                        chars[next_i]
                    )
                    chars[i] = SEQ_TIE if both_vocalic else TIE_BAR
        return "".join(chars)

    def _wild_variants(self) -> dict[str, str]:
        """Glyph-variant spellings of registered tied names -> canonical,
        longest first so longer chains win. Cached per instance."""
        cached: dict[str, str] | None = getattr(self, "_wild_variants_cache", None)
        if cached is not None:
            return cached
        variants: dict[str, str] = {}
        for name in self.phones:
            if TIE_BAR not in name and SEQ_TIE not in name:
                continue
            positions = [i for i, ch in enumerate(name) if ch in (TIE_BAR, SEQ_TIE)]
            for mask in range(1, 2 ** len(positions)):
                chars = list(name)
                for bit, pos in enumerate(positions):
                    if mask & (1 << bit):
                        chars[pos] = SEQ_TIE if chars[pos] == TIE_BAR else TIE_BAR
                variants["".join(chars)] = name
        return dict(sorted(variants.items(), key=lambda kv: -len(kv[0])))

    def import_phoneset(self, phoneset: Phoneset) -> Phoneset:
        """Import a phoneset written in other conventions into house style.

        Each member goes through :meth:`from_wild` (tie-convention
        spellings of registered compounds canonicalize; everything else
        passes through); duplicates that collapse under canonicalization
        are dropped, order preserved. Explicit, like all wild imports --
        phoneset members are never rewritten implicitly.
        """
        seen: set[str] = set()
        phones: list[str] = []
        for member in phoneset.phones:
            canonical = self.from_wild(member)
            if canonical not in seen:
                seen.add(canonical)
                phones.append(canonical)
        return Phoneset(name=phoneset.name, phones=phones)

    def is_structural_token(self, token: str) -> bool:
        """True if ``token`` is entirely structural marks (the linking
        undertie, breaks): a boundary relation between units, not a
        segment. Distance and alignment treat such tokens as transparent."""
        return bool(token) and all(
            ch in self.diacritics and modifier_mode(self, ch) == "structural"
            for ch in token
        )

    def _parse_constituent(self, part: str) -> Constituent:
        part = self._resolve_token(part)
        base, best_len = longest_match(part, 0, self.phones, MAX_MATCH_LEN)
        if not base:
            raise ValueError(f"no registered base phone in {part!r}")
        modifiers = []
        for ch in part[best_len:]:
            if ch not in self.diacritics:
                raise ValueError(f"unknown modifier {ch!r} in {part!r}")
            modifiers.append(ch)
        return Constituent(base=base, modifiers=tuple(modifiers))

    def _segment_from_token(
        self, token: str, stress: tuple[str, ...] = ()
    ) -> Segment | None:
        parsed = self.parse(token)
        if not parsed:
            return None
        chain, diacritics = parsed[0]

        raw = re.split(f"([{TIE_BAR}{SEQ_TIE}])", chain)
        part_strs = raw[0::2]
        glyphs = raw[1::2]
        try:
            constituents = tuple(self._parse_constituent(p) for p in part_strs)
        except ValueError:
            # Structural-only or malformed token (lone tie, stray mark):
            # nothing segmental to represent.
            return None

        if len(constituents) > 1 and chain in self.phones:
            # Registered entry: its sense wins over the written glyph.
            # Transitional rule until the data migration makes sense
            # explicit: all-vocalic entries are sequential, else fused.
            all_vocalic = all(
                (p := self.get_phone(c.base)) is not None
                and p.features.get("manner") == "vowel"
                for c in constituents
            )
            sense = Sense.SEQ if all_vocalic else Sense.FUSE
            junctures = tuple([sense] * (len(constituents) - 1))
        else:
            junctures = tuple(Sense.FUSE if g == TIE_BAR else Sense.SEQ for g in glyphs)

        prosody: list[str] = list(stress)
        modifiers: list[str] = []
        for mark in diacritics:
            mode = modifier_mode(self, mark)
            if mode == "structural":
                continue
            if mode == "prosodic":
                prosody.append(mark)
            else:
                modifiers.append(mark)
        if modifiers:
            last = constituents[-1]
            constituents = constituents[:-1] + (
                Constituent(
                    base=last.base, modifiers=last.modifiers + tuple(modifiers)
                ),
            )
        return Segment(
            constituents=constituents,
            junctures=junctures,
            prosody=tuple(prosody),
            _features=self,
        )

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
        """True if ``phone`` is a registered phone or a composable tie-barred
        sequence of known phones (e.g. "t͡ɬ"), matching what
        :meth:`get_features` can resolve. Not the same set as
        :meth:`__iter__`/:meth:`__len__`, which cover the registered
        inventory only.
        """
        phone = self._resolve_token(phone)
        return phone in self.phones or self._is_composable(phone)

    def __iter__(self) -> Iterator[str]:
        return iter(self.phones.keys())

    def __len__(self) -> int:
        return len(self.phones)
