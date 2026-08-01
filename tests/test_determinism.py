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

FINGERPRINT_PROBE = """
from ipakit import IPAFeatures
from ipakit.metric import metric_fingerprint
ipa = IPAFeatures()
print(metric_fingerprint(ipa, list(ipa.phones)))
"""

PROBE = """
import ipakit
from ipakit import IPAFeatures
ipa = IPAFeatures()
pairs = [("p","b"),("s","z"),("t","d"),("k","g"),("m","n"),("l","ɫ"),
         ("i","u"),("a","ɑ"),("t͡ʃ","t͡s"),("w","ɥ"),("ɚ","ə"),("ç","c")]
print(";".join(f"{a}~{b}={ipakit.distance(a,b)!r}" for a, b in pairs))
"""


def _under(probe: str, seed: str) -> str:
    result = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        env={"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"},
        check=True,
    )
    return result.stdout.strip()


def _distances_under(seed: str) -> str:
    return _under(PROBE, seed)


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


class TestFingerprintSeedIndependence:
    """The feature-space fingerprint is derived data in a repository that
    pins the seed so derived data regenerates byte-identically. An
    order-dependent digest would sit quiet until CI shuffled, and then
    refuse every matrix ipakit ships."""

    def test_the_fingerprint_is_identical_across_hash_seeds(self) -> None:
        baseline = _under(FINGERPRINT_PROBE, "0")
        assert len(baseline) == 16, f"probe produced {baseline!r}"
        for seed in ("1", "2", "12345"):
            assert _under(FINGERPRINT_PROBE, seed) == baseline, f"seed {seed} diverged"
