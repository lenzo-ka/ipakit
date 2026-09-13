"""Katakana rendering of curated gairaigo fixtures on the mora tier.

The vocabulary supplies local demonstration spellings; phonetic attestation
and whole-sequence phonotactics are separate profile obligations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .bridges.kana import KANA

if TYPE_CHECKING:
    from .form import Form


def render(form: Form) -> str:
    return KANA.render(form)
