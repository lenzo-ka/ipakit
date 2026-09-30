"""CLTS convention projection and independently testable token emission."""

from __future__ import annotations

import dataclasses
import json

import pytest
from ipakit import Form
from ipakit.clts import (
    CLTSInputError,
    emit_tokens,
    import_document,
    import_tokens,
    load_import,
)
from ipakit.form import FormProjectionError


def _source_form(*tokens: str, projection: str = "explicit-only") -> Form:
    result = import_tokens(list(tokens), projection=projection, unsupported="preserve")
    assert result.graph is not None
    return Form.from_dict(result.to_data()["form"])


def test_house_convention_is_explicit_and_records_each_assumption() -> None:
    explicit = import_tokens(["ts"])
    conventional = import_tokens(["ts"], projection="house-convention-v1")

    assert explicit.status == "refused"
    assert conventional.status == "complete"
    assert conventional.house_form().to_ipa() == "t͡s"
    assert conventional.report()["changes"] == [
        {
            "token": 0,
            "convention": "house-convention-v1",
            "source": "ts",
            "stage": "house-projection",
            "target": "t͡s",
        }
    ]
    assert conventional.source_tokens() == ("ts",)


def test_convention_assumption_is_recorded_when_spelling_does_not_change() -> None:
    result = import_tokens(["a"], projection="house-convention-v1")

    assert result.status == "complete"
    assert result.report()["changes"][0] == {
        "token": 0,
        "convention": "house-convention-v1",
        "source": "a",
        "stage": "house-projection",
        "target": "a",
    }


def test_explicit_projection_remains_the_default_and_unknown_policy_refuses() -> None:
    assert import_tokens(["ts"]).status == "refused"
    with pytest.raises(CLTSInputError) as caught:
        import_tokens(["p"], projection="guess")  # type: ignore[arg-type]
    assert caught.value.code == "invalid-option"


def test_convention_result_reloads_by_recomputing_the_same_policy() -> None:
    result = import_tokens(["ts", "a"], projection="house-convention-v1")
    restored = load_import(result.to_json())

    assert restored.to_json() == result.to_json()
    assert restored.house_form().to_ipa() == "t͡sa"


def test_source_emission_is_exact_and_independent_of_house_coverage() -> None:
    result = import_tokens(["t͜s", "☃"], unsupported="preserve")
    emission = emit_tokens(result, spelling="source")

    assert emission.status == "complete"
    assert emission.tokens == ("t͜s", "☃")
    assert emission.report()["source_fidelity"] == "exact"

    restored = _source_form("t͜s", "☃")
    assert emit_tokens(restored, spelling="source").to_json() == emission.to_json()


def test_canonical_emission_refuses_an_unauthorized_tie_loss() -> None:
    result = import_tokens(["t͜s"], unsupported="preserve")
    emission = emit_tokens(result, spelling="bipa")

    assert emission.status == "refused"
    assert emission.to_data() == {
        "tokens": None,
        "error": {"code": "loss-not-authorized", "stage": "emit-bipa"},
        "report": {
            "changes": [
                {
                    "convention": "clts-bipa-canonical-v1",
                    "source": "t͜s",
                    "target": "ts",
                    "token": 0,
                }
            ],
            "losses": [
                {
                    "token": 0,
                    "source": "t͜s",
                    "target": "ts",
                    "claim": "sequential-juncture",
                }
            ],
            "spelling": "bipa",
            "status": "refused",
            "unavailable": [],
        },
    }


def test_canonical_emission_reports_each_authorized_loss_deterministically() -> None:
    result = import_tokens(["t͜s", "t͡s"], unsupported="preserve")
    emission = emit_tokens(result, spelling="bipa", allow_loss=True)

    assert emission.tokens == ("ts", "ts")
    assert [loss["claim"] for loss in emission.report()["losses"]] == [
        "sequential-juncture",
        "simultaneous-juncture",
    ]
    assert (
        emission.to_json()
        == emit_tokens(result, spelling="bipa", allow_loss=True).to_json()
    )
    assert json.loads(emission.to_json()) == emission.to_data()


def test_canonical_emission_without_a_canonical_source_refuses() -> None:
    result = import_tokens(["☃"], unsupported="preserve")
    emission = emit_tokens(result, spelling="bipa", allow_loss=True)

    assert emission.status == "refused"
    assert emission.to_data()["error"] == {
        "code": "canonical-unavailable",
        "stage": "emit-bipa",
    }
    assert emission.report()["unavailable"] == [
        {"token": 0, "source": "☃", "code": "outside-artifact-domain"}
    ]


def test_source_form_generic_replacement_refuses_before_facts_can_be_dropped() -> None:
    source = _source_form("p")

    with pytest.raises(FormProjectionError, match="authoritative source/profile facts"):
        dataclasses.replace(source)

    ordinary = Form.parse("p")
    assert dataclasses.replace(ordinary) == ordinary


def test_editing_source_input_reimports_a_new_revision_without_stale_emission() -> None:
    original = import_tokens(["p"])
    edited = original.source_document()
    edited["tokens"][0]["raw"] = "b"
    revised = import_document(edited)

    assert emit_tokens(original).tokens == ("p",)
    assert emit_tokens(revised).tokens == ("b",)
    assert original.to_json() != revised.to_json()


def test_emission_options_and_input_profile_are_guarded() -> None:
    result = import_tokens(["p"])
    with pytest.raises(CLTSInputError, match="spelling"):
        emit_tokens(result, spelling="canonical")  # type: ignore[arg-type]
    with pytest.raises(CLTSInputError, match="allow_loss"):
        emit_tokens(result, allow_loss=1)  # type: ignore[arg-type]
    with pytest.raises(CLTSInputError) as caught:
        emit_tokens(Form.parse("p"))
    assert caught.value.code == "source-profile-required"
