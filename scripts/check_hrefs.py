#!/usr/bin/env python
"""Is every ``href`` in the shipped data still a live article?

The inventory documents itself by pointing at Wikipedia -- 346 ``href``
attributes over some 240 distinct titles -- and those are the only part
of the data whose truth lives somewhere else. A feature value is right or
wrong against the declaration beside it; a link is right or wrong against
a page someone else may rename, merge or delete, and nothing in a test
suite can notice.

They rot silently and in one direction. Four were already dead when this
was written: ``Boundary_(linguistics)``, ``Consonant_release``,
``Pause_(linguistics)`` and ``Utterance_(linguistics)`` had all gone,
while every symbol they documented was still correct. So the failure is
invisible from inside the repository, which is why it wants a check
rather than care.

NOT IN CI, ON PURPOSE. This needs the network and a third party's uptime,
so wiring it into the ordinary gate would make an unrelated change fail
because Wikipedia was slow. It belongs in the release checklist, where a
human is already waiting and a stale link is about to be published.

    python scripts/check_hrefs.py            # exits 1 if any are dead

A redirect counts as live: a page that moved still lands a reader on the
article, and following redirects is what a browser does anyway.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "ipakit" / "data"

#: The API takes fifty titles a call, so the whole inventory is five
#: requests rather than a title at a time -- politeness as much as speed.
BATCH = 50
API = "https://en.wikipedia.org/w/api.php"
AGENT = "ipakit-href-check (https://github.com/lenzo-ka/ipakit)"


def declared() -> dict[str, list[Path]]:
    """Every distinct href in the shipped XML, and which files claim it."""
    found: dict[str, list[Path]] = {}
    for path in sorted(DATA.rglob("*.xml")):
        text = path.read_text(encoding="utf-8")
        for target in re.findall(r'href="([^"]+)"', text):
            found.setdefault(target, []).append(path)
    return found


def missing(titles: list[str]) -> set[str]:
    """The titles Wikipedia does not have, following redirects."""
    absent: set[str] = set()
    for start in range(0, len(titles), BATCH):
        batch = titles[start : start + BATCH]
        query = urllib.parse.urlencode(
            {
                "action": "query",
                "format": "json",
                "redirects": "1",
                "titles": "|".join(batch),
            }
        )
        request = urllib.request.Request(
            f"{API}?{query}", headers={"User-Agent": AGENT}
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            pages = json.load(response)["query"]["pages"]
        absent |= {page["title"] for page in pages.values() if "missing" in page}
    return absent


def main() -> int:
    targets = declared()
    titles = sorted(targets)
    print(f"{sum(len(v) for v in targets.values())} hrefs, {len(titles)} distinct")
    try:
        absent = missing(titles)
    except Exception as error:  # noqa: BLE001 - a failed check is not a pass
        print(f"could not reach Wikipedia: {type(error).__name__}: {error}")
        print("UNCHECKED -- this is not the same as clean; run it again")
        return 2

    if not absent:
        print("every href is a live article")
        return 0

    # Titles come back with spaces where the data writes underscores.
    for title in sorted(absent):
        underscored = title.replace(" ", "_")
        where = targets.get(underscored) or targets.get(title) or []
        files = ", ".join(sorted({p.name for p in where})) or "?"
        print(f"  DEAD: {underscored}  ({files})")
    print(f"{len(absent)} dead href(s); repoint them at what they document")
    return 1


if __name__ == "__main__":
    sys.exit(main())
