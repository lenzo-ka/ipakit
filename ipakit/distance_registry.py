"""Explicit named cost arms over the existing exact-token alignment engine.

Custom factories own their semantic receipts and token admission. Registration
records caller assertions; it does not authenticate their provenance.
"""

from __future__ import annotations

import itertools
import json
import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from numbers import Real
from typing import Any, cast

from ._identity import identity_fingerprint
from .bridges.costmodel import (
    FAITHFUL,
    AbsentCell,
    CostPack,
    CostPolicy,
    DeclaredCostFamily,
    Segmentation,
    compare_tokens,
    house_pack,
    pack_from_ternary_declaration,
    set_feature_pack,
)
from .distance import PhoneCost, _checked_price, price
from .features import IPAFeatures
from .finite_declaration import TernaryDeclaration


def _real_price(value: float, token: str, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{label} must return a real price; got {value!r}")
    return _checked_price(value, token, label)


def _validated_prices(pack: CostPack) -> CostPack:
    """Guard callback prices before the existing fold can choose an alternative."""
    if not callable(pack.sub_cost):
        raise TypeError("sub_cost must be callable")

    def sub(left: str, right: str) -> float:
        return _real_price(pack.sub_cost(left, right), repr((left, right)), "sub_cost")

    def gap(cost: PhoneCost, label: str) -> Callable[[str], float]:
        if not callable(cost):
            _real_price(cost, "", label)

        def checked(token: str) -> float:
            return _real_price(price(cost, token), token, label)

        return checked

    return replace(
        pack,
        sub_cost=sub,
        insert_cost=gap(pack.insert_cost, "insert_cost"),
        delete_cost=gap(pack.delete_cost, "delete_cost"),
    )


def _json(value: object) -> str:
    def check(item: object) -> None:
        if isinstance(item, dict):
            if any(not isinstance(key, str) for key in item):
                raise ValueError("JSON receipt keys must be strings")
            for child in item.values():
                check(child)
        elif isinstance(item, (tuple, list)):
            for child in item:
                check(child)
        elif item is not None and type(item) not in (str, int, float, bool):
            raise ValueError("receipt values must be JSON scalars, arrays or objects")

    check(value)
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True)


@dataclass(frozen=True, init=False)
class Metric:
    """A named factory with an owned JSON configuration and content identity.

    Include all custom weights, references, transforms and cost semantics in
    config. The factory receives a fresh copy, and must return a stable CostPack
    with explicit token admission. Factories must not acquire external sources.
    """

    name: str
    inventory_identity: str
    _config: str = field(repr=False)
    factory: Callable[[dict[str, Any]], CostPack] = field(compare=False, repr=False)

    def __init__(
        self,
        name: str,
        inventory_identity: str,
        config: Mapping[str, Any],
        factory: Callable[[dict[str, Any]], CostPack],
    ) -> None:
        if not isinstance(name, str) or not name.strip() or name == "all":
            raise ValueError("metric name must be nonempty and cannot be 'all'")
        if not isinstance(inventory_identity, str) or not inventory_identity.strip():
            raise ValueError("inventory_identity must be a nonempty content identity")
        if not isinstance(config, Mapping) or not callable(factory):
            raise ValueError(
                "metric requires a JSON configuration and callable factory"
            )
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "inventory_identity", inventory_identity)
        object.__setattr__(self, "_config", _json(dict(config)))
        object.__setattr__(self, "factory", factory)

    @property
    def config(self) -> dict[str, Any]:
        """Return a detached configuration receipt."""
        return cast(dict[str, Any], json.loads(self._config))


def _error(exc: Exception) -> dict[str, str]:
    return {
        "type": type(exc).__name__,
        "code": str(getattr(exc, "code", type(exc).__name__)),
        "message": str(exc),
    }


def _tokens(tokens: Sequence[str]) -> tuple[str, ...]:
    if not isinstance(tokens, Sequence) or isinstance(tokens, (str, bytes)):
        raise ValueError("supply an explicit sequence of exact tokens, not a string")
    result = tuple(tokens)
    if any(not isinstance(token, str) or not token for token in result):
        raise ValueError("tokens must be nonempty strings")
    return result


class DistanceRegistry:
    """An ordered snapshot of caller-selected metric registrations."""

    def __init__(self, metrics: Iterable[Metric]) -> None:
        registrations = tuple(metrics)
        if any(not isinstance(metric, Metric) for metric in registrations):
            raise ValueError("registry entries must be Metric registrations")
        names = tuple(metric.name for metric in registrations)
        if len(names) != len(set(names)):
            raise ValueError("duplicate metric names")
        self._metrics = dict(zip(names, registrations, strict=True))
        # This host contributes only the existing alignment method; foreign
        # tokens are admitted solely by the selected pack's validator.
        self._host = IPAFeatures()

    @property
    def names(self) -> tuple[str, ...]:
        """Registered names in deterministic expansion order."""
        return tuple(self._metrics)

    @property
    def registrations(self) -> tuple[Metric, ...]:
        """Immutable registrations for explicit extension in a new registry."""
        return tuple(self._metrics.values())

    def _select(self, metrics: str | Sequence[str]) -> tuple[str, ...]:
        if not isinstance(metrics, (str, Sequence)) or isinstance(metrics, bytes):
            raise ValueError("metrics must be a name or an ordered name sequence")
        names = (
            self.names
            if metrics == "all"
            else ((metrics,) if isinstance(metrics, str) else tuple(metrics))
        )
        if not names or any(not isinstance(name, str) for name in names):
            raise ValueError("select at least one named metric")
        if len(names) != len(set(names)):
            raise ValueError("duplicate metric selection")
        if any(name not in self._metrics for name in names):
            raise ValueError("unknown metric; 'all' must be a standalone selector")
        return names

    def distances(
        self,
        left_tokens: Sequence[str],
        right_tokens: Sequence[str],
        *,
        metrics: str | Sequence[str] = "all",
    ) -> dict[str, Any]:
        """Compare one exact-token pair under the selected named arms."""
        return self.compare_corpus([left_tokens, right_tokens], metrics=metrics)

    def compare_corpus(
        self,
        corpus: Sequence[Sequence[str]],
        *,
        metrics: str | Sequence[str] = "all",
        all_pairs: bool = False,
    ) -> dict[str, Any]:
        """Compare adjacent pairs, or all ordered distinct corpus positions.

        Unavailable arms describe constructor failures. Refused rows describe
        input failures in an available arm. The report owns all JSON data.
        """
        names = self._select(metrics)
        if type(all_pairs) is not bool:
            raise ValueError("all_pairs must be a boolean")
        if not isinstance(corpus, Sequence) or isinstance(corpus, (str, bytes)):
            raise ValueError("corpus must contain explicit token sequences")
        frozen = tuple(_tokens(tokens) for tokens in corpus)
        if len(frozen) < 2:
            raise ValueError("a comparison corpus requires at least two sequences")
        pairs = (
            tuple(itertools.permutations(range(len(frozen)), 2))
            if all_pairs
            else tuple((index, index + 1) for index in range(len(frozen) - 1))
        )
        arms: list[dict[str, Any]] = []
        rows: list[dict[str, Any]] = []
        for name in names:
            metric = self._metrics[name]
            receipt: dict[str, Any] = {
                "name": name,
                "inventory_identity": metric.inventory_identity,
                "config": metric.config,
            }
            try:
                pack = metric.factory(metric.config)
                if not isinstance(pack, CostPack) or pack.validate_token is None:
                    raise ValueError(
                        "factory must return a CostPack with explicit token admission"
                    )
                if not isinstance(pack.policy, CostPolicy) or not callable(
                    pack.validate_token
                ):
                    raise ValueError(
                        "pack requires an actual CostPolicy and callable validator"
                    )
                if any(
                    not isinstance(label, str) or not label
                    for label in (pack.name, pack.geometry)
                ):
                    raise ValueError("pack name and geometry must be nonempty strings")
                if pack.reference is not None and not isinstance(pack.reference, str):
                    raise ValueError("pack reference must be a string or None")
                if not math.isfinite(pack.indel_ceiling) or pack.indel_ceiling <= 0:
                    raise ValueError("pack indel ceiling must be positive and finite")
                if (
                    not math.isfinite(pack.substitution_ceiling)
                    or pack.substitution_ceiling < 0
                ):
                    raise ValueError(
                        "pack substitution ceiling must be nonnegative and finite"
                    )
                pack = _validated_prices(pack)
                receipt.update(
                    pack=pack.name,
                    geometry=pack.geometry,
                    policy=pack.policy.identity,
                    reference=pack.reference,
                    substitution_ceiling=pack.substitution_ceiling,
                    indel_ceiling=pack.indel_ceiling,
                )
                arm_id = identity_fingerprint(receipt)
            except (
                ValueError,
                TypeError,
                KeyError,
                OSError,
                ImportError,
                OverflowError,
            ) as exc:
                receipt.update(
                    arm_id=identity_fingerprint(receipt),
                    status="unavailable",
                    error=_error(exc),
                )
                arms.append(receipt)
                continue
            receipt.update(arm_id=arm_id, status="available")
            arms.append(receipt)
            for left, right in pairs:
                row = {**receipt, "left": left, "right": right}
                try:
                    scored = compare_tokens(
                        self._host,
                        pack,
                        Segmentation(frozen[left]),
                        Segmentation(frozen[right]),
                    )
                    _real_price(scored.edit_cost, "alignment", "edit_cost")
                    _real_price(scored.normalized, "alignment", "normalized")
                    row.update(
                        status="scored",
                        edit_cost=scored.edit_cost,
                        normalized=scored.normalized,
                    )
                except (ValueError, KeyError, TypeError, OverflowError) as exc:
                    row.update(status="refused", error=_error(exc))
                rows.append(row)
        return cast(
            dict[str, Any],
            json.loads(
                _json(
                    {
                        "schema": "ipakit/named-distances",
                        "version": 1,
                        "selection": names,
                        "all_pairs": all_pairs,
                        "corpus": frozen,
                        "corpus_identity": identity_fingerprint(frozen),
                        "pairs": pairs,
                        "arms": arms,
                        "rows": rows,
                    }
                )
            ),
        )


def ternary_metric(
    name: str,
    declaration: TernaryDeclaration,
    *,
    policy: CostPolicy = FAITHFUL,
    family: DeclaredCostFamily = DeclaredCostFamily.SYMMETRIC_DIFFERENCE,
    absent: AbsentCell = AbsentCell.HALF_COUNTED,
) -> Metric:
    """Register a declaration with its complete weight and absence receipt.

    Factory compatibility is evaluated during binding, so an unsupported
    weighted basis remains visible as an unavailable arm.
    """

    def build(_: dict[str, Any]) -> CostPack:
        return replace(
            pack_from_ternary_declaration(
                declaration, policy, family=family, absent=absent
            ),
            validate_token=declaration.model.read,
        )

    return Metric(
        name,
        declaration.model.identity,
        {
            "version": 1,
            "policy": policy.identity,
            "input": "exact-tokens",
            "family": family.value,
            "absent": absent.value,
            "weights": declaration.weights,
            "weight_names": declaration.weight_names,
            "source": (
                declaration.model.source.to_dict()
                if declaration.model.source is not None
                else None
            ),
        },
        build,
    )


def builtin_registry(
    *,
    policy: CostPolicy = FAITHFUL,
    clts_gap: float = 1.0,
) -> DistanceRegistry:
    """Bind shipped house, Panphon and CLTS costs without developer packages.

    CLTS uses an explicit adapter gap of 1.0 by default; this is independent
    of its raw set similarity. Weighted Panphon remains a discoverable arm
    whose shipped incomplete weight basis reports unavailability.
    """
    from . import feature_models
    from .clts import read_snapshot
    from .inventory_operations import HouseInventory

    house = IPAFeatures()
    house_inventory = HouseInventory(house)
    declaration = feature_models.read("panphon")
    snapshot = read_snapshot()
    common = {"version": 1, "policy": policy.identity, "input": "exact-tokens"}
    registrations = [
        Metric(
            "house/articulatory",
            house_inventory.identity,
            {**common, "family": "house-articulatory"},
            lambda _: replace(
                house_pack(house, policy), validate_token=house_inventory.read
            ),
        )
    ]
    for family in DeclaredCostFamily:
        absent = (
            AbsentCell.SKIP
            if family is DeclaredCostFamily.WEIGHTED_DIFFERENCE
            else AbsentCell.HALF_COUNTED
        )

        registrations.append(
            ternary_metric(
                f"panphon/{family.value}",
                declaration,
                policy=policy,
                family=family,
                absent=absent,
            )
        )
    registrations.append(
        Metric(
            "clts/jaccard",
            snapshot.identity,
            {**common, "family": "set-jaccard", "gap": clts_gap},
            lambda config: replace(
                set_feature_pack(snapshot.geometry, policy, gap=config["gap"]),
                validate_token=snapshot.geometry.features,
            ),
        )
    )
    return DistanceRegistry(registrations)
