"""Transcription spellings retain established computation and dispatch."""

import inspect
import json
import sys

import ipakit
import ipakit.cli
import pytest
from ipakit.distance_model import DistanceModel

NAMES = (
    ("transcription_distance", "word_distance"),
    ("transcription_similarity", "word_similarity"),
    ("directional_transcription_distance", "directional_word_distance"),
    ("explain_transcription_distance", "explain_word_distance"),
)


@pytest.fixture(scope="module")
def ipa():
    return ipakit.IPAFeatures()


@pytest.mark.parametrize("new,old", NAMES)
def test_exports_and_exact_signatures(new, old):
    assert new in ipakit.__all__ and old in ipakit.__all__
    assert inspect.signature(getattr(ipakit, new)) == inspect.signature(
        getattr(ipakit, old)
    )
    assert inspect.signature(getattr(ipakit.IPAFeatures, new)) == inspect.signature(
        getattr(ipakit.IPAFeatures, old)
    )


@pytest.mark.parametrize(
    "left,right", [("kæt kæd", "kæt kæ"), ("a|a", "a‖a"), ("ka.tə", "kat.ə"), ("", "")]
)
@pytest.mark.parametrize("new,old", NAMES)
def test_raw_old_new_parity(ipa, left, right, new, old):
    options = {"weighted": False, "applicable_only": True}
    if new.endswith("distance") and not new.startswith("explain"):
        options["return_alignment"] = True
    for surface in (ipakit, ipa):
        assert getattr(surface, new)(left, right, **options) == getattr(surface, old)(
            left, right, **options
        )


@pytest.mark.parametrize("new,old", NAMES)
def test_new_mixin_methods_forward_every_option(ipa, monkeypatch, new, old):
    signature = inspect.signature(getattr(ipa, new))
    options = {
        name: False
        for name, parameter in signature.parameters.items()
        if parameter.kind == parameter.KEYWORD_ONLY
    }
    if "insert_cost" in options:
        options.update(insert_cost=0.25, delete_cost=0.5)
    seen = []
    sentinel = object()

    def existing(*args, **kwargs):
        seen.append((args, kwargs))
        return sentinel

    monkeypatch.setattr(ipa, old, existing)
    assert getattr(ipa, new)("a a", "a", **options) is sentinel
    assert seen == [(("a a", "a"), options)]


def test_directional_custom_costs_and_model_parity(ipa):
    schedule = ipakit.CostSchedule("drops", {"ə": 0.25}, 1.0)
    options = dict(delete_cost=schedule, insert_cost=2.0, return_alignment=True)
    assert ipa.directional_transcription_distance(
        "kæt ə", "kæt", **options
    ) == ipa.directional_word_distance("kæt ə", "kæt", **options)
    model = DistanceModel(
        ipa,
        "custom",
        ["a", "t", "p"],
        [[0.0, 1.0, 0.5], [1.0, 0.0, 0.75], [0.5, 0.75, 0.0]],
        "distance",
        gamma=0.5,
        insert_cost=2.0,
        delete_cost=0.25,
    )
    for new, old in NAMES[:3]:
        assert inspect.signature(getattr(model, new)) == inspect.signature(
            getattr(model, old)
        )
        options = {} if new.endswith("similarity") else {"return_alignment": True}
        assert getattr(model, new)("a a", "a", **options) == getattr(model, old)(
            "a a", "a", **options
        )
    assert model.directional_transcription_distance("a a", "a").edit_cost == 0.25
    assert model.directional_transcription_distance("a", "a a").edit_cost == 2.0


@pytest.mark.parametrize("new,old", NAMES)
def test_flat_forwarding_uses_preferred_instance_method(monkeypatch, new, old):
    signature = inspect.signature(getattr(ipakit, new))
    options = {
        name: False
        for name, parameter in signature.parameters.items()
        if parameter.kind == parameter.KEYWORD_ONLY
    }
    if "insert_cost" in options:
        options.update(insert_cost=0.25, delete_cost=0.5)
    seen = []
    sentinel = object()

    class Receiver:
        pass

    receiver = Receiver()

    def preferred(*args, **kwargs):
        seen.append((args, kwargs))
        return sentinel

    monkeypatch.setattr(receiver, new, preferred, raising=False)
    monkeypatch.setattr(ipakit, "_get_ipa", lambda: receiver)
    assert getattr(ipakit, new)("a a", "a", **options) is sentinel
    assert seen == [(("a a", "a"), options)]


@pytest.mark.parametrize("new,old", NAMES)
def test_strict_refusal_preserved(ipa, new, old):
    for surface in (ipa, ipakit):
        with pytest.raises(ValueError):
            getattr(surface, new)("a☃", "a")
        with pytest.raises(ValueError):
            getattr(surface, old)("a☃", "a")


@pytest.mark.parametrize("extra", [[], ["--raw"], ["--explain"]])
def test_cli_new_name_and_old_aliases_share_output(monkeypatch, capsys, extra):
    outputs = []
    for group, command in [
        ("distance", "transcription"),
        ("distance", "word"),
        ("d", "w"),
    ]:
        monkeypatch.setattr(
            sys, "argv", ["ipakit", group, command, "a a", "a", "-j", *extra]
        )
        assert ipakit.cli.main() == 0
        captured = capsys.readouterr()
        assert not captured.err
        outputs.append(json.loads(captured.out))
    assert outputs[0] == outputs[1] == outputs[2]
