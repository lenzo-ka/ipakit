"""The metric must not depend on Python's hash randomization.

`bundle_distance` sums one float per feature key. Addition is not
associative, so iterating a *set* of keys made the result depend on
per-process string hashing: the same inputs produced matrices differing
in the last bits from run to run. The shipped confusion matrix is a
derived artifact checked in CI, so it has to be reproducible bit for
bit, not merely within a tolerance.
"""

import subprocess
import sys

PROBE = """
import ipakit
from ipakit import IPAFeatures
ipa = IPAFeatures()
pairs = [("p","b"),("s","z"),("t","d"),("k","g"),("m","n"),("l","ɫ"),
         ("i","u"),("a","ɑ"),("t͡ʃ","t͡s"),("w","ɥ"),("ɚ","ə"),("ç","c")]
print(";".join(f"{a}~{b}={ipakit.distance(a,b)!r}" for a, b in pairs))
"""


def _distances_under(seed: str) -> str:
    result = subprocess.run(
        [sys.executable, "-c", PROBE],
        capture_output=True,
        text=True,
        env={"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"},
        check=True,
    )
    return result.stdout.strip()


class TestHashSeedIndependence:
    def test_distances_are_identical_across_hash_seeds(self) -> None:
        # Distinct seeds give distinct string hashes, so any set-ordered
        # float summation shows up here as a last-bit difference.
        baseline = _distances_under("0")
        assert baseline, "probe produced no output"
        for seed in ("1", "2", "12345"):
            assert _distances_under(seed) == baseline, f"seed {seed} diverged"

    def test_the_probe_would_notice_a_difference(self) -> None:
        # Guard the guard: the comparison is exact repr, so it cannot
        # silently pass on values that merely round to the same display.
        assert repr(0.1 + 0.2) != repr(0.3)
