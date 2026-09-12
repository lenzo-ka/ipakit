"""Verify real distribution bytes, notices and provider-free default lookup."""

import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

from .test_packaging import built_wheel, package_source  # noqa: F401


def test_phoible_wheel_sdist_bytes_and_isolated_lookup(
    built_wheel, package_source, tmp_path  # noqa: F811
):
    output = tmp_path / "sdist"
    output.mkdir()
    subprocess.run(
        [
            sys.executable,
            "-c",
            "from setuptools import build_meta; "
            f"build_meta.build_sdist({str(output)!r})",
        ],
        cwd=package_source,
        check=True,
        capture_output=True,
    )
    sdist = next(output.glob("*.tar.gz"))
    original = Path(__file__).resolve().parents[1] / "ipakit/data/phoible"
    expected = {
        str(path.relative_to(original)): path.read_bytes()
        for path in original.rglob("*")
        if path.is_file()
    }
    assert len(expected) == 9
    assert {
        "NOTICE.txt",
        "MIT-upstream.txt",
        "GPL-3.0.txt",
        "CC-BY-SA-3.0.txt",
        "manifest.json",
    } <= set(expected)
    site = tmp_path / "site"
    with zipfile.ZipFile(built_wheel) as wheel, tarfile.open(sdist) as archive:
        prefix = archive.getnames()[0].split("/")[0]
        for relative, content in expected.items():
            assert wheel.read("ipakit/data/phoible/" + relative) == content
            assert (
                archive.extractfile(prefix + "/ipakit/data/phoible/" + relative).read()
                == content
            )
        wheel.extractall(site)
    # The sole imported graph dependency is copied explicitly; no site-packages,
    # optional providers, checkout imports or implicit environment source.
    import tiergraph

    shutil.copytree(Path(tiergraph.__file__).parent, site / "tiergraph")
    code = f"""
import sys, socket, importlib.util
sys.path.insert(0, {str(site)!r})
def forbidden(*args, **kwargs):
    raise AssertionError('network attempted')
socket.socket = forbidden
assert importlib.util.find_spec('panphon') is None
assert importlib.util.find_spec('pyclts') is None
from ipakit.bridges.phoible import PhoibleBridge
from ipakit.phoible_source import read_source, source_files
source = PhoibleBridge()
assert source.root is None
assert len(source.language('eng').inventories) == 9
assert len(source.inventory(160).refusals) == 9
assert len(source_files()) == 4
assert len(read_source('data/phoible.csv')) == 24578868
"""
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in ("IPAKIT_PHOIBLE", "PYTHONPATH")
    }
    subprocess.run(
        [sys.executable, "-I", "-S", "-c", code],
        cwd=tmp_path,
        env=env,
        check=True,
        capture_output=True,
    )
