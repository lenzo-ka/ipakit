"""Bundles differ if and only if the distance does -- for DISTINCTIVE differences.

The principle is that a feature which distinguishes nothing is not
distinctive, so a pair whose bundles differ while their distance is zero
attacks the feature system itself. Stated bare, that is false here, and
measurably: 47 registered pairs differ in a bundle and score zero.

Secondary-place and bridge restatements are absorbed by the feature read, so
``ɡˠ`` and ``m̃`` no longer need exceptions here.  The spelling remains on
the structured segment.  The remaining free bundle differences are marks
which make an imputed articulator explicit: ``d̺`` states the tongue-tip
articulator that ``d`` already gets from its place.

What this gate says, then: no registered pair differs in a NON-VACUOUS
feature while scoring zero. That still catches the regression the
principle exists to catch -- a real contrast collapsing to zero -- while
not reporting the 47 as defects every time somebody measures.

That remaining exemption is derived from the absence of an explicit
articulator, not a list of phones.
"""

from __future__ import annotations

import ipakit
import pytest
from ipakit.features import IPAFeatures


def _imputed_articulator(base: dict[str, str], key: str) -> bool:
    """Whether a mark only states the articulator the base leaves imputed."""
    return key == "articulator" and base.get("articulator") is None


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


def _registered_pairs(features: IPAFeatures):
    """Every base and mark the inventory accepts, with both bundles."""
    declared = set(features.features)
    for base in features.phones:
        left = {k: v for k, v in features._get_features(base).items() if k in declared}
        for mark in features.diacritics:
            spelled = base + mark
            if features.validate_ipa(spelled):
                continue
            try:
                right = {
                    k: v
                    for k, v in features._get_features(spelled).items()
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
            if _imputed_articulator(left, key):
                continue
            offenders.append((base, spelled, key))
    assert compared > 500, f"the sweep compared only {compared} pairs"
    assert offenders == [], offenders


def test_only_imputed_articulator_restatements_remain_free(ipa: IPAFeatures) -> None:
    """The narrower exemption describes real pairs, not a hypothetical class.

    If this drops to zero the exemption has stopped applying to anything
    and should be deleted rather than left standing -- an exemption for a
    population that no longer exists is a silence nobody needs.
    """
    exempted = [
        (base, spelled, key)
        for base, spelled, left, right in _registered_pairs(ipa)
        if ipakit.distance(base, spelled) == 0.0
        for key in right
        if left.get(key) != right.get(key) and _imputed_articulator(left, key)
    ]
    assert len(exempted) > 20, f"only {len(exempted)} imputed pairs found"
    spellings = {spelled for _, spelled, _ in exempted}
    assert "d̺" in spellings
    assert not {"ɡˠ", "cʲ", "m̃"} & spellings
