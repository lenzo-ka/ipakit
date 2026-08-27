"""Tests for Wikipedia link validation."""

import time
import urllib.error
import urllib.request

import pytest
from ipakit import IPAFeatures

#: Statuses that mean the page is genuinely not there.
_ABSENT_CODES = frozenset({404, 410})
#: How many times to re-ask when the answer was "not now" rather than "no".
_RETRY_ATTEMPTS = 3
#: Wikimedia asks that automated traffic identify itself and a way to be reached.
_USER_AGENT = "ipakit-test/1.0 (https://github.com/ogionllc/ipakit)"


class TestWikiLinks:
    """Tests for Wikipedia documentation links."""

    def test_wiki_base_loaded(self, ipa: IPAFeatures) -> None:
        """Wiki base URL should be loaded from XML."""
        assert ipa.wiki_base
        assert ipa.wiki_base.startswith("https://")
        assert "wikipedia.org" in ipa.wiki_base

    def test_references_loaded(self, ipa: IPAFeatures) -> None:
        """Reference links should be loaded."""
        assert len(ipa.references) > 0
        assert "IPA" in ipa.references
        assert "X-SAMPA" in ipa.references

    def test_phones_have_hrefs(self, ipa: IPAFeatures) -> None:
        """Most phones should have Wikipedia hrefs."""
        phones_with_href = sum(1 for p in ipa.phones.values() if p.features.get("href"))
        # At least 80% of phones should have hrefs
        assert phones_with_href / len(ipa.phones) > 0.8

    def test_diacritics_have_hrefs(self, ipa: IPAFeatures) -> None:
        """Most diacritics should have Wikipedia hrefs."""
        diacritics_with_href = sum(
            1 for d in ipa.diacritics.values() if d.features.get("href")
        )
        # At least 80% of diacritics should have hrefs
        assert diacritics_with_href / len(ipa.diacritics) > 0.8

    def _collect_all_hrefs(self, ipa: IPAFeatures) -> set[str]:
        """Collect all unique hrefs from the IPA data."""
        hrefs = set()
        for phone in ipa.phones.values():
            if h := phone.features.get("href"):
                hrefs.add(h)
        for diac in ipa.diacritics.values():
            if h := diac.features.get("href"):
                hrefs.add(h)
        for h in ipa.references.values():
            hrefs.add(h)
        return hrefs

    def test_hrefs_are_valid_format(self, ipa: IPAFeatures) -> None:
        """All hrefs should be valid Wikipedia article names."""
        hrefs = self._collect_all_hrefs(ipa)
        for href in hrefs:
            # Should not be a full URL (we use wiki_base prefix)
            assert not href.startswith("http"), f"href should be article name: {href}"
            # Should not have spaces (Wikipedia uses underscores)
            assert " " not in href, f"href should use underscores: {href}"
            # Should not be empty
            assert href, "href should not be empty"


@pytest.mark.slow
class TestWikiLinksNetwork:
    """Network tests to verify Wikipedia pages exist.

    Run with: pytest -m slow tests/test_wiki.py
    """

    #: Set once the host starts refusing traffic, so the rest of the run stops
    #: asking. Wikipedia answers for every phone and diacritic in the
    #: inventory; once it has said "slow down", continuing to probe is both
    #: rude and pointless, and the answers would be inconclusive anyway.
    _throttled = False

    def _check_url(self, url: str) -> tuple[str, str]:
        """Ask whether a page exists, distinguishing "no" from "cannot say".

        Returns one of ``"exists"``, ``"absent"`` or ``"inconclusive"`` with a
        reason. Only ``"absent"`` is a claim about the page; a rate limit, a
        server error or a timeout says nothing about whether the page is there,
        so it must not be reported as a missing page.
        """
        if type(self)._throttled:
            return "inconclusive", "host rate-limited earlier in this run"
        reason = ""
        for attempt in range(_RETRY_ATTEMPTS):
            try:
                req = urllib.request.Request(url, method="HEAD")
                req.add_header("User-Agent", _USER_AGENT)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status == 200:
                        return "exists", ""
                    return "inconclusive", f"HTTP {resp.status}"
            except urllib.error.HTTPError as e:
                if e.code in _ABSENT_CODES:
                    return "absent", f"HTTP {e.code}"
                reason = f"HTTP {e.code}"
                if e.code == 429 or e.code >= 500:
                    if attempt + 1 < _RETRY_ATTEMPTS:
                        self._wait_before_retry(e, attempt)
                        continue
                    type(self)._throttled = True
                return "inconclusive", reason
            except Exception as e:  # timeouts, DNS, connection resets
                reason = str(e)
                if attempt + 1 < _RETRY_ATTEMPTS:
                    self._wait_before_retry(None, attempt)
        return "inconclusive", reason

    @staticmethod
    def _wait_before_retry(error: urllib.error.HTTPError | None, attempt: int) -> None:
        """Back off, honoring ``Retry-After`` when the server sent one."""
        delay = 1.0 * (2**attempt)
        if error is not None:
            retry_after = error.headers.get("Retry-After") if error.headers else None
            if retry_after:
                try:
                    delay = min(float(retry_after), 10.0)
                except ValueError:
                    pass
        time.sleep(delay)

    @staticmethod
    def _report(missing: list[str], inconclusive: list[str]) -> None:
        """Fail on pages proven absent; skip when the network never answered."""
        assert not missing, "Missing Wikipedia pages:\n" + "\n".join(missing)
        if inconclusive:
            pytest.skip(
                f"{len(inconclusive)} page(s) could not be checked "
                f"(rate limit, server error or timeout):\n" + "\n".join(inconclusive)
            )

    def test_reference_urls_exist(self, ipa: IPAFeatures) -> None:
        """All reference Wikipedia pages should exist."""
        missing: list[str] = []
        inconclusive: list[str] = []
        for name, href in ipa.references.items():
            url = ipa.wiki_base + href
            status, error = self._check_url(url)
            if status == "absent":
                missing.append(f"{name}: {href} ({error})")
            elif status == "inconclusive":
                inconclusive.append(f"{name}: {href} ({error})")

        self._report(missing, inconclusive)

    def test_sample_phone_urls_exist(self, ipa: IPAFeatures) -> None:
        """Sample of phone Wikipedia pages should exist."""
        # Test a representative sample
        sample_phones = [
            "p",
            "b",
            "t",
            "d",
            "k",
            "ɡ",
            "m",
            "n",
            "s",
            "z",
            "f",
            "v",
            "ʃ",
            "ʒ",
            "i",
            "u",
            "a",
            "e",
            "o",
            "ə",
        ]
        missing: list[str] = []
        inconclusive: list[str] = []
        for phone in sample_phones:
            if phone not in ipa.phones:
                continue
            href = ipa.phones[phone].features.get("href")
            if not href:
                continue
            url = ipa.wiki_base + href
            status, error = self._check_url(url)
            if status == "absent":
                missing.append(f"{phone}: {href} ({error})")
            elif status == "inconclusive":
                inconclusive.append(f"{phone}: {href} ({error})")

        self._report(missing, inconclusive)

    def test_all_phone_urls_exist(self, ipa: IPAFeatures) -> None:
        """All phone Wikipedia pages should exist."""
        missing: list[str] = []
        inconclusive: list[str] = []
        for symbol, phone in ipa.phones.items():
            href = phone.features.get("href")
            if not href:
                continue
            url = ipa.wiki_base + href
            status, error = self._check_url(url)
            if status == "absent":
                missing.append(f"{symbol}: {href} ({error})")
            elif status == "inconclusive":
                inconclusive.append(f"{symbol}: {href} ({error})")

        self._report(missing, inconclusive)

    def test_all_diacritic_urls_exist(self, ipa: IPAFeatures) -> None:
        """All diacritic Wikipedia pages should exist."""
        missing: list[str] = []
        inconclusive: list[str] = []
        for symbol, diac in ipa.diacritics.items():
            href = diac.features.get("href")
            if not href:
                continue
            url = ipa.wiki_base + href
            status, error = self._check_url(url)
            if status == "absent":
                missing.append(f"{symbol}: {href} ({error})")
            elif status == "inconclusive":
                inconclusive.append(f"{symbol}: {href} ({error})")

        self._report(missing, inconclusive)
