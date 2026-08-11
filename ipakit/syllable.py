"""Construct language-relative syllabifiers from declared span constraints.

The declarations are the phonology; this module is only the mechanism which
validates candidates, locates their edges, and writes intervals.  The optional
sonority ordering is a model of syllabic prominence, not a phonetic fact, and
is used only when a declaration explicitly asks for it.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .constants import DATA_DIR
from .features import IPAFeatures  # noqa: E402
from .form import Form, Interval, Unit, tier_names
from .rules import Pattern, RuleError, _pattern

SYLLABLES_DIR = Path(DATA_DIR) / "syllables"


def _default(features: IPAFeatures | None) -> IPAFeatures:
    if features is not None:
        return features
    from . import _get_ipa

    return _get_ipa()


@dataclass(frozen=True)
class Span:
    """One declared sequence of rule-engine patterns."""

    source: str
    terms: tuple[Pattern, ...]

    def matches(self, units: Sequence[Unit], features: IPAFeatures) -> bool:
        if len(units) != len(self.terms):
            return False
        bindings: dict[str, str] = {}
        return all(
            pattern.matches(unit, features, bindings)
            for pattern, unit in zip(self.terms, units, strict=True)
        )


@dataclass(frozen=True)
class Language:
    """Validated declarations supplied to the constructor."""

    name: str
    mode: str
    provenance: str
    nuclei: tuple[Span, ...] = ()
    onsets: tuple[Span, ...] = ()
    morae: tuple[Span, ...] = ()
    syllables: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Conflict:
    """A stated syllable edge and the different freely derived edge(s)."""

    at: int
    stated: int
    derived: tuple[int, ...]
    text: str = "."


@dataclass(frozen=True)
class Syllabification:
    """A form carrying the derived tiers and any stated-mark conflicts."""

    form: Form
    conflicts: tuple[Conflict, ...] = ()
    unsyllabified: tuple[tuple[int, int], ...] = ()

    @property
    def syllables(self) -> tuple[Interval, ...]:
        return tuple(i for i in self.form.intervals if i.tier == "syllable")

    @property
    def morae(self) -> tuple[Interval, ...]:
        return tuple(i for i in self.form.intervals if i.tier == "mora")

    def spelled(self, tier: str = "syllable") -> tuple[str, ...]:
        return tuple(
            "".join(u.text for u in self.form.units[i.start : i.end])
            for i in self.form.intervals
            if i.tier == tier
        )

    def marks(self) -> str:
        cuts = {i.start for i in self.syllables} | {i.end for i in self.syllables}
        out: list[str] = []
        for n, unit in enumerate(self.form.units):
            if (
                n in cuts
                and out
                and not unit.is_boundary
                and not self.form.units[n - 1].is_boundary
            ):
                out.append(".")
            out.append(unit.text)
        return "".join(out)

    def __len__(self) -> int:
        return len(self.syllables)


def _terms(source: str, features: IPAFeatures) -> Span:
    # Spaces delimit unit patterns in the landed rule notation; brackets
    # contain no spaces in shipped declarations.
    tokens = re.findall(r"\[[^]]+\]|\([^)]*\)|\S+", source)
    terms = tuple(_pattern(term, features) for term in tokens)
    if not terms:
        raise RuleError("a declared span must contain at least one term")
    variables: dict[str, int] = {}
    for term in terms:
        if term.names_boundary or term.names_tier:
            raise RuleError(
                f"{source!r} names structure where a segment span is required"
            )
        for agreement in term.agreements.values():
            variables[agreement.name] = variables.get(agreement.name, 0) + 1
    lone = sorted(name for name, count in variables.items() if count == 1)
    if lone:
        raise RuleError(f"{source!r} uses agreement variable(s) {' '.join(lone)} once")
    return Span(source, terms)


def read_language(path: str | Path, features: IPAFeatures | None = None) -> Language:
    """Read one XML language declaration after RELAX NG validation."""
    features = _default(features)
    path = Path(path)
    try:
        from lxml import etree  # type: ignore[import-untyped]

        schema = etree.RelaxNG(etree.parse(str(SYLLABLES_DIR / "syllables.rng")))
        document = etree.parse(str(path))
        schema.assertValid(document)
    except ImportError:  # pragma: no cover - lxml is a project dependency
        pass
    root = ET.parse(path).getroot()
    groups: dict[str, list[Span]] = {"nucleus": [], "onset": [], "mora": []}
    for kind in groups:
        groups[kind] = [_terms(e.attrib["span"], features) for e in root.findall(kind)]
    return Language(
        root.attrib["language"],
        root.attrib["mode"],
        root.attrib["provenance"],
        tuple(groups["nucleus"]),
        tuple(groups["onset"]),
        tuple(groups["mora"]),
        frozenset(e.attrib["ipa"] for e in root.findall("syllable")),
    )


def languages() -> tuple[str, ...]:
    return tuple(sorted(p.stem for p in SYLLABLES_DIR.glob("*.xml")))


def language(name: str, features: IPAFeatures | None = None) -> Language:
    path = SYLLABLES_DIR / f"{name}.xml"
    if not path.is_file():
        raise ValueError(
            f"no syllable declaration {name!r}; available: {', '.join(languages())}"
        )
    return read_language(path, features)


def _segments_before(units: Sequence[Unit]) -> list[int]:
    out = [0]
    for unit in units:
        out.append(out[-1] + (unit.segment is not None))
    return out


@dataclass(frozen=True)
class Syllabifier:
    """A Form-to-Intervals syllabifier built from one language declaration."""

    language: Language
    features: IPAFeatures = field(repr=False)

    def __call__(self, form: Form | str) -> Syllabification:
        if isinstance(form, str):
            form = Form.parse(form, self.features)
        honored, empty = self._derive(form.units, True)
        free, _ = self._derive(form.units, False)
        intervals = [*honored, *self._morae(form.units, honored)]
        return Syllabification(
            Form.of(form.units, [*form.intervals, *intervals]),
            self._conflicts(form.units, honored, free),
            tuple(empty),
        )

    def _is_nucleus(self, unit: Unit) -> bool:
        return unit.segment is not None and (
            "stress" in unit.prosody
            or any(
                span.matches((unit,), self.features) for span in self.language.nuclei
            )
        )

    def _delimiters(self, units: Sequence[Unit], honor: bool) -> list[int]:
        return [
            i
            for i, u in enumerate(units)
            if u.is_boundary
            and u.features.get("linking") != "+"
            and (u.level != "syllable" or honor)
        ]

    def _derive(
        self, units: Sequence[Unit], honor: bool
    ) -> tuple[list[Interval], list[tuple[int, int]]]:
        out: list[Interval] = []
        empty: list[tuple[int, int]] = []
        start = 0
        for stop in [*self._delimiters(units, honor), len(units)]:
            if start < stop:
                spans = self._within(units, start, stop)
                out.extend(spans)
                if not spans and any(u.segment is not None for u in units[start:stop]):
                    empty.append((start, stop))
            start = stop + 1
        return out, empty

    def _within(self, units: Sequence[Unit], start: int, stop: int) -> list[Interval]:
        if self.language.mode == "enumerated":
            return self._enumerate(units, start, stop)
        nuclei = [i for i in range(start, stop) if self._is_nucleus(units[i])]
        if not nuclei:
            return []
        edges = [
            start,
            *(self._cut(units, a, b) for a, b in zip(nuclei, nuclei[1:], strict=False)),
            stop,
        ]
        return [
            Interval("syllable", a, b, self.features)
            for a, b in zip(edges, edges[1:], strict=False)
        ]

    def _cut(self, units: Sequence[Unit], left: int, right: int) -> int:
        # First match is maximal onset. A failed longer span locates the edge
        # at the first suffix which satisfies a declared constraint.
        for gap in range(left + 1, right + 1):
            candidate = tuple(u for u in units[gap:right] if u.segment is not None)
            if any(
                span.matches(candidate, self.features) for span in self.language.onsets
            ):
                return gap
        return right

    def _enumerate(
        self, units: Sequence[Unit], start: int, stop: int
    ) -> list[Interval]:
        out: list[Interval] = []
        at = start
        while at < stop:
            matches = []
            for end in range(at + 1, stop + 1):
                text = "".join(u.text for u in units[at:end] if u.segment is not None)
                if text in self.language.syllables:
                    matches.append(end)
            if not matches:
                return []
            end = max(matches)
            out.append(Interval("syllable", at, end, self.features))
            at = end
        return out

    def _morae(
        self, units: Sequence[Unit], syllables: Sequence[Interval]
    ) -> list[Interval]:
        if self.language.mode != "moraic":
            return []
        out: list[Interval] = []
        for syllable in syllables:
            for i in range(syllable.start, syllable.end):
                unit = units[i]
                if unit.segment is None:
                    continue
                matching = [
                    m for m in self.language.morae if m.matches((unit,), self.features)
                ]
                if matching:
                    out.append(Interval("mora", i, i + 1, self.features))
                    if unit.prosody.get("length") == "long":
                        out.append(Interval("mora", i, i + 1, self.features))
        return out

    def _conflicts(
        self,
        units: Sequence[Unit],
        honored: Sequence[Interval],
        free: Sequence[Interval],
    ) -> tuple[Conflict, ...]:
        before = _segments_before(units)
        derived = {before[i.start] for i in free} | {before[i.end] for i in free}
        return tuple(
            Conflict(n, before[n], tuple(sorted(derived - {before[n]})), u.text)
            for n, u in enumerate(units)
            if u.is_boundary and u.level == "syllable" and before[n] not in derived
        )


def syllabifier(
    name: str | Language, features: IPAFeatures | None = None
) -> Syllabifier:
    features = _default(features)
    if not {"syllable", "mora"} <= set(tier_names(features)):
        raise ValueError("the inventory must declare syllable and mora tiers")
    return Syllabifier(
        language(name, features) if isinstance(name, str) else name, features
    )


def syllabify(
    form: Form | str, name: str, features: IPAFeatures | None = None
) -> Syllabification:
    return syllabifier(name, features)(form)
