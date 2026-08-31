"""The three Spearman implementations must agree about ties.

`interop.py`, `perceptual_validation.py` and `areafunctions.py` each carry
a rank function. Two averaged tied ranks and one did not, so `interop`
printed a rho computed over an ordering the data does not carry -- and it
is fed every pairwise phone distance, which is tied by construction.

Agreement is asserted rather than shared, because a shared helper would
satisfy this test and so would three correct copies. What must not happen
again is that they diverge without anything saying so.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rankers():
    interop = _load("interop")
    perceptual = _load("perceptual_validation")
    return {
        "interop": interop._ranks,
        "perceptual_validation": perceptual._ranks,
    }


@pytest.mark.parametrize(
    "values",
    [
        [1.0, 1.0, 1.0, 2.0, 2.0, 3.0],
        [0.0, 0.0, 0.0, 0.0],
        [3.0, 1.0, 2.0],
        [0.5, 0.5, 0.1, 0.9, 0.5],
    ],
    ids=["heavy ties", "all tied", "no ties", "mixed"],
)
def test_every_ranker_averages_ties_the_same_way(values) -> None:
    produced = {name: list(rank(list(values))) for name, rank in _rankers().items()}
    reference = produced["perceptual_validation"]
    for name, ranks in produced.items():
        assert ranks == reference, (name, ranks, reference)


def test_a_tie_does_not_get_an_invented_ordering() -> None:
    """The discriminating case: tied values must share one rank. A ranker
    that assigns them distinct ranks by sort position passes every
    no-ties test and is wrong on the data these scripts actually see."""
    for name, rank in _rankers().items():
        ranks = list(rank([5.0, 5.0, 5.0]))
        assert len(set(ranks)) == 1, (name, ranks)
