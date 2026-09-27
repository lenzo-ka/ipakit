"""Shipped finite resources have one authority, independent of producers."""

import hashlib
from pathlib import Path

import pytest
from ipakit import feature_models
from ipakit.finite_declaration import read_ternary_declaration


def test_named_resource_matches_existing_codec_and_frozen_artifact():
    assert "panphon" in feature_models.available()
    path = feature_models.resource_path("panphon")
    assert (
        hashlib.sha256(path.read_bytes()).hexdigest()
        == "dc782cfbb1fd61cd8845ff0db583bb7095c5f130ec5b06bbc3932bf65375f4da"
    )
    assert feature_models.read("panphon") == read_ternary_declaration(path)
    assert not (Path(__file__).parent / "panphon/panphon.xml").exists()


def test_declaration_has_no_second_source_authority():
    root = feature_models.resource_path("panphon").read_text()
    assert 'source-receipt="panphon-receipt.json"' in root.splitlines()[1]
    for removed in ("upstream=", "version=", "license=", "ipa-all-sha256="):
        assert removed not in root.splitlines()[1]


@pytest.mark.parametrize(
    "name", ["missing", "../panphon", "panphon.xml", "", "/panphon"]
)
def test_unknown_or_path_names_refuse(name):
    with pytest.raises(ValueError, match="supplied declaration"):
        feature_models.read(name)


def test_named_reader_delegates_to_public_codec(monkeypatch):
    called = []
    original = feature_models.read_ternary_declaration

    def witness(path):
        called.append(path)
        return original(path)

    monkeypatch.setattr(feature_models, "read_ternary_declaration", witness)
    feature_models.read("panphon")
    assert called == [feature_models.resource_path("panphon")]
