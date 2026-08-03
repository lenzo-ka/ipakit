"""A vowel's constriction location is read from `backness` and nothing else.

That is a real limit and it reaches the metric through `metric._sagittal`,
not only the drawing: `u o ɑ ɔ ʌ` are all `back`, so all five sit at one
point. MRI-derived area functions (Story, Titze & Hoffman 1996, read by
`scripts/areafunctions.py`) put `u`/`o` at arc 0.38 and `ɑ`/`ɔ`/`ʌ` at
0.65 to 0.67, with 0.22 of tract length between the two groups that no
vowel of that speaker occupies -- and ipakit puts all five in the middle
of it. Gaines et al. (2021) reach the same two groups from a continuous
articulatory model.

**This is pinned open, not closed.** Every declarative fix was tried and
each is refused by evidence rather than by taste, which is why the limit
is written down here instead of being worked around:

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
* **Declaring `place` on a vowel does not move `arc`** -- `tract_point`
  takes the `manner == "vowel"` branch and reads `backness`
  unconditionally, and `unmodelled` reports the stated place as `unread`
  rather than dropping it -- and it renames the phone, because `describe`
  reads the place slot out of the bundle.
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
one-feature-one-value-one-number declaration can state, and which no
source assigns the central vowel series to at all.
`docs/design/vowel-constriction.md` is that assessment. The limit is
unchanged and every pin below stands; what moved is the reason.

If one of these stops holding, the limit has moved and the write-up
needs revising -- which is the point of asserting it.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from ipakit import IPAFeatures
from ipakit.tract import tract_point, tract_reading, unmodelled

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
    def test_a_vowel_arc_is_a_function_of_backness_alone(
        self, ipa: IPAFeatures
    ) -> None:
        """Two vowels agreeing on `backness` agree on `arc`, whatever else
        they state. This is the defect, asserted rather than described."""
        by_backness: dict[str, set[float | None]] = {}
        for phone in _vowels(ipa):
            bundle = ipa.get_features(phone)
            by_backness.setdefault(bundle["backness"], set()).add(
                tract_point(ipa, bundle).arc
            )
        assert len(by_backness) == 5, sorted(by_backness)
        for backness, arcs in by_backness.items():
            assert len(arcs) == 1, f"{backness}: {sorted(arcs)}"

    def test_the_five_back_vowels_share_one_point(self, ipa: IPAFeatures) -> None:
        """The headline case, with the measurement beside it.

        Measured: `u` and `o` at 0.38, `ɑ` at 0.67, `ɔ` and `ʌ` at 0.65.
        """
        arcs = {p: tract_point(ipa, ipa.get_features(p)).arc for p in "uoɑɔʌ"}
        assert set(arcs.values()) == {0.56}, arcs

    def test_no_vowel_reaches_the_pharyngeal_anchor(self, ipa: IPAFeatures) -> None:
        """The tongue-body sweep stops at `uvular` and `place` declares a
        location past it that no `backness` value reaches -- the third of
        Gaines et al.'s three constriction locations."""
        places = ipa.features["place"].coordinates
        reached = {tract_point(ipa, ipa.get_features(p)).arc for p in _vowels(ipa)}
        assert max(reached) == places["uvular"]["arc"] == 0.56
        assert places["pharyngeal"]["arc"] == 0.74
        assert not [a for a in reached if a > places["uvular"]["arc"]]

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

    def test_the_annotation_layer_cannot_see_this_limit(self, ipa: IPAFeatures) -> None:
        """And says so, rather than leaving it assumed shut.

        `unmodelled` reports a stated value the posture did not read.
        This limit is not one: `backness` is read for `arc` and `height`
        for `offset` on every vowel in the inventory, so nothing is
        dropped. Five back vowels sharing one point is a *resolution*
        limit -- `arc` has five values for thirty-five (height, backness)
        cells -- and a predicate over consumption is blind to it by
        construction. Anyone reading a clean annotation strip under a
        vowel figure is reading "nothing was dropped", not "the position
        is right".

        The attempt the docstring refuses is the other half: a `place`
        stated on a vowel *is* read by nothing, and is reported.
        """
        vowels = _vowels(ipa)
        assert len(vowels) > 20, f"only {len(vowels)} vowels: the sweep is vacuous"
        for phone in vowels:
            stated = ipa.get_features(phone, with_defaults=False)
            assert {"backness", "height"} <= tract_reading(ipa, stated).read, phone
            assert not [m for m in unmodelled(ipa, stated) if m.kind == "unread"], phone
        placed = {**ipa.get_features("a"), "place": "uvular"}
        assert (
            tract_point(ipa, placed).arc
            == ipa.features["backness"].coordinates["front"]["arc"]
        )
        assert ("place", "unread") in {
            (m.feature, m.kind) for m in unmodelled(ipa, placed)
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
        # `u` is rounded, and is exactly where it was.
        assert tract_point(patched, patched.get_features("u")).arc == 0.56

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
