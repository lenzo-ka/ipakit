"""Strict internal source-occurrence ingress; no tokenizer or resolver."""

from __future__ import annotations

import math
import re
from typing import Any

FORMAT = "ipakit-clts-input"
HOST = "clts:source-tone-host"


class InputError(ValueError):
    """An operation refusal with a document-local location."""

    def __init__(self, code: str, path: str, message: str):
        self.code, self.path = code, path
        super().__init__(message)


def _object(
    value: Any, required: set[str], optional: set[str], path: str
) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or not required <= value.keys()
        or value.keys() - required - optional
    ):
        raise InputError("invalid-input", path, "missing or unknown object fields")
    return value


def endpoint(value: Any, count: int, path: str) -> int:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"/tokens/(0|[1-9][0-9]*)", value) is None
    ):
        raise InputError("invalid-relation", path, "expected a /tokens/N pointer")
    digits = value.removeprefix("/tokens/")
    if len(digits) > len(str(count)):
        raise InputError("invalid-relation", path, "dangling token pointer")
    index = int(digits)
    if index >= count:
        raise InputError("invalid-relation", path, "dangling token pointer")
    return index


def _valid_time(value: Any) -> bool:
    if type(value) not in (int, float) or value < 0:
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def decode(value: Any) -> dict[str, Any]:
    """Copy and validate the one document contract, including array shorthand."""
    if isinstance(value, str):
        raise InputError("segmentation-required", "", "supply explicit tokens")
    if isinstance(value, list):
        if any(not isinstance(raw, str) for raw in value):
            raise InputError("invalid-input", "", "shorthand is an array of strings")
        value = {
            "format": FORMAT,
            "version": 1,
            "tokens": [{"raw": raw} for raw in value],
        }
    source = _object(value, {"format", "version", "tokens"}, {"relations"}, "")
    if (
        source["format"] != FORMAT
        or type(source["version"]) is not int
        or source["version"] != 1
    ):
        raise InputError("invalid-input", "", "unsupported input format/version")
    if not isinstance(source["tokens"], list):
        raise InputError("invalid-input", "/tokens", "tokens must be an ordered array")
    tokens = []
    for index, entry in enumerate(source["tokens"]):
        path = f"/tokens/{index}"
        token = _object(entry, {"raw"}, {"time"}, path)
        raw = token["raw"]
        if not isinstance(raw, str) or not raw:
            raise InputError(
                "invalid-input", path + "/raw", "raw must be a nonempty string"
            )
        copied: dict[str, Any] = {"raw": raw}
        if "time" in token:
            timing = token["time"]
            if (
                not isinstance(timing, dict)
                or timing.keys() != {"start", "duration"}
                or any(not _valid_time(v) for v in timing.values())
            ):
                raise InputError(
                    "invalid-timing",
                    path + "/time",
                    "supply finite nonnegative start and duration together",
                )
            copied["time"] = dict(timing)
        tokens.append(copied)
    result: dict[str, Any] = {"format": FORMAT, "version": 1, "tokens": tokens}
    if "relations" in source:
        if not isinstance(source["relations"], list):
            raise InputError(
                "invalid-relation", "/relations", "relations must be an array"
            )
        relations = []
        for index, value in enumerate(source["relations"]):
            path = f"/relations/{index}"
            relation = _object(value, {"type", "source", "target"}, set(), path)
            if relation["type"] != HOST:
                raise InputError(
                    "invalid-relation", path + "/type", "undeclared source relation"
                )
            left = endpoint(relation["source"], len(tokens), path + "/source")
            right = endpoint(relation["target"], len(tokens), path + "/target")
            if left == right:
                raise InputError("invalid-relation", path, "a tone cannot host itself")
            relations.append(dict(relation))
        result["relations"] = relations
    return result
