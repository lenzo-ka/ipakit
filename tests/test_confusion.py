"""Guard: the shipped confusion matrix matches what the metric derives.

The matrix (data/confusion.json) is a committed derived cache of pairwise
feature distances over the full bundled IPA inventory. It must be regenerated
whenever ipa.xml or the distance metric changes; this test fails on drift.
Pure stdlib -- no dev dependency, so it runs in the normal suite.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "confusion.py"


def _load_script():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("confusion", _SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_shipped_confusion_matches_derived() -> None:
    c = _load_script()
    d, s = c.derive(), c.shipped()
    # Metadata must match exactly; the float triangle is compared to a tolerance
    # because last-bit rounding differs across CPython versions (see confusion.py).
    assert d["phones"] == s["phones"]
    assert d["space"] == s["space"]
    assert c.triangles_match(d["triangle"], s["triangle"])


def test_shipped_confusion_matrix_sha256_is_unchanged() -> None:
    confusion = (
        Path(__file__).resolve().parent.parent / "ipakit" / "data" / "confusion.json"
    )
    tracked = confusion.read_bytes()
    shipped = json.loads(tracked)
    assert hashlib.sha256(tracked).hexdigest() == (
        "ad2fa05766bb6641a3a9a595df32699ee732fadb122d7746fdd7071ec02127b5"
    )
    assert len(shipped["phones"]) == 139
    assert len(shipped["triangle"]) == 9591
    assert shipped["metric"] == "afb63270471b8ca8"


def test_validate_subcommand_exit_zero() -> None:
    c = _load_script()
    assert c.main(["validate"]) == 0


def test_shipped_confusion_records_its_feature_space() -> None:
    """The key `phones` cannot stand in for: a bridge or a changed feature
    declaration leaves the phone list byte-identical and moves the values."""
    from ipakit import IPAFeatures
    from ipakit.metric import metric_fingerprint

    c = _load_script()
    s = c.shipped()
    assert s["metric"] == metric_fingerprint(IPAFeatures(), s["phones"])


def test_validate_reports_a_moved_fingerprint(monkeypatch, capsys) -> None:
    """A metric change that happened to leave every cell inside the
    tolerance would pass every other check this script makes."""
    c = _load_script()
    moved = {**c.shipped(), "metric": "0" * 16}
    monkeypatch.setattr(c, "shipped", lambda: moved)
    assert c.main(["validate"]) == 1
    out = capsys.readouterr().out
    assert "fingerprint" in out and "regenerate confusion.json" in out
