"""Bridge the rewrite derivation machine to the tier-graph representation.

This module intentionally implements no recognition or rewriting.  It consumes
the immutable trace produced by :mod:`ipakit.rules` and projects that trace onto
the input-owned graph clock.  The rule engine scans its changing derivation
state.  The graph stores the resulting phantoms in the builder's pinned
four-coordinate order, gated in ``tests/tiergraph/test_rewrite_bridge.py`` by
``test_hot_bridge_projection_matches_serialized_fixture``, whose golden pins
the order of chained phantoms sharing a tick and tier.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ._fact_builder import (
    EventHandle,
    EventSpec,
    FactBuilder,
    PositionHandle,
    UnitCoordinates,
)
from ._graph_facts import (
    Declarations,
    EndpointKind,
    FeatureDeclaration,
    RelationDeclaration,
    TierDeclaration,
)
from ._ipa_graph import declarations
from ._moraic import Mora
from .form import Form, Unit


@dataclass(frozen=True)
class MoraicFixture:
    source: str
    output: str
    morae: tuple[str, ...]


def japanese_moraic_fixtures() -> Mapping[str, MoraicFixture]:
    """The curated rules-output-equals-adaptation demonstration fixture set."""
    return {
        "pen": MoraicFixture("pɛn", "pen", ("pe", "n")),
        "hot": MoraicFixture("hɑt", "hotːo", ("ho", "t", "to")),
        "bed": MoraicFixture("bɛd", "bedːo", ("be", "d", "do")),
        "cheese": MoraicFixture("t͡ʃiz", "t͡ɕiːzu", ("t͡ɕi", "i", "zu")),
        "beer": MoraicFixture("biɹ", "biːɾu", ("bi", "i", "ɾu")),
        "strike": MoraicFixture("stɹa͜ɪk", "sutoɾaiku", ("su", "to", "ɾa", "i", "ku")),
        "London": MoraicFixture("lɑndɑn", "ɾondon", ("ɾo", "n", "do", "n")),
        "Christmas": MoraicFixture(
            "kɹɪsməs", "kuɾisumasu", ("ku", "ɾi", "su", "ma", "su")
        ),
    }


def _bridge_declarations(inventory: Any, tier_names: Sequence[str]) -> Declarations:
    base = declarations(inventory)
    feature_names = {item.name for item in base.features}
    bridge_features = {
        "rule",
        "trace",
        "derivation-step",
        "source-site-order",
        "application-order",
        "target-index",
        "mora-kind",
    }
    permitted = frozenset(
        {
            "value",
            "spelling",
            "phantom",
            "input",
            "unit",
            "unit-index",
            *bridge_features,
        }
    )
    selected = set(tier_names)
    existing = {tier.name for tier in base.tiers}
    extra_tiers = tuple(
        TierDeclaration(name, permitted)
        for name in dict.fromkeys(tier_names)
        if name not in existing
    )
    events = frozenset({EndpointKind.EVENT})
    positions = frozenset({EndpointKind.COARSE_TICK, EndpointKind.REFINED_GAP})
    relations = base.relations + (
        RelationDeclaration(
            "rewrites-to",
            source_kinds=events,
            target_kinds=events,
            allow_empty_target=True,
            target_arity=(0, None),
        ),
        (
            RelationDeclaration(
                "inserts",
                source_kinds=positions,
                target_kinds=events,
                source_arity=(1, 1),
            )
            if base.relation("inserts") is None
            else ()
        ),
    )
    # The conditional tuple above is intentionally flattened here.
    flat_relations = tuple(
        relation
        for item in relations
        for relation in (item if isinstance(item, tuple) else (item,))
    )
    return Declarations(
        extra_tiers
        + tuple(
            TierDeclaration(
                tier.name,
                tier.features | permitted if tier.name in selected else tier.features,
            )
            for tier in base.tiers
        ),
        base.features
        + tuple(
            FeatureDeclaration(name) for name in sorted(bridge_features - feature_names)
        ),
        flat_relations,
        base.closed,
    )


@dataclass
class _Token:
    unit: Any
    handle: Any
    anchor: Any


def _walk_projection(
    current: list[_Token], steps: Sequence[Any], writer: Any
) -> list[_Token]:
    """One trace-site traversal; writers own payloads, references and anchors."""
    for step_index, step in enumerate(steps):
        edits: dict[int, list[Any]] = {}
        for edit in step.edits:
            edits.setdefault(edit.start, []).append(edit)
        output: list[_Token] = []
        cursor = 0
        site_order = 0
        while cursor <= len(current):
            at_site = edits.get(cursor)
            if at_site is not None:
                furthest = cursor
                for edit in at_site:
                    sources = current[edit.start : edit.end]
                    anchor = (
                        sources[0].anchor
                        if sources
                        else writer.insertion_anchor(edit.start)
                    )
                    targets = writer.emit(
                        step_index, step, edit, sources, anchor, site_order
                    )
                    output.extend(
                        _Token(unit, handle, anchor)
                        for unit, handle in zip(edit.replacement, targets, strict=True)
                    )
                    furthest = max(furthest, edit.end)
                    site_order += 1
                edits.pop(cursor, None)
                cursor = furthest
                continue
            if cursor == len(current):
                break
            old = current[cursor]
            target = writer.carry(step_index, step, old, cursor)
            output.append(_Token(old.unit, target, old.anchor))
            cursor += 1
        current = output
    return current


@dataclass
class _NativeWriter:
    builder: FactBuilder
    coordinates: UnitCoordinates
    input_length: int
    source_tiers: Sequence[str]
    target_tiers: Sequence[str]

    def insertion_anchor(self, index: int) -> PositionHandle:
        return self.coordinates.to_graph(min(index, self.input_length))

    def tier(self, step_index: int) -> str:
        return (
            self.target_tiers[min(step_index, len(self.target_tiers) - 1)]
            if self.target_tiers
            else self.source_tiers[-1]
        )

    def emit(
        self,
        step_index: int,
        step: Any,
        edit: Any,
        sources: Sequence[_Token],
        anchor: Any,
        site_order: int,
    ) -> Sequence[EventHandle]:
        specs = tuple(
            EventSpec(
                {
                    "value": unit.segment if unit.segment is not None else unit.text,
                    "spelling": unit.text,
                    "phantom": True,
                    "rule": edit.rule,
                    "trace": str(edit),
                    "derivation-step": step_index,
                    "source-site-order": site_order,
                    "application-order": site_order,
                    "target-index": target_index,
                },
                duration=0,
            )
            for target_index, unit in enumerate(edit.replacement)
        )
        targets = self.builder.add_ordered_sequence(
            self.tier(step_index),
            anchor,
            specs,
            derivation_step=step_index,
            source_site_order=site_order,
            application_order=site_order,
        )
        if sources:
            self.builder.relate(
                (token.handle for token in sources), "rewrites-to", targets
            )
        elif targets:
            self.builder.relate((anchor,), "inserts", targets)
        return targets

    def carry(
        self, step_index: int, step: Any, old: _Token, cursor: int
    ) -> EventHandle:
        targets = self.builder.add_ordered_sequence(
            self.tier(step_index),
            old.anchor,
            (
                EventSpec(
                    {
                        "value": old.unit.segment or old.unit.text,
                        "spelling": old.unit.text,
                        "phantom": True,
                        "rule": step.rule,
                        "trace": "no-op",
                    },
                    duration=0,
                ),
            ),
            derivation_step=step_index,
            source_site_order=cursor,
            application_order=cursor,
        )
        self.builder.relate((old.handle,), "rewrites-to", targets)
        return targets[0]


def derive_morae(units: Sequence[Unit], inventory: Any) -> tuple[Mora, ...]:
    """Analyze Japanese morae using the same declaration as syllabify.

    Material outside declared local mora spans is refused. Whole-sequence
    phonotactics and lexical attestation are outside this profile. Boundaries
    delimit regions and never silently carry an onset into the next word.
    """
    from .syllable import syllabifier

    engine = syllabifier("japanese", inventory)
    _, _, residue, groups = engine._derive_moraic(units, True)
    if residue:
        raise ValueError(
            f"derived mora segmentation has unlicensed material: {residue}"
        )
    return tuple(mora for group in groups for mora in group)


def _input(builder: FactBuilder, form: Form, source_tier: str) -> list[_Token]:
    tokens: list[_Token] = []
    for index, unit in enumerate(form.units):
        facts = {
            "value": unit.segment if unit.segment is not None else unit.text,
            "spelling": unit.text,
            "input": True,
            "unit": dataclasses.replace(unit, timing=None),
            "unit-index": index,
        }
        if unit.is_boundary:
            handle = builder.append_input_occurrence(
                source_tier, facts, refines_tick=True
            )
        else:
            handle = builder.append_input_atom(source_tier, facts)
        tokens.append(_Token(unit, handle, builder.unit_coordinates().to_graph(index)))
    return tokens


def project_derivation(
    derivation: Any,
    inventory: Any,
    *,
    source_tiers: Sequence[str] = ("broad",),
    target_tiers: Sequence[str] = ("narrow", "allophonic"),
    mora_language: str | None = None,
) -> Form:
    """Project an existing :class:`~ipakit.rules.Derivation` onto one clock.

    ``source_tiers`` is explicit and ordered.  The first is the unit projection
    input sequence. Only fired passes emit a layer; each reads the preceding
    emitted layer. Target names are clamped at the last supplied name, so an
    arbitrary number of fired passes remains representable without inventing
    tiers. Ordering within a layer is the builder's pinned total order.
    ``mora_language="japanese"`` explicitly adds the declared mora analysis;
    the default projects the trace without assigning a language.
    """
    if mora_language not in {None, "japanese"}:
        raise ValueError("rewrite mora projection supports only explicit 'japanese'")
    if not source_tiers:
        raise ValueError("a derivation projection requires an ordered source tier")
    tiers = (*source_tiers, *target_tiers, *(("mora",) if mora_language else ()))
    builder = FactBuilder(_bridge_declarations(inventory, tiers))
    start = inventory.read(derivation.start, strict=True)
    current = _input(builder, start, source_tiers[0])
    coordinates = builder.unit_coordinates()

    current = _walk_projection(
        current,
        derivation.fired,
        _NativeWriter(
            builder, coordinates, len(start.units), source_tiers, target_tiers
        ),
    )

    analyses = (
        derive_morae(tuple(t.unit for t in current), inventory)
        if mora_language is not None
        else ()
    )
    for index, analysis in enumerate(analyses):
        spelling = analysis.spelling
        children = [current[child] for child in analysis.children]
        anchor = children[0].anchor if children else builder.tick(0)
        mora = builder.add_ordered_sequence(
            "mora",
            anchor,
            (
                EventSpec(
                    {
                        "value": spelling,
                        "spelling": spelling,
                        "phantom": True,
                        "mora-kind": analysis.kind,
                    },
                    duration=0,
                ),
            ),
            derivation_step=len(derivation.fired),
            source_site_order=index,
            application_order=index,
        )[0]
        if children:
            builder.contain(mora, (child.handle for child in children))

    return Form._from_projection_input(
        builder.build_input(), spelling=derivation.result, features=inventory
    )


def japanese_moraic_fixture(name: str, inventory: Any) -> Form:
    """Run one curated adaptation fixture through rules and the bridge."""
    from .rules import shipped

    fixture = japanese_moraic_fixtures()[name]
    derivation = shipped("japanese-moraic", inventory).derive(fixture.source, inventory)
    if derivation.result != fixture.output:
        raise AssertionError(
            f"japanese-moraic {name}: {derivation.result!r} != {fixture.output!r}"
        )
    form = project_derivation(derivation, inventory, mora_language="japanese")
    derived = tuple(event["value"] for event in form.tier_events("mora"))
    if derived != fixture.morae:
        raise AssertionError(
            f"japanese-moraic {name}: derived morae {derived!r} != {fixture.morae!r}"
        )
    return form
