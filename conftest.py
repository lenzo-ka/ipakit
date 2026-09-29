"""Pytest configuration shared across the suite.

Makes ``ipakit`` available inside doctests so module docstring examples
(``>>> ipakit.describe("p")``) execute under ``--doctest-modules``.

Also provides shared, session-scoped ``ipa`` and ``mapper`` fixtures. Both
``IPAFeatures`` and ``CMUMapper`` parse XML on construction; building them once
per session (rather than once per test) keeps the suite fast. The instances are
treated as read-only by the tests, so sharing them across tests is safe.
"""

import os

import pytest
from ipakit import CMUMapper, IPAFeatures


def pytest_collection_modifyitems(items):  # type: ignore[no-untyped-def]
    """Skip source-dependent eSpeak integration tests when no source is supplied."""
    if os.environ.get("IPAKIT_ESPEAK_NG"):
        return
    reason = "set IPAKIT_ESPEAK_NG to run tests requiring eSpeak NG source"
    for item in items:
        path = item.path.name
        if (
            path == "test_espeak_binary.py"
            or (
                path in {"test_bridges.py", "test_inventories.py"}
                and (
                    "espeak" in item.name
                    or item.name == "test_styles_normalize_canonically_equivalent_input"
                )
                and item.name != "test_espeak_requires_user_source"
            )
            or (path == "test_phoneset_comparison.py" and "espeak" in item.nodeid)
        ):
            item.add_marker(pytest.mark.skip(reason=reason))


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
