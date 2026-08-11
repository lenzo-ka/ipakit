"""Declared vocabularies written as groupings over house IPA units."""

from __future__ import annotations

import dataclasses
import json
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
    kind: str = "unit"


@dataclass(frozen=True)
class ProjectionDrop:
    """One declared loss at a half-open span of house units."""

    name: str
    span: tuple[int, int]
    content: str
    output: str

    def to_dict(self) -> dict[str, object]:
        """Return this loss as JSON-compatible data."""
        return {
            "name": self.name,
            "span": list(self.span),
            "content": self.content,
            "output": self.output,
        }


@dataclass(frozen=True)
class ProjectionReport:
    """The declared losses exercised by one house-to-vocabulary projection."""

    drops: tuple[ProjectionDrop, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Return this report as JSON-compatible data."""
        return {"drops": [drop.to_dict() for drop in self.drops]}


@dataclass(frozen=True)
class VocabularyProjection:
    """A vocabulary-grouped house form and its per-form loss report."""

    form: Form
    report: ProjectionReport

    def to_dict(self, self_contained: bool = False) -> dict[str, object]:
        """Serialize the grouped form and its report beside one another."""
        return {
            "form": self.form.to_dict(self_contained=self_contained),
            "report": self.report.to_dict(),
        }

    def to_json(self, self_contained: bool = False) -> str:
        """Serialize the grouped form and report as Unicode JSON."""
        return json.dumps(self.to_dict(self_contained), ensure_ascii=False)


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
        mapper = root.find("mapper")
        self.tie_drop = mapper.attrib.get("tie-drop") if mapper is not None else None
        self.boundary_drop = (
            mapper.attrib.get("boundary-drop") if mapper is not None else None
        )
        atoms_list: list[Atom] = []
        output_positions: dict[str, int] = {}
        for position, item in enumerate(root.findall("atom"), start=1):
            spelling = item.attrib.get("spelling")
            if not spelling:
                raise ValueError(
                    f"{self.name} vocabulary atom {position} has no spelling"
                )
            kind = item.attrib.get("kind", "unit")
            probe = spelling + "a" if kind == "prefix" else spelling
            try:
                Form.parse(probe, strict=True)
            except ValueError as error:
                qualification = (
                    "a house IPA prefix" if kind == "prefix" else "house IPA"
                )
                raise ValueError(
                    f"{self.name} vocabulary atom {position} spelling "
                    f"{spelling!r} is not {qualification}: {error}"
                ) from error
            output = item.attrib.get("output", spelling)
            if not output:
                raise ValueError(
                    f"{self.name} vocabulary atom {position} has empty output"
                )
            if output in output_positions:
                raise ValueError(
                    f"{self.name} vocabulary atom {position} output {output!r} "
                    f"duplicates atom {output_positions[output]}"
                )
            output_positions[output] = position
            atoms_list.append(
                Atom(
                    spelling,
                    output,
                    item.attrib.get("exemplar"),
                    item.attrib.get("notes"),
                    kind,
                )
            )
        atoms = tuple(atoms_list)
        if not atoms:
            raise ValueError(f"{self.name} vocabulary declares no atoms")
        self.atoms = atoms
        self._by_output = {atom.output: atom for atom in atoms}
        self._ordered = tuple(
            sorted(atoms, key=lambda atom: len(atom.output), reverse=True)
        )
        self._unit_patterns = tuple(
            sorted(
                (
                    (
                        tuple(
                            unit.text
                            for unit in Form.parse(atom.spelling, strict=True).units
                        ),
                        atom,
                    )
                    for atom in atoms
                    if atom.kind == "unit"
                ),
                key=lambda item: len(item[0]),
                reverse=True,
            )
        )
        reductions: dict[str, tuple[Atom, str]] = {}
        if mapper is not None:
            declared_drops = set(self.round_trip.house_to_external.drops)
            for item in mapper.findall("reduction"):
                source = item.attrib["source"]
                target = item.attrib["target"]
                drop = item.attrib["drop"]
                parsed = Form.parse(source, strict=True)
                if len(parsed.units) != 1:
                    raise ValueError(
                        f"{self.name} mapper reduction source must be one house unit: {source!r}"
                    )
                if source in reductions:
                    raise ValueError(
                        f"{self.name} mapper duplicates reduction {source!r}"
                    )
                if target not in self._by_spelling:
                    raise ValueError(
                        f"{self.name} mapper reduction target is not an atom: {target!r}"
                    )
                if drop not in declared_drops:
                    raise ValueError(
                        f"{self.name} mapper reduction names undeclared drop {drop!r}"
                    )
                reductions[source] = (self._by_spelling[target], drop)
            for label in (self.tie_drop, self.boundary_drop):
                if label is not None and label not in declared_drops:
                    raise ValueError(
                        f"{self.name} mapper names undeclared drop {label!r}"
                    )
        self._reductions = reductions

    def tokenize(self, text: str | Sequence[str]) -> tuple[Atom, ...]:
        """Resolve text by longest match, or a sequence as segmented atoms.

        The declared separator is skipped wherever it occurs, so the
        vocabulary reads its own default emission.
        """

        if not isinstance(text, str):
            out = []
            for index, token in enumerate(text):
                atom = self._by_output.get(token)
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
                    if text.startswith(candidate.output, position)
                ),
                None,
            )
            if atom is None:
                end = position + 1
                while end < len(text) and not any(
                    text.startswith(candidate.output, end)
                    for candidate in self._ordered
                ):
                    end += 1
                raise VocabularyResidueError(
                    f"{self.name} vocabulary has unvocabularied residue at span "
                    f"[{position}:{end}]: {text[position:end]!r}"
                )
            out.append(atom)
            position += len(atom.output)
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
        units = [
            (ref, handles[ref])
            for ref in sorted(
                handles,
                key=lambda ref: (
                    form._graph.at(ref).features.get("compatibility-index", 10**9),
                    ref,
                ),
            )
            if isinstance(form._graph.at(ref).features.get("compatibility-index"), int)
        ]
        cursor = 0
        prefixes: list[Atom] = []
        for atom in atoms:
            if atom.kind == "prefix":
                prefixes.append(atom)
                continue
            width = len(Form.parse(atom.spelling, strict=True).units)
            grouped_spelling = (
                "".join(prefix.spelling for prefix in prefixes) + atom.spelling
            )
            grouped_output = "".join(prefix.output for prefix in prefixes) + atom.output
            owned = units[cursor : cursor + width]
            start = int(owned[0][0].split("/")[2])
            last_ref = owned[-1][0]
            last_tick = int(last_ref.split("/")[2])
            duration = (
                last_tick - start + (form._graph.at(last_ref).structural_duration or 0)
            )
            parent = builder.add_event(
                self.tier,
                start,
                {
                    "atom": grouped_spelling,
                    "output": grouped_output,
                    **({"exemplar": atom.exemplar} if atom.exemplar else {}),
                    **({"notes": atom.notes} if atom.notes else {}),
                },
                duration=duration,
            )
            builder.contain(parent, (handle for _, handle in owned), relation="groups")
            cursor += width
            prefixes.clear()
        return Form._from_graph(builder.build(), spelling=ipa)

    def emit(
        self, form: Form | VocabularyProjection, *, separator: str | None = None
    ) -> str:
        """Emit grouped atoms, using the declared separator unless overridden.

        Pass ``separator=""`` explicitly to concatenate atom outputs without
        preserving their segmentation.
        """

        if isinstance(form, VocabularyProjection):
            form = form.form
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

    def map(self, form: Form) -> VocabularyProjection:
        """Project house units into declared atoms by longest match.

        Exact atom spellings, declared one-unit reductions, and tied units
        whose untied sequential spelling is an atom are the only routes.
        Anything else is positioned residue, never a similarity guess.
        """
        units = form.units
        if not units:
            raise VocabularyResidueError(
                f"{self.name} vocabulary has unvocabularied residue at span [0:0]: ''"
            )
        matches: list[tuple[int, int, Atom]] = []
        drops: list[ProjectionDrop] = []
        position = 0
        while position < len(units):
            exact = next(
                (
                    (pattern, atom)
                    for pattern, atom in self._unit_patterns
                    if tuple(
                        unit.text for unit in units[position : position + len(pattern)]
                    )
                    == pattern
                ),
                None,
            )
            if exact is not None:
                pattern, atom = exact
                end = position + len(pattern)
                if len(pattern) > 1 and self.boundary_drop is not None:
                    content = "".join(unit.text for unit in units[position:end])
                    drops.append(
                        ProjectionDrop(
                            self.boundary_drop, (position, end), content, atom.output
                        )
                    )
            else:
                source = units[position].text
                reduction = self._reductions.get(source)
                if reduction is not None:
                    atom, drop = reduction
                    end = position + 1
                    drops.append(
                        ProjectionDrop(drop, (position, end), source, atom.output)
                    )
                else:
                    sequential = source.replace("͡", "").replace("͜", "")
                    tied_atom = self._by_spelling.get(sequential)
                    if (
                        sequential == source
                        or tied_atom is None
                        or self.tie_drop is None
                    ):
                        end = position + 1
                        raise VocabularyResidueError(
                            f"{self.name} vocabulary has unvocabularied residue at span "
                            f"[{position}:{end}]: {source!r}"
                        )
                    atom = tied_atom
                    end = position + 1
                    drops.append(
                        ProjectionDrop(
                            self.tie_drop, (position, end), source, atom.output
                        )
                    )
            matches.append((position, end, atom))
            position = end

        old = form._graph.declarations
        feature_names = {feature.name for feature in old.features}
        additions = tuple(
            FeatureDeclaration(name)
            for name in ("atom", "output", "exemplar", "notes")
            if name not in feature_names
        )
        tier_names = {tier.name for tier in old.tiers}
        relation_names = {relation.name for relation in old.relations}
        declared = Declarations(
            old.tiers
            + (
                ()
                if self.tier in tier_names
                else (
                    TierDeclaration(
                        self.tier, frozenset({"atom", "output", "exemplar", "notes"})
                    ),
                )
            ),
            old.features + additions,
            old.relations
            + (
                ()
                if "groups" in relation_names
                else (
                    RelationDeclaration(
                        "groups",
                        acyclic=True,
                        containment=True,
                        source_tiers=frozenset({self.tier}),
                        target_tiers=frozenset({"segment", "zero", "boundary"}),
                    ),
                )
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
        for start, end, atom in matches:
            parent = builder.add_event(
                self.tier,
                start,
                {
                    "atom": atom.spelling,
                    "output": atom.output,
                    **({"exemplar": atom.exemplar} if atom.exemplar else {}),
                    **({"notes": atom.notes} if atom.notes else {}),
                },
                duration=end - start,
            )
            builder.contain(parent, unit_handles[start:end], relation="groups")
        mapped = Form._from_graph(builder.build(), spelling=form.spelling)
        return VocabularyProjection(mapped, ProjectionReport(tuple(drops)))
