"""The tutorial notebook, and how a reader gets a copy of it.

``ipakit/notebooks/ipakit-tutorial.ipynb`` is a rendering of
``docs/tutorial.src.md``, written by ``scripts/tutorial.py`` and checked
in beside the data. It ships in the wheel, so the one thing a student
needs after ``pip install ipakit`` is a way to get it out of
``site-packages`` and into a directory they can work in. That is the
whole of this module: a copy, and a path.

Copying rather than opening a stream keeps the promise the file makes
about itself. The notebook carries no outputs and no execution counts,
which is what lets ``make check`` compare it byte for byte against a
fresh render; a writer that rebuilt it here could hand out something the
check never saw.
"""

from __future__ import annotations

import shutil
from pathlib import Path

#: The shipped notebook. The name it has in the package is the name it
#: lands under, so "the file I was given" and "the file the wheel carries"
#: are one thing to compare rather than two to keep in step.
NOTEBOOK = Path(__file__).parent / "notebooks" / "ipakit-tutorial.ipynb"


def notebook(dest: str | Path = ".", *, force: bool = False) -> Path:
    """Write the tutorial notebook into *dest* and return the path written.

    *dest* is a directory; it is created if it does not exist. An
    existing notebook is left alone and :exc:`FileExistsError` raised
    unless *force* is given, because the copy a reader has been working
    in is worth more than the pristine one.
    """
    directory = Path(dest)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / NOTEBOOK.name
    if target.exists() and not force:
        raise FileExistsError(f"{target} already exists")
    shutil.copyfile(NOTEBOOK, target)
    return target
