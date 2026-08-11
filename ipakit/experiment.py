"""Reproducible rule-set experiments over directory corpora."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from ._corpus import Corpus
from ._corpus_query import BudgetRefusal, ExhaustiveRefusal, derives
from ._tiergraph_json import identity_fingerprint
from .features import IPAFeatures
from .rules import DEFAULT_LIMIT, Derivation, RuleError, RuleSet

Classification = Literal[
    "derivable", "provably_underivable", "cap_truncated", "ill_formed_input"
]
REPORT_VERSION = 1


def rule_set_identity(ruleset: RuleSet) -> dict[str, str]:
    """Return the named, content-addressed identity of a rule set."""
    identity = {"name": ruleset.name, "rules": [repr(rule) for rule in ruleset.rules]}
    return {
        "name": ruleset.name or "anonymous",
        "version": identity_fingerprint(identity),
    }


@dataclass(frozen=True)
class Residue:
    """One classified corpus pair, including the counterexample itself."""

    entry_id: str
    classification: Classification
    source: str | None
    target: str | None
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "classification": self.classification,
            "source": self.source,
            "target": self.target,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class Movement:
    """An entry whose classification differs between two reports."""

    entry_id: str
    before: Classification
    after: Classification


@dataclass(frozen=True)
class ExperimentReport:
    """Serializable paper-table and regression-test result."""

    provenance: dict[str, Any]
    source_role: str
    target_role: str
    limit: int
    entries: tuple[Residue, ...]

    @property
    def counts(self) -> dict[str, int]:
        names = (
            "derivable",
            "provably_underivable",
            "cap_truncated",
            "ill_formed_input",
        )
        return {
            name: sum(row.classification == name for row in self.entries)
            for name in names
        }

    @property
    def coverage(self) -> dict[str, int | float]:
        total = len(self.entries)
        derived = self.counts["derivable"]
        return {
            "derived": derived,
            "total": total,
            "ratio": derived / total if total else 0.0,
        }

    def compare(self, other: ExperimentReport) -> tuple[Movement, ...]:
        """Return class transitions, requiring the exact same data selection."""
        if (
            self.provenance.get("corpus") != other.provenance.get("corpus")
            or self.provenance.get("split") != other.provenance.get("split")
            or self.source_role != other.source_role
            or self.target_role != other.target_role
        ):
            raise ValueError("experiment reports do not describe the same data")
        before = {row.entry_id: row.classification for row in self.entries}
        after = {row.entry_id: row.classification for row in other.entries}
        if before.keys() != after.keys():
            raise ValueError("experiment reports do not contain the same entries")
        return tuple(
            Movement(entry_id, before[entry_id], after[entry_id])
            for entry_id in before
            if before[entry_id] != after[entry_id]
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "ipakit.experiment.report",
            "v": REPORT_VERSION,
            "provenance": self.provenance,
            "source_role": self.source_role,
            "target_role": self.target_role,
            "limit": self.limit,
            "coverage": self.coverage,
            "counts": self.counts,
            "entries": [row.to_dict() for row in self.entries],
        }

    def to_json(self) -> str:
        return (
            json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, indent=2)
            + "\n"
        )

    def write(self, path: str | Path) -> None:
        Path(path).write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def from_dict(cls, document: dict[str, Any]) -> ExperimentReport:
        """Restore a report document, refusing another type or version."""
        if document.get("type") != "ipakit.experiment.report":
            raise ValueError("not an ipakit experiment report")
        if document.get("v") != REPORT_VERSION:
            raise ValueError(
                f"unsupported experiment report version {document.get('v')!r}"
            )
        try:
            rows = tuple(
                Residue(
                    row["entry_id"],
                    row["classification"],
                    row["source"],
                    row["target"],
                    row.get("reason"),
                )
                for row in document["entries"]
            )
            if any(
                row.classification
                not in (
                    "derivable",
                    "provably_underivable",
                    "cap_truncated",
                    "ill_formed_input",
                )
                for row in rows
            ):
                raise ValueError("unknown experiment classification")
            return cls(
                document["provenance"],
                document["source_role"],
                document["target_role"],
                document["limit"],
                rows,
            )
        except (KeyError, TypeError) as exc:
            raise ValueError("malformed experiment report") from exc

    @classmethod
    def from_json(cls, text: str) -> ExperimentReport:
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError("experiment report must be a JSON object")
        return cls.from_dict(value)

    @classmethod
    def read(cls, path: str | Path) -> ExperimentReport:
        return cls.from_json(Path(path).read_text(encoding="utf-8"))


@dataclass(frozen=True)
class Experiment:
    """A rule set posed against named roles in a corpus or durable split."""

    ruleset: RuleSet
    corpus: Corpus
    source_role: str
    target_role: str
    split: str | None = None
    declaration_fingerprint: str | None = None
    limit: int = DEFAULT_LIMIT

    def run(self, features: IPAFeatures | None = None) -> ExperimentReport:
        ids = (
            self.corpus.split(self.split)
            if self.split is not None
            else tuple(self.corpus.ids())
        )
        rows: list[Residue] = []
        for entry_id in ids:
            try:
                entry = self.corpus.read_roles(
                    entry_id, (self.source_role, self.target_role)
                )
                source = entry.forms.get(self.source_role)
                target = entry.forms.get(self.target_role)
                if source is None or target is None:
                    missing = self.source_role if source is None else self.target_role
                    rows.append(
                        Residue(
                            entry_id,
                            "ill_formed_input",
                            source.to_ipa() if source else None,
                            target.to_ipa() if target else None,
                            f"missing role {missing!r}",
                        )
                    )
                    continue
                answer = derives(
                    self.ruleset, source, target, features=features, limit=self.limit
                )
                classification: Classification
                reason = None
                if isinstance(answer, Derivation):
                    classification = "derivable"
                elif isinstance(answer, ExhaustiveRefusal):
                    classification = "provably_underivable"
                elif isinstance(answer, BudgetRefusal):
                    classification = "cap_truncated"
                    reason = (
                        f"at least {answer.unexplored} choice combination(s) unexplored"
                    )
                else:  # pragma: no cover - closed union guard
                    raise AssertionError(type(answer))
                rows.append(
                    Residue(
                        entry_id,
                        classification,
                        source.to_ipa(),
                        target.to_ipa(),
                        reason,
                    )
                )
            except (RuleError, TypeError, ValueError) as exc:
                rows.append(Residue(entry_id, "ill_formed_input", None, None, str(exc)))
        provenance = {
            "rule_set": rule_set_identity(self.ruleset),
            "declaration_fingerprint": self.declaration_fingerprint
            or self.corpus.declaration_fingerprint,
            "corpus": self.corpus.fingerprint(),
            "split": self.split,
        }
        return ExperimentReport(
            provenance, self.source_role, self.target_role, self.limit, tuple(rows)
        )


__all__ = [
    "Classification",
    "Experiment",
    "ExperimentReport",
    "Movement",
    "Residue",
    "REPORT_VERSION",
    "rule_set_identity",
]
