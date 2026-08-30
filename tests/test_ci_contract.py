"""Predicates over the CI configuration and its declared environments."""

from __future__ import annotations

import ast
import re
import shlex
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _requirement_name(requirement: str) -> str:
    match = re.match(r"[A-Za-z0-9_.-]+", requirement)
    assert match is not None, requirement
    return match.group().lower().replace("_", "-")


def _provided_modules(project: dict[str, object], selected: set[str]) -> set[str]:
    optional = project["project"]["optional-dependencies"]  # type: ignore[index]
    pending = list(selected)
    requirements = list(project["project"].get("dependencies", ()))  # type: ignore[union-attr,index]
    requirements.extend(project["build-system"].get("requires", ()))  # type: ignore[union-attr,index]
    seen: set[str] = set()
    while pending:
        extra = pending.pop()
        if extra in seen:
            continue
        seen.add(extra)
        for requirement in optional[extra]:  # type: ignore[index]
            recursive = re.fullmatch(r"ipakit\[([^]]+)]", requirement)
            if recursive:
                pending.extend(part.strip() for part in recursive.group(1).split(","))
            else:
                requirements.append(requirement)
    distributions = {_requirement_name(str(item)) for item in requirements}
    modules = {name.replace("-", "_") for name in distributions}
    # Distribution names are not required to equal their import names.
    if "icukit-pyicu" in distributions:
        modules.add("icu")
    return modules


def _guarded_files(tests: Path) -> dict[str, set[str]]:
    guarded: dict[str, set[str]] = {}
    for path in tests.rglob("*.py"):
        modules: set[str] = set()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            function = node.func
            if (
                isinstance(function, ast.Attribute)
                and function.attr == "importorskip"
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                modules.add(node.args[0].value.split(".", 1)[0])
        if modules:
            guarded[path.relative_to(ROOT).as_posix()] = modules
    return guarded


def _job_blocks(workflow: str) -> list[str]:
    starts = list(re.finditer(r"(?m)^  [A-Za-z0-9_-]+:\s*$", workflow))
    return [
        workflow[
            start.start() : (
                starts[index + 1].start() if index + 1 < len(starts) else None
            )
        ]
        for index, start in enumerate(starts)
    ]


def _pytest_paths(command: str) -> list[str] | None:
    if not re.match(r"^(?:(?:- )?run:\s*)?(?:python -m )?pytest(?:\s|$)", command):
        return None
    words = shlex.split(command)
    try:
        start = words.index("pytest")
    except ValueError:
        return None
    paths = [
        word for word in words[start + 1 :] if word.startswith(("tests/", "ipakit/"))
    ]
    return paths or ["tests/"]


def _unreachable_guards(workflow: str, project_text: str) -> list[str]:
    project = tomllib.loads(project_text)
    coverage: list[tuple[list[str], set[str]]] = []
    for job in _job_blocks(workflow):
        extras = {
            extra
            for group in re.findall(r"pip install -e [\"']?\.\[([^]]+)]", job)
            for extra in group.split(",")
        }
        modules = _provided_modules(project, extras)
        for line in job.splitlines():
            paths = _pytest_paths(line.strip())
            if paths is not None:
                coverage.append((paths, modules))

    missing: list[str] = []
    for path, required in _guarded_files(ROOT / "tests").items():
        if not any(
            required <= provided
            and any(path == named or path.startswith(named) for named in paths)
            for paths, provided in coverage
        ):
            missing.append(f"{path}: {', '.join(sorted(required))}")
    return missing


def test_importorskip_files_run_in_a_job_that_installs_their_modules() -> None:
    """A skipped dependency must be present in at least one job naming the file."""
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert _unreachable_guards(workflow, project) == []


def test_ci_guard_detects_a_file_removed_from_its_only_capable_job() -> None:
    """Measure the predicate against a configuration with a known hole."""
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    broken = workflow.replace(" tests/test_panphon_live_geometry.py", "", 1)
    assert _unreachable_guards(broken, project) == [
        "tests/test_panphon_live_geometry.py: panphon"
    ]
