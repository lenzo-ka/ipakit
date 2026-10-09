"""One strict receipt envelope for generated external-source artifacts.

The schema is data so producers can inspect the common contract without
duplicating it.  Source-specific validators may require optional properties,
but they may not add undeclared top-level fields.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from ._identity import identity_fingerprint

RECEIPT_SCHEMA_ID = "ipakit-source-receipt"
RECEIPT_SCHEMA_VERSION = 1
RECEIPT_SCHEMA: dict[str, Any] = {
    "id": RECEIPT_SCHEMA_ID,
    "version": RECEIPT_SCHEMA_VERSION,
    "required": (
        "schema",
        "kind",
        "domain",
        "source-policy",
        "extractor",
        "artifacts",
        "license",
        "fingerprint",
    ),
    "optional": (
        "build",
        "house-declarations",
        "adapter",
        "projection-policy",
        "profile-family",
    ),
    "additional-properties": False,
}

_SOURCE_FIELDS = {
    "upstream",
    "upstream-url",
    "artifact",
    "version",
    "license",
    "kind",
}
_HEX_SHA256 = re.compile(r"[0-9a-f]{64}").fullmatch
_HEX_COMMIT = re.compile(r"[0-9a-f]{40}").fullmatch
_IDENTITY_SHA256 = re.compile(r"sha256:[0-9a-f]{64}").fullmatch
_RFC3339_UTC = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z"
).fullmatch


def unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Build a JSON object without silently replacing duplicate keys."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _exact_object(value: Any, keys: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise ValueError(f"{label} must contain exactly {sorted(keys)}")
    return value


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a nonempty string")
    return value


def _hash_map(value: Any, label: str, *, empty: bool = False) -> None:
    if not isinstance(value, Mapping) or (not value and not empty):
        raise ValueError(f"{label} must be a nonempty path-to-sha256 object")
    for path, digest in value.items():
        if (
            not isinstance(path, str)
            or not path
            or not isinstance(digest, str)
            or _HEX_SHA256(digest) is None
        ):
            raise ValueError(f"{label} contains an invalid path or sha256")


def _rfc3339_utc(value: Any, label: str) -> str:
    from datetime import datetime

    text = _nonempty(value, label)
    if _RFC3339_UTC(text) is None:
        raise ValueError(f"{label} must be an RFC 3339 UTC string ending in Z")
    try:
        datetime.fromisoformat(f"{text[:-1]}+00:00")
    except ValueError as error:
        raise ValueError(
            f"{label} must be an RFC 3339 UTC string ending in Z"
        ) from error
    return text


def validate_receipt(data: Any) -> None:
    """Validate the shared source-receipt schema and its own fingerprint."""
    if not isinstance(data, Mapping):
        raise ValueError("receipt must be a JSON object")
    required = set(RECEIPT_SCHEMA["required"])
    allowed = required | set(RECEIPT_SCHEMA["optional"])
    if not required <= set(data):
        raise ValueError(
            f"receipt lacks required fields: {sorted(required - set(data))}"
        )
    if RECEIPT_SCHEMA["additional-properties"] is False and set(data) - allowed:
        raise ValueError(f"unexpected receipt fields: {sorted(set(data) - allowed)}")

    schema = _exact_object(data["schema"], {"id", "version"}, "receipt schema")
    if schema != {"id": RECEIPT_SCHEMA_ID, "version": RECEIPT_SCHEMA_VERSION}:
        raise ValueError("unsupported receipt schema/version")
    _nonempty(data["kind"], "receipt kind")
    _nonempty(data["domain"], "receipt domain")

    policy = data["source-policy"]
    if (
        not isinstance(policy, Mapping)
        or not {
            "version",
            "source",
            "inputs",
        }
        <= set(policy)
        or set(policy)
        - {
            "version",
            "source",
            "inputs",
            "resolver",
            "credit",
            "revision",
        }
    ):
        raise ValueError("invalid source-policy fields")
    if type(policy["version"]) is not int or policy["version"] < 1:
        raise ValueError("source-policy version must be a positive integer")
    source = _exact_object(policy["source"], _SOURCE_FIELDS, "source identity")
    for key, value in source.items():
        _nonempty(value, f"source identity {key}")
    _hash_map(policy["inputs"], "source-policy inputs")
    if "credit" in policy and not isinstance(policy["credit"], Mapping):
        raise ValueError("source-policy credit must be an object")
    if "revision" in policy:
        revision = policy["revision"]
        if not isinstance(revision, Mapping):
            raise ValueError("source-policy revision must be an object")
        keys = set(revision)
        identities = keys & {"commit", "sha256"}
        if len(identities) != 1 or keys - {"commit", "sha256", "tag"}:
            raise ValueError(
                "source-policy revision must contain exactly one of commit or sha256"
                " and optional tag"
            )
        if "commit" in revision and (
            not isinstance(revision["commit"], str)
            or _HEX_COMMIT(revision["commit"]) is None
        ):
            raise ValueError(
                "source-policy revision commit must be 40 hexadecimal digits"
            )
        if "sha256" in revision and (
            not isinstance(revision["sha256"], str)
            or _HEX_SHA256(revision["sha256"]) is None
        ):
            raise ValueError(
                "source-policy revision sha256 must be 64 hexadecimal digits"
            )
        if "tag" in revision:
            _nonempty(revision["tag"], "source-policy revision tag")
    if "resolver" in policy:
        resolver = _exact_object(
            policy["resolver"], {"name", "version", "inputs"}, "resolver"
        )
        _nonempty(resolver["name"], "resolver name")
        _nonempty(resolver["version"], "resolver version")
        _hash_map(resolver["inputs"], "resolver inputs")

    extractor = _exact_object(data["extractor"], {"id", "version"}, "extractor")
    _nonempty(extractor["id"], "extractor id")
    _nonempty(extractor["version"], "extractor version")

    artifacts = data["artifacts"]
    if not isinstance(artifacts, Mapping) or not artifacts:
        raise ValueError("artifacts must be a nonempty object")
    for path, receipt in artifacts.items():
        _nonempty(path, "artifact path")
        if (
            not isinstance(receipt, Mapping)
            or not {"sha256"} <= set(receipt)
            or set(receipt) - {"sha256", "identity", "schema"}
        ):
            raise ValueError(f"invalid derived-artifact receipt: {path}")
        if (
            not isinstance(receipt["sha256"], str)
            or _HEX_SHA256(receipt["sha256"]) is None
        ):
            raise ValueError(f"invalid derived-artifact sha256: {path}")
        if "identity" in receipt and (
            not isinstance(receipt["identity"], str)
            or _IDENTITY_SHA256(receipt["identity"]) is None
        ):
            raise ValueError(f"invalid derived-artifact identity: {path}")
        if "schema" in receipt:
            artifact_schema = _exact_object(
                receipt["schema"], {"id", "version"}, "artifact schema"
            )
            _nonempty(artifact_schema["id"], "artifact schema id")
            if type(artifact_schema["version"]) not in (str, int):
                raise ValueError("artifact schema version must be a string or integer")

    license_receipt = _exact_object(data["license"], {"id", "notices"}, "license")
    _nonempty(license_receipt["id"], "license id")
    _hash_map(license_receipt["notices"], "license notices")

    if "build" in data:
        build = _exact_object(
            data["build"],
            {"tool", "tool-version", "format", "built-at"},
            "build",
        )
        _nonempty(build["tool"], "build tool")
        _nonempty(build["tool-version"], "build tool version")
        if type(build["format"]) is not int or build["format"] < 1:
            raise ValueError("build format must be a positive integer")
        _rfc3339_utc(build["built-at"], "build time")

    if "house-declarations" in data:
        house = _exact_object(
            data["house-declarations"], {"fingerprint"}, "house declarations"
        )
        if (
            not isinstance(house["fingerprint"], str)
            or _IDENTITY_SHA256(house["fingerprint"]) is None
        ):
            raise ValueError("invalid house declaration fingerprint")
    if "adapter" in data:
        adapter = _exact_object(data["adapter"], {"schema", "outcomes"}, "adapter")
        adapter_schema = _exact_object(
            adapter["schema"], {"id", "version"}, "adapter schema"
        )
        _nonempty(adapter_schema["id"], "adapter schema id")
        if type(adapter_schema["version"]) is not int or adapter_schema["version"] < 1:
            raise ValueError("adapter schema version must be a positive integer")
        if not isinstance(adapter["outcomes"], Mapping) or not adapter["outcomes"]:
            raise ValueError("adapter outcomes must be a nonempty object")
    if "projection-policy" in data:
        projection = _exact_object(
            data["projection-policy"],
            {"name", "version", "unsupported"},
            "projection policy",
        )
        _nonempty(projection["name"], "projection policy name")
        _nonempty(projection["unsupported"], "projection unsupported action")
        if type(projection["version"]) is not int or projection["version"] < 1:
            raise ValueError("projection policy version must be a positive integer")
    if "profile-family" in data:
        family = _exact_object(
            data["profile-family"], {"id", "version"}, "profile family"
        )
        _nonempty(family["id"], "profile family id")
        if type(family["version"]) is not int or family["version"] < 1:
            raise ValueError("profile family version must be a positive integer")

    if (
        not isinstance(data["fingerprint"], str)
        or _IDENTITY_SHA256(data["fingerprint"]) is None
    ):
        raise ValueError("invalid receipt fingerprint")
    material = {key: value for key, value in data.items() if key != "fingerprint"}
    if identity_fingerprint(material) != data["fingerprint"]:
        raise ValueError("receipt content fingerprint mismatch")


def loads_receipt(content: str | bytes) -> dict[str, Any]:
    """Decode a strict JSON receipt and validate the common schema."""
    data = json.loads(content, object_pairs_hook=unique_json_object)
    validate_receipt(data)
    return dict(data)
