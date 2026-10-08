"""Refuse package data whose source license class does not permit shipping."""

from __future__ import annotations

import copy
import fnmatch
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from xml.etree import ElementTree

import pytest

from .test_packaging import built_wheel as packaging_built_wheel  # noqa: F401
from .test_packaging import package_source  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
REGISTER_PATH = ROOT / "tests/license-classes.json"
RECEIPT_SCHEMA = {"id": "ipakit-source-receipt", "version": 1}
CLASSES = {
    "shippable",
    "shippable-share-alike",
    "derived-shippable",
    "internal-only",
}
SHIPPABLE = CLASSES - {"internal-only"}
SYNTHETIC_LDC_ID = "LicenseRef-LDC-SYNTHETIC"
SYNTHETIC_LDC_PATH = "ipakit/data/phonemaps/synthetic-ldc.xml"


@dataclass(frozen=True)
class Route:
    kind: str
    license_id: str | None
    license_class: str


@dataclass(frozen=True)
class Audit:
    members: tuple[str, ...]
    routes: dict[str, tuple[Route, ...]]
    unclassified: tuple[str, ...]
    two_routes: tuple[str, ...]
    forbidden: tuple[tuple[str, str | None, str], ...]
    classes: frozenset[str]
    derived: tuple[str, ...]
    dead: tuple[str, ...]


def _load_register() -> dict[str, Any]:
    return json.loads(REGISTER_PATH.read_text())


def _validate_register(register: dict[str, Any]) -> None:
    if set(register) != {"licenses", "defaults", "house"}:
        raise ValueError("register must contain exactly licenses, defaults, and house")
    if not isinstance(register["licenses"], dict) or not register["licenses"]:
        raise ValueError("licenses must be a nonempty object")
    for license_id, entry in register["licenses"].items():
        allowed = {"spdx", "class", "term", "artifacts"}
        if not isinstance(entry, dict) or set(entry) - allowed:
            raise ValueError(f"{license_id}: invalid license entry")
        if entry.get("spdx") != license_id:
            raise ValueError(f"{license_id}: spdx must repeat the license id")
        license_class = entry.get("class")
        if license_class not in CLASSES:
            raise ValueError(f"{license_id}: invalid or missing class")
        if license_class == "derived-shippable":
            if not isinstance(entry.get("term"), str) or not entry["term"].strip():
                raise ValueError(f"{license_id}: derived-shippable requires a term")
            artifacts = entry.get("artifacts")
            if (
                not isinstance(artifacts, list)
                or not artifacts
                or not all(isinstance(path, str) and path for path in artifacts)
                or len(set(artifacts)) != len(artifacts)
            ):
                raise ValueError(
                    f"{license_id}: derived-shippable requires unique artifacts"
                )
        else:
            if "term" in entry:
                raise ValueError(f"{license_id}: term is only for derived-shippable")
            if "artifacts" in entry:
                raise ValueError(
                    f"{license_id}: artifacts are only for derived-shippable"
                )

    if set(register["defaults"]) != {"LicenseRef-LDC-*"}:
        raise ValueError("the sole default must be LicenseRef-LDC-*")
    default = register["defaults"]["LicenseRef-LDC-*"]
    if default != {
        "spdx": "LicenseRef-LDC-*",
        "class": "internal-only",
    }:
        raise ValueError("unlisted LicenseRef-LDC-* ids must be internal-only")

    if not isinstance(register["house"], dict):
        raise ValueError("house must be an object")
    for path, entry in register["house"].items():
        if (
            not path.startswith("ipakit/")
            or not isinstance(entry, dict)
            or set(entry) != {"class", "reason"}
            or entry["class"] not in SHIPPABLE
            or not isinstance(entry["reason"], str)
            or not entry["reason"].strip()
            or "\n" in entry["reason"]
        ):
            raise ValueError(f"{path}: invalid house entry")


def _join_receipt_path(receipt_path: str, value: str) -> str:
    if value.startswith("ipakit/"):
        return value
    return str(PurePosixPath(receipt_path).parent / value)


def _license_class(register: dict[str, Any], license_id: str, path: str) -> str:
    entry = register["licenses"].get(license_id)
    if entry is None:
        for pattern, default in register["defaults"].items():
            if fnmatch.fnmatchcase(license_id, pattern):
                return default["class"]
        return "unclassified"
    license_class = entry["class"]
    if license_class == "derived-shippable" and path not in entry["artifacts"]:
        return "derived-shippable outside its artifacts"
    return license_class


def _audit(wheel: Path, register: dict[str, Any]) -> Audit:
    _validate_register(register)
    with zipfile.ZipFile(wheel) as archive:
        members = tuple(
            sorted(
                name
                for name in archive.namelist()
                if name.startswith("ipakit/") and not name.endswith(".py")
            )
        )
        payloads = {name: archive.read(name) for name in members}

    receipts: dict[str, dict[str, Any]] = {}
    for path, payload in payloads.items():
        if not path.endswith(".json"):
            continue
        try:
            value = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(value, dict) and value.get("schema") == RECEIPT_SCHEMA:
            receipts[path] = value

    receipt_members: dict[str, set[str]] = {}
    for receipt_path, receipt in receipts.items():
        related = {receipt_path}
        related.update(
            _join_receipt_path(receipt_path, path) for path in receipt["artifacts"]
        )
        related.update(
            _join_receipt_path(receipt_path, path)
            for path in receipt["license"]["notices"]
        )
        for path in related:
            receipt_members.setdefault(path, set()).add(receipt_path)

    routes: dict[str, tuple[Route, ...]] = {}
    used_ids: set[str] = set()
    classes: set[str] = set()
    derived: list[str] = []
    forbidden: list[tuple[str, str | None, str]] = []
    for path in members:
        member_routes: list[Route] = []
        xml_root = None
        if path.endswith(".xml"):
            try:
                xml_root = ElementTree.fromstring(payloads[path])
            except ElementTree.ParseError:
                xml_root = None
        if xml_root is not None and "license" in xml_root.attrib:
            license_id = xml_root.attrib["license"]
            member_routes.append(
                Route(
                    "xml-license",
                    license_id,
                    _license_class(register, license_id, path),
                )
            )
        pointer = None if xml_root is None else xml_root.attrib.get("source-receipt")
        if pointer is not None:
            receipt_path = str(PurePosixPath(path).parent / pointer)
            receipt = receipts.get(receipt_path)
            license_id = None if receipt is None else receipt["license"]["id"]
            license_class = (
                "unclassified"
                if license_id is None
                else _license_class(register, license_id, path)
            )
            member_routes.append(Route("source-receipt", license_id, license_class))
        else:
            for receipt_path in sorted(receipt_members.get(path, ())):
                license_id = receipts[receipt_path]["license"]["id"]
                member_routes.append(
                    Route(
                        "receipt-member",
                        license_id,
                        _license_class(register, license_id, path),
                    )
                )
        if path in register["house"]:
            member_routes.append(Route("house", None, register["house"][path]["class"]))
        routes[path] = tuple(member_routes)
        for route in member_routes:
            if route.license_id in register["licenses"]:
                used_ids.add(route.license_id)
            if route.license_class in SHIPPABLE:
                classes.add(route.license_class)
            else:
                forbidden.append((path, route.license_id, route.license_class))
            if route.license_class == "derived-shippable":
                derived.append(path)

    unclassified = tuple(path for path in members if not routes[path])
    two_routes = tuple(
        path for path in members if len(routes[path]) != 1 and routes[path]
    )
    dead = tuple(sorted(set(register["licenses"]) - used_ids))
    return Audit(
        members=members,
        routes=routes,
        unclassified=unclassified,
        two_routes=two_routes,
        forbidden=tuple(forbidden),
        classes=frozenset(classes),
        derived=tuple(sorted(derived)),
        dead=dead,
    )


def _mutate_wheel(
    built_wheel: Path, tmp_path: Path, mutation: str, replacements: dict[str, bytes]
) -> Path:
    target = tmp_path / f"{mutation}.whl"
    with zipfile.ZipFile(built_wheel) as source, zipfile.ZipFile(target, "w") as out:
        existing = set(source.namelist())
        for info in source.infolist():
            out.writestr(info, replacements.get(info.filename, source.read(info)))
        for path, payload in replacements.items():
            if path not in existing:
                out.writestr(path, payload)
    return target


def _synthetic_derived_register() -> dict[str, Any]:
    register = _load_register()
    register["licenses"][SYNTHETIC_LDC_ID] = {
        "spdx": SYNTHETIC_LDC_ID,
        "class": "derived-shippable",
        "term": "Synthetic test term permitting only the named artifact.",
        "artifacts": [SYNTHETIC_LDC_PATH],
    }
    return register


def _synthetic_xml(license_id: str) -> bytes:
    return f'<phonemap license="{license_id}"/>\n'.encode()


def test_t1_every_shipped_member_has_exactly_one_route(
    packaging_built_wheel,  # noqa: F811
):
    """Mutation ``default-house`` removes a real house route."""
    register = _load_register()
    actual = _audit(packaging_built_wheel, register)
    assert actual.unclassified == ()
    assert actual.two_routes == ()
    assert len(actual.members) > 90
    assert actual.classes == {"shippable"}

    mutated = copy.deepcopy(register)
    removed = sorted(mutated["house"])[0]
    del mutated["house"][removed]
    fault = _audit(packaging_built_wheel, mutated)
    assert fault.unclassified == (removed,), "default-house mutation escaped"


def test_t2_no_internal_only_source_is_reachable(
    packaging_built_wheel, tmp_path  # noqa: F811
):
    """Mutation ``checkout-only`` injects a restricted XRMB member."""
    register = _load_register()
    actual = _audit(packaging_built_wheel, register)
    assert actual.forbidden == ()
    assert actual.derived == ()

    license_id = "LicenseRef-XRMB-SYNTHETIC"
    path = "ipakit/data/phonemaps/synthetic-xrmb.xml"
    mutated_register = copy.deepcopy(register)
    mutated_register["licenses"][license_id] = {
        "spdx": license_id,
        "class": "internal-only",
    }
    wheel = _mutate_wheel(
        packaging_built_wheel,
        tmp_path,
        "checkout-only",
        {path: _synthetic_xml(license_id)},
    )
    fault = _audit(wheel, mutated_register)
    assert fault.forbidden == ((path, license_id, "internal-only"),)


def test_t3_an_explicit_internal_only_entry_is_refused(
    packaging_built_wheel, tmp_path  # noqa: F811
):
    """Mutation ``receipts-only`` flips an injected LDC class in memory."""
    register = _synthetic_derived_register()
    wheel = _mutate_wheel(
        packaging_built_wheel,
        tmp_path,
        "receipts-only",
        {SYNTHETIC_LDC_PATH: _synthetic_xml(SYNTHETIC_LDC_ID)},
    )
    assert _audit(wheel, register).derived == (SYNTHETIC_LDC_PATH,)
    register["licenses"][SYNTHETIC_LDC_ID] = {
        "spdx": SYNTHETIC_LDC_ID,
        "class": "internal-only",
    }
    fault = _audit(wheel, register)
    assert fault.forbidden == ((SYNTHETIC_LDC_PATH, SYNTHETIC_LDC_ID, "internal-only"),)


def test_t4_phoible_receipt_members_are_all_guarded(
    packaging_built_wheel,  # noqa: F811
):
    """Mutation ``xml-only`` flips the license the PHOIBLE receipt names."""
    register = _load_register()
    expected = tuple(
        sorted(
            path
            for path, routes in _audit(packaging_built_wheel, register).routes.items()
            if any(route.license_id == "CC-BY-4.0" for route in routes)
        )
    )
    phoible = {path for path in expected if path.startswith("ipakit/data/phoible/")}
    assert len(phoible) == 8
    mutated = copy.deepcopy(register)
    mutated["licenses"]["CC-BY-4.0"]["class"] = "internal-only"
    fault = _audit(packaging_built_wheel, mutated)
    assert tuple(path for path, _, _ in fault.forbidden) == expected


def test_t5_unlisted_ldc_id_uses_the_internal_only_default(
    packaging_built_wheel, tmp_path  # noqa: F811
):
    """Mutation ``permissive-ldc-default`` injects an unlisted LDC id."""
    license_id = "LicenseRef-LDC-PRONLEX"
    wheel = _mutate_wheel(
        packaging_built_wheel,
        tmp_path,
        "permissive-ldc-default",
        {SYNTHETIC_LDC_PATH: _synthetic_xml(license_id)},
    )
    fault = _audit(wheel, _load_register())
    assert fault.forbidden == ((SYNTHETIC_LDC_PATH, license_id, "internal-only"),)


def test_t6_derived_class_is_scoped_to_named_artifacts(
    packaging_built_wheel, tmp_path  # noqa: F811
):
    """Mutation ``class-by-license-only`` injects an unscoped LDC copy."""
    register = _synthetic_derived_register()
    copied_path = "ipakit/data/phonemaps/synthetic-ldc-copy.xml"
    wheel = _mutate_wheel(
        packaging_built_wheel,
        tmp_path,
        "class-by-license-only",
        {copied_path: _synthetic_xml(SYNTHETIC_LDC_ID)},
    )
    fault = _audit(wheel, register)
    assert fault.forbidden == (
        (
            copied_path,
            SYNTHETIC_LDC_ID,
            "derived-shippable outside its artifacts",
        ),
    )


def test_t7_derived_class_requires_only_its_own_term():
    """Mutations ``term-unchecked`` delete a term and put one on BSD."""
    missing = _synthetic_derived_register()
    del missing["licenses"][SYNTHETIC_LDC_ID]["term"]
    with pytest.raises(
        ValueError,
        match=f"{SYNTHETIC_LDC_ID}: derived-shippable requires a term",
    ):
        _validate_register(missing)

    misplaced = _load_register()
    misplaced["licenses"]["BSD-2-Clause"]["term"] = "not applicable"
    with pytest.raises(
        ValueError, match="BSD-2-Clause: term is only for derived-shippable"
    ):
        _validate_register(misplaced)


def test_t8_two_routes_are_refused_even_when_both_ship(
    packaging_built_wheel, tmp_path  # noqa: F811
):
    """Mutation ``house-wins`` adds an injected LDC artifact to house."""
    register = _synthetic_derived_register()
    register["house"][SYNTHETIC_LDC_PATH] = {
        "class": "shippable",
        "reason": "Synthetic duplicate route for T8.",
    }
    wheel = _mutate_wheel(
        packaging_built_wheel,
        tmp_path,
        "house-wins",
        {SYNTHETIC_LDC_PATH: _synthetic_xml(SYNTHETIC_LDC_ID)},
    )
    fault = _audit(wheel, register)
    assert fault.two_routes == (SYNTHETIC_LDC_PATH,)


def test_t9_no_dead_register_entries(packaging_built_wheel):  # noqa: F811
    """Mutation ``stale-register`` adds an unused license entry."""
    register = _load_register()
    assert _audit(packaging_built_wheel, register).dead == ()
    license_id = "LicenseRef-STALE-SYNTHETIC"
    register["licenses"][license_id] = {
        "spdx": license_id,
        "class": "shippable",
    }
    assert _audit(packaging_built_wheel, register).dead == (license_id,)


def test_t10_unknown_license_is_not_assumed_shippable(
    packaging_built_wheel, tmp_path  # noqa: F811
):
    """Mutation ``unknown-as-shippable`` rewrites one real MFA XML root."""
    path = "ipakit/data/bridges/mfa/arabic.xml"
    with zipfile.ZipFile(packaging_built_wheel) as archive:
        original = archive.read(path)
    changed = original.replace(b'license="CC-BY-4.0"', b'license="CC-BY-NC-4.0"')
    assert changed != original
    wheel = _mutate_wheel(
        packaging_built_wheel,
        tmp_path,
        "unknown-as-shippable",
        {path: changed},
    )
    fault = _audit(wheel, _load_register())
    assert fault.forbidden == ((path, "CC-BY-NC-4.0", "unclassified"),)
