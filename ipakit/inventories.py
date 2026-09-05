"""Named finite phone inventories and the notations that spell them."""

from __future__ import annotations

import functools
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .models import Phoneset

if TYPE_CHECKING:
    from .bridges.vocabulary import VocabularyBridge

_DATA = Path(__file__).parent / "data"
_ESPEAK = _DATA / "bridges" / "espeak"
_PHONEMAPS = _DATA / "phonemaps"


@dataclass(frozen=True)
class Style:
    """A strict spelling boundary around house IPA.

    Reading produces one house-IPA phone. Spelling is reversible unless the
    style explicitly declares that one spelling collapses several phones.
    """

    name: str
    _reader: Callable[[str], str] = field(repr=False, compare=False)
    _speller: Callable[[str], str] = field(repr=False, compare=False)
    collapses: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def read(self, spelling: str) -> str:
        """Read one external spelling as house IPA."""
        return self._reader(spelling)

    def spell(self, ipa: str) -> str:
        """Spell one house-IPA phone in this notation."""
        spelling = self._speller(ipa)
        read = self.read(spelling)
        if read == ipa or ipa in self.collapses.get(spelling, ()):
            return spelling
        raise ValueError(
            f"cannot spell {ipa!r} in {self.name}: {spelling!r} reads as "
            f"{read!r}; would accept {read!r}"
        )


@dataclass(frozen=True)
class Inventory:
    """A named notation and, where finite, the phones it carries."""

    name: str
    style: Style
    phones: Phoneset | None
    provenance: str
    version: str | None = None
    refusals: dict[str, str] = field(default_factory=dict)


def _one_ipa(spelling: str) -> str:
    from .form import Form

    Form.parse(spelling, strict=True)
    return spelling


def _wild(spelling: str) -> str:
    from .features import IPAFeatures

    return _one_ipa(IPAFeatures().from_wild(spelling))


def _inventory_phones(phones: list[str], name: str) -> Phoneset:
    """Build a finite sound inventory under the phoneset-file silence rule."""
    from .models import _silence_spellings

    silence = _silence_spellings()
    return Phoneset.from_list(
        list(dict.fromkeys(phone for phone in phones if phone not in silence)), name
    )


def _bridge_inventory(name: str, bridge: VocabularyBridge) -> Inventory:
    """Build in XML atom order; choose spellings by union ranking rules."""
    from .features import IPAFeatures
    from .phoneset_map import tie_delimited_entry

    features = IPAFeatures()
    phones = []
    outputs: dict[str, list[str]] = defaultdict(list)
    inputs: dict[str, set[str]] = defaultdict(set)
    declaration_counts: dict[str, int] = defaultdict(int)
    for atom in bridge.atoms:
        if atom.kind != "unit":
            continue
        phone = tie_delimited_entry(atom.spelling, features)
        if len(features.segments(phone)) == 1:
            phones.append(phone)
            outputs[phone].append(atom.output)
            inputs[atom.output].add(phone)
            declaration_counts[atom.output] += 1
    phones = list(dict.fromkeys(phones))

    def read(spelling: str) -> str:
        try:
            meanings = inputs[spelling]
        except KeyError as error:
            raise ValueError(f"cannot read {spelling!r} as one {name} phone") from error
        if len(meanings) != 1:
            raise ValueError(f"cannot read {spelling!r} as one {name} phone")
        return next(iter(meanings))

    def spell(ipa: str) -> str:
        try:
            names = outputs[ipa]
        except KeyError as error:
            raise ValueError(f"cannot spell {ipa!r} as one {name} phone") from error
        return min(
            names,
            key=lambda value: (-declaration_counts[value], len(value), value),
        )

    return Inventory(
        name,
        Style(name, read, spell),
        _inventory_phones(phones, name),
        bridge.provenance,
    )


def _cmu_inventory(name: str) -> Inventory:
    from ._cmu_graph import BASE_CMUDICT, POCKETSPHINX
    from .mapper import CMUMapper

    dialect = {d.name: d for d in (BASE_CMUDICT, POCKETSPHINX)}[name]
    mapper = CMUMapper()

    def read(spelling: str) -> str:
        if not dialect.preserves_stress and spelling[-1:].isdigit():
            raise ValueError(f"stress is not accepted by {name}: {spelling}")
        result = mapper.cmu_to_ipa([spelling], strict=True)
        _one_ipa(result)
        from .features import IPAFeatures

        if len(IPAFeatures().segments(result)) != 1:
            raise ValueError(f"cannot read {spelling!r} as one {name} phone")
        return result

    def spell(ipa: str) -> str:
        symbols = mapper.ipa_to_cmu(
            ipa,
            with_stress=dialect.preserves_stress and ipa[:1] in {"ˈ", "ˌ"},
            strict=True,
        )
        if len(symbols) != 1:
            raise ValueError(f"cannot spell {ipa!r} as one {name} phone")
        return symbols[0]

    phones = list(mapper._ipa_to_cmu)  # XML row order is the declaration order.
    assert set(phones) == mapper.get_ipa_phones(include_extras=False)
    grouped: dict[str, list[str]] = defaultdict(list)
    for phone in phones:
        grouped[spell(phone)].append(phone)
    collapses = {
        spelling: tuple(members)
        for spelling, members in grouped.items()
        if len(members) > 1
    }
    return Inventory(
        name,
        Style(name, read, spell, collapses),
        _inventory_phones(phones, name),
        f"CMU ARPAbet ({dialect.purpose}) from cmu.xml",
    )


def _timit_inventory() -> Inventory:
    from .phonemaps import _load_phonemap, from_phonemap, to_phonemap

    ipa_to_timit, _ = _load_phonemap("timit")

    def read(spelling: str) -> str:
        result = from_phonemap([spelling], "timit", strict=True)
        _one_ipa(result)
        from .features import IPAFeatures

        if len(IPAFeatures().segments(result)) != 1:
            raise ValueError(f"cannot read {spelling!r} as one timit phone")
        return result

    def spell(ipa: str) -> str:
        symbols = to_phonemap(ipa, "timit", strict=True)
        if len(symbols) != 1:
            raise ValueError(f"cannot spell {ipa!r} as one timit phone")
        return symbols[0]

    from .features import IPAFeatures
    from .phoneset_map import tie_delimited_entry

    features = IPAFeatures()
    phones = [
        tied
        for phone in ipa_to_timit
        if len(features.segments(tied := tie_delimited_entry(phone, features))) == 1
    ]
    return Inventory(
        "timit",
        Style("timit", read, spell),
        _inventory_phones(list(dict.fromkeys(phones)), "timit"),
        "TIMIT phonemap declaration",
    )


def inventories() -> tuple[str, ...]:
    """Return names discovered from the shipped declarations."""
    return tuple(sorted(_registry()))


def _disagreement(
    direction: str, value: str, declarations: dict[str, frozenset[str]]
) -> ValueError:
    details = ", ".join(
        f"{language}={','.join(sorted(spellings))!r}"
        for language, spellings in sorted(declarations.items())
    )
    return ValueError(
        f"cannot {direction} {value!r} in espeak: declarations do not give one phone "
        f"({details}); select espeak:<code>"
    )


@functools.lru_cache(maxsize=1)
def _espeak_inventory() -> Inventory:
    """Build the cross-language eSpeak name union and agreement-only style.

    It reads a name only where every declaration carrying it agrees. It spells
    with an agreed name, preferring the name carried by the most declarations,
    then the shortest, then the lexically first.
    """
    from . import normalize
    from .bridges.espeak import EspeakBridge
    from .features import IPAFeatures
    from .models import _silence_spellings
    from .phoneset_map import tie_delimited_entry

    features = IPAFeatures()
    silence = _silence_spellings()
    by_name_mutable: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    by_phone_mutable: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    phones: list[str] = []
    for declaration in sorted(_ESPEAK.glob("*.xml")):
        language = declaration.stem
        bridge = EspeakBridge(language)
        for atom in bridge.atoms:
            if atom.kind != "unit":
                continue
            phone = normalize(tie_delimited_entry(atom.spelling, features))
            if len(features.segments(phone)) != 1 or phone in silence:
                continue
            phones.append(phone)
            by_name_mutable[atom.output][language].add(phone)
            by_phone_mutable[phone][language].add(atom.output)
    by_name = {
        name: {
            language: frozenset(declared) for language, declared in declarations.items()
        }
        for name, declarations in by_name_mutable.items()
    }
    by_phone = {
        phone: {language: frozenset(names) for language, names in declarations.items()}
        for phone, declarations in by_phone_mutable.items()
    }

    def read(spelling: str) -> str:
        try:
            declarations = by_name[spelling]
        except KeyError as error:
            raise ValueError(f"cannot read {spelling!r} as one espeak phone") from error
        values = {value for declared in declarations.values() for value in declared}
        if len(values) != 1:
            raise _disagreement("read", spelling, declarations)
        return next(iter(values))

    def spell(ipa: str) -> str:
        try:
            declarations = by_phone[ipa]
        except KeyError as error:
            raise ValueError(f"cannot spell {ipa!r} as one espeak phone") from error
        candidates = {name for names in declarations.values() for name in names}
        agreed = []
        for name in candidates:
            meanings = {
                phone for declared in by_name[name].values() for phone in declared
            }
            if meanings == {ipa}:
                agreed.append(name)
        if agreed:
            return min(
                agreed,
                key=lambda name: (-len(by_name[name]), len(name), name),
            )
        details = "; ".join(
            f"candidate {name!r}: "
            + ", ".join(
                f"espeak:{language}={','.join(sorted(declared))!r}"
                for language, declared in sorted(by_name[name].items())
            )
            for name in sorted(candidates)
        )
        raise ValueError(
            f"cannot spell {ipa!r} in espeak: no unambiguous name "
            f"({details}); select espeak:<code>"
        )

    return Inventory(
        "espeak",
        Style("espeak", read, spell),
        _inventory_phones(sorted(set(phones)), "espeak"),
        "Union across every shipped eSpeak NG 1.52.0 declaration; its names "
        "are the vocabulary emitted by wav2vec2 eSpeak phoneme recognizers",
    )


def _ipa_inventory() -> Inventory:
    """Build the finite house-IPA inventory in declaration order."""
    from .features import IPAFeatures

    ipa = IPAFeatures()
    return Inventory(
        "ipa",
        Style("ipa", _one_ipa, lambda value: value),
        _inventory_phones(list(ipa.phones), "ipa"),
        "ipakit house IPA declaration",
    )


def _wild_inventory() -> Inventory:
    return Inventory(
        "wild",
        Style("wild", _wild, lambda value: value),
        None,
        "ipakit soft IPA reader",
    )


@functools.cache
def _mfa_bridge(declaration: str) -> VocabularyBridge:
    """Load one MFA declaration once; the generated union is relatively large."""
    from .bridges.mfa import MFABridge

    return MFABridge(declaration)


@functools.cache
def _mfa_inventory(declaration: str) -> Inventory:
    """Build an MFA inventory without changing its declared house spellings."""
    bridge = _mfa_bridge(declaration)
    by_output = {atom.output: atom.spelling for atom in bridge.atoms}
    by_spelling = {atom.spelling: atom.output for atom in bridge.atoms}
    name = bridge.name

    def read(spelling: str) -> str:
        try:
            return by_output[spelling]
        except KeyError as error:
            raise ValueError(f"cannot read {spelling!r} as one {name} phone") from error

    def spell(ipa: str) -> str:
        try:
            return by_spelling[ipa]
        except KeyError as error:
            raise ValueError(f"cannot spell {ipa!r} as one {name} phone") from error

    return Inventory(
        name,
        Style(name, read, spell),
        _inventory_phones([atom.spelling for atom in bridge.atoms], name),
        bridge.provenance,
        bridge.version,
        {item.spelling: item.reason for item in bridge.refusals},
    )


def _espeak_language_inventory(code: str) -> Inventory:
    from .bridges.espeak import EspeakBridge

    name = f"espeak:{code}"
    return _bridge_inventory(name, EspeakBridge(code))


@functools.lru_cache(maxsize=1)
def _registry() -> dict[str, tuple[Callable[[], Inventory], str]]:
    """Return the one registry table used for listing and loading."""
    import xml.etree.ElementTree as ET

    from ._cmu_graph import BASE_CMUDICT
    from .bridges.mfa import UNION, declarations

    registry: dict[str, tuple[Callable[[], Inventory], str]] = {
        "ipa": (_ipa_inventory, "ipakit house IPA declaration"),
        "wild": (_wild_inventory, "ipakit soft IPA reader"),
        "cmudict": (
            functools.partial(_cmu_inventory, "cmudict"),
            f"CMU ARPAbet ({BASE_CMUDICT.purpose}) from cmu.xml",
        ),
        "pocketsphinx": (
            functools.partial(_cmu_inventory, "pocketsphinx"),
            "CMUdict phone set; PocketSphinx stress handling from cmu.xml",
        ),
        "espeak": (
            _espeak_inventory,
            "Union across every shipped eSpeak NG 1.52.0 declaration; its names "
            "are the vocabulary emitted by wav2vec2 eSpeak phoneme recognizers",
        ),
    }
    for declaration in (UNION, *declarations()):
        path = _DATA / "bridges" / "mfa" / f"{declaration}.xml"
        root = ET.parse(path).getroot()
        name = root.attrib["name"]
        registry[name] = (
            functools.partial(_mfa_inventory, declaration),
            root.attrib["provenance"],
        )
    if (_PHONEMAPS / "timit.xml").is_file():
        registry["timit"] = (_timit_inventory, "TIMIT phonemap declaration")
    for path in sorted(_ESPEAK.glob("*.xml")):
        code = path.stem
        name = f"espeak:{code}"
        registry[name] = (
            functools.partial(_espeak_language_inventory, code),
            ET.parse(path).getroot().attrib["provenance"],
        )
    return registry


def inventory(name: str) -> Inventory:
    """Load a named inventory, refusing an absent declaration."""
    registry = _registry()
    try:
        builder, provenance = registry[name]
    except KeyError as error:
        if name.startswith("mfa:"):
            from .bridges.mfa import declarations

            raise ValueError(
                f"no shipped inventory {name!r}; have mfa:<name> "
                f"({', '.join(declarations())})"
            ) from error
        ordinary = [
            member for member in sorted(registry) if not member.startswith("espeak:")
        ]
        languages = sum(member.startswith("espeak:") for member in registry)
        raise ValueError(
            f"no shipped inventory {name!r}; have {', '.join(ordinary)}, "
            f"espeak:<code> ({languages} languages); see 'ipakit inventory list'"
        ) from error
    item = builder()
    if item.name != name:
        raise ValueError(f"inventory builder for {name!r} returned {item.name!r}")
    if item.provenance != provenance:
        return Inventory(
            item.name,
            item.style,
            item.phones,
            provenance,
            item.version,
            item.refusals,
        )
    return item


__all__ = ["Inventory", "Style", "inventories", "inventory"]
