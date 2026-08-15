"""Regenerate display-space epiglottal tip-to-target aperture pins."""

from __future__ import annotations

import json
import math
import sys
from dataclasses import replace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from ipakit.features import IPAFeatures  # noqa: E402
from ipakit.tract import head, landmarks, posture  # noqa: E402
from ipakit.tract_svg import _extent, _scaler, build_geometry  # noqa: E402


def capture() -> dict[str, float]:
    ipa, h = IPAFeatures(), head()
    base = posture(ipa, "ʡ", h)
    postures = {
        "open": replace(base, epiglottal=0.0),
        "ʜ": posture(ipa, "ʜ", h),
        "ʢ": posture(ipa, "ʢ", h),
        "ʡ": base,
    }
    out = {}
    for name, p in postures.items():
        geometry = build_geometry(h, landmarks(ipa, h.name), p)
        # Measure the named constriction endpoints, not arbitrary pixels on
        # the leaf and wall: the previous global minimum selected the leaf's
        # laryngeal root.  Transform both through the renderer's scaler so the
        # pins remain distances in the committed SVG's display pixels.
        to = _scaler(*_extent(geometry))
        shape = geometry["epiglottis"]
        out[name] = math.dist(to(*shape["tip"]), to(*shape["target"]))
    return out


if __name__ == "__main__":
    path = Path(__file__).with_name("epiglottal_constriction.json")
    path.write_text(json.dumps(capture(), indent=2, sort_keys=True) + "\n")
