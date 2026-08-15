"""Regenerate raster-derived epiglottal aperture pins."""

from __future__ import annotations

import json
import math
import re
import sys
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from ipakit.features import IPAFeatures  # noqa: E402
from ipakit.tract import head, landmarks, posture  # noqa: E402
from ipakit.tract_svg import build_geometry, section_svg  # noqa: E402
from tests.test_tract_figures import _alpha_pixels, _pixels  # noqa: E402


def isolated(paths: list[str], cls: str) -> str:
    body = "".join(f'<path d="{path}" class="{cls}"/>' for path in paths)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 540">'
        f"<style>.{cls}{{fill:none;stroke:#000;stroke-width:2}}</style>{body}</svg>"
    )


def capture() -> dict[str, float]:
    ipa, h = IPAFeatures(), head()
    base = posture(ipa, "ʡ", h)
    out = {}
    with TemporaryDirectory() as directory:
        root = Path(directory)
        for name, degree in (("open", 0.0), ("approximant", 0.5), ("closure", 1.0)):
            p = replace(base, epiglottal=degree)
            geometry = build_geometry(h, landmarks(ipa, h.name), p)
            svg = section_svg(geometry, None, p.velic, None, None, {})
            paths = re.findall(r'<path d="([^"]+)" class="([^"]+)"/?>', svg)
            leaf = [path for path, cls in paths if cls == "epiglottis"]
            wall = [path for path, cls in paths if cls == "wall"]
            width, leaf_rows = _pixels(
                isolated(leaf, "epiglottis"), root / f"{name}-leaf.svg", 760
            )
            _, wall_rows = _pixels(
                isolated(wall, "wall"), root / f"{name}-wall.svg", 760
            )
            leaf_pixels = _alpha_pixels(width, leaf_rows, 20)
            wall_pixels = _alpha_pixels(width, wall_rows, 20)
            out[name] = min(math.dist(a, b) for a in leaf_pixels for b in wall_pixels)
    return out


if __name__ == "__main__":
    path = Path(__file__).with_name("epiglottal_constriction.json")
    path.write_text(json.dumps(capture(), indent=2, sort_keys=True) + "\n")
