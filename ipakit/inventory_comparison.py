"""Experimental, versioned pairwise inventory comparison reports.

The report in this module is a serialization layer over the existing
``phoneset_comparison()`` and ``phoneset_mapping()`` engines. It does not
define another distance, normalization, set, or assignment implementation.
Consumers must check the schema identifier and version.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, cast

from . import _get_ipa, phoneset_comparison, phoneset_mapping
from ._identity import identity_fingerprint
from .inventories import Inventory, Style, inventory
from .inventory_views import INVENTORY_VIEW_SCHEMA_ID, InventoryView
from .models import Phoneset
from .phoneset_map import Correspondence, PhonesetComparison, PhonesetMapping

if TYPE_CHECKING:
    from .features import IPAFeatures

INVENTORY_COMPARISON_SCHEMA_ID = "ipakit.inventory-comparison-report"
INVENTORY_COMPARISON_SCHEMA_VERSION = 1

MappingStrategy = Literal["nearest", "one-to-one"]

_STATUS_ORDER = (
    "present",
    "filtered",
    "dropped",
    "unreadable",
    "refused",
    "unavailable",
    "unresolved",
)


def _status_counts(view: InventoryView) -> dict[str, int]:
    return {
        status: sum(member.status == status for member in view.members)
        for status in _STATUS_ORDER
    }


def _view_data(view: InventoryView, *, detail: bool) -> dict[str, object]:
    result: dict[str, object] = {
        "schema": {
            "id": INVENTORY_VIEW_SCHEMA_ID,
            "version": view.schema_version,
        },
        "identity": view.identity,
        "name": view.name,
        "kind": view.kind,
        "provenance": view.provenance,
        "availability": view.availability,
        "style": view.style,
        "version": view.version,
        "source": None if view.source is None else view.source.to_dict(),
        "declared_count": len(view.members),
        "status_counts": _status_counts(view),
    }
    if detail:
        result["members"] = [member.to_dict() for member in view.members]
    return result


def _present_house_forms(view: InventoryView) -> tuple[str, ...]:
    if view.availability != "available":
        raise ValueError(
            f"inventory comparison requires an available finite view, got "
            f"{view.name!r}"
        )
    values = []
    for member in view.members:
        if member.status == "present":
            assert member.house_form is not None
            values.append(member.house_form)
    return tuple(values)


def _style(view: InventoryView, features: IPAFeatures) -> Style:
    """Resolve only notation behavior; the view remains membership authority."""
    return inventory(view.style or "ipa", ipa=features).style


def _snapshot_inventory(view: InventoryView, features: IPAFeatures) -> Inventory:
    """Give the current engine the view's exact admitted population."""
    phones = Phoneset.from_list(list(_present_house_forms(view)), view.name)
    return Inventory(
        view.name,
        _style(view, features),
        phones,
        view.provenance,
        view.version,
        source=view.source,
    )


def _mapping_inventory(
    view: InventoryView, phones: Phoneset, features: IPAFeatures
) -> Inventory:
    """Retain view identity/style around the comparison engine's population."""
    return Inventory(
        view.name,
        _style(view, features),
        phones,
        view.provenance,
        view.version,
        source=view.source,
    )


def _correspondence_data(
    item: Correspondence,
    *,
    relation: MappingStrategy,
    features: IPAFeatures,
    include_feature_terms: bool,
    applicable_only: bool,
) -> dict[str, object]:
    result: dict[str, object] = {
        "source": item.source,
        "target": item.target,
        "relation": relation,
        "distance": item.distance,
        "ties": list(item.ties),
        "source_spelling": item.source_spelling,
        "target_spelling": item.target_spelling,
        "reason": item.reason,
    }
    if include_feature_terms and item.target is not None:
        steps = features.explain_transcription_distance(
            item.source,
            item.target,
            applicable_only=applicable_only,
        )
        if len(steps) != 1:
            raise ValueError(
                "house-readable phone pair did not produce one explanation step"
            )
        step = steps[0]
        if step["terms"]:
            result["feature_explanation"] = {
                "distance": step["cost"],
                "reconstruction": "sum(cost * weight) / sum(weight)",
                "terms": step["terms"],
            }
    return result


def _worst_data(item: Correspondence | None) -> dict[str, object] | None:
    if item is None:
        return None
    return {
        "source": item.source,
        "target": item.target,
        "distance": item.distance,
    }


def _direction_data(
    result: PhonesetMapping,
    *,
    source: str,
    target: str,
    strategy: MappingStrategy,
    max_distance: float | None,
    detail: bool,
    include_feature_terms: bool,
    features: IPAFeatures,
    applicable_only: bool,
) -> dict[str, object]:
    data: dict[str, object] = {
        "source": source,
        "target": target,
        "relation": strategy,
        "max_distance": max_distance,
        "source_count": len(result.source),
        "target_count": len(result.target),
        "mapped_count": len(result.mapped),
        "unmapped_count": len(result.unmapped),
        "exact_count": len(result.exact),
        "collapse_count": len(result.collapses),
        "ambiguous_count": len(result.ambiguous),
        "unused_target_count": len(result.unused_targets),
        "total_distance": result.total_distance,
        "mean_distance": result.mean_distance,
        "worst": _worst_data(result.worst),
    }
    if detail:
        data.update(
            {
                "correspondences": [
                    _correspondence_data(
                        item,
                        relation=strategy,
                        features=features,
                        include_feature_terms=include_feature_terms,
                        applicable_only=applicable_only,
                    )
                    for item in result.correspondences
                ],
                "collapses": {
                    target_phone: list(source_phones)
                    for target_phone, source_phones in result.collapses.items()
                },
                "unmapped": list(result.unmapped),
                "unused_targets": list(result.unused_targets),
                "unreadable_targets": [list(row) for row in result.unreadable_targets],
            }
        )
    return data


def _membership_data(result: PhonesetComparison, *, detail: bool) -> dict[str, object]:
    data: dict[str, object] = {
        "a_count": len(result.a),
        "b_count": len(result.b),
        "union_count": len(result.union),
        "intersection_count": len(result.intersection),
        "only_a_count": len(result.only_a),
        "only_b_count": len(result.only_b),
    }
    if detail:
        data.update(
            {
                "union": list(result.union),
                "intersection": list(result.intersection),
                "only_a": list(result.only_a),
                "only_b": list(result.only_b),
                "rows": [
                    {
                        "symbol": phone,
                        "a": phone in result.a,
                        "b": phone in result.b,
                        "a_spelling": result.spellings[phone][0],
                        "b_spelling": result.spellings[phone][1],
                    }
                    for phone in result.union
                ],
            }
        )
    return data


def _matrix_data(result: PhonesetComparison) -> dict[str, object]:
    forward = [list(row) for row in result.matrix]
    reverse = [
        [result.matrix[row][column] for row in range(len(result.a))]
        for column in range(len(result.b))
    ]
    return {
        "measure": "similarity",
        "a_to_b": {
            "rows": list(result.a.phones),
            "columns": list(result.b.phones),
            "values": forward,
        },
        "b_to_a": {
            "rows": list(result.b.phones),
            "columns": list(result.a.phones),
            "values": reverse,
        },
    }


@dataclass(frozen=True)
class InventoryComparisonReport:
    """A canonical JSON report for exactly two inventory views.

    Summary output is the default. ``detail`` adds symbol-bearing membership
    rows, matrices, correspondence rows, and exact strip witnesses. Feature
    terms are separately opt-in and require detail.
    """

    a: InventoryView
    b: InventoryView
    comparison: PhonesetComparison = field(repr=False)
    strategy: MappingStrategy | None = None
    max_distance: float | None = None
    detail: bool = False
    include_feature_terms: bool = False
    forward: PhonesetMapping | None = field(default=None, repr=False)
    backward: PhonesetMapping | None = field(default=None, repr=False)
    _features: IPAFeatures = field(repr=False, compare=False, default_factory=_get_ipa)

    def __post_init__(self) -> None:
        if self.strategy not in {None, "nearest", "one-to-one"}:
            raise ValueError(f"unknown mapping strategy {self.strategy!r}")
        if self.max_distance is not None and (
            not math.isfinite(self.max_distance) or self.max_distance < 0
        ):
            raise ValueError("max_distance must be a finite nonnegative number")
        if self.strategy is None:
            if self.max_distance is not None:
                raise ValueError("max_distance requires a mapping strategy")
            if self.forward is not None or self.backward is not None:
                raise ValueError("mapping results require a mapping strategy")
        elif self.forward is None or self.backward is None:
            raise ValueError("mapping strategy requires both directions")
        if self.include_feature_terms and not self.detail:
            raise ValueError("feature terms require detail=True")
        if self.include_feature_terms and self.strategy is None:
            raise ValueError("feature terms require a mapping strategy")
        rows = len(self.comparison.a)
        columns = len(self.comparison.b)
        if len(self.comparison.matrix) != rows or any(
            len(row) != columns for row in self.comparison.matrix
        ):
            raise ValueError("comparison matrix dimensions do not match its phonesets")
        if self.forward is not None and self.backward is not None:
            if (
                self.forward.kind != self.strategy
                or self.backward.kind != self.strategy
            ):
                raise ValueError("mapping result kind does not match report strategy")
            if (
                self.forward.source.phones != self.comparison.a.phones
                or self.forward.target.phones != self.comparison.b.phones
                or self.backward.source.phones != self.comparison.b.phones
                or self.backward.target.phones != self.comparison.a.phones
            ):
                raise ValueError(
                    "mapping directions do not match comparison populations"
                )

    @property
    def schema_version(self) -> int:
        """Return the experimental schema version."""
        return INVENTORY_COMPARISON_SCHEMA_VERSION

    def _material(self) -> dict[str, object]:
        result: dict[str, object] = {
            "schema": {
                "id": INVENTORY_COMPARISON_SCHEMA_ID,
                "version": INVENTORY_COMPARISON_SCHEMA_VERSION,
                "stability": "experimental",
            },
            "options": {
                "detail": self.detail,
                "mapping": self.strategy,
                "max_distance": self.max_distance,
                "strip": self.comparison.strip,
                "applicable_only": self.comparison.applicable_only,
                "feature_terms": self.include_feature_terms,
            },
            "terms": {
                "membership": "exact-post-strip-post-tie-engine-form-membership",
                "distance": "raw-feature-distance",
                "matrix": "similarity",
                "mapping": self.strategy,
                "directionality": (
                    "A -> B and B -> A are independent directional results"
                    if self.strategy is not None
                    else None
                ),
            },
            "inputs": {
                "a": _view_data(self.a, detail=self.detail),
                "b": _view_data(self.b, detail=self.detail),
            },
            "membership": _membership_data(self.comparison, detail=self.detail),
            "stripping": {
                "mode": self.comparison.strip,
                "changed_count": len(self.comparison.stripped),
            },
            "mapping": None,
        }
        if self.strategy is not None:
            assert self.forward is not None and self.backward is not None
            result["mapping"] = {
                "strategy": self.strategy,
                "max_distance": self.max_distance,
                "directional": True,
                "a_to_b": _direction_data(
                    self.forward,
                    source="a",
                    target="b",
                    strategy=self.strategy,
                    max_distance=self.max_distance,
                    detail=self.detail,
                    include_feature_terms=self.include_feature_terms,
                    features=self._features,
                    applicable_only=self.comparison.applicable_only,
                ),
                "b_to_a": _direction_data(
                    self.backward,
                    source="b",
                    target="a",
                    strategy=self.strategy,
                    max_distance=self.max_distance,
                    detail=self.detail,
                    include_feature_terms=self.include_feature_terms,
                    features=self._features,
                    applicable_only=self.comparison.applicable_only,
                ),
            }
        if self.detail:
            cast("dict[str, object]", result["stripping"])["changed"] = [
                list(row) for row in self.comparison.stripped
            ]
            result["matrices"] = _matrix_data(self.comparison)
        return result

    @property
    def identity(self) -> str:
        """Fingerprint the canonical report material, including its options."""
        return identity_fingerprint(self._material())

    def to_dict(self) -> dict[str, object]:
        """Return the canonical JSON-ready experimental report."""
        material = self._material()
        return {**material, "identity": identity_fingerprint(material)}

    def to_json(self) -> str:
        """Serialize canonical JSON with deterministic key ordering."""
        return (
            json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, indent=2)
            + "\n"
        )


def inventory_comparison_report(
    a: InventoryView,
    b: InventoryView,
    *,
    mapping: MappingStrategy | None = None,
    max_distance: float | None = None,
    detail: bool = False,
    include_feature_terms: bool = False,
    strip: str | None = "stress",
    ipa: IPAFeatures | None = None,
    applicable_only: bool = False,
) -> InventoryComparisonReport:
    """Build one pairwise report through the current comparison engines."""
    if mapping not in {None, "nearest", "one-to-one"}:
        raise ValueError(f"unknown mapping strategy {mapping!r}")
    if max_distance is not None and mapping is None:
        raise ValueError("max_distance requires a mapping strategy")
    if include_feature_terms and not detail:
        raise ValueError("feature terms require detail=True")
    if include_feature_terms and mapping is None:
        raise ValueError("feature terms require a mapping strategy")

    features = ipa or _get_ipa()
    left = _snapshot_inventory(a, features)
    right = _snapshot_inventory(b, features)
    comparison = phoneset_comparison(
        left,
        right,
        ipa=features,
        strip=strip,
        applicable_only=applicable_only,
    )

    forward: PhonesetMapping | None = None
    backward: PhonesetMapping | None = None
    if mapping == "nearest" and max_distance is None:
        forward = comparison.forward
        backward = comparison.backward
    elif mapping is not None:
        compared_left = _mapping_inventory(a, comparison.a, features)
        compared_right = _mapping_inventory(b, comparison.b, features)
        one_to_one = mapping == "one-to-one"
        forward = phoneset_mapping(
            compared_left,
            compared_right,
            one_to_one=one_to_one,
            max_distance=max_distance,
            ipa=features,
            applicable_only=applicable_only,
        )
        backward = phoneset_mapping(
            compared_right,
            compared_left,
            one_to_one=one_to_one,
            max_distance=max_distance,
            ipa=features,
            applicable_only=applicable_only,
        )

    return InventoryComparisonReport(
        a,
        b,
        comparison,
        mapping,
        max_distance,
        detail,
        include_feature_terms,
        forward,
        backward,
        features,
    )


__all__ = [
    "INVENTORY_COMPARISON_SCHEMA_ID",
    "INVENTORY_COMPARISON_SCHEMA_VERSION",
    "InventoryComparisonReport",
    "MappingStrategy",
    "inventory_comparison_report",
]
