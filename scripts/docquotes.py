#!/usr/bin/env python
"""Check the sentences one document quotes out of another.

``scripts/docexamples.py`` checks quoted *values* against the library.
This checks quoted *prose* against the document it is attributed to: when
a page writes a sentence in quotation marks and names the sibling it took
that sentence from, the sentence has to still be there.

The documents under ``docs/design/`` argue against each other and quote
each other heavily, and nothing was holding those quotations true. Four
went stale in a single week -- the sibling was reworded and the quoting
page kept the old words, which reads as a citation and is not one.
``docs/reviewing.md`` names documentation drifting away from behavior as
a recurring failure here; a quotation drifting away from its source is
the same failure between two documents.

A quotation is bound to the **nearest document named before it in its own
sentence**, either as a markdown link or written out as
``docs/rules.md``. A sentence is as far back as an attribution reaches:
a link two sentences up is what those sentences were about, not the
source of this quote. Anything else -- a sentence that names no document,
or names a URL, a book, or a file that is not a repo-relative ``.md`` --
is left alone, because a quotation from *SPE* or from a docstring is not
one this can reach. It reports how many it left alone. What it does not
check, it does not claim to have checked.

Comparison is on the words. Quote characters, emphasis, code spans and
runs of whitespace normalize away, ``...`` elides whatever the citation
skipped, the first character may change case, and a closing period may
be the citation's rather than the source's. All of that is copy-editing
a citation is allowed. Nothing else is folded: a different word is a
finding.

Both counts are printed and asserted against floors, so this cannot go
quietly vacuous -- a reader that finds no quotations, or finds them and
attributes none, passes every document by not looking.

    python scripts/docquotes.py             # the whole tree
    python scripts/docquotes.py some/dir    # any tree of .md files

Exit status is 1 if a quotation is not in the document it cites.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: ``[text](target)``, with the optional title markdown allows.
LINK = re.compile(r"\[[^\]]*\]\(\s*([^)\s]+)(?:\s+\"[^\"]*\")?\s*\)")

#: Any run between a pair of double quotes. The ``*"..."*`` form the
#: design documents favor is this with emphasis around it, so one pattern
#: reads both.
QUOTE = re.compile(r"\"([^\"]+)\"")

#: A fence, whatever it is fencing. Code is not prose.
FENCE = re.compile(r"^\s*(```|~~~)")

#: What starts a paragraph even without a blank line before it. These
#: documents are written one line per paragraph *or bullet*, and a list
#: runs without blank lines, so a link in one item must not claim a
#: quotation in the next one.
BREAK = re.compile(r"^\s*(#{1,6}\s|[-*+]\s|\d+[.)]\s|>|\|)")

#: The end of a sentence, which is as far back as an attribution
#: reaches. Never inside a quotation -- the spans are subtracted first.
SENTENCE = re.compile(r"[.?!]\s")

#: A document named in prose rather than linked -- ``docs/rules.md``
#: inside a code span, most often. It attributes a sentence exactly as a
#: link does, and half the citations here are written that way.
MENTION = re.compile(r"(?<![\w/.-])((?:[\w.-]+/)*[\w.-]+\.md)\b")

#: Below this, a pair of quotes is scare quotes or a mention of a word --
#: `"non-overlapping"` -- rather than a sentence taken from somewhere.
MIN_WORDS = 4

#: Floors, not totals, for the same reason ``docexamples.py`` uses one:
#: both move whenever a document gains a citation, and only a collapse of
#: the sweep itself should fail them. They are two because there are two
#: ways for this to go vacuous -- the reader stops finding quotations at
#: all, or it finds them and stops attributing any of them.
FLOOR = 100
CITED_FLOOR = 4

_QUOTE_CHARS = str.maketrans(
    {
        "'": '"',
        "‘": '"',
        "’": '"',
        "“": '"',
        "”": '"',
        "′": '"',
    }
)


def normalize(text: str) -> str:
    """The words, with typography that a citation may restyle removed."""
    text = unicodedata.normalize("NFC", text)
    text = text.translate(_QUOTE_CHARS)
    text = text.replace("…", "...")
    for mark in ("*", "`"):
        text = text.replace(mark, "")
    return " ".join(text.split())


def found(needle: str, haystack: str) -> bool:
    """Whether the quoted words are in the document, ``...`` eliding."""
    if "..." in needle:
        parts = [part for part in (p.strip() for p in needle.split("...")) if part]
        if not parts:
            return False
        return re.search(".*".join(re.escape(p) for p in parts), haystack) is not None
    return needle in haystack


def variants(needle: str) -> list[str]:
    """The needle, and the copy-editing a citation is allowed.

    A sentence lifted out of the middle of another sentence gets its
    capital lowered, and one lifted to open a sentence gets it raised.
    A quotation cut at a clause boundary closes with a period where the
    source ran on with a comma or a colon. Both are ordinary practice.

    It is the *first* character and the *last* period only. Folding case
    throughout, or punctuation throughout, would let a real misquotation
    through, and a misquotation is what this exists to find.
    """
    out = [needle]
    if needle.endswith("."):
        out.append(needle[:-1])
    if needle and needle[0].isalpha():
        out += [needle[0].swapcase() + rest[1:] for rest in list(out)]
    return out


def appears(needle: str, haystack: str) -> bool:
    return any(found(one, haystack) for one in variants(needle))


def mask_code(line: str) -> str:
    """Blank out inline code spans, keeping the line's length.

    A ``"`` inside backticks is a character in an example, not the edge
    of a quotation, and it would pair with the next real one.
    """
    out = list(line)
    index = 0
    while index < len(out):
        if out[index] == "`":
            run = 1
            while index + run < len(out) and out[index + run] == "`":
                run += 1
            close = line.find("`" * run, index + run)
            if close == -1:
                index += run
                continue
            for spot in range(index + run, close):
                if out[spot] not in " \t":
                    out[spot] = "."
            index = close + run
            continue
        index += 1
    return "".join(out)


def paragraphs(text: str) -> list[tuple[str, str, list[int]]]:
    """The prose paragraphs, each as written, as masked, and by line.

    The three are the same length, so a match found in the masked text
    slices the text as written and names the line it came from.

    Documents here are written one line per paragraph or bullet, but not
    all of them -- ``README.md`` and ``docs/releasing.md`` are hard
    wrapped, and a quotation there spans lines. Blank lines and list
    items separate; fenced blocks are dropped whole.
    """
    blocks: list[tuple[str, str, list[int]]] = []
    raw = masked = ""
    lines: list[int] = []
    fence = ""

    def flush() -> None:
        nonlocal raw, masked, lines
        if raw:
            blocks.append((raw, masked, lines))
        raw, masked, lines = "", "", []

    for number, line in enumerate(text.split("\n"), start=1):
        mark = FENCE.match(line)
        if fence:
            if mark and line.strip().startswith(fence):
                fence = ""
            continue
        if mark:
            flush()
            fence = mark.group(1)
            continue
        if not line.strip() or BREAK.match(line):
            flush()
            if not line.strip():
                continue
        if raw:
            raw += " "
            masked += " "
            lines.append(number)
        raw += line
        masked += mask_code(line)
        lines.extend([number] * len(line))
    flush()
    return blocks


def target_of(link: str, path: Path, root: Path) -> Path | None:
    """The repo-relative ``.md`` a link points at, if it is one.

    A URL, an anchor into the page itself, an image, a ``.py`` -- none of
    those are documents this can read a sentence out of, so a quotation
    attributed to one is not checked.
    """
    if "://" in link or link.startswith(("#", "mailto:")):
        return None
    link = link.split("#", 1)[0]
    if not link.endswith(".md"):
        return None
    try:
        resolved = (path.parent / link).resolve()
        resolved.relative_to(root)
    except (OSError, ValueError):
        return None
    return resolved if resolved.is_file() else None


def documents(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*.md")
        if not any(part.startswith(".") for part in path.relative_to(root).parts)
    )


def named_of(name: str, path: Path, root: Path, tree: list[Path]) -> Path | None:
    """The document a bare ``something.md`` in prose refers to.

    Relative to the page, then to the root, then by name if exactly one
    document in the tree carries it. Two documents sharing a name --
    ``README.md`` does -- makes the reference ambiguous, and an ambiguous
    attribution is not one this should guess at. The tree is walked; no
    document is named here, because a list of them in this file would be
    the second copy of the tree that ``docs/reviewing.md`` warns about.
    """
    for candidate in (path.parent / name, root / name):
        try:
            resolved = candidate.resolve()
            resolved.relative_to(root)
        except (OSError, ValueError):
            continue
        if resolved.is_file():
            return resolved
    same = [other for other in tree if other.name == name.rsplit("/", 1)[-1]]
    return same[0] if len(same) == 1 else None


def citations(
    path: Path, root: Path, tree: list[Path]
) -> tuple[list[tuple[int, str, Path]], int]:
    """Every quotation in ``path`` naming a sibling, and how many do not.

    The second number is the escape this cannot cover: a quotation from
    a book, a handout, a docstring or nothing at all. It is reported
    rather than dropped, so the reach of the check stays known.
    """
    text = path.read_text(encoding="utf-8")
    out: list[tuple[int, str, Path]] = []
    elsewhere = 0
    for raw, masked, lines in paragraphs(text):
        links = list(LINK.finditer(masked))
        anchors = [
            (match.end(), target_of(match.group(1), path, root)) for match in links
        ]
        # A name written out rather than linked is read off the page as
        # written, because a document is usually named inside a code span
        # and ``masked`` has that blanked out. A name inside a link is
        # already an anchor.
        inside = [(match.start(), match.end()) for match in links]
        anchors += [
            (match.end(), named_of(match.group(1), path, root, tree))
            for match in MENTION.finditer(raw)
            if not any(lo <= match.start() < hi for lo, hi in inside)
        ]
        anchors.sort()
        quotes = list(QUOTE.finditer(masked))
        spans = [(match.start(), match.end()) for match in quotes]
        stops = [
            match.start()
            for match in SENTENCE.finditer(masked)
            if not any(lo <= match.start() < hi for lo, hi in spans)
        ]
        for match in quotes:
            quote = raw[match.start(1) : match.end(1)]
            if len(quote.split()) < MIN_WORDS:
                continue
            # An attribution reaches back to the start of its own
            # sentence and no further: a link two sentences up is the
            # subject of those sentences, not the source of this quote.
            opens = max((stop for stop in stops if stop < match.start()), default=-1)
            before = [target for end, target in anchors if opens < end <= match.start()]
            if not before or before[-1] is None:
                elsewhere += 1
                continue
            number = lines[match.start()] if match.start() < len(lines) else 0
            out.append((number, quote, before[-1]))
    return out, elsewhere


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "root",
        nargs="?",
        type=Path,
        default=ROOT,
        help="the tree to read; every .md under it is both a source and a target",
    )
    parser.add_argument(
        "--floor",
        type=int,
        default=FLOOR,
        help="the fewest quotations the tree must contain at all",
    )
    parser.add_argument(
        "--cited-floor",
        type=int,
        default=CITED_FLOOR,
        help="the fewest of those that must be attributed to a document here",
    )
    args = parser.parse_args(argv)
    root = args.root.resolve()

    tree = documents(root)
    sources: dict[Path, str] = {}
    total = failures = elsewhere = 0
    for path in tree:
        report = []
        checked = 0
        cited, external = citations(path, root, tree)
        elsewhere += external
        for number, quote, target in cited:
            if target not in sources:
                sources[target] = normalize(
                    target.read_text(encoding="utf-8"),
                )
            checked += 1
            if not appears(normalize(quote), sources[target]):
                report.append((number, quote, target.relative_to(root)))
        total += checked
        failures += len(report)
        if checked:
            mark = "ok  " if not report else "FAIL"
            name = path.relative_to(root)
            print(
                f"  [{mark}] {name}: {checked} quotations checked, "
                f"{len(report)} not in the document cited"
            )
        for number, quote, target in report:
            print(f"         line {number}, cited to {target}")
            print(f"           quoted: {' '.join(quote.split())[:96]}")

    print(f"\n{total} quotations checked against the document each one cites")
    print(
        f"{elsewhere} attributed to something this cannot read -- a book, a "
        "handout, a URL, or nothing -- and left alone"
    )
    if total + elsewhere < args.floor:
        print(
            f"only {total + elsewhere} quotations read, below the floor of "
            f"{args.floor}: this reader stopped finding the quotations in the "
            "documents, so it is passing them by not looking",
            file=sys.stderr,
        )
        return 1
    if total < args.cited_floor:
        print(
            f"only {total} quotations attributed to a document here, below the "
            f"floor of {args.cited_floor}: the quotations are being read and "
            "none of them is being bound to a source, so nothing is compared",
            file=sys.stderr,
        )
        return 1
    if failures:
        print(
            f"\n{failures} quotation(s) are not in the document they cite. Either "
            "the cited document was reworded and the quotation is now a "
            "paraphrase wearing quotation marks, or it was never the wording "
            "there. Quote what the document says, or drop the quotation marks.",
            file=sys.stderr,
        )
        return 1
    print("every quotation is in the document it cites")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
