"""Bundles differ if and only if the distance does -- for DISTINCTIVE differences.

The principle is that a feature which distinguishes nothing is not
distinctive, so a pair whose bundles differ while their distance is zero
attacks the feature system itself. Stated bare, that is false here, and
measurably: 91 registered pairs differ in a bundle and score zero.

Every one of them is a mark asserting what the base already carries --
``ɡˠ`` is a velar wearing a velar secondary, ``d̺`` states the articulator
``d`` already implies, ``m̃`` nasalizes a nasal. Those are not
counterexamples to the principle. They are cases where the *difference*
is not distinctive, and the principle was always about distinctive ones.

Respellings are operators, which is why the code is right as it stands.
``compose_unit`` is faithful to what it is asked -- ``compose_unit("ɡ",
velarized="+")`` is ``ɡˠ`` -- and returns its input where the base already
carries the value. The vacuity is a fact about the resulting segment's
phonetics, not about the operation, so the narrowing belongs in the
principle rather than in the operator.

What this gate says, then: no registered pair differs in a NON-VACUOUS
feature while scoring zero. That still catches the regression the
principle exists to catch -- a real contrast collapsing to zero -- while
not reporting the 91 as defects every time somebody measures.

Vacuity is derived from declared data, never enumerated, so a supplement
declaring a combination nobody anticipated is covered by the same rule.
"""

from __future__ import annotations

import ipakit
import pytest
from ipakit.features import IPAFeatures


def _vacuous(features: IPAFeatures, base: dict[str, str], key: str, value: str) -> bool:
    """Whether a mark stating ``key=value`` tells this base something new.

    Three shapes, each read from the declaration:

    * A SECONDARY whose declared place the base already constricts at.
      ``ipa.xml`` gives each secondary a ``place`` and
      :attr:`IPAFeatures.secondary_places` reads it back, so ``ɡˠ`` is a
      velar asked to be velar. Combined places expand first, so a
      secondary targeting ``bilabial^palatal`` is vacuous only where the
      base makes both.
    * An ARTICULATOR the base leaves imputed. ``d`` states no
      articulator and ``d̺`` states ``tongue-tip``; the sound is the same
      one, described in more words.
    * NASALIZATION where the base is already nasal, or is silence and so
      has no airflow to route.
    """
    if key == "articulator":
        return base.get("articulator") is None
    if key == "nasalized" and value == "+":
        return base.get("manner") in {"nasal", "silence"}
    if value != "+":
        return False
    target = features.secondary_places.get(key)
    place = base.get("place")
    place_feature = features.features.get("place")
    if target is None or place is None or place_feature is None:
        return False
    return set(place_feature.expand(target)) <= set(place_feature.expand(place))


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


def _registered_pairs(features: IPAFeatures):
    """Every base and mark the inventory accepts, with both bundles."""
    declared = set(features.features)
    for base in features.phones:
        left = {k: v for k, v in features.get_features(base).items() if k in declared}
        for mark in features.diacritics:
            spelled = base + mark
            if features.validate_ipa(spelled):
                continue
            try:
                right = {
                    k: v
                    for k, v in features.get_features(spelled).items()
                    if k in declared
                }
            except Exception:  # noqa: BLE001 - unreadable spellings are not pairs
                continue
            if not right or right == left:
                continue
            yield base, spelled, left, right


def test_a_distinctive_difference_is_never_free(ipa: IPAFeatures) -> None:
    """A pair differing in a feature that distinguishes something scores.

    The sweep is asserted against a floor because a run that compared
    nothing would pass this trivially, and the whole point is that it is
    measured over the registered inventory rather than over examples.
    """
    offenders: list[tuple[str, str, str]] = []
    compared = 0
    for base, spelled, left, right in _registered_pairs(ipa):
        compared += 1
        if ipakit.distance(base, spelled) != 0.0:
            continue
        for key in right:
            if left.get(key) == right.get(key):
                continue
            if _vacuous(ipa, left, key, str(right.get(key))):
                continue
            offenders.append((base, spelled, key))
    assert compared > 500, f"the sweep compared only {compared} pairs"
    assert offenders == [], offenders


def test_the_vacuous_cases_are_still_there_and_still_vacuous(ipa: IPAFeatures) -> None:
    """The exemption describes real pairs, not a hypothetical class.

    If this drops to zero the exemption has stopped applying to anything
    and should be deleted rather than left standing -- an exemption for a
    population that no longer exists is a silence nobody needs.
    """
    exempted = [
        (base, spelled, key)
        for base, spelled, left, right in _registered_pairs(ipa)
        if ipakit.distance(base, spelled) == 0.0
        for key in right
        if left.get(key) != right.get(key)
        and _vacuous(ipa, left, key, str(right.get(key)))
    ]
    assert len(exempted) > 50, f"only {len(exempted)} vacuous pairs found"
    spellings = {spelled for _, spelled, _ in exempted}
    assert {"ɡˠ", "cʲ", "d̺", "m̃"} <= spellings, sorted(spellings)[:12]
