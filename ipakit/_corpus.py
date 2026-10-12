"""Storage-neutral corpus model and the directory-backed implementation.

The module is private while the corpus surface settles. Lean entry documents
rebuild only after a write-time structural proof; every other Form retains its
complete native graph in a compressed entry.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import zlib
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .features import IPAFeatures
from .form import Form, Interval, _default

CORPUS_VERSION = 2
ENTRY_VERSION = 2
FORM_VERSION = 1
_CORPUS_TYPE = "ipakit.corpus"
_ENTRY_TYPE = "ipakit.corpus.entry"
_FORM_TYPE = "ipakit.corpus.form"
_LEAN = b"L"
_NATIVE = b"N"
# The longest an entry id may be. The pattern spells it as one leading
# character plus the rest, and _check_id quotes it in its message, so the
# bound is named once and both read from it.
MAX_ENTRY_ID_LENGTH = 128
# A split name is free text rather than an id -- it is not matched against
# the pattern above -- so it carries its own bound, which happens to be the
# same number today. They are separate rules and may move apart.
MAX_SPLIT_NAME_LENGTH = 128
_ID_RE = re.compile(rf"[A-Za-z0-9'][A-Za-z0-9.'_-]{{0,{MAX_ENTRY_ID_LENGTH - 1}}}\Z")
_KIND_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
_EXTENSIONS = {"textgrid": "TextGrid"}


class CorpusError(ValueError):
    """A corpus cannot be created, opened, or read as requested."""


class CorpusInventoryError(CorpusError):
    """A corpus operation named an inventory the format cannot rebuild."""


@dataclass(frozen=True)
class Entry:
    """One corpus item; storage details deliberately do not appear here."""

    id: str
    meta: Mapping[str, Any]
    forms: Mapping[str, Form]
    provenance: Mapping[str, FormProvenance] = field(default_factory=dict)


@dataclass(frozen=True)
class Producer:
    """Stable identity of the process that produced a stored role."""

    name: str
    version: str


@dataclass(frozen=True)
class FormProvenance:
    """Producer and declaration contract for one stored form role."""

    producer: Producer
    declaration_fingerprint: str


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
            f"invalid entry id {entry_id!r}: expected "
            f"1-{MAX_ENTRY_ID_LENGTH} ASCII letters, "
            "digits, apostrophe, '.', '_' or '-', beginning with one of those"
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


def _entry_bytes(document: Mapping[str, Any]) -> bytes:
    """Encode one versioned entry using its file-level storage discriminator."""
    payload = _json_bytes(document)
    forms = document.get("forms")
    native = isinstance(forms, dict) and any(
        isinstance(value, dict) and value.get("encoding") == "native-zlib"
        for value in forms.values()
    )
    return _NATIVE + zlib.compress(payload, level=9) if native else _LEAN + payload


def _load_object(path: Path, what: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CorpusError(f"cannot read {what} {path.name!r}: {exc}") from exc
    if not isinstance(value, dict):
        raise CorpusError(f"{what} {path.name!r} must contain a JSON object")
    return value


def _load_entry(path: Path) -> tuple[dict[str, Any], bytes]:
    """Read an entry after refusing an unknown file encoding discriminator."""
    try:
        stored = path.read_bytes()
    except OSError as exc:
        raise CorpusError(f"cannot read entry {path.name!r}: {exc}") from exc
    if not stored or stored[:1] not in {_LEAN, _NATIVE}:
        raise CorpusError(f"entry {path.name!r} has unsupported storage encoding")
    payload = stored[1:]
    if stored[:1] == _NATIVE:
        try:
            payload = zlib.decompress(payload)
        except zlib.error as exc:
            raise CorpusError(
                f"cannot read entry {path.name!r}: invalid compressed payload"
            ) from exc
    try:
        value = json.loads(payload)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise CorpusError(f"cannot read entry {path.name!r}: {exc}") from exc
    if not isinstance(value, dict):
        raise CorpusError(f"entry {path.name!r} must contain a JSON object")
    return value, stored[:1]


def _load_entry_object(path: Path) -> dict[str, Any]:
    """Read an entry document without exposing its storage discriminator."""
    return _load_entry(path)[0]


def _check_entry_storage(forms: Mapping[str, object], storage: bytes) -> None:
    native = any(
        isinstance(value, dict) and value.get("encoding") == "native-zlib"
        for value in forms.values()
    )
    expected = _NATIVE if native else _LEAN
    if storage != expected:
        raise CorpusError("entry storage encoding disagrees with its Form envelopes")


def _inventory(features: IPAFeatures | None = None) -> IPAFeatures:
    """Return the corpus inventory, refusing every non-default declaration."""
    from ._form_profile import provider_identity

    default = _default(None)
    selected = _default(features)
    if provider_identity(selected) != provider_identity(default):
        raise CorpusInventoryError(
            "corpus format v2 supports only the default inventory"
        )
    return selected


def _check_form_inventory(form: Form, inventory: IPAFeatures) -> None:
    from ._form_profile import provider_identity

    if form.__dict__.get("_tiergraph_inventory_identity") != provider_identity(
        inventory
    ):
        raise CorpusInventoryError(
            "corpus format v2 supports only Forms built with the default inventory"
        )


def _unit_view(form: Form) -> tuple[object, ...]:
    return tuple(
        (
            unit.text,
            None if unit.segment is None else unit.segment.to_dict(),
            tuple(sorted(unit.features.items())),
            tuple(sorted(unit.prosody.items())),
            unit.provenance,
            unit.timing,
            unit.spelling,
        )
        for unit in form.units
    )


def _eligibility_projection(form: Form) -> tuple[object, ...]:
    """Return every construction fact that a lean rebuild must preserve."""
    from ._containment_projection import _projection_signature

    source = form.__dict__["_tiergraph_index"].containment_input
    return (
        form.to_ipa("exact"),
        _unit_view(form),
        form.intervals,
        tuple(
            (ref, tuple(sorted(source.events[ref].features.items())))
            for ref in source.refs
        ),
        _projection_signature(source, frozenset()),
        tuple((index, path) for index, _, path in source.unit_occurrences()),
    )


def _lean_envelope(form: Form) -> dict[str, object]:
    return {
        "type": _FORM_TYPE,
        "v": FORM_VERSION,
        "encoding": "lean",
        "spelling": form.to_ipa("exact"),
        "intervals": [
            {"tier": span.tier, "start": span.start, "end": span.end}
            for span in form.intervals
        ],
    }


def _rebuild_lean(record: Mapping[str, Any], inventory: IPAFeatures) -> Form:
    if set(record) != {"type", "v", "encoding", "spelling", "intervals"}:
        raise CorpusError("lean corpus form has invalid fields")
    spelling = record["spelling"]
    raw_intervals = record["intervals"]
    if not isinstance(spelling, str) or not isinstance(raw_intervals, list):
        raise CorpusError("lean corpus form has invalid spelling or intervals")
    if any(
        not isinstance(item, dict)
        or set(item) != {"tier", "start", "end"}
        or not isinstance(item["tier"], str)
        or type(item["start"]) is not int
        or type(item["end"]) is not int
        for item in raw_intervals
    ):
        raise CorpusError("lean corpus form has an invalid interval")
    try:
        form = inventory.read(spelling, strict=True)
        intervals = tuple(
            Interval(
                item["tier"],
                item["start"],
                item["end"],
                inventory,
            )
            for item in raw_intervals
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CorpusError(f"lean corpus form cannot be restored: {exc}") from exc
    return Form.of(form.units, intervals) if intervals else form


def _form_envelope(form: Form, inventory: IPAFeatures) -> dict[str, object]:
    """Choose lean storage only after proving exact contract reconstruction."""
    _check_form_inventory(form, inventory)
    if "_source_profile_graph" not in form.__dict__ and not form.__dict__.get(
        "_source_profile_gaps"
    ):
        try:
            lean = _lean_envelope(form)
            rebuilt = _rebuild_lean(lean, inventory)
            if _eligibility_projection(form) == _eligibility_projection(rebuilt):
                return lean
        except (CorpusError, KeyError, TypeError, ValueError):
            pass
    return {
        "type": _FORM_TYPE,
        "v": FORM_VERSION,
        "encoding": "native-zlib",
        "native": form.to_dict(),
    }


def _check_envelope(record: object) -> Mapping[str, Any]:
    if not isinstance(record, dict) or record.get("type") != _FORM_TYPE:
        raise CorpusError("unsupported corpus form type")
    if record.get("v") != FORM_VERSION:
        raise CorpusError(
            f"unsupported corpus form version {record.get('v')!r}; "
            f"current version is {FORM_VERSION}"
        )
    encoding = record.get("encoding")
    if encoding == "lean":
        expected = {"type", "v", "encoding", "spelling", "intervals"}
    elif encoding == "native-zlib":
        expected = {"type", "v", "encoding", "native"}
    else:
        expected = None
    if expected is None:
        raise CorpusError(f"unsupported corpus form encoding {encoding!r}")
    if set(record) != expected:
        raise CorpusError(f"corpus form encoding {encoding!r} has invalid fields")
    return record


def _restore_form(record: object, inventory: IPAFeatures) -> Form:
    envelope = _check_envelope(record)
    if envelope["encoding"] == "lean":
        return _rebuild_lean(envelope, inventory)
    native = envelope["native"]
    if not isinstance(native, dict):
        raise CorpusError("native corpus form must contain a JSON object")
    return Form.from_dict(native, inventory)


class Corpus:
    """A corpus backed by a directory, exposed through entry operations."""

    def __init__(self, location: Path):
        self._location = location
        self._entries = location / "entries"

    @property
    def declaration_fingerprint(self) -> str | None:
        value = _load_object(self._location / "corpus.json", "corpus manifest").get(
            "declaration_fingerprint"
        )
        return value if isinstance(value, str) else None

    def put_split(self, name: str, entry_ids: Iterable[str]) -> tuple[str, ...]:
        """Atomically define a named, explicit subset of current entry IDs."""
        if not isinstance(name, str) or not name or len(name) > MAX_SPLIT_NAME_LENGTH:
            raise CorpusError(
                "split names must be non-empty strings of at most "
                f"{MAX_SPLIT_NAME_LENGTH} characters"
            )
        members = tuple(dict.fromkeys(_check_id(item) for item in entry_ids))
        missing = sorted(set(members) - set(self.ids()))
        if missing:
            raise CorpusError(f"split {name!r} names missing entries: {missing}")
        manifest = _load_object(self._location / "corpus.json", "corpus manifest")
        splits = manifest.setdefault("splits", {})
        if not isinstance(splits, dict):
            raise CorpusError("corpus splits must be a JSON object")
        splits[name] = list(members)
        self._write_manifest(manifest)
        return members

    def split(self, name: str) -> tuple[str, ...]:
        """Read a named split, refusing stale membership."""
        manifest = _load_object(self._location / "corpus.json", "corpus manifest")
        splits = manifest.get("splits", {})
        if not isinstance(splits, dict) or name not in splits:
            raise KeyError(name)
        raw = splits[name]
        if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
            raise CorpusError(f"split {name!r} must contain entry ids")
        members = tuple(_check_id(item) for item in raw)
        missing = sorted(set(members) - set(self.ids()))
        if missing:
            raise CorpusError(f"split {name!r} names missing entries: {missing}")
        return members

    def fingerprint(self) -> str:
        """Content identity of the manifest and canonical entry documents."""
        from ._identity import identity_fingerprint

        manifest_path = self._location / "corpus.json"
        entry_paths = [self._entry_path(entry_id) for entry_id in self.ids()]
        try:
            manifest = _load_object(manifest_path, "corpus manifest")
            entries = [_load_entry_object(path) for path in entry_paths]
            value: Any = {"manifest": manifest, "entries": entries}
        except CorpusError:
            # A report over damaged input still needs a stable identity.  Keep
            # the established semantic fingerprint for readable corpora and
            # fall back to exact stored bytes only when JSON cannot be read.
            value = {
                "manifest_bytes": manifest_path.read_bytes().hex(),
                "entry_bytes": [
                    [path.name, path.read_bytes().hex()] for path in entry_paths
                ],
            }
        return identity_fingerprint(value)

    def _write_manifest(self, manifest: Mapping[str, Any]) -> None:
        descriptor, temporary = tempfile.mkstemp(dir=self._location, prefix=".corpus-")
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(_json_bytes(manifest))
            os.replace(temporary, self._location / "corpus.json")
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise

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
        inventory = _inventory()
        encoded_forms: dict[str, object] = {}
        for role, form in forms.items():
            if not isinstance(role, str) or not role:
                raise CorpusError("form role names must be non-empty strings")
            if not isinstance(form, Form):
                raise CorpusError(f"form {role!r} is not a Form")
            encoded_forms[role] = _form_envelope(form, inventory)
        document = {
            "type": _ENTRY_TYPE,
            "v": ENTRY_VERSION,
            "id": entry_id,
            "meta": dict(meta),
            "forms": encoded_forms,
            "provenance": {},
        }
        data = _entry_bytes(document)
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

    def read(self, entry_id: str, features: IPAFeatures | None = None) -> Entry:
        """Restore one entry and all its named forms."""
        return self.read_roles(entry_id, features=features)

    def roles(self, entry_id: str) -> tuple[str, ...]:
        """Return stored form role names without restoring their form wires."""
        _check_id(entry_id)
        path = self._entry_path(entry_id)
        if not path.is_file():
            raise KeyError(entry_id)
        raw, storage = _load_entry(path)
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
        raw_forms = raw.get("forms")
        if not isinstance(raw_forms, dict):
            raise CorpusError(f"entry {entry_id!r} forms must be a JSON object")
        _check_entry_storage(raw_forms, storage)
        for role in raw_forms:
            if not isinstance(role, str) or not role:
                raise CorpusError(
                    f"entry {entry_id!r} has an invalid form role {role!r}"
                )
            _check_envelope(raw_forms[role])
        return tuple(raw_forms)

    def put_form(
        self,
        entry_id: str,
        role: str,
        form: Form,
        provenance: FormProvenance | None = None,
    ) -> Entry:
        """Atomically add or replace one form role on an existing entry."""
        _check_id(entry_id)
        if not isinstance(role, str) or not role:
            raise CorpusError("form role names must be non-empty strings")
        if not isinstance(form, Form):
            raise CorpusError(f"form {role!r} is not a Form")
        inventory = _inventory()
        _check_form_inventory(form, inventory)
        path = self._entry_path(entry_id)
        if not path.is_file():
            raise KeyError(entry_id)
        # Reading first applies all entry and form validation before a write can
        # preserve or extend a malformed document.
        current = self.read(entry_id)
        next_forms = {**current.forms, role: form}
        next_provenance = dict(current.provenance)
        if provenance is None:
            next_provenance.pop(role, None)
        else:
            if not isinstance(provenance, FormProvenance):
                raise CorpusError("form provenance must be a FormProvenance")
            next_provenance[role] = provenance
        document = {
            "type": _ENTRY_TYPE,
            "v": ENTRY_VERSION,
            "id": entry_id,
            "meta": dict(current.meta),
            "forms": {
                name: _form_envelope(value, inventory)
                for name, value in next_forms.items()
            },
            "provenance": {
                name: {
                    "producer": {
                        "name": value.producer.name,
                        "version": value.producer.version,
                    },
                    "declaration_fingerprint": value.declaration_fingerprint,
                }
                for name, value in next_provenance.items()
            },
        }
        data = _entry_bytes(document)
        descriptor, temporary = tempfile.mkstemp(dir=self._entries, prefix=".entry-")
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
            os.replace(temporary, path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise
        return Entry(entry_id, current.meta, next_forms, next_provenance)

    def read_roles(
        self,
        entry_id: str,
        roles: Iterable[str] | None = None,
        features: IPAFeatures | None = None,
    ) -> Entry:
        """Restore one entry, optionally restoring only selected form roles.

        The entry document is still read once, but unselected form wires are
        left untouched.  Collection operations use this to avoid constructing
        forms they cannot inspect.
        """
        inventory = _inventory(features)
        _check_id(entry_id)
        path = self._entry_path(entry_id)
        if not path.is_file():
            raise KeyError(entry_id)
        raw, storage = _load_entry(path)
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
        raw_provenance = raw.get("provenance", {})
        if not isinstance(metadata, dict):
            raise CorpusError(f"entry {entry_id!r} metadata must be a JSON object")
        if not isinstance(raw_forms, dict):
            raise CorpusError(f"entry {entry_id!r} forms must be a JSON object")
        _check_entry_storage(raw_forms, storage)
        if not isinstance(raw_provenance, dict):
            raise CorpusError(f"entry {entry_id!r} provenance must be a JSON object")
        selected = None if roles is None else frozenset(roles)
        restored: dict[str, Form] = {}
        provenance: dict[str, FormProvenance] = {}
        for role, representation in raw_forms.items():
            if not isinstance(role, str) or not role:
                raise CorpusError(
                    f"entry {entry_id!r} has an invalid form role {role!r}"
                )
            if selected is not None and role not in selected:
                continue
            _check_envelope(representation)
            try:
                restored[role] = _restore_form(representation, inventory)
            except (CorpusError, KeyError, TypeError, ValueError) as exc:
                raise CorpusError(
                    f"entry {entry_id!r} form {role!r} cannot be restored: {exc}"
                ) from exc
            record = raw_provenance.get(role)
            if record is not None:
                try:
                    producer = record["producer"]
                    provenance[role] = FormProvenance(
                        Producer(producer["name"], producer["version"]),
                        record["declaration_fingerprint"],
                    )
                except (KeyError, TypeError) as exc:
                    raise CorpusError(
                        f"entry {entry_id!r} form {role!r} has malformed provenance"
                    ) from exc
        return Entry(entry_id, metadata, restored, provenance)

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


def create(
    location: str | os.PathLike[str], *, declaration_identity: object | None = None
) -> Corpus:
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
    if declaration_identity is not None:
        from ._identity import identity_fingerprint

        manifest["declaration_fingerprint"] = identity_fingerprint(declaration_identity)
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
            raw, storage = _load_entry(path)
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
        entry_stamp_valid = True
        if raw.get("type") != _ENTRY_TYPE:
            entry_stamp_valid = False
            findings.append(
                Finding(
                    "entry_type",
                    f"entry {path.name!r} has unsupported type {raw.get('type')!r}",
                    path=path.name,
                )
            )
        if raw.get("v") != ENTRY_VERSION:
            entry_stamp_valid = False
            findings.append(
                Finding(
                    "entry_version",
                    f"entry {path.name!r} has unsupported version {raw.get('v')!r}",
                    path=path.name,
                )
            )
        if not entry_stamp_valid:
            continue
        raw_forms = raw.get("forms")
        raw_provenance = raw.get("provenance", {})
        if not isinstance(raw_provenance, dict):
            findings.append(
                Finding(
                    "provenance",
                    f"entry {path.name!r} provenance must be a JSON object",
                    entry_id=stored_id if isinstance(stored_id, str) else None,
                    path=path.name,
                )
            )
            raw_provenance = {}
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
            try:
                _check_entry_storage(raw_forms, storage)
            except CorpusError as exc:
                findings.append(
                    Finding(
                        "entry_storage",
                        str(exc),
                        entry_id=stored_id if isinstance(stored_id, str) else None,
                        path=path.name,
                    )
                )
                continue
            for role, representation in sorted(raw_forms.items(), key=repr):
                if not isinstance(role, str) or not role:
                    findings.append(
                        Finding(
                            "form_role",
                            f"entry {path.name!r} has an invalid form role {role!r}",
                            entry_id=stored_id if isinstance(stored_id, str) else None,
                            path=path.name,
                        )
                    )
                record = raw_provenance.get(role) if raw_provenance else None
                if record is not None:
                    try:
                        producer = record["producer"]
                        Producer(producer["name"], producer["version"])
                        record["declaration_fingerprint"]
                    except (KeyError, TypeError):
                        findings.append(
                            Finding(
                                "form_provenance",
                                f"entry {path.name!r} form {role!r} has malformed provenance",
                                entry_id=(
                                    stored_id if isinstance(stored_id, str) else None
                                ),
                                path=path.name,
                            )
                        )
                try:
                    restored = _restore_form(representation, _inventory())
                    # The native graph carries structured segments without
                    # reparsing them. Validation is the deliberate exception:
                    # exercise the lexical ingestion boundary as well, so an
                    # unregistered base in an otherwise valid graph produces
                    # the same lossy-read warning as every other CLI reader.
                    if "_source_profile_graph" not in restored.__dict__:
                        Form.parse(restored.to_ipa())
                except (KeyError, TypeError, ValueError) as exc:
                    message = str(exc)
                    code = (
                        "form_version"
                        if "unsupported" in message
                        and ("format_version" in message or "form version" in message)
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
    "CorpusInventoryError",
    "Entry",
    "Finding",
    "FormProvenance",
    "Producer",
    "ValidationReport",
    "create",
    "open",
    "validate",
]
