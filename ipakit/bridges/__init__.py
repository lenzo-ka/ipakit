"""Bidirectional, fidelity-classified bridges to external representations."""

from .base import Bridge, Fidelity, RoundTripLeg, RoundTripReport
from .generator import GeneratorDoor
from .ipa_dict import (
    IPADictEntry,
    IPADictPronunciation,
    IPADictProvenance,
    IPADictReader,
    IPADictReadReport,
    IPADictRefusal,
)
from .notation import NotationBridge
from .provider import ProviderBridge
from .vocabulary import (
    Atom,
    ProjectionDrop,
    ProjectionReport,
    VocabularyBridge,
    VocabularyProjection,
    VocabularyResidueError,
)

__all__ = [
    "Atom",
    "Bridge",
    "Fidelity",
    "GeneratorDoor",
    "IPADictEntry",
    "IPADictPronunciation",
    "IPADictProvenance",
    "IPADictReader",
    "IPADictReadReport",
    "IPADictRefusal",
    "NotationBridge",
    "ProviderBridge",
    "ProjectionDrop",
    "ProjectionReport",
    "RoundTripLeg",
    "RoundTripReport",
    "VocabularyBridge",
    "VocabularyProjection",
    "VocabularyResidueError",
]
