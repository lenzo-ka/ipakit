"""Common metadata and fidelity reports for external-representation bridges."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Fidelity(StrEnum):
    """The bridge contract's three round-trip classifications."""

    LOSSLESS = "lossless"
    LOSSLESS_WITH_DECLARED_TRICKS = "lossless-with-declared-tricks"
    LOSSY_WITH_REPORT = "lossy-with-report"


@dataclass(frozen=True)
class RoundTripLeg:
    direction: str
    fidelity: Fidelity
    drops: tuple[str, ...] = ()
    tricks: tuple[str, ...] = ()


@dataclass(frozen=True)
class RoundTripReport:
    external_to_house: RoundTripLeg
    house_to_external: RoundTripLeg


@dataclass(frozen=True)
class Bridge:
    """Identity, provenance, and classified fidelity shared by every bridge."""

    name: str
    version: str
    provenance: str
    round_trip: RoundTripReport
