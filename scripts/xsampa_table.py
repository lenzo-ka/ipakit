#!/usr/bin/env python
"""Generate and validate the IPA <-> X-SAMPA table (data/phonemaps/xsampa.xml).

The table is *derived*, not hand-maintained value-by-value:

    xsampa(symbol) = OVERRIDES[symbol]              if curated, else
                     ICU "IPA-XSampa"(symbol)       if ICU maps it, else
                     <omitted>                      (must be listed in UNMAPPABLE)

over an inventory drawn from ipakit's own phone/diacritic set (plus a few
structural X-SAMPA symbols, minus the redundant spellings X-SAMPA folds).

This keeps the table reproducible and the human judgment calls explicit:
  * OVERRIDES  - symbols ICU can't transliterate (tone bars, suprasegmentals,
                 a few rare phones). Each is a deliberate, documented choice.
  * _extras()  - X-SAMPA structural symbols not in the IPA inventory.
  * EXCLUDE    - redundant IPA spellings kept out, so the one X-SAMPA
                 encoding stays attached to the canonical spelling.
  * UNMAPPABLE - inventory symbols X-SAMPA has no encoding for at all.

An inventory symbol that ICU passes through unchanged and that appears in
neither EXCLUDE nor UNMAPPABLE is an error, not a silent omission: without that
check, a symbol added to ipa.xml drops out of the table -- and so out of every
conversion, mid-string and without a trace -- with nothing to notice it.

Usage:
    python scripts/xsampa_table.py validate          # CI guard: shipped == derived
    python scripts/xsampa_table.py generate          # print derived table to stdout
    python scripts/xsampa_table.py generate --write   # overwrite xsampa.xml

Requires the dev dependency `icukit-pyicu` (bundled ICU + PyICU, `import icu`).
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import quoteattr

# Make the package importable when run from a source checkout.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ipakit.constants import PHONEMAPS_DIR  # noqa: E402
from ipakit.features import IPAFeatures  # noqa: E402

XSAMPA_FILE = PHONEMAPS_DIR / "xsampa.xml"

# IPA symbols ICU's "IPA-XSampa" transliterator does not handle (it passes them
# through unchanged) or maps differently from established X-SAMPA. Curated.
OVERRIDES: dict[str, str] = {
    "␣": "*",  # silence placeholder
    "‿": "-\\",  # linking (absence of a break)
    "ʱ": "_hh",  # breathy-voiced / murmured release
    "ᶣ": "_H_w",  # labial-palatal approximant release
    "ť": "t_>",  # ejective (legacy caron form)
    "ȡ": "d_j\\",  # curly-tail d (alveolo-palatal)
    "ȴ": "l_j\\",  # curly-tail l (alveolo-palatal)
    "ȶ": "t_j\\",  # curly-tail t (alveolo-palatal)
    "ʴ": "`",  # rhoticity
    "˥": "_T",  # extra-high tone bar
    "˦": "_H",  # high tone bar
    "˧": "_M",  # mid tone bar
    "˨": "_L",  # low tone bar
    "˩": "_B",  # extra-low tone bar
    # The contour diacritics, spelled as the run of level bars they name.
    # X-SAMPA has `_R` and `_F` for a rise and a fall with no levels, which
    # is what the caron and the circumflex say; these six say their levels,
    # so they encode as those levels in order. Composed here rather than
    # taken from ICU, whose `_H_T` for `᷄` and `_B_L` for `᷅` sit a step
    # away from the levels the characters' own names give -- a different
    # contour under the model, so a silent wrong answer in conversion.
    "᷄": "_M_H",  # macron-acute: mid then high
    "᷅": "_L_M",  # grave-macron: low then mid
    "᷆": "_M_L",  # macron-grave: mid then low
    "᷇": "_H_M",  # acute-macron: high then mid
    "᷈": "_L_H_L",  # grave-acute-grave: low, high, low
    "᷉": "_H_L_H",  # acute-grave-acute: high, low, high
    "ꜛ": "^",  # upstep
    "ꜜ": "!",  # downstep
    "‖": "||",  # major (intonation) group
    "͜": "_",  # under-tie: X-SAMPA has one tie encoding
}


# X-SAMPA structural symbols that are not phones/diacritics in the inventory.
# Both tie glyphs encode as `_` (X-SAMPA has one tie notion); the reverse
# reading of `_` is the over-tie, and callers canonicalize via from_wild.
# The ties are asked of the inventory, which declares them.
def _extras(ipa: IPAFeatures) -> set[str]:
    return {"#", ".", *ipa.tie_bars}


# Redundant IPA spellings deliberately kept out of the table. X-SAMPA has one
# encoding where IPA has two, and this table is bijective, so only the house-
# canonical spelling can carry the encoding -- listing both would make the
# reverse reading ambiguous and depend on file order. Each is mapped to the
# spelling that does carry it.
EXCLUDE: dict[str, str] = {
    "˞": "ʴ",  # rhotic hook -> modifier hook (`)
    "̀": "˨",  # combining grave -> low tone bar (_L)
    "́": "˦",  # combining acute -> high tone bar (_H)
    "̄": "˧",  # combining macron -> mid tone bar (_M)
    "ʻ": "ʰ",  # turned comma -> modifier h (_h); both are `release=aspirated`
}

# Inventory symbols X-SAMPA has no encoding for. Listing a symbol here is not a
# mapping and not an excuse: it records that the gap was looked up and is real,
# so the generator can treat every *other* ICU passthrough as a bug. Conversion
# drops these (or raises, with `strict=True`); README documents them.
UNMAPPABLE: dict[str, str] = {
    # Prominence belongs to the IPA spelling profile. X-SAMPA is a separate
    # encoding and is never mixed with that prefix notation.
    "^": "unit prominence: house IPA notation is outside X-SAMPA",
    # X-SAMPA (1995) predates the IPA's 2005 adoption of the labiodental flap.
    # Wells' chart marks the cell as having no symbol and none has been agreed
    # since; `4_d` or `v\_r` would be invention, and would collide with the
    # dental tap and the raised labiodental approximant respectively.
    "ⱱ": "labiodental flap: no X-SAMPA symbol exists",
    # X-SAMPA's secondary-articulation diacritics are a closed list
    # (_h _w ' _G _?\ ...) with no glottal or schwa member.
    "ˀ": "glottalization: no X-SAMPA diacritic",
    "ᵊ": "schwa release: no X-SAMPA diacritic",
}


def _icu_forward():  # type: ignore[no-untyped-def]
    """Return the ICU IPA->X-SAMPA transliterator, or exit with guidance."""
    try:
        import icu
    except ImportError:
        sys.exit(
            "icukit-pyicu is required (dev dependency). Install with:\n"
            '    pip install -e ".[dev]"'
        )
    return icu.Transliterator.createInstance("IPA-XSampa")


def canonical_pairs() -> dict[str, str]:
    """Compute the derived IPA -> X-SAMPA table."""
    fwd = _icu_forward()
    ipa = IPAFeatures()
    inventory = (
        {
            s
            for s in (set(ipa.phones) | set(ipa.diacritics))
            if not ipa.tie_bars & set(s)
        }
        | _extras(ipa)
    ) - EXCLUDE.keys()

    table: dict[str, str] = {}
    for sym in sorted(inventory):
        if sym in UNMAPPABLE:
            continue
        if sym in OVERRIDES:
            table[sym] = OVERRIDES[sym]
            continue
        x = fwd.transliterate(sym)
        if x == sym and not sym.isascii():
            if sym not in UNMAPPABLE:
                raise ValueError(
                    f"ICU has no X-SAMPA for {sym!r} (U+{ord(sym[0]):04X}) and it "
                    "is listed in neither EXCLUDE nor UNMAPPABLE. Omitting it "
                    "would delete it from every conversion silently: add an "
                    "OVERRIDES entry if X-SAMPA can spell it, an EXCLUDE entry "
                    "if it is a redundant spelling of one that can, or an "
                    "UNMAPPABLE entry if X-SAMPA genuinely cannot."
                )
            continue
        table[sym] = x
    return table


def shipped_pairs() -> dict[str, str]:
    """Load the IPA -> X-SAMPA pairs currently shipped in xsampa.xml."""
    root = ET.parse(XSAMPA_FILE).getroot()
    pairs: dict[str, str] = {}
    for m in root.findall("map"):
        ip, xs = m.get("ipa"), m.get("xsampa")
        if ip is not None and xs is not None:
            pairs[ip] = xs
    return pairs


def render(table: dict[str, str]) -> str:
    """Render a table as a phonemap XML document (sorted by IPA codepoint)."""
    lines = [
        "<?xml version='1.0' encoding='utf-8'?>",
        '<phonemap description="IPA to X-SAMPA" from="ipa" to="xsampa">',
        "    <!-- Generated by scripts/xsampa_table.py (ICU + curated overrides). -->",
    ]
    for ip in sorted(table):
        lines.append(f"    <map ipa={quoteattr(ip)} xsampa={quoteattr(table[ip])}/>")
    lines.append("</phonemap>")
    return "\n".join(lines) + "\n"


def cmd_validate(_: argparse.Namespace) -> int:
    derived = canonical_pairs()
    shipped = shipped_pairs()

    missing = {k: derived[k] for k in derived.keys() - shipped.keys()}
    extra = {k: shipped[k] for k in shipped.keys() - derived.keys()}
    mismatch = {
        k: (shipped[k], derived[k])
        for k in derived.keys() & shipped.keys()
        if shipped[k] != derived[k]
    }

    if not (missing or extra or mismatch):
        print(f"OK: shipped xsampa.xml matches derived table ({len(shipped)} entries).")
        return 0

    print("DRIFT between shipped xsampa.xml and the derived (ICU + overrides) table:")
    for k, v in sorted(missing.items()):
        print(f"  missing (derived has, shipped lacks): {k!r} -> {v!r}")
    for k, v in sorted(extra.items()):
        print(f"  extra (shipped has, derived lacks):    {k!r} -> {v!r}")
    for k, (s, d) in sorted(mismatch.items()):
        print(f"  mismatch {k!r}: shipped={s!r}  derived={d!r}")
    return 1


def cmd_generate(args: argparse.Namespace) -> int:
    table = canonical_pairs()
    text = render(table)
    if args.write:
        XSAMPA_FILE.write_text(text, encoding="utf-8")
        print(f"Wrote {len(table)} entries to {XSAMPA_FILE}")
    else:
        sys.stdout.write(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_val = sub.add_parser("validate", help="check shipped table matches derived")
    p_val.set_defaults(func=cmd_validate)

    p_gen = sub.add_parser("generate", help="emit the derived table")
    p_gen.add_argument(
        "--write",
        action="store_true",
        help="overwrite data/phonemaps/xsampa.xml (loses hand grouping/comments)",
    )
    p_gen.set_defaults(func=cmd_generate)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
