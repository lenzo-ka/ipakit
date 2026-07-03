"""Guard: the shipped confusion matrix matches what the metric derives.

The matrix (data/confusion.json) is a committed derived cache of pairwise
feature distances over the full bundled IPA inventory. It must be regenerated
whenever ipa.xml or the distance metric changes; this test fails on drift.
Pure stdlib -- no dev dependency, so it runs in the normal suite.
"""

from __future__ import annotations

import importlib.util
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


def test_validate_subcommand_exit_zero() -> None:
    c = _load_script()
    assert c.main(["validate"]) == 0
