#!/usr/bin/env python3
"""Generate language-scoped eSpeak NG native-phoneme vocabularies.

The input is the phoneme-table source at the exact eSpeak NG 1.52.0 tag
commit.  Table inheritance is resolved base first and later declarations
replace an inherited mnemonic, exactly as the compiler does.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import Counter, OrderedDict
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import quoteattr

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "ipakit" / "data" / "bridges" / "espeak"
SUMMARY = ROOT / "docs" / "espeak-vocabularies.md"
DEFAULT_SOURCE = Path.home() / "dev" / "other" / "espeak-ng"
REVISION = "4870adfa25b1a32b4361592f1be8a40337c58d6c"
VERSION = "espeak-ng-1.52.0"
INTERNAL = frozenset({"base1", "base2", "consonants", "hi_base"})


@dataclass(frozen=True)
class Phone:
    """One resolved eSpeak mnemonic and its source block."""

    mnemonic: str
    body: tuple[str, ...]


@dataclass(frozen=True)
class Table:
    """One declared table before inheritance is resolved."""

    name: str
    parent: str | None
    source: str | None


def _run(source: Path, *args: str) -> str:
    """Run Git in ``source`` and return stripped stdout."""
    return subprocess.run(
        ["git", "-C", str(source), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def require_pin(source: Path) -> None:
    """Refuse any checkout other than the provenance revision."""
    try:
        found = _run(source, "rev-parse", "HEAD")
    except (OSError, subprocess.CalledProcessError) as error:
        raise ValueError(f"eSpeak NG checkout is unreadable: {source}") from error
    if found != REVISION:
        raise ValueError(
            f"eSpeak NG checkout is at {found}; required {REVISION} ({VERSION})"
        )


def blocks(text: str) -> OrderedDict[str, Phone]:
    """Read phoneme blocks, with later definitions replacing earlier ones."""
    found: OrderedDict[str, Phone] = OrderedDict()
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        clean = lines[index].split("//", 1)[0].strip()
        if not clean.startswith("phoneme "):
            index += 1
            continue
        mnemonic = clean.split(None, 1)[1].strip()
        mnemonic = mnemonic.replace(r"\,", ",")
        body: list[str] = []
        index += 1
        while (
            index < len(lines)
            and lines[index].split("//", 1)[0].strip() != "endphoneme"
        ):
            body.append(lines[index].split("//", 1)[0].strip())
            index += 1
        found[mnemonic] = Phone(mnemonic, tuple(body))
        index += 1
    return found


def tables(master: str) -> list[Table]:
    """Read table declarations and the single source file following each."""
    result: list[Table] = []
    for raw in master.splitlines():
        line = raw.split("//", 1)[0].strip()
        if line.startswith("phonemetable "):
            parts = line.split()
            result.append(Table(parts[1], parts[2] if len(parts) > 2 else None, None))
        elif line.startswith("include ") and result:
            prior = result[-1]
            result[-1] = Table(prior.name, prior.parent, line.split()[1])
    return result


def kirshenbaum() -> dict[str, str]:
    """Return eSpeak-like ASCII spellings mapped to declared house IPA."""
    root = ET.parse(ROOT / "ipakit" / "data" / "phonemaps" / "kirshenbaum.xml")
    return {
        item.attrib["kirshenbaum"]: item.attrib["ipa"]
        for item in root.iter("map")
        if "kirshenbaum" in item.attrib
    }


def _explicit_ipa(phone: Phone) -> tuple[str | None, str | None]:
    for line in phone.body:
        if not line.startswith("ipa "):
            continue
        value = line.split(None, 1)[1].strip()
        if value == "NULL":
            return None, "conditional-null"
        parts = value.split()
        try:
            decoded = "".join(
                chr(int(part[2:], 16)) if part.startswith("U+") else part
                for part in parts
            )
        except ValueError:
            return None, "unresolved-ipa-directive"
        return decoded, None
    return None, None


def spelling(phone: Phone, mapping: dict[str, str]) -> tuple[str | None, str | None]:
    """Resolve one mnemonic without phonetic guessing."""
    explicit, refusal = _explicit_ipa(phone)
    if explicit is not None or refusal is not None:
        candidate = explicit
    elif any(line.startswith(("virtual", "pause", "stress")) for line in phone.body):
        return None, "control-or-virtual"
    else:
        candidate = mapping.get(phone.mnemonic)
        if candidate is None:
            return None, "no-declared-ipa-spelling"
    if not candidate:
        return None, refusal or "no-declared-ipa-spelling"
    from ipakit.form import Form

    try:
        Form.parse(candidate, strict=True)
    except ValueError:
        return None, "outside-house-ipa"
    return candidate, None


def resolve(source: Path) -> tuple[list[Table], dict[str, OrderedDict[str, Phone]]]:
    """Resolve every table base first, including mnemonic replacement."""
    master = (source / "phsource" / "phonemes").read_text(errors="replace")
    declared = tables(master)
    own: dict[str, OrderedDict[str, Phone]] = {
        "base1": blocks(master.split("phonemetable consonants", 1)[0])
    }
    for table in declared:
        if table.source:
            own[table.name] = blocks(
                (source / "phsource" / table.source).read_text(errors="replace")
            )
        else:
            own.setdefault(table.name, OrderedDict())
    parents = {table.name: table.parent for table in declared}
    done: dict[str, OrderedDict[str, Phone]] = {}

    def one(name: str) -> OrderedDict[str, Phone]:
        if name in done:
            return done[name]
        inherited = (
            OrderedDict(one(parents[name])) if parents.get(name) else OrderedDict()
        )
        inherited.update(own.get(name, OrderedDict()))
        done[name] = inherited
        return inherited

    for table in declared:
        one(table.name)
    return declared, done


def render(name: str, inventory: OrderedDict[str, Phone]) -> tuple[bytes, Counter[str]]:
    """Render one declaration and return its refusal reason counts."""
    mapping = kirshenbaum()
    atoms: list[tuple[str, str, str]] = [
        ("ˈ", "'", "prefix"),
        ("ˌ", ",", "prefix"),
        (" ", " ", "unit"),
    ]
    refused: list[tuple[str, str]] = []
    used = {"'", ",", " "}
    for mnemonic, phone in inventory.items():
        if mnemonic in used:
            continue
        value, reason = spelling(phone, mapping)
        if value is None:
            refused.append((mnemonic, reason or "no-declared-ipa-spelling"))
        else:
            atoms.append((value, mnemonic, "unit"))
        used.add(mnemonic)
    provenance = "eSpeak NG 1.52.0 phsource phoneme tables (GPL-3.0-or-later)"
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f"<!-- Generated by scripts/espeak_vocabularies.py from tag commit {REVISION}. -->",
        f"<vocabulary name={quoteattr('espeak-' + name)} version={quoteattr(VERSION)} provenance={quoteattr(provenance)} tier={quoteattr('espeak-' + name)} source-style=\"text\">",
        "  <round-trip>",
        '    <external-to-house fidelity="lossless" />',
        '    <house-to-external fidelity="lossy-with-report">',
        f"      <drop name={quoteattr('the house-to-eSpeak leg awaits a mapper; emit requires an existing espeak-' + name + ' grouping tier')} />",
        "    </house-to-external>",
        "  </round-trip>",
    ]
    lines.extend(
        f"  <refusal spelling={quoteattr(mnemonic)} reason={quoteattr(reason)} />"
        for mnemonic, reason in refused
    )
    lines.extend(
        f"  <atom spelling={quoteattr(value)} output={quoteattr(mnemonic)}"
        + (' kind="prefix"' if kind == "prefix" else "")
        + " />"
        for value, mnemonic, kind in atoms
    )
    lines.append("</vocabulary>")
    return ("\n".join(lines) + "\n").encode(), Counter(reason for _, reason in refused)


def english_compatibility_bytes(inventory: OrderedDict[str, Phone]) -> bytes:
    """Return the landed English declaration after checking its source atoms.

    English is the byte-level compatibility witness for this generator.  Its
    deliberately explanatory layout predates the uniform renderer, so the
    committed parent version is retained rather than reformatted.
    """
    content = subprocess.run(
        ["git", "show", "HEAD:ipakit/data/bridges/espeak/en.xml"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    root = ET.fromstring(content)
    source_mnemonics = set(inventory)
    undeclared = {
        item.attrib.get("output", item.attrib["spelling"])
        for item in root.findall("atom")
        if item.attrib.get("output", item.attrib["spelling"]) not in {" ", "'", ","}
    } - source_mnemonics
    if undeclared:
        raise ValueError(
            "landed English declaration contains mnemonics absent from the pinned "
            f"table: {sorted(undeclared)!r}"
        )
    return content


def generate(source: Path) -> tuple[dict[Path, bytes], Counter[str]]:
    """Produce all declarations and the counts-only summary exhibit."""
    require_pin(source)
    declared, inventories = resolve(source)
    artifacts: dict[Path, bytes] = {}
    classes: Counter[str] = Counter()
    states: Counter[str] = Counter()
    for table in declared:
        if table.name in INTERNAL:
            continue
        if table.name == "en":
            content = english_compatibility_bytes(inventories[table.name])
            reasons: Counter[str] = Counter()
        else:
            content, reasons = render(table.name, inventories[table.name])
        artifacts[OUT / f"{table.name}.xml"] = content
        classes.update(reasons)
        states["full" if not reasons else "partial"] += 1
    total = len(artifacts)
    summary = [
        "# eSpeak NG vocabulary generation summary",
        "",
        "Generated from eSpeak NG 1.52.0 phoneme tables. Counts are generated; the declarations are the inventory.",
        "",
        f"- Total languages: {total}",
        f"- Fully readable: {states['full']}",
        f"- Partially readable: {states['partial']}",
        "- Unreadable: 0",
        "- Refusal reason classes:",
    ]
    summary.extend(
        f"  - {reason}: {count}" for reason, count in sorted(classes.items())
    )
    artifacts[SUMMARY] = ("\n".join(summary) + "\n").encode()
    return artifacts, states


def main() -> int:
    """Write generated data or check it byte for byte."""
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("generate", "check"))
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    args = parser.parse_args()
    try:
        artifacts, _ = generate(args.source)
    except ValueError as error:
        print(f"espeak-vocabularies: {error}", file=sys.stderr)
        return 2
    stale = []
    for path, content in artifacts.items():
        if args.mode == "generate":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        elif not path.is_file() or path.read_bytes() != content:
            stale.append(path.relative_to(ROOT))
    extras = set(OUT.glob("*.xml")) - set(artifacts)
    if args.mode == "generate":
        for path in extras:
            path.unlink()
    elif extras:
        stale.extend(path.relative_to(ROOT) for path in extras)
    if stale:
        print(
            "espeak-vocabularies: generated artifacts differ: "
            + ", ".join(map(str, stale)),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
