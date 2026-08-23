"""The tier vocabulary: names an interval may be declared on.

A tier is not a rung on the ``level`` ladder. ``level`` is ordinal and is
read as one in two places; a syllable, a mora and a morph do not nest, so
ranking them would let a comparison answer that a morph "reaches" a
syllable, which is not a fact about anything.
"""

import itertools
from pathlib import Path

import pytest
from ipakit import IPAFeatures

SHIPPED = Path(__file__).resolve().parents[1] / "ipakit" / "data" / "ipa.xml"


@pytest.mark.slow
class TestTheTierVocabularyIsDeclaredAndNominal:
    def test_the_tier_names_are_declared_rather_than_written_in_python(
        self, ipa: IPAFeatures
    ) -> None:
        assert "tier" in ipa.features, "no tier feature is declared"
        assert set(ipa.features["tier"].values) >= {"syllable", "mora", "morph"}

    def test_a_tier_is_nominal_so_nothing_can_rank_two_of_them(
        self, ipa: IPAFeatures
    ) -> None:
        """``categorical`` is what says the values compare as unordered.

        If this ever reads ``ordinal``, something can take an index into
        the values and call the difference a distance -- which would put a
        mora between a syllable and a segment, where it does not belong.
        """
        assert ipa.features["tier"].type == "categorical"
        assert ipa.features["tier"].axis is None

    def test_a_tier_is_structural_so_it_reaches_no_bundle(
        self, ipa: IPAFeatures
    ) -> None:
        """The mechanism that keeps the metric out of this.

        docs/design/tiers.md §7 commits that a language declaring tiers
        moves no distance. That holds by construction, not by care: a
        structural feature is excluded from every phone bundle.
        """
        assert ipa.features["tier"].mode == "structural"
        assert not any("tier" in ipa.get_features(p) for p in ipa.phones)

    def test_declaring_the_tier_vocabulary_moved_no_distance(self) -> None:
        """Measured over every pair, against the inventory without it.

        The control is in the sibling test below: the same comparison over
        a perturbed inventory must report a large non-zero, or a zero here
        means only that the comparison cannot see.
        """
        shipped = IPAFeatures(xml_path=SHIPPED)
        stripped = _without_the_tier_feature()
        shared = [p for p in shipped.phones if p in stripped.phones]
        moved = sum(
            1
            for a, b in itertools.combinations(shared, 2)
            if abs(shipped.distance(a, b) - stripped.distance(a, b)) > 1e-12
        )
        assert len(shared) > 100, f"inventory did not load: {len(shared)}"
        assert moved == 0, f"declaring a structural feature moved {moved} pairs"

    def test_the_same_comparison_sees_a_perturbation(self, tmp_path: Path) -> None:
        """The control. Moving an arc phones actually read must move pairs."""
        text = SHIPPED.read_text()
        assert 'name="velar" arc-landmark="velum-rest"' in text
        moved_file = tmp_path / "perturbed.xml"
        moved_file.write_text(
            text.replace(
                'name="velar" arc-landmark="velum-rest"',
                'name="velar" arc="0.60"',
            )
        )
        shipped = IPAFeatures(xml_path=SHIPPED)
        perturbed = IPAFeatures(xml_path=moved_file)
        shared = [p for p in shipped.phones if p in perturbed.phones]
        moved = sum(
            1
            for a, b in itertools.combinations(shared, 2)
            if abs(shipped.distance(a, b) - perturbed.distance(a, b)) > 1e-12
        )
        assert moved > 1000, f"the comparison cannot see a moved arc: {moved}"


class TestTheTierNameDoesNotSilentlyShadowTheBoundaryLevel:
    """``syllable`` is now claimed by two features, and that is deliberate.

    ``level=syllable`` is a boundary's strength; ``tier=syllable`` is the
    tier a span sits on. Neither declares ``bare``, so a plain ``syllable``
    is refused rather than resolved by which one ipa.xml declares first.
    """

    def test_both_features_claim_it(self, ipa: IPAFeatures) -> None:
        claimants = {name for name, _ in ipa._claimants("syllable")}
        assert claimants == {"level", "tier"}, claimants

    def test_and_so_the_bare_term_is_refused_naming_both(
        self, ipa: IPAFeatures
    ) -> None:
        with pytest.raises(ValueError) as caught:
            ipa.phones_matching(["syllable"])
        message = str(caught.value)
        assert "ambiguous" in message
        assert "level" in message and "tier" in message

    def test_neither_claims_it_bare(self, ipa: IPAFeatures) -> None:
        assert "syllable" not in ipa.features["level"].bare
        assert "syllable" not in ipa.features["tier"].bare


def _without_the_tier_feature() -> IPAFeatures:
    """The shipped inventory with the tier declaration removed."""
    import re
    import tempfile

    text = SHIPPED.read_text()
    stripped = re.sub(
        r'\n\s*<feature name="tier".*?</feature>\n', "\n", text, flags=re.DOTALL
    )
    assert stripped != text, "the tier feature was not found to remove"
    handle = tempfile.NamedTemporaryFile(
        "w", suffix=".xml", delete=False, encoding="utf-8"
    )
    handle.write(stripped)
    handle.close()
    return IPAFeatures(xml_path=Path(handle.name))


class TestDeclaringATierDoesNotInvalidateASavedMatrix:
    """§7's promise, held operationally rather than only in the numbers.

    ``docs/design/tiers.md`` §7 commits that a language declaring a tier
    moves no distance. That was true of the distances and false of the
    reader: the feature-space fingerprint hashed every declared feature,
    so declaring ``tier`` moved 0 of 9591 pairs and still refused every
    saved matrix. A structural feature cannot reach the metric -- the mode
    gate drops it before a bundle is built -- so the digest now skips it,
    and the two agree by construction.
    """

    def test_a_new_structural_feature_leaves_the_fingerprint_alone(
        self, ipa: IPAFeatures, tmp_path: Path
    ) -> None:
        from ipakit.metric import metric_fingerprint

        phones = tuple(ipa.phones)
        without = _load(_strip_the_tier_feature(), tmp_path / "without.xml")
        assert metric_fingerprint(ipa, phones) == metric_fingerprint(without, phones)

    def test_but_changing_a_feature_out_of_structural_does_not(
        self, ipa: IPAFeatures, tmp_path: Path
    ) -> None:
        """The control, and the case the guard exists for.

        Skipping structural features would be worthless if it also hid a
        feature *becoming* non-structural, which does reprice things. It
        does not: the flip moves the feature into the digested set.
        """
        from ipakit.metric import metric_fingerprint

        text = SHIPPED.read_text()
        assert 'name="tier" short="tir" type="categorical" mode="structural"' in text
        flipped = _load(
            text.replace(
                'name="tier" short="tir" type="categorical" mode="structural"',
                'name="tier" short="tir" type="categorical" mode="additive"',
            ),
            tmp_path / "flipped.xml",
        )
        phones = tuple(ipa.phones)
        assert metric_fingerprint(ipa, phones) != metric_fingerprint(flipped, phones)

    def test_and_a_real_metric_change_still_moves_it(
        self, ipa: IPAFeatures, tmp_path: Path
    ) -> None:
        """The second control: the digest has not been made blind in general."""
        from ipakit.metric import metric_fingerprint

        text = SHIPPED.read_text()
        assert 'name="velar" arc-landmark="velum-rest"' in text
        moved = _load(
            text.replace(
                'name="velar" arc-landmark="velum-rest"',
                'name="velar" arc="0.60"',
            ),
            tmp_path / "moved.xml",
        )
        phones = tuple(ipa.phones)
        assert metric_fingerprint(ipa, phones) != metric_fingerprint(moved, phones)


def _strip_the_tier_feature() -> str:
    import re

    text = SHIPPED.read_text()
    stripped = re.sub(
        r'\n\s*<feature name="tier".*?</feature>\n', "\n", text, flags=re.DOTALL
    )
    assert stripped != text, "the tier feature was not found to remove"
    return stripped


def _load(text: str, where: Path) -> IPAFeatures:
    where.write_text(text, encoding="utf-8")
    return IPAFeatures(xml_path=where)
