"""Pytest configuration shared across the suite.

Makes ``ipakit`` available inside doctests so module docstring examples
(``>>> ipakit.describe("p")``) execute under ``--doctest-modules``.
"""

import pytest


@pytest.fixture(autouse=True)
def _doctest_ipakit(doctest_namespace):  # type: ignore[no-untyped-def]
    import ipakit

    doctest_namespace["ipakit"] = ipakit
