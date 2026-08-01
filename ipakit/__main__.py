"""``python -m ipakit`` -- the same command line as the ``ipakit`` script.

The console entry point and ``python -m ipakit.cli`` both already ran
:func:`ipakit.cli.main`; the package itself did not, so the obvious
invocation failed with "No module named ipakit.__main__". A reader who
has not installed the script, or who wants a particular interpreter's
copy, types this one -- ``scripts/tutorial.py`` is such a reader, and so
is anyone following the README from a checkout.

Nothing is re-implemented here: the whole file is the dispatch, so the
two spellings cannot come to mean different things.
"""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
