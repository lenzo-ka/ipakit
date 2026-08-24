"""Katakana rendering of attested gairaigo adaptations on the mora tier.

This codec describes forms Japanese licenses; it is not an accent simulator.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .bridges.kana import KANA

if TYPE_CHECKING:
    from .form import Form


def render(form: Form) -> str:
    return KANA.render(form)
