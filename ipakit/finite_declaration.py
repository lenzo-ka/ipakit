"""The existing ternary XML codec, shared by finite operations and scoring."""

from __future__ import annotations

import math
import unicodedata
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import dataclass, field
from os import PathLike
from typing import cast

from ._provenance import SourceMetadata
from .bridges.base import Bridge, Fidelity, RoundTripLeg, RoundTripReport
from .finite_model import FeatureSchema, FiniteModel


@dataclass(frozen=True)
class TernaryDeclaration:
    """Codec metadata is separate from the model's feature/inventory identity.

    Weight order is retained even when it is not a complete feature basis.
    The directional bridge labels are legacy metadata, not a required pivot.
    """

    model: FiniteModel
    weights: tuple[float, ...]
    weight_names: tuple[str, ...]
    bridge: Bridge
    _ordered: tuple[str, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "weights", tuple(self.weights))
        object.__setattr__(self, "weight_names", tuple(self.weight_names))
        object.__setattr__(
            self, "_ordered", tuple(sorted(self.model.rows, key=len, reverse=True))
        )

    @property
    def vectors(self) -> Mapping[str, tuple[int | None, ...]]:
        """Ternary values guaranteed by this codec's validation."""
        return cast(Mapping[str, tuple[int | None, ...]], self.model.rows)

    def tokenize(self, word: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """NFD longest match with explicit unrecognized material."""
        remaining = unicodedata.normalize("NFD", word)
        tokens: list[str] = []
        dropped: list[str] = []
        while remaining:
            token = next(
                (item for item in self._ordered if remaining.startswith(item)), None
            )
            if token is None:
                dropped.append(remaining[0])
                remaining = remaining[1:]
            else:
                tokens.append(token)
                remaining = remaining[len(token) :]
        return tuple(tokens), tuple(dropped)


def read_ternary_declaration(path: str | PathLike[str]) -> TernaryDeclaration:
    """Read and validate a declaration without choosing a scoring family."""
    root = ET.parse(path).getroot()
    round_trip = root.find("round-trip")
    if round_trip is None:
        raise ValueError("a feature declaration requires a round-trip classification")
    external = round_trip.find("external-to-house")
    house = round_trip.find("house-to-external")
    if external is None or house is None:
        raise ValueError("a feature declaration must classify both directions")

    def leg(element: ET.Element, direction: str) -> RoundTripLeg:
        try:
            fidelity = Fidelity(element.attrib["fidelity"])
        except KeyError as error:
            raise ValueError(f"{direction} requires a fidelity") from error
        return RoundTripLeg(
            direction,
            fidelity,
            tuple(item.attrib["name"] for item in element.findall("drop")),
            tuple(item.attrib["name"] for item in element.findall("trick")),
        )

    identity = root.get("name", "declared")
    source = SourceMetadata.from_root(root, path)
    bridge = Bridge(
        identity,
        source.version,
        source.provenance,
        RoundTripReport(
            leg(external, "external-to-house"),
            leg(house, "house-to-external"),
        ),
        source,
    )
    feature_block = root.find("features")
    segment_block = root.find("segments")
    if feature_block is None or segment_block is None:
        raise ValueError("a feature declaration requires features and segments blocks")
    if any(not item.get("name") for item in feature_block.findall("feature")):
        raise ValueError("every declared feature requires a nonempty name")
    features = tuple(
        name
        for item in feature_block.findall("feature")
        if (name := item.get("name")) is not None
    )
    if len(set(features)) != len(features):
        raise ValueError("duplicate feature names")
    if not features:
        raise ValueError("a feature declaration must declare at least one feature")

    vectors: dict[str, tuple[int | None, ...]] = {}
    for item in segment_block:
        name = item.get("name")
        if not name:
            raise ValueError("every declared segment requires a name")
        normalized = unicodedata.normalize("NFD", name)
        if normalized != name:
            raise ValueError(f"segment key is not NFD: {name!r}")
        if normalized in vectors:
            raise ValueError(f"duplicate segment key: {normalized!r}")
        unknown = set(item.attrib) - {"name", *features}
        if unknown:
            raise ValueError(f"undeclared row features: {sorted(unknown)!r}")
        values: list[int | None] = []
        for feature in features:
            raw = item.get(feature)
            if raw not in {None, "-", "0", "+"}:
                raise ValueError(
                    f"segment {name!r} feature {feature!r} is not ternary: {raw!r}"
                )
            values.append(None if raw is None else {"-": -1, "0": 0, "+": 1}[raw])
        vectors[normalized] = tuple(values)

    weights_block = root.find("weights")
    weight_items = tuple(weights_block) if weights_block is not None else ()
    declared_weights: list[float] = []
    for index, item in enumerate(weight_items):
        feature = item.get("name") or (
            features[index] if index < len(features) else f"weight[{index}]"
        )
        raw_weight = item.get("value")
        try:
            weight = float(raw_weight) if raw_weight is not None else math.nan
        except ValueError as error:
            raise ValueError(
                f"weight for feature {feature!r} is not numeric: {raw_weight!r}"
            ) from error
        if not math.isfinite(weight) or weight < 0.0:
            raise ValueError(
                f"weight for feature {feature!r} must be non-negative and finite; "
                f"got {raw_weight!r}"
            )
        declared_weights.append(weight)

    model = FiniteModel(
        identity,
        FeatureSchema({feature: (-1, 0, 1) for feature in features}),
        vectors,
        source,
    )
    names = tuple(
        item.get("name")
        or (features[index] if index < len(features) else f"weight[{index}]")
        for index, item in enumerate(weight_items)
    )
    return TernaryDeclaration(model, tuple(declared_weights), names, bridge)
