import os
import re
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from ipakit.bridges import VocabularyBridge, VocabularyResidueError
from ipakit.bridges.mfa import MFA, UNION, MFABridge, declarations
from ipakit.form import Form
from scripts.mfa_vocabularies import REVISION, ROOT, generate, stale

DATA = ROOT / "ipakit" / "data" / "bridges" / "mfa"


def _source() -> Path:
    return Path(
        os.environ.get("MFA_MODELS", Path.home() / ".cache" / "ipakit" / "mfa-models")
    )


SOURCE = _source()
needs_source = pytest.mark.skipif(
    not (SOURCE / "dictionary").is_dir(),
    reason="MFA_MODELS does not name a populated mfa-models checkout",
)


def test_every_shipped_declaration_loads_and_is_listed() -> None:
    paths = set(DATA.glob("*.xml"))
    assert {path.stem for path in paths} == {UNION, *declarations()}
    assert all(VocabularyBridge(path).atoms for path in paths)


def test_every_atom_is_exactly_one_house_unit() -> None:
    for declaration in (UNION, *declarations()):
        bridge = MFABridge(declaration)
        assert all(
            len(Form.parse(atom.spelling, strict=True).units) == 1
            for atom in bridge.atoms
        )


def test_segmented_atom_lists_do_not_resegment() -> None:
    for declaration in (UNION, *declarations()):
        bridge = MFABridge(declaration)
        form = bridge.read([atom.output for atom in bridge.atoms])
        assert len(form.units) == len(bridge.atoms)


def test_every_atom_round_trips() -> None:
    for declaration in (UNION, *declarations()):
        bridge = MFABridge(declaration)
        for atom in bridge.atoms:
            assert bridge.emit(bridge.read([atom.output]), separator=" ") == atom.output


def test_union_contains_every_declaration_value() -> None:
    union = MFABridge(UNION)
    atoms = {atom.output: atom.spelling for atom in union.atoms}
    refusals = {item.spelling: item.reason for item in union.refusals}
    for declaration in declarations():
        bridge = MFABridge(declaration)
        assert all(atoms[atom.output] == atom.spelling for atom in bridge.atoms)
        assert all(refusals[item.spelling] == item.reason for item in bridge.refusals)


def test_union_atoms_and_refusals_are_disjoint() -> None:
    union = MFABridge(UNION)
    assert {atom.output for atom in union.atoms}.isdisjoint(
        item.spelling for item in union.refusals
    )
    assert all(item.reason for item in union.refusals)


def test_default_and_union_identity() -> None:
    assert MFA.version == "english_mfa-v3.1.0"
    assert MFA.name == "mfa:english"
    assert MFA.tier == "mfa"
    with pytest.raises(ValueError, match="'nope'"):
        MFABridge("nope")
    union = MFABridge(UNION)
    assert union.name == "mfa"
    assert union.version == f"mfa-models@{REVISION}"


def test_segmented_refusal_preserves_declared_reason() -> None:
    bridge = MFABridge("korean")
    refused = bridge.refusals[0]
    with pytest.raises(VocabularyResidueError, match=re.escape(refused.reason)):
        bridge.read([refused.spelling])


@needs_source
def test_generator_reproduces_shipped_tree() -> None:
    assert stale(generate(SOURCE), ROOT) == []


@needs_source
def test_stale_finds_changed_and_stray_declarations(tmp_path: Path) -> None:
    artifacts = generate(SOURCE)
    target = tmp_path / "ipakit" / "data" / "bridges" / "mfa"
    target.parent.mkdir(parents=True)
    shutil.copytree(DATA, target)
    summary = tmp_path / "docs" / "mfa-vocabularies.md"
    summary.parent.mkdir(parents=True)
    shutil.copy(ROOT / "docs" / "mfa-vocabularies.md", summary)

    changed = target / "english.xml"
    root = ET.parse(changed).getroot()
    root.findall("atom")[0].set("spelling", "e")
    ET.ElementTree(root).write(changed, encoding="utf-8", xml_declaration=True)
    assert stale(artifacts, tmp_path) == [Path("ipakit/data/bridges/mfa/english.xml")]

    shutil.copy(DATA / "english.xml", changed)
    stray = target / "extra.xml"
    shutil.copy(DATA / "english.xml", stray)
    assert stale(artifacts, tmp_path) == [Path("ipakit/data/bridges/mfa/extra.xml")]
