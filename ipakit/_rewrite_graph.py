"""Bridge the rewrite derivation machine to the tier-graph representation.

This module intentionally implements no recognition or rewriting.  It consumes
the immutable trace produced by :mod:`ipakit.rules` and projects that trace onto
the input-owned graph clock.  The rule engine scans its changing derivation
state.  The graph stores the resulting phantoms in the builder's pinned
four-coordinate order, tested by
``test_chained_phantom_sequences_have_pinned_subsequent_scan_order``.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ._ipa_graph import declarations
from ._tiergraph import (
    Declarations,
    EndpointKind,
    FeatureDeclaration,
    RelationDeclaration,
    TierDeclaration,
)
from ._tiergraph_builder import EventHandle, EventSpec, GraphBuilder, PositionHandle
from .form import Form, Unit


@dataclass(frozen=True)
class MoraicFixture:
    source: str
    output: str
    morae: tuple[str, ...]


def japanese_moraic_fixtures() -> Mapping[str, MoraicFixture]:
    """The attested rules-output-equals-adaptation fixture set."""
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
            "compatibility-unit",
            "compatibility-index",
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
    unit: Unit
    handle: EventHandle
    anchor: PositionHandle


@dataclass(frozen=True)
class _Mora:
    spelling: str
    children: tuple[int, ...]
    kind: str = "ordinary"


def derive_morae(units: Sequence[Unit], inventory: Any) -> tuple[_Mora, ...]:
    """Deterministically segment a derived narrow sequence into morae.

    Classification is read from the inventory's ``manner`` declaration.
    A consonant onset joins the following vowel; coda nasals, geminate first
    halves, long-vowel second halves, and diphthong second vowels stand alone.
    """
    morae: list[_Mora] = []
    onset: list[tuple[int, str]] = []
    for index, unit in enumerate(units):
        segment = unit.segment
        if segment is None:
            continue
        is_vowel = inventory.get_features(unit.text).get("manner") == "vowel"
        if is_vowel:
            phases = tuple(part.base for part in segment.constituents)
            first = phases[0]
            onset_spelling = "".join(spelling for _, spelling in onset)
            children = tuple(child for child, _ in onset) + (index,)
            morae.append(_Mora(onset_spelling + first, children))
            for phase in phases[1:]:
                morae.append(_Mora(phase, (index,), "diphthong-second"))
            if "ː" in segment.prosody:
                morae.append(_Mora(first, (index,), "long-vowel-second"))
            onset.clear()
            continue

        base = segment.constituents[0].base
        if "ː" in segment.prosody:
            morae.append(_Mora(base, (index,), "geminate-half"))
            onset = [(index, base)]
            continue
        manner = inventory.get_features(unit.text).get("manner")
        next_is_vowel = index + 1 < len(units) and (
            inventory.get_features(units[index + 1].text).get("manner") == "vowel"
        )
        if manner == "nasal" and not next_is_vowel:
            if onset:
                # Settled Japanese fixtures have no non-nasal coda here;
                # retain any pending material with the independently moraic nasal.
                base = "".join(spelling for _, spelling in onset) + base
                children = tuple(child for child, _ in onset) + (index,)
                onset.clear()
            else:
                children = (index,)
            morae.append(_Mora(base, children, "nasal"))
        else:
            onset.append((index, unit.text))
    if onset:
        raise ValueError("derived mora segmentation ended with a non-nasal coda")
    return tuple(morae)


def _input(builder: GraphBuilder, form: Form, source_tier: str) -> list[_Token]:
    tokens: list[_Token] = []
    for index, unit in enumerate(form.units):
        facts = {
            "value": unit.segment if unit.segment is not None else unit.text,
            "spelling": unit.text,
            "input": True,
            "compatibility-unit": dataclasses.replace(unit, timing=None),
            "compatibility-index": index,
        }
        if unit.is_boundary:
            handle = builder.append_input_occurrence(
                source_tier, facts, refines_tick=True
            )
        else:
            handle = builder.append_input_atom(source_tier, facts)
        tokens.append(
            _Token(unit, handle, builder.compatibility_coordinates().to_graph(index))
        )
    return tokens


def project_derivation(
    derivation: Any,
    inventory: Any,
    *,
    source_tiers: Sequence[str] = ("broad",),
    target_tiers: Sequence[str] = ("narrow", "allophonic"),
) -> Form:
    """Project an existing :class:`~ipakit.rules.Derivation` onto one clock.

    ``source_tiers`` is explicit and ordered.  The first is the compatibility
    input sequence. Only fired passes emit a layer; each reads the preceding
    emitted layer. Target names are clamped at the last supplied name, so an
    arbitrary number of fired passes remains representable without inventing
    tiers. Ordering within a layer is the builder's pinned total order.
    """
    if not source_tiers:
        raise ValueError("a derivation projection requires an ordered source tier")
    tiers = (*source_tiers, *target_tiers, "mora")
    builder = GraphBuilder(_bridge_declarations(inventory, tiers))
    start = inventory.read(derivation.start, strict=True)
    current = _input(builder, start, source_tiers[0])
    coordinates = builder.compatibility_coordinates()

    for step_index, step in enumerate(derivation.fired):
        tier = (
            target_tiers[min(step_index, len(target_tiers) - 1)]
            if target_tiers
            else source_tiers[-1]
        )
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
                        else coordinates.to_graph(min(edit.start, len(start.units)))
                    )
                    specs = tuple(
                        EventSpec(
                            {
                                "value": (
                                    unit.segment
                                    if unit.segment is not None
                                    else unit.text
                                ),
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
                    targets = builder.add_ordered_sequence(
                        tier,
                        anchor,
                        specs,
                        derivation_step=step_index,
                        source_site_order=site_order,
                        application_order=site_order,
                    )
                    if sources:
                        builder.relate(
                            (token.handle for token in sources), "rewrites-to", targets
                        )
                    elif targets:
                        builder.relate((anchor,), "inserts", targets)
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
            targets = builder.add_ordered_sequence(
                tier,
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
            builder.relate((old.handle,), "rewrites-to", targets)
            output.append(_Token(old.unit, targets[0], old.anchor))
            cursor += 1
        current = output

    analyses = derive_morae(tuple(t.unit for t in current), inventory)
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

    return Form._from_graph(builder.build(), spelling=derivation.result)


def japanese_moraic_fixture(name: str, inventory: Any) -> Form:
    """Run one attested adaptation fixture through rules and the bridge."""
    from .rules import shipped

    fixture = japanese_moraic_fixtures()[name]
    derivation = shipped("japanese-moraic", inventory).derive(fixture.source, inventory)
    if derivation.result != fixture.output:
        raise AssertionError(
            f"japanese-moraic {name}: {derivation.result!r} != {fixture.output!r}"
        )
    form = project_derivation(derivation, inventory)
    derived = tuple(
        event.features["value"]
        for node in form._graph.clock
        for group in node.groups
        if group.tier == "mora"
        for event in group.events
    )
    if derived != fixture.morae:
        raise AssertionError(
            f"japanese-moraic {name}: derived morae {derived!r} != {fixture.morae!r}"
        )
    return form
