"""What ``compose_unit`` must satisfy: it answers the question, or nothing.

The defect this file exists for was silent in the way ``docs/reviewing.md``
describes. ``compose_unit`` spells a change by appending the mark that
*declares* the wanted value, then verifies by reading the result back and
checking the keys it was asked for. Those keys were right and the answer
was still wrong: ``compose_unit("s", place="bilabial")`` was ``"s̼"``, the
linguolabial fricative, because the linguolabial mark genuinely declares
``place="bilabial"`` and also, independently, ``articulator="tongue-tip"``.
A caller asking for one dimension got two moved, and the self-check could
not see it because it never looked at the dimensions it had not asked
about. Reachable from a rule: ``respell`` cannot spell that change either,
so ``Action`` falls through to here.

The obvious repair is wrong, and is pinned below so it cannot be
reintroduced. Refusing any mark that declares more than was asked also
refuses the devoicing ring, which declares ``phonation="devoiced"`` *and*
``voiced="-"`` -- so ``ɹ̥`` and ``l̥`` stop composing and approximant
devoicing stops firing at all. Those are not two facts. ``voiced`` is the
glottal state read two ways where ``phonation`` reads it four, and
``<projections>`` in ``ipa.xml`` is where the data says so.

So the tests here are about the *distinction*, swept rather than sampled:
every registered phone crossed with every ``(feature, value)`` any
diacritic declares, with each outcome classified by comparing the whole
before and after bundle rather than the requested keys. 8062 cells today,
and the count is derived from the inventory so it cannot go quietly
vacuous.
"""

from __future__ import annotations

import ipakit
import pytest
from ipakit.constants import DATA_DIR, METADATA_ATTRS
from ipakit.features import IPAFeatures

from tests.corpus import assert_swept, self_spelling_phones

FEATURES = ipakit.load_ipa_features()

#: Compositions an allophonic rule actually asks for. Each is a mark that
#: says more than one thing, says only what was asked, or is the sole
#: spelling of its value -- the three shapes the coherence test must not
#: break.
COHERENT = [
    ("ɹ", {"phonation": "devoiced"}, "ɹ̥"),
    ("l", {"phonation": "devoiced"}, "l̥"),
    ("t", {"release": "aspirated"}, "tʰ"),
    ("ɪ", {"nasalized": "+"}, "ɪ̃"),
    ("t", {"release": "no-audible"}, "t̚"),
    ("n", {"syllabic": "+"}, "n̩"),
    ("t", {"release": "nasal"}, "tⁿ"),
    ("t", {"release": "lateral"}, "tˡ"),
]


def declared_pairs(features: IPAFeatures = FEATURES) -> list[tuple[str, str]]:
    """Every ``(feature, value)`` some diacritic declares.

    The write side's whole reachable vocabulary: a request outside it
    cannot be spelled by any mark, so sweeping it is sweeping every
    request that could compose.
    """
    pairs = {
        (key, value)
        for mark in features.diacritics.values()
        for key, value in (getattr(mark, "features", None) or {}).items()
        if key not in METADATA_ATTRS
    }
    return sorted(pairs)


def _bundle(features: IPAFeatures, unit: str) -> dict[str, str]:
    return {
        k: v for k, v in features.get_features(unit).items() if k not in METADATA_ATTRS
    }


def _moved(before: dict[str, str], after: dict[str, str]) -> set[tuple[str, str]]:
    """Every dimension that differs, a dropped key included as an empty value.

    Reading both bundles is the point: a mark's declared features are what
    it claims, and this is what it did.
    """
    return {
        (key, after.get(key, ""))
        for key in set(before) | set(after)
        if before.get(key) != after.get(key)
    }


def restates(
    features: IPAFeatures, pair: tuple[str, str], asked: tuple[str, str]
) -> bool:
    """Are these two ``(feature, value)`` pairs one fact written twice?

    Read off ``ipa.xml``'s ``<projections>``, not off ``compose_unit``'s
    own predicate: a sweep that classifies with the code it is testing
    agrees with a broken implementation as readily as a working one.
    """
    return (
        features.projections.get(pair) == asked
        or features.projections.get(asked) == pair
    )


def sweep(features: IPAFeatures = FEATURES) -> dict[str, list[str]]:
    """Classify every phone x every declared pair. Keyed by outcome.

    ``already`` was true before it was asked for, and the base comes back
    unchanged; ``exact`` moved only the requested keys; ``restated`` also
    moved a dimension that is a declared projection of a requested one
    (the glottal state written both ways); ``incoherent`` moved something
    that varies independently of everything asked for, and must be empty;
    ``refused`` answered ``None``.
    """
    out: dict[str, list[str]] = {
        "already": [],
        "exact": [],
        "restated": [],
        "incoherent": [],
        "refused": [],
    }
    pairs = declared_pairs(features)
    for base in self_spelling_phones():
        before = _bundle(features, base)
        for key, value in pairs:
            got = features.compose_unit(base, **{key.replace("-", "_"): value})
            cell = f"{base} {key}={value}"
            if got is None:
                out["refused"].append(cell)
                continue
            if got == base:
                out["already"].append(cell)
                continue
            extra = _moved(before, _bundle(features, got)) - {(key, value)}
            if not extra:
                out["exact"].append(f"{cell} -> {got}")
            elif all(restates(features, e, (key, value)) for e in extra):
                out["restated"].append(f"{cell} -> {got}")
            else:
                out["incoherent"].append(f"{cell} -> {got} moved {sorted(extra)}")
    return out


@pytest.fixture(scope="module")
def swept() -> dict[str, list[str]]:
    return sweep()


class TestAComposedUnitMovesOnlyWhatWasAsked:
    """The property the old read-back check could not see."""

    def test_the_sweep_covers_every_phone_and_every_spellable_request(self, swept):
        phones = self_spelling_phones()
        assert_swept(len(phones), phones)
        pairs = declared_pairs()
        # Exact, and derived: a floor cannot tell that a whole feature
        # dropped out of the diacritic inventory.
        # 58 before the boundary marks declared their tiers: '|' phrase,
        # '‖' utterance, '‿' word. All three are requests no mark can
        # spell, and they are counted here because the sweep is over the
        # whole declared vocabulary, not the spellable part of it.
        # 61 before the six contour diacritics declared their level
        # sequences: a contour is a sequence of tone values, so each of the
        # six names a tone that is not one of the five levels.
        assert len(pairs) == 67, f"{len(pairs)} declared pairs, not 67"
        assert sum(len(v) for v in swept.values()) == len(phones) * len(pairs) == 9313

    def test_no_composition_moves_a_dimension_nobody_asked_for(self, swept):
        assert swept["incoherent"] == [], (
            f"{len(swept['incoherent'])} incoherent compositions, "
            f"first: {swept['incoherent'][:3]}"
        )

    def test_the_headline_case_is_refused_rather_than_answered_wrongly(self):
        """``s̼`` declares the requested place and a different articulation."""
        assert FEATURES.compose_unit("s", place="bilabial") is None
        # The mark itself is unharmed: asked for what it actually spells,
        # it still composes.
        assert FEATURES.compose_unit("s", articulator="tongue-tip") == "s̺"

    def test_the_refusal_is_a_class_not_a_spot_fix(self, swept):
        """Every phone, not just ``s``: no mark can *make* a segment bilabial.

        The eight phones that already are bilabial are not refused, they
        are unchanged -- asking for a value a unit already carries is a
        no-op, which is what ``respell`` has always answered. The two
        classes together are still the whole inventory, which is what
        makes this a class and not a spot fix.
        """
        refused = [c for c in swept["refused"] if c.endswith("place=bilabial")]
        already = [c for c in swept["already"] if c.endswith("place=bilabial")]
        assert len(refused) + len(already) == len(self_spelling_phones()) == 139
        assert {c.split()[0] for c in already} == {
            p
            for p in self_spelling_phones()
            if FEATURES.get_features(p).get("place") == "bilabial"
        }
        assert already, "the no-op class went empty; this test would be vacuous"

    def test_where_a_value_has_a_clean_mark_and_a_dirty_one_the_clean_one_wins(self):
        """Two orderings agree here, and the agreement is measured.

        A declared value is *contested* where it is spelled both by a mark
        that says only that value and by a mark that also moves an
        independent dimension. Screening the candidates is what makes the
        clean one win; the "fewest declared features" ordering picks the
        same mark today, and ``docs/reviewing.md`` records what happens when
        two orderings agree only by habit. So the set is enumerated rather
        than trusted, and the answer checked.

        One pair, and it is prosody that shrank the set: four of the five
        were tone and contour values a contour diacritic declared *beside*
        another prosodic key. A contour is a sequence of levels, so those
        marks now declare one key each and contest nothing. The remaining
        pair is the only segmental one, and it is the one this test is for.
        """
        contested: dict[tuple[str, str], set[bool]] = {}
        for pair in declared_pairs():
            key, value = pair
            marks = [
                mark
                for mark in FEATURES.diacritics.values()
                if (mark.features or {}).get(key) == value
            ]
            verdicts = {
                all(
                    declared == value or restates(FEATURES, (name, declared), pair)
                    for name, declared in (mark.features or {}).items()
                    if name not in METADATA_ATTRS
                )
                for mark in marks
            }
            if len(verdicts) > 1:
                contested[pair] = verdicts
        # One, and prosody is what emptied the rest. Four of the five were
        # tone and contour values a compound tone diacritic declared beside
        # another prosodic key. A contour is a sequence of levels, so each
        # of those marks now declares one key -- its own level sequence --
        # and contests nothing. The remaining pair is the only segmental
        # one, and it is the one this test is for.
        assert set(contested) == {("articulator", "tongue-tip")}, sorted(contested)
        # Segmental, so composable at all: the apical mark answers it, not
        # the linguolabial.
        assert FEATURES.compose_unit("s", articulator="tongue-tip") == "s̺"


class TestTheCoherentCompositionsStillCompose:
    """The regression the wrong fix caused, kept where it can be seen."""

    @pytest.mark.parametrize("base,changes,want", COHERENT)
    def test_the_compositions_a_rule_asks_for(self, base, changes, want):
        got = FEATURES.compose_unit(base, **changes)
        assert got == want, f"{base} {changes} -> {got!r}, wanted {want!r}"

    def test_devoicing_is_reachable_from_either_spelling(self):
        """Both directions of the projection, because the marks state both.

        Asking ``phonation`` gets ``voiced`` along with it; asking
        ``voiced`` gets ``phonation``. Refusing the second direction
        would cost most of the compositions that move a restated
        dimension, which is why the test is not one-sided.

        The phone has to be one the value is *not* already true of.
        ``compose_unit("s", voiced="-")`` is ``"s"``, not ``"s̥"``: /s/ is
        voiceless already and the ring would be a second, unrequested
        claim (``phonation="devoiced"`` is a normally-voiced segment
        realized without voice). That is a no-op, and the shipped German
        set spelled 3582 of them before it was one.
        """
        assert FEATURES.compose_unit("ɹ", phonation="devoiced") == "ɹ̥"
        assert FEATURES.compose_unit("ɹ", voiced="-") == "ɹ̥"
        assert FEATURES.compose_unit("s", phonation="modal") == "s̬"
        assert FEATURES.compose_unit("s", voiced="+") == "s̬"
        assert FEATURES.compose_unit("s", voiced="-") == "s"

    def test_the_restated_class_is_populated_and_is_only_the_glottal_state(self, swept):
        """A count above a floor cannot say *which* dimension was restated.

        264 today. It was 394 while a request already true of the base
        composed a mark anyway -- 130 of those were a devoicing ring on
        a segment that was voiceless to begin with, which is now the
        no-op ``already`` class.
        """
        assert len(swept["restated"]) > 200, f"only {len(swept['restated'])}"
        keys = {cell.split()[1].split("=")[0] for cell in swept["restated"]}
        assert keys == {"phonation", "voiced"}, keys

    def test_the_shipped_english_rules_still_devoice(self):
        """The end the regression was measured at: the rule fires or it does not."""
        from ipakit.rules import shipped

        english = shipped("american-english")
        assert english.apply("pɹɪnt") == "pɹ̥ɪ̃nt̚"
        assert english.apply("plʌs") == "pl̥ʌs"


class TestAskingForWhatIsAlreadyTrueIsANoOp:
    """A value the base already carries gets no second mark.

    The same silent shape as the headline defect and one layer further
    in: the read-back checked that the requested value was there
    afterwards, and a doubled mark passes that -- ``ɪ̃`` wearing a second
    tilde still reads ``nasalized="+"`` and moves nothing else. So the
    guard measured the bundle while the defect was in the *spelling*,
    and ``validate_ipa`` was calling the result ``duplicate_diacritic``
    all along.

    It reached shipped output on ordinary input: American English spelled
    *hidden* ``ˈhɪdⁿn̩̩``, because the nasal-release rule and the
    syllabic-nasal rule both fired on the same nasal. Over five shipped
    sets and 40322 forms, correcting it moved 3637 outputs and every one
    of them lost a mark that said nothing new.

    ``respell`` was already right (``respell("ɫ", velarized="+")`` is
    ``"ɫ"``), so this is the two halves of one question agreeing again.
    """

    @pytest.mark.parametrize(
        ("unit", "changes"),
        [
            ("ɪ̃", {"nasalized": "+"}),
            ("n̩", {"syllabic": "+"}),
            ("pʰ", {"release": "aspirated"}),
            ("ɫ", {"velarized": "+"}),
            ("s", {"voiced": "-"}),
            ("b", {"place": "bilabial"}),
        ],
    )
    def test_the_unit_comes_back_unchanged(self, unit, changes):
        assert FEATURES.compose_unit(unit, **changes) == unit

    def test_a_mixed_request_still_writes_the_half_that_is_new(self):
        # Not an early return: one value already held and one to write
        # composes the one to write, and only that one.
        assert FEATURES.compose_unit("ɪ̃", nasalized="+", release="aspirated") == "ɪ̃ʰ"

    def test_it_holds_over_the_whole_corpus(self):
        """Every self-spelling unit x every value it already carries.

        The sweep, not the three cases that were reported: 14680 of these
        answered with a longer spelling before, and another 157994 with
        ``None`` where the honest answer is the unit itself.
        """
        from tests.corpus import self_spelling_phones

        checked, wrong = 0, []
        for unit in self_spelling_phones():
            for mark in list(FEATURES.diacritics)[:24]:
                for text in (unit, unit + mark):
                    if FEATURES.segment(text).to_ipa() != text:
                        continue
                    bundle = _bundle(FEATURES, text)
                    for key, value in bundle.items():
                        if key not in FEATURES.features:
                            continue
                        checked += 1
                        got = FEATURES.compose_unit(
                            text, **{key.replace("-", "_"): value}
                        )
                        if got != text:
                            wrong.append(f"{text!r} [{key}={value}] -> {got!r}")
        assert checked > 5000, f"sweep did not run: {checked}"
        assert wrong == [], f"{len(wrong)} moved, first: {wrong[:5]}"

    def test_the_shipped_english_set_spells_hidden_once(self):
        from ipakit.rules import shipped

        assert shipped("american-english").apply("ˈhɪdn̩") == "ˈhɪdⁿn̩"
        assert ipakit.validate_ipa("ˈhɪdⁿn̩") == []

    def test_german_still_devoices_what_is_voiced(self):
        # The correction must not have turned the rule off: it fires on a
        # voiced obstruent and no longer writes a ring on a voiceless one.
        from ipakit.rules import shipped

        german = shipped("german-final-devoicing")
        assert german.apply("hund") == "hunt"
        assert german.apply("taɡ") == "tak"
        assert german.apply("cʰ") == "cʰ"


class TestWhatCannotBeComposedIsSaidOutLoud:
    """Pin the escapes: a request no mark can spell is refused, and the
    reasons are enumerated so the list can only change deliberately."""

    def test_the_wholly_unspellable_requests_are_the_declared_ones_plus_one(
        self, swept
    ):
        composed = {
            cell.split(" -> ")[0].split(" ", 1)[1]
            for kind in ("exact", "restated")
            for cell in swept[kind]
        }
        dead = {f"{k}={v}" for k, v in declared_pairs()} - composed
        # Prosodic and structural features live on the unit, outside the
        # feature bag (docs/ties.md), so no amount of marking puts them in
        # a composed bundle: read off the declared mode rather than listed.
        outside = {
            f"{k}={v}"
            for k, v in declared_pairs()
            if FEATURES.features[k].mode in ("prosodic", "structural")
        }
        # 21 before 'level' was declared structural and the boundary marks
        # declared their tiers; the derived read picked all three up with no
        # case added here, which is the whole point of reading the mode.
        # 24 before the six contour diacritics declared their level
        # sequences, which are prosodic and so outside the bag too.
        assert len(outside) == 30, f"{len(outside)} pairs outside the bag"
        # The one segmental request the inventory cannot spell cleanly. If
        # a mark for it is ever added, this fails and should.
        assert dead == outside | {"place=bilabial"}, sorted(dead ^ outside)

    def test_a_request_the_data_does_not_declare_still_raises(self):
        with pytest.raises(ValueError, match="not a value of feature"):
            FEATURES.compose_unit("t", place="nonsense")
        with pytest.raises(ValueError, match="unknown feature"):
            FEATURES.compose_unit("t", nonsense="+")
        with pytest.raises(ValueError, match="at least one feature"):
            FEATURES.compose_unit("t")


class TestAMisdeclaredProjectionFailsOnLoad:
    """The declaration is load-bearing, so a wrong one must not load.

    A projection that named the wrong feature, or covered only some of the
    finer feature's values, would silently widen or narrow what counts as
    one fact -- which is exactly the class of quiet data error
    ``docs/reviewing.md`` says to let fail loudly.
    """

    ORIGINAL = '<value name="devoiced" reads="-"/>'

    def _load(self, tmp_path, replacement: str) -> IPAFeatures:
        text = (DATA_DIR / "ipa.xml").read_text(encoding="utf-8")
        assert text.count(self.ORIGINAL) == 1, "the projection moved; fix this test"
        path = tmp_path / "ipa.xml"
        path.write_text(text.replace(self.ORIGINAL, replacement), encoding="utf-8")
        return IPAFeatures(xml_path=path)

    def test_the_unmodified_data_loads(self, tmp_path):
        """So a failure below is the edit, not the harness."""
        assert self._load(tmp_path, self.ORIGINAL).projections

    def test_a_value_left_unmapped_is_refused(self, tmp_path):
        with pytest.raises(ValueError, match="unmapped"):
            self._load(tmp_path, "")

    def test_a_value_the_finer_feature_does_not_declare_is_refused(self, tmp_path):
        with pytest.raises(ValueError, match="does not declare"):
            self._load(tmp_path, self.ORIGINAL + '<value name="whispered" reads="-"/>')

    def test_a_reading_the_coarser_feature_does_not_declare_is_refused(self, tmp_path):
        with pytest.raises(ValueError, match="which feature 'voiced' does not"):
            self._load(tmp_path, '<value name="devoiced" reads="maybe"/>')

    def test_an_undeclared_feature_is_refused(self, tmp_path):
        text = (DATA_DIR / "ipa.xml").read_text(encoding="utf-8")
        path = tmp_path / "ipa.xml"
        path.write_text(text.replace('to="voiced"', 'to="vioced"'), encoding="utf-8")
        with pytest.raises(ValueError, match="undeclared feature 'vioced'"):
            IPAFeatures(xml_path=path)

    def test_a_feature_projected_onto_itself_is_refused(self, tmp_path):
        text = (DATA_DIR / "ipa.xml").read_text(encoding="utf-8")
        path = tmp_path / "ipa.xml"
        path.write_text(
            text.replace('from="phonation" to="voiced"', 'from="voiced" to="voiced"'),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="onto itself"):
            IPAFeatures(xml_path=path)
