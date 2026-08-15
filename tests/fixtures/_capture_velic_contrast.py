"""Regenerate the raster-derived velic contrast pins.

Run from the repository root with a deterministic hash seed:

    PYTHONHASHSEED=0 python tests/fixtures/_capture_velic_contrast.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from ipakit import tract_svg  # noqa: E402
from tests.test_tract_figures import (  # noqa: E402
    _alpha_pixels,
    _only_layer,
    _pixel_hausdorff,
    _pixels,
)

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "velic_contrast.json"


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        pins = {}
        for nasal, oral in (("m", "b"), ("n", "d"), ("ŋ", "k")):
            width, nasal_rows = _pixels(
                _only_layer(tract_svg.figure(nasal), "velum"), temp / f"{nasal}.svg"
            )
            _, oral_rows = _pixels(
                _only_layer(tract_svg.figure(oral), "velum"), temp / f"{oral}.svg"
            )
            pins[f"{nasal}-{oral}"] = round(
                _pixel_hausdorff(
                    _alpha_pixels(width, nasal_rows), _alpha_pixels(width, oral_rows)
                ),
                2,
            )

    OUT.write_text(
        json.dumps(pins, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {OUT}: {pins}")


if __name__ == "__main__":
    main()
