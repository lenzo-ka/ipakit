"""Praat TextGrid interchange over tiergraph's span view."""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from tiergraph.spanview import SpanViewProfile, span_view
from tiergraph.textgrid import from_textgrid, to_textgrid

import tiergraph

from . import _get_ipa
from ._textgrid_graph import build, clock
from .features import IPAFeatures
from .form import (
    Form,
    Interval,
    Timing,
    Unit,
    boundary_marks,
    edge_level,
    levels,
    tier_names,
    units,
)
from .form import spell as spell_units
from .inventories import Style, inventory

TEXTGRID_DIR = Path(__file__).parent / "data" / "textgrid"


@dataclass(frozen=True)
class Profile:
    """A named TextGrid tier mapping and its tiergraph selection document."""

    name: str
    summary: str
    tier_map: Mapping[str, str]
    span_view: SpanViewProfile


def _features(features: IPAFeatures | None) -> IPAFeatures:
    return _get_ipa() if features is None else features


def profiles() -> tuple[str, ...]:
    """Return the declarations present in the profile directory."""
    paths = tuple(TEXTGRID_DIR.iterdir())
    stray = sorted(path.name for path in paths if path.suffix != ".json")
    if stray:
        raise ValueError(
            f"TextGrid profile file {stray[0]!r} is not a JSON document; accepted directory contents: profile documents only"
        )
    return tuple(sorted(path.stem for path in paths))


def _roles(features: IPAFeatures) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                "boundary",
                "segment",
                *tier_names(features),
                *features.features_by_mode["prosodic"],
            }
        )
    )


def _point_roles(features: IPAFeatures) -> frozenset[str]:
    return frozenset({"boundary", *features.features_by_mode["prosodic"]})


def profile(name: str, *, features: IPAFeatures | None = None) -> Profile:
    """Load a profile, refusing names absent from the declaration directory."""
    accepted = profiles()
    if name not in accepted:
        raise ValueError(
            f"TextGrid profile {name!r} is unavailable; accepted profiles: {', '.join(accepted)}"
        )
    data = json.loads((TEXTGRID_DIR / f"{name}.json").read_text(encoding="utf-8"))
    envelope = {"summary", "tier_map", "span_view"}
    unknown = sorted(set(data) - envelope)
    if unknown:
        raise ValueError(
            f"TextGrid profile {name!r} has unknown key {unknown[0]!r}; accepted keys: summary, tier_map, span_view"
        )
    missing = sorted(envelope - set(data))
    if missing:
        raise ValueError(f"TextGrid profile {name!r} is missing key {missing[0]!r}")
    path = TEXTGRID_DIR / f"{name}.json"
    try:
        view = SpanViewProfile.from_data(data["span_view"])
    except ValueError as error:
        raise ValueError(
            f"TextGrid profile {name!r} in {str(path)!r} has an invalid span_view: {error}"
        ) from error
    mapping = data["tier_map"]
    declared = tuple(t.local_name for t in (*view.span_tiers, *view.point_tiers))
    if set(mapping) != set(declared):
        raise ValueError(
            f"TextGrid profile {name!r} maps {sorted(mapping)!r}; accepted tier names are {sorted(declared)!r}"
        )
    features = _features(features)
    accepted_roles = _roles(features)
    point_roles = _point_roles(features)
    point_tiers = {tier.local_name for tier in view.point_tiers}
    for tier, role in mapping.items():
        if role not in accepted_roles:
            raise ValueError(
                f"TextGrid tier {tier!r} has role {role!r}; accepted roles: {', '.join(accepted_roles)}"
            )
        point = tier in point_tiers
        if point != (role in point_roles):
            expected = "point tier" if role in point_roles else "span tier"
            raise ValueError(
                f"TextGrid tier {tier!r} assigns role {role!r} to the wrong class; accepted class: {expected}"
            )
    segments = [tier for tier, role in mapping.items() if role == "segment"]
    if len(segments) != 1:
        raise ValueError(
            f"TextGrid profile {name!r} has {len(segments)} segment tiers; accepted mapping: exactly one segment role"
        )
    return Profile(name, data["summary"], mapping, view)


_load_profile = profile  # Preserve access where the public parameter shadows its name.


def _write_base(
    form: Form, intervals: tuple[Interval, ...]
) -> tuple[list[Timing | None], dict[int, tuple[int, int]]]:
    segments = [unit for unit in form.units if not unit.is_boundary]
    timed = bool(segments) and all(unit.timing is not None for unit in segments)
    base: list[Timing | None] = []
    positions: dict[int, tuple[int, int]] = {}
    interval_edges = {
        Decimal(str(edge))
        for interval in intervals
        if interval.timing is not None
        for edge in (interval.timing.start, interval.timing.end)
    }
    previous_end: Decimal | None = None
    for unit_index, unit in enumerate(form.units):
        if unit.is_boundary:
            continue
        timing = unit.timing if timed else None
        if timing is not None:
            start = Decimal(str(timing.start))
            if previous_end is not None and start < previous_end:
                raise ValueError(
                    f"unit {unit_index} {unit.text!r} starts at {start} before the preceding end {previous_end}; accepted timing: adjacent or separated units"
                )
            if previous_end is not None and start > previous_end:
                base.append(Timing(float(previous_end), float(start - previous_end)))
            previous_end = start + Decimal(str(timing.duration))
        first = len(base)
        if timing is None:
            base.append(None)
        else:
            end = start + Decimal(str(timing.duration))
            cuts = [
                start,
                *sorted(edge for edge in interval_edges if start < edge < end),
                end,
            ]
            base.extend(
                Timing(float(left), float(right - left))
                for left, right in zip(cuts, cuts[1:], strict=False)
            )
        positions[unit_index] = (first, len(base))
    return base, positions


def write(
    form: Form,
    profile: str = "segments",
    *,
    spell: Callable[[str], str] | None = None,
    style: str | Style | None = None,
    scale: int | None = None,
    features: IPAFeatures | None = None,
) -> str:
    """Write carried spans as carried, or derive tiers when none are carried.

    ``style`` selects a named or supplied inventory style. ``spell`` remains
    the callable seam for callers that do not use the registry.
    """
    if style is not None and spell is not None:
        raise ValueError(
            "TextGrid style and spell cannot be combined; accepted input: one or the other"
        )
    features = _features(features)
    selected = _load_profile(profile, features=features)
    selected_style = (
        inventory(style, ipa=features).style if isinstance(style, str) else style
    )
    transform: Callable[[str], str] = (
        selected_style.spell
        if selected_style is not None
        else ((lambda value: value) if spell is None else spell)
    )
    refusals: list[tuple[str, int, str]] = []

    def styled(value: str, tier: str, interval: int) -> str:
        try:
            return transform(value)
        except ValueError:
            refusals.append((tier, interval, value))
            return ""

    if selected.span_view.clock_face == "physical":
        missing = next(
            (
                pair
                for pair in enumerate(form.units)
                if not pair[1].is_boundary and pair[1].timing is None
            ),
            None,
        )
        if missing is not None:
            index, unit = missing
            raise ValueError(
                f"TextGrid profile {profile!r} requires physical timing, but unit {index} {unit.text!r} has none; accepted input: every segment timed"
            )
    intervals = form.intervals if form.intervals else form.tier_intervals(features)
    for role in tier_names(features):
        role_intervals = tuple(item for item in intervals if item.tier == role)
        for left, right in zip(role_intervals, role_intervals[1:], strict=False):
            if right.start < left.end:
                raise ValueError(
                    f"TextGrid role {role!r} has intervals {left!r} and {right!r} overlapping or unordered; accepted intervals: one ordered, non-overlapping cover per tier"
                )
    base, positions = _write_base(form, intervals)
    physical_edges = {
        Decimal(str(timing.start)): index
        for index, timing in enumerate(base)
        if timing is not None
    }
    if base and base[-1] is not None:
        last_timing = base[-1]
        assert last_timing is not None
        physical_edges[
            Decimal(str(last_timing.start)) + Decimal(str(last_timing.duration))
        ] = len(base)
    span_data: list[tuple[tiergraph.QualifiedName, list[tuple[str, int, int]]]] = []
    point_data: list[tuple[tiergraph.QualifiedName, list[tuple[str, int]]]] = []
    nonboundary = [i for i, unit in enumerate(form.units) if not unit.is_boundary]
    for tier in selected.span_view.span_tiers:
        role = selected.tier_map[tier.local_name]
        values: list[tuple[str, int, int]] = []
        if role == "segment":
            values = [
                (
                    styled(form.units[i].text, tier.local_name, number),
                    positions[i][0],
                    positions[i][1],
                )
                for number, i in enumerate(nonboundary, 1)
            ]
        else:
            for interval in (item for item in intervals if item.tier == role):
                if interval.end > len(form.units):
                    raise ValueError(
                        f"TextGrid tier {tier.local_name!r} span {interval.start}..{interval.end} runs past the units; accepted end: at most {len(form.units)}"
                    )
                covered = [
                    i for i in range(interval.start, interval.end) if i in positions
                ]
                if not covered:
                    raise ValueError(
                        f"TextGrid tier {tier.local_name!r} span {interval.start}..{interval.end} covers no segment; accepted span: at least one non-boundary unit"
                    )
                start = positions[covered[0]][0]
                end = positions[covered[-1]][1]
                if selected.span_view.clock_face == "physical" and interval.timing:
                    start = physical_edges[Decimal(str(interval.timing.start))]
                    end = physical_edges[Decimal(str(interval.timing.end))]
                if selected_style is None:
                    label = transform(spell_units([form.units[i] for i in covered]))
                else:
                    separator = (
                        selected_style.separator
                        if selected_style.separator is not None
                        else " "
                    )
                    label = separator.join(
                        styled(form.units[i].text, tier.local_name, len(values) + 1)
                        for i in covered
                    )
                values.append(
                    (
                        label,
                        start,
                        end,
                    )
                )
        span_data.append((tier, values))
    for tier in selected.span_view.point_tiers:
        role = selected.tier_map[tier.local_name]
        point_values: list[tuple[str, int]] = []
        if role == "boundary":
            marks: dict[int, list[str]] = {}
            segment_position = 0
            for item in form.units:
                if item.is_boundary:
                    marks.setdefault(segment_position, []).append(item.text)
                else:
                    segment_position += 1
            starts = [positions[i][0] for i in nonboundary]
            for position, run in marks.items():
                at = len(base) if position == len(starts) else starts[position]
                mark = "".join(run)
                point_values.append(
                    (mark if selected_style is not None else transform(mark), at)
                )
        else:
            for i in nonboundary:
                mark = "".join(
                    glyph
                    for glyph, feature, _ in form.units[i].provenance
                    if feature == role
                )
                if mark:
                    point_values.append(
                        (
                            mark if selected_style is not None else transform(mark),
                            positions[i][0],
                        )
                    )
        point_data.append((tier, point_values))
    if refusals:
        details = "; ".join(
            f"tier {tier!r} interval {interval} label {label!r}"
            for tier, interval, label in refusals
        )
        style_name = selected_style.name if selected_style is not None else "callable"
        raise ValueError(
            f"TextGrid profile {profile!r} style {style_name!r} refused {details}; "
            "accepted labels: phones the style can spell"
        )
    graph = build(base, span_data, point_data)
    graph_clock = clock(graph) if selected.span_view.clock_face == "physical" else None
    document: str = to_textgrid(
        graph, selected.span_view, clock=graph_clock, scale=scale
    )
    return document


def read(
    document: str | bytes,
    *,
    profile: str | None = None,
    unit: str = "s",
    tier_map: Mapping[str, str] | None = None,
    face: str | None = None,
    read: Callable[[str], str] | None = None,
    style: str | Style | None = None,
    features: IPAFeatures | None = None,
) -> Form:
    """Read a TextGrid through an explicit mapping from tier names to roles.

    ``style`` selects a named or supplied inventory style. ``read`` remains
    the callable seam for callers that do not use the registry.
    """
    if style is not None and read is not None:
        raise ValueError(
            "TextGrid style and read cannot be combined; accepted input: one or the other"
        )
    features = _features(features)
    selected = (
        _load_profile(profile, features=features) if profile is not None else None
    )
    accepted_faces = ("physical", "tick")
    if face is not None and face not in accepted_faces:
        raise ValueError(
            f"TextGrid face {face!r} is unavailable; accepted faces: physical, tick"
        )
    if selected is not None and face is not None:
        raise ValueError(
            f"TextGrid profile {profile!r} carries face {selected.span_view.clock_face!r}; accepted input: omit face with a named profile"
        )
    if selected is None and tier_map is not None and face is None:
        raise ValueError(
            "TextGrid tier_map requires a face; accepted faces: physical, tick"
        )
    result = from_textgrid(document, unit=unit)
    selected_style = (
        inventory(style, ipa=features).style if isinstance(style, str) else style
    )
    transform: Callable[[str], str] = (
        selected_style.read
        if selected_style is not None
        else ((lambda value: value) if read is None else read)
    )
    span_names = tuple(t.local_name for t in result.profile.span_tiers)
    point_names = tuple(t.local_name for t in result.profile.point_tiers)
    document_names = (*span_names, *point_names)
    mapping = (
        tier_map
        if tier_map is not None
        else (selected.tier_map if selected is not None else None)
    )
    accepted = _roles(features)
    if mapping is None:
        raise ValueError(
            f"TextGrid tiers {document_names!r} require a mapping covering every tier and the segment role; accepted roles: {', '.join(accepted)}"
        )
    for tier, role in mapping.items():
        if role not in accepted:
            raise ValueError(
                f"TextGrid tier {tier!r} has role {role!r}; accepted roles: {', '.join(accepted)}"
            )
        if tier not in document_names:
            raise ValueError(
                f"tier map names {tier!r}, which is absent; accepted document tiers: {', '.join(document_names)}"
            )
    for tier in document_names:
        if tier not in mapping:
            raise ValueError(
                f"TextGrid tier {tier!r} is uncovered; accepted mapping: every document tier"
            )
    segments = [tier for tier, role in mapping.items() if role == "segment"]
    if len(segments) != 1:
        raise ValueError(
            f"TextGrid mapping has {len(segments)} segment tiers; accepted mapping: exactly one segment role"
        )
    point_roles = _point_roles(features)
    for tier, role in mapping.items():
        point = tier in point_names
        if point != (role in point_roles):
            actual = "TextTier" if point else "IntervalTier"
            expected = "TextTier" if role in point_roles else "IntervalTier"
            raise ValueError(
                f"TextGrid tier {tier!r} is a {actual}; accepted class for role {role!r}: {expected}"
            )
    views = {}
    for qualified_tier in (*result.profile.span_tiers, *result.profile.point_tiers):
        point = qualified_tier in result.profile.point_tiers
        one = dataclasses.replace(
            result.profile,
            span_tiers=() if point else (qualified_tier,),
            point_tiers=(qualified_tier,) if point else (),
            point_coverage_relation=(
                result.profile.point_coverage_relation if point else None
            ),
        )
        views[qualified_tier.local_name] = span_view(result.graph, one).spans
    segment_tier = segments[0]
    tick = (
        selected.span_view.clock_face == "tick"
        if selected is not None
        else face == "tick"
    )
    built_units: list[Unit] = []
    base_to_unit: dict[int, int] = {}
    unit_starts: set[int] = set()
    labels: list[str] = []
    segment_spans = []
    for interval_number, span in enumerate(views[segment_tier], 1):
        if not span.value:
            continue
        try:
            label = transform(span.value)
        except ValueError as error:
            accepted_label = (
                f"one {selected_style.name} segment"
                if selected_style is not None
                else "one house-IPA segment"
            )
            raise ValueError(
                f"TextGrid tier {segment_tier!r} interval {interval_number} "
                f"label {span.value!r} is unreadable; accepted label: {accepted_label}"
            ) from error
        try:
            parsed = units(label, features, strict=True)
        except ValueError as error:
            raise ValueError(
                f"TextGrid tier {segment_tier!r} interval {interval_number} label {span.value!r} is unreadable; accepted label: one segment"
            ) from error
        if len(parsed) != 1 or parsed[0].is_boundary:
            raise ValueError(
                f"TextGrid tier {segment_tier!r} interval {interval_number} label {span.value!r} parsed to {len(parsed)} units; accepted label: one segment"
            )
        first = result.clock.timing(result.profile.base_tier, span.start)
        last = result.clock.timing(result.profile.base_tier, span.end - 1)
        if not tick and first is not None and last is not None:
            parsed[0] = dataclasses.replace(
                parsed[0],
                timing=Timing(
                    float(first.start),
                    float(last.start + last.duration - first.start),
                ),
            )
        base_to_unit.update(
            (base, len(built_units)) for base in range(span.start, span.end)
        )
        unit_starts.add(span.start)
        labels.append(label)
        segment_spans.append(span)
        built_units.append(parsed[0])
    level_order = levels(features)
    level_set = set(level_order)
    boundary_tiers = tuple(
        tier
        for tier in result.profile.point_tiers
        if mapping[tier.local_name] == "boundary"
    )
    if tick and not boundary_tiers:
        marks: dict[str, str] = {}
        candidates = (
            (symbol, phone.features or {})
            for symbol, phone in features.separators.items()
        )
        for symbol, bundle in candidates:
            if "level" in bundle:
                marks.setdefault(bundle["level"], symbol)
        for symbol, bundle in boundary_marks(features).items():
            if "level" in bundle and "break" in bundle and "linking" not in bundle:
                marks.setdefault(bundle["level"], symbol)
        endings: dict[int, list[str]] = {}
        for qualified_tier in result.profile.span_tiers:
            role = mapping[qualified_tier.local_name]
            if role not in level_set:
                continue
            if role not in marks:
                raise ValueError(
                    f"TextGrid level tier {role!r} has no declared boundary mark; accepted profile: a mark declaring that level"
                )
            for span in views[qualified_tier.local_name]:
                if span.value:
                    endings.setdefault(span.end, []).append(role)
        pieces: list[str] = []
        for index, (label, span) in enumerate(zip(labels, segment_spans, strict=True)):
            pieces.append(label)
            ending = endings.get(span.end, [])
            if not ending:
                continue
            strongest = min(ending, key=level_order.index)
            final = index == len(labels) - 1
            if not final or level_order.index(strongest) < level_order.index(
                edge_level(features)
            ):
                pieces.append(marks[strongest])
        built_units = list(units("".join(pieces), features, strict=True))
        segment_units = [
            i for i, item in enumerate(built_units) if not item.is_boundary
        ]
        base_to_unit = {
            base: segment_units[index]
            for index, span in enumerate(segment_spans)
            for base in range(span.start, span.end)
        }
    elif boundary_tiers:
        base_tier = next(
            tier
            for tier in result.graph.tiers
            if tier.declaration.name == result.profile.base_tier
        )
        final_boundary = len(base_tier.items)
        boundary_points: dict[int, list[tuple[str, int, str]]] = {}
        for qualified_tier in boundary_tiers:
            for number, span in enumerate(views[qualified_tier.local_name], 1):
                if span.start not in unit_starts and span.start != final_boundary:
                    coordinate = result.clock.timing(
                        result.profile.base_tier, span.start
                    )
                    shown = span.start if coordinate is None else coordinate.start
                    raise ValueError(
                        f"TextGrid tier {qualified_tier.local_name!r} point {number} at {shown} does not land on a segment start or the final boundary; accepted coordinate: a segment's left boundary or the final base boundary"
                    )
                boundary_points.setdefault(span.start, []).append(
                    (
                        qualified_tier.local_name,
                        number,
                        (
                            (span.value or "")
                            if selected_style is not None
                            else transform(span.value or "")
                        ),
                    )
                )
        carried_units: list[Unit] = []
        base_to_carried: dict[int, int] = {}
        for segment, span in zip(built_units, segment_spans, strict=True):
            for tier_name, number, mark in boundary_points.get(span.start, []):
                try:
                    parsed_mark = units(mark, features, strict=True)
                except ValueError as error:
                    raise ValueError(
                        f"TextGrid tier {tier_name!r} point {number} mark {mark!r} is unreadable; accepted mark: boundary glyphs"
                    ) from error
                if not parsed_mark or any(not item.is_boundary for item in parsed_mark):
                    raise ValueError(
                        f"TextGrid tier {tier_name!r} point {number} mark {mark!r} is not a boundary run; accepted mark: boundary glyphs"
                    )
                carried_units.extend(parsed_mark)
            segment_index = len(carried_units)
            carried_units.append(segment)
            base_to_carried.update(
                (base, segment_index) for base in range(span.start, span.end)
            )
        for tier_name, number, mark in boundary_points.get(final_boundary, []):
            try:
                parsed_mark = units(mark, features, strict=True)
            except ValueError as error:
                raise ValueError(
                    f"TextGrid tier {tier_name!r} point {number} mark {mark!r} is unreadable; accepted mark: boundary glyphs"
                ) from error
            if not parsed_mark or any(not item.is_boundary for item in parsed_mark):
                raise ValueError(
                    f"TextGrid tier {tier_name!r} point {number} mark {mark!r} is not a boundary run; accepted mark: boundary glyphs"
                )
            carried_units.extend(parsed_mark)
        built_units = carried_units
        base_to_unit = base_to_carried
    intervals: list[Interval] = []
    for qualified_tier in result.profile.span_tiers:
        role = mapping[qualified_tier.local_name]
        if role == "segment" or (tick and role in level_set):
            continue
        for number, span in enumerate(views[qualified_tier.local_name], 1):
            if not span.value:
                continue
            covered = [
                base_to_unit[i]
                for i in range(span.start, span.end)
                if i in base_to_unit
            ]
            if not covered:
                raise ValueError(
                    f"TextGrid tier {qualified_tier.local_name!r} interval {number} covers only unclaimed base items; accepted span: at least one segment"
                )
            timing = (
                None
                if tick
                else result.clock.timing(result.profile.base_tier, span.start)
            )
            last = result.clock.timing(result.profile.base_tier, span.end - 1)
            held = (
                None
                if timing is None or last is None
                else Timing(
                    float(timing.start),
                    float(last.start + last.duration - timing.start),
                )
            )
            intervals.append(
                Interval(role, covered[0], covered[-1] + 1, features, held)
            )
    for qualified_tier in result.profile.point_tiers:
        role = mapping[qualified_tier.local_name]
        if role == "boundary":
            continue
        for number, span in enumerate(views[qualified_tier.local_name], 1):
            if span.start not in unit_starts:
                coordinate = result.clock.timing(result.profile.base_tier, span.start)
                shown = span.start if coordinate is None else coordinate.start
                raise ValueError(
                    f"TextGrid tier {qualified_tier.local_name!r} point {number} at {shown} does not land on a unit start; accepted coordinate: a segment's left boundary"
                )
            index = base_to_unit[span.start]
            mark = (
                (span.value or "")
                if selected_style is not None
                else transform(span.value or "")
            )
            existing = "".join(
                g for g, feature, _ in built_units[index].provenance if feature == role
            )
            if existing and mark != existing:
                raise ValueError(
                    f"TextGrid tier {qualified_tier.local_name!r} point {number} mark {mark!r} disagrees with segment {built_units[index].text!r}; accepted mark: {existing!r}"
                )
            if not existing:
                replacement = None
                for candidate in (
                    mark + built_units[index].text,
                    built_units[index].text + mark,
                ):
                    try:
                        parsed_mark = units(candidate, features, strict=True)
                    except ValueError:
                        continue
                    if (
                        len(parsed_mark) == 1
                        and not parsed_mark[0].is_boundary
                        and any(
                            feature == role
                            for _, feature, _ in parsed_mark[0].provenance
                        )
                    ):
                        replacement = parsed_mark
                        break
                if replacement is None:
                    raise ValueError(
                        f"TextGrid tier {qualified_tier.local_name!r} point {number} mark {mark!r} cannot apply to {built_units[index].text!r}; accepted mark: one {role} glyph"
                    )
                built_units[index] = dataclasses.replace(
                    replacement[0], timing=built_units[index].timing
                )
    return Form.of(built_units, intervals)
