"""Frozen CLTS geometry is finite, explicit and independent of its dev oracle."""

from __future__ import annotations

import builtins
import json
import os
import subprocess
from dataclasses import FrozenInstanceError
from importlib import metadata
from pathlib import Path

import pytest
from ipakit import clts, load_ipa_features
from ipakit._identity import identity_fingerprint
from ipakit.bridges.costmodel import (
    CostPolicy,
    Segmentation,
    align_under,
    compare,
    compare_token_corpus,
    compare_tokens,
    set_feature_pack,
)
from ipakit.extraction import SourceContentError, SourceMissingError, SourceVersionError
from ipakit.feature_sets import FeatureSets, OutsideDomain, jaccard


def test_native_set_arithmetic_is_not_qualified_feature_arithmetic() -> None:
    geometry = FeatureSets(
        "test", {"x": {"front", "vowel"}, "y": {"front", "consonant"}, "z": set()}
    )
    assert geometry.similarity("x", "y") == 1 / 3
    assert geometry.similarity("z", "z") == 0
    assert jaccard(set(), set(), empty=1) == 1
    with pytest.raises(FrozenInstanceError):
        geometry.name = "changed"
    with pytest.raises(TypeError):
        geometry.values["x"] = frozenset()


def test_composite_direction_is_retained_without_native_ipa_mapping() -> None:
    geometry = FeatureSets(
        "composite",
        {
            "ai": {"from_open", "to_close", "diphthong"},
            "ia": {"from_close", "to_open", "diphthong"},
        },
    )
    assert geometry.similarity("ai", "ia") == 1 / 5


@pytest.mark.parametrize(
    "left,right", [(("unknown",), ()), ((), ("unknown",)), (("unknown",), ("unknown",))]
)
def test_unknowns_refuse_even_on_self_or_gap_only_alignments(
    left: tuple[str, ...], right: tuple[str, ...]
) -> None:
    pack = set_feature_pack(FeatureSets("test", {"a": {"vowel"}}))
    with pytest.raises(OutsideDomain, match="finite domain"):
        align_under(load_ipa_features(), pack, Segmentation(left), Segmentation(right))
    with pytest.raises(OutsideDomain):
        pack.sub_cost("unknown", "unknown")


def test_explicit_tokens_use_actual_existing_fold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ipa = load_ipa_features()
    pack = set_feature_pack(
        FeatureSets("test", {"a": {"vowel"}, "p": {"consonant"}}),
        CostPolicy(substitution_scale=0.5),
        gap=2,
    )
    calls = []
    original = ipa._align

    def witness(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(ipa, "_align", witness)
    row = compare_tokens(
        ipa, pack, Segmentation(("a",)), Segmentation(("p",)), return_alignment=True
    )
    assert row.edit_cost == 0.5 and row.alignment is not None
    assert len(calls) == 1
    assert (
        calls[0][2] is pack.sub_cost
        and calls[0][3] is pack.insert_cost
        and calls[0][4] is pack.delete_cost
    )
    with pytest.raises(ValueError, match="segmentation-required"):
        compare(ipa, pack, "a", "p")


def test_shipped_snapshot_keeps_literal_source_and_nfd_aliases() -> None:
    snapshot = clts.read_snapshot()
    assert snapshot.similarity("ç", "ç") == 1
    data = snapshot.to_data()
    assert data["domain"] == "core-bipa"
    assert data["entries"]["ç"]["declaration"] == "ç"
    assert data["entries"]["ç"]["normalized"]
    assert data["entries"]["ç"]["canonical"] == "ç"
    assert data["excluded"]["_"] == "marker"
    assert data["excluded"]["ʈʂʰ "] == "unknown-source-spelling"
    for token in ("_", "ai", "ʈʂʰ ", "unknown"):
        with pytest.raises(OutsideDomain):
            snapshot.similarity(token, token)
    assert set(data["requested"]) == set(data["entries"]) | set(data["excluded"])
    assert clts.Snapshot(data).dumps() == snapshot.dumps()
    data["entries"]["a"]["features"].clear()
    assert snapshot.features("a")


@pytest.mark.parametrize(
    "change", ["version", "source", "hash", "marker", "duplicate-label", "partition"]
)
def test_artifact_validation_refuses_schema_pin_and_shape_changes(change: str) -> None:
    data = clts.read_snapshot().to_data()
    if change == "version":
        data["version"] = 99
    elif change == "source":
        data["source"]["resolver"]["version"] = "other"
    elif change == "hash":
        data["identity"] = "sha256:wrong"
    elif change == "marker":
        data["entries"]["a"]["kind"] = "marker"
    elif change == "duplicate-label":
        data["entries"]["a"]["features"].append("vowel")
    else:
        data["requested"].remove("a")
    if change != "hash":
        data["identity"] = identity_fingerprint(
            {k: v for k, v in data.items() if k != "identity"}
        )
    with pytest.raises(clts.ArtifactInvalid):
        clts.Snapshot(data)


def test_invalid_json_and_missing_artifact_are_typed(tmp_path: Path) -> None:
    with pytest.raises(clts.ArtifactInvalid):
        clts.read_snapshot(tmp_path / "missing")
    path = tmp_path / "bad.json"
    path.write_text('{"version":1,"version":2}')
    with pytest.raises(clts.ArtifactInvalid):
        clts.read_snapshot(path)


def test_frozen_reads_never_import_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name == "pyclts" or name.startswith("pyclts."):
            raise AssertionError("runtime attempted to import pyclts")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    snapshot = clts.read_snapshot()
    assert snapshot.similarity("a", "a") == 1
    pack = set_feature_pack(snapshot.geometry)
    assert (
        compare_tokens(
            load_ipa_features(), pack, Segmentation(("a",)), Segmentation(())
        ).edit_cost
        == 1
    )


def test_missing_provider_and_wrong_version_are_distinct(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def unavailable(_: str) -> str:
        raise metadata.PackageNotFoundError("pyclts")

    monkeypatch.setattr(clts.metadata, "version", unavailable)
    with pytest.raises(clts.ResolverUnavailable, match="interop"):
        clts.extract_snapshot(tmp_path)
    monkeypatch.setattr(clts.metadata, "version", lambda _: "0.0")
    with pytest.raises(SourceVersionError, match="pyclts=="):
        clts.extract_snapshot(tmp_path)


def test_missing_checkout_is_not_a_phone_claim(tmp_path: Path) -> None:
    with pytest.raises(SourceMissingError):
        clts.validate_source(tmp_path)


def test_wrong_checkout_revision_is_distinct(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        clts.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args, 0, stdout="wrong-revision\n", stderr=""
        ),
    )
    with pytest.raises(SourceVersionError, match="CLTS must be"):
        clts.validate_source(tmp_path)


def test_systematic_token_report_keeps_refusals_and_population() -> None:
    pack = set_feature_pack(clts.read_snapshot().geometry)
    report = compare_token_corpus(
        load_ipa_features(), [pack], [["a"], ["p"], ["ai"]], all_pairs=True
    )
    assert report["ordered_pairs_per_pack"] == 6
    assert len(report["rows"]) == 6
    refused = [r for r in report["rows"] if r["status"] == "refused"]
    assert len(refused) == 4
    assert {r["code"] for r in refused} == {"outside-artifact-domain"}
    with pytest.raises(ValueError):
        compare_token_corpus(load_ipa_features(), [pack], ["a", "p"])


def test_cli_comparison_uses_library_token_corpus(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from scripts import costmodel_compare

    corpus = [["p", "a"], ["b", "a"], ["ai"]]
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps(corpus))
    monkeypatch.setattr(
        "sys.argv",
        [
            "costmodel_compare",
            "--tokens-json",
            str(path),
            "--clts-snapshot",
            "--policy",
            "faithful",
            "--format",
            "json",
        ],
    )
    assert costmodel_compare.main() == 0
    report = json.loads(capsys.readouterr().out)
    assert report["corpus"] == corpus
    clts_rows = [row for row in report["rows"] if row["pack"].startswith("set/clts/")]
    assert [row["status"] for row in clts_rows] == ["scored", "refused"]


@pytest.fixture
def live_source() -> Path:
    value = os.environ.get("IPAKIT_CLTS_DIR")
    if not value:
        pytest.skip(
            "explicit IPAKIT_CLTS_DIR required for the live extraction/parity oracle"
        )
    pytest.importorskip("pyclts")
    return Path(value)


def test_live_core_regeneration_and_exhaustive_unique_set_parity(
    live_source: Path,
) -> None:
    built = clts.build_core(live_source)
    assert built.stale(Path(__file__).resolve().parents[1]) == []
    assert clts.build_core(live_source).artifacts == built.artifacts
    snapshot = clts.read_snapshot()
    report = clts.validate_parity(live_source, snapshot)
    n = len(set(snapshot.geometry.values.values()))
    assert report["unique_sets"] == n
    assert report["pairs_including_diagonal"] == n * (n + 1) // 2
    assert report["keys"] == len(snapshot.geometry.values)


def test_live_supplied_tokens_preserve_composite_and_marker_outcomes(
    live_source: Path,
) -> None:
    snapshot = clts.extract_snapshot(live_source, tokens=["ai", "ia", "_", "nonsense"])
    assert snapshot.to_data()["domain"] == "supplied-tokens"
    assert {"from_open", "to_close", "diphthong"} <= snapshot.features("ai")
    assert snapshot.to_data()["excluded"] == {
        "_": "marker",
        "nonsense": "unknown-sound",
    }
    assert clts.validate_parity(live_source, snapshot)["keys"] == 2


def test_live_changed_consumed_input_is_refused(
    live_source: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = Path.read_bytes

    def changed(path: Path) -> bytes:
        data = original(path)
        return (
            data + b"\n"
            if path == live_source / "pkg/transcriptionsystems/features.json"
            else data
        )

    monkeypatch.setattr(Path, "read_bytes", changed)
    with pytest.raises(SourceContentError, match="accepted bytes"):
        clts.validate_source(live_source)


def test_live_changed_provider_content_is_refused(
    live_source: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = Path.read_bytes

    def changed(path: Path) -> bytes:
        data = original(path)
        return (
            data + b"\n"
            if path.name == "models.py" and path.parent.name == "pyclts"
            else data
        )

    monkeypatch.setattr(Path, "read_bytes", changed)
    with pytest.raises(SourceContentError, match="pyclts source differs"):
        clts.extract_snapshot(live_source)
