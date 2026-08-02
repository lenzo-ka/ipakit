"""Tests for query and matching functionality."""

import itertools

import pytest
from ipakit import IPAFeatures
from ipakit.constants import DATA_DIR


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
        phones."""
        checked = 0
        for name, feature in ipa.features.items():
            for value in sorted(feature.values_set):
                if value in _PREFIXES:
                    continue
                if ipa._resolve_query_term(value) != (name, value):
                    continue
                assert ipa.phones_matching([value]) == ipa.phones_matching(
                    {name: value}
                ), (name, value)
                checked += 1
        assert checked > 50, f"sweep did not run: {checked}"

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
