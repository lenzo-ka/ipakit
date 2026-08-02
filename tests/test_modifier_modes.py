"""The flat projection reads a diacritic the way the bundle does.

``Constituent.bundle`` has always applied a modifier by its contribution
mode (docs/ties.md): overriding marks replace their base's value,
everything else adds only what the base leaves unstated. ``Segment.scalar``
and ``IPAFeatures.compose_segments`` overlaid the mark unconditionally
instead, so a release-phase mark spoke for the whole segment: ``tˀ``
read as glottal, ``describe("tˀ") == describe("kˀ")``, and
``to_phone(features("tˀ"))`` was the glottal stop ``ʔ``.

The invariant these tests hold is that for an atomic unit -- one
constituent, so the flat and structured reads describe the same object --
the two agree on every phonetic key.
"""

import warnings

import pytest
from ipakit import IPAFeatures
from ipakit.constants import METADATA_ATTRS


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


class TestAtomicUnitsAgree:
    """The sweep, not a spot check: every base against every mark."""

    def test_scalar_agrees_with_the_bundle(self, ipa: IPAFeatures) -> None:
        divergent: list[tuple[str, str, str, str]] = []
        checked = 0
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for base in ipa.phones:
                for mark in ipa.diacritics:
                    unit = base + mark
                    try:
                        parsed = ipa.segment(unit)
                    except ValueError:
                        continue
                    if len(parsed.constituents) != 1:
                        continue
                    checked += 1
                    bundle = parsed.constituents[0].bundle(ipa)
                    for key, value in parsed.scalar().items():
                        if key in METADATA_ATTRS:
                            continue
                        if bundle.get(key) != value:
                            divergent.append((unit, key, value, bundle.get(key, "")))
        assert checked > 5000, "sweep did not run"
        assert divergent == []

    def test_the_flat_read_stays_inside_the_bag(self, ipa: IPAFeatures) -> None:
        # bag() is the union over constituents, so an atomic unit's
        # scalar value must be *the* value the bag holds.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for unit in ("tˀ", "kˀ", "aᵊ", "kᵊ", "ǀʼ", "pʼ", "d̥", "tʲ", "ã"):
                parsed = ipa.segment(unit)
                bag = parsed.bag()
                for key, value in parsed.scalar().items():
                    if key in METADATA_ATTRS:
                        continue
                    assert value in bag[key], (unit, key, value)


class TestReleaseMarksDoNotSpeakForTheSegment:
    def test_preglottalization_keeps_its_base_place(self, ipa: IPAFeatures) -> None:
        assert ipa.get_features("tˀ")["place"] == "alveolar"
        assert ipa.get_features("kˀ")["place"] == "velar"

    def test_preglottalized_stops_describe_distinctly(self, ipa: IPAFeatures) -> None:
        assert ipa.describe("tˀ") != ipa.describe("kˀ")
        # The release is named as a phase and the base keeps its own
        # place: "glottalized alveolar", never "glottal".
        assert ipa.describe("tˀ") == "voiceless glottalized alveolar plosive"
        assert "glottal plosive" not in ipa.describe("tˀ")

    def test_preglottalized_t_is_not_a_glottal_stop(self, ipa: IPAFeatures) -> None:
        # Nothing registered spells "alveolar plosive with a glottal
        # release", so the realization is None -- the same answer every
        # other release mark already gives. It used to come back as the
        # bare "t" only because the mark contributed nothing at all.
        assert ipa.to_phone(ipa.get_features("tˀ")) != "ʔ"
        assert ipa.to_phone(ipa.get_features("tˀ")) is None
        assert ipa.to_phone(ipa.get_features("tʰ")) is None

    def test_a_release_mark_names_its_phase_and_nothing_else(
        self, ipa: IPAFeatures
    ) -> None:
        # The data declares what these marks are; the mode falls out.
        assert ipa.get_features("tˀ")["release"] == "glottal"
        assert ipa.get_features("aᵊ")["release"] == "schwa"

    def test_a_phase_mark_does_not_fill_a_slot_its_base_leaves_empty(
        self, ipa: IPAFeatures
    ) -> None:
        # The mode rule only stops a mark *overriding* its base. While the
        # data said pre-glottalization was a glottal plosive, the mark
        # still filled a slot the base left empty: a vowel has no place,
        # so "aˀ" came out glottal, and a consonant has no vowel quality,
        # so "tᵊ" came out mid/central. Declaring both as releases is what
        # actually stops that.
        assert "place" not in ipa.get_features("aˀ")
        assert "height" not in ipa.get_features("tᵊ")
        assert "backness" not in ipa.get_features("tᵊ")

    def test_the_schwa_release_leaves_a_vowel_alone(self, ipa: IPAFeatures) -> None:
        # The mark states mid/central; the vowel already states its own
        # height and backness, and an added phase never overrules them.
        assert ipa.get_features("aᵊ")["height"] == "open"
        assert ipa.get_features("aᵊ")["backness"] == "front"
        # Named as a release, but the vowel's own qualities are its own:
        # naming a phase is not overruling the segment.
        assert ipa.describe("aᵊ") == "schwa-released open front unrounded vowel"
        assert ipa.describe("aᵊ") != ipa.describe("a")

    def test_the_schwa_release_does_not_make_a_stop_a_vowel(
        self, ipa: IPAFeatures
    ) -> None:
        assert ipa.get_features("kᵊ")["manner"] == "plosive"
        assert ipa.get_features("kᵊ")["place"] == "velar"
        assert ipa.to_phone(ipa.get_features("kᵊ")) != "ə"

    def test_a_click_keeps_everything_the_ejective_mark_does_not_state(
        self, ipa: IPAFeatures
    ) -> None:
        # 'ʼ' is not a release mark and never was; it states the segment's
        # airstream, and 'airstream' is now declared overriding, so it
        # lands. Under the additive default it did not, and the click's
        # own value stood: features("ǀʼ")["airstream"] was "velaric",
        # d("ǂʼ", "ǂ") was 0.0, and an ejective click was the same sound
        # as a plain one. What a release mark must not touch -- the place,
        # the manner, the article -- the ejective mark does not touch.
        assert ipa.get_features("ǀʼ")["airstream"] == "ejective"
        assert ipa.get_features("ǀʼ")["place"] == ipa.get_features("ǀ")["place"]
        assert ipa.get_features("ǀʼ")["manner"] == ipa.get_features("ǀ")["manner"]
        assert ipa.get_features("ǀʼ")["href"] == ipa.get_features("ǀ")["href"]


class TestTheOtherModesStillWork:
    def test_an_overriding_mark_overrides(self, ipa: IPAFeatures) -> None:
        assert ipa.get_features("d")["voiced"] == "+"
        assert ipa.get_features("d̥")["voiced"] == "-"
        assert ipa.get_features("d̥")["phonation"] == "devoiced"
        assert ipa.get_features("t̪")["place"] == "dental"

    def test_a_secondary_mark_adds(self, ipa: IPAFeatures) -> None:
        assert ipa.get_features("tʲ")["palatalized"] == "+"
        assert ipa.get_features("tʲ")["place"] == "alveolar"
        assert ipa.get_features("kʷ")["labialized"] == "+"

    def test_an_additive_mark_adds_what_the_base_leaves_unstated(
        self, ipa: IPAFeatures
    ) -> None:
        # nasalized defaults to "-", so this only holds because the
        # overlay runs before the defaults are filled.
        assert ipa.get_features("ã")["nasalized"] == "+"
        assert ipa.get_features("pʼ")["airstream"] == "ejective"

    def test_a_release_mark_still_names_its_phase(self, ipa: IPAFeatures) -> None:
        assert ipa.get_features("tʰ")["release"] == "aspirated"
        assert ipa.get_features("tˡ")["release"] == "lateral"

    def test_prosody_stays_off_the_bag_but_reaches_compose(
        self, ipa: IPAFeatures
    ) -> None:
        # The one documented divergence between compose() and scalar().
        assert ipa.segment("eː").scalar()["length"] == "normal"
        assert ipa.segment("eː").prosody == ("ː",)
        assert ipa.compose("eː")[0]["length"] == "long"


class TestMetadataIsNotAFeature:
    """``href``/``xsampa``/``class`` name a symbol, and the symbol a
    unit's metadata describes is its base, not the mark riding on it."""

    def test_the_units_article_is_its_bases(self, ipa: IPAFeatures) -> None:
        assert ipa.get_features("tʰ")["href"] == ipa.get_features("t")["href"]
        assert ipa.get_features("tʰ")["class"] == "phone"

    def test_no_mark_contributes_metadata(self, ipa: IPAFeatures) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for base in ("t", "a", "k", "n"):
                base_meta = {
                    k: v
                    for k, v in ipa.get_features(base).items()
                    if k in METADATA_ATTRS
                }
                for mark in ipa.diacritics:
                    unit = base + mark
                    # A precomposed spelling that is registered in its own
                    # right (ť, the alveolar ejective) is a phone, not an
                    # overlay, and carries its own article.
                    if ipa.canonicalize_unicode(unit) in ipa.phones:
                        continue
                    feats = ipa.get_features(unit)
                    if not feats:
                        continue
                    assert {
                        k: v for k, v in feats.items() if k in METADATA_ATTRS
                    } == base_meta, unit
