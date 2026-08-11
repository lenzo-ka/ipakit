"""The shipped XML against the grammars that state its shape.

Every number ipakit computes comes out of a file in ``ipakit/data``, and
the code that reads those files says nothing about their shape. A
misplaced attribute or a section under the wrong parent is read by
``xml.etree.ElementTree`` without complaint and comes back as a missing
feature, a phone with no place, a head that draws slightly wrong -- a
silent wrong answer of the shape ``docs/reviewing.md`` is about. The
grammars in ``ipakit/data`` say what well-formed means; this module is
what makes the saying bite.

Four claims, in order of how much they are worth:

1. Every shipped XML validates against its grammar.
2. Every XML document in the repository is claimed by exactly one
   grammar, so a *new* document arriving without one fails here rather
   than shipping unstated.
3. No grammar names any of the inventory. ipa.xml is the one place a
   feature, a value or a symbol is declared, and a schema listing them
   would be a second copy that drifts.
4. Each grammar rejects the things it is supposed to reject. A schema
   nobody has seen fail is not known to work.
"""

from __future__ import annotations

import functools
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
# The worked supplement, in the directory it ships from, beside the grammar
# that states its shape.
SUPPLEMENT_XML = DATA / "supplements" / "aspirated-stops.xml"

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


@functools.cache
def _grammar_roots(grammar: Path) -> frozenset[str]:
    """The root elements ``grammar`` starts with.

    Read out of ``<start>``, following any ``<ref>`` into its define and
    stopping at the first element on each branch: that element is the
    document root, and what is inside it is that document's business.
    """
    root = ET.parse(grammar).getroot()
    defines = {d.get("name", ""): d for d in root.iter(f"{RNG}define") if d.get("name")}
    found: set[str] = set()

    def walk(node: ET.Element, seen: frozenset[str]) -> None:
        for child in node:
            if child.tag == f"{RNG}element":
                if name := child.get("name"):
                    found.add(name)
                continue
            if child.tag == f"{RNG}ref":
                name = child.get("name", "")
                if name in defines and name not in seen:
                    walk(defines[name], seen | {name})
                continue
            walk(child, seen)

    for start in root.iter(f"{RNG}start"):
        walk(start, frozenset())
    return frozenset(found)


@functools.cache
def _document_root(document: Path) -> str:
    return str(ET.parse(document).getroot().tag)


def _grammars_for(document: Path) -> list[Path]:
    """The grammars that claim ``document``, by the element it starts with.

    A grammar's ``<start>`` already names the root of the documents it
    describes, so the claim is read out of the grammar rather than guessed
    from a file name. Every document has exactly one root, which is what
    keeps "claimed by exactly one grammar" a checkable property.

    A rule over file names does not reach as far. The grammars all live
    under ``ipakit/data``, beside the documents they describe, because a
    copied file should carry what states its shape and because an installed
    user has to be able to reach one. A supplement is named after what it
    declares -- ``aspirated-stops.xml`` -- rather than after
    ``supplement.rng`` sitting beside it, and no naming convention was
    going to relate them.
    """
    return [g for g in _grammars() if _document_root(document) in _grammar_roots(g)]


# A checkout accumulates files that are not the repository's: build output,
# virtualenvs, tool caches, an editor's droppings. Everything else is in
# scope, named as a subtraction rather than dodged by a narrow glob, so an
# XML document added anywhere lands in these tests instead of missing them.
_NOT_THE_REPOSITORY = frozenset(
    {"build", "dist", "wheels", "venv", "ENV", "htmlcov", "export", "__pycache__"}
)


def _ours(path: Path) -> bool:
    parts = path.relative_to(ROOT).parts[:-1]
    return not any(
        part.startswith(".")
        or part.endswith(".egg-info")
        or part in _NOT_THE_REPOSITORY
        for part in parts
    )


def _documents() -> list[Path]:
    return sorted(p for p in ROOT.rglob("*.xml") if _ours(p))


@functools.cache
def _grammars() -> tuple[Path, ...]:
    return tuple(sorted(p for p in ROOT.rglob("*.rng") if _ours(p)))


def _pairs() -> Iterator[tuple[Path, Path]]:
    for document in _documents():
        for grammar in _grammars_for(document):
            yield grammar, document


def _ident(pair: tuple[Path, Path]) -> str:
    grammar, document = pair
    return f"{document.relative_to(ROOT)}-{grammar.name}"


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
    grammars = _grammars()
    assert grammars, "no .rng files found in the repository"
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
    """A document no grammar covers fails here rather than shipping unstated.

    Every ``.xml`` in the repository, not only the inventory: a supplement
    is a document type the library invites its users to write, and the
    worked example is the one instance of it anybody can copy. A format
    demonstrated in the documentation and stated nowhere is a format whose
    readers are guessing.

    If you have just added an XML document and landed on this failure:
    write a grammar for it, put it in ``ipakit/data`` with the others, and
    let its ``<start>`` name the document's root element -- that is what
    claims the document. A family of documents sharing a root share a
    grammar, which is how ``phonemaps/phonemap.rng`` claims every phonemap
    at once.

    The point is not ceremony. Nothing else in the suite notices when a
    document's shape changes underneath it: ElementTree reads a section
    under the wrong parent without complaint, and what comes back is a
    missing feature rather than an error.

    The ``.svg`` figures under ``docs/figures`` are XML too and are out of
    scope deliberately. They are derived, not written: ``make figures``
    regenerates them and ``tests/test_tract_figures.py`` fails on any
    difference from what is checked in, so their shape is already pinned
    exactly, by the code that emits it rather than by a grammar restating
    it.
    """
    documents = _documents()
    # Non-vacuity: a collapse in the walk must fail here, not pass quietly.
    assert len(documents) > 4, f"walk found only {len(documents)} XML files"

    unclaimed = [
        str(d.relative_to(ROOT)) for d in documents if len(_grammars_for(d)) == 0
    ]
    assert not unclaimed, (
        f"no grammar starts with the root element of these XML documents, so "
        f"nothing states what they are allowed to look like: {unclaimed}"
    )

    contested = {
        str(d.relative_to(ROOT)): [g.name for g in _grammars_for(d)]
        for d in documents
        if len(_grammars_for(d)) > 1
    }
    assert not contested, (
        f"these XML documents are claimed by more than one grammar, so which "
        f"one states their shape is a matter of opinion: {contested}"
    )


def test_no_grammar_claims_nothing() -> None:
    """A grammar matching no document is a stale declaration, not protection."""
    claimed = {g for d in _documents() for g in _grammars_for(d)}
    dead = [str(g.relative_to(ROOT)) for g in _grammars() if g not in claimed]
    assert not dead, (
        f"these grammars claim no document in the repository: {dead}. Either "
        f"the document moved and the grammar was left behind, or the grammar "
        f"starts with a root element nothing here is written under."
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

    checked: dict[str, set[str]] = {}
    for grammar in _grammars():
        root = ET.parse(grammar).getroot()
        defines = {
            d.get("name", ""): d for d in root.iter(f"{RNG}define") if d.get("name")
        }
        for element in root.iter(f"{RNG}element"):
            if (symbol_element := element.get("name")) not in SYMBOL_ELEMENTS:
                continue
            assert symbol_element is not None
            checked.setdefault(grammar.name, set()).add(symbol_element)
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

    # Non-vacuity, and a claim in its own right: a grammar that admits
    # symbols at all admits every char class ipa.xml declares, so no
    # document type is left with a section this check never looked at.
    assert checked, (
        f"no grammar defines any of {sorted(SYMBOL_ELEMENTS)}; the check is "
        f"scoped to symbol elements and found none, so it is not checking "
        f"what it claims"
    )
    partial = {
        name: sorted(SYMBOL_ELEMENTS - found)
        for name, found in checked.items()
        if found != SYMBOL_ELEMENTS
    }
    assert not partial, (
        f"these grammars admit some symbol elements and not others: {partial}. "
        f"The char classes are declared together in ipa.xml and a grammar that "
        f"takes symbols takes all of them."
    )


def test_no_grammar_enumerates_a_declared_value() -> None:
    """``<value>`` in a grammar is an enumeration, and enumerations drift.

    Anywhere a grammar spells out a legal string it has taken a copy of
    something ipa.xml declares. The flags are the exception the docstring on
    :func:`_inventory` describes, and they are excluded there rather than
    here so that the exception is stated once.
    """
    inventory = _inventory()
    for grammar in _grammars():
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
#
# Each also names the libxml2 error it must provoke. Rejection alone is a
# weak claim: a mutation written to prove that an element in the wrong
# place is refused, but failing because the element it carried has no
# `name`, passes while checking nothing. The codes are libxml2's own enum
# names -- ATTRVALID for a required attribute missing, INVALIDATTR for one
# whose value is out of range, ELEMNAME and ELEMWRONG for an element the
# content model has no room for, NOELEM for a required one absent.


def _first(root: ET.Element, path: str) -> ET.Element:
    found = root.find(path)
    assert found is not None, f"{path} is not in the document any more"
    return found


def _mutations(
    document: Path,
) -> list[tuple[str, Callable[[ET.Element], None], str]]:
    if document.name == "ipa.xml":
        return [
            (
                "phone with no name",
                lambda r: _first(r, "phones/phone").attrib.pop("name"),
                "RELAXNG_ERR_ATTRVALID",
            ),
            (
                "arc off the tract",
                lambda r: _first(r, "features/feature/value[@arc]").set("arc", "1.5"),
                "RELAXNG_ERR_INVALIDATTR",
            ),
            (
                "offscale spelled with a word",
                lambda r: _first(r, "features/feature/value[@offscale]").set(
                    "offscale", "yes"
                ),
                "RELAXNG_ERR_INVALIDATTR",
            ),
            (
                "an unknown element under features",
                lambda r: ET.SubElement(_first(r, "features"), "gadget"),
                "RELAXNG_ERR_ELEMNAME",
            ),
            (
                "a phone declared among the features",
                lambda r: ET.SubElement(_first(r, "features"), "phone", {"name": "p"}),
                "RELAXNG_ERR_ELEMNAME",
            ),
            (
                "a feature value with no name",
                lambda r: _first(r, "features/feature/value").attrib.pop("name"),
                "RELAXNG_ERR_ATTRVALID",
            ),
        ]
    if document.name == "heads.xml":
        return [
            (
                "head with no name",
                lambda r: _first(r, "head").attrib.pop("name"),
                "RELAXNG_ERR_ATTRVALID",
            ),
            (
                "midline point off the box",
                lambda r: _first(r, "head/midline/point").set("arc", "2"),
                "RELAXNG_ERR_ATTRVALID",
            ),
            (
                "negative tract length",
                lambda r: _first(r, "head").set("length-cm", "-1"),
                "RELAXNG_ERR_INVALIDATTR",
            ),
            (
                "a head with no midline",
                lambda r: _first(r, "head").remove(_first(r, "head/midline")),
                "RELAXNG_ERR_NOELEM",
            ),
            (
                "a phone nested under heads",
                lambda r: ET.SubElement(r, "phone", {"name": "p"}),
                "RELAXNG_ERR_ELEMWRONG",
            ),
            (
                "a midline point with no provenance",
                lambda r: _first(r, "head/midline/point").attrib.pop("provenance"),
                "RELAXNG_ERR_ATTRVALID",
            ),
        ]
    if document.name == "aspirated-stops.xml":
        return [
            (
                "phone with no name",
                lambda r: _first(r, "phones/phone").attrib.pop("name"),
                "RELAXNG_ERR_ATTRVALID",
            ),
            (
                "a supplement with no name",
                lambda r: r.attrib.pop("name"),
                "RELAXNG_ERR_ATTRVALID",
            ),
            (
                "a diacritic among the phones",
                lambda r: ET.SubElement(
                    _first(r, "phones"), "diacritic", {"name": "̥"}
                ),
                "RELAXNG_ERR_ELEMWRONG",
            ),
            (
                "a section that registers nothing",
                lambda r: _empty(_first(r, "phones")),
                "RELAXNG_ERR_NOELEM",
            ),
        ]
    if document.name == "mfa.xml":
        return [
            (
                "atom with no spelling",
                lambda r: _first(r, "atom").attrib.pop("spelling"),
                "RELAXNG_ERR_ATTRVALID",
            ),
            (
                "an unknown atom attribute",
                lambda r: _first(r, "atom").set("guess", "p"),
                "RELAXNG_ERR_INVALIDATTR",
            ),
            (
                "an unknown vocabulary element",
                lambda r: ET.SubElement(r, "passthrough"),
                "RELAXNG_ERR_EXTRACONTENT",
            ),
        ]
    return [
        (
            "map with no ipa side",
            lambda r: _first(r, "map").attrib.pop("ipa"),
            "RELAXNG_ERR_ATTRVALID",
        ),
        (
            "map with no target side",
            lambda r: _strip_to_ipa(_first(r, "map")),
            "RELAXNG_ERR_ATTRVALID",
        ),
        (
            "a phone nested under phonemap",
            lambda r: ET.SubElement(r, "phone", {"name": "p"}),
            "RELAXNG_ERR_EXTRACONTENT",
        ),
        (
            "an unknown element among the extras",
            lambda r: ET.SubElement(_first(r, "extras"), "junk"),
            "RELAXNG_ERR_ELEMNAME",
        ),
        (
            "a root with no description",
            lambda r: r.attrib.pop("description"),
            "RELAXNG_ERR_ATTRVALID",
        ),
        (
            # The column its rows carry the target spelling in is the one
            # thing a reader cannot work out from the document, so a table
            # that leaves it unsaid is refused here rather than loading as
            # a table of nothing.
            "a root that does not say what it maps to",
            lambda r: r.attrib.pop("to"),
            "RELAXNG_ERR_ATTRVALID",
        ),
    ]


def _strip_to_ipa(element: ET.Element) -> None:
    """Leave a map row with its IPA side and nothing to map it to."""
    element.attrib = {"ipa": element.get("ipa", "")}


def _empty(element: ET.Element) -> None:
    """Leave a section with no entries in it."""
    for child in list(element):
        element.remove(child)


def _negatives() -> Iterator[Any]:
    for document in (
        IPA_XML,
        DATA / "heads.xml",
        DATA / "phonemaps" / "cmu.xml",
        SUPPLEMENT_XML,
        DATA / "bridges" / "mfa" / "mfa.xml",
    ):
        grammar = _grammars_for(document)[0]
        for label, mutate, code in _mutations(document):
            yield pytest.param(
                grammar, document, label, mutate, code, id=f"{grammar.stem}: {label}"
            )


@pytest.mark.parametrize(
    ("grammar", "document", "label", "mutate", "code"), list(_negatives())
)
def test_grammar_rejects(
    grammar: Path,
    document: Path,
    label: str,
    mutate: Callable[[ET.Element], None],
    code: str,
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
    # lxml prints libxml2's error code beside its message; xmllint prints
    # the message alone, so the fallback path can only ask that the
    # document was refused, and says so here rather than looking stronger
    # than it is.
    if _lxml is not None:
        assert code in errors, (
            f"{grammar.name} refused {document.name} with {label}, but not for "
            f"{code} -- so this mutation is passing on some other fault and is "
            f"not testing what its name says:\n{errors}"
        )


@pytest.mark.parametrize(
    "block", ["features", "types", "classes", "modes", "bridges", "projections"]
)
def test_a_supplement_may_not_declare(
    block: str, validate: Callable[[Path, bytes], str | None]
) -> None:
    """The line ``ipakit.features`` holds at load, drawn one step earlier.

    A supplement adds symbols to a feature space; it does not get to
    change the space. Every attribute on an entry lands in that symbol's
    bundle and every bundle key is a term in the metric, so a file able to
    declare a feature could move every distance in the inventory it was
    merely extending.

    The grammar refuses them by admitting only the symbol sections, which
    is why the blocks are named here and not there: this test is where the
    consequence for each of them is checked, and a grammar that listed
    them would be a blocklist -- silent on the next kind of declaration
    the day ipa.xml grows one.
    """
    grammar = _grammars_for(SUPPLEMENT_XML)[0]
    root = ET.parse(SUPPLEMENT_XML).getroot()
    ET.SubElement(root, block)
    errors = validate(grammar, ET.tostring(root, encoding="utf-8"))
    assert errors is not None, (
        f"supplement.rng accepted a <{block}> block, so a supplement could add "
        f"a term to the metric of the inventory it is extending"
    )
    if _lxml is not None:
        assert "RELAXNG_ERR_ELEMWRONG" in errors, errors
    assert f"element {block} there" in errors, (
        f"the refusal of <{block}> does not say which element it is about, so a "
        f"reader cannot act on it:\n{errors}"
    )
