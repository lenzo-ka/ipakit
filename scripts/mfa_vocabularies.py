#!/usr/bin/env python3
"""Generate the MFA-phone-set vocabulary declarations from mfa-models.

The source is a dev-only git checkout, not a package or runtime dependency.
Pass an existing checkout with ``--source``, or let ``--fetch`` obtain its
sparse metadata tree.  One generate command reproduces every artifact at the
pinned revision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import warnings
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import quoteattr

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
REVISION = "d6eff86a42c6a90b641e17dfdf7a16555b934483"
ORIGIN = "https://github.com/MontrealCorpusTools/mfa-models.git"
SOURCE_ENV = "MFA_MODELS"
DEFAULT_SOURCE = Path(
    os.environ.get(SOURCE_ENV, Path.home() / ".cache" / "ipakit" / "mfa-models")
)
OUT = ROOT / "ipakit" / "data" / "bridges" / "mfa"
SUMMARY = ROOT / "docs" / "mfa-vocabularies.md"
META_SHA256 = "9f7c029fd82ec15f742f7ea615c293967151706b12e7993aaac7f33551731af1"
DROP = "narrow detail outside the MFA inventory"


@dataclass(frozen=True)
class Curated:
    """Hand-made detail a generated declaration would otherwise lose."""

    reductions: tuple[tuple[str, str], ...] = ()
    exemplars: Mapping[str, str] = field(default_factory=dict)
    notes: Mapping[str, str] = field(default_factory=dict)


CURATED = {
    "english": Curated(
        reductions=(("n̪", "n"),),
        notes={"ɚ": "MFA rhotic-vowel unit"},
        exemplars=dict(item.split(" ", 1) for item in """p crip
pʰ pampa
b buys
f frown
v vonda
θ third
t̪ thick
ð thou
d̪ there
t gut
tʰ tuple
d drama
ɾ dad
tʃ chip
dʒ jules
ʃ shape
ʒ usual
s slot
z noisy
ɹ tree
m mates
m̩ 'em
n shin
ɲ sonya
ŋ sang
ɟ mcgee
ɡ rig
c skin
cʷ quick
cʰ cute
k mink
kʷ quart
kʰ cone
ç hugh
h habit
aj mice
j yorke
w will""".splitlines()),
    )
}


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


def require_pin(source: Path) -> None:
    """Refuse a checkout or archive other than the pinned source content."""
    try:
        found = _run(source, "rev-parse", "HEAD")
    except (OSError, subprocess.CalledProcessError) as error:
        if not (source / "dictionary").is_dir():
            raise ValueError(f"mfa-models checkout is unreadable: {source}") from error
        found = f"meta-sha256:{_meta_digest(source)}"
        if found == f"meta-sha256:{META_SHA256}":
            return
    if found != REVISION:
        raise ValueError(f"mfa-models checkout is at {found}; required {REVISION}")
    digest = _meta_digest(source)
    if digest != META_SHA256:
        raise ValueError(
            f"mfa-models metadata has sha256:{digest}; required sha256:{META_SHA256}"
        )


def fetch(source: Path) -> None:
    """Obtain only the pinned dictionary metadata when it is absent."""
    if (source / "dictionary").is_dir():
        return
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    _run(source, "remote", "add", "origin", ORIGIN)
    _run(
        source, "fetch", "-q", "--depth", "1", "--filter=blob:none", "origin", REVISION
    )
    _run(
        source,
        "sparse-checkout",
        "set",
        "--no-cone",
        "/dictionary/*/*/*/meta.json",
    )
    _run(source, "checkout", "-q", "FETCH_HEAD")


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


def spelling(phone: str, ipa) -> tuple[str | None, str | None]:
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
            if issue.get("code") == "unknown_symbol" and symbol not in symbols:
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


def _checked_phones(item: Selected, ipa) -> list[tuple[str, str | None, str | None]]:
    from ipakit.form import Form

    phones = [str(phone) for phone in item.meta["phones"]]  # type: ignore[index]
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
    version = f"{meta['name']}-v{meta['version']}"
    provenance = (
        f"Montreal Forced Aligner {meta['name']} dictionary v{meta['version']} "
        f"({meta['license']})"
    )
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f"<!-- Generated by scripts/mfa_vocabularies.py from mfa-models {REVISION}. -->",
        f"<vocabulary name={quoteattr('mfa:' + item.declaration)} version={quoteattr(version)} provenance={quoteattr(provenance)} tier=\"mfa\" source-style=\"segmented\" separator=\" \">",
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
    licenses = {str(item.meta["license"]) for item in selected}
    if len(licenses) != 1:
        raise ValueError(f"MFA dictionary licenses disagree: {sorted(licenses)!r}")
    by_phone: dict[str, list[tuple[str, str | None, str | None]]] = defaultdict(list)
    for item in selected:
        for phone, value, reason in readings[item.declaration]:
            by_phone[phone].append((item.declaration, value, reason))
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f"<!-- Generated by scripts/mfa_vocabularies.py from mfa-models {REVISION}; phones are ordered by Unicode code points. -->",
        f"<vocabulary name=\"mfa\" version={quoteattr('mfa-models@' + REVISION)} provenance={quoteattr('Montreal Forced Aligner MFA phone set, the union of every MFA-phone-set dictionary at mfa-models ' + REVISION[:7] + ' (' + licenses.pop() + ')')} tier=\"mfa\" source-style=\"segmented\" separator=\" \">",
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


def stale(artifacts: Mapping[Path, bytes], root: Path) -> list[Path]:
    """Return missing, changed, and unclaimed declaration artifact paths."""
    relative = {path.relative_to(ROOT): content for path, content in artifacts.items()}
    result = [
        path
        for path, content in relative.items()
        if not (root / path).is_file() or (root / path).read_bytes() != content
    ]
    claimed = {root / path for path in relative}
    extras = set((root / OUT.relative_to(ROOT)).glob("*.xml")) - claimed
    result.extend(path.relative_to(root) for path in extras)
    return sorted(result)


def main() -> int:
    """Write generated data or check it byte for byte."""
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("generate", "check"))
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    try:
        if args.fetch:
            fetch(args.source)
        artifacts = generate(args.source)
    except ValueError as error:
        print(f"mfa-vocabularies: {error}", file=sys.stderr)
        return 2
    differences = stale(artifacts, ROOT)
    if args.mode == "generate":
        for path, content in artifacts.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        claimed = set(artifacts)
        for path in OUT.glob("*.xml"):
            if path not in claimed:
                path.unlink()
        differences = []
    if differences:
        print(
            "mfa-vocabularies: generated artifacts differ: "
            + ", ".join(map(str, differences)),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
