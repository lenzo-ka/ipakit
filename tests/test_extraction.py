from pathlib import Path

import pytest
from ipakit.extraction import (
    BuildResult,
    SourceContentError,
    SourceError,
    SourceMissingError,
    SourceVersionError,
)


def test_result_checks_missing_changed_and_unclaimed(tmp_path: Path) -> None:
    result = BuildResult({Path("data/a.xml"): b"a"}, (Path("data/*.xml"),))
    assert result.stale(tmp_path) == [Path("data/a.xml")]
    (tmp_path / "data").mkdir()
    (tmp_path / "data/a.xml").write_bytes(b"a")
    assert result.stale(tmp_path) == []
    (tmp_path / "data/a.xml").write_bytes(b"wrong")
    (tmp_path / "data/stray.xml").write_bytes(b"stray")
    (tmp_path / "data/keep.txt").write_bytes(b"unowned")
    assert result.stale(tmp_path) == [Path("data/a.xml"), Path("data/stray.xml")]


@pytest.mark.parametrize("path", [Path("/absolute"), Path("../escape"), Path(".")])
def test_result_rejects_uncontained_paths(path: Path) -> None:
    with pytest.raises(ValueError, match="relative and contained"):
        BuildResult({path: b""})
    with pytest.raises(ValueError, match="relative and contained"):
        BuildResult({}, (path,))


def test_source_failures_are_catchable_and_distinct() -> None:
    errors = (SourceMissingError, SourceVersionError, SourceContentError)
    assert len({error.code for error in errors}) == len(errors)
    assert all(issubclass(error, (SourceError, ValueError)) for error in errors)


def test_result_copies_caller_owned_mapping() -> None:
    artifacts = {Path("safe"): b"safe"}
    result = BuildResult(artifacts)
    artifacts[Path("../escape")] = b"unsafe"
    assert dict(result.artifacts) == {Path("safe"): b"safe"}
