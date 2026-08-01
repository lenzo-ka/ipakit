#!/usr/bin/env python3
"""The tract renderer moved into the package; this is the old way in.

``ipakit.tract_svg`` is the drawing code. It lives in the package because
``scripts/`` ships in neither the wheel nor the sdist's importable half, so
while it lived here ``pip install ipakit`` got the tract model with no way
to draw it -- the classroom's headline figure, unreachable from an install.

Nothing is reimplemented here. This file is the command line kept working
for ``make figures`` and for anyone with the old invocation in their
fingers; a second copy of the drawing logic is exactly what one place
exists to prevent, and ``tests/test_tract_figures.py`` asserts that this
module defines no drawing of its own.

Equivalent, and preferred:

    python -m ipakit.tract_svg draw --head adult-male -o tract.html
    ipakit tract draw t -o t.svg
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ipakit.tract_svg import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
