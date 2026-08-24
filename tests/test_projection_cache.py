"""Content-keyed containment projection caching contracts."""

import pytest
from ipakit import IPAFeatures
from ipakit._containment_projection import (
    ContainmentProjection,
    ContainmentProjectionInput,
    _projection_cache_clear,
    _projection_cache_info,
)
from ipakit._graph_facts import Declarations


def test_equal_forms_share_projection_without_sharing_form(ipa: IPAFeatures) -> None:
    _projection_cache_clear()
    first = ipa.read("kæt")
    second = ipa.read("kæt")

    assert first is not second
    assert first.segments == second.segments
    assert first.units == second.units
    hits, misses, size, _ = _projection_cache_info()
    assert hits >= 1
    assert misses >= 1
    assert size == 1


def test_different_content_does_not_collide(ipa: IPAFeatures) -> None:
    _projection_cache_clear()

    assert ipa.read("kæt").segments != ipa.read("dɒɡ").segments
    hits, misses, size, _ = _projection_cache_info()
    assert hits == 0
    assert misses == 2
    assert size == 2


def test_unreferenced_event_tier_does_not_collide() -> None:
    _projection_cache_clear()
    declarations = Declarations((), (), ())
    first_input = ContainmentProjectionInput((), declarations, (), {}, {}, {}, (), ())
    second_input = ContainmentProjectionInput(
        (), declarations, (), {"unreferenced": "extra"}, {}, {}, (), ()
    )

    first = ContainmentProjection.from_input(first_input)
    second = ContainmentProjection.from_input(second_input)

    assert first.event_tiers == {}
    assert second.event_tiers == {"unreferenced": "extra"}
    assert second is not first


def test_read_diagnostics_are_never_cached(ipa: IPAFeatures) -> None:
    for _ in range(2):
        with pytest.warns(UserWarning):
            ipa.read("k4t")
        with pytest.raises(ValueError):
            ipa.read("k4t", strict=True)
