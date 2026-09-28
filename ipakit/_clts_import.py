"""Public strict import of explicit CLTS source occurrences."""

from __future__ import annotations

import copy
import functools
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, Literal

import tiergraph as tg

from ._clts_input import InputError, decode

if TYPE_CHECKING:
    from .form import Form


_SCHEMA = {"id": "ipakit-clts-import-result", "version": 1}


class CLTSInputError(ValueError):
    """A public CLTS import refusal, optionally located in caller input."""

    __slots__ = ("_code", "_path", "_message", "_locked")
    _code: str
    _path: str | None
    _message: str
    _locked: bool

    def __init__(self, code: str, path: str | None, message: str):
        object.__setattr__(self, "_locked", False)
        object.__setattr__(self, "_code", code)
        object.__setattr__(self, "_path", path)
        object.__setattr__(self, "_message", message)
        super().__init__(message)
        object.__setattr__(self, "_locked", True)

    def __setattr__(self, name: str, value: Any) -> None:
        if getattr(self, "_locked", False):
            raise AttributeError("CLTSInputError is immutable")
        object.__setattr__(self, name, value)

    @property
    def code(self) -> str:
        return self._code

    @property
    def path(self) -> str | None:
        return self._path

    @property
    def message(self) -> str:
        return self._message

    def to_data(self) -> dict[str, Any]:
        error = {"code": self.code, "message": self.message}
        if self.path is not None:
            error["path"] = self.path
        return {"error": error, "form": None}


@dataclass(frozen=True, init=False, slots=True)
class CLTSImport:
    """An immutable strict import result with detached public views."""

    _status: Literal["complete", "refused"]
    _graph: tg.Graph | None
    _report: dict[str, Any] = field(repr=False)
    _source: dict[str, Any] = field(repr=False)
    _KEY: ClassVar[object] = object()

    def __new__(cls, *args: Any, **kwargs: Any) -> CLTSImport:
        if kwargs.pop("_key", None) is not cls._KEY or args or kwargs:
            raise TypeError("CLTSImport has no public constructor")
        return object.__new__(cls)

    @classmethod
    def _create(
        cls,
        status: Literal["complete", "refused"],
        graph: tg.Graph | None,
        report: dict[str, Any],
        source: dict[str, Any],
    ) -> CLTSImport:
        result = cls(_key=cls._KEY)
        object.__setattr__(result, "_status", status)
        object.__setattr__(result, "_graph", graph)
        object.__setattr__(result, "_report", copy.deepcopy(report))
        object.__setattr__(result, "_source", copy.deepcopy(source))
        return result

    @property
    def status(self) -> Literal["complete", "refused"]:
        return self._status

    @property
    def source_complete(self) -> bool:
        return bool(self._report["source_complete"])

    @property
    def house_complete(self) -> bool:
        return bool(self._report["house_complete"])

    @property
    def graph(self) -> tg.Graph | None:
        return self._graph

    def report(self) -> dict[str, Any]:
        return copy.deepcopy(self._report)

    def source_document(self) -> dict[str, Any]:
        return copy.deepcopy(self._source)

    def source_tokens(self) -> tuple[str, ...]:
        return tuple(token["raw"] for token in self._source["tokens"])

    def house_form(self) -> Form:
        """Return a new house-IPA Form, or refuse any incomplete projection."""
        if self.status != "complete":
            gaps = ", ".join(
                f"{item['token']} ({item['code']})"
                for item in self._report["diagnostics"]
            )
            raise CLTSInputError(
                "house-incomplete", None, f"house projection incomplete at {gaps}"
            )

        from .form import FormBuilder

        builder = FormBuilder()
        for occurrence in self._report["occurrences"]:
            token = occurrence["token"]
            facts = occurrence["projection"].get("facts", [])
            for fact in facts:
                if (
                    set(fact) != {"house-kind", "house-symbol"}
                    or fact["house-kind"] != "segment"
                    or not isinstance(fact["house-symbol"], str)
                ):
                    raise CLTSInputError(
                        "house-incomplete",
                        None,
                        f"house projection incomplete at {token} (invalid-house-fact)",
                    )
                try:
                    appended = builder.append_ipa(fact["house-symbol"], strict=True)
                except ValueError as error:
                    raise CLTSInputError(
                        "house-incomplete",
                        None,
                        f"house projection incomplete at {token} (invalid-house-fact)",
                    ) from error
                if len(appended) != 1:
                    raise CLTSInputError(
                        "house-incomplete",
                        None,
                        f"house projection incomplete at {token} (invalid-house-fact)",
                    )
        return builder.build()

    def to_data(self) -> dict[str, Any]:
        return {
            "form": None if self.graph is None else tg.to_data(self.graph),
            "report": self.report(),
        }

    def to_json(self, *, pretty: bool = False) -> str:
        options: dict[str, Any] = {
            "ensure_ascii": False,
            "allow_nan": False,
            "sort_keys": True,
        }
        if pretty:
            options["indent"] = 2
        else:
            options["separators"] = (",", ":")
        return json.dumps(self.to_data(), **options)


@dataclass
class _Binding:
    snapshot: Any
    authority: Any
    spec: Any
    projections: dict[str, dict[str, Any]] = field(default_factory=dict)

    def projection(self, raw: str) -> dict[str, Any]:
        if raw not in self.projections:
            self.projections[raw] = self.authority._projection_record(
                raw, self.snapshot, self.spec
            )
        return copy.deepcopy(self.projections[raw])


@functools.lru_cache(maxsize=1)
def _verified_binding() -> _Binding:
    # These imports stay inside the binding to preserve either module's fresh
    # import path and to keep development-only pyclts out of runtime imports.
    from . import _clts_profile as profile
    from . import clts_mapping as mapping
    from . import load_ipa_features
    from .clts import ArtifactInvalid, read_snapshot

    try:
        snapshot = read_snapshot()
        authority = mapping.read_authority()
        spec = profile.core_bipa_spec(snapshot, mapping_identity=authority.identity)
        authority.require_import_profile(spec)
        authority_data = authority.to_data()
        authority.validate_context(
            authority_data["census"], snapshot, load_ipa_features()
        )
        return _Binding(snapshot, authority, spec)
    except ArtifactInvalid as error:
        raise CLTSInputError("artifact-invalid", None, str(error)) from error
    except mapping.MappingInvalid as error:
        raise CLTSInputError("mapping-invalid", None, str(error)) from error


def _cache_clear() -> None:
    """Clear the verified binding and its per-raw projection memo for tests."""
    _verified_binding.cache_clear()


def _public_error(error: InputError) -> CLTSInputError:
    return CLTSInputError(error.code, error.path, str(error))


def _provenance(binding: _Binding) -> dict[str, str]:
    from ._clts_profile import metadata

    return {
        "domain": str(binding.snapshot.to_data()["domain"]),
        "manifest": str(binding.spec.manifest_fingerprint),
        "mapping": str(binding.spec.mapping_identity),
        "profile": str(metadata(binding.spec)["fingerprint"]),
        "snapshot": str(binding.spec.provider_fingerprint),
    }


def _reduce_projection(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(value) for key, value in record.items() if key != "mapping"
    }


def _reduce_resolution(record: dict[str, Any]) -> dict[str, Any]:
    reduced = {"status": record["status"]}
    if record["status"] == "resolved":
        reduced["canonical"] = record["sounds"][0]["canonical"]
    return reduced


def _import(document: dict[str, Any]) -> CLTSImport:
    from . import _clts_profile as profile
    from . import clts_mapping as mapping
    from .clts import ArtifactInvalid

    binding = _verified_binding()
    raws = [token["raw"] for token in document["tokens"]]
    try:
        resolutions = profile.core_bipa_resolutions(binding.snapshot, raws)
        for record in resolutions:
            if record["status"] == "resolved" and len(record["sounds"]) != 1:
                raise ArtifactInvalid(
                    "a resolved CLTS occurrence must contain exactly one sound"
                )
        projections = tuple(binding.projection(raw) for raw in raws)
        graph = profile.construct(document, resolutions, projections, binding.spec)
    except InputError as error:
        raise _public_error(error) from error
    except ArtifactInvalid as error:
        raise CLTSInputError("artifact-invalid", None, str(error)) from error
    except mapping.MappingInvalid as error:
        raise CLTSInputError("mapping-invalid", None, str(error)) from error

    occurrences = []
    diagnostics = []
    for index, (token, resolution, projection) in enumerate(
        zip(document["tokens"], resolutions, projections, strict=True)
    ):
        occurrence: dict[str, Any] = {
            "projection": _reduce_projection(projection),
            "raw": token["raw"],
            "resolution": _reduce_resolution(resolution),
            "token": index,
        }
        if "time" in token:
            occurrence["time"] = copy.deepcopy(token["time"])
        occurrences.append(occurrence)
        if resolution["status"] != "resolved":
            diagnostics.append(
                {
                    "action": "refused",
                    "code": resolution["status"],
                    "stage": "resolution",
                    "token": index,
                }
            )
        elif projection["status"] != "supported":
            diagnostics.append(
                {
                    "action": "refused",
                    "code": projection["code"],
                    "stage": "house-projection",
                    "token": index,
                }
            )

    complete = not diagnostics
    status: Literal["complete", "refused"] = "complete" if complete else "refused"
    report: dict[str, Any] = {
        "changes": [],
        "diagnostics": diagnostics,
        "house_complete": complete,
        "occurrences": occurrences,
        "provenance": _provenance(binding),
        "schema": dict(_SCHEMA),
        "source_complete": True,
        "status": status,
    }
    if "relations" in document:
        report["relations"] = copy.deepcopy(document["relations"])
    return CLTSImport._create(status, graph if complete else None, report, document)


def import_tokens(tokens: list[str] | tuple[str, ...]) -> CLTSImport:
    """Strictly import explicitly segmented CLTS tokens."""
    from collections import UserString

    if isinstance(tokens, (str, UserString)):
        raise CLTSInputError("segmentation-required", "", "supply explicit tokens")
    if not isinstance(tokens, (list, tuple)):
        raise CLTSInputError(
            "invalid-input", "", "tokens must be supplied as a list or tuple"
        )
    try:
        document = decode(list(tokens))
    except InputError as error:
        raise _public_error(error) from error
    return _import(document)


def import_document(document: dict[str, Any]) -> CLTSImport:
    """Strictly import one explicit CLTS input document."""
    if isinstance(document, str):
        raise CLTSInputError("segmentation-required", "", "supply explicit tokens")
    if not isinstance(document, dict):
        raise CLTSInputError("invalid-input", "", "document must be an object")
    try:
        decoded = decode(document)
    except InputError as error:
        raise _public_error(error) from error
    return _import(decoded)
