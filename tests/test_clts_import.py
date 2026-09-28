"""Public strict CLTS import, plan-final slice D1."""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
from array import array
from collections import UserString

import ipakit
import pytest
from ipakit import _clts_import as adapter
from ipakit import _clts_profile as profile
from ipakit import clts, clts_mapping
from ipakit._clts_input import FORMAT, HOST, InputError
from ipakit.clts import CLTSInputError, import_document, import_tokens

P = {
    "domain": "core-bipa",
    "manifest": "sha256:2d8aa509068014cbec6a3fb017f6ed6fd72e98b0b02eeeec03dd86eb2408070b",
    "mapping": "sha256:d8d67f8a076a6e44ef5f2f908aff74febfe8dabd9fa0c333f8baee57c94603be",
    "profile": "sha256:ed846c398e47326cfb6fcbbb3133c5ab2cc06703f34db7d9b2ae0fe96cf3ee3e",
    "snapshot": "sha256:8b5620aed4b88e6d14d02ddbd6e404fbe9bf9b13577851acd244a95b5793dcc4",
}
SCHEMA = {"id": "ipakit-clts-import-result", "version": 1}


def supported(raw: str, token: int) -> dict[str, object]:
    return {
        "projection": {
            "facts": [{"house-kind": "segment", "house-symbol": raw}],
            "status": "supported",
        },
        "raw": raw,
        "resolution": {"canonical": raw, "status": "resolved"},
        "token": token,
    }


@pytest.fixture(autouse=True)
def clear_import_cache():
    adapter._cache_clear()
    yield
    adapter._cache_clear()


def error(callable_, code: str, path: str | None = "") -> CLTSInputError:
    with pytest.raises(CLTSInputError) as caught:
        callable_()
    assert (caught.value.code, caught.value.path) == (code, path)
    return caught.value


def test_d1_1_complete_literal_and_house_form_round_trip():
    result = import_tokens(["p", "b", "t", "d", "p"])
    expected = {
        "changes": [],
        "diagnostics": [],
        "house_complete": True,
        "occurrences": [
            supported("p", 0),
            supported("b", 1),
            supported("t", 2),
            supported("d", 3),
            supported("p", 4),
        ],
        "provenance": P,
        "schema": SCHEMA,
        "source_complete": True,
        "status": "complete",
    }
    assert result.report() == expected
    assert result.to_data()["report"] == expected
    assert result.to_data()["form"] is not None
    form = result.house_form()
    assert form.to_ipa() == "pbtdp"
    assert len(form.units) == 5
    restored = ipakit.read_json(form.to_json())
    assert restored.to_json() == form.to_json()
    assert "clts-source" not in form.to_json()
    assert json.loads(result.to_json()) == result.to_data()
    assert json.loads(result.to_json(pretty=True)) == result.to_data()


def test_d1_2_strict_refusal_drops_graph_and_blocks_house_form():
    result = import_tokens(["p", "a"])
    assert result.status == "refused"
    assert result.graph is None
    assert result.report()["occurrences"][0] == supported("p", 0)
    caught = error(result.house_form, "house-incomplete", None)
    assert "1 (outside-reviewed-token-context)" in str(caught)


def test_d1_3_diagnostics_take_resolution_cause_before_projection():
    report = import_tokens(["+", "☃", " ɺ̣", "a", "ts", "tˢ"]).report()
    assert [(d["code"], d["stage"]) for d in report["diagnostics"]] == [
        ("marker", "resolution"),
        ("outside-artifact-domain", "resolution"),
        ("unknown-sound", "resolution"),
        ("outside-reviewed-token-context", "house-projection"),
        ("unasserted-house-juncture", "house-projection"),
        ("unasserted-house-juncture", "house-projection"),
    ]


def test_d1_4_string_requires_segmentation():
    error(lambda: import_tokens("pb"), "segmentation-required")  # type: ignore[arg-type]


def test_d1_5_user_string_requires_segmentation():
    error(
        lambda: import_tokens(UserString("pb")),  # type: ignore[arg-type]
        "segmentation-required",
    )


@pytest.mark.parametrize(
    "value",
    [array("u", "pb"), (x for x in ["p", "b"]), b"pb", {"raw": "p"}],
)
def test_d1_6_other_iterables_are_invalid(value):
    error(lambda: import_tokens(value), "invalid-input")  # type: ignore[arg-type]


def test_d1_7_shorthand_elements_are_not_stringified():
    caught = error(lambda: import_tokens(["p", 1]), "invalid-input")  # type: ignore[list-item]
    assert str(caught) == "shorthand is an array of strings"


@pytest.mark.parametrize("value", [["p"], (("format", FORMAT),)])
def test_d1_8_document_requires_a_dict(value):
    error(lambda: import_document(value), "invalid-input")  # type: ignore[arg-type]


def test_d1_8_document_string_requires_segmentation():
    error(
        lambda: import_document("pb"),  # type: ignore[arg-type]
        "segmentation-required",
    )


def test_d1_9_house_form_appends_one_fact_at_a_time(monkeypatch):
    from ipakit.form import FormBuilder

    calls = []
    original = FormBuilder.append_ipa

    def recording(self, text, *, strict=False):
        calls.append((text, strict))
        return original(self, text, strict=strict)

    monkeypatch.setattr(FormBuilder, "append_ipa", recording)
    import_tokens(["p", "b"]).house_form()
    assert calls == [("p", True), ("b", True)]


def test_d1_10_raws_are_exact_and_resolution_canonical_is_reported():
    raws = [" p", "tˢ", "ç", "ç"]
    occurrences = import_tokens(raws).report()["occurrences"]
    assert [row["raw"] for row in occurrences] == raws
    assert [row["resolution"] for row in occurrences] == [
        {"status": "outside-artifact-domain"},
        {"canonical": "ts", "status": "resolved"},
        {"canonical": "ç", "status": "resolved"},
        {"canonical": "ç", "status": "resolved"},
    ]


@pytest.mark.parametrize(
    "raws",
    [["p", "a"], ["⁵", "☃"]],
)
def test_d1_11_invalid_hosts_raise_before_refusal(raws):
    document = {
        "format": FORMAT,
        "version": 1,
        "tokens": [{"raw": raw} for raw in raws],
        "relations": [{"type": HOST, "source": "/tokens/0", "target": "/tokens/1"}],
    }
    error(lambda: import_document(document), "invalid-host", "/relations/0")


def test_d1_12_decoder_refusal_is_wrapped_with_literal_wire_form():
    document = {"format": FORMAT, "version": 1, "tokens": [{"raw": ""}]}
    caught = error(lambda: import_document(document), "invalid-input", "/tokens/0/raw")
    assert isinstance(caught.__cause__, InputError)
    assert caught.to_data() == {
        "error": {
            "code": "invalid-input",
            "message": "raw must be a nonempty string",
            "path": "/tokens/0/raw",
        },
        "form": None,
    }
    with pytest.raises(AttributeError):
        caught.code = "changed"  # type: ignore[misc]


def test_d1_13_environment_failures_keep_distinct_unlocated_codes(monkeypatch):
    def stale(*args, **kwargs):
        raise clts.ArtifactInvalid("stale test manifest")

    monkeypatch.setattr(profile, "verify_manifest", stale)
    caught = error(lambda: import_tokens(["p"]), "artifact-invalid", None)
    assert caught.to_data() == {
        "error": {"code": "artifact-invalid", "message": "stale test manifest"},
        "form": None,
    }

    adapter._cache_clear()
    monkeypatch.undo()

    def wrong_basis(self, spec):
        raise clts_mapping.MappingInvalid("wrong test basis")

    monkeypatch.setattr(
        clts_mapping.MappingAuthority, "_require_profile_basis", wrong_basis
    )
    caught = error(lambda: import_tokens(["p"]), "mapping-invalid", None)
    assert "path" not in caught.to_data()["error"]


def test_d1_14_verified_binding_is_process_cached(monkeypatch):
    calls = 0
    original = profile.verify_manifest

    def recording(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(profile, "verify_manifest", recording)
    import_tokens(["p"])
    first = calls
    assert first > 0
    import_tokens(["b"])
    assert calls == first


def test_d1_15_projection_records_are_memoized_per_raw(monkeypatch):
    calls = []
    original = clts_mapping.MappingAuthority._projection_record

    def recording(self, raw, snapshot, spec):
        calls.append(raw)
        return original(self, raw, snapshot, spec)

    monkeypatch.setattr(clts_mapping.MappingAuthority, "_projection_record", recording)
    import_tokens(["p", "p", "b"])
    assert calls == ["p", "b"]
    calls.clear()
    import_tokens(["p"])
    assert calls == []


def test_d1_16_empty_import_is_complete_with_a_graph_and_empty_form():
    result = import_tokens([])
    assert result.report() == {
        "changes": [],
        "diagnostics": [],
        "house_complete": True,
        "occurrences": [],
        "provenance": P,
        "schema": SCHEMA,
        "source_complete": True,
        "status": "complete",
    }
    assert result.graph is not None
    assert result.house_form().units == ()


def test_d1_17_provenance_and_schema_are_hand_pinned():
    report = import_tokens(["p"]).report()
    assert report["provenance"] == P
    assert report["schema"] == SCHEMA


def test_d1_18_public_views_and_caller_input_are_detached():
    source = ["p", "b"]
    result = import_tokens(source)
    expected_report = result.report()
    expected_source = result.source_document()
    report = result.report()
    document = result.source_document()
    report["occurrences"][0]["raw"] = "x"
    document["tokens"][0]["raw"] = "x"
    source[0] = "x"
    assert result.report() == expected_report
    assert result.source_document() == expected_source
    assert result.source_tokens() == ("p", "b")


def test_d1_19_native_restore_retains_document_and_full_facts():
    document = {
        "format": FORMAT,
        "version": 1,
        "tokens": [{"raw": "p"}, {"raw": "b"}],
        "relations": [],
    }
    result = import_document(document)
    restored, _, projections = profile.restore(result.graph, profile.core_bipa_spec())
    assert restored == document
    assert projections == (
        {
            "mapping": P["mapping"],
            "status": "supported",
            "facts": [{"house-kind": "segment", "house-symbol": "p"}],
        },
        {
            "mapping": P["mapping"],
            "status": "supported",
            "facts": [{"house-kind": "segment", "house-symbol": "b"}],
        },
    )


def test_d1_20_only_the_four_d1_names_are_exported_from_clts():
    for name in ("import_tokens", "import_document", "CLTSImport", "CLTSInputError"):
        assert hasattr(clts, name)
        assert name not in ipakit.__all__
    assert not hasattr(clts, "load_import")


def test_d1_22_runtime_import_does_not_need_pyclts():
    code = r"""
import builtins
original = builtins.__import__
def blocked(name, *args, **kwargs):
    if name.split('.')[0] == 'pyclts':
        raise AssertionError('pyclts import attempted')
    return original(name, *args, **kwargs)
builtins.__import__ = blocked
from ipakit.clts import import_tokens
print(import_tokens(['p']).status)
"""
    completed = subprocess.run(
        [sys.executable, "-c", code], text=True, capture_output=True, check=False
    )
    assert (completed.returncode, completed.stdout, completed.stderr) == (
        0,
        "complete\n",
        "",
    )


@pytest.mark.parametrize(
    "module",
    [
        "ipakit._clts_profile",
        "ipakit.clts_mapping",
        "ipakit._clts_import",
        "ipakit.clts",
    ],
)
def test_d1_23_each_import_path_is_fresh_importable(module):
    completed = subprocess.run(
        [sys.executable, "-c", f"import {module}"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert (completed.returncode, completed.stderr) == (0, "")


@pytest.mark.parametrize(
    "facts",
    [
        [{"house-kind": "tone", "house-symbol": "p"}],
        [{"house-kind": "segment", "house-symbol": "ts"}],
        [
            {"house-kind": "segment", "house-symbol": "p"},
            {"house-kind": "segment", "house-symbol": "b"},
        ],
    ],
)
def test_d1_24_house_form_refuses_nonsegment_or_multiunit_facts(monkeypatch, facts):
    def projection(self, raw, snapshot, spec):
        return {
            "mapping": spec.mapping_identity,
            "status": "supported",
            "facts": facts,
        }

    monkeypatch.setattr(clts_mapping.MappingAuthority, "_projection_record", projection)
    result = import_tokens(["p"])
    caught = error(result.house_form, "house-incomplete", None)
    assert "0 (invalid-house-fact)" in str(caught)


def test_envelope_bytes_are_canonical_compact_and_unescaped():
    text = import_tokens(["p", "a", "+", "tˢ", "p"]).to_json()
    assert len(text) == 1543
    assert text.startswith('{"form":null,"report":{"changes":[],"diagnostics":[{')
    assert '"raw":"tˢ"' in text
    assert "\\u" not in text
    assert ", " not in text and ": " not in text


def test_d1_25_resolved_occurrence_must_have_exactly_one_sound(monkeypatch):
    original = profile.core_bipa_resolutions

    def doubled(snapshot, raws):
        records = list(original(snapshot, raws))
        records[0] = {**records[0], "sounds": records[0]["sounds"] * 2}
        return tuple(records)

    monkeypatch.setattr(profile, "core_bipa_resolutions", doubled)
    error(lambda: import_tokens(["p"]), "artifact-invalid", None)


def test_d1_26_report_records_are_reduced_in_every_d1_literal():
    reports = [
        import_tokens(["p", "b"]).report(),
        import_tokens([]).report(),
        import_tokens(["p", "a", "+", "tˢ", "p"]).report(),
    ]
    for report in reports:
        for occurrence in report["occurrences"]:
            assert "mapping" not in occurrence["projection"]
            expected = (
                {"canonical", "status"}
                if occurrence["resolution"]["status"] == "resolved"
                else {"status"}
            )
            assert set(occurrence["resolution"]) == expected


def test_c_d1a_not_attempted_eligibility_reason_is_pinned():
    snapshot = profile.read_snapshot()
    spec = profile.core_bipa_spec()
    row = clts_mapping.read_authority().eligibility("+", snapshot, profile=spec)
    assert row["reason"] == "not-attempted"
    assert row["projection"]["status"] == "not-attempted"


def test_c_d1b_projection_coverage_remains_preserved():
    assert (
        profile.projection_coverage([{"status": "unsupported"}])["status"]
        == "preserved"
    )


def test_c_d1c_import_ipakit_does_not_import_clts():
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, ipakit; assert 'ipakit.clts' not in sys.modules",
        ],
        check=False,
    )
    assert completed.returncode == 0


def test_c_d1d_load_ipa_features_is_not_an_import_reader():
    assert inspect.isfunction(clts.load_ipa_features)
    assert clts.load_ipa_features.__module__ == "ipakit"
