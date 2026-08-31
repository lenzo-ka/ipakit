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


def _binary_guarded_files(tests: Path) -> dict[str, set[str]]:
    """Test files that skip themselves when an external binary is absent.

    The module guard above reads ``importorskip``, which names a Python module.
    A file can also gate itself on a program found through ``shutil.which``, and
    that form is invisible to it: the module is installed, so nothing reports a
    hole while every test in the file skips.

    A ``which`` call alone is not the pattern -- ``test_schema.py`` looks a
    validator up and then fails loudly when it is missing, which is the
    behavior wanted. What makes a file unreachable is looking one up and
    skipping on it, so both must be present.
    """
    guarded: dict[str, set[str]] = {}
    for path in sorted(tests.rglob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        if "skipif" not in text:
            continue
        binaries: set[str] = set()
        for node in ast.walk(ast.parse(text)):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            function = node.func
            if (
                isinstance(function, ast.Attribute)
                and function.attr == "which"
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                binaries.add(node.args[0].value)
        if binaries:
            guarded[path.relative_to(ROOT).as_posix()] = binaries
    return guarded


def _installed_binaries(job: str) -> set[str]:
    """Package names an apt-get step installs, which are the binaries we get."""
    return {
        package
        for group in re.findall(r"apt-get install(?:\s+-[A-Za-z-]+)*\s+([^\n]+)", job)
        for package in shlex.split(group)
        if not package.startswith("-")
    }


# A binary-gated file that CI genuinely cannot run, with the reason. An entry
# here is a declaration, not a silence: the file still skips, but the skip is
# stated and reviewable instead of being invisible. Keep it short -- anything
# CI could install belongs in a job, not here.
DECLARED_UNRUNNABLE = {
    "tests/test_espeak_binary.py": (
        "asserts espeak-ng 1.52.0 exactly, because the mnemonic-to-IPA "
        "agreement it checks was established against that build; "
        "ubuntu-latest ships 1.51, so installing the package makes these "
        "tests fail rather than pass"
    ),
}


def _runs_on_pull_request(job: str) -> bool:
    """Whether this job runs on a pull request at all.

    A job excluded from pull requests still installs its binaries on main and
    on the nightly, so a file it names is not unreachable -- but it cannot show
    those tests passing on the change that introduces them. Coverage that only
    appears after merge is not coverage a reviewer can see, so it does not
    count here.
    """
    return "github.event_name != 'pull_request'" not in job


def _unreachable_binary_guards(workflow: str) -> list[str]:
    coverage: list[tuple[list[str], set[str]]] = []
    for job in _job_blocks(workflow):
        if not _runs_on_pull_request(job):
            continue
        binaries = _installed_binaries(job)
        for line in job.splitlines():
            paths = _pytest_paths(line.strip())
            if paths is not None:
                coverage.append((paths, binaries))

    missing: list[str] = []
    for path, required in _binary_guarded_files(ROOT / "tests").items():
        if path in DECLARED_UNRUNNABLE:
            continue
        if not any(
            required <= provided
            and any(path == named or path.startswith(named) for named in paths)
            for paths, provided in coverage
        ):
            missing.append(f"{path}: {', '.join(sorted(required))}")
    return missing


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


def test_binary_guarded_files_run_in_a_job_that_installs_their_binary() -> None:
    """A file that skips on a missing program must have a job supplying it."""
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert _unreachable_binary_guards(workflow) == []


def test_every_declared_exemption_still_names_a_real_guarded_file() -> None:
    """An exemption for a file that no longer skips is a silence nobody needs."""
    guarded = _binary_guarded_files(ROOT / "tests")
    assert set(DECLARED_UNRUNNABLE) <= set(guarded), (
        f"exempted files that are no longer binary-gated: "
        f"{sorted(set(DECLARED_UNRUNNABLE) - set(guarded))}"
    )


def test_the_binary_guard_reports_a_file_that_loses_its_exemption() -> None:
    """Measure the predicate against a known hole.

    Dropping the exemption must surface the file, because nothing in CI
    installs espeak-ng. If this passes with the exemption in place and fails
    without it, the predicate is reading the workflow rather than the map.
    """
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    exempt = dict(DECLARED_UNRUNNABLE)
    try:
        DECLARED_UNRUNNABLE.clear()
        assert _unreachable_binary_guards(workflow) == [
            "tests/test_espeak_binary.py: espeak-ng"
        ]
    finally:
        DECLARED_UNRUNNABLE.update(exempt)


def test_the_full_suite_is_not_counted_as_pull_request_coverage() -> None:
    """A job excluded from pull requests cannot vouch for a file on a PR.

    The full suite installs and runs things the per-PR jobs do not, and its
    own comment says it never runs on a pull request. Counting it as coverage
    is how a file can be "covered" and still skip on every change that
    touches it.
    """
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    named = {
        re.match(r"(?m)^  ([A-Za-z0-9_-]+):", job).group(1): _runs_on_pull_request(job)
        for job in _job_blocks(workflow)
        if re.match(r"(?m)^  ([A-Za-z0-9_-]+):", job)
    }
    assert named["full-suite"] is False, "the full suite is gated off pull requests"
    assert named["test"] is True, "the per-PR test job must run on pull requests"
