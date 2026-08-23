"""CMUdict-family graph profiles and development corpus adapter."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

from tiergraph.core import (
    AttributeDeclaration,
    AttributeDomain,
    AttributeValue,
    Graph,
    ItemRef,
    NamespaceDeclaration,
    QualifiedName,
    TierDeclaration,
    XsdType,
)
from tiergraph.machine import (
    AddItem,
    AttachValue,
    DeclareAttribute,
    DeclareNamespace,
    DeclareTier,
    Opcode,
    Program,
)

_MAP = Path(__file__).parent / "data" / "phonemaps" / "cmu.xml"
_NAMESPACE = "https://ipakit/cmu"
_PHONE_TIER = QualifiedName(_NAMESPACE, "phone")
_PHONE_ATTRIBUTE = QualifiedName(_NAMESPACE, "phone")
_STRESS_ATTRIBUTE = QualifiedName(_NAMESPACE, "stress")


@dataclass(frozen=True)
class CMUDialect:
    name: str
    purpose: str
    preserves_stress: bool
    silence: frozenset[str]
    boundaries: frozenset[str]
    inventory: frozenset[str]


@dataclass(frozen=True)
class ProjectionLoss:
    feature: str
    reason: str


def _inventory() -> tuple[frozenset[str], Mapping[str, frozenset[str]]]:
    root = ET.parse(_MAP).getroot()
    stress: dict[str, set[str]] = {}
    symbols: set[str] = set()
    for item in root.findall("map"):
        symbol = item.get("cmu")
        if symbol is not None:
            symbols.add(symbol)
            stress.setdefault(symbol, set()).update(item.get("stress", "").split())
    return frozenset(symbols), {
        symbol: frozenset(policy) for symbol, policy in stress.items()
    }


def _stress_values() -> Mapping[str, str]:
    from .features import IPAFeatures

    inventory = IPAFeatures()
    marked = {
        str(level): inventory.diacritics[symbol].features["stress"]
        for symbol, level in inventory.stress_markers.items()
    }
    unmarked = set(inventory.features["stress"].values) - set(marked.values())
    if len(unmarked) != 1:
        raise ValueError("CMU stress requires one unmarked prosodic value")
    return {"0": unmarked.pop(), **marked}


_SYMBOLS, _STRESS_POLICY = _inventory()
BASE_CMUDICT = CMUDialect(
    "cmudict", "tts", True, frozenset({"SIL"}), frozenset(), _SYMBOLS
)
POCKETSPHINX = CMUDialect(
    "pocketsphinx",
    "asr",
    False,
    frozenset({"SIL"}),
    frozenset({"<s>", "</s>"}),
    _SYMBOLS,
)
IPA_PROJECTION_LOSSES = (
    ProjectionLoss("vowel-quality", "AH collapses /ʌ/ and /ə/ according to stress"),
    ProjectionLoss(
        "rhotic-vowel-quality", "ER collapses /ɚ/ and /ɝ/ according to stress"
    ),
)


def declarations() -> tuple[
    NamespaceDeclaration,
    TierDeclaration,
    AttributeDeclaration,
    AttributeDeclaration,
]:
    return (
        NamespaceDeclaration("cmu", _NAMESPACE),
        TierDeclaration(_PHONE_TIER, "phone"),
        AttributeDeclaration(_PHONE_ATTRIBUTE, AttributeDomain.ITEM, XsdType.STRING),
        AttributeDeclaration(_STRESS_ATTRIBUTE, AttributeDomain.ITEM, XsdType.STRING),
    )


def read(tokens: Iterable[str], dialect: CMUDialect = BASE_CMUDICT) -> Graph:
    """Construct through the canonical machine from already-tokenized phones."""
    namespace, tier, phone_attribute, stress_attribute = declarations()
    opcodes: list[Opcode] = [
        DeclareNamespace(namespace),
        DeclareTier(tier),
        DeclareAttribute(phone_attribute),
        DeclareAttribute(stress_attribute),
    ]
    stress_values = _stress_values()
    for index, token in enumerate(tokens):
        digit = token[-1:] if token[-1:].isdigit() else ""
        phone = token[:-1] if digit else token
        if phone not in dialect.inventory and phone not in dialect.boundaries:
            raise ValueError(f"undeclared {dialect.name} phone: {token}")
        stress: str | None = None
        if dialect.preserves_stress:
            policy = _STRESS_POLICY.get(phone, frozenset())
            if (policy or digit) and digit not in policy:
                raise ValueError(f"invalid {dialect.name} stress: {token}")
            if digit:
                stress = stress_values[digit]
        elif digit:
            raise ValueError(f"stress is not accepted by {dialect.name}: {token}")
        target = ItemRef(_PHONE_TIER, index)
        opcodes.extend(
            (
                AddItem(_PHONE_TIER),
                AttachValue(
                    AttributeDomain.ITEM,
                    target,
                    AttributeValue(_PHONE_ATTRIBUTE, XsdType.STRING, phone),
                ),
            )
        )
        if stress is not None:
            opcodes.append(
                AttachValue(
                    AttributeDomain.ITEM,
                    target,
                    AttributeValue(_STRESS_ATTRIBUTE, XsdType.STRING, stress),
                )
            )
    return Program(tuple(opcodes)).unroll().graph


def render(graph: Graph, dialect: CMUDialect = BASE_CMUDICT) -> tuple[str, ...]:
    reverse = {value: key for key, value in _stress_values().items()}
    result = []
    for tier in graph.tiers:
        if tier.declaration.name != _PHONE_TIER:
            continue
        for item in tier.items:
            attributes = {value.name: value.lexical for value in item.attributes}
            phone = attributes[_PHONE_ATTRIBUTE]
            stress = attributes.get(_STRESS_ATTRIBUTE)
            result.append(
                phone
                + (
                    reverse[str(stress)]
                    if dialect.preserves_stress and stress is not None
                    else ""
                )
            )
    return tuple(result)


def projection_losses(graph: Graph, dialect: CMUDialect) -> tuple[ProjectionLoss, ...]:
    if dialect.preserves_stress:
        return ()
    if any(
        value.name == _STRESS_ATTRIBUTE
        for tier in graph.tiers
        for item in tier.items
        for value in item.attributes
    ):
        return (ProjectionLoss("stress", "target dialect has no stress notation"),)
    return ()


def corpus_entries(checkout: Path) -> Iterator[tuple[str, tuple[str, ...]]]:
    """Read a local upstream checkout; this development helper never fetches."""
    source = checkout / "cmudict.dict"
    if not source.is_file():
        source = checkout / "cmudict-0.7b"
    for line in source.read_text(encoding="latin-1").splitlines():
        if not line or line.startswith(";;;"):
            continue
        word, phones = line.split(maxsplit=1)
        yield re.sub(r"\(\d+\)$", "", word), tuple(phones.split())
