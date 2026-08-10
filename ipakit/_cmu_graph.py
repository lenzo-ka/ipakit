"""CMUdict-family graph profiles and development corpus adapter."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

from ._tiergraph import Declarations, FeatureDeclaration, Graph, TierDeclaration
from ._tiergraph_builder import GraphBuilder

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
    stress: dict[str, frozenset[str]] = {}
    symbols: set[str] = set()
    for item in root.findall("map"):
        symbol = item.get("cmu")
        if symbol is not None:
            symbols.add(symbol)
            stress[symbol] = frozenset(item.get("stress", "").split())
    return frozenset(symbols), stress


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


def declarations() -> Declarations:
    features = (FeatureDeclaration("phone"), FeatureDeclaration("stress"))
    return Declarations(
        (TierDeclaration("phone", frozenset(f.name for f in features)),), features, ()
    )


def read(tokens: Iterable[str], dialect: CMUDialect = BASE_CMUDICT) -> Graph:
    """Construct through the canonical builder from already-tokenized phones."""
    builder = GraphBuilder(declarations())
    stress_values = _stress_values()
    for token in tokens:
        digit = token[-1:] if token[-1:].isdigit() else ""
        phone = token[:-1] if digit else token
        if phone not in dialect.inventory and phone not in dialect.boundaries:
            raise ValueError(f"undeclared {dialect.name} phone: {token}")
        facts: dict[str, str] = {"phone": phone}
        if dialect.preserves_stress:
            policy = _STRESS_POLICY.get(phone, frozenset())
            if policy and digit not in policy:
                raise ValueError(f"invalid {dialect.name} stress: {token}")
            if digit:
                facts["stress"] = stress_values[digit]
        elif digit:
            raise ValueError(f"stress is not accepted by {dialect.name}: {token}")
        builder.append_input_atom("phone", facts)
    return builder.build()


def render(graph: Graph, dialect: CMUDialect = BASE_CMUDICT) -> tuple[str, ...]:
    reverse = {value: key for key, value in _stress_values().items()}
    result = []
    for node in graph.clock:
        for group in node.groups:
            if group.tier != "phone":
                continue
            for event in group.events:
                phone = str(event.features["phone"])
                stress = event.features.get("stress")
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
        "stress" in event.features
        for node in graph.clock
        for group in node.groups
        for event in group.events
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
