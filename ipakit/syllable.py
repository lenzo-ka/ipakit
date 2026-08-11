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
    codas: tuple[Span, ...] = ()


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
    groups: dict[str, list[Span]] = {"nucleus": [], "onset": [], "coda": [], "mora": []}
    for kind in groups:
        groups[kind] = [_terms(e.attrib["span"], features) for e in root.findall(kind)]
    declared_syllables = list(root.findall("syllable"))
    inventory = root.find("inventory")
    if inventory is not None:
        source = (path.parent / inventory.attrib["source"]).resolve()
        declared_syllables.extend(ET.parse(source).getroot().findall("syllable"))
    return Language(
        name=root.attrib["language"],
        mode=root.attrib["mode"],
        provenance=root.attrib["provenance"],
        nuclei=tuple(groups["nucleus"]),
        onsets=tuple(groups["onset"]),
        codas=tuple(groups["coda"]),
        morae=tuple(groups["mora"]),
        syllables=frozenset(e.attrib["ipa"] for e in declared_syllables),
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
        if self.language.mode == "moraic":
            honored, morae, empty = self._derive_moraic(form.units, True)
            free, _, _ = self._derive_moraic(form.units, False)
            intervals = [*honored, *morae]
        else:
            honored, empty = self._derive(form.units, True)
            free, _ = self._derive(form.units, False)
            intervals = honored
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
                spans, residue = self._within(units, start, stop)
                out.extend(spans)
                empty.extend(residue)
                if (
                    not spans
                    and not residue
                    and any(u.segment is not None for u in units[start:stop])
                ):
                    empty.append((start, stop))
            start = stop + 1
        return out, empty

    def _derive_moraic(
        self, units: Sequence[Unit], honor: bool
    ) -> tuple[list[Interval], list[Interval], list[tuple[int, int]]]:
        syllables: list[Interval] = []
        morae: list[Interval] = []
        empty: list[tuple[int, int]] = []
        start = 0
        for stop in [*self._delimiters(units, honor), len(units)]:
            if start < stop:
                grouped, tiled, residue = self._moraic_region(units, start, stop)
                syllables.extend(grouped)
                morae.extend(tiled)
                empty.extend(residue)
            start = stop + 1
        return syllables, morae, empty

    def _moraic_region(
        self, units: Sequence[Unit], start: int, stop: int
    ) -> tuple[list[Interval], list[Interval], list[tuple[int, int]]]:
        """Tile a region with morae, then group those morae into syllables."""
        entries: list[tuple[Interval, bool]] = []
        residue: list[tuple[int, int]] = []
        at = start
        have_nucleus = False
        while at < stop:
            unit = units[at]
            if unit.segment is None:
                at += 1
                have_nucleus = False
                continue
            candidates: list[tuple[int, bool]] = []
            for span in self.language.morae:
                end = at + len(span.terms)
                if end <= stop and span.matches(units[at:end], self.features):
                    bears_nucleus = any(self._is_nucleus(u) for u in units[at:end])
                    candidates.append((end, bears_nucleus))
            weights = [candidate for candidate in candidates if not candidate[1]]
            nuclei = [candidate for candidate in candidates if candidate[1]]
            choices = weights if have_nucleus and weights else nuclei
            if not choices:
                residue.append((at, at + 1))
                at += 1
                have_nucleus = False
                continue
            end, bears_nucleus = max(choices, key=lambda candidate: candidate[0])
            entries.append((Interval("mora", at, end, self.features), bears_nucleus))
            if bears_nucleus:
                nucleus = next(i for i in range(at, end) if self._is_nucleus(units[i]))
                if units[nucleus].prosody.get("length") == "long":
                    entries.append(
                        (Interval("mora", nucleus, nucleus + 1, self.features), False)
                    )
            have_nucleus = True
            at = end

        syllables: list[Interval] = []
        opened: int | None = None
        closed: int | None = None
        pending_geminate = False
        for mora, bears_nucleus in entries:
            if bears_nucleus:
                if pending_geminate:
                    closed = mora.end
                    pending_geminate = False
                else:
                    if opened is not None and closed is not None:
                        syllables.append(
                            Interval("syllable", opened, closed, self.features)
                        )
                    opened = mora.start
                    closed = mora.end
            elif (
                mora.end == mora.start + 1
                and units[mora.start].prosody.get("length") == "long"
                and not self._is_nucleus(units[mora.start])
            ):
                if opened is not None and closed is not None:
                    syllables.append(
                        Interval("syllable", opened, closed, self.features)
                    )
                opened = mora.start
                closed = mora.end
                pending_geminate = True
            elif opened is not None:
                closed = max(closed or mora.end, mora.end)
        if opened is not None and closed is not None:
            syllables.append(Interval("syllable", opened, closed, self.features))
        return syllables, [mora for mora, _ in entries], residue

    def _within(
        self, units: Sequence[Unit], start: int, stop: int
    ) -> tuple[list[Interval], list[tuple[int, int]]]:
        if self.language.mode == "enumerated":
            return self._enumerate(units, start, stop), []
        nuclei = [i for i in range(start, stop) if self._is_nucleus(units[i])]
        if not nuclei:
            return [], []
        first = self._initial_edge(units, start, nuclei[0])
        last = self._final_edge(units, nuclei[-1], stop)
        edges = [
            first,
            *(self._cut(units, a, b) for a, b in zip(nuclei, nuclei[1:], strict=False)),
            last,
        ]
        residue = [
            (i, i + 1)
            for i in (*range(start, first), *range(last, stop))
            if units[i].segment is not None
        ]
        return (
            [
                Interval("syllable", a, b, self.features)
                for a, b in zip(edges, edges[1:], strict=False)
            ],
            residue,
        )

    def _initial_edge(self, units: Sequence[Unit], start: int, nucleus: int) -> int:
        """Locate the first licensed onset suffix at a region's left edge."""
        if not any(u.segment is not None for u in units[start:nucleus]):
            return start
        for edge in range(start, nucleus):
            candidate = tuple(u for u in units[edge:nucleus] if u.segment is not None)
            if any(
                span.matches(candidate, self.features) for span in self.language.onsets
            ):
                return edge
        return nucleus

    def _final_edge(self, units: Sequence[Unit], nucleus: int, stop: int) -> int:
        """Locate the longest licensed coda prefix at a region's right edge."""
        if not self.language.codas:
            return stop
        for edge in range(stop, nucleus, -1):
            candidate = tuple(
                u for u in units[nucleus + 1 : edge] if u.segment is not None
            )
            if candidate and any(
                span.matches(candidate, self.features) for span in self.language.codas
            ):
                return edge
        return nucleus + 1

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
                text = "".join(u.core for u in units[at:end] if u.segment is not None)
                if text in self.language.syllables:
                    matches.append(end)
            if not matches:
                return []
            end = max(matches)
            out.append(Interval("syllable", at, end, self.features))
            at = end
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
