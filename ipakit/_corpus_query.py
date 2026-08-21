"""Streaming structural and derivational questions over stored forms.

Private with the corpus kernel until the public surface settles in K3.
Recognition is the rewrite engine's :class:`rules.Query`; this module only
compiles its familiar context notation and translates legacy sites to graph
paths.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field

from . import rules
from ._corpus import Corpus
from .features import IPAFeatures
from .form import Form, _default
from .models import Phoneset
from .rules import DEFAULT_LIMIT, Derivation, Query, RuleSet


@dataclass(frozen=True)
class ExhaustiveRefusal:
    """The target is absent after complete exploration."""

    source: str
    target: str


@dataclass(frozen=True)
class BudgetRefusal:
    """No witness was found, but the variant cap cut the search."""

    source: str
    target: str
    unexplored: int


DerivationAnswer = Derivation | ExhaustiveRefusal | BudgetRefusal


def _normalize_wild_query(spec: str, inventory: IPAFeatures) -> str:
    """Import IPA spellings without rewriting feature-group vocabulary."""
    out: list[str] = []
    buffer = ""
    depth = 0
    for char in spec:
        if char in rules._GROUPS:
            if depth == 0:
                out.append(inventory.from_wild(buffer))
                buffer = ""
            depth += 1
        buffer += char
        if char in rules._CLOSERS:
            depth -= 1
            if depth == 0:
                out.append(buffer)
                buffer = ""
    out.append(inventory.from_wild(buffer) if depth == 0 else buffer)
    return "".join(out)


class QueryParseError(rules.RuleError):
    """A query token could not be parsed, with its source position."""

    def __init__(self, source: str, message: str, token: str | None = None):
        quoted = re.search(r"'([^']+)'", message)
        offending = token or (quoted.group(1) if quoted else _offending_token(source))
        stated = re.search(r"at position (\d+)", message)
        position = (
            int(stated.group(1))
            if stated is not None
            else source.find(offending) if offending else 0
        )
        self.position = max(position, 0)
        self.expected = message
        self.token = offending
        super().__init__(
            f"query error at position {self.position}: expected a valid pattern "
            f"element; offending token {offending!r}: {message}"
        )


def _offending_token(source: str) -> str:
    return next(
        (
            token
            for token in source.replace("/", " ").replace("_", " ").split()
            if token
        ),
        source,
    )


def _parse_query(
    spec: str,
    features: IPAFeatures | None = None,
    *,
    wild: bool = False,
) -> Query:
    """Compile rule-context notation for an anywhere query.

    ``[vowel]`` matches that target anywhere.  A slash adds the ordinary
    rule environment, for example ``t / [vowel] _ #``.  This is a thin
    constructor for the engine's Pattern and Query objects, not a matcher.
    """
    inventory = _default(features)
    if wild:
        spec = _normalize_wild_query(spec, inventory)
    reserved_at = spec.find("(?")
    if reserved_at >= 0:
        raise rules.RuleError(
            f"{spec!r} uses '(?' at position {reserved_at}; that group prefix "
            "is reserved for extension"
        )
    target_text, slash, environment = spec.partition("/")
    target_text = target_text.strip()
    if not target_text:
        raise rules.RuleError(f"{spec!r} has no target")
    if target_text in rules.NULL:
        raise rules.RuleError(
            f"{spec!r} has an insertion target; insertion sites are not "
            "recognizable patterns"
        )
    target = rules._pattern(target_text, inventory)
    if target.optional:
        raise rules.RuleError(
            f"{spec!r} marks its target optional at position 0, and a target is what the "
            "query recognizes: there is no target where it is absent. "
            "Optionality is for context items."
        )
    if target.repeated:
        raise rules.RuleError(
            f"{spec!r} marks its target repeated at position 0, and a query cannot recognize "
            "a span it has not counted. Repetition is for context items."
        )
    if target.literal in inventory.zeros:
        raise rules.RuleError(
            f"{spec!r} has a zero target; insertion sites are not "
            "recognizable patterns"
        )
    if target.names_tier:
        raise rules.RuleError("a structural query target must name a unit")
    _check_query_variables(spec, (target,))
    if not slash:
        if target.source == "*":
            raise rules.RuleError(
                "a bare '*' query is an unconstrained everything-matcher; "
                "add an anchored feature bundle such as '[vowel]' or use '*' "
                "only in a context"
            )
        return Query(target)
    if environment.count("_") != 1:
        raise rules.RuleError(
            f"{spec!r} must contain exactly one '_' marking the target site"
        )
    before, after = environment.split("_")
    context_items = (*rules._items(before), *rules._items(after))
    if any(item.strip() in rules.NULL for item in context_items):
        null = next(
            item.strip() for item in context_items if item.strip() in rules.NULL
        )
        raise rules.RuleError(
            f"{spec!r} names a null at position {spec.find(null, spec.find('/'))} "
            "in its environment. An environment names "
            "what stands there, and nothing stands at a deletion site; if "
            "zero-width context was meant, spell it with an optional element "
            "'(X)'."
        )
    left = tuple(
        reversed([rules._pattern(item, inventory) for item in rules._items(before)])
    )
    right = tuple(rules._pattern(item, inventory) for item in rules._items(after))
    if any(pattern.literal in inventory.zeros for pattern in (*left, *right)):
        null = next(
            pattern.source
            for pattern in (*left, *right)
            if pattern.literal in inventory.zeros
        )
        raise rules.RuleError(
            f"{spec!r} names a null at position {spec.find(null, spec.find('/'))} "
            "in its environment. An environment names "
            "what stands there, and nothing stands at a deletion site; if "
            "zero-width context was meant, spell it with an optional element "
            "'(X)'."
        )
    _check_query_variables(spec, (target, *left, *right))
    return Query(target, left, right)


def parse_query(
    spec: str,
    features: IPAFeatures | None = None,
    *,
    wild: bool = False,
) -> Query:
    """Parse arrowless rule notation into the rewrite engine's query object."""
    try:
        return _parse_query(spec, features, wild=wild)
    except QueryParseError:
        raise
    except rules.RuleError as exc:
        raise QueryParseError(spec, str(exc)) from exc


# K2's spelling remains a compatibility alias; K3's public name says what it
# does and exposes wild-input policy explicitly.
context = parse_query


def query_rule(
    spec: str | Query,
    replacement: str,
    features: IPAFeatures | None = None,
    *,
    wild: bool = False,
) -> rules.Rule:
    """Compose an arrowless query and replacement into a rewrite rule."""
    inventory = _default(features)
    compiled = (
        parse_query(spec, inventory, wild=wild) if isinstance(spec, str) else spec
    )
    target = compiled.target.source if compiled.target is not None else "∅"
    if compiled.left or compiled.right:
        left = " ".join(pattern.source for pattern in reversed(compiled.left))
        right = " ".join(pattern.source for pattern in compiled.right)
        environment = " ".join(part for part in (left, "_", right) if part)
        source = f"{target} -> {replacement} / {environment}"
    else:
        source = f"{target} -> {replacement}"
    return rules.parse(source, inventory)


def _query_source(query: Query) -> str:
    target = query.target.source if query.target is not None else "∅"
    if not query.left and not query.right:
        return target
    left = " ".join(pattern.source for pattern in reversed(query.left))
    right = " ".join(pattern.source for pattern in query.right)
    return f"{target} / {left} _ {right}".rstrip()


@dataclass(frozen=True)
class Match:
    """One form-level structural match, independent of collection identity."""

    paths: tuple[str, ...]
    text: str
    bindings: tuple[tuple[str, str], ...] = ()
    _preceding_text: tuple[str, ...] = field(default=(), repr=False, compare=False)

    @property
    def offset(self) -> int:
        """Codepoint offset in the form's string representation."""
        return sum(len(text) for text in self._preceding_text)


@dataclass(frozen=True)
class CorpusMatch:
    """A :class:`Match` paired with its corpus identity."""

    fileid: str
    role: str
    match: Match

    @property
    def paths(self) -> tuple[str, ...]:
        return self.match.paths

    @property
    def text(self) -> str:
        return self.match.text

    @property
    def bindings(self) -> tuple[tuple[str, str], ...]:
        return self.match.bindings

    @property
    def offset(self) -> int:
        return self.match.offset

    # Transitional tuple projection for K2 callers.  The record remains the
    # public shape, while unpacking/indexing old streams still reaches their
    # former ``(fileid, paths)`` view.
    def __iter__(self) -> Iterator[str | tuple[str, ...]]:
        yield self.fileid
        yield self.paths

    def __getitem__(self, index: int) -> str | tuple[str, ...]:
        return (self.fileid, self.paths)[index]


def _check_query_variables(source: str, patterns: Sequence[rules.Pattern]) -> None:
    """Refuse only variable uses that cannot describe a query binding.

    Every variable in a recognition pattern binds a value into its site's
    payload.  It therefore need not occur twice, whether it appears in the
    target or its environment.  Repeated occurrences retain agreement
    semantics, and one variable still cannot range over two feature domains.
    """
    features_of: dict[str, str] = {}
    for pattern in patterns:
        for key, variable in pattern.agreements.items():
            seen = features_of.setdefault(variable.name, key)
            if seen != key:
                raise rules.RuleError(
                    f"{source!r} uses the variable {variable.name!r} on two "
                    f"features, {seen!r} and {key!r}. A variable ranges over "
                    "the declared values of ONE feature -- two features "
                    "declare two different sets of values, so there is "
                    "nothing for it to be. Use a second variable for the "
                    "second feature."
                )


def _unit_paths(form: Form) -> dict[int, str]:
    paths: dict[int, str] = {}
    graph_index = form.__dict__["_tiergraph_index"]
    for pointer, (_, event) in graph_index.events.items():
        unit_index = event.features.get("compatibility-index")
        if isinstance(unit_index, int):
            paths[unit_index] = pointer
    return paths


def find(
    form: str | Form,
    spec: str | Query,
    *,
    features: IPAFeatures | None = None,
    wild: bool = False,
) -> Iterator[Match]:
    """Yield match records from one utterance."""
    inventory = _default(features)
    parsed = inventory.read(form) if isinstance(form, str) else form
    compiled = (
        parse_query(spec, inventory, wild=wild) if isinstance(spec, str) else spec
    )
    paths = _unit_paths(parsed)
    seen: set[tuple[tuple[str, ...], str, tuple[tuple[str, str], ...]]] = set()
    for site in compiled.sites(parsed.units, inventory, parsed.intervals):
        span_paths = tuple(paths[index] for index in range(site.start, site.end))
        match = Match(
            span_paths,
            "".join(unit.text for unit in parsed.units[site.start : site.end]),
            site.bindings,
            tuple(unit.text for unit in parsed.units[: site.start]),
        )
        key = (match.paths, match.text, match.bindings)
        if key not in seen:
            seen.add(key)
            yield match


def query(
    corpus: Corpus,
    pattern: str | Query,
    *,
    role: str,
    features: IPAFeatures | None = None,
) -> Iterator[CorpusMatch]:
    """Yield form matches paired with entry and role identity."""
    inventory = _default(features)
    compiled = context(pattern, inventory) if isinstance(pattern, str) else pattern
    for entry_id in corpus.ids():
        entry = corpus.read_roles(entry_id, iter((role,)))
        form = entry.forms.get(role)
        if form is None:
            continue
        for match in find(form, compiled, features=inventory):
            yield CorpusMatch(entry_id, role, match)


def derives(
    ruleset: RuleSet,
    source: str | Form,
    target: str | Form,
    *,
    features: IPAFeatures | None = None,
    phoneset: Phoneset | None = None,
    limit: int = DEFAULT_LIMIT,
) -> DerivationAnswer:
    """Return a witness, exhaustive refusal, or cap-qualified refusal.

    An all-invertible obligatory cascade takes the single deterministic
    path. A set that has lost invertibility (or contains optional choices)
    uses the existing capped candidate enumeration. ``phoneset`` declares
    the underlying inventory for that classification. Omitting it preserves
    the historical deterministic path for an obligatory cascade.
    """
    inventory = _default(features)
    wanted = target.to_ipa() if isinstance(target, Form) else target
    deterministic = not ruleset.optional and (
        phoneset is None or ruleset.invertibility(phoneset, inventory).invertible
    )
    if deterministic:
        derivation = ruleset.derive(source, inventory)
        return (
            derivation
            if derivation.result == wanted
            else ExhaustiveRefusal(derivation.start, wanted)
        )
    variants = ruleset.variants(source, inventory, limit=limit)
    witness = next((v.derivation for v in variants if v.form == wanted), None)
    if witness is not None:
        return witness
    if variants.complete:
        return ExhaustiveRefusal(variants.start, wanted)
    return BudgetRefusal(variants.start, wanted, variants.unexplored)


def query_derivations(
    corpus: Corpus,
    ruleset: RuleSet,
    *,
    source_role: str,
    target_role: str,
    features: IPAFeatures | None = None,
    limit: int = DEFAULT_LIMIT,
) -> Iterator[tuple[str, DerivationAnswer]]:
    """Map :func:`derives` lazily over stored source/target role pairs."""
    for entry_id in corpus.ids():
        entry = corpus.read_roles(entry_id, iter((source_role, target_role)))
        source = entry.forms.get(source_role)
        target = entry.forms.get(target_role)
        if source is None or target is None:
            continue
        yield entry_id, derives(ruleset, source, target, features=features, limit=limit)
