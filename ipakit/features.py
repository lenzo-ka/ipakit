"""IPAFeatures class for IPA feature database."""

from __future__ import annotations

import dataclasses
import functools
import re
import unicodedata
import warnings
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, TypeVar

from ._convert import longest_match, require_convertible
from .analysis import AnalysisMixin
from .anatomy import landmark_arc
from .constants import (
    DEFAULT_IPA_FEATS,
    DEFAULT_SHORT_NAME_LEN,
    DERIVED_CLASSES,
    MAX_MATCH_LEN,
    METADATA_ATTRS,
    SUPPLEMENT_ROOT,
    SUPPLEMENTS_DIR,
    ZERO_CLASS,
)
from .distance import DistanceMixin

# What a unit's prosody marks say, derived contour included. Underscored
# because it is internal to the package rather than to the module, the way
# `rules` reads `IPAFeatures._resolve_query`: `find` has to resolve a
# Segment's prosody exactly as `form` and `rules` do, and a second copy of
# that read is how the three of them would come to disagree.
from .form import _prosodic_features, boundary_marks
from .hierarchy import HierarchyMixin
from .models import Feature, Phone, Phoneset
from .phonemaps import _load_phonemap
from .segment import (
    APPROACH_MODE,
    Constituent,
    Segment,
    Sense,
    apply_modifiers,
    approach_run,
    check_prosody,
    fill_defaults,
    flat_projection,
    modifier_mode,
    part_bundle,
    phase_keys,
    takes_defaults,
)
from .validation import ValidationMixin

if TYPE_CHECKING:
    from ._tiergraph import Declarations
    from .form import Form, _FormConstants

#: What a resolved query term carries: one value, or a set of them.
_T = TypeVar("_T")

#: A resolved query for one namespace: (required, included, excluded).
#: The three arms answer differently about an absent feature, which is
#: what :meth:`IPAFeatures._query_matches` documents and what keeps a term
#: from going vacuous on a bundle that omits the feature it names.
_Terms = tuple[dict[str, str], dict[str, set[str]], dict[str, set[str]]]

#: What the query language takes: a mapping of feature to value, or a
#: collection of terms. Written as a shape rather than as the two concrete
#: types the resolver used to test for, because everything that failed that
#: test fell into the mapping arm and was asked for ``.items()`` -- so a
#: tuple of terms, a frozenset of them and a bare string all left an
#: ``AttributeError`` out of a public method (#148).
_Query = Mapping[str, str] | Iterable[str]


def available_supplements() -> list[str]:
    """The shipped supplements, by the name ``supplements=`` accepts."""
    return sorted(p.stem for p in SUPPLEMENTS_DIR.glob("*.xml"))


def supplement_path(name: str) -> Path:
    """Where a shipped supplement is, in this copy of the package.

    ``supplements=["aspirated-stops"]`` is the reason this exists: a
    student in a notebook should not have to spell a path into
    ``site-packages`` to reach a file the install already carries, the way
    :func:`ipakit.shipped` already spares them for a rule set.
    """
    path = SUPPLEMENTS_DIR / f"{name}.xml"
    if not path.exists():
        raise ValueError(
            f"no shipped supplement {name!r}; have {available_supplements()}. "
            "A supplement of your own is passed as a path."
        )
    return path


def _resolve_supplement(spec: Path | str) -> Path:
    """A shipped supplement's name, or a path to one of the caller's.

    A shipped name is read first, and it is a bare stem; a path to a
    supplement of the caller's carries its ``.xml``, so the two spellings
    do not overlap. A string that is neither is refused here rather than
    at ``ET.parse``, where a mistyped name reads as a missing file and
    says nothing about the names that would have worked.
    """
    if isinstance(spec, str) and spec in available_supplements():
        return SUPPLEMENTS_DIR / f"{spec}.xml"
    path = Path(spec)
    if not path.exists():
        raise ValueError(
            f"no supplement at {path}, and no shipped supplement of that "
            f"name; have {available_supplements()}"
        )
    return path


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

    def __init__(
        self,
        xml_path: Path = DEFAULT_IPA_FEATS,
        supplements: Sequence[Path | str] = (),
    ):
        self.xml_path = Path(xml_path)
        #: Supplement name -> the file it was read from, in load order.
        #: Empty for the shipped inventory, which is what every module-level
        #: call and every derived artifact in this repository is built on.
        self.supplements: dict[str, Path] = {}
        #: Symbol -> the supplement that declared it. Provenance is held
        #: here rather than as an attribute on the declaring element, for
        #: the reason ``<notations>`` records beside itself: every
        #: attribute on a declaring element lands in that symbol's feature
        #: bundle, and a key in a bundle is a term in the metric. Putting
        #: it there was measured, once, at 37 moved distances.
        self.supplement_of: dict[str, str] = {}
        self.classes: list[str] = []
        self.modes: list[str] = []  # declaration order is mode precedence
        self.default_mode: str = "additive"
        # Bridge name -> the (feature, value) spellings of that dimension.
        self.bridges: dict[str, tuple[tuple[str, str], ...]] = {}
        # Bridge name -> spelling -> how far that spelling opens the velic
        # port, when the bridge declares one. Rendering geometry: read by
        # ipakit.tract, never by the metric, which uses only the pairs above.
        self.bridge_apertures: dict[str, dict[tuple[str, str], float]] = {}
        # A fine (feature, value) -> the coarse (feature, value) it reads as:
        # phonation="devoiced" is voiced="-" read two ways instead of four.
        # Declared in <projections>; read by compose_unit and by
        # ipakit.tract, never resolved onto a segment's features (see the
        # block's comment).
        self.projections: dict[tuple[str, str], tuple[str, str]] = {}
        self.types: dict[str, list[str]] = {}
        self.features: dict[str, Feature] = {}
        self.phones: dict[str, Phone] = {}
        self.diacritics: dict[str, Phone] = {}
        self.separators: dict[str, Phone] = {}
        #: Declared positions that hold a slot open without filling one --
        #: today ``∅``. Its own element class because it is neither a sound
        #: nor a relation between sounds; see :func:`ipakit.form.zeros`.
        self.zeros: dict[str, Phone] = {}
        #: Symbol -> the notation it belongs to, from ``<notations>``. Only
        #: the *listed* symbols: everything else is :attr:`default_notation`,
        #: which is what :meth:`notation_of` reads. Provenance is held here
        #: rather than on each symbol's own element because an attribute
        #: there lands in that symbol's feature bundle, and a key in a
        #: bundle is a term in the metric (the block's comment in ipa.xml
        #: carries the measurement).
        self.notations: dict[str, str] = {}
        #: The notation an unlisted symbol belongs to -- ``chart`` in the
        #: shipped file. Empty where no ``<notations>`` block is declared,
        #: rather than a name invented here.
        self.default_notation: str = ""
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
        # (feature, value) -> named anatomical arc. Feature coordinates stay
        # head-independent for comparison; renderers resolve this retained
        # declaration against the head they project through.
        self._arc_landmarks: dict[tuple[str, str], str] = {}
        self._load()
        self._validate_prominence_contract()
        self._load_lookalikes()
        # Registered symbols whose NFC form differs from NFD (e.g. ä, ç, ť),
        # mapped from their NFD decomposition back to the registered form.
        # Built after loading so canonicalize_unicode can recompose them.
        self._nfd_to_registered: dict[str, str] = {}
        self._index_nfd()
        # Tied entries carry only spelling/aliases/href in the data; their
        # features are derived here from the constituents under the entry's
        # sense, so registered and composed can never drift (docs/ties.md).
        self.derived_phones: frozenset[str] = self._derive_compound_features()
        # Supplements load last, over a complete inventory: an entry that
        # declares no features takes them from what its spelling already
        # composes to, and a tied entry only composes once the block above
        # has filled the tied phones it is built from.
        for spec in supplements:
            self._load_supplement(_resolve_supplement(spec))
        if self.supplements:
            self._index_nfd()
            self._invalidate_derived_reads()

    def _validate_prominence_contract(self) -> None:
        """Refuse inventory drift from the one unit-raising mechanism.

        Prefix raising is deliberately not a generic interpretation of every
        centred structural feature: the reader, word-event projection and
        renderers implement the literally named ``prominence`` feature.  Make
        that coupling a load-time contract instead of letting a declaration
        rename turn the notation into an unregistered character.
        """
        feature = self.features.get("prominence")
        if feature is None:
            raise ValueError(
                "the prefix unit-raising mechanism requires a declared "
                "'prominence' feature; the declaration is missing or renamed"
            )
        if feature.centre is None:
            raise ValueError(
                "the prefix unit-raising mechanism requires feature "
                "'prominence' to declare a centre"
            )
        centre = feature.values.index(feature.centre)
        if centre + 1 >= len(feature.values):
            raise ValueError(
                "the prefix unit-raising mechanism requires feature "
                "'prominence' to declare a value above its centre"
            )
        expected = feature.values[centre + 1]
        markers = {
            symbol: mark.features.get("prominence")
            for symbol, mark in self.diacritics.items()
            if "prominence" in mark.features
        }
        if not markers:
            raise ValueError(
                "the prefix unit-raising mechanism requires a suprasegmental "
                "that declares feature 'prominence'"
            )
        wrong = {
            symbol: value for symbol, value in markers.items() if value != expected
        }
        if wrong:
            raise ValueError(
                "the prefix unit-raising mechanism requires each prominence "
                f"mark to name the first value above the centre, {expected!r}; "
                f"got {wrong}"
            )

    def _index_nfd(self) -> None:
        """Map each registered symbol's NFD form back to the registered one.

        Rebuilt after supplements rather than computed once, because a
        supplement may register a symbol that decomposes (``ǯ``, ``ṭ``)
        and :meth:`canonicalize_unicode` recomposes from this table.
        """
        self._nfd_to_registered = {
            decomposed: sym
            for sym in (
                list(self.phones)
                + list(self.diacritics)
                + list(self.separators)
                + list(self.zeros)
                + list(self.ligature_map)
                + list(self.lookalikes)
            )
            if (decomposed := unicodedata.normalize("NFD", sym)) != sym
        }

    def _invalidate_derived_reads(self) -> None:
        """Drop every cached read of the tables a supplement can extend.

        The derived reads on this class (:attr:`tie_marks`,
        :attr:`stress_markers`, :attr:`features_by_mode` and the rest) are
        ``cached_property``, and loading the base inventory populates
        several of them on the way through. A supplement that registers a
        diacritic would otherwise be invisible to whichever ones had
        already been asked -- one table extended, another answering from
        before it was.

        The set of them is asked of the class rather than listed here, so
        a cached read added later cannot quietly stay stale.
        """
        for klass in type(self).__mro__:
            for name, attr in vars(klass).items():
                if isinstance(attr, functools.cached_property):
                    self.__dict__.pop(name, None)

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

        # Load the contribution-mode vocabulary. Declaration order is
        # precedence; `default` is the mode an undeclared feature makes.
        if (modes_elem := root.find("modes")) is not None:
            self.modes = [
                name for m in modes_elem.findall("mode") if (name := m.get("name"))
            ]
            self.default_mode = modes_elem.get("default") or self.default_mode
            if self.default_mode not in self.modes:
                raise ValueError(
                    f"default mode {self.default_mode!r} is not declared in <modes>"
                )

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
                bare_values: set[str] = set()
                coordinates: dict[str, dict[str, float]] = {}
                articulators: dict[str, str] = {}
                value_apertures: dict[str, str] = {}
                lip_dofs: dict[str, dict[str, float]] = {}
                # Read out of every <value>, typed or not: a typed feature
                # takes its value *set* from the type, but it may still say
                # how its values read and what classes they belong to.
                labels: dict[str, str] = {}
                classes: dict[str, set[str]] = {}
                moves: dict[str, str] = {}
                for v in feat_elem.findall("value"):
                    if not (val_name := v.get("name")):
                        continue
                    if (label := v.get("label")) is not None:
                        labels[val_name] = label
                    if (sign := v.get("move")) is not None:
                        moves[val_name] = sign
                    lip = {
                        attr.replace("lip-", ""): float(raw)
                        for attr in ("lip-width", "lip-protrusion")
                        if (raw := v.get(attr)) is not None
                    }
                    if lip:
                        lip_dofs[val_name] = lip
                    for cls in (v.get("natural-class") or "").split():
                        classes.setdefault(cls, set()).add(val_name)
                if feat_type in self.types:
                    values = self.types[feat_type]
                    # Auto-generate shorts for typed features: +feat, -feat, 0feat
                    declared = set(labels) | {v for m in classes.values() for v in m}
                    if undeclared := declared - set(values):
                        raise ValueError(
                            f"feature {name!r} is typed {feat_type!r} and takes "
                            f"its values from that type; {sorted(undeclared)} is "
                            "not among them"
                        )
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
                            # Which feature a term spelled bare belongs to,
                            # where more than one declares it. Stated, because
                            # the alternative is document order: `nasal` is a
                            # manner, a release phase and an approach phase,
                            # and `[nasal]` meant the manner only because
                            # `manner` is declared first in this file.
                            if v.get("bare"):
                                bare_values.add(val_name)
                            if v.get("offscale"):
                                offscale.add(val_name)
                            coords = {
                                attr: float(raw)
                                for attr in ("arc", "offset")
                                if (raw := v.get(attr)) is not None
                            }
                            if anchor := v.get("arc-landmark"):
                                # An explicit arc in a caller-supplied inventory
                                # is a deliberate override; shipped data owns the
                                # value solely through the named anatomy.
                                if "arc" not in coords:
                                    coords["arc"] = landmark_arc(anchor)
                                    self._arc_landmarks[(name, val_name)] = anchor
                            if coords:
                                coordinates[val_name] = coords
                            if (art := v.get("articulator")) is not None:
                                articulators[val_name] = art
                            if aperture := v.get("aperture"):
                                value_apertures[val_name] = aperture
                            if alias := v.get("alias"):
                                self._value_aliases[name][alias] = val_name
                            if vshort := v.get("short"):
                                self._short_to_feature[vshort] = (name, val_name)
                                self._feature_to_short[(name, val_name)] = vshort
                # A feature may take its value set from another feature
                # rather than restate it. Two features that name the same
                # tract locations must not be two declarations of where
                # those locations are: `constriction-location` says a
                # nucleus constricts at one of the places `place` locates,
                # and copying here is what makes the two one statement, so
                # moving `velar` moves both or neither. The borrower gets
                # the values, the aliases and the geometry; it does not get
                # the source's short codes, which are that feature's
                # notation and must stay unambiguous, nor its labels, which
                # are how the source reads out in a description.
                vocabulary = feat_elem.get("vocabulary")
                if vocabulary is not None:
                    source = self.features.get(vocabulary)
                    if source is None:
                        raise ValueError(
                            f"feature {name!r} declares vocabulary "
                            f"{vocabulary!r}, which is not a feature declared "
                            "before it"
                        )
                    if values:
                        raise ValueError(
                            f"feature {name!r} takes its values from "
                            f"{vocabulary!r} and declares "
                            f"{sorted(set(values))} of its own"
                        )
                    values = list(source.values)
                    self._value_aliases[name] = dict(source.value_aliases)
                    offscale = set(source.offscale)
                    coordinates = {v: dict(c) for v, c in source.coordinates.items()}
                    for landmark_value in source.values:
                        if anchor := self._arc_landmarks.get(
                            (vocabulary, landmark_value)
                        ):
                            self._arc_landmarks[(name, landmark_value)] = anchor
                    articulators = dict(source.articulators)
                    value_apertures = dict(source.apertures)
                    lip_dofs = {v: dict(x) for v, x in source.lip_dofs.items()}
                    classes = {k: set(v) for k, v in source.value_classes.items()}
                # Use feature default, or fall back to type default
                default = feat_elem.get("default") or self._type_defaults.get(feat_type)
                desc = feat_elem.get("desc")
                mode = feat_elem.get("mode")
                if mode is not None and self.modes and mode not in self.modes:
                    raise ValueError(
                        f"feature {name!r} declares mode {mode!r}, which is not "
                        f"one of the declared modes {self.modes}"
                    )
                self.features[name] = Feature(
                    name=name,
                    values=values,
                    default=default,
                    centre=feat_elem.get("centre"),
                    type=feat_type,
                    desc=desc,
                    value_aliases=dict(self._value_aliases.get(name, {})),
                    axis=feat_elem.get("axis"),
                    offscale=frozenset(offscale),
                    coordinates=coordinates,
                    articulators=articulators,
                    apertures=value_apertures,
                    lip_dofs=lip_dofs,
                    mode=mode,
                    place=feat_elem.get("place"),
                    constriction=feat_elem.get("constriction"),
                    applies=frozenset((feat_elem.get("applies") or "").split()),
                    labels=labels,
                    value_classes={k: frozenset(v) for k, v in classes.items()},
                    sequence=feat_elem.get("sequence") == "+",
                    over=feat_elem.get("over"),
                    vocabulary=vocabulary,
                    moves=moves,
                    bare=frozenset(bare_values),
                )

        # `applies` names a declared manner value, or one of the derived
        # classes below -- each a predicate over declared data, not a list
        # of values restated in Python.
        manner_values = (
            set(self.features["manner"].values) if "manner" in self.features else set()
        )
        for name, feat in self.features.items():
            if feat.centre is not None and feat.centre not in feat.values_set:
                raise ValueError(
                    f"feature {name!r} declares centre={feat.centre!r}, which "
                    "is not one of its declared values"
                )
            for token in feat.applies:
                if (
                    manner_values
                    and token not in DERIVED_CLASSES
                    and token not in manner_values
                ):
                    raise ValueError(
                        f"feature {name!r} declares applies={token!r}, which is "
                        f"neither a declared manner value nor one of "
                        f"{sorted(DERIVED_CLASSES)}"
                    )
            # `over` names the scale this feature's values move along, and
            # a move is only readable if the scale is ordered. Checked at
            # load, because a dangling name would show up as a contour
            # that quietly never derives.
            if feat.over is not None:
                scale = self.features.get(feat.over)
                if scale is None or not scale.is_ordinal:
                    raise ValueError(
                        f"feature {name!r} declares over={feat.over!r}, which is "
                        "not a declared ordinal feature"
                    )
                if undeclared := set(feat.moves) - feat.values_set:
                    raise ValueError(
                        f"feature {name!r} gives a move to {sorted(undeclared)}, "
                        "which it does not declare as values"
                    )

        # Load elements by class (plural section, singular child = section[:-1])
        for section_name in self.classes:
            if (elem := root.find(section_name)) is not None:
                child_name = section_name[:-1]  # phones -> phone
                for child_elem in elem.findall(child_name):
                    self._load_element(child_elem, child_name)

        # Load the provenance block: which symbols are NOT on the IPA chart.
        # A block, and not an attribute on each symbol's own element, for
        # the reason ipa.xml records beside it: an attribute there lands in
        # that symbol's feature bundle, and a key in a bundle is a term in
        # the metric.
        if (notations_elem := root.find("notations")) is not None:
            declared_notations = [
                name
                for n in notations_elem.findall("notation")
                if (name := n.get("name"))
            ]
            self.default_notation = notations_elem.get("default") or ""
            if (
                self.default_notation
                and self.default_notation not in declared_notations
            ):
                raise ValueError(
                    f"default notation {self.default_notation!r} is not "
                    f"declared in <notations>; declared are "
                    f"{declared_notations}"
                )
            for notation in notations_elem.findall("notation"):
                if not (name := notation.get("name")):
                    continue
                for symbol_elem in notation.findall("symbol"):
                    if not (symbol := symbol_elem.get("name")):
                        continue
                    # One symbol comes from one convention. Without this the
                    # last block listing it would win, so the answer would
                    # depend on declaration order and say so nowhere.
                    if (prior := self.notations.get(symbol)) is not None:
                        raise ValueError(
                            f"symbol {symbol!r} is listed under two "
                            f"notations, {prior!r} and {name!r}; a symbol "
                            "belongs to one, or which one is read depends "
                            "on the order the blocks happen to be in"
                        )
                    self.notations[symbol] = name

        # Load the bridge declarations (one dimension, several spellings).
        if (bridges_elem := root.find("bridges")) is not None:
            for bridge in bridges_elem.findall("bridge"):
                if not (bname := bridge.get("name")):
                    continue
                if bname in self.features:
                    raise ValueError(
                        f"bridge {bname!r} collides with a declared feature; a "
                        "bridge is derived for comparison and must not shadow one"
                    )
                spellings: list[tuple[str, str]] = []
                apertures: dict[tuple[str, str], float] = {}
                for spelling in bridge.findall("spelling"):
                    feat_name, value = spelling.get("feature"), spelling.get("value")
                    if not feat_name or value is None:
                        continue
                    feature = self.features.get(feat_name)
                    if feature is None:
                        raise ValueError(
                            f"bridge {bname!r} names undeclared feature {feat_name!r}"
                        )
                    if feature.values and value not in feature.values_set:
                        raise ValueError(
                            f"bridge {bname!r} names value {value!r}, which "
                            f"feature {feat_name!r} does not declare"
                        )
                    spellings.append((feat_name, value))
                    raw_port = spelling.get("port")
                    if raw_port is not None:
                        apertures[(feat_name, value)] = float(raw_port)
                self.bridges[bname] = tuple(spellings)
                if apertures:
                    self.bridge_apertures[bname] = apertures

        # Load the projections (one fact, a fine feature and a coarse one).
        if (projections_elem := root.find("projections")) is not None:
            for projection in projections_elem.findall("projection"):
                fine_name, coarse_name = projection.get("from"), projection.get("to")
                if not fine_name or not coarse_name:
                    continue
                fine = self.features.get(fine_name)
                coarse = self.features.get(coarse_name)
                if fine is None or coarse is None:
                    missing = fine_name if fine is None else coarse_name
                    raise ValueError(
                        f"projection {fine_name!r}->{coarse_name!r} names "
                        f"undeclared feature {missing!r}"
                    )
                if fine_name == coarse_name:
                    raise ValueError(
                        f"projection {fine_name!r}->{coarse_name!r} projects a "
                        "feature onto itself, which says nothing"
                    )
                mapped: set[str] = set()
                for value_elem in projection.findall("value"):
                    fine_value = value_elem.get("name")
                    coarse_value = value_elem.get("reads")
                    if not fine_value or coarse_value is None:
                        continue
                    if fine_value not in fine.values_set:
                        raise ValueError(
                            f"projection {fine_name!r}->{coarse_name!r} names "
                            f"value {fine_value!r}, which feature "
                            f"{fine_name!r} does not declare"
                        )
                    if coarse_value not in coarse.values_set:
                        raise ValueError(
                            f"projection {fine_name!r}->{coarse_name!r} reads "
                            f"{fine_value!r} as {coarse_value!r}, which feature "
                            f"{coarse_name!r} does not declare"
                        )
                    self.projections[(fine_name, fine_value)] = (
                        coarse_name,
                        coarse_value,
                    )
                    mapped.add(fine_value)
                # Total by construction: a projection that covered only some
                # values would leave the rest looking like an independent
                # dimension, so adding a phonation cannot quietly opt out of
                # saying whether it is voiced.
                if unmapped := set(fine.values) - mapped:
                    raise ValueError(
                        f"projection {fine_name!r}->{coarse_name!r} leaves "
                        f"{sorted(unmapped)} unmapped; every value of "
                        f"{fine_name!r} must say how it reads as {coarse_name!r}"
                    )

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
            if not self.tie_bars & set(name):
                continue
            phone = self.phones[name]
            explicit = set(phone.features) - {"class", "href"}
            if explicit:
                continue
            parts = name.replace(self.seq_tie, self.tie_bar).split(self.tie_bar)
            all_vocalic = all(
                self._part_features(part).get("manner") == "vowel" for part in parts
            )
            spelling = name.replace(self.tie_bar, self.seq_tie) if all_vocalic else name
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
        """The ASCII soft-read table, read through the phonemap loader.

        ``lookalikes.xml`` is a phonemap like the four notation tables
        beside it, so the one loader reads it. A second reader of one
        file is a second answer waiting to be given, and here it would
        be given quietly: no caller consults both, so the two can hold
        different ideas of what the file says with nothing to fail.

        The reverse direction is the one a soft read wants -- from the
        keyboard character to the IPA symbol it stands in for. Copied
        rather than aliased, because the loader's tables are cached and
        shared and this one is an attribute callers can reach.
        """
        _, lookalike_to_ipa = _load_phonemap("lookalikes")
        self.lookalikes = dict(lookalike_to_ipa)

    def _load_element(self, elem: ET.Element, element_type: str) -> None:
        """Load a single element into the dict its class routes to.

        Every class ``<classes>`` declares must be routed here. An
        unrouted one used to load into nowhere, silently: ``<zeros>`` was
        declared, parsed by nothing, and read by a second opener of
        ``ipa.xml`` in ``ipakit.form`` -- so the next block added would
        have vanished the same way, with a green suite and no diagnostic.
        A class with no home is now a load-time refusal, because the data
        and the reader disagreeing about what the file contains is not a
        thing to discover from a wrong answer later.
        """
        if not (symbol := elem.get("name")):
            return
        features = {
            k: self._value_aliases.get(k, {}).get(v, v)
            for k, v in elem.attrib.items()
            if k not in ("name", "alias", "desc")
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
        elif element_type == ZERO_CLASS:
            self.zeros[symbol] = phone
        else:
            raise ValueError(
                f"element class {element_type!r} (section "
                f"{element_type + 's'!r}, declaring {symbol!r}) is declared "
                "in <classes> but routed into no table, so everything in it "
                "would load into nowhere. Give it a home in "
                "IPAFeatures._load_element."
            )

        # Aliases become normalization entries (alias → canonical)
        # Supports multiple space-separated aliases
        if aliases := elem.get("alias"):
            for alias in aliases.split():
                self.ligature_map[alias] = symbol

    @property
    def declared_symbols(self) -> dict[str, dict[str, str]]:
        """Every symbol this inventory declares, with what it declared.

        One read over the tables :meth:`_load_element` routes into, so
        "is this symbol taken" has a single answer. The supplement loader
        asks it to refuse a collision and ``scripts/invariants.py`` asks
        it to sweep the inventory; those two used to be one hand-written
        tuple of tables each, which is the shape that drifts.
        """
        return {
            symbol: dict(declared.features or {})
            for table in (self.phones, self.diacritics, self.separators, self.zeros)
            for symbol, declared in table.items()
        }

    def _load_supplement(self, path: Path) -> None:
        """Merge one supplemental inventory file into this instance.

        A supplement **extends the inventory and nothing else**. It may
        declare entries in the element sections ``<classes>`` already
        names -- phones, diacritics, suprasegmentals, separators, zeros --
        and may declare no features, types, classes, modes, bridges or
        projections. That is the line that keeps the feature space fixed:
        a bundle key is a term in the metric, so a file that could add a
        dimension could silently reshape every distance in the inventory
        it was merely meant to extend. Anything else in the file is a
        load-time refusal rather than a block that quietly loads into
        nowhere, which is what ``<zeros>`` did for a release.

        Merge is **additive and order-independent**. A symbol the base
        file, or an earlier supplement, already declares is refused: a
        supplement that could redefine ``t`` would move the shipped
        metric out from under every caller sharing the process, and
        "which file wins" is exactly the question this repository has
        answered wrong before by declaration order.

        A ``<phone>`` that declares **no features takes them from its own
        spelling** -- ``<phone name="t͡ʃʰ"/>`` is registered with the
        bundle ``t͡ʃʰ`` already composes to -- so a registered composed
        segment and the same string read as a composition cannot give two
        answers. It is the rule tied entries already load under, applied
        to the general case. A phone that *does* declare features is a
        sound the base inventory cannot spell, and is taken as written.

        The supplement's own name is recorded in :attr:`supplement_of`,
        never on the entries, because an attribute on a declaring element
        lands in that symbol's feature bundle.
        """
        root = ET.parse(path).getroot()
        if root.tag != SUPPLEMENT_ROOT:
            raise ValueError(
                f"{path} has root <{root.tag}>, not <{SUPPLEMENT_ROOT}>; a "
                "supplement extends an inventory and is not one itself. Pass "
                "a whole inventory as xml_path instead."
            )
        name = root.get("name") or path.stem
        if name in self.supplements:
            raise ValueError(
                f"supplement {name!r} is already loaded from "
                f"{self.supplements[name]}; two supplements under one name "
                "make their entries' provenance depend on load order"
            )
        for section in root:
            if not isinstance(section.tag, str):  # an XML comment
                continue
            if section.tag not in self.classes:
                raise ValueError(
                    f"supplement {name!r} declares a <{section.tag}> block. A "
                    "supplement may declare entries in the element sections "
                    f"{self.xml_path.name} declares -- {', '.join(self.classes)} "
                    "-- and nothing else: a feature, type or bridge declared "
                    "here would add a term to the metric of an inventory it is "
                    "only extending."
                )
            child_name = section.tag[:-1]
            for elem in section:
                if not isinstance(elem.tag, str):  # an XML comment
                    continue
                if elem.tag != child_name:
                    raise ValueError(
                        f"supplement {name!r} puts a <{elem.tag}> inside "
                        f"<{section.tag}>, which holds <{child_name}> "
                        "elements. It would be read by nothing and register "
                        "nothing, in silence."
                    )
                self._load_supplement_element(elem, child_name, name)
        self.supplements[name] = Path(path)

    def _load_supplement_element(
        self, elem: ET.Element, element_type: str, supplement: str
    ) -> None:
        """Register one supplement entry, deriving its bundle if it declares none."""
        if not (symbol := elem.get("name")):
            raise ValueError(
                f"supplement {supplement!r} declares a <{element_type}> with "
                "no name attribute, so it registers nothing"
            )
        if (taken := self.declared_symbols.get(symbol)) is not None:
            where = self.supplement_of.get(symbol, self.xml_path.name)
            raise ValueError(
                f"supplement {supplement!r} redeclares {symbol!r}, which "
                f"{where} already declares as {taken.get('class', '?')!r}. A "
                "supplement adds to an inventory; it does not redefine it."
            )
        # Read the composed bundle *before* registering: once the symbol is
        # in the table, get_features answers from the table and the
        # composition it is meant to agree with is unreachable.
        derived: dict[str, str] | None = None
        if element_type == "phone" and not (
            set(elem.attrib) - {"name", "alias"} - METADATA_ATTRS
        ):
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                composed = self.get_features(symbol, with_defaults=False)
            if not composed or not set(composed) - METADATA_ATTRS:
                raise ValueError(
                    f"supplement {supplement!r} declares {symbol!r} with no "
                    "features, and its spelling composes to nothing this "
                    "inventory can read. Give it features, or spell it out of "
                    "symbols the inventory declares."
                )
            derived = composed
        self._load_element(elem, element_type)
        if derived is not None:
            stated = dict(self.phones[symbol].features)
            self.phones[symbol] = Phone(
                symbol=symbol, features=MappingProxyType({**derived, **stated})
            )
        self.supplement_of[symbol] = supplement
        for alias in (elem.get("alias") or "").split():
            self.supplement_of.setdefault(alias, supplement)

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

        What holds for one shape of base holds for the other. A mark the
        parse cannot place is refused whether the base is atomic or a tie
        composition: ``tˈ``, ``t͡sˈ`` and ``a͜sˈ`` all read ``{}`` and
        warn, because a stress mark scopes the unit that follows it and
        none of these gives it one. ``t͡sˈ`` used to answer with ``t͡s``'s
        bundle and say nothing.

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
            c.base if i == 0 else unit.junctures[i - 1].glyph(self) + c.base
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
        # because a unit emits its marks in its own order (prosody on the
        # side it binds from, combining marks in canonical order), which
        # need not be the order they were written in: what is checked
        # here is that nothing was lost, not that nothing moved.
        # Structural marks are excluded on both sides: the linking
        # undertie is a boundary relation between units and belongs to no
        # Segment by design, so its absence from the emission is not a
        # dropped character.
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
        """Canonicalize a token: Unicode form, then alias -> registered name.

        Delegates to :meth:`expand_ligatures`, which is also what
        :meth:`parse` runs, so a symbol lookup and a segmentation resolve
        aliases by one piece of code. This used to map a token that was an
        alias *entire* and nothing else, so ``ʦ`` resolved but ``ʦʰ`` did
        not -- the flat reads then disagreed with the structured one about
        the same string.
        """
        return self.expand_ligatures(token)

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
        defaults) for a modifier-bearing part.

        The string spelling of :func:`~ipakit.segment.part_bundle`, so a
        part contributes the same bundle to the merge whether it arrived
        as text or as a parsed :class:`~ipakit.segment.Constituent`."""
        part = self._resolve_token(part)
        if part in self.phones:
            return dict(self.phones[part].features)
        return part_bundle(self, self._parse_constituent(part))

    def _is_composable(self, phone: str) -> bool:
        """True if ``phone`` is a tie-barred sequence of resolvable parts.

        Cheap membership predicate: does the splitting and lookups of
        :meth:`_compose_tie_bar_features` without building a feature dict.
        Sequential (under-tie) chains are composable when every
        SEQ-separated part resolves (registered, base+modifiers, or a
        composable over-tie run); pure over-tie runs when every part
        resolves as a phone or base+modifiers.
        """
        if self.seq_tie in phone:
            parts = phone.split(self.seq_tie)
            return len(parts) >= 2 and all(
                p and (self._resolves_part(p) or self._is_composable(p)) for p in parts
            )
        if self.tie_bar not in phone:
            return False
        parts = phone.split(self.tie_bar)
        return len(parts) >= 2 and all(self._resolves_part(p) for p in parts)

    def _compose_tie_bar_features(self, phone: str) -> dict[str, str] | None:
        """Features for an ad hoc tie-barred sequence of resolvable parts.

        Returns ``None`` if ``phone`` has no tie bar or any part isn't
        resolvable. Everything else is
        :func:`~ipakit.segment.flat_projection`, which
        :meth:`~ipakit.segment.Segment.scalar` also calls: this method
        only splits the string into blocks and parts and reads each one's
        bundle, so the flat entry points and the structured ones cannot
        disagree about one unit.
        """
        if not self._is_composable(phone):
            return None
        if self.seq_tie in phone:
            blocks = phone.split(self.seq_tie)
            return flat_projection(
                self,
                [self._block_features(b) for b in blocks],
                [Sense.SEQ] * (len(blocks) - 1),
            )
        return self._fuse_run(phone)

    def _fuse_run(self, run: str) -> dict[str, str]:
        """One over-tie run merged into a single bundle.

        An unbound tie contributes an empty part, and it is dropped
        rather than resolved: ``parse`` already treats a tie that binds
        nothing as no juncture at all, so composing it away here keeps
        this read from raising where ``compose`` and ``scalar`` answer.

        No caller reaches this with an empty part today --
        ``_is_composable`` refuses a part whose tie binds nothing, so
        ``a͜ɪ͡`` now takes the structured route through
        ``_modified_features`` instead. The drop stays because the
        alternative is ``_parse_constituent`` raising out of a read
        documented to return ``{}``, which is a worse answer than an
        ignored glyph whichever route arrives here.
        """
        parts = [p for p in run.split(self.tie_bar) if p]
        if not parts:
            return {}
        return flat_projection(
            self,
            [self._part_features(p) for p in parts],
            [Sense.FUSE] * (len(parts) - 1),
        )

    def _block_features(self, block: str) -> dict[str, str]:
        """Explicit features of one top-level block of a chain: a
        registered entry (or a tie-free base with its marks), else the
        fused merge of the over-tie run.

        The registry only wins for the block *as written*: ``k͡p̪`` is not
        a registered entry, so it merges ``k`` with ``p̪`` rather than
        reading as the registered ``k͡p`` wearing a dental mark. The mark
        binds the base it sits on, which is what the structured parse
        already says.
        """
        if self._resolve_token(block) in self.phones or self.tie_bar not in block:
            return self._part_features(block)
        return self._fuse_run(block)

    def get_phone(self, symbol: str) -> Phone | None:
        return self.phones.get(self._resolve_token(symbol))

    def get_diacritic(self, symbol: str) -> Phone | None:
        return self.diacritics.get(self._resolve_token(symbol))

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
        # A short name, a value (long name), or a friendly alias of one
        # (labial-velar -> bilabial^velar): aliases resolve everywhere a
        # value is accepted, including here. All three are asked together,
        # because they are spelled in one namespace and a reader writing a
        # bare term is not saying which kind it is.
        #
        # Every claimant, not the first one. Scanning in declaration order
        # and taking the first hit made a term that two features claim mean
        # whichever of them ``ipa.xml`` happens to declare earlier, and said
        # nothing about the choice: ``[high]`` is a constraint on vowel
        # HEIGHT, because ``height`` declares ``high`` as an alias of
        # ``close`` and sits above ``tone``, for which ``high`` is a value
        # outright. A tone rule written the obvious way parsed, ran, and
        # answered about height. That is the shape docs/reviewing.md names:
        # not a match against nothing, which the guards below already catch
        # loudly, but a match against something else. Deciding it here
        # rather than by where a feature sits in the file is the point --
        # declaration order is not meaning.
        claims = self._claimants(term)
        if len(claims) == 1:
            return claims[0]
        if len(claims) > 1:
            # Ambiguous, so unresolved: reported by :meth:`_unresolved_term`
            # in the same voice as any other term that named nothing.
            return None
        # Try as a binary feature name (e.g., 'voiced' -> ('voiced', '+' or '-'))
        if term in self.features and self.features[term].type == "binary":
            if prefix == "+":
                return (term, "+")
            elif prefix == "-":
                return (term, "-")
        return None

    def _claimants(self, term: str) -> list[tuple[str, str]]:
        """Every feature that claims ``term``, as ``(feature, value)``.

        A value or a friendly alias of one -- aliases resolve everywhere a
        value is accepted, so ``labial-velar`` is a claim on ``place`` in
        the same way ``bilabial^velar`` is.

        **A borrower does not compete with its lender.** A feature
        declaring ``vocabulary="place"`` states no values of its own; it
        restates ``place``'s as a reading of the same symbol, so
        ``[velar]`` means one thing whichever of the two answers and there
        is nothing to disambiguate. Dropping the borrower where the lender
        is also in the running is what keeps the ordinary place terms
        working while the genuinely contested ones -- ``high``, ``mid``,
        ``nasal``, ``lateral`` -- are refused. Without it this would refuse
        eighteen terms that no one has ever been confused by.

        A short code counts as a claim, and is not privileged for being
        looked up first. ``mid`` is ``height``'s short code for its own
        ``mid`` and is also ``tone``'s value outright; the two are spelled
        the same, so answering from the short table before asking who else
        claims the term just moved the silent choice one line earlier.
        """
        claims: list[tuple[str, str]] = []
        short = self._short_to_feature.get(term)
        if short is not None:
            claims.append(short)
        for feat_name, feat in self.features.items():
            if term in feat.values:
                claim = (feat_name, term)
            elif term in feat.value_aliases:
                claim = (feat_name, feat.value_aliases[term])
            else:
                continue
            if claim not in claims:
                claims.append(claim)
        if len(claims) < 2:
            return claims
        running = {name for name, _ in claims}
        claims = [
            (name, value)
            for name, value in claims
            if (self.features[name].vocabulary or "") not in running
        ]
        if len(claims) < 2:
            return claims
        # Contested, so the data decides rather than the file's order. A
        # value declaring `bare` owns the plain spelling; the others are
        # still reachable as `feature=value`. Exactly one may claim it --
        # two would be the same silent choice wearing a declaration -- and
        # none is a legitimate answer, meaning the term is refused.
        declared = [
            (name, value) for name, value in claims if value in self.features[name].bare
        ]
        if len(declared) > 1:
            raise ValueError(
                f"{term!r} is declared bare by more than one feature: "
                f"{sorted(name for name, _ in declared)}. A bare term "
                f"resolves to one feature, so at most one may claim it"
            )
        return declared or claims

    def _resolve_class_term(self, term: str) -> tuple[str, frozenset[str]] | None:
        """Resolve a declared natural-class name to (feature, its values).

        A ``natural-class`` on a ``<value>`` groups values of one feature
        under a name a phonologist already has -- ``obstruent`` for the
        plosives, fricatives and affricates. The name is not itself a
        value, so it resolves here rather than through
        :meth:`_resolve_query_term`, which answers with a single value.
        """
        for feat_name, feat in self.features.items():
            members = feat.value_classes.get(term)
            if members:
                return (feat_name, members)
        return None

    def _unresolved_term(
        self, spelled: str, term: str, prefix: str, value: str | None = None
    ) -> str:
        """Why one query term named nothing, and what would have worked.

        The value arm of the ``key=value`` guard in :mod:`ipakit.rules`
        names the legal alternatives when a value is misspelled, and a
        bare term gets the same treatment here, because a term that
        resolves to nothing is usually not a misspelling: it is a feature
        name asked for as if it were binary. ``-stress`` is the case in
        point -- ``stress`` declares ``primary`` and ``secondary``, so
        there is no ``-`` to take and the spelling that means what it
        looks like is per-value negation.

        ``value`` is the dict arm's case, where the feature name resolved
        and what was asked of it did not. It is the same diagnostic and
        not a second one, so a query dict and a query list answer a
        misspelling in one voice.
        """
        if value is not None:
            feature = self.features.get(term)
            if feature is not None:
                hint = (
                    f". {value!r} is a declared natural class over those "
                    f"values, and a class is not a value: ask for it as the "
                    f"bare term {value!r}"
                    if value in feature.value_classes
                    else ""
                )
                return (
                    f"{spelled!r} resolves to no feature term; {value!r} is "
                    f"not a value of feature {term!r}, whose declared values "
                    f"are {sorted(feature.values_set)}{hint}"
                )
        # Ambiguity before the misspelling diagnostics: a contested term is
        # not a term that named nothing, and telling its writer it "is not a
        # declared value" would be false as well as useless.
        claims = self._claimants(term)
        if len(claims) > 1:
            spellings = ", ".join(f"{name}={value}" for name, value in sorted(claims))
            return (
                f"{spelled!r} is ambiguous; {term!r} is claimed by "
                f"{sorted({name for name, _ in claims})}, and none of them "
                f"declares it bare, so nothing says which one a plain term "
                f"means. Name the feature: {spellings}"
            )
        klass = self._resolve_class_term(term)
        if klass is not None:
            return (
                f"{spelled!r} resolves to no feature term; {term!r} is a "
                f"declared natural class of feature {klass[0]!r}, which is "
                f"selected or excluded whole: write {term!r} or '-{term}'"
            )
        feature = self.features.get(term)
        if feature is None:
            return (
                f"{spelled!r} resolves to no feature term; {term!r} is not a "
                "declared feature, a declared value, a declared natural "
                "class, or a short name"
            )
        values = sorted(feature.values_set)
        if feature.type == "binary":
            return (
                f"{spelled!r} resolves to no feature term; feature {term!r} "
                f"is binary, so name a side of it: '+{term}' or '-{term}'"
            )
        if prefix == "-":
            negated = " ".join(f"-{value}" for value in values)
            return (
                f"{spelled!r} resolves to no feature term; feature {term!r} "
                f"is not binary, so there is no '-' value to take. Its "
                f"declared values are {values}; negate them individually "
                f"instead, as {negated!r}"
            )
        return (
            f"{spelled!r} resolves to no feature term; feature {term!r} takes "
            f"a value, so ask for one: {term}=<value>, with declared values "
            f"{values}"
        )

    def _require_value(
        self, positive: dict[str, str], feature: str, value: str
    ) -> str | None:
        """Record ``feature=value``; report a value already required for it.

        The one place a positive constraint is written, because there are
        three ways to reach one -- a short name, a ``+``/``-``/``0``
        prefix on a feature name, and a term resolving to a value or a
        value alias -- and a plain assignment at each of them let the last
        writer win. ``['alveolar', 'velar']`` answered the velars and
        ``['velar', 'alveolar']`` answered the alveolars: one query, two
        answers, chosen by the order the terms were written, and by
        nothing at all when the query is a ``set``.

        A query is a **conjunction** wherever else this library reads one
        -- that is what a rule's bracket means and what
        :meth:`phones_matching` documents -- so two values for one feature
        state something no phone can satisfy. Reporting it is the answer
        rather than matching nothing, because an impossible query is far
        more likely a mistake than an intent, and because a term that
        resolves and is then discarded is the same silent widening this
        resolver already refuses one arity up.

        The message names the feature and its two values, sorted, and not
        the term that happened to arrive second: the whole complaint about
        the old behavior was that it depended on arrival order, and a
        ``set`` has none to depend on.
        """
        held = positive.get(feature)
        if held is not None and held != value:
            both = " and ".join(repr(v) for v in sorted((held, value)))
            return (
                f"the query constrains feature {feature!r} to {both}; a "
                f"feature holds one value at a time and a query is a "
                f"conjunction, so nothing can satisfy this. Ask for the "
                f"values in separate queries, or name a declared natural "
                f"class over them"
            )
        positive[feature] = value
        return None

    def _admit_values(
        self,
        inclusive: dict[str, set[str]],
        feature: str,
        term: str,
        members: frozenset[str],
    ) -> str | None:
        """Record a natural class; report two classes that cannot both hold.

        The counterpart of :meth:`_require_value` for the class arm, and
        it exists for the same reason: a bracket is a conjunction, so two
        classes over one feature mean the values in both, and where they
        share none the query states something no unit can satisfy.
        Reported rather than answered with silence, on the resolver's
        standing policy that an impossible query is a mistake far more
        often than an intent.
        """
        held = inclusive.get(feature)
        admitted = set(members) if held is None else held & set(members)
        if not admitted:
            return (
                f"the query asks for the class {term!r} alongside a class "
                f"over feature {feature!r} that shares no value with it; a "
                f"feature holds one value at a time and a query is a "
                f"conjunction, so nothing can satisfy this"
            )
        inclusive[feature] = admitted
        return None

    def _split_by_mode(
        self, terms: Mapping[str, _T]
    ) -> tuple[dict[str, _T], dict[str, _T]]:
        """Partition resolved query terms into (segmental, prosodic).

        Prosody is a second namespace, not a second phone: ``features("a")
        == features("ˈa") == features("aː")``, so a term naming ``stress``
        or ``length`` has nothing to ask of a feature bag and must be put
        to the unit's prosody instead. Which features those are is read
        off :attr:`features_by_mode`, so no list of prosodic feature names
        appears here.

        There is no third bucket, and that is why a term naming a
        ``structural`` feature is refused before it gets here: a
        structural feature belongs to a boundary or a juncture, not to a
        unit, so neither of these two bags could ever answer one.
        """
        prosodic = self.features_by_mode.get("prosodic", frozenset())
        return (
            {k: v for k, v in terms.items() if k not in prosodic},
            {k: v for k, v in terms.items() if k in prosodic},
        )

    def _query_constraints(self, query: _Query) -> tuple[_Terms, _Terms]:
        """Resolve a query and split it into (segmental, prosodic) halves.

        One resolution and one split, so :meth:`phones_matching`,
        :meth:`find` and :class:`ipakit.rules.Pattern` cannot come to
        different conclusions about which namespace a term belongs to.
        The three of them used to reach that answer three ways --
        ``phones_matching`` did not split at all, which is why
        ``['-normal']`` answered one phone there and every unit in a rule.
        """
        required, included, excluded = self._resolve_query(query)
        seg_required, pro_required = self._split_by_mode(required)
        seg_included, pro_included = self._split_by_mode(included)
        seg_excluded, pro_excluded = self._split_by_mode(excluded)
        return (
            (seg_required, seg_included, seg_excluded),
            (pro_required, pro_included, pro_excluded),
        )

    def _prosody_asked(
        self, feats: Mapping[str, str], prosody: Mapping[str, str]
    ) -> Mapping[str, str]:
        """A unit's prosody as a query sees it: asserted, plus the defaults.

        :attr:`Segment.prosody` and :attr:`ipakit.form.Unit.prosody` are
        what the *marks* say, and a mark for ``length="normal"`` does not
        exist -- no shipped diacritic spells it, because it is what a unit
        has when nothing is written on it. That is exactly what
        ``default="normal"`` declares, and reading the assertion without
        the declaration made the two halves of one feature answer
        differently: ``[length=normal]`` found no site anywhere, while
        ``[-normal]`` matched every unit there is.

        So a query reads prosody the way it reads a feature bag: with the
        declared defaults filled in under ``with_defaults``, and without
        them under ``with_defaults=False``, where absence is again the
        answer. The defaults are read off :attr:`features_by_mode` and the
        declarations, so a prosodic feature declared later is filled here
        without an edit.

        Skipped for a non-speech bundle, on the same grounds
        :func:`~ipakit.segment.fill_defaults` skips it: silence takes no
        articulatory default and takes no prosodic one either.
        """
        if not takes_defaults(self, feats):
            return prosody
        filled = dict(prosody)
        for name in self.features_by_mode.get("prosodic", frozenset()):
            default = self.features[name].default
            if default is not None and name not in filled:
                filled[name] = default
        return filled

    def _satisfies(
        self,
        feats: Mapping[str, str],
        prosody: Mapping[str, str],
        segmental: _Terms,
        prosodic: _Terms,
        with_defaults: bool = True,
    ) -> bool:
        """The one place a unit is judged against a resolved query.

        Every caller of the query language ends here --
        :meth:`phones_matching` over the registered inventory,
        :meth:`find` over a transcription, :meth:`ipakit.rules.Pattern.
        matches` over a rule's site -- so "does this term hold of this
        unit" has one answer rather than one per entry point.
        """
        if with_defaults:
            prosody = self._prosody_asked(feats, prosody)
        return self._query_matches(feats, *segmental) and self._query_matches(
            prosody, *prosodic
        )

    def _structural_terms(self, *constrained: Mapping[str, object]) -> list[str]:
        """Complaints for any resolved term naming a ``structural`` feature.

        A structural feature is a property of a **boundary or a juncture**
        -- ``level``, ``break``, ``linking``, ``tie`` -- and ``ipa.xml``
        says so in the mode itself: "a level belongs to no segment's
        feature bag". A unit has a feature bag and a prosody, and neither
        of them can hold one, so ``[-word]`` and ``[-simultaneous]`` were
        not narrow terms that happened to find nothing: they were terms
        matched against a bag that could never carry the key, satisfied by
        its absence, and so true of every segment there is.

        Refused rather than answered, for the reason the empty query is
        refused one arity up: a term that cannot constrain anything is a
        query silently widened, and the widening is what makes it a wrong
        answer instead of a narrow one. Which features these are is read
        off :attr:`features_by_mode`, so a structural feature declared
        later is refused without an edit here.
        """
        structural = self.features_by_mode.get("structural", frozenset())
        named = sorted({k for terms in constrained for k in terms} & structural)
        # The glyphs that carry a structural feature, read off the same
        # declarations that carry it, so the advice names what this
        # inventory actually spells rather than a list written here.
        marks = " ".join(sorted(set(self.separators) | set(boundary_marks(self))))
        return [
            f"feature {name!r} is structural: it is a property of a "
            f"boundary or a juncture, not of a segment, so no unit's "
            f"features or prosody can answer a term over it. Name the "
            f"mark itself instead ({marks}), or the boundary notation."
            for name in named
        ]

    def _resolve_query(
        self, query: _Query
    ) -> tuple[dict[str, str], dict[str, set[str]], dict[str, set[str]]]:
        """Resolve a query into (required, included, excluded) constraints.

        The query language is documented on :meth:`phones_matching`;
        resolution is factored out here so :meth:`find` runs that same
        language over a transcription instead of growing a second one.

        The three constraints are three different questions, and keeping
        them apart is what stops a term going vacuous:

        ``required``
            one value, from ``place=velar`` or a bare value term.
        ``included``
            the values a **declared natural class** admits, from
            ``[obstruent]``. Carried this way round rather than as the
            exclusion of every value outside the class, which is what it
            used to be: an exclusion is satisfied by a bundle that does
            not carry the feature at all, so a class declared over a
            feature some bundle omits would have matched that bundle
            instead of skipping it. No class is declared over such a
            feature today; this makes the day one is declared uneventful.
        ``excluded``
            the values an explicit ``-`` term forbids, from ``[-fricative]``
            or ``[-obstruent]``.

        The two negative-looking forms differ deliberately, and
        :meth:`_query_matches` states the difference.

        **Every** term must resolve, whatever else is in the query.
        Dropping a term that names nothing while keeping the ones that do
        is a narrower query silently widened -- ``['vowel', '-stress']``
        meaning ``['vowel']``, matching the stressed vowels the term was
        written to exclude -- which is a wrong answer rather than a
        vacuous one, so it raises at every arity rather than only when
        nothing at all resolves.

        That rule is stated of the *query*, so both arms keep it. The dict
        arm used to keep neither half of it: ``{'not-a-feature': '+'}`` and
        ``{'place': 'nonsense'}`` both resolved to themselves and matched
        nothing, turning a misspelling into a plausible empty result --
        which is the wrong answer the paragraph above exists to refuse,
        reached by writing the query the other way round.

        **Which arm a query takes is decided by shape**, and the answer for
        anything that is neither is a :class:`ValueError` like every other
        refusal here. It used to be decided by ``isinstance(query, (list,
        set))``, with the mapping arm as the fallback, so every other type
        reached ``.items()`` and raised ``AttributeError`` -- out of
        ``phones_matching`` and ``find``, which is a public method telling a
        caller nothing and raising something they cannot catch beside
        :class:`ipakit.rules.RuleError`. That reached a tuple of terms and a
        frozenset of them, which are queries this should simply answer, as
        well as ``'[+voiced]'``, ``42`` and ``None``, which it should
        refuse.

        A **string is refused rather than iterated**, and that is the whole
        reason the test is not "iterable, else mapping": a string is a
        collection of its characters, so ``'+voiced'`` would resolve as the
        seven terms ``'+'``, ``'v'``, ``'o'`` ... -- a wrong answer dressed
        as a query, which is worse than the crash it replaces. Bracket text
        is the *rule* language's spelling of a query and
        :func:`ipakit.rules._pattern` parses it; accepting it here would be
        a second reading of that notation, kept in step by habit.
        """
        positive: dict[str, str] = {}
        inclusive: dict[str, set[str]] = {}  # feature -> values admitted
        negative: dict[str, set[str]] = {}  # feature -> values to exclude
        unresolved: list[str] = []

        if isinstance(query, (str, bytes)) or not isinstance(
            query, (Mapping, Iterable)
        ):
            raise ValueError(
                f"a query is a mapping of feature to value or a collection "
                f"of terms, not {type(query).__name__}: {query!r}. Name the "
                f"terms in a list -- ['+voiced', 'plosive'] -- or the "
                f"features in a dict; the bracket spelling '[+voiced]' is "
                f"the rule language's and is read by ipakit.rules."
            )

        if not isinstance(query, Mapping):
            # Read once, so a query written as an iterator is not consumed
            # here and then found empty by the check at the end.
            for s in list(query):
                # Whole string is a short name (e.g. '-voi', '+voi', '0trt').
                # Not where another feature claims the same spelling: `mid`
                # is `height`'s short code for its own `mid` and `tone`'s
                # value outright, and answering from this table first only
                # moved the silent choice one branch earlier. A contested
                # term falls through to the resolver, which refuses it.
                if s in self._short_to_feature and len(self._claimants(s)) < 2:
                    feat, val = self._short_to_feature[s]
                    if clash := self._require_value(positive, feat, val):
                        unresolved.append(clash)
                    continue
                # Optional +/-/0 prefix selects a feature value directly.
                prefix = s[0] if s[:1] in ("+", "-", "0") else ""
                term = s[1:] if prefix else s
                if (
                    prefix
                    and term in self.features
                    and prefix in self.features[term].values
                ):
                    if clash := self._require_value(positive, term, prefix):
                        unresolved.append(clash)
                    continue
                # A declared natural class names several values of one
                # feature, and a bracket is a conjunction, so the positive
                # form ADMITS its members and the negated form excludes
                # them: '[obstruent -fricative]' admits the three
                # obstruent manners and then takes the fricatives back
                # out. Both arms are derived from the declaration, so a
                # manner added to the data joins the class or stays
                # outside it by what the data says.
                #
                # The positive arm used to be spelled as the exclusion of
                # every value OUTSIDE the class, which agrees with this
                # wherever the feature is present and disagrees where it
                # is absent -- an exclusion holds vacuously there, so the
                # class would have matched a bundle that has no such
                # feature at all.
                klass = self._resolve_class_term(term)
                if klass is not None and prefix in ("", "+", "-"):
                    feat, members = klass
                    if prefix == "-":
                        negative.setdefault(feat, set()).update(members)
                    elif clash := self._admit_values(inclusive, feat, term, members):
                        unresolved.append(clash)
                    continue
                resolved = self._resolve_query_term(term, prefix=prefix)
                if not resolved:
                    unresolved.append(self._unresolved_term(s, term, prefix))
                    continue
                feat, val = resolved
                if prefix == "-":
                    negative.setdefault(feat, set()).add(val)
                elif clash := self._require_value(positive, feat, val):
                    unresolved.append(clash)
        else:
            # A dict names features directly, but its key and its value are
            # held to the same standard the list arm holds a bare term to:
            # both must be declared. Values go through the alias table --
            # labial-velar is the readable spelling of bilabial^velar and
            # must match it -- and a value may be a sequence of steps or a
            # generative overlap, each part of which is checked in its own
            # right, exactly as `respell` checks a change.
            for key, val in query.items():
                spelled = f"{key}={val}"
                feature = self.features.get(key)
                if feature is None:
                    unresolved.append(self._unresolved_term(spelled, key, ""))
                    continue
                value = feature.value_aliases.get(val, val)
                if not all(
                    part in feature.values_set
                    for step in feature.steps(value)
                    for part in feature.expand(step)
                ):
                    unresolved.append(
                        self._unresolved_term(spelled, key, "", value=val)
                    )
                    continue
                if clash := self._require_value(positive, key, value):
                    unresolved.append(clash)

        unresolved.extend(self._structural_terms(positive, inclusive, negative))
        if unresolved:
            raise ValueError("; ".join(unresolved))
        if not positive and not inclusive and not negative:
            raise ValueError(
                f"no feature terms resolved from {query!r}; an unresolved "
                "query would match the entire inventory"
            )
        return positive, inclusive, negative

    @staticmethod
    def _query_matches(
        feats: Mapping[str, str],
        required: dict[str, str],
        included: dict[str, set[str]],
        excluded: dict[str, set[str]],
    ) -> bool:
        """True if a feature bundle satisfies resolved query constraints.

        The bundle is read and never written, so it is typed by what is
        asked of it: a unit's features and prosody are read-only.

        **What an absent feature answers**, which is the whole of the
        difference between the three arms:

        ``required`` and ``included`` are claims *about* a feature, so a
        bundle that does not carry the feature does not satisfy them. A
        vowel declares no ``place``, so ``place=velar`` skips it and so
        does ``[obstruent]``, which is a claim about its manner.

        ``excluded`` is satisfied by absence, and that is a **deliberate
        three-valued reading**: ``stress`` declares ``primary`` and
        ``secondary`` and no default, so a unit carrying no stress is
        unstressed, and ``[-primary -secondary]`` -- which is how the
        shipped American English rule set says "unstressed" -- has to hold
        of it.

        That reading is only safe because absence is confined to the
        features whose declaration allows it. A feature declaring a
        ``default`` is filled in every bundle a query is asked of, the
        feature bag through :func:`~ipakit.segment.fill_defaults` and
        prosody through :meth:`_prosody_asked`, so no term over it is ever
        decided by absence. That is what ``[-normal]`` turned on: ``length``
        declares ``default="normal"``, the default was filled into the
        feature bag where the term is not asked, and left out of the
        prosody where it is -- so ``[-normal]`` matched every unit and
        ``[length=normal]`` matched none.
        """
        return (
            all(feats.get(k) == v for k, v in required.items())
            and all(feats.get(k) in vals for k, vals in included.items())
            and all(feats.get(k) not in vals for k, vals in excluded.items())
        )

    def phones_matching(self, query: _Query, with_defaults: bool = True) -> list[str]:
        """Get all phones matching features.

        Accepts a dict of feature to value, or any collection of short or
        long names that is not a string -- a string is refused rather than
        read as its characters. Names can be prefixed with + (has value)
        or - (does not have value). E.g., ['+aspirated', '-voiced'] or
        ['+asp', '-voi']. Anything else raises ``ValueError``, as every
        other refusal in the query language does, so one handler catches a
        malformed query here and a malformed one in a rule.

        Searches the registered inventory; :meth:`find` runs the same query
        over the units of a transcription.

        A registered phone is a unit that has been written down with
        nothing on it, so it is judged as one, through the same
        :meth:`_satisfies` that answers for a transcription and for a
        rule's site. It carries no prosodic mark, which is not the same as
        carrying no prosody: what an unmarked unit has is what the
        declaration says it has by default. Asked instead of the feature
        bag alone -- which is what this did -- a prosodic term was put to a
        bag that has prosody taken out of it, and ``['-normal']`` answered
        one phone here while the same term matched every unit in a rule.
        """
        segmental, prosodic = self._query_constraints(query)
        return [
            symbol
            for symbol in self.phones
            if self._satisfies(
                self.get_features(symbol, with_defaults=with_defaults),
                {},
                segmental,
                prosodic,
                with_defaults=with_defaults,
            )
        ]

    def find(
        self,
        ipa: str,
        query: _Query,
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

        A term naming a **prosodic** feature is put to the unit's prosody
        rather than to that projection, because the projection has prosody
        taken out of it by design: ``features("a") == features("ˈa")``.
        Matched against the bag, ``['primary']`` found nothing and
        ``['-primary', '-secondary']`` -- the spelling ``_unresolved_term``
        recommends, and the shipped American English rule set writes --
        answered "carries no stress" about a unit carrying primary stress.
        The split is by declared mode and is the same one
        :class:`ipakit.rules.Pattern` makes, so a query asked here and the
        same query asked in a rule cannot come to different conclusions
        about the same unit.

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
        segmental, prosodic = self._query_constraints(query)
        return [
            (i, unit)
            for i, unit in enumerate(self.read(ipa).segments)
            if self._satisfies(
                unit.scalar(with_defaults=with_defaults),
                _prosodic_features(unit, self),
                segmental,
                prosodic,
                with_defaults=with_defaults,
            )
        ]

    def to_phone(self, bundle: dict[str, str]) -> str | None:
        """The registered symbol a feature bundle names.

        A **canonicalizer over a lossy projection**, and not an inverse of
        :meth:`get_features`, which it claimed to be and is not. The claim
        holds where the projection does not lose anything -- ``t`` reads
        out and comes back ``t`` -- and fails wherever it does: the flat
        read of an under-tie chain is its first constituent (docs/ties.md),
        so ``to_phone(get_features("a͜ɪ"))`` is ``"a"``. Nothing here is
        wrong; there is simply nothing in a flat bundle that says a
        diphthong was ever there. The phonetic keys of ``a͜ɪ`` and ``a``
        are identical, and the one key that differs, ``href``, is a
        documentation link rather than a fact about the sound and must not
        be what picks a spelling.

        What holds instead is idempotence on the answer:
        ``to_phone(get_features(to_phone(b)))`` is ``to_phone(b)``.

        A candidate matches when it agrees on every key the caller wrote;
        keys the caller omitted are free. Candidates are read with their
        defaults filled, so ``{"manner": "plosive", "place": "alveolar"}``
        realizes as "t" -- the phone that takes the defaults -- not "d".
        Metadata keys (``class``, ``href``) are ignored, so a bundle
        straight out of :meth:`get_features` round-trips.

        Several phones can satisfy one bundle; the winner is decided, in
        order, by:

        1. **the base inventory before a supplement** -- an entry from a
           supplemental file answers only where the file this instance
           was built on could not. Without that key a supplement could
           outrank an existing winner, which is measurable and silent:
           registering an atomic ``č`` for ``t͡ʃ`` beats it on constituent
           count, so 25 bundles that answered ``t͡ʃ`` would answer ``č``
           merely because a second file was loaded. With it, adding a
           supplement can only turn a ``None`` into an answer;
        2. **fewest extra features** -- the explicit (non-default)
           features a candidate declares beyond the ones asked for, so
           the most general phone answering the request wins;
        3. **fewest constituents** -- a tied compound's flat bundle is
           only the projection of one constituent (docs/ties.md), so it
           never outranks an atom matching equally well: "a", not "a͜ɪ";
        4. **declaration order** in the data.

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
        best: tuple[int, int, int, int] | None = None
        winner: str | None = None
        for order, symbol in enumerate(self.phones):
            feats = self.get_features(symbol)
            if any(feats.get(k) != v for k, v in query.items()):
                continue
            supplemented = 1 if symbol in self.supplement_of else 0
            extras = sum(
                1
                for k in self.phones[symbol].features
                if k not in METADATA_ATTRS and k not in query
            )
            junctures = symbol.count(self.tie_bar) + symbol.count(self.seq_tie)
            rank = (supplemented, extras, junctures, order)
            if best is None or rank < best:
                best, winner = rank, symbol
        return winner

    def _respell_flat(self, symbol: str, changes: Mapping[str, str]) -> str | None:
        """One symbol's flat bundle with ``changes`` laid on it, realized.

        The core of :meth:`respell`, factored out because a tied unit
        applies it once per constituent and an atomic one once. ``changes``
        arrives already resolved and already checked against the
        declaration.

        **A borrowed reading is spent, not carried.** A feature declaring
        ``vocabulary`` states no values of its own: it restates another
        feature's vocabulary as a reading of *this symbol*, sourced for
        this symbol. ``constriction-location`` is one, and where a
        published measurement puts ``u``'s tongue-body constriction is a
        fact about ``u`` rather than about every bundle reachable from
        it. Laid onto a changed bundle it either asserts that fact of a
        different vowel or -- since :meth:`to_phone` requires every
        stated key to agree -- answers ``None`` for a phone that exists.
        ``respell("u", rounded="-")`` is ``ɯ``, which is in no source's
        family and declares no location, and carrying ``u``'s location
        into the query loses it. Dropping the reading can only widen the
        search, and no two registered phones agree on everything else and
        differ here, so it cannot change an answer that existed. A change
        that *names* the borrowing writes it, like any other.
        """
        feats = self.get_features(symbol)
        if not feats:
            return None
        feats.update(changes)
        for meta in METADATA_ATTRS:
            feats.pop(meta, None)
        for name, feature in self.features.items():
            if feature.vocabulary is not None and name not in changes:
                feats.pop(name, None)
        return self.to_phone(feats)

    def respell(self, phone: str, **changes: str) -> str | None:
        """Apply a feature change to ``phone`` and realize the result.

        ``respell("t", voiced="+")`` is "d"; ``respell("p",
        place="velar")`` is "k". The delta lands on the phone's
        default-filled features and goes through :meth:`to_phone`, whose
        matching and tie rules therefore govern the answer. This is what
        makes a feature-changing rule expressible at all.

        A feature whose name carries a hyphen is also reachable with an
        underscore (``tongue_root``), since a hyphen cannot be a keyword.

        **Prosody is carried, never spent.** The bundle this reads has
        prosody taken out of it by design -- ``features("t") ==
        features("tː")`` -- so respelling from the bundle alone answered
        ``respell("tː", voiced="+")`` with ``"d"``, dropping a length
        nobody asked about. The unit's prosody is put back on the answer,
        so a change asked of one feature moves one feature.

        A change *naming* a prosodic feature is refused rather than
        answered. It has nowhere to land here: the key would sit in a
        segmental bundle that prosody is defined to be outside of, and
        ``respell("a", length="long")`` was stopped only by
        :meth:`to_phone` happening to match nothing, which is luck and not
        a contract. :func:`ipakit.form.with_prosody` is what writes
        prosody.

        A **tied** unit takes the change on each of its constituents.
        The flat read of an under-tie chain *is* its first constituent
        (docs/ties.md), so realizing that bundle could only ever answer an
        atom: ``respell("a͜ɪ", voiced="+")`` was ``"a"``, silently
        replacing a diphthong with its first half in the name of a change
        that moved nothing. Over-tie compounds keep the flat path, because
        their flat read is a genuine fusion of both constituents rather
        than a projection of one, and ``t͡s`` voiced really is ``d͡z``.

        Returns ``None`` when the changed bundle names no registered
        phone; for a tied unit, when any constituent does not. Raises
        ``ValueError`` if ``phone`` does not resolve, or if a change names
        a feature or a value the data does not declare: a misspelled
        feature has to fail loudly rather than quietly leave the phone as
        it was.
        """
        if not self.get_features(phone):
            raise ValueError(f"cannot resolve phone {phone!r}")
        wanted: dict[str, str] = {}
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
            wanted[key] = resolved
        _segmental, prosodic = self._split_by_mode(wanted)
        if prosodic:
            raise ValueError(
                f"respell cannot write {sorted(prosodic)}: a prosodic feature "
                "is a property of the unit and not of the phone, so it is "
                "absent from the bundle this respells from and there is "
                "nothing here for the change to move. Write it with "
                "ipakit.form.with_prosody, which rewrites Segment.prosody"
            )

        try:
            unit = self.segment(phone, strict=True)
        except (ValueError, KeyError):
            # Readable as a bundle and not parseable as a unit: answer the
            # bundle, which is the whole of what such a string offers.
            return self._respell_flat(phone, wanted)

        tied = Sense.SEQ in unit.junctures
        parts = [str(c) for c in unit.constituents] if tied else [phone]
        spelled: list[str] = []
        for part in parts:
            got = self._respell_flat(part, wanted)
            if got is None:
                return None
            spelled.append(got)
        try:
            if tied:
                rebuilt = tuple(self._parse_constituent(s) for s in spelled)
                return dataclasses.replace(unit, constituents=rebuilt).to_ipa()
            if not unit.prosody:
                return spelled[0]
            # The answer is a whole unit, so the prosody goes back onto it
            # rather than onto one of its constituents: `t͡sː` voiced is
            # `d͡zː`, and `d͡z` is what the bundle realized.
            answer = self.segment(spelled[0], strict=True)
            return dataclasses.replace(answer, prosody=unit.prosody).to_ipa()
        except (ValueError, KeyError):  # pragma: no cover - to_phone answers
            return None  # registered symbols, which reparse

    def notation_of(self, symbol: str) -> str:
        """Which notation ``symbol`` belongs to; unlisted is the default.

        The declared read over :attr:`notations`, in the shape of
        :meth:`declaring_mark`: the block says which symbols are *not* on
        the IPA chart, and everything else -- including a character this
        inventory registers nowhere -- answers :attr:`default_notation`.

        Unknown is deliberately not a third answer. "Not on the chart" and
        "not in this inventory" are different questions and
        :meth:`validate_ipa` is what answers the second; a symbol that is
        registered nowhere is not an *extension*, it is a typo.
        """
        return self.notations.get(symbol, self.default_notation)

    def declaring_mark(
        self, key: str, value: str, wanted: dict[str, str] | None = None
    ) -> tuple[int, str] | None:
        """The mark that declares ``key=value``, with its declaration rank.

        The one read of "which glyph says this", so the segmental composer
        and the prosody writer cannot disagree about it.
        :meth:`compose_unit` writes marks into a phone's spelling and
        :func:`ipakit.form.with_prosody` writes them into a unit's
        prosody; both need the same answer, and a second copy of this
        loop is exactly the kind of duplication that drifted three times
        already in this repo.

        Which mark carries a value is *asked of the declaration* -- no
        feature-to-glyph table appears anywhere. Where several declare the
        same value the most specific wins: fewest declared features, so
        the mark that says only what was asked beats one that drags a
        second dimension along; then fewest surplus values the data gives
        a **label**; then declaration order to break the remaining tie.

        That middle key exists because a projection is many to one. Three
        marks declare ``voiced="+"`` -- the modal, breathy and creaky
        rings -- and all three survive the screen below, since the
        projection says each of those phonations reads ``voiced="+"``.
        They are not interchangeable, which ``ipa.xml`` says where it
        declares the projection, so answering "voice this segment" with
        the breathy ring is a wrong answer wearing a coherent one's
        clothes: ``compose_unit("s", voiced="+")`` would be ``s̤``. A
        ``label`` is the data's own statement that a value is worth
        saying out loud -- ``breathy`` and ``creaky`` declare one,
        ``modal`` and ``devoiced`` do not, exactly as ``channel=flat``
        does not -- so a surplus that carries one is a fact the caller
        did not ask for, and a surplus without one adds nothing sayable.
        Measured over every declared ``(feature, value)``: seven have
        several equally specific marks, and this key changes the answer
        for exactly one of them, ``voiced="+"``. The other six are pairs
        of marks with identical declarations, where declaration order was
        already the whole of the choice.

        A mark declaring MORE than was asked is not rejected outright:
        refusing every surplus was tried and is wrong, because the
        devoicing ring declares both ``phonation`` and ``voiced``, so it
        would also refuse ``ɹ̥`` -- exactly the composition an allophonic
        rule wants. Pass ``wanted``, the whole request, to screen the
        surplus instead: a mark survives where its extras are the same
        fact restated per the declared ``<projections>``, and is refused
        where a genuine second dimension moves. The linguolabial mark is
        that counterexample -- it declares the requested
        ``place="bilabial"`` and, independently,
        ``articulator="tongue-tip"``.

        Without ``wanted`` nothing is screened, which is what the prosody
        writer needs: it writes marks into a unit's prosody rather than
        into a phone's spelling, so a segmental surplus cannot arise.

        The rank comes back with the symbol because a caller emitting
        several marks orders them by mode and then by declaration, and
        recovering the rank from the symbol would be a second read of the
        same list.

        Returns ``None`` when nothing declares the value -- which is not
        always a failure. Nothing declares ``length=normal``, because a
        bare vowel already says it; a writer reads that as "spell it with
        no mark at all".
        """
        asked = set(wanted) if wanted is not None else {key}
        # Which placement the request is about, so a mark is judged on what
        # it says *there*. The four phase marks declare one key at each end
        # of the segment, and counting both would make each of them look
        # twice as unspecific as it is: asked for an aspirated release,
        # `ʰ` would lose to `ʻ`, which says the same thing and is the
        # spelling nobody writes.
        approach = key in self.features_by_mode.get(APPROACH_MODE, frozenset())
        candidates: list[tuple[int, int, int, str]] = []
        for order, symbol in enumerate(self.diacritics):
            here = phase_keys(self, symbol, approach)
            declared = self.diacritics[symbol]
            bundle = {
                k: v
                for k, v in (getattr(declared, "features", None) or {}).items()
                if k in here
            }
            if bundle.get(key) != value:
                continue
            if wanted is not None and not self._coheres(bundle, wanted):
                continue
            extras = sum(1 for k in bundle if k not in METADATA_ATTRS)
            # Of the surplus, how much the data says out loud. See the
            # docstring: a labeled surplus is a second fact, not a
            # restatement of the one requested.
            sayable = sum(
                1
                for k, v in bundle.items()
                if k not in METADATA_ATTRS
                and k not in asked
                and (feature := self.features.get(k)) is not None
                and feature.labels.get(v) is not None
            )
            candidates.append((extras, sayable, order, symbol))
        if not candidates:
            return None
        _, _, order, symbol = min(candidates)
        return order, symbol

    def _mark_rank(self, symbol: str, approach: bool = False) -> tuple[int, int, int]:
        """Where one mark sits in a stack: how it binds, then its mode,
        then its declaration.

        The single ordering over marks, so a mark already spelled on a
        base and a mark :meth:`compose_unit` picks this call are placed by
        one rule. ``<modes>`` declares its modes in precedence order and
        :func:`~ipakit.segment.modifier_mode` reads a mark's mode off the
        keys the mark itself declares, so nothing here knows which glyph
        is a release phase and which is a secondary articulation.
        Declaration order breaks the remaining tie, which is what
        :meth:`declaring_mark` already returns beside its answer, so two
        marks of one mode stack in the order the data lists them.

        Binding comes first because it is not this library's decision. A
        combining mark attaches to the character *before* it, so one
        written after a spacing modifier letter is a mark on that letter
        and not on the phone: ``dʰ̥`` rings the ``ʰ``. Every combining
        mark therefore precedes every spacing one, and the modes order
        within each -- which is the answer the ``<modes>`` block was
        always reaching for, since a mark that lands on the wrong
        character has no mode on this segment at all.

        Unicode has the last word among the combining marks themselves:
        canonical ordering sorts them by combining class whatever is
        decided here, which is why the spelling is normalized once before
        it is checked.

        ``approach=True`` ranks the stack written before the base, where a
        mark's mode is the one it makes *there*.
        """
        modes = {mode: rank for rank, mode in enumerate(self.modes)}
        order = {glyph: rank for rank, glyph in enumerate(self.diacritics)}
        return (
            1 if all(unicodedata.combining(ch) == 0 for ch in symbol) else 0,
            modes.get(modifier_mode(self, symbol, approach), len(modes)),
            order.get(symbol, len(order)),
        )

    def compose_unit(self, base: str, **changes: str) -> str | None:
        """Spell ``base`` wearing the declared marks that supply ``changes``.

        The composed counterpart of :meth:`respell`. ``respell`` answers
        only with a *registered* phone, and the fine-grained phones an
        allophonic rule produces are composed rather than registered:
        the inventory has no entry for ``tʰ``, ``ɪ̃`` or ``t̚``. So
        ``respell("t", release="aspirated")`` is ``None`` while
        ``compose_unit("t", release="aspirated")`` is ``"tʰ"``.

        Registered still wins where one exists, which is this repo's
        standing rule -- ``l`` velarized is the registered ``ɫ``, not
        ``lˠ`` -- so a caller wanting the best answer tries
        :meth:`respell` first and falls back to this.

        **Asking for a value the base already carries is a no-op**, and
        the base comes back unchanged, which is what :meth:`respell` has
        always answered. Writing the mark anyway is not a second
        statement of the same fact, it is a misspelling: ``ɪ̃`` asked to
        be nasalized came back ``ɪ̃̃``, ``n̩`` asked to be syllabic came
        back ``n̩̩``, and the shipped American English set spelled
        *hidden* ``ˈhɪdⁿn̩̩`` because its nasal-release rule and its
        syllabic-nasal rule both fired on the same nasal. ``validate_ipa``
        called those ``duplicate_diacritic`` while the read-back below
        passed them, because a doubled mark reads back carrying the
        requested value and moving nothing -- the guard measured the
        bundle, and the defect was in the spelling.

        Which mark carries a value is :meth:`declaring_mark`'s answer, so
        no feature-to-mark table appears here and the prosody writer reads
        the same declaration. The marks are emitted in the order the
        ``<modes>`` block declares, so a release phase and a secondary
        articulation cannot land in an arbitrary order.

        **Every** mark the unit ends up carrying is ordered, not only the
        ones picked this call, and this is the whole of what makes the
        method confluent. Appending the new marks after whatever was
        already spelled on the base made the answer depend on the order
        the calls arrived in: aspirating then devoicing a ``d`` gave
        ``dʰ̥`` and devoicing then aspirating gave ``d̥ʰ`` -- one feature
        bundle, two spellings, and iterative rule application is where
        that bites, since a rule set applies one change at a time to
        whatever the last rule left. The base is decomposed and the whole
        mark stack re-emitted, so the two routes cannot diverge rather
        than being checked not to.

        A mark is ranked by :func:`~ipakit.segment.modifier_mode`, which
        reads the mode off the mark's own declared keys. That is the same
        read :func:`~ipakit.segment.apply_modifiers` uses to decide what a
        mark contributes, and it answers for a mark already on the base --
        which the requested feature's mode cannot, since a mark on the
        base was not requested.

        Returns ``None`` unless the result re-emits itself, reads back
        carrying every requested value, **and moved nothing else**: the
        composition is measured on the composed unit rather than assumed
        from the marks picked. That last clause is the whole difference
        between a composition and a different phone wearing the right
        answer's clothes. ``place="bilabial"`` is spelled by no mark but
        the linguolabial one, which is also ``articulator="tongue-tip"``,
        so ``compose_unit("s", place="bilabial")`` used to answer ``"s̼"``
        -- a true bilabial declaration on a segment whose articulation is
        not the one asked for. It is now ``None``, because the inventory
        cannot spell that change and inventing a symbol is worse than
        declining.

        "Moved nothing else" cannot mean "moved only the requested keys",
        which was tried and is wrong: the devoicing ring declares
        ``phonation="devoiced"`` *and* ``voiced="-"``, so refusing every
        extra refuses ``ɹ̥`` and ``l̥`` and stops approximant devoicing
        firing at all. Those two keys are not two facts -- ``voiced`` is
        the glottal state read two ways where ``phonation`` reads it four,
        which the data says in ``<projections>`` and this method reads
        rather than restates. So an unrequested move is tolerated exactly
        when it is a projection of a requested one, or a requested one is
        a projection of it; a move on a dimension that varies
        independently of everything asked for is a wrong answer.

        The same test screens the *candidate marks* before one is picked,
        which is a choice rather than a second guard. Five declared values
        are spelled by both a coherent mark and an incoherent one --
        ``articulator="tongue-tip"`` by the apical mark and by the
        linguolabial -- and screening is what makes the coherent one win by
        construction. Today the "fewest declared features" ordering happens
        to pick the same mark, so either check alone refuses the same
        compositions; two orderings agreeing by habit is how this repo has
        been bitten before, so that agreement is measured in the tests
        rather than relied on. The read-back is what makes the guarantee,
        since a mark's declared bundle is not the whole of what wearing it
        does to a segment.

        Examples:
            >>> ipa = IPAFeatures()
            >>> ipa.compose_unit("t", release="aspirated")
            'tʰ'
            >>> ipa.compose_unit("ɹ", phonation="devoiced")
            'ɹ̥'
            >>> ipa.compose_unit("s", place="bilabial") is None
            True
            >>> ipa.compose_unit("t", place="nonsense")
            Traceback (most recent call last):
            ValueError: 'nonsense' is not a value of feature 'place'
        """
        wanted: dict[str, str] = {}
        for name, value in changes.items():
            key = name if name in self.features else name.replace("_", "-")
            feature = self.features.get(key)
            if feature is None:
                raise ValueError(f"unknown feature {name!r}")
            resolved = feature.value_aliases.get(value, value)
            if not all(
                part in feature.values_set
                for step in feature.steps(resolved)
                for part in feature.expand(step)
            ):
                raise ValueError(f"{value!r} is not a value of feature {key!r}")
            wanted[key] = resolved
        if not wanted:
            raise ValueError(
                "cannot compose without a change: pass at least one feature"
            )

        try:
            was = self.get_features(base)
            unit = self.segment(base, strict=True)
        except (ValueError, KeyError):
            return None

        # Picks are kept per placement: a mark supplying an approach-phase
        # key is written before the base and one supplying anything else
        # after it, which is the same rule the reader applies and the only
        # thing that makes `compose_unit(d, approach="nasal")` spell `ⁿd`
        # rather than a `dⁿ` that reads back as a release.
        at_approach = self.features_by_mode.get(APPROACH_MODE, frozenset())
        picked: dict[bool, list[str]] = {False: [], True: []}
        written: dict[str, str] = {}
        for key, value in wanted.items():
            # Already true is a no-op, not a second mark. This is what
            # `respell` does -- `respell('ɫ', velarized='+')` is `'ɫ'` --
            # and the composed path did not: it picked a mark for every
            # requested key and appended it, so `ɪ̃` asked to be nasal came
            # back `ɪ̃̃`, and the shipped American set spelled `hidden`
            # `ˈhɪdⁿn̩̩` because the syllabic rule fired on a unit that was
            # already syllabic. The read-back below could not see it: a
            # doubled mark reads back with the requested value intact and
            # moves nothing, so the composition was measured as correct
            # and was misspelled. Skipping the key rather than returning
            # early is what keeps a mixed request working -- one value
            # already held and one to write composes the one to write.
            if was.get(key) == value:
                continue
            found = self.declaring_mark(key, value, wanted=wanted)
            if found is None:
                return None
            _order, symbol = found
            written[key] = value
            side = picked[key in at_approach]
            if symbol not in side:
                side.append(symbol)

        # A mark already on the base that states a key being written gives
        # way to the mark writing it, rather than standing beside it. Two
        # marks stating one feature is not a stack, it is a contradiction:
        # `aʱ` asked for an aspirated release would be `aʰʱ`, which reads
        # back as whichever of the two the projection reaches first.
        #
        # Read against `written` and not `wanted`: a key the base already
        # satisfies wrote no mark, so nothing supersedes the one that is
        # saying so. `ǀʼ` asked for the velaric airstream it already has
        # would otherwise come back `ǀ`, the ejective mark dropped in the
        # name of a change that moved nothing.
        #
        # And read over what each mark says *where it stands*: `ʰ` in the
        # approach stack is not saying anything about the release, so a
        # requested release does not evict it.
        def survivors(glyphs: tuple[str, ...], approach: bool) -> tuple[str, ...]:
            return tuple(
                glyph
                for glyph in glyphs
                if not any(
                    written.get(key, value) != value
                    for key, value in (
                        getattr(self.diacritics.get(glyph), "features", None) or {}
                    ).items()
                    if key in phase_keys(self, glyph, approach)
                )
            )

        # The new marks join the ones the base already wears, and each
        # stack is ordered together. A trailing mark lands on the LAST
        # constituent and an approach mark on the FIRST, because that is
        # where writing them into the spelling put them; a mark on an
        # inner constituent of a tied unit belongs to that constituent and
        # stays on it.
        constituents = list(unit.constituents)
        tail, head = constituents[-1], constituents[0]
        constituents[-1] = dataclasses.replace(
            tail,
            modifiers=tuple(
                sorted(
                    dict.fromkeys(
                        survivors(tail.modifiers, False) + tuple(picked[False])
                    ),
                    key=self._mark_rank,
                )
            ),
        )
        constituents[0] = dataclasses.replace(
            constituents[0],
            approach=tuple(
                sorted(
                    dict.fromkeys(survivors(head.approach, True) + tuple(picked[True])),
                    key=lambda glyph: self._mark_rank(glyph, approach=True),
                )
            ),
        )
        rebuilt = tuple(constituents)
        try:
            # Unicode has the last word on the order of combining marks:
            # `̚` and `̃` are canonically reordered whatever the modes say,
            # so the spelling is normalized once and then held to
            # re-emitting *itself*. Ordering by mode and refusing whatever
            # normalization touched would decline 6,746 compositions the
            # inventory can spell perfectly well.
            candidate = self.segment(
                dataclasses.replace(unit, constituents=rebuilt).to_ipa()
            ).to_ipa()
            if self.segment(candidate).to_ipa() != candidate:
                return None
            got = self.get_features(candidate)
        except (ValueError, KeyError):
            return None
        if any(got.get(key) != value for key, value in wanted.items()):
            return None
        # Every difference between base and composed, read off both rather
        # than predicted from the marks: a key the composition dropped shows
        # up here as a move to no value, which no request and no projection
        # can excuse.
        moved = {
            key: got.get(key, "")
            for key in set(was) | set(got)
            if key not in METADATA_ATTRS and was.get(key) != got.get(key)
        }
        if not self._coheres(moved, wanted):
            return None
        return candidate

    def _coheres(self, bundle: dict[str, str], wanted: dict[str, str]) -> bool:
        """Does ``bundle`` state only what ``wanted`` asked for?

        True when every ``(feature, value)`` in ``bundle`` is either
        requested outright, or one side of a declared projection whose
        other side is requested -- the glottal state written as
        ``phonation`` and as ``voiced`` is one fact, so either spelling
        excuses the other. Anything else is a second, independent claim,
        and a composition that makes one is answering a question nobody
        asked. Metadata is not a phonetic claim and is skipped.

        A projection excuses a key the request is **silent** about, and
        never one it names. Contradicting a requested value outright is
        the one thing no other requested value can make right: the breathy
        ring projects to ``voiced="+"``, so asking for ``phonation="modal"``
        and ``voiced="+"`` together let it in on the strength of the
        second half while flatly denying the first, and
        ``compose_unit("c", phonation="modal", voiced="+")`` came back
        ``c̤̬`` -- two phonation marks, breathy then modal, on one segment.
        """
        for key, value in bundle.items():
            if key in METADATA_ATTRS or wanted.get(key) == value:
                continue
            if key in wanted:
                return False
            coarse = self.projections.get((key, value))
            if coarse is not None and wanted.get(coarse[0]) == coarse[1]:
                continue
            if any(
                self.projections.get(pair) == (key, value) for pair in wanted.items()
            ):
                continue
            return False
        return True

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
        text = text.replace(self.seq_tie + self.tie_bar, self.tie_bar)
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

        This is the package's one alias resolution: :meth:`parse` runs it,
        :meth:`_resolve_token` is it, and the string converters reach it
        through :func:`ipakit._convert.resolve_aliases`. Output is in the
        canonical Unicode form, so it is idempotent.

        Examples:
            >>> IPAFeatures().expand_ligatures("g:")  # default parsing is literal
            'g:'
        """
        ipa = self.canonicalize_unicode(ipa)
        replaced = False
        for lig, expanded in self.ligature_map.items():
            if len(lig) > 1 and self.tie_bars & set(lig):
                continue
            if lig in ipa:
                ipa = ipa.replace(lig, expanded)
                replaced = True
        # An alias may expand to a combining mark ("˖" -> U+031F), which
        # canonical ordering can then move; canonicalizing again is what
        # makes "k͡˖" and "k̟͡" the same string rather than two readings.
        return self.canonicalize_unicode(ipa) if replaced else ipa

    def _vocalic(self, ch: str) -> bool:
        """Whether a base glyph is a vowel, for tie sense.

        The one read behind both places that sense a tie:
        :meth:`add_ties`, which writes one into a whitespace-grouped
        segment, and :meth:`from_wild`, which re-senses the ties already
        in imported text. They held byte-identical copies of this, so a
        correction to either would have made the two entry points
        disagree about what an under-tie means.
        """
        phone = self.phones.get(ch)
        return phone is not None and phone.features.get("manner") == "vowel"

    def add_ties(self, segment: str) -> str:
        """Add tie bars between base phones in a multi-phone segment.

        Whitespace grouping asserts unit-hood; the inserted glyph follows a
        documented heuristic: two adjacent vocalic bases bind sequentially
        (under-tie: a trajectory), anything else binds simultaneously
        (over-tie). Write the tie explicitly to override.

        A tie binds the preceding **unit** -- a base and the marks written
        on it -- which is what :meth:`parse` reads back off the result, so
        the run of marks a base carries is taken by :meth:`_modifier_run`
        here too and the two cannot come to disagree about where a unit
        ends. Walking characters and letting any mark reset the left side
        meant a mark between two bases declined the tie outright
        (``d̪ɮ``), and on a longer chain moved it to the wrong junction:
        ``d̠ʒxʼ`` tied ``ʒ`` to ``x``.

        A mark that binds something other than the base before it does end
        the unit, and that is the same run: a stress mark scopes what
        follows, a break and the linking tie stand between units. So
        ``pə.tˈeɪ.toʊ`` still ties within each syllable and across
        neither.

        Every adjacent pair inside one group is tied, so a whole word
        handed over as one group comes back as one unit. That is the
        contract -- the grouping is the assertion -- and not something
        this can detect: ``add_ties("kæt")`` is ``k͡æ͡t`` because ``kæt``
        was offered as a segment.
        """
        if self.tie_bars & set(segment):
            return segment

        result: list[str] = []
        prev_phone_char = ""
        i = 0
        while i < len(segment):
            char = segment[i]
            i += 1
            if char not in self.phones:
                result.append(char)
                prev_phone_char = ""
                continue
            if prev_phone_char:
                result.append(
                    self.seq_tie
                    if self._vocalic(prev_phone_char) and self._vocalic(char)
                    else self.tie_bar
                )
            result.append(char)
            prev_phone_char = char
            # The marks written on this base ride with it into the unit the
            # next tie binds to.
            run = self._modifier_run(segment, i)
            result.extend(run)
            i += len(run)
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
                expanded, i, self.phones, MAX_MATCH_LEN, self.phones, self.tie_bars
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

                # Check if this segment is syllabic (a nucleus), through
                # the same read the `nucleus` derived class resolves.
                is_syllabic = best_phone in self.phones and self.is_nucleus(
                    self.phones[best_phone].features
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
        the sense). Ligature aliases resolve in :meth:`parse`, so every
        caller of it -- not only this one -- reads ``ʧ`` as ``t͡ʃ``.

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
        if phoneset is not None:
            return [
                unicodedata.normalize("NFC", base + "".join(diacs))
                for base, diacs in self.parse(ipa, phoneset=phoneset, strict=strict)
            ]
        parsed = self.read(ipa, strict=strict)
        opaque = boundary_marks(self)
        return [
            unicodedata.normalize("NFC", unit.text)
            for unit in parsed.units
            if unit.segment is not None or unit.text in opaque
        ]

    def segmented(
        self,
        ipa: str,
        phoneset: Phoneset | None = None,
        strict: bool = False,
    ) -> str:
        """Parse IPA string and return whitespace-separated segments."""
        return " ".join(self.tokenize(ipa, phoneset=phoneset, strict=strict))

    def _parse_all(
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

        Registered ligature aliases (``ʧ``, ``ʦ``, ``ƛ``, the spacing
        ``˖``/``˗``) are expanded here, before matching, because this is
        the gate every read of an IPA string passes -- flat, structured
        and converter alike. Doing it in the callers instead left the ones
        that call ``parse`` directly reading an alias as a character
        registered nowhere and *dropping* it, so a converter answered a
        word short of a phoneme while the tokenizer read all of it.

        A character that is registered nowhere in the inventory cannot be
        represented, so it is dropped -- but never silently: the default
        path warns, naming what it lost, because a shorter result that
        still *looks* well formed is the failure mode worth hearing about.
        ``strict=True`` raises ``ValueError`` instead. (Registered
        separators, declared zeros and whitespace are not "unknown": they
        are known marks that carry no unit, and they neither warn nor
        raise. :attr:`carries_no_segment` is the declared half of that
        set, asked here and by :meth:`validate_ipa` so the two cannot
        come to disagree about what is registered.)

        ASCII stand-ins are not soft-read here -- ``g``, ``:``, ``?`` and
        ``'`` are unregistered characters like any other. Import such text
        with :meth:`from_wild` first.
        """
        if not segment:
            return []

        # Alias resolution happens here rather than in each caller: this is
        # the one gate every read of an IPA string passes through, and a
        # caller that reached ``parse`` without expanding first used to lose
        # the alias entirely (see the note in the docstring).
        segment = self.expand_ligatures(segment)
        phone_lookup = set(self.phones.keys())
        if phoneset:
            phone_lookup |= set(phoneset.phones)

        if segment in phone_lookup:
            return [(segment, [])]

        result = []
        skipped: list[str] = []
        unbound_ties: list[str] = []
        unitless = self.carries_no_segment
        n = len(segment)
        i = 0
        while i < n:
            # A mark declaring an approach phase states it of the base
            # written after it, so the run is read forward and kept only
            # when a base is actually there. Where none is, ``lead`` is
            # discarded and the mark falls through to the refusal below,
            # which is what ``ʷk`` and a trailing ``ⁿ`` still get.
            lead = approach_run(self, segment, i)
            best_phone, best_len = longest_match(
                segment,
                i + len(lead),
                phone_lookup,
                MAX_MATCH_LEN,
                phone_lookup,
                self.tie_bars,
            )
            if not best_phone:
                lead = []

            if best_phone:
                chain = "".join(lead) + best_phone
                j = i + len(lead) + best_len
                diacritics = self._modifier_run(segment, j)
                j += len(diacritics)
                # A tie joins the unit just read -- base *and* the
                # modifiers written on it -- to the one after it.
                # ``longest_match`` only spans ties between registered
                # bases, so the rest of the chain is grown here; without
                # this, a tie written after a diacritic falls through to
                # the standalone branch and the juncture is lost.
                while j < n and segment[j] in self.tie_bars:
                    # Each constituent of the chain may carry its own
                    # approach run, on the same terms as the first.
                    next_lead = approach_run(self, segment, j + 1)
                    next_phone, next_len = longest_match(
                        segment,
                        j + 1 + len(next_lead),
                        phone_lookup,
                        MAX_MATCH_LEN,
                        phone_lookup,
                        self.tie_bars,
                    )
                    if not next_phone:
                        break
                    chain += (
                        "".join(diacritics)
                        + segment[j]
                        + "".join(next_lead)
                        + next_phone
                    )
                    j += 1 + len(next_lead) + next_len
                    diacritics = self._modifier_run(segment, j)
                    j += len(diacritics)
                result.append((chain, diacritics))
                i = j
            elif segment[i] in self.tie_bars:
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
                # Registered separators (syllable break, word mark), a
                # declared zero and whitespace are known symbols that
                # simply carry no unit; only unregistered characters
                # count as lost. A zero used to fall through here and be
                # reported as an unregistered symbol -- the parser
                # calling unknown what ``<zeros>`` declares, and
                # shortening the string to say so.
                if segment[i].isspace() or segment[i] in unitless:
                    # Preserve every registered non-segmental position in
                    # the canonical scan. Public ``parse`` projects the
                    # separators/zeros/space it historically dropped; Form
                    # consumes them here, from this same pass.
                    result.append((segment[i], []))
                else:
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

    def parse(
        self,
        segment: str,
        phoneset: Phoneset | None = None,
        strict: bool = False,
    ) -> list[tuple[str, list[str]]]:
        """Compatibility projection of the canonical token scan.

        Segment and opaque structural tokens are retained; separators,
        structural zeros, and whitespace are the positions this historical
        API drops. :meth:`read` is the lossless ingestion boundary.
        """
        scanned = self._parse_all(segment, phoneset=phoneset, strict=strict)
        dropped = set(self.separators) | set(self.zeros)
        return [
            item for item in scanned if not (item[0].isspace() or item[0] in dropped)
        ]

    def _modifier_run(self, text: str, start: int) -> list[str]:
        """The run of modifier diacritics starting at ``text[start]``.

        Stops at anything structural -- a tie, a break, the linking mark --
        because those relate units rather than modify one, and at a stress
        mark, because a stress mark is written *before* what it scopes.

        That last stop is about direction, not about mode. Prosody does
        not all bind one way: length (``eː``), tone (``a˥``) and the
        contour marks are written after the segment they lengthen or
        pitch, so they are trailing modifiers of the unit just read and
        belong in this run. Stress is the one prosodic mark whose domain
        follows it -- ``ˈ`` announces the syllable to come -- so
        sweeping it up here binds it to the unit *before* it, and since
        :meth:`Segment.to_ipa` re-emits stress ahead of its unit that
        walks the mark left across a segment boundary. Stopping at every
        prosodic mark would cure that and lose the length of ``eː``
        with it.
        """
        run: list[str] = []
        j = start
        while (
            j < len(text)
            and text[j] in self.diacritics
            and text[j] not in self.tie_bars
            and text[j] not in self.stress_markers
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

        Each token is read as :meth:`Segment.scalar` reads it -- one
        :func:`~ipakit.segment.flat_projection` over the unit's
        constituents -- so the three reads of one token are one
        computation. The single divergence is prosody: this returns one
        flat bundle per token and has no unit level to put a prosodic
        mark on, so ``compose("eː")`` reports ``length=long`` where
        ``scalar()`` reports the length of ``e`` and carries the mark in
        :attr:`Segment.prosody`.
        """
        result: list[tuple[str, dict[str, str]]] = []
        parsed_units = (
            [
                unit
                for base, diacritics in self.parse(segment, phoneset=phoneset)
                if (unit := self._segment_from_parsed(base, diacritics)) is not None
            ]
            if phoneset is not None
            else list(self.read(segment).segments)
        )
        for unit in parsed_units:
            # This compatibility projection has never represented prefix
            # stress: it returns segmental bundles, whereas Form retains
            # stress on the occurrence. Project it away only here, after the
            # canonical read, instead of giving it a second parse path.
            projected = dataclasses.replace(
                unit,
                prosody=tuple(
                    mark for mark in unit.prosody if mark not in self.stress_markers
                ),
            )
            # The unit's own flat projection, undefaulted: a mark belongs
            # to the constituent it is written on, and a mark that adds
            # what the base leaves unstated has to land before defaults do.
            if not (feats := projected.scalar(with_defaults=False)):
                continue
            apply_modifiers(
                self,
                feats,
                projected.prosody,
                prosody=True,
                where=repr(projected.to_ipa()),
            )
            if with_defaults:
                fill_defaults(self, feats)
            result.append((unicodedata.normalize("NFC", projected.to_ipa()), feats))
        return result

    # -------------------------------------------------------------------------
    # Structured segments (docs/ties.md; design spec)
    # -------------------------------------------------------------------------

    def read(
        self,
        text: str | Form,
        strict: bool = False,
        *,
        segmented: bool = False,
        wild: bool = False,
    ) -> Form:
        """Parse an IPA transcription into its canonical structured form.

        This is the lossless ingestion boundary.  Computation should carry
        the returned :class:`~ipakit.form.Form` and take named projections
        from it instead of tokenizing or reparsing the source string.
        ``strict=True`` refuses any material that cannot be represented.
        """
        from .form import Form

        if isinstance(text, Form):
            return text

        if segmented:
            words: list[str] = []
            for line in text.splitlines():
                inline: list[str] = []
                for part in line.split("#"):
                    tokens = part.split()
                    if wild:
                        tokens = [self.from_wild(token) for token in tokens]
                    for token in tokens:
                        try:
                            parsed = self._parse_all(token, strict=True)
                            form = Form.from_parsed(token, parsed, self, True)
                        except ValueError as exc:
                            raise ValueError(
                                f"segmented token {token!r} is not house IPA: {exc}"
                            ) from exc
                        if not form.units or any(
                            unit.segment is None for unit in form.units
                        ):
                            raise ValueError(
                                f"segmented token {token!r} is not house IPA"
                            )
                    inline.append("".join(tokens))
                words.extend(inline)
            text = "#".join(words)
        elif wild:
            text = self.from_wild(text)

        parsed = self._parse_all(text, strict=strict)
        collapsed: list[tuple[str, list[str]]] = []
        for token, marks in parsed:
            if token.isspace() and collapsed and collapsed[-1][0].isspace():
                previous, previous_marks = collapsed[-1]
                collapsed[-1] = (previous + token, previous_marks + marks)
            else:
                collapsed.append((token, marks))
        return Form.from_parsed(text, collapsed, self, strict)

    def read_json(self, data: str) -> Form:
        """Restore a canonical representation serialized by ``Form.to_json``."""
        from .form import Form

        return Form.from_json(data, self)

    def segments(self, text: str, strict: bool = False) -> list[Segment]:
        """Parse IPA text into structured :class:`Segment` units.

        Same segmentation as :meth:`tokenize`. Stress marks attach to
        the first following syllabic unit's prosody -- wherever they stand,
        not only at the start of the string -- while the other prosodic marks
        (length, tone, contour) attach to the unit they follow, which is
        the side each is written on. Structural marks (ties become
        junctures; breaks/linking live between units) never appear in a
        unit's prosody.

        A unit bears one stress level, so of several marks standing
        before one nucleus only the nearest binds: the others are superseded
        and reported. A stress mark with no syllabic unit after it binds nothing
        and is reported the same way -- like an unbound tie, and for the
        same reason: dropping it silently would make the result shorter
        than the input while still looking well formed.

        Every other mark binds the unit *before* it, so one written where
        there is no such unit -- ``ⁿd``, the pre-modifier convention every
        external inventory uses -- binds nothing either, and is reported on
        exactly those terms. It is not re-read as a modifier of what
        follows: the library has no pre-modifier, and inventing a binding
        the data does not declare is how ``ǂʼ`` would come back ``ǂ``.
        Structural marks are the exception, and by declaration rather than
        by exemption: a break or the linking tie is a relation *between*
        units, belongs to no unit at either side, and is kept by ``Form``.

        Unregistered characters are dropped with a warning, as in
        :meth:`tokenize`; ``strict=True`` raises instead, which is what
        guarantees ``to_ipa(segments(text)) == text``.
        """
        return list(self.read(text, strict=strict).segments)

    def _segments_from_parsed(
        self, parsed: Sequence[tuple[str, list[str]]], strict: bool
    ) -> list[Segment]:
        """Build segments from one canonical token scan."""
        return [
            segment
            for _, segment in self._units_from_parsed(parsed, strict)
            if segment is not None
        ]

    def _units_from_parsed(
        self, parsed: Sequence[tuple[str, list[str]]], strict: bool
    ) -> list[tuple[str, Segment | None]]:
        """Project the shared prefix-raising pass to its historical pairs."""
        return [
            (token, segment)
            for token, segment, _ in self._raised_units_from_parsed(parsed, strict)
        ]

    def _raised_units_from_parsed(
        self, parsed: Sequence[tuple[str, list[str]]], strict: bool
    ) -> list[tuple[str, Segment | None, dict[str, str]]]:
        """Attach one scan while retaining its structural token positions.

        A stress mark binds the first following syllabic unit -- a vowel or
        a consonant marked syllabic -- while its token stays at the position
        where it was written.  Non-syllabic units and structural tokens are
        transparent to that binding.  If the scan reaches its end without a
        following syllabic unit, the mark is unbound: lax reading warns and
        drops its semantic claim, and ``strict=True`` raises.
        """
        result: list[tuple[str, Segment | None, dict[str, str]]] = []
        pending_stress: list[str] = []
        pending_prominence: list[str] = []
        word_has_unit = False
        superseded: list[str] = []
        unplaced: list[str] = []
        for base, diacritics in parsed:
            token = unicodedata.normalize("NFC", base + "".join(diacritics))
            if token and all(ch in self.stress_markers for ch in token):
                result.append((token, None, {}))
                pending_stress.extend(token)
                # Stress is a single-valued feature of a syllable, so a
                # unit cannot carry two of these. The nearest mark binds:
                # a mark written closer to its domain outranks one
                # written further from it, whichever side it binds from.
                if len(pending_stress) > 1:
                    superseded.extend(pending_stress[:-1])
                    pending_stress = pending_stress[-1:]
                continue
            if token and all(ch in self.prominence_markers for ch in token):
                result.append((token, None, {}))
                pending_prominence.extend(token)
                try:
                    self.raised_prominence(pending_prominence)
                except ValueError:
                    if strict:
                        raise
                    warnings.warn(
                        f"dropped {len(pending_prominence)} unregistered symbol(s) "
                        f"{sorted(set(pending_prominence))} while parsing IPA: "
                        "repetition names no declared prominence level. "
                        "Pass strict=True to raise instead.",
                        stacklevel=3,
                    )
                    pending_prominence = []
                continue
            if token.isspace() or token in self.carries_no_segment:
                result.append((token, None, {}))
                if token.isspace() or self._ends_word(token):
                    word_has_unit = False
                continue
            # ``base`` and ``diacritics`` are already the canonical scan's
            # unit. Building from them is the point of this path: feeding
            # ``token`` back through ``_segment_from_token`` would perform a
            # second tokenization once for every segment in the form.
            seg = self._segment_from_parsed(base, diacritics)
            # A token that carries no unit has nothing to take the stress,
            # so the mark stays pending for the syllabic unit that does.
            if seg is not None:
                raised: dict[str, str] = {}
                if pending_stress and self.is_nucleus(seg.scalar()):
                    seg = self._segment_from_parsed(
                        base, diacritics, tuple(pending_stress)
                    )
                    pending_stress = []
                if pending_prominence:
                    if word_has_unit:
                        self._report_misplaced_prominence(pending_prominence, strict)
                    else:
                        # The same forward carry has found the first position
                        # of its unit. Form projects this binding onto the
                        # containing word event; it never enters the segment's
                        # feature bag.
                        raised["prominence"] = self.raised_prominence(
                            pending_prominence
                        )
                    pending_prominence = []
                result.append((token, seg, raised))
                word_has_unit = True
            elif not self.is_structural_token(token):
                unplaced.append(token)
                result.append((token, None, {}))
            else:
                result.append((token, None, {}))
                if self._ends_word(token):
                    word_has_unit = False
        self._report_unplaced(superseded, pending_stress, unplaced, strict)
        if pending_prominence:
            what = "unbound prominence mark(s)"
            detail = "a prominence mark raises to the first following unit"
            if strict:
                raise ValueError(
                    f"Cannot parse IPA segment: {len(pending_prominence)} {what} "
                    f"{sorted(set(pending_prominence))} reach no unit: {detail}."
                )
            warnings.warn(
                f"dropped {len(pending_prominence)} {what} "
                f"{sorted(set(pending_prominence))} while parsing IPA: {detail}. "
                "Pass strict=True to raise instead.",
                stacklevel=3,
            )
        return result

    def _ends_word(self, token: str) -> bool:
        """Return whether a declared structural token reaches the word tier."""
        declared = self.separators.get(token) or self.diacritics.get(token)
        if declared is None:
            return False
        level = (declared.features or {}).get("level")
        levels = self.features["level"].values
        return level in levels and levels.index(level) >= levels.index("word")

    @staticmethod
    def _report_misplaced_prominence(marks: list[str], strict: bool) -> None:
        """Report a prefix unit claim written after its word has begun."""
        what = "misplaced prominence mark(s)"
        detail = "a prominence mark must precede the first segment of its word"
        glyphs = sorted(set(marks))
        if strict:
            raise ValueError(
                f"Cannot parse IPA segment: {len(marks)} {what} {glyphs}: {detail}."
            )
        warnings.warn(
            f"dropped {len(marks)} {what} {glyphs} while parsing IPA: {detail}. "
            "Pass strict=True to raise instead.",
            stacklevel=3,
        )

    def _report_unplaced(
        self,
        superseded: list[str],
        unbound: list[str],
        unplaced: list[str],
        strict: bool,
    ) -> None:
        """Report marks that reached no unit.

        The same contract :meth:`parse` gives an unbound tie: the mark is
        a registered symbol, so ``strict=`` would never have seen it as
        "unknown", and dropping it quietly leaves a shorter result that
        still reads as well formed.
        """
        reports = (
            (
                superseded,
                "superseded stress mark(s)",
                "a unit bears one stress level, and the mark nearest it binds",
            ),
            (
                unbound,
                "unbound stress mark(s)",
                "a stress mark binds the first syllabic unit that follows it",
            ),
            (
                unplaced,
                "unplaced mark(s)",
                "a mark binds the unit written before it, and these have none",
            ),
        )
        for marks, what, detail in reports:
            if not marks:
                continue
            if strict:
                raise ValueError(
                    f"Cannot parse IPA segment: {len(marks)} {what} "
                    f"{sorted(set(marks))} reach no unit: {detail}."
                )
            warnings.warn(
                f"dropped {len(marks)} {what} "
                f"{sorted(set(marks))} while parsing IPA: {detail}. "
                "Pass strict=True to raise instead.",
                stacklevel=3,
            )

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
        check_prosody(self, prosody)
        return Segment(
            constituents=constituents,
            junctures=junctures,
            prosody=prosody,
            _features=self,
        )

    def to_ipa(self, segments: list[Segment]) -> str:
        """Join structured units back into one IPA string.

        The inverse of :meth:`segments`: ``to_ipa(segments(s)) == s`` for
        house-canonical input, stress marks included. A syllable-leading
        spelling such as ``ˈkæt`` binds the nucleus and therefore projects
        through segments as ``kˈæt``; :class:`~ipakit.form.Form` retains
        the independent written position and round-trips ``ˈkæt`` exactly.
        A join guarantees no more than its parts do, and each
        unit emits through :meth:`Segment.to_ipa`, which is lossy on the
        enumerable set of legacy alias spellings (docs/ties.md) -- so the
        join is too: ``segments("ʧa")`` rejoins as ``"t͡ʃa"``, the
        canonical spelling of what was parsed rather than the ligature
        that was written.

        One further difference is the Segment model showing through, not
        this method rewriting anything: marks that belong to no unit
        (syllable breaks, the linking undertie) are not carried by a
        Segment, so a join cannot restore them. Structure that must
        survive a string round trip travels as ``Segment.to_json``.
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
        for variant, canonical in self._wild_variants.items():
            text = text.replace(variant, canonical)

        # Remaining ties belong to unregistered chains. Wild text uses one
        # tie glyph as a typographic habit, so only uniform-glyph chains are
        # re-sensed (per juncture, from the neighboring bases -- the
        # add_ties heuristic, through the same read); a chain already
        # mixing both glyphs is house-authored and passes through
        # untouched.
        chars = list(text)
        runs: list[list[int]] = []
        current: list[int] = []
        pending_tie = False
        for i, ch in enumerate(chars):
            if ch in self.tie_bars:
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
                    both_vocalic = self._vocalic(chars[prev_i]) and self._vocalic(
                        chars[next_i]
                    )
                    chars[i] = self.seq_tie if both_vocalic else self.tie_bar
        return "".join(chars)

    def tie_glyph_variants(self, spelling: str) -> list[str]:
        """Every spelling of ``spelling`` differing only in which glyph
        writes each of its ties -- itself excluded, and ``[]`` when it
        holds no tie.

        The two glyphs are distinct *senses* in house style, so this is
        not a normalization the parser performs. It is what a reader of
        outside convention needs, where the glyphs are typographic free
        variants: :meth:`from_wild` maps a variant of a registered name
        back to that name, and a converter whose target alphabet cannot
        express the sense at all (ARPABET has one ``CH``) keys its table
        under both. Written once here so those two readers cannot come to
        enumerate the variants differently.
        """
        positions = [i for i, ch in enumerate(spelling) if ch in self.tie_bars]
        variants = []
        for mask in range(1, 2 ** len(positions)):
            chars = list(spelling)
            for bit, pos in enumerate(positions):
                if mask & (1 << bit):
                    chars[pos] = (
                        self.seq_tie if chars[pos] == self.tie_bar else self.tie_bar
                    )
            variants.append("".join(chars))
        return variants

    @functools.cached_property
    def _wild_variants(self) -> dict[str, str]:
        """Glyph-variant spellings of registered tied names -> canonical,
        longest first so longer chains win."""
        variants: dict[str, str] = {}
        for name in self.phones:
            for variant in self.tie_glyph_variants(name):
                variants[variant] = name
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
        """One base phone with the marks written on it, or ``ValueError``.

        The modifiers are taken by :meth:`_modifier_run`, which is also
        what :meth:`parse` uses to decide how far a unit extends, so the
        two cannot disagree about which marks a base absorbs. That run
        stops at a mark that binds something other than the base it
        follows -- a tie, a break, and above all a stress mark, which
        scopes the unit *after* it. Such a mark is left for the caller
        rather than swallowed: a constituent has no place to put it, and
        a bundle that quietly ignores part of its own spelling is the
        silent wrong answer this refusal exists to prevent.

        Anything left over is therefore an error, whether it is an
        unregistered character or a registered mark this constituent
        cannot carry.
        """
        part = self._resolve_token(part)
        approach = approach_run(self, part, 0)
        base, best_len = longest_match(part, len(approach), self.phones, MAX_MATCH_LEN)
        if not base:
            raise ValueError(f"no registered base phone in {part!r}")
        start = len(approach) + best_len
        modifiers = self._modifier_run(part, start)
        if start + len(modifiers) != len(part):
            stray = part[start + len(modifiers)]
            raise ValueError(f"unknown modifier {stray!r} in {part!r}")
        return Constituent(
            base=base, modifiers=tuple(modifiers), approach=tuple(approach)
        )

    def _segment_from_token(
        self, token: str, stress: tuple[str, ...] = ()
    ) -> Segment | None:
        parsed = self.parse(token)
        if not parsed:
            return None
        chain, diacritics = parsed[0]
        return self._segment_from_parsed(chain, diacritics, stress)

    def _segment_from_parsed(
        self, chain: str, diacritics: list[str], stress: tuple[str, ...] = ()
    ) -> Segment | None:
        """Build one unit from an already-parsed ``(chain, diacritics)``
        pair, so a caller that has run :meth:`parse` does not run it
        twice."""
        raw = re.split(f"([{self.tie_bar}{self.seq_tie}])", chain)
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
            junctures = tuple(
                Sense.FUSE if g == self.tie_bar else Sense.SEQ for g in glyphs
            )

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
                dataclasses.replace(last, modifiers=last.modifiers + tuple(modifiers)),
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

    @functools.cached_property
    def _graph_declarations(self) -> Declarations:
        """Immutable tier-graph declarations derived once per inventory."""
        from ._ipa_graph import _derive_declarations

        return _derive_declarations(self)

    @functools.cached_property
    def _form_constants(self) -> _FormConstants:
        """Immutable form vocabulary derived once per inventory."""
        from .form import _derive_form_constants

        return _derive_form_constants(self)

    @functools.cached_property
    def _prosody_declarations(self) -> Mapping[str, Mapping[str, str]]:
        """Immutable per-mark prosody declarations for this inventory."""
        from .form import _derive_prosody_declarations

        return _derive_prosody_declarations(self)

    @property
    def feature_order(self) -> list[str]:
        """Feature names in XML declaration order."""
        return list(self.features.keys())

    @functools.cached_property
    def features_by_mode(self) -> dict[str, frozenset[str]]:
        """Declared feature names grouped by their contribution mode.

        The partition is total and comes from the data: a feature that
        declares no ``mode`` contributes the vocabulary's default one. The
        grouping is what makes "a mark stating this key is a secondary
        articulation" one statement rather than a set in each module that
        needs it.
        """
        grouped: dict[str, set[str]] = {mode: set() for mode in self.modes}
        for name, feat in self.features.items():
            grouped.setdefault(feat.mode or self.default_mode, set()).add(name)
        return {mode: frozenset(names) for mode, names in grouped.items()}

    @functools.cached_property
    def approach_marks(self) -> frozenset[str]:
        """The marks that may stand before a base, derived from the data.

        A mark belongs here because it declares a feature the ``<modes>``
        block puts at the approach phase, which is the whole of the rule:
        no glyph is listed, and a mark that starts declaring one joins
        without a change here. Everything else written where no unit
        precedes it still binds nothing and is still reported
        (:meth:`_report_unplaced`) -- ``ʷ`` is a secondary articulation,
        which spans the segment rather than naming a phase of it, so
        ``ʷk`` stays refused.
        """
        return frozenset(
            symbol
            for symbol in self.diacritics
            if phase_keys(self, symbol, approach=True)
        )

    @functools.cached_property
    def secondary_places(self) -> dict[str, str]:
        """Secondary-articulation feature -> the place it constricts at.

        Keyed by feature rather than by diacritic: the same articulation
        can be written as a modifier (``lˠ``) or be inherent to the base
        phone (``ɫ``), so a reader has to see it on the assembled bundle
        rather than on the glyph stack. Its keys are exactly the
        ``secondary`` bucket of :attr:`features_by_mode`, by construction.
        """
        return {
            name: feat.place
            for name, feat in self.features.items()
            if feat.mode == "secondary" and feat.place is not None
        }

    def feature_applies(self, feature: str, bundle: dict[str, str]) -> bool:
        """Whether a description of this segment reads ``feature`` out.

        A feature that declares no ``applies`` applies to everything.
        Otherwise it applies when the segment's manner is named, or when
        one of the derived classes claims it: ``consonant`` is the
        complement of vowel and silence (:attr:`consonant_manners`), and
        ``nucleus`` is anything that can be a syllable peak
        (:meth:`is_nucleus`).
        """
        feat = self.features.get(feature)
        if feat is None or not feat.applies:
            return True
        manner = bundle.get("manner")
        if manner is None:
            return True
        if manner in feat.applies:
            return True
        if "consonant" in feat.applies and manner in self.consonant_manners:
            return True
        return "nucleus" in feat.applies and self.is_nucleus(bundle)

    def is_nucleus(self, bundle: Mapping[str, str]) -> bool:
        """Whether a feature bundle can be a syllable peak.

        A vowel, or any segment marked syllabic. Nucleus-hood is not a
        manner class: a syllabic liquid is a nucleus with consonantal
        manner, and Tashlhiyt Berber and Miyako put stops and fricatives
        in the same position.

        One read, because it had been two: the ``nucleus`` derived class
        that :meth:`feature_applies` routes and the private test
        :meth:`normalize_stress_to_nucleus` used to walk a transcription
        with were the same predicate written twice, with nothing making
        them agree. What a nucleus is decides where a stress mark lands
        and which features a description reads out, and those two
        answers have to come from one place.
        """
        return bundle.get("manner") == "vowel" or bundle.get("syllabic") == "+"

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
    def prominence_markers(self) -> frozenset[str]:
        """Prefix marks whose repetition raises a unit above its default.

        Both the feature and its glyphs are derived from the inventory.  The
        ordinal declaration supplies the level count; no Python table restates
        ``^`` or the names of the rungs.
        """
        return frozenset(
            symbol
            for symbol, mark in self.diacritics.items()
            if "prominence" in mark.features
        )

    def raised_prominence(self, marks: Sequence[str]) -> str:
        """Read a repeated upward mark against prominence's centred ladder."""
        feature = self.features["prominence"]
        if feature.centre is None:
            raise ValueError("prominence requires a declared centre")
        index = feature.values.index(feature.centre) + len(marks)
        if not marks or len(set(marks)) != 1 or index >= len(feature.values):
            glyphs = sorted(set(marks))
            raise ValueError(
                f"Cannot parse IPA segment: {len(marks)} unregistered symbol(s) "
                f"{glyphs}: repetition names no declared prominence level."
            )
        return feature.values[index]

    @functools.cached_property
    def syllable_break(self) -> str:
        """Syllable-boundary char (the separator declared at level 'syllable')."""
        for sym, sep in self.separators.items():
            if sep.features.get("level") == "syllable":
                return sym
        return "."

    @property
    def carries_no_segment(self) -> frozenset[str]:
        """Declared symbols a flat read produces no token for.

        Two element classes, one property, because the flat reads have
        exactly one question to ask of both: is this character *known*
        and simply not a segment, or is it unregistered and therefore
        lost? ``<separators>`` are relations between segments (the
        syllable break, the word mark, the linking tie); ``<zeros>`` are
        positions with no segment in them. Neither is "unknown", so
        neither warns and neither raises under ``strict``, exactly as
        docs/ties.md says of a declared mark that carries no unit -- and
        neither survives :meth:`to_ipa`, which joins segments. ``Form``
        is the layer that keeps them, and it reads the two tables
        directly.

        Read rather than listed so a class added to ``ipa.xml`` cannot
        be known to the tokenizer and unknown to the validator: they ask
        this, and the zero spent a release being dropped by one and
        reported by the other because each named ``separators`` on its
        own.

        Whitespace is deliberately absent: ``ipa.xml`` declares no space,
        so its callers add ``str.isspace`` themselves rather than have
        this property state an undeclared fact.
        """
        return frozenset(self.separators) | frozenset(self.zeros)

    @functools.cached_property
    def tie_marks(self) -> dict[str, str]:
        """Tie sense -> the mark that spells it, from the `tie` feature.

        The one derived read of "which characters are ties", in the shape
        of :attr:`stress_markers`. The package used to keep the two
        glyphs in ``constants.py`` as bare strings, which is the same
        mistake the stress table made: ``ipa.xml`` declares a ``tie``
        feature whose values are ``simultaneous`` and ``sequential``, and
        declares the suprasegmental that carries each, so the question
        has an answer in the data and a second copy in Python can only go
        stale. :meth:`declaring_mark` is that answer, asked once here.

        Empty if the loaded data declares no ``tie`` feature at all -- an
        inventory with no ties has no tie glyphs, and the membership
        reads below then correctly find none.
        """
        feature = self.features.get("tie")
        if feature is None:
            return {}
        found = ((v, self.declaring_mark("tie", v)) for v in feature.values)
        return {value: mark[1] for value, mark in found if mark is not None}

    @property
    def tie_bar(self) -> str:
        """The over-tie: the mark declaring a simultaneous juncture."""
        return self.tie_marks.get("simultaneous", "")

    @property
    def seq_tie(self) -> str:
        """The under-tie: the mark declaring a sequential juncture."""
        return self.tie_marks.get("sequential", "")

    @functools.cached_property
    def tie_bars(self) -> frozenset[str]:
        """Every tie mark, for membership tests.

        A set rather than a string so that data declaring no tie asks a
        question with the answer "no" rather than one with the answer
        ``"" in text``, which is always yes.
        """
        return frozenset(self.tie_marks.values())

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
