"""Literal semantic controls for the bounded reviewed mapping authority."""

from __future__ import annotations

import builtins
import copy
import json
import os
from dataclasses import replace
from pathlib import Path

import pytest
from ipakit import _clts_profile as clts_profile
from ipakit import clts_mapping, load_ipa_features
from ipakit._clts_profile import core_bipa_basis, core_bipa_spec, profile_basis
from ipakit._form_profile import graph_profile
from ipakit._graph_facts import FeatureDeclaration
from ipakit._identity import identity_fingerprint
from ipakit.clts import (
    MASTER_FEATURES,
    Snapshot,
    declaration_audit,
    extract_snapshot,
    read_snapshot,
)
from ipakit.clts_mapping import (
    DISPOSITION_CLASSES,
    ENHANCEMENT_DECISIONS,
    ENHANCEMENT_GAP_KINDS,
    MappingAuthority,
    MappingInvalid,
    _native_witnesses,
    _queues,
    _source_witnesses,
    build_authority,
    build_mapping_artifacts,
    read_authority,
    reviewed_rules,
)
from ipakit.features import FeatureNarrowingWarning


def reseal(data: dict) -> dict:
    data["identity"] = identity_fingerprint(
        {k: v for k, v in data.items() if k != "identity"}
    )
    return data


def test_resealed_census_with_wrong_source_hash_is_refused_offline() -> None:
    data = read_authority().to_data()
    data["census"]["clts_to_ipakit"].pop()
    name = "pkg/transcriptionsystems/features.json"
    data["census"]["sources"]["clts"][name] = "0" * 64
    data["dispositions"] = _queues(data["census"], data["rules"])
    with pytest.raises(MappingInvalid, match=f"accepted policy: {name}"):
        MappingAuthority(reseal(data))


def test_offline_mapping_artifacts_match_their_committed_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = builtins.__import__

    def blocked(name, *args, **kwargs):
        if name.split(".")[0] == "pyclts":
            raise AssertionError("pyclts import attempted")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked)
    root = Path(__file__).resolve().parents[1]
    authority = read_authority()
    assert (
        authority.dumps().encode()
        == (root / "ipakit/data/clts/semantic-mapping.json").read_bytes()
    )
    assert authority.gap_report().encode() == (root / "docs/clts-gaps.md").read_bytes()


def test_live_mapping_regeneration_is_current_and_deterministic() -> None:
    value = os.environ.get("IPAKIT_CLTS_DIR")
    if not value:
        pytest.skip("explicit IPAKIT_CLTS_DIR required for live mapping regeneration")
    pytest.importorskip("pyclts")
    root = Path(__file__).resolve().parents[1]
    first = build_mapping_artifacts(Path(value))
    assert set(first.artifacts) == {
        Path("ipakit/data/clts/semantic-mapping.json"),
        Path("docs/clts-gaps.md"),
    }
    assert first.stale(root) == []
    assert build_mapping_artifacts(Path(value)).artifacts == first.artifacts


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
    assert data["version"] == 2
    assert data["rules"]["version"] == 8
    assert data["rules"]["disposition_classes"] == [
        "exact under stated conditions",
        "conditional/composite",
        "convention-based or lossy",
        "unsupported by the adapter despite native expressibility",
        "not expressible in the target model",
        "conflicting",
        "unresolved pending evidence",
    ]
    assert tuple(data["rules"]["disposition_classes"]) == DISPOSITION_CLASSES
    for direction in ("clts_to_ipakit", "ipakit_to_clts"):
        rows = data["dispositions"][direction]
        assert [r["source"] for r in rows] == [
            r["source"] for r in data["census"][direction]
        ]
        assert all(r["status"] in DISPOSITION_CLASSES for r in rows)
    assert all(
        r["status"] == "unresolved pending evidence"
        for r in data["dispositions"]["ipakit_to_clts"]
    )
    reviewed = {
        tuple(r["source"])
        for r in data["dispositions"]["clts_to_ipakit"]
        if r["status"] == "conditional/composite"
    }
    assert reviewed == {
        ("clts", "consonant", "manner", "stop"),
        ("clts", "consonant", "place", "bilabial"),
        ("clts", "consonant", "place", "alveolar"),
        ("clts", "consonant", "phonation", "voiced"),
        ("clts", "consonant", "phonation", "voiceless"),
    }


def test_release_declarations_resolve_to_exact_values() -> None:
    observed = _native_witnesses(reviewed_rules(), load_ipa_features())
    data = read_authority().to_data()
    rows = {
        row["source"][-1]: row
        for row in data["dispositions"]["clts_to_ipakit"]
        if row["source"][1:3] == ["consonant", "release"]
    }
    expected = {
        "unreleased": (
            "feature",
            ["ipakit", "release", "no-audible"],
            "exact under stated conditions",
        ),
        "with-lateral-release": (
            "feature",
            ["ipakit", "release", "lateral"],
            "exact under stated conditions",
        ),
        "with-mid-central-vowel-release": (
            "feature",
            ["ipakit", "release", "schwa"],
            "exact under stated conditions",
        ),
        "with-nasal-release": (
            "feature",
            ["ipakit", "release", "nasal"],
            "exact under stated conditions",
        ),
        "with-sibilant-release": (
            "feature",
            ["ipakit", "release", "sibilant"],
            "exact under stated conditions",
        ),
        "with-trilled-release": (
            "feature",
            ["ipakit", "release", "trilled"],
            "exact under stated conditions",
        ),
        "with-uvular-release": (
            "feature",
            ["ipakit", "release", "uvular"],
            "exact under stated conditions",
        ),
    }
    assert set(rows) == set(expected)
    for source, (form, target, disposition) in expected.items():
        row = rows[source]
        assert row["status"] == disposition
        assert len(row["targets"]) == 1
        assert row["targets"][0]["form"] == form
        assert row["targets"][0]["path"] == target
        assert len(row["rule_ids"]) == 1
    assert "superscript phase mark" in data["rules"]["release_adjudication"]
    assert "tie asserts a constituent sequence" in data["rules"]["release_adjudication"]
    assert all(
        row["status"] == "unresolved pending evidence"
        for row in data["dispositions"]["ipakit_to_clts"]
        if row["source"][1] == "release"
    )
    ruled_releases = {
        rule["id"]: rule
        for rule in data["rules"]["declaration_rules"]
        if rule["id"]
        in {
            "release-sibilant/1",
            "release-trilled/1",
            "release-uvular/1",
        }
    }
    assert set(ruled_releases) == {
        "release-sibilant/1",
        "release-trilled/1",
        "release-uvular/1",
    }
    for rule_id, rule in ruled_releases.items():
        assert rule["preconditions"] == {"host": {"manner": "stop"}}
        assert rule["target"]["form"] == "feature"
        assert observed[rule_id]["observed_value"] == rule["target"]["path"][-1]
        assert data["native_witnesses"][rule_id]["constituents"] == 1


def test_feature_release_rules_state_source_assertion() -> None:
    rules = {
        rule["source"][-1]: rule["preconditions"]
        for rule in reviewed_rules()["declaration_rules"]
        if rule["id"]
        in {
            "release-unreleased/1",
            "release-lateral/1",
            "release-schwa/1",
            "release-nasal/1",
        }
    }
    assert rules == {
        "unreleased": {"source": "asserted"},
        "with-lateral-release": {"source": "asserted"},
        "with-mid-central-vowel-release": {"source": "asserted"},
        "with-nasal-release": {"source": "asserted"},
    }


def test_duration_declarations_preserve_distinct_native_length_values() -> None:
    expected = {
        ("vowel", "long"): ("aː", "long"),
        ("vowel", "mid-long"): ("aˑ", "half-long"),
        ("vowel", "ultra-long"): ("aːː", "overlong"),
        ("vowel", "ultra-short"): ("ă", "extra-short"),
        ("consonant", "long"): ("tː", "long"),
        ("consonant", "mid-long"): ("tˑ", "half-long"),
        ("consonant", "ultra-long"): ("tːː", "overlong"),
    }
    rules = {
        (rule["source"][1], rule["source"][3]): rule
        for rule in reviewed_rules()["declaration_rules"]
        if rule["source"][2] == "duration"
    }
    assert set(rules) == set(expected)
    for source, (witness, house_value) in expected.items():
        rule = rules[source]
        assert rule["disposition"] == "exact under stated conditions"
        assert rule["preconditions"] == {"source": "asserted"}
        assert rule["target"] == {
            "form": "feature",
            "path": ["ipakit", "length", house_value],
            "witness": witness,
        }
    authority = read_authority().to_data()
    rows = {
        (row["source"][1], row["source"][3]): row
        for row in authority["dispositions"]["clts_to_ipakit"]
        if row["source"][2] == "duration"
    }
    observed = _native_witnesses(reviewed_rules(), load_ipa_features())
    assert set(rows) == set(expected)
    for source, (witness, house_value) in expected.items():
        rule = rules[source]
        assert rows[source]["status"] == "exact under stated conditions"
        assert rows[source]["targets"] == [rule["target"]]
        assert observed[rule["id"]] == {
            "form": "feature",
            "target": ["ipakit", "length", house_value],
            "witness": witness,
            "constituents": 1,
            "read": "feature_values",
            "observed_value": house_value,
        }
        assert authority["native_witnesses"][rule["id"]] == observed[rule["id"]]
    assert {value for (kind, _), (_, value) in expected.items() if kind == "vowel"} == {
        "long",
        "half-long",
        "overlong",
        "extra-short",
    }
    assert {
        value for (kind, _), (_, value) in expected.items() if kind == "consonant"
    } == {"long", "half-long", "overlong"}


@pytest.mark.parametrize(
    "rule_id",
    [
        "release-unreleased/1",
        "release-lateral/1",
        "release-schwa/1",
        "release-nasal/1",
    ],
)
def test_exact_release_rule_requires_its_stated_precondition(rule_id: str) -> None:
    rules = copy.deepcopy(reviewed_rules())
    rule = next(rule for rule in rules["declaration_rules"] if rule["id"] == rule_id)
    del rule["preconditions"]
    with pytest.raises(
        MappingInvalid, match="exact under stated conditions rule lacks preconditions"
    ):
        _queues(read_authority().to_data()["census"], rules)


@pytest.mark.parametrize(
    ("preconditions", "message"),
    [
        ({"source": "inferred"}, "unknown source precondition"),
        ({"unchecked": "value"}, "unknown declaration precondition"),
        ({"host": {}}, "host precondition must state features"),
        ({"host": {"manner": "not-declared"}}, "unknown host precondition"),
    ],
)
def test_declaration_precondition_vocabulary_is_enforced(
    preconditions: dict, message: str
) -> None:
    rules = copy.deepcopy(reviewed_rules())
    rules["declaration_rules"][0]["preconditions"] = preconditions
    with pytest.raises(MappingInvalid, match=message):
        _queues(read_authority().to_data()["census"], rules)


def test_flat_read_would_collapse_duration_witnesses_to_normal() -> None:
    ipa = load_ipa_features()
    with pytest.warns(FeatureNarrowingWarning):
        assert ipa.get_features("aˑ")["length"] == "normal"
    with pytest.warns(FeatureNarrowingWarning):
        assert ipa.get_features("aːː")["length"] == "normal"
    observed = _native_witnesses(reviewed_rules(), ipa)
    assert observed["vowel-duration-mid-long/1"]["observed_value"] == "half-long"
    assert observed["vowel-duration-ultra-long/1"]["observed_value"] == "overlong"


def _supplied_snapshot(entries: dict[str, tuple[str, list[str]]]) -> Snapshot:
    data = {k: v for k, v in read_snapshot().to_data().items() if k != "identity"}
    data["domain"] = "supplied-tokens"
    data["requested"] = sorted(entries)
    data["excluded"] = {}
    data["entries"] = {
        token: {
            "alias": False,
            "canonical": token,
            "declaration": None,
            "features": sorted(features),
            "kind": kind,
            "normalized": False,
        }
        for token, (kind, features) in entries.items()
    }
    return Snapshot({**data, "identity": identity_fingerprint(data)})


def _supplied_consonants(entries: dict[str, list[str]]) -> Snapshot:
    return _supplied_snapshot(
        {token: ("consonant", features) for token, features in entries.items()}
    )


def test_duration_targets_require_the_source_value_to_be_asserted() -> None:
    snapshot = _supplied_snapshot(
        {
            "v-long": ("vowel", ["vowel", "long"]),
            "v-mid": ("vowel", ["vowel", "mid-long"]),
            "v-ultra": ("vowel", ["vowel", "ultra-long"]),
            "v-short": ("vowel", ["vowel", "ultra-short"]),
            "c-long": ("consonant", ["consonant", "long"]),
            "c-mid": ("consonant", ["consonant", "mid-long"]),
            "c-ultra": ("consonant", ["consonant", "ultra-long"]),
            "v-plain": ("vowel", ["vowel"]),
            "c-plain": ("consonant", ["consonant"]),
        }
    )
    expected = {
        ("vowel", "long", "v-long"): "long",
        ("vowel", "mid-long", "v-mid"): "half-long",
        ("vowel", "ultra-long", "v-ultra"): "overlong",
        ("vowel", "ultra-short", "v-short"): "extra-short",
        ("consonant", "long", "c-long"): "long",
        ("consonant", "mid-long", "c-mid"): "half-long",
        ("consonant", "ultra-long", "c-ultra"): "overlong",
    }
    authority = read_authority()
    for (kind, source_value, token), house_value in expected.items():
        source = ["clts", kind, "duration", source_value]
        assert authority.declaration_target(source, token, snapshot)["path"] == [
            "ipakit",
            "length",
            house_value,
        ]
        with pytest.raises(MappingInvalid, match="does not assert"):
            authority.declaration_target(source, f"{kind[0]}-plain", snapshot)


@pytest.mark.parametrize(
    ("release", "value"),
    [
        ("unreleased", "no-audible"),
        ("with-lateral-release", "lateral"),
        ("with-mid-central-vowel-release", "schwa"),
        ("with-nasal-release", "nasal"),
    ],
)
def test_feature_release_targets_require_the_source_value_to_be_asserted(
    release: str, value: str
) -> None:
    snapshot = _supplied_consonants(
        {
            "asserted": ["consonant", "fricative", "velar", "voiceless", release],
            "plain": ["consonant", "fricative", "velar", "voiceless"],
        }
    )
    source = ["clts", "consonant", "release", release]
    authority = read_authority()
    assert authority.declaration_target(source, "asserted", snapshot)["path"] == [
        "ipakit",
        "release",
        value,
    ]
    with pytest.raises(MappingInvalid, match="does not assert"):
        authority.declaration_target(source, "plain", snapshot)


def test_macron_a_is_tone_not_a_duration_witness_without_live_clts() -> None:
    ipa = load_ipa_features()
    values = ipa.feature_values("ā")
    assert values["tone"] == ("mid",)
    assert values["length"] == ("normal",)
    duration_witnesses = {
        rule["target"]["witness"]
        for rule in reviewed_rules()["declaration_rules"]
        if rule["source"][2] == "duration"
    }
    assert "ā" not in duration_witnesses
    snapshot = _supplied_snapshot(
        {"ā": ("vowel", ["front", "open", "unrounded", "vowel", "with-mid_tone"])}
    )
    with pytest.raises(MappingInvalid, match="does not assert"):
        read_authority().declaration_target(
            ["clts", "vowel", "duration", "long"], "ā", snapshot
        )


@pytest.mark.parametrize(
    ("release", "value"),
    [
        ("with-sibilant-release", "sibilant"),
        ("with-trilled-release", "trilled"),
        ("with-uvular-release", "uvular"),
    ],
)
def test_ruled_release_holds_only_on_a_stop_host(release: str, value: str) -> None:
    snapshot = _supplied_consonants(
        {
            "stop": ["bilabial", "consonant", "stop", "voiceless", release],
            "fricative": [
                "consonant",
                "fricative",
                "labio-dental",
                "voiceless",
                release,
            ],
        }
    )
    source = ["clts", "consonant", "release", release]
    authority = read_authority()
    assert authority.declaration_target(source, "stop", snapshot)["path"] == [
        "ipakit",
        "release",
        value,
    ]
    with pytest.raises(MappingInvalid, match="host manner=stop"):
        authority.declaration_target(source, "fricative", snapshot)


def test_sibilant_release_refuses_non_stop_host_from_master_tables() -> None:
    value = os.environ.get("IPAKIT_CLTS_DIR")
    if not value:
        pytest.skip("explicit IPAKIT_CLTS_DIR required for the live CLTS master")
    snapshot = extract_snapshot(Path(value), tokens=["fˢ"])
    assert snapshot.features("fˢ") == frozenset(
        {"consonant", "fricative", "labio-dental", "voiceless", "with-sibilant-release"}
    )
    assert "data/sounds.tsv" not in snapshot.to_data()["source"]["inputs"]
    with pytest.raises(MappingInvalid, match="host manner=stop"):
        read_authority().declaration_target(
            ["clts", "consonant", "release", "with-sibilant-release"],
            "fˢ",
            snapshot,
        )


@pytest.mark.parametrize(
    ("release", "token", "value"),
    [
        ("unreleased", "ð̚", "no-audible"),
        ("with-lateral-release", "xˡ", "lateral"),
        ("with-mid-central-vowel-release", "xᵊ", "schwa"),
        ("with-nasal-release", "ǂⁿ", "nasal"),
    ],
)
def test_feature_releases_accept_non_stop_hosts_from_master_tables(
    release: str, token: str, value: str
) -> None:
    clts = os.environ.get("IPAKIT_CLTS_DIR")
    if not clts:
        pytest.skip("explicit IPAKIT_CLTS_DIR required for the live CLTS master")
    snapshot = extract_snapshot(Path(clts), tokens=[token])
    entry = snapshot.to_data()["entries"][token]
    assert release in entry["features"]
    assert "stop" not in entry["features"]
    assert read_authority().declaration_target(
        ["clts", "consonant", "release", release], token, snapshot
    )["path"] == ["ipakit", "release", value]


def test_duration_witnesses_and_macron_a_match_live_clts_resolver() -> None:
    value = os.environ.get("IPAKIT_CLTS_DIR")
    if not value:
        pytest.skip("explicit IPAKIT_CLTS_DIR required for live duration witnesses")
    expected = {
        "aː": ("vowel", "long"),
        "aˑ": ("vowel", "mid-long"),
        "aːː": ("vowel", "ultra-long"),
        "ă": ("vowel", "ultra-short"),
        "tː": ("consonant", "long"),
        "tˑ": ("consonant", "mid-long"),
        "tːː": ("consonant", "ultra-long"),
    }
    snapshot = extract_snapshot(Path(value), tokens=[*expected, "ā"])
    data = snapshot.to_data()
    assert "data/sounds.tsv" not in data["source"]["inputs"]
    rules = {
        rule["target"]["witness"]: (rule["source"][1], rule["source"][3])
        for rule in reviewed_rules()["declaration_rules"]
        if rule["source"][2] == "duration"
    }
    assert rules == expected
    for witness, (kind, source_value) in expected.items():
        entry = data["entries"][witness]
        assert entry["kind"] == kind
        assert source_value in entry["features"]
    macron = data["entries"]["ā"]
    assert macron["kind"] == "vowel"
    assert macron["features"] == [
        "front",
        "open",
        "unrounded",
        "vowel",
        "with-mid_tone",
    ]
    assert not {"long", "mid-long", "ultra-long", "ultra-short"} & set(
        macron["features"]
    )


def test_census_refuses_same_kind_cross_feature_value_spelling(tmp_path: Path) -> None:
    master = tmp_path.joinpath(*MASTER_FEATURES)
    master.parent.mkdir(parents=True)
    master.write_text(
        json.dumps({"consonant": {"manner": ["shared"], "place": ["shared"]}})
    )
    with pytest.raises(ValueError, match="duplicate value spelling across features"):
        declaration_audit(tmp_path, include_catalog=False)


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


@pytest.mark.parametrize("payload", ["catalog", "witness_ids", "source", "cardinality"])
def test_shipped_authority_refuses_catalog_payload_and_bad_counts(payload: str) -> None:
    data = read_authority().to_data()
    census = data["census"]
    if payload == "catalog":
        census["catalog"] = {"sounds": 0, "unit_kinds": {}}
    elif payload == "witness_ids":
        census["clts_to_ipakit"][0]["witness_ids"] = ["uncleared"]
    elif payload == "source":
        census["sources"]["clts"]["data/sounds.tsv"] = "uncleared"
    else:
        census["semantic_correspondences_audited"] = True
    with pytest.raises(MappingInvalid):
        MappingAuthority(reseal(data))


def test_bound_profile_and_caller_mutation_do_not_change_authority() -> None:
    authority = read_authority()
    before = authority.identity
    data = authority.to_data()
    data["rules"]["rules"].clear()
    assert authority.identity == before
    assert authority.require_import_profile(core_bipa_spec()) is None


@pytest.mark.parametrize(
    "change",
    [
        {
            "house_fields": (
                FeatureDeclaration(
                    "changed-house", ("urn:changed-house", "changed-house")
                ),
            )
        },
        {"kinds": ("consonant", "vowel")},
        {"domains": {"features": (False,)}},
        {"domains": {"features": (0,)}},
        {"provider_fingerprint": "sha256:" + "1" * 64},
        {"manifest_fingerprint": "sha256:" + "2" * 64},
        {"manifest_kind": "interim"},
    ],
)
def test_import_profile_basis_guard_covers_every_nonmapping_component(
    change: dict,
) -> None:
    original = core_bipa_spec(
        mapping_identity=(
            "sha256:b03736ce99784cf51c8042d6b38358955b4ff239d73afa0ea19d95d4c30b1bc9"
        )
    )
    changed = replace(original, **change)
    assert changed.mapping_identity == original.mapping_identity
    assert profile_basis(changed) != profile_basis(original)
    authority = read_authority()
    with pytest.raises(MappingInvalid, match="profile basis"):
        authority._require_profile_basis(changed)


def test_import_profile_mapping_identity_guard_is_separate() -> None:
    authority = read_authority()
    original = core_bipa_spec()
    changed = replace(original, mapping_identity="sha256:" + "0" * 64)
    assert profile_basis(changed) == profile_basis(original)
    with pytest.raises(MappingInvalid, match="mapping identity"):
        authority.require_import_profile(changed)


def test_import_profile_final_manifest_guard_precedes_mapping_guard() -> None:
    changed = replace(
        core_bipa_spec(),
        manifest_kind="interim",
        mapping_identity="sha256:" + "0" * 64,
    )
    with pytest.raises(ValueError, match="manifest kind mismatch"):
        read_authority().require_import_profile(changed)


def test_rules_pin_profile_family_and_basis_as_literals() -> None:
    binding = reviewed_rules()["profile_binding"]
    assert binding["profile"] == {"id": "ipakit-clts-source", "version": 1}
    assert binding["basis"] == (
        "sha256:6078e6a669c7517792c96bf1fbdec0a07e44260cba5e20cb0b49d6682b741cba"
    )
    assert read_authority().identity == (
        "sha256:b03736ce99784cf51c8042d6b38358955b4ff239d73afa0ea19d95d4c30b1bc9"
    )


def test_reader_refuses_stale_profile_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        clts_profile.ADAPTER_OUTCOMES["excluded"], "marker", "unknown-sound"
    )
    with pytest.raises(MappingInvalid, match="profile binding") as error:
        read_authority()
    assert "recomputed profile basis: sha256:" in str(error.value)
    assert reviewed_rules()["profile_binding"]["basis"] not in str(error.value)


def test_builder_refuses_to_silently_rebind_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(
        clts_profile.ADAPTER_OUTCOMES["excluded"], "marker", "unknown-sound"
    )
    monkeypatch.setattr(
        clts_mapping,
        "validate_source",
        lambda path: pytest.fail("builder continued past profile binding"),
    )
    with pytest.raises(MappingInvalid, match="profile binding") as error:
        build_authority(Path("unused"), snapshot=read_snapshot())
    assert "recomputed profile basis: sha256:" in str(error.value)
    assert reviewed_rules()["profile_binding"]["basis"] not in str(error.value)


def test_core_basis_does_not_read_mapping_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def refused(*args, **kwargs):
        raise AssertionError("mapping authority read")

    monkeypatch.setattr(clts_mapping, "read_authority", refused)
    assert core_bipa_basis() == (
        "sha256:6078e6a669c7517792c96bf1fbdec0a07e44260cba5e20cb0b49d6682b741cba"
    )


@pytest.mark.parametrize(
    "wrong",
    [None, pytest.param("form-profile", id="form-profile-fingerprint")],
)
def test_import_profile_type_guard_refuses_non_source_profiles(wrong) -> None:
    if wrong == "form-profile":
        wrong = graph_profile(load_ipa_features()).name
    with pytest.raises(MappingInvalid, match="SourceProfileSpec"):
        read_authority().require_import_profile(wrong)


def test_gap_report_is_generated_and_enhancement_dispositions_are_scoped() -> None:
    authority = read_authority()
    report = authority.gap_report()
    assert report == (Path(__file__).parents[1] / "docs/clts-gaps.md").read_text()
    assert "## Accepted for lane H" in report
    records = {r["id"]: r for r in authority.to_data()["rules"]["enhancements"]}
    decisions = {record_id: record["decision"] for record_id, record in records.items()}
    assert decisions == {
        "nasal-approach": "rejected",
        "tie-conversion": "deferred",
        "tone-host": "deferred",
        "superscript-releases": "accepted",
        "nasal-release-place": "accepted",
        "unspecified-values": "deferred",
        "whistled-sibilant": "deferred",
    }
    assert {record["gap_kind"] for record in records.values()} <= set(
        ENHANCEMENT_GAP_KINDS
    )
    assert {record["decision"] for record in records.values()} <= set(
        ENHANCEMENT_DECISIONS
    )
    assert {
        record_id
        for record_id, record in records.items()
        if record.get("accepted_for") == "H"
    } == {"superscript-releases", "nasal-release-place"}
    assert records["nasal-release-place"]["reason"].find("release=bilabial-nasal") >= 0
    assert "release=nasal remains" in records["nasal-release-place"]["reason"]
    assert "no release-place dimension" in records["nasal-release-place"]["reason"]
    assert records["nasal-release-place"]["consequence"].startswith("Implemented")
    assert records["superscript-releases"]["consequence"].startswith("Implemented")
    assert records["tone-host"]["affected_source_declarations"] == [
        "clts / tone / start / *",
        "clts / tone / middle / *",
        "clts / tone / end / *",
        "clts / tone / contour / *",
    ]
    ipa = load_ipa_features()
    for spelling, value in (("tˢ", "sibilant"), ("dʳ", "trilled"), ("dʶ", "uvular")):
        assert ipa.get_features(spelling, with_defaults=False)["release"] == value
    assert ipa.get_features("tᵐ", with_defaults=False)["release"] == "bilabial-nasal"
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


def test_every_model_gap_has_a_failed_strict_native_construction() -> None:
    ipa = load_ipa_features()
    records = reviewed_rules()["enhancements"]
    for record in records:
        assert record["gap_kind"] in ENHANCEMENT_GAP_KINDS
        assert record["decision"] in ENHANCEMENT_DECISIONS
        assert record["native_construction_attempts"]
        if record["gap_kind"] == "model gap":
            assert all(
                attempt["expected"] == "fails"
                for attempt in record["native_construction_attempts"]
            )
            for attempt in record["native_construction_attempts"]:
                with pytest.raises(ValueError):
                    ipa.read(attempt["witness"], strict=True)


@pytest.mark.parametrize("missing", ["gap_kind", "decision"])
def test_enhancement_record_requires_gap_kind_and_decision(missing: str) -> None:
    rules = copy.deepcopy(reviewed_rules())
    del rules["enhancements"][0][missing]
    with pytest.raises(MappingInvalid, match="enhancement record fields"):
        _native_witnesses(rules, load_ipa_features())


def test_constructible_distinction_cannot_be_labeled_model_gap() -> None:
    rules = copy.deepcopy(reviewed_rules())
    nasal_approach = next(
        record for record in rules["enhancements"] if record["id"] == "nasal-approach"
    )
    assert nasal_approach["native_construction_attempts"] == [
        {
            "witness": "ⁿd",
            "expected": "succeeds",
            "distinction": "nasal approach on a stop",
        }
    ]
    nasal_approach["gap_kind"] = "model gap"
    with pytest.raises(MappingInvalid, match="model gap is constructible"):
        _native_witnesses(rules, load_ipa_features())


def test_enhancement_source_evidence_has_an_offline_pinned_counterpart() -> None:
    entries = read_snapshot().to_data()["entries"]
    assert entries["tˢ"]["canonical"] == "ts"
    assert entries["tⁿ"]["features"] == [
        "alveolar",
        "consonant",
        "stop",
        "voiceless",
        "with-nasal-release",
    ]
    assert entries["Ø"]["features"] == [
        "consonant",
        "unspecified-manner",
        "unspecified-place",
        "unspecified-voice",
    ]
    assert "whistled-sibilant" in entries["s̫"]["features"]
    assert entries["¹³¹"]["features"] == [
        "contour",
        "from-low",
        "to-low",
        "tone",
        "via-mid",
    ]


def test_enhancement_source_evidence_matches_live_clts_master() -> None:
    value = os.environ.get("IPAKIT_CLTS_DIR")
    if not value:
        pytest.skip("explicit IPAKIT_CLTS_DIR required for live enhancement evidence")
    entries = extract_snapshot(
        Path(value), tokens=["tˢ", "dʳ", "dʶ", "tᵐ", "tⁿ", "Ø", "s̫", "¹³¹"]
    ).to_data()["entries"]
    assert entries["tˢ"]["canonical"] == "ts"
    assert entries["dʳ"]["features"][-1] == "with-trilled-release"
    assert entries["dʶ"]["features"][-1] == "with-uvular-release"
    assert entries["tᵐ"]["canonical"] == entries["tⁿ"]["canonical"] == "tⁿ"
    assert entries["tᵐ"]["features"] == entries["tⁿ"]["features"]
    assert entries["Ø"]["features"][-3:] == [
        "unspecified-manner",
        "unspecified-place",
        "unspecified-voice",
    ]
    assert "whistled-sibilant" in entries["s̫"]["features"]
    assert entries["¹³¹"]["features"] == [
        "contour",
        "from-low",
        "to-low",
        "tone",
        "via-mid",
    ]
