"""The model half of animation (H0.2): ``score`` and ``blend``.

``score`` reads a word into one :class:`~ipakit.tract.Posture` per segment;
``blend`` interpolates those postures at ordinal time ``t`` by dominance
functions, per articulator. The property that matters is that a constriction
keeps its *place* and moves only in *degree*: interpolating one primary point
from an alveolar to a velar closure would draw a tract no tongue makes, a
closure sliding across the hard palate. These tests pin the place and let the
degree move.
"""

from __future__ import annotations

import math

from ipakit.features import IPAFeatures
from ipakit.tract import (
    GLOTTAL_REST,
    Posture,
    TractPoint,
    blend,
    head,
    posture,
    score,
)

IPA = IPAFeatures()


def _offset_at(word: str, t: float) -> tuple[float, float]:
    """The tongue's peak constriction (arc, degree) in the blend at ``t``.

    Asked of the model the way a renderer does -- ``Head.tongue_offset`` over
    the blended controls, the max at each arc -- so it measures where the
    tongue actually approaches the wall, not merely which control was emitted.
    """
    h = head()
    controls = list(blend(score(IPA, word), t).constrictions)
    best = (0.0, -1.0)
    for i in range(101):
        arc = i / 100
        offs = [o for c in controls if (o := h.tongue_offset(arc, c)) is not None]
        if offs and max(offs) > best[1]:
            best = (arc, max(offs))
    return best


def test_score_is_one_posture_per_segment() -> None:
    units = score(IPA, "kat")
    assert len(units) == 3
    assert all(isinstance(u, Posture) for u in units)
    # A dictionary pronunciation in plain IPA goes straight through as its
    # segments -- same postures as reading each phone alone.
    for unit, phone in zip(units, ["k", "a", "t"], strict=True):
        assert unit.reading == posture(IPA, phone).reading


def test_score_binds_ties_into_one_unit() -> None:
    # The tokenizer binds a tie-joined run into a single unit, so an affricate
    # is one posture, not two.
    assert len(score(IPA, "t͡ʃa")) == 2


def test_blend_at_integer_returns_that_unit() -> None:
    units = score(IPA, "ata")
    for i, unit in enumerate(units):
        got = blend(units, float(i))
        # The owning unit reigns; neighbours leak a couple of percent at the
        # default falloff, so the primary offset matches to within that.
        assert unit.reading is not None and got.reading is not None
        assert math.isclose(got.reading.offset, unit.reading.offset, abs_tol=0.05)
        assert math.isclose(got.velic, unit.velic, abs_tol=0.05)


def test_constriction_place_is_pinned_across_the_transition() -> None:
    # /t/ closes at the alveolar ridge; through the whole /a/->/t/ transition
    # the peak constriction stays there and only its degree grows. Nothing
    # slides toward the velum.
    # At t=0 the vowel's own below-rest root gesture is active. Once the /t/
    # gesture enters, its peak stays pinned at the ridge.
    arcs = [_offset_at("ata", t)[0] for t in (0.25, 0.5, 0.75, 1.0)]
    assert max(arcs) - min(arcs) < 1e-6
    degrees = [_offset_at("ata", t)[1] for t in (0.25, 0.5, 1.0)]
    assert degrees[0] < degrees[1] < degrees[2]


def test_velar_and_alveolar_do_not_share_an_arc() -> None:
    # The dorsum rises at the velum for /k/, the tip at the ridge for /t/: two
    # different fixed arcs, neither one migrating to the other's place.
    alveolar, _ = _offset_at("ata", 1.0)
    velar, _ = _offset_at("aka", 1.0)
    assert velar - alveolar > 0.2


def test_only_the_word_articulators_are_active_in_a_single_place_word() -> None:
    # /a/ lowers the tongue root and /t/ raises the tip. Both named controls
    # remain present as implied whole-body targets instead of dropping to
    # global rest between them; no third articulator appears.
    for t in (0.0, 0.5, 1.0, 1.5, 2.0):
        cons = blend(score(IPA, "ata"), t).constrictions
        assert {c.articulator for c in cons} <= {"tongue-root", "tongue-tip"}
    assert {c.articulator for c in blend(score(IPA, "ata"), 0.0).constrictions} == {
        "tongue-root",
        "tongue-tip",
    }


def test_two_stops_blend_per_articulator_in_opposite_directions() -> None:
    # /tk/: as t goes 0->1 the tip opens and the dorsum closes, each at its own
    # arc. This is the whole claim -- degree interpolates, place does not.
    units = score(IPA, "tk")

    def offset(name: str, t: float) -> float:
        for c in blend(units, t).constrictions:
            if c.articulator == name:
                return c.offset or 0.0
        return 0.0

    tip = [offset("tongue-tip", t) for t in (0.0, 0.5, 1.0)]
    dorsum = [offset("tongue-dorsum", t) for t in (0.0, 0.5, 1.0)]
    assert tip[0] > tip[1] > tip[2]
    assert dorsum[0] < dorsum[1] < dorsum[2]


def test_two_vowels_blend_reading_monotonically() -> None:
    # /ai/: the open back /a/ to the close front /i/. The primary reading's
    # degree climbs monotonically across the interval.
    units = score(IPA, "ai")
    offs = []
    for k in range(6):
        r = blend(units, k / 5).reading
        assert r is not None and r.offset is not None
        offs.append(r.offset)
    assert all(a < b for a, b in zip(offs, offs[1:], strict=False))


def test_velic_opens_over_a_nasal() -> None:
    # /ana/: the port is sealed at the vowels and open at the nasal peak, so
    # velic rises to a maximum at t=1 and falls back.
    velics = [blend(score(IPA, "ana"), t).velic for t in (0.0, 1.0, 2.0)]
    assert velics[1] > 0.9
    assert velics[0] < 0.1 and velics[2] < 0.1


def test_glottal_none_resolves_to_rest_before_blending() -> None:
    # A unit that fixes no glottal state contributes GLOTTAL_REST, never None,
    # so the mean is a real number and equals the rest when every unit is None.
    silent = Posture(
        reading=TractPoint(0.3, 0.5, "tongue-front"),
        rest=None,
        constrictions=(),
        velic=0.0,
        glottal=None,
        secondary=(),
        unmodeled=(),
    )
    out = blend([silent, silent], 0.5)
    assert out.glottal is not None
    assert math.isclose(out.glottal, GLOTTAL_REST)


def test_blend_rejects_empty_and_nonpositive_falloff() -> None:
    import pytest

    with pytest.raises(ValueError):
        blend([], 0.0)
    with pytest.raises(ValueError):
        blend(score(IPA, "at"), 0.5, falloff=0.0)


def test_distant_units_keep_only_implied_whole_body_controls() -> None:
    # These are no longer Gaussian-tail ghosts: each unit supplies the
    # position its posture implies for every tongue articulator used by the
    # word, so the body moves target-to-target instead of via global rest.
    units = score(IPA, "kat")
    expected = {"tongue-dorsum", "tongue-root", "tongue-tip"}
    assert {c.articulator for c in blend(units, 2.0).constrictions} == expected
    assert {c.articulator for c in blend(units, 0.0).constrictions} == expected
