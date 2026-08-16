"""What a drawn tract has to satisfy, whatever the head or the phone.

The first properties here were found by looking at a picture and then chased
by hand for a while. A label that overlaps another, or a cavity that leaks
where it should be sealed, is not something the rest of the suite can see:
the geometry is well-formed, the numbers are fine, and the drawing is wrong.

Two later ones answer a different question -- not whether the drawing is
well-formed but whether it *says* anything. A figure that gives two phones
the same picture is well-formed and useless, so the collapse is measured
here and the remainder is named rather than left as a round number.

And one is not about the SVG at all. A mark can be present, styled, inside
the frame and last in document order and still be invisible, because a fill
above it is opaque or a renderer outside a browser dropped its custom
property. So it gets rasterized, removed, rasterized again and the changed
pixels counted, which is the only claim about a mark worth making.
"""

from __future__ import annotations

import ast
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import warnings
import xml.etree.ElementTree as ET
import zlib
from dataclasses import replace
from pathlib import Path
from typing import Any

import ipakit
import pytest
from ipakit import anatomy, tract_svg
from ipakit import tract as tract_module
from ipakit.constants import METADATA_ATTRS
from ipakit.features import IPAFeatures
from ipakit.models import Feature
from ipakit.tract import (
    GLOTTAL_AXIS,
    Head,
    TractPoint,
    constrictions,
    glottal_aperture,
    glottal_scale,
    head,
    heads,
    landmarks,
    posture,
    secondary_marks,
    tract_point,
    tract_reading,
    unmodelled,
    velic_aperture,
)

from tests import corpus

# Advances rounded up: a box narrower than the text it holds is the bug this
# guards against, so erring wide is the safe direction.
ADVANCE = {"glyph": 24 * 0.62, "caption": 12 * 0.62, "feat": 10.5 * 0.62}
DEFAULT_ADVANCE = 10.5 * 0.64
LINE = 12.0

_TEXT = re.compile(
    r'<text x="([-\d.]+)" y="([-\d.]+)" class="([^"]*)"[^>]*>(.*?)</text>', re.S
)
_TSPAN = re.compile(r"<tspan[^>]*>([^<]*)</tspan>")


def _boxes(svg: str) -> list[tuple[float, float, float, float, str]]:
    out = []
    for match in _TEXT.finditer(svg):
        x, y, cls, body = match.group(1), match.group(2), match.group(3), match.group(4)
        lines = _TSPAN.findall(body) or [re.sub(r"<[^>]*>", "", body)]
        advance = next((v for k, v in ADVANCE.items() if k in cls), DEFAULT_ADVANCE)
        width = max(len(line) for line in lines) * advance
        left = (
            float(x) - width
            if 'text-anchor="end"' in match.group(0)
            else float(x) - width / 2
        )
        top = float(y) - LINE
        out.append((left, top, left + width, top + LINE * len(lines), "/".join(lines)))
    return out


def _section(name: str, phone: str | None) -> str:
    """The section a figure would carry, less the caption.

    Derived by ``tract_svg.drawing``, which is what ``make figures`` calls:
    these properties used to re-derive the posture themselves, which is two
    chances to disagree about what the picture is, and a test that passes
    against a drawing the command would not produce checks nothing.
    """
    drawn = tract_svg.drawing(name, phone)
    return tract_svg.section_svg(
        drawn["geometry"],
        None,
        drawn["aperture"],
        drawn["posture"],
        None,
        drawn["active"],
    )


PHONES = [None, "m", "b", "n", "t", "k", "ɡ", "s", "ʃ", "a", "i", "u", "h", "␣"]

#: Phones and marked units whose contrast the posture alone cannot carry:
#: glottal state, laterality, a secondary articulation, a release phase, an
#: airstream. Every one of them is what a shipped rule set emits or what the
#: chart spells with a diacritic, so none is a hypothetical.
ANNOTATED = [
    "ʔ",
    "ɦ",
    "a̤",
    "a̰",
    "ɬ",
    "ɫ",
    "l̥",
    "n̩",
    "tʰ",
    "t̚",
    "tˡ",
    "tˤ",
    "tʲ",
    "ɓ",
    "ʘ",
    "pʼ",
]


@pytest.mark.parametrize("head_name", sorted(heads()))
@pytest.mark.parametrize("phone", PHONES + ANNOTATED, ids=lambda p: p or "reference")
def test_no_label_overlaps_another(head_name: str, phone: str | None) -> None:
    """Two labels may not occupy the same space.

    The layout drops each label until its box is clear, so this can only fail
    if a box is reserved for something other than what is drawn -- a narrower
    advance than the face, or a name reserved before a state was appended to
    it. Both of those shipped.
    """
    boxes = _boxes(_section(head_name, phone))
    assert boxes, "a drawing with no labels is not being checked"
    clashes = [
        (a[4], b[4])
        for i, a in enumerate(boxes)
        for b in boxes[i + 1 :]
        if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
    ]
    assert not clashes, f"{head_name} {phone!r}: {clashes}"


def _pts(d: str) -> list[tuple[float, float]]:
    return [(float(a), float(b)) for a, b in re.findall(r"([-\d.]+),([-\d.]+)", d)]


@pytest.mark.parametrize("head_name", sorted(heads()))
@pytest.mark.parametrize("phone", ["b", "p", "m"])
def test_a_shut_mouth_leaks_only_at_the_glottis(phone: str, head_name: str) -> None:
    """With the lips together the oral boundary closes, glottis apart.

    The tract is drawn from several declarations -- wall, floor, two lip
    bodies -- that have to meet. They met by luck before they met by
    construction, and the seams were invisible until something was rasterized.
    """
    svg = _section(head_name, phone)
    walls = [_pts(d) for d in re.findall(r'<path d="([^"]*)" class="wall"/>', svg)]
    floor = re.search(r'<path d="([^"]*)" class="openline"/>', svg)
    lips = [_pts(d) for d in re.findall(r'<path d="([^"]*)" class="lip[^"]*"/>', svg)]
    assert walls and floor and len(lips) == 2

    def gap(a: tuple[float, float], b: tuple[float, float]) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    assert gap(lips[0][2], lips[1][2]) < 0.5, "the lips do not meet"
    assert (
        min(gap(v, walls[0][0]) for v in lips[0]) < 0.5
    ), "roof adrift of the upper lip"
    floor_pts = _pts(floor.group(1))
    assert (
        min(gap(v, floor_pts[0]) for v in lips[1]) < 0.5
    ), "floor adrift of the lower lip"
    if velic_aperture(IPAFeatures(), IPAFeatures().get_features(phone)) <= 0.01:
        assert len(walls) == 1, "a sealed velum must leave the roof unbroken"


@pytest.mark.parametrize("head_name", sorted(heads()))
def test_the_tongue_stays_inside_the_tract(head_name: str) -> None:
    """No tongue surface may pass the roof or the floor, for any phone.

    ``offset`` is a fraction from the floor to the wall, so the jaw has to
    move the floor rather than displace the result. Displacing it instead
    pushes a closure that already touches the wall straight through it, which
    needs a front closure and a half-closed jaw together to show up -- a
    click. A closed jaw or an open one both hide it.

    Asked of ``drawing`` rather than re-derived here. Re-deriving it took the
    surface from the *first* constriction where the drawing takes it from all
    of them, so the clicks this was written for -- and every other segment
    that closes twice -- were checked on a surface no figure carries.
    """
    ipa = IPAFeatures()
    checked, escapes = 0, []
    for phone in sorted(ipa.phones):
        current = tract_svg.drawing(head_name, phone)["geometry"]
        surface = current.get("tongue") or []
        if not surface:  # a posture the tongue is not the boundary of
            continue
        checked += 1
        at = {round(a, 4): (x, y) for a, x, y in surface}
        for row in current["rows"]:
            here = at.get(round(row["arc"], 4))
            if here is None:
                continue
            if here[1] > row["wall"][1] + 1e-9 or here[1] < row["open"][1] - 1e-9:
                escapes.append((phone, round(row["arc"], 3)))
                break
    assert checked > 100, f"only {checked} phones drew a tongue: the sweep is vacuous"
    assert not escapes, f"{head_name}: tongue outside the tract for {escapes[:6]}"


#: How far short of a stated constriction a *sampled* surface may sit. The
#: nearest sample to a constriction is up to one step of arc off its peak,
#: where the raised cosine has come down by well under this. What the check
#: has to separate is a constriction the figure does not carry at all, which
#: leaves the surface at rest -- two orders further down.
SAMPLING_SLACK = 1e-3


@pytest.mark.parametrize("phone", ["k", "a", "i", "u", "ʃ"])
def test_unbounded_tongue_surface_reaches_declared_attachment(phone: str) -> None:
    """Without an active tip gesture, the declared anterior taper is drawn."""
    current = tract_svg.drawing(head().name, phone)["geometry"]
    surface = current["tongue"]
    span_front = head().tongue_span[0]
    assert surface[0][0] >= span_front
    assert surface[0][0] - span_front < 1.0 / tract_svg.SAMPLES


def test_dental_tip_reaches_its_forward_declared_arc() -> None:
    """A tip target anterior to the tip landmark remains reachable."""
    ipa, h = IPAFeatures(), head()
    target = next(
        point
        for point in posture(ipa, "θ", h).constrictions
        if point.articulator == "tongue-tip"
    )
    surface = tract_svg.drawing(h.name, "θ")["geometry"]["tongue"]
    assert target.arc is not None
    assert target.arc <= surface[0][0] < target.arc + 1.0 / tract_svg.SAMPLES


@pytest.mark.parametrize("phone", ["ʜ", "ʢ", "ʡ"])
def test_epiglottal_phones_pose_the_leaf_and_couple_the_tongue_root(phone: str) -> None:
    """The epiglottal closure belongs to its leaf, with a bounded root assist."""
    ipa, h = IPAFeatures(), head()
    p = posture(ipa, phone, h)
    current = tract_svg.build_geometry(h, landmarks(ipa, h.name), p)

    assert p.reading is not None and p.reading.articulator == "epiglottis"
    assert p.epiglottal == pytest.approx(p.reading.offset)
    assert current["epiglottis"]["aperture"] < h.epiglottis(p.epiglottal / 2).aperture
    assert any(q.articulator == "tongue-root" for q in p.tongue_controls)
    assert current["tongue"][-1][0] == pytest.approx(h.tongue_span[1])


def test_epiglottal_tongue_assist_is_bounded_by_declared_coupling() -> None:
    """The leaf never enters tongue controls through its primary reading."""
    ipa, original = IPAFeatures(), head()
    zero = replace(original, epiglottis_tongue_coupling=0.0)
    capped = replace(original, epiglottis_tongue_coupling=0.45)
    at_zero = posture(ipa, "ʡ", zero)
    at_cap = posture(ipa, "ʡ", capped)

    assert at_zero.tongue_controls == zero.rest.tongue_controls
    assert len(at_cap.tongue_controls) == len(capped.rest.tongue_controls) + 1
    assist = at_cap.tongue_controls[-1]
    assert assist.articulator == "tongue-root"
    assert assist.offset == pytest.approx(
        capped.rest.offset
        + (1.0 - capped.rest.offset)
        * at_cap.epiglottal
        * capped.epiglottis_tongue_coupling
    )
    zero_geometry = tract_svg.build_geometry(zero, landmarks(ipa, zero.name), at_zero)
    cap_geometry = tract_svg.build_geometry(capped, landmarks(ipa, capped.name), at_cap)
    assert zero_geometry["tongue"] != cap_geometry["tongue"]
    assert zero_geometry["epiglottis"] == cap_geometry["epiglottis"]


def test_non_epiglottal_postures_leave_the_leaf_byte_identical_at_rest() -> None:
    """Unrelated gestures do not leak into the epiglottis pose."""
    ipa, h = IPAFeatures(), head()
    bodies = []
    for phone in ("t", "k", "a", "ʕ", "␣"):
        p = posture(ipa, phone, h)
        current = tract_svg.build_geometry(h, landmarks(ipa, h.name), p)
        assert p.epiglottal == 0.0
        bodies.append(current["epiglottis"]["body"])
    assert all(body == bodies[0] for body in bodies[1:])


def test_epiglottal_degree_scales_the_modeled_aperture() -> None:
    """Open, approximant and closure degrees monotonically close the gap."""
    h = head()
    apertures = [h.epiglottis(degree).aperture for degree in (0.0, 0.5, 1.0)]
    assert apertures[0] > apertures[1] > apertures[2]
    assert apertures[2] == pytest.approx(0.0)


def test_epiglottal_aperture_matches_generated_pixel_pins() -> None:
    """Inventory epiglottals pin their displayed tip-to-target gap."""
    from tests.fixtures._capture_epiglottal_constriction import capture

    pinned = json.loads(
        (
            Path(__file__).parent / "fixtures" / "epiglottal_constriction.json"
        ).read_text()
    )
    assert capture() == pinned
    assert pinned["open"] > pinned["ʜ"] == pinned["ʢ"] > pinned["ʡ"]
    assert pinned["ʡ"] == pytest.approx(0.0)


@pytest.mark.parametrize("phone", ["t", "s"])
def test_tip_closure_guards_against_a_forward_scallop(phone: str) -> None:
    """The top surface starts at an active tip instead of continuing before it."""
    ipa, h = IPAFeatures(), head()
    target = next(
        point
        for point in posture(ipa, phone, h).constrictions
        if point.articulator == "tongue-tip"
    )
    surface = tract_svg.drawing(h.name, phone)["geometry"]["tongue"]
    assert target.arc is not None
    assert target.arc - 1.0 / tract_svg.SAMPLES <= surface[0][0] <= target.arc + 1e-12


def test_lateral_keeps_the_declared_anterior_attachment() -> None:
    """The model's half-height /l/ is deliberately not closure-clamped."""
    h = head()
    assert h.tongue_span is not None
    surface = tract_svg.drawing(h.name, "l")["geometry"]["tongue"]
    assert surface[0][0] == 0.0800 == h.tongue_span[0]


@pytest.mark.skipif(shutil.which("rsvg-convert") is None, reason="rsvg-convert absent")
def test_dental_tip_paints_the_declared_target_region(tmp_path: Path) -> None:
    """The dental target is occupied by tongue pixels, not white space."""
    svg = _section(head().name, "θ")
    marker = re.search(
        r'<circle cx="([-\d.]+)" cy="([-\d.]+)" r="5" class="constriction', svg
    )
    assert marker is not None
    without = re.sub(r'<path d="[^"]*" class="tongue(?:body)?"[^>]*/>', "", svg)
    width, painted = _pixels(svg, tmp_path / "theta.svg", width=760)
    _, absent = _pixels(without, tmp_path / "theta-without-tongue.svg", width=760)
    cx, cy = float(marker.group(1)), float(marker.group(2))
    near_target = [
        (x, y)
        for x, y in _differing(width, painted, absent)
        if math.hypot(x - cx, y - cy) <= 18.0
    ]
    assert len(near_target) >= 10


def _along(
    floor: tuple[float, float], wall: tuple[float, float], at: tuple[float, float]
) -> float:
    """How far from the floor to the wall a drawn point sits: its offset."""
    dx, dy = wall[0] - floor[0], wall[1] - floor[1]
    return ((at[0] - floor[0]) * dx + (at[1] - floor[1]) * dy) / (dx * dx + dy * dy)


@pytest.mark.parametrize("head_name", sorted(heads()))
def test_an_articulator_reaches_its_target(head_name: str) -> None:
    """Where a segment states a constriction, the drawn tongue gets there.

    The taper that brings the tongue to a point at each end of its span was
    scaling constrictions inside that band, so a tip closing near the front
    stopped short of the ridge it was supposed to touch -- visible on a click,
    whose front closure sits well inside the taper.

    Read off the surface ``drawing`` puts in the figure rather than off the
    model beside it. Asked of the model, this holds while the figure carries
    only the first of a segment's constrictions: a click's velar closure is
    then absent from every picture and present in every check.
    """
    ipa = IPAFeatures()
    counts: dict[str, int] = {}
    short = []
    for phone in sorted(ipa.phones):
        current = tract_svg.drawing(head_name, phone)["geometry"]
        surface = current.get("tongue") or []
        if not surface:
            continue
        rows = {round(row["arc"], 6): row for row in current["rows"]}
        for point in constrictions(ipa, ipa.get_features(phone)):
            if point.arc is None or point.offset is None:
                continue
            if not surface[0][0] <= point.arc <= surface[-1][0]:
                continue  # outside the span the tongue bounds, e.g. the lips
            counts[phone] = counts.get(phone, 0) + 1
            near = min(surface, key=lambda s: abs(s[0] - point.arc))
            row = rows.get(round(near[0], 6))
            if row is None:
                # A clamped tip is an interpolated edge, not a sample-grid row.
                floor = head(head_name).project(TractPoint(near[0], 0.0))
                wall = head(head_name).project(TractPoint(near[0], 1.0))
                assert floor is not None and wall is not None
                row = {"open": floor, "wall": wall}
            reached = _along(row["open"], row["wall"], (near[1], near[2]))
            if reached < point.offset - SAMPLING_SLACK:
                short.append(
                    (phone, round(point.arc, 3), round(point.offset - reached, 4))
                )
    checked = sum(counts.values())
    assert checked > 100, f"only {checked} constrictions drawn: the sweep is vacuous"
    # The mistake this is here for only shows on a segment whose second
    # closure the tongue makes, so the sweep has to reach one. Pinned rather
    # than assumed: a change that puts every such segment outside the span
    # would leave this passing on the easy half.
    assert [
        p for p, n in counts.items() if n > 1
    ], "no segment closing twice inside the tongue's span is checked"
    assert not short, f"{head_name}: articulator short of target for {short[:6]}"


@pytest.mark.parametrize("head_name", sorted(heads()))
def test_no_label_leaves_the_frame(head_name: str) -> None:
    """A label pushed off the canvas is as unreadable as one under another.

    The layout only knew about collisions, so the three-line glottal label
    ran past the bottom edge on every head -- invisible to the overlap
    property, which does not care where the boxes are.
    """
    checked = 0
    escapes = []
    for phone in [None, *PHONES[1:], *ANNOTATED]:
        for box in _boxes(_section(head_name, phone)):
            checked += 1
            if not (0 <= box[1] and box[3] <= tract_svg.SECTION_HEIGHT):
                escapes.append((phone, box[4], round(box[1], 1), round(box[3], 1)))
            if not (0 <= box[0] and box[2] <= tract_svg.WIDTH):
                escapes.append((phone, box[4], round(box[0], 1), round(box[2], 1)))
    assert checked > 200, "sweep did not run"
    assert not escapes, f"{head_name}: {len(escapes)} outside the frame, {escapes[:4]}"


class TestTheAnnotationLayerIsReadOffTheDeclarations:
    """Marks are asked of the data, never listed here.

    The drawing carries two parameters against the specification's nine, so
    most of what a segment states has no contour. The rule is that what is
    annotated, and *why*, both come from ``ipa.xml``: a table of phones or
    of features here would drift from it the way three copies of the
    secondary set once did.
    """

    def test_nothing_the_posture_already_draws_is_annotated(self) -> None:
        """A feature the constriction expresses must not be repeated.

        What the constriction expresses is what the posture *read for this
        bundle*, which ``tract_reading`` answers, so this holds for a
        feature added to the data tomorrow. It is deliberately not "a
        feature whose values declare coordinates": that asks whether the
        feature could ever be postural, answers for every bundle at once,
        and leaves the layer silent on every bundle whose stated
        coordinate the posture drops.

        The one exception is a feature read for a coordinate it does not
        state, which the reading reports as ``approximated``. A vowel
        that declares no ``constriction-location`` still gets an ``arc``,
        from ``backness`` -- which says where the tongue body is and not
        where it constricts -- and that arc is drawn. Annotating it is
        not repeating the drawing; it is saying which part of the drawing
        is a stand-in. The exemption is taken from the reading rather
        than from a list of features, so it cannot cover a second one by
        accident.
        """
        ipa = IPAFeatures()
        postural = {n for n, f in ipa.features.items() if f.coordinates}
        assert len(postural) >= 5, "no postural features found: the sweep is vacuous"
        ported = {p for ports in ipa.bridge_apertures.values() for p in ports}
        checked, wrong, approximate = 0, [], 0
        for phone in sorted(ipa.phones):
            stated = ipa.get_features(phone, with_defaults=False)
            reading = tract_reading(ipa, stated)
            drawn = reading.read - reading.approximated
            for mark in unmodelled(ipa, stated):
                checked += 1
                approximate += mark.kind == "approximate"
                if mark.feature in drawn or (mark.feature, mark.value) in ported:
                    wrong.append((phone, mark.feature))
                if mark.feature in ipa.secondary_places:
                    wrong.append((phone, mark.feature))
        assert checked > 60, f"only {checked} marks over the inventory"
        assert not wrong, f"annotated what the drawing already shows: {wrong[:5]}"
        assert approximate > 10, "no approximate marks: the exemption is vacuous"

    def test_an_approximated_coordinate_is_annotated_and_a_stated_one_is_not(
        self,
    ) -> None:
        """The two vowel readings, told apart without reading a source.

        This is what a partial declaration has to buy to be worth making.
        Some vowels state where they constrict and the rest do not; the
        arc is a float either way, so nothing in the number says which is
        which. ``ə`` gets an ``approximate`` mark naming ``backness`` and
        ``i`` does not -- ``i`` reports ``backness`` as ``unread``
        instead, because the location took the arc and backness supplied
        nothing.
        """
        ipa = IPAFeatures()
        vowels = [
            p
            for p in sorted(ipa.phones)
            if ipa.get_features(p).get("manner") == "vowel"
        ]
        assert len(vowels) > 20, f"only {len(vowels)} vowels: the sweep is vacuous"
        stated_location, approximated = [], []
        for phone in vowels:
            stated = ipa.get_features(phone, with_defaults=False)
            kinds = {(m.feature, m.kind) for m in unmodelled(ipa, stated)}
            if "constriction-location" in stated:
                stated_location.append(phone)
                assert ("backness", "unread") in kinds, phone
                assert ("backness", "approximate") not in kinds, phone
            else:
                approximated.append(phone)
                assert ("backness", "approximate") in kinds, phone
                assert ("backness", "unread") not in kinds, phone
        assert stated_location and approximated, (stated_location, approximated)
        assert "ə" in approximated and "i" in stated_location

    def test_a_stated_value_the_posture_drops_is_annotated(self) -> None:
        """The other half, and the one that was missing.

        A posture holds one arc and one offset, so a bundle stating both a
        consonantal place and a vowel posture must lose one of them. That
        bundle is what a rule setting ``manner`` over a vowel produces, and
        it reaches the drawing. Whether a stated value is carried is a
        property of the *call*: ``height`` is the offset of a vowel and
        nothing at all beside ``manner="stop"``.

        Swept over every registered phone crossed with every declared
        manner, so this is a property of the branch rather than of two
        hand-built bundles.
        """
        ipa = IPAFeatures()
        manners = ipa.features["manner"].values
        assert len(manners) > 3, "no manner scale: the sweep is vacuous"
        checked, silent = 0, []
        for phone in sorted(ipa.phones):
            base = ipa.get_features(phone, with_defaults=False)
            for manner in manners:
                bundle = {**base, "manner": manner}
                read = tract_reading(ipa, bundle).read
                dropped = {
                    name
                    for name, value in bundle.items()
                    if name in ipa.features
                    and ipa.features[name].coordinates
                    and name not in read
                    and value != ipa.features[name].default
                }
                if not dropped:
                    continue
                checked += 1
                reported = {m.feature for m in unmodelled(ipa, bundle)}
                if not dropped <= reported:
                    silent.append((phone, manner, sorted(dropped - reported)))
        assert checked > 100, f"only {checked} bundles dropped a stated value"
        assert not silent, f"stated, dropped, and not reported: {silent[:5]}"

    def test_the_two_bundles_that_certified_themselves_complete(self) -> None:
        """The guard is shown reporting before it is believed silent.

        Both of these drew a posture, dropped what the bundle stated, and
        answered that nothing was missing: the constructed bundle, and a
        registered vowel with its manner changed -- whose posture has no
        position at all.
        """
        ipa = IPAFeatures()
        built = {
            "manner": "stop",
            "place": "alveolar",
            "height": "open",
            "backness": "front",
        }
        assert tract_point(ipa, built) == tract_point(
            ipa, {"manner": "stop", "place": "alveolar"}
        ), "the posture no longer drops the vowel coordinates"
        assert {(m.feature, m.kind) for m in unmodelled(ipa, built)} == {
            ("height", "unread"),
            ("backness", "unread"),
        }

        composed = {**ipa.get_features("a"), "manner": "stop"}
        assert not tract_point(ipa, composed).placed, "it is the unplaced case"
        assert {"height", "backness"} <= {m.feature for m in unmodelled(ipa, composed)}

        # And the other direction: a vowel manner reads no place.
        vocalic = {**ipa.get_features("t", with_defaults=False), "manner": "vowel"}
        assert ("place", "unread") in {
            (m.feature, m.kind) for m in unmodelled(ipa, vocalic)
        }

    def test_a_value_that_declares_no_position_says_why(self) -> None:
        """``offscale`` is the data's own word for holding no position.

        ``manner="silence"`` declares it, so the posture is unplaced --
        which the point could say, while nothing said why. The kind is off
        the declaration, so a second offscale value added tomorrow is
        annotated without a change here.
        """
        ipa = IPAFeatures()
        offscale = {
            (name, value)
            for name, feat in ipa.features.items()
            for value in feat.offscale
        }
        assert offscale, "nothing declares offscale: the sweep is vacuous"
        for name, value in sorted(offscale):
            marks = unmodelled(ipa, {name: value})
            assert [(m.feature, m.kind) for m in marks] == [(name, "off scale")]
            assert not tract_point(ipa, {name: value}).placed

    def test_every_mark_says_what_the_data_says(self) -> None:
        """The word on a mark is the feature's declared ``label``.

        ``_BINARY_LABELS`` once decided in Python that ``channel=grooved``
        reads "sibilant". It reads that because the data says so, and a
        mark shows the same word a description does.
        """
        ipa = IPAFeatures()
        checked = 0
        for phone in sorted(ipa.phones):
            stated = ipa.get_features(phone, with_defaults=False)
            for mark in unmodelled(ipa, stated):
                checked += 1
                declared = ipa.features[mark.feature].labels.get(mark.value)
                assert mark.label == (declared or f"{mark.feature} {mark.value}")
                assert stated[mark.feature] == mark.value
        assert checked > 60, f"only {checked} marks over the inventory"

    def test_the_reason_is_the_declaration(self) -> None:
        """``kind`` is why the plane cannot hold it, and it is not chosen here.

        ``channel`` declares ``axis="+z"`` and says in its own ``desc`` that
        a mid-sagittal section projects that axis away; ``release`` declares
        ``mode="release"``, a phase and not a posture; ``silence`` declares
        ``offscale``, which is the data saying it holds no position.

        Swept over the inventory and over every manner change on it, since
        ``unread`` is a property of a bundle and no registered phone is
        incoherent enough to have one.
        """
        ipa = IPAFeatures()
        kinds: dict[str, set[tuple[str, str]]] = {}
        for phone in sorted(ipa.phones):
            stated = ipa.get_features(phone, with_defaults=False)
            bundles = [stated] + [
                {**stated, "manner": m} for m in ipa.features["manner"].values
            ]
            for bundle in bundles:
                for mark in unmodelled(ipa, bundle):
                    kinds.setdefault(mark.kind, set()).add((mark.feature, mark.value))
        names = {kind: {n for n, _ in pairs} for kind, pairs in kinds.items()}
        assert names["out of plane"] == {
            n for n, f in ipa.features.items() if f.axis == "+z"
        }
        assert {"airstream", "retroflex"} <= names["unmodelled"]
        assert {"height", "backness", "place"} <= names["unread"]
        for kind, pairs in kinds.items():
            for name, value in pairs:
                feat = ipa.features[name]
                if kind == "out of plane":
                    assert feat.axis == "+z", name
                elif kind == "phase":
                    assert feat.mode == "release", name
                elif kind == "prosodic":
                    assert feat.mode == "prosodic", name
                elif kind == "off scale":
                    assert feat.value_aliases.get(value, value) in feat.offscale, name
                elif kind == "unread":
                    assert feat.coordinates, name

    def test_a_secondary_articulation_is_drawn_where_it_is_declared(self) -> None:
        """It has a place, so it is geometry and not an annotation.

        ``velarized`` carries ``place="velar"``; the mark lands at that
        place's own arc, at approximant degree, because a secondary
        constriction that reached the primary's degree would be one.
        """
        ipa = IPAFeatures()
        place = ipa.features["place"]
        approximant = ipa.features["manner"].coordinates["approximant"]["offset"]
        seen = set()
        for phone in sorted(ipa.phones):
            bundle = ipa.get_features(phone)
            for mark in secondary_marks(ipa, bundle):
                seen.add(mark.feature)
                target = ipa.secondary_places[mark.feature]
                assert mark.arc in [
                    place.coordinates[c]["arc"] for c in place.expand(target)
                ]
                assert mark.offset == approximant
                primary = tract_point(ipa, bundle)
                assert primary.offset is None or mark.offset <= primary.offset
        assert seen, "no phone in the inventory carries a secondary articulation"

    def test_the_glottal_scale_is_found_not_named(self) -> None:
        """Fold aperture rides the axis ``phonation`` declares.

        ``+glottal-aperture`` ascends creaky to devoiced, and ``voiced`` is
        that same axis read two ways instead of four -- which is what the
        ``<projection>`` says, and is how a bundle spelling only ``voiced``
        gets a position at all.
        """
        ipa = IPAFeatures()
        order = ipa.features["phonation"].values
        apertures = [
            glottal_aperture(ipa, {"phonation": value, "manner": "vowel"})
            for value in order
        ]
        assert apertures == sorted(apertures) and apertures == [0.0, 1 / 3, 2 / 3, 1.0]
        # The coarse spelling commits only to the center of what it covers.
        voiced = glottal_aperture(ipa, {"voiced": "+", "manner": "vowel"})
        assert voiced == glottal_aperture(ipa, {"phonation": "modal"})
        assert glottal_aperture(ipa, ipa.get_features("t")) > voiced
        # A complete closure at the folds is theirs, whatever else is said.
        assert glottal_aperture(ipa, ipa.get_features("ʔ")) == 0.0
        assert glottal_aperture(ipa, ipa.get_features("h")) == 1.0
        assert glottal_aperture(ipa, {}) is None

    def test_the_layer_states_what_it_cannot_see(self) -> None:
        """Prosody never reaches a feature bundle, so it cannot be annotated.

        ``length`` and ``stress`` belong to the unit rather than to the bag
        (docs/ties.md), so ``aː`` and ``a`` state the same features and draw
        the same picture. That is why the shipped rule sets' emitted units
        still collapse in pairs. If one of these starts arriving in a
        bundle this fails, and the documented limits need updating.

        Asked as "the marked unit annotates exactly what the bare one
        does" rather than as "it annotates nothing", because the second
        was a claim about ``a`` and not about prosody: ``a`` now states a
        ``constriction-location``, so its ``backness`` is reported
        ``unread`` and an emptiness assertion would fail without prosody
        having reached anything.
        """
        ipa = IPAFeatures()
        prosodic = {n for n, f in ipa.features.items() if f.mode == "prosodic"}
        assert prosodic, "no prosodic features declared"
        bare = ipa.get_features("a", with_defaults=False)
        for unit in ("aː", "ˈa", "aˑ"):
            stated = ipa.get_features(unit, with_defaults=False)
            assert not (set(stated) & prosodic), unit
            assert stated == bare, unit
            assert unmodelled(ipa, stated) == unmodelled(ipa, bare), unit


DATA = Path(ipakit.__file__).resolve().parent / "data" / "ipa.xml"


def _inventory(tmp_path: Path, edit: Any) -> IPAFeatures:
    """The declared inventory with one declaration changed, as a caller's own.

    Perturbed rather than written from scratch: what is being asked is
    whether a drawing follows the data it was made against, and a
    hand-built inventory would answer a different question -- whether the
    renderer copes with a small one.
    """
    tree = ET.parse(DATA)
    edit(tree.getroot())
    path = tmp_path / "ipa.xml"
    tree.write(path, encoding="utf-8")
    return IPAFeatures(path)


def _place_label(svg: str, name: str) -> tuple[float, str]:
    """Where a place is labeled, and the class it carries there."""
    found = re.search(
        r'<text x="([-\d.]+)"[^>]*class="lbl (place[^"]*)"[^>]*>'
        + re.escape(name.replace("-", " "))
        + "</text>",
        svg,
    )
    assert found is not None, f"{name} is not labeled at all"
    return float(found.group(1)), found.group(2)


class TestADrawingFollowsTheInventoryItIsMadeAgainst:
    """A caller's own ``features`` reaches the geometry, and everything on it.

    ``drawing`` takes an inventory, and the caption was already asked of
    that one rather than of the package default, so the two could not
    disagree. The landmarks were not: they were resolved once at import,
    from the package data, and a caller passing their own inventory got a
    posture from theirs and folds, places and articulators from ours --
    silently, since the two agree byte for byte until the data differs.

    Each of these perturbs one declaration and asserts the drawing follows
    it. A fix without them is unguarded, because nothing else in the suite
    and no command line passes ``features`` to ``drawing`` at all.
    """

    def test_the_folds_are_drawn_only_where_a_median_aperture_is_declared(
        self, tmp_path: Path
    ) -> None:
        """Take the median aperture away and the folds go with it.

        ``aperture="median"`` is what says an articulator closes about the
        tract axis rather than toward a wall. An inventory that does not
        say it has no folds to draw, and drew them anyway.
        """
        declared = landmarks(IPAFeatures()).median
        assert declared, "no median articulator declared: the perturbation is vacuous"

        def drop(root: Any) -> None:
            for value in root.iter("value"):
                if value.get("name") in declared:
                    value.attrib.pop("aperture", None)

        custom = _inventory(tmp_path, drop)
        assert not landmarks(custom).median, "the perturbation did not land"
        stated = tract_svg.figure("h", "adult-male")
        perturbed = tract_svg.figure("h", "adult-male", features=custom)
        assert 'class="fold' in stated, "no folds to lose"
        assert 'class="fold' not in perturbed, "the folds ignore the inventory"

    def test_a_place_is_labeled_where_the_inventory_puts_it(
        self, tmp_path: Path
    ) -> None:
        """Move a place along the tract and its label moves with it.

        The arc moved to is halfway across the widest gap the data leaves
        between two places, so the perturbation cannot land on another
        place whatever the inventory declares.
        """
        places = landmarks(IPAFeatures()).places
        assert len(places) > 4, "too few places to move one: the sweep is vacuous"
        ordered = sorted(places.values())
        lo, hi = max(zip(ordered, ordered[1:], strict=False), key=lambda p: p[1] - p[0])
        name = next(n for n, arc in places.items() if arc == lo)
        moved = (lo + hi) / 2

        def shift(root: Any) -> None:
            for value in root.iter("value"):
                if value.get("name") == name and value.get("arc") is not None:
                    value.set("arc", f"{moved:.4f}")

        custom = _inventory(tmp_path, shift)
        assert landmarks(custom).places[name] == pytest.approx(moved)
        was, _ = _place_label(tract_svg.figure(None, "adult-male"), name)
        now, _ = _place_label(
            tract_svg.figure(None, "adult-male", features=custom), name
        )
        assert now != pytest.approx(was), f"{name} is labeled where it no longer is"

    def test_a_place_reads_as_fricative_only_while_one_lives_there(
        self, tmp_path: Path
    ) -> None:
        """The amber places are the ones hosting a fricative in *this* data.

        Restate the manner of every fricative and affricate at one place
        and that place is no longer one of them. The place chosen is the
        one the fewest phones would have to move.
        """
        ipa = IPAFeatures()
        frication = ("fricative", "affricate")
        hosts: dict[str, list[str]] = {}
        for phone in sorted(ipa.phones):
            bundle = ipa.get_features(phone)
            if bundle.get("manner") in frication and bundle.get("place"):
                hosts.setdefault(bundle["place"], []).append(phone)
        assert hosts, "no place hosts a fricative: the perturbation is vacuous"
        place = sorted(hosts, key=lambda p: (len(hosts[p]), p))[0]
        other = next(v for v in ipa.features["manner"].values if v not in frication)

        def restate(root: Any) -> None:
            for phone in root.iter("phone"):
                if phone.get("place") == place and phone.get("manner") in frication:
                    phone.set("manner", other)

        custom = _inventory(tmp_path, restate)
        assert place not in landmarks(custom).frication, "the perturbation did not land"
        _, was = _place_label(tract_svg.figure(None, "adult-male"), place)
        _, now = _place_label(
            tract_svg.figure(None, "adult-male", features=custom), place
        )
        assert "fric" in was, f"{place} hosts a fricative and is not marked as one"
        assert "fric" not in now, f"{place} still reads as fricative with none left"


class TestTheGlottalScaleIsDeclaredAndNotDiscovered:
    """Which feature measures the folds is read off ``axis``, once.

    It used to be inferred: the first ordinal feature a ``<projection>``
    refined, in alphabetical order. That is right while one projection is
    declared and a coin toss at two, and the second projection would have
    won silently -- no exception, no warning, and every figure redrawn.

    So the tests here are perturbations of the declaration rather than
    assertions about ``phonation``, which would pass equally against the
    hardcoding they exist to rule out.
    """

    def _feature_element(self, root: Any, name: str) -> Any:
        return next(f for f in root.iter("feature") if f.get("name") == name)

    def test_a_second_projection_does_not_move_the_folds(self, tmp_path: Path) -> None:
        """Declare another projection and the glottal state stays put.

        Swept over every ordinal feature that sorts before the declared
        scale, because alphabetical order is what the discovery turned on
        and a single named feature would test one draw of the coin. The
        projections are about the mechanism, not phonetic claims: each
        maps every value of its feature onto one coarse value, which is
        all the loader's totality rule asks for.
        """
        ipa = IPAFeatures()
        scale = glottal_scale(ipa)
        assert scale is not None, "no glottal scale declared: the sweep is vacuous"
        sources = {fine for fine, _ in ipa.projections}
        assert sources, "no projection declared: the sweep is vacuous"
        candidates = sorted(
            name
            for name, feat in ipa.features.items()
            if feat.is_ordinal
            and len(feat.values) > 1
            and name not in sources
            and name < min(sources)
        )
        assert candidates, "nothing sorts before a source: the sweep is vacuous"
        annotated = {
            mark.feature
            for phone in ipa.phones
            for mark in unmodelled(ipa, ipa.get_features(phone, with_defaults=False))
        }
        assert set(candidates) & annotated, "no candidate reaches the annotations"

        was = {
            p: glottal_aperture(ipa, ipa.get_features(p)) for p in sorted(ipa.phones)
        }
        assert len({v for v in was.values() if v is not None}) > 1, "one aperture only"

        for fine in candidates:

            def project(root: Any, fine: str = fine) -> None:
                block = root.find("projections")
                added = ET.SubElement(
                    block, "projection", {"from": fine, "to": "voiced"}
                )
                for value in ipa.features[fine].values:
                    ET.SubElement(added, "value", {"name": value, "reads": "+"})

            room = tmp_path / fine
            room.mkdir()
            custom = _inventory(room, project)
            assert fine in {f for f, _ in custom.projections}, "it did not land"
            assert glottal_scale(custom) is not None
            now = {
                p: glottal_aperture(custom, custom.get_features(p))
                for p in sorted(custom.phones)
            }
            moved = [p for p in was if was[p] != now[p]]
            assert not moved, f"{fine} took the glottal scale over: {moved[:5]}"
            # The same declaration decides what the annotation layer treats
            # as already drawn, so a projection must not silence a mark.
            for phone in sorted(ipa.phones):
                stated = ipa.get_features(phone, with_defaults=False)
                assert [m.feature for m in unmodelled(ipa, stated)] == [
                    m.feature for m in unmodelled(custom, stated)
                ], f"{fine} silenced a mark on {phone}"

    def test_the_scale_is_whichever_feature_declares_the_axis(
        self, tmp_path: Path
    ) -> None:
        """Move the axis to another feature and the folds move with it.

        The name ``phonation`` is nowhere in the read, so an inventory
        that measures glottal state with some other feature is drawn from
        that one -- and the feature that used to carry the axis stops
        placing the folds, because it no longer says it measures them.
        """
        ipa = IPAFeatures()
        scale = glottal_scale(ipa)
        assert scale is not None
        target = next(
            name
            for name, feat in sorted(ipa.features.items())
            if feat.is_ordinal and len(feat.values) > 2 and name != scale.name
        )

        def move(root: Any) -> None:
            self._feature_element(root, scale.name).attrib.pop("axis")
            self._feature_element(root, target).set("axis", GLOTTAL_AXIS)

        custom = _inventory(tmp_path, move)
        moved = glottal_scale(custom)
        assert moved is not None and moved.name == target
        order = list(ipa.features[target].values)
        assert [glottal_aperture(custom, {target: value}) for value in order] == [
            i / (len(order) - 1) for i in range(len(order))
        ]
        # The old scale is now a feature like any other: it says nothing
        # about the folds, and nothing about it is remembered here.
        assert glottal_aperture(custom, {scale.name: scale.values[0]}) is None

    def test_two_features_on_the_axis_are_refused(self, tmp_path: Path) -> None:
        """The folds have one aperture, so one feature may measure it.

        Two is the case the discovery answered by sorting names. There is
        no right answer to pick, so the read says which two features are
        in dispute and stops.
        """
        ipa = IPAFeatures()
        scale = glottal_scale(ipa)
        assert scale is not None
        other = next(
            name
            for name, feat in sorted(ipa.features.items())
            if feat.is_ordinal and len(feat.values) > 1 and name != scale.name
        )

        def duplicate(root: Any) -> None:
            self._feature_element(root, other).set("axis", GLOTTAL_AXIS)

        custom = _inventory(tmp_path, duplicate)
        with pytest.raises(ValueError, match=re.escape(GLOTTAL_AXIS)) as raised:
            glottal_aperture(custom, custom.get_features("a"))
        assert scale.name in str(raised.value) and other in str(raised.value)

    def test_an_inventory_declaring_no_axis_draws_no_glottal_state(
        self, tmp_path: Path
    ) -> None:
        """Nothing declares it, so there is nothing to read and none is invented.

        The folds keep their place -- ``aperture="median"`` is what puts
        them in the drawing -- and lose their state. If an inventory
        without the axis starts drawing folds again this fails, and what
        the absence means needs writing down afresh.
        """
        ipa = IPAFeatures()
        scale = glottal_scale(ipa)
        assert scale is not None

        def drop(root: Any) -> None:
            self._feature_element(root, scale.name).attrib.pop("axis")

        custom = _inventory(tmp_path, drop)
        assert glottal_scale(custom) is None
        assert all(
            glottal_aperture(custom, custom.get_features(p)) is None
            for p in custom.phones
        )
        stated = tract_svg.figure("h", "adult-male")
        perturbed = tract_svg.figure("h", "adult-male", features=custom)
        assert 'class="fold' in stated, "no folds to lose"
        assert 'class="fold' not in perturbed, "folds drawn off an undeclared scale"
        assert "medianmark" in perturbed, "the folds lost their place, not their state"


class TestTheDrawingSeparatesWhatTheFeaturesSeparate:
    """What the annotation layer buys, measured rather than asserted.

    Voicing, laterality, secondary articulation, release and airstream are
    each a contrast a bare posture cannot carry, so each is a pair of
    phones the figure would otherwise draw the same way.

    The claim is one predicate, over the inventory and over the units the
    shipped rule sets emit: **the drawing separates exactly what the
    feature bundle separates**. A count of emitted units is a function of
    how many words the rule-set corpora hold, so it belongs in an
    assertion that derives it, not in a number anybody has to maintain.
    """

    def test_a_stated_contrast_the_layer_covers_reaches_the_drawing(self) -> None:
        """Two phones differing only in an annotated feature draw differently.

        Swept over the whole inventory rather than over named pairs: the
        pairs anyone thinks of are the ones already fixed.
        """
        ipa = IPAFeatures()
        by_posture: dict[tuple[Any, ...], list[str]] = {}
        for phone in sorted(ipa.phones):
            bundle = ipa.get_features(phone)
            point = tract_point(ipa, bundle)
            key = (point.arc, point.offset, velic_aperture(ipa, bundle))
            by_posture.setdefault(key, []).append(phone)
        covered = {"voiced", "phonation", "channel", "release", "airstream"}
        covered |= set(ipa.secondary_places)
        checked, same = 0, []
        for group in by_posture.values():
            for i, one in enumerate(group):
                for other in group[i + 1 :]:
                    a, b = ipa.get_features(one), ipa.get_features(other)
                    differ = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
                    differ -= set(METADATA_ATTRS)
                    # Two units may share a bundle outright -- a diphthong
                    # reads its first element's features -- and then there
                    # is no featural contrast for a drawing to carry.
                    if not differ or not differ <= covered:
                        continue
                    checked += 1
                    if _section("adult-male", one) == _section("adult-male", other):
                        same.append((one, other))
        assert checked > 40, f"only {checked} pairs contrast on an annotated feature"
        assert not same, f"{len(same)} pairs still share a drawing: {same[:6]}"

    def test_what_still_collapses_is_a_trajectory_or_a_prosody(self) -> None:
        """The remainder, named rather than left as a round number.

        A diphthong is a movement between two postures and the figure draws
        one; length and stress are not in a bundle at all. Roundedness is now
        carried by the posture but deliberately projected away by this view.
        """
        ipa = IPAFeatures()
        groups: dict[str, list[str]] = {}
        for phone in sorted(ipa.phones):
            groups.setdefault(_section("adult-male", phone), []).append(phone)
        collapsed = [g for g in groups.values() if len(g) > 1]
        assert len(groups) == 123, (
            f"{len(groups)} distinct figures for {len(ipa.phones)} phones; "
            f"{len(collapsed)} groups share one"
        )
        ties = ipa.tie_bars
        for group in collapsed:
            tied = any(any(tie in unit for tie in ties) for unit in group)
            without_rounding = {
                tuple(
                    sorted(
                        (k, v)
                        for k, v in ipa.get_features(unit).items()
                        if k not in METADATA_ATTRS and k != "rounded"
                    )
                )
                for unit in group
            }
            assert (
                tied or len(without_rounding) == 1
            ), f"{group} share a drawing but differ beyond roundedness"

    def test_what_the_rule_sets_emit_draws_one_picture_per_bundle(self) -> None:
        """The emitted-units claim ``docs/tract-figures.md`` makes.

        An integer here is a snapshot of corpus size, so what is asserted
        is the identity an integer would only sample --

            distinct pictures == distinct feature bundles

        -- which holds at any corpus size. Every collapse is then a
        contrast the bundle does not state (a length or stress mark, or a
        diphthong reading its first element), and every contrast the
        bundle *does* state reaches the drawing. Adding a corpus word
        moves both counts together or fails here.

        The corpus is imported from ``tests/test_rule_sets.py`` rather than
        restated, for the reason ``tests/corpus.py`` gives: a second copy
        of an enumeration is a second definition waiting to drift.
        """
        from tests.test_rule_sets import ALL_SETS, CORPUS

        ipa = IPAFeatures()
        units: set[str] = set()
        for name in ALL_SETS:
            ruleset = ipakit.ruleset(name)
            for word in CORPUS[name]:
                units |= {u.to_ipa() for u in ipa.segments(ruleset.apply(word))}

        def bundle(unit: str) -> tuple[tuple[str, str], ...]:
            stated = ipa.get_features(unit)
            return tuple(
                sorted(
                    (k, v)
                    for k, v in stated.items()
                    if k not in METADATA_ATTRS and k != "rounded"
                )
            )

        pictures: dict[str, list[str]] = {}
        for unit in sorted(units):
            pictures.setdefault(_section("adult-male", unit), []).append(unit)
        bundles = {bundle(unit) for unit in units}
        # A floor, not a total: it fails when the sweep collapses, not when
        # a corpus word is added. Both sets get one, since a run that drew
        # one picture for everything would still clear a floor on units.
        assert len(units) > 60, f"only {len(units)} emitted units swept"
        assert len(pictures) > 40, f"only {len(pictures)} pictures drawn"
        assert len(pictures) == len(bundles), (
            f"{len(units)} emitted units state {len(bundles)} bundles but draw "
            f"{len(pictures)} pictures"
        )
        # The same identity said the other way round, which is what makes
        # the counts meaningful: a collapse is units that state the same
        # features, never two different bundles sharing one picture.
        for group in pictures.values():
            stated = {bundle(unit) for unit in group}
            assert len(stated) == 1, f"{group} share a drawing, stating {stated}"


ROOT = Path(__file__).resolve().parent.parent
FIGURES = ROOT / "docs" / "figures"

#: Each new layer, with a unit that carries it. A mark that does not paint,
#: or that something later paints over, is the failure mode these exist for:
#: reading the DOM said "present, styled, in frame, painted late" four times
#: while the thing was invisible.
#:
#: ``approximate`` is its own entry rather than being covered by ``chip``,
#: because it is the one chip drawn as something other than the default
#: square and a shape that falls back to the square would pass the generic
#: test while saying the opposite of what it means.
LAYERS = {"fold": "ʔ", "second": "ɫ", "chip": "s", "approximate": "ə"}


def _pixels(svg: str, path: Path, width: int = 1520) -> tuple[int, list[bytes]]:
    """Rasterize and decode, so a claim about a mark is about pixels.

    A minimal PNG read -- 8-bit RGBA, the five filters -- because the point
    is to look at what a renderer outside a browser actually produced.
    """
    path.write_text(svg, encoding="utf-8")
    png = subprocess.run(
        ["rsvg-convert", "-w", str(width), str(path)],
        check=True,
        capture_output=True,
    ).stdout
    at, w, h, depth, color, idat = 8, 0, 0, 0, 0, b""
    while at < len(png):
        (length,) = struct.unpack(">I", png[at : at + 4])
        kind, data = png[at + 4 : at + 8], png[at + 8 : at + 8 + length]
        if kind == b"IHDR":
            w, h, depth, color = struct.unpack(">IIBB", data[:10])
        elif kind == b"IDAT":
            idat += data
        at += 12 + length
    assert depth == 8 and color == 6, f"unexpected PNG: {depth}-bit type {color}"
    raw, stride, rows, prior = zlib.decompress(idat), w * 4, [], bytearray(w * 4)
    at = 0
    for _ in range(h):
        filt, line = raw[at], bytearray(raw[at + 1 : at + 1 + stride])
        at += 1 + stride
        for x in range(stride):
            a = line[x - 4] if x >= 4 else 0
            b = prior[x]
            c = prior[x - 4] if x >= 4 else 0
            if filt == 1:
                line[x] = (line[x] + a) & 255
            elif filt == 2:
                line[x] = (line[x] + b) & 255
            elif filt == 3:
                line[x] = (line[x] + (a + b) // 2) & 255
            elif filt == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                near = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + near) & 255
        rows.append(bytes(line))
        prior = line
    return w, rows


def _alpha_pixels(
    width: int, rows: list[bytes], threshold: int = 0
) -> set[tuple[int, int]]:
    return {
        (x, y)
        for y, row in enumerate(rows)
        for x in range(width)
        if row[x * 4 + 3] > threshold
    }


def _pixel_hausdorff(one: set[tuple[int, int]], other: set[tuple[int, int]]) -> float:
    def directed(source: set[tuple[int, int]], target: set[tuple[int, int]]) -> float:
        return max(
            min(math.dist(point, candidate) for candidate in target) for point in source
        )

    return max(directed(one, other), directed(other, one))


VELIC_PIN_PATH = Path(__file__).resolve().parent / "fixtures" / "velic_contrast.json"
REFERENCE_LANDMARK_PIN_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "reference_landmark_distances.json"
)


def _label_anchor(svg: str, label: str, label_class: str) -> tuple[float, float]:
    """Return the start of the leader attached to a named rendered label."""
    root = ET.fromstring(svg)
    children = list(root)
    for index, child in enumerate(children):
        if child.tag.rsplit("}", 1)[-1] != "text":
            continue
        if label_class not in child.attrib.get("class", "").split():
            continue
        if label not in " ".join("".join(child.itertext()).split()):
            continue
        x = float(child.attrib["x"])
        for prior in reversed(children[:index]):
            if prior.tag.rsplit("}", 1)[-1] != "line":
                continue
            if "lead" in prior.attrib.get("class", "").split() and float(
                prior.attrib["x2"]
            ) == pytest.approx(x):
                return float(prior.attrib["x1"]), float(prior.attrib["y1"])
    raise AssertionError(f"no leader for {label_class} label {label!r}")


def _distance_from_anchor_to_pixels(
    anchor: tuple[float, float],
    svg: str,
    layer: str,
    path: Path,
) -> float:
    """Measure an SVG-space anchor against a separately rasterized layer."""
    viewbox = tuple(
        float(value)
        for value in re.search(r'viewBox="([^"]+)"', svg).group(1).split()  # type: ignore[union-attr]
    )
    width, rows = _pixels(_only_layer(svg, layer), path)
    height = len(rows)
    point = (
        (anchor[0] - viewbox[0]) * width / viewbox[2],
        (anchor[1] - viewbox[1]) * height / viewbox[3],
    )
    painted = _alpha_pixels(width, rows)
    assert painted, f"{layer} painted no pixels"
    return min(math.dist(point, candidate) for candidate in painted)


@pytest.mark.skipif(shutil.which("rsvg-convert") is None, reason="rsvg-convert absent")
def test_moved_reference_landmarks_stay_on_their_anatomy(tmp_path: Path) -> None:
    """Moved sagittal contours retain their labels in every shipped head.

    The leader start is the label's anatomical anchor.  Velum and epiglottis
    anchors touch their filled bodies; the nares anchor sits midway in the
    deliberately open nostril and is measured to its nearest painted rim.
    Its separate upper-lip distance proves it remains in that opening rather
    than following the nose into the overlap region cleared from the lip.
    """
    pins = json.loads(REFERENCE_LANDMARK_PIN_PATH.read_text(encoding="utf-8"))
    measured = {}
    labels = {
        "velum": ("velum", "velum"),
        "epiglottis": ("art", "epiglottis"),
        "nares": ("nasal", "nasalside"),
    }
    for head_name in sorted(heads()):
        svg = tract_svg.figure(None, head_name)
        distances = {}
        for label, (label_class, anatomy_layer) in labels.items():
            anchor = _label_anchor(svg, label, label_class)
            distances[label] = round(
                _distance_from_anchor_to_pixels(
                    anchor, svg, anatomy_layer, tmp_path / f"{head_name}-{label}.svg"
                ),
                2,
            )
            if label == "nares":
                distances["nares-to-upper-lip"] = round(
                    _distance_from_anchor_to_pixels(
                        anchor,
                        svg,
                        "upper-lip",
                        tmp_path / f"{head_name}-nares-upper-lip.svg",
                    ),
                    2,
                )
        measured[head_name] = distances
    assert measured == pins
    assert all(
        values["nares"] < values["nares-to-upper-lip"] for values in measured.values()
    ), measured


@pytest.mark.skipif(shutil.which("rsvg-convert") is None, reason="rsvg-convert absent")
def test_velic_contrast_matches_generated_pixel_pins(tmp_path: Path) -> None:
    """Every place keeps the same wall gap, measured in rendered pixels."""
    pins = json.loads(VELIC_PIN_PATH.read_text(encoding="utf-8"))
    measured = {}
    for nasal, oral in (("m", "b"), ("n", "d"), ("ŋ", "k")):
        width, nasal_rows = _pixels(
            _only_layer(tract_svg.figure(nasal), "velum"), tmp_path / f"{nasal}.svg"
        )
        _, oral_rows = _pixels(
            _only_layer(tract_svg.figure(oral), "velum"), tmp_path / f"{oral}.svg"
        )
        measured[f"{nasal}-{oral}"] = round(
            _pixel_hausdorff(
                _alpha_pixels(width, nasal_rows), _alpha_pixels(width, oral_rows)
            ),
            2,
        )
    assert measured == pins
    assert len(set(measured.values())) == 1, measured


def test_lowered_velum_is_the_dorsums_declared_boundary() -> None:
    """A velar closure and the lowered flap meet without an endpoint clamp."""
    ipa, shape = IPAFeatures(), head()
    p = posture(ipa, "ŋ", shape)
    velum = shape.velum(1.0)
    assert velum is not None and shape.velum_lowered_arc is not None
    dorsum = shape.tongue_point(shape.velum_lowered_arc, p.constrictions)
    assert dorsum is not None
    assert dorsum == pytest.approx(velum.tip)


def test_moving_a_heads_velar_anchor_moves_both_contact_sides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A head's anatomy owns its flap, closure, and dorsal landmark."""
    original_anatomy_file = anatomy.ANATOMY_FILE
    old_ipa = IPAFeatures()
    route_bytes = {
        name: {
            "drawing": tract_svg.render(tract_svg.drawing(name, None, old_ipa)),
            "figure": tract_svg.figure(None, name, old_ipa),
            "animate": tract_svg.animate("aŋ", name, old_ipa, frames_per_unit=2),
            "animate_two_pane": tract_svg.animate_two_pane(
                "aŋ", name, old_ipa, frames_per_unit=2
            ),
            "frontal_figure": tract_svg.frontal_figure("ŋ", name, old_ipa),
        }
        for name in heads()
    }
    old = {
        name: (
            shape.velum_lowered_arc,
            posture(old_ipa, "ŋ", shape).constrictions[-1].arc,
            tract_svg.drawing(name, None, old_ipa)["geometry"][
                "landmarks"
            ].articulators["tongue-dorsum"],
        )
        for name, shape in heads().items()
    }
    old_arc = old["child"][0]

    tree = ET.parse(anatomy.ANATOMY_FILE)
    landmark = tree.getroot().find("landmarks/landmark[@name='velum-rest']")
    assert landmark is not None and old_arc is not None
    ET.SubElement(landmark, "head", name="child", arc=str(old_arc + 0.01))
    moved_path = tmp_path / "tract-anatomy.xml"
    tree.write(moved_path, encoding="utf-8", xml_declaration=True)
    monkeypatch.setattr(anatomy, "ANATOMY_FILE", moved_path)

    tract_module._load_heads.cache_clear()
    moved_ipa = IPAFeatures()
    moved_heads = heads()
    moved = moved_heads["child"]
    moved_pose = posture(moved_ipa, "ŋ", moved)
    moved_implied = next(
        point
        for point in posture(moved_ipa, "a", moved).implied
        if point.articulator == "tongue-dorsum"
    )
    moved_dorsum = tract_svg.drawing("child", None, moved_ipa)["geometry"][
        "landmarks"
    ].articulators["tongue-dorsum"]
    assert (
        moved.velum_lowered_arc,
        moved_pose.constrictions[-1].arc,
        moved_dorsum,
    ) == (
        pytest.approx(old_arc + 0.01),
        pytest.approx(old_arc + 0.01),
        pytest.approx(old_arc + 0.01),
    )
    assert moved_implied.arc == pytest.approx(old_arc + 0.01)
    assert moved_implied.offset == pytest.approx(0.1983610701)
    for name in ("adult-male", "adult-female"):
        shape = moved_heads[name]
        assert (
            shape.velum_lowered_arc,
            posture(moved_ipa, "ŋ", shape).constrictions[-1].arc,
            tract_svg.drawing(name, None, moved_ipa)["geometry"][
                "landmarks"
            ].articulators["tongue-dorsum"],
        ) == old[name]
    velum = moved.velum(1.0)
    dorsum = moved.tongue_point(moved.velum_lowered_arc, moved_pose.constrictions)
    assert velum is not None and dorsum == pytest.approx(velum.tip)

    # Hold the moved Head constant and remove only its landmark override. This
    # isolates each route's landmark resolution from the child's other geometry.
    with monkeypatch.context() as canonical_landmarks:
        canonical_landmarks.setattr(anatomy, "ANATOMY_FILE", original_anatomy_file)
        child_without_override = {
            "drawing": tract_svg.render(tract_svg.drawing("child", None, moved_ipa)),
            "figure": tract_svg.figure(None, "child", moved_ipa),
            "animate": tract_svg.animate("aŋ", "child", moved_ipa, frames_per_unit=2),
            "animate_two_pane": tract_svg.animate_two_pane(
                "aŋ", "child", moved_ipa, frames_per_unit=2
            ),
            "frontal_figure": tract_svg.frontal_figure("ŋ", "child", moved_ipa),
        }

    resolved_for: list[str | None] = []
    real_landmarks = tract_svg.landmarks

    def recording_landmarks(
        features: IPAFeatures, head_name: str | None = None
    ) -> tract_module.Landmarks:
        resolved_for.append(head_name)
        return real_landmarks(features, head_name)

    monkeypatch.setattr(tract_svg, "landmarks", recording_landmarks)
    moved_route_bytes = {
        name: {
            "drawing": tract_svg.render(tract_svg.drawing(name, None, moved_ipa)),
            "figure": tract_svg.figure(None, name, moved_ipa),
            "animate": tract_svg.animate("aŋ", name, moved_ipa, frames_per_unit=2),
            "animate_two_pane": tract_svg.animate_two_pane(
                "aŋ", name, moved_ipa, frames_per_unit=2
            ),
            "frontal_figure": tract_svg.frontal_figure("ŋ", name, moved_ipa),
        }
        for name in moved_heads
    }
    assert resolved_for == [name for name in moved_heads for _ in range(5)]
    changed = {
        route
        for route in child_without_override
        if moved_route_bytes["child"][route] != child_without_override[route]
    }
    assert changed == set(child_without_override)
    for name in ("adult-male", "adult-female"):
        assert moved_route_bytes[name] == route_bytes[name]
    tract_module._load_heads.cache_clear()


@pytest.mark.skipif(shutil.which("rsvg-convert") is None, reason="rsvg-convert absent")
@pytest.mark.parametrize("head_name", sorted(heads()))
@pytest.mark.parametrize("phone", ["ŋ", "k", "ɡ", "k͡p", "ǃ"])
def test_velum_and_dorsum_filled_interiors_do_not_overlap(
    tmp_path: Path, head_name: str, phone: str
) -> None:
    """Lowered and sealed contacts are boundaries, never penetration."""
    svg = tract_svg.figure(phone, head_name=head_name)
    stem = f"{head_name}-{ord(phone[0])}"
    width, velum_rows = _pixels(
        _only_layer(svg, "velum", fill_only=True), tmp_path / f"{stem}-velum.svg"
    )
    _, tongue_rows = _pixels(
        _only_layer(svg, "tonguebody", fill_only=True), tmp_path / f"{stem}-tongue.svg"
    )
    overlap = _alpha_pixels(width, velum_rows, 127) & _alpha_pixels(
        width, tongue_rows, 20
    )
    assert not overlap, (head_name, phone, len(overlap))

    tongue = ET.fromstring(_only_layer(svg, "tonguebody", fill_only=True))
    tonguebody = next(
        node
        for node in tongue.iter()
        if "tonguebody" in node.attrib.get("class", "").split()
    )
    tonguebody.set("transform", "translate(0,-0.2)")
    _, translated_rows = _pixels(
        ET.tostring(tongue, encoding="unicode"), tmp_path / f"{stem}-translated.svg"
    )
    translated_overlap = _alpha_pixels(width, velum_rows, 127) & _alpha_pixels(
        width, translated_rows, 20
    )
    assert translated_overlap, (head_name, phone)


def test_nasal_floor_truncation_still_varies_every_pair() -> None:
    """The independent 0.18 * aperture nasal-branch cue remains intact."""
    for nasal, oral in (("m", "b"), ("n", "d"), ("ŋ", "k")):
        nasal_svg, oral_svg = tract_svg.figure(nasal), tract_svg.figure(oral)
        pattern = r'<path d="([^"]+)" class="nasalside"/>'
        nasal_sides = re.findall(pattern, nasal_svg)
        oral_sides = re.findall(pattern, oral_svg)
        assert len(nasal_sides) == len(oral_sides) == 2
        assert nasal_sides[1] != oral_sides[1]


@pytest.mark.parametrize("head_name", sorted(heads()))
def test_upper_lip_never_enters_nose_over_inventory(
    head_name: str, tmp_path: Path
) -> None:
    """Filled nose and upper-lip interiors stay disjoint in every posture.

    The nasal cavity is skull-fixed, so rasterize it once per head.  The lip
    is posed for every registered phone; that sweep includes the open jaw of
    vowels such as /a/ as well as closed and non-labial consonants.
    """
    if shutil.which("rsvg-convert") is None:  # pragma: no cover
        pytest.skip("rsvg-convert not installed: the raster claim is unmeasured here")
    drawings = [
        tract_svg.drawing(head_name, phone) for phone in (None, *IPAFeatures().phones)
    ]
    extent = tract_svg._extent(*(drawn["geometry"] for drawn in drawings))

    def fixed_svg(drawn: dict[str, Any]) -> str:
        svg = tract_svg.section_svg(
            drawn["geometry"],
            None,
            drawn["aperture"],
            drawn["posture"],
            drawn["caption"],
            drawn["active"],
            extent=extent,
        )
        return svg.replace(
            "<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1
        ).replace(">", f"><style>{tract_svg._literal_style()}</style>", 1)

    reference = fixed_svg(drawings[0])
    width, nose_rows = _pixels(
        _only_layer(reference, "nasalfill", fill_only=True),
        tmp_path / f"{head_name}-nose.svg",
    )
    nose = _alpha_pixels(width, nose_rows)
    collisions = []
    for phone, drawn in zip(IPAFeatures().phones, drawings[1:], strict=True):
        svg = fixed_svg(drawn)
        _, lip_rows = _pixels(
            _only_layer(svg, "upper-lip", fill_only=True),
            tmp_path / f"{head_name}-{ord(phone[0])}-upper-lip.svg",
        )
        overlap = nose & _alpha_pixels(width, lip_rows)
        if overlap:
            collisions.append((phone, len(overlap)))
    assert not collisions, (head_name, collisions[:10])


@pytest.mark.parametrize("head_name", sorted(heads()))
def test_external_nose_tip_projects_past_upper_lip(head_name: str) -> None:
    """The pronasale is anterior to the upper lip, not flattened behind it."""
    svg = tract_svg.render(tract_svg.drawing(head_name, None))
    nose = re.search(r'<path d="([^"]+)" class="nasalfill"/>', svg)
    lip = re.search(r'<path d="([^"]+)" class="lip upper-lip"/>', svg)
    assert nose is not None and lip is not None
    nose_front = min(x for x, _ in _pts(nose.group(1)))
    lip_front = min(x for x, _ in _pts(lip.group(1)))
    assert nose_front < lip_front, (head_name, nose_front, lip_front)


@pytest.mark.parametrize("head_name", sorted(heads()))
def test_nares_are_an_open_down_forward_end(head_name: str) -> None:
    """The nasal side walls end apart; no stroked cap seals the naris."""
    svg = _section(head_name, "m")
    sides = re.findall(r'<path d="([^"]+)" class="nasalside"/>', svg)
    assert len(sides) == 2
    upper, lower = (_pts(side) for side in sides)
    assert upper[0] != lower[0]
    assert not any(side.rstrip().endswith("Z") for side in sides)
    # In display coordinates the lower rim remains down and behind the upper
    # rim, leaving the gap's outward normal down-forward (left).
    assert lower[0][0] > upper[0][0]
    assert lower[0][1] > upper[0][1]


def _differing(
    width: int, one: list[bytes], other: list[bytes]
) -> list[tuple[int, int]]:
    return [
        (x, y)
        for y, (a, b) in enumerate(zip(one, other, strict=True))
        if a != b
        for x in range(width)
        if a[x * 4 : x * 4 + 4] != b[x * 4 : x * 4 + 4]
    ]


def _only_layer(
    svg: str, layer: str, *, fill_only: bool = False, unmask: bool = False
) -> str:
    """Keep one painted SVG layer and any definitions it depends on."""
    root = ET.fromstring(svg)
    painted = {"path", "line", "circle", "rect", "text"}
    for parent in root.iter():
        if parent.tag.rsplit("}", 1)[-1] in {"defs", "mask"}:
            continue
        for child in list(parent):
            tag = child.tag.rsplit("}", 1)[-1]
            classes = child.attrib.get("class", "").split()
            if tag in painted and (layer not in classes or tag != "path"):
                parent.remove(child)
    if unmask:
        for child in root.iter():
            if layer in child.attrib.get("class", "").split():
                child.attrib.pop("mask", None)
    if fill_only:
        style = next(
            (node for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "style"),
            None,
        )
        if style is not None and style.text:
            style.text += f".{layer}{{stroke:none}}"
    return ET.tostring(root, encoding="unicode")


@pytest.mark.parametrize(("nasal", "oral"), [("m", "b"), ("n", "d")])
def test_nasality_changes_painted_velum_pixels(
    nasal: str, oral: str, tmp_path: Path
) -> None:
    if shutil.which("rsvg-convert") is None:  # pragma: no cover
        pytest.skip("rsvg-convert not installed: the raster claim is unmeasured here")
    width, nasal_rows = _pixels(
        _only_layer(tract_svg.figure(nasal), "velum"), tmp_path / f"{nasal}.svg"
    )
    _, oral_rows = _pixels(
        _only_layer(tract_svg.figure(oral), "velum"), tmp_path / f"{oral}.svg"
    )
    assert _differing(width, nasal_rows, oral_rows)


def test_drawn_velum_moves_monotonically_with_velic() -> None:
    ipa, h, marks = IPAFeatures(), head(), landmarks(IPAFeatures())
    base = posture(ipa, "m", h)
    tips = []
    for aperture in (0.0, 0.25, 0.5, 0.75, 1.0):
        geometry = tract_svg.build_geometry(h, marks, replace(base, velic=aperture))
        svg = tract_svg.section_svg(geometry, None, aperture, tract_svg._pose(base))
        path = re.search(r'<path d="([^"]+)" class="velum"', svg)
        assert path is not None
        points = _pts(path.group(1))
        # Head.velum supplies oral points followed by the reversed nasal
        # surface, so the free edge is the last point of the first half.
        tips.append(points[len(points) // 2 - 1])
    sealed = tips[0]
    distances = [math.hypot(x - sealed[0], y - sealed[1]) for x, y in tips]
    assert distances == sorted(distances)
    assert distances[-1] > 20
    assert all(
        math.isclose(distance, distances[-1] * aperture, abs_tol=0.2)
        for distance, aperture in zip(
            distances, (0.0, 0.25, 0.5, 0.75, 1.0), strict=True
        )
    )


@pytest.mark.parametrize(
    ("aperture", "state"), [(0.0, "sealed"), (0.5, "part-open"), (1.0, "open")]
)
def test_velum_annotation_tracks_model(aperture: float, state: str) -> None:
    ipa, h = IPAFeatures(), head()
    base = posture(ipa, "m", h)
    geometry = tract_svg.build_geometry(
        h, landmarks(ipa), replace(base, velic=aperture)
    )
    svg = tract_svg.section_svg(geometry, None, aperture, tract_svg._pose(base))
    assert f"port {state}" in svg


def test_velum_and_tongue_never_interpenetrate(tmp_path: Path) -> None:
    """Filled interiors never penetrate under geometric contact.

    This deliberately excludes strokes and low-alpha antialiasing: contact is
    established by geometry now, so the independently painted boundary
    strokes legitimately share pixels. Thresholds 127 for the velum and 20
    for the tongue retain the interior-overlap guard without calling rendered
    contact itself penetration.
    """
    if shutil.which("rsvg-convert") is None:  # pragma: no cover
        pytest.skip("rsvg-convert not installed: the raster claim is unmeasured here")
    ipa = IPAFeatures()
    checked: dict[tuple[str, str], str] = {}
    for phone in sorted(ipa.phones):
        svg = tract_svg.figure(phone)
        velum = re.search(r'<path d="([^"]+)" class="velum"', svg)
        tongue = re.search(r'<path d="([^"]+)" class="tonguebody"', svg)
        if velum is not None and tongue is not None:
            checked.setdefault((velum.group(1), tongue.group(1)), phone)
    collisions = []
    for index, (_paths, phone) in enumerate(checked.items()):
        svg = tract_svg.figure(phone)
        width, velum_rows = _pixels(
            _only_layer(svg, "velum", fill_only=True),
            tmp_path / f"velum-{index}.svg",
            width=760,
        )
        _, tongue_rows = _pixels(
            _only_layer(svg, "tonguebody", fill_only=True),
            tmp_path / f"tongue-{index}.svg",
            width=760,
        )
        velum_pixels = _alpha_pixels(width, velum_rows, 127)
        tongue_pixels = _alpha_pixels(width, tongue_rows, 20)
        overlap = len(velum_pixels & tongue_pixels)
        if overlap:
            collisions.append((phone, overlap))
    assert len(checked) > 50, f"only {len(checked)} distinct postures checked"
    assert not collisions, f"velum intersects tongue: {collisions[:6]}"


VELUM_SURVIVAL = 0.90


def test_every_velum_survives_contact_with_the_tongue(tmp_path: Path) -> None:
    """Geometric contact must not erase the roof that the tongue meets.

    The model-owned velum leaves 100% of its area painted. Ninety percent
    leaves ten points of rasterizer headroom for contact antialiasing.
    """
    if shutil.which("rsvg-convert") is None:  # pragma: no cover
        pytest.skip("rsvg-convert not installed: the raster claim is unmeasured here")
    ipa = IPAFeatures()
    failures = []
    for index, phone in enumerate(sorted(ipa.phones)):
        svg = tract_svg.figure(phone)
        if 'class="velum"' not in svg:
            continue
        _, painted_rows = _pixels(
            _only_layer(svg, "velum"),
            tmp_path / f"velum-painted-{index}.svg",
            width=760,
        )
        _, whole_rows = _pixels(
            _only_layer(svg, "velum", unmask=True),
            tmp_path / f"velum-whole-{index}.svg",
            width=760,
        )
        painted = sum(
            row[x] != 0 for row in painted_rows for x in range(3, len(row), 4)
        )
        whole = sum(row[x] != 0 for row in whole_rows for x in range(3, len(row), 4))
        if whole and painted / whole < VELUM_SURVIVAL:
            failures.append((phone, painted, whole, painted / whole))
    assert not failures, f"velum erased at contact: {failures[:6]}"


@pytest.mark.parametrize("layer", sorted(LAYERS), ids=sorted(LAYERS))
def test_a_mark_is_painted_and_nothing_paints_over_it(
    layer: str, tmp_path: Path
) -> None:
    """Rasterize, take the layer out, rasterize again, count the difference.

    Inspecting the SVG cannot settle this. An element can be present,
    styled, inside the frame and last in document order and still show
    nothing, because a fill above it is opaque or a custom property was
    dropped by the renderer. Removing it and finding the picture unchanged
    is the only statement about the mark that a reader can rely on, and it
    is how nine defects in this drawing were found.
    """
    if shutil.which("rsvg-convert") is None:  # pragma: no cover - CI has no rsvg
        pytest.skip("rsvg-convert not installed: the raster claim is unmeasured here")
    svg = tract_svg.figure(LAYERS[layer], "adult-male")
    without = re.sub(
        r'<(path|circle|rect|line)\b[^>]*class="[^"]*(?<![a-z-])'
        + layer
        + r'(?![a-z-])[^"]*"[^>]*/>',
        "",
        svg,
    )
    assert without != svg, f"no .{layer} element is emitted at all"
    width, before = _pixels(svg, tmp_path / "with.svg")
    _, after = _pixels(without, tmp_path / "without.svg")
    moved = _differing(width, before, after)
    assert len(moved) > 50, f".{layer} changes only {len(moved)} px: it is not visible"


@pytest.mark.parametrize(
    "figure", sorted(FIGURES.glob("tract-*.svg")), ids=lambda p: p.stem
)
def test_the_checked_in_figure_is_what_the_code_draws(figure: Path) -> None:
    """``make figures`` must be a no-op on a clean tree.

    The figures are checked in so a reader gets them without running
    anything, which only works while they are current: a stale one is a
    picture of geometry the library no longer has. The phone comes from the
    figure's own caption rather than from a list here, so a figure added to
    the Makefile is checked without this test being told about it.
    """
    text = figure.read_text(encoding="utf-8")
    glyph = re.search(r'<text[^>]*class="glyph"[^>]*>([^<]*)</text>', text)
    phone = glyph.group(1) if glyph else None
    fresh = tract_svg.figure(phone, "adult-male")
    assert fresh == text, f"{figure.name} is stale: run `make figures`"


def test_the_metric_point_is_a_closure_unless_the_place_combines() -> None:
    """What the metric compares and what a drawing closes are not one tuple.

    ``constrictions`` once promised its first point was always
    ``tract_point``'s. It cannot be. A combining place declares no arc, so
    the metric answers with the mean of its components, and a mean of two
    distinct arcs lies strictly between them -- a coordinate where, for a
    labial-velar, neither the lips nor the dorsum close. The promise invited
    a reader to take ``[0]`` as the primary and quietly disagree with the
    metric on ``w``.

    Stated as the shape of the mistake rather than as today's six segments:
    a single named place puts the metric's point in the tuple, a combining
    one keeps it out. Both arms are required to be reached, so removing
    either kind from the inventory fails here instead of passing vacuously.
    """
    ipa = IPAFeatures()
    combining: list[str] = []
    simple = 0
    for phone in sorted(ipa.phones):
        bundle = ipa.get_features(phone)
        summary = tract_point(ipa, bundle)
        points = constrictions(ipa, bundle)
        if summary.arc is None or not points:
            continue
        if Feature.COMBINER in (bundle.get("place") or ""):
            combining.append(phone)
            assert all(
                q.arc is not None and abs(q.arc - summary.arc) > 1e-9 for q in points
            ), f"{phone}: the mean of two places is not a closure at either"
        else:
            simple += 1
            assert points[0] == summary, (
                f"{phone}: names one place, so the metric's point is its "
                f"front-most closure -- got {points[0]} for {summary}"
            )
    assert simple > 100, f"only {simple} single-place segments: the sweep is vacuous"
    assert combining, "no combining place reached: the exception is unchecked"


def test_a_click_closes_twice() -> None:
    """A click holds a front closure and a velar one at the same time.

    Drawn with only the place it names it is an ordinary stop wearing a
    velaric label: the pocket that makes the sound is the space between the
    two closures, so one of them is not optional.
    """
    ipa = IPAFeatures()
    clicks = [
        p for p in ipa.phones if ipa.get_features(p).get("airstream") == "velaric"
    ]
    assert clicks, "no clicks in the inventory to check"
    for phone in clicks:
        points = constrictions(ipa, ipa.get_features(phone))
        arcs = sorted(q.arc for q in points if q.arc is not None)
        assert len(points) >= 2, f"{phone}: only {len(points)} constriction(s)"
        assert arcs[-1] >= 0.45 - 1e-9, f"{phone}: no velar closure, arcs {arcs}"
        assert all(
            q.offset is not None and q.offset >= 0.995 for q in points
        ), f"{phone}: a click's closures must be complete"


def _draw(*argv: str, out: Path) -> str:
    """Run one of the command lines that draw, and read back what it wrote."""
    proc = subprocess.run(
        [sys.executable, *argv, "-o", str(out)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONHASHSEED": "0"},
    )
    assert proc.returncode == 0, f"{argv} failed:\n{proc.stderr}"
    return out.read_text(encoding="utf-8")


class TestThereIsOneWayToDraw:
    """Three command lines, a call and a display hook; one drawing behind them.

    The renderer is in the package because ``scripts/`` ships in neither
    the wheel nor the importable half of the sdist, and an installed
    ipakit holding the tract model with no way to draw it is no use to
    anyone. That is what leaves the risk this class exists to close:
    several entries into the same picture, free to drift, one of them a
    script and one of them a subcommand. ``drawing()`` is the single
    derivation and ``render()`` the single assembly, and these assert that
    every entry lands on the same bytes as the figure checked into
    ``docs/``.
    """

    def test_every_entry_writes_the_same_bytes(self, tmp_path: Path) -> None:
        """The library call, the module, the script and the CLI agree.

        And they agree with ``docs/figures/tract-t.svg``, which is what
        ``make figures`` wrote -- so a change that quietly reroutes any one
        of them fails here rather than in a diff nobody reads.
        """
        checked_in = (FIGURES / "tract-t.svg").read_text(encoding="utf-8")
        entries = {
            "figure()": tract_svg.figure("t", "adult-male"),
            "python -m ipakit.tract_svg": _draw(
                "-m",
                "ipakit.tract_svg",
                "draw",
                "--head",
                "adult-male",
                "--phone",
                "t",
                out=tmp_path / "module.svg",
            ),
            "scripts/tract_svg.py": _draw(
                "scripts/tract_svg.py",
                "draw",
                "--head",
                "adult-male",
                "--phone",
                "t",
                out=tmp_path / "script.svg",
            ),
            "ipakit tract draw": _draw(
                "-m",
                "ipakit.cli",
                "tract",
                "draw",
                "t",
                "--head",
                "adult-male",
                out=tmp_path / "cli.svg",
            ),
            "Segment._repr_svg_": ipakit.segment("t")._repr_svg_(),
        }
        differ = [name for name, svg in entries.items() if svg != checked_in]
        assert not differ, f"these do not draw docs/figures/tract-t.svg: {differ}"

    def test_every_entry_writes_the_same_page(self, tmp_path: Path) -> None:
        """And the page route has one assembly, for the same reason.

        ``render_page`` is to :func:`tract_svg.page` what ``render`` is to
        ``standalone_svg``. There was none, and the two call sites unpacked
        the same mapping into eight positional arguments by hand.
        """
        entries = {
            "render_page()": tract_svg.render_page(
                tract_svg.drawing("adult-male", "t")
            ),
            "python -m ipakit.tract_svg": _draw(
                "-m",
                "ipakit.tract_svg",
                "draw",
                "--head",
                "adult-male",
                "--phone",
                "t",
                out=tmp_path / "module.html",
            ),
            "scripts/tract_svg.py": _draw(
                "scripts/tract_svg.py",
                "draw",
                "--head",
                "adult-male",
                "--phone",
                "t",
                out=tmp_path / "script.html",
            ),
            "ipakit tract draw --page": _draw(
                "-m",
                "ipakit.cli",
                "tract",
                "draw",
                "t",
                "--head",
                "adult-male",
                "--page",
                out=tmp_path / "cli.html",
            ),
        }
        one = entries["render_page()"]
        differ = [name for name, text in entries.items() if text != one]
        assert not differ, f"these do not write the same page: {differ}"

    def test_the_page_leaves_the_caption_off_when_it_is_asked_to(
        self, tmp_path: Path
    ) -> None:
        """``--no-caption`` reaches the page, and moves nothing else.

        It reached the SVG route and not the page one, which passed the
        caption whatever the flag said. The other half of the claim is that
        a phone asked for without a caption is still a phone: the aperture
        profile and the provenance table belong to the reference drawing.
        """
        cli = ["-m", "ipakit.cli", "tract", "draw", "--head", "adult-male", "--page"]
        with_caption = _draw(*cli, "t", out=tmp_path / "with.html")
        without = _draw(*cli, "t", "--no-caption", out=tmp_path / "without.html")
        reference = _draw(*cli, out=tmp_path / "reference.html")

        assert 'class="glyph"' in with_caption, "no caption to leave off"
        assert 'class="glyph"' not in without, "--page ignores --no-caption"
        # The caption is the only thing that goes: the three classes
        # ``_caption`` emits, and nothing beyond them.
        stripped = re.sub(
            r'<text[^>]*class="(?:glyph|lbl caption|lbl feat)"[^>]*>.*?</text>',
            "",
            with_caption,
        )
        assert without == stripped, "--no-caption moved more than the caption"
        assert "Declared aperture" in reference, "the reference lost its profile"
        assert (
            "Declared aperture" not in without
        ), "a phone drawn without a caption became the reference page"

    def test_the_script_is_a_way_in_and_not_a_second_renderer(self) -> None:
        """``scripts/tract_svg.py`` may delegate; it may not draw.

        Written as a predicate rather than a diff against today's file: the
        mistake to catch is a copy of the drawing logic left behind, and a
        copy declares functions and emits markup whatever it is called.
        """
        source = (ROOT / "scripts" / "tract_svg.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        declared = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        ]
        assert not declared, f"the shim declares its own {declared}"
        markup = [
            token for token in ("<svg", "<path", "<circle", "@media") if token in source
        ]
        assert not markup, f"the shim carries drawing markup: {markup}"

    def test_the_cli_reaches_every_declared_head(self) -> None:
        """``tract heads`` lists what ``heads()`` declares, and no less.

        A drawing command that can only reach the head someone remembered
        to name is the shape of divergence this repo has fixed once per
        surface; the list is read off the model.
        """
        proc = subprocess.run(
            [sys.executable, "-m", "ipakit.cli", "tract", "heads", "-f", "json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert proc.returncode == 0, proc.stderr
        listed = {row["name"] for row in json.loads(proc.stdout)}
        assert listed == set(
            heads()
        ), f"CLI lists {listed}, model declares {set(heads())}"


class TestWhatDrawsItselfInANotebook:
    """One posture, one figure -- and the hook is only where that holds.

    A ``_repr_svg_`` is not a convenience, it is a claim: *this object is
    what the picture shows*. A ``Segment`` is one unit and therefore one
    posture, and a ``Head`` is one geometry at one rest posture, so both
    can make it. A ``Form`` is a sequence of postures and a ``Derivation``
    a sequence of forms; either would have to pick one posture, which is a
    silent wrong answer, or lay out a strip, which is a feature of its own
    and belongs with the document that explains it.
    """

    def test_a_segment_draws_itself_over_the_inventory(self) -> None:
        """Sampled deliberately, and the sample says what it covers.

        Every registered phone, plus one marked unit per diacritic so no
        diacritic goes unexercised. The full 8060-unit corpus is ~90s of
        drawing, which is too slow for the default run; what a marked unit
        can do that a bare one cannot is reach ``unmodelled``, and one unit
        per diacritic reaches all of it.
        """
        ipa = IPAFeatures()
        phones = corpus.self_spelling_phones()
        units = list(phones)
        barren = []
        with warnings.catch_warnings():
            # Probing a mark against a base is *expected* to fail for the
            # marks that bind nothing, and their warnings would be noise in
            # every run. How many there are is asserted instead, so the
            # blind spot stays known rather than assumed shut.
            warnings.simplefilter("ignore")
            for mark in sorted(ipa.diacritics):
                for phone in phones:
                    candidate = phone + mark
                    if ipa.segment(candidate).to_ipa() == candidate:
                        units.append(candidate)
                        break
                else:
                    barren.append(mark)
        assert len(barren) <= 8, f"{len(barren)} marks compose with nothing: {barren}"
        corpus.assert_swept(len(units), phones)
        assert len(units) > 190, f"only {len(units)} units: the sample lost the marks"
        for unit in units:
            svg = ipakit.segment(unit)._repr_svg_()
            assert svg.startswith("<svg "), unit
            assert (
                "<style>" in svg
            ), f"{unit}: no resolved styles, it would rasterize blank"
            assert svg.endswith("</svg>"), unit

    def test_a_segment_carrying_its_own_inventory_draws_against_it(self) -> None:
        """The figure follows the data the segment was built from.

        A caller with their own ``ipa.xml`` gets a picture of their data:
        the caption is asked of the segment's own inventory rather than of
        the package-level default, which is where the two could disagree
        silently.
        """
        ipa = IPAFeatures()
        seg = ipa.segment("t")
        assert seg._repr_svg_() == tract_svg.figure("t", features=ipa)

    @pytest.mark.parametrize("head_name", sorted(heads()))
    def test_a_head_draws_its_own_reference(self, head_name: str) -> None:
        """Each head shows itself, at the posture it declares for rest."""
        svg = head(head_name)._repr_svg_()
        assert svg == tract_svg.figure(None, head_name)
        assert svg.startswith("<svg ") and "<style>" in svg

    def test_a_sequence_of_postures_has_no_figure(self) -> None:
        """Pinned, so the limit stays known rather than assumed shut.

        If ``Form`` or ``Derivation`` grows a display hook this fails, and
        ``docs/tract-figures.md`` -- which says why they have none -- needs
        updating in the same commit. A filmstrip is the obvious next thing
        to build, and it should arrive with the paragraph explaining it.
        """
        hooks = ("_repr_svg_", "_repr_html_", "_repr_markdown_", "_repr_png_")
        for kind in (ipakit.Form, ipakit.Derivation):
            grown = [hook for hook in hooks if hasattr(kind, hook)]
            assert not grown, f"{kind.__name__} grew {grown}: see docs/tract-figures.md"
        # The other half of the claim: what does have one, still has one.
        for kind in (ipakit.Segment, Head):
            assert hasattr(kind, "_repr_svg_"), kind.__name__
