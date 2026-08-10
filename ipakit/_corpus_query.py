"""Streaming structural and derivational questions over stored forms.

Private with the corpus kernel until the public surface settles in K3.
Recognition is the rewrite engine's :class:`rules.Query`; this module only
compiles its familiar context notation and translates legacy sites to graph
paths.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from . import rules
from ._corpus import Corpus
from .features import IPAFeatures
from .form import Form, _default
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


def context(spec: str, features: IPAFeatures | None = None) -> Query:
    """Compile rule-context notation for an anywhere query.

    ``[vowel]`` matches that target anywhere.  A slash adds the ordinary
    rule environment, for example ``t / [vowel] _ #``.  This is a thin
    constructor for the engine's Pattern and Query objects, not a matcher.
    """
    inventory = _default(features)
    target_text, slash, environment = spec.partition("/")
    target_text = target_text.strip()
    if not target_text:
        raise rules.RuleError(f"{spec!r} has no target")
    target = rules._pattern(target_text, inventory)
    if target.names_tier:
        raise rules.RuleError("a structural query target must name a unit")
    if not slash:
        return Query(target)
    if environment.count("_") != 1:
        raise rules.RuleError(
            f"{spec!r} must contain exactly one '_' marking the target site"
        )
    before, after = environment.split("_")
    left = tuple(
        reversed([rules._pattern(item, inventory) for item in rules._items(before)])
    )
    right = tuple(rules._pattern(item, inventory) for item in rules._items(after))
    rules._check_variables(spec, target, left, right, None)
    return Query(target, left, right)


def _unit_paths(form: Form) -> dict[int, str]:
    paths: dict[int, str] = {}
    for pointer in form._graph.event_references():
        event = form._graph.resolve(pointer).event
        assert event is not None
        index = event.features.get("compatibility-index")
        if isinstance(index, int):
            paths[index] = pointer
    return paths


def query(
    corpus: Corpus,
    pattern: str | Query,
    *,
    role: str,
    features: IPAFeatures | None = None,
) -> Iterator[tuple[str, tuple[str, ...]]]:
    """Yield entry IDs and canonical graph paths matching ``pattern``."""
    inventory = _default(features)
    compiled = context(pattern, inventory) if isinstance(pattern, str) else pattern
    for entry_id in corpus.ids():
        entry = corpus.read_roles(entry_id, iter((role,)))
        form = entry.forms.get(role)
        if form is None:
            continue
        paths = _unit_paths(form)
        matched = tuple(
            paths[site.start]
            for site in compiled.sites(form.units, inventory, form.intervals)
        )
        if matched:
            yield entry_id, matched


def derives(
    ruleset: RuleSet,
    source: str | Form,
    target: str | Form,
    *,
    features: IPAFeatures | None = None,
    limit: int = DEFAULT_LIMIT,
) -> DerivationAnswer:
    """Return a witness, exhaustive refusal, or cap-qualified refusal."""
    inventory = _default(features)
    wanted = target.to_ipa() if isinstance(target, Form) else target
    if not ruleset.optional:
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
