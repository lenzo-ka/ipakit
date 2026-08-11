from __future__ import annotations

import json
from pathlib import Path

import ipakit
import ipakit.form as form_module
import pytest
from ipakit import _corpus
from ipakit._tiergraph_json import identity_fingerprint
from ipakit.form import Form


def _form(text: str) -> Form:
    return ipakit.read(text)


@pytest.mark.parametrize("text", ["ˈkæt", "#kæt#", "ˈkæt.dɒɡ"])
def test_round_trip_and_canonical_entry_bytes(tmp_path: Path, text: str):
    corpus = _corpus.create(tmp_path / "speech")
    original = _form(text)
    corpus.add("utt-001", {"text": "cat", "n": 1}, {"utt": original})
    before = (tmp_path / "speech" / "entries" / "utt-001.json").read_bytes()

    reopened = _corpus.open(tmp_path / "speech")
    assert reopened.read("utt-001").forms["utt"] == original
    assert before == (tmp_path / "speech" / "entries" / "utt-001.json").read_bytes()
    assert before.endswith(b"\n")
    assert b'"features"' in before


def test_same_form_has_identical_entry_bytes(tmp_path: Path):
    form = _form("#kæt#")
    first = _corpus.create(tmp_path / "first")
    second = _corpus.create(tmp_path / "second")

    first.add("same", {}, {"utt": form})
    second.add("same", {}, {"utt": form})

    assert (tmp_path / "first" / "entries" / "same.json").read_bytes() == (
        tmp_path / "second" / "entries" / "same.json"
    ).read_bytes()


def test_put_form_preserves_entry_and_replaces_only_named_role(tmp_path: Path):
    corpus = _corpus.create(tmp_path / "corpus")
    source = _form("kæt")
    first = _form("dɒɡ")
    second = _form("bɜːd")
    corpus.add("word", {"text": "cat"}, {"source": source})

    written = corpus.put_form("word", "aligned", first)
    assert written.meta == {"text": "cat"}
    assert written.forms == {"source": source, "aligned": first}
    corpus.put_form("word", "aligned", second)

    restored = _corpus.open(tmp_path / "corpus").read("word")
    assert restored.meta == {"text": "cat"}
    assert restored.forms == {"source": source, "aligned": second}


def test_role_provenance_and_corpus_declaration_identity_are_additive(tmp_path: Path):
    identity = {"provider": "test", "features": ["phone"]}
    corpus = _corpus.create(tmp_path / "corpus", declaration_identity=identity)
    corpus.add("word", {}, {"source": _form("a")})
    provenance = _corpus.FormProvenance(
        _corpus.Producer("aligner", "sha256:abc"), identity_fingerprint(identity)
    )
    corpus.put_form("word", "aligned", _form("b"), provenance)

    reopened = _corpus.open(tmp_path / "corpus")
    assert reopened.declaration_fingerprint == identity_fingerprint(identity)
    assert reopened.read("word").provenance == {"aligned": provenance}

    legacy = json.loads((tmp_path / "corpus" / "entries" / "word.json").read_text())
    legacy.pop("provenance")
    (tmp_path / "corpus" / "entries" / "word.json").write_text(json.dumps(legacy))
    assert _corpus.open(tmp_path / "corpus").read("word").provenance == {}


def test_named_split_is_explicit_durable_and_refuses_stale_ids(tmp_path: Path):
    root = tmp_path / "corpus"
    corpus = _corpus.create(root)
    corpus.add("one", {}, {})
    corpus.add("two", {}, {})
    assert corpus.put_split("test", ["two"]) == ("two",)
    corpus.add("three", {}, {})
    assert _corpus.open(root).split("test") == ("two",)

    corpus.remove("two")
    with pytest.raises(_corpus.CorpusError, match="missing entries"):
        corpus.split("test")


def test_self_contained_views_survive_changed_ambient_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    corpus = _corpus.create(tmp_path / "corpus")
    original = _form("ˈkæt.dɒɡ")
    stored_views = tuple(
        (dict(unit.features), dict(unit.prosody), unit.provenance)
        for unit in original.units
    )
    corpus.add("word", {}, {"utt": original})

    monkeypatch.setattr(
        form_module,
        "_resolve_unit_views",
        lambda segment, inventory: (
            {"revised": True},
            {"stress": "revised"},
            (("revised", segment.to_ipa(), "inventory"),),
        ),
    )
    restored = _corpus.open(tmp_path / "corpus").read("word").forms["utt"]

    assert restored == original
    assert (
        tuple(
            (dict(unit.features), dict(unit.prosody), unit.provenance)
            for unit in restored.units
        )
        == stored_views
    )


def test_order_and_bytes_do_not_depend_on_add_order(tmp_path: Path):
    first = _corpus.create(tmp_path / "first")
    second = _corpus.create(tmp_path / "second")
    entries = {
        "b": ({"z": 2, "a": 1}, {"target": _form("b")}),
        "a": ({"text": "a"}, {"source": _form("a")}),
    }
    for entry_id in ("b", "a"):
        first.add(entry_id, *entries[entry_id])
    for entry_id in ("a", "b"):
        second.add(entry_id, *entries[entry_id])

    assert list(first.ids()) == list(second.ids()) == ["a", "b"]
    for entry_id in entries:
        assert (tmp_path / "first" / "entries" / f"{entry_id}.json").read_bytes() == (
            tmp_path / "second" / "entries" / f"{entry_id}.json"
        ).read_bytes()


def test_ids_do_not_read_or_restore_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """ID iteration must not open an entry document or restore its forms."""
    corpus = _corpus.create(tmp_path / "corpus")
    corpus.add("one", {}, {"utt": _form("a")})

    def forbid_read_text(*args: object, **kwargs: object) -> str:
        raise AssertionError("ID iteration opened an entry document")

    def forbidden(*args: object, **kwargs: object) -> Form:
        raise AssertionError("ID iteration restored a form")

    monkeypatch.setattr(Path, "read_text", forbid_read_text)
    monkeypatch.setattr(Form, "from_dict", forbidden)
    assert list(corpus.ids()) == ["one"]


def test_assets_absence_orphans_missing_and_cascade(tmp_path: Path):
    root = tmp_path / "corpus"
    corpus = _corpus.create(root)
    corpus.add("one", {}, {"utt": _form("a")})
    corpus.add("two", {}, {"utt": _form("b")})
    (root / "wav").mkdir()
    (root / "wav" / "one.wav").write_bytes(b"RIFF")
    (root / "wav" / "orphan.wav").write_bytes(b"RIFF")
    (root / "textgrid").mkdir()
    (root / "textgrid" / "one.TextGrid").write_text("", encoding="utf-8")

    assert corpus.asset("one", "wav") == root / "wav" / "one.wav"
    assert corpus.asset("two", "wav") is None
    assert corpus.asset_kinds() == ("textgrid", "wav")
    codes = [finding.code for finding in _corpus.validate(root).findings]
    assert "orphan_asset" in codes
    assert "missing_asset" in codes

    corpus.remove("one")
    assert not (root / "wav" / "one.wav").exists()
    assert not (root / "textgrid" / "one.TextGrid").exists()


def test_distinct_tamper_findings(tmp_path: Path):
    root = tmp_path / "corpus"
    corpus = _corpus.create(root)
    corpus.add("good", {}, {"utt": _form("a")})
    original = json.loads((root / "entries" / "good.json").read_text())

    bad_version = dict(original)
    bad_version["id"] = "versioned"
    bad_version["forms"] = dict(original["forms"])
    bad_version["forms"]["utt"] = dict(original["forms"]["utt"])
    bad_version["forms"]["utt"]["v"] = 999
    (root / "entries" / "versioned.json").write_text(json.dumps(bad_version))

    mismatch = dict(original)
    mismatch["id"] = "shared"
    (root / "entries" / "mismatch.json").write_text(json.dumps(mismatch))
    duplicate = dict(original)
    duplicate["id"] = "shared"
    (root / "entries" / "duplicate.json").write_text(json.dumps(duplicate))
    invalid = dict(original)
    invalid["id"] = "../bad"
    (root / "entries" / "invalid.json").write_text(json.dumps(invalid))

    findings = _corpus.validate(root).findings
    codes = {finding.code for finding in findings}
    assert {
        "form_version",
        "duplicate_id",
        "id_filename_mismatch",
        "invalid_id",
    } <= codes


def test_add_rejects_invalid_and_duplicate_ids(tmp_path: Path):
    corpus = _corpus.create(tmp_path / "corpus")
    with pytest.raises(_corpus.CorpusError, match="invalid entry id"):
        corpus.add("../escape", {}, {})
    corpus.add("same", {}, {})
    with pytest.raises(_corpus.CorpusError, match="duplicate entry id"):
        corpus.add("same", {}, {})


def test_apostrophe_is_filesystem_safe_in_entry_ids(tmp_path: Path):
    corpus = _corpus.create(tmp_path / "corpus")
    corpus.add("tom's", {}, {})
    assert list(corpus.ids()) == ["tom's"]


def test_create_and_open_layout_contract(tmp_path: Path):
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "file").touch()
    with pytest.raises(_corpus.CorpusError, match="not empty"):
        _corpus.create(occupied)
    with pytest.raises(_corpus.CorpusError, match="invalid corpus layout"):
        _corpus.open(tmp_path)

    root = tmp_path / "version"
    _corpus.create(root)
    (root / "corpus.json").write_text('{"type":"ipakit.corpus","v":999}\n')
    with pytest.raises(_corpus.CorpusError, match="unsupported corpus version"):
        _corpus.open(root)
