#!/usr/bin/env python3
"""Generate language-scoped eSpeak NG native-phoneme vocabularies.

The input is the phoneme-table source at the exact eSpeak NG 1.52.0 tag
commit.  Table inheritance is resolved base first and later declarations
replace an inherited mnemonic, exactly as the compiler does.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
import warnings
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
PHSOURCE_SHA256 = "7f65326cf12433f67611237f47c0e69e06ef6df34a081af5a29533781aef9a96"
INTERNAL = frozenset({"base1", "base2", "consonants", "hi_base"})
CHAO_LETTERS = "˩˨˧˦˥"
CHAO = str.maketrans("12345", CHAO_LETTERS)
TONE_RE = re.compile(
    r"^Tone\s*\(\s*(-?\d+)\s*,\s*(-?\d+)\s*,\s*" r"(?:envelope/)?([^,\s)]+)"
)


@dataclass(frozen=True)
class Phone:
    """One resolved eSpeak mnemonic and its source block."""

    mnemonic: str
    body: tuple[str, ...]
    vowel: bool = False


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
    """Refuse any checkout/archive other than the provenance revision."""
    try:
        found = _run(source, "rev-parse", "HEAD")
    except (OSError, subprocess.CalledProcessError) as error:
        phsource = source / "phsource"
        if not phsource.is_dir():
            raise ValueError(f"eSpeak NG checkout is unreadable: {source}") from error
        digest = hashlib.sha256()
        for path in sorted(item for item in phsource.rglob("*") if item.is_file()):
            digest.update(path.relative_to(phsource).as_posix().encode() + b"\0")
            digest.update(path.read_bytes())
        found = f"phsource-sha256:{digest.hexdigest()}"
        if digest.hexdigest() == PHSOURCE_SHA256:
            return
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
        declaration = clean.split(None, 1)[1].strip()
        parts = declaration.split()
        mnemonic = parts[0]
        mnemonic = mnemonic.replace(r"\,", ",")
        # ``virtual`` may occur on the declaration line (for example
        # ``phoneme #a virtual``), not only as a body instruction.
        body: list[str] = [" ".join(parts[1:])] if len(parts) > 1 else []
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


# eSpeak NG's ``ipa1`` table in src/libespeak-ng/dictionary.c, indexed by
# ASCII 0x20..0x7f.  This is deliberately pinned here rather than borrowing the
# house Kirshenbaum map: eSpeak calls the scheme Kirshenbaum-like, but this
# table (and the filtering in ``default_ipa``) is its actual output contract.
IPA1 = tuple(
    chr(value)
    for value in (
        0x20,
        0x21,
        0x22,
        0x2B0,
        0x24,
        0x25,
        0x0E6,
        0x2C8,
        0x28,
        0x29,
        0x27E,
        0x2B,
        0x2CC,
        0x2D,
        0x2E,
        0x2F,
        0x252,
        0x31,
        0x32,
        0x25C,
        0x34,
        0x35,
        0x36,
        0x37,
        0x275,
        0x39,
        0x2D0,
        0x2B2,
        0x3C,
        0x3D,
        0x3E,
        0x294,
        0x259,
        0x251,
        0x3B2,
        0xE7,
        0xF0,
        0x25B,
        0x46,
        0x262,
        0x127,
        0x26A,
        0x25F,
        0x4B,
        0x26B,
        0x271,
        0x14B,
        0x254,
        0x3A6,
        0x263,
        0x280,
        0x283,
        0x3B8,
        0x28A,
        0x28C,
        0x153,
        0x3C7,
        0xF8,
        0x292,
        0x32A,
        0x5C,
        0x5D,
        0x5E,
        0x5F,
        0x60,
        0x61,
        0x62,
        0x63,
        0x64,
        0x65,
        0x66,
        0x261,
        0x68,
        0x69,
        0x6A,
        0x6B,
        0x6C,
        0x6D,
        0x6E,
        0x6F,
        0x70,
        0x71,
        0x72,
        0x73,
        0x74,
        0x75,
        0x76,
        0x77,
        0x78,
        0x79,
        0x7A,
        0x7B,
        0x7C,
        0x7D,
        0x303,
        0x7F,
    )
)


def default_ipa(phone: Phone) -> str:
    """Apply eSpeak NG 1.52.0 ``WritePhMnemonic(..., use_ipa=1)`` rules."""
    vowel = is_vowel(phone)
    result: list[str] = []
    for index, character in enumerate(phone.mnemonic):
        if character == "/":
            break  # variant indicator and everything after it are not printed
        if index == 0 and character == "_":
            break  # pause mnemonic
        if character == "#" and vowel:
            break  # consonant # is modifier letter h; vowel # is a variant
        if index and character.isascii() and character.isdigit():
            continue
        codepoint = ord(character)
        result.append(IPA1[codepoint - 0x20] if 0x20 <= codepoint < 0x80 else character)
    return "".join(result)


def is_vowel(phone: Phone) -> bool:
    """Return whether the source instructions give this phoneme vowel type."""
    return phone.vowel or any(
        line.split(None, 1)[0] in {"vowel", "vwl"} for line in phone.body if line
    )


def _explicit_ipa(phone: Phone) -> tuple[str | None, str | None]:
    # An import copies the compiled structure at that point; a later local
    # ``ipa`` instruction can replace the copied field.  Resolved bodies are
    # in compiler order, so the final instruction is authoritative.
    unconditional: list[str] = []
    depth = 0
    for line in phone.body:
        if line.startswith(("IF ", "IF(", "SWITCH ")):
            depth += 1
            continue
        if line.startswith(("ENDIF", "ENDSWITCH")):
            depth = max(0, depth - 1)
            continue
        if depth == 0 and line.startswith("ipa "):
            unconditional.append(line)
    for line in reversed(unconditional):
        value = line.split(None, 1)[1].strip()
        if value == "NULL":
            return None, "conditional-null"
        try:
            decoded = re.sub(
                r"U\+([0-9A-Fa-f]{4,6})",
                lambda match: chr(int(match.group(1), 16)),
                value,
            )
        except (ValueError, OverflowError):
            return None, "unresolved-ipa-directive"
        return decoded, None
    return None, None


def tone_directive(phone: Phone) -> tuple[int, int, str] | None:
    """Return the final compiled Tone instruction, if this is tone content."""
    for line in reversed(phone.body):
        match = TONE_RE.match(line)
        if match:
            return int(match.group(1)), int(match.group(2)), match.group(3)
    return None


def tone_spellings(inventory: OrderedDict[str, Phone]) -> dict[str, str]:
    """Derive language-relative Chao contours from compiled Tone envelopes.

    The integers in ``Tone(start, end, envelope)`` are synthesis pitch values,
    not Chao digits.  Chao levels are relative to a speaker/language, so rank
    all endpoints in this phoneme table and spread those ranks over the five
    bands.  Monotone envelopes use their endpoints.  The named dip/peak
    envelopes add the language's bottom/top band: their names encode shape
    which endpoints alone cannot recover (notably 214 and rise-fall).
    """
    directives = {
        mnemonic: directive
        for mnemonic, phone in inventory.items()
        if (directive := tone_directive(phone)) is not None
    }
    pitches = sorted(
        {pitch for start, end, _ in directives.values() for pitch in (start, end)}
    )

    def level(pitch: int) -> str:
        if len(pitches) == 1:
            band = 3
        else:
            band = 1 + round(4 * pitches.index(pitch) / (len(pitches) - 1))
        return CHAO_LETTERS[band - 1]

    result: dict[str, str] = {}
    for mnemonic, (start, end, envelope) in directives.items():
        # Pyash already names its tones with literal Chao letters.  Preserve
        # those source spellings instead of needlessly re-quantizing them.
        if mnemonic and set(mnemonic) <= set(CHAO_LETTERS):
            result[mnemonic] = mnemonic
            continue
        points = [level(start)]
        lowered = envelope.lower()
        if "risefall" in lowered:
            points.append(CHAO_LETTERS[-1])
        elif any(shape in lowered for shape in ("fallrise", "214", "512")):
            points.append(CHAO_LETTERS[0])
        points.append(level(end))
        # Level tones should be one repeated level in conventional Chao
        # transcription; retain both endpoints for all other envelopes.
        if "level" in lowered and points[0] == points[-1]:
            points = [points[0], points[0]]
        result[mnemonic] = "".join(points)
    return result


def spelling(
    phone: Phone, tones: dict[str, str] | None = None
) -> tuple[str | None, str | None]:
    """Resolve one mnemonic using explicit IPA or declared source semantics.

    eSpeak tone mnemonics are labels, not necessarily contour digits.  The
    renderer supplies contours derived language-wide from their Tone fields.

    ``_|`` is the one pause given a house spelling: eSpeak emits that very
    short pause as the word delimiter in ``-x`` text, so the house word
    boundary ``#`` preserves its structural meaning.  Other pauses carry
    duration or clause semantics the house word boundary cannot represent.
    """
    explicit, refusal = _explicit_ipa(phone)
    if explicit is not None or refusal is not None:
        candidate = explicit
    # Tone content is stress-kind in phsource; the Tone directive, rather
    # than the broad source type, distinguishes it from stress controls.
    elif tone_directive(phone) is not None:
        candidate = (tones or {}).get(phone.mnemonic)
    elif phone.mnemonic == "_|" and any(
        line.startswith("pause") for line in phone.body
    ):
        candidate = "#"
    elif any(line.startswith(("pause", "stress")) for line in phone.body):
        return None, "control-or-virtual"
    elif (
        any(line.startswith("virtual") for line in phone.body) and phone.mnemonic != ":"
    ):
        return None, "control-or-virtual"
    else:
        candidate = default_ipa(phone)
    if not candidate:
        return None, refusal or "no-declared-ipa-spelling"
    from ipakit.form import Form

    probe = "a" + candidate if tone_directive(phone) is not None else candidate
    try:
        Form.parse(probe, strict=True)
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

    # ``import_phoneme table/name`` copies the complete compiled phoneme at
    # the position of the instruction.  Inline the imported instruction body
    # there: explicit IPA, Tone data, type, and every other spelling-relevant
    # property then have the same before/after ordering as in the compiler.
    def compiled_body(
        name: str, mnemonic: str, seen: set[tuple[str, str]]
    ) -> tuple[str, ...]:
        key = (name, mnemonic)
        if key in seen:
            return ()
        seen = seen | {key}
        phone = done[name].get(mnemonic)
        if phone is None:
            return ()
        body: list[str] = []
        for line in phone.body:
            if line.startswith("import_phoneme "):
                target = line.split(None, 1)[1].split()[0]
                if "/" in target:
                    table_name, target_mnemonic = target.split("/", 1)
                    if table_name in done:
                        body.extend(compiled_body(table_name, target_mnemonic, seen))
                        continue
            body.append(line)
        return tuple(body)

    for table_name, inventory in done.items():
        for mnemonic, phone in tuple(inventory.items()):
            body = compiled_body(table_name, mnemonic, set())
            inventory[mnemonic] = Phone(phone.mnemonic, body)
    return declared, done


def render(name: str, inventory: OrderedDict[str, Phone]) -> tuple[bytes, Counter[str]]:
    """Render one declaration and return its refusal reason counts."""
    atoms: list[tuple[str, str, str]] = [
        ("ˈ", "'", "prefix"),
        ("ˌ", ",", "prefix"),
        (" ", " ", "unit"),
    ]
    refused: list[tuple[str, str]] = []
    used = {"'", ",", " "}
    tones = tone_spellings(inventory)
    for mnemonic, phone in inventory.items():
        if mnemonic in used:
            continue
        value, reason = spelling(phone, tones)
        if value is None:
            refused.append((mnemonic, reason or "no-declared-ipa-spelling"))
        else:
            kind = "mark" if tone_directive(phone) is not None else "unit"
            atoms.append((value, mnemonic, kind))
        used.add(mnemonic)
    # Some tables emit the fixed ``:`` phoneme after a vowel rather than
    # declaring a colon-suffixed vowel mnemonic.  eSpeak renders that phoneme
    # as IPA length U+02D0.  House vocabulary atoms are units (or prefixes), so
    # declare the compiler's two-phoneme spelling as one longest-match atom.
    if ":" in inventory:
        from ipakit.form import Form

        for mnemonic, phone in inventory.items():
            combined = mnemonic + ":"
            if not is_vowel(phone) or combined in used:
                continue
            value, reason = spelling(phone)
            if value is not None and reason is None:
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter("error")
                        Form.parse(value + "ː", strict=True)
                except (ValueError, UserWarning):
                    continue
                atoms.append((value + "ː", combined, "unit"))
                used.add(combined)
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
        + (f' kind="{kind}"' if kind != "unit" else "")
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
        # Control/virtual and outside-house spellings are explicit, correctly
        # positioned refusals.  The completeness state measures the failure
        # this exhibit audits: a source phoneme lacking any IPA declaration or
        # eSpeak default derivation.
        states["partial" if reasons["no-declared-ipa-spelling"] else "full"] += 1
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
