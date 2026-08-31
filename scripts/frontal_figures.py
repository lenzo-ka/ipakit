#!/usr/bin/env python3
"""Regenerate D1 frontal figures.

Outputs under ``docs/figures/`` are checked in for review. Outputs under
``talking-heads/`` are on-demand working artifacts excluded from pinning by
design; that owner working area is not part of the repository's figure set.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ipakit.form import FormBuilder
from ipakit.tract import head, trajectory
from ipakit.tract_svg import animate_two_pane, frontal_figure

FIGURES = Path(__file__).resolve().parent.parent / "docs" / "figures"
TALKING_HEADS = Path(__file__).resolve().parent.parent / "talking-heads"
PHONES: tuple[tuple[str, str | None], ...] = (
    ("frontal-reference.svg", None),
    ("frontal-rest.svg", "␣"),
    ("frontal-t.svg", "t"),
    ("frontal-a.svg", "a"),
    ("frontal-i.svg", "i"),
    ("frontal-m.svg", "m"),
    ("frontal-u.svg", "u"),
)


def main() -> int:
    for filename, phone in PHONES:
        (FIGURES / filename).write_text(frontal_figure(phone) + "\n", encoding="utf-8")
    builder = FormBuilder()
    handles = builder.append_ipa("a")
    for handle, (start, duration) in zip(handles, ((0.0, 0.20),), strict=True):
        builder.attach_timing(handle, start, duration)
    timed = replace(trajectory(builder.build(), head=head(), fps=5), frames_per_unit=1)
    (FIGURES / "two-pane-timed.html").write_text(
        animate_two_pane(timed) + "\n", encoding="utf-8"
    )
    TALKING_HEADS.mkdir(exist_ok=True)
    # This owner working-area output is on demand and deliberately unpinned.
    (TALKING_HEADS / "kaet-two-pane.html").write_text(
        animate_two_pane("kæt", frames_per_unit=12) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
