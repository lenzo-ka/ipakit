"""Tests for the consistent ``strict`` error policy across converters (I12).

Every converter skips unconvertible input by default (backward compatible) and
raises ``ValueError`` when called with ``strict=True``.
"""

from __future__ import annotations

import ipakit
import pytest
from ipakit import CMUMapper, IPAFeatures


class TestDefaultSkips:
    """Default behavior is unchanged: unconvertible symbols are skipped."""

    def test_converters_skip_by_default(self) -> None:
        assert ipakit.to_cmu("k4t") == ["K", "T"]
        assert ipakit.to_ipa(["K", "ZZ", "T"]) == "kt"
        assert ipakit.to_timit("k4t") == ["k", "t"]
        assert ipakit.from_timit(["k", "zz", "t"]) == "kt"
        assert ipakit.to_kirshenbaum("k4t") == "kt"
        assert ipakit.from_kirshenbaum("kπt") == "kt"
        assert ipakit.xsampa_to_ipa("pπ") == "p"
        assert ipakit.ipa_to_xsampa("p4") == "p"


class TestStrictRaises:
    """strict=True raises ValueError naming the unconvertible symbols."""

    @pytest.mark.parametrize(
        "call",
        [
            lambda: ipakit.to_cmu("k4t", strict=True),
            lambda: ipakit.to_ipa(["K", "ZZ", "T"], strict=True),
            lambda: ipakit.to_timit("k4t", strict=True),
            lambda: ipakit.from_timit(["k", "zz", "t"], strict=True),
            lambda: ipakit.to_kirshenbaum("k4t", strict=True),
            lambda: ipakit.from_kirshenbaum("kπt", strict=True),
            lambda: ipakit.xsampa_to_ipa("pπ", strict=True),
            lambda: ipakit.ipa_to_xsampa("p4", strict=True),
        ],
    )
    def test_strict_raises_value_error(self, call) -> None:  # type: ignore[no-untyped-def]
        with pytest.raises(ValueError, match="Cannot convert"):
            call()

    def test_error_lists_unknown_symbols(self) -> None:
        with pytest.raises(ValueError, match=r"unknown symbols \['4'\]"):
            ipakit.to_cmu("k4t", strict=True)

    def test_strict_passes_for_valid_input(self) -> None:
        # No unconvertible symbols -> strict must not raise.
        assert ipakit.to_cmu("ˈkæt", strict=True) == ["K", "AE1", "T"]
        assert ipakit.to_ipa(["K", "AE1", "T"], strict=True) == "kˈæt"
        assert ipakit.ipa_to_xsampa("t͡ʃ", strict=True) == "t_S"
        assert ipakit.xsampa_to_ipa("t_S", strict=True) == "t͡ʃ"


class TestStrictOnClasses:
    """strict is available on the class-based converters too."""

    def test_cmu_mapper(self) -> None:
        m = CMUMapper()
        with pytest.raises(ValueError):
            m.ipa_to_cmu("k4t", strict=True)
        with pytest.raises(ValueError):
            m.cmu_to_ipa(["K", "ZZ"], strict=True)

    def test_ipafeatures_xsampa(self) -> None:
        ipa = IPAFeatures()
        with pytest.raises(ValueError):
            ipa.ipa_to_xsampa("p4", strict=True)
        with pytest.raises(ValueError):
            ipa.xsampa_to_ipa("pπ", strict=True)
