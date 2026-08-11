"""Declared vocabularies written as groupings over house IPA units."""

from __future__ import annotations

import dataclasses
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .._codecs import RenderLane, RenderProfile, render_graph
from .._tiergraph import (
    Declarations,
    FeatureDeclaration,
    RelationDeclaration,
    TierDeclaration,
)
from .._tiergraph_builder import _copy_builder
from ..form import Form
from .base import Bridge, Fidelity, RoundTripLeg, RoundTripReport


class VocabularyResidueError(ValueError):
    """Input contains a span that no declared atom owns."""


@dataclass(frozen=True)
class Atom:
    """One declared external spelling and the value emitted for its group."""

    spelling: str
    output: str
    exemplar: str | None = None
    notes: str | None = None


def _leg(element: ET.Element, direction: str) -> RoundTripLeg:
    return RoundTripLeg(
        direction,
        Fidelity(element.attrib["fidelity"]),
        tuple(item.attrib["name"] for item in element.findall("drop")),
        tuple(item.attrib["name"] for item in element.findall("trick")),
    )


class VocabularyBridge(Bridge):
    """Longest-match tokenizer and structural renderer for one declaration."""

    def __init__(self, declaration: Path):
        """Load and check the vocabulary declaration at ``declaration``."""

        root = ET.parse(declaration).getroot()
        if root.tag != "vocabulary":
            raise ValueError(f"{declaration} is not a vocabulary declaration")
        report = root.find("round-trip")
        if report is None:
            raise ValueError("vocabulary declaration has no round-trip classification")
        outward = report.find("external-to-house")
        inward = report.find("house-to-external")
        if outward is None or inward is None:
            raise ValueError("vocabulary declaration must classify both directions")
        super().__init__(
            root.attrib["name"],
            root.attrib["version"],
            root.attrib["provenance"],
            RoundTripReport(
                _leg(outward, "external-to-house"), _leg(inward, "house-to-external")
            ),
        )
        self.tier = root.attrib.get("tier", "vocabulary")
        self.source_style = root.attrib.get("source-style", "text")
        self.separator = root.attrib.get("separator", "")
        atoms_list: list[Atom] = []
        positions: dict[str, int] = {}
        for position, item in enumerate(root.findall("atom"), start=1):
            spelling = item.attrib.get("spelling")
            if not spelling:
                raise ValueError(
                    f"{self.name} vocabulary atom {position} has no spelling"
                )
            if spelling in positions:
                raise ValueError(
                    f"{self.name} vocabulary atom {position} spelling {spelling!r} "
                    f"duplicates atom {positions[spelling]}"
                )
            try:
                Form.parse(spelling, strict=True)
            except ValueError as error:
                raise ValueError(
                    f"{self.name} vocabulary atom {position} spelling "
                    f"{spelling!r} is not house IPA: {error}"
                ) from error
            positions[spelling] = position
            atoms_list.append(
                Atom(
                    spelling,
                    item.attrib.get("output", spelling),
                    item.attrib.get("exemplar"),
                    item.attrib.get("notes"),
                )
            )
        atoms = tuple(atoms_list)
        if not atoms:
            raise ValueError(f"{self.name} vocabulary declares no atoms")
        self.atoms = atoms
        self._by_spelling = {atom.spelling: atom for atom in atoms}
        self._ordered = tuple(
            sorted(atoms, key=lambda atom: len(atom.spelling), reverse=True)
        )

    def tokenize(self, text: str | Sequence[str]) -> tuple[Atom, ...]:
        """Resolve text by longest match, or a sequence as segmented atoms.

        The declared separator is skipped wherever it occurs, so the
        vocabulary reads its own default emission.
        """

        if not isinstance(text, str):
            out = []
            for index, token in enumerate(text):
                atom = self._by_spelling.get(token)
                if atom is None:
                    raise VocabularyResidueError(
                        f"{self.name} vocabulary has no atom for token {index}: {token!r}"
                    )
                out.append(atom)
            return tuple(out)
        out = []
        position = 0
        while position < len(text):
            if self.separator and text.startswith(self.separator, position):
                position += len(self.separator)
                continue
            atom = next(
                (
                    candidate
                    for candidate in self._ordered
                    if text.startswith(candidate.spelling, position)
                ),
                None,
            )
            if atom is None:
                end = position + 1
                while end < len(text) and not any(
                    text.startswith(candidate.spelling, end)
                    for candidate in self._ordered
                ):
                    end += 1
                raise VocabularyResidueError(
                    f"{self.name} vocabulary has unvocabularied residue at span "
                    f"[{position}:{end}]: {text[position:end]!r}"
                )
            out.append(atom)
            position += len(atom.spelling)
        return tuple(out)

    def read(self, text: str | Sequence[str]) -> Form:
        """Read external atoms into house IPA with their grouping tier intact."""

        atoms = self.tokenize(text)
        ipa = "".join(atom.spelling for atom in atoms)
        form = Form.parse(ipa, strict=True)
        old = form._graph.declarations
        feature_names = {feature.name for feature in old.features}
        additions = tuple(
            FeatureDeclaration(name)
            for name in ("atom", "output", "exemplar", "notes")
            if name not in feature_names
        )
        declared = Declarations(
            old.tiers
            + (
                TierDeclaration(
                    self.tier, frozenset({"atom", "output", "exemplar", "notes"})
                ),
            ),
            old.features + additions,
            old.relations
            + (
                RelationDeclaration(
                    "groups",
                    acyclic=True,
                    containment=True,
                    source_tiers=frozenset({self.tier}),
                    target_tiers=frozenset({"segment", "zero", "boundary"}),
                ),
            ),
        )
        graph = dataclasses.replace(form._graph, declarations=declared)
        builder, handles = _copy_builder(graph)
        unit_handles = [
            handles[ref]
            for ref in sorted(
                handles,
                key=lambda ref: (
                    form._graph.at(ref).features.get("compatibility-index", 10**9),
                    ref,
                ),
            )
            if isinstance(form._graph.at(ref).features.get("compatibility-index"), int)
        ]
        offset = 0
        for atom in atoms:
            width = len(Form.parse(atom.spelling, strict=True).units)
            parent = builder.add_event(
                self.tier,
                offset,
                {
                    "atom": atom.spelling,
                    "output": atom.output,
                    **({"exemplar": atom.exemplar} if atom.exemplar else {}),
                    **({"notes": atom.notes} if atom.notes else {}),
                },
                duration=width,
            )
            builder.contain(
                parent, unit_handles[offset : offset + width], relation="groups"
            )
            offset += width
        return Form._from_graph(builder.build(), spelling=ipa)

    def emit(self, form: Form, *, separator: str | None = None) -> str:
        """Emit grouped atoms, using the declared separator unless overridden.

        Pass ``separator=""`` explicitly to concatenate atom outputs without
        preserving their segmentation.
        """

        if separator is None:
            separator = self.separator
        profile = RenderProfile((RenderLane(self.tier, "output"),))
        rendered = render_graph(form._graph, profile)
        if not separator:
            return rendered
        values: list[str] = []
        for node in form._graph.clock:
            for group in node.groups:
                if group.tier == self.tier:
                    values.extend(
                        str(event.features["output"]) for event in group.events
                    )
        return separator.join(values)
