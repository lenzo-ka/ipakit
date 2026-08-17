from __future__ import annotations

import pytest
from scripts.piece1_oracle import CONTRACT_MUTATIONS, OracleMismatch, capture, check


def test_piece1_oracle_matches_pre_cutover_bytes_and_contracts() -> None:
    check()
    contracts = capture()["contracts"]
    assert all(
        contracts[name]
        for name in (
            "memoized_units_tuple",
            "memoized_unit_objects",
            "memoized_intervals_tuple",
            "equality",
            "hash",
            "distinct_equality",
            "distinct_hash",
        )
    )
    assert all(contracts["at_object_identity"].values())
    assert contracts["root_spelling"] == "/clock/0/utterance/0"
    assert contracts["wire_type_version"] == ["ipakit.form", 2]


@pytest.mark.parametrize("contract", CONTRACT_MUTATIONS)
def test_piece1_oracle_discriminates_every_contract(contract: str) -> None:
    with pytest.raises(OracleMismatch):
        check(mutation=contract)
