"""Regenerate deterministic animation render hashes.

Run from the repository root:

    PYTHONHASHSEED=0 python tests/fixtures/_capture_animation_sha256.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from ipakit.tract_svg import animate  # noqa: E402

OUTPUT = Path(__file__).with_name("animation_sha256.json")
WORDS = ("sũn", "ˈkæt")


def main() -> None:
    hashes = {
        word: hashlib.sha256(animate(word).encode()).hexdigest() for word in WORDS
    }
    OUTPUT.write_text(json.dumps(hashes, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
