"""The gate for animating a posture trajectory (H0.2).

H0.1 split a drawing into ``symbol -> vector -> geometry``: a phone reads to a
:class:`~ipakit.tract.Posture`, and ``build_geometry(head, marks, posture)``
projects that vector reading *no symbol*. Animation is the payoff of that
split -- a word becomes a sequence of Postures, you blend between them, and you
project each blended Posture through the same ``build_geometry``. Nothing new
reaches the picture; the symbol channel stays shut per frame.

This file gates that trajectory API:

* ``ipakit.tract.score(features, word) -> tuple[Posture, ...]`` -- one Posture
  per segment (via ``features.segments(word)``).
* ``ipakit.tract.blend(units, t, falloff=...) -> Posture`` -- a dominance blend
  at ordinal ``t`` in ``[0, N-1]``; a real Posture, each integer ``t=i``
  dominated by unit ``i`` (coarticulated, not identical -- see ``CENTER_TOL``).
* ``ipakit.tract_svg.animate(word, head_name=None, features=None,
  frames_per_unit=...) -> str`` -- a self-contained animated artifact whose
  frames are ``build_geometry(head, marks, blend(score, t))``.

None of the three exists until the animation lane lands. Until then the import
below fails and every ``@needs_api`` test skips; there is no soft path through
them -- once the API is present the assertions are real. The H0.1 gate in
``tests/test_posture_no_side_channel.py`` still owns the per-phone side-channel
proof; this file adds the per-frame one.

The known-weak cases this cut does not cover are enumerated in
``tests/ANIMATION_LIMITS.md``. The anti-slide guarantee it *does* hold --
no constriction leaves its articulator's arc across an articulator change --
is pinned by ``test_articulator_change_does_not_slide_the_constriction``.
"""

from __future__ import annotations

import dataclasses
import inspect
import re

import pytest
from ipakit.features import IPAFeatures
from ipakit.tract import Posture, head, landmarks
from ipakit.tract_svg import build_geometry

# The animation API. Absent until the score/blend/animate lane lands: import
# what exists, and let every check below skip until it does. score, blend and
# animate arrive together, so a single failed import gates the whole surface.
try:
    from ipakit.tract import GLOTTAL_REST, blend, score
    from ipakit.tract_svg import animate

    HAS_ANIM_API = True
except ImportError:  # pragma: no cover - exercised only pre-integration
    blend = None  # type: ignore[assignment]
    score = None  # type: ignore[assignment]
    animate = None  # type: ignore[assignment]
    GLOTTAL_REST = 1.0
    HAS_ANIM_API = False

needs_api = pytest.mark.skipif(
    not HAS_ANIM_API,
    reason="score()/blend()/animate() not present until the H0.2 animation lane lands",
)

# The default head heads.xml declares -- the one figures draw on.
HEAD_NAME = head().name

# Dictionary pronunciations that must animate without raising.
WORDS = ["kat", "aki", "sun"]

# Two vowels on one articulator (both tongue-front: i off=0.38, e off=0.28),
# so a blend between them moves one constriction degree monotonically.
SAME_ARTICULATOR_VOWELS = "ie"

# Two vowels on *different* articulators (a tongue-root, i tongue-front): the
# transition this cut cannot yet model as two gestures. See ANIMATION_LIMITS.md.
ARTICULATOR_CHANGE = "ai"

# How far a coarticulated center may sit from its citation posture, per scalar.
# The dominance blend is non-cardinal (chosen 2026-08-07): at t=i the owning
# unit's weight is ~0.96 and each neighbor leaks ~0.018, so any one blendable
# scalar moves at most a few hundredths -- undershoot/overlap, the point of
# Cohen-Massaro. A center must still be *dominated by* its own unit; this bounds
# how much it may be pulled, well below the gap between distinct units.
CENTER_TOL = 0.06

# Words the model surface must never grow a clock for. A blend takes an ordinal
# t and a falloff; a Posture carries articulation, not seconds.
TIME_WORDS = {
    "seconds",
    "second",
    "duration",
    "dur",
    "ms",
    "millis",
    "milliseconds",
    "time",
    "timing",
    "fps",
    "rate",
    "tempo",
    "bpm",
}


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


def _scalars(p: Posture) -> tuple[float, float, float, float]:
    """A posture's blendable scalars, for a coarse posture distance.

    The primary reading's arc and offset, the velic and the glottal (a ``None``
    glottal resolved to rest the way ``blend`` resolves it). Enough to say which
    unit a blended posture sits nearest and how far off it is.
    """
    r = p.reading
    arc, off = (r.arc or 0.0, r.offset or 0.0) if r is not None else (0.0, 0.0)
    glottal = GLOTTAL_REST if p.glottal is None else p.glottal
    return (arc, off, p.velic, glottal)


def _apart(a: Posture, b: Posture) -> float:
    """L1 distance over the blendable scalars -- for ranking the nearest unit."""
    return sum(abs(x - y) for x, y in zip(_scalars(a), _scalars(b), strict=True))


def _max_dev(a: Posture, b: Posture) -> float:
    """Largest single-scalar deviation -- the tolerance a center is held to."""
    return max(abs(x - y) for x, y in zip(_scalars(a), _scalars(b), strict=True))


def _assert_self_contained(art: str) -> None:
    """No frame may reach the network -- a zero-dep artifact ships whole.

    The SVG/XML namespace URIs (``xmlns="http://www.w3.org/2000/svg"``) are
    identifiers, not fetches, and are allowed; a fetched resource is a
    ``src``/``href`` pointing at ``http(s)``, a CSS ``url(http...)`` or an
    ``@import``, and none of those may appear.
    """
    assert "src=" not in art, "animation references an external src"
    assert not re.search(
        r'(?:xlink:)?href\s*=\s*["\'][^"\']*https?://', art
    ), "animation references an external href"
    assert not re.search(
        r'url\(\s*["\']?\s*https?://', art
    ), "animation pulls a CSS resource over the network"
    assert "@import" not in art, "animation @imports an external stylesheet"


# --------------------------------------------------------------------------
# 1. A dictionary pronunciation animates.
# --------------------------------------------------------------------------
@needs_api
@pytest.mark.parametrize("word", WORDS)
def test_word_animates_self_contained(word: str, ipa: IPAFeatures) -> None:
    """``animate(word)`` returns a non-empty, self-contained artifact."""
    art = animate(word, head_name=HEAD_NAME, features=ipa)
    assert isinstance(art, str)
    assert art.strip(), f"animate({word!r}) produced an empty artifact"
    _assert_self_contained(art)


# --------------------------------------------------------------------------
# 2. A uniform ordinal clock: one unit per unit, endpoints on the units.
# --------------------------------------------------------------------------
@needs_api
@pytest.mark.parametrize("word", ["kat", SAME_ARTICULATOR_VOWELS])
def test_one_posture_per_segment(word: str, ipa: IPAFeatures) -> None:
    """``score`` returns exactly one Posture per segment, each a real Posture."""
    units = score(ipa, word)
    expected = len(ipa.segments(word))
    assert (
        len(units) == expected
    ), f"score({word!r}) has {len(units)} units for {expected} segments"
    assert all(isinstance(u, Posture) for u in units)


@needs_api
@pytest.mark.parametrize("word", ["kat", SAME_ARTICULATOR_VOWELS])
def test_timeline_lands_each_center_on_its_unit(word: str, ipa: IPAFeatures) -> None:
    """The clock is ordinal: integer ``t=i`` is dominated by unit ``i``.

    Not exact equality -- the dominance blend coarticulates (chosen behavior:
    non-cardinal, so a center is slightly pulled toward its neighbors, which is
    the undershoot/overlap Cohen-Massaro is for). The ordinal-clock guarantee is
    weaker and truer: at every integer ``i`` the blend sits *nearer its own unit
    than any other* and within ``CENTER_TOL`` of it, endpoints included. The
    timeline spans ``[0, N-1]`` -- one unit per unit; the model counts units,
    never seconds.
    """
    units = score(ipa, word)
    n = len(units)
    for i in range(n):
        b = blend(units, i)
        nearest = min(range(n), key=lambda j: _apart(b, units[j]))
        assert nearest == i, f"blend at t={i} sits nearer unit {nearest} than {i}"
        dev = _max_dev(b, units[i])
        assert (
            dev < CENTER_TOL
        ), f"blend at t={i} is {dev:.3f} from unit {i} (>{CENTER_TOL})"


@needs_api
def test_no_seconds_on_the_model_surface() -> None:
    """The model surface names ordinals and falloff, never a duration.

    ``blend`` and ``score`` take no time-shaped parameter, and ``Posture``
    carries no time-shaped field -- the clock is the unit index, and turning
    frames into seconds is a rendering choice that never reaches the vector.
    """
    for fn in (blend, score):
        params = {p.lower() for p in inspect.signature(fn).parameters}
        clash = TIME_WORDS & params
        assert not clash, f"{fn.__name__} exposes a time parameter: {sorted(clash)}"
    fields = {f.name.lower() for f in dataclasses.fields(Posture)}
    clash = TIME_WORDS & fields
    assert not clash, f"Posture carries a time field: {sorted(clash)}"


# --------------------------------------------------------------------------
# 3. No side-channel per frame: every frame is a pure function of a Posture.
# --------------------------------------------------------------------------
@needs_api
@pytest.mark.parametrize("word", ["kat", "aki"])
def test_every_frame_is_pure_in_the_posture(word: str, ipa: IPAFeatures) -> None:
    """A blended frame's geometry depends on the vector and nothing else.

    Mirrors the H0.1 round-trip: for sampled ordinals, ``blend`` yields a real
    Posture, and a symbol-free copy rebuilt from its own fields alone
    (``dataclasses.replace``) projects to byte-identical geometry. If a frame
    could differ, something other than the Posture reached ``build_geometry``.
    """
    h = head(HEAD_NAME)
    marks = landmarks(ipa)
    units = score(ipa, word)
    n = len(units)
    step = 0.5
    t = 0.0
    while t <= n - 1 + 1e-9:
        blended = blend(units, t)
        assert isinstance(blended, Posture), f"blend at t={t} is not a Posture"
        rebuilt = dataclasses.replace(blended)  # fields only -- no symbol
        assert build_geometry(h, marks, blended) == build_geometry(h, marks, rebuilt)
        t += step


# --------------------------------------------------------------------------
# 4. Blend sanity.
# --------------------------------------------------------------------------
@needs_api
def test_centers_coarticulate_but_only_slightly(ipa: IPAFeatures) -> None:
    """A medial center is pulled toward its neighbors -- really, and a little.

    This pins the chosen non-cardinal behavior from both sides: the pull is
    real (a segment in context is not its isolated citation posture, so the
    deviation is nonzero) and bounded (within ``CENTER_TOL``). The static
    ``figure()`` still draws the exact citation posture; only the animation
    coarticulates.
    """
    units = score(ipa, "kat")
    assert len(units) >= 3, "need a medial unit with neighbors on both sides"
    medial = blend(units, 1)
    dev = _max_dev(medial, units[1])
    assert 0.0 < dev < CENTER_TOL, f"medial center deviates {dev:.4f} from its unit"


@needs_api
def test_same_articulator_vowels_move_monotonically(ipa: IPAFeatures) -> None:
    """Between two vowels on one articulator, the constriction moves one way.

    ``i`` and ``e`` share the tongue-front articulator and one arc, differing
    only in offset (0.38 -> 0.28). A dominance blend from the first to the
    second must walk that offset monotonically -- no overshoot, no reversal --
    and must actually move, so the frames are an interpolation and not a jump.
    """
    units = score(ipa, SAME_ARTICULATOR_VOWELS)
    assert len(units) == 2
    offsets = []
    t = 0.0
    while t <= 1.0 + 1e-9:
        point = blend(units, t).reading
        assert point is not None and point.offset is not None
        offsets.append(point.offset)
        t += 0.25
    assert offsets == sorted(offsets) or offsets == sorted(
        offsets, reverse=True
    ), f"offset is not monotonic across the transition: {offsets}"
    assert offsets[0] != offsets[-1], "the vowels did not move -- no interpolation"


@needs_api
def test_glottal_and_velic_never_blend_through_none(ipa: IPAFeatures) -> None:
    """A None glottal is resolved before blending; the aperture stays a float.

    ``glottal_aperture`` returns None when a bundle fixes no glottal state, and
    a trajectory cannot interpolate through None. The contract is that ``blend``
    resolves it first: for units where one endpoint carries ``glottal=None``,
    every ordinal along the span -- endpoints included -- yields a real float
    glottal, and velic (already a float) stays one.
    """
    voiced = score(ipa, "aki")
    for word_units in (voiced,):
        n = len(word_units)
        t = 0.0
        while t <= n - 1 + 1e-9:
            b = blend(word_units, t)
            assert b.glottal is not None, f"glottal is None at t={t}"
            assert isinstance(b.velic, float), f"velic is not a float at t={t}"
            t += 0.5

    # A directed case: force one endpoint's glottal to None and confirm the
    # blend never returns None -- the resolution happens inside blend, at the
    # blend() surface, not upstream in score().
    a = dataclasses.replace(score(ipa, "a")[0], glottal=None)
    i = score(ipa, "i")[0]
    pair = (a, i)
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        assert (
            blend(pair, t).glottal is not None
        ), f"blend passed a None glottal through at t={t}"


# --------------------------------------------------------------------------
# The anti-slide guarantee -- see tests/ANIMATION_LIMITS.md.
# --------------------------------------------------------------------------
@needs_api
def test_articulator_change_does_not_slide_the_constriction(ipa: IPAFeatures) -> None:
    """A transition across articulators fades gestures; it does not slide one.

    ``a`` constricts with the tongue-root (arc 0.74) and ``i`` with the
    tongue-front (arc 0.32). A true two-gesture transition fades one
    constriction out while the other fades in; it never places a *constriction*
    at arc ~0.53, where neither articulator reaches. The blend keeps each
    articulator at its own arc, so no constriction slides -- checked here at the
    midpoint over the whole transition.

    ``reading`` is exempt: it is the weighted mean of the units' readings and
    drives jaw close only, not a tongue closure, so it does interpolate through
    the midpoint by design -- which is why the guarantee is on ``constrictions``
    and not on ``reading``.
    """
    units = score(ipa, ARTICULATOR_CHANGE)
    assert len(units) == 2
    unit_arcs = {round(c.arc, 6) for u in units for c in u.constrictions}
    for step in range(11):
        t = step / 10
        for c in blend(units, t).constrictions:
            assert round(c.arc, 6) in unit_arcs, (
                f"a constriction slid to phantom arc {c.arc} at t={t}; "
                f"the declared articulator arcs are {sorted(unit_arcs)}"
            )
