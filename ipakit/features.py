"""IPAFeatures class for IPA feature database."""

from __future__ import annotations

import functools
import re
import unicodedata
import warnings
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from pathlib import Path
from types import MappingProxyType

from ._convert import longest_match, require_convertible
from .analysis import AnalysisMixin
from .constants import (
    DEFAULT_IPA_FEATS,
    DEFAULT_SHORT_NAME_LEN,
    MAX_MATCH_LEN,
    METADATA_ATTRS,
    SEQ_TIE,
    TIE_BAR,
)
from .distance import DistanceMixin
from .hierarchy import HierarchyMixin
from .models import Feature, Phone, Phoneset
from .segment import (
    Constituent,
    Segment,
    Sense,
    apply_modifiers,
    fill_defaults,
    modifier_mode,
)
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
        # Soft reads: ASCII stand-in -> IPA symbol. Applied only on explicit
        # wild import (:meth:`from_wild`), never by default parsing.
        self.lookalikes: dict[str, str] = {}
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
                offscale: set[str] = set()
                coordinates: dict[str, dict[str, float]] = {}
                articulators: dict[str, str] = {}
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
                            if v.get("offscale"):
                                offscale.add(val_name)
                            coords = {
                                attr: float(raw)
                                for attr in ("arc", "offset")
                                if (raw := v.get(attr)) is not None
                            }
                            if coords:
                                coordinates[val_name] = coords
                            if (art := v.get("articulator")) is not None:
                                articulators[val_name] = art
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
                    axis=feat_elem.get("axis"),
                    offscale=frozenset(offscale),
                    coordinates=coordinates,
                    articulators=articulators,
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
            self.phones[name] = Phone(symbol=name, features=MappingProxyType(merged))
            derived.add(name)
        return frozenset(derived)

    def _load_lookalikes(self) -> None:
        """Load the ASCII soft-read table from lookalikes.xml."""
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
        phone = Phone(symbol=symbol, features=MappingProxyType(features))

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

        A base carrying diacritics (``tʲ``, ``ã``, ``tʰ``) is neither
        registered nor a tie chain; it reads through the same parse the
        structured level uses, so the two levels cannot disagree about
        one string. Prosodic marks are the documented exception: they
        belong to the unit, not to its feature bag, so ``eː`` reads the
        features of ``e`` and carries its length as prosody.

        Returns ``{}`` when nothing resolves.
        """
        phone = self._resolve_token(phone)
        if phone in self.phones:
            feats = dict(self.phones[phone].features)
        elif (composed := self._compose_tie_bar_features(phone)) is not None:
            feats = composed
        else:
            return self._modified_features(phone, with_defaults=with_defaults)
        if with_defaults:
            fill_defaults(self, feats)
        return feats

    def _modified_features(
        self, phone: str, with_defaults: bool = True
    ) -> dict[str, str]:
        """Features of a base carrying diacritics, via the structured parse.

        :meth:`Segment.scalar` is the modifier overlay over the unit's
        bare chain, and it calls back into :meth:`get_features` with that
        chain. That is the recursion this guards: when the chain is the
        string itself, nothing was stripped, so the overlay has nothing
        to add and the chain is the string we already failed to resolve.
        The answer is then ``{}``.

        The test is the chain rather than the modifier list because a
        prosodic mark (``eː``) is stripped to the unit's prosody and
        never becomes a modifier, yet still leaves a chain worth reading.
        """
        try:
            unit = self.segment(phone)
        except ValueError:
            return {}
        chain = "".join(
            c.base if i == 0 else unit.junctures[i - 1].glyph + c.base
            for i, c in enumerate(unit.constituents)
        )
        if chain == phone:
            return {}

        # Tokenization currently drops characters it does not know, so a
        # parse can succeed while silently discarding input: "q͡X" parses
        # to "q". Re-emitting the unit is the check that the parse
        # accounts for the whole string.
        #
        # The comparison is by character multiset rather than by string,
        # because a stress mark is re-emitted before its base ("tˈ"
        # spells back as "ˈt") -- reordered, not lost. Structural marks
        # are excluded on both sides: the linking undertie is a boundary
        # relation between units and belongs to no Segment by design, so
        # its absence from the emission is not a dropped character.
        def _substantive(text: str) -> list[str]:
            return sorted(ch for ch in text if not self.is_structural_token(ch))

        if _substantive(unit.to_ipa()) != _substantive(phone):
            return {}
        return unit.scalar(with_defaults=with_defaults)

    def feature_values(self, unit: str) -> dict[str, tuple[str, ...]]:
        """Every value each feature takes across one unit's constituents.

        The multi-valued companion of :meth:`get_features`, and the named
        bridge from the flat string API to the structured reads: the flat
        read is *scalar* (one value per feature) and for a composed unit it
        is a summary -- ``u͜i`` projects its first element, so its
        ``backness`` reads ``back`` and the ``front`` is only recoverable
        from the token. This read keeps both, in constituent order.

        The three shapes on :class:`Segment` are the same three:
        ``scalar()`` is what :meth:`get_features` returns, ``bag()`` is this,
        and ``disagreements()`` is this filtered to the features holding
        more than one value.

        Raises ``ValueError`` if ``unit`` is not exactly one unit.
        """
        return self.segment(unit).bag()

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
        # Try as a feature value (long name), or a friendly alias of one
        # (labial-velar -> bilabial^velar): aliases resolve everywhere a
        # value is accepted, including here.
        for feat_name, feat in self.features.items():
            if term in feat.values:
                return (feat_name, term)
            if term in feat.value_aliases:
                return (feat_name, feat.value_aliases[term])
        # Try as a binary feature name (e.g., 'voiced' -> ('voiced', '+' or '-'))
        if term in self.features and self.features[term].type == "binary":
            if prefix == "+":
                return (term, "+")
            elif prefix == "-":
                return (term, "-")
        return None

    def _resolve_query(
        self, query: dict[str, str] | list[str] | set[str]
    ) -> tuple[dict[str, str], dict[str, set[str]]]:
        """Resolve a feature query into (required, excluded) constraints.

        The query language is documented on :meth:`phones_matching`;
        resolution is factored out here so :meth:`find` runs that same
        language over a transcription instead of growing a second one.
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
            # A dict names features directly, but its values still go
            # through the alias table: labial-velar is the readable
            # spelling of bilabial^velar and must match it.
            for key, val in query.items():
                feature = self.features.get(key)
                positive[key] = feature.value_aliases.get(val, val) if feature else val

        if not positive and not negative:
            raise ValueError(
                f"no feature terms resolved from {query!r}; an unresolved "
                "query would match the entire inventory"
            )
        return positive, negative

    @staticmethod
    def _query_matches(
        feats: dict[str, str],
        required: dict[str, str],
        excluded: dict[str, set[str]],
    ) -> bool:
        """True if a feature bundle satisfies resolved query constraints."""
        return all(feats.get(k) == v for k, v in required.items()) and all(
            feats.get(k) not in vals for k, vals in excluded.items()
        )

    def phones_matching(
        self, query: dict[str, str] | list[str] | set[str], with_defaults: bool = True
    ) -> list[str]:
        """Get all phones matching features.

        Accepts dict or list/set of short or long names.
        Names can be prefixed with + (has value) or - (does not have value).
        E.g., ['+aspirated', '-voiced'] or ['+asp', '-voi'].

        Searches the registered inventory; :meth:`find` runs the same query
        over the units of a transcription.
        """
        required, excluded = self._resolve_query(query)
        return [
            symbol
            for symbol in self.phones
            if self._query_matches(
                self.get_features(symbol, with_defaults=with_defaults),
                required,
                excluded,
            )
        ]

    def find(
        self,
        ipa: str,
        query: dict[str, str] | list[str] | set[str],
        with_defaults: bool = True,
    ) -> list[tuple[int, Segment]]:
        """Locate the units of ``ipa`` whose features match ``query``.

        Natural-class search over a transcription: the same query language
        :meth:`phones_matching` takes (a feature dict, or short/long names
        with +/-/0 prefixes), matched against each unit's flat projection --
        :meth:`Segment.scalar`, which is the read :meth:`get_features` gives
        for the same string. A registered unit therefore matches here
        exactly when its spelling matches there, and a composed unit, which
        :meth:`phones_matching` never sees, matches on the same terms.

        Positions index :meth:`segments`, not characters: stress and
        structural marks are not units (they ride on the unit they modify,
        or between units), so ``find(s, q)[k]`` is ``(i, segments(s)[i])``.

        Matches are :class:`Segment` objects rather than token strings
        because a match is usually the prologue to reading the unit, and the
        unit is already parsed: it spells itself with ``to_ipa()`` and also
        carries ``kind``, ``bag()`` and the edge reads, where a token would
        have to be re-parsed for any of them. The token form costs one
        comprehension: ``[(i, u.to_ipa()) for i, u in find(...)]``.
        """
        required, excluded = self._resolve_query(query)
        return [
            (i, unit)
            for i, unit in enumerate(self.segments(ipa))
            if self._query_matches(
                unit.scalar(with_defaults=with_defaults), required, excluded
            )
        ]

    def to_phone(self, bundle: dict[str, str]) -> str | None:
        """The registered symbol a feature bundle names: the inverse of
        :meth:`get_features`.

        A candidate matches when it agrees on every key the caller wrote;
        keys the caller omitted are free. Candidates are read with their
        defaults filled, so ``{"manner": "plosive", "place": "alveolar"}``
        realizes as "t" -- the phone that takes the defaults -- not "d".
        Metadata keys (``class``, ``href``) are ignored, so a bundle
        straight out of :meth:`get_features` round-trips.

        Several phones can satisfy one bundle; the winner is decided, in
        order, by:

        1. **fewest extra features** -- the explicit (non-default)
           features a candidate declares beyond the ones asked for, so
           the most general phone answering the request wins;
        2. **fewest constituents** -- a tied compound's flat bundle is
           only the projection of one constituent (docs/ties.md), so it
           never outranks an atom matching equally well: "a", not "a͜ɪ";
        3. **declaration order** in the data.

        Returns ``None`` when nothing registered matches -- an impossible
        or merely unattested combination.
        """
        # Values go through the alias table, as they do on every read
        # path: labial-velar is a spelling of bilabial^velar, and the
        # write side must not be the one place it fails.
        query: dict[str, str] = {}
        for key, value in bundle.items():
            if key in METADATA_ATTRS:
                continue
            feature = self.features.get(key)
            query[key] = feature.value_aliases.get(value, value) if feature else value
        if not query:
            # Every phone satisfies a bundle that asks nothing, and the
            # tie-break then answers with silence -- so an empty read
            # upstream would come back as a confident phone.
            raise ValueError(
                "cannot realize an empty feature bundle: it names every "
                "phone, not one. Pass at least one feature."
            )
        best: tuple[int, int, int] | None = None
        winner: str | None = None
        for order, symbol in enumerate(self.phones):
            feats = self.get_features(symbol)
            if any(feats.get(k) != v for k, v in query.items()):
                continue
            extras = sum(
                1
                for k in self.phones[symbol].features
                if k not in METADATA_ATTRS and k not in query
            )
            junctures = symbol.count(TIE_BAR) + symbol.count(SEQ_TIE)
            rank = (extras, junctures, order)
            if best is None or rank < best:
                best, winner = rank, symbol
        return winner

    def respell(self, phone: str, **changes: str) -> str | None:
        """Apply a feature change to ``phone`` and realize the result.

        ``respell("t", voiced="+")`` is "d"; ``respell("p",
        place="velar")`` is "k". The delta lands on the phone's
        default-filled features and goes through :meth:`to_phone`, whose
        matching and tie rules therefore govern the answer. This is what
        makes a feature-changing rule expressible at all.

        A feature whose name carries a hyphen is also reachable with an
        underscore (``tongue_root``), since a hyphen cannot be a keyword.

        Returns ``None`` when the changed bundle names no registered
        phone. Raises ``ValueError`` if ``phone`` does not resolve, or if
        a change names a feature or a value the data does not declare: a
        misspelled feature has to fail loudly rather than quietly leave
        the phone as it was.
        """
        feats = self.get_features(phone)
        if not feats:
            raise ValueError(f"cannot resolve phone {phone!r}")
        for name, value in changes.items():
            key = name if name in self.features else name.replace("_", "-")
            feature = self.features.get(key)
            if feature is None:
                raise ValueError(f"unknown feature {name!r}")
            resolved = feature.value_aliases.get(value, value)
            # Every component must be declared. A scalar value expands to
            # itself, so this accepts a plain value and a generative
            # overlap (bilabial^velar) on the same terms.
            if not all(part in feature.values_set for part in feature.expand(resolved)):
                raise ValueError(f"{value!r} is not a value of feature {key!r}")
            feats[key] = resolved
        for meta in METADATA_ATTRS:
            feats.pop(meta, None)
        return self.to_phone(feats)

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

        The recomposition looks within a base's whole run of combining
        marks rather than at the two characters that happen to be
        adjacent, because canonical ordering can separate a symbol from
        its own mark: "ç" plus the velarization overlay reorders to
        c, U+0334, U+0327 (ccc 1 sorts before ccc 202), and a substring
        replace would leave the cedilla stranded -- turning a palatal
        fricative into a velarized "c".
        """
        text = self._recompose_registered(unicodedata.normalize("NFD", text))
        # Both ties stacked on one juncture assert contradictory timing; the
        # simultaneous reading takes precedence, so the pair collapses to the
        # over-tie. (NFD orders U+035C before U+0361 - ccc 233 < 234 - so one
        # replace covers both written orders.)
        text = text.replace(SEQ_TIE + TIE_BAR, TIE_BAR)
        return text

    def _recompose_registered(self, text: str) -> str:
        """Rebuild registered precomposed symbols from decomposed text.

        Each base plus its following run of combining marks is one
        cluster; a mark anywhere in that run may be the one belonging to
        the base, so it is pulled out wherever it sits rather than only
        when it happens to be adjacent.
        """
        out: list[str] = []
        i = 0
        while i < len(text):
            base = text[i]
            end = i + 1
            while end < len(text) and unicodedata.combining(text[end]):
                end += 1
            marks = list(text[i + 1 : end])
            for position, mark in enumerate(marks):
                if (symbol := self._nfd_to_registered.get(base + mark)) is not None:
                    base = symbol
                    marks.pop(position)
                    break
            out.append(base)
            out.extend(marks)
            i = end
        return "".join(out)

    def normalize_lookalikes(self, text: str) -> str:
        """Apply the ASCII soft reads: keyboard stand-ins -> IPA symbols.

        This is a **wild-import** step, not a parsing step: default
        parsing is strict house style and never rewrites input, so this
        runs only where import is explicit (:meth:`from_wild`, the
        ``features`` CLI) or where a caller asks for it by name.

        The table (``data/phonemaps/lookalikes.xml``) holds only
        characters with one dominant wild reading::

            g -> ɡ    :  -> ː    ?  -> ʔ    '  -> ˈ (PRIMARY STRESS)

        ``'`` reads as primary stress U+02C8, not the ejective U+02BC:
        that is what ``kirshenbaum.xml`` in this package already says, and
        X-SAMPA spells the ejective ``_>``. ``!`` is **not** in the table
        at all -- click, downstep and punctuation are all live readings of
        it, so it stays unknown rather than being guessed at (see
        docs/ties.md).

        Examples:
            >>> IPAFeatures().normalize_lookalikes("gɑ:t")
            'ɡɑːt'
        """
        for lookalike, ipa in self.lookalikes.items():
            text = text.replace(lookalike, ipa)
        return text

    def expand_ligatures(self, ipa: str) -> str:
        """Expand deprecated IPA ligatures (ʧ, ʤ) to modern tie-bar form.

        Only single-character ligature aliases are replaced; tie glyphs are
        never rewritten here (the glyph is the sense), and neither are the
        ASCII soft reads (``g``, ``:``, ``?``, ``'``) -- wild-convention
        text imports via :meth:`from_wild`.

        Examples:
            >>> IPAFeatures().expand_ligatures("g:")  # default parsing is literal
            'g:'
        """
        ipa = self.canonicalize_unicode(ipa)
        for lig, expanded in self.ligature_map.items():
            if len(lig) > 1 and (TIE_BAR in lig or SEQ_TIE in lig):
                continue
            ipa = ipa.replace(lig, expanded)
        return ipa

    def add_ties(self, segment: str) -> str:
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

    def normalize(self, segments: str) -> str:
        """Normalize whitespace-separated IPA segments into decodable IPA string.

        Each whitespace-separated group is treated as one asserted unit;
        :meth:`add_ties` inserts the tie by sense (adjacent vowels bind
        sequentially, anything else fuses).
        """
        segments = self.expand_ligatures(segments)
        return unicodedata.normalize(
            "NFC", "".join(self.add_ties(seg) for seg in segments.split())
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

    def tokenize(
        self,
        ipa: str,
        phoneset: Phoneset | None = None,
        strict: bool = False,
    ) -> list[str]:
        """Parse IPA string into list of segment tokens.

        Tokens are emitted in NFC so both precomposed and decomposed input
        yield identical output. Tie-joined runs of known phones are one
        token whichever tie binds them; the tie glyph is preserved (it is
        the sense).

        The tokenizer is total by default -- it never raises, whatever it
        is handed -- but it is not silent: an unregistered character is
        dropped with a warning (see :meth:`parse`). ``strict=True`` raises
        ``ValueError`` instead, which is what to use when
        ``to_ipa(segments(x)) == x`` has to be guaranteed rather than
        hoped for.

        Examples:
            >>> IPAFeatures().tokenize("t͡ʃa")
            ['t͡ʃ', 'a']
        """
        ipa = self.expand_ligatures(ipa)
        return [
            unicodedata.normalize("NFC", base + "".join(diacs))
            for base, diacs in self.parse(ipa, phoneset=phoneset, strict=strict)
        ]

    def segmented(
        self,
        ipa: str,
        phoneset: Phoneset | None = None,
        strict: bool = False,
    ) -> str:
        """Parse IPA string and return whitespace-separated segments."""
        return " ".join(self.tokenize(ipa, phoneset=phoneset, strict=strict))

    def parse(
        self,
        segment: str,
        phoneset: Phoneset | None = None,
        strict: bool = False,
    ) -> list[tuple[str, list[str]]]:
        """Parse an IPA segment string into (chain, diacritics) tuples.

        Registered symbols match longest-first; tie glyphs are preserved
        as written (the glyph is the sense).

        A tie binds the whole preceding **unit**, not merely a registered
        base: a base plus the modifiers written on it is one constituent,
        so ``t̪͡s`` and ``kʷ͡p`` are single tokens exactly as ``t͡s`` and
        ``k͡p`` are. The returned chain therefore carries the modifiers of
        every constituent but the last, whose modifiers stay in the second
        element -- where they have always been for ``t͡sʷ``.

        A tie with nothing to bind on one side carries no juncture, so it
        cannot be represented either; it is reported exactly like an
        unregistered character rather than emitted as a token of its own,
        because a silently dropped tie turns one asserted unit into two.
        This is the ``malformed_tie`` :meth:`validate_ipa` reports.

        A character that is registered nowhere in the inventory cannot be
        represented, so it is dropped -- but never silently: the default
        path warns, naming what it lost, because a shorter result that
        still *looks* well formed is the failure mode worth hearing about.
        ``strict=True`` raises ``ValueError`` instead. (Registered
        separators and whitespace are not "unknown": they are known marks
        that carry no unit, and they neither warn nor raise.)

        ASCII stand-ins are not soft-read here -- ``g``, ``:``, ``?`` and
        ``'`` are unregistered characters like any other. Import such text
        with :meth:`from_wild` first.
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
        unbound_ties: list[str] = []
        n = len(segment)
        i = 0
        while i < n:
            best_phone, best_len = longest_match(
                segment, i, phone_lookup, MAX_MATCH_LEN, tie_set=phone_lookup
            )

            if best_phone:
                chain = best_phone
                j = i + best_len
                diacritics = self._modifier_run(segment, j)
                j += len(diacritics)
                # A tie joins the unit just read -- base *and* the
                # modifiers written on it -- to the one after it.
                # ``longest_match`` only spans ties between registered
                # bases, so the rest of the chain is grown here; without
                # this, a tie written after a diacritic falls through to
                # the standalone branch and the juncture is lost.
                while j < n and segment[j] in (TIE_BAR, SEQ_TIE):
                    next_phone, next_len = longest_match(
                        segment,
                        j + 1,
                        phone_lookup,
                        MAX_MATCH_LEN,
                        tie_set=phone_lookup,
                    )
                    if not next_phone:
                        break
                    chain += "".join(diacritics) + segment[j] + next_phone
                    j += 1 + next_len
                    diacritics = self._modifier_run(segment, j)
                    j += len(diacritics)
                result.append((chain, diacritics))
                i = j
            elif segment[i] in (TIE_BAR, SEQ_TIE):
                # Only reached when the tie binds nothing on one side: a
                # tie with units either side is consumed by the loop above
                # or by ``longest_match``. Losing it would turn one
                # asserted unit into two, so it is recorded, not emitted.
                unbound_ties.append(segment[i])
                i += 1
            elif segment[i] in self.diacritics:
                result.append((segment[i], []))
                i += 1
            else:
                # Registered separators (syllable break, word mark) and
                # whitespace are known symbols that simply carry no unit;
                # only unregistered characters count as lost.
                if not (segment[i].isspace() or segment[i] in self.separators):
                    skipped.append(segment[i])
                i += 1

        if strict:
            require_convertible(skipped, "IPA segment")
            if unbound_ties:
                raise ValueError(
                    f"Cannot parse IPA segment: {len(unbound_ties)} tie "
                    f"glyph(s) {sorted(set(unbound_ties))} bind nothing "
                    "(malformed tie): a tie joins the unit before it to the "
                    "unit after it."
                )
        else:
            if skipped:
                warnings.warn(
                    f"dropped {len(skipped)} unregistered symbol(s) "
                    f"{sorted(set(skipped))} while parsing IPA: the result is "
                    "shorter than the input. Pass strict=True to raise instead, "
                    "or import wild-convention text with from_wild().",
                    stacklevel=2,
                )
            if unbound_ties:
                warnings.warn(
                    f"dropped {len(unbound_ties)} unbound tie glyph(s) "
                    f"{sorted(set(unbound_ties))} while parsing IPA: a tie "
                    "joins the unit before it to the unit after it, and these "
                    "bind nothing. Pass strict=True to raise instead.",
                    stacklevel=2,
                )

        return result

    def _modifier_run(self, text: str, start: int) -> list[str]:
        """The run of modifier diacritics starting at ``text[start]``.

        Stops at anything structural -- a tie, a break, the linking mark --
        because those relate units rather than modify one.
        """
        run: list[str] = []
        j = start
        while (
            j < len(text)
            and text[j] in self.diacritics
            and text[j] not in (TIE_BAR, SEQ_TIE)
            and modifier_mode(self, text[j]) != "structural"
        ):
            run.append(text[j])
            j += 1
        return run

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

        Same segmentation as :meth:`tokenize`, but suprasegmentals and
        separators that carry no phonetic features (stress, syllable breaks) are
        dropped, so every token lines up with its composed feature bundle.

        Diacritics contribute through :func:`~ipakit.segment.apply_modifiers`,
        the same overlay :meth:`Segment.scalar` and
        :meth:`Constituent.bundle` use, so the three reads of one marked
        token agree. The base is read undefaulted so that a mark adding
        what the base leaves unstated lands before the defaults do.
        """
        result: list[tuple[str, dict[str, str]]] = []
        for base, diacritics in self.parse(segment, phoneset=phoneset):
            if not (feats := self.get_features(base, with_defaults=False)):
                continue
            apply_modifiers(self, feats, diacritics, prosody=True)
            if with_defaults:
                fill_defaults(self, feats)
            token = unicodedata.normalize("NFC", base + "".join(diacritics))
            result.append((token, feats))
        return result

    # -------------------------------------------------------------------------
    # Structured segments (docs/ties.md; design spec)
    # -------------------------------------------------------------------------

    def segments(self, text: str, strict: bool = False) -> list[Segment]:
        """Parse IPA text into structured :class:`Segment` units.

        Same segmentation as :meth:`tokenize`. Stress marks attach to
        the following unit's prosody; other prosodic marks (length, tone)
        attach to the unit they follow. Structural marks (ties become
        junctures; breaks/linking live between units) never appear in a
        unit's prosody.

        Unregistered characters are dropped with a warning, as in
        :meth:`tokenize`; ``strict=True`` raises instead, which is what
        guarantees ``to_ipa(segments(text)) == text``.
        """
        result: list[Segment] = []
        pending_stress: list[str] = []
        for token in self.tokenize(text, strict=strict):
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

    def segment(self, text: str, strict: bool = False) -> Segment:
        """Parse exactly one unit into a :class:`Segment`.

        Raises ``ValueError`` if the text tokenizes to zero or several
        units -- or, with ``strict=True``, if it holds an unregistered
        character (which by default is dropped with a warning).
        """
        segs = self.segments(text, strict=strict)
        if len(segs) != 1:
            raise ValueError(
                f"expected exactly one unit, got {len(segs)} from {text!r}"
            )
        return segs[0]

    def build_segment(
        self,
        parts: list[str | dict[str, str]],
        senses: Sense | list[Sense] | None = None,
        prosody: tuple[str, ...] = (),
    ) -> Segment:
        """Construct a :class:`Segment` from intent, bypassing string-alias
        collisions: each part is a base phone with optional trailing
        modifiers -- or a feature bundle, realized through
        :meth:`to_phone` -- and ``senses`` gives the junctures explicitly
        (one ``Sense``, repeated, or one per juncture).

        Taking bundles makes the structured level writable on the same
        terms as the flat one: a rule that computes features can build a
        unit without first spelling its parts out as symbols. A bundle
        naming no registered phone is the caller's error, not a silent
        omission, so it raises ``ValueError``.
        """
        constituents = tuple(self._parse_constituent(self._as_part(p)) for p in parts)
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

    def to_ipa(self, segments: list[Segment]) -> str:
        """Join structured units back into one IPA string.

        The inverse of :meth:`segments`: ``to_ipa(segments(s)) == s`` for
        house-canonical, purely segmental input. A join guarantees no more
        than its parts do, and each unit emits through
        :meth:`Segment.to_ipa`, which is lossy on the enumerable set of
        legacy alias spellings (docs/ties.md) -- so the join is too:
        ``segments("ʧa")`` rejoins as ``"t͡ʃa"``, the canonical spelling of
        what was parsed rather than the ligature that was written.

        Two further differences are the Segment model showing through, not
        this method rewriting anything: marks that belong to no unit
        (syllable breaks, the linking undertie) are not carried by a
        Segment, so a join cannot restore them; and a stress mark binds to
        the base it was written on and re-emits before it (``kˈæt`` ->
        ``ˈkæt`` -- the same claim about the same unit, spelled
        syllable-initially). Structure that must survive a string round
        trip travels as ``Segment.to_json``.
        """
        return unicodedata.normalize("NFC", "".join(s.to_ipa() for s in segments))

    def from_wild(self, text: str) -> str:
        """Import IPA written in other conventions into house style.

        This is the one door soft reads come through. Two kinds of wild
        spelling are canonicalized here — explicitly, never as part of
        default parsing:

        **Tie conventions.** In the wild the two tie glyphs are
        typographic free variants, so a spelling carries no reliable
        sense. Each tied chain is rewritten to house style: a spelling
        whose glyph-variant names a registered compound becomes that
        canonical spelling (``t͜s`` -> ``t͡s``, ``a͡ɪ`` -> ``a͜ɪ``); an
        unregistered chain gets the sense heuristic (all-vocalic ->
        sequential, else simultaneous).

        **ASCII soft reads.** Keyboard stand-ins become the IPA symbol
        they stand in for: ``g`` -> ``ɡ``, ``:`` -> ``ː``, ``?`` -> ``ʔ``,
        and ``'`` -> ``ˈ`` (primary stress, *not* the ejective ``ʼ``; see
        :meth:`normalize_lookalikes`). ``!`` is left alone — click,
        downstep and punctuation are all live readings of it, and none
        dominates, so it stays an unknown symbol for validation to report
        rather than a guess.

        House input passes through unchanged.

        Examples:
            >>> IPAFeatures().from_wild("'gu:d")
            'ˈɡuːd'
            >>> IPAFeatures().from_wild("kæt!")  # ambiguous, left alone
            'kæt!'
        """
        text = self.canonicalize_unicode(text)
        text = self.normalize_lookalikes(text)
        for variant, canonical in self._wild_variants().items():
            text = text.replace(variant, canonical)

        # Remaining ties belong to unregistered chains. Wild text uses one
        # tie glyph as a typographic habit, so only uniform-glyph chains are
        # re-sensed (per juncture, from the neighbouring bases -- the
        # add_ties heuristic); a chain already mixing both glyphs is
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

    def _as_part(self, part: str | dict[str, str]) -> str:
        """A ``build_segment`` part as a symbol string, realizing a bundle."""
        if isinstance(part, str):
            return part
        symbol = self.to_phone(part)
        if symbol is None:
            raise ValueError(f"no registered phone matches {part!r}")
        return symbol

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
        """True if ``phone`` is a registered phone, a composable tie-barred
        sequence of known phones (e.g. "t͡ɬ"), or a base carrying diacritics
        ("tʲ") -- matching what :meth:`get_features` can resolve. Not the
        same set as :meth:`__iter__`/:meth:`__len__`, which cover the
        registered inventory only.
        """
        phone = self._resolve_token(phone)
        if phone in self.phones or self._is_composable(phone):
            return True
        return bool(self._modified_features(phone, with_defaults=False))

    def __iter__(self) -> Iterator[str]:
        return iter(self.phones.keys())

    def __len__(self) -> int:
        return len(self.phones)
