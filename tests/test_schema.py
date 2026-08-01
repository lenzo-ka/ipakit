"""The shipped XML against the grammars that state its shape.

Every number ipakit computes comes out of a file in ``ipakit/data``, and
until now nothing said what those files have to look like. A misplaced
attribute or a section under the wrong parent is read by
``xml.etree.ElementTree`` without complaint and comes back as a missing
feature, a phone with no place, a head that draws slightly wrong -- a
silent wrong answer of the shape ``docs/reviewing.md`` is about. The
grammars beside the data say what well-formed means; this module is what
makes the saying bite.

Four claims, in order of how much they are worth:

1. Every shipped XML validates against its grammar.
2. Every XML file under ``ipakit/data`` is claimed by exactly one grammar,
   so a *new* data file arriving without one fails here rather than
   shipping unstated.
3. No grammar names any of the inventory. ipa.xml is the one place a
   feature, a value or a symbol is declared, and a schema listing them
   would be a second copy that drifts.
4. Each grammar rejects the things it is supposed to reject. A schema
   nobody has seen fail is not known to work.
"""

from __future__ import annotations

import shutil
import subprocess
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "ipakit" / "data"
IPA_XML = DATA / "ipa.xml"

RNG = "{http://relaxng.org/ns/structure/1.0}"

# The char classes ipa.xml declares, and the element each section holds.
# These are the symbol elements: what they say beyond `name` is a feature
# bundle, so their attribute names are the feature inventory and a grammar
# must not enumerate them. Test 3 is scoped to exactly these.
SYMBOL_ELEMENTS = frozenset(
    {"phone", "diacritic", "suprasegmental", "separator", "zero"}
)


# --------------------------------------------------------------------------
# Validator plumbing
# --------------------------------------------------------------------------

try:  # lxml is in the `test` extra; libxml2's validator is the same engine
    from lxml import etree as _lxml  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - exercised only where lxml is absent
    _lxml = None

_XMLLINT = shutil.which("xmllint")

# Not a skip. A schema check that quietly disappears when the validator is
# missing leaves a green suite claiming something nobody checked, which is
# worse than having no schema at all -- so the tests that need a validator
# fail, and say this.
_NO_VALIDATOR = (
    "no RELAX NG validator: neither lxml (the `test` extra installs it) nor "
    "xmllint is available, so the shipped XML went unvalidated"
)


def _validate(grammar: Path, document: bytes, tmp_path: Path) -> str | None:
    """Validate ``document`` against ``grammar``; return the diagnosis or None."""
    if _lxml is not None:
        schema = _lxml.RelaxNG(_lxml.parse(str(grammar)))
        if schema.validate(_lxml.fromstring(document)):
            return None
        return str(schema.error_log)
    if _XMLLINT is not None:
        scratch = tmp_path / "document.xml"
        scratch.write_bytes(document)
        proc = subprocess.run(
            [_XMLLINT, "--noout", "--relaxng", str(grammar), str(scratch)],
            capture_output=True,
            text=True,
        )
        return None if proc.returncode == 0 else proc.stderr
    pytest.fail(_NO_VALIDATOR)


@pytest.fixture
def validate(tmp_path: Path) -> Callable[[Path, bytes], str | None]:
    if _lxml is None and _XMLLINT is None:
        pytest.fail(_NO_VALIDATOR)

    def run(grammar: Path, document: bytes) -> str | None:
        return _validate(grammar, document, tmp_path)

    return run


# --------------------------------------------------------------------------
# Which grammar claims which document
# --------------------------------------------------------------------------


def _grammars_for(document: Path) -> list[Path]:
    """The grammars in ``document``'s own directory that claim it.

    Co-location is the whole convention: a grammar sits beside the data it
    describes, so a copied ipa.xml carries its grammar with it. Within a
    directory, a grammar named for a document claims that document
    (``ipa.rng`` claims ``ipa.xml``); a grammar named for no document is
    the shape of the rest (``phonemap.rng`` claims every phonemap). The two
    rules cannot both fire, which is what makes "exactly one" checkable.
    """
    siblings = sorted(document.parent.glob("*.rng"))
    named = [g for g in siblings if g.stem == document.stem]
    if named:
        return named
    return [g for g in siblings if not (g.parent / f"{g.stem}.xml").exists()]


def _shipped_xml() -> list[Path]:
    return sorted(DATA.rglob("*.xml"))


def _shipped_grammars() -> list[Path]:
    return sorted(DATA.rglob("*.rng"))


def _pairs() -> Iterator[tuple[Path, Path]]:
    for document in _shipped_xml():
        for grammar in _grammars_for(document):
            yield grammar, document


def _ident(pair: tuple[Path, Path]) -> str:
    grammar, document = pair
    return f"{document.relative_to(DATA)}-{grammar.name}"


# --------------------------------------------------------------------------
# 1. The shipped documents validate
# --------------------------------------------------------------------------


@pytest.mark.parametrize("pair", sorted(_pairs()), ids=_ident)
def test_shipped_xml_validates(
    pair: tuple[Path, Path], validate: Callable[[Path, bytes], str | None]
) -> None:
    grammar, document = pair
    errors = validate(grammar, document.read_bytes())
    assert errors is None, f"{document.relative_to(ROOT)} does not validate:\n{errors}"


def test_every_grammar_is_well_formed_relax_ng(
    validate: Callable[[Path, bytes], str | None],
) -> None:
    """A grammar that does not load validates nothing and says so nowhere."""
    grammars = _shipped_grammars()
    assert grammars, "no .rng files found beside the data"
    for grammar in grammars:
        if _lxml is not None:
            _lxml.RelaxNG(_lxml.parse(str(grammar)))
        else:  # pragma: no cover - the xmllint fallback
            assert _XMLLINT is not None
            proc = subprocess.run(
                [_XMLLINT, "--noout", "--relaxng", str(grammar), str(grammar)],
                capture_output=True,
                text=True,
            )
            assert "failed to compile" not in proc.stderr, proc.stderr


# --------------------------------------------------------------------------
# 2. Coverage
# --------------------------------------------------------------------------


def test_every_shipped_xml_is_claimed_by_exactly_one_grammar() -> None:
    """A data file no grammar covers fails here rather than shipping unstated.

    If you have just added an XML document under ``ipakit/data`` and landed
    on this failure: write a grammar for it and put the grammar beside it.
    Name it after the document (``widgets.xml`` takes ``widgets.rng``), or,
    if the document is one of a family that share a shape, name the grammar
    after the shape and after no document in that directory -- which is how
    ``phonemaps/phonemap.rng`` claims every phonemap at once.

    The point is not ceremony. Nothing else in the suite notices when a
    document's shape changes underneath it: ElementTree reads a section
    under the wrong parent without complaint, and what comes back is a
    missing feature rather than an error.
    """
    documents = _shipped_xml()
    # Non-vacuity: a collapse in the walk must fail here, not pass quietly.
    assert len(documents) > 4, f"walk found only {len(documents)} XML files"

    unclaimed = [
        str(d.relative_to(DATA)) for d in documents if len(_grammars_for(d)) == 0
    ]
    assert not unclaimed, (
        f"these XML documents under ipakit/data have no grammar beside them, "
        f"so nothing states what they are allowed to look like: {unclaimed}"
    )

    contested = {
        str(d.relative_to(DATA)): [g.name for g in _grammars_for(d)]
        for d in documents
        if len(_grammars_for(d)) > 1
    }
    assert not contested, (
        f"these XML documents are claimed by more than one grammar, so which "
        f"one states their shape is a matter of opinion: {contested}"
    )


def test_no_grammar_claims_nothing() -> None:
    """A grammar matching no document is a stale declaration, not protection."""
    claimed = {g for d in _shipped_xml() for g in _grammars_for(d)}
    dead = [str(g.relative_to(DATA)) for g in _shipped_grammars() if g not in claimed]
    assert not dead, (
        f"these grammars claim no document under ipakit/data: {dead}. Either "
        f"the data moved and the grammar was left behind, or the grammar is "
        f"named after a document that does not exist."
    )


# --------------------------------------------------------------------------
# 3. No smuggling
# --------------------------------------------------------------------------


def _inventory() -> set[str]:
    """Every name the live ipa.xml declares, that a grammar must not know.

    Features, their values, the symbols in every char class, and the named
    vocabularies -- types, modes, notations, bridges -- that a declaration
    can point at. All of it is data, all of it moves when the inventory
    moves, and none of it may appear in a schema.

    The one exclusion is the value alphabet ``<types>`` declares: ``+``,
    ``-`` and ``0``. Those are how this document spells a sign, not what it
    has an inventory of, and a flag attribute whose only legal content is
    ``+`` is stating structure. The exclusion is narrow on purpose: it takes
    out that sign alphabet and leaves every other declared name in.
    """
    root = ET.parse(IPA_XML).getroot()
    names = {
        element.get("name", "")
        for path in (
            "features/feature",
            "features/feature/value",
            "types/type",
            "modes/mode",
            "notations/notation",
            "bridges/bridge",
        )
        for element in root.findall(path)
    }
    for section in root.findall("classes/class"):
        plural = section.get("name", "")
        names |= {
            symbol.get("name", "")
            for symbol in root.findall(f"{plural}/{plural.rstrip('s')}")
        }
    sigils = {v.get("name", "") for v in root.findall("types/type/value")}
    return {n for n in names if n} - sigils


def _expand(node: ET.Element, defines: dict[str, ET.Element]) -> Iterator[ET.Element]:
    """Walk a RELAX NG pattern, following every ``<ref>`` into its define."""
    seen: set[str] = set()

    def walk(current: ET.Element) -> Iterator[ET.Element]:
        yield current
        for child in current:
            if child.tag == f"{RNG}ref":
                name = child.get("name", "")
                if name in defines and name not in seen:
                    seen.add(name)
                    yield from walk(defines[name])
            else:
                yield from walk(child)

    yield from walk(node)


def test_no_grammar_names_the_inventory() -> None:
    """A symbol element's attribute names are the feature inventory.

    ``<phone place="velar">`` says this sound is velar, and ``place`` is a
    feature declared in ``<features>`` above it. A grammar that wrote
    ``<attribute name="place">`` there would be a second copy of the
    feature list, agreeing with the first only until someone adds a
    feature. The grammars admit those attributes by shape instead --
    anything except ``name``, ``alias`` and ``href`` -- and this is what
    holds them to it.

    Naming ``place`` on a *declaration* element is a different thing and is
    allowed: ``<feature name="velarized" place="velar">`` says where the
    constriction that feature names is made, which is metadata about the
    declaration rather than a feature of a symbol. That is why the check is
    scoped to the symbol elements and not to every attribute in the file.
    """
    inventory = _inventory()
    assert len(inventory) > 100, f"only {len(inventory)} declared names found"

    checked = 0
    for grammar in _shipped_grammars():
        root = ET.parse(grammar).getroot()
        defines = {
            d.get("name", ""): d for d in root.iter(f"{RNG}define") if d.get("name")
        }
        for element in root.iter(f"{RNG}element"):
            if element.get("name") not in SYMBOL_ELEMENTS:
                continue
            checked += 1
            named = {
                attribute.get("name", "")
                for node in _expand(element, defines)
                if node.tag == f"{RNG}attribute"
                for attribute in (node,)
                if node.get("name")
            }
            assert (
                named
            ), f"{grammar.name} names no attribute on <{element.get('name')}>"
            smuggled = sorted(named & inventory)
            assert not smuggled, (
                f"{grammar.name} names {smuggled} as attributes of "
                f"<{element.get('name')}>, but those are declared in ipa.xml. "
                f"A symbol's attributes are its feature bundle: admit them by "
                f"shape, or the grammar becomes a second inventory that drifts."
            )

    assert checked == len(SYMBOL_ELEMENTS), (
        f"expected a definition for each of {sorted(SYMBOL_ELEMENTS)}, found "
        f"{checked}; the check is scoped to symbol elements and found the wrong "
        f"number of them, so it is not checking what it claims"
    )


def test_no_grammar_enumerates_a_declared_value() -> None:
    """``<value>`` in a grammar is an enumeration, and enumerations drift.

    Anywhere a grammar spells out a legal string it has taken a copy of
    something ipa.xml declares. The flags are the exception the docstring on
    :func:`_inventory` describes, and they are excluded there rather than
    here so that the exception is stated once.
    """
    inventory = _inventory()
    for grammar in _shipped_grammars():
        root = ET.parse(grammar).getroot()
        enumerated = {(node.text or "").strip() for node in root.iter(f"{RNG}value")}
        smuggled = sorted(enumerated & inventory)
        assert not smuggled, (
            f"{grammar.name} enumerates {smuggled}, which ipa.xml declares. "
            f"The grammar describes structure; the vocabulary lives in the data."
        )


# --------------------------------------------------------------------------
# 4. Negative tests
# --------------------------------------------------------------------------
#
# Each mutation takes the real document, breaks one thing, and asserts the
# grammar notices. The round trip through ElementTree is asserted valid
# first, so a mutation that fails because of how it was serialized cannot
# pass for a mutation the grammar caught.


def _first(root: ET.Element, path: str) -> ET.Element:
    found = root.find(path)
    assert found is not None, f"{path} is not in the document any more"
    return found


def _mutations(
    document: Path,
) -> list[tuple[str, Callable[[ET.Element], None]]]:
    if document.name == "ipa.xml":
        return [
            (
                "phone with no name",
                lambda r: _first(r, "phones/phone").attrib.pop("name"),
            ),
            (
                "arc off the tract",
                lambda r: _first(r, "features/feature/value[@arc]").set("arc", "1.5"),
            ),
            (
                "offscale spelled with a word",
                lambda r: _first(r, "features/feature/value[@offscale]").set(
                    "offscale", "yes"
                ),
            ),
            (
                "an unknown element under features",
                lambda r: ET.SubElement(_first(r, "features"), "gadget"),
            ),
            (
                "a phone declared among the features",
                lambda r: ET.SubElement(_first(r, "features"), "phone", {"name": "p"}),
            ),
            (
                "a feature value with no name",
                lambda r: _first(r, "features/feature/value").attrib.pop("name"),
            ),
        ]
    if document.name == "heads.xml":
        return [
            ("head with no name", lambda r: _first(r, "head").attrib.pop("name")),
            (
                "midline point off the box",
                lambda r: _first(r, "head/midline/point").set("arc", "2"),
            ),
            (
                "negative tract length",
                lambda r: _first(r, "head").set("length-cm", "-1"),
            ),
            (
                "a head with no midline",
                lambda r: _first(r, "head").remove(_first(r, "head/midline")),
            ),
            (
                "a phone nested under heads",
                lambda r: ET.SubElement(r, "phone", {"name": "p"}),
            ),
            (
                "a midline point with no provenance",
                lambda r: _first(r, "head/midline/point").attrib.pop("provenance"),
            ),
        ]
    return [
        ("map with no ipa side", lambda r: _first(r, "map").attrib.pop("ipa")),
        ("map with no target side", lambda r: _strip_to_ipa(_first(r, "map"))),
        (
            "a phone nested under phonemap",
            lambda r: ET.SubElement(r, "phone", {"name": "p"}),
        ),
        (
            "an unknown element among the extras",
            lambda r: ET.SubElement(_first(r, "extras"), "junk"),
        ),
        ("a root with no description", lambda r: r.attrib.pop("description")),
    ]


def _strip_to_ipa(element: ET.Element) -> None:
    """Leave a map row with its IPA side and nothing to map it to."""
    element.attrib = {"ipa": element.get("ipa", "")}


def _negatives() -> Iterator[Any]:
    for document in (IPA_XML, DATA / "heads.xml", DATA / "phonemaps" / "cmu.xml"):
        grammar = _grammars_for(document)[0]
        for label, mutate in _mutations(document):
            yield pytest.param(
                grammar, document, label, mutate, id=f"{grammar.stem}: {label}"
            )


@pytest.mark.parametrize(("grammar", "document", "label", "mutate"), list(_negatives()))
def test_grammar_rejects(
    grammar: Path,
    document: Path,
    label: str,
    mutate: Callable[[ET.Element], None],
    validate: Callable[[Path, bytes], str | None],
) -> None:
    root = ET.parse(document).getroot()
    control = validate(grammar, ET.tostring(root, encoding="utf-8"))
    assert control is None, (
        f"{document.name} does not validate after a round trip through "
        f"ElementTree, so no mutation of it proves anything:\n{control}"
    )

    mutate(root)
    errors = validate(grammar, ET.tostring(root, encoding="utf-8"))
    assert errors is not None, (
        f"{grammar.name} accepted {document.name} with {label}; the grammar is "
        f"not saying what it was written to say"
    )
