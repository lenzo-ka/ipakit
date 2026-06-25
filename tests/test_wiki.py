"""Tests for Wikipedia link validation."""

import urllib.error
import urllib.request

import pytest
from ipakit import IPAFeatures


class TestWikiLinks:
    """Tests for Wikipedia documentation links."""

    @pytest.fixture
    def ipa(self) -> IPAFeatures:
        return IPAFeatures()

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

    @pytest.fixture
    def ipa(self) -> IPAFeatures:
        return IPAFeatures()

    def _check_url_exists(self, url: str) -> tuple[bool, str]:
        """Check if a URL exists (returns 200)."""
        try:
            req = urllib.request.Request(url, method="HEAD")
            req.add_header("User-Agent", "ipakit-test/1.0")
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status == 200, ""
        except urllib.error.HTTPError as e:
            return False, f"HTTP {e.code}"
        except Exception as e:
            return False, str(e)

    def test_reference_urls_exist(self, ipa: IPAFeatures) -> None:
        """All reference Wikipedia pages should exist."""
        missing = []
        for name, href in ipa.references.items():
            url = ipa.wiki_base + href
            exists, error = self._check_url_exists(url)
            if not exists:
                missing.append(f"{name}: {href} ({error})")

        assert not missing, "Missing Wikipedia pages:\n" + "\n".join(missing)

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
        missing = []
        for phone in sample_phones:
            if phone not in ipa.phones:
                continue
            href = ipa.phones[phone].features.get("href")
            if not href:
                continue
            url = ipa.wiki_base + href
            exists, error = self._check_url_exists(url)
            if not exists:
                missing.append(f"{phone}: {href} ({error})")

        assert not missing, "Missing Wikipedia pages:\n" + "\n".join(missing)

    def test_all_phone_urls_exist(self, ipa: IPAFeatures) -> None:
        """All phone Wikipedia pages should exist."""
        missing = []
        for symbol, phone in ipa.phones.items():
            href = phone.features.get("href")
            if not href:
                continue
            url = ipa.wiki_base + href
            exists, error = self._check_url_exists(url)
            if not exists:
                missing.append(f"{symbol}: {href} ({error})")

        assert not missing, "Missing Wikipedia pages:\n" + "\n".join(missing)

    def test_all_diacritic_urls_exist(self, ipa: IPAFeatures) -> None:
        """All diacritic Wikipedia pages should exist."""
        missing = []
        for symbol, diac in ipa.diacritics.items():
            href = diac.features.get("href")
            if not href:
                continue
            url = ipa.wiki_base + href
            exists, error = self._check_url_exists(url)
            if not exists:
                missing.append(f"{symbol}: {href} ({error})")

        assert not missing, "Missing Wikipedia pages:\n" + "\n".join(missing)
