"""`∅`: a position a transcription keeps open with no segment in it.

Its own element class in ``ipa.xml``, alongside ``<separators>``. Not a
phone -- that would take the inventory from 139 to 140 and move
``confusion.json``, which is the wrong reason to touch the metric. Not a
diacritic either: a diacritic modifies the segment it is written on, and
a zero is exactly the case where there is no segment to write on.

Distinct from ``␣``. Silence is a registered phone with
``manner="silence"``, a segment with duration; a zero is the absence of
one. Both are conventions off the IPA chart, and they are not the same
thing.

Deletion is untouched: ``x -> ∅`` keeps writing nothing, because ``∅``
is already the rule notation for the empty string and the shipped rule
sets read it that way -- ``∅ -> ə`` is epenthesis in two of them, so
freeing the glyph would silently change every shipped insertion rule.
Emitting a zero is a different statement, written ``[zero]``: brackets
already mean *described, not spelled*, ``zero`` is a declared element
class rather than a magic word, and the notation was a hard error
before, so it collides with nothing.

The last class pins what a zero does *not* do. Those are decisions for
the owner rather than oversights to fix here.
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import ipakit
import pytest
from ipakit import IPAFeatures
from ipakit.constants import DEFAULT_IPA_FEATS
from ipakit.form import Form, zeros
from ipakit.rules import RuleError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from invariants import CHART, check_zero  # noqa: E402

FEATURES = IPAFeatures()


class TestTheZeroIsAPosition:
    """`∅` keeps a slot open and contributes no sound."""

    def test_the_shipped_inventory_passes_the_invariant(self) -> None:
        assert check_zero(FEATURES)

    def test_it_is_declared_in_its_own_class(self) -> None:
        assert "zeros" in FEATURES.classes
        assert set(zeros(FEATURES)) == {"∅"}
        assert "∅" not in FEATURES.phones
        assert "∅" not in FEATURES.diacritics
        assert "∅" not in FEATURES.separators

    def test_the_loader_routes_it_like_any_other_class(self) -> None:
        # It used to be read by a second opener of ipa.xml, because
        # `_load_element` routed four classes and dropped the rest.
        assert set(FEATURES.zeros) == {"∅"}
        assert zeros(FEATURES) == {
            s: dict(p.features or {}) for s, p in FEATURES.zeros.items()
        }
        assert FEATURES.zeros["∅"].features["class"] == "zero"

    def test_every_declared_class_has_a_table(self) -> None:
        # The property, not the four names: a class in <classes> that no
        # table takes is a section that loads into nowhere.
        singular = {name[:-1] for name in FEATURES.classes}
        routed = {
            (declared.features or {}).get("class")
            for table in (
                FEATURES.phones,
                FEATURES.diacritics,
                FEATURES.separators,
                FEATURES.zeros,
            )
            for declared in table.values()
        }
        assert singular == {"phone", "diacritic", "suprasegmental", "separator", "zero"}
        assert singular <= routed | {"suprasegmental"}, singular - routed


class TestAnUnroutedClassIsRefused:
    """The silent drop that put `<zeros>` behind a second parser.

    `_load_element` named four classes and dropped everything else, so a
    fifth block loaded into nothing with a green suite and no diagnostic.
    It is a load-time refusal now, which is the only thing that makes the
    routing and the data unable to disagree.
    """

    def _with_class(self, tmp_path: Path, block: str) -> Path:
        text = DEFAULT_IPA_FEATS.read_text(encoding="utf-8")
        anchor = '<class name="zeros"/>'
        assert text.count(anchor) == 1, "the class list moved; fix this test"
        text = text.replace(anchor, anchor + '<class name="widgets"/>')
        text = text.replace("<zeros>", block + "<zeros>", 1)
        path = tmp_path / "ipa.xml"
        path.write_text(text, encoding="utf-8")
        return path

    def test_a_class_with_no_table_fails_to_load(self, tmp_path: Path) -> None:
        path = self._with_class(tmp_path, '<widgets><widget name="Ω"/></widgets>')
        with pytest.raises(ValueError, match="routed into no table"):
            IPAFeatures(path)

    def test_the_message_names_the_class_and_the_symbol(self, tmp_path: Path) -> None:
        path = self._with_class(tmp_path, '<widgets><widget name="Ω"/></widgets>')
        with pytest.raises(ValueError) as caught:
            IPAFeatures(path)
        assert "widget" in str(caught.value)
        assert "widgets" in str(caught.value)
        assert "Ω" in str(caught.value)

    def test_a_declared_class_with_no_section_is_not_an_error(
        self, tmp_path: Path
    ) -> None:
        # Nothing is dropped when nothing is there, so this must load.
        # Pinned so the refusal cannot creep into "declared" from
        # "declared and populated".
        path = self._with_class(tmp_path, "")
        assert set(IPAFeatures(path).zeros) == {"∅"}

    def test_it_round_trips_and_is_not_a_phone(self) -> None:
        form = Form.parse("le∅ʃjɛ̃", FEATURES)
        assert form.to_ipa() == "le∅ʃjɛ̃"
        assert form.phones == ("l", "e", "ʃ", "j", "ɛ̃")
        assert [s.to_ipa() for s in form.segments] == ["l", "e", "ʃ", "j", "ɛ̃"]

    def test_it_is_neither_a_segment_nor_a_boundary(self) -> None:
        (unit,) = [u for u in Form.parse("le∅ʃ", FEATURES).units if u.is_zero]
        assert unit.segment is None
        assert not unit.is_boundary
        assert unit.level is None
        assert not unit.transparent

    def test_it_does_not_split_the_tree_or_count_as_a_boundary(self) -> None:
        form = Form.parse("le∅ʃ", FEATURES)
        assert form.boundaries == ()
        assert len(form.tree(FEATURES).at("word")) == 1

    def test_it_does_not_shift_attribute_positions(self) -> None:
        # `Attribute.at` indexes the segmental projection, so a position
        # that contributes no segment must not advance it.
        form = Form.parse("le∅ʃˈa", FEATURES)
        (attribute,) = form.attributes
        assert (attribute.feature, attribute.value) == ("stress", "primary")
        # Four phones, and the stress rides the fourth: the zero occupies
        # a position in the form and none in the projection it indexes.
        assert form.phones == ("l", "e", "ʃ", "a")
        assert attribute.at == 3
        assert form.phones[attribute.at] == "a"

    def test_it_carries_no_phonetic_features(self) -> None:
        bundle = zeros(FEATURES)["∅"]
        structural = set(FEATURES.features_by_mode.get("structural", ()))
        assert not (set(bundle) & (set(FEATURES.features) - structural))

    def test_the_inventory_and_the_metric_do_not_move(self) -> None:
        assert len(FEATURES.phones) == 139
        # Nothing about the zero can reach a distance: it is in no table
        # the metric reads.
        assert ipakit.distance("t", "d") == pytest.approx(0.05)


class TestZeroIsNotSilence:
    """Both are off the chart; they are not the same thing."""

    def test_silence_is_a_phone_and_the_zero_is_not(self) -> None:
        assert "␣" in FEATURES.phones
        assert FEATURES.get_features("␣")["manner"] == "silence"
        assert "∅" not in FEATURES.phones

    def test_silence_contributes_a_phone_and_the_zero_does_not(self) -> None:
        assert Form.parse("a␣b", FEATURES).phones == ("a", "␣", "b")
        assert Form.parse("a∅b", FEATURES).phones == ("a", "b")

    def test_both_are_marked_off_the_chart(self) -> None:
        assert FEATURES.notation_of("␣") != CHART
        assert FEATURES.notation_of("∅") != CHART


class TestTheFlatApiReadsTheDeclaration:
    """The parser called unknown what `<zeros>` declares, and said so by
    quietly shortening the string.

    Three reads disagreed with the data at once, which is why fixing one
    of them would have been worse than fixing none: `parse` dropped the
    zero as an unregistered symbol *and warned*, `validate_ipa` reported
    `unknown_symbol`, and `describe` answered "unknown phone". The
    reproducing case was this library's own output --
    `rewrite("lezami", "z -> [zero] / [vowel] _ [vowel]")` is `le∅ami`,
    which `is_valid_ipa` then rejected.

    A zero is now what a separator already was: a declared mark that
    carries no unit, dropped by the flat reads without complaint and kept
    by `Form`.
    """

    def test_the_flat_reads_drop_it_in_silence(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            assert ipakit.tokenize("le∅ʃ") == ["l", "e", "ʃ"]
        assert not caught, [str(c.message) for c in caught]

    def test_strict_does_not_raise_on_a_declared_zero(self) -> None:
        # `strict=True` is for what cannot be represented. A zero is
        # declared, so there is nothing to refuse -- the same answer
        # `strict` gives a syllable break.
        assert FEATURES.parse("le∅ʃ", strict=True) == FEATURES.parse("leʃ", strict=True)
        assert ipakit.tokenize("le∅ʃ", strict=True) == ["l", "e", "ʃ"]

    def test_it_validates(self) -> None:
        assert FEATURES.validate_ipa("le∅ami") == []
        assert ipakit.is_valid_ipa("le∅ami")

    def test_our_own_output_validates(self) -> None:
        # The case that reported the defect: a rule wrote a zero and the
        # validator rejected the result.
        produced = ipakit.rewrite("lezami", "z -> [zero] / [vowel] _ [vowel]")
        assert produced == "le∅ami"
        assert ipakit.is_valid_ipa(produced)

    def test_describe_answers_from_the_declaration(self) -> None:
        # The word is the element class the data gives it, so renaming
        # the class in ipa.xml renames the description. Pinned as the
        # derived read *and* as today's sentence, so neither can drift
        # without this failing.
        (symbol,) = FEATURES.zeros
        declared = FEATURES.zeros[symbol].features["class"]
        assert ipakit.describe(symbol) == f"{declared}: a position with no segment"
        assert ipakit.describe(symbol) == "zero: a position with no segment"
        assert "unknown" not in ipakit.describe(symbol)

    def test_describe_invents_no_phonetics_for_it(self) -> None:
        # It carries no phonetic features, and the description must not
        # supply any: that empty bag is what keeps the zero out of the
        # metric by construction.
        assert FEATURES.get_features("∅") == {}
        said = ipakit.describe("∅")
        values = {
            v
            for name, feature in FEATURES.features.items()
            if name not in ("class",)
            for v in feature.values
        }
        assert not [v for v in values if v and v in said.split()]

    def test_all_three_reads_agree_for_every_declared_zero(self) -> None:
        # The property, not the one symbol: a second zero declared in
        # ipa.xml would have to pass this too, and no read may be fixed
        # without the others -- a string that validates while `describe`
        # still calls it unknown is a new inconsistency, not a fix.
        assert FEATURES.zeros, "no zero declared: this sweep would be vacuous"
        for symbol in FEATURES.zeros:
            text = f"le{symbol}ami"
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                assert ipakit.tokenize(text) == ["l", "e", "a", "m", "i"]
            assert not caught
            assert FEATURES.validate_ipa(text) == []
            assert "unknown" not in ipakit.describe(symbol)
            assert [u.text for u in Form.parse(text, FEATURES).units] == [
                "l",
                "e",
                symbol,
                "a",
                "m",
                "i",
            ]

    def test_the_tokenizer_and_the_validator_ask_one_question(self) -> None:
        # Made equal by construction rather than by habit: both read
        # `carries_no_segment`, so a class added to ipa.xml cannot be
        # known to one and unknown to the other. This is exactly how the
        # zero came to be dropped by `parse` and reported by
        # `validate_ipa` -- each named `separators` on its own.
        assert FEATURES.carries_no_segment == frozenset(
            FEATURES.separators
        ) | frozenset(FEATURES.zeros)
        checked = 0
        for symbol in FEATURES.carries_no_segment:
            checked += 1
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                FEATURES.parse(f"a{symbol}b")
            assert not caught, symbol
            codes = {i["code"] for i in FEATURES.validate_ipa(f"a{symbol}b")}
            assert "unknown_symbol" not in codes, symbol
        assert checked == len(FEATURES.carries_no_segment) >= 3

    @pytest.mark.parametrize(
        ("text", "codes"),
        [
            ("a∅b", []),
            ("∅ab", []),
            ("ab∅", []),
            ("a∅∅b", []),
            ("a∅.b", []),
            ("a.∅b", []),
            ("a∅#", []),
            ("a‿∅‿b", []),
            # A form of nothing but marks names no sound, and a zero is
            # not an exception: it is a position, and a position is not a
            # sound. Warning, never error -- the form still round trips.
            ("∅", ["no_segments"]),
            ("∅∅", ["no_segments"]),
            # ...but the constituent a zero stands in is *not*
            # degenerate. `Form.tree` keeps the syllable in ".∅." and the
            # word in "#∅#" where it discards both in ".." and "##", and
            # `empty_constituent` exists to report a constituent that was
            # asserted and then discarded.
            (".∅.", ["no_segments"]),
            ("#∅#", ["no_segments"]),
            ("a.∅.b", []),
            ("a#∅#b", []),
            ("a..b", ["empty_constituent"]),
            # A zero has no segment to write a mark on, and no unit for a
            # tie to bind. Both stay errors.
            ("a∅̃b", ["orphan_diacritic"]),
            ("a∅͡b", ["malformed_tie"]),
            ("∅͡a", ["malformed_tie"]),
        ],
    )
    def test_the_degenerate_cases(self, text: str, codes: list[str]) -> None:
        assert [i["code"] for i in FEATURES.validate_ipa(text)] == codes

    def test_the_constituent_a_zero_stands_in_survives(self) -> None:
        # The measurement the case above turns on, asserted rather than
        # believed: with a zero between them the tree keeps the node,
        # without one it discards it.
        def nodes(text: str, tier: str) -> list[str]:
            return [
                n.to_ipa() for n in Form.parse(text, FEATURES).tree(FEATURES).at(tier)
            ]

        assert nodes(".∅.", "syllable") == ["∅"]
        assert nodes("..", "syllable") == []
        assert nodes("#∅#", "word") == ["∅"]
        assert nodes("##", "word") == []

    def test_the_metric_still_cannot_see_it(self) -> None:
        # Accepting the zero at the parse gate must not let it reach a
        # distance: it carries no features, so a word containing one
        # measures as the word without it, the way the linking mark does.
        assert len(FEATURES.phones) == 139
        assert ipakit.word_distance("le∅ami", "leami").edit_cost == 0.0
        assert ipakit.word_distance("lez‿ami", "lezami").edit_cost == 0.0


class TestDeletionStillWritesNothing:
    """`x -> ∅` must keep its output: four shipped rule sets read it.

    `∅` is the rule notation for the empty string (`rules.NULL`), and
    registering the same glyph as a form symbol must not turn a deletion
    into an insertion of a zero. Emitting one is opt-in and unbuilt.
    """

    @pytest.mark.parametrize(
        ("text", "spec", "want"),
        [
            ("lez‿ami", "z -> ∅ / _ #", "le‿ami"),
            ("lez ami", "z -> ∅ / _ #", "le ami"),
            ("atəm", "ə -> ∅ / [vowel] [manner=plosive] _", "atm"),
            ("kæt", "∅ -> ə / _ #", "kætə"),
            ("#kæt#", "∅ -> ə / # _", "#əkæt#"),
        ],
    )
    def test_the_output_is_unchanged(self, text: str, spec: str, want: str) -> None:
        assert ipakit.rewrite(text, spec) == want

    def test_no_shipped_rule_set_emits_a_zero(self) -> None:
        # Every shipped set over a word list, rather than the deletion
        # rules someone remembered: a rule that started emitting zeros
        # would show up in the output whatever its shape.
        from ipakit.rules import available, shipped

        words = [
            "lez‿ami",
            "lezami",
            "les ʃjɛ̃",
            "ˈbʊtɚ",
            "ˈkætəl",
            "hunde",
            "tan.to",
            "es.pa.ɲol",
            "ni.ho.ɴ",
            "aktəm",
        ]
        checked = 0
        names = available()
        assert len(names) >= 4, "no shipped rule sets found"
        for name in names:
            rules = shipped(name, FEATURES)
            for word in words:
                checked += 1
                assert "∅" not in rules.apply(word)
        assert checked > 40, "sweep did not run"


class TestEmittingAZero:
    """`z -> [zero]`: the position had content, and now has none.

    Different from `z -> ∅`, which says the /z/ is gone and leaves no
    position behind. A latent consonant needs the first: a /z/ was here
    and could surface.
    """

    def test_the_notation_was_free_before_it_meant_this(self) -> None:
        # The claim this feature was built on, checked rather than
        # assumed. On the right `[zero]` resolved to no 'key=value'
        # terms; on the left and in a context it resolved to no feature
        # terms. Both were refusals, so nothing was reinterpreted.
        base = IPAFeatures()
        base.zeros.clear()  # the inventory as it reads with no <zeros>
        for spec in (
            "z -> [zero]",
            "[zero] -> z",
            "t -> ʔ / _ [zero]",
            "∅ -> [zero] / a _ b",
        ):
            with pytest.raises(RuleError):
                ipakit.rules.parse(spec, base)

    def test_a_zero_is_written_where_the_segment_was(self) -> None:
        assert ipakit.rewrite("lez", "z -> [zero] / _ #") == "le∅"
        assert ipakit.rewrite("lez‿ami", "z -> [zero] / _ #") == "le∅‿ami"

    def test_deletion_and_a_zero_are_different_statements(self) -> None:
        assert ipakit.rewrite("lez", "z -> ∅ / _ #") == "le"
        assert ipakit.rewrite("lez", "z -> [zero] / _ #") == "le∅"
        # And what is left behind is a position, not a sound.
        form = Form.parse(ipakit.rewrite("lez", "z -> [zero] / _ #"), FEATURES)
        assert form.phones == ("l", "e")
        assert [u.is_zero for u in form.units] == [False, False, True]

    def test_a_zero_can_be_filled_and_unwritten(self) -> None:
        assert ipakit.rewrite("le∅ʃ", "[zero] -> z") == "lezʃ"
        assert ipakit.rewrite("le∅ʃ", "[zero] -> ∅") == "leʃ"

    def test_the_notation_reads_off_the_declaration(self) -> None:
        # '[zero]' is the element CLASS those symbols carry, and the
        # symbol written is the one declared -- neither is spelled in
        # rules.py, so renaming the class moves the notation with it.
        (symbol,) = FEATURES.zeros
        (declared_class,) = {p.features["class"] for p in FEATURES.zeros.values()}
        assert ipakit.rewrite("lez", f"z -> [{declared_class}] / _ #") == "le" + symbol

    @pytest.mark.parametrize(
        "spec",
        [
            "∅ -> [zero] / a _ b",  # an insertion had no content to lose
            "[zero] -> [voiced=+]",  # a zero has no bundle to change
            ". -> [zero]",  # a boundary is a relation, not a position
        ],
    )
    def test_what_a_zero_may_not_do_is_refused_loudly(self, spec: str) -> None:
        with pytest.raises(RuleError):
            ipakit.rule(spec)

    def test_no_shipped_rule_set_is_disturbed(self) -> None:
        # '∅' on the left still means "insert here" everywhere it is
        # shipped, which is what freeing the glyph would have broken.
        from ipakit.rules import available, shipped

        checked = 0
        for name in available():
            rules = shipped(name, FEATURES)
            for rule in rules.rules:
                checked += 1
                assert "[zero]" not in rule.source
        assert checked > 40, "sweep did not run"
        assert ipakit.rewrite("kæt", "∅ -> ə / _ #") == "kætə"


class TestTransparencyIsSelectable:
    """Whether a zero blocks a context is the rule's decision.

    It depends on what the zero is being used for: a latent consonant's
    zero should not stop a rule about the vowels either side, and a zero
    standing for an empty mora is a position that counts. So the default
    is unchanged -- a zero is a position and blocks -- and a rule that
    wants to reach across one says so where it wants it, with the
    parenthesis generative phonology already uses for an optional
    element.
    """

    def test_a_zero_blocks_by_default(self) -> None:
        assert ipakit.rewrite("leʃ", "e -> a / _ ʃ") == "laʃ"
        assert ipakit.rewrite("le∅ʃ", "e -> a / _ ʃ") == "le∅ʃ"

    def test_an_optional_zero_is_stepped_over(self) -> None:
        spec = "e -> a / _ (∅) ʃ"
        assert ipakit.rewrite("le∅ʃ", spec) == "la∅ʃ"
        assert ipakit.rewrite("leʃ", spec) == "laʃ"

    def test_naming_it_without_the_parentheses_requires_it(self) -> None:
        # The third reading, and the one that was already available: the
        # rule that wants the zero to be there names it.
        spec = "e -> a / _ [zero] ʃ"
        assert ipakit.rewrite("le∅ʃ", spec) == "la∅ʃ"
        assert ipakit.rewrite("leʃ", spec) == "leʃ"

    def test_it_holds_on_either_side_of_the_target(self) -> None:
        assert ipakit.rewrite("ʃ∅e", "e -> a / ʃ (∅) _") == "ʃ∅a"
        assert ipakit.rewrite("ʃe", "e -> a / ʃ (∅) _") == "ʃa"

    def test_an_absent_optional_item_licenses_no_unit(self) -> None:
        rule = ipakit.rule("e -> a / _ (∅) ʃ")
        (present,) = rule.recognize("le∅ʃ")
        (absent,) = rule.recognize("leʃ")
        assert present.right == (2, 3)
        assert absent.right == (None, 2), "one entry per item, whether or not it took"

    def test_only_a_zero_may_be_optional_today(self) -> None:
        # A pinned escape: optionality is not general, because an
        # optional boundary would have to answer to the boundary-run
        # rule and the virtual edge. If this starts passing, the limit
        # has moved and this test is where to say so.
        for spec in ("t -> x / _ (t)", "t -> x / _ ([vowel])", "t -> x / _ (#)"):
            with pytest.raises(RuleError):
                ipakit.rule(spec)
        with pytest.raises(RuleError):
            ipakit.rule("(∅) -> t")

    def test_no_shipped_rule_has_an_optional_item(self) -> None:
        # Optionality is new notation, so nothing shipped can be reading
        # differently because of it. Asked of the parsed patterns rather
        # than of the source: two shipped rules carry parentheses in
        # their NAME ('nasal assimilation (labial)'), which is past the
        # ';' and never reaches the context splitter.
        from ipakit.rules import available, shipped

        checked = 0
        for name in available():
            for rule in shipped(name, FEATURES).rules:
                query = rule.query
                for pattern in (*query.left, *query.right, query.target):
                    if pattern is None:
                        continue
                    checked += 1
                    assert not pattern.optional
        assert checked > 40, "sweep did not run"

    def test_a_name_may_still_carry_parentheses(self) -> None:
        rule = ipakit.rule("n -> m / _ p ; assimilation (labial)")
        assert rule.name == "assimilation (labial)"


class TestWhatTheZeroDoesNotDoYet:
    """Pinned limits, so they change deliberately rather than by drift.

    Each of these is a decision for the owner, not an oversight to be
    fixed quietly here.
    """

    def test_rebuild_does_not_carry_it(self) -> None:
        # `Form.rebuild` reassembles from segments and boundaries, and a
        # zero is neither, so a form taken apart that way loses it.
        form = Form.parse("le∅ʃ", FEATURES)
        assert Form.rebuild(form.segments, form.boundaries, FEATURES).to_ipa() == "leʃ"

    def test_it_offers_no_insertion_gap(self) -> None:
        assert ipakit.rewrite("le∅ʃ", "∅ -> t / e _ ʃ") == "le∅ʃ"
        assert ipakit.rewrite("leʃ", "∅ -> t / e _ ʃ") == "letʃ"

    def test_a_rule_still_reaches_segments_around_it(self) -> None:
        assert ipakit.rewrite("le∅ʃ", "ʃ -> s") == "le∅s"
