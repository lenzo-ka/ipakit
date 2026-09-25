"""``ipakit --version`` reports the version the installed package declares."""

import subprocess
import sys

import ipakit


def test_version_flag_prints_the_package_version_and_exits_zero():
    result = subprocess.run(
        [sys.executable, "-m", "ipakit", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == f"ipakit {ipakit.__version__}"
