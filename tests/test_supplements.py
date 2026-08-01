"""A supplement extends an inventory, and must not move the one it extends.

``docs/supplements.md`` is the reference; this is what makes it true.

The motivating case is registering a composed segment as a first-class
phone -- ``tʰ``, ``ɪ̃``, ``t̚`` -- and most of what that sounds like it
buys, it does not: a composed unit is already accepted as *input* by
``features``, ``distance``, ``describe``, ``confusability`` and
``nearest_phones``. What registering actually buys is membership: a place
in the reference distribution the metric normalizes against, an answer
from ``to_phone``/``respell``, and a seat in the pools that
``nearest_phones``, ``minimal_pairs`` and ``hierarchy`` draw *results*
from. So these tests are about membership and its two hazards.

The first hazard is the metric. ``ipakit.phones`` is the reference
distribution for ``confusability``, ``normalized_distance`` and
``DistanceModel.global_``, and ``data/confusion.json`` is that
distribution shipped. A supplement that reached it would move numbers for
every caller in the process, so the shipped artifacts are pinned here to
the bare inventory and a supplemented instance is required to carry its
own derived data.

The second is ``to_phone``, which picks a winner over the whole phone
table. A new candidate can outrank an existing winner -- measured below
at 25 bundles for one plausible supplement -- and that is a silent
behavior change of exactly the shape ``docs/reviewing.md`` records. The
rank key that stops it is asserted in both directions: monotone with it,
and the movers it would otherwise let through, pinned.
"""

from __future__ import annotations

import functools
import json
import sys
import warnings
from pathlib import Path

import ipakit
import pytest
from ipakit import IPAFeatures
from ipakit.constants import METADATA_ATTRS
from ipakit.distance_model import DistanceModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "docs" / "examples" / "aspirated-stops.xml"
ASPIRATED = EXAMPLE.read_text(encoding="utf-8")

#: A supplement whose entry matches a bundle the base already answers.
#: ``č`` is the Americanist spelling of ``t͡ʃ`` and carries the same
#: features, so it beats it on constituent count -- which is what the
#: base-first rank key exists to refuse.
AMERICANIST = """<?xml version='1.0' encoding='utf-8'?>
<supplement name="americanist">
  <phones>
    <phone name="č" manner="affricate" place="postalveolar" channel="grooved"/>
  </phones>
</supplement>
"""


def write(tmp_path: Path, name: str, text: str) -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def aspirated() -> Path:
    """The worked example the documents show, exercised rather than displayed."""
    return EXAMPLE


class TestTheDocumentedExampleIsTheOneThatRuns:
    """Every supplement the documents show is the checked-in one.

    Two copies of anything is what this repository drifts on, and a page
    showing a supplement that is not the one the tests load would be the
    same failure ``tests/test_license.py`` exists to stop for the license.
    ``scripts/docexamples.py`` already runs the pages' Python; this is the
    XML half, and it is a predicate over every document rather than a list
    of the two that carry one today.
    """

    def shown(self) -> list[tuple[str, str]]:
        found = []
        for page in sorted((ROOT / "docs").glob("*.md")) + [ROOT / "README.md"]:
            for block in page.read_text(encoding="utf-8").split("```"):
                if block.startswith("xml\n") and "<supplement " in block:
                    found.append((page.name, block.removeprefix("xml\n")))
        return found

    def test_the_documents_show_it(self) -> None:
        assert {name for name, _ in self.shown()} == {
            "supplements.md",
            "tutorial.md",
            "tutorial.src.md",
        }

    def test_every_shown_supplement_is_the_file(self) -> None:
        for name, block in self.shown():
            assert (
                block == ASPIRATED
            ), f"{name} shows a supplement that is not {EXAMPLE}"


@pytest.fixture(scope="module")
def supplemented(aspirated: Path) -> IPAFeatures:
    return IPAFeatures(supplements=[aspirated])


class TestASupplementAdds:
    def test_the_entries_are_registered_phones(
        self, ipa: IPAFeatures, supplemented: IPAFeatures
    ) -> None:
        added = set(supplemented.phones) - set(ipa.phones)
        assert added == {"pʰ", "tʰ", "kʰ"}
        assert len(supplemented) == len(ipa) + 3

    def test_the_base_inventory_is_untouched(
        self, ipa: IPAFeatures, supplemented: IPAFeatures
    ) -> None:
        """A second instance is a second inventory, not a mutation of the first."""
        assert "tʰ" not in ipa.phones
        assert ipa.supplements == {}
        assert ipa.supplement_of == {}

    def test_the_entries_reach_the_write_side(
        self, ipa: IPAFeatures, supplemented: IPAFeatures
    ) -> None:
        """``respell`` is the gap ``compose_unit`` was added to work around."""
        assert ipa.respell("t", release="aspirated") is None
        assert supplemented.respell("t", release="aspirated") == "tʰ"
        bundle = {
            k: v
            for k, v in supplemented.get_features("tʰ").items()
            if k not in METADATA_ATTRS
        }
        assert ipa.to_phone(bundle) is None
        assert supplemented.to_phone(bundle) == "tʰ"

    def test_the_entries_join_the_result_pools(
        self, ipa: IPAFeatures, supplemented: IPAFeatures
    ) -> None:
        """A composed unit can already be the *query*; registering makes it
        an *answer*. Both pools draw from the phone table."""
        assert [p for p, _ in ipa.nearest_phones("t", n=139)].count("tʰ") == 0
        assert "tʰ" in [p for p, _ in supplemented.nearest_phones("t", n=142)]
        assert "pʰ" not in [p for p, _, _ in ipa.minimal_pairs("t")]
        assert "pʰ" in [p for p, _, _ in supplemented.minimal_pairs("t")]

    def test_two_supplements_merge_in_either_order(self, tmp_path: Path) -> None:
        """Merge is additive, so load order is not a fact about the result."""
        a = write(tmp_path, "a.xml", ASPIRATED)
        b = write(tmp_path, "b.xml", AMERICANIST)
        forward = IPAFeatures(supplements=[a, b])
        backward = IPAFeatures(supplements=[b, a])
        assert set(forward.phones) == set(backward.phones)
        assert forward.supplement_of == backward.supplement_of


class TestProvenanceIsNotADeclaration:
    """Where a symbol came from must not reach a feature bundle.

    Measured, not theoretical: putting provenance as an attribute on a
    declaring element moved 37 distances while ``confusion.json`` stayed
    byte-identical, because every attribute on a declaring element lands
    in the bundle and a bundle key is a term in the metric. ``<notations>``
    records the same finding beside itself in ``ipa.xml``. This is the
    converse of ``tests/test_license.py``'s last test.
    """

    def test_the_supplement_name_is_held_beside_the_symbol(
        self, supplemented: IPAFeatures
    ) -> None:
        assert supplemented.supplement_of["tʰ"] == "aspirated-stops"
        assert set(supplemented.supplements) == {"aspirated-stops"}

    def test_no_bundle_carries_it(self, supplemented: IPAFeatures) -> None:
        for phone in supplemented.phones:
            bundle = supplemented.get_features(phone)
            assert "supplement" not in bundle
            assert "name" not in bundle
        assert "supplement" not in supplemented.features
        assert "supplement" not in supplemented.classes


class TestFeaturesAreEqualByConstruction:
    """A registered composed segment reads the same as the composition.

    An entry that declares no features takes them from its own spelling,
    which is the rule tied entries already load under. The alternative --
    the author retyping the bundle -- is two copies of one fact, and this
    repository's record on those is in ``docs/reviewing.md``.
    """

    @pytest.mark.parametrize("unit", ["pʰ", "tʰ", "kʰ"])
    def test_the_bundle_does_not_move(
        self, ipa: IPAFeatures, supplemented: IPAFeatures, unit: str
    ) -> None:
        assert ipa.get_features(unit) == supplemented.get_features(unit)

    @pytest.mark.parametrize("unit", ["pʰ", "tʰ", "kʰ"])
    def test_the_distance_does_not_move(
        self, ipa: IPAFeatures, supplemented: IPAFeatures, unit: str
    ) -> None:
        for other in ("t", "d", "s", "a", "ʔ"):
            assert ipa.distance(unit, other) == supplemented.distance(unit, other)

    @pytest.mark.parametrize("unit", ["pʰ", "tʰ", "kʰ"])
    def test_the_description_does_not_move(
        self, ipa: IPAFeatures, supplemented: IPAFeatures, unit: str
    ) -> None:
        assert ipa.describe(unit) == supplemented.describe(unit)

    def test_a_declared_entry_is_taken_as_written(self, tmp_path: Path) -> None:
        """An entry that states features is a sound the base cannot spell."""
        f = IPAFeatures(supplements=[write(tmp_path, "a.xml", AMERICANIST)])
        assert f.get_features("č")["manner"] == "affricate"
        assert f.get_features("č")["place"] == "postalveolar"


class TestASupplementMayOnlyExtend:
    def test_a_redeclared_symbol_is_refused(self, tmp_path: Path) -> None:
        """Which file wins is a question this repository has answered wrong
        by declaration order before. It is refused rather than answered."""
        path = write(
            tmp_path,
            "clash.xml",
            '<supplement name="clash"><phones>'
            '<phone name="t" manner="vowel"/>'
            "</phones></supplement>",
        )
        with pytest.raises(ValueError, match="redeclares 't'"):
            IPAFeatures(supplements=[path])

    def test_a_symbol_redeclared_by_a_second_supplement_is_refused(
        self, tmp_path: Path
    ) -> None:
        first = write(tmp_path, "a.xml", ASPIRATED)
        second = write(
            tmp_path,
            "b.xml",
            '<supplement name="other"><phones><phone name="tʰ"/></phones></supplement>',
        )
        with pytest.raises(ValueError, match="aspirated-stops already declares"):
            IPAFeatures(supplements=[first, second])

    @pytest.mark.parametrize(
        "block",
        [
            '<features><feature name="loudness"/></features>',
            '<types><type name="quaternary"/></types>',
            '<classes><class name="glyphs"/></classes>',
            '<bridges><bridge name="stridency"/></bridges>',
            "<license>whatever</license>",
        ],
    )
    def test_a_block_that_is_not_an_element_class_is_refused(
        self, tmp_path: Path, block: str
    ) -> None:
        """The line that keeps the feature space fixed.

        A supplement may declare entries in the sections ``<classes>``
        already names and nothing else, because a feature declared here
        would add a key to every bundle -- a term in the metric -- of an
        inventory it is only extending.
        """
        path = write(tmp_path, "x.xml", f'<supplement name="x">{block}</supplement>')
        with pytest.raises(ValueError, match="A supplement may declare entries"):
            IPAFeatures(supplements=[path])

    def test_an_inventory_is_not_a_supplement(self, tmp_path: Path) -> None:
        path = write(tmp_path, "x.xml", '<ipa version="1.1"><phones/></ipa>')
        with pytest.raises(ValueError, match="not <supplement>"):
            IPAFeatures(supplements=[path])

    def test_two_supplements_may_not_share_a_name(self, tmp_path: Path) -> None:
        a = write(tmp_path, "a.xml", ASPIRATED)
        b = write(tmp_path, "b.xml", ASPIRATED.replace('name="pʰ"', 'name="qʰ"'))
        with pytest.raises(ValueError, match="already loaded"):
            IPAFeatures(supplements=[a, b])

    def test_an_entry_in_the_wrong_section_is_refused(self, tmp_path: Path) -> None:
        """``<phones>`` holds ``<phone>``; anything else there loads nowhere."""
        path = write(
            tmp_path,
            "x.xml",
            '<supplement name="x"><phones>'
            '<diacritic name="̑" airstream="implosive"/>'
            "</phones></supplement>",
        )
        with pytest.raises(ValueError, match="would be read by nothing"):
            IPAFeatures(supplements=[path])

    def test_an_entry_with_no_name_is_refused(self, tmp_path: Path) -> None:
        path = write(
            tmp_path,
            "x.xml",
            '<supplement name="x"><phones><phone/></phones></supplement>',
        )
        with pytest.raises(ValueError, match="no name attribute"):
            IPAFeatures(supplements=[path])

    def test_an_entry_that_composes_to_nothing_is_refused(self, tmp_path: Path) -> None:
        """Silence is the failure mode: an undeclared spelling with no
        features would register a phone the metric reads as all-defaults."""
        path = write(
            tmp_path,
            "x.xml",
            '<supplement name="x"><phones><phone name="۩"/></phones></supplement>',
        )
        with pytest.raises(ValueError, match="composes to nothing"):
            IPAFeatures(supplements=[path])


class TestASupplementReachesTheDerivedReads:
    """A table extended and a cached read of it answering from before.

    The derived reads on ``IPAFeatures`` -- ``tie_marks``,
    ``stress_markers``, ``features_by_mode`` and the rest -- are
    ``cached_property``, and loading the base file populates some of them
    on the way through. A supplement extends the tables underneath them,
    so they are dropped rather than left holding the pre-supplement
    answer.
    """

    def test_a_supplemented_diacritic_is_read_off_the_declaration(
        self, ipa: IPAFeatures, tmp_path: Path
    ) -> None:
        """A mark for a value the base spells with no mark at all."""
        assert ipa.declaring_mark("airstream", "implosive") is None
        path = write(
            tmp_path,
            "d.xml",
            '<supplement name="marks"><diacritics>'
            '<diacritic name="̑" airstream="implosive"/>'
            "</diacritics></supplement>",
        )
        f = IPAFeatures(supplements=[path])
        assert f.supplement_of["̑"] == "marks"
        found = f.declaring_mark("airstream", "implosive")
        assert found is not None and found[1] == "̑"
        assert f.get_features("t̑")["airstream"] == "implosive"

    def test_no_cached_read_survives_a_supplement(self, aspirated: Path) -> None:
        """The mechanism, asserted rather than trusted."""
        f = IPAFeatures(supplements=[aspirated])
        assert not (set(_cached_names(f)) & set(f.__dict__))

    def test_which_reads_the_base_load_populates(self) -> None:
        """Pinned, because it is what decides whether the drop above matters.

        Only the tie tables are asked for while the base file loads, so
        today the drop is insurance rather than a fix. If another derived
        read starts being populated at load time this fails, and whether a
        supplement can move it wants looking at. A fresh instance, not the
        session fixture: the point is what *loading* asks for, and a shared
        inventory accumulates whatever the suite has asked it since.
        """
        fresh = IPAFeatures()
        populated = set(_cached_names(fresh)) & set(fresh.__dict__)
        assert populated == {"tie_marks", "tie_bars"}


def _cached_names(ipa: IPAFeatures) -> list[str]:
    """Every ``cached_property`` on the inventory, asked of the class."""
    return [
        name
        for klass in type(ipa).__mro__
        for name, attr in vars(klass).items()
        if isinstance(attr, functools.cached_property)
    ]


class TestToPhoneOnlyGainsAnswers:
    """Adding a supplement turns ``None`` into an answer, and nothing else.

    ``to_phone`` ranks every candidate over the whole phone table, so a
    supplement entry that is more general, or less tied, than an existing
    winner would take bundles the base already answered -- silently, on a
    call that did not change. The base-first rank key is what makes the
    change monotone, and both halves are measured: the direction, and the
    movers the key refuses.
    """

    def bundles(self, ipa: IPAFeatures, units: list[str]) -> dict[str, dict[str, str]]:
        out: dict[str, dict[str, str]] = {}
        for unit in units:
            bundle = {
                k: v
                for k, v in ipa.get_features(unit).items()
                if k not in METADATA_ATTRS
            }
            if bundle:
                out[unit] = bundle
        return out

    def test_over_the_registered_inventory(
        self, ipa: IPAFeatures, supplemented: IPAFeatures
    ) -> None:
        asked = self.bundles(ipa, list(ipa.phones))
        assert len(asked) == len(ipa.phones), "sweep did not run"
        outranked = {
            unit: (was, now)
            for unit, bundle in asked.items()
            if (was := ipa.to_phone(bundle)) != (now := supplemented.to_phone(bundle))
            and was is not None
        }
        assert not outranked, f"a supplement took answers the base gave: {outranked}"

    def test_the_key_is_what_refuses_the_outrank(self, tmp_path: Path) -> None:
        """Pinned so the rank key cannot be dropped as decoration.

        ``č`` declares exactly ``t͡ʃ``'s features and spells them without a
        tie, so it wins on constituent count. Neutralizing the key is the
        same computation with that one term removed.
        """
        ipa = IPAFeatures()
        f = IPAFeatures(supplements=[write(tmp_path, "a.xml", AMERICANIST)])
        bundle = {
            k: v for k, v in ipa.get_features("t͡ʃ").items() if k not in METADATA_ATTRS
        }
        assert ipa.to_phone(bundle) == "t͡ʃ"
        assert f.to_phone(bundle) == "t͡ʃ"
        kept, f.supplement_of = f.supplement_of, {}
        try:
            assert f.to_phone(bundle) == "č"
        finally:
            f.supplement_of = kept

    @pytest.mark.slow
    def test_over_the_whole_unit_corpus(self, tmp_path: Path) -> None:
        """The sweep the fast test samples: every unit that spells itself back.

        The corpus is ``scripts/sweep.py``'s, imported rather than rebuilt,
        for the reason ``docs/reviewing.md`` gives: six rounds rebuilt this
        enumeration by hand and it drifted. Slow because ``to_phone`` reads
        the whole phone table per call.
        """
        from sweep import corpus

        ipa = IPAFeatures()
        units = [unit for unit, _, _ in corpus(ipa)]
        asked = self.bundles(ipa, units)
        assert len(asked) > 8000, f"sweep covered only {len(asked)} units"
        for path, expected_outranked in (
            (write(tmp_path, "a.xml", ASPIRATED), 0),
            (write(tmp_path, "b.xml", AMERICANIST), 0),
        ):
            f = IPAFeatures(supplements=[path])
            outranked = [
                unit
                for unit, bundle in asked.items()
                if (was := ipa.to_phone(bundle)) != f.to_phone(bundle)
                and was is not None
            ]
            assert len(outranked) == expected_outranked, outranked[:5]
        # The same sweep with the key removed: the movers it refuses.
        f = IPAFeatures(supplements=[write(tmp_path, "b.xml", AMERICANIST)])
        f.supplement_of = {}
        taken = [
            unit
            for unit, bundle in asked.items()
            if (was := ipa.to_phone(bundle)) != f.to_phone(bundle) and was is not None
        ]
        assert len(taken) == 25


class TestTheShippedMetricDoesNotMove:
    """The distribution the package normalizes against is the bare inventory's.

    ``f.phones`` is the reference for ``confusability``,
    ``normalized_distance``, ``nearest_phones`` and
    ``DistanceModel.global_``; ``data/confusion.json`` is that reference
    shipped, and ``scripts/confusion.py validate`` guards it. A supplement
    is opt-in per instance, so none of that can see one -- asserted here
    rather than trusted.
    """

    def test_the_default_inventory_takes_no_supplement(self) -> None:
        assert IPAFeatures().supplements == {}
        assert ipakit.load_ipa_features().supplements == {}

    def test_the_shipped_matrix_is_the_bare_inventory(self) -> None:
        shipped = json.loads(
            (ipakit.DATA_DIR / "confusion.json").read_text(encoding="utf-8")
        )
        assert shipped["phones"] == list(IPAFeatures().phones)
        n = len(shipped["phones"])
        assert len(shipped["triangle"]) == n * (n - 1) // 2

    def test_a_supplemented_instance_leaves_the_module_alone(
        self, aspirated: Path
    ) -> None:
        """The module-level reads share one cached inventory; building
        another must not reach it."""
        before = (ipakit.distance("p", "b"), ipakit.confusability("p", "b"))
        loaded = ipakit.load_ipa_features(supplements=[aspirated])
        assert "tʰ" in loaded.phones
        assert (ipakit.distance("p", "b"), ipakit.confusability("p", "b")) == before
        assert "tʰ" not in ipakit.distance_model().reference_phones

    def test_the_shipped_model_still_refuses_a_composed_reference(
        self, aspirated: Path
    ) -> None:
        """The gap registering exists to close, pinned as still open.

        ``for_phoneset`` re-slices the shipped matrix, so a member that
        matrix has no row for is dropped from the reference CDF -- with a
        warning, and the percentiles are then the surviving subset's.
        """
        with pytest.warns(UserWarning, match="dropped from the reference CDF"):
            model = ipakit.distance_model(reference=["p", "t", "k", "tʰ", "s", "a"])
        assert "tʰ" not in model.reference_phones
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            without = ipakit.distance_model(reference=["p", "t", "k", "s", "a"])
        assert model.confusability("tʰ", "t") == without.confusability("tʰ", "t")


class TestASupplementCarriesItsOwnDerivedData:
    def test_derive_puts_the_supplement_in_the_reference(
        self, supplemented: IPAFeatures
    ) -> None:
        model = DistanceModel.derive(supplemented)
        assert "tʰ" in model.reference_phones
        assert len(model.reference_phones) == len(supplemented.phones)
        assert model.reference_name == "ipa+aspirated-stops"

    def test_derive_reproduces_the_shipped_matrix_on_the_bare_inventory(
        self, ipa: IPAFeatures
    ) -> None:
        """The two constructors are one object read two ways.

        A tolerance rather than bytes, for the reason
        ``scripts/confusion.py`` gives: float summation differs in the last
        bit across CPython builds, and a real change moves values by orders
        of magnitude more.
        """
        derived = DistanceModel.derive(ipa)
        shipped = DistanceModel.global_(ipa)
        assert derived.reference_phones == shipped.reference_phones
        for a in ("p", "t", "k", "s", "a", "i", "t͡ʃ"):
            for b in ("b", "d", "ɡ", "z", "u", "m"):
                assert derived.confusability(a, b) == pytest.approx(
                    shipped.confusability(a, b), abs=1e-9
                )

    def test_a_saved_matrix_reads_back(
        self, supplemented: IPAFeatures, tmp_path: Path
    ) -> None:
        model = DistanceModel.derive(supplemented)
        path = model.save(tmp_path / "confusion.json")
        reloaded = DistanceModel.from_matrix_file(supplemented, path)
        assert reloaded.reference_phones == model.reference_phones
        assert reloaded.confusability("tʰ", "t") == model.confusability("tʰ", "t")

    def test_the_percentile_moves_because_the_yardstick_did(
        self, ipa: IPAFeatures, supplemented: IPAFeatures
    ) -> None:
        """What registering buys, in one number.

        ``distance`` is inventory-independent and does not move.
        ``confusability`` is a percentile within the reference
        distribution, and three aspirated stops are three phones' worth of
        new pairs in it -- so the same raw distance reads differently, by
        design. That is the whole reason a supplemented instance needs its
        own derived data rather than the shipped file.
        """
        assert ipa.distance("tʰ", "t") == supplemented.distance("tʰ", "t")
        shipped = DistanceModel.global_(ipa)
        own = DistanceModel.derive(supplemented)
        assert own.confusability("tʰ", "t") != shipped.confusability("tʰ", "t")
