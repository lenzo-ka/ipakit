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
        == "0f3046ac49d6ff0abdcf1aa87430f14c3b9afbe7bc169a5bb64e0a65bae32106"
    )
    assert feature_models.read("panphon") == read_ternary_declaration(path)
    assert not (Path(__file__).parent / "panphon/panphon.xml").exists()


def test_original_payload_differs_only_in_corrected_project_url():
    current = feature_models.resource_path("panphon").read_bytes()
    original = current.replace(
        b'upstream-url="https://github.com/dmort27/panphon"',
        b'upstream-url="https://github.com/dmort27/panphon/tree/0.22.2"',
        1,
    )
    assert current != original
    assert (
        hashlib.sha256(original).hexdigest()
        == "f2c9dda2abdfd6394c8f000bf4f4ae0fe10f41a47b90b7ff3fb89440026646b1"
    )


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
