#!/usr/bin/env python3
"""Capture the golden mid-sagittal SVG for every registered phone.

This freezes the *current* (pre-refactor) output of
``render(drawing(head, phone))`` so the posture-vector split (H0.1) can be
proved byte-identical. The split moves ``drawing`` from one step to two --
``posture(features, phone)`` then ``build_geometry(head, marks, posture)`` --
and ``tests/test_posture_no_side_channel.py`` asserts the redrawn bytes still
equal what is captured here.

Run it from the repo root to (re)write ``tests/fixtures/posture_golden.json``:

    python tests/fixtures/_capture_posture_golden.py

The map is ``{phone: svg}`` over ``IPAFeatures().phones``, plus the reference
drawing (``phone=None``) under ``REFERENCE_KEY``. The head is the one
``heads.xml`` declares as default -- the same head ``make figures`` draws --
so the twelve per-phone figures and the reference under ``docs/figures`` are
reproduced byte-for-byte by their entries here.

The output is independent of ``PYTHONHASHSEED``: ``make figures`` does not pin
it and checks the drawn bytes into the tree, so the drawing cannot depend on
hash order. Nothing is pinned here for the same reason.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Runnable from the repo root without an install: the package sits two levels
# up from tests/fixtures/, and scripts/tract_svg.py does the same to draw.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from ipakit.features import IPAFeatures  # noqa: E402
from ipakit.tract import head  # noqa: E402
from ipakit.tract_svg import drawing, render  # noqa: E402

# A key for the phone=None reference drawing. NUL is not a phone in any
# inventory, so it cannot collide with a real entry in the map.
REFERENCE_KEY = "\x00"

GOLDEN_PATH = Path(__file__).resolve().parent / "posture_golden.json"


def capture(features: IPAFeatures | None = None) -> dict[str, str]:
    """The golden ``{phone: svg}`` map, reference included, for one inventory."""
    ipa = features or IPAFeatures()
    name = head().name
    golden: dict[str, str] = {
        REFERENCE_KEY: render(drawing(name, None, ipa)),
    }
    for phone in ipa.phones:
        golden[phone] = render(drawing(name, phone, ipa))
    return golden


def main() -> int:
    golden = capture()
    text = json.dumps(golden, ensure_ascii=False, indent=0, sort_keys=True) + "\n"
    GOLDEN_PATH.write_text(text, encoding="utf-8")
    phones = len(golden) - 1  # less the reference
    print(f"wrote {GOLDEN_PATH}: {phones} phones + reference, {len(text)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
