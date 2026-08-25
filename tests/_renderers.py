"""Renderer guards that refuse to silently skip when a renderer is required.

Several figure tests measure a rendered raster or layout, so they need an
external renderer: ``rsvg-convert`` (from ``librsvg2-bin``) for the SVG figures,
``dot`` (from ``graphviz``) for the tiergraph layout. Locally and in the
ordinary CI jobs -- which install no renderer -- those tests skip.

But a check that quietly disappears when its tool is missing leaves a green
suite claiming something nobody measured, which is worse than having no check
at all. This is the same silent-wrong-answer that ``tests/test_schema.py``
refuses for its XML validator. So the dedicated ``render`` CI job installs the
renderers and sets ``REQUIRE_RENDERERS=1``; under that flag a missing renderer
is a hard failure here, not a skip, so the job cannot go green having rendered
nothing.

Two shapes, one policy:

* ``@needs_renderer("rsvg-convert", "...")`` decorates a test.
* ``require_renderer("dot", "...")`` guards inline from a test body.

Both skip when the binary is absent and ``REQUIRE_RENDERERS`` is unset, and
fail when it is set. This is only for renderers; genuinely optional interop
skips (panphon, ICU) stay ordinary skips.
"""

from __future__ import annotations

import functools
import os
import shutil
from collections.abc import Callable
from typing import TypeVar

import pytest

_REQUIRE = "REQUIRE_RENDERERS"

_F = TypeVar("_F", bound=Callable[..., object])


def require_renderer(binary: str, reason: str) -> None:
    """Guard a test body: skip if ``binary`` is absent, or fail when required.

    Call as the first statement of a test that shells out to ``binary``. With
    the binary present this is a no-op. Absent, it skips -- unless
    ``REQUIRE_RENDERERS`` is set, where it fails instead, so the ``render`` job
    never passes a renderer-dependent test it did not actually run.
    """
    if shutil.which(binary) is not None:
        return
    message = f"{binary} not installed: {reason}"
    if os.environ.get(_REQUIRE):
        pytest.fail(f"{message} -- but {_REQUIRE} is set, so this must run")
    pytest.skip(message)


def needs_renderer(binary: str, reason: str) -> Callable[[_F], _F]:
    """Decorator form of :func:`require_renderer`.

    Replaces ``@pytest.mark.skipif(shutil.which(...) is None, ...)``: a plain
    ``skipif`` can only skip, so a required-but-missing renderer would still
    slip past. This runs the guard before the test body instead, composing with
    ``@pytest.mark.parametrize`` and fixtures (the wrapper forwards both).
    """

    def decorate(test: _F) -> _F:
        @functools.wraps(test)
        def wrapper(*args: object, **kwargs: object) -> object:
            require_renderer(binary, reason)
            return test(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorate
