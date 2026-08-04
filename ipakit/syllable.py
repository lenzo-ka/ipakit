"""Building a syllabifier for a language, rather than shipping one.

There is no language-independent syllabifier. Legal onsets differ --
English takes ``str`` and Spanish does not -- codas may or may not be
moraic, onset maximization is a tendency rather than a law, and each
language violates sonority sequencing in its own way. A single shipped
``syllabify.rules`` would be right for about one language and quietly
wrong everywhere else, which is the failure mode this library exists to
avoid.

So what ships here is a **constructor** and two worked languages built
with it. A language supplies three things, each of them a declared query
in the notation :mod:`ipakit.rules` already parses, and none of them a
number typed by hand:

``nucleus``
    what may carry a syllable. American English says ``[vowel]`` and
    ``[syllabic=+]``; Spanish says ``[vowel]``.
``onset-appendix``
    a unit licensed at the left edge of an onset **in violation of the
    sonority rise**. American English says ``[manner=fricative
    place=alveolar]``, which is the ``s`` of ``str``; Spanish says
    nothing, which is why Spanish has ``es.tre`` where English has
    ``e.stre``.
``coda-appendix``
    the same exemption at the right edge of a coda.

Everything else -- which clusters rise, where the cut falls -- is derived
from :func:`sonority_scale`, which is itself read off ``ipa.xml``. The two
languages live in ``ipakit/data/syllables/*.syllable`` beside the rule
sets, with the prose that says what each claim is derived from, because a
language's phonotactics are a claim about that language and not a
constant this module gets to hold.

**The output is an interval, and the dot is the lossy fallback.** A
syllable that crosses a word boundary -- French *petite amie*, where the
``t`` of *petite* is the onset of a syllable whose nucleus is the ``a`` of
*amie* -- cannot be written as nesting, which is the limitation
:meth:`~ipakit.form.Form.tree` has and :class:`~ipakit.form.Interval` does
not (docs/form.md). :meth:`Syllabification.marks` is still there, because a
transcription has to round-trip as text, and it says what it cannot state.

**What is written is honored.** A transcription carrying ``.`` has stated
its syllabification and this does not overrule it: the derivation runs
between the stated boundaries, and where the mechanism would have cut
somewhere else the disagreement is **reported** as a
:class:`Conflict` rather than resolved in silence. Reporting is the
answer because only the transcriber knows which of the two they meant.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .constants import DATA_DIR
from .form import Form, Interval, Unit, tier_names
from .rules import Pattern, RuleError, _pattern

#: Where the shipped language declarations live, beside the rule sets.
SYLLABLES_DIR = Path(DATA_DIR) / "syllables"

#: The extension a language declaration carries.
SUFFIX = ".syllable"

from .features import IPAFeatures  # noqa: E402  (cycle: features imports form)


def _default(features: IPAFeatures | None) -> IPAFeatures:
    if features is not None:
        return features
    from . import _get_ipa

    return _get_ipa()


# -- the scale ------------------------------------------------------------


def sonority_scale(features: IPAFeatures | None = None) -> tuple[str, ...]:
    """Declared manners, least sonorous first. **A model, not a fact.**

    Read Daland, Hayes, White, Garellek, Davis & Norrmann (2011),
    "Explaining sonority projection effects", before treating this or any
    other sonority scale as a fact. Several scales are tested there
    against speaker judgments on unattested clusters and they do not
    agree; a scale is a hypothesis about syllabic prominence that a
    language may falsify, and this one is derived rather than surveyed.

    Two declarations, both already in ``ipa.xml``, and nothing typed:

    * ``manner``'s ``natural-class="obstruent"``, which names the
      plosives, affricates and fricatives; and
    * each value's declared ``offset`` on the ``+constriction`` axis.

    Obstruents rank below sonorants, and within each group a value ranks
    by constriction, most closed first. That gives::

        plosive < affricate < fricative < nasal < tap < trill
                < approximant < vowel

    which is the order every standard hierarchy gives, and it is not what
    either declaration gives alone. Constriction by itself puts ``nasal``
    and ``plosive`` at the same position -- correct for a nasal's oral
    tract, backwards for its sonority -- and ``docs/distance.md`` says so;
    the ``obstruent`` class is what separates them.

    **The one claim no declaration makes** is the class ranking itself:
    that every sonorant outranks every obstruent. It is the definition of
    the class rather than a further fact about it, and it is stated here
    because it is stated nowhere else. Everything downstream of it moves
    when ``ipa.xml`` moves.

    **Two limits it has by construction.** ``l`` and ``j`` are both
    ``manner=approximant``, so a hierarchy ranking liquid below glide
    disagrees with this one there; and the scale reads ``manner`` only, so
    ``s`` and ``z`` rank alike.

    A value holding no position on the axis -- ``silence``, declared
    ``offscale`` -- is not on the scale at all, and :func:`sonority`
    answers ``None`` for it.
    """
    features = _default(features)
    manner = features.features["manner"]
    obstruents = manner.value_classes.get("obstruent", frozenset())
    ranked = [v for v in manner.values if v not in manner.offscale]
    return tuple(
        sorted(
            ranked,
            key=lambda v: (
                v not in obstruents,
                -manner.coordinates.get(v, {}).get("offset", 0.0),
            ),
        )
    )


def sonority(unit: Unit, features: IPAFeatures | None = None) -> int | None:
    """Where ``unit`` sits on :func:`sonority_scale`, or ``None``.

    ``None`` for a boundary, a structural zero, and for a segment whose
    manner holds no position on the constriction axis. A caller has to
    decide what to do about a position with no sonority, which is why this
    does not pick a number for it.
    """
    features = _default(features)
    value = unit.features.get("manner")
    if value is None:
        return None
    scale = sonority_scale(features)
    return scale.index(value) if value in scale else None


# -- what a language supplies ---------------------------------------------


@dataclass(frozen=True)
class Language:
    """A language's syllabification, as declared queries and nothing else.

    Every field is a query in the notation ``.rules`` files use, so what a
    language claims is written in the vocabulary ``ipa.xml`` declares and
    is checked against it when the syllabifier is built. There is no
    number here on purpose: cluster size and margin shape follow from the
    sonority scale and from the appendix exemptions, and a maximum onset
    length typed per language would be exactly the hand-maintained table
    this library refuses.

    :attr:`provenance` is what the declaration is a claim *about* -- the
    prose header of the file it was read from. It is carried rather than
    discarded because these are claims about two particular languages, and
    a reader has to be able to find out on what evidence.
    """

    name: str
    nucleus: tuple[str, ...]
    onset_appendix: tuple[str, ...] = ()
    coda_appendix: tuple[str, ...] = ()
    provenance: str = ""

    def __str__(self) -> str:
        return self.name


#: The keys a ``.syllable`` file may state, each naming a field above.
#: Format vocabulary, not phonetic vocabulary: no value here is declared
#: in ``ipa.xml`` and none describes a sound.
_FIELDS = {
    "nucleus": "nucleus",
    "onset-appendix": "onset_appendix",
    "coda-appendix": "coda_appendix",
}


def read_language(text: str, name: str) -> Language:
    """Parse a ``.syllable`` declaration.

    One ``key query`` per line, ``#`` starting a comment, blank lines
    ignored. A key may be repeated, and the queries it states are a
    disjunction: two ``nucleus`` lines say a unit matching either may
    carry a syllable.

    The comment block is kept as :attr:`Language.provenance`, so what the
    file says its claims rest on travels with the object.
    """
    stated: dict[str, list[str]] = {field: [] for field in _FIELDS.values()}
    prose: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            prose.append(stripped.lstrip("#").strip())
            continue
        key, _, query = stripped.partition(" ")
        if key not in _FIELDS:
            raise ValueError(
                f"{name}:{number}: {key!r} is not a syllable declaration; "
                f"expected one of {', '.join(sorted(_FIELDS))}"
            )
        if not query.strip():
            raise ValueError(f"{name}:{number}: {key!r} states no query")
        stated[_FIELDS[key]].append(query.strip())
    if not stated["nucleus"]:
        raise ValueError(
            f"{name}: no 'nucleus' declared, so nothing may carry a syllable "
            "and the syllabifier would answer nothing everywhere"
        )
    return Language(
        name=name,
        nucleus=tuple(stated["nucleus"]),
        onset_appendix=tuple(stated["onset_appendix"]),
        coda_appendix=tuple(stated["coda_appendix"]),
        provenance="\n".join(prose).strip(),
    )


def languages() -> list[str]:
    """The shipped language declarations, by name."""
    if not SYLLABLES_DIR.is_dir():  # pragma: no cover - packaging failure
        return []
    return sorted(path.stem for path in SYLLABLES_DIR.glob(f"*{SUFFIX}"))


def language(name: str) -> Language:
    """One shipped declaration, read from ``ipakit/data/syllables``."""
    path = SYLLABLES_DIR / f"{name}{SUFFIX}"
    if not path.is_file():
        raise ValueError(
            f"no shipped syllable declaration {name!r}; "
            f"available: {', '.join(languages()) or '(none)'}"
        )
    return read_language(path.read_text(encoding="utf-8"), name)


# -- what comes out -------------------------------------------------------


@dataclass(frozen=True)
class Conflict:
    """A written syllable mark the derivation would not have placed.

    Reported rather than resolved. The transcription is honored -- the
    syllable intervals respect the mark -- and this records that the
    mechanism disagreed, because preferring either side in silence is the
    well-formed wrong answer this library is built against.

    :attr:`at` indexes ``Form.units``; :attr:`stated` and :attr:`derived`
    count **segments**, the same measure :attr:`~ipakit.form.Boundary.at`
    uses, so a position survives the projection that drops the marks.
    """

    #: Index of the written mark in ``Form.units``.
    at: int
    #: Segments before the written mark.
    stated: int
    #: Where the mechanism would have cut between the same two nuclei,
    #: in segments. Empty where it would have cut nowhere at all.
    derived: tuple[int, ...]
    #: What was written, so a richer mark is identifiable in the report.
    text: str = "."

    def __str__(self) -> str:
        wanted = ", ".join(str(d) for d in self.derived) or "no cut"
        return (
            f"{self.text!r} at unit {self.at} states a boundary after "
            f"{self.stated} segment(s); derived: {wanted}"
        )


@dataclass(frozen=True)
class Syllabification:
    """What a syllabifier answers: a form carrying syllable intervals.

    :attr:`form` is the input form with :class:`~ipakit.form.Interval`
    spans on the ``syllable`` tier attached, so nothing is re-transcribed
    and the spelling is untouched.
    """

    form: Form
    conflicts: tuple[Conflict, ...] = ()
    #: Spans of the form holding segments and no nucleus, so no syllable
    #: was derived over them. Nothing is invented, per docs/form.md: a
    #: stretch with nothing to carry a syllable gets none.
    unsyllabified: tuple[tuple[int, int], ...] = ()

    @property
    def syllables(self) -> tuple[Interval, ...]:
        return tuple(s for s in self.form.intervals if s.tier == "syllable")

    def spelled(self) -> tuple[str, ...]:
        """Each syllable as it is written, boundary marks inside it kept.

        The linking mark stays where a syllable spans it, because it is
        part of what that syllable is written with.
        """
        return tuple(
            "".join(u.text for u in self.form.units[s.start : s.end])
            for s in self.syllables
        )

    def marks(self) -> str:
        """The syllabification written back into the string, with dots.

        **The lossy output, and it says what it loses.** A dot cannot state
        a syllable that crosses a word boundary, so ``pətit‿ami``
        round-trips as ``pə.ti.t‿a.mi`` -- correct as a spelling, and
        re-reading it gives four syllables under the *nested* reading and
        five, because the crossing one is cut in two. The intervals on
        :attr:`form` are the reading that survives.

        **Nothing already written is overwritten.** Where a derived
        boundary falls on a position that already carries a mark, the mark
        stands and no dot is added: ``#`` and ``|`` already assert a
        boundary at least as strong as a syllable's, and replacing one
        with a dot would spell the same break and lose what the mark
        carried -- ``|``'s ``break=minor``, ``‿``'s ``linking=+``. That is
        the shape of the defect ``Form.rebuild`` was fixed for.
        """
        cuts = {s.start for s in self.syllables} | {s.end for s in self.syllables}
        out: list[str] = []
        for index, unit in enumerate(self.form.units):
            if index in cuts and out and not unit.is_boundary:
                # A mark already standing here is left alone: it is a
                # boundary already, and a richer one than the dot.
                if not self.form.units[index - 1].is_boundary:
                    out.append(".")
            out.append(unit.text)
        return "".join(out)

    def __len__(self) -> int:
        return len(self.syllables)

    def __iter__(self) -> Iterator[Interval]:
        return iter(self.syllables)

    def __repr__(self) -> str:
        held = f"{len(self.syllables)} syllables"
        if self.conflicts:
            held += f", {len(self.conflicts)} conflicts"
        return f"Syllabification({'.'.join(self.spelled())!r}, {held})"


# -- the constructor ------------------------------------------------------


@dataclass(frozen=True)
class Syllabifier:
    """A syllabifier for one language. Call it with a form.

    Built from a :class:`Language` and an inventory. The queries are
    compiled once, here, so a declaration naming an undeclared feature
    fails when the syllabifier is built rather than at the first form that
    happens to reach the term.
    """

    language: Language
    features: IPAFeatures = field(repr=False)
    _nucleus: tuple[Pattern, ...] = field(repr=False, default=())
    _onset_appendix: tuple[Pattern, ...] = field(repr=False, default=())
    _coda_appendix: tuple[Pattern, ...] = field(repr=False, default=())

    def __repr__(self) -> str:
        return f"Syllabifier({self.language.name!r})"

    # -- deriving ---------------------------------------------------------

    def __call__(self, form: Form | str) -> Syllabification:
        return self.syllabify(form)

    def syllabify(self, form: Form | str) -> Syllabification:
        """Syllable intervals over ``form``, honoring what it already states.

        Runs the derivation twice: once with every written syllable mark
        treated as the boundary it is, and once with the marks transparent
        -- which is what ``Unit.transparent`` already says a dot is. The
        first is the answer; the difference between the two is the
        :class:`Conflict` list, and it is a measurement rather than a
        warning, because a transcription and a model of a language may
        legitimately disagree.
        """
        if isinstance(form, str):
            form = Form.parse(form, self.features)
        units = form.units
        spans, unsyllabified = self._spans(units, honor=True)
        free, _ = self._spans(units, honor=False)
        return Syllabification(
            form=Form.of(units, spans),
            conflicts=self._conflicts(units, spans, free),
            unsyllabified=tuple(unsyllabified),
        )

    # -- licensing, which is the language-particular part ------------------

    def licenses_onset(self, units: Sequence[Unit]) -> bool:
        """Whether ``units`` may stand as an onset before their nucleus.

        The sequence is the onset **and its nucleus**: the sonority
        sequencing principle is a claim about the rise into the peak, not
        about the consonants on their own.
        """
        return self._sequenced(units, self._onset_appendix, rising=True)

    def licenses_coda(self, units: Sequence[Unit]) -> bool:
        """Whether ``units`` may stand as a coda, nucleus first."""
        return self._sequenced(units, self._coda_appendix, rising=False)

    def is_nucleus(self, unit: Unit) -> bool:
        """Whether ``unit`` may carry a syllable.

        A unit matching a declared ``nucleus`` query, **or** one carrying
        stress. Stress rides on the nucleus in this library -- ``ˈɑ``
        parses as one unit with ``stress=primary`` rather than as a mark
        plus a vowel -- so a stressed unit *is* a nucleus, and a
        syllabifier that read only the query would put a boundary through
        one.
        """
        if unit.segment is None:
            return False
        if "stress" in unit.prosody:
            return True
        return any(pattern.matches(unit, self.features) for pattern in self._nucleus)

    # -- internals --------------------------------------------------------

    def _sequenced(
        self, units: Sequence[Unit], appendix: tuple[Pattern, ...], rising: bool
    ) -> bool:
        segments = [u for u in units if u.segment is not None]
        if len(segments) < 2:
            return True
        if self._monotone(segments, rising):
            return True
        if not appendix:
            return False
        # The exemption sits at the margin's **outer** edge -- the left of
        # an onset, the right of a coda -- which is where the languages
        # that have one put it: English `s` in `str`, and the coronal
        # obstruents that pile up word-finally.
        edge = segments[0] if rising else segments[-1]
        rest = segments[1:] if rising else segments[:-1]
        if not any(pattern.matches(edge, self.features) for pattern in appendix):
            return False
        return len(rest) < 2 or self._monotone(rest, rising)

    def _monotone(self, segments: Sequence[Unit], rising: bool) -> bool:
        ranks = [sonority(u, self.features) for u in segments]
        if any(rank is None for rank in ranks):
            # A position with no place on the scale -- silence -- is not a
            # margin member this can rule on, so it does not license one.
            return False
        pairs = zip(ranks, ranks[1:], strict=False)
        return all((a < b) if rising else (a > b) for a, b in pairs)  # type: ignore[operator]

    def _delimiters(self, units: Sequence[Unit], honor: bool) -> list[int]:
        """Units that delimit a syllable and belong to none.

        A boundary declaring ``linking="+"`` is skipped, and it is the
        interesting one: ``‿`` is a *word* boundary that exists precisely
        to say the words run together, so a syllable crosses it. That is
        enchaînement, and it is the case the French rule set ships for.
        """
        out: list[int] = []
        for index, unit in enumerate(units):
            if not unit.is_boundary:
                continue
            if unit.features.get("linking") == "+":
                continue
            if unit.level == "syllable":
                if honor:
                    out.append(index)
            elif unit.level is not None:
                out.append(index)
        return out

    def _spans(
        self, units: Sequence[Unit], honor: bool
    ) -> tuple[list[Interval], list[tuple[int, int]]]:
        held: list[Interval] = []
        empty: list[tuple[int, int]] = []
        start = 0
        stops = [*self._delimiters(units, honor), len(units)]
        for stop in stops:
            if start < stop:
                self._within(units, start, stop, held, empty)
            start = stop + 1
        return held, empty

    def _within(
        self,
        units: Sequence[Unit],
        start: int,
        stop: int,
        held: list[Interval],
        empty: list[tuple[int, int]],
    ) -> None:
        nuclei = [i for i in range(start, stop) if self.is_nucleus(units[i])]
        if not nuclei:
            if any(units[i].segment is not None for i in range(start, stop)):
                empty.append((start, stop))
            return
        edges = [start]
        for left, right in zip(nuclei, nuclei[1:], strict=False):
            edges.append(self._cut(units, left, right))
        edges.append(stop)
        for opened, closed in zip(edges, edges[1:], strict=False):
            held.append(Interval("syllable", opened, closed, self.features))

    def _cut(self, units: Sequence[Unit], left: int, right: int) -> int:
        """Where the boundary falls between two nuclei.

        **Onset maximization, subject to licensing**: the largest onset the
        language licenses wins, provided what is left over is a licensed
        coda. Scanning from the largest onset down is what makes it
        maximization, and the licensing check is what stops it being
        universal -- Spanish declares no onset appendix, so ``estre``
        stops at ``es.tre`` where English reaches ``e.stre``.

        Where nothing satisfies both, the largest licensed onset wins and
        the coda takes what is left; where nothing licenses an onset at
        all, the coda takes everything. Neither is a claim that the result
        is well formed, and a language with a real phonotactic filter would
        state it as one.
        """
        for gap in range(left + 1, right + 1):
            onset = [*units[gap:right], units[right]]
            coda = [units[left], *units[left + 1 : gap]]
            if self.licenses_onset(onset) and self.licenses_coda(coda):
                return gap
        for gap in range(left + 1, right + 1):
            if self.licenses_onset([*units[gap:right], units[right]]):
                return gap
        return right

    def _conflicts(
        self,
        units: Sequence[Unit],
        honored: Sequence[Interval],
        free: Sequence[Interval],
    ) -> tuple[Conflict, ...]:
        """Written marks the free derivation would not have placed.

        Compared in **segment** positions rather than unit positions, so
        the two runs are commensurable: an honored cut sits at the mark
        and a free cut sits in the gap the mark occupies, and counting the
        segments before each is what makes them the same measure.
        """
        before = _segments_before(units)
        derived = {before[s.start] for s in free} | {before[s.end] for s in free}
        stated = {before[s.start] for s in honored} | {before[s.end] for s in honored}
        nuclei = [i for i, u in enumerate(units) if self.is_nucleus(u)]
        out: list[Conflict] = []
        for index, unit in enumerate(units):
            if not unit.is_boundary or unit.level != "syllable":
                continue
            at = before[index]
            if at in derived:
                continue
            left = max((n for n in nuclei if n < index), default=None)
            right = min((n for n in nuclei if n > index), default=None)
            between: tuple[int, ...] = ()
            if left is not None and right is not None:
                between = tuple(
                    sorted(
                        d
                        for d in derived - stated
                        if before[left] < d <= before[right]
                    )
                )
            out.append(
                Conflict(at=index, stated=at, derived=between, text=unit.text)
            )
        return tuple(out)


def _segments_before(units: Sequence[Unit]) -> list[int]:
    """Segments preceding each position, for every position including the end.

    The measure :attr:`~ipakit.form.Boundary.at` uses, so a cut expressed
    in it survives the projection that drops boundary units -- which is
    what makes the honored run and the free run comparable at all.
    """
    out = [0]
    for unit in units:
        out.append(out[-1] + (1 if unit.segment is not None else 0))
    return out


def _compile(
    queries: Iterable[str], features: IPAFeatures, where: str
) -> tuple[Pattern, ...]:
    out: list[Pattern] = []
    for source in queries:
        pattern = _pattern(source, features)
        if pattern.names_boundary or pattern.names_tier:
            raise RuleError(
                f"{where}: {source!r} names a boundary or a tier. A syllable "
                "declaration constrains a unit -- what may be a nucleus, what "
                "may sit at a margin's edge -- and a boundary is not one."
            )
        out.append(pattern)
    return tuple(out)


def syllabifier(
    name: str | Language, features: IPAFeatures | None = None
) -> Syllabifier:
    """Build a syllabifier from a shipped declaration, or from your own.

        >>> import ipakit
        >>> english = ipakit.syllabifier("american-english")
        >>> english("ɛstɹeɪndʒ").spelled()
        ('ɛ', 'stɹeɪndʒ')

    The tier is checked here rather than assumed: ``syllable`` has to be a
    declared tier name for an interval to carry it, and a data file that
    stopped declaring one would otherwise fail at the first form.
    """
    features = _default(features)
    if "syllable" not in tier_names(features):
        raise ValueError(
            "the inventory declares no 'syllable' tier, so a syllabifier has "
            f"nowhere to write; declared: {', '.join(tier_names(features)) or '(none)'}"
        )
    declared = language(name) if isinstance(name, str) else name
    return Syllabifier(
        language=declared,
        features=features,
        _nucleus=_compile(declared.nucleus, features, f"{declared.name}: nucleus"),
        _onset_appendix=_compile(
            declared.onset_appendix, features, f"{declared.name}: onset-appendix"
        ),
        _coda_appendix=_compile(
            declared.coda_appendix, features, f"{declared.name}: coda-appendix"
        ),
    )


def syllabify(
    form: Form | str, name: str, features: IPAFeatures | None = None
) -> Syllabification:
    """Syllabify one form with one shipped language. The one-shot form."""
    return syllabifier(name, features).syllabify(form)
