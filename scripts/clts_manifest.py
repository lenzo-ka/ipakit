#!/usr/bin/env python3
"""Regenerate the final CLTS core-BIPA receipt without loading pyclts."""

from __future__ import annotations

import argparse
from pathlib import Path

from ipakit._clts_profile import dumps_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rendered = dumps_manifest()
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
