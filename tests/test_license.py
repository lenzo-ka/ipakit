"""The license in ``ipa.xml`` is the repository license, still.

``ipa.xml`` is the most copyable thing here. It is the inventory, the feature
declarations and the reasoning together in one document, and it reads perfectly
well with no package around it -- which is exactly why it carries its own
``<license>`` rather than relying on a sibling ``LICENSE`` file that a copy
would leave behind.

That puts the same license in two places, and two copies of anything is what
this repository drifts on. ``docs/reviewing.md`` is a record of that shape:
prose and data that agreed when written and quietly stopped agreeing. So the
second copy is only safe if something compares them, and this is that
something.

Whitespace is normalized because the XML copy is indented to sit inside its
element and the file copy is not. Nothing else is forgiven -- a changed year, a
changed holder or a reworded clause fails here.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import ipakit

ROOT = Path(__file__).resolve().parent.parent
LICENSE = ROOT / "LICENSE"


def _lines(text: str) -> list[str]:
    """The license as comparable lines, indentation and blank runs removed."""
    return [stripped for line in text.splitlines() if (stripped := line.strip())]


def _element() -> ET.Element:
    """The ``<license>`` element of the shipped ``ipa.xml``.

    Read through ``DATA_DIR`` rather than the checkout, so this asks the file
    that actually travels in the wheel -- which is the copy the license is
    there to accompany.
    """
    tree = ET.parse(ipakit.DATA_DIR / "ipa.xml")
    found = tree.getroot().find("license")
    assert found is not None, "ipa.xml declares no <license>"
    return found


class TestTheDataCarriesItsLicense:
    def test_ipa_xml_declares_a_license(self) -> None:
        assert _element().text, "<license> is present but empty"

    def test_the_embedded_license_is_the_repository_license(self) -> None:
        """The two copies say the same thing, clause for clause."""
        embedded = _lines(_element().text or "")
        canonical = _lines(LICENSE.read_text(encoding="utf-8"))
        assert embedded == canonical, (
            "ipa.xml's <license> and the repository LICENSE have diverged; "
            "they are one license written twice and must be edited together"
        )

    def test_the_spdx_identifier_names_the_license_that_follows(self) -> None:
        """The short name and the long text are not free to disagree."""
        elem = _element()
        spdx = elem.get("spdx")
        assert spdx, "<license> carries no spdx attribute"
        first = _lines(elem.text or "")[0]
        assert spdx == "BSD-2-Clause"
        assert first.startswith(
            "BSD 2-Clause"
        ), f"spdx says {spdx!r} but the text opens with {first!r}"


class TestTheLicenseCostsTheInventoryNothing:
    def test_the_license_is_not_a_declaration(self) -> None:
        """A license is not phonetics, and must not reach the feature space.

        Every attribute on a declaring element lands in a feature bundle, and a
        bundle key is a term in the metric -- that is measured, not theoretical.
        ``<license>`` sits outside the classes the loader reads, so it declares
        nothing; this asserts that rather than trusting it.
        """
        ipa = ipakit.load_ipa_features()
        assert "license" not in ipa.classes
        for phone in ipa.phones:
            bundle = ipakit.features(phone)
            assert "spdx" not in bundle
            assert "license" not in bundle
