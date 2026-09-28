"""Library-visible warning classification shared with the command line."""

from __future__ import annotations

import warnings
from collections.abc import Iterable
from pathlib import Path

from ._convert import InputLossWarning
from .distance_model import UnusableReferenceWarning

_PACKAGE = Path(__file__).resolve().parent


def _fold(caught: Iterable[warnings.WarningMessage]) -> list[str]:
    """Fold repeated warning messages while preserving their first order."""
    counts: dict[str, int] = {}
    for entry in caught:
        text = str(entry.message)
        counts[text] = counts.get(text, 0) + 1
    return [
        text if count == 1 else f"{text} [{count} times]"
        for text, count in counts.items()
    ]


def input_reports(caught: Iterable[warnings.WarningMessage]) -> list[str]:
    """Return typed input-loss reports, wherever the warning points.

    An untyped ``UserWarning`` raised from inside ipakit also counts. Declared
    non-input warnings do not, nor do untyped warnings originating outside the
    package.
    """
    reports = []
    for entry in caught:
        if not issubclass(entry.category, UserWarning):
            continue
        if issubclass(entry.category, UnusableReferenceWarning):
            continue
        try:
            inside = Path(entry.filename).resolve().is_relative_to(_PACKAGE)
        except (OSError, ValueError):  # pragma: no cover - unparseable path
            inside = False
        if not issubclass(entry.category, InputLossWarning) and not inside:
            continue
        reports.append(entry)
    return _fold(reports)


def degraded_reports(caught: Iterable[warnings.WarningMessage]) -> list[str]:
    """Return messages saying a reference cannot support usable positions."""
    return _fold(
        entry
        for entry in caught
        if issubclass(entry.category, UnusableReferenceWarning)
    )
