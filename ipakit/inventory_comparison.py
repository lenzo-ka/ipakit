"""Experimental, versioned inventory comparison reports.

The report in this module is a serialization layer over the existing
``phoneset_comparison()`` and ``phoneset_mapping()`` engines. It does not
define another distance, normalization, set, or assignment implementation.
Exactly two inputs retain the original pairwise serialization byte for byte;
other arities use the N-way membership shape. Consumers must check the schema
identifier and version.
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

_COVERAGE_NAMES = (
    "overlap",
    "readable/admitted",
    "reviewed-mapped",
    "exact representability",
    "thresholded-nearest",
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


def _authority_and_loss_data(
    views: tuple[InventoryView, ...], labels: tuple[str, ...], *, detail: bool
) -> dict[str, object] | None:
    bridges: list[dict[str, object]] = []
    declared: list[dict[str, object]] = []
    exercised: list[dict[str, object]] = []
    reviewed: list[dict[str, object]] = []
    for view, label in zip(views, labels, strict=True):
        receipt = view.bridge
        if receipt is not None:
            bridge_data = receipt.to_dict()
            bridges.append(
                {
                    "input": label,
                    "name": receipt.name,
                    "version": receipt.version,
                    "declared": bridge_data["declared"],
                }
            )
            for direction, names in (
                ("external-to-house", receipt.external_to_house_drops),
                ("house-to-external", receipt.house_to_external_drops),
            ):
                declared.extend(
                    {"input": label, "direction": direction, "name": name}
                    for name in names
                )
            exercised.extend(
                {"input": label, **loss.to_dict()} for loss in receipt.exercised_losses
            )
        if view.mapping_authority is not None:
            reviewed.append(_reviewed_mapping_data(view, label, detail=detail))
    if not bridges and not reviewed:
        return None
    return {
        "bridges": bridges,
        "reviewed_mappings": reviewed,
        "losses": {"declared": declared, "exercised": exercised},
    }


def _reviewed_mapping_data(
    view: InventoryView, label: str, *, detail: bool
) -> dict[str, object]:
    mappings = [
        member
        for member in view.members
        if member.mapping is not None and member.mapping.relation == "reviewed"
    ]
    row: dict[str, object] = {
        "input": label,
        "authority": view.mapping_authority,
        "reviewed_count": len(mappings),
        "unresolved_count": sum(
            member.status == "unresolved" for member in view.members
        ),
    }
    if detail:
        row["mappings"] = [
            {
                "source": member.source_token,
                "target": member.mapping.target,
                "relation": member.mapping.relation,
            }
            for member in mappings
            if member.mapping is not None
        ]
    return row


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


def _normalized_population(
    view: InventoryView,
    features: IPAFeatures,
    *,
    strip: str | None,
    applicable_only: bool,
) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...]]:
    """Normalize one view through the current comparison engine."""
    result = phoneset_comparison(
        _snapshot_inventory(view, features),
        Phoneset.from_list([], "empty comparison population"),
        b_style="ipa",
        ipa=features,
        strip=strip,
        applicable_only=applicable_only,
    )
    return tuple(result.a.phones), result.stripped


def _input_key(index: int) -> str:
    return f"input-{index}"


def _nway_membership_data(
    populations: tuple[tuple[str, ...], ...], *, detail: bool
) -> dict[str, object]:
    input_sets = tuple(set(population) for population in populations)
    union = tuple(
        dict.fromkeys(phone for population in populations for phone in population)
    )
    memberships = {
        phone: tuple(
            _input_key(index)
            for index, population in enumerate(input_sets)
            if phone in population
        )
        for phone in union
    }
    shared_by_all = tuple(
        phone
        for phone in union
        if populations and len(memberships[phone]) == len(populations)
    )
    shared_by_subset = tuple(
        phone for phone in union if 1 < len(memberships[phone]) < len(populations)
    )
    unique_to_one = tuple(phone for phone in union if len(memberships[phone]) == 1)

    subset_groups: dict[tuple[str, ...], list[str]] = {}
    for phone in shared_by_subset:
        subset_groups.setdefault(memberships[phone], []).append(phone)
    unique_groups = {
        _input_key(index): [
            phone
            for phone in unique_to_one
            if memberships[phone] == (_input_key(index),)
        ]
        for index in range(len(populations))
    }

    data: dict[str, object] = {
        "input_count": len(populations),
        "input_sizes": [len(population) for population in populations],
        "union_count": len(union),
        "shared_by_all_count": len(shared_by_all),
        "shared_by_subset_count": len(shared_by_subset),
        "unique_to_one_count": len(unique_to_one),
        "shared_by_subset_groups": [
            {"inputs": list(inputs), "count": len(symbols)}
            for inputs, symbols in subset_groups.items()
        ],
        "unique_to_one_groups": [
            {"input": input_key, "count": len(symbols)}
            for input_key, symbols in unique_groups.items()
        ],
    }
    if detail:
        data.update(
            {
                "union": list(union),
                "shared_by_all": list(shared_by_all),
                "shared_by_subset": [
                    {"inputs": list(inputs), "symbols": symbols}
                    for inputs, symbols in subset_groups.items()
                ],
                "unique_to_one": [
                    {"input": input_key, "symbols": symbols}
                    for input_key, symbols in unique_groups.items()
                ],
                "rows": [
                    {
                        "symbol": phone,
                        "inputs": list(memberships[phone]),
                        "membership": [
                            phone in population for population in input_sets
                        ],
                    }
                    for phone in union
                ],
            }
        )
    return data


def _coverage_measure(
    name: str,
    numerator: int,
    denominator: int,
    definition: str,
    *,
    numerator_statuses: tuple[str, ...],
    denominator_statuses: tuple[str, ...],
    applicable: bool = True,
) -> dict[str, object]:
    if name not in _COVERAGE_NAMES:
        raise ValueError(f"unknown coverage measure {name!r}")
    if numerator < 0 or denominator < 0 or numerator > denominator:
        raise ValueError(f"invalid {name} coverage fraction")
    unknown = (set(numerator_statuses) | set(denominator_statuses)) - set(_STATUS_ORDER)
    if unknown:
        raise ValueError(f"unknown coverage status buckets {sorted(unknown)!r}")
    return {
        "name": name,
        "numerator": numerator,
        "denominator": denominator,
        "definition": definition,
        "status_buckets": {
            "numerator": list(numerator_statuses),
            "denominator": list(denominator_statuses),
        },
        "applicable": applicable,
    }


def _nway_coverage_data(
    views: tuple[InventoryView, ...],
    populations: tuple[tuple[str, ...], ...],
    *,
    thresholded_nearest_numerator: int | None,
) -> list[dict[str, object]]:
    input_sets = tuple(set(population) for population in populations)
    union = set().union(*input_sets) if input_sets else set()
    shared_by_all = set.intersection(*input_sets) if input_sets else set()
    declared = sum(len(view.members) for view in views)
    admitted = sum(
        member.status == "present" for view in views for member in view.members
    )
    directed_denominator = sum(
        len(source)
        for source_index, source in enumerate(populations)
        for target_index in range(len(populations))
        if source_index != target_index
    )
    exactly_represented = sum(
        len(source & target)
        for source_index, source in enumerate(input_sets)
        for target_index, target in enumerate(input_sets)
        if source_index != target_index
    )
    threshold_applicable = thresholded_nearest_numerator is not None
    authoritative = tuple(view for view in views if view.mapping_authority is not None)
    reviewed_mapped = sum(
        member.mapping is not None and member.mapping.relation == "reviewed"
        for view in authoritative
        for member in view.members
    )
    reviewed_population = sum(
        member.status in {"present", "unresolved"}
        for view in authoritative
        for member in view.members
    )

    return [
        _coverage_measure(
            "overlap",
            len(shared_by_all),
            len(union),
            "symbols present in every selected input divided by symbols present "
            "in at least one selected input",
            numerator_statuses=("present",),
            denominator_statuses=("present",),
        ),
        _coverage_measure(
            "readable/admitted",
            admitted,
            declared,
            "declared source members admitted as present with a house-readable "
            "form divided by all declared source members",
            numerator_statuses=("present",),
            denominator_statuses=_STATUS_ORDER,
        ),
        _coverage_measure(
            "reviewed-mapped",
            reviewed_mapped,
            reviewed_population,
            "members with a reviewed source-native mapping divided by members "
            "in a view carrying that mapping authority",
            numerator_statuses=(("present",) if authoritative else ()),
            denominator_statuses=(("present", "unresolved") if authoritative else ()),
            applicable=bool(authoritative),
        ),
        _coverage_measure(
            "exact representability",
            exactly_represented,
            directed_denominator,
            "directed source symbols present exactly in the target divided by "
            "all directed source-symbol opportunities across distinct inputs",
            numerator_statuses=("present",),
            denominator_statuses=("present",),
            applicable=len(populations) > 1,
        ),
        _coverage_measure(
            "thresholded-nearest",
            thresholded_nearest_numerator or 0,
            directed_denominator if threshold_applicable else 0,
            "directed source symbols with a nearest target at or below the "
            "explicit maximum distance divided by all directed source-symbol "
            "opportunities across distinct inputs",
            numerator_statuses=(("present",) if threshold_applicable else ()),
            denominator_statuses=(("present",) if threshold_applicable else ()),
            applicable=threshold_applicable,
        ),
    ]


@dataclass(frozen=True)
class InventoryComparisonReport:
    """A canonical JSON report for zero or more inventory views.

    Exactly two views retain the lane-B pairwise shape. Other arities use the
    permutation-invariant N-way shape. Summary output is the default;
    ``detail`` adds symbol-bearing membership rows and strip witnesses.
    Pairwise matrices, correspondence rows, and feature terms remain limited
    to the two-input detail shape.
    """

    a: InventoryView | None
    b: InventoryView | None
    comparison: PhonesetComparison | None = field(repr=False)
    strategy: MappingStrategy | None = None
    max_distance: float | None = None
    detail: bool = False
    include_feature_terms: bool = False
    forward: PhonesetMapping | None = field(default=None, repr=False)
    backward: PhonesetMapping | None = field(default=None, repr=False)
    _features: IPAFeatures = field(repr=False, compare=False, default_factory=_get_ipa)
    additional: tuple[InventoryView, ...] = ()
    nway_populations: tuple[tuple[str, ...], ...] = field(default=(), repr=False)
    nway_stripped: tuple[tuple[tuple[str, str], ...], ...] = field(
        default=(), repr=False
    )
    thresholded_nearest_numerator: int | None = field(default=None, repr=False)
    nway_strip: str | None = field(default="stress", repr=False)
    nway_applicable_only: bool = field(default=False, repr=False)
    coverage_at: tuple[float, ...] = ()

    @property
    def inputs(self) -> tuple[InventoryView, ...]:
        """Return the report inputs in their canonical report order."""
        leading = tuple(view for view in (self.a, self.b) if view is not None)
        return (*leading, *self.additional)

    def __post_init__(self) -> None:
        if self.strategy not in {None, "nearest", "one-to-one"}:
            raise ValueError(f"unknown mapping strategy {self.strategy!r}")
        if self.max_distance is not None and (
            not math.isfinite(self.max_distance) or self.max_distance < 0
        ):
            raise ValueError("max_distance must be a finite nonnegative number")
        if any(not math.isfinite(value) or value < 0 for value in self.coverage_at):
            raise ValueError("coverage thresholds must be finite nonnegative numbers")
        if self.coverage_at and (len(self.inputs) != 2 or self.strategy != "nearest"):
            raise ValueError("coverage thresholds require pairwise nearest mapping")
        if self.strategy is None:
            if self.max_distance is not None:
                raise ValueError("max_distance requires a mapping strategy")
            if self.forward is not None or self.backward is not None:
                raise ValueError("mapping results require a mapping strategy")
        elif len(self.inputs) == 2 and (self.forward is None or self.backward is None):
            raise ValueError("mapping strategy requires both directions")
        if self.include_feature_terms and not self.detail:
            raise ValueError("feature terms require detail=True")
        if self.include_feature_terms and self.strategy is None:
            raise ValueError("feature terms require a mapping strategy")
        if len(self.inputs) != 2:
            if self.comparison is not None:
                raise ValueError("N-way report cannot carry one pairwise comparison")
            if self.forward is not None or self.backward is not None:
                raise ValueError("N-way report cannot carry pairwise mapping results")
            if self.include_feature_terms:
                raise ValueError("feature terms require exactly two inputs")
            if len(self.nway_populations) != len(self.inputs):
                raise ValueError("N-way populations must match report inputs")
            if len(self.nway_stripped) != len(self.inputs):
                raise ValueError("N-way strip witnesses must match report inputs")
            if self.strategy not in {None, "nearest"}:
                raise ValueError("N-way coverage supports only nearest mapping")
            if self.strategy == "nearest" and self.max_distance is None:
                raise ValueError(
                    "N-way nearest coverage requires an explicit max_distance"
                )
            if self.strategy is None and self.thresholded_nearest_numerator is not None:
                raise ValueError("thresholded coverage requires nearest mapping")
            directed_denominator = sum(
                len(source)
                for source_index, source in enumerate(self.nway_populations)
                for target_index in range(len(self.nway_populations))
                if source_index != target_index
            )
            if self.thresholded_nearest_numerator is not None and not (
                0 <= self.thresholded_nearest_numerator <= directed_denominator
            ):
                raise ValueError("invalid thresholded-nearest numerator")
            return
        if self.a is None or self.b is None or self.comparison is None:
            raise ValueError("two-input report requires its pairwise comparison")
        if self.additional or self.nway_populations or self.nway_stripped:
            raise ValueError("two-input report cannot carry N-way material")
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

    def _pairwise_material(self) -> dict[str, object]:
        assert self.a is not None and self.b is not None
        assert self.comparison is not None
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
            "asymmetry": (
                self.comparison.asymmetry if self.strategy is not None else None
            ),
            "mapping": None,
        }
        authority = _authority_and_loss_data(
            (self.a, self.b), ("a", "b"), detail=self.detail
        )
        if authority is not None:
            result["authority_and_loss"] = authority
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
            if self.coverage_at:
                mapping = cast("dict[str, object]", result["mapping"])
                for key, direction in (
                    ("a_to_b", self.forward),
                    ("b_to_a", self.backward),
                ):
                    row = cast("dict[str, object]", mapping[key])
                    row["coverage"] = [
                        {
                            "max_distance": item.max_distance,
                            "covered": item.covered,
                            "total": item.total,
                            "fraction": item.fraction,
                        }
                        for item in (
                            direction.coverage(value) for value in self.coverage_at
                        )
                    ]
        if self.detail:
            cast("dict[str, object]", result["stripping"])["changed"] = [
                list(row) for row in self.comparison.stripped
            ]
            result["matrices"] = _matrix_data(self.comparison)
        return result

    def _nway_material(self) -> dict[str, object]:
        views = self.inputs
        changed = [
            {
                "input": _input_key(index),
                "from": source,
                "to": target,
            }
            for index, rows in enumerate(self.nway_stripped)
            for source, target in rows
        ]
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
                "strip": self.nway_strip,
                "applicable_only": self.nway_applicable_only,
                "feature_terms": False,
            },
            "terms": {
                "membership": "exact-post-strip-post-tie-engine-form-membership",
                "distance": "raw-feature-distance",
                "matrix": "similarity",
                "mapping": self.strategy,
                "directionality": (
                    "ordered source and target inputs are independent directional results"
                    if self.strategy is not None
                    else None
                ),
            },
            "inputs": {
                _input_key(index): _view_data(view, detail=self.detail)
                for index, view in enumerate(views)
            },
            "membership": _nway_membership_data(
                self.nway_populations, detail=self.detail
            ),
            "coverage": _nway_coverage_data(
                views,
                self.nway_populations,
                thresholded_nearest_numerator=self.thresholded_nearest_numerator,
            ),
            "stripping": {
                "mode": self.nway_strip,
                "changed_count": len(changed),
            },
            "mapping": (
                None
                if self.strategy is None
                else {
                    "strategy": self.strategy,
                    "max_distance": self.max_distance,
                    "directional": True,
                    "ordered_pair_count": len(views) * max(0, len(views) - 1),
                }
            ),
        }
        authority = _authority_and_loss_data(
            views,
            tuple(_input_key(index) for index in range(len(views))),
            detail=self.detail,
        )
        if authority is not None:
            result["authority_and_loss"] = authority
        if self.detail:
            cast("dict[str, object]", result["stripping"])["changed"] = changed
        return result

    def _material(self) -> dict[str, object]:
        if len(self.inputs) == 2:
            return self._pairwise_material()
        return self._nway_material()

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
    a: InventoryView | None = None,
    b: InventoryView | None = None,
    *additional: InventoryView,
    mapping: MappingStrategy | None = None,
    max_distance: float | None = None,
    detail: bool = False,
    include_feature_terms: bool = False,
    coverage_at: tuple[float, ...] = (),
    strip: str | None = "stress",
    ipa: IPAFeatures | None = None,
    applicable_only: bool = False,
) -> InventoryComparisonReport:
    """Build one report through the current comparison and mapping engines."""
    if mapping not in {None, "nearest", "one-to-one"}:
        raise ValueError(f"unknown mapping strategy {mapping!r}")
    if max_distance is not None and mapping is None:
        raise ValueError("max_distance requires a mapping strategy")
    if include_feature_terms and not detail:
        raise ValueError("feature terms require detail=True")
    if include_feature_terms and mapping is None:
        raise ValueError("feature terms require a mapping strategy")

    features = ipa or _get_ipa()
    views = tuple(view for view in (a, b) if view is not None) + additional
    if coverage_at and (len(views) != 2 or mapping != "nearest"):
        raise ValueError("coverage thresholds require pairwise nearest mapping")
    if len(views) != 2:
        if include_feature_terms:
            raise ValueError("feature terms require exactly two inputs")
        if mapping not in {None, "nearest"}:
            raise ValueError("N-way coverage supports only nearest mapping")
        if mapping == "nearest" and max_distance is None:
            raise ValueError("N-way nearest coverage requires an explicit max_distance")
        canonical_views = tuple(sorted(views, key=lambda view: view.identity))
        normalized = tuple(
            _normalized_population(
                view,
                features,
                strip=strip,
                applicable_only=applicable_only,
            )
            for view in canonical_views
        )
        populations = tuple(population for population, _changed in normalized)
        stripped = tuple(changed for _population, changed in normalized)
        thresholded_nearest_numerator: int | None = None
        if mapping == "nearest":
            assert max_distance is not None
            inventories = tuple(
                _mapping_inventory(
                    view,
                    Phoneset.from_list(list(population), view.name),
                    features,
                )
                for view, population in zip(canonical_views, populations, strict=True)
            )
            thresholded_nearest_numerator = sum(
                len(
                    phoneset_mapping(
                        source,
                        target,
                        max_distance=max_distance,
                        ipa=features,
                        applicable_only=applicable_only,
                    ).mapped
                )
                for source_index, source in enumerate(inventories)
                for target_index, target in enumerate(inventories)
                if source_index != target_index
            )
        return InventoryComparisonReport(
            a=canonical_views[0] if canonical_views else None,
            b=canonical_views[1] if len(canonical_views) > 1 else None,
            comparison=None,
            strategy=mapping,
            max_distance=max_distance,
            detail=detail,
            include_feature_terms=False,
            forward=None,
            backward=None,
            _features=features,
            additional=canonical_views[2:],
            nway_populations=populations,
            nway_stripped=stripped,
            thresholded_nearest_numerator=thresholded_nearest_numerator,
            nway_strip=strip,
            nway_applicable_only=applicable_only,
            coverage_at=coverage_at,
        )

    left_view, right_view = views
    left = _snapshot_inventory(left_view, features)
    right = _snapshot_inventory(right_view, features)
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
        compared_left = _mapping_inventory(left_view, comparison.a, features)
        compared_right = _mapping_inventory(right_view, comparison.b, features)
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
        a=left_view,
        b=right_view,
        comparison=comparison,
        strategy=mapping,
        max_distance=max_distance,
        detail=detail,
        include_feature_terms=include_feature_terms,
        forward=forward,
        backward=backward,
        _features=features,
        coverage_at=coverage_at,
    )


__all__ = [
    "INVENTORY_COMPARISON_SCHEMA_ID",
    "INVENTORY_COMPARISON_SCHEMA_VERSION",
    "InventoryComparisonReport",
    "MappingStrategy",
    "inventory_comparison_report",
]
