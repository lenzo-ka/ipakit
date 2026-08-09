"""The structured Segment representation (docs/ties.md; design spec).

A unit is stored as its flat chain (constituents + typed junctures +
prosody); grouping, kind, bag, scalar, and emission are derived reads.
These tests pin the design-spec acceptance criteria that belong to the
representation (the distance work builds on it separately).
"""

import json

import pytest
from ipakit import IPAFeatures, Kind, Segment, Sense
from ipakit.segment import modifier_mode


def _prosody_payload(ipa: IPAFeatures, mark: str) -> str:
    """A serialized `d` carrying `mark` in its prosody.

    Round-tripped out of a live segment rather than spelled here, so the
    payload always states the current version and the current constituent
    shape. A hand-written one goes stale silently: it starts being refused
    for its version rather than for what it is testing.
    """
    obj = json.loads(ipa.segment("d").to_json())
    obj["prosody"] = [mark]
    return json.dumps(obj)


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


def test_segment_dict_is_the_json_representation(ipa: IPAFeatures) -> None:
    segment = ipa.segment("ⁿd͡ʒʷː")
    assert json.loads(segment.to_json()) == segment.to_dict()
    assert Segment.from_dict(segment.to_dict(), ipa) == segment


class TestKindTotality:
    CASES = [
        ("a", Kind.ATOMIC),
        ("tʲ", Kind.ATOMIC),
        ("t͡s", Kind.AFFRICATE),
        ("t͡ɬ", Kind.AFFRICATE),
        ("n͡d", Kind.PRENASALIZED),
        ("d͡n", Kind.PRE_STOPPED),
        ("t͡l", Kind.LATERAL_RELEASE),
        ("k͡ǂ", Kind.CLICK_ACCOMPANIMENT),
        ("k͡p", Kind.DOUBLE_ARTICULATION),
        # A double articulation is two places to articulate at, which is
        # the test the projection applies before it spells one: `t͡d` has
        # a single alveolar place and a vowel pair declares none, so
        # neither has anything double about it. All three are still
        # single-block fusions -- one timing slot, unordered notation --
        # which `phased` answers below, off the structure and not the name.
        ("t͡d", Kind.OVERLAY),
        ("u͡i", Kind.OVERLAY),  # V-V fusion: shape, not consonant-hood
        ("a͡t", Kind.OVERLAY),
        ("a͜ɪ", Kind.DIPHTHONG),
        ("a͡ɪ", Kind.OVERLAY),  # over-tie vowel pair: a fusion claim
        ("u͜i", Kind.DIPHTHONG),
        ("a͜ɪ͜ə", Kind.DIPHTHONG),
        ("t͜a", Kind.CHAIN),
        ("t͡s͜a", Kind.CHAIN),
        ("ŋ͡m͡ɡ͡b", Kind.PRENASALIZED),
    ]

    @pytest.mark.parametrize("text,kind", CASES)
    def test_kind(self, ipa: IPAFeatures, text: str, kind: Kind) -> None:
        assert ipa.segment(text).kind is kind

    def test_glyph_is_authoritative_for_registered_entries(
        self, ipa: IPAFeatures
    ) -> None:
        # Canonical spellings are sense-correct; the glyph is the sense.
        seg = ipa.segment("a͜ɪ")
        assert seg.sense is Sense.SEQ
        assert seg.kind is Kind.DIPHTHONG
        assert ipa.get_phone("a͜ɪ") is not None


class TestGrouping:
    def test_single_block_skips_degenerate_layer(self, ipa: IPAFeatures) -> None:
        # k͡p has one phase block; children are the constituents directly,
        # so traversal terminates.
        seg = ipa.segment("k͡p")
        assert [c.to_ipa() for c in seg.children] == ["k", "p"]
        assert all(c.children == () for c in seg.children)

    def test_hybrid_n_ary_blocks(self, ipa: IPAFeatures) -> None:
        seg = ipa.segment("ŋ͡m͡ɡ͡b")
        assert [c.to_ipa() for c in seg.children] == ["ŋ͡m", "ɡ͡b"]
        assert [c.kind for c in seg.children] == [
            Kind.DOUBLE_ARTICULATION,
            Kind.DOUBLE_ARTICULATION,
        ]
        assert [[g.to_ipa() for g in c.children] for c in seg.children] == [
            ["ŋ", "m"],
            ["ɡ", "b"],
        ]

    def test_mixed_chain_children_are_fuse_runs(self, ipa: IPAFeatures) -> None:
        seg = ipa.segment("t͡s͜a")
        assert [c.to_ipa() for c in seg.children] == ["t͡s", "a"]
        assert seg.left.kind is Kind.AFFRICATE
        assert seg.right.kind is Kind.ATOMIC

    def test_atomic_sides_return_self(self, ipa: IPAFeatures) -> None:
        seg = ipa.segment("a")
        assert seg.left is seg and seg.right is seg
        assert seg[0] is seg

    def test_edge_feature_reads(self, ipa: IPAFeatures) -> None:
        # The edge reads approach a composed unit from one side.
        seg = ipa.segment("t͡s͜a")
        assert seg.left_features(with_defaults=False)["manner"] == "affricate"
        assert seg.right_features(with_defaults=False)["manner"] == "vowel"
        tri = ipa.segment("a͜ɪ͜ə")
        assert tri.features_at(1, with_defaults=False)["height"] == "near-close"
        atom = ipa.segment("a")
        assert atom.left_features() == atom.scalar()


class TestBagAndBundle:
    def test_per_constituent_defaults_reach_the_bag(self, ipa: IPAFeatures) -> None:
        # /i/ carries no explicit rounded; the per-constituent default is
        # materialized before the union.
        bag = ipa.segment("u͜i").bag()
        assert bag["rounded"] == ("+", "-")
        assert bag["backness"] == ("back", "front")

    def test_modifier_projections_stay_sparse(self, ipa: IPAFeatures) -> None:
        # ʲ must not inject default rounding into the bag.
        bag = ipa.segment("uʲ").bag()
        assert bag["rounded"] == ("+",)
        assert bag["palatalized"] == ("+",)

    def test_overriding_modifier_replaces(self, ipa: IPAFeatures) -> None:
        # The devoicing ring replaces voiced=+, never unions to {+, -}.
        seg = ipa.segment("d̥")
        assert seg.constituents[0].bundle(ipa)["voiced"] == "-"
        assert seg.bag()["voiced"] == ("-",)

    def test_values_dedupe_in_constituent_order(self, ipa: IPAFeatures) -> None:
        bag = ipa.segment("ŋ͡m͡ɡ͡b").bag()
        assert bag["place"] == ("velar", "bilabial")
        assert bag["voiced"] == ("+",)


class TestScalarAgreement:
    STRINGS = ["t͡s", "t͡ɬ", "q͡χ", "u͜i", "t͡s͜a", "tʲ", "d̥", "a͜ɪ͜ə", "a͡ɪ"]

    @pytest.mark.parametrize("text", STRINGS)
    def test_scalar_matches_compose(self, ipa: IPAFeatures, text: str) -> None:
        composed = ipa.compose(text, with_defaults=False)
        assert composed, text
        assert ipa.segment(text).scalar(with_defaults=False) == composed[0]


class TestProsody:
    def test_stress_attaches_to_following_unit(self, ipa: IPAFeatures) -> None:
        segs = ipa.segments("ˈat͡sa")
        assert [s.to_ipa() for s in segs] == ["ˈa", "t͡s", "a"]
        assert segs[0].prosody == ("ˈ",)

    def test_length_attaches_to_its_unit(self, ipa: IPAFeatures) -> None:
        seg = ipa.segment("aː")
        assert seg.prosody == ("ː",)
        assert seg.kind is Kind.ATOMIC

    def test_prosody_excluded_from_bag(self, ipa: IPAFeatures) -> None:
        assert ipa.segment("aː").bag() == ipa.segment("a").bag()

    def test_build_rejects_structural_prosody(self, ipa: IPAFeatures) -> None:
        with pytest.raises(ValueError):
            ipa.build_segment(["a"], prosody=("͡",))


class TestSerialization:
    def test_json_round_trip_structural_equality(self, ipa: IPAFeatures) -> None:
        for text in ["t͡s͜a", "a͜ɪ͜ə", "uʲ", "ˈa", "ŋ͡m͡ɡ͡b"]:
            seg = ipa.segments(text)[0] if text.startswith("ˈ") else ipa.segment(text)
            assert Segment.from_json(seg.to_json(), ipa) == seg

    def test_json_version_pinned(self, ipa: IPAFeatures) -> None:
        with pytest.raises(ValueError):
            Segment.from_json('{"v": 99, "constituents": []}', ipa)

    def test_from_json_rejects_structural_prosody(self, ipa: IPAFeatures) -> None:
        """A tie is a juncture, so it is not a property of one unit.

        The payload is built from a live segment rather than written out
        here. Spelled by hand it carried its own version number, and when
        the version moved this passed on the version instead -- refusing
        the right payload for the wrong reason, which is no guard at all.
        """
        data = _prosody_payload(ipa, "͡")
        with pytest.raises(ValueError, match="junctures"):
            Segment.from_json(data, ipa)

    def test_prosody_admits_exactly_the_prosodic_marks(self, ipa: IPAFeatures) -> None:
        """Prosody carries prosodic marks, and the rest are refused there.

        Stated over every mark the inventory declares rather than over a
        list of offenders, and both arms are required to be reached, so
        this cannot pass by finding nothing to check.
        """
        admitted, refused = [], []
        for mark in sorted(ipa.diacritics):
            payload = _prosody_payload(ipa, mark)
            prosodic = modifier_mode(ipa, mark) == "prosodic"
            try:
                Segment.from_json(payload, ipa)
            except ValueError:
                refused.append(mark)
                assert not prosodic, f"{mark!r} is prosodic and was refused"
            else:
                admitted.append(mark)
                assert prosodic, f"{mark!r} states {modifier_mode(ipa, mark)}"
        assert admitted, "no prosodic mark was admitted: the sweep is vacuous"
        assert refused, "no other mark was refused: the sweep is vacuous"

    def test_an_accepted_segment_survives_being_written_and_read(
        self, ipa: IPAFeatures
    ) -> None:
        """What `from_json` accepts, `to_ipa` must not turn into something else.

        A segmental diacritic parked in `prosody` changed nothing where it
        sat, because prosody is not read for features. Then `to_ipa` wrote
        it in the one position where the parser reads it as a constituent
        modifier, and a voiced `d` came back devoiced -- accepted, emitted
        as valid IPA, reparsed correctly, and a different phone, with
        nothing raising anywhere along the way.

        The invariant is the round trip, not the one mark that broke it:
        either the payload is refused, or what comes back describes the
        same sound.
        """
        checked = 0
        for mark in sorted(ipa.diacritics):
            payload = _prosody_payload(ipa, mark)
            try:
                seg = Segment.from_json(payload, ipa)
            except ValueError:
                continue
            checked += 1
            back = ipa.segment(seg.to_ipa())
            assert seg.scalar() == back.scalar(), (
                f"{mark!r} in prosody spells {seg.to_ipa()!r}, which reads "
                f"back as a different sound"
            )
        assert checked, "every payload was refused: the round trip is unchecked"


class TestEmissionFaithfulness:
    """With strict glyph authority there are no collision spellings:
    to_ipa() is faithful, and parse(emit(x)) == x structurally for every
    expressible unit."""

    def test_round_trips_are_structural(self, ipa: IPAFeatures) -> None:
        for parts, sense in [
            (["u", "i"], Sense.FUSE),
            (["a", "ɪ"], Sense.FUSE),
            (["t", "s"], Sense.SEQ),
            (["a", "ɪ"], Sense.SEQ),
        ]:
            built = ipa.build_segment(parts, sense)
            assert ipa.segment(built.to_ipa()) == built

    def test_canonical_spelling_emits_itself(self, ipa: IPAFeatures) -> None:
        for text in ["a͜ɪ", "t͡s", "t͡s͜a", "a͜ɪ͜ə"]:
            assert ipa.segment(text).to_ipa() == text

    def test_built_sequential_ts_is_the_parsed_one(self, ipa: IPAFeatures) -> None:
        seq_ts = ipa.build_segment(["t", "s"], Sense.SEQ)
        assert seq_ts.to_ipa() == "t͜s"
        assert ipa.segment("t͜s") == seq_ts
        assert Segment.from_json(seq_ts.to_json(), ipa) == seq_ts


class TestConstituentParsing:
    def test_chain_with_internal_modifier(self, ipa: IPAFeatures) -> None:
        seg = ipa.segment("a͜ʊ̯")
        assert [c.base for c in seg.constituents] == ["a", "ʊ"]
        assert seg.constituents[1].modifiers == ("̯",)
        assert seg.kind is Kind.DIPHTHONG

    def test_trailing_modifiers_attach_to_last_constituent(
        self, ipa: IPAFeatures
    ) -> None:
        seg = ipa.segment("t͡sʲ")
        assert seg.constituents[1].modifiers == ("ʲ",)

    def test_segment_rejects_multiple_units(self, ipa: IPAFeatures) -> None:
        with pytest.raises(ValueError):
            ipa.segment("ta")
