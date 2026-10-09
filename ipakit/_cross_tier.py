"""Cross-tier Form matching lowered to TierGraph predicates and patterns."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from functools import cached_property
from itertools import pairwise
from typing import Any, cast

from tiergraph.match import (
    AltPattern,
    AtomPattern,
    BoundOrdering,
    BoundPattern,
    CompiledPattern,
    DeclaredOrder,
    EndPattern,
    FocusPattern,
    RepeatPattern,
    SeqPattern,
    StartPattern,
    compile_pattern,
)
from tiergraph.match import (
    Pattern as GraphPattern,
)
from tiergraph.predicate import (
    And,
    Cell,
    Current,
    Elements,
    Equals,
    Has,
    Not,
    Or,
    Predicate,
    Quantifier,
)

import tiergraph as tg

from . import rules
from .form import Form, Interval, Unit, tier_names

NS = "urn:ipakit:form:matching"
POSITION = tg.QualifiedName(NS, "position")
PAYLOAD = tg.QualifiedName(NS, "payload")
LINEAR_NEXT = tg.QualifiedName(NS, "linear-next")
ASSOCIATES_WITH = tg.QualifiedName(NS, "associates-with")
_NONPOSITIONAL_TIERS = frozenset({"delivery", "analysis"})


def _and(parts: Iterable[Predicate]) -> Predicate:
    held = tuple(
        child
        for part in parts
        for child in (part.args if isinstance(part, And) else (part,))
    )
    return held[0] if len(held) == 1 else And(held)


def _or(parts: Iterable[Predicate]) -> Predicate:
    held = tuple(
        child
        for part in parts
        for child in (part.args if isinstance(part, Or) else (part,))
    )
    return held[0] if len(held) == 1 else Or(held)


def _cell(*pointer: str) -> Cell:
    return Cell(PAYLOAD, pointer)


def _ranges(
    units: Sequence[Unit], spelling: str | None = None
) -> tuple[tuple[int, int], ...]:
    out, at = [], 0
    for unit in units:
        token = unit.spelling if unit.spelling is not None else unit.text
        start = spelling.find(token, at) if spelling is not None else at
        if start < 0:
            start = at
        end = start + len(token)
        out.append((start, end))
        at = end
    return tuple(out)


def _route(
    features: dict[str, Any], routes: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {"features": features, "routes": routes or {}}


def _prosody_positions(
    unit: Unit, index: int, start: int, inventory: Any, path: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    before: list[dict[str, Any]] = []
    after: list[dict[str, Any]] = []
    cursor = 0
    for glyph in unit.segment.prosody if unit.segment is not None else ():
        declared = inventory.diacritics.get(glyph)
        features = dict(getattr(declared, "features", None) or {})
        found = unit.text.find(glyph, cursor)
        if found < 0:
            found = unit.text.rfind(glyph)
        if found < 0:
            continue
        cursor = found + len(glyph)
        selectors = {"tier:prosody": True}
        selectors.update(
            {
                f"feature:{key}": True
                for key in features
                if key in inventory.features_by_mode.get("prosodic", ())
            }
        )
        payload = {
            "kind": "prosody",
            "selectors": selectors,
            "features": features,
            "cells": features,
            "text": glyph,
            "input-ranges": [[start + found, start + cursor]],
            "output-ranges": [[start + found, start + cursor]],
            "unit-indices": [index],
            "paths": [path],
            "routes": {"tier:segment": [_route(dict(unit.features))]},
        }
        target = before if glyph in inventory.stress_markers else after
        target.append(payload)
    return before, after


def _focus_complete(pattern: GraphPattern) -> GraphPattern:
    if not isinstance(pattern, SeqPattern):
        return FocusPattern(pattern)
    leading = isinstance(pattern.parts[0], StartPattern)
    trailing = isinstance(pattern.parts[-1], EndPattern)
    if not leading and not trailing:
        return FocusPattern(pattern)
    start = 1 if leading else 0
    end = -1 if trailing else len(pattern.parts)
    body = _sequence(pattern.parts[start:end])
    parts: list[GraphPattern] = []
    if leading:
        parts.append(pattern.parts[0])
    parts.append(FocusPattern(body))
    if trailing:
        parts.append(pattern.parts[-1])
    return _sequence(parts)


def _exclude_outer_edges(pattern: GraphPattern) -> GraphPattern:
    """Keep internal edge positions available to context, never to focus."""
    if isinstance(pattern, AtomPattern):
        return AtomPattern(
            _and(
                (
                    pattern.predicate,
                    Not(Equals(_cell("selectors", "internal:outer-edge"), (True,))),
                )
            )
        )
    if isinstance(pattern, SeqPattern):
        return SeqPattern(tuple(_exclude_outer_edges(part) for part in pattern.parts))
    if isinstance(pattern, AltPattern):
        return AltPattern(tuple(_exclude_outer_edges(part) for part in pattern.parts))
    if isinstance(pattern, RepeatPattern):
        return RepeatPattern(
            _exclude_outer_edges(pattern.body), pattern.min, pattern.max
        )
    return pattern


def _matching_graph(form: Form) -> tg.Graph:
    graph = cast(tg.Graph, form.graph)
    if any(tier.declaration.name == POSITION for tier in graph.tiers):
        return graph
    cached = form.__dict__.get("_matching_graph")
    if cached is not None:
        return cast(tg.Graph, cached)
    index = form.__dict__["_tiergraph_index"]
    editor = graph.edit()
    augment_graph(
        editor,
        graph,
        index.containment_input,
        index.inventory,
        form.to_ipa("exact"),
    )
    cached = editor.freeze()
    form.__dict__["_matching_graph"] = cached
    return cached


@dataclass(frozen=True)
class CrossTierQuery:
    """One TierGraph pattern over a projection of the Form parse order."""

    source: str
    selectors: tuple[str, ...]
    pattern: GraphPattern

    @cached_property
    def compiled(self) -> CompiledPattern:
        return compile_pattern(self.pattern)

    @classmethod
    def parse(cls, source: str, inventory: Any) -> CrossTierQuery:
        match = re.match(r"\s*on\(([^)]*)\)\s*:\s*(.+)\Z", source, re.DOTALL)
        if match is None:
            raise rules.RuleError("on(...) query requires ':' and a pattern")
        names = [part.strip() for part in match.group(1).split(",") if part.strip()]
        if not names:
            raise rules.RuleError("on(...) requires a tier or feature")
        selectors = tuple(_qualified_selector(name, inventory) for name in names)
        blocked = [
            name
            for name in selectors
            if name.removeprefix("tier:") in _NONPOSITIONAL_TIERS
        ]
        if blocked:
            raise rules.RuleError(
                f"{', '.join(blocked)} is nonpositional; use a routed atom"
            )
        body_text = match.group(2)
        target_text, slash, context = body_text.partition("/")
        target = _parse_graph_pattern(target_text, inventory)
        if "unit" in selectors:
            target = _exclude_outer_edges(target)
        if not slash:
            return cls(source, selectors, _focus_complete(target))
        if context.count("_") != 1:
            raise rules.RuleError("a slash pattern requires exactly one '_' focus site")
        left_text, right_text = context.split("_")
        parts: list[GraphPattern] = []
        if left_text.strip():
            left = _parse_graph_pattern(left_text, inventory)
            parts.extend(left.parts if isinstance(left, SeqPattern) else (left,))
        parts.append(FocusPattern(target))
        if right_text.strip():
            right = _parse_graph_pattern(right_text, inventory)
            parts.extend(right.parts if isinstance(right, SeqPattern) else (right,))
        return cls(source, selectors, _sequence(parts))

    def spans(self, form: Form) -> tuple[Any, ...]:
        return cast(tuple[Any, ...], self._bound(form).spans().matches)

    def focused(self, form: Form) -> frozenset[tg.Node]:
        return frozenset(self._bound(form).focus().nodes)

    def _bound(self, form: Form) -> BoundPattern:
        graph = _matching_graph(form)
        cache = form.__dict__.setdefault("_cross_tier_orders", {})
        held = cache.get(self.selectors)
        if held is None or held.graph is not graph:
            predicates = tuple(
                Equals(_cell("selectors", selector), (True,))
                for selector in self.selectors
            )
            selection = predicates[0] if len(predicates) == 1 else Or(predicates)
            members = tg.WhereSelector(tg.ItemsSelector(POSITION), selection)
            held = BoundOrdering(
                graph,
                DeclaredOrder(
                    LINEAR_NEXT,
                    members,
                    chain=tg.ItemsSelector(POSITION),
                ),
            )
            if len(cache) >= 128:
                cache.pop(next(iter(cache)))
            cache[self.selectors] = held
        return self.compiled.bind(graph, held)


def payload_for(graph: tg.Graph, reference: tg.ItemRef) -> dict[str, Any]:
    tier = next(t for t in graph.tiers if t.declaration.name == reference.tier)
    values = [
        value
        for value in tier.items[reference.index].attributes
        if value.name == PAYLOAD
    ]
    if len(values) != 1:
        raise ValueError("matching position has no unique payload")
    value = values[0]
    if not isinstance(value, tg.JsonAttributeValue):
        raise ValueError("matching position payload is not JSON")
    return cast(dict[str, Any], value.to_value())


def _match_payloads_uncached(
    form: Form, query: CrossTierQuery
) -> Iterator[tuple[dict[str, Any], ...]]:
    bound = query._bound(form)
    focused = frozenset(bound.focus().nodes)
    for span in bound.spans().matches:
        yield tuple(
            payload_for(bound.graph, cast(tg.ItemRef, node.reference))
            for node in span.items
            if node in focused
        )


def match_payloads(
    form: Form, query: CrossTierQuery
) -> Iterator[tuple[dict[str, Any], ...]]:
    cache = form.__dict__.setdefault("_cross_tier_matches", {})
    held = cache.get(query.source)
    if held is None:
        held = tuple(_match_payloads_uncached(form, query))
        if len(cache) >= 128:
            cache.pop(next(iter(cache)))
        cache[query.source] = held
    yield from held


def result_ranges(
    payloads: Iterable[dict[str, Any]], name: str
) -> tuple[tuple[int, int], ...]:
    values = sorted({tuple(pair) for payload in payloads for pair in payload[name]})
    result: list[tuple[int, int]] = []
    for start, end in values:
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(result[-1][1], end))
        else:
            result.append((start, end))
    return tuple(result)


def _qualified_selector(name: str, inventory: Any | None) -> str:
    if name == "unit":
        return name
    if name.startswith(("tier:", "feature:")):
        if not name.split(":", 1)[1]:
            raise rules.RuleError(f"empty selector {name!r}")
        return name
    if inventory is None:
        raise rules.RuleError(f"cross-tier selector {name!r} must be qualified")
    tiers = set(tier_names(inventory))
    tiers.update({"segment", "zero", "boundary", "prosody", "delivery", "analysis"})
    features = set(inventory.features)
    in_tier, in_feature = name in tiers, name in features
    if in_tier and in_feature:
        raise rules.RuleError(
            f"selector {name!r} is ambiguous; qualify tier:{name} or feature:{name}"
        )
    if in_tier:
        return f"tier:{name}"
    if in_feature:
        return f"feature:{name}"
    raise rules.RuleError(f"undeclared tier or feature selector {name!r}")


def _brace_predicate(text: str, *, current: bool = False) -> Predicate:
    text = text.strip()
    if not text:
        raise rules.RuleError("empty brace expression")
    choices = _split_top(text, frozenset({"|"}))
    value_list = (
        len(choices) > 1
        and "=" in choices[0]
        and all("=" not in part for part in choices[1:])
    )
    if len(choices) > 1 and not value_list:
        return _or(_brace_predicate(part, current=current) for part in choices)
    terms = _split_top(text.replace(",", "&"), frozenset({"&"}))
    if len(terms) > 1:
        return _and(_brace_predicate(part, current=current) for part in terms)
    if text.startswith("!"):
        return Not(_brace_predicate(text[1:], current=current))
    if text == "∅":
        return Or(())
    if text.startswith("@"):
        match = re.fullmatch(r"@([^{}\s]+)(?:\{(.*)\})?", text, re.DOTALL)
        if match is None:
            raise rules.RuleError(f"malformed cross-tier atom {text!r}")
        selector = _qualified_selector(match.group(1), None)
        body = match.group(2)
        target = And(()) if body is None else _brace_predicate(body, current=True)
        pointer = ("routes", selector)
        operand = Current(pointer) if current else _cell(*pointer)
        return Elements(operand, Quantifier.ANY, target)
    match = re.fullmatch(r"([\w-]+)\s*(!=|=)\s*(.*)", text, re.DOTALL)
    if match is None:
        raise rules.RuleError(f"malformed brace cell test {text!r}")
    key, operator, raw = match.groups()
    values: list[Any] = []
    for value in _split_top(raw, frozenset({"|"})):
        value = value.strip()
        if value == "none":
            values.append(None)
        elif value == '""':
            values.append("")
        elif value.startswith('"') and value.endswith('"'):
            values.append(value[1:-1])
        else:
            values.append(value)
    pointer = (("features" if current else "cells"), key)
    operand = Current(pointer) if current else _cell(*pointer)
    alternatives: list[Predicate] = []
    if None in values:
        alternatives.append(Not(Has(operand, "none")))
    concrete = tuple(value for value in values if value is not None)
    if concrete:
        alternatives.append(Equals(operand, concrete))
    equality = _or(alternatives)
    return equality if operator == "=" else Not(equality)


def _pattern_predicate(pattern: rules.Pattern) -> Predicate:
    parts: list[Predicate] = []
    if pattern.mark is not None:
        return Elements(
            _cell("marks"), Quantifier.ANY, Equals(Current(), (pattern.mark,))
        )
    if pattern.boundary is not None:
        parts.append(Equals(_cell("kind"), ("boundary",)))
        if pattern.boundary != "any":
            parts.append(
                Elements(
                    _cell("levels"),
                    Quantifier.ANY,
                    Equals(Current(), (pattern.boundary,)),
                )
            )
        return _and(parts)
    parts.append(Equals(_cell("kind"), ("zero", "segment")))
    if pattern.literal is not None:
        parts.append(Equals(_cell("core"), (pattern.literal,)))
    for key, value in pattern.seg_required.items():
        parts.append(Equals(_cell("features", key), (value,)))
    for key, values in pattern.seg_included.items():
        parts.append(Equals(_cell("features", key), tuple(values)))
    for key, values in pattern.seg_excluded.items():
        parts.append(Not(Equals(_cell("features", key), tuple(values))))
    for key, value in pattern.pro_required.items():
        parts.append(Equals(_cell("prosody", key), (value,)))
    for key, values in pattern.pro_included.items():
        parts.append(Equals(_cell("prosody", key), tuple(values)))
    for key, values in pattern.pro_excluded.items():
        parts.append(Not(Equals(_cell("prosody", key), tuple(values))))
    return _and(parts)


def _atom(text: str, inventory: Any) -> GraphPattern:
    brace: str | None = None
    base = text
    if text.endswith("}"):
        depth = 0
        for index in range(len(text) - 1, -1, -1):
            if text[index] == "}":
                depth += 1
            elif text[index] == "{":
                depth -= 1
                if depth == 0:
                    base, brace = text[:index], text[index + 1 : -1]
                    break
    if base == "*":
        predicate: Predicate = And(())
    elif base == "[vowel]":
        predicate = Equals(_cell("features", "manner"), ("vowel",))
    elif base == "[consonant]":
        predicate = _and(
            (
                Equals(_cell("kind"), ("segment",)),
                Not(Equals(_cell("features", "manner"), ("vowel",))),
            )
        )
    else:
        terms = (
            base[1:-1].replace(",", " ").split()
            if base.startswith("[") and base.endswith("]")
            else []
        )
        if terms and all("=" in term for term in terms):
            direct = []
            for term in terms:
                if "=" in term:
                    key, value = term.split("=", 1)
                    direct.append(Equals(_cell("features", key), (value,)))
            if direct:
                predicate = _and(direct)
        else:
            predicate = _pattern_predicate(rules._pattern(base, inventory))
    if brace is not None:
        predicate = _and((predicate, _brace_predicate(brace)))
    return AtomPattern(predicate)


def _sequence(parts: Sequence[GraphPattern]) -> GraphPattern:
    if not parts:
        raise rules.RuleError("empty sequence pattern")
    return parts[0] if len(parts) == 1 else SeqPattern(tuple(parts))


def _parse_graph_pattern(text: str, inventory: Any) -> GraphPattern:
    text = text.strip()
    alternatives = _split_top(text, frozenset({"|"}))
    if len(alternatives) > 1:
        return AltPattern(
            tuple(_parse_graph_pattern(part, inventory) for part in alternatives)
        )
    tokens: list[str] = []
    start = square = curly = round_ = 0
    for index, char in enumerate(text):
        if char == "[":
            square += 1
        elif char == "]":
            square -= 1
        elif char == "{":
            curly += 1
        elif char == "}":
            curly -= 1
        elif char == "(":
            round_ += 1
        elif char == ")":
            round_ -= 1
        elif char.isspace() and not square and not curly and not round_:
            token = text[start:index].strip()
            if token:
                tokens.append(token)
            start = index + 1
    token = text[start:].strip()
    if token:
        tokens.append(token)
    parsed: list[GraphPattern] = []
    for token in tokens:
        quantified = re.fullmatch(r"\((.*)\)(\*|\+|\?|\{\d+(?:,\d*)?\})", token)
        if token == "^":
            parsed.append(StartPattern())
        elif token == "$":
            parsed.append(EndPattern())
        elif quantified is not None:
            body = _parse_graph_pattern(quantified.group(1), inventory)
            suffix = quantified.group(2)
            if suffix == "*":
                bounds: tuple[int, int | None] = (0, None)
            elif suffix == "+":
                bounds = (1, None)
            elif suffix == "?":
                bounds = (0, 1)
            else:
                raw = suffix[1:-1]
                first, comma, last = raw.partition(",")
                minimum = int(first)
                maximum = minimum if not comma else int(last) if last else None
                bounds = (minimum, maximum)
            parsed.append(RepeatPattern(body, *bounds))
        elif token.startswith("(") and token.endswith(")"):
            parsed.append(_parse_graph_pattern(token[1:-1], inventory))
        else:
            parsed.append(_atom(token, inventory))
    return _sequence(parsed)


def _outer_edge(at: int, inventory: Any) -> dict[str, Any]:
    return {
        "kind": "boundary",
        "selectors": {"unit": True, "internal:outer-edge": True},
        "features": {"level": inventory._form_constants.edge_level},
        "cells": {"level": inventory._form_constants.edge_level},
        "levels": list(inventory.features["level"].values),
        "marks": [],
        "text": "",
        "input-ranges": [[at, at]],
        "output-ranges": [[at, at]],
        "unit-indices": [],
        "paths": [],
        "routes": {},
    }


def position_payloads(
    units: Sequence[Unit],
    intervals: Sequence[Interval],
    inventory: Any,
    paths: dict[int, str],
    views: Sequence[tuple[Mapping[str, str], Mapping[str, str]]],
    spelling: str | None = None,
) -> tuple[dict[str, Any], ...]:
    offsets = _ranges(units, spelling)
    positions: list[dict[str, Any]] = []
    routed: dict[int, list[dict[str, Any]]] = {index: [] for index in range(len(units))}
    openings: dict[int, list[tuple[int, Interval]]] = {}
    edges: dict[int, dict[str, set[str]]] = {}
    for number, interval in enumerate(intervals):
        openings.setdefault(interval.start, []).append((number, interval))
        for at, side in ((interval.start, "starts"), (interval.end, "ends")):
            edges.setdefault(at, {"starts": set(), "ends": set()})[side].add(
                interval.tier
            )
        aggregate: dict[str, str] = {}
        for _features, prosody in views[interval.start : interval.end]:
            aggregate.update(prosody)
        nested = {
            f"feature:{key}": [_route({key: value})]
            for key, value in aggregate.items()
            if key in inventory.features_by_mode.get("prosodic", ())
        }
        route = _route({}, nested)
        route.update(tier=interval.tier)
        for index in range(interval.start, interval.end):
            routed[index].append(route)
    total = (
        len(spelling) if spelling is not None else sum(len(unit.text) for unit in units)
    )
    if not units or not units[0].is_boundary:
        positions.append(_outer_edge(0, inventory))
    index = 0
    while index <= len(units):
        for number, interval in openings.get(index, ()):
            start = offsets[index][0] if index < len(offsets) else total
            end = offsets[interval.end - 1][1] if index < interval.end else start
            positions.append(
                {
                    "kind": "interval",
                    "selectors": {f"tier:{interval.tier}": True},
                    "features": {},
                    "text": "".join(unit.text for unit in units[index : interval.end]),
                    "input-ranges": [[start, end]],
                    "output-ranges": [[start, end]],
                    "unit-indices": list(range(index, interval.end)),
                    "paths": [],
                    "routes": {},
                    "interval-index": number,
                }
            )
        if index in edges:
            at = offsets[index][0] if index < len(offsets) else total
            positions.append(
                {
                    "kind": "gap",
                    "selectors": {"internal:gap": True},
                    "features": {
                        "starts": sorted(edges[index]["starts"]),
                        "ends": sorted(edges[index]["ends"]),
                    },
                    "text": "",
                    "input-ranges": [[at, at]],
                    "output-ranges": [[at, at]],
                    "unit-indices": [],
                    "paths": [],
                    "routes": {},
                }
            )
        if index == len(units):
            break
        unit = units[index]
        start, end = offsets[index]
        if unit.is_boundary:
            run_end = index + 1
            while run_end < len(units) and units[run_end].is_boundary:
                run_end += 1
            features: dict[str, Any] = {}
            for member_features, _prosody in views[index:run_end]:
                features.update(member_features)
            declared_levels = list(inventory.features["level"].values)
            level = features.get("level")
            levels = (
                declared_levels[: declared_levels.index(level) + 1]
                if level in declared_levels
                else []
            )
            selectors = {"unit": True, "tier:boundary": True}
            selectors.update({f"feature:{key}": True for key in features})
            positions.append(
                {
                    "kind": "boundary",
                    "selectors": selectors,
                    "features": features,
                    "cells": features,
                    "levels": levels,
                    "marks": [item.text for item in units[index:run_end]],
                    "text": "".join(item.text for item in units[index:run_end]),
                    "input-ranges": [[start, offsets[run_end - 1][1]]],
                    "output-ranges": [[start, offsets[run_end - 1][1]]],
                    "unit-indices": list(range(index, run_end)),
                    "paths": [paths[at] for at in range(index, run_end)],
                    "routes": {},
                }
            )
            index = run_end
            continue
        before, after = _prosody_positions(unit, index, start, inventory, paths[index])
        positions.extend(before)
        tier = "zero" if unit.is_zero else "segment"
        view_features, view_prosody = views[index]
        routes: dict[str, Any] = {}
        for route in routed[index]:
            routes.setdefault(f"tier:{route['tier']}", []).append(route)
        for key, value in view_prosody.items():
            if key in inventory.features_by_mode.get("prosodic", ()):
                routes[f"feature:{key}"] = [_route({key: value})]
        core = unit.text
        if unit.segment is not None and len(unit.segment.constituents) == 1:
            core = unit.segment.constituents[0].base
        positions.append(
            {
                "kind": tier,
                "selectors": {"unit": True, f"tier:{tier}": True},
                "features": dict(view_features),
                "prosody": dict(view_prosody),
                "cells": {**dict(view_features), **dict(view_prosody)},
                "core": core,
                "text": unit.text,
                "input-ranges": [[start, end]],
                "output-ranges": [[start, end]],
                "unit-indices": [index],
                "paths": [paths[index]],
                "routes": routes,
            }
        )
        positions.extend(after)
        index += 1
    if units and not units[-1].is_boundary:
        positions.append(_outer_edge(total, inventory))
    return tuple(positions)


def _source_intervals(source: Any, inventory: Any) -> tuple[Interval, ...]:
    """Decode carried intervals without constructing a second public projection."""
    gap_prefix = [0]
    for node in source.clock:
        gap_prefix.append(gap_prefix[-1] + node.gap_count)

    def coordinate(pointer: str) -> int:
        parts = pointer.split("/")
        tick = int(parts[2])
        gap = int(parts[4]) if len(parts) == 5 else 0
        return gap + gap_prefix[tick]

    indexed: list[tuple[int, Interval]] = []
    for tick, node in enumerate(source.clock):
        for group in node.groups:
            for event in group.events:
                index = source.house_features(event).get("interval-index")
                if type(index) is not int:
                    continue
                if event.span is not None:
                    start = coordinate(event.span.start)
                    end = coordinate(event.span.end)
                elif event.duration is not None:
                    start = gap_prefix[tick]
                    end = gap_prefix[tick + int(event.duration)]
                else:
                    raise ValueError("interval has no exact span")
                indexed.append(
                    (
                        index,
                        Interval(
                            group.tier,
                            start,
                            end,
                            inventory,
                            timing=event.timing,
                        ),
                    )
                )
    indexed.sort(key=lambda item: item[0])
    if [index for index, _interval in indexed] != list(range(len(indexed))):
        raise ValueError("graph interval order is not contiguous")
    return tuple(interval for _index, interval in indexed)


def _stored_json(graph: tg.Graph, path: str, name: str) -> dict[str, str] | None:
    resolved = graph.resolve_item(tg.DurableItemRef(path))
    tier = next(t for t in graph.tiers if t.declaration.name == resolved.tier)
    values = [
        attribute
        for attribute in tier.items[resolved.index].attributes
        if attribute.name.local_name == name
        and isinstance(attribute, tg.JsonAttributeValue)
    ]
    if not values:
        return None
    value = values[0].to_value()
    return cast(dict[str, str], value) if isinstance(value, dict) else None


def _unit_views(
    graph: tg.Graph,
    source: Any,
    indexed: Sequence[tuple[int, Unit, str]],
    inventory: Any,
) -> tuple[tuple[Mapping[str, str], Mapping[str, str]], ...]:
    """Read stored views first and derive only absent, known segment views."""
    from .form import _prosodic_features, _segmental

    views: list[tuple[Mapping[str, str], Mapping[str, str]]] = []
    for _index, unit, path in indexed:
        features = _stored_json(graph, path, "features-json")
        prosody = _stored_json(graph, path, "prosody-json")
        house = source.house_features(source.events[path])
        if unit.segment is not None:
            if features is None:
                features = (
                    {
                        key: value
                        for key, value in house.items()
                        if key in inventory.features
                        and key not in inventory.features_by_mode.get("prosodic", ())
                        and isinstance(value, str)
                    }
                    if "provenance" in house
                    else _segmental(unit.segment.scalar(), inventory)
                )
            if prosody is None:
                prosody = (
                    {
                        key: value
                        for key, value in house.items()
                        if key in inventory.features_by_mode.get("prosodic", ())
                        and isinstance(value, str)
                    }
                    if "provenance" in house
                    else _prosodic_features(unit.segment, inventory)
                )
        else:
            if features is None:
                features = {
                    key: value
                    for key, value in house.items()
                    if key in inventory.features and isinstance(value, str)
                }
            if prosody is None:
                prosody = {}
        views.append((features or {}, prosody or {}))
    return tuple(views)


def augment_graph(
    editor: tg.GraphEditor,
    base_graph: tg.Graph,
    source: Any,
    inventory: Any,
    spelling: str | None = None,
) -> None:
    """Add logical positions and their successor chain to ``editor``.

    The caller owns the editor and freezes it after all graph additions are
    complete. ``base_graph`` supplies the source tiers used to derive views.
    """
    indexed = source.unit_occurrences()
    units = tuple(unit for _, unit, _ in indexed)
    paths = {index: path for index, _, path in indexed}
    payloads = position_payloads(
        units,
        _source_intervals(source, inventory),
        inventory,
        paths,
        _unit_views(base_graph, source, indexed, inventory),
        spelling,
    )
    namespace = tg.NamespaceDeclaration("form-match", NS)
    position = tg.TierDeclaration(POSITION, "Form logical match positions")
    payload_declaration = tg.AttributeDeclaration(
        PAYLOAD, tg.AttributeDomain.ITEM, tg.JsonType.JSON
    )
    side = tg.RelationSideDeclaration(
        (tg.RelationEndpointKind.ITEM,), (POSITION,), 1, 1
    )
    linear_next = tg.PolyadicRelationDeclaration(
        LINEAR_NEXT,
        side,
        side,
        unique_sources=True,
        single_parent=True,
        acyclic=True,
    )
    associates_with = tg.PolyadicRelationDeclaration(
        ASSOCIATES_WITH,
        side,
        side,
        unique_sources=True,
    )
    if any(
        declaration.prefix == namespace.prefix for declaration in base_graph.namespaces
    ):
        raise tg.GraphValidationError(
            "duplicate namespace prefix 'form-match'; names must be unique"
        )
    items = tuple(
        tg.Item(
            durable_id=f"/matching/position/{index}",
            attributes=(tg.JsonAttributeValue(PAYLOAD, item_payload),),
        )
        for index, item_payload in enumerate(payloads)
    )
    relations = [
        tg.PolyadicRelationInstance(
            LINEAR_NEXT,
            (tg.ItemRef(POSITION, left),),
            (tg.ItemRef(POSITION, right),),
        )
        for left, right in pairwise(range(len(payloads)))
    ]
    segment_by_unit = {
        item_payload["unit-indices"][0]: index
        for index, item_payload in enumerate(payloads)
        if item_payload["kind"] in {"segment", "zero"}
    }
    for index, item_payload in enumerate(payloads):
        if item_payload["kind"] != "prosody":
            continue
        target = segment_by_unit[item_payload["unit-indices"][0]]
        relations.append(
            tg.PolyadicRelationInstance(
                ASSOCIATES_WITH,
                (tg.ItemRef(POSITION, index),),
                (tg.ItemRef(POSITION, target),),
            )
        )
    for declaration in (
        namespace,
        position,
        payload_declaration,
        linear_next,
        associates_with,
    ):
        editor.declare(declaration)
    editor.insert_items(POSITION, 0, items)
    for relation in relations:
        editor.add_relation(relation)


def _split_top(text: str, separators: frozenset[str]) -> list[str]:
    parts: list[str] = []
    start = square = curly = round_ = 0
    quoted = escaped = False
    for index, char in enumerate(text):
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == "[":
            square += 1
        elif char == "]":
            square -= 1
        elif char == "{":
            curly += 1
        elif char == "}":
            curly -= 1
        elif char == "(":
            round_ += 1
        elif char == ")":
            round_ -= 1
        elif not square and not curly and not round_ and char in separators:
            parts.append(text[start:index].strip())
            start = index + 1
    parts.append(text[start:].strip())
    return parts
