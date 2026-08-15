"""Capture scripts are inert when imported by tools or test collection."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

FIXTURES = Path(__file__).with_name("fixtures")


def _fixture_files() -> dict[Path, bytes]:
    return {
        path.relative_to(FIXTURES): path.read_bytes()
        for path in FIXTURES.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }


def test_capture_scripts_do_no_work_at_import(monkeypatch) -> None:
    subprocess_calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []
    file_writes: list[tuple[str, Path]] = []

    def record_subprocess(
        kind: str,
        *args: object,
        **kwargs: object,
    ) -> None:
        subprocess_calls.append((kind, args, kwargs))

    def record_write_text(path: Path, *args: object, **kwargs: object) -> int:
        file_writes.append(("text", path))
        return 0

    def record_write_bytes(path: Path, *args: object, **kwargs: object) -> int:
        file_writes.append(("bytes", path))
        return 0

    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: record_subprocess("run", *a, **kw)
    )
    monkeypatch.setattr(
        subprocess, "Popen", lambda *a, **kw: record_subprocess("Popen", *a, **kw)
    )
    monkeypatch.setattr(Path, "write_text", record_write_text)
    monkeypatch.setattr(Path, "write_bytes", record_write_bytes)

    before = _fixture_files()
    scripts = sorted(FIXTURES.glob("_capture_*.py"))
    assert scripts
    for index, script in enumerate(scripts):
        spec = importlib.util.spec_from_file_location(
            f"_capture_import_{index}", script
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

    assert subprocess_calls == []
    assert file_writes == []
    assert _fixture_files() == before
