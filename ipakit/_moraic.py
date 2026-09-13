"""Shared, declaration-licensed mora analysis over immutable IPA units."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .features import IPAFeatures
from .form import Unit
from .segment import Kind, Sense

if TYPE_CHECKING:
    from .syllable import Language


@dataclass(frozen=True)
class Mora:
    spelling: str
    children: tuple[int, ...]
    kind: str = "ordinary"
    begins_syllable: bool = True


def vowel_phases(unit: Unit) -> tuple[str, ...]:
    """Read sequential vowel phases; simultaneous timing needs a model."""
    segment = unit.segment
    assert segment is not None
    if any(sense != Sense.SEQ for sense in segment.junctures):
        raise ValueError("mora analysis requires a policy for simultaneous vowel ties")
    if segment.junctures and unit.prosody.get("length") == "long":
        raise ValueError("mora analysis requires a length host for tied vowel phases")
    return tuple(str(part) for part in segment.constituents)


def consonant_hold(unit: Unit, inventory: IPAFeatures) -> str:
    """Preserve the held consonant, with a closure-only affricate first mora."""
    segment = unit.segment
    assert segment is not None
    if not segment.junctures:
        return segment.spelling
    if segment.kind == Kind.AFFRICATE and len(segment.constituents) == 2:
        return str(segment.constituents[0])
    raise ValueError("mora analysis requires a hold policy for this consonant compound")


def analyze_region(
    units: Sequence[Unit],
    start: int,
    stop: int,
    language: Language,
    inventory: IPAFeatures,
    is_nucleus: Callable[[Unit], bool],
) -> tuple[list[Mora], list[tuple[int, int]]]:
    """License spans and associate geminates with coda and following onset.

    Unit indices are occurrences, so sharing one index expresses association
    without splitting its source features or inventing physical durations.
    """
    entries: list[Mora] = []
    residue: list[tuple[int, int]] = []
    at = start
    have_nucleus = False
    pending: int | None = None
    while at < stop:
        if units[at].segment is None:
            at += 1
            have_nucleus = False
            pending = None
            continue
        candidate_start = pending if pending is not None else at
        candidates = []
        for span in language.morae:
            end = candidate_start + len(span.terms)
            if (
                end <= stop
                and end > at
                and span.matches(units[candidate_start:end], inventory)
            ):
                nucleus = next(
                    (i for i in range(candidate_start, end) if is_nucleus(units[i])),
                    None,
                )
                candidates.append((end, nucleus))
        weights = [item for item in candidates if item[1] is None]
        nuclei = [item for item in candidates if item[1] is not None]
        long = units[at].prosody.get("length") == "long"
        choices = (
            weights
            if have_nucleus and weights and pending is None and (long or not nuclei)
            else nuclei
        )
        if not choices:
            if pending is not None:
                raise ValueError(
                    "long consonant requires a licensed following onset in this mora model"
                )
            residue.append((at, at + 1))
            at += 1
            have_nucleus = False
            pending = None
            continue
        end, nucleus = max(choices, key=lambda item: item[0])
        children = tuple(range(candidate_start, end))
        if nucleus is not None:
            if any(
                units[i].prosody.get("length") == "long"
                for i in range(candidate_start, nucleus)
                if i != pending
            ):
                raise ValueError(
                    "long consonant requires a preceding nucleus in this mora model"
                )
            phases = vowel_phases(units[nucleus])
            onset = "".join(
                units[i].segment.spelling  # type: ignore[union-attr]
                for i in range(candidate_start, nucleus)
                if units[i].segment is not None
            )
            entries.append(Mora(onset + phases[0], children))
            for phase in phases[1:]:
                entries.append(Mora(phase, (nucleus,), "diphthong-second", False))
            if units[nucleus].prosody.get("length") == "long":
                entries.append(Mora(phases[0], (nucleus,), "long-vowel-second", False))
            pending = None
        else:
            unit = units[at]
            assert unit.segment is not None
            nasal = unit.features.get("manner") == "nasal"
            long = unit.prosody.get("length") == "long"
            kind = "nasal" if nasal else "geminate-half"
            spelling = (
                consonant_hold(unit, inventory) if long else unit.segment.spelling
            )
            entries.append(Mora(spelling, children, kind, False))
            pending = at if long else None
        have_nucleus = True
        at = end
    if pending is not None:
        raise ValueError("long consonant requires a following onset in this mora model")
    return entries, residue
