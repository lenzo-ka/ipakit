"""The geometry figures ``docs/distance.md`` quotes are the ones the metric gives.

These need numpy, which the ``compare`` extra declares; where it is absent
the module skips, and the CI job that installs ``.[dev]`` runs the same
comparison as ``scripts/geometry.py check``.
"""

import sys
from pathlib import Path

import pytest

pytest.importorskip("numpy")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import geometry  # noqa: E402


@pytest.fixture(scope="module")
def measured() -> dict[str, object]:
    return geometry.measure()


def test_every_quoted_figure_is_the_measured_one(measured):
    assert (
        geometry.differences(measured, geometry.DOC.read_text(encoding="utf-8")) == []
    )


def test_a_stale_figure_is_named(measured):
    document = geometry.DOC.read_text(encoding="utf-8")
    stale = document.replace(
        f"negative eigenvalue mass                {measured['negative eigenvalue mass']}",
        "negative eigenvalue mass                99.9%",
    )
    assert stale != document, "the doctoring found nothing to change"
    problems = geometry.differences(measured, stale)
    assert problems == [
        f"negative eigenvalue mass: the document says '99.9%', "
        f"measured {measured['negative eigenvalue mass']!r}"
    ]


def test_a_figure_dropped_from_the_quote_is_named(measured):
    document = geometry.DOC.read_text(encoding="utf-8")
    line = next(line for line in document.splitlines() if line.startswith("phones  "))
    problems = geometry.differences(measured, document.replace(line + "\n", ""))
    assert problems == ["phones: measured but not quoted"]
