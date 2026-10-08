#!/usr/bin/env python3
"""CLI for the library-owned eSpeak NG vocabulary builder."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ipakit.extraction.espeak import (  # noqa: E402
    ORIGIN as ORIGIN,
)
from ipakit.extraction.espeak import (  # noqa: E402
    PIN as PIN,
)
from ipakit.extraction.espeak import (  # noqa: E402
    REVISION as REVISION,
)
from ipakit.extraction.espeak import (  # noqa: E402
    build as build,
)
from ipakit.extraction.espeak import (  # noqa: E402
    require_pin as require_pin,
)

SUMMARY = ROOT / "docs" / "espeak-vocabularies.md"


def generate(source: Path) -> dict[Path, bytes]:
    """Return repository-absolute artifact paths."""
    return {ROOT / path: content for path, content in build(source).artifacts.items()}


def fetch(source: Path) -> None:
    """Acquire into an absent path, or validate an existing source unchanged."""
    from scripts.dev_sources import acquire_espeak

    acquire_espeak(source)


def main() -> int:
    """Write generated data or check it byte for byte."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("generate", "check"))
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    try:
        if args.fetch:
            fetch(args.source)
        result = build(args.source)
        if args.mode == "generate":
            from scripts.dev_sources import publish

            publish(result, ROOT)
        differences = result.stale(ROOT)
    except (OSError, ValueError) as error:
        print(f"espeak-vocabularies: {error}", file=sys.stderr)
        return 2
    if differences:
        print(
            "espeak-vocabularies: generated artifacts differ: "
            + ", ".join(map(str, differences)),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
