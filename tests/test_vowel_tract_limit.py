"""A vowel's constriction location is read from a source where there is
one, and from `backness` where there is not.

Nineteen vowels state a `constriction-location` and twenty do not, so
the limit this file pins has moved and what it pins has changed with
it. What used to be here was that a vowel's `arc` is a function of
`backness` alone, so `u o ɑ ɔ ʌ` all sat at 0.56 while the measurement
put them at two locations 0.22 of a tract apart. That is fixed for the
vowels a source classifies. `u` is at 0.45, `o`, `ɔ` and `ʌ` at 0.56 and
`ɑ` at 0.74.

**What remains pinned is the fallback and its report.** The nine central
vowels no source places, and three peripheral qualities outside the
ranges Wood names, keep an `arc` from `backness`; `backness` says
where the tongue body is rather than where it constricts, so that arc is
reported in `Reading.approximated` and by `unmodeled` as kind
`approximate`. A caller can tell a sourced location from an unsourced one
without reading a source, which is the property that makes a partial
declaration worth making. `tests/test_constriction_location.py` holds the
classification and the report; this file holds what is still not known.

**Every declarative fix short of a source was tried and each is refused
by evidence rather than by taste.** These are why the repair took a
source rather than a rule:

* **`rounded` does not bear on `arc`.** The one minimal pair the
  measurement supplies is `ʌ` and `ɔ`, identical but for rounding, and
  both constrict at 0.65. ipakit giving them the same tract point is
  what the data says is *correct*; what they do not share is a lip
  aperture, which `docs/tract-anatomy.md` 4.4 says this geometry does
  not model.
* **`height` bears on it, but not by any rule a per-value declaration
  can state.** Height's effect at fixed backness is -0.01 from `i` to
  `ɛ` and +0.27 from `u` to `ʌ`. The interaction, 0.28, is larger than
  the entire declared backness span (0.56 - 0.32 = 0.24), so additive is
  out; the backness effect grows with openness (+0.11 close, +0.28
  near-close, +0.39 open-mid), so multiplicative, threshold and `max`
  rules all die on the same `ɛ` against `ʌ` pair. Every coordinate in
  `ipa.xml` is one feature, one value, one number.
* **Declaring `place` on a vowel does not move `arc`** -- the vowel
  branch never reads that slot, and `unmodeled` reports the stated place
  as `unread` rather than dropping it -- and it renames the phone,
  because `describe` reads the place slot out of the bundle. This is why
  the carrier is a separate `constriction-location` borrowing `place`'s
  vocabulary rather than `place` itself.
* **A secondary articulation cannot reach a vowel at all**, which
  `test_a_secondary_articulation_is_drawn_where_it_is_declared` already
  requires and this restates as the reason: a secondary is of
  approximant degree and must be no tighter than the primary, and every
  vowel's primary is looser than that. So `rhotacized` and `rounded`
  cannot be given a place the way `velarized` has one.

What is left needs a location per (height, backness) cell, and that
partition is five bits read straight off the measurement. `ipa.xml` is
the source of truth and the area functions are evidence about it, so a
table copied out of one speaker's MRI is the fit this refuses to make.
`docs/design/tract-validation.md` 6 (D1, D2) is the assessment; this is
the same finding where something checks it.

**Two further sources have since been measured, and they refuse the
table rather than supplying it.** Wood (1979) reviews X-rayed vowel
articulations from 40 subjects in 13 languages; Yang & Kasuya (1994)
print area functions for the five Japanese vowels from an adult male, an
adult female and a boy. Held against the constriction bands those
tabulated sources give, one symbol's measured location moves 0.059 to
0.284 of tract length between them -- for `o`, more than the whole
declared backness span of 0.24 that a cell table would have to resolve.
So there is no coordinate to copy. What reproduces is Wood's four
discrete locations, which land inside the measured band in 21 of 25
columns against 12 of 25 for the arcs ipakit declares -- a partition of
the (height, backness) plane into four families, which is a shape no
one-feature-one-value-one-number declaration can state.
`docs/design/vowel-constriction.md` is that assessment. **The
classification is what has since been adopted**, at the arcs `place`
already declares for the four locations: over the same 35 measured bands
the library now scores 26, against 25 for the classification read at
those arcs, 26 for Wood's own proportions, and 17 for `backness` alone.

**A fourth source has since re-imaged the third one's speaker, and the
central series has been looked for and largely is not there.** Story
(2008) re-measured the 1996 speaker in 2002: `i`, `ɪ` and `o` move by
more than 0.10 of tract length at every cutoff tried, and `o`'s two
bands do not overlap at any of them -- so a coordinate does not
reproduce even with the speaker, the laboratory and the procedure all
held fixed. And of the eleven central symbols this inventory placed at
arc 0.44, exactly two are classified by any source, and they go to
*different* families: Wood puts `ɨ` at the soft palate (0.514) and
Swedish `ʉː` at the hard palate (0.314), leaving 0.44 in the gap
between them. Both now state their family and neither is at 0.44. Cavar
et al. (2025) measure Polish `ɨ` with a front dorsum and Russian `ɨ`
with a back one over 28 speakers, so the disagreement is not an artifact
of Wood's review. The central column is not under-measured; it is not one
constriction location, and the nine symbols left in it state none.

The assessment counts ten symbols at 0.44 and there are eleven: `ä` is
`a` with the centralizing diaeresis, a registered phone with
`backness="central"`, and it is in none of its lists. Nothing in that
document's argument turns on the count.

If one of these stops holding, the limit has moved and the write-up
needs revising -- which is the point of asserting it.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from ipakit import IPAFeatures
from ipakit.tract import tract_point, tract_reading, unmodeled

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from invariants import (  # noqa: E402
    POSTURAL_ATTRS,
    check_typed_values_declare_no_geometry,
)

FEATURES = IPAFeatures()


@pytest.fixture
def ipa() -> IPAFeatures:
    return FEATURES


def _vowels(ipa: IPAFeatures) -> list[str]:
    return [
        p for p in sorted(ipa.phones) if ipa.get_features(p).get("manner") == "vowel"
    ]


class TestTheLimitAsItStands:
    def test_a_vowel_arc_is_a_function_of_backness_only_where_no_source_speaks(
        self, ipa: IPAFeatures
    ) -> None:
        """Two vowels agreeing on `backness` used to agree on `arc`
        whatever else they stated. That was the defect. What is left of it
        is that the vowels no source classifies still behave that way, and
        the ones a source classifies do not: `front` alone now spans 0.32
        to 0.74, because `a` and `æ` are in Wood's lower-pharyngeal family
        and `i e ɛ y ø` are in his palatal one."""
        spread: dict[str, set[float | None]] = {}
        unsourced: dict[str, set[float | None]] = {}
        for phone in _vowels(ipa):
            bundle = ipa.get_features(phone)
            arc = tract_point(ipa, bundle).arc
            spread.setdefault(bundle["backness"], set()).add(arc)
            if "constriction-location" not in bundle:
                unsourced.setdefault(bundle["backness"], set()).add(arc)
        assert len(spread) == 5, sorted(spread)
        assert len(spread["front"]) > 1, sorted(spread["front"])
        assert len(spread["back"]) > 1, sorted(spread["back"])
        # And the fallback is still exactly one number per backness value,
        # which is the part of the defect that no source closed.
        assert unsourced, "no vowel falls back: the second half is vacuous"
        for backness, arcs in unsourced.items():
            assert len(arcs) == 1, f"{backness}: {sorted(arcs)}"

    def test_the_five_back_vowels_no_longer_share_one_point(
        self, ipa: IPAFeatures
    ) -> None:
        """The headline case, with the measurement beside it.

        Measured: `u` and `o` at 0.38, `ɑ` at 0.67, `ɔ` and `ʌ` at 0.65 in
        the 1996 session; Wood puts `u` at the soft palate, `o`, `ɔ` and
        `ʌ` at the upper pharynx and `ɑ` at the lower one. All five state
        a location, and three arcs remain: `ʌ` shares `o` and `ɔ`'s,
        which is what its family says and what its own 0.65 says.
        """
        arcs = {p: tract_point(ipa, ipa.get_features(p)).arc for p in "uoɑɔʌ"}
        assert arcs == {"u": 0.45, "o": 0.56, "ɑ": 0.74, "ɔ": 0.56, "ʌ": 0.56}
        assert len(set(arcs.values())) == 3
        stated = {p for p in arcs if "constriction-location" in ipa.get_features(p)}
        assert stated == {"u", "o", "ɑ", "ɔ", "ʌ"}

    def test_the_pharyngeal_anchor_is_reached_only_by_a_stated_location(
        self, ipa: IPAFeatures
    ) -> None:
        """`backness` stops at `uvular`, so the third of Gaines et al.'s
        three constriction locations was unreachable by any vowel. It is
        reached now, and only through a stated location: `a ɑ æ` are
        Wood's `[ɑ-a-æ]`-like family and nothing else gets there."""
        places = ipa.features["place"].coordinates
        arcs = {p: tract_point(ipa, ipa.get_features(p)).arc for p in _vowels(ipa)}
        backness = ipa.features["backness"].coordinates
        assert max(c["arc"] for c in backness.values()) == places["uvular"]["arc"]
        assert places["pharyngeal"]["arc"] == 0.74
        past = {p for p, a in arcs.items() if a is not None and a > 0.56}
        assert past, "nothing reaches past uvular: the fix did not land"
        for phone in past:
            assert ipa.get_features(phone)["constriction-location"] == "pharyngeal"
            assert arcs[phone] == places["pharyngeal"]["arc"]

    def test_a_secondary_articulation_cannot_reach_a_vowel(
        self, ipa: IPAFeatures
    ) -> None:
        """Why `rhotacized` and `rounded` cannot be given a place.

        A secondary constriction is of approximant degree and must be no
        tighter than the primary, or it would be the primary. Every
        vowel's primary is looser than approximant degree, so a vowel
        can carry no secondary at all -- `mode="secondary"` is a
        consonant mechanism by construction.
        """
        approximant = ipa.features["manner"].coordinates["approximant"]["offset"]
        degrees = {tract_point(ipa, ipa.get_features(p)).offset for p in _vowels(ipa)}
        assert degrees, "sweep did not run"
        assert all(d is not None and d < approximant for d in degrees), sorted(degrees)

    def test_the_annotation_layer_can_now_see_this_limit(
        self, ipa: IPAFeatures
    ) -> None:
        """And that is the change, not a side effect of it.

        `unmodeled` reports a stated value the posture did not read, and
        this limit used to be invisible to it: `backness` was read for
        `arc` and `height` for `offset` on every vowel, so nothing was
        dropped and a predicate over consumption was blind by
        construction. Anyone reading a clean annotation strip under a
        vowel figure was reading "nothing was dropped", not "the position
        is right".

        A third kind fixes that without inventing a coordinate.
        `backness` supplying the `arc` is now reported as `approximate`,
        because the coordinate it supplied is not the coordinate it
        states. So the strip under `ə` says which number is a stand-in,
        and the strip under `i` does not, and neither says anything about
        the other's position being right.

        The attempt the docstring refuses is unchanged: a `place` stated
        on a vowel is read by nothing, and is reported.
        """
        vowels = _vowels(ipa)
        assert len(vowels) > 20, f"only {len(vowels)} vowels: the sweep is vacuous"
        approximate, sourced = 0, 0
        for phone in vowels:
            stated = ipa.get_features(phone, with_defaults=False)
            reading = tract_reading(ipa, stated)
            assert "height" in reading.read, phone
            kinds = {m.feature: m.kind for m in unmodeled(ipa, stated)}
            if "constriction-location" in stated:
                sourced += 1
                assert reading.read >= {"constriction-location", "height"}, phone
                assert kinds.get("backness") == "unread", phone
            else:
                approximate += 1
                assert reading.approximated == frozenset({"backness"}), phone
                assert kinds.get("backness") == "approximate", phone
        assert approximate and sourced, (approximate, sourced)
        placed = {**ipa.get_features("ə"), "place": "uvular"}
        assert (
            tract_point(ipa, placed).arc
            == ipa.features["backness"].coordinates["central"]["arc"]
        )
        assert ("place", "unread") in {
            (m.feature, m.kind) for m in unmodeled(ipa, placed)
        }

    def test_the_features_that_would_carry_it_declare_no_geometry(
        self, ipa: IPAFeatures
    ) -> None:
        """`rounded` and `rhotacized` are binary, so they hold no
        coordinates -- and could not be given any (below)."""
        for name in ("rounded", "rhotacized"):
            feature = ipa.features[name]
            assert feature.type == "binary", name
            assert not feature.coordinates, name
            assert feature.place is None, name


class TestTheChartIsAlreadyWhatIsDeclared:
    """Why deriving a location from the vowel chart's geometry adds nothing.

    The proposal that keeps coming back is to place the IPA vowel
    quadrilateral in the mid-sagittal plane and read a constriction
    location off it, on the ground that the figure is a stated model
    with no free parameters to fit. These two tests are why that is not
    a new source of information here: both of the figure's axes are
    already declared, faithfully, and one of them is already read as a
    position along the tract.

    `docs/design/vowel-chart-geometry.md` is the assessment, and it
    measures what the projection does with the other axis. If either of
    these stops holding, the declarations have moved away from the
    figure and that document's argument needs re-checking.
    """

    def test_backness_is_the_chart_horizontal_projected_between_two_places(
        self, ipa: IPAFeatures
    ) -> None:
        """The five `backness` arcs are the quarters of `palatal` to
        `uvular`, to within 0.01. So a vowel's `arc` already *is* the
        chart's front-to-back axis laid on the tract between two
        anatomical anchors -- which is the horizontal half of what any
        projection of the quadrilateral would compute."""
        order = ("front", "near-front", "central", "near-back", "back")
        arcs = ipa.features["backness"].coordinates
        places = ipa.features["place"].coordinates
        low, high = places["palatal"]["arc"], places["uvular"]["arc"]
        assert set(arcs) == set(order), sorted(arcs)
        for step, value in enumerate(order):
            even = low + step * (high - low) / (len(order) - 1)
            assert round(abs(arcs[value]["arc"] - even), 3) <= 0.01, (value, even)

    def test_height_is_the_chart_vertical_read_as_a_degree(
        self, ipa: IPAFeatures
    ) -> None:
        """And the seven `height` offsets, as fractions of the close-to-open
        span, reproduce the rows of the Association's own drawing to within
        0.03 -- measured off the vector paths of the 2020 chart, because its
        glyphs are in a custom-encoded font and extract to nonsense.

        The vertical axis is declared as `offset`, constriction *degree*.
        Routing it into `arc` as well is the whole of what a chart-derived
        location would change, and it is the axis the measurement refuses.
        """
        drawn = {
            "close": 0.000,
            "near-close": 0.155,
            "close-mid": 0.328,
            "mid": 0.489,
            "open-mid": 0.657,
            "near-open": 0.820,
            "open": 0.999,
        }
        offsets = ipa.features["height"].coordinates
        assert set(offsets) == set(drawn), sorted(offsets)
        close, open_ = offsets["close"]["offset"], offsets["open"]["offset"]
        for value, row in drawn.items():
            down = (close - offsets[value]["offset"]) / (close - open_)
            assert round(abs(down - row), 3) <= 0.03, (value, down, row)


class TestTheLoaderTrapThatHidesAnAttempt:
    """A coordinate on a binary feature evaporates, and nothing said so.

    The obvious first move on the defect above is to give `rounded` an
    `arc`. The loader builds the coordinate tables only for a feature
    that lists its own `<value>` elements; a typed one takes its values
    from its `<type>` and the attributes are never read. So the
    declaration loads clean, validates against `ipa.rng`, and does
    nothing at all.
    """

    def test_the_invariant_holds(self, ipa: IPAFeatures) -> None:
        assert check_typed_values_declare_no_geometry(ipa)

    def test_a_coordinate_on_a_binary_feature_is_dropped(
        self, ipa: IPAFeatures, tmp_path: Path
    ) -> None:
        """The behavior the guard exists for, demonstrated not asserted."""
        tree = ET.parse(ipa.xml_path)
        rounded = tree.getroot().find(".//feature[@name='rounded']/value[@name='+']")
        assert rounded is not None
        rounded.set("arc", "0.99")
        rounded.set("offset", "0.99")
        path = tmp_path / "ipa.xml"
        tree.write(path, encoding="utf-8", xml_declaration=True)

        patched = IPAFeatures(path)
        assert not patched.features["rounded"].coordinates
        # `u` is rounded, and is exactly where its declared location puts
        # it -- at `velar`, unmoved by an arc on the rounding feature.
        assert tract_point(patched, patched.get_features("u")).arc == 0.45

    def test_the_guard_fires_on_that_declaration(
        self, ipa: IPAFeatures, tmp_path: Path
    ) -> None:
        tree = ET.parse(ipa.xml_path)
        rounded = tree.getroot().find(".//feature[@name='rounded']/value[@name='+']")
        assert rounded is not None
        rounded.set("arc", "0.99")
        path = tmp_path / "ipa.xml"
        tree.write(path, encoding="utf-8", xml_declaration=True)
        assert not check_typed_values_declare_no_geometry(IPAFeatures(path))

    def test_the_guard_covers_every_attribute_the_branch_reads(self) -> None:
        """`POSTURAL_ATTRS` is a list, so it goes stale; pin it against
        the loader's own read.

        The guard can only name attributes it knows about. If
        `IPAFeatures` learns to read another `<value>` attribute in the
        branch a typed feature never takes, that one becomes silently
        inert too and the guard needs it -- so the two are compared here
        rather than kept in step by hand.
        """
        source = (
            Path(__file__).resolve().parent.parent / "ipakit" / "features.py"
        ).read_text()
        # The `else` arm of `if feat_type in self.types:` -- the one that
        # reads a feature's own <value> elements. A typed feature takes
        # the arm above it and never reaches this.
        untyped = source.split("if feat_type in self.types:")[1]
        untyped = untyped.split("\n                else:\n")[1]
        untyped = untyped.split("# Use feature default")[0]
        read = {
            attr
            for attr in POSTURAL_ATTRS
            if f'"{attr}"' in untyped or f"'{attr}'" in untyped
        }
        assert read == set(POSTURAL_ATTRS), sorted(set(POSTURAL_ATTRS) ^ read)
        # And the typed arm reads none of them, which is the whole defect.
        typed = source.split("if feat_type in self.types:")[1].split(
            "\n                else:\n"
        )[0]
        assert not [a for a in POSTURAL_ATTRS if f'"{a}"' in typed], typed
