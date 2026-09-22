"""What a student gets from ``pip install ipakit``, not from the checkout.

Every value ipakit computes comes out of a file in ``ipakit/data``. Those
files reach an installed user only if a glob in ``pyproject.toml`` names
them, and nothing else in the suite notices when one does not: the tests
import from the checkout, where the data is on disk either way. A data
file that stops shipping is therefore a silent wrong answer -- green
suite, broken install.

``data/rules/*.rules`` was added to ``package-data`` after the rule sets
themselves; between those two commits the shipped wheel had no rule sets
in it and the suite was green. These tests are written so the *next* such
extension fails here rather than in a classroom.

The guards are predicates over the whole tree rather than a list of
today's files, because a guard that lists today's offenders documents
only the present.
"""

import json
import os
import shutil
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from email.parser import BytesParser
from pathlib import Path

import pytest
from packaging.requirements import Requirement

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "ipakit"

# The build inputs, and nothing else. Copying only these into the sandbox
# also asserts that they are sufficient to build a wheel -- if the build
# ever starts needing another top-level file, this list is where it shows.
BUILD_INPUTS = ("pyproject.toml", "MANIFEST.in", "README.md", "LICENSE", "CHANGELOG.md")
SOURCE_SUPPORT_FILES = ("Makefile", "conftest.py", ".pre-commit-config.yaml")
SOURCE_SUPPORT_DIRS = ("tests", "scripts", "docs", ".github/workflows")


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


def _copy_build_inputs(src: Path) -> None:
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


@pytest.fixture(scope="module")
def package_source(tmp_path_factory) -> Path:
    """Minimal package build inputs, without tests or development support."""
    pytest.importorskip("setuptools")
    src = tmp_path_factory.mktemp("src")
    _copy_build_inputs(src)
    return src


@pytest.fixture(scope="module")
def complete_source(tmp_path_factory) -> Path:
    """A source distribution additionally needs its verification support."""
    pytest.importorskip("setuptools")
    src = tmp_path_factory.mktemp("complete-src")
    _copy_build_inputs(src)
    # The sdist must carry the inputs its shipped tests read, not just their
    # Python modules. Keep the expectation source-derived rather than asking
    # the built archive what it thinks should have shipped.
    for name in SOURCE_SUPPORT_FILES:
        shutil.copyfile(ROOT / name, src / name)
    for name in SOURCE_SUPPORT_DIRS:
        shutil.copytree(
            ROOT / name,
            src / name,
            ignore=shutil.ignore_patterns(
                "__pycache__", "*.py[cod]", ".pytest_cache", ".DS_Store"
            ),
        )

    return src


def _build_archives(src: Path, out: Path, methods: tuple[str, ...]) -> None:
    # Call the native backend offline; no second packaging implementation or
    # network isolation environment is needed to test the declared inputs.
    program = "from setuptools import build_meta; " + "; ".join(
        f"build_meta.{method}({str(out)!r})" for method in methods
    )
    subprocess.run(
        [sys.executable, "-c", program], cwd=src, check=True, capture_output=True
    )


@pytest.fixture(scope="module")
def built_wheel(package_source, tmp_path_factory) -> Path:
    """Build the actual wheel from minimal inputs, without checkout support."""
    out = tmp_path_factory.mktemp("wheel")
    _build_archives(package_source, out, ("build_wheel", "build_sdist"))
    wheels = list(out.glob("*.whl"))
    assert len(wheels) == 1, f"expected one wheel, got {wheels}"
    return wheels[0]


@pytest.fixture(scope="module")
def built_sdist(complete_source, tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("sdist")
    _build_archives(complete_source, out, ("build_sdist",))
    archives = list(out.glob("*.tar.gz"))
    assert len(archives) == 1
    return archives[0]


def test_wheel_build_inputs_exclude_verification_support(package_source):
    assert all(
        not (package_source / name).exists()
        for name in (*SOURCE_SUPPORT_FILES, *SOURCE_SUPPORT_DIRS)
    )


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


def test_wheel_requires_the_tiergraph_line_its_documents_are_written_in(built_wheel):
    """Installation admits exactly the tiergraph 0.3 line.

    A tiergraph reader accepts only its own format version, so a provider from
    another line refuses every document ipakit writes or ships.
    """
    with zipfile.ZipFile(built_wheel) as archive:
        metadata_paths = [
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        ]
        assert len(metadata_paths) == 1
        metadata = BytesParser().parsebytes(archive.read(metadata_paths[0]))
    requirements = [
        Requirement(value) for value in metadata.get_all("Requires-Dist", [])
    ]
    native = [item for item in requirements if item.name == "tiergraph"]
    assert len(native) == 1
    requirement = native[0]
    assert requirement.url is None and requirement.marker is None
    assert "0.2.3" not in requirement.specifier
    assert "0.3.0" in requirement.specifier
    assert "0.4.0" not in requirement.specifier


def test_the_wheel_carries_one_canonical_panphon_declaration_and_credit(built_wheel):
    with zipfile.ZipFile(built_wheel) as zf:
        names = zf.namelist()
        prefix = "ipakit/data/feature-models/"
        assert [n for n in names if n.endswith("panphon.xml")] == [
            prefix + "panphon.xml"
        ]
        for filename in ("panphon.xml", "PANPHON-LICENSE.txt", "NOTICE.md"):
            assert (
                zf.read(prefix + filename)
                == (PKG / "data/feature-models" / filename).read_bytes()
            )


def test_sdist_carries_one_canonical_panphon_declaration_and_credit(built_wheel):
    archives = list(built_wheel.parent.glob("*.tar.gz"))
    assert len(archives) == 1
    with tarfile.open(archives[0]) as archive:
        members = archive.getnames()
        roots = {name.split("/")[0] for name in members}
        assert len(roots) == 1
        prefix = roots.pop() + "/ipakit/data/feature-models/"
        assert [n for n in members if n.endswith("panphon.xml")] == [
            prefix + "panphon.xml"
        ]
        for filename in ("panphon.xml", "PANPHON-LICENSE.txt", "NOTICE.md"):
            stream = archive.extractfile(prefix + filename)
            assert stream is not None
            assert (
                stream.read() == (PKG / "data/feature-models" / filename).read_bytes()
            )


def test_sdist_carries_source_verification_inputs(built_sdist, complete_source):
    expected = [complete_source / name for name in SOURCE_SUPPORT_FILES]
    for name in SOURCE_SUPPORT_DIRS:
        expected.extend(
            path for path in (complete_source / name).rglob("*") if path.is_file()
        )
    assert any(path.suffix == ".json" for path in expected)
    assert any(path.suffix == ".dot" for path in expected)
    with tarfile.open(built_sdist) as archive:
        members = archive.getnames()
        roots = {name.split("/")[0] for name in members}
        assert len(roots) == 1
        prefix = roots.pop() + "/"
        missing = [
            path.relative_to(complete_source).as_posix()
            for path in expected
            if prefix + path.relative_to(complete_source).as_posix() not in members
        ]
        assert not missing, f"source verification inputs missing from sdist: {missing}"
        for path in expected:
            stream = archive.extractfile(
                prefix + path.relative_to(complete_source).as_posix()
            )
            assert stream is not None and stream.read() == path.read_bytes()
        assert not any(
            "__pycache__" in name or name.endswith(".pyc") for name in members
        )


def test_unpacked_sdist_collects_its_suite(built_sdist, tmp_path):
    """The shipped verification tree can collect independently of the checkout."""
    with tarfile.open(built_sdist) as archive:
        archive.extractall(tmp_path, filter="data")
    roots = [path for path in tmp_path.iterdir() if path.is_dir()]
    assert len(roots) == 1
    source = roots[0]
    assert not (source / ".git").exists()
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-o", "addopts="],
        cwd=source,
        env=env,
        text=True,
        capture_output=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (
        "tests/test_packaging.py::test_unpacked_sdist_collects_its_suite"
        in result.stdout
    )


@pytest.mark.parametrize("omit_timit", [False, True])
def test_installed_inventory_census_and_models_need_no_checkout_or_provider(
    built_wheel, tmp_path, omit_timit
):
    from ipakit import feature_models, inventories

    import tiergraph

    # Derive the expected census from the source, not the possibly incomplete
    # installed wheel. No fixed inventory count constrains future declarations.
    expected = {
        "inventories": list(inventories()),
        "models": list(feature_models.available()),
    }
    assert expected["inventories"] and expected["models"]
    site = tmp_path / "site"
    with zipfile.ZipFile(built_wheel) as zf:
        zf.extractall(site)
    if omit_timit:
        # This registry member silently disappears if its resource is absent.
        # The source-derived census must detect that incomplete installation.
        (site / "ipakit/data/phonemaps/timit.xml").unlink()
    # Supply only the declared runtime dependency, not development site-packages.
    shutil.copytree(Path(tiergraph.__file__).parent, site / "tiergraph")
    program = """
import builtins, json, pathlib, socket, sys
sys.path.insert(0, sys.argv[1])
original = builtins.__import__
def blocked(name, *args, **kwargs):
    if name.split('.')[0] in {'panphon', 'pyclts', 'tests', 'scripts'}:
        raise AssertionError('runtime provider/checkout import: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = blocked
socket.socket = lambda *a, **k: (_ for _ in ()).throw(AssertionError('network'))
import ipakit
from ipakit import feature_models
from ipakit.finite_declaration import read_ternary_declaration
assert pathlib.Path(ipakit.__file__).resolve().is_relative_to(pathlib.Path(sys.argv[1]))
expected = json.load(sys.stdin)
assert list(ipakit.inventories()) == expected['inventories'], 'installed inventory census differs'
for name in expected['inventories']:
    found = ipakit.inventory(name)
    assert found.name == name
assert list(feature_models.available()) == expected['models']
for name in expected['models']:
    assert feature_models.read(name).model.name == name
assert 'panphon' in feature_models.available()
declaration = feature_models.read('panphon')
assert len(declaration.model.rows) == 6367
assert declaration.model.respell('p', {'voi': 1}).candidates == ('b', 'b̟', 'b̠')
assert read_ternary_declaration(feature_models.resource_path('panphon')).model == declaration.model
assert (feature_models.resource_path('panphon').parent / 'PANPHON-LICENSE.txt').is_file()
# Load the actual installed console entry point, without a checkout script.
import contextlib, importlib.metadata, io
main = importlib.metadata.entry_points(group='console_scripts')['ipakit'].load()
def command(args, group='model'):
    sys.argv = ['ipakit', group, *args, '-j']
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        assert main() == 0
    return json.loads(stream.getvalue())
assert 'panphon' in command(['list'])
assert command(['respell', '--model', 'panphon', '--token', 'p', '--changes-json', '{"voi":1}'])['candidates'] == ['b', 'b̟', 'b̠']
table = pathlib.Path('supplied.xml')
table.write_text('<model name="supplied" upstream="fixture" upstream-url="https://example.org" artifact="table" version="1" license="MIT" kind="features"><round-trip><external-to-house fidelity="lossy-with-report"/><house-to-external fidelity="lossy-with-report"/></round-trip><features><feature name="f"/></features><segments><s name="A/B #" f="-"/><s name="help" f="+"/></segments></model>', encoding='utf-8')
assert command(['respell', '--model-declaration', str(table), '--token', 'A/B #', '--changes-json', '{"f":1}'])['candidates'] == ['help']
tokens = pathlib.Path('tokens.json')
tokens.write_text('[["A/B #"], ["help"], []]', encoding='utf-8')
rows = command(['apply', '--model-declaration', str(table), '--tokens-json', str(tokens), '-r', '[f=-1] -> [f=1]'], group='rules')
assert [row['tokens'] for row in rows] == [['help'], ['help'], []]
tokens.write_text('[["p"], []]', encoding='utf-8')
rows = command(['trace', '--model', 'panphon', '--tokens-json', str(tokens), '-r', 'p -> b'], group='rules')
assert rows[0]['steps'][0]['before_tokens'] == ['p']
assert rows[0]['steps'][0]['after_tokens'] == ['b']
assert rows[1]['tokens'] == []
print(declaration.model.identity)
"""
    proc = subprocess.run(
        [sys.executable, "-I", "-S", "-c", program, str(site)],
        cwd=tmp_path,
        input=json.dumps(expected),
        text=True,
        encoding="utf-8",
        capture_output=True,
    )
    if omit_timit:
        assert proc.returncode != 0
        assert "installed inventory census differs" in proc.stderr
    else:
        assert proc.returncode == 0, proc.stderr


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

    orphaned = sorted(
        d
        for d in documents
        if not any(
            d.rsplit("/", 1)[0] == directory
            or d.rsplit("/", 1)[0].startswith(directory + "/")
            for directory in grammars
        )
    )
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
    "xsampa": ipakit.to_xsampa("\\u0283"),
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
    "positioned": ipakit.similarity_position("p", "b") is not None,
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
    assert got["positioned"], got


def test_the_installed_package_carries_the_tutorial_notebook(built_wheel, tmp_path):
    """The teaching material has to travel too, not only the library.

    Everything built to *learn* ipakit lived in the checkout: no tutorial,
    no examples, no figures reached an install. The notebook is the answer
    to that, and it is worth nothing unless it is in the wheel and
    reachable from an empty directory -- the case a student is in.

    Both surfaces are asked, from that empty directory, and the bytes are
    compared against the checked-in notebook, so "some JSON landed" cannot
    pass for "the tutorial landed".
    """
    site = tmp_path / "site"
    with zipfile.ZipFile(built_wheel) as zf:
        names = set(zf.namelist())
        zf.extractall(site)

    shipped = sorted(n for n in names if n.endswith(".ipynb"))
    assert shipped == ["ipakit/notebooks/ipakit-tutorial.ipynb"], shipped

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    program = """
import json, subprocess, sys
from pathlib import Path
import ipakit

api = ipakit.notebook(".")
proc = subprocess.run(
    [sys.executable, "-m", "ipakit.cli", "notebook", "-o", "cli"],
    capture_output=True, text=True, encoding="utf-8",
)
cli = Path("cli") / api.name
print(json.dumps({
    "where": ipakit.__file__,
    "api": api.read_text(encoding="utf-8"),
    "cli_status": proc.returncode,
    "cli_stdout": proc.stdout,
    "cli_stderr": proc.stderr,
    "cli": cli.read_text(encoding="utf-8") if cli.exists() else "",
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
    ), f"an installed ipakit could not write its notebook:\n{proc.stderr}"

    got = json.loads(proc.stdout)
    assert str(site) in got["where"], f"imported the wrong ipakit: {got['where']}"
    expected = (ROOT / "ipakit" / "notebooks" / "ipakit-tutorial.ipynb").read_text(
        encoding="utf-8"
    )
    assert got["cli_status"] == 0, got["cli_stderr"]
    assert got["api"] == expected, "the API wrote a different notebook"
    assert got["cli"] == expected, "the CLI wrote a different notebook"
    # It has to say where the file went and how to open it; a path printed
    # into the void leaves the student exactly where they started.
    assert "ipakit-tutorial.ipynb" in got["cli_stdout"], got["cli_stdout"]
    assert "jupyter" in got["cli_stdout"], got["cli_stdout"]
    document = json.loads(got["api"])
    assert document["nbformat"] == 4, document["nbformat"]
    assert document["cells"], "the notebook that landed has no cells"


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
