"""Keep fixture provenance labels aligned across public kana surfaces."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "relative",
    [
        "ipakit/data/bridges/kana/kana.xml",
        "ipakit/data/rules/japanese-moraic.rules",
        "ipakit/__init__.py",
        "ipakit/_rewrite_graph.py",
        "ipakit/_katakana_codec.py",
        "ipakit/bridges/kana.py",
        "ipakit/cli/__init__.py",
        "ipakit/cli/convert.py",
        "ipakit/cli/rules.py",
        "docs/kana.md",
        "docs/cli-api-sync.md",
        "docs/systems.md",
        "docs/tutorial.src.md",
        "docs/tutorial.md",
        "ipakit/notebooks/ipakit-tutorial.ipynb",
    ],
)
def test_kana_population_labels_describe_curated_fixtures(relative):
    """Guard the previously unsupported population claims, not attestation talk.

    Dictionary evidence for a named spelling and discussion of the open
    phonetic-attestation audit remain appropriate. These population labels
    would require a separate row-level source audit before adoption.
    """
    text = (ROOT / relative).read_text(encoding="utf-8")
    assert not re.search(
        r"\b(?:attested|established)\s+"
        r"(?:gairaigo|Japanese loanword|Japanese adaptation|loanword adaptation|"
        r"adaptation morae|fixture vocabulary|IPA source|source IPA)",
        text,
        re.IGNORECASE,
    ), relative
