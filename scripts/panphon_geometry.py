#!/usr/bin/env python
"""Generate or validate the declared feature table from installed panphon.

panphon's feature system, restated as a declaration ipakit can read. The
point is not to copy a table but to make a second feature system available
on the same footing as ipakit's own, so the two can be compared by handing
one machine two declarations rather than by writing two programs.

Four decisions in the emitted document are load-bearing, and each is a
refusal to tidy the source:

`0` is written verbatim. panphon's third value conflates three states that
are not the same thing -- a feature its geometry never licenses here, a
feature left contrastively underspecified, and a genuinely intermediate
value. Nothing shipped distinguishes them, so nothing here may either.
Splitting the value would invent a distinction the source does not make,
and would leave every later measurement stated against a baseline panphon
does not have.

Keys are NFD. Ninety of panphon's spellings are stored decomposed, and a
lookup keyed on the raw column misses exactly those against panphon's own
segment dictionary.

Weight columns keep the weight file's order, declared apart from the
feature order. The two orders disagree in their tails, and writing the
weights in feature order would silently correct that -- repairing, in
transcription, a defect that is a property of the source and one of the
things a comparison exists to expose.

No `applies` attribute is emitted. ipakit states applicability at the
feature level; panphon states none anywhere. Writing one would assert a
licensing structure the source does not contain, and would make the
declaration a claim about panphon rather than a record of it.

`validate` regenerates the XML and source receipt from the installed library
and compares both byte for byte, so a version bump that moves the table is
caught rather than assumed away. Note that a bare `generate` prints the XML and
only `--write` writes both artifacts.

Usage:
    python scripts/panphon_geometry.py generate
    python scripts/panphon_geometry.py generate --write
    python scripts/panphon_geometry.py validate
    python scripts/panphon_geometry.py describe

``describe`` prints the declared bridge -- both round-trip legs and every
drop -- for the pack the declaration builds. It is the dev-side entry
point to that pack: ``declared_pack()`` returns it. Runtime callers can read
the shipped declaration with ``ipakit.feature_models.read('panphon')``;
only regeneration and live validation require the optional producer package.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import hashlib
import importlib.metadata
import json
import sys
import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING
from xml.sax.saxutils import quoteattr

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ipakit._provenance import SourceMetadata  # noqa: E402
from ipakit._source_receipt import loads_receipt  # noqa: E402
from ipakit.extraction import (  # noqa: E402
    BuildResult,
    SourceContentError,
    SourceIdentity,
    SourceVersionError,
)
from ipakit.feature_models import DATA  # noqa: E402
from ipakit.panphon_source import (  # noqa: E402
    ARTIFACT_NAME,
    NOTICE_FILES,
    RECEIPT_NAME,
    receipt_metadata,
    source_policy,
)

OUTPUT = DATA / "panphon.xml"
RECEIPT = DATA / RECEIPT_NAME

if TYPE_CHECKING:
    from ipakit.bridges.costmodel import CostPack

ROUND_TRIP = (
    "  <round-trip>",
    '    <external-to-house fidelity="lossy-with-report">',
    '      <drop name="10 refused spellings"/>',
    '      <drop name="0-versus-absence mismatch"/>',
    '      <drop name="silent segment deletion"/>',
    "    </external-to-house>",
    '    <house-to-external fidelity="lossy-with-report">',
    '      <drop name="house bundles with no panphon vector"/>',
    '      <drop name="house feature names and non-binary domains"/>',
    '      <drop name="sequential tie U+035C has no row and is silently dropped"/>',
    "    </house-to-external>",
    "  </round-trip>",
)


# The shape of the panphon tables this declaration was generated against.
# Pinned exactly rather than floored, because the output is a generated
# declaration: a table of a different shape produces a different one, and a
# floor would let it regenerate silently against changed input. Contrast
# scripts/interop.py, which asserts only that ipa_all.csv has not collapsed --
# that is a sweep guarding against a vacuous run, not a generator pinning its
# input, so the two strictnesses are deliberate rather than a disagreement.
PANPHON_ROWS = 6367
PANPHON_FEATURES = 24
PANPHON_WEIGHTS = 22


def _sources(source: Path | None = None) -> tuple[Path, Path]:
    if source is not None:
        return source / "ipa_all.csv", source / "feature_weights.csv"
    try:
        import panphon
    except ImportError:
        sys.exit('panphon is required; install with: pip install -e ".[interop]"')
    data = Path(panphon.__file__).resolve().parent / "data"
    return data / "ipa_all.csv", data / "feature_weights.csv"


def _source_identity(source: Path | None = None) -> SourceIdentity:
    bases_path, weights_path = _sources(source)
    version = importlib.metadata.version("panphon")
    accepted = source_policy()["source"]
    if version != accepted["version"]:
        raise SourceVersionError(
            f"Panphon extraction requires version {accepted['version']}; found {version}"
        )
    metadata = SourceMetadata(
        accepted["upstream"],
        accepted["upstream-url"],
        accepted["artifact"],
        accepted["version"],
        accepted["license"],
        accepted["kind"],
    )
    return SourceIdentity(
        metadata,
        {
            "ipa_all.csv": hashlib.sha256(bases_path.read_bytes()).hexdigest(),
            "feature_weights.csv": hashlib.sha256(
                weights_path.read_bytes()
            ).hexdigest(),
        },
    )


def render(source: Path | None = None) -> str:
    """Render installed panphon's data as a deterministic XML declaration."""
    bases_path, weights_path = _sources(source)
    with bases_path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    with weights_path.open(encoding="utf-8", newline="") as stream:
        weights_reader = csv.DictReader(stream)
        weight_row = next(weights_reader)
        weight_names = tuple(weight_row)
    feature_names = tuple(rows[0])[1:]
    if (
        len(rows) != PANPHON_ROWS
        or len(feature_names) != PANPHON_FEATURES
        or len(weight_names) != PANPHON_WEIGHTS
    ):
        raise ValueError(
            "unexpected panphon table shape: "
            f"{len(rows)} rows, {len(feature_names)} features, "
            f"{len(weight_names)} weights"
        )

    lines = [
        "<?xml version='1.0' encoding='utf-8'?>",
        f"<feature-table name={quoteattr('panphon')} "
        f"source-receipt={quoteattr(RECEIPT_NAME)}>",
        "  <!-- Generated by scripts/panphon_geometry.py from installed panphon.",
        "       Do not edit: `validate` regenerates this and compares byte for byte.",
        "",
        "       panphon's feature system stated as a declaration, so it can be read",
        "       on the same footing as any other and the two compared by handing one",
        "       machine two declarations rather than by writing two programs.",
        "",
        "       Four things here are deliberate and are refusals to tidy the source.",
        "       `0` is verbatim: panphon's third value conflates a feature its",
        "       geometry never licenses, one left contrastively underspecified, and",
        "       one genuinely intermediate, and nothing shipped tells them apart, so",
        "       nothing here may either. Segment keys are NFD, because ninety of the",
        "       spellings are stored decomposed and a raw-column key misses exactly",
        "       those. The weight columns keep the weight file's own order, declared",
        "       apart from the feature order, because the two disagree in their tails",
        "       and writing weights in feature order would repair that in",
        "       transcription. And no `applies` attribute is written, because panphon",
        "       states applicability nowhere and asserting one would make this a",
        "       claim about panphon rather than a record of it. -->",
    ]
    lines.extend(ROUND_TRIP)
    lines.append("  <features>")
    lines.extend(f"    <feature name={quoteattr(name)}/>" for name in feature_names)
    lines.extend(["  </features>", "  <weights>"])
    lines.extend(
        f"    <weight name={quoteattr(name)} value={quoteattr(weight_row[name])}/>"
        for name in weight_names
    )
    lines.extend(["  </weights>", "  <segments>"])
    seen: set[str] = set()
    for row in rows:
        name = unicodedata.normalize("NFD", row["ipa"])
        if name in seen:
            raise ValueError(f"duplicate NFD segment key: {name!r}")
        seen.add(name)
        attributes = [f"name={quoteattr(name)}"]
        attributes.extend(f"{key}={quoteattr(row[key])}" for key in feature_names)
        lines.append(f"    <segment {' '.join(attributes)}/>")
    lines.extend(["  </segments>", "</feature-table>"])
    return "\n".join(lines) + "\n"


def build(source: Path | None = None) -> BuildResult:
    """Build the declaration and its receipt as one deterministic transaction."""
    identity = _source_identity(source)
    xml = render(source).encode("utf-8")
    policy = {
        "version": 1,
        "source": identity.metadata.to_dict(),
        "inputs": dict(identity.digests),
    }
    notices = {name: (DATA / name).read_bytes() for name in NOTICE_FILES}
    receipt = receipt_metadata(policy, xml, notices)
    receipt_bytes = (
        json.dumps(
            receipt, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2
        )
        + "\n"
    ).encode("utf-8")
    return BuildResult(
        {
            Path("ipakit/data/feature-models") / ARTIFACT_NAME: xml,
            Path("ipakit/data/feature-models") / RECEIPT_NAME: receipt_bytes,
        },
        source=identity,
    )


def verify_manifest(data_dir: Path = DATA, source: Path | None = None) -> str:
    """Regenerate both Panphon artifacts and refuse a stale field by name."""
    result = build(source)
    xml_key = Path("ipakit/data/feature-models") / ARTIFACT_NAME
    receipt_key = Path("ipakit/data/feature-models") / RECEIPT_NAME
    try:
        actual = loads_receipt((data_dir / RECEIPT_NAME).read_bytes())
        expected = loads_receipt(result.artifacts[receipt_key])
        actual_xml = (data_dir / ARTIFACT_NAME).read_bytes()
        if actual_xml != result.artifacts[xml_key]:
            raise SourceContentError("stale Panphon manifest field: artifacts")
        for field in (
            "schema",
            "kind",
            "domain",
            "source-policy",
            "extractor",
            "artifacts",
            "license",
            "fingerprint",
        ):
            if actual[field] != expected[field]:
                raise SourceContentError(f"stale Panphon manifest field: {field}")
        return str(actual["fingerprint"])
    except SourceContentError:
        raise
    except (KeyError, OSError, TypeError, ValueError) as error:
        raise SourceContentError(f"invalid Panphon source receipt: {error}") from error


def cmd_generate(args: argparse.Namespace) -> int:
    result = build()
    text = result.artifacts[Path("ipakit/data/feature-models") / ARTIFACT_NAME]
    if args.write:
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_bytes(text)
        RECEIPT.write_bytes(
            result.artifacts[Path("ipakit/data/feature-models") / RECEIPT_NAME]
        )
        print(f"Wrote 6,367 segments to {OUTPUT} and {RECEIPT}")
    else:
        sys.stdout.buffer.write(text)
    return 0


def cmd_validate(_: argparse.Namespace) -> int:
    result = build()
    expected = {
        OUTPUT: result.artifacts[Path("ipakit/data/feature-models") / ARTIFACT_NAME],
        RECEIPT: result.artifacts[Path("ipakit/data/feature-models") / RECEIPT_NAME],
    }
    stale = [
        path
        for path, content in expected.items()
        if not path.is_file() or path.read_bytes() != content
    ]
    if not stale:
        print(
            "OK: panphon.xml and panphon-receipt.json match installed panphon "
            "(6,367 segments)."
        )
        return 0
    path = stale[0]
    actual_text = path.read_text(encoding="utf-8") if path.exists() else ""
    expected_text = expected[path].decode("utf-8")
    diff = list(
        difflib.unified_diff(
            actual_text.splitlines(),
            expected_text.splitlines(),
            "declared",
            "generated",
            n=2,
        )
    )
    print(f"DRIFT: {path} differs from installed panphon.")
    print("\n".join(diff[:80]))
    if len(diff) > 80:
        print(f"... {len(diff) - 80} additional diff lines omitted")
    return 1


def declared_pack() -> CostPack:
    """Load the dev declaration and expose its stated boundary losses."""
    sys.path.insert(0, str(ROOT))
    from ipakit.bridges.costmodel import pack_from_declaration

    return pack_from_declaration(OUTPUT)


def cmd_describe(_: argparse.Namespace) -> int:
    """Print the checked declaration's identity and round-trip losses."""
    pack = declared_pack()
    assert pack.bridge is not None
    print(f"{pack.name} ({pack.geometry})")
    for leg in (
        pack.bridge.round_trip.external_to_house,
        pack.bridge.round_trip.house_to_external,
    ):
        print(f"{leg.direction}: {leg.fidelity.value}")
        for loss in leg.drops:
            print(f"  drops: {loss}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate")
    generate.add_argument("--write", action="store_true")
    generate.set_defaults(func=cmd_generate)
    validate = subparsers.add_parser("validate")
    validate.set_defaults(func=cmd_validate)
    describe = subparsers.add_parser(
        "describe", help="show the dev pack and its declared boundary losses"
    )
    describe.set_defaults(func=cmd_describe)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
