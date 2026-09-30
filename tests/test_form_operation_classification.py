"""Gate every public operation that returns a :class:`ipakit.Form`."""

from __future__ import annotations

import importlib
import inspect
import io
import json
import pkgutil
import re
import tokenize
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import ipakit
import pytest
from ipakit.form import Form

ROOT = Path(__file__).resolve().parent.parent
CLASSIFICATION_PATH = ROOT / "tests/data/form_operation_classification.json"
CLASSES = frozenset({"preserves", "refuses", "constructs-new"})

# Public methods on classes other than Form are outside the deliberately narrow
# runtime scan below. Syllabification is also named here because its public
# result wraps the transformed Form instead of annotating the function with it.
# Keeping these spellings explicit makes that limit reviewable rather than an
# accidental hole in the gate.
ADDITIONAL_PUBLIC_FORM_OPERATIONS = (
    "ipakit.bridges.mfa.MFABridge.read_tokens",
    "ipakit.bridges.vocabulary.VocabularyBridge.read",
    "ipakit.bridges.zipa.ZIPABridge.read_original",
    "ipakit.bridges.zipa.ZIPABridge.read_tokens",
    "ipakit.features.IPAFeatures.read",
    "ipakit.features.IPAFeatures.read_json",
    "ipakit.form.FormBuilder.build",
    "ipakit.clts.CLTSImport.house_form",
    "ipakit.rules.Derivation.to_form",
    "ipakit.rules.Rule.rewrite",
    "ipakit.syllable.Syllabifier.__call__",
    "ipakit.syllable.syllabify",
)


def _returns_form(callable_: Callable[..., Any]) -> bool:
    """Whether a return annotation or explicit return doc names ``Form``."""
    annotation = inspect.get_annotations(callable_, eval_str=False).get("return")
    if annotation is not None and re.search(
        r"(?<![A-Za-z0-9_])Form(?![A-Za-z0-9_])", str(annotation)
    ):
        return True
    doc = inspect.getdoc(callable_) or ""
    return bool(re.search(r"\breturn(?:s|ed|ing)?\b[^.\n]{0,100}\bForm\b", doc))


def _public_modules() -> tuple[Any, ...]:
    names = {ipakit.__name__}
    for found in pkgutil.walk_packages(ipakit.__path__, f"{ipakit.__name__}."):
        parts = found.name.split(".")[1:]
        if not any(part.startswith("_") for part in parts):
            names.add(found.name)
    return tuple(importlib.import_module(name) for name in sorted(names))


def public_form_operations() -> set[str]:
    """Discover the review boundary from the live public API."""
    found: set[str] = set()
    for name, raw in inspect.getmembers_static(Form):
        if name.startswith("_"):
            continue
        member = raw
        if isinstance(raw, (classmethod, staticmethod)):
            member = raw.__func__
        elif isinstance(raw, property):
            member = raw.fget
        if callable(member) and _returns_form(member):
            found.add(f"{Form.__module__}.{Form.__qualname__}.{name}")

    for module in _public_modules():
        for name, member in inspect.getmembers(module, inspect.isfunction):
            if (
                not name.startswith("_")
                and member.__module__ == module.__name__
                and _returns_form(member)
            ):
                found.add(f"{module.__name__}.{name}")
    return found


def _resolve(name: str) -> Any:
    parts = name.split(".")
    for stop in range(len(parts), 0, -1):
        try:
            value = importlib.import_module(".".join(parts[:stop]))
        except ModuleNotFoundError:
            continue
        for part in parts[stop:]:
            value = inspect.getattr_static(value, part)
            if isinstance(value, (classmethod, staticmethod)):
                value = value.__func__
            elif isinstance(value, property):
                value = value.fget
        return value
    raise LookupError(name)


def _classification() -> dict[str, dict[str, Any]]:
    document = json.loads(CLASSIFICATION_PATH.read_text(encoding="utf-8"))
    assert document["schema_version"] == 1
    return document["operations"]


def _evidence_lands_on_code(path: Path, line: int) -> bool:
    """Reject blank, comment, and docstring-only evidence locations."""
    source = path.read_text(encoding="utf-8")
    seen_code = False
    for item in tokenize.generate_tokens(io.StringIO(source).readline):
        if not (item.start[0] <= line <= item.end[0]):
            continue
        if item.type in {tokenize.COMMENT, tokenize.STRING}:
            continue
        if item.type not in {
            tokenize.ENCODING,
            tokenize.ENDMARKER,
            tokenize.INDENT,
            tokenize.DEDENT,
            tokenize.NEWLINE,
            tokenize.NL,
        }:
            seen_code = True
    return seen_code


def _evidence_lands_in_operation(name: str, path: Path, line: int) -> bool:
    """Require the evidence to be executable code inside the named operation."""
    operation = _resolve(name)
    source_path = inspect.getsourcefile(operation)
    if source_path is None or Path(source_path).resolve() != path.resolve():
        return False
    source, start = inspect.getsourcelines(operation)
    return start <= line < start + len(source) and _evidence_lands_on_code(path, line)


def assert_classification_complete(
    classified: Mapping[str, Mapping[str, Any]],
) -> None:
    discoverable = public_form_operations()
    expected = discoverable | set(ADDITIONAL_PUBLIC_FORM_OPERATIONS)
    named = set(classified)
    missing = sorted(expected - named)
    stale = sorted(named - expected)
    unresolved = []
    for name in sorted(named & set(ADDITIONAL_PUBLIC_FORM_OPERATIONS)):
        try:
            _resolve(name)
        except (AttributeError, ImportError, LookupError):
            unresolved.append(name)
    messages = []
    if missing:
        messages.append("unclassified Form-returning operations: " + ", ".join(missing))
    if stale:
        messages.append("classified operations no longer public: " + ", ".join(stale))
    if unresolved:
        messages.append(
            "classified operations no longer exist: " + ", ".join(unresolved)
        )
    if messages:
        raise AssertionError("; ".join(messages))


def test_every_public_form_operation_is_classified() -> None:
    classified = _classification()
    assert_classification_complete(classified)
    for name, row in classified.items():
        assert row["classification"] in CLASSES, name
        evidence = row["evidence"]
        path = ROOT / evidence["file"]
        assert path.is_file(), name
        assert type(evidence["line"]) is int and evidence["line"] > 0, name
        assert evidence["note"].strip() and "\n" not in evidence["note"], name
        assert evidence["line"] <= len(
            path.read_text(encoding="utf-8").splitlines()
        ), name
        assert _evidence_lands_in_operation(name, path, evidence["line"]), name


def test_fault_injection_new_form_method_is_named(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unclassified_test_operation(self: Form) -> Form:
        return self

    monkeypatch.setattr(
        Form, "unclassified_test_operation", unclassified_test_operation, raising=False
    )
    with pytest.raises(AssertionError) as caught:
        assert_classification_complete(_classification())
    assert str(caught.value) == (
        "unclassified Form-returning operations: "
        "ipakit.form.Form.unclassified_test_operation"
    )


def test_fault_injection_removed_classification_is_named() -> None:
    classified = _classification()
    removed = "ipakit.form.Form.without_boundaries"
    del classified[removed]
    with pytest.raises(AssertionError) as caught:
        assert_classification_complete(classified)
    assert str(caught.value) == f"unclassified Form-returning operations: {removed}"


def test_fault_injection_zipa_reader_omission_is_named() -> None:
    classified = _classification()
    removed = "ipakit.bridges.zipa.ZIPABridge.read_original"
    del classified[removed]
    with pytest.raises(AssertionError) as caught:
        assert_classification_complete(classified)
    assert str(caught.value) == f"unclassified Form-returning operations: {removed}"


def test_evidence_location_rejects_a_docstring_line() -> None:
    assert not _evidence_lands_on_code(ROOT / "ipakit/form.py", 2552)
    assert _evidence_lands_on_code(ROOT / "ipakit/form.py", 2559)


def test_evidence_location_rejects_code_from_another_operation() -> None:
    assert _evidence_lands_on_code(ROOT / "ipakit/features.py", 3689)
    assert not _evidence_lands_in_operation(
        "ipakit.features.IPAFeatures.read", ROOT / "ipakit/features.py", 3689
    )
