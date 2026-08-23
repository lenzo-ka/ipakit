"""CMUdict-family graph profiles and development corpus adapter."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

from tiergraph.build import document
from tiergraph.build import item as graph_item

import tiergraph as tg

_MAP = Path(__file__).parent / "data" / "phonemaps" / "cmu.xml"


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


_NAMESPACE = "urn:ipakit:cmu"


def declarations() -> tuple[tg.AttributeDeclaration, ...]:
    """Return the native declarations for authoritative CMU item facts."""
    return tuple(
        tg.AttributeDeclaration(
            tg.QualifiedName(_NAMESPACE, name),
            tg.AttributeDomain.ITEM,
            tg.XsdType.STRING,
        )
        for name in ("phone", "stress")
    )


def read(tokens: Iterable[str], dialect: CMUDialect = BASE_CMUDICT) -> tg.Graph:
    """Build a faithful native graph from already-tokenized phones."""
    stress_values = _stress_values()
    items = []
    for token in tokens:
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
        items.append(
            graph_item(phone=phone)
            if stress is None
            else graph_item(phone=phone, stress=stress)
        )

    builder = document(_NAMESPACE, prefix="cmu")
    for declaration in declarations():
        builder.attribute(
            declaration.name,
            declaration.value_type,
            domain=declaration.domain,
        )
    builder.tier(
        "phone",
        items,
        item_type="phone",
        membership="phone-members",
    )
    return builder.build()


def render(graph: tg.Graph, dialect: CMUDialect = BASE_CMUDICT) -> tuple[str, ...]:
    reverse = {value: key for key, value in _stress_values().items()}
    result = []
    for tier in graph.tiers:
        if tier.declaration.name.local_name != "phone":
            continue
        for phone_item in tier.items:
            attributes = {
                value.name.local_name: value.lexical for value in phone_item.attributes
            }
            stress = attributes.get("stress")
            result.append(
                attributes["phone"]
                + (
                    reverse[stress]
                    if dialect.preserves_stress and stress is not None
                    else ""
                )
            )
    return tuple(result)


def projection_losses(
    graph: tg.Graph, dialect: CMUDialect
) -> tuple[ProjectionLoss, ...]:
    if dialect.preserves_stress:
        return ()
    if any(
        value.name.local_name == "stress"
        for tier in graph.tiers
        for graph_item in tier.items
        for value in graph_item.attributes
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
