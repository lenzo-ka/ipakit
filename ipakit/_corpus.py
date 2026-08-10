"""Storage-neutral corpus model and the directory-backed implementation.

The module is private while the corpus surface settles.  Entry documents are
ordinary canonical JSON; forms use :class:`ipakit.form.Form`'s self-contained
wire so reading a corpus never reparses IPA text.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .form import Form

CORPUS_VERSION = 1
ENTRY_VERSION = 1
_CORPUS_TYPE = "ipakit.corpus"
_ENTRY_TYPE = "ipakit.corpus.entry"
_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_KIND_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
_EXTENSIONS = {"textgrid": "TextGrid"}


class CorpusError(ValueError):
    """A corpus cannot be created, opened, or read as requested."""


@dataclass(frozen=True)
class Entry:
    """One corpus item; storage details deliberately do not appear here."""

    id: str
    meta: Mapping[str, Any]
    forms: Mapping[str, Form]


@dataclass(frozen=True)
class Finding:
    """One validation result with a stable machine-readable code."""

    code: str
    message: str
    entry_id: str | None = None
    kind: str | None = None
    path: str | None = None


@dataclass(frozen=True)
class ValidationReport:
    """All findings from a validation pass."""

    findings: tuple[Finding, ...]
    entry_count: int = 0

    @property
    def valid(self) -> bool:
        return not self.findings

    @property
    def errors(self) -> tuple[Finding, ...]:
        """Compatibility spelling for consumers that surface validation."""
        return self.findings


def _check_id(entry_id: str) -> str:
    if not isinstance(entry_id, str) or _ID_RE.fullmatch(entry_id) is None:
        raise CorpusError(
            f"invalid entry id {entry_id!r}: expected 1-128 ASCII letters, "
            "digits, '.', '_' or '-', beginning with a letter or digit"
        )
    return entry_id


def _check_kind(kind: str) -> str:
    if not isinstance(kind, str) or _KIND_RE.fullmatch(kind) is None:
        raise CorpusError(
            f"invalid asset kind {kind!r}: expected an ASCII filesystem-safe name"
        )
    return kind


def _json_bytes(value: object) -> bytes:
    try:
        text = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise CorpusError(f"value is not canonical JSON data: {exc}") from exc
    return (text + "\n").encode("utf-8")


def _load_object(path: Path, what: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CorpusError(f"cannot read {what} {path.name!r}: {exc}") from exc
    if not isinstance(value, dict):
        raise CorpusError(f"{what} {path.name!r} must contain a JSON object")
    return value


class Corpus:
    """A corpus backed by a directory, exposed through entry operations."""

    def __init__(self, location: Path):
        self._location = location
        self._entries = location / "entries"

    def ids(self) -> Iterator[str]:
        """Yield IDs in lexical order without opening any entry document."""
        for path in sorted(self._entries.glob("*.json"), key=lambda item: item.name):
            yield path.stem

    def __iter__(self) -> Iterator[Entry]:
        """Lazily yield restored entries in ID order."""
        for entry_id in self.ids():
            yield self.read(entry_id)

    def __len__(self) -> int:
        return sum(1 for _ in self.ids())

    def add(
        self,
        entry_id: str,
        meta: Mapping[str, Any],
        forms: Mapping[str, Form],
    ) -> Entry:
        """Add one entry, refusing invalid or already-used IDs."""
        _check_id(entry_id)
        if not isinstance(meta, Mapping):
            raise CorpusError("entry metadata must be a mapping")
        if not isinstance(forms, Mapping):
            raise CorpusError("entry forms must be a mapping")
        encoded_forms: dict[str, object] = {}
        for role, form in forms.items():
            if not isinstance(role, str) or not role:
                raise CorpusError("form role names must be non-empty strings")
            if not isinstance(form, Form):
                raise CorpusError(f"form {role!r} is not a Form")
            encoded_forms[role] = form.to_dict(self_contained=True)
        document = {
            "type": _ENTRY_TYPE,
            "v": ENTRY_VERSION,
            "id": entry_id,
            "meta": dict(meta),
            "forms": encoded_forms,
        }
        data = _json_bytes(document)
        path = self._entry_path(entry_id)
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        except FileExistsError as exc:
            raise CorpusError(f"duplicate entry id {entry_id!r}") from exc
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return Entry(entry_id, dict(meta), dict(forms))

    def read(self, entry_id: str) -> Entry:
        """Restore one entry and all its named forms."""
        _check_id(entry_id)
        path = self._entry_path(entry_id)
        if not path.is_file():
            raise KeyError(entry_id)
        raw = _load_object(path, "entry")
        if raw.get("type") != _ENTRY_TYPE:
            raise CorpusError(
                f"entry {entry_id!r} has unsupported type {raw.get('type')!r}"
            )
        if raw.get("v") != ENTRY_VERSION:
            raise CorpusError(
                f"entry {entry_id!r} has unsupported version {raw.get('v')!r}; "
                f"current version is {ENTRY_VERSION}"
            )
        stored_id = raw.get("id")
        if stored_id != entry_id:
            raise CorpusError(
                f"entry id/filename mismatch: file {path.name!r} contains {stored_id!r}"
            )
        _check_id(stored_id)
        metadata = raw.get("meta")
        raw_forms = raw.get("forms")
        if not isinstance(metadata, dict):
            raise CorpusError(f"entry {entry_id!r} metadata must be a JSON object")
        if not isinstance(raw_forms, dict):
            raise CorpusError(f"entry {entry_id!r} forms must be a JSON object")
        restored: dict[str, Form] = {}
        for role, representation in raw_forms.items():
            if not isinstance(role, str) or not role:
                raise CorpusError(
                    f"entry {entry_id!r} has an invalid form role {role!r}"
                )
            if not isinstance(representation, dict):
                raise CorpusError(
                    f"entry {entry_id!r} form {role!r} must be a JSON object"
                )
            try:
                restored[role] = Form.from_dict(representation)
            except (KeyError, TypeError, ValueError) as exc:
                raise CorpusError(
                    f"entry {entry_id!r} form {role!r} cannot be restored: {exc}"
                ) from exc
        return Entry(entry_id, metadata, restored)

    def remove(self, entry_id: str) -> None:
        """Remove an entry and its conventional asset in every kind directory."""
        _check_id(entry_id)
        path = self._entry_path(entry_id)
        try:
            path.unlink()
        except FileNotFoundError as exc:
            raise KeyError(entry_id) from exc
        for kind in self.asset_kinds():
            self._asset_path(entry_id, kind).unlink(missing_ok=True)

    def asset(self, entry_id: str, kind: str) -> Path | None:
        """Resolve an existing conventional asset, or return ``None``."""
        _check_id(entry_id)
        path = self._asset_path(entry_id, _check_kind(kind))
        return path if path.is_file() else None

    def asset_kinds(self) -> tuple[str, ...]:
        """Return valid asset-kind directories currently present."""
        return tuple(
            path.name
            for path in sorted(self._location.iterdir(), key=lambda item: item.name)
            if path.is_dir()
            and path.name != "entries"
            and _KIND_RE.fullmatch(path.name) is not None
        )

    def _entry_path(self, entry_id: str) -> Path:
        return self._entries / f"{entry_id}.json"

    def _asset_path(self, entry_id: str, kind: str) -> Path:
        extension = _EXTENSIONS.get(kind.lower(), kind)
        return self._location / kind / f"{entry_id}.{extension}"


def create(location: str | os.PathLike[str]) -> Corpus:
    """Create a directory corpus in an absent or empty location."""
    root = Path(location)
    if root.exists():
        if not root.is_dir():
            raise CorpusError(f"corpus location {root} is not a directory")
        try:
            next(root.iterdir())
        except StopIteration:
            pass
        else:
            raise CorpusError(f"corpus location {root} is not empty")
    else:
        root.mkdir(parents=True)
    (root / "entries").mkdir()
    manifest = {"type": _CORPUS_TYPE, "v": CORPUS_VERSION}
    (root / "corpus.json").write_bytes(_json_bytes(manifest))
    return Corpus(root)


def open(location: str | os.PathLike[str]) -> Corpus:
    """Open a directory corpus after validating its structural layout."""
    root = Path(location)
    if not root.is_dir():
        raise CorpusError(f"corpus location {root} is not a directory")
    manifest_path = root / "corpus.json"
    if not manifest_path.is_file() or not (root / "entries").is_dir():
        raise CorpusError(f"invalid corpus layout at {root}")
    manifest = _load_object(manifest_path, "corpus manifest")
    if manifest.get("type") != _CORPUS_TYPE:
        raise CorpusError(f"unsupported corpus type {manifest.get('type')!r}")
    if manifest.get("v") != CORPUS_VERSION:
        raise CorpusError(
            f"unsupported corpus version {manifest.get('v')!r}; "
            f"current version is {CORPUS_VERSION}"
        )
    return Corpus(root)


def validate(location: str | os.PathLike[str]) -> ValidationReport:
    """Inspect all entries and conventional assets, collecting every finding."""
    try:
        corpus = open(location)
    except CorpusError as exc:
        return ValidationReport((Finding("layout", str(exc)),))

    findings: list[Finding] = []
    seen: dict[str, str] = {}
    valid_ids: set[str] = set()
    entry_paths = sorted(corpus._entries.glob("*.json"), key=lambda item: item.name)
    for path in entry_paths:
        filename_id = path.stem
        try:
            _check_id(filename_id)
        except CorpusError as exc:
            findings.append(Finding("invalid_id", str(exc), path=path.name))
        try:
            raw = _load_object(path, "entry")
        except CorpusError as exc:
            findings.append(Finding("entry_parse", str(exc), path=path.name))
            continue
        stored_id = raw.get("id")
        if not isinstance(stored_id, str) or _ID_RE.fullmatch(stored_id) is None:
            findings.append(
                Finding(
                    "invalid_id",
                    f"entry {path.name!r} contains invalid id {stored_id!r}",
                    path=path.name,
                )
            )
        else:
            previous = seen.get(stored_id)
            if previous is not None:
                findings.append(
                    Finding(
                        "duplicate_id",
                        f"duplicate entry id {stored_id!r} in {previous!r} and {path.name!r}",
                        entry_id=stored_id,
                        path=path.name,
                    )
                )
            else:
                seen[stored_id] = path.name
            if stored_id != filename_id:
                findings.append(
                    Finding(
                        "id_filename_mismatch",
                        f"entry id/filename mismatch: file {path.name!r} contains {stored_id!r}",
                        entry_id=stored_id,
                        path=path.name,
                    )
                )
            else:
                valid_ids.add(stored_id)
        if raw.get("type") != _ENTRY_TYPE:
            findings.append(
                Finding(
                    "entry_type",
                    f"entry {path.name!r} has unsupported type {raw.get('type')!r}",
                    path=path.name,
                )
            )
        if raw.get("v") != ENTRY_VERSION:
            findings.append(
                Finding(
                    "entry_version",
                    f"entry {path.name!r} has unsupported version {raw.get('v')!r}",
                    path=path.name,
                )
            )
        raw_forms = raw.get("forms")
        if not isinstance(raw.get("meta"), dict):
            findings.append(
                Finding(
                    "metadata",
                    f"entry {path.name!r} metadata must be a JSON object",
                    entry_id=stored_id if isinstance(stored_id, str) else None,
                    path=path.name,
                )
            )
        if not isinstance(raw_forms, dict):
            findings.append(
                Finding("forms", f"entry {path.name!r} forms must be a JSON object")
            )
        else:
            for role, representation in sorted(raw_forms.items()):
                try:
                    if not isinstance(representation, dict):
                        raise ValueError("representation must be a JSON object")
                    Form.from_dict(representation)
                except (KeyError, TypeError, ValueError) as exc:
                    code = (
                        "form_version"
                        if "unsupported Form JSON version" in str(exc)
                        else "form_restore"
                    )
                    findings.append(
                        Finding(
                            code,
                            f"entry {path.name!r} form {role!r} cannot be restored: {exc}",
                            entry_id=stored_id if isinstance(stored_id, str) else None,
                            path=path.name,
                        )
                    )

    for kind in corpus.asset_kinds():
        kind_dir = corpus._location / kind
        expected_suffix = "." + _EXTENSIONS.get(kind.lower(), kind)
        present: set[str] = set()
        for path in sorted(kind_dir.iterdir(), key=lambda item: item.name):
            if not path.is_file() or not path.name.endswith(expected_suffix):
                continue
            asset_id = path.name[: -len(expected_suffix)]
            present.add(asset_id)
            if asset_id not in valid_ids:
                findings.append(
                    Finding(
                        "orphan_asset",
                        f"orphan {kind!r} asset for entry id {asset_id!r}",
                        entry_id=asset_id,
                        kind=kind,
                        path=str(Path(kind) / path.name),
                    )
                )
        for entry_id in sorted(valid_ids - present):
            findings.append(
                Finding(
                    "missing_asset",
                    f"missing {kind!r} asset for entry id {entry_id!r}",
                    entry_id=entry_id,
                    kind=kind,
                )
            )
    return ValidationReport(tuple(findings), len(entry_paths))


__all__ = [
    "CORPUS_VERSION",
    "ENTRY_VERSION",
    "Corpus",
    "CorpusError",
    "Entry",
    "Finding",
    "ValidationReport",
    "create",
    "open",
    "validate",
]
