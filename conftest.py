"""Pytest configuration shared across the suite.

Makes ``ipakit`` available inside doctests so module docstring examples
(``>>> ipakit.describe("p")``) execute under ``--doctest-modules``.

Also provides shared, session-scoped ``ipa`` and ``mapper`` fixtures. Both
``IPAFeatures`` and ``CMUMapper`` parse XML on construction; building them once
per session (rather than once per test) keeps the suite fast. The instances are
treated as read-only by the tests, so sharing them across tests is safe.
"""

import pytest
from ipakit import CMUMapper, IPAFeatures


@pytest.fixture(autouse=True)
def _doctest_ipakit(doctest_namespace):  # type: ignore[no-untyped-def]
    import ipakit

    doctest_namespace["ipakit"] = ipakit


@pytest.fixture(scope="session")
def ipa() -> IPAFeatures:
    """Shared, read-only IPA feature inventory."""
    return IPAFeatures()


@pytest.fixture(scope="session")
def mapper() -> CMUMapper:
    """Shared, read-only CMU/ARPAbet mapper."""
    return CMUMapper()
