#!/usr/bin/env python3
"""A command line over ``ipakit.tract_svg``, which is where the drawing lives.

The drawing lives in the package because ``scripts/`` ships in neither the
wheel nor the sdist's importable half, and ``pip install ipakit`` has to be
enough to draw -- the classroom's headline figure must not be reachable
only from a source tree.

So nothing is reimplemented here: this file resolves no posture and
computes no geometry, and ``tests/test_tract_figures.py`` asserts that it
defines no drawing of its own. A second copy of the drawing logic is
exactly what one place exists to prevent.

Equivalent, and preferred:

    python -m ipakit.tract_svg draw --head adult-male -o tract.html
    ipakit tract draw t -o t.svg
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ipakit.tract_svg import main

if __name__ == "__main__":
    raise SystemExit(main())
