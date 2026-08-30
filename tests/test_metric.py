"""The structural distance (design spec section 7): acceptance pins.

Constituents compare as whole bundles; alignment mode follows the unit
kinds; junctures carry the binding-sense term; secondary articulations
enter as weighted place components; bridge features unify dimensions
spelled as manner, property, or release.
"""

import itertools

import ipakit.metric as metric
import pytest
from ipakit import IPAFeatures
from ipakit.constants import DATA_DIR
from ipakit.metric import (
    SECONDARY_WEIGHT,
    _arity_base,
    _metric_bundle,
    _nearest_part_cost,
    bundle_distance,
    metric_fingerprint,
    segment_metric,
    segment_terms,
)
from scripts.invariants import check_fusion_arity


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


def D(ipa: IPAFeatures, a: str, b: str) -> float:
    return segment_metric(ipa, ipa.segment(a), ipa.segment(b))


class TestExactPins:
    def test_sharing_stays_graded_beside_the_arity_base(self, ipa: IPAFeatures) -> None:
        # D(ɡ, ɡ͡b) = A + d_b(ɡ, b) / 2, exactly. The new constituent
        # has categorical mass, while its identity still supplies the old
        # graded sharing term.
        db = bundle_distance(
            ipa, ipa.segment("ɡ").constituents[0], ipa.segment("b").constituents[0]
        )
        assert _arity_base(ipa) == pytest.approx(1 / 20, abs=1e-12)
        assert D(ipa, "ɡ", "ɡ͡b") == pytest.approx(_arity_base(ipa) + db / 2, abs=1e-12)
        assert D(ipa, "b", "ɡ͡b") == pytest.approx(
            _arity_base(ipa)
            + bundle_distance(
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
        assert segment_terms(ipa, ipa.segment("u͡i"), ipa.segment("u͜i")) == [
            ("matched part a[0]~b[0]", "u", "u", 0.0),
            ("matched part a[1]~b[1]", "i", "i", 0.0),
            ("juncture a[0]~b[0]", "fuse", "seq", 1.0),
        ]

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


class TestMaterialBudget:
    def test_every_shipped_composite_pair_reconstructs_exactly(
        self, ipa: IPAFeatures
    ) -> None:
        """Flat report rows are exactly the outer metric terms, once each."""
        checked = 0
        phones = list(ipa.phones)
        for i, left in enumerate(phones):
            for right in phones[i:]:
                x, y = ipa.segment(left), ipa.segment(right)
                if len(x.constituents) == 1 and len(y.constituents) == 1:
                    continue
                rows = segment_terms(ipa, x, y)
                reconstructed = sum(row[3] for row in rows) / len(rows)
                assert reconstructed == segment_metric(ipa, x, y), (left, right)
                assert all(row[0] != "segmental" for row in rows)
                checked += 1
        assert checked == 2944

    def test_composites_are_nearer_their_own_atomic_constituents(
        self, ipa: IPAFeatures
    ) -> None:
        """No unrelated atomic phone without a shared manner beats a part."""
        checked = 0
        atomic = {
            symbol: ipa.segment(symbol)
            for symbol in ipa.phones
            if len(ipa.segment(symbol).constituents) == 1
        }
        for symbol in ipa.phones:
            composite = ipa.segment(symbol)
            if len(composite.constituents) < 2:
                continue
            bases = {part.base for part in composite.constituents}
            manners = {
                part.bundle(ipa, with_defaults=True).get("manner")
                for part in composite.constituents
            }
            for base in bases:
                own = D(ipa, symbol, base)
                for other, segment in atomic.items():
                    manner = (
                        segment.constituents[0]
                        .bundle(ipa, with_defaults=True)
                        .get("manner")
                    )
                    if other in bases or manner in manners:
                        continue
                    checked += 1
                    assert own < D(ipa, symbol, other), (symbol, base, other)
        assert checked > 3000, f"budget sweep checked only {checked} comparisons"

    def test_an_unmatched_part_never_exceeds_a_real_comparison(
        self, ipa: IPAFeatures
    ) -> None:
        """The orphan price is bounded by comparisons actually available."""
        checked = 0
        for symbol in ipa.phones:
            segment = ipa.segment(symbol)
            if len(segment.constituents) < 2:
                continue
            parts = tuple(ipa.segment(part.base) for part in segment.constituents)
            for part in parts:
                available = [segment_metric(ipa, part, other) for other in parts]
                charged = _nearest_part_cost(ipa, part, parts)
                checked += 1
                assert charged <= max(available), (symbol, part, charged, available)
        assert checked > 30, f"budget sweep checked only {checked} parts"

    def test_expected_gap_geometry(self, ipa: IPAFeatures) -> None:
        assert D(ipa, "t͡s", "t") == pytest.approx(0.2629, abs=0.00005)
        assert D(ipa, "t͡ʃ", "ʃ") == pytest.approx(0.2652, abs=0.00005)
        assert D(ipa, "t͡ʃ", "ʃ") < D(ipa, "t͡ʃ", "i")
        assert D(ipa, "t͡ʃ", "t͡s") == pytest.approx(0.0030, abs=0.00005)

    def test_adding_an_articulator_costs_at_least_a_release_phase(
        self, ipa: IPAFeatures
    ) -> None:
        """Every unordered one-to-two pair clears the independent release price."""
        release = ipa.distance("t", "tʰ")
        checked = 0
        for left, right in itertools.combinations(ipa.phones, 2):
            x, y = ipa.segment(left), ipa.segment(right)
            x_speech = ipa.get_features(left).get("manner") != "silence"
            y_speech = ipa.get_features(right).get("manner") != "silence"
            if (
                not x_speech
                or not y_speech
                or x.phased
                or y.phased
                or {len(x.constituents), len(y.constituents)}
                != {
                    1,
                    2,
                }
            ):
                continue
            checked += 1
            assert ipa.distance(left, right) >= release, (left, right)
        assert checked == 345

    def test_invariant_5_catches_a_weakened_arity_term(
        self, ipa: IPAFeatures, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A zero perturbation fails the public-distance check."""
        monkeypatch.setattr(metric, "_arity_base", lambda _: 0.0)
        assert not check_fusion_arity(ipa)

    @pytest.mark.slow
    def test_full_matrix_mover_class_is_declared_before_the_diff(
        self, ipa: IPAFeatures, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Only unequal-arity comparisons on the unordered branch may move.

        In the shipped inventory that is precisely a speech atom paired with a
        single-phase fusion. Silence remains maximally distant by its earlier
        categorical rule. Equal-arity fusion pairs retain their graded sharing
        distance, and every ordered/phased comparison is outside this lane.

        The audit computes both matrices and requires their diff to equal that
        declared class, so either a missed member or any movement outside it is
        a failure rather than a count-preserving substitution.
        """
        phones = list(ipa.phones)
        pairs = list(itertools.combinations(phones, 2))
        active = {pair: ipa.distance(*pair) for pair in pairs}
        monkeypatch.setattr(metric, "_arity_base", lambda _: 0.0)
        uncharged = {pair: ipa.distance(*pair) for pair in pairs}
        expected = set()
        for i, left in enumerate(phones):
            x = ipa.segment(left)
            for right in phones[i + 1 :]:
                y = ipa.segment(right)
                x_speech = ipa.get_features(left).get("manner") != "silence"
                y_speech = ipa.get_features(right).get("manner") != "silence"
                is_expected = (
                    x_speech
                    and y_speech
                    and not (x.phased or y.phased)
                    and len(x.children) != len(y.children)
                )
                if is_expected:
                    expected.add((left, right))
        movers = {
            pair
            for pair in pairs
            if active[pair] != pytest.approx(uncharged[pair], abs=1e-12)
        }
        assert movers == expected
        assert len(movers) == 345


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

    def test_secondary_counted_once(self, ipa: IPAFeatures) -> None:
        # The articulation enters as exactly one weighted component. Twice
        # would push tʲ away from c; not at all would erase it.
        for unit, expected in [
            ("tʲ", (("alveolar", 1.0), ("palatal", SECONDARY_WEIGHT))),
            ("ɫ", (("alveolar", 1.0), ("velar", SECONDARY_WEIGHT))),
        ]:
            _, components = _metric_bundle(ipa, ipa.segment(unit).constituents[0])
            assert components == expected

    def test_inherent_secondary_registers(self, ipa: IPAFeatures) -> None:
        # ɫ spells velarization into the base phone rather than as a
        # modifier; the metric has to see it either way.
        assert D(ipa, "l", "ɫ") > 0.0
        assert D(ipa, "l", "ɫ") == D(ipa, "l", "lˠ")

    def test_spellings_of_one_sound_coincide(self, ipa: IPAFeatures) -> None:
        # Inherent, modifier-letter, and combining-diacritic velarization
        # are three spellings of the same sound.
        for spelling in ["lˠ", "l̴"]:
            assert D(ipa, "ɫ", spelling) == 0.0

    def test_every_secondary_diacritic_registers(self, ipa: IPAFeatures) -> None:
        # No secondary articulation is silently dropped: whatever key a
        # diacritic contributes, applying it has to move the segment.
        marks = [
            symbol
            for symbol, mark in ipa.diacritics.items()
            if set(mark.features) & set(ipa.secondary_places)
        ]
        assert marks
        for mark in marks:
            assert D(ipa, "t", "t" + mark) > 0.0


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

    def test_a_prosodic_rider_bears_graded_distance(self, ipa: IPAFeatures) -> None:
        # A prosodic-tier mark rides on the unit and bears distance (#190):
        # length long vs unmarked is a step on the length ordinal, graded --
        # one tier among the unit's features -- rather than excluded.
        d = D(ipa, "a", "aː")
        assert 0.0 < d < 0.2


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
        assert pl.value_distance("bilabial^velar", "bilabial^velar") == 0.0
        assert pl.expand("bilabial^velar") == ("bilabial", "velar")
        # Expansion, not a scale step: the same value as comparing the tuple.
        assert pl.value_distance("bilabial^velar", "velar") == pl.value_distance(
            ("bilabial", "velar"), "velar"
        )

    def test_friendly_names_are_value_aliases(self, ipa: IPAFeatures) -> None:
        pl = ipa.features["place"]
        assert pl.value_distance("labial-velar", "bilabial^velar") == 0.0
        assert pl.expand("labial-velar") == ("bilabial", "velar")

    def test_combining_order_is_canonical(self, ipa: IPAFeatures) -> None:
        pl = ipa.features["place"]
        assert pl.combine({"velar", "bilabial"}) == "bilabial^velar"
        assert pl.combine({"palatal", "alveolar"}) == "alveolar^palatal"
        # A novel combination is expressible without a granted name.
        assert ipa.get_features("p͡t", with_defaults=False)["place"] == (
            "bilabial^alveolar"
        )


class TestCombiningSpellings:
    """A combining value is its components joined by the combiner, so the
    spelling has to hold up as a spelling. Structure is refused; a merely
    undeclared component is not."""

    MALFORMED = ("", "^", "a^", "^a", "a^^b", "bilabial^", "^bilabial")

    @pytest.mark.parametrize("value", MALFORMED)
    def test_expand_refuses_malformed_spellings(
        self, ipa: IPAFeatures, value: str
    ) -> None:
        # An empty component names nothing under any data. Answering it
        # (expand("") was ("",), expand("a^^b") was ("a", "", "b")) fed a
        # phantom component into the best-match mean, and a typo came back
        # as a mid-range number that read like a measurement.
        pl = ipa.features["place"]
        with pytest.raises(ValueError, match="malformed value"):
            pl.expand(value)

    @pytest.mark.parametrize("value", MALFORMED)
    def test_value_distance_refuses_malformed_spellings(
        self, ipa: IPAFeatures, value: str
    ) -> None:
        pl = ipa.features["place"]
        with pytest.raises(ValueError, match="malformed value"):
            pl.value_distance(value, "velar")
        with pytest.raises(ValueError, match="malformed value"):
            pl.value_distance("velar", value)

    def test_combine_refuses_nothing_and_malformed_members(
        self, ipa: IPAFeatures
    ) -> None:
        # combine(set()) manufactured "", which then expanded to ("",).
        pl = ipa.features["place"]
        with pytest.raises(ValueError, match="at least one value"):
            pl.combine(set())
        with pytest.raises(ValueError, match="malformed value"):
            pl.combine({"", "bilabial"})

    def test_expand_resolves_aliases_inside_a_combination(
        self, ipa: IPAFeatures
    ) -> None:
        # The alias was applied to the whole spelling before the split, so
        # a component alias survived unresolved and the caller compared a
        # name the data never declares.
        pl = ipa.features["place"]
        assert pl.expand("labial-velar^palatal") == ("bilabial", "velar", "palatal")
        assert (
            pl.value_distance("labial-velar^palatal", "bilabial^velar^palatal") == 0.0
        )

    def test_combine_emits_a_spelling_expand_reads_back(self, ipa: IPAFeatures) -> None:
        # combine used to pass an alias member through verbatim
        # ("alveolar^labial-velar"), which expand could not normalize.
        pl = ipa.features["place"]
        combined = pl.combine({"labial-velar", "alveolar"})
        assert combined == "bilabial^alveolar^velar"
        assert pl.expand(combined) == ("bilabial", "alveolar", "velar")
        assert pl.combine(pl.expand(combined)) == combined

    def test_declared_combinations_round_trip(self, ipa: IPAFeatures) -> None:
        for name, feat in ipa.features.items():
            for value in feat.values:
                if feat.COMBINER not in value:
                    continue
                assert feat.combine(feat.expand(value)) == value, (name, value)
            for alias, target in feat.value_aliases.items():
                assert feat.expand(alias) == feat.expand(target), (name, alias)

    def test_undeclared_components_stay_generative(self, ipa: IPAFeatures) -> None:
        # Deliberately permissive: expand is generative, and an undeclared
        # value is a question about this data, which comparison already
        # answers with maximal distance -- the plain scalar "NOTAPLACE"
        # gets 1.0 rather than an error, and a combination must not be
        # stricter than its own components.
        pl = ipa.features["place"]
        assert pl.expand("bilabial^NOTAPLACE") == ("bilabial", "NOTAPLACE")
        assert pl.value_distance("NOTAPLACE", "velar") == 1.0
        assert pl.value_distance("bilabial^NOTAPLACE", "bilabial") == 0.5

    def test_public_entry_points_are_unregressed(self, ipa: IPAFeatures) -> None:
        # respell names the offending value, and so does a query: the
        # generative expansion above is what `value_distance` needs, and
        # comparison is where an undeclared component is answered with
        # maximal distance. A *query* asking for one is a misspelling, and
        # an empty result is a wrong answer that looks like an inventory
        # fact -- which is the whole of `_resolve_query`'s stated policy.
        assert ipa.respell("k", place="labial-velar") == "k͡p"
        with pytest.raises(ValueError, match="is not a value of feature"):
            ipa.respell("t", place="bilabial^NOTAPLACE")
        with pytest.raises(ValueError, match="malformed value"):
            ipa.respell("t", place="bilabial^")
        for value in ("NOTAPLACE", "bilabial^NOTAPLACE"):
            with pytest.raises(ValueError, match="resolves to no feature term"):
                ipa.phones_matching({"place": value})


class TestReferenceFrame:
    """The ordinal scales ascend a declared reference frame: a left-facing
    oral tract (+x lips->glottis, +y jaw->palate).

    Which is why not every feature belongs in it. ``tone`` used to declare
    ``+y``, the axis ``height`` ascends, so a read asking what climbs the
    tract's vertical axis got pitch alongside vowel height. Pitch is the
    rate the vocal folds vibrate at, and "high tone" shares a word with
    "high vowel" and nothing else; it ascends ``+f0``, outside the tract
    frame entirely, as ``length`` ascends ``+t``.
    """

    #: Every declared axis and what ascends it. Pinned whole rather than
    #: asserted feature by feature, because the defect this replaces was
    #: not a wrong value on one feature but two unlike things sharing one
    #: axis, which no per-feature assertion is shaped to notice.
    #:
    #: Sharing an axis is not itself the error, and that is why this is a
    #: map rather than a rule. Four features declare ``+x`` and are right
    #: to: place, backness, constriction-location and articulator all
    #: measure position along the same tract. ``height`` and ``tone``
    #: sharing ``+y`` was the same arrangement in the file and the
    #: opposite in kind, because the quantities are unrelated. No
    #: mechanical rule separates those two cases -- "one feature per
    #: axis" would refuse ``+x``, which is correct -- so what is checked
    #: is the map, and a change to it has to be made on purpose.
    #:
    #: ``ipakit.tract.glottal_scale`` does refuse a second feature on
    #: ``+glottal-aperture``, and that is not this rule generalized: it
    #: refuses because it reads a single position off that axis, so two
    #: features would leave the choice to the function. It is the only
    #: reader that takes a single scale off an axis today. A reader that
    #: wanted one off ``+y`` would need the same refusal, and the map
    #: below is what keeps the question answerable until then.
    AXES = {
        "+constriction": {"manner"},
        "+f0": {"tone"},
        "+glottal-aperture": {"phonation"},
        "+t": {"length"},
        "+x": {"place", "backness", "constriction-location", "articulator"},
        "+y": {"height"},
        "+z": {"channel"},
    }

    def test_axes_declared(self, ipa: IPAFeatures) -> None:
        found: dict[str, set[str]] = {}
        for name, feature in ipa.features.items():
            if feature.axis:
                found.setdefault(feature.axis, set()).add(name)
        assert found == self.AXES

    def test_the_tract_frame_holds_only_tract_features(self, ipa: IPAFeatures) -> None:
        """The half that says why the map above is the shape it is: an
        axis of the oral tract carries positions in that tract, and a
        quantity measured somewhere else gets an axis of its own."""
        tract = {"+x", "+y", "+z"}
        on_tract = {n for n, f in ipa.features.items() if f.axis in tract}
        assert "tone" not in on_tract
        assert ipa.features["tone"].axis == "+f0"

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
        assert point.articulator == "lower-lip^tongue-dorsum"
        # Spelled with the combiner, so it reads back as two organs. A
        # literal "+" here was correct only while "+" was the combiner.
        art = ipa.features["articulator"]
        assert art.expand(point.articulator) == ("lower-lip", "tongue-dorsum")


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


class TestChannelAxis:
    """The +z axis: where the airflow channel sits in cross-section --
    lateral (out), flat, grooved (in). The mid-sagittal plane projects
    this away, so it has an ordering but no contour."""

    def test_sibilants_group_together(self, ipa: IPAFeatures) -> None:
        # Both grooved and one place step apart, against a channel change:
        # s~ʃ must be nearer than s~θ. Before the axis existed, s and θ
        # differed only by a tiny place step and scored near-identical.
        assert D(ipa, "s", "ʃ") < D(ipa, "s", "θ")

    def test_channel_outranks_a_small_place_move(self, ipa: IPAFeatures) -> None:
        assert D(ipa, "s", "θ") > D(ipa, "t", "d") / 4  # channel is not noise
        assert D(ipa, "s", "ɬ") > D(ipa, "s", "ʃ")  # lateral is further still

    def test_axis_is_ordered_out_to_in(self, ipa: IPAFeatures) -> None:
        ch = ipa.features["channel"]
        assert ch.axis == "+z"
        assert ch.values == ["lateral", "flat", "grooved"]
        # Adjacent steps are smaller than the full span.
        assert ch.value_distance("lateral", "flat") < ch.value_distance(
            "lateral", "grooved"
        )

    def test_laterality_bridge_still_works(self, ipa: IPAFeatures) -> None:
        # tˡ (lateral release) is nearer l than plain t is.
        assert D(ipa, "tˡ", "l") < D(ipa, "t", "l")


class TestDocumentedNonMetricity:
    """The triangle inequality does not hold, and docs/distance.md says so.

    This test exists to keep the documentation honest rather than to pin a
    number: if the metric ever became a true metric the doc would be wrong
    in the other direction, and that should be noticed.
    """

    def test_the_triangle_inequality_is_violated(self, ipa: IPAFeatures) -> None:
        # A composite sits near two things that are far from each other,
        # because it shares a different constituent with each.
        far = ipa.distance("b͡v", "ɡ")
        via = ipa.distance("b͡v", "ɡ͡b") + ipa.distance("ɡ͡b", "ɡ")
        assert via < far, (via, far)

    def test_the_properties_that_do_hold(self, ipa: IPAFeatures) -> None:
        for a, b in [("p", "b"), ("s", "z"), ("a", "i"), ("t͡ʃ", "ʃ")]:
            assert ipa.distance(a, b) == ipa.distance(b, a)
            assert 0.0 <= ipa.distance(a, b) <= 1.0
        assert ipa.distance("p", "p") == 0.0


class TestDataIntegrity:
    """Guards for facts that can silently disagree with the model. Each
    of these caught a real defect when first written."""

    def test_the_voicing_default_only_applies_where_it_is_right(
        self, ipa: IPAFeatures
    ) -> None:
        # `voiced` defaults to "-", the unmarked value for an obstruent
        # and the wrong one for everything else. No vowel declared it, so
        # the data said every vowel was voiceless and /i/ scored nearer a
        # voiceless nasal than a voiced one. Every non-obstruent speech
        # phone must say what it is, so the default is only ever reached
        # where it is right.
        manner = ipa.features["manner"]
        obstruent = manner.value_classes.get("obstruent", frozenset())
        assert obstruent, "the obstruent natural class must be declared"
        for symbol, phone in ipa.phones.items():
            if symbol in ipa.derived_phones:
                continue  # composed from constituents that declare it
            value = ipa.get_features(symbol).get("manner")
            if value is None or value in obstruent or value in manner.offscale:
                continue
            assert "voiced" in phone.features, symbol

    def test_one_property_is_spelled_with_one_feature(self, ipa: IPAFeatures) -> None:
        # r-coloring reached the data twice: ɚ/ɝ carried retroflex (the
        # consonant tongue shape, "Tongue tip curled back") while the ˞
        # and ʴ diacritics carried rhotacized. Same sound, two features,
        # so d(ɚ, ə˞) was 0.095 -- larger than d(ə, ə˞).
        assert D(ipa, "ɚ", "ə˞") == 0.0
        assert D(ipa, "ɝ", "ɜ˞") == 0.0
        assert D(ipa, "ə", "ɚ") == D(ipa, "ə", "ə˞")

    def test_retroflex_is_a_consonant_feature_only(self, ipa: IPAFeatures) -> None:
        # The two features mean different things and must not be carried
        # by the same class of phone: retroflex is a tongue shape a
        # consonant makes, rhotacized is a vowel color.
        for symbol, phone in ipa.phones.items():
            if phone.features.get("retroflex") == "+":
                assert phone.features.get("manner") != "vowel", symbol
            if phone.features.get("rhotacized") == "+":
                assert phone.features.get("manner") == "vowel", symbol

    def test_combiner_is_not_itself_a_declared_value(self, ipa: IPAFeatures) -> None:
        # The combiner marks a value as a combination, so a value spelled
        # with it parses as one. When "+" was both, expand("+") returned
        # two empty components and the binary scale lost its own "+".
        for name, feature in ipa.features.items():
            for value in feature.values:
                assert value != feature.COMBINER, f"{name}: {value!r}"
            assert feature.expand("+") == ("+",), name
            if feature.is_binary:
                assert set(feature._value_index) == {"+", "-"}, name

    def test_typed_features_carry_no_per_value_tables(self, ipa: IPAFeatures) -> None:
        # The loader once built these inside the non-typed branch and read
        # them outside it, so `voiced` inherited backness coordinates and
        # `syllabic` inherited articulator ones.
        for name, feat in ipa.features.items():
            if feat.type in ("binary", "ternary"):
                assert not feat.coordinates, name
                assert not feat.articulators, name

    def test_anchored_features_are_fully_anchored(self, ipa: IPAFeatures) -> None:
        # A partially anchored feature silently mixes two distance regimes:
        # anchored pairs measure in tract space, the rest fall back to
        # declaration order.
        for name, feat in ipa.features.items():
            if not feat.coordinates:
                continue
            for attr in ("arc", "offset"):
                anchored = {v for v, c in feat.coordinates.items() if attr in c}
                if not anchored:
                    continue
                scale = [
                    v
                    for v in feat.values
                    if feat.COMBINER not in v and v not in feat.offscale
                ]
                assert not [v for v in scale if v not in anchored], (name, attr)

    def test_aliases_resolve_to_something(self, ipa: IPAFeatures) -> None:
        for alias, target in ipa.ligature_map.items():
            assert target in ipa.phones or target in ipa.diacritics, alias

    def test_phone_features_are_declared(self, ipa: IPAFeatures) -> None:
        from ipakit.constants import METADATA_ATTRS

        declared = set(ipa.features) | METADATA_ATTRS | {"class"}
        for sym, phone in ipa.phones.items():
            assert not set(phone.features) - declared, sym


class TestMetricFingerprint:
    """The digest of the feature space a matrix was derived in.

    A derived matrix is only readable against the space it came from, and
    nothing in a saved matrix said which space that was: ``phones``
    detects membership drift, and a bridge changes no membership. The
    fingerprint is what a reader compares against the inventory in hand,
    so the two keys answer two questions and do not overlap.
    """

    BRIDGE = """
    <bridge name="posteriority">
      <spelling feature="retroflex" value="+"/>
      <spelling feature="place" value="postalveolar"/>
    </bridge>
  </bridges>"""
    #: ``phonation`` reaches the metric only through marks, so the two
    #: edits below move real distances while every registered phone's
    #: bundle stays byte-identical -- which is what makes them the honest
    #: test of a digest keyed to the registered phones.
    VALUE = '<value name="devoiced" short="dev" href="Voicelessness"/>'
    READS = '<value name="devoiced" reads="-"/>'
    DECLARED = '<feature name="phonation" axis="+glottal-aperture"'

    def _variant(self, tmp_path, *pairs: tuple[str, str]) -> IPAFeatures:
        text = (DATA_DIR / "ipa.xml").read_text(encoding="utf-8")
        for original, replacement in pairs:
            assert text.count(original) == 1, f"the data moved: {original!r}"
            text = text.replace(original, replacement)
        tmp_path.mkdir(parents=True, exist_ok=True)
        path = tmp_path / "ipa.xml"
        path.write_text(text, encoding="utf-8")
        return IPAFeatures(xml_path=path)

    def _grown(self, tmp_path) -> IPAFeatures:
        """A fifth phonation value, and the projection that must map it."""
        return self._variant(
            tmp_path,
            (self.VALUE, self.VALUE + '<value name="whispered" short="whs"/>'),
            (self.READS, self.READS + '<value name="whispered" reads="-"/>'),
        )

    def test_stable_within_a_run(self, ipa: IPAFeatures) -> None:
        phones = list(ipa.phones)
        assert metric_fingerprint(ipa, phones) == metric_fingerprint(ipa, phones)

    def test_it_is_not_a_constant(self, ipa: IPAFeatures) -> None:
        # The shape to avoid: a digest test that would pass against a
        # function returning the same string for everything.
        phones = list(ipa.phones)
        assert metric_fingerprint(ipa, phones) != metric_fingerprint(ipa, phones[:-1])
        assert metric_fingerprint(ipa, phones) != metric_fingerprint(ipa, [])

    def test_a_supplement_leaves_it_alone(self, ipa: IPAFeatures) -> None:
        # The direction that makes supplements usable at all: a supplement
        # adds phones and declares nothing, so the space is still the one
        # the shipped matrix was derived in and that matrix stays readable.
        phones = list(ipa.phones)
        supplemented = IPAFeatures(supplements=["aspirated-stops"])
        assert set(supplemented.phones) > set(phones)
        assert metric_fingerprint(supplemented, phones) == metric_fingerprint(
            ipa, phones
        )

    def test_a_wider_phone_list_reads_differently(self, ipa: IPAFeatures) -> None:
        # Keyed to the phone list the file itself carries: a matrix derived
        # over the supplemented inventory is a different object, and the
        # rows a fingerprint covers are part of what it says.
        supplemented = IPAFeatures(supplements=["aspirated-stops"])
        assert metric_fingerprint(
            supplemented, list(supplemented.phones)
        ) != metric_fingerprint(ipa, list(ipa.phones))

    def test_a_bridge_moves_it(self, tmp_path, ipa: IPAFeatures) -> None:
        phones = list(ipa.phones)
        bridged = self._variant(tmp_path, ("\n  </bridges>", self.BRIDGE))
        assert "posteriority" in bridged.bridges
        # The case `phones` is blind to: the same entries in the same order.
        assert list(bridged.phones) == phones
        assert metric_fingerprint(bridged, phones) != metric_fingerprint(ipa, phones)

    def test_a_value_added_to_a_scale_moves_it(
        self, tmp_path, ipa: IPAFeatures
    ) -> None:
        phones = list(ipa.phones)
        grown = self._grown(tmp_path)
        # A longer ordinal prices its own steps lower, so this is a real
        # change to the metric and not only to the declaration.
        assert grown.distance("d̤", "d̥") != ipa.distance("d̤", "d̥")
        assert metric_fingerprint(grown, phones) != metric_fingerprint(ipa, phones)

    def test_a_changed_type_moves_it(self, tmp_path, ipa: IPAFeatures) -> None:
        phones = list(ipa.phones)
        recast = self._variant(
            tmp_path, (self.DECLARED, self.DECLARED + ' type="categorical"')
        )
        assert recast.features["phonation"].type == "categorical"
        assert recast.distance("d̤", "d̥") != ipa.distance("d̤", "d̥")
        assert metric_fingerprint(recast, phones) != metric_fingerprint(ipa, phones)

    def test_those_edits_move_no_registered_bundle(
        self, tmp_path, ipa: IPAFeatures
    ) -> None:
        # Guard the guard. If either edit moved a phone's bundle, the two
        # tests above would be detecting membership again and the claim
        # they make about the feature space would be vacuous.
        for variant in (
            self._grown(tmp_path / "grown"),
            self._variant(
                tmp_path / "recast",
                (self.DECLARED, self.DECLARED + ' type="categorical"'),
            ),
        ):
            assert [variant.get_features(p) for p in ipa.phones] == [
                ipa.get_features(p) for p in ipa.phones
            ]
            assert list(variant.phones) == list(ipa.phones)
