"""Katakana rendering of attested gairaigo adaptations on the mora tier.

This codec describes forms Japanese licenses; it is not an accent simulator.
"""

from __future__ import annotations

from .bridges.kana import KANA


def render(form: object) -> str:
    return KANA.render(form)
