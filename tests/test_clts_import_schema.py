"""Schema and canonical fixtures for public CLTS import envelopes."""

from __future__ import annotations

import copy
import json
import tomllib
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError
from scripts.clts_import_fixtures import fixtures

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "clts_import"
SCHEMA_PATH = ROOT / "ipakit" / "data" / "clts" / "import-result.schema.json"


def _documents() -> dict[str, dict]:
    return {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(FIXTURES.glob("*.json"))
    }


def _validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def test_r1_1_regenerated_fixtures_are_byte_equal() -> None:
    generated = fixtures()
    assert set(generated) == {path.name for path in FIXTURES.glob("*.json")}
    for name, data in generated.items():
        assert data == (FIXTURES / name).read_bytes()


@pytest.mark.parametrize(
    ("name", "status", "occurrences"),
    [
        ("complete", "complete", 2),
        ("empty", "complete", 0),
        ("refused", "refused", 5),
        ("preserved", "preserved", 3),
        ("error", None, None),
    ],
)
def test_r1_2_fixtures_validate_with_hand_authored_facts(
    name: str, status: str | None, occurrences: int | None
) -> None:
    document = _documents()[name]
    assert json.loads(fixtures()[f"{name}.json"]) == document
    _validator().validate(document)
    if name == "error":
        assert document == {
            "error": {
                "code": "invalid-timing",
                "message": "supply finite nonnegative start and duration together",
                "path": "/tokens/0/time",
            },
            "form": None,
        }
        assert "schema" not in document
        return
    assert document["report"]["status"] == status
    assert len(document["report"]["occurrences"]) == occurrences
    assert (document["form"] is None) is (status == "refused")


def test_r1_3_schema_rejects_status_and_schema_contradictions() -> None:
    documents = _documents()
    complete = documents["complete"]
    refused = documents["refused"]
    preserved = documents["preserved"]
    error = documents["error"]

    mutations = []
    changed = copy.deepcopy(complete)
    changed["form"] = None
    mutations.append(changed)
    changed = copy.deepcopy(refused)
    changed["form"] = complete["form"]
    mutations.append(changed)
    changed = copy.deepcopy(preserved)
    changed["report"]["house_complete"] = True
    mutations.append(changed)
    changed = copy.deepcopy(complete)
    changed["report"]["diagnostics"] = [refused["report"]["diagnostics"][0]]
    mutations.append(changed)
    changed = copy.deepcopy(complete)
    changed["report"]["source_complete"] = False
    mutations.append(changed)
    changed = copy.deepcopy(complete)
    del changed["report"]["schema"]
    mutations.append(changed)
    changed = copy.deepcopy(complete)
    changed["report"]["schema"]["version"] = 2
    mutations.append(changed)
    changed = copy.deepcopy(error)
    changed["report"] = complete["report"]
    mutations.append(changed)
    changed = copy.deepcopy(error)
    changed["schema"] = {"id": "ipakit-clts-import-result", "version": 1}
    mutations.append(changed)

    validator = _validator()
    for changed in mutations:
        with pytest.raises(ValidationError):
            validator.validate(changed)


def test_jsonschema_is_supplied_only_by_the_test_extra() -> None:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)["project"]
    assert not any(item.startswith("jsonschema") for item in project["dependencies"])
    assert (
        sum(
            item.startswith("jsonschema")
            for item in project["optional-dependencies"]["test"]
        )
        == 1
    )
