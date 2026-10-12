"""Corpus-v2 lean routing, lossless fallback, and refusal witnesses."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import ipakit
import pytest
from ipakit import Form, FormBuilder, Interval, Timing, _corpus
from ipakit._clts_import import import_tokens
from ipakit._containment_projection import ContainmentProjectionInput
from ipakit._graph_facts import (
    ClockNode,
    Declarations,
    Event,
    EventGroup,
    Relation,
    RelationDeclaration,
    TierDeclaration,
)
from ipakit._rewrite_graph import japanese_moraic_fixture


def _stored(corpus: _corpus.Corpus, entry_id: str) -> bytes:
    return corpus._entry_path(entry_id).read_bytes()


def _round_trip(tmp_path: Path, name: str, form: Form) -> tuple[Form, bytes]:
    corpus = _corpus.create(tmp_path / name)
    corpus.add("witness", {}, {"cited": form})
    restored = _corpus.open(tmp_path / name).read("witness").forms["cited"]
    assert restored == form
    assert restored.to_dict() == form.to_dict()
    return restored, _stored(corpus, "witness")


def _relation_form() -> Form:
    declarations = Declarations(
        (TierDeclaration("token"),),
        (),
        (RelationDeclaration("links"),),
    )
    group = EventGroup("token", (Event({}), Event({})))
    clock = (ClockNode(groups=(group,)),)
    paths = ("/clock/0/token/0", "/clock/0/token/1")
    source = ContainmentProjectionInput.from_facts(
        declarations,
        clock,
        (Relation((paths[0],), "links", (paths[1],)),),
        (paths[0],),
    )
    return Form._from_projection_input(source, features=ipakit.load_ipa_features())


def _boundary_witness() -> Form:
    builder = FormBuilder()
    builder.append_ipa("a", strict=True)
    builder.add_event("boundary", {}, duration=0)
    return builder.build()


def _source_profile_form() -> Form:
    imported = import_tokens(["p", "a"], unsupported="preserve")
    return Form.from_dict(imported.to_data()["form"])


def test_ordinary_and_untimed_intervals_use_proven_lean_entries(tmp_path: Path):
    ordinary = ipakit.read("ˈkæt.dɒɡ")
    restored, stored = _round_trip(tmp_path, "ordinary", ordinary)
    assert stored[:1] == b"L"
    assert restored.to_ipa("exact") == "ˈkæt.dɒɡ"

    inventory = ipakit.load_ipa_features()
    parsed = inventory.read("pə.ti.t‿a.mi", strict=True)
    interval = Form.of(
        parsed.units,
        (
            Interval("syllable", 0, 2, inventory),
            Interval("syllable", 3, 5, inventory),
            Interval("syllable", 6, 9, inventory),
            Interval("syllable", 10, 12, inventory),
        ),
    )
    _, stored = _round_trip(tmp_path, "interval", interval)
    assert stored[:1] == b"L"

    zero = inventory.read("le∅ʃ", strict=True)
    _, stored = _round_trip(tmp_path, "zero", zero)
    assert stored[:1] == b"L"


def test_timed_relation_moraic_boundary_and_source_forms_fall_back(tmp_path: Path):
    inventory = ipakit.load_ipa_features()
    base = inventory.read("a", strict=True).units[0]
    timed = Form.of((dataclasses.replace(base, timing=Timing(0.1, 0.2)),))
    witnesses = {
        "timed": timed,
        "relation": _relation_form(),
        "moraic": japanese_moraic_fixture("hot", inventory),
        "boundary": _boundary_witness(),
        "source": _source_profile_form(),
    }
    for name, form in witnesses.items():
        restored, stored = _round_trip(tmp_path, name, form)
        assert stored[:1] == b"N", name
        assert restored.to_dict() == form.to_dict()
        assert _corpus.validate(tmp_path / name).valid


def test_unit_constructed_form_falls_back_without_losing_resolved_views(
    tmp_path: Path,
) -> None:
    inventory = ipakit.load_ipa_features()
    original = Form.of(inventory.read("ab", strict=True).units)

    restored, stored = _round_trip(tmp_path, "unit-constructed", original)

    assert stored[:1] == b"N"
    assert restored.at("/clock/0/segment/0") == original.at("/clock/0/segment/0")


def test_boundary_clock_answers_survive_fallback(tmp_path: Path):
    original = _boundary_witness()
    restored, stored = _round_trip(tmp_path, "boundary-clock", original)
    assert stored[:1] == b"N"
    for path in ("/clock/1", "/clock/1/gaps/1"):
        try:
            expected = original.at(path)
        except Exception as expected_error:  # noqa: BLE001 - compare public refusal
            with pytest.raises(type(expected_error)):
                restored.at(path)
        else:
            assert restored.at(path) == expected


def test_custom_inventory_refuses_at_write_read_and_query(tmp_path: Path):
    custom = ipakit.load_ipa_features(supplements=["aspirated-stops"])
    custom_form = custom.read("tʰ", strict=True)
    corpus = _corpus.create(tmp_path / "corpus")
    with pytest.raises(_corpus.CorpusInventoryError, match="default inventory"):
        corpus.add("custom", {}, {"cited": custom_form})

    corpus.add("default", {}, {"cited": ipakit.read("a")})
    with pytest.raises(_corpus.CorpusInventoryError, match="default inventory"):
        corpus.read("default", custom)
    with pytest.raises(_corpus.CorpusInventoryError, match="default inventory"):
        list(ipakit.corpus.query(corpus, "[vowel]", role="cited", features=custom))


@pytest.mark.parametrize(
    "mutate,match",
    [
        (lambda manifest: manifest.update(type="foreign.corpus"), "corpus type"),
        (lambda manifest: manifest.update(v=999), "corpus version"),
    ],
)
def test_manifest_stamps_refuse_before_entry_decompression(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutate, match: str
):
    root = tmp_path / "corpus"
    corpus = _corpus.create(root)
    corpus.add("entry", {}, {"cited": _boundary_witness()})
    manifest_path = root / "corpus.json"
    manifest = json.loads(manifest_path.read_bytes())
    mutate(manifest)
    manifest_path.write_bytes(_corpus._json_bytes(manifest))

    def forbidden(*args, **kwargs):
        raise AssertionError("entry decompression ran")

    monkeypatch.setattr(_corpus.zlib, "decompress", forbidden)
    with pytest.raises(_corpus.CorpusError, match=match):
        _corpus.open(root)


@pytest.mark.parametrize(
    "mutate,match",
    [
        (lambda entry: entry.update(type="foreign.entry"), "entry.*type"),
        (lambda entry: entry.update(v=999), "entry.*version"),
        (
            lambda entry: entry["forms"]["cited"].update(type="foreign.form"),
            "form type",
        ),
        (lambda entry: entry["forms"]["cited"].update(v=999), "form version"),
        (
            lambda entry: entry["forms"]["cited"].update(encoding="unknown"),
            "form encoding",
        ),
    ],
)
def test_entry_and_form_stamps_refuse_before_form_decode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutate, match: str
):
    corpus = _corpus.create(tmp_path / "corpus")
    corpus.add("entry", {}, {"cited": ipakit.read("a")})
    path = corpus._entry_path("entry")
    document = _corpus._load_entry_object(path)
    mutate(document)
    path.write_bytes(_corpus._entry_bytes(document))

    def forbidden(*args, **kwargs):
        raise AssertionError("semantic Form decode ran")

    monkeypatch.setattr(_corpus, "_restore_form", forbidden)
    with pytest.raises(_corpus.CorpusError, match=match):
        corpus.read("entry")


def test_storage_discriminator_refuses_before_decompression(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    corpus = _corpus.create(tmp_path / "corpus")
    corpus.add("entry", {}, {"cited": ipakit.read("a")})
    path = corpus._entry_path("entry")
    path.write_bytes(b"X" + path.read_bytes()[1:])

    def forbidden(*args, **kwargs):
        raise AssertionError("decompression ran")

    monkeypatch.setattr(_corpus.zlib, "decompress", forbidden)
    with pytest.raises(_corpus.CorpusError, match="storage encoding"):
        corpus.read("entry")


def test_storage_discriminator_must_match_form_envelopes(tmp_path: Path) -> None:
    corpus = _corpus.create(tmp_path / "corpus")
    corpus.add("entry", {}, {"cited": _boundary_witness()})
    path = corpus._entry_path("entry")
    document = _corpus._load_entry_object(path)
    path.write_bytes(b"L" + _corpus._json_bytes(document))

    with pytest.raises(_corpus.CorpusError, match="disagrees"):
        corpus.read("entry")
    assert [
        finding.code for finding in _corpus.validate(tmp_path / "corpus").findings
    ] == ["entry_storage"]


def test_validation_refuses_entry_stamp_before_form_decode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = _corpus.create(tmp_path / "corpus")
    corpus.add("entry", {}, {"cited": ipakit.read("a")})
    path = corpus._entry_path("entry")
    document = _corpus._load_entry_object(path)
    document["type"] = "foreign.entry"
    path.write_bytes(_corpus._entry_bytes(document))

    def forbidden(*args, **kwargs):
        raise AssertionError("semantic Form decode ran")

    monkeypatch.setattr(_corpus, "_restore_form", forbidden)
    report = _corpus.validate(tmp_path / "corpus")
    assert [finding.code for finding in report.findings] == ["entry_type"]


def test_versionless_form_profile_refuses() -> None:
    document = ipakit.read("a").to_dict()
    profile = next(
        attribute
        for tier in document["graph"]["tiers"]
        for item in tier.get("items", [])
        for attribute in item.get("attributes", [])
        if attribute.get("name") == "form:profile"
    )
    del profile["value"]["version"]
    with pytest.raises(ValueError, match="malformed current Form profile metadata"):
        Form.from_dict(document)


def test_lean_bytes_are_hash_seed_independent(tmp_path: Path) -> None:
    first = _corpus.create(tmp_path / "first")
    second = _corpus.create(tmp_path / "second")
    first.add("same", {"b": 2, "a": 1}, {"cited": ipakit.read("ana")})
    second.add("same", {"a": 1, "b": 2}, {"cited": ipakit.read("ana")})
    assert _stored(first, "same") == _stored(second, "same")
    assert json.loads(_stored(first, "same")[1:])["v"] == 2
