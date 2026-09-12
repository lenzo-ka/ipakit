"""Declaration census distinguishes missing evidence from missing domains."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from ipakit import clts, load_ipa_features
from scripts import interop


@pytest.fixture
def source(tmp_path: Path) -> Path:
    master = tmp_path.joinpath(*clts.MASTER_FEATURES)
    master.parent.mkdir(parents=True)
    master.write_text(json.dumps({"vowel": {"height": ["close", "open"]}}))
    data = tmp_path / "data"
    data.mkdir()
    (data / "features.tsv").write_text(
        "ID\tTYPE\tFEATURE\tVALUE\n"
        "v1\tvowel\theight\tclose\n"
        "v2\tvowel\theight\topen\n"
    )
    (data / "sounds.tsv").write_text(
        "ID\tTYPE\tFEATURES\tGRAPHEME\n" "s1\tvowel\tv1\ti\n" "s2\tdiphthong\tv1\tii\n"
    )
    return tmp_path


def test_declared_but_unobserved_and_composite_context(source: Path) -> None:
    result = clts.declaration_audit(source)
    close, opened = result["clts_to_ipakit"]
    assert close["observed_count"] == 2
    assert close["observed_unit_kinds"] == {"diphthong": 1, "vowel": 1}
    assert opened["declared"] and opened["cataloged"]
    assert opened["observed_count"] == 0 and opened["witness_ids"] == []
    assert result["scope"]["catalog_unit_kinds_without_master_domains"] == ["diphthong"]
    assert "tier/host relationships" in result["scope"]["outside"]
    assert result["semantic_correspondences_audited"] == 0
    for row in result["clts_to_ipakit"] + result["ipakit_to_clts"]:
        assert row["status"] == "unclassified" and row["targets"] == []


def test_declarations_only_do_not_read_or_freeze_catalog(source: Path) -> None:
    full = clts.declaration_audit(source)
    for name in ("features.tsv", "sounds.tsv"):
        (source / "data" / name).unlink()
    narrow = clts.declaration_audit(source, include_catalog=False)
    assert "catalog" not in narrow
    assert set(narrow["sources"]["clts"]) == {"/".join(clts.MASTER_FEATURES)}
    assert [r["source"] for r in narrow["clts_to_ipakit"]] == [
        r["source"] for r in full["clts_to_ipakit"] if r["declared"]
    ]
    assert all(
        set(row) == {"source", "status", "direction", "targets", "declared"}
        for row in narrow["clts_to_ipakit"]
    )


@pytest.mark.parametrize("invalid", [True, -1, 1])
def test_census_sound_cardinality_is_typed_and_coherent(
    source: Path, invalid: object
) -> None:
    data = clts.declaration_audit(source)
    data["catalog"]["sounds"] = invalid
    with pytest.raises(ValueError):
        clts.validate_declaration_census(data)


@pytest.mark.parametrize("field", ["observed_count", "observed_occurrences"])
def test_census_observation_counts_are_not_boolean(source: Path, field: str) -> None:
    data = clts.declaration_audit(source)
    data["clts_to_ipakit"][0][field] = True
    with pytest.raises(ValueError):
        clts.validate_declaration_census(data)


def test_census_nested_cardinalities_and_schema_are_checked(source: Path) -> None:
    mutations = (
        lambda d: d.update(version=True),
        lambda d: d["catalog"]["unit_kinds"].update(vowel=True),
        lambda d: d["clts_to_ipakit"][0]["observed_unit_kinds"].update(vowel=-1),
        lambda d: d["clts_to_ipakit"][0].update(witness_ids=[]),
    )
    for mutation in mutations:
        data = clts.declaration_audit(source)
        mutation(data)
        with pytest.raises(ValueError):
            clts.validate_declaration_census(data)


def test_new_declaration_without_catalog_witness_is_not_lost(source: Path) -> None:
    path = source.joinpath(*clts.MASTER_FEATURES)
    master = json.loads(path.read_text())
    master["new-kind"] = {"new-feature": ["close"]}
    path.write_text(json.dumps(master))
    rows = clts.declaration_audit(source)["clts_to_ipakit"]
    added = next(row for row in rows if row["source"][1] == "new-kind")
    assert added["source"] == ["clts", "new-kind", "new-feature", "close"]
    assert added["declared"] and not added["cataloged"]
    assert added["observed_count"] == 0


def test_undeclared_catalog_value_remains_explicit(source: Path) -> None:
    path = source.joinpath(*clts.MASTER_FEATURES)
    path.write_text('{"vowel": {"height": ["close"]}}')
    rows = clts.declaration_audit(source)["clts_to_ipakit"]
    assert rows[1]["cataloged"] and not rows[1]["declared"]


def test_native_population_comes_from_loader(source: Path) -> None:
    ipa = load_ipa_features()
    rows = clts.declaration_audit(source)["ipakit_to_clts"]
    assert {tuple(row["source"][1:]) for row in rows} == {
        (name, value)
        for name, feature in ipa.features.items()
        for value in feature.values
    }
    tone = next(row for row in rows if row["source"][1] == "tone")
    assert tone["context"]["sequence"] is ipa.features["tone"].sequence
    assert tone["context"]["mode"] == ipa.features["tone"].mode


@pytest.mark.parametrize(
    "content",
    [
        "{}",
        "[]",
        '{"vowel": {}}',
        '{"vowel": {"height": []}}',
        '{"vowel": {"height": ["close", "close"]}}',
        '{"vowel": {}, "vowel": {"height": ["close"]}}',
        '{"vowel": {"height": [null]}}',
        "not json",
    ],
)
def test_malformed_master_fails(source: Path, content: str) -> None:
    source.joinpath(*clts.MASTER_FEATURES).write_text(content)
    with pytest.raises(ValueError):
        clts.declaration_audit(source)


@pytest.mark.parametrize(
    "name,content",
    [
        ("features.tsv", "ID\tTYPE\tFEATURE\tVALUE\n"),
        (
            "features.tsv",
            "ID\tTYPE\tFEATURE\tVALUE\n1\tvowel\theight\tclose\n1\tvowel\theight\topen\n",
        ),
        (
            "features.tsv",
            "ID\tTYPE\tFEATURE\tVALUE\n1\tvowel\theight\tclose\n2\tvowel\theight\tclose\n",
        ),
        ("features.tsv", "ID\tTYPE\tFEATURE\tVALUE\n1\tvowel\theight\n"),
        ("sounds.tsv", "ID\tTYPE\tFEATURES\tGRAPHEME\n1\tvowel\tunknown\tx\n"),
        ("sounds.tsv", "ID\tTYPE\tFEATURES\tGRAPHEME\n1\tvowel\tv1\tx\textra\n"),
        ("sounds.tsv", "ID\tID\tFEATURES\tGRAPHEME\n1\tvowel\tv1\tx\n"),
    ],
)
def test_malformed_catalog_fails(source: Path, name: str, content: str) -> None:
    (source / "data" / name).write_text(content)
    with pytest.raises(ValueError):
        clts.declaration_audit(source)


@pytest.mark.parametrize(
    "name,content",
    [
        (
            "features.tsv",
            'ID\tTYPE\tFEATURE\tVALUE\nv1\tvowel\theight\tclose\nv2\tvowel\theight\t"open\n',
        ),
        ("sounds.tsv", 'ID\tTYPE\tFEATURES\tGRAPHEME\ns1\tvowel\tv1\t"i\n'),
    ],
)
def test_malformed_quotes_fail_cli_without_json(
    source: Path, name: str, content: str, capsys: pytest.CaptureFixture[str]
) -> None:
    (source / "data" / name).write_text(content)
    assert interop.main(["--clts", str(source), "declarations"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "declarations:" in captured.err
    assert "TSV quoting" in captured.err


def test_valid_quoted_tabs_and_newlines_are_preserved() -> None:
    rows = clts._audit_tsv(b'ID\tNOTE\n1\t"first\tpart\nsecond line"\n', {"ID"})
    assert rows == [{"ID": "1", "NOTE": "first\tpart\nsecond line"}]


def test_cli_is_deterministic_and_content_pinned(
    source: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    argv = ["--clts", str(source), "declarations"]
    assert interop.main(argv) == 0
    first = capsys.readouterr().out
    assert interop.main(argv) == 0
    assert capsys.readouterr().out == first
    result = json.loads(first)
    assert result == clts.declaration_audit(source)
    assert interop.declaration_audit is clts.declaration_audit
    name = "/".join(clts.MASTER_FEATURES)
    assert (
        result["sources"]["clts"][name]
        == hashlib.sha256((source / name).read_bytes()).hexdigest()
    )
    assert str(source) not in first


def test_cli_missing_source_is_failure_not_empty_success(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert interop.main(["--clts", str(tmp_path), "declarations"]) == 1
    assert capsys.readouterr().out == ""
    assert interop.main(["--clts", "", "declarations"]) == 1
    assert capsys.readouterr().out == ""


def test_legacy_missing_source_behavior_preserved(tmp_path: Path) -> None:
    assert interop.main(["--clts", str(tmp_path), "features"]) == 0


def test_composite_repeated_features_are_occurrences_not_duplicate_sounds(
    source: Path,
) -> None:
    (source / "data/sounds.tsv").write_text(
        "ID\tTYPE\tFEATURES\tGRAPHEME\n1\tcluster\tv1 v1\tii\n"
    )
    row = clts.declaration_audit(source)["clts_to_ipakit"][0]
    assert row["observed_count"] == 1
    assert row["observed_occurrences"] == 2
    assert row["witness_ids"] == ["1"]


def test_featureless_sound_refuses_without_a_success_report(
    source: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (source / "data/sounds.tsv").write_text(
        "ID\tTYPE\tFEATURES\tGRAPHEME\ns1\tvowel\t\ti\n"
    )
    assert interop.main(["--clts", str(source), "declarations"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "featureless sound row" in captured.err


@pytest.mark.parametrize("metadata_present", [True, False])
def test_similarity_labels_and_fractional_rank_rendering(
    source: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    metadata_present: bool,
) -> None:
    class Sound:
        def similarity(self, other: Sound) -> float:
            return 0.5

    phones = {str(i): Sound() for i in range(101)}
    inventory = SimpleNamespace(phones=phones, xml_path=source / "data/features.tsv")
    clts = SimpleNamespace(root=source, bipa=lambda: phones)
    sibling = source / "pkg/transcriptionsystems/sibling/sounds.tsv"
    sibling.parent.mkdir()
    sibling.write_text("a consumed sibling declaration")
    monkeypatch.setattr(interop, "load_ipa_features", lambda: inventory)
    monkeypatch.setattr(interop, "distance", lambda a, b: 0.25)
    monkeypatch.setattr(
        interop, "metric_fingerprint", lambda ipa, phones: "metric-test"
    )

    def resolver_version(package: str) -> str:
        if not metadata_present:
            raise interop.metadata.PackageNotFoundError(package)
        return "test-version"

    monkeypatch.setattr(interop.metadata, "version", resolver_version)
    assert interop.cmd_similarity(clts, SimpleNamespace(top=1)) == 0
    output = capsys.readouterr().out
    expected_version = (
        "test-version"
        if metadata_present
        else "unknown (distribution metadata unavailable)"
    )
    assert f"pyclts version: {expected_version}" in output
    assert (
        "source sha256 pkg/transcriptionsystems/sibling/sounds.tsv: "
        + hashlib.sha256(sibling.read_bytes()).hexdigest()
    ) in output
    assert "native metric fingerprint: metric-test" in output
    assert "catalog-validation sha256 data/sounds.tsv:" in output
    assert "not perceptual-equivalence" in output
    assert "pairs: 5050" in output
    assert "CLTS 1-Jaccard 0.5000 (rank  2525.5)" in output
