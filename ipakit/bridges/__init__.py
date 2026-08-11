"""Bidirectional, fidelity-classified bridges to external representations."""

from .base import Bridge, Fidelity, RoundTripLeg, RoundTripReport
from .espeak import ESPEAK_EN, EspeakBridge
from .generator import GeneratorDoor
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
    "ESPEAK_EN",
    "EspeakBridge",
    "Fidelity",
    "GeneratorDoor",
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
