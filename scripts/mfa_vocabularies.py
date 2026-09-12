#!/usr/bin/env python3
"""Compatibility CLI for the library-owned MFA artifact builder."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ipakit.extraction import BuildResult  # noqa: E402
from ipakit.extraction.mfa import (  # noqa: E402
    PIN as PIN,
)
from ipakit.extraction.mfa import (  # noqa: E402
    REVISION as REVISION,
)
from ipakit.extraction.mfa import (  # noqa: E402
    build,
)
from ipakit.extraction.mfa import (  # noqa: E402
    require_pin as require_pin,
)
from scripts.dev_sources import acquire_mfa, publish  # noqa: E402

DEFAULT_SOURCE = Path(
    os.environ.get("MFA_MODELS", Path.home() / ".cache" / "ipakit" / "mfa-models")
)


def generate(source: Path) -> dict[Path, bytes]:
    """Retain the legacy script's repository-absolute artifact mapping."""
    return {ROOT / path: content for path, content in build(source).artifacts.items()}


def stale(artifacts: Mapping[Path, bytes], root: Path) -> list[Path]:
    """Retain the legacy checker while using the shared result implementation."""
    from ipakit.extraction.mfa import OUT

    relative = {path.relative_to(ROOT): content for path, content in artifacts.items()}
    return BuildResult(relative, (OUT / "*.xml",)).stale(root)


def fetch(source: Path) -> None:
    """Acquire into an absent path, or validate an existing source unchanged."""
    acquire_mfa(source)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("generate", "check"))
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    try:
        if args.fetch:
            fetch(args.source)
        result = build(args.source)
        if args.mode == "generate":
            publish(result, ROOT)
        differences = result.stale(ROOT)
    except (OSError, ValueError) as error:
        print(f"mfa-vocabularies: {error}", file=sys.stderr)
        return 2
    if differences:
        print(
            "mfa-vocabularies: generated artifacts differ: "
            + ", ".join(map(str, differences)),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
