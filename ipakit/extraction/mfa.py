"""Build MFA vocabulary artifacts from a validated local mfa-models source.

The source is a dev-only git checkout, not a package or runtime dependency.
This module validates and renders without acquisition or output writes.
Developer scripts own fetching and publication. Curated compatibility inputs
live in data/mfa-curation.json and are checked against each source inventory.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import warnings
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import quoteattr

from .._provenance import SourceMetadata
from ..features import IPAFeatures
from . import (
    BuildResult,
    SourceContentError,
    SourceIdentity,
    SourceMissingError,
    SourceVersionError,
)

REVISION = "d6eff86a42c6a90b641e17dfdf7a16555b934483"
ORIGIN = "https://github.com/MontrealCorpusTools/mfa-models.git"
UPSTREAM = "Montreal Forced Aligner"
UPSTREAM_URL = f"https://github.com/MontrealCorpusTools/mfa-models/tree/{REVISION}"
PIN = f"mfa-models@{REVISION}"
KIND = "dictionary-phone-set"
OUT = Path("ipakit/data/bridges/mfa")
SUMMARY = Path("docs/mfa-vocabularies.md")
META_SHA256 = "9f7c029fd82ec15f742f7ea615c293967151706b12e7993aaac7f33551731af1"
DICTIONARY = Path("dictionary/english/us_mfa/english_us_mfa.dict")
DICTIONARY_SHA256 = "6640a93655af618429ddc879484318d6755892c9d90b8848988ff5b8c10e6915"
DROP = "narrow detail outside the MFA inventory"


@dataclass(frozen=True)
class Curated:
    """Hand-made detail a generated declaration would otherwise lose."""

    reductions: tuple[tuple[str, str], ...] = ()
    exemplars: Mapping[str, str] = field(default_factory=dict)
    notes: Mapping[str, str] = field(default_factory=dict)


def _curation() -> dict[str, Curated]:
    path = Path(__file__).resolve().parents[1] / "data/mfa-curation.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        name: Curated(
            reductions=tuple(tuple(pair) for pair in item.get("reductions", ())),
            notes=item.get("notes", {}),
            exemplars=item.get("exemplars", {}),
        )
        for name, item in data.items()
    }


CURATED = _curation()


@dataclass(frozen=True)
class Selected:
    declaration: str
    directory: Path
    meta: Mapping[str, object]


def _run(source: Path, *args: str) -> str:
    """Run Git in ``source`` and return stripped stdout."""
    return subprocess.run(
        ["git", "-C", str(source), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _meta_digest(source: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(source.glob("dictionary/**/meta.json")):
        digest.update(path.relative_to(source).as_posix().encode() + b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def require_pin(source: Path, *, dictionary: bool = False) -> None:
    """Refuse a checkout or archive other than the pinned source content."""
    try:
        found = _run(source, "rev-parse", "HEAD")
    except (OSError, subprocess.CalledProcessError) as error:
        if not (source / "dictionary").is_dir():
            raise SourceMissingError(
                f"mfa-models checkout is unreadable: {source}"
            ) from error
        found = f"meta-sha256:{_meta_digest(source)}"
        if found != f"meta-sha256:{META_SHA256}":
            raise SourceContentError(
                f"mfa-models metadata has {found}; required {META_SHA256}"
            ) from error
    else:
        if found != REVISION:
            raise SourceVersionError(
                f"mfa-models checkout is at {found}; required {REVISION}"
            )
    digest = _meta_digest(source)
    if digest != META_SHA256:
        raise SourceContentError(
            f"mfa-models metadata has sha256:{digest}; required sha256:{META_SHA256}"
        )
    if dictionary:
        path = source / DICTIONARY
        if not path.is_file():
            raise SourceMissingError(f"MFA dictionary is absent: {path}")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != DICTIONARY_SHA256:
            raise SourceContentError(
                f"MFA dictionary has sha256:{digest}; required sha256:{DICTIONARY_SHA256}"
            )


def _version(path: Path) -> tuple[tuple[int, ...], str]:
    match = re.fullmatch(r"v([0-9]+(?:\.[0-9]+)*)([A-Za-z]*)", path.name)
    if match is None:
        raise ValueError(f"unrecognized mfa-models version directory: {path}")
    return tuple(int(part) for part in match.group(1).split(".")), match.group(2)


def _select(source: Path) -> tuple[list[Selected], dict[str, list[Path]]]:
    selected: list[Selected] = []
    skipped: dict[str, list[Path]] = defaultdict(list)
    for variant in sorted((source / "dictionary").glob("*/*")):
        if not variant.is_dir():
            continue
        candidates = []
        sets = set()
        for path in sorted(variant.glob("*/meta.json")):
            meta = json.loads(path.read_text())
            phone_set = str(meta["phone_set"])
            sets.add(phone_set)
            if phone_set == "MFA":
                candidates.append((path.parent, meta))
        if not candidates:
            for phone_set in sorted(sets):
                skipped[phone_set].append(variant.relative_to(source))
            continue
        picked_dir, picked_meta = max(candidates, key=lambda item: _version(item[0]))
        for other_dir, other_meta in candidates:
            if str(other_meta["train_date"]) > str(picked_meta["train_date"]):
                raise ValueError(
                    f"version order picks {picked_dir} after later-trained {other_dir}"
                )
        language = variant.parent.name
        declaration = (
            language
            if variant.name == "mfa"
            else f"{language}_{variant.name.removesuffix('_mfa')}"
        )
        selected.append(Selected(declaration, picked_dir, picked_meta))
    names = [item.declaration for item in selected]
    if len(names) != len(set(names)):
        raise ValueError(
            "MFA dictionary directories produce duplicate declaration names"
        )
    return sorted(selected, key=lambda item: item.declaration), skipped


def spelling(phone: str, ipa: IPAFeatures) -> tuple[str | None, str | None]:
    """Return the house spelling of one MFA phone, or the reason it has none."""
    from ipakit import validate_ipa
    from ipakit.form import Form
    from ipakit.phoneset_map import tie_delimited_entry

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            parsed = Form.parse(phone, strict=True)
    except (ValueError, UserWarning):
        symbols = []
        for issue in validate_ipa(phone):
            symbol = issue.get("symbol")
            if (
                issue.get("code") == "unknown_symbol"
                and isinstance(symbol, str)
                and symbol not in symbols
            ):
                symbols.append(symbol)
        suffix = " ".join(f"U+{ord(symbol):04X}" for symbol in symbols)
        return None, f"outside-house-ipa: {suffix}" if suffix else "outside-house-ipa"
    if len(parsed.units) == 1:
        return phone, None
    tied = tie_delimited_entry(phone, ipa)
    if tied != phone:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                if len(Form.parse(tied, strict=True).units) == 1:
                    return tied, None
        except (ValueError, UserWarning):
            pass
    return None, "not-one-house-unit"


def _spdx_license(value: str) -> str:
    """Translate the one upstream license spelling to its SPDX identifier."""
    if value == "CC BY 4.0":
        return "CC-BY-4.0"
    raise ValueError(f"MFA dictionary has unrecognized license {value!r}")


def _checked_phones(
    item: Selected, ipa: IPAFeatures
) -> list[tuple[str, str | None, str | None]]:
    from ipakit.form import Form

    raw_phones = item.meta["phones"]
    if not isinstance(raw_phones, list):
        raise SourceContentError("MFA phones metadata must be a list")
    phones = [str(phone) for phone in raw_phones]
    result = [(phone, *spelling(phone, ipa)) for phone in phones]
    values = {phone: value for phone, value, _ in result}
    curated = CURATED.get(item.declaration, Curated())
    for kind, keys in (("exemplar", curated.exemplars), ("note", curated.notes)):
        for phone in keys:
            if phone not in values or values[phone] is None:
                raise ValueError(
                    f"curated {kind} phone {phone!r} is absent or refused in {item.declaration}"
                )
    for source, target in curated.reductions:
        parsed = Form.parse(source, strict=True)
        if len(parsed.units) != 1 or source in values:
            raise ValueError(
                f"curated reduction source {source!r} is invalid in {item.declaration}"
            )
        if target not in values or values[target] is None:
            raise ValueError(
                f"curated reduction target {target!r} is absent or refused in {item.declaration}"
            )
    outputs = [phone for phone, value, _ in result if value is not None]
    if len(outputs) != len(set(outputs)):
        raise ValueError(f"duplicate MFA phone outputs in {item.declaration}")
    return result


def _render(item: Selected, phones: list[tuple[str, str | None, str | None]]) -> bytes:
    meta = item.meta
    curated = CURATED.get(item.declaration, Curated())
    artifact = f"{meta['name']} dictionary v{meta['version']}"
    license_id = _spdx_license(str(meta["license"]))
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f"<!-- Generated by scripts/mfa_vocabularies.py from mfa-models {REVISION}. -->",
        (
            f"<vocabulary name={quoteattr('mfa:' + item.declaration)} "
            f"version={quoteattr(PIN)} upstream={quoteattr(UPSTREAM)} "
            f"upstream-url={quoteattr(UPSTREAM_URL)} "
            f"artifact={quoteattr(artifact)} license={quoteattr(license_id)} "
            f'kind={quoteattr(KIND)} tier="mfa" '
            'source-style="segmented" separator=" ">'
        ),
        "  <round-trip>",
        '    <external-to-house fidelity="lossless" />',
    ]
    if curated.reductions:
        lines.extend(
            [
                '    <house-to-external fidelity="lossy-with-report">',
                f"      <drop name={quoteattr(DROP)} />",
                "    </house-to-external>",
                "  </round-trip>",
                "  <mapper>",
                *(
                    f"    <reduction source={quoteattr(source)} target={quoteattr(target)} drop={quoteattr(DROP)} />"
                    for source, target in curated.reductions
                ),
                "  </mapper>",
            ]
        )
    else:
        lines.extend(
            ['    <house-to-external fidelity="lossless" />', "  </round-trip>"]
        )
    lines.extend(
        f"  <refusal spelling={quoteattr(phone)} reason={quoteattr(reason or '')} />"
        for phone, value, reason in phones
        if value is None
    )
    for phone, value, _ in phones:
        if value is None:
            continue
        attrs = f"spelling={quoteattr(value)}"
        if value != phone:
            attrs += f" output={quoteattr(phone)}"
        if phone in curated.exemplars:
            attrs += f" exemplar={quoteattr(curated.exemplars[phone])}"
        if phone in curated.notes:
            attrs += f" notes={quoteattr(curated.notes[phone])}"
        lines.append(f"  <atom {attrs} />")
    lines.append("</vocabulary>")
    return ("\n".join(lines) + "\n").encode()


def _render_union(
    selected: list[Selected],
    readings: Mapping[str, list[tuple[str, str | None, str | None]]],
) -> bytes:
    licenses = {_spdx_license(str(item.meta["license"])) for item in selected}
    if len(licenses) != 1:
        raise ValueError(f"MFA dictionary licenses disagree: {sorted(licenses)!r}")
    by_phone: dict[str, list[tuple[str, str | None, str | None]]] = defaultdict(list)
    for item in selected:
        for phone, value, reason in readings[item.declaration]:
            by_phone[phone].append((item.declaration, value, reason))
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f"<!-- Generated by scripts/mfa_vocabularies.py from mfa-models {REVISION}; phones are ordered by Unicode code points. -->",
        (
            f'<vocabulary name="mfa" version={quoteattr(PIN)} '
            f"upstream={quoteattr(UPSTREAM)} upstream-url={quoteattr(UPSTREAM_URL)} "
            f"artifact={quoteattr('MFA phone-set union of selected dictionaries')} "
            f"license={quoteattr(licenses.pop())} kind={quoteattr(KIND)} "
            'tier="mfa" source-style="segmented" separator=" ">'
        ),
        "  <round-trip>",
        '    <external-to-house fidelity="lossless" />',
        '    <house-to-external fidelity="lossless" />',
        "  </round-trip>",
    ]
    atoms = []
    refusals = []
    for phone in sorted(by_phone):
        entries = by_phone[phone]
        values = sorted({value for _, value, _ in entries if value is not None})
        reasons = sorted({reason for _, _, reason in entries if reason is not None})
        if len(values) > 1:
            reason = "declarations disagree on the house spelling: " + ", ".join(
                f"{min(name for name, candidate, _ in entries if candidate == value)}={value}"
                for value in values
            )
            refusals.append((phone, reason))
        elif not values:
            if len(reasons) != 1:
                raise ValueError(
                    f"declarations disagree on refusal reason for {phone!r}"
                )
            refusals.append((phone, reasons[0]))
        else:
            atoms.append((phone, values[0]))
    lines.extend(
        f"  <refusal spelling={quoteattr(phone)} reason={quoteattr(reason or '')} />"
        for phone, reason in refusals
    )
    lines.extend(
        f"  <atom spelling={quoteattr(value)}"
        + (f" output={quoteattr(phone)}" if value != phone else "")
        + " />"
        for phone, value in atoms
    )
    lines.append("</vocabulary>")
    return ("\n".join(lines) + "\n").encode()


def _summary(
    source: Path,
    selected: list[Selected],
    skipped: Mapping[str, list[Path]],
    readings: Mapping[str, list[tuple[str, str | None, str | None]]],
) -> bytes:
    union = {phone for values in readings.values() for phone, _, _ in values}
    refused: dict[str, tuple[str, list[str]]] = {}
    for name, values in readings.items():
        for phone, value, reason in values:
            if value is None:
                stored_reason, names = refused.setdefault(phone, (reason or "", []))
                if stored_reason != reason:
                    raise ValueError(
                        f"declarations disagree on refusal reason for {phone!r}"
                    )
                names.append(name)
    lines = [
        "# MFA vocabulary generation summary",
        "",
        f"Generated from mfa-models commit `{REVISION}` at [{ORIGIN}]({ORIGIN}). The declarations are the inventory, and the counts on this page are generated.",
        "",
        "The source is a `[dev]`-only git clone, never a runtime dependency or a manual prerequisite. `python scripts/mfa_vocabularies.py generate --fetch` clones the metadata at the pin, `--source PATH` points at an existing clone, and the `MFA_MODELS` environment variable supplies the default path. There is nothing to install with pip because the source is a repository, not a package.",
        "",
        "## Union",
        "",
        f"The union covers {len(union)} distinct MFA phones: {len(union) - len(refused)} atoms and {len(refused)} refusals.",
        "",
        "## Declarations",
        "",
        "| Declaration | Artifact tag | Source directory | Atoms | Refusals |",
        "|---|---|---|---:|---:|",
    ]
    for item in selected:
        values = readings[item.declaration]
        atoms = sum(value is not None for _, value, _ in values)
        refusals = len(values) - atoms
        source_dir = item.directory.relative_to(source).as_posix()
        tag = f"{item.meta['name']}-v{item.meta['version']}"
        lines.append(
            f"| `{item.declaration}` | `{tag}` | `{source_dir}` | {atoms} | {refusals} |"
        )
    lines.extend(
        [
            "",
            "## Skipped dictionaries",
            "",
            "A dictionary whose `phone_set` is not `MFA` is skipped. `ARPA` is the English ARPAbet set, `CV` the Common Voice set, `PINYIN` the Mandarin pinyin set, and `PROSODYLAB` the Prosodylab set; none of them is the MFA phone set.",
            "",
        ]
    )
    for phone_set in sorted(skipped):
        paths = ", ".join(f"`{path.as_posix()}`" for path in skipped[phone_set])
        lines.extend([f"### {phone_set}", "", paths, ""])
    lines.extend(["## Refusals", ""])
    for phone in sorted(refused):
        reason, names = refused[phone]
        codepoints = " ".join(f"U+{ord(character):04X}" for character in phone)
        lines.append(
            f"`{phone}` ({codepoints}) — {reason}; declarations: {', '.join(sorted(names))}."
        )
    return ("\n".join(lines) + "\n").encode()


def generate(source: Path) -> dict[Path, bytes]:
    """Produce every declaration and the generated summary."""
    require_pin(source)
    from ipakit import _get_ipa

    selected, skipped = _select(source)
    ipa = _get_ipa()
    readings = {item.declaration: _checked_phones(item, ipa) for item in selected}
    artifacts = {
        OUT / f"{item.declaration}.xml": _render(item, readings[item.declaration])
        for item in selected
    }
    artifacts[OUT / "mfa.xml"] = _render_union(selected, readings)
    artifacts[SUMMARY] = _summary(source, selected, skipped, readings)
    return artifacts


def build(source: Path) -> BuildResult:
    """Validate and render MFA declarations without writing or acquiring data."""
    artifacts = generate(source)
    metadata = SourceMetadata.from_root(
        ET.fromstring(artifacts[OUT / "mfa.xml"]), OUT / "mfa.xml"
    )
    return BuildResult(
        artifacts,
        (OUT / "*.xml",),
        SourceIdentity(metadata, {"dictionary/**/meta.json": META_SHA256}),
    )
