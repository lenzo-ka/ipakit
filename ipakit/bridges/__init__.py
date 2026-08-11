"""Bidirectional, fidelity-classified bridges to external representations."""

from .base import Bridge, Fidelity, RoundTripLeg, RoundTripReport
from .espeak import ESPEAK_EN, EspeakBridge
from .generator import GeneratorDoor
from .notation import NotationBridge
from .phoible import (
    PHOIBLE_ENV,
    PhoibleAudit,
    PhoibleBridge,
    PhoibleDataUnavailable,
    PhoibleEntry,
    PhoibleInventory,
    PhoibleProvenance,
    PhoibleRefusal,
    PhoibleSpread,
)
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
    "PHOIBLE_ENV",
    "PhoibleAudit",
    "PhoibleBridge",
    "PhoibleDataUnavailable",
    "PhoibleEntry",
    "PhoibleInventory",
    "PhoibleProvenance",
    "PhoibleRefusal",
    "PhoibleSpread",
    "ProviderBridge",
    "ProjectionDrop",
    "ProjectionReport",
    "RoundTripLeg",
    "RoundTripReport",
    "VocabularyBridge",
    "VocabularyProjection",
    "VocabularyResidueError",
]
