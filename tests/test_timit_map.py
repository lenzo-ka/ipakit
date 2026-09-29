"""The ipakit-authored TIMIT map and its NISTIR 4930 §4.3 basis."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from scripts import timit_map

ROOT = Path(__file__).resolve().parent.parent
MAP = ROOT / "ipakit" / "data" / "phonemaps" / "timit.xml"

CHANGED = {
    "epi": ("␣", "epenthetic silence"),
    "pcl": ("p̚", "closure interval of p"),
    "bcl": ("b̚", "closure interval of b"),
    "tcl": ("t̚", "closure interval of t"),
    "dcl": ("d̚", "closure interval of d"),
    "kcl": ("k̚", "closure interval of k"),
    "gcl": ("ɡ̚", "closure interval of g"),
    "ux": ("u̟", "fronted u"),
    "ax-h": ("ə̥", "devoiced schwa"),
}


def _shipped_rows() -> dict[str, ET.Element]:
    root = ET.parse(MAP).getroot()
    return {item.get("timit", ""): item for item in root.iterfind(".//map")}


def test_changed_values_transcribe_their_nist_definitions() -> None:
    """Each correction says which §4.3 definition licenses the house IPA."""
    shipped = _shipped_rows()
    assert len(timit_map.TIMIT_ROWS) == len(timit_map.ROWS_BY_LABEL) == 61
    for label, (ipa, definition) in CHANGED.items():
        source = timit_map.ROWS_BY_LABEL[label]
        assert source.ipa == ipa
        assert definition in source.citation
        assert source.citation.startswith("NISTIR 4930 §4.3:")
        assert shipped[label].get("ipa") == ipa
        assert shipped[label].get("note") == source.citation


def test_timit_map_is_ipakit_licensed_and_has_no_ldc_license_reference() -> None:
    """The corpus is not the source or license of ipakit's transcription."""
    contents = MAP.read_text(encoding="utf-8")
    root = ET.fromstring(contents)
    assert root.get("license") == "BSD-2-Clause"
    assert root.get("upstream") == "NISTIR 4930 §4.3"
    assert root.get("upstream-url") == timit_map.SOURCE_URL
    assert "LicenseRef-LDC" not in contents
    assert "LDC93S1" not in contents


def test_generator_check_detects_one_byte_drift(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    """The offline check accepts its bytes and rejects a one-byte edit."""
    output = tmp_path / "timit.xml"
    monkeypatch.setattr(timit_map, "OUTPUT", output)
    output.write_text(timit_map.render(), encoding="utf-8")
    assert timit_map.main(["check"]) == 0
    clean = output.read_bytes()
    output.write_bytes(clean[:-2] + b" \n")
    assert timit_map.main(["check"]) == 1
    assert "generated artifact differs" in capsys.readouterr().err
