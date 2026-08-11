"""Provenanced, non-adjudicating comparisons of retained forms."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .distance import Alignment, AlignmentStep, PhoneCost
from .features import IPAFeatures
from .form import Form, Interval, Timing

WIRE_VERSION = 1


class DisagreementKind(Enum):
    """Typed families of claims on which retained transcriptions differ."""

    FEATURE = "feature"
    STRUCTURE = "structure"
    TIMING = "timing"


@dataclass(frozen=True)
class ProvenancedForm:
    """One retained form and the non-empty identity of its source."""

    provenance: str
    form: Form

    def __post_init__(self) -> None:
        if not isinstance(self.provenance, str) or not self.provenance.strip():
            raise ValueError(
                "a disagreement input must have a non-empty provenance identity"
            )
        if not isinstance(self.form, Form):
            raise TypeError("a disagreement input must pair provenance with a Form")


@dataclass(frozen=True)
class AgreementPosition:
    """One aligned position at which a source agrees with the reference."""

    reference_position: int
    source_position: int
    unit: str


@dataclass(frozen=True)
class DisagreementPosition:
    """One priced, typed difference in an alignment or carried form claim."""

    kind: DisagreementKind
    reference_position: int | None
    source_position: int | None
    reference: str | None
    source: str | None
    cost: float
    terms: tuple[str, ...] = ()
    claim: str | None = None


@dataclass(frozen=True)
class FormComparison:
    """One source compared pairwise with the designated spread reference."""

    source: int
    alignment: Alignment
    agreements: tuple[AgreementPosition, ...]
    disagreements: tuple[DisagreementPosition, ...]


def _timing(value: Timing | None) -> str | None:
    return None if value is None else f"{value.start:g}+{value.duration:g}"


def _interval(value: Interval) -> str:
    timing = "" if value.timing is None else f"@{_timing(value.timing)}"
    return f"{value.tier}[{value.start},{value.end}){timing}"


def _segment_units(form: Form) -> list[Any]:
    return [unit for unit in form.units if unit.segment is not None]


def _pair(
    features: IPAFeatures,
    reference: Form,
    source: Form,
    source_number: int,
    insert_cost: PhoneCost | None,
    delete_cost: PhoneCost | None,
) -> FormComparison:
    result = features.directional_word_distance(
        reference.to_ipa(),
        source.to_ipa(),
        insert_cost=insert_cost,
        delete_cost=delete_cost,
        return_alignment=True,
    )
    assert result.alignment is not None
    left_units, right_units = _segment_units(reference), _segment_units(source)
    agreements: list[AgreementPosition] = []
    disagreements: list[DisagreementPosition] = []
    li = ri = 0
    for step in result.alignment.steps:
        lp = li if step.left is not None else None
        rp = ri if step.right is not None else None
        if step.op == "match":
            assert lp is not None and rp is not None
            agreements.append(AgreementPosition(lp, rp, step.left or ""))
            lt, rt = left_units[lp].timing, right_units[rp].timing
            if lt != rt:
                disagreements.append(
                    DisagreementPosition(
                        DisagreementKind.TIMING,
                        lp,
                        rp,
                        _timing(lt),
                        _timing(rt),
                        step.cost,
                        claim="unit timing",
                    )
                )
        else:
            tied = any(mark in (step.left or "") + (step.right or "") for mark in "͜͡")
            kind = (
                DisagreementKind.STRUCTURE
                if step.op != "sub" or tied
                else DisagreementKind.FEATURE
            )
            labels = tuple(
                str(term["label"])
                for term in step.terms
                if term.get("cost", 0.0) != 0.0
            )
            disagreements.append(
                DisagreementPosition(
                    kind,
                    lp,
                    rp,
                    step.left,
                    step.right,
                    step.cost,
                    labels,
                    (
                        "tie or unit structure"
                        if tied
                        else ("unit alignment" if step.op != "sub" else None)
                    ),
                )
            )
            lt = left_units[lp].timing if lp is not None else None
            rt = right_units[rp].timing if rp is not None else None
            if lt != rt:
                # The structural row above already carries this step's cost;
                # the metric declares no timing term, so the timing claim is
                # reported unpriced rather than double-surfacing the step.
                disagreements.append(
                    DisagreementPosition(
                        DisagreementKind.TIMING,
                        lp,
                        rp,
                        _timing(lt),
                        _timing(rt),
                        0.0,
                        claim="unit timing",
                    )
                )
        li += step.left is not None
        ri += step.right is not None
    left_intervals = {_interval(item) for item in reference.intervals}
    right_intervals = {_interval(item) for item in source.intervals}
    for claim in sorted(left_intervals ^ right_intervals):
        disagreements.append(
            DisagreementPosition(
                DisagreementKind.STRUCTURE,
                None,
                None,
                claim if claim in left_intervals else None,
                claim if claim in right_intervals else None,
                0.0,
                claim="tier claim (unpriced by segment metric)",
            )
        )
    return FormComparison(
        source_number, result.alignment, tuple(agreements), tuple(disagreements)
    )


@dataclass(frozen=True)
class DisagreementSpread:
    """A doculect-law spread of forms: queryable and never merged.

    Every retained transcription keeps its provenance identity.  Pairwise
    comparison against the designated reference partitions agreement from
    typed disagreement and carries the declared alignment price.  This object
    adjudicates nothing: it selects no winner, averages no forms, and emits no
    merged transcription.  A spread is evidence; selection belongs outside it.
    """

    inputs: tuple[ProvenancedForm, ...]
    reference: int
    comparisons: tuple[FormComparison, ...]

    @classmethod
    def compare(
        cls,
        *inputs: ProvenancedForm,
        reference: int = 0,
        features: IPAFeatures | None = None,
        insert_cost: PhoneCost | None = None,
        delete_cost: PhoneCost | None = None,
    ) -> DisagreementSpread:
        if len(inputs) < 2:
            raise ValueError(
                "a disagreement spread requires two or more provenanced forms"
            )
        if any(not isinstance(item, ProvenancedForm) for item in inputs):
            raise TypeError(
                "anonymous forms are refused; wrap each Form in ProvenancedForm"
            )
        if not 0 <= reference < len(inputs):
            raise IndexError("reference index is outside the disagreement spread")
        ipa = features or IPAFeatures()
        comparisons = tuple(
            _pair(
                ipa, inputs[reference].form, item.form, number, insert_cost, delete_cost
            )
            for number, item in enumerate(inputs)
            if number != reference
        )
        return cls(tuple(inputs), reference, comparisons)

    @property
    def disagreements(self) -> tuple[DisagreementPosition, ...]:
        return tuple(item for pair in self.comparisons for item in pair.disagreements)

    def to_dict(self) -> dict[str, Any]:
        def disagreement(item: DisagreementPosition) -> dict[str, Any]:
            return {
                "kind": item.kind.value,
                "reference_position": item.reference_position,
                "source_position": item.source_position,
                "reference": item.reference,
                "source": item.source,
                "cost": item.cost,
                "terms": list(item.terms),
                "claim": item.claim,
            }

        return {
            "type": "ipakit.disagreement.spread",
            "v": WIRE_VERSION,
            "reference": self.reference,
            "inputs": [
                {
                    "provenance": item.provenance,
                    "form": item.form.to_dict(self_contained=True),
                }
                for item in self.inputs
            ],
            "comparisons": [
                {
                    "source": pair.source,
                    "alignment": pair.alignment.to_data(),
                    "agreements": [vars(item) for item in pair.agreements],
                    "disagreements": [
                        disagreement(item) for item in pair.disagreements
                    ],
                }
                for pair in self.comparisons
            ],
        }

    def to_json(self) -> str:
        return (
            json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, indent=2)
            + "\n"
        )

    @classmethod
    def from_json(
        cls, text: str, features: IPAFeatures | None = None
    ) -> DisagreementSpread:
        doc = json.loads(text)
        if (
            not isinstance(doc, dict)
            or doc.get("type") != "ipakit.disagreement.spread"
            or doc.get("v") != WIRE_VERSION
        ):
            raise ValueError("not a supported ipakit disagreement spread")
        ipa = features or IPAFeatures()
        inputs = tuple(
            ProvenancedForm(row["provenance"], Form.from_dict(row["form"], ipa))
            for row in doc["inputs"]
        )
        pairs = []
        for row in doc["comparisons"]:
            a = row["alignment"]
            steps = tuple(
                AlignmentStep(
                    s["op"],
                    s["a"],
                    s["b"],
                    s["cost"],
                    tuple(s["terms"]),
                    s.get("left_event"),
                    s.get("right_event"),
                )
                for s in a["steps"]
            )
            alignment = Alignment(
                steps, a["edit_cost"], a["similarity"], a["coverage"], a["costs"]
            )
            agreements = tuple(AgreementPosition(**item) for item in row["agreements"])
            disagreements = tuple(
                DisagreementPosition(
                    DisagreementKind(item["kind"]),
                    item["reference_position"],
                    item["source_position"],
                    item["reference"],
                    item["source"],
                    item["cost"],
                    tuple(item["terms"]),
                    item["claim"],
                )
                for item in row["disagreements"]
            )
            pairs.append(
                FormComparison(row["source"], alignment, agreements, disagreements)
            )
        return cls(inputs, doc["reference"], tuple(pairs))


__all__ = [
    "AgreementPosition",
    "DisagreementKind",
    "DisagreementPosition",
    "DisagreementSpread",
    "FormComparison",
    "ProvenancedForm",
]
