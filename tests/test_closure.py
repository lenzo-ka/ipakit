"""The metric view, and what it costs.

`distance` is a dissimilarity: symmetric, zero on identity, bounded, and
not subject to the triangle inequality. `MetricClosure` supplies a metric
for callers that need one, and these tests pin both what it gives and
what it takes away -- the second being the reason it is not the default
and not exported at module level.
"""

import itertools

import pytest
from ipakit import IPAFeatures
from ipakit.closure import MetricClosure, metric_closure


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


@pytest.fixture(scope="module")
def closure(ipa: IPAFeatures) -> MetricClosure:
    return metric_closure(ipa)


class TestItIsAMetric:
    def test_triangle_inequality_holds(self, closure: MetricClosure) -> None:
        sample = closure.phones[:60]
        for a, b, c in itertools.combinations(sample, 3):
            for x, y, z in ((a, b, c), (b, c, a), (c, a, b)):
                assert closure.distance(x, z) <= (
                    closure.distance(x, y) + closure.distance(y, z) + 1e-9
                ), (x, y, z)

    def test_symmetry_and_identity(self, closure: MetricClosure) -> None:
        for phone in closure.phones:
            assert closure.distance(phone, phone) == 0.0
        for a, b in itertools.combinations(closure.phones[:40], 2):
            assert closure.distance(a, b) == closure.distance(b, a)

    def test_never_exceeds_the_distance_it_closes(
        self, ipa: IPAFeatures, closure: MetricClosure
    ) -> None:
        # The closure is the largest metric under the open distance, so a
        # pair can only move closer, never further.
        for a, b in itertools.combinations(closure.phones[:40], 2):
            assert closure.distance(a, b) <= ipa.distance(a, b) + 1e-9


class TestWhatItCosts:
    """Why this is opt-in. A shortcut through a third phone is not
    evidence that the endpoints are alike."""

    def test_it_shortens_a_fifth_of_the_inventory(
        self, ipa: IPAFeatures, closure: MetricClosure
    ) -> None:
        moved = closure.shortened(ipa)
        total = len(closure.phones) * (len(closure.phones) - 1) // 2
        assert 0.1 < len(moved) / total < 0.4

    def test_the_largest_shortcuts_join_unlike_segments(
        self, ipa: IPAFeatures, closure: MetricClosure
    ) -> None:
        # A voiced velar plosive and a voiced labiodental affricate are
        # not alike; the cheap path runs through a double articulation
        # that shares a different constituent with each.
        assert ipa.distance("ɡ", "b͡v") > 0.25
        assert closure.distance("ɡ", "b͡v") < 0.1

    def test_the_diagnostic_reports_the_damage(
        self, ipa: IPAFeatures, closure: MetricClosure
    ) -> None:
        moved = closure.shortened(ipa)
        assert moved
        for a, b, opened, closed in moved:
            assert closed < opened
            assert opened == ipa.distance(a, b)


class TestItIsDeliberatelyHardToReachForByAccident:
    def test_not_in_the_module_namespace(self) -> None:
        import ipakit

        assert "metric_closure" not in ipakit.__all__
        assert not hasattr(ipakit, "metric_closure")

    def test_out_of_inventory_raises_rather_than_falling_back(
        self, closure: MetricClosure
    ) -> None:
        # Falling back to the open distance would silently break the one
        # property the closure exists to provide.
        with pytest.raises(KeyError, match="not in this closure"):
            closure.distance("q͡χ", "p")

    def test_a_restricted_inventory_is_its_own_closure(self, ipa: IPAFeatures) -> None:
        # Inventory-relative by construction: fewer intermediates, fewer
        # shortcuts, so the same pair can be further apart.
        small = metric_closure(ipa, ["ɡ", "b͡v", "p", "t"])
        full = metric_closure(ipa)
        assert small.distance("ɡ", "b͡v") > full.distance("ɡ", "b͡v")
