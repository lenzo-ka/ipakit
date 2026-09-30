"""Public import of explicit CLTS source occurrences."""

from __future__ import annotations

import copy
import functools
import json
import math
import warnings
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, Literal

import tiergraph as tg

from ._clts_input import FORMAT, InputError, decode

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
    """An immutable import result with detached public views."""

    _status: Literal["complete", "preserved", "refused"]
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
        status: Literal["complete", "preserved", "refused"],
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
    def status(self) -> Literal["complete", "preserved", "refused"]:
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
            if len(facts) != 1:
                raise CLTSInputError(
                    "house-incomplete",
                    None,
                    f"house projection incomplete at {token} (invalid-house-fact)",
                )
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


@dataclass(frozen=True, init=False, slots=True)
class CLTSEmission:
    """An immutable deterministic source or canonical-BIPA emission result."""

    _status: Literal["complete", "refused"]
    _tokens: tuple[str, ...] | None
    _report: dict[str, Any] = field(repr=False)
    _error: dict[str, Any] | None = field(repr=False)
    _KEY: ClassVar[object] = object()

    def __new__(cls, *args: Any, **kwargs: Any) -> CLTSEmission:
        if kwargs.pop("_key", None) is not cls._KEY or args or kwargs:
            raise TypeError("CLTSEmission has no public constructor")
        return object.__new__(cls)

    @classmethod
    def _create(
        cls,
        status: Literal["complete", "refused"],
        tokens: tuple[str, ...] | None,
        report: dict[str, Any],
        error: dict[str, Any] | None = None,
    ) -> CLTSEmission:
        result = cls(_key=cls._KEY)
        object.__setattr__(result, "_status", status)
        object.__setattr__(result, "_tokens", tokens)
        object.__setattr__(result, "_report", copy.deepcopy(report))
        object.__setattr__(result, "_error", copy.deepcopy(error))
        return result

    @property
    def status(self) -> Literal["complete", "refused"]:
        return self._status

    @property
    def tokens(self) -> tuple[str, ...] | None:
        return self._tokens

    def report(self) -> dict[str, Any]:
        return copy.deepcopy(self._report)

    def to_data(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "tokens": None if self.tokens is None else list(self.tokens),
            "report": self.report(),
        }
        if self._error is not None:
            data["error"] = copy.deepcopy(self._error)
        return data

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

    def convention_projection(
        self, raw: str, resolution: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        """Apply the declared house convention after explicit mapping."""
        explicit = self.projection(raw)
        if explicit["status"] == "supported" or resolution["status"] != "resolved":
            return explicit, None
        sounds = resolution.get("sounds", ())
        if len(sounds) != 1:
            return explicit, None

        from . import load_ipa_features
        from .form import Form

        source = sounds[0]["canonical"]
        inventory = load_ipa_features()
        target = inventory.add_ties(inventory.normalize_lookalikes(source))
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                form = Form.parse(target, inventory, strict=True)
                units = form.units
            if caught or len(units) != 1 or units[0].segment is None:
                return explicit, None
            target = form.to_ipa("canonical")
        except (TypeError, ValueError):
            return explicit, None
        return (
            {
                "mapping": self.spec.mapping_identity,
                "status": "supported",
                "facts": [{"house-kind": "segment", "house-symbol": target}],
            },
            {
                "convention": "house-convention-v1",
                "source": source,
                "stage": "house-projection",
                "target": target,
            },
        )


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


def _import(
    document: dict[str, Any],
    *,
    projection_policy: Literal["explicit-only", "house-convention-v1"],
    unsupported: Literal["error", "preserve"],
) -> CLTSImport:
    from . import _clts_profile as profile
    from . import clts_mapping as mapping
    from .clts import ArtifactInvalid

    if unsupported not in ("error", "preserve"):
        raise CLTSInputError(
            "invalid-option",
            None,
            'unsupported must be "error" or "preserve"',
        )
    if projection_policy not in ("explicit-only", "house-convention-v1"):
        raise CLTSInputError(
            "invalid-option",
            None,
            'projection must be "explicit-only" or "house-convention-v1"',
        )

    binding = _verified_binding()
    raws = [token["raw"] for token in document["tokens"]]
    try:
        resolutions = profile.core_bipa_resolutions(binding.snapshot, raws)
        for record in resolutions:
            if record["status"] == "resolved" and len(record["sounds"]) != 1:
                raise ArtifactInvalid(
                    "a resolved CLTS occurrence must contain exactly one sound"
                )
        projection_changes: list[dict[str, Any]] = []
        projection_records: list[dict[str, Any]] = []
        for index, (raw, resolution) in enumerate(zip(raws, resolutions, strict=True)):
            if projection_policy == "house-convention-v1":
                projected, change = binding.convention_projection(raw, resolution)
                if change is not None:
                    projection_changes.append({"token": index, **change})
            else:
                projected = binding.projection(raw)
            projection_records.append(projected)
        projections = tuple(projection_records)
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
                    "action": "preserved" if unsupported == "preserve" else "refused",
                    "code": resolution["status"],
                    "stage": "resolution",
                    "token": index,
                }
            )
        elif projection["status"] != "supported":
            diagnostics.append(
                {
                    "action": "preserved" if unsupported == "preserve" else "refused",
                    "code": projection["code"],
                    "stage": "house-projection",
                    "token": index,
                }
            )

    complete = not diagnostics
    status: Literal["complete", "preserved", "refused"] = (
        "complete"
        if complete
        else "preserved" if unsupported == "preserve" else "refused"
    )
    report: dict[str, Any] = {
        "changes": projection_changes,
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
    return CLTSImport._create(
        status, graph if status != "refused" else None, report, document
    )


def import_tokens(
    tokens: list[str] | tuple[str, ...],
    *,
    projection: Literal["explicit-only", "house-convention-v1"] = "explicit-only",
    unsupported: Literal["error", "preserve"] = "error",
) -> CLTSImport:
    """Import explicitly segmented CLTS tokens under the selected loss policy."""
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
    return _import(document, projection_policy=projection, unsupported=unsupported)


def import_document(
    document: dict[str, Any],
    *,
    projection: Literal["explicit-only", "house-convention-v1"] = "explicit-only",
    unsupported: Literal["error", "preserve"] = "error",
) -> CLTSImport:
    """Import one explicit CLTS input document under the selected loss policy."""
    if isinstance(document, str):
        raise CLTSInputError("segmentation-required", "", "supply explicit tokens")
    if not isinstance(document, dict):
        raise CLTSInputError("invalid-input", "", "document must be an object")
    try:
        decoded = decode(document)
    except InputError as error:
        raise _public_error(error) from error
    return _import(decoded, projection_policy=projection, unsupported=unsupported)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _pointer_part(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _first_difference(left: Any, right: Any, path: str = "") -> str | None:
    """Return the first canonical-order difference, with type-strict scalars."""
    if type(left) is not type(right):
        return path
    if isinstance(left, dict):
        left_keys = set(left)
        right_keys = set(right)
        for key in sorted(left_keys | right_keys):
            child = f"{path}/{_pointer_part(key)}"
            if key not in left_keys or key not in right_keys:
                return child
            difference = _first_difference(left[key], right[key], child)
            if difference is not None:
                return difference
        return None
    if isinstance(left, list):
        for index, (left_item, right_item) in enumerate(zip(left, right, strict=False)):
            difference = _first_difference(left_item, right_item, f"{path}/{index}")
            if difference is not None:
                return difference
        return path if len(left) != len(right) else None
    return None if _canonical_bytes(left) == _canonical_bytes(right) else path


def _invalid_envelope(path: str, message: str) -> CLTSInputError:
    return CLTSInputError("invalid-envelope", path, message)


_ENVIRONMENT_CODES = frozenset({"artifact-invalid", "mapping-invalid"})


def _parse_envelope(data: str | bytes | dict[str, Any]) -> dict[str, Any]:
    from .clts import _unique_object

    def invalid_constant(value: str) -> None:
        raise ValueError(f"invalid JSON constant: {value}")

    def finite_float(value: str) -> float:
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"invalid JSON number: {value} is not finite")
        return number

    try:
        if isinstance(data, dict):
            text = json.dumps(data, ensure_ascii=False, allow_nan=False)
            parsed = json.loads(
                text,
                object_pairs_hook=_unique_object,
                parse_constant=invalid_constant,
                parse_float=finite_float,
            )
        elif isinstance(data, (str, bytes)):
            parsed = json.loads(
                data,
                object_pairs_hook=_unique_object,
                parse_constant=invalid_constant,
                parse_float=finite_float,
            )
        else:
            raise TypeError("saved import must be JSON text, bytes, or an object")
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise _invalid_envelope("", str(error)) from error
    if not isinstance(parsed, dict):
        raise _invalid_envelope("", "saved import must be a JSON object")
    return parsed


def _check_envelope_shape(envelope: dict[str, Any]) -> dict[str, Any]:
    if set(envelope) != {"form", "report"}:
        raise _invalid_envelope("", "saved import must contain only form and report")
    report = envelope["report"]
    if not isinstance(report, dict):
        raise _invalid_envelope("/report", "report must be an object")
    required = {
        "changes",
        "diagnostics",
        "house_complete",
        "occurrences",
        "provenance",
        "schema",
        "source_complete",
        "status",
    }
    if set(report) not in (required, required | {"relations"}):
        raise _invalid_envelope("/report", "report has an invalid key set")

    schema = report["schema"]
    if not isinstance(schema, dict) or set(schema) != {"id", "version"}:
        raise _invalid_envelope("/report/schema", "schema must contain id and version")
    if type(schema["id"]) is not str or schema["id"] != _SCHEMA["id"]:
        raise _invalid_envelope("/report/schema/id", "unknown import-result schema id")
    if type(schema["version"]) is not int or schema["version"] != _SCHEMA["version"]:
        raise _invalid_envelope(
            "/report/schema/version", "unknown import-result schema version"
        )

    status = report["status"]
    if type(status) is not str or status not in (
        "complete",
        "preserved",
        "refused",
    ):
        raise _invalid_envelope("/report/status", "unknown import status")
    if status != "refused" and envelope["form"] is None:
        raise _invalid_envelope("/form", f"a {status} import must contain a form")
    if status == "refused" and envelope["form"] is not None:
        raise _invalid_envelope("/form", "a refused import must have a null form")
    if status == "complete" and report["house_complete"] is not True:
        raise _invalid_envelope(
            "/report/house_complete", "a complete import must be house-complete"
        )
    return report


def _check_provenance(report: dict[str, Any], binding: _Binding) -> None:
    actual = report["provenance"]
    expected = _provenance(binding)
    if not isinstance(actual, dict):
        raise CLTSInputError(
            "provenance-mismatch", "/report/provenance", "provenance differs"
        )
    keys = set(actual) | set(expected)
    for key in sorted(keys):
        if (
            key not in actual
            or key not in expected
            or _canonical_bytes(actual[key]) != _canonical_bytes(expected[key])
        ):
            raise CLTSInputError(
                "provenance-mismatch",
                f"/report/provenance/{_pointer_part(key)}",
                "provenance differs",
            )


def _source_from_report(report: dict[str, Any]) -> dict[str, Any]:
    occurrences = report["occurrences"]
    if not isinstance(occurrences, list):
        raise _invalid_envelope("/report/occurrences", "occurrences must be an array")
    tokens = []
    for index, occurrence in enumerate(occurrences):
        if not isinstance(occurrence, dict):
            raise _invalid_envelope(
                f"/report/occurrences/{index}", "occurrence must be an object"
            )
        token = {}
        if "raw" in occurrence:
            token["raw"] = copy.deepcopy(occurrence["raw"])
        if "time" in occurrence:
            token["time"] = copy.deepcopy(occurrence["time"])
        tokens.append(token)
    document: dict[str, Any] = {
        "format": FORMAT,
        "version": 1,
        "tokens": tokens,
    }
    if "relations" in report:
        document["relations"] = copy.deepcopy(report["relations"])
    return document


def _projection_from_report(
    report: dict[str, Any],
) -> Literal["explicit-only", "house-convention-v1"]:
    changes = report["changes"]
    if not isinstance(changes, list):
        raise _invalid_envelope("/report/changes", "changes must be an array")
    return (
        "house-convention-v1"
        if any(
            isinstance(change, dict)
            and change.get("convention") == "house-convention-v1"
            for change in changes
        )
        else "explicit-only"
    )


def _envelope_input_path(path: str | None) -> str | None:
    if path is None:
        return None
    if path == "":
        return "/report"
    if path == "/tokens" or path.startswith("/tokens/"):
        return "/report/occurrences" + path[len("/tokens") :]
    if path == "/relations" or path.startswith("/relations/"):
        return "/report/relations" + path[len("/relations") :]
    return "/report" + path


def load_import(data: str | bytes | dict[str, Any]) -> CLTSImport:
    """Reload a same-provenance saved import by recomputing it from its report."""
    envelope = _parse_envelope(data)
    report = _check_envelope_shape(envelope)
    _check_provenance(report, _verified_binding())
    document = _source_from_report(report)
    try:
        unsupported: Literal["error", "preserve"] = (
            "preserve" if report["status"] == "preserved" else "error"
        )
        recomputed = import_document(
            document,
            projection=_projection_from_report(report),
            unsupported=unsupported,
        )
    except CLTSInputError as error:
        if error.code in _ENVIRONMENT_CODES:
            raise
        raise CLTSInputError(
            "invalid-envelope", _envelope_input_path(error.path), str(error)
        ) from error

    expected = recomputed.to_data()
    if _canonical_bytes(envelope) != _canonical_bytes(expected):
        difference = _first_difference(envelope, expected)
        raise CLTSInputError(
            "import-mismatch", difference or "", "saved import does not match re-import"
        )
    return recomputed


def _emission_source(
    value: CLTSImport | Form,
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    if isinstance(value, CLTSImport):
        report = value.report()
        return value.source_document(), tuple(
            copy.deepcopy(occurrence["resolution"])
            for occurrence in report["occurrences"]
        )

    from .form import Form

    if not isinstance(value, Form):
        raise TypeError("emit_tokens requires a CLTSImport or source-profile Form")
    from ._clts_profile import restore

    binding = _verified_binding()
    try:
        document, resolutions, _ = restore(value.graph, binding.spec)
    except ValueError as error:
        raise CLTSInputError(
            "source-profile-required",
            None,
            "canonical CLTS emission requires a verified source-profile Form",
        ) from error
    return document, tuple(copy.deepcopy(item) for item in resolutions)


def _canonical_bipa(
    raw: str, resolution: dict[str, Any], binding: _Binding
) -> str | None:
    if resolution.get("status") == "resolved":
        canonical = resolution.get("canonical")
        if canonical is None:
            sounds = resolution.get("sounds", ())
            canonical = sounds[0].get("canonical") if len(sounds) == 1 else None
        return canonical if isinstance(canonical, str) and canonical else None

    # BIPA treats the two tie glyphs as typography.  The finite resolver stays
    # exact; emission may apply this explicit spelling convention and records
    # the erased juncture as a loss before using a shipped canonical row.
    untied = raw.replace("\u0361", "").replace("\u035c", "")
    if untied == raw:
        return None
    entry = binding.snapshot.to_data()["entries"].get(untied)
    if not isinstance(entry, dict):
        return None
    canonical = entry.get("canonical")
    return canonical if isinstance(canonical, str) and canonical else None


def _emission_losses(token: int, source: str, target: str) -> list[dict[str, Any]]:
    if source == target:
        return []
    claims = []
    if "\u035c" in source:
        claims.append("sequential-juncture")
    if "\u0361" in source:
        claims.append("simultaneous-juncture")
    if not claims:
        claims.append("source-spelling")
    return [
        {"token": token, "source": source, "target": target, "claim": claim}
        for claim in claims
    ]


def emit_tokens(
    value: CLTSImport | Form,
    *,
    spelling: Literal["source", "bipa"] = "source",
    allow_loss: bool = False,
) -> CLTSEmission:
    """Emit exact source tokens or canonical BIPA with explicit loss consent."""
    if spelling not in ("source", "bipa"):
        raise CLTSInputError(
            "invalid-option", None, 'spelling must be "source" or "bipa"'
        )
    if type(allow_loss) is not bool:
        raise CLTSInputError("invalid-option", None, "allow_loss must be a boolean")

    document, resolutions = _emission_source(value)
    source = tuple(token["raw"] for token in document["tokens"])
    if spelling == "source":
        return CLTSEmission._create(
            "complete",
            source,
            {
                "changes": [],
                "losses": [],
                "source_fidelity": "exact",
                "spelling": "source",
                "status": "complete",
            },
        )

    binding = _verified_binding()
    emitted = []
    unavailable = []
    losses: list[dict[str, Any]] = []
    changes = []
    for index, (raw, resolution) in enumerate(zip(source, resolutions, strict=True)):
        canonical = _canonical_bipa(raw, resolution, binding)
        if canonical is None:
            unavailable.append(
                {
                    "token": index,
                    "source": raw,
                    "code": str(resolution.get("status", "canonical-unavailable")),
                }
            )
            continue
        emitted.append(canonical)
        current_losses = _emission_losses(index, raw, canonical)
        losses.extend(current_losses)
        if raw != canonical:
            changes.append(
                {
                    "convention": "clts-bipa-canonical-v1",
                    "source": raw,
                    "target": canonical,
                    "token": index,
                }
            )
    if unavailable:
        return CLTSEmission._create(
            "refused",
            None,
            {
                "changes": changes,
                "losses": losses,
                "spelling": "bipa",
                "status": "refused",
                "unavailable": unavailable,
            },
            {"code": "canonical-unavailable", "stage": "emit-bipa"},
        )
    if losses and not allow_loss:
        return CLTSEmission._create(
            "refused",
            None,
            {"losses": losses},
            {"code": "loss-not-authorized", "stage": "emit-bipa"},
        )
    return CLTSEmission._create(
        "complete",
        tuple(emitted),
        {
            "changes": changes,
            "losses": losses,
            "source_fidelity": (
                "canonical-with-authorized-loss" if losses else "canonical"
            ),
            "spelling": "bipa",
            "status": "complete",
        },
    )
