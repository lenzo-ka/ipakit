"""Tests for the consistent ``strict`` error policy across converters (I12).

Every converter skips unconvertible input by default and raises
``ValueError`` when called with ``strict=True``.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable

import ipakit
import pytest
from ipakit import CMUMapper, IPAFeatures


class TestDefaultSkips:
    """Default behavior is unchanged: unconvertible symbols are skipped."""

    def test_converters_skip_by_default(self) -> None:
        assert ipakit.to_cmu("k4t") == ["K", "T"]
        assert ipakit.from_cmu(["K", "ZZ", "T"]) == "kt"
        assert ipakit.to_timit("k4t") == ["k", "t"]
        assert ipakit.from_timit(["k", "zz", "t"]) == "kt"
        assert ipakit.to_kirshenbaum("k4t") == "kt"
        assert ipakit.from_kirshenbaum("kπt") == "kt"
        assert ipakit.from_xsampa("pπ") == "p"
        assert ipakit.to_xsampa("p4") == "p"


class TestStrictRaises:
    """strict=True raises ValueError naming the unconvertible symbols."""

    @pytest.mark.parametrize(
        "call",
        [
            lambda: ipakit.to_cmu("k4t", strict=True),
            lambda: ipakit.from_cmu(["K", "ZZ", "T"], strict=True),
            lambda: ipakit.to_timit("k4t", strict=True),
            lambda: ipakit.from_timit(["k", "zz", "t"], strict=True),
            lambda: ipakit.to_kirshenbaum("k4t", strict=True),
            lambda: ipakit.from_kirshenbaum("kπt", strict=True),
            lambda: ipakit.from_xsampa("pπ", strict=True),
            lambda: ipakit.to_xsampa("p4", strict=True),
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
        assert ipakit.from_cmu(["K", "AE1", "T"], strict=True) == "kˈæt"
        assert ipakit.to_xsampa("t͡ʃ", strict=True) == "t_S"
        assert ipakit.from_xsampa("t_S", strict=True) == "t͡ʃ"


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
            ipa.to_xsampa("p4", strict=True)
        with pytest.raises(ValueError):
            ipa.from_xsampa("pπ", strict=True)


_WHOLE_CONVERSION_CASES = (
    (
        ipakit.to_xsampa,
        "IPA -> X-SAMPA",
        {
            "kæt.dɒɡ": set(),
            "a∅b": {"∅"},
            "ᵐb": {"ᵐ"},
            "..##": set(),
        },
    ),
    (
        ipakit.to_timit,
        "IPA -> timit",
        {
            "kæt.dɒɡ": {".", "ɒ"},
            "a∅b": {"a", "∅"},
            "ᵐb": {"ᵐ"},
            "..##": {".", "#"},
        },
    ),
    (
        ipakit.to_kirshenbaum,
        "IPA -> kirshenbaum",
        {
            "kæt.dɒɡ": {"."},
            "a∅b": {"∅"},
            "ᵐb": {"ᵐ"},
            "..##": {".", "#"},
        },
    ),
    (
        ipakit.to_cmu,
        "to CMU ARPABET",
        {
            "kæt.dɒɡ": {".", "ɒ"},
            "a∅b": {"a", "∅"},
            "ᵐb": {"ᵐ"},
            "..##": {".", "#"},
        },
    ),
)


def _reported_offenders(source: str, offenders: set[str], frame: str) -> list[str]:
    """The exact order each converter promises for its loss report."""

    if frame in {"IPA -> timit", "IPA -> kirshenbaum"}:
        return list(dict.fromkeys(symbol for symbol in source if symbol in offenders))
    return sorted(offenders)


@pytest.mark.parametrize("converter,frame,cases", _WHOLE_CONVERSION_CASES)
def test_strict_diagnostics_name_the_complete_offender_set(
    converter: Callable[..., object], frame: str, cases: dict[str, set[str]]
) -> None:
    for source, offenders in cases.items():
        if not offenders:
            converter(source, strict=True)
            continue
        expected = (
            f"Cannot convert {frame}: unknown symbols "
            f"{_reported_offenders(source, offenders, frame)!r}"
        )
        with pytest.raises(ValueError) as caught:
            converter(source, strict=True)
        assert str(caught.value) == expected


@pytest.mark.parametrize("converter,frame,cases", _WHOLE_CONVERSION_CASES)
def test_lossy_diagnostics_warn_once_in_the_converter_callers_frame(
    converter: Callable[..., object], frame: str, cases: dict[str, set[str]]
) -> None:
    for source, offenders in cases.items():
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            converter(source)
        assert len(caught) == (1 if offenders else 0)
        if offenders:
            warning = caught[0]
            assert warning.filename == __file__
            assert repr(_reported_offenders(source, offenders, frame)) in str(
                warning.message
            )
            assert f"converting {frame}:" in str(warning.message)
            assert "while parsing IPA" not in str(warning.message)
