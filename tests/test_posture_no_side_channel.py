"""The gate for the posture-vector split (H0.1).

The drawing is being refactored from one step into two: a symbol->vector step
``ipakit.tract.posture(features, phone) -> Posture`` and a vector->geometry
step ``ipakit.tract_svg.build_geometry(head, marks, posture) -> dict``. The
whole point of the split is that geometry becomes a pure function of the
posture -- ``build_geometry`` never sees the symbol -- so two phones that pose
the tract the same way cannot draw differently, and nothing downstream can
reach the glyph through the picture.

This file gates the *post-integration* result. It asserts three things:

1. **Behavior is preserved.** For every registered phone (and the reference),
   ``render(drawing(head, phone))`` still equals the byte-for-byte golden
   captured from the pre-refactor code in ``tests/fixtures/posture_golden.json``
   (see ``tests/fixtures/_capture_posture_golden.py``). This runs *now*, on the
   current code, and stays green only if the refactor is byte-identical.

2. **No symbol side-channel, structurally.** ``build_geometry`` takes a
   ``Posture`` (plus head and landmarks) and has no ``phone``/``bundle``/symbol
   parameter, and the geometry it returns for a phone equals the ``geometry``
   inside ``drawing(head, phone)``.

3. **No symbol side-channel, behaviorally.** A ``Posture`` rebuilt from its own
   fields alone -- carrying no symbol -- draws the same geometry as the
   original, so the geometry depends on the vector and nothing else.

Checks 2 and 3 need the new API, which does not exist until the ``posture`` /
``build_geometry`` lane lands. Until then this module imports what it can and
those two checks skip; check 1 runs regardless. Once the API is present the
skips turn into real assertions -- there is no soft path through them.
"""

from __future__ import annotations

import dataclasses
import inspect
import json
from pathlib import Path

import pytest
from ipakit.features import IPAFeatures
from ipakit.tract import head, landmarks
from ipakit.tract_svg import drawing, render

# The reference (phone=None) drawing is stored under this sentinel key in the
# golden map; it is not a phone in any inventory. Kept in step with
# tests/fixtures/_capture_posture_golden.py::REFERENCE_KEY.
REFERENCE_KEY = "\x00"

GOLDEN_PATH = Path(__file__).resolve().parent / "fixtures" / "posture_golden.json"
GOLDEN: dict[str, str] = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))

# Parameter names that would be a symbol side-channel into the geometry step.
FORBIDDEN_PARAMS = {"phone", "bundle", "symbol", "features", "ipa"}

# The new two-step API. Absent on the pre-split branch: import what exists and
# let checks 2 and 3 skip until the lane that adds it lands.
try:
    from ipakit.tract import Posture, posture
    from ipakit.tract_svg import build_geometry

    HAS_POSTURE_API = True
except ImportError:  # pragma: no cover - exercised only pre-integration
    Posture = None  # type: ignore[assignment,misc]
    posture = None  # type: ignore[assignment]
    build_geometry = None  # type: ignore[assignment]
    HAS_POSTURE_API = False

needs_api = pytest.mark.skipif(
    not HAS_POSTURE_API,
    reason="posture()/build_geometry()/Posture not present until the H0.1 split lands",
)


def _phone_for(key: str) -> str | None:
    """The ``drawing``/``posture`` argument a golden key stands for."""
    return None if key == REFERENCE_KEY else key


# The default head heads.xml declares -- the head make figures draws and the
# head the golden was captured against.
HEAD_NAME = head().name

GOLDEN_KEYS = sorted(GOLDEN)


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


# --------------------------------------------------------------------------
# 1. Behavior-preservation: byte-identical to the pre-refactor golden.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("key", GOLDEN_KEYS)
def test_render_matches_golden(key: str) -> None:
    """Every phone (and the reference) redraws to its captured bytes.

    This is the drift gate for the refactor: ``drawing`` stays the one entry
    every caller reaches a picture through, so if the split changes a single
    byte of any drawing, this fails.
    """
    phone = _phone_for(key)
    assert render(drawing(HEAD_NAME, phone)) == GOLDEN[key]


# --------------------------------------------------------------------------
# 2. No side-channel, structural.
# --------------------------------------------------------------------------
@needs_api
def test_build_geometry_signature_has_no_symbol() -> None:
    """``build_geometry`` takes a Posture plus head/landmarks -- no symbol."""
    params = inspect.signature(build_geometry).parameters
    names = set(params)
    assert FORBIDDEN_PARAMS.isdisjoint(names), (
        f"build_geometry exposes a symbol channel: "
        f"{sorted(FORBIDDEN_PARAMS & names)}"
    )
    assert (
        "posture" in names
    ), f"build_geometry has no posture parameter: {sorted(names)}"

    # If the posture parameter is annotated, it must be the Posture type.
    annotation = params["posture"].annotation
    if annotation is not inspect.Parameter.empty:
        text = (
            annotation
            if isinstance(annotation, str)
            else getattr(annotation, "__name__", str(annotation))
        )
        assert "Posture" in str(text), f"posture parameter is not a Posture: {text!r}"


@needs_api
def test_posture_is_a_frozen_dataclass() -> None:
    """The vector is a frozen dataclass -- rebuildable from its fields alone."""
    assert dataclasses.is_dataclass(Posture)
    assert Posture.__dataclass_params__.frozen, "Posture must be frozen"


@needs_api
@pytest.mark.parametrize("key", GOLDEN_KEYS)
def test_build_geometry_equals_drawing_geometry(key: str, ipa: IPAFeatures) -> None:
    """The vector->geometry step reproduces the geometry ``drawing`` derives."""
    phone = _phone_for(key)
    h = head(HEAD_NAME)
    marks = landmarks(ipa)
    post = posture(ipa, phone)
    assert build_geometry(h, marks, post) == drawing(HEAD_NAME, phone, ipa)["geometry"]


# --------------------------------------------------------------------------
# 3. No side-channel, behavioral round-trip.
# --------------------------------------------------------------------------
@needs_api
@pytest.mark.parametrize("key", GOLDEN_KEYS)
def test_geometry_is_pure_in_the_posture(key: str, ipa: IPAFeatures) -> None:
    """A Posture rebuilt from its fields alone draws the same geometry.

    ``p2`` carries only what ``p``'s fields carry -- no symbol, no bundle. If
    the geometry differs, something other than the vector reached the drawing.
    """
    phone = _phone_for(key)
    h = head(HEAD_NAME)
    marks = landmarks(ipa)
    p = posture(ipa, phone)
    # Reconstruct from fields only: a fresh, symbol-free copy of the vector.
    p2 = dataclasses.replace(p)
    assert build_geometry(h, marks, p) == build_geometry(h, marks, p2)
