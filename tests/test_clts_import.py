"""Public CLTS import, plan-final slices D1, D2 and E1."""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
from array import array
from collections import UserString
from pathlib import Path

import ipakit
import pytest
from ipakit import _clts_import as adapter
from ipakit import _clts_profile as profile
from ipakit import clts, clts_mapping
from ipakit._clts_input import FORMAT, HOST, InputError
from ipakit.clts import CLTSInputError, import_document, import_tokens, load_import

import tiergraph as tg

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


def test_d1_20_d2_11_only_the_five_import_names_are_exported_from_clts():
    for name in (
        "import_tokens",
        "import_document",
        "load_import",
        "CLTSImport",
        "CLTSInputError",
    ):
        assert hasattr(clts, name)
        assert name not in ipakit.__all__


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
    assert len(text) == 1543  # characters
    assert len(text.encode("utf-8")) == 1544
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


def _forged_graph(*, resolution_raw: str, projection_raw: str):
    snapshot = profile.read_snapshot()
    authority = clts_mapping.read_authority()
    spec = profile.core_bipa_spec(snapshot, mapping_identity=authority.identity)
    document = {"format": FORMAT, "version": 1, "tokens": [{"raw": "p"}]}
    resolutions = profile.core_bipa_resolutions(snapshot, [resolution_raw])
    projections = [
        authority._projection_record(projection_raw, snapshot, spec)  # noqa: SLF001
    ]
    return profile.construct(document, resolutions, projections, spec), spec


def test_d2_1_string_bytes_and_dict_round_trips_rebuild_source_document():
    timed = {
        "format": FORMAT,
        "version": 1,
        "tokens": [
            {"raw": "t", "time": {"start": 1.25, "duration": 0.5}},
            {"raw": "⁵"},
        ],
        "relations": [
            {
                "type": HOST,
                "source": "/tokens/1",
                "target": "/tokens/0",
            }
        ],
    }
    cases = [
        (
            import_tokens(["p", "b"]),
            {
                "format": FORMAT,
                "version": 1,
                "tokens": [{"raw": "p"}, {"raw": "b"}],
            },
        ),
        (
            import_tokens(["p", "a"]),
            {
                "format": FORMAT,
                "version": 1,
                "tokens": [{"raw": "p"}, {"raw": "a"}],
            },
        ),
        (import_tokens([]), {"format": FORMAT, "version": 1, "tokens": []}),
        (import_document(timed), timed),
    ]
    for original, source in cases:
        text = original.to_json()
        for saved in (text, text.encode("utf-8"), json.loads(text)):
            loaded = load_import(saved)
            assert loaded.to_json().encode("utf-8") == text.encode("utf-8")
            assert loaded.source_document() == source


def test_d2_2_forged_projection_graph_is_refused_without_restore():
    envelope = import_tokens(["p"]).to_data()
    forged, _ = _forged_graph(resolution_raw="p", projection_raw="b")
    envelope["form"] = tg.to_data(forged)
    with pytest.raises(CLTSInputError) as caught:
        load_import(envelope)
    assert caught.value.code == "import-mismatch"
    assert caught.value.path is not None and caught.value.path.startswith("/form")


def test_d2_3_forged_resolution_graph_is_refused_without_restore():
    envelope = import_tokens(["p"]).to_data()
    forged, _ = _forged_graph(resolution_raw="b", projection_raw="p")
    envelope["form"] = tg.to_data(forged)
    with pytest.raises(CLTSInputError) as caught:
        load_import(envelope)
    assert caught.value.code == "import-mismatch"


def test_d2_4_edited_report_raw_is_refused():
    envelope = import_tokens(["p"]).to_data()
    envelope["report"]["occurrences"][0]["raw"] = "b"
    with pytest.raises(CLTSInputError) as caught:
        load_import(envelope)
    assert caught.value.code == "import-mismatch"


def test_d2_5_provenance_is_checked_before_whole_envelope_comparison():
    envelope = import_tokens(["p"]).to_data()
    envelope["report"]["provenance"]["mapping"] = "sha256:" + "0" * 64
    error(
        lambda: load_import(envelope),
        "provenance-mismatch",
        "/report/provenance/mapping",
    )


def _invalid_envelopes():
    complete = import_tokens(["p"]).to_data()
    refused = import_tokens(["p", "a"]).to_data()
    refused_text = import_tokens(["p", "a"]).to_json()

    complete_without_form = json.loads(json.dumps(complete))
    complete_without_form["form"] = None
    refused_with_form = json.loads(json.dumps(refused))
    refused_with_form["form"] = complete["form"]
    extra_key = json.loads(json.dumps(complete))
    extra_key["extra"] = None
    return [
        complete_without_form,
        refused_with_form,
        extra_key,
        refused_text.replace('{"form":null,', '{"form":null,"form":null,', 1),
        refused_text.replace('"token":0', '"token":NaN', 1),
        {
            "error": {"code": "invalid-input", "message": "bad", "path": ""},
            "form": None,
        },
    ]


@pytest.mark.parametrize(
    "envelope",
    _invalid_envelopes(),
    ids=[
        "complete-null",
        "refused-form",
        "extra-key",
        "duplicate-key",
        "nan-text",
        "error-envelope",
    ],
)
def test_d2_6_malformed_envelopes_are_refused(envelope):
    with pytest.raises(CLTSInputError) as caught:
        load_import(envelope)
    assert caught.value.code == "invalid-envelope"


def test_d2_7_reimport_error_is_relocated_into_the_envelope():
    envelope = import_tokens(["p"]).to_data()
    envelope["report"]["occurrences"][0]["time"] = {"start": 0.0}
    error(
        lambda: load_import(envelope),
        "invalid-envelope",
        "/report/occurrences/0/time",
    )


def test_d2_8_unknown_schema_version_is_refused_before_comparison():
    envelope = import_tokens(["p"]).to_data()
    envelope["report"]["schema"]["version"] = 2
    error(
        lambda: load_import(envelope),
        "invalid-envelope",
        "/report/schema/version",
    )


def test_d2_9_canonical_bytes_make_comparison_type_strict():
    envelope = import_tokens(["p"]).to_data()
    envelope["report"]["occurrences"][0]["token"] = False
    error(
        lambda: load_import(envelope),
        "import-mismatch",
        "/report/occurrences/0/token",
    )


def test_d2_10_dict_input_refuses_nonfinite_numbers():
    envelope = import_tokens(["p"]).to_data()
    envelope["report"]["occurrences"][0]["token"] = float("nan")
    error(lambda: load_import(envelope), "invalid-envelope")


def test_d2_11_load_import_is_in_the_declared_reader_set():
    readers = {
        name
        for name, function in inspect.getmembers(clts, inspect.isfunction)
        if not name.startswith("_") and function.__module__ == "ipakit._clts_import"
    }
    assert readers == {"import_tokens", "import_document", "load_import"}


def test_c_d2a_restore_accepts_the_forged_projection_today():
    forged, spec = _forged_graph(resolution_raw="p", projection_raw="b")
    _, _, projections = profile.restore(forged, spec)
    assert projections[0]["facts"] == [{"house-kind": "segment", "house-symbol": "b"}]


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ('"domain":"core-bipa"', '"domain":1e400'),
        ('"format_version":"0.3.0"', '"format_version":-1e309'),
    ],
)
def test_overflowing_float_literal_in_text_is_invalid_envelope(old, new):
    text = import_tokens(["p"]).to_json()
    assert old in text
    error(lambda: load_import(text.replace(old, new, 1)), "invalid-envelope", "")


def test_deeply_nested_text_is_invalid_envelope():
    error(lambda: load_import("[" * 10000 + "]" * 10000), "invalid-envelope", "")


def test_environment_failure_during_reload_keeps_its_code(monkeypatch):
    envelope = import_tokens(["p"]).to_data()
    original = profile.core_bipa_resolutions

    def doubled(snapshot, raws):
        records = original(snapshot, raws)
        for record in records:
            if record["status"] == "resolved":
                record["sounds"] = record["sounds"] + record["sounds"]
        return records

    monkeypatch.setattr(profile, "core_bipa_resolutions", doubled)
    adapter._cache_clear()
    error(lambda: load_import(envelope), "artifact-invalid", None)


def test_empty_relations_are_distinct_from_absent_relations():
    document = {
        "format": FORMAT,
        "version": 1,
        "tokens": [{"raw": "p"}],
        "relations": [],
    }
    reloaded = load_import(import_document(document).to_data())
    assert reloaded.source_document() == document
    forged = import_tokens(["p"]).to_data()
    forged["report"]["relations"] = []
    error(
        lambda: load_import(forged),
        "import-mismatch",
        "/form/graph/tiers/3/items/0/attributes/1/value/relations-present",
    )


PRESERVED_DOCUMENT = {
    "format": FORMAT,
    "version": 1,
    "tokens": [
        {"raw": "t", "time": {"start": 1.25, "duration": 0.5}},
        {"raw": "⁵"},
        {"raw": "☃"},
    ],
    "relations": [{"type": HOST, "source": "/tokens/1", "target": "/tokens/0"}],
}


def test_e1_1_preserved_literal_source_and_reload_round_trip():
    result = import_document(PRESERVED_DOCUMENT, unsupported="preserve")
    expected = {
        "changes": [],
        "diagnostics": [
            {
                "action": "preserved",
                "code": "outside-reviewed-token-context",
                "stage": "house-projection",
                "token": 1,
            },
            {
                "action": "preserved",
                "code": "outside-artifact-domain",
                "stage": "resolution",
                "token": 2,
            },
        ],
        "house_complete": False,
        "occurrences": [
            {
                **supported("t", 0),
                "time": {"duration": 0.5, "start": 1.25},
            },
            {
                "projection": {
                    "code": "outside-reviewed-token-context",
                    "status": "unsupported",
                },
                "raw": "⁵",
                "resolution": {"canonical": "⁵", "status": "resolved"},
                "token": 1,
            },
            {
                "projection": {"status": "not-attempted"},
                "raw": "☃",
                "resolution": {"status": "outside-artifact-domain"},
                "token": 2,
            },
        ],
        "provenance": P,
        "relations": [{"source": "/tokens/1", "target": "/tokens/0", "type": HOST}],
        "schema": SCHEMA,
        "source_complete": True,
        "status": "preserved",
    }
    assert result.report() == expected
    assert result.graph is not None
    assert result.source_document() == PRESERVED_DOCUMENT
    assert load_import(result.to_json()).to_json() == result.to_json()


def test_e1_2_preserved_import_blocks_partial_house_form():
    result = import_document(PRESERVED_DOCUMENT, unsupported="preserve")
    caught = error(result.house_form, "house-incomplete", None)
    assert str(caught) == (
        "house projection incomplete at "
        "1 (outside-reviewed-token-context), 2 (outside-artifact-domain)"
    )


def test_e1_3_preserve_mode_is_strictly_equal_for_supported_input():
    strict = import_tokens(["p"])
    preserved = import_tokens(["p"], unsupported="preserve")
    assert preserved.status == "complete"
    assert preserved.to_json() == strict.to_json()


def test_e1_4_default_option_remains_strict_refusal():
    assert import_tokens(["a"]).status == "refused"


def test_e1_5_input_errors_still_raise_in_preserve_mode():
    invalid_timing = {
        "format": FORMAT,
        "version": 1,
        "tokens": [{"raw": "p", "time": {"start": 0.0}}],
    }
    error(
        lambda: import_document(invalid_timing, unsupported="preserve"),
        "invalid-timing",
        "/tokens/0/time",
    )

    invalid_host = {
        "format": FORMAT,
        "version": 1,
        "tokens": [{"raw": "p"}, {"raw": "a"}],
        "relations": [{"type": HOST, "source": "/tokens/0", "target": "/tokens/1"}],
    }
    error(
        lambda: import_document(invalid_host, unsupported="preserve"),
        "invalid-host",
        "/relations/0",
    )

    multi_host = {
        "format": FORMAT,
        "version": 1,
        "tokens": [{"raw": "t"}, {"raw": "⁵"}, {"raw": "a"}],
        "relations": [
            {"type": HOST, "source": "/tokens/1", "target": "/tokens/0"},
            {"type": HOST, "source": "/tokens/1", "target": "/tokens/2"},
        ],
    }
    error(
        lambda: import_document(multi_host, unsupported="preserve"),
        "invalid-relation",
        "/relations/1/source",
    )


def test_e1_6_unknown_unsupported_option_is_refused():
    caught = error(
        lambda: import_tokens(["p"], unsupported="drop"),  # type: ignore[arg-type]
        "invalid-option",
        None,
    )
    assert caught.to_data() == {
        "error": {
            "code": "invalid-option",
            "message": 'unsupported must be "error" or "preserve"',
        },
        "form": None,
    }


def test_e1_7_preserved_reload_refuses_report_forgery():
    envelope = import_document(PRESERVED_DOCUMENT, unsupported="preserve").to_data()
    envelope["report"]["occurrences"][1]["projection"] = {
        "facts": [{"house-kind": "segment", "house-symbol": "t"}],
        "status": "supported",
    }
    error(
        lambda: load_import(envelope),
        "import-mismatch",
        "/report/occurrences/1/projection/code",
    )

    envelope = import_document(PRESERVED_DOCUMENT, unsupported="preserve").to_data()
    envelope["report"]["status"] = "complete"
    error(
        lambda: load_import(envelope),
        "invalid-envelope",
        "/report/house_complete",
    )


def test_e1_8_public_preserve_import_reproduces_committed_example():
    document = {
        "format": FORMAT,
        "version": 1,
        "tokens": [
            {"raw": "t", "time": {"start": 1.25, "duration": 0.5}},
            {"raw": "⁵"},
            {"raw": "t"},
            {"raw": " ɺ̣"},
            {"raw": "+"},
            {"raw": "☃"},
            {"raw": "ts"},
        ],
        "relations": [{"type": HOST, "source": "/tokens/1", "target": "/tokens/0"}],
    }
    result = import_document(document, unsupported="preserve")
    assert result.graph is not None
    fixture = (
        Path(__file__).parent / "tiergraph" / "fixtures" / "clts_core_bipa_profile.json"
    )
    assert tg.dumps(result.graph) == fixture.read_text()


def test_c_e1a_source_profile_fixture_is_not_a_form():
    fixture = (
        Path(__file__).parent / "tiergraph" / "fixtures" / "clts_core_bipa_profile.json"
    )
    text = fixture.read_text()
    with pytest.raises(ValueError):
        ipakit.Form.from_json(text)
    with pytest.raises(ValueError):
        ipakit.read_json(text)
    assert isinstance(ipakit.read_graph_json(text), tg.Graph)
