"""What a student gets from ``pip install ipakit``, not from the checkout.

Every value ipakit computes comes out of a file in ``ipakit/data``. Those
files reach an installed user only if a glob in ``pyproject.toml`` names
them, and nothing else in the suite notices when one does not: the tests
import from the checkout, where the data is on disk either way. A data
file that stops shipping is therefore a silent wrong answer of exactly
the shape ``docs/reviewing.md`` describes -- green suite, broken install.

``data/rules/*.rules`` was added to ``package-data`` after the rule sets
themselves; between those two commits the shipped wheel had no rule sets
in it and the suite was green. These tests are written so the *next* such
extension fails here rather than in a classroom.

The guards are predicates over the whole tree rather than a list of
today's files, per ``docs/reviewing.md``: "a guard that lists today's
offenders documents the present."
"""

import json
import os
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "ipakit"

# The build inputs, and nothing else. Copying only these into the sandbox
# also asserts that they are sufficient to build a wheel -- if the build
# ever starts needing another top-level file, this list is where it shows.
BUILD_INPUTS = ("pyproject.toml", "MANIFEST.in", "README.md", "LICENSE", "CHANGELOG.md")


def _package_data_globs() -> list[str]:
    with (ROOT / "pyproject.toml").open("rb") as fh:
        cfg = tomllib.load(fh)
    globs = cfg["tool"]["setuptools"]["package-data"]["ipakit"]
    assert globs, "pyproject declares no package-data for ipakit"
    return list(globs)


def _shipped_candidates() -> list[Path]:
    """Every non-source file under ``ipakit/`` that an install needs.

    Python modules travel because they are in a package; everything else
    travels only if a ``package-data`` glob names it.
    """
    out = []
    for path in sorted(PKG.rglob("*")):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix in (".py", ".pyc"):
            continue
        out.append(path.relative_to(PKG))
    return out


def test_every_non_source_file_in_the_package_is_declared_shippable():
    """No data file may exist that no ``package-data`` glob matches."""
    globs = _package_data_globs()
    candidates = _shipped_candidates()
    # Non-vacuity: a collapse in the walk must fail here, not pass quietly.
    assert len(candidates) > 10, f"walk found only {len(candidates)} data files"

    undeclared = [
        str(rel)
        for rel in candidates
        if not any(rel.match(pattern) for pattern in globs)
    ]
    assert not undeclared, (
        f"these files live in ipakit/ but no package-data glob in "
        f"pyproject.toml matches them, so they will not ship: {undeclared}. "
        f"Declared globs: {globs}"
    )


def test_no_declared_glob_is_dead():
    """A glob matching nothing is a stale declaration, not protection."""
    candidates = _shipped_candidates()
    dead = [
        pattern
        for pattern in _package_data_globs()
        if not any(rel.match(pattern) for rel in candidates)
    ]
    assert not dead, (
        f"these package-data globs match no file under ipakit/: {dead}. "
        f"Either the data moved and the glob was left behind, or the glob "
        f"has a typo and the file it was meant to carry is not shipping."
    )


@pytest.fixture(scope="module")
def built_wheel(tmp_path_factory) -> Path:
    """A wheel built from a copy of the tree, offline and out of place.

    Built through ``setuptools.build_meta`` directly rather than ``python
    -m build`` so there is no build isolation and therefore no network:
    a classroom on institutional wifi is the case this whole file is
    about, and CI should not need a package index to check packaging.
    """
    setuptools = pytest.importorskip("setuptools")
    del setuptools

    src = tmp_path_factory.mktemp("src")
    out = tmp_path_factory.mktemp("wheel")

    for name in BUILD_INPUTS:
        source = ROOT / name
        assert source.is_file(), f"build input {name} is missing from the tree"
        (src / name).write_bytes(source.read_bytes())

    # Copy the package by hand: shutil.copytree would drag __pycache__ in.
    for path in PKG.rglob("*"):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        target = src / path.relative_to(ROOT)
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())

    subprocess.run(
        [
            sys.executable,
            "-c",
            "from setuptools import build_meta; "
            f"build_meta.build_wheel({str(out)!r})",
        ],
        cwd=src,
        check=True,
        capture_output=True,
    )
    wheels = list(out.glob("*.whl"))
    assert len(wheels) == 1, f"expected one wheel, got {wheels}"
    return wheels[0]


def test_the_wheel_carries_every_data_file(built_wheel):
    """What is on disk under ``ipakit/`` is what lands in the wheel."""
    with zipfile.ZipFile(built_wheel) as zf:
        names = set(zf.namelist())

    expected = {f"ipakit/{rel.as_posix()}" for rel in _shipped_candidates()}
    assert len(expected) > 10, "no data files found to check"

    missing = sorted(expected - names)
    assert not missing, (
        f"these files are in the source tree but not in the built wheel, so "
        f"`pip install ipakit` does not get them: {missing}"
    )


def test_the_wheel_carries_each_grammar_beside_its_data(built_wheel):
    """A grammar travels with the data it describes, into the wheel too.

    ``ipa.xml`` says of itself that it travels on its own, which is why the
    RELAX NG grammars sit in ``ipakit/data`` rather than in a schemas
    directory: a copied file should carry what states its shape. That claim
    is about co-location, and co-location is the one thing a per-directory
    ``package-data`` glob can quietly break -- ``data/*.rng`` and
    ``data/phonemaps/*.rng`` are two globs, and shipping one without the
    other leaves half the data unstated with nothing else noticing.
    """
    with zipfile.ZipFile(built_wheel) as zf:
        names = [n for n in zf.namelist() if n.startswith("ipakit/data/")]

    documents = [n for n in names if n.endswith(".xml")]
    grammars = {n.rsplit("/", 1)[0] for n in names if n.endswith(".rng")}
    assert documents, "no XML data in the wheel to check"
    assert grammars, "no grammars in the wheel; `data/*.rng` is not shipping"

    orphaned = sorted(d for d in documents if d.rsplit("/", 1)[0] not in grammars)
    assert not orphaned, (
        f"these documents shipped without a grammar beside them, so an "
        f"installed copy cannot say what shape it is in: {orphaned}"
    )


def test_the_installed_package_reads_its_data_without_the_checkout(
    built_wheel, tmp_path
):
    """The real question: does it work from somewhere else entirely?

    The suite otherwise always runs with the checkout on ``sys.path`` and
    the data reachable by relative path, so a module resolving data
    against the current directory rather than against itself would pass
    everything and fail on every installed user.
    """
    site = tmp_path / "site"
    with zipfile.ZipFile(built_wheel) as zf:
        zf.extractall(site)

    # An empty directory to run from, so neither the checkout nor any
    # data beside it is reachable as a relative path.
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    program = """
import json, sys
import ipakit
from ipakit import rules
from ipakit.tract import head
import ipakit.xsampa, ipakit.phonemaps

assert "ipakit" not in str(sys.path[0]) or not sys.path[0], sys.path[0]
out = {
    "where": ipakit.__file__,
    # ipa.xml
    "features": len(ipakit.features("p")),
    # phonemaps/cmu.xml
    "cmu": ipakit.to_cmu("kaet".replace("ae", "\\u00e6")),
    # phonemaps/xsampa.xml
    "xsampa": ipakit.ipa_to_xsampa("\\u0283"),
    # data/rules/*.rules
    "rulesets": sorted(p.stem for p in rules.RULES_DIR.glob("*.rules")),
    "derived": rules.shipped("german-final-devoicing").apply("ta\\u02d0\\u0261"),
    # data/supplements/*.xml, asked for as the documents ask for it
    "supplements": ipakit.available_supplements(),
    "registered": sorted(
        set(ipakit.load_ipa_features(supplements=["aspirated-stops"]).phones)
        - set(ipakit.load_ipa_features().phones)
    ),
    # heads.xml
    "head": head("adult-male").name,
    # confusion.json
    "confusable": ipakit.confusability("p", "b") is not None,
}
print(json.dumps(out))
"""
    # Inherit the environment rather than scrubbing it: a replacement env
    # without SYSTEMROOT fails to start CPython on Windows, and PYTHONPATH
    # is the only variable this needs to control. `encoding` is explicit
    # because the child prints IPA and the parent must not decode it with
    # whatever the locale says (cp1252 on Windows).
    env = {**os.environ, "PYTHONPATH": str(site)}
    env.pop("PYTHONHOME", None)
    proc = subprocess.run(
        [sys.executable, "-c", program],
        cwd=elsewhere,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert (
        proc.returncode == 0
    ), f"an installed ipakit could not read its own data:\n{proc.stderr}"

    got = json.loads(proc.stdout)
    assert str(site) in got["where"], f"imported the wrong ipakit: {got['where']}"
    assert got["features"] > 10, got
    assert got["cmu"] == ["K", "AE0", "T"], got
    assert got["xsampa"] == "S", got
    # Every shipped rule set, named from the installed tree.
    assert len(got["rulesets"]) == 5, got
    assert "american-english" in got["rulesets"], got
    assert got["derived"] == "taːk", got
    # The worked supplement, loaded by name from the install rather than
    # from a path into the checkout -- which is the whole point of shipping
    # it: an installed reader had the grammar and no instance of the format.
    assert "aspirated-stops" in got["supplements"], got
    assert got["registered"] == ["kʰ", "pʰ", "tʰ"], got
    assert got["head"] == "adult-male", got
    assert got["confusable"], got


def test_the_installed_package_can_draw_a_tract_figure(built_wheel, tmp_path):
    """The tract figure, from an install rather than from the checkout.

    This is the case the move exists for. ``ipakit/tract.py`` -- the model
    -- has always shipped, but the renderer lived in ``scripts/``, which is
    in neither the wheel nor the importable half of the sdist. So ``pip
    install ipakit`` gave a student the geometry and no way to see it, under
    a green suite, because every test imported the drawing from the
    checkout by putting ``scripts/`` on ``sys.path``.

    Three claims, all made from an empty directory with only the unpacked
    wheel importable: the library draws, the CLI draws, and the notebook
    hook draws. The bytes are compared against ``docs/figures/tract-t.svg``
    -- what ``make figures`` wrote -- so "it produced some SVG" cannot pass
    for "it produced the figure".
    """
    site = tmp_path / "site"
    with zipfile.ZipFile(built_wheel) as zf:
        zf.extractall(site)

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    program = """
import json, subprocess, sys
from pathlib import Path
import ipakit
from ipakit.tract import head
from ipakit.tract_svg import figure

svg = figure("t", "adult-male")
# The CLI, as an installed user would reach it (the console script is not
# on PATH here, so through the module it dispatches to).
out = Path("cli.svg")
proc = subprocess.run(
    [sys.executable, "-m", "ipakit.cli", "tract", "draw", "t",
     "--head", "adult-male", "-o", str(out)],
    capture_output=True, text=True, encoding="utf-8",
)
print(json.dumps({
    "where": ipakit.__file__,
    "library": svg,
    "cli_status": proc.returncode,
    "cli_stderr": proc.stderr,
    "cli": out.read_text(encoding="utf-8") if out.exists() else "",
    "notebook": ipakit.segment("t")._repr_svg_(),
    "reference": figure(None, "adult-male")[:5],
    "head_repr": head("child")._repr_svg_()[:5],
}))
"""
    env = {**os.environ, "PYTHONPATH": str(site)}
    env.pop("PYTHONHOME", None)
    proc = subprocess.run(
        [sys.executable, "-c", program],
        cwd=elsewhere,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert (
        proc.returncode == 0
    ), f"an installed ipakit could not draw a tract figure:\n{proc.stderr}"

    got = json.loads(proc.stdout)
    assert str(site) in got["where"], f"imported the wrong ipakit: {got['where']}"

    expected = (ROOT / "docs" / "figures" / "tract-t.svg").read_text(encoding="utf-8")
    assert got["cli_status"] == 0, got["cli_stderr"]
    assert got["library"] == expected, "the installed library draws a different figure"
    assert got["cli"] == expected, "the installed CLI draws a different figure"
    assert got["notebook"] == expected, "Segment._repr_svg_ draws a different figure"
    # The reference drawing and a head's own repr are the other two entries
    # a student meets; they only have to be SVG, not a particular figure.
    assert got["reference"] == "<svg ", got["reference"]
    assert got["head_repr"] == "<svg ", got["head_repr"]
