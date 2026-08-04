"""Tests for query and matching functionality."""

import itertools
import warnings

import pytest
from ipakit import IPAFeatures
from ipakit.constants import DATA_DIR
from ipakit.features import _Query
from ipakit.form import Unit
from ipakit.form import units as form_units
from ipakit.segment import takes_defaults

from tests.corpus import (
    prosody_bearing_units,
    self_spelling_phones,
    single_mark_units,
)


class TestPhonesMatching:
    """Tests for phones_matching query method."""

    def test_match_single_feature(self, ipa: IPAFeatures) -> None:
        # Match by manner
        result = ipa.phones_matching({"manner": "plosive"})
        assert "p" in result
        assert "t" in result
        assert "s" not in result  # fricative

    def test_match_multiple_features(self, ipa: IPAFeatures) -> None:
        # Voiceless bilabial plosive
        result = ipa.phones_matching(
            {"manner": "plosive", "place": "bilabial", "voiced": "-"}
        )
        assert "p" in result
        assert "b" not in result  # voiced

    def test_match_short_names_list(self, ipa: IPAFeatures) -> None:
        # Match using short name list
        result = ipa.phones_matching(["plo", "bil"])
        assert "p" in result
        assert "b" in result

    def test_match_binary_short_names(self, ipa: IPAFeatures) -> None:
        # Binary features with +/- prefix
        result = ipa.phones_matching(["-voi", "plo", "bil"])
        assert "p" in result
        assert "b" not in result  # voiced

    def test_match_ternary_short_names(self, ipa: IPAFeatures) -> None:
        # Ternary features (tongue-root) with 0 for neutral
        result = ipa.phones_matching(["0trt", "vow"])
        assert len(result) > 0

    def test_match_long_names_binary(self, ipa: IPAFeatures) -> None:
        # Long names for binary features
        result = ipa.phones_matching(["-voiced", "plosive", "bilabial"])
        assert "p" in result
        assert "b" not in result

    def test_match_long_names_ternary(self, ipa: IPAFeatures) -> None:
        result = ipa.phones_matching(["0tongue-root", "vowel"])
        assert len(result) > 0

    def test_match_with_defaults(self, ipa: IPAFeatures) -> None:
        # Without defaults, phones without explicit voiced=- won't match
        # With defaults (default=True), voiceless phones should match
        result = ipa.phones_matching(["-voi", "fri", "alv"], with_defaults=True)
        assert "s" in result

    def test_match_negation_ordinal(self, ipa: IPAFeatures) -> None:
        # Negation for ordinal features: -aspirated means NOT aspirated
        result = ipa.phones_matching(["plo", "-asp"], with_defaults=True)
        assert "p" in result
        # pʰ is aspirated (and composed, not a base phone), so it must not match.
        assert "pʰ" not in result

    def test_value_aliases_resolve_in_every_query_form(self, ipa: IPAFeatures) -> None:
        # A friendly alias is a spelling of its value, so it must select the
        # same phones the canonical name does -- as a dict value, as a bare
        # term, and as a short name. The dict form used to pass its value
        # through untouched and silently match nothing, which matters more
        # now that the canonical spelling carries a combiner glyph.
        canonical = ipa.phones_matching({"place": "bilabial^velar"})
        assert "w" in canonical
        for query in ({"place": "labial-velar"}, ["labial-velar"], ["lbv"]):
            assert ipa.phones_matching(query) == canonical, query
        # Aliases on an ordinary value behave the same way.
        assert ipa.phones_matching({"manner": "stop"}) == ipa.phones_matching(
            {"manner": "plosive"}
        )


class TestNaturalClassTerms:
    """A ``natural-class`` declared in the data is a query term.

    ``obstruent`` sits on three values of ``manner`` in ipa.xml and, for a
    long time, exactly one consumer in the package could read it. Three
    shipped rule sets wanted the class and spelled it out as a complement
    instead, because the resolver routed feature names and values and not
    class names.

    A bracket is a conjunction, so the class is carried as the exclusion
    of every value of its feature outside it -- which is what those rule
    sets wrote by hand. The difference is where the list comes from: this
    one is derived from the declaration, so it is the declaration that
    decides what a new manner belongs to.
    """

    def test_the_class_selects_its_declared_members(self, ipa: IPAFeatures) -> None:
        """The partition, not a count: a whole manner could fall out of a
        count-checked class and it would still pass."""
        members = ipa.features["manner"].value_classes["obstruent"]
        assert members, "the obstruent natural class must be declared"
        expected = {
            p for p in ipa.phones if ipa.get_features(p).get("manner") in members
        }
        assert expected, "no obstruents in the inventory; the test is vacuous"
        assert set(ipa.phones_matching(["obstruent"])) == expected

    def test_the_negated_class_is_the_complement(self, ipa: IPAFeatures) -> None:
        inside = set(ipa.phones_matching(["obstruent"]))
        assert set(ipa.phones_matching(["-obstruent"])) == set(ipa.phones) - inside

    def test_a_class_narrows_like_any_other_term(self, ipa: IPAFeatures) -> None:
        """The Japanese gemination class: obstruents minus the fricatives,
        which is the declared class and one of its manners taken back out
        rather than a second enumeration standing beside it."""
        narrowed = set(ipa.phones_matching(["obstruent", "-fricative"]))
        assert narrowed == {
            p
            for p in ipa.phones_matching(["obstruent"])
            if ipa.get_features(p).get("manner") != "fricative"
        }
        assert narrowed < set(ipa.phones_matching(["obstruent"]))

    def test_a_class_takes_no_neutral_prefix(self, ipa: IPAFeatures) -> None:
        """A class is selected or excluded whole. '0' is the neutral value
        of a ternary feature and means nothing here, so it must not be
        read as the bare term -- and the message must not claim the class
        is undeclared, which is what a generic one would say."""
        with pytest.raises(ValueError) as caught:
            ipa.phones_matching(["0obstruent"])
        message = str(caught.value)
        assert "declared natural class" in message
        assert "'-obstruent'" in message

    def test_no_class_name_is_shadowed(self, ipa: IPAFeatures) -> None:
        """A class name that also spelled a feature, a value, an alias or a
        short name would resolve as that instead, silently, since the value
        arms are tried first. Swept over the declaration so a class added
        later is covered."""
        taken = set(ipa.features) | set(ipa._short_to_feature)
        for feature in ipa.features.values():
            taken |= feature.values_set | set(feature.value_aliases)
        classes = {name for f in ipa.features.values() for name in f.value_classes}
        assert classes, "no natural class is declared; the sweep is vacuous"
        assert not (classes & taken), classes & taken


class TestAMannerAddedToTheDataDoesNotWidenTheClass:
    """The reason the rule sets stopped spelling the class out.

    ``[-vowel -approximant -nasal -trill -tap -silence]`` selects the
    obstruents today and says nothing about why. Add a manner to ipa.xml
    and it takes that manner in without a word, while the declaration it
    was standing in for does not -- one phone reclassified, every rule
    site written that way quietly wider, no test anywhere the wiser.
    That is the shape of defect ``docs/reviewing.md`` was written about.

    Measured on a loaded copy of the data rather than argued: the phone
    moves to the new manner, and the two spellings are asked what they
    select.
    """

    VALUE = '<value name="affricate" offset="0.95" short="aff" natural-class="obstruent" href="Affricate"/>'  # noqa: E501
    PHONE = '<phone name="m" manner="nasal" place="bilabial" voiced="+" href="Voiced_bilabial_nasal"/>'  # noqa: E501
    #: The class as the shipped rule sets used to write it out.
    BY_HAND = ["-vowel", "-approximant", "-nasal", "-trill", "-tap", "-silence"]

    def _load(self, tmp_path, added: str) -> IPAFeatures:
        text = (DATA_DIR / "ipa.xml").read_text(encoding="utf-8")
        for original in (self.VALUE, self.PHONE):
            assert text.count(original) == 1, "the data moved; fix this test"
        text = text.replace(self.VALUE, self.VALUE + added)
        text = text.replace(self.PHONE, self.PHONE.replace("nasal", "percussive"))
        path = tmp_path / "ipa.xml"
        path.write_text(text, encoding="utf-8")
        return IPAFeatures(xml_path=path)

    def test_an_undeclared_manner_joins_neither(self, tmp_path) -> None:
        ipa = self._load(
            tmp_path, '<value name="percussive" offset="0.90" short="prc"/>'
        )
        assert ipa.get_features("m")["manner"] == "percussive", "the edit missed"
        assert "m" not in ipa.phones_matching(["obstruent"])
        # The spelling it replaced does not know that.
        assert "m" in ipa.phones_matching(self.BY_HAND)

    def test_a_manner_declared_into_the_class_joins_it(self, tmp_path) -> None:
        """The other arm, so the test is not passing because the class
        cannot grow at all: the data decides, in both directions."""
        ipa = self._load(
            tmp_path,
            '<value name="percussive" offset="0.90" short="prc"'
            ' natural-class="obstruent"/>',
        )
        assert "m" in ipa.phones_matching(["obstruent"])

    def test_the_unedited_data_still_agrees(self, ipa: IPAFeatures) -> None:
        """So a failure above is the added manner and not the harness."""
        assert set(ipa.phones_matching(["obstruent"])) == set(
            ipa.phones_matching(self.BY_HAND)
        )


class TestEveryTermMustResolve:
    """A term that names nothing is a mistake at every arity.

    Dropping it while keeping the terms that resolve turns a narrow query
    into a wide one with no sign that it happened: ``['vowel', '-stress']``
    meaning ``['vowel']`` matches exactly the stressed vowels the term was
    written to exclude. A vacuous query is a visible wrong answer; a
    silently widened one is not.

    Swept rather than spot-checked: the two arities are compared over
    every spelling the declared data can produce, so the guard covers the
    terms nobody thought to name.
    """

    @staticmethod
    def spellings(ipa: IPAFeatures) -> list[str]:
        """Every query spelling the declared data can produce.

        Feature names, feature values, value aliases and natural-class
        names, each bare and under every prefix the language accepts, plus
        the short names. Declared, not listed: a new feature, or a new
        class, joins the sweep by being declared.
        """
        terms = set(ipa.features)
        for feature in ipa.features.values():
            terms |= (
                feature.values_set
                | set(feature.value_aliases)
                | set(feature.value_classes)
            )
        out = {short for short in ipa._short_to_feature}
        for term in terms:
            out |= {term, f"+{term}", f"-{term}", f"0{term}"}
        return sorted(out)

    def verdict(self, ipa: IPAFeatures, query: list[str]) -> str:
        """What the resolver does with ``query``: resolve it, refuse a
        term for naming nothing, or refuse the query as unsatisfiable.

        The third is not a verdict on the term. A bracket is a
        conjunction, so ``['vowel', 'plosive']`` asks one feature to hold
        two values at once and is refused for saying something no phone
        can be. Every manner value does that beside the companion below,
        and none of them is being dropped -- which is what this sweep is
        about.
        """
        try:
            ipa._resolve_query(query)
        except ValueError as caught:
            named = "resolves to no feature term" in str(caught)
            return "unresolved" if named else "unsatisfiable"
        return "resolves"

    def test_the_two_arities_agree(self, ipa: IPAFeatures) -> None:
        """Bare and mixed must give the same verdict on the same term."""
        # 'vowel' is the resolving companion: a real mixed query has one,
        # and it is what would hide a dropped term.
        assert self.verdict(ipa, ["vowel"]) == "resolves"
        checked, disagreed = 0, []
        for term in self.spellings(ipa):
            checked += 1
            alone = self.verdict(ipa, [term]) == "unresolved"
            mixed = self.verdict(ipa, ["vowel", term]) == "unresolved"
            if alone != mixed:
                disagreed.append(term)
        assert checked > 300, "sweep did not run"
        assert not disagreed, f"dropped beside a resolving term: {disagreed[:10]}"

    def test_the_mixed_query_says_which_term_failed(self, ipa: IPAFeatures) -> None:
        with pytest.raises(ValueError, match="'zzz' resolves to no feature term"):
            ipa.phones_matching(["vowel", "zzz"])

    def test_a_feature_with_no_negative_value_names_the_ones_it_has(
        self, ipa: IPAFeatures
    ) -> None:
        """The error names what WOULD have worked.

        ``stress`` is neither a feature value nor a binary feature name,
        so '-stress' resolves to nothing; the spelling that means what it
        looks like is per-value negation, and the message says so rather
        than leaving a reader to find it.
        """
        with pytest.raises(ValueError) as caught:
            ipa.phones_matching(["vowel", "-stress"])
        message = str(caught.value)
        for value in ipa.features["stress"].values:
            assert value in message, value
        assert "-primary -secondary" in message


class TestShortsConversion:
    """Tests for short name conversion."""

    def test_features_to_shorts(self, ipa: IPAFeatures) -> None:
        feats = {"manner": "plosive", "place": "bilabial", "voiced": "-"}
        shorts = ipa.features_to_shorts(feats)
        assert "plo" in shorts
        assert "bil" in shorts
        assert "-voi" in shorts

    def test_shorts_to_features(self, ipa: IPAFeatures) -> None:
        shorts = ["plo", "bil", "-voi"]
        feats = ipa.shorts_to_features(shorts)
        assert feats["manner"] == "plosive"
        assert feats["place"] == "bilabial"
        assert feats["voiced"] == "-"

    def test_shorts_round_trip(self, ipa: IPAFeatures) -> None:
        original = {"manner": "fricative", "place": "alveolar", "voiced": "+"}
        shorts = ipa.features_to_shorts(original)
        recovered = ipa.shorts_to_features(shorts)
        for k, v in original.items():
            assert recovered[k] == v

    def test_ternary_shorts(self, ipa: IPAFeatures) -> None:
        # Ternary features: -, 0, +
        feats = {"tongue-root": "+"}
        shorts = ipa.features_to_shorts(feats)
        assert "+trt" in shorts

        feats = {"tongue-root": "0"}
        shorts = ipa.features_to_shorts(feats)
        assert "0trt" in shorts


class TestFeatureBundles:
    """Tests for feature_bundles function."""

    def test_single_phone(self) -> None:
        import ipakit

        bundles = ipakit.feature_bundles("p")
        assert len(bundles) == 1
        assert bundles[0]["manner"] == "plosive"

    def test_multi_segment(self) -> None:
        import ipakit

        bundles = ipakit.feature_bundles("pat")
        assert len(bundles) == 3
        assert bundles[0]["manner"] == "plosive"
        assert bundles[1]["manner"] == "vowel"
        assert bundles[2]["manner"] == "plosive"

    def test_with_diacritics(self) -> None:
        import ipakit

        bundles = ipakit.feature_bundles("pʰ")
        assert len(bundles) == 1
        assert bundles[0]["release"] == "aspirated"


#: The one-character values a binary feature declares. As bare list
#: terms they are read as the +/-/0 prefix rather than as values, so the
#: sweeps below reach them through the feature name instead.
_PREFIXES = frozenset("+-0")


class TestABracketIsAConjunction:
    """Two positive values for one feature contradict; they do not stack.

    `positive[feat] = val` was written at each of the three places a
    positive term is recognized, so the last one to arrive won:
    `['alveolar', 'velar']` answered the velars and `['velar',
    'alveolar']` answered the alveolars. One query, two answers, chosen by
    the order the terms happened to be written -- and by nothing at all
    when the query is a `set`, where iteration order is not the caller's
    to see.

    Refusing is the answer rather than matching nothing. A feature holds
    one value at a time, so an impossible query is far more likely a
    mistake than an intent, and "every term must resolve" already refuses
    a term that resolves and is then dropped.
    """

    CONTRADICTIONS: list[list[str]] = [
        ["alveolar", "velar"],
        ["velar", "alveolar"],
        ["plosive", "fricative"],
        ["+voi", "-voi"],
        ["+voiced", "-voiced"],
        ["stop", "fricative"],  # through the alias table
    ]

    @pytest.mark.parametrize("query", CONTRADICTIONS)
    def test_it_is_refused(self, ipa: IPAFeatures, query: list[str]) -> None:
        with pytest.raises(ValueError, match="a conjunction"):
            ipa.phones_matching(query)

    def test_the_two_orders_give_the_same_message(self, ipa: IPAFeatures) -> None:
        """Which is what makes a `set` query answerable at all: the message
        names both values, sorted, so it does not depend on which arrived
        first."""
        messages = set()
        for query in (["alveolar", "velar"], ["velar", "alveolar"]):
            with pytest.raises(ValueError) as caught:
                ipa.phones_matching(query)
            messages.add(str(caught.value))
        assert len(messages) == 1
        assert "'alveolar' and 'velar'" in messages.pop()

    def test_a_set_is_refused_too(self, ipa: IPAFeatures) -> None:
        with pytest.raises(ValueError, match="a conjunction"):
            ipa.phones_matching({"alveolar", "velar"})

    def test_asking_twice_for_the_same_value_is_not_a_contradiction(
        self, ipa: IPAFeatures
    ) -> None:
        assert ipa.phones_matching(["plosive", "plo"]) == ipa.phones_matching(["plo"])

    def test_it_holds_over_every_pair_of_values_one_feature_declares(
        self, ipa: IPAFeatures
    ) -> None:
        """Swept: no pair of distinct values of one feature resolves.

        Restricted to values whose bare term resolves to that feature --
        a name several features declare goes to whichever is declared
        first, and that is the resolver's rule and not this one's.
        """
        checked = 0
        for name, feature in ipa.features.items():
            spellings = [
                value
                for value in sorted(feature.values_set)
                if value not in _PREFIXES
                and ipa._resolve_query_term(value) == (name, value)
            ]
            for first, second in itertools.combinations(spellings, 2):
                with pytest.raises(ValueError, match="a conjunction"):
                    ipa._resolve_query([first, second])
                checked += 1
        assert checked > 200, f"sweep did not run: {checked}"


class TestTheTwoArmsRefuseAlike:
    """A dict query is held to the policy stated of the query, not of the
    list arm.

    `_resolve_query`'s docstring says **every** term must resolve, and why:
    a narrowed query silently widened is a wrong answer rather than a
    vacuous one. The dict arm kept neither half of that. `{'not-a-feature':
    '+'}` and `{'place': 'nonsense'}` resolved to themselves and matched
    nothing, so a misspelling came back as a plausible inventory fact --
    the same wrong answer the policy exists to refuse, reached by writing
    the query the other way round.
    """

    UNDECLARED = "not-a-declared-name"

    def test_a_name_that_is_no_feature_is_refused_in_both_arms(
        self, ipa: IPAFeatures
    ) -> None:
        for query in ([self.UNDECLARED], {self.UNDECLARED: "+"}):
            with pytest.raises(ValueError, match="resolves to no feature term"):
                ipa.phones_matching(query)

    def test_a_value_the_feature_does_not_declare_is_refused(
        self, ipa: IPAFeatures
    ) -> None:
        checked = 0
        for name in ipa.features:
            with pytest.raises(ValueError, match="is not a value of feature"):
                ipa.phones_matching({name: self.UNDECLARED})
            checked += 1
        assert checked > 20, f"sweep did not run: {checked}"

    def test_a_natural_class_is_not_a_value_and_the_message_says_so(
        self, ipa: IPAFeatures
    ) -> None:
        with pytest.raises(ValueError) as caught:
            ipa.phones_matching({"manner": "obstruent"})
        assert "declared natural class" in str(caught.value)
        assert ipa.phones_matching(["obstruent"])

    def test_the_arms_agree_where_they_resolve(self, ipa: IPAFeatures) -> None:
        """And the refusal is not a narrowing: wherever a bare term names
        one (feature, value), the dict spelling of it selects the same
        phones.

        A structural feature is refused in both arms rather than answered
        in either, and the sweep asserts that too. ``level`` is a property
        of a boundary, a query is asked of a unit, and which way round the
        term is written does not change either fact.
        """
        structural = ipa.features_by_mode.get("structural", frozenset())
        checked = 0
        refused = 0
        for name, feature in ipa.features.items():
            for value in sorted(feature.values_set):
                if value in _PREFIXES:
                    continue
                if ipa._resolve_query_term(value) != (name, value):
                    continue
                if name in structural:
                    for query in ([value], {name: value}):
                        with pytest.raises(ValueError, match="is structural"):
                            ipa.phones_matching(query)
                    refused += 1
                    continue
                assert ipa.phones_matching([value]) == ipa.phones_matching(
                    {name: value}
                ), (name, value)
                checked += 1
        assert checked > 50, f"sweep did not run: {checked}"
        assert refused >= len(structural), f"structural sweep did not run: {refused}"

    def test_a_generative_overlap_still_resolves(self, ipa: IPAFeatures) -> None:
        # The dict arm expands each component, so a declared overlap is
        # accepted and one with an undeclared half is not.
        assert ipa.phones_matching({"place": "bilabial^velar"})
        with pytest.raises(ValueError, match="is not a value of feature"):
            ipa.phones_matching({"place": f"bilabial^{self.UNDECLARED}"})

    def test_an_alias_still_resolves(self, ipa: IPAFeatures) -> None:
        assert ipa.phones_matching({"place": "labial-velar"}) == ipa.phones_matching(
            {"place": "bilabial^velar"}
        )


def _spellable_terms(ipa: IPAFeatures) -> list[str]:
    """Every single term the bracket language can spell, both polarities.

    Enumerated from the declaration rather than listed: every declared
    value, every declared natural class, and the ``+``/``-``/``0`` prefix
    on every feature name. A value, a class or a feature added to
    ``ipa.xml`` joins these sweeps without an edit here, which is the
    whole point of asking the data what the language can say.
    """
    out: list[str] = []
    for name, feature in ipa.features.items():
        for value in feature.values:
            out += [value, f"-{value}"]
        for klass in feature.value_classes:
            out += [klass, f"-{klass}"]
        out += [f"+{name}", f"-{name}", f"0{name}"]
    seen: set[str] = set()
    return [t for t in out if not (t in seen or seen.add(t))]


def _corpus_units(ipa: IPAFeatures) -> list[Unit]:
    """The canonical corpus, parsed into the units a query is asked about.

    ``tests.corpus`` is the one enumeration (docs/reviewing.md), taken
    here in all three extents it offers: the bare phones, one mark on
    either side of every base, and the two-prosodic-mark sample. The last
    two matter for different reasons -- a stressed unit is spelled with
    the mark in front, and a contour is only *derived* where two levels
    sit next to each other -- and without them a term about stress and a
    term about nothing look identical.
    """
    seen: set[str] = set()
    units: list[Unit] = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for text in (
            *self_spelling_phones(),
            *single_mark_units(),
            *prosody_bearing_units(),
        ):
            if text in seen:
                continue
            seen.add(text)
            units.append(form_units(text, ipa)[0])
    return units


class TestNoTermIsTrueOfEverything:
    """A query term must ask something of a unit, or be refused.

    Fifteen terms matched every segment and no boundary, and one query
    that reads as their complement matched nothing at all. Both came from
    the same place: a term was compared against a bundle that could not
    carry the feature it named, and the comparison answered from the
    absence rather than declining to answer. On the negative side that is
    true of everything, on the positive side true of nothing, and neither
    says a word about it.

    The guards here are written over the *shape* rather than over the
    fifteen. Each names one way a term can stop constraining anything.
    """

    def test_a_declared_default_is_in_every_bundle_a_query_reads(
        self, ipa: IPAFeatures
    ) -> None:
        """Absence happens only where the declaration leaves room for it.

        The negative arm of a query is satisfied by a bundle that omits
        the feature, deliberately: ``stress`` declares two values and no
        default, so a unit carrying no stress is unstressed and
        ``[-primary -secondary]`` -- which is how the shipped American
        English set says so -- has to hold of it.

        That reading is only safe while absence is confined to the
        features whose declaration allows it. A feature declaring a
        ``default`` is not one of them: every unit has that value until a
        mark says otherwise, so no term over it can be decided by absence.
        ``length`` declared ``normal`` and the fill went to the feature
        bag, which is the bag a prosodic term is *not* asked of -- so
        ``[-normal]`` was true of every unit and ``[length=normal]`` of
        none.
        """
        prosodic = ipa.features_by_mode.get("prosodic", frozenset())
        defaulted = [n for n, f in ipa.features.items() if f.default is not None]
        assert len(defaulted) > 10, f"sweep has nothing to check: {defaulted}"
        assert prosodic & set(defaulted), "no prosodic feature declares a default"
        checked = 0
        for unit in _corpus_units(ipa):
            if not takes_defaults(ipa, unit.features):
                continue
            asked = ipa._prosody_asked(unit.features, unit.prosody)
            for name in defaulted:
                bag = asked if name in prosodic else unit.features
                assert name in bag, (unit.text, name)
            checked += 1
        assert checked > 4000, f"sweep did not run: {checked}"

    def test_a_natural_class_declines_a_bundle_that_has_no_such_feature(
        self, ipa: IPAFeatures
    ) -> None:
        """The two negative-looking terms differ, and this is how.

        ``[obstruent]`` is a claim *about* a unit's manner, so a bundle
        carrying no manner does not satisfy it, exactly as
        ``[manner=plosive]`` does not. ``[-obstruent]`` is an exclusion,
        and an exclusion is satisfied by absence -- the reading the test
        above depends on.

        Carried as the exclusion of every value outside the class, which
        is what a class was, the two were one constraint and the positive
        one held of any bundle omitting the feature. No class is declared
        over a feature some unit omits today, so nothing was wrong; this
        is the guard for the day one is.
        """
        classes = [c for f in ipa.features.values() for c in f.value_classes]
        assert classes, "no natural class is declared"
        for klass in classes:
            assert not ipa._query_matches({}, *ipa._resolve_query([klass])), klass
            assert ipa._query_matches({}, *ipa._resolve_query([f"-{klass}"])), klass

    def test_a_structural_feature_is_refused_rather_than_answered(
        self, ipa: IPAFeatures
    ) -> None:
        """``level``, ``break``, ``tie`` and ``linking`` name a boundary.

        A boundary is a relation between units and a juncture is a
        relation inside one; neither is a unit, and a query is asked of a
        unit's features and its prosody. So a term over one of these was
        matched against a bag that could never carry the key and was
        satisfied by its absence: ``[-word]`` and ``[-simultaneous]``
        matched every segment there is.
        """
        structural = ipa.features_by_mode.get("structural", frozenset())
        assert structural, "no structural feature is declared"
        checked = 0
        ambiguous = 0
        for name in structural:
            feature = ipa.features[name]
            # Every spelling that names this feature: a side of it where
            # it is binary, and each of its values bare and negated. A
            # bare '+' or '-' is not a term on its own, so it is the name
            # that carries the prefix.
            named = [v for v in feature.values if v not in _PREFIXES]
            queries: list[list[str] | dict[str, str]] = [
                [f"{prefix}{name}"] for prefix in _PREFIXES if prefix in feature.values
            ]
            queries += [[v] for v in named]
            queries += [[f"-{v}"] for v in named]
            queries += [{name: v} for v in named]
            for query in queries:
                # A bare term two features claim is refused one step
                # earlier, as ambiguous, because nothing has resolved it to
                # a feature yet -- `syllable` is `level`'s boundary strength
                # and `tier`'s span. Still a refusal and still not an
                # answer, which is what this test is about, so both arms
                # count and both are required to run.
                bare = query[0].lstrip("-") if isinstance(query, list) else None
                contested = bare is not None and len(ipa._claimants(bare)) > 1
                expected = "ambiguous" if contested else "is structural"
                with pytest.raises(ValueError, match=expected):
                    ipa.phones_matching(query)
                if contested:
                    ambiguous += 1
                else:
                    checked += 1
        assert checked > 20, f"sweep did not run: {checked}"
        assert ambiguous > 0, (
            "no structural value is claimed by two features, so the "
            "ambiguity arm above never ran and proves nothing"
        )

    def test_the_two_matchers_answer_one_question(self, ipa: IPAFeatures) -> None:
        """``phones_matching`` and ``find`` over the same registered phone.

        A registered phone is a unit that has been written down with
        nothing on it, so the inventory query and the transcription query
        are the same question asked twice, and their answers are compared
        here term by term rather than at a handful of named cases. They
        disagreed about ``['-normal']`` -- one phone against every unit --
        because only one of them put a prosodic term to the prosody.

        They now share ``_query_constraints`` and ``_satisfies``, so the
        sweep is a check on the construction rather than the thing that
        keeps them in step.
        """
        checked = 0
        refused = 0
        for term in _spellable_terms(ipa):
            try:
                inventory = ipa.phones_matching([term])
            except ValueError:
                with pytest.raises(ValueError):
                    ipa.find(next(iter(ipa.phones)), [term])
                refused += 1
                continue
            assert inventory == [p for p in ipa.phones if ipa.find(p, [term])], term
            checked += 1
        assert checked > 150, f"sweep did not run: {checked}"
        assert refused > 50, f"the refusals were not swept: {refused}"

    def test_the_guard_states_the_terms_it_cannot_speak_for(
        self, ipa: IPAFeatures
    ) -> None:
        """What is still true of every unit, and why it is not this defect.

        ``articulator`` names the organ that moves, and ``ipa.xml``
        declares one on each ``place`` and ``backness`` value rather than
        on a phone: ``velar`` carries ``articulator="tongue-dorsum"``. The
        metric resolves that mapping and compares the organ
        (``metric._metric_bundle``); the query language does not, so the
        only ``articulator`` a bundle ever holds is one a mark wrote --
        the apical, laminal and linguolabial marks. Every other value of
        it is carried by nothing, and the negation of a value nothing
        carries is true of everything.

        That is a *projection* the query language does not make, not a
        term decided by a missing key, and giving it one would change what
        every read returns. Stated here so the limit stays known: if one
        of these stops being universal, the projection has been made and
        this needs rewriting.
        """
        corpus = _corpus_units(ipa)
        assert len(corpus) > 4000, "sweep did not run"
        universal = []
        for term in _spellable_terms(ipa):
            try:
                segmental, prosodic = ipa._query_constraints([term])
            except ValueError:
                continue
            if all(
                ipa._satisfies(u.features, u.prosody, segmental, prosodic)
                for u in corpus
            ):
                universal.append(term)
        resolved = {ipa._resolve_query_term(t.lstrip("-"))[0] for t in universal}
        # ``articulator`` (above) and ``stress``: the stress feature's ``none``
        # value is the unstressed ordinal anchor, spelled by no mark, so no unit
        # carries it and its negation ``-none`` is true of everything -- the
        # same projection shape, a value carried by nothing rather than a term
        # decided by a missing key.
        assert resolved == {"articulator", "stress"}, sorted(universal)
        assert len(universal) >= 5, sorted(universal)


class TestEveryQueryEntryPointRefusesInOneVocabulary:
    """A malformed query is refused as a domain error, whatever its shape.

    The resolver decided which arm to take with `isinstance(query, (list,
    set))` and let everything else fall into the mapping arm, where it was
    asked for `.items()`. So a query the resolver could not place did not
    reach a refusal at all -- it left an `AttributeError` out of
    `phones_matching` and `find`, which tells a caller nothing about what
    they wrote and cannot be caught beside `RuleError`, the `ValueError`
    the rule side raises for the same mistakes (#148).

    The sweep is over the *shape* of the mistake rather than the three
    spellings the issue named. It finds the public entry points by
    signature and puts every malformed shape to each, so an entry point
    added later is swept without an edit here, and it also puts the
    well-formed collection shapes to each, so refusing everything is not a
    way to pass.
    """

    @staticmethod
    def entry_points(ipa: IPAFeatures) -> dict[str, object]:
        """Every public callable taking a query-language query, bound to a call.

        Discovered by the *annotation*, over the module surface and the
        inventory object, rather than named here: `phones_matching` and
        `find` are today's two and the point of the guard is the next one.
        By the annotation and not the parameter name, because
        `ipakit.Rule.query` is a rules `Query` -- a pattern and its context
        -- and is not this entry point.
        """
        import inspect

        import ipakit

        found = {}
        for holder, prefix in ((ipakit, "ipakit."), (ipa, "IPAFeatures.")):
            for name in dir(holder):
                if name.startswith("_"):
                    continue
                member = getattr(holder, name)
                if not callable(member):
                    continue
                try:
                    params = inspect.signature(member).parameters
                except (TypeError, ValueError):  # pragma: no cover - builtins
                    continue
                asked = params.get("query")
                if asked is None or asked.annotation not in ("_Query", _Query):
                    continue
                if "ipa_string" in params or "ipa" in params:
                    found[prefix + name] = lambda q, f=member: f("ata", q)
                else:
                    found[prefix + name] = lambda q, f=member: f(q)
        return found

    #: Shapes that are not a query at all. Spelled as a description of the
    #: shape, not as a list of literals: a bare string (in every spelling
    #: the issue named and in one that looks well formed), bytes, and the
    #: non-collections a caller reaches by passing the wrong variable.
    MALFORMED = [
        "",
        " ",
        "[]",
        "[ ]",
        "[+voiced]",
        "+voiced",
        "voiced",
        "manner=plosive",
        b"+voiced",
        None,
        42,
        3.5,
        True,
        object(),
    ]

    def test_no_entry_point_leaks_a_non_domain_error(self, ipa: IPAFeatures) -> None:
        checked = 0
        for name, call in self.entry_points(ipa).items():
            for query in self.MALFORMED:
                try:
                    call(query)
                except ValueError:
                    checked += 1
                    continue
                except Exception as leaked:  # noqa: BLE001
                    raise AssertionError(
                        f"{name}({query!r}) raised "
                        f"{type(leaked).__name__}: {leaked}"
                    ) from None
                raise AssertionError(f"{name}({query!r}) was answered, not refused")
        assert checked >= 2 * len(self.MALFORMED), f"sweep did not run: {checked}"

    def test_the_entry_points_are_found_by_signature(self, ipa: IPAFeatures) -> None:
        """The discovery above is what makes the sweep non-vacuous.

        If it silently found nothing the sweep would pass over an empty
        product, so what it found is asserted here: both entry points, on
        the module and on the inventory, four bindings in all.
        """
        found = self.entry_points(ipa)
        assert {
            "ipakit.phones_matching",
            "ipakit.find",
            "IPAFeatures.phones_matching",
            "IPAFeatures.find",
        } <= set(found), sorted(found)

    def test_a_string_is_never_read_as_its_characters(self, ipa: IPAFeatures) -> None:
        """Why the test is not "a mapping, else iterate".

        A string is a collection of characters, so iterating one would
        resolve `'0trt'` -- a declared short name, whole -- as four terms,
        and `'-voi'` as three. That is a wrong answer wearing the shape of
        a query, which is worse than the crash it would replace, so every
        string is refused however well formed it looks whole.
        """
        wholes = [s for s in ipa._short_to_feature if len(s) > 1]
        assert len(wholes) > 20, f"no multi-character short names: {len(wholes)}"
        for short in wholes:
            with pytest.raises(ValueError, match="not str"):
                ipa.phones_matching(short)

    def test_a_collection_of_terms_is_answered_whatever_holds_it(
        self, ipa: IPAFeatures
    ) -> None:
        """Refusing everything is not a way to pass the sweep above.

        A tuple of terms and a frozenset of them are queries, and used to
        leak the same `AttributeError` as `42` because they were neither
        of the two concrete types the resolver tested for. They now answer
        what the list answers, term by term over the spellable terms
        rather than at one named query.
        """
        checked = 0
        for term in _spellable_terms(ipa):
            try:
                expected = ipa.phones_matching([term])
            except ValueError:
                continue
            for holder in (tuple, frozenset, iter):
                assert ipa.phones_matching(holder([term])) == expected, (term, holder)
            checked += 1
        assert checked > 150, f"sweep did not run: {checked}"

    def test_the_rule_side_refuses_in_the_same_vocabulary(self) -> None:
        """What "one vocabulary" means: `except ValueError` catches both.

        `RuleError` is a `ValueError`, so a caller writing one handler
        around a query and a rule catches both refusals. Pinned because
        the shared vocabulary is the whole of what #148 asked for, and it
        would be lost silently if `RuleError` were ever rebased.
        """
        from ipakit.rules import RuleError, RuleSet

        assert issubclass(RuleError, ValueError)
        with pytest.raises(ValueError, match="empty query"):
            RuleSet.parse("[] -> ∅ / a _")

    def test_the_guard_states_what_it_does_not_reach(self, ipa: IPAFeatures) -> None:
        """The empty query is refused here and stays #102's question.

        An empty *collection* is a well-formed query that resolves to no
        term, and it is refused for that -- not for its shape. #148 did
        not decide whether it should instead answer the whole inventory;
        if #102 adopts the wildcard, this is the test that has to change,
        and nothing above it does.
        """
        for empty in ([], set(), {}, ()):
            with pytest.raises(ValueError, match="no feature terms resolved"):
                ipa.phones_matching(empty)


class TestABareTermBelongsToOneFeature:
    """Which feature a plain term names is declared, not inherited from
    the order ``ipa.xml`` happens to list its features in.

    Twenty-six value names are claimed by more than one feature. Resolving
    them by scanning in declaration order and taking the first hit made
    ``[high]`` a constraint on vowel HEIGHT -- ``height`` declares ``high``
    as an alias of ``close`` and sits above ``tone``, for which ``high`` is
    a value outright -- so a tone rule written the obvious way parsed, ran,
    and answered about height. That is a well-formed wrong answer, which is
    the shape docs/reviewing.md says every defect here has had.
    """

    def test_a_contested_term_no_feature_claims_is_refused(
        self, ipa: IPAFeatures
    ) -> None:
        """And the refusal names the claimants and what to write instead."""
        for term, claimants in (
            ("high", ["height", "tone"]),
            ("low", ["height", "tone"]),
            ("mid", ["height", "tone"]),
        ):
            assert ipa._resolve_query_term(term) is None, term
            with pytest.raises(ValueError) as caught:
                ipa.phones_matching([term])
            message = str(caught.value)
            assert "ambiguous" in message, term
            for claimant in claimants:
                assert claimant in message, (term, claimant)
            # The way out is spelled, not just the complaint.
            assert "=" in message, term

    def test_the_keyed_spelling_of_a_refused_term_still_answers(
        self, ipa: IPAFeatures
    ) -> None:
        """Refusing the bare spelling takes nothing away.

        ``mid`` is the case that no precedence rule could have saved: it is
        a canonical value of ``height`` AND of ``tone``, so there is no
        alias-versus-value tie-break to apply.
        """
        for feature, value in (("height", "mid"), ("height", "close")):
            assert ipa.phones_matching({feature: value}), (feature, value)
        # And the prosodic side is reachable too, which is the reading the
        # bare spelling could never give: `tone` is prosodic, so it is in no
        # phone bundle and the query is refused as structural rather than
        # answered emptily.
        assert "mid" in ipa.features["tone"].values

    def test_a_declared_claim_wins_the_bare_spelling(self, ipa: IPAFeatures) -> None:
        """``nasal`` is a manner, a release phase and an approach phase.

        Two shipped rules in ``japanese-moraic.rules`` write ``[-vowel
        -nasal]`` and mean the manner. That now holds because ``manner``
        declares it, rather than because ``manner`` is declared first.
        """
        for term, feature in (
            ("nasal", "manner"),
            ("lateral", "channel"),
            ("glottal", "place"),
            ("aspirated", "release"),
        ):
            resolved = ipa._resolve_query_term(term)
            assert resolved is not None, term
            assert resolved[0] == feature, (term, resolved)
            assert term in ipa.features[feature].bare, (term, feature)

    def test_a_borrower_does_not_contest_its_lender(self, ipa: IPAFeatures) -> None:
        """A feature declaring ``vocabulary`` restates the lender's values
        rather than competing with them, so the term is not contested at
        all and needs no ``bare`` declaration to keep working.

        Without the exemption this would refuse every ordinary place term.
        """
        borrowers = {
            name: feature.vocabulary
            for name, feature in ipa.features.items()
            if feature.vocabulary
        }
        assert borrowers, "no borrowing feature is declared; this cannot fail"
        exercised = 0
        for name, lender in borrowers.items():
            for value in sorted(ipa.features[name].values):
                if value in _PREFIXES:
                    continue
                resolved = ipa._resolve_query_term(value)
                if resolved is None:
                    continue
                assert resolved[0] != name or lender not in ipa.features, (
                    name,
                    value,
                )
                exercised += 1
        assert exercised > 10, f"borrowing sweep did not run: {exercised}"

    def test_at_most_one_feature_may_declare_a_term_bare(
        self, ipa: IPAFeatures
    ) -> None:
        """Two declarations would be the same silent choice wearing a
        declaration, so the loader refuses them rather than picking."""
        claimed: dict[str, list[str]] = {}
        for name, feature in ipa.features.items():
            for value in feature.bare:
                claimed.setdefault(value, []).append(name)
        assert claimed, "nothing declares a bare term; this cannot fail"
        for value, names in claimed.items():
            assert len(names) == 1, (value, names)

    def test_every_contested_term_is_declared_or_refused(
        self, ipa: IPAFeatures
    ) -> None:
        """The sweep that pins this, and the proof it can see.

        No contested term may resolve without a declaration. The instrument
        is shown to work by counting the contested terms it found: if the
        claim-gathering were broken it would find none and the sweep would
        pass vacuously.
        """
        claims: dict[str, set[str]] = {}
        for name, feature in ipa.features.items():
            for value in feature.values:
                claims.setdefault(value, set()).add(name)
            for alias in feature.value_aliases:
                claims.setdefault(alias, set()).add(name)
        contested = {t: names for t, names in claims.items() if len(names) > 1}
        assert len(contested) > 20, f"contest sweep did not run: {len(contested)}"
        for term in contested:
            resolved = ipa._resolve_query_term(term)
            if resolved is None:
                continue
            feature, value = resolved
            borrowed = {
                name
                for name in contested[term]
                if (ipa.features[name].vocabulary or "") in contested[term]
            }
            uncontested_by_borrowing = contested[term] - borrowed
            if len(uncontested_by_borrowing) == 1:
                continue
            assert value in ipa.features[feature].bare, (
                f"{term!r} resolves to {feature}={value} and no feature "
                f"declares it bare, so declaration order decided it"
            )
