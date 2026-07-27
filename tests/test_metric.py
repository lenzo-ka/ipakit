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

    def test_anchored_distance_follows_anatomy_not_label_count(
        self, ipa: IPAFeatures
    ) -> None:
        pl = ipa.features["place"]
        # Steps are not uniform: the lips-to-teeth move is tiny, the
        # velum-to-uvula move larger, though both are "one label" apart.
        assert pl.value_distance("bilabial", "labiodental") < pl.value_distance(
            "velar", "uvular"
        )
        # Overlaps hold no position and never pad an interval.
        assert pl.value_distance("bilabial", "glottal") == pytest.approx(1.0)

    def test_places_are_monotone_along_the_tract(self, ipa: IPAFeatures) -> None:
        pl = ipa.features["place"]
        order = ["bilabial", "dental", "alveolar", "palatal", "velar", "glottal"]
        for i in range(len(order) - 2):
            near = pl.value_distance(order[i], order[i + 1])
            far = pl.value_distance(order[i], order[i + 2])
            assert near < far, (order[i], order[i + 1], order[i + 2])

    def test_anchored_distances_survive_inventory_growth(
        self, ipa: IPAFeatures
    ) -> None:
        # The property an index scale cannot have: adding a value leaves
        # every existing distance untouched, because anchors are absolute.
        pl = ipa.features["place"]
        before = pl.value_distance("bilabial", "velar")
        grown = type(pl)(
            name="place",
            values=[*pl.values, "fictional"],
            type="ordinal",
            coordinates={**pl.coordinates, "fictional": {"arc": 0.6}},
        )
        assert grown.value_distance("bilabial", "velar") == pytest.approx(before)

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


class TestSilence:
    """Silence is not a speech sound: no articulatory defaults, no bridge
    features, no tract position. Substituting it for a phone costs what
    deleting the phone costs."""

    def test_maximally_distant_from_every_speech_sound(self, ipa: IPAFeatures) -> None:
        for other in ["p", "a", "s", "t͡s", "w", "i", "k͡p", "tʲ"]:
            assert D(ipa, "␣", other) == 1.0, other

    def test_identical_to_itself(self, ipa: IPAFeatures) -> None:
        assert D(ipa, "␣", "␣") == 0.0

    def test_carries_no_articulatory_defaults(self, ipa: IPAFeatures) -> None:
        feats = ipa.get_features("␣", with_defaults=True)
        assert feats == {"manner": "silence", "class": "phone"}
        # A speech sound still gets its defaults.
        assert ipa.get_features("p", with_defaults=True)["rounded"] == "-"

    def test_has_no_tract_position_but_draws_at_rest(self, ipa: IPAFeatures) -> None:
        from ipakit.tract import head, tract_point

        bundle = ipa.segment("␣").constituents[0].bundle(ipa)
        point = tract_point(ipa, bundle)
        # Featurally null: no articulatory position at all.
        assert not point.placed
        assert head().project(point) is None
        # But a renderer still has somewhere to draw it: the rest posture
        # (jaw and lips closed, tongue neutral), which is head anatomy,
        # not phone features - and the home position for animations.
        assert head().project(point, at_rest=True) is not None
        assert head().rest is not None and head().rest.lips == "closed"


class TestTractSpace:
    """Phones sit in a normalized, head-independent tract space; heads
    project it to 2D for rendering and never affect distance."""

    def test_anchors_follow_anatomy(self, ipa: IPAFeatures) -> None:
        from ipakit.tract import tract_point

        def point(sym: str):
            return tract_point(ipa, ipa.segment(sym).constituents[0].bundle(ipa))

        # Arc ascends lips -> glottis.
        arcs = [point(s).arc for s in ["p", "t", "k", "q", "ʔ"]]
        assert arcs == sorted(arcs)
        # Offset ascends open -> closed across the classes.
        assert point("a").offset < point("i").offset < point("j").offset
        assert point("j").offset < point("s").offset <= point("t").offset

    def test_combining_place_sits_between_its_components(
        self, ipa: IPAFeatures
    ) -> None:
        from ipakit.tract import tract_point

        def arc(sym: str):
            return tract_point(ipa, ipa.segment(sym).constituents[0].bundle(ipa)).arc

        assert arc("p") < arc("w") < arc("k")

    def test_heads_project_without_touching_distance(self, ipa: IPAFeatures) -> None:
        from ipakit.tract import head, heads, tract_point

        assert set(heads()) >= {"adult-male", "adult-female", "child"}
        bundle = ipa.segment("t").constituents[0].bundle(ipa)
        point = tract_point(ipa, bundle)
        positions = {
            name: head(name).project(point) for name in ("adult-male", "child")
        }
        # Different heads place the same phone differently...
        assert positions["adult-male"] != positions["child"]
        # ...but the phone's own coordinates, which distance uses, are one.
        assert point.arc is not None and point.offset is not None

    def test_child_tract_is_shorter(self, ipa: IPAFeatures) -> None:
        from ipakit.tract import head

        assert head("child").length_cm < head("adult-female").length_cm
        assert head("adult-female").length_cm < head("adult-male").length_cm


class TestArticulator:
    """Place names the constriction target; the articulator names the
    organ that gets there. The two coincide by convention for most
    sounds, and where they do not, the metric can now see it."""

    def test_places_declare_their_default_articulator(self, ipa: IPAFeatures) -> None:
        from ipakit.tract import tract_point

        def organ(sym: str) -> str | None:
            return tract_point(
                ipa, ipa.segment(sym).constituents[0].bundle(ipa)
            ).articulator

        assert organ("p") == "lower-lip"
        assert organ("t") == "tongue-tip"
        assert organ("ʃ") == "tongue-blade"
        assert organ("k") == "tongue-dorsum"
        assert organ("ħ") == "tongue-root"
        assert organ("ʔ") == "vocal-folds"

    def test_linguolabial_overrides_the_default(self, ipa: IPAFeatures) -> None:
        from ipakit.tract import tract_point

        point = tract_point(ipa, ipa.segment("t̼").constituents[0].bundle(ipa))
        # Tongue to the upper lip: labial target, lingual articulator.
        assert point.articulator == "tongue-tip"
        assert point.arc == pytest.approx(0.0)
        # And it is no longer indistinguishable from a bilabial stop.
        assert D(ipa, "p", "t̼") > 0.0

    def test_apical_and_laminal_are_visible(self, ipa: IPAFeatures) -> None:
        # Same place, different part of the tongue - invisible before.
        assert D(ipa, "t̺", "t̻") > 0.0

    def test_combining_place_combines_articulators(self, ipa: IPAFeatures) -> None:
        from ipakit.tract import tract_point

        point = tract_point(ipa, ipa.segment("w").constituents[0].bundle(ipa))
        # A labial-velar moves the lower lip and the dorsum both.
        assert point.articulator == "lower-lip+tongue-dorsum"


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
