"""Finite set-feature geometries, independent of a transcription provider."""

from __future__ import annotations

from collections.abc import Mapping, Set
from dataclasses import dataclass
from types import MappingProxyType

from ._identity import identity_fingerprint


class OutsideDomain(ValueError):
    """A finite feature table makes no claim about this exact key."""

    code = "outside-artifact-domain"


def jaccard(left: Set[str], right: Set[str], *, empty: float = 0.0) -> float:
    """Unweighted intersection/union; explicitly select empty-union behavior.

    The default follows CLTS, whose empty/empty similarity is zero, not one.
    It is not a claim that all users of Jaccard choose that convention.
    """
    if empty not in (0.0, 1.0):
        raise ValueError("empty-union similarity must be zero or one")
    union = left | right
    return len(left & right) / len(union) if union else empty


@dataclass(frozen=True, init=False)
class FeatureSets:
    """An immutable finite geometry; values are opaque labels, not IPA features."""

    name: str
    empty: float
    values: Mapping[str, frozenset[str]]
    identity: str

    def __init__(
        self, name: str, values: Mapping[str, Set[str]], *, empty: float = 0.0
    ) -> None:
        if not name or not values:
            raise ValueError(
                "a feature-set geometry needs a name and a nonempty domain"
            )
        copied = {}
        for key, labels in values.items():
            if not isinstance(key, str) or not key or not isinstance(labels, Set):
                raise ValueError(
                    "feature-set keys must be nonempty strings with set values"
                )
            if any(not isinstance(label, str) or not label for label in labels):
                raise ValueError("feature-set labels must be nonempty strings")
            copied[key] = frozenset(labels)
        jaccard(frozenset(), frozenset(), empty=empty)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "empty", empty)
        object.__setattr__(self, "values", MappingProxyType(copied))
        object.__setattr__(
            self,
            "identity",
            identity_fingerprint(
                {
                    "name": name,
                    "empty": empty,
                    "values": {k: sorted(v) for k, v in copied.items()},
                }
            ),
        )

    def features(self, token: str) -> frozenset[str]:
        try:
            return self.values[token]
        except KeyError:
            raise OutsideDomain(
                f"{token!r} is outside {self.name}'s finite domain"
            ) from None

    def similarity(self, left: str, right: str) -> float:
        """Look up both keys before scoring, including identical strings."""
        return jaccard(self.features(left), self.features(right), empty=self.empty)
