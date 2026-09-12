"""Literal semantic controls for the bounded reviewed mapping authority."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
from ipakit import load_ipa_features
from ipakit._identity import identity_fingerprint
from ipakit.clts import Snapshot, read_snapshot
from ipakit.clts_mapping import (
    MappingAuthority,
    MappingInvalid,
    ProfilePending,
    _source_witnesses,
    read_authority,
    reviewed_rules,
)


def reseal(data: dict) -> dict:
    data["identity"] = identity_fingerprint(
        {k: v for k, v in data.items() if k != "identity"}
    )
    return data


def test_four_complete_plain_stop_witnesses_not_a_general_converter() -> None:
    authority, snapshot = read_authority(), read_snapshot()
    expected = {
        "p": ("bilabial", "-"),
        "b": ("bilabial", "+"),
        "t": ("alveolar", "-"),
        "d": ("alveolar", "+"),
    }
    data = authority.to_data()
    for token, (place, voiced) in expected.items():
        result = authority.eligibility(token, snapshot)
        assert result["status"] == "eligible-witness"
        assert result["target"] == token
        assert result["import_ready"] is False
        evidence = data["native_witnesses"][result["rule_id"]]
        assert evidence["asserted_target_predicates"] == {
            "place": place,
            "manner": "plosive",
            "voiced": voiced,
        }
        assert evidence["structure"] == {
            "constituents": 1,
            "modifiers": 0,
            "approach": 0,
            "junctures": 0,
            "prosody": 0,
        }
        assert "airstream" in evidence["additional_native_claims"]
    for token in ("a", "ts", "t͡s", "t͜s", "ⁿd", "dⁿ", "⁵", "UNKNOWN"):
        result = authority.eligibility(token, snapshot)
        assert result["status"] == "unresolved"
        assert result["target"] is None
    with pytest.raises(MappingInvalid, match="inverse"):
        authority.eligibility("p", snapshot, direction="ipakit-to-clts")


def test_all_finite_declarations_accounted_without_invented_reverse() -> None:
    data = read_authority().to_data()
    for direction in ("clts_to_ipakit", "ipakit_to_clts"):
        rows = data["dispositions"][direction]
        assert [r["source"] for r in rows] == [
            r["source"] for r in data["census"][direction]
        ]
        assert all(r["status"] in ("unresolved", "conditional-witness") for r in rows)
    assert all(
        r["status"] == "unresolved" for r in data["dispositions"]["ipakit_to_clts"]
    )
    reviewed = {
        tuple(r["source"])
        for r in data["dispositions"]["clts_to_ipakit"]
        if r["rule_ids"]
    }
    assert reviewed == {
        ("clts", "consonant", "manner", "stop"),
        ("clts", "consonant", "place", "bilabial"),
        ("clts", "consonant", "place", "alveolar"),
        ("clts", "consonant", "phonation", "voiced"),
        ("clts", "consonant", "phonation", "voiceless"),
    }


def test_extra_claim_absence_and_wrong_voicing_refuse_even_when_resealed() -> None:
    authority = read_authority()
    for features in (
        ["consonant", "stop", "bilabial", "voiceless", "pre-nasalized"],
        ["consonant", "stop", "bilabial"],
        ["consonant", "stop", "bilabial", "voiced"],
    ):
        data = read_snapshot().to_data()
        data["entries"]["p"]["features"] = sorted(features)
        changed = Snapshot(reseal(data))
        with pytest.raises(MappingInvalid, match="complete source claims"):
            _source_witnesses(reviewed_rules(), changed)
        with pytest.raises(MappingInvalid, match="artifact identity"):
            authority.eligibility("p", changed)


@pytest.mark.parametrize(
    "mutation",
    ["source", "native", "rule", "typed", "witness-typed", "profile", "disposition"],
)
def test_semantic_bindings_checked_beyond_artifact_hash(mutation: str) -> None:
    data = read_authority().to_data()
    if mutation == "source":
        data["bindings"]["source_policy"] = "sha256:wrong"
    elif mutation == "native":
        data["bindings"]["native_metric"] = "wrong"
    elif mutation == "rule":
        data["rules"]["rules"][0]["target_predicates"]["voiced"] = "+"
    elif mutation == "typed":
        data["rules"]["target_structure"]["constituents"] = True
    elif mutation == "witness-typed":
        data["native_witnesses"]["plain-p/1"]["structure"]["constituents"] = True
    elif mutation == "profile":
        data["rules"]["profile_binding"] = "invented"
    else:
        data["dispositions"]["ipakit_to_clts"][0]["status"] = "exact"
    with pytest.raises(MappingInvalid):
        MappingAuthority(reseal(data))


def test_changed_population_refuses_until_reconciled() -> None:
    authority = read_authority()
    census = authority.to_data()["census"]
    row = copy.deepcopy(census["clts_to_ipakit"][0])
    row["source"] = ["clts", "consonant", "new-feature", "new-value"]
    census["clts_to_ipakit"].append(row)
    with pytest.raises(MappingInvalid, match="population"):
        authority.validate_context(census, read_snapshot(), load_ipa_features())


def test_profile_pending_and_caller_mutation_do_not_change_authority() -> None:
    authority = read_authority()
    before = authority.identity
    data = authority.to_data()
    data["rules"]["rules"].clear()
    assert authority.identity == before
    for fingerprint in (None, "fake-reviewed-profile"):
        with pytest.raises(ProfilePending):
            authority.require_import_profile(fingerprint)


def test_gap_report_is_generated_and_enhancement_dispositions_are_scoped() -> None:
    authority = read_authority()
    assert (
        authority.gap_report()
        == (Path(__file__).parents[1] / "docs/clts-gaps.md").read_text()
    )
    decisions = {
        r["id"]: r["decision"] for r in authority.to_data()["rules"]["enhancements"]
    }
    assert decisions == {
        "nasal-approach": "rejected",
        "tie-conversion": "deferred",
        "tone-host": "deferred",
    }
    ipa = load_ipa_features()
    approach = ipa.read("ⁿd", strict=True).units[0].segment
    release = ipa.read("dⁿ", strict=True).units[0].segment
    assert approach is not None and release is not None
    assert approach.constituents[0].approach
    assert not release.constituents[0].approach
    assert release.constituents[0].modifiers
    assert ipa.get_features("a")["voiced"] == "+"
    assert "voiced" not in read_snapshot().features("a")
    assert (
        len({ipa.read(token, strict=True).to_json() for token in ("ts", "t͡s", "t͜s")})
        == 3
    )
