"""Strict occurrence syntax is independent of resolution and native IPA."""

import pytest
from ipakit._clts_input import FORMAT, HOST, InputError, decode


def document(tokens, **fields):
    return {"format": FORMAT, "version": 1, "tokens": tokens, **fields}


def test_shorthand_and_optional_presence():
    assert decode(["t͜s", "é", "é", "t͜s"]) == document(
        [{"raw": "t͜s"}, {"raw": "é"}, {"raw": "é"}, {"raw": "t͜s"}]
    )
    assert decode([]) == document([])
    assert decode(document([], relations=[])) == document([], relations=[])


def test_raw_must_be_utf8_encodable():
    with pytest.raises(InputError) as caught:
        decode(document([{"raw": "\ud800"}]))
    assert caught.value.code == "invalid-input"
    assert caught.value.path == "/tokens/0/raw"


@pytest.mark.parametrize(
    "value",
    [
        None,
        {},
        "abc",
        [None],
        [""],
        document(
            {},
        ),
        document([], extra=True),
        {"format": FORMAT, "version": True, "tokens": []},
        document([{"raw": "a", "extra": 1}]),
    ],
)
def test_invalid_input(value):
    with pytest.raises(InputError):
        decode(value)


@pytest.mark.parametrize(
    "timing",
    [
        None,
        {},
        {"start": 0},
        {"duration": 1},
        {"start": 0, "duration": 1, "end": 1},
        {"start": True, "duration": 1},
        {"start": 0, "duration": False},
        {"start": -1, "duration": 1},
        {"start": 0, "duration": -1},
        {"start": float("inf"), "duration": 1},
        {"start": 0, "duration": float("nan")},
    ],
)
def test_invalid_timing(timing):
    with pytest.raises(InputError) as caught:
        decode(document([{"raw": "a", "time": timing}]))
    assert caught.value.code == "invalid-timing"
    assert caught.value.path == "/tokens/0/time"


def test_times_do_not_sort_or_reject_overlap():
    value = document(
        [
            {"raw": "a", "time": {"start": 2, "duration": 0}},
            {"raw": "b", "time": {"start": 0, "duration": 3}},
        ]
    )
    assert decode(value) == value


def test_unrepresentably_large_time_refuses_as_timing():
    with pytest.raises(InputError) as caught:
        decode(document([{"raw": "a", "time": {"start": 10**400, "duration": 0}}]))
    assert caught.value.code == "invalid-timing"


def test_integer_time_must_fit_json_exact_range():
    value = document([{"raw": "a", "time": {"start": 2**53, "duration": 1}}])
    with pytest.raises(InputError) as caught:
        decode(value)
    assert caught.value.code == "invalid-timing"
    assert caught.value.path == "/tokens/0/time"

    boundary = document([{"raw": "a", "time": {"start": 2**53 - 1, "duration": 1}}])
    assert decode(boundary) == boundary


@pytest.mark.parametrize(
    "pointer",
    [
        "/tokens/01",
        "/tokens/-1",
        "/tokens/1.0",
        "/tokens/2",
        "/tokens/٠",
        "/tokens/1/raw",
        "tokens/1",
        True,
    ],
)
def test_bad_endpoint(pointer):
    with pytest.raises(InputError) as caught:
        decode(
            document(
                [{"raw": "a"}, {"raw": "⁵"}],
                relations=[{"type": HOST, "source": pointer, "target": "/tokens/0"}],
            )
        )
    assert caught.value.path == "/relations/0/source"


@pytest.mark.parametrize(
    "relations",
    [
        None,
        {},
        [{"type": "unknown", "source": "/tokens/1", "target": "/tokens/0"}],
        [{"type": HOST, "source": "/tokens/0", "target": "/tokens/0"}],
    ],
)
def test_bad_relations(relations):
    with pytest.raises(InputError):
        decode(document([{"raw": "a"}, {"raw": "⁵"}], relations=relations))


def test_tone_cannot_have_two_hosts():
    relations = [
        {"type": HOST, "source": "/tokens/1", "target": "/tokens/0"},
        {"type": HOST, "source": "/tokens/1", "target": "/tokens/2"},
    ]
    with pytest.raises(InputError) as caught:
        decode(
            document(
                [{"raw": "t"}, {"raw": "⁵"}, {"raw": "a"}, {"raw": "⁵"}],
                relations=relations,
            )
        )
    assert caught.value.code == "invalid-relation"
    assert caught.value.path == "/relations/1/source"


def test_duplicate_host_relation_refuses_at_second_source():
    relation = {"type": HOST, "source": "/tokens/1", "target": "/tokens/0"}
    with pytest.raises(InputError) as caught:
        decode(
            document(
                [{"raw": "t"}, {"raw": "⁵"}],
                relations=[relation, dict(relation)],
            )
        )
    assert caught.value.code == "invalid-relation"
    assert caught.value.path == "/relations/1/source"


def test_two_tones_can_share_one_host():
    value = document(
        [{"raw": "t"}, {"raw": "⁵"}, {"raw": "⁵"}],
        relations=[
            {"type": HOST, "source": "/tokens/1", "target": "/tokens/0"},
            {"type": HOST, "source": "/tokens/2", "target": "/tokens/0"},
        ],
    )
    assert decode(value) == value
