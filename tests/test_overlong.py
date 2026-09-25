"""Written overlong length is a declared point, not repeated long."""

from __future__ import annotations

import warnings

import ipakit
import pytest


def test_written_overlong_has_its_own_length_value() -> None:
    ipa = ipakit.IPAFeatures()

    assert ipa.feature_values("aː")["length"] == ("long",)
    assert ipa.feature_values("aːː")["length"] == ("overlong",)


def test_written_length_prices_are_monotone() -> None:
    short_to_long = ipakit.distance("a", "aː")
    short_to_overlong = ipakit.distance("a", "aːː")
    long_to_overlong = ipakit.distance("aː", "aːː")

    assert short_to_long < short_to_overlong
    assert long_to_overlong > 0.0


def test_three_length_marks_report_the_unrepresentable_excess() -> None:
    ipa = ipakit.IPAFeatures()

    with pytest.warns(UserWarning, match="two marks state 'length'.*not recorded"):
        values = ipa.feature_values("aːːː")
    assert values["length"] == ("overlong",)


def test_overlong_form_round_trips() -> None:
    ipa = ipakit.IPAFeatures()

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        form = ipa.read("saːːt", strict=True)
    assert form.segments[1].prosody == ("ːː",)
    assert form.to_ipa() == "saːːt"


def test_multicharacter_suprasegmental_is_one_longest_match() -> None:
    ipa = ipakit.IPAFeatures()

    assert ipa.tokenize("aːː", strict=True) == ["aːː"]
    assert ipa.segment("aːː", strict=True).prosody == ("ːː",)
    assert ipa.validate_ipa("aːː") == []
