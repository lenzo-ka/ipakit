"""PHOIBLE doculect inventories from shipped sources or an explicit checkout."""

from __future__ import annotations

import csv
import io
import os
import warnings
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from ..features import IPAFeatures
from ..models import Phoneset
from ..phoible_source import read_source, source_policy
from .base import Fidelity, RoundTripLeg, RoundTripReport
from .provider import ProviderBridge

PHOIBLE_ENV = "IPAKIT_PHOIBLE"


class PhoibleDataUnavailable(FileNotFoundError):
    """An explicitly selected PHOIBLE checkout is unavailable."""


@dataclass(frozen=True)
class PhoibleProvenance:
    """Generated identity and bibliography for one PHOIBLE inventory."""

    inventory_id: str
    glottocode: str
    iso6393: str
    language_name: str
    source: str
    bibtex_keys: tuple[str, ...]


@dataclass(frozen=True)
class PhoibleRefusal:
    """A positioned PHOIBLE value that cannot be represented as house IPA."""

    row: int
    field: str
    value: str
    reason: str


@dataclass(frozen=True)
class PhoibleEntry:
    """One accepted phoneme and the PHOIBLE annotations retained beside it."""

    phoneme: str
    allophones: tuple[str, ...]
    marginal: bool | None
    row: int


@dataclass(frozen=True)
class PhoibleInventory:
    """A selected doculect inventory and its explicit import report.

    ``Phoneset`` currently carries only names and strings, so allophones and
    marginality remain on ``entries``.  ``refusals`` is the deliberate seam:
    every PHOIBLE spelling is either read under the house's declared
    canonicalization (Unicode normalization and the aliases ``ipa.xml``
    declares) or refused with its position — never repaired ad hoc or
    silently dropped.
    """

    provenance: PhoibleProvenance
    phoneset: Phoneset
    entries: tuple[PhoibleEntry, ...]
    refusals: tuple[PhoibleRefusal, ...]


@dataclass(frozen=True)
class PhoibleSpread:
    """All source inventories attested for a language code."""

    code: str
    inventories: tuple[PhoibleProvenance, ...]


@dataclass(frozen=True)
class PhoibleAudit:
    """Whole-checkout primary-segment acceptance counts and refusal reasons."""

    rows: int
    accepted_rows: int
    refused_rows: int
    inventories: int
    accepted_inventories: int
    refused_inventories: int
    refusal_reasons: tuple[tuple[str, int], ...]


def _root(path: str | Path | None) -> Path | None:
    supplied = path if path is not None else os.environ.get(PHOIBLE_ENV)
    if supplied is None:
        return None
    resolved = Path(supplied).expanduser()
    if resolved.name == "phoible.csv":
        resolved = resolved.parent.parent
    required = (
        resolved / "data" / "phoible.csv",
        resolved / "mappings" / "InventoryID-LanguageCodes.csv",
        resolved / "mappings" / "InventoryID-Bibtex.csv",
    )
    missing = [str(item) for item in required if not item.is_file()]
    if missing:
        raise PhoibleDataUnavailable(
            "PHOIBLE data is unavailable; missing " + ", ".join(missing)
        )
    return resolved


def _inventory_sort(value: str) -> tuple[int, int | str]:
    return (0, int(value)) if value.isdecimal() else (1, value)


class PhoibleBridge(ProviderBridge):
    """Provider for PHOIBLE inventories without merging rival doculects."""

    def __init__(self, path: str | Path | None = None) -> None:
        """Select explicit path, then environment, otherwise the shipped snapshot."""
        self.root = _root(path)
        super().__init__(
            "phoible",
            (
                "external-checkout"
                if self.root is not None
                else source_policy()["revision"]
            ),
            (
                f"generated from {self.root}"
                if self.root is not None
                else "shipped PHOIBLE development snapshot (separately licensed source aggregate)"
            ),
            RoundTripReport(
                RoundTripLeg(
                    "external-to-house",
                    Fidelity.LOSSY_WITH_REPORT,
                    ("spellings refused by the house IPA parser",),
                ),
                RoundTripLeg(
                    "house-to-external",
                    Fidelity.LOSSY_WITH_REPORT,
                    ("phones absent from the selected PHOIBLE inventory",),
                ),
            ),
        )
        self._metadata = self._read_metadata()
        self._bibtex = self._read_bibtex()

    def _open(self, name: str, *, encoding: str = "utf-8") -> TextIO:
        if self.root is not None:
            return (self.root / name).open(encoding=encoding, newline="")
        return io.TextIOWrapper(
            io.BytesIO(read_source(name)), encoding=encoding, newline=""
        )

    def _read_metadata(self) -> dict[str, dict[str, str]]:
        with self._open("mappings/InventoryID-LanguageCodes.csv") as stream:
            rows = list(csv.DictReader(stream))
        return {row["InventoryID"]: row for row in rows}

    def _read_bibtex(self) -> dict[str, tuple[str, ...]]:
        found: dict[str, list[str]] = defaultdict(list)
        with self._open(
            "mappings/InventoryID-Bibtex.csv", encoding="utf-8-sig"
        ) as stream:
            for row in csv.DictReader(stream):
                key = row["BibtexKey"]
                if key not in found[row["InventoryID"]]:
                    found[row["InventoryID"]].append(key)
        return {inventory_id: tuple(keys) for inventory_id, keys in found.items()}

    def _provenance(self, inventory_id: str) -> PhoibleProvenance:
        try:
            row = self._metadata[inventory_id]
        except KeyError as error:
            raise KeyError(f"PHOIBLE has no inventory {inventory_id!r}") from error
        keys = self._bibtex.get(inventory_id, ())
        if not keys:
            raise ValueError(f"PHOIBLE inventory {inventory_id} has no BibTeX key")
        return PhoibleProvenance(
            inventory_id,
            row["Glottocode"],
            row["ISO6393"],
            row["LanguageName"],
            row["Source"],
            keys,
        )

    def language(self, code: str) -> PhoibleSpread:
        """Return every inventory for an ISO 639-3 code or Glottocode.

        Even a one-item answer has the spread shape.  Selection is exclusively
        by :meth:`inventory`; this makes the no-silent-merge law structural.
        """
        matches = [
            inventory_id
            for inventory_id, row in self._metadata.items()
            if code in (row["ISO6393"], row["Glottocode"])
        ]
        if not matches:
            raise KeyError(f"PHOIBLE has no inventories for language {code!r}")
        matches.sort(key=_inventory_sort)
        return PhoibleSpread(code, tuple(self._provenance(item) for item in matches))

    @staticmethod
    def _house_segment(
        ipa: IPAFeatures, value: str | None, row: int, field: str
    ) -> tuple[str | None, PhoibleRefusal | None]:
        if value is None:
            return None, PhoibleRefusal(row, field, "", "row is missing this column")
        try:
            canonical = ipa.from_wild(value)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                tokens = ipa.tokenize(canonical, strict=True)
            if caught:
                raise ValueError("; ".join(str(item.message) for item in caught))
            if not tokens:
                raise ValueError("parses as no house segments")
            # A PHOIBLE CSV row declares the inventory member boundary.  House
            # Phonesets can represent compound members, so an untied affricate
            # or diphthong stays an explicit sequence; no tie is invented.
            return "".join(tokens), None
        except (ValueError, KeyError) as error:
            return None, PhoibleRefusal(row, field, value, str(error))

    def inventory(
        self, inventory_id: str | int, *, ipa: IPAFeatures | None = None
    ) -> PhoibleInventory:
        """Import exactly one InventoryID as a house phoneset plus refusals."""
        key = str(inventory_id)
        provenance = self._provenance(key)
        features = ipa or IPAFeatures()
        entries: list[PhoibleEntry] = []
        refusals: list[PhoibleRefusal] = []
        with self._open("data/phoible.csv") as stream:
            for row_number, row in enumerate(csv.DictReader(stream), 2):
                if row["InventoryID"] != key:
                    continue
                phoneme, refusal = self._house_segment(
                    features, row["Phoneme"], row_number, "Phoneme"
                )
                if refusal is not None:
                    refusals.append(refusal)
                    continue
                allophones: list[str] = []
                if row["Allophones"] not in ("", "NA"):
                    for value in row["Allophones"].split():
                        accepted, allophone_refusal = self._house_segment(
                            features, value, row_number, "Allophones"
                        )
                        if allophone_refusal is not None:
                            refusals.append(allophone_refusal)
                        elif accepted is not None:
                            allophones.append(accepted)
                marginal = {"TRUE": True, "FALSE": False, "NA": None, "": None}.get(
                    row["Marginal"]
                )
                if marginal is None and row["Marginal"] not in ("NA", ""):
                    refusals.append(
                        PhoibleRefusal(
                            row_number,
                            "Marginal",
                            row["Marginal"],
                            "expected TRUE, FALSE, or NA",
                        )
                    )
                entries.append(
                    PhoibleEntry(phoneme or "", tuple(allophones), marginal, row_number)
                )
        if not entries and not refusals:
            raise ValueError(f"PHOIBLE inventory {key} has no segment rows")
        phoneset = Phoneset(
            name=f"phoible-{key}", phones=[entry.phoneme for entry in entries]
        )
        return PhoibleInventory(provenance, phoneset, tuple(entries), tuple(refusals))

    def audit(self, *, ipa: IPAFeatures | None = None) -> PhoibleAudit:
        """Parse every primary segment once and summarize positioned refusals."""
        features = ipa or IPAFeatures()
        rows = accepted = 0
        inventory_ids: set[str] = set()
        refused_ids: set[str] = set()
        reasons: dict[str, int] = defaultdict(int)
        with self._open("data/phoible.csv") as stream:
            for row_number, row in enumerate(csv.DictReader(stream), 2):
                rows += 1
                inventory_ids.add(row["InventoryID"])
                _, refusal = self._house_segment(
                    features, row["Phoneme"], row_number, "Phoneme"
                )
                if refusal is None:
                    accepted += 1
                else:
                    refused_ids.add(row["InventoryID"])
                    reasons[refusal.reason] += 1
        return PhoibleAudit(
            rows,
            accepted,
            rows - accepted,
            len(inventory_ids),
            len(inventory_ids - refused_ids),
            len(refused_ids),
            tuple(sorted(reasons.items(), key=lambda item: (-item[1], item[0]))),
        )
