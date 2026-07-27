"""The structural distance (design spec section 7): acceptance pins.

Constituents compare as whole bundles; alignment mode follows the unit
kinds; junctures carry the binding-sense term; secondary articulations
enter as weighted place components; bridge features unify dimensions
spelled as manner, property, or release.
"""

import itertools

import pytest
from ipakit import IPAFeatures
from ipakit.metric import bundle_distance, segment_metric


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


def D(ipa: IPAFeatures, a: str, b: str) -> float:
    return segment_metric(ipa, ipa.segment(a), ipa.segment(b))


class TestExactPins:
    def test_shares_one_articulation_is_half(self, ipa: IPAFeatures) -> None:
        # D(ɡ, ɡ͡b) = d_b(ɡ, b) / 2, exactly (unordered best-match with a
        # lifted singleton) - and symmetric between the two sharers.
        db = bundle_distance(
            ipa, ipa.segment("ɡ").constituents[0], ipa.segment("b").constituents[0]
        )
        assert D(ipa, "ɡ", "ɡ͡b") == pytest.approx(db / 2, abs=1e-12)
        assert D(ipa, "b", "ɡ͡b") == pytest.approx(
            bundle_distance(
                ipa,
                ipa.segment("b").constituents[0],
                ipa.segment("ɡ").constituents[0],
            )
            / 2,
            abs=1e-12,
        )

    def test_binding_sense_is_one_term(self, ipa: IPAFeatures) -> None:
        # Same constituents, different timing claim: one juncture mismatch
        # over three terms.
        assert D(ipa, "u͡i", "u͜i") == pytest.approx(1 / 3, abs=1e-12)

    def test_identity_is_zero(self, ipa: IPAFeatures) -> None:
        for s in ["a", "t͡s", "u͜i", "t͡s͜a", "ŋ͡m͡ɡ͡b"]:
            assert D(ipa, s, s) == 0.0


class TestOrderSemantics:
    def test_double_articulation_is_unordered(self, ipa: IPAFeatures) -> None:
        assert D(ipa, "u͡i", "i͡u") == 0.0
        assert D(ipa, "ɡ͡b", "b͡ɡ") == 0.0

    def test_phased_units_are_ordered(self, ipa: IPAFeatures) -> None:
        assert D(ipa, "n͡d", "d͡n") > 0.0
        assert D(ipa, "a͡t", "t͡a") > 0.0

    def test_cross_feature_association_survives(self, ipa: IPAFeatures) -> None:
        # ɡ͡p and k͡b have identical per-feature value sets; whole-bundle
        # alignment keeps them apart.
        assert D(ipa, "ɡ͡p", "k͡b") > 0.0

    def test_hybrid_n_ary_blocks(self, ipa: IPAFeatures) -> None:
        # Within-block order is notation; block order is meaning.
        assert D(ipa, "ŋ͡m͡ɡ͡b", "m͡ŋ͡b͡ɡ") == 0.0
        assert D(ipa, "ŋ͡m͡ɡ͡b", "ɡ͡b͡ŋ͡m") > 0.0

    def test_affricates_cluster_with_affricates(self, ipa: IPAFeatures) -> None:
        # Structural semantics: shared phase structure beats a shared bare
        # component.
        assert D(ipa, "t͡ʃ", "t͡s") < D(ipa, "t͡ʃ", "ʃ")
        assert D(ipa, "q͡χ", "t͡ʃ") < D(ipa, "q͡χ", "χ")


class TestSecondaryArticulation:
    def test_palatalization_moves_toward_palatal(self, ipa: IPAFeatures) -> None:
        # place(t, tʲ) = δ/3 < place(tʲ, c) = 2δ/3 < place(t, c) = δ shows
        # through the full D as a strict ordering.
        assert D(ipa, "t", "tʲ") < D(ipa, "tʲ", "c") < D(ipa, "t", "c")

    def test_both_sides_secondary(self, ipa: IPAFeatures) -> None:
        d = D(ipa, "tʲ", "kʷ")
        assert 0.0 < d < 1.0
        assert d == D(ipa, "kʷ", "tʲ")

    def test_secondary_never_outweighs_primary(self, ipa: IPAFeatures) -> None:
        assert D(ipa, "t", "tʲ") < D(ipa, "t", "c")


class TestBridges:
    def test_nasality_bridge(self, ipa: IPAFeatures) -> None:
        # ã (nasalized property) shares the nasality dimension with n
        # (nasal manner).
        assert D(ipa, "ã", "n") < D(ipa, "a", "n")

    def test_laterality_bridge(self, ipa: IPAFeatures) -> None:
        assert D(ipa, "tˡ", "l") < D(ipa, "t", "l")


class TestModifiers:
    def test_overriding_modifier_registers(self, ipa: IPAFeatures) -> None:
        assert D(ipa, "d", "d̥") > 0.0

    def test_additive_modifier_registers(self, ipa: IPAFeatures) -> None:
        assert D(ipa, "a", "ã") > 0.0

    def test_prosody_excluded(self, ipa: IPAFeatures) -> None:
        assert D(ipa, "a", "aː") == 0.0


class TestOrdinalScales:
    """Within-dimension ordering drives distance when the ordinal is
    sensible - and only true points on the continuum hold scale positions.
    Combined places (overlaps, not points) compare by expansion."""

    def test_overlap_values_hold_no_scale_position(self, ipa: IPAFeatures) -> None:
        pl = ipa.features["place"]
        one_step = pl.value_distance("dental", "alveolar")
        # labial-palatal / labial-velar no longer pad these intervals:
        assert pl.value_distance("palatal", "velar") == pytest.approx(one_step)
        assert pl.value_distance("velar", "uvular") == pytest.approx(one_step)

    def test_real_intermediate_places_keep_their_positions(
        self, ipa: IPAFeatures
    ) -> None:
        pl = ipa.features["place"]
        one_step = pl.value_distance("dental", "alveolar")
        # alveolo-palatal is a real single place between postalveolar and
        # palatal; labiodental between bilabial and dental.
        assert pl.value_distance("postalveolar", "palatal") == pytest.approx(
            2 * one_step
        )
        assert pl.value_distance("bilabial", "dental") == pytest.approx(2 * one_step)

    def test_combining_values_compare_by_expansion(self, ipa: IPAFeatures) -> None:
        pl = ipa.features["place"]
        assert pl.value_distance("bilabial+velar", "bilabial+velar") == 0.0
        assert pl.expand("bilabial+velar") == ("bilabial", "velar")
        # Expansion, not a scale step: the same value as comparing the tuple.
        assert pl.value_distance("bilabial+velar", "velar") == pl.value_distance(
            ("bilabial", "velar"), "velar"
        )

    def test_friendly_names_are_value_aliases(self, ipa: IPAFeatures) -> None:
        pl = ipa.features["place"]
        assert pl.value_distance("labial-velar", "bilabial+velar") == 0.0
        assert pl.expand("labial-velar") == ("bilabial", "velar")

    def test_combining_order_is_canonical(self, ipa: IPAFeatures) -> None:
        pl = ipa.features["place"]
        assert pl.combine({"velar", "bilabial"}) == "bilabial+velar"
        assert pl.combine({"palatal", "alveolar"}) == "alveolar+palatal"
        # A novel combination is expressible without a granted name.
        assert ipa.get_features("p͡t", with_defaults=False)["place"] == (
            "bilabial+alveolar"
        )


class TestReferenceFrame:
    """The ordinal scales ascend a declared reference frame: a left-facing
    oral tract (+x lips->glottis, +y jaw->palate)."""

    def test_axes_declared(self, ipa: IPAFeatures) -> None:
        assert ipa.features["place"].axis == "+x"
        assert ipa.features["backness"].axis == "+x"
        assert ipa.features["height"].axis == "+y"
        assert ipa.features["tone"].axis == "+y"
        assert ipa.features["manner"].axis == "+constriction"

    def test_height_ascends_y(self, ipa: IPAFeatures) -> None:
        h = ipa.features["height"]
        assert h.values[0] == "open" and h.values[-1] == "close"
        assert h.value_distance("open", "close") == 1.0
        # Phones are untouched by the declaration flip.
        assert ipa.get_features("i", with_defaults=False)["height"] == "close"

    def test_silence_holds_no_scale_position(self, ipa: IPAFeatures) -> None:
        m = ipa.features["manner"]
        # Absence of signal: equidistant from every real manner, adjacent
        # to none.
        assert m.value_distance("silence", "vowel") == 1.0
        assert m.value_distance("silence", "plosive") == 1.0
        assert m.value_distance("silence", "silence") == 0.0

    def test_release_and_airstream_are_categorical(self, ipa: IPAFeatures) -> None:
        r = ipa.features["release"]
        assert r.value_distance("aspirated", "no-audible") == r.value_distance(
            "aspirated", "breathy"
        )
        a = ipa.features["airstream"]
        assert a.value_distance("pulmonic", "implosive") == a.value_distance(
            "pulmonic", "ejective"
        )


class TestSagittalBridges:
    """The frame's axes are stored twice (place/backness on x,
    manner-constriction/height on y) in features that never co-occur;
    the sagittal bridges project both classes onto shared scalars so
    cross-class spatial proximity is visible."""

    def test_glide_nearer_its_vowel_than_a_stop_is(self, ipa: IPAFeatures) -> None:
        # j and i are nearly the same articulation; before the bridges a
        # voiceless alveolar stop scored closer to i than its own glide.
        assert D(ipa, "j", "i") < D(ipa, "t", "i")
        assert D(ipa, "w", "u") < D(ipa, "k", "u")

    def test_tongue_body_proximity_is_graded(self, ipa: IPAFeatures) -> None:
        # velar consonant ~ back vowel closer than alveolar ~ back vowel.
        assert D(ipa, "k", "u") < D(ipa, "t", "u")

    def test_secondary_articulation_does_not_relocate_the_body(
        self, ipa: IPAFeatures
    ) -> None:
        # ʲ shades the place term; the x-bridge reads primary components
        # only, so the t < tʲ < c ordering survives the bridges.
        assert D(ipa, "t", "tʲ") < D(ipa, "tʲ", "c") < D(ipa, "t", "c")


class TestProperties:
    PROBES = [
        "a",
        "t",
        "tʲ",
        "d̥",
        "t͡s",
        "t͡ɬ",
        "k͡p",
        "n͡d",
        "d͡n",
        "u͡i",
        "a͜ɪ",
        "u͜i",
        "t͡s͜a",
        "a͜ɪ͜ə",
        "ŋ͡m͡ɡ͡b",
        "k͡ǂ",
        "w",
        "ã",
    ]

    def test_symmetry_and_range(self, ipa: IPAFeatures) -> None:
        for a, b in itertools.combinations(self.PROBES, 2):
            d1, d2 = D(ipa, a, b), D(ipa, b, a)
            assert d1 == pytest.approx(d2, abs=1e-12), (a, b)
            assert 0.0 <= d1 <= 1.0, (a, b)

    def test_atomic_combined_place_bridge(self, ipa: IPAFeatures) -> None:
        # w carries scalar labial-velar; it compares component-wise against
        # the composed double articulation.
        d = D(ipa, "w", "k͡p")
        assert 0.0 < d < 1.0
        # Closer to the labial-velar unit than to a plain velar stop's
        # place-mate with no shared articulation structure.
        assert D(ipa, "w", "ɡ͡b") < D(ipa, "w", "t͡s")
