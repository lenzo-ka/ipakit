"""The XRMB anchor lane remains testable without licensed corpus data."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/anchor_study.py"
FIXTURE = ROOT / "tests/fixtures/xrmb_anchor_prompts.json"


def _module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("anchor_study", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_prompt_fixture_is_narrow_and_cites_public_handbook() -> None:
    payload = json.loads(FIXTURE.read_text())
    assert set(payload["tasks"]) == {"002", "007"}
    assert {row["type"] for row in payload["tasks"].values()} == {
        "citation-words",
        "sentences",
    }
    assert payload["provenance"]["url"].startswith("https://")


def test_absent_corpus_is_successful_and_explanatory(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--corpus", str(tmp_path / "absent")],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert "external licensed data is not bundled" in result.stdout


def test_timestamp_reader_uses_missing_sentinel_and_asserts_shape(
    tmp_path: Path,
) -> None:
    module = _module()
    short = tmp_path / "short.txy"
    short.write_text("0\t" + "\t".join(["1000000"] * 16) + "\n")
    with pytest.raises(ValueError, match="read only 1 usable rows"):
        module.read_timed_frames(short)


def test_anchor_fraction_metric_is_untouched() -> None:
    module = _module()
    token = module.Token("JW00", "002", "p", "bilabial-stop", 1.0, 0.2, 1.05)
    assert token.fraction == pytest.approx(0.25)


def test_classification_covers_declared_observables() -> None:
    module = _module()
    assert module._classify("p") == "bilabial-stop"
    assert module._classify("n") == "alveolar-nasal"
    assert module._classify("ɛ") == "vowel"
    assert module._classify("k") is None
