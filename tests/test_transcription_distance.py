"""Canonical transcription operations and convenience CLI spellings."""

import json
import sys

import ipakit
import ipakit.cli
import pytest
from ipakit.distance_model import DistanceModel

NAMES = (
    "transcription_distance",
    "transcription_similarity",
    "directional_transcription_distance",
    "explain_transcription_distance",
)


@pytest.fixture(scope="module")
def ipa():
    return ipakit.IPAFeatures()


@pytest.mark.parametrize("name", NAMES)
def test_canonical_export_and_strict_refusal(ipa, name):
    assert name in ipakit.__all__
    for surface in (ipa, ipakit):
        with pytest.raises(ValueError):
            getattr(surface, name)("a☃", "a")


def test_transcription_boundary_types_are_graded_without_changing_coverage(ipa):
    result = ipa.transcription_distance("a|a", "a‖a", return_alignment=True)
    assert isinstance(result, ipakit.TranscriptionDistanceResult)
    assert result.edit_cost > 0
    assert result.coverage == 1


@pytest.mark.parametrize("haystack,target", [(["a"], ["a", "a"]), (["a", "a"], ["a"])])
def test_local_sequence_coverage_is_shorter_over_longer(ipa, haystack, target):
    result = ipa.sequence_distance(haystack, target, mode="local")
    assert result.coverage == 0.5


def test_directional_custom_costs_and_model(ipa):
    schedule = ipakit.CostSchedule("drops", {"ə": 0.25}, 1.0)
    result = ipa.directional_transcription_distance(
        "kæt ə", "kæt", delete_cost=schedule, insert_cost=2.0, return_alignment=True
    )
    # The deleted schwa keeps its schedule price; the asserted word margin
    # separately contributes one atomic structural-term mass.
    assert result.edit_cost == pytest.approx(0.25 + 1 / 21)
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
    assert model.directional_transcription_distance(
        "a a", "a"
    ).edit_cost == pytest.approx(0.25 + 1 / 21)
    assert model.directional_transcription_distance(
        "a", "a a"
    ).edit_cost == pytest.approx(2.0 + 1 / 21)


@pytest.mark.parametrize("name", NAMES)
def test_flat_forwarding_uses_canonical_instance_method(monkeypatch, name):
    import inspect

    signature = inspect.signature(getattr(ipakit, name))
    options = {
        key: False
        for key, parameter in signature.parameters.items()
        if parameter.kind == parameter.KEYWORD_ONLY
    }
    if "insert_cost" in options:
        options.update(insert_cost=0.25, delete_cost=0.5)
    seen = []
    sentinel = object()

    class Receiver:
        pass

    receiver = Receiver()

    def operation(*args, **kwargs):
        seen.append((args, kwargs))
        return sentinel

    monkeypatch.setattr(receiver, name, operation, raising=False)
    monkeypatch.setattr(ipakit, "_get_ipa", lambda: receiver)
    assert getattr(ipakit, name)("a a", "a", **options) is sentinel
    assert seen == [(("a a", "a"), options)]


@pytest.mark.parametrize("extra", [[], ["--raw"], ["--explain"]])
def test_cli_convenience_names_share_output(monkeypatch, capsys, extra):
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
        value = json.loads(captured.out)
        assert value["transcription1"] == "a a"
        assert value["transcription2"] == "a"
        outputs.append(value)
    assert outputs[0] == outputs[1] == outputs[2]
