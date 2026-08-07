"""THROWAWAY dev stub for smoke-testing ipakit.tract_svg.animate.

NOT the real model. ``score``/``blend`` are the model lane's job; this is a
minimal stand-in so the renderer half can be exercised before integration.
``install()`` monkeypatches ``ipakit.tract`` with these; nothing here is
imported by the package, and this file must never move under ``ipakit/``.

``blend`` here is a cheap linear interpolation of the postural scalars between
the two bracketing units (nearest unit for the discrete parts). The real
dominance blend with falloff is deliberately not implemented here.
"""

from __future__ import annotations

from ipakit.features import IPAFeatures
from ipakit.tract import Posture, TractPoint, head, posture


def stub_score(features: IPAFeatures, word: str) -> tuple[Posture, ...]:
    h = head()
    return tuple(posture(features, seg.to_ipa(), h) for seg in features.segments(word))


def _lerp(a: float | None, b: float | None, f: float) -> float | None:
    if a is None:
        return b
    if b is None:
        return a
    return a + (b - a) * f


def _lerp_point(a: TractPoint, b: TractPoint, f: float) -> TractPoint:
    # Articulator (a discrete label) is taken from whichever unit dominates.
    return TractPoint(
        arc=_lerp(a.arc, b.arc, f),
        offset=_lerp(a.offset, b.offset, f),
        articulator=(a if f < 0.5 else b).articulator,
    )


def stub_blend(units: tuple[Posture, ...], t: float, falloff: float = 0.0) -> Posture:
    n = len(units)
    if n == 0:
        raise ValueError("no units to blend")
    t = max(0.0, min(t, n - 1))
    i0 = int(t)
    i1 = min(i0 + 1, n - 1)
    f = t - i0
    a, b = units[i0], units[i1]
    near = a if f < 0.5 else b
    reading = None
    if a.reading is not None and b.reading is not None:
        reading = _lerp_point(a.reading, b.reading, f)
    else:
        reading = near.reading
    m = min(len(a.constrictions), len(b.constrictions))
    constrictions = (
        tuple(_lerp_point(a.constrictions[k], b.constrictions[k], f) for k in range(m))
        + near.constrictions[m:]
    )
    return Posture(
        reading=reading,
        rest=near.rest,
        constrictions=constrictions,
        velic=_lerp(a.velic, b.velic, f) or 0.0,
        glottal=_lerp(a.glottal, b.glottal, f),
        secondary=near.secondary,
        unmodelled=near.unmodelled,
    )


def install() -> None:
    """Attach the stubs to ipakit.tract so animate() can find them."""
    import ipakit.tract as tract

    tract.score = stub_score  # type: ignore[attr-defined]
    tract.blend = stub_blend  # type: ignore[attr-defined]
