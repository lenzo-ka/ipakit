import shutil
import subprocess
from pathlib import Path

import pytest
from scripts import tiergraph_pin


def test_declared_tiergraph_pin_matches_editable_shadow_or_skips_wheel():
    actual = tiergraph_pin.verify()
    if actual is None:
        pytest.skip(
            "tiergraph.__file__ is not inside a Git work tree; the wheel was "
            "installed directly from the pyproject.toml pin"
        )


def test_pin_guard_names_expected_actual_and_source_on_disagreement():
    source = Path("/synthetic/editable/tiergraph/__init__.py")
    expected = "0" * 40
    actual = "1" * 40

    with pytest.raises(tiergraph_pin.PinMismatch) as caught:
        tiergraph_pin.verify(
            expected=expected,
            source=source,
            resolve_worktree=lambda _: Path("/synthetic/editable"),
            resolve_head=lambda _: actual,
        )

    message = str(caught.value)
    assert expected in message
    assert actual in message
    assert str(source) in message


def test_wheel_install_is_a_loud_skip_not_a_silent_pass(capsys):
    source = Path("/synthetic/site-packages/tiergraph/__init__.py")
    result = tiergraph_pin.verify(
        expected="a" * 40,
        source=source,
        resolve_worktree=lambda _: None,
    )

    assert result is None
    output = capsys.readouterr().out
    assert "tiergraph pin [SKIP]" in output
    assert str(source) in output
    assert "wheel installs" in output


def test_unreadable_source_checkout_fails_instead_of_skipping(tmp_path):
    checkout = tmp_path / "tiergraph"
    source = checkout / "src" / "tiergraph" / "__init__.py"
    source.parent.mkdir(parents=True)
    source.write_text("", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(checkout)], check=True)
    subprocess.run(["git", "-C", str(checkout), "add", str(source)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(checkout),
            "-c",
            "user.name=Pin Test",
            "-c",
            "user.email=pin@example.test",
            "commit",
            "-qm",
            "wrong commit",
        ],
        check=True,
    )
    assert (
        subprocess.run(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        != "f" * 40
    )
    shutil.rmtree(checkout / ".git")

    with pytest.raises(tiergraph_pin.PinMismatch, match="git state cannot be read"):
        tiergraph_pin.verify(expected="f" * 40, source=source)


def test_wheel_under_repo_local_venv_skips_before_enclosing_git_lookup(capsys):
    source = Path(
        "/synthetic/repo/.venv/lib/python3.13/site-packages/tiergraph/__init__.py"
    )

    result = tiergraph_pin.verify(
        expected="a" * 40,
        source=source,
        resolve_worktree=lambda _: pytest.fail("wheel must not inspect enclosing Git"),
    )

    assert result is None
    assert "tiergraph pin [SKIP]" in capsys.readouterr().out


def test_short_pin_is_rejected(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\ndependencies = ["tiergraph @ git+https://example.test/tiergraph@abcdef0"]\n',
        encoding="utf-8",
    )

    with pytest.raises(tiergraph_pin.PinMismatch, match="full 40-character lowercase"):
        tiergraph_pin.pinned_sha(pyproject)


def test_source_worktree_must_contain_resolved_module():
    source = Path("/synthetic/tiergraph/src/tiergraph/__init__.py")

    with pytest.raises(tiergraph_pin.PinMismatch, match="does not contain"):
        tiergraph_pin.verify(
            expected="a" * 40,
            source=source,
            resolve_worktree=lambda _: Path("/unrelated/repository"),
        )
