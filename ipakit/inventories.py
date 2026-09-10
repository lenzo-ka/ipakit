"""Named finite phone inventories and the notations that spell them."""

from __future__ import annotations

import functools
import xml.etree.ElementTree as ET
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from ._provenance import SourceMetadata
from .models import Phoneset

if TYPE_CHECKING:
    from .bridges.vocabulary import VocabularyBridge
    from .features import IPAFeatures

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
    separator: str | None = None

    def read(self, spelling: str) -> str:
        """Read one external spelling as house IPA."""
        from . import normalize

        return self._reader(normalize(spelling))

    def spell(self, ipa: str) -> str:
        """Spell one house-IPA phone in this notation."""
        from . import normalize

        ipa = normalize(ipa)
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
    counts: dict[str, dict[str, int]] = field(default_factory=dict)
    dropped: dict[str, dict[str, int]] = field(default_factory=dict)
    source: SourceMetadata | None = None


def _source(path: Path) -> SourceMetadata:
    """Read structured source metadata from a declaration root."""
    return SourceMetadata.from_root(ET.parse(path).getroot(), path)


def _declared_inventory(
    name: str,
    style: Style,
    phones: Phoneset | None,
    source: SourceMetadata,
    refusals: dict[str, str] | None = None,
) -> Inventory:
    """Build an inventory whose prose provenance has one declared source."""
    return Inventory(
        name,
        style,
        phones,
        source.provenance,
        source.version,
        refusals or {},
        source=source,
    )


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
    from . import normalize
    from .features import IPAFeatures
    from .phoneset_map import tie_delimited_entry

    source = bridge.source
    if source is None:
        raise ValueError(f"{bridge.name} has no structured source metadata")
    features = IPAFeatures()
    phones = []
    outputs: dict[str, list[str]] = defaultdict(list)
    inputs: dict[str, set[str]] = defaultdict(set)
    declaration_counts: dict[str, int] = defaultdict(int)
    for atom in bridge.atoms:
        if atom.kind != "unit":
            continue
        phone = normalize(tie_delimited_entry(atom.spelling, features))
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

    return _declared_inventory(
        name,
        Style(name, read, spell, separator=bridge.separator or None),
        _inventory_phones(phones, name),
        source,
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
    return _declared_inventory(
        name,
        Style(name, read, spell, collapses, " "),
        _inventory_phones(phones, name),
        _source(_PHONEMAPS / "cmu.xml"),
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
    return _declared_inventory(
        "timit",
        Style("timit", read, spell),
        _inventory_phones(list(dict.fromkeys(phones)), "timit"),
        _source(_PHONEMAPS / "timit.xml"),
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
def _espeak_source() -> SourceMetadata:
    """Derive the union's source identity from every language declaration."""
    sources = [_source(path) for path in sorted(_ESPEAK.glob("*.xml"))]
    if not sources:
        raise ValueError("the eSpeak inventory has no declarations")
    common = {
        field: {getattr(source, field) for source in sources}
        for field in ("upstream", "upstream_url", "version", "license", "kind")
    }
    disagreements = {
        field: values for field, values in common.items() if len(values) != 1
    }
    if disagreements:
        raise ValueError(
            f"eSpeak declarations disagree on source metadata: {disagreements}"
        )
    first = sources[0]
    return SourceMetadata(
        first.upstream,
        first.upstream_url,
        f"union of {len(sources)} declared {first.kind} artifacts",
        first.version,
        first.license,
        first.kind,
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

    return _declared_inventory(
        "espeak",
        Style("espeak", read, spell),
        _inventory_phones(sorted(set(phones)), "espeak"),
        _espeak_source(),
    )


def _ipa_inventory() -> Inventory:
    """Build the finite house-IPA inventory in declaration order."""
    from .features import IPAFeatures

    ipa = IPAFeatures()
    return _declared_inventory(
        "ipa",
        Style("ipa", _one_ipa, lambda value: value),
        _inventory_phones(list(ipa.phones), "ipa"),
        _source(_DATA / "ipa.xml"),
    )


def _wild_inventory() -> Inventory:
    return _declared_inventory(
        "wild",
        Style("wild", _wild, lambda value: value),
        None,
        _source(_DATA / "ipa.xml"),
    )


@functools.cache
def _mfa_bridge(declaration: str, ipa: IPAFeatures | None = None) -> VocabularyBridge:
    """Load one MFA declaration once; the generated union is relatively large."""
    from .bridges.mfa import MFABridge

    return MFABridge(declaration, ipa=ipa)


@functools.cache
def _mfa_inventory(declaration: str, ipa: IPAFeatures | None = None) -> Inventory:
    """Build an MFA inventory with canonically normalized house spellings."""
    from . import normalize

    bridge = _mfa_bridge(declaration, ipa)
    source = bridge.source
    if source is None:
        raise ValueError(f"{bridge.name} has no structured source metadata")
    by_output = {atom.output: normalize(atom.spelling) for atom in bridge.atoms}
    by_spelling = {normalize(atom.spelling): atom.output for atom in bridge.atoms}
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

    return _declared_inventory(
        name,
        Style(name, read, spell, separator=""),
        _inventory_phones([normalize(atom.spelling) for atom in bridge.atoms], name),
        source,
        {item.spelling: item.reason for item in bridge.refusals},
    )


def _espeak_language_inventory(code: str) -> Inventory:
    from .bridges.espeak import EspeakBridge

    name = f"espeak:{code}"
    return _bridge_inventory(name, EspeakBridge(code))


@functools.lru_cache(maxsize=1)
def _registry() -> dict[str, tuple[Callable[[], Inventory], SourceMetadata]]:
    """Return the one registry table used for listing and loading."""
    from .bridges.mfa import UNION, declarations

    ipa_source = _source(_DATA / "ipa.xml")
    cmu_source = _source(_PHONEMAPS / "cmu.xml")
    registry: dict[str, tuple[Callable[[], Inventory], SourceMetadata]] = {
        "ipa": (_ipa_inventory, ipa_source),
        "wild": (_wild_inventory, ipa_source),
        "cmudict": (
            functools.partial(_cmu_inventory, "cmudict"),
            cmu_source,
        ),
        "pocketsphinx": (
            functools.partial(_cmu_inventory, "pocketsphinx"),
            cmu_source,
        ),
        "espeak": (_espeak_inventory, _espeak_source()),
    }
    for declaration in (UNION, *declarations()):
        path = _DATA / "bridges" / "mfa" / f"{declaration}.xml"
        root = ET.parse(path).getroot()
        name = root.attrib["name"]
        registry[name] = (
            functools.partial(_mfa_inventory, declaration),
            SourceMetadata.from_root(root, path),
        )
    if (_PHONEMAPS / "timit.xml").is_file():
        registry["timit"] = (_timit_inventory, _source(_PHONEMAPS / "timit.xml"))
    for path in sorted(_ESPEAK.glob("*.xml")):
        code = path.stem
        name = f"espeak:{code}"
        registry[name] = (
            functools.partial(_espeak_language_inventory, code),
            _source(path),
        )
    return registry


def inventory(name: str, *, ipa: IPAFeatures | None = None) -> Inventory:
    """Load a named inventory, refusing an absent declaration."""
    registry = _registry()
    try:
        builder, source = registry[name]
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
    if ipa is not None and (name == "mfa" or name.startswith("mfa:")):
        from .bridges.mfa import UNION

        declaration = UNION if name == "mfa" else name.removeprefix("mfa:")
        item = _mfa_inventory(declaration, ipa)
    else:
        item = builder()
    if item.name != name:
        raise ValueError(f"inventory builder for {name!r} returned {item.name!r}")
    if item.source != source:
        return Inventory(
            item.name,
            item.style,
            item.phones,
            source.provenance,
            source.version,
            item.refusals,
            item.counts,
            item.dropped,
            source,
        )
    return item


def inventory_from_dictionary(
    path: Path,
    style: str | Style,
    *,
    name: str | None = None,
    ipa: IPAFeatures | None = None,
    min_entries: int | None = None,
    refuse_unreadable: bool = False,
) -> Inventory:
    """Derive a counted finite inventory from a pronunciation dictionary.

    Marker-only MFA placeholders are reported on the returned inventory unless
    ``refuse_unreadable`` requests the strict unreadable-token behavior.
    """
    if min_entries is not None and min_entries < 1:
        raise ValueError("min_entries must be at least 1")
    selected = inventory(style).style if isinstance(style, str) else style
    if ipa is not None and selected.name in {"ipa", "wild"}:
        from .form import Form

        def read_house(spelling: str) -> str:
            Form.parse(spelling, features=ipa, strict=True)
            return spelling

        selected = (
            Style("ipa", read_house, lambda value: value)
            if selected.name == "ipa"
            else Style(
                "wild",
                lambda spelling: read_house(ipa.from_wild(spelling)),
                lambda value: value,
            )
        )
    supported = "cmudict, pocketsphinx, mfa, mfa:<name>, ipa, wild"
    placeholder_pronunciation: Callable[[tuple[str, ...]], bool] | None = None
    if selected.name in {"cmudict", "pocketsphinx"}:
        from ._corpus_cmudict import read_cmudict_dictionary_line

        def read_line(line: str) -> tuple[str, tuple[str, ...]] | None:
            entry = read_cmudict_dictionary_line(line)
            return None if entry is None else (entry.word, entry.phones)

    elif selected.name == "mfa" or selected.name.startswith("mfa:"):
        from .bridges.mfa import MFABridge

        placeholder_pronunciation = MFABridge.is_placeholder_pronunciation

        def read_line(line: str) -> tuple[str, tuple[str, ...]] | None:
            if not line.strip() or line.lstrip().startswith("#"):
                return None
            word, spellings, _ = MFABridge.split_dictionary_line(line)
            return word, spellings

    elif selected.name in {"ipa", "wild"}:

        def read_line(line: str) -> tuple[str, tuple[str, ...]] | None:
            content = line.strip()
            if not content:
                return None
            fields = content.split()
            if len(fields) < 2:
                raise ValueError("expected a headword and one or more phones")
            return fields[0], tuple(fields[1:])

    else:
        raise ValueError(
            f"style {selected.name!r} has no pronunciation-dictionary reader; "
            f"would accept {supported}"
        )

    phones: list[str] = []
    token_counts: dict[str, int] = defaultdict(int)
    entry_counts: dict[str, int] = defaultdict(int)
    refusals: dict[str, str] = {}
    source = Path(path)
    from .models import _silence_spellings

    silence = _silence_spellings()
    try:
        with source.open(encoding="utf-8") as stream:
            for line_number, raw in enumerate(stream, 1):
                line = raw.rstrip("\r\n")
                try:
                    parsed = read_line(line)
                except (UnicodeError, ValueError) as error:
                    raise ValueError(
                        f"cannot read dictionary line {line_number} in {source}: "
                        f"entry {line!r}: {error}"
                    ) from error
                if parsed is None:
                    continue
                entry, spellings = parsed
                if (
                    not refuse_unreadable
                    and placeholder_pronunciation is not None
                    and placeholder_pronunciation(spellings)
                ):
                    markers = " ".join(spellings)
                    refusals[entry] = (
                        f"dictionary line {line_number}: placeholder pronunciation "
                        f"consists entirely of non-phone MFA aligner markers: {markers!r}"
                    )
                    continue
                entry_phones: list[str] = []
                for spelling in spellings:
                    if spelling in silence:
                        continue
                    try:
                        phone = selected.read(spelling)
                    except ValueError as error:
                        raise ValueError(
                            f"cannot read dictionary line {line_number} in {source}: "
                            f"entry {entry!r}, phone {spelling!r}: {error}"
                        ) from error
                    phones.append(phone)
                    entry_phones.append(phone)
                    token_counts[phone] += 1
                for phone in dict.fromkeys(entry_phones):
                    entry_counts[phone] += 1
    except OSError as error:
        raise ValueError(
            f"cannot read pronunciation dictionary {source}: {error}"
        ) from error
    inventory_name = name or source.stem
    counts = {
        phone: {"entries": entry_counts[phone], "tokens": token_counts[phone]}
        for phone in dict.fromkeys(phones)
    }
    dropped = {
        phone: dict(count)
        for phone, count in counts.items()
        if min_entries is not None and count["entries"] < min_entries
    }
    return Inventory(
        inventory_name,
        selected,
        _inventory_phones(
            [phone for phone in phones if phone not in dropped], inventory_name
        ),
        f"Pronunciation dictionary {source} read as {selected.name}",
        refusals=refusals,
        counts=counts,
        dropped=dropped,
    )


__all__ = [
    "Inventory",
    "Style",
    "inventories",
    "inventory",
    "inventory_from_dictionary",
]
