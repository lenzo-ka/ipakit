"""The shipped rule sets: real derived forms, and the claims their files make.

``tests/test_rules.py`` tests the engine. This file tests the *data* --
``ipakit/data/rules/*.rules`` -- and it exists because a rule set is the
kind of thing that goes wrong silently. A mis-ordered cascade, a literal
target bled by an earlier rule, an epenthetic vowel of the wrong quality:
each produces a well-formed IPA string that only a reader who knows the
language can see is wrong. So the assertions here are **whole derived
forms**, not "something changed".

Three properties get more than a named case each, because each is a shape
of mistake rather than a single value:

* **Ordering.** Every file claims some orderings are load-bearing and the
  rest are not. Both halves are measured, and against each other: the
  named dependencies are permuted and shown to change specific words, and
  then a sweep over every pairwise transposition asserts that the
  permutations which move an answer are *exactly* the ones putting a
  named dependency the wrong way round. So a file that says "ordered
  before X, or else Y" and is wrong about it fails here, and so does one
  that leaves a dependency out. This sweep earned its keep twice over:
  the Spanish set turns /z/ to /s/ and the /s/ it makes is what licenses
  a trill in 'Israel', and the Japanese set's affricate rules make the
  segment its /i/ epenthesis asks for. Neither file said so.
* **Optional notation.** A syllable dot must not change what a rule set
  does, or the same word gets two answers depending on who typed the
  dots. Swept over every dot position in every corpus word. This sweep
  earned its keep: it found the French deletion rules, first written
  ``_ %``, losing the liaison consonant they had just placed on 28 of 88
  dotted spellings, because ``%`` reaches a syllable dot too. (The corpus
  has grown since; the same substitution costs 24 of 122 today, and the
  ratio is the claim rather than either integer.) The German and English
  sets are the deliberate exceptions -- each has a rule that *names* a
  boundary -- and both are asserted in both directions rather than skipped.
* **The traps the files record.** Each ``.rules`` file names a spelling
  that looks right and fails silently. Those are pinned, so the warnings
  cannot go stale while still being read as warnings.

The American English set was the last to get a derivation table here, and
four over-applications had survived in it until it did: three rules stated
over adjacent segments where English states them over syllable
constituents, and a literal bled by an earlier rule in the file that warns
about literals being bled. That is the argument for this file in one set.
"""

from __future__ import annotations

import itertools

import ipakit
import pytest
from ipakit import rules as R

FEATURES = ipakit.load_ipa_features()

ENGLISH = "american-english"
SPANISH = "spanish-accented-english"
JAPANESE = "japanese-moraic"
FRENCH = "french-liaison"
GERMAN = "german-final-devoicing"

#: The sets added by this lane.
NEW = (SPANISH, JAPANESE, FRENCH, GERMAN)
#: Everything shipped.
ALL_SETS = (ENGLISH, *NEW)
#: The three whose rules never name a syllable boundary, so the dot must be
#: transparent to them. The German set names one on purpose; see
#: TestTheGermanSetNamesTheBoundaryAndSoTheDotIsNotOptional. The English
#: set names one too -- aspiration is conditioned on '. _' -- which is why
#: it is absent here and why 'ə.tˈæk' and 'ətˈæk' derive differently.
DOT_BLIND = (SPANISH, JAPANESE, FRENCH)

#: The words each set is exercised over. Small and hand-checked: these are
#: derivations somebody has to be able to verify by eye, which a generated
#: corpus would not be. The sweeps below reuse them, and assert the size.
CORPUS: dict[str, tuple[str, ...]] = {
    ENGLISH: (
        "pˈɪn",
        "spˈɪn",
        "bˈʌtɚ",
        "kˈæt",
        "klˈin",
        "fˈʊl",
        "ˈbʌ.tn",
        "pə.tˈe͜ɪ.to͜ʊ",
        "bˈɑ.tl",
        "hˈæn.dbˌæɡ",
        "ˈɑɹm",
        "fˈɪlm",
        "kˈɪln",
        "snˈɑɹl",
        "pɹˈɪzm",
        "ˈmʌni",
        "ˈsʌmɚ",
        "təmˈe͜ɪto͜ʊ",
        "ˈfa͜ɪnl",
        "ˈt͡ʃænl",
        "pˈɑɹti",
        "lˈɪtl",
        "ˈæpl",
        "ˈɪnkʌm",
        "ˈɪnpʊt",
        "kˈæmp",
        "wˈɔtɚ",
        "ə.tˈæk",
        "pɪn",
        # Flapping is conditioned on the FOLLOWING nucleus, and each of
        # these has a flap outside the first foot -- the shape a
        # preceding-stress statement of the rule cannot reach. 'editor'
        # is both halves in one word: two stops flap, and only one of
        # them follows the stress.
        "ˈɛdɪtɚ",
        "kˈæpɪtəl",
        "pˈɑzɪtɪv",
        # The other side of the same condition: a stop before a STRESSED
        # nucleus does not flap, whatever stands behind it -- and
        # 'secondary' counts as stressed, which is what '-secondary' in
        # the rules buys. Stress on the NUCLEUS, per the house
        # convention: 'ˈmɪlɪˌtɛɹi' puts the mark on the /t/ instead and
        # gets the other answer.
        "mˈɪlɪtˌɛɹi",
        # The two places nasal assimilation reaches now that it is ONE
        # rule with an agreement variable rather than one rule per place.
        # Pinned in the corpus so the widening is visible here and not
        # only in the rule file's note: 'input' and 'income' were the
        # whole of it while the labial and velar cases were enumerated.
        "ˈɪnfənt",
        "tˈɛnθ",
    ),
    SPANISH: (
        "skul",
        "stap",
        "speɪn",
        "snoʊ",
        "stɹɛs",
        "slɪp",
        "smɔl",
        "sfɪɹ",
        "swit",
        "vɛɹi",
        "zu",
        "ʃip",
        "θɪŋk",
        "ðɪs",
        "hɛlp",
        "sɪŋ",
        "sɪŋk",
        "bʌtɚ",
        "bɝd",
        "ɹɛd",
        "kʌt",
        "bʊk",
        "kɔl",
        "æpəl",
        "hɑt",
        "bisbɔl",
        "t͡ʃiz",
        "stɹa͜ɪk",
        "ke͜ɪk",
        "ɛnɹɪt͡ʃ",
        "ɪzɹeɪl",
        "ɔlɹa͜ɪt",
        "bɹɛd",
        "hɛnɹi",
    ),
    JAPANESE: (
        "hɑt",
        "bɛd",
        "mæt͡ʃ",
        "mɪlk",
        "stɹa͜ɪk",
        "kɹɪsməs",
        "pɛn",
        "hæm",
        "kæmp",
        "fɪlm",
        "bʊk",
        "kʌp",
        "bit",
        "ko͜ʊt",
        "kɪŋ",
        "tɛnɪs",
        "dɪʃ",
        "θæŋk",
        "ðɪs",
        "vɔ͜ɪs",
        "skul",
        "bɑks",
        "tɑp",
        "kjut",
        "bjuti",
        "bʌtɚ",
        "ha͜ʊs",
        "t͡ʃiz",
        "dɹa͜ɪv",
        "ke͜ɪk",
        "kæb",
        "bæɡ",
        "bæd͡ʒ",
        "bɔl",
        "bɝd",
        "mæt͡ʃbɑks",
        "lʌnt͡ʃ",
        "ʌp",
        "ɛɡ",
        "æd",
        "ɪt",
        "wɛb",
    ),
    FRENCH: (
        "lez‿ami",
        "pətit‿ami",
        "lez‿ʃjɛ̃",
        "pətit‿ʃjɛ̃",
        "lez",
        "lez ami",
        "mɔ̃n‿ami",
        "tʁop‿ɛmabl",
        "pʁəmjeʁ‿etaʒ",
        "pətitə",
        "pətit",
        "bɔnə",
        "bɔn",
        "nuz‿avɔ̃",
        "il‿ɛt‿ɛ̃",
        "tʁop",
        "pʁəmjeʁ",
        "pətitə‿ami",
        "bɔ̃ʒuʁ",
        "mɛʁ",
        "puʁ",
        "lə",
        "ʒə",
        "ynə",
        "katʁə",
        # The four e caduc words. 'devenir' is the one that needs the
        # interior rule and the only corpus word that reaches it, which
        # test_every_rule_in_the_set_fires_on_the_corpus found by saying
        # so; 'vendredi' and 'cheval' are the two sides of the loi des
        # trois consonnes.
        "dəvəniʁ",
        "samədi",
        "vɑ̃dʁədi",
        "ʃəval",
    ),
    GERMAN: (
        "ʁaːd",
        "ʁaː.dəs",
        "taːɡ",
        "taː.ɡəs",
        "liːb",
        "liː.bə",
        "bʁaːv",
        "bʁaː.və",
        "liːb.lɪç",
        "liːblɪç",
        "laŋ",
        "viːl",
        "kɪnd",
        "zaːɡ.baːɐ̯",
        "haʊz",
        "hɔy.zɐ",
    ),
}


def _set(name: str) -> R.RuleSet:
    return R.shipped(name, FEATURES)


def _reordered(name: str, moved: set[str], where: int) -> R.RuleSet:
    """The set with the rules named in ``moved`` lifted to index ``where``.

    Block moves, not adjacent swaps. MEASURED, and the reason this helper
    exists: the dependencies these files record are between *blocks* of
    rules separated by many lines, so every adjacent transposition in the
    Japanese set leaves all 42 derivations untouched while moving the
    gemination block changes 14 of them. A neighbor sweep would have
    reported the ordering as irrelevant.
    """
    rules = _set(name).rules
    names = [r.name for r in rules]
    unknown = moved - set(names)
    assert not unknown, f"no such rule(s) in {name}: {sorted(unknown)}"
    block = [r for r in rules if r.name in moved]
    rest = [r for r in rules if r.name not in moved]
    return R.RuleSet(rules=tuple(rest[:where] + block + rest[where:]))


def _cut_positions(word: str) -> list[int]:
    """Every interior offset where a dot can go without splitting a unit.

    Read off the tokenizer's own segmentation rather than from any list of
    tie bars or combining marks. Two reasons, and the second is the one
    that matters:

    * A hand-written list of "characters that bind to a neighbor" is a
      third copy of something the inventory already declares, and this
      repo's recurring defect is exactly that -- a constant maintained
      beside the data instead of derived from it, agreeing only by habit.
    * The alternative of inserting the dot and discarding the spellings
      that no longer round-trip works, but it reaches the tokenizer with an
      orphaned tie bar first, so the sweep runs behind a screen of "dropped
      1 unbound tie glyph" warnings -- which is how a real warning gets
      missed.

    So the unit boundaries are the cut positions, by construction.
    """
    units = R.units(word, FEATURES)
    assert "".join(u.text for u in units) == word, word
    offsets: list[int] = []
    at = 0
    for unit in units:
        at += len(unit.text)
        if 0 < at < len(word):
            offsets.append(at)
    return offsets


#: The Spanish trill rules, named once. They and the tap rule are one
#: statement split by position, so a permutation that moves one without
#: the others is measuring a set nobody wrote.
_TRILLS = frozenset(
    {
        "ɹ is the trill word-initially",
        "ɹ is the trill after n",
        "ɹ is the trill after l",
        "ɹ is the trill after s",
    }
)


def _index(name: str, rule: str) -> int:
    names = [r.name for r in _set(name).rules]
    assert rule in names, f"no rule {rule!r} in {name}"
    return names.index(rule)


class TestTheShippedSetsLoadAndNameThemselves:
    def test_every_set_is_available_by_name(self):
        assert R.available() == sorted(ALL_SETS)

    @pytest.mark.parametrize("name", ALL_SETS)
    def test_the_file_parses_and_has_rules(self, name):
        assert len(_set(name)) > 0

    @pytest.mark.parametrize("name", ALL_SETS)
    def test_every_rule_is_named(self, name):
        """A rule with no ';' is named by its own source, which reads as
        noise in a trace. The predicate is "no rule's name is its source",
        which is what "every rule is named" means operationally."""
        unnamed = [r.source for r in _set(name).rules if r.name == r.source]
        assert unnamed == [], f"{len(unnamed)} unnamed rules: {unnamed[:3]}"

    @pytest.mark.parametrize("name", ALL_SETS)
    def test_the_file_argues_its_choices(self, name):
        """The house voice is not decoration: these files record traps that
        cost real time to find. A file stripped to bare rules has lost
        them, and the count is the cheapest predicate for that.

        Extended to the English set, which shipped without a "not modeled"
        section and accumulated four wrong derivations and two false claims
        in its prose before anybody re-measured it.
        """
        text = (R.RULES_DIR / f"{name}.rules").read_text(encoding="utf-8")
        comments = [ln for ln in text.splitlines() if ln.startswith("#")]
        assert len(comments) > 40, f"{name} has only {len(comments)} comment lines"
        assert "not modeled" in text, f"{name} does not name what it leaves out"


# --------------------------------------------------------------------------
# Set 0: American English -- broad to narrow
# --------------------------------------------------------------------------


class TestAmericanEnglishDerivesTheseForms:
    """Whole forms, including every one a phonology review found wrong.

    This set shipped first and was the last to get a derivation table, which
    is how four over-applications survived in it: three rules stated over
    ADJACENT SEGMENTS where the language states them over SYLLABLE
    CONSTITUENTS, and one literal bled by an earlier rule in the very file
    that warns about literals being bled. All four produced well-formed IPA,
    which is why nothing failed.
    """

    @pytest.mark.parametrize(
        "source,expected,gloss",
        [
            ("pˈɪn", "pʰˈɪ̃n", "pin"),
            ("spˈɪn", "spˈɪ̃n", "spin: the margin is taken by /s/"),
            ("bˈʌtɚ", "bˈʌɾɚ", "butter"),
            ("kˈæt", "kʰˈæt̚", "cat"),
            ("klˈin", "kl̥ˈĩn", "clean"),
            ("fˈʊl", "fˈʊɫ", "full"),
            ("ˈbʌ.tn", "ˈbʌ.tⁿn̩", "button"),
            ("pə.tˈe͜ɪ.to͜ʊ", "pə.tʰˈe͜ɪ.ɾo͜ʊ", "potato"),
            ("hˈæn.dbˌæɡ", "hˈæ̃n.dbˌæɡ", "handbag"),
            ("ˈɪnpʊt", "ˈɪ̃mpʊt̚", "input: nasal assimilation, labial"),
            ("ˈɪnkʌm", "ˈɪ̃ŋkʌ̃m", "income: nasal assimilation, velar"),
            # The two the enumeration never reached. One rule with an
            # agreement variable states the process, so these follow from
            # the same line the two above do rather than from two more.
            ("ˈɪnfənt", "ˈɪ̃ɱfə̃nt̚", "infant: labiodental, which was not enumerated"),
            ("tˈɛnθ", "tʰˈɛ̃n̪θ", "tenth: dental, which was not enumerated"),
            ("kˈæmp", "kʰˈæ̃mp̚", "camp"),
            ("ə.tˈæk", "ə.tʰˈæk̚", "attack: the margin is stated"),
            ("pɪn", "pɪ̃n", "pin, unstressed: no aspiration"),
            ("ˈɛdɪtɚ", "ˈɛɾɪɾɚ", "editor: both stops flap"),
            ("kˈæpɪtəl", "kʰˈæpɪɾəɫ", "capital"),
            ("pˈɑzɪtɪv", "pʰˈɑzɪɾɪv", "positive"),
            ("mˈɪlɪtˌɛɹi", "mˈɪɫɪtˌɛɹi", "military: a secondary stress blocks it"),
        ],
    )
    def test_derivation(self, source, expected, gloss):
        assert _set(ENGLISH).apply(source) == expected, gloss

    @pytest.mark.parametrize(
        "source,expected,gloss",
        [
            ("ˈɑɹm", "ˈɑɹm", "arm is one syllable"),
            ("fˈɪlm", "fˈɪɫm", "film"),
            ("kˈɪln", "kʰˈɪɫn", "kiln"),
            ("snˈɑɹl", "snˈɑɹl", "snarl: the lateral is not a nucleus either"),
            ("pɹˈɪzm", "pɹ̥ˈɪzm̩", "prism: behind an obstruent, so it is"),
            ("ˈfa͜ɪnl", "ˈfa͜ɪnl̩", "final: an /l/ behind a nasal is"),
            ("ˈt͡ʃænl", "ˈt͡ʃæ̃nl̩", "channel"),
        ],
    )
    def test_a_sonorant_is_syllabic_only_where_it_carries_a_syllable(
        self, source, expected, gloss
    ):
        """'[-vowel] _ #' made a nasal syllabic after any consonant at all.

        The generalization is "after an obstruent" for the nasal, and "after
        an obstruent or a nasal" for the lateral, and the difference between
        the two classes is a fact about English rather than an oversight.
        """
        assert _set(ENGLISH).apply(source) == expected, gloss

    @pytest.mark.parametrize(
        "source,expected,gloss",
        [
            ("ˈmʌni", "ˈmʌni", "money: the nasal is the next onset"),
            ("ˈsʌmɚ", "ˈsʌmɚ", "summer"),
            ("təmˈe͜ɪto͜ʊ", "təmˈe͜ɪɾo͜ʊ", "tomato"),
            ("pˈɪn", "pʰˈɪ̃n", "pin: a coda nasal, so nasalized"),
            ("kˈæmp", "kʰˈæ̃mp̚", "camp: a coda nasal before a consonant"),
        ],
    )
    def test_a_vowel_nasalizes_only_before_a_coda_nasal(self, source, expected, gloss):
        assert _set(ENGLISH).apply(source) == expected, gloss

    @pytest.mark.parametrize(
        "source,expected,gloss",
        [
            ("bˈɑtl", "bˈɑɾl̩", "bottle: flapped before a syllabic lateral"),
            ("bˈɑ.tl", "bˈɑ.ɾl̩", "bottle, dotted: the same answer"),
            ("lˈɪtl", "lˈɪɾl̩", "little"),
            ("pˈɑɹti", "pʰˈɑɹɾi", "party: flapped after a coda rhotic"),
            ("wˈɔtɚ", "wˈɔɾɚ", "water: and after the vocalic spelling"),
            ("ˈbʌ.tn", "ˈbʌ.tⁿn̩", "button: a syllabic NASAL does not flap"),
            ("ˈæpl", "ˈæpˡl̩", "apple: lateral release, not a flap"),
        ],
    )
    def test_tapping_reaches_the_nucleus_however_the_nucleus_is_spelled(
        self, source, expected, gloss
    ):
        """Three rules, because a rhyme is not a sequence of vowels.

        A syllabic lateral is a nucleus and no feature says "vowel"; a coda
        /ɹ/ is part of the rhyme and no feature says that either. Whether
        tapping fired used to depend on which of two equivalent
        transcriptions somebody typed, which is the defect these pin.
        """
        assert _set(ENGLISH).apply(source) == expected, gloss

    @pytest.mark.parametrize(
        "source,expected,gloss",
        [
            # Flaps: the next nucleus carries no stress.
            ("bˈʌtɚ", "bˈʌɾɚ", "butter: the trochee both statements agree on"),
            ("ˈɛdɪtɚ", "ˈɛɾɪɾɚ", "editor: the second /t/ follows an UNSTRESSED ɪ"),
            ("kˈæpɪtəl", "kʰˈæpɪɾəɫ", "capital"),
            ("pˈɑzɪtɪv", "pʰˈɑzɪɾɪv", "positive"),
            ("ˈæ.lə.ɡˌe͜ɪ.tɚ", "ˈæ.ɫə.ɡˌe͜ɪ.ɾɚ", "alligator: two feet, one flap"),
            # Does not flap: the next nucleus is stressed, or there is no
            # nucleus behind the stop for it to be foot-medial in.
            ("ə.tˈæk", "ə.tʰˈæk̚", "attack: the next nucleus is stressed"),
            ("mˈɪlɪtˌɛɹi", "mˈɪɫɪtˌɛɹi", "military: a SECONDARY stress blocks it"),
            ("təmˈe͜ɪto͜ʊ", "təmˈe͜ɪɾo͜ʊ", "tomato: the word-initial /t/ stays"),
            ("spˈɪn", "spˈɪ̃n", "spin: nothing here is an alveolar stop at all"),
            ("tˈæk", "tʰˈæk̚", "tack: word-initial, and nothing precedes it"),
            ("ˈæftɚ", "ˈæftɚ", "after: the /t/ is behind an /f/, not a nucleus"),
        ],
    )
    def test_flapping_is_conditioned_on_the_following_nucleus(
        self, source, expected, gloss
    ):
        """The restatement, in both directions.

        The rules asked for a PRECEDING primary-stressed vowel until a
        review measured them past the first foot. That statement is a real
        if minority textbook position and it is right about every trochee,
        which is exactly why it survived: 'butter' passes under both. It
        cannot reach a flap in any later foot -- 'editor' flapped its /d/
        and not its /t/, and GA flaps both -- and it has to stipulate
        separately that a stop before a stressed vowel never flaps. The
        rules now ask for an UNSTRESSED nucleus on the right, which is the
        standard generalization and gets both facts from one condition.

        The left context has not gone away: it is what keeps a
        word-initial stop out ('tomato'), which is a different job from
        the one the stress was doing.
        """
        assert _set(ENGLISH).apply(source) == expected, gloss

    def test_unstressed_is_the_absence_of_the_feature_not_a_negative_value(self):
        """Why the rules spell it '-primary -secondary' and not '-stress'.

        ``stress`` declares no default, so there is no unmarked value to
        name. ``∅`` is how the absence is *written* on the right of an
        arrow, but it is not a declared VALUE, so it cannot be asked for
        in a context: ``[vowel stress=∅]`` there is refused.
        ``[vowel -stress]`` reads like the thing wanted and is not: a '-'
        term resolves as a feature VALUE first and a BINARY feature name
        second, and ``stress`` is neither, so the term names nothing and
        the query is refused, with a message naming the spelling that
        works. That refusal is the resolver's, swept over every term in
        ``tests/test_query.py::TestEveryTermMustResolve``; what is pinned
        here is the rules' own choice -- the misleading spelling does not
        parse, and the working one derives both forms.
        """
        assert FEATURES.features["stress"].default is None
        # '∅' clears a value; it does not name one, so a context cannot
        # ask for it.
        assert ipakit.rewrite("kˈat", "[vowel] -> [stress=∅]") == "kat"
        with pytest.raises(R.RuleError):
            R.parse("t -> ɾ / [vowel] _ [vowel stress=∅]", FEATURES)
        with pytest.raises(R.RuleError):
            R.parse("t -> ɾ / [vowel] _ [-stress]", FEATURES)
        looks_right = "t -> ɾ / [vowel] _ [vowel -stress]"
        with pytest.raises(R.RuleError, match="-primary -secondary"):
            R.parse(looks_right, FEATURES)
        per_value = "t -> ɾ / [vowel] _ [vowel -primary -secondary]"
        assert ipakit.rewrite("ˈatˈa", per_value) == "ˈatˈa"
        assert ipakit.rewrite("ˈata", per_value) == "ˈaɾa"
        # And the shipped rules are written that way, all three of them.
        tapping = [r for r in _set(ENGLISH) if r.name.startswith("tapping")]
        assert len(tapping) == 3, "the tapping block changed shape"
        for rule in tapping:
            assert "-primary -secondary" in rule.source, rule.name
            assert "stress=primary" not in rule.source, rule.name

    def test_the_tie_no_longer_decides_whether_a_stop_flaps(self):
        """Swept, because the file's diphthong block now claims it.

        A rule that asks about stress on its left reads a tie, since an
        untied diphthong puts the stress on its first element and the unit
        beside the stop is the second. Tapping asks about the nucleus on
        its right instead, so both spellings of a word give the same
        flapping. The set is still tie-sensitive elsewhere -- vowel
        nasalization reaches one unit -- and that half is asserted too, so
        "ties may be dropped" cannot be read out of this.
        """
        rule_set = _set(ENGLISH)
        untie = "".join(dict.fromkeys(FEATURES.tie_bars))
        drop = str.maketrans("", "", untie)
        pairs = [
            (
                s1 + v1 + m + s2 + v2,
                s1 + v1.translate(drop) + m + s2 + v2.translate(drop),
            )
            for s1 in ("", "ˈ", "ˌ")
            for v1 in ("e͜ɪ", "a͜ɪ", "o͜ʊ")
            for m in ("t", "d")
            for s2 in ("", "ˈ", "ˌ")
            for v2 in ("o͜ʊ", "e͜ɪ", "ɪ")
        ]
        checked = 0
        for tied, untied in pairs:
            checked += 1
            a, b = rule_set.apply(tied), rule_set.apply(untied)
            assert a.count("ɾ") == b.count("ɾ"), (tied, a, untied, b)
        assert checked >= 50, "sweep did not run"
        assert rule_set.apply("pə.tˈeɪ.toʊ") == "pə.tʰˈeɪ.ɾoʊ"
        assert rule_set.apply("pə.tˈe͜ɪ.to͜ʊ") == "pə.tʰˈe͜ɪ.ɾo͜ʊ"
        # ... and the tie is still load-bearing for nasalization, which is
        # why the file does not tell anybody to stop writing them.
        assert rule_set.apply("ˈkaɪn") == "ˈkaɪ̃n"
        assert rule_set.apply("ˈka͜ɪn") == "ˈka͜ɪn"
        assert untie, "the inventory declares no tie bars"

    def test_the_lateral_release_rule_is_not_bled_by_the_syllabic_rule(self):
        """The literal-versus-class defect, found a second time.

        The file records it for the syllabic lateral and then repeated it one
        block further down: 'lateral release' was written '_ l', the syllabic
        rule had already made the /l/ an 'l̩', and 'bottle' came out with no
        release while 'button', whose rule is a class, was right. The rule
        now asks for the nucleus, which is both what it means and immune.
        """
        rule = next(r for r in _set(ENGLISH) if r.name == "lateral release")
        assert "syllabic=+" in rule.source, "the release rule stopped naming a nucleus"
        assert ipakit.rewrite(
            "bɑtl̩", "[manner=plosive] -> [release=lateral] / _ l"
        ) == ("bɑtl̩"), "premise moved: a literal now matches a syllabic lateral"
        assert _set(ENGLISH).apply("ˈæpl") == "ˈæpˡl̩"
        # And not in an onset cluster, which is what a bare lateral class
        # would have caught: 'plʌs' is /pl/, not a stop plus a nucleus.
        assert _set(ENGLISH).apply("plʌs") == "pl̥ʌs"
        assert _set(ENGLISH).apply("klˈin") == "kl̥ˈĩn"


class TestTheEnglishSetAssignsConstituencyBeforeReadingIt:
    """The ordering the American English fixes rest on, in both directions.

    Two rules ask '[syllabic=+]'. Neither can be right if the block that
    assigns it has not run, and neither failure is visible as an error --
    each just quietly does something else.
    """

    def _above_the_syllabic_block(self, name: str) -> R.RuleSet:
        rules = [r for r in _set(ENGLISH).rules if r.name != name]
        block = [r for r in _set(ENGLISH).rules if r.name == name]
        assert len(block) == 1, name
        return R.RuleSet(
            rules=tuple(
                rules[: [r.name for r in rules].index("syllabic nasal")]
                + block
                + rules[[r.name for r in rules].index("syllabic nasal") :]
            )
        )

    def test_tapping_before_a_syllabic_lateral_needs_the_block_first(self):
        permuted = self._above_the_syllabic_block("tapping (before a syllabic lateral)")
        assert _set(ENGLISH).apply("bˈɑtl") == "bˈɑɾl̩"
        assert permuted.apply("bˈɑtl") == "bˈɑtˡl̩", "no flap: nothing was syllabic yet"
        assert permuted.apply("lˈɪtl") == "lˈɪtˡl̩"

    def test_lateral_release_needs_the_block_first(self):
        permuted = self._above_the_syllabic_block("lateral release")
        assert _set(ENGLISH).apply("ˈæpl") == "ˈæpˡl̩"
        assert permuted.apply("ˈæpl") == "ˈæpl̩", "no release: nothing was syllabic yet"

    def test_but_where_the_block_sits_otherwise_is_free(self):
        """The file says the block could stand anywhere before its readers
        and that lifting the group to the top changes nothing. Measured."""
        group = {
            "syllabic nasal",
            "syllabic lateral",
            "tapping (before a syllabic lateral)",
            "tapping (after a coda rhotic)",
        }
        for where in (0, 1):
            permuted = _reordered(ENGLISH, group, where)
            moved = [
                w
                for w in CORPUS[ENGLISH]
                if permuted.apply(w) != _set(ENGLISH).apply(w)
            ]
            assert moved == [], f"lifting the group to {where} moved {moved}"

    def test_tapping_and_aspiration_can_no_longer_compete_for_a_segment(self):
        """The ordering claim the restatement retired, measured both ways.

        The file used to open by saying tapping runs before aspiration so
        that a stop which has become a tap is not then read as a voiceless
        plosive and aspirated. Once tapping asks for an UNSTRESSED nucleus
        on the right and aspiration for a primary-stressed one, no segment
        can satisfy both, and the ordering carries nothing. Two
        consequences are asserted rather than argued: the two rules swap
        freely, and all three tapping rules gather below the syllabic
        block without moving a derivation. The file's remaining ordering
        claim is the block one above, which does still bite.
        """
        base = {w: _set(ENGLISH).apply(w) for w in CORPUS[ENGLISH]}
        rules = list(_set(ENGLISH).rules)
        assert [r.name for r in rules[:2]] == ["tapping", "aspiration"]
        swapped = R.RuleSet(rules=(rules[1], rules[0], *rules[2:]))
        moved = [w for w in CORPUS[ENGLISH] if swapped.apply(w) != base[w]]
        assert moved == [], f"swapping tapping and aspiration moved {moved}"

        rest = [r for r in rules if r.name != "tapping"]
        at = [r.name for r in rest].index("tapping (before a syllabic lateral)")
        grouped = R.RuleSet(rules=tuple(rest[:at] + [rules[0]] + rest[at:]))
        moved = [w for w in CORPUS[ENGLISH] if grouped.apply(w) != base[w]]
        assert moved == [], f"gathering the tapping block moved {moved}"


class TestTheEnglishSetNamesASyllableMarginAndSoTheDotIsNotFreeThere:
    """The English set is not dot-blind, and exactly one position shows it.

    Aspiration is conditioned on '. _', so a dot is structure the rule was
    asked to read -- the same deliberate exception the German set makes.
    MEASURED over every dot position in the corpus: 1 of 130 changes the
    answer, and it is the one where the dot asserts a syllable margin
    between /s/ and /p/ that 'spˈɪn' did not assert. Writing it is a
    different claim about the word, and getting a different answer is
    correct.

    It was 1 of 122 until the corpus gained 'infant' and 'tenth' for the
    two places nasal assimilation reaches now that it is one rule with an
    agreement variable. The corpus moves, so the denominator moves; the
    claim is the numerator and which word it is.
    """

    def test_only_the_stated_margin_moves(self):
        rule_set = _set(ENGLISH)
        checked = 0
        moved: list[str] = []
        for word in CORPUS[ENGLISH]:
            base = rule_set.apply(word).replace(".", "")
            for cut in _cut_positions(word):
                dotted = word[:cut] + "." + word[cut:]
                checked += 1
                if rule_set.apply(dotted).replace(".", "") != base:
                    moved.append(dotted)
        assert checked == 130, f"sweep covered {checked}, not 130"
        assert moved == ["s.pˈɪn"], moved

    def test_and_the_unstated_margin_is_not_guessed(self):
        """Underspecification, the other half of the same claim."""
        assert _set(ENGLISH).apply("ə.tˈæk") == "ə.tʰˈæk̚"
        assert _set(ENGLISH).apply("ətˈæk") == "ətˈæk̚"


class TestTheEnglishGapThatIsRecordedRatherThanFixed:
    """The file names one under-application it does not repair.

    GA aspirates a word-initial voiceless stop before an unstressed vowel
    and this set does not, because the rule asks for a following primary
    stress. The file states the one-line repair and why it is not applied
    here; this pins the gap so it cannot be forgotten, and pins that the
    stated repair really is one -- if either half stops holding, the note
    is wrong and has to be rewritten.
    """

    def test_the_gap_is_real(self):
        assert _set(ENGLISH).apply("təmˈe͜ɪto͜ʊ") == "təmˈe͜ɪɾo͜ʊ"

    def test_and_the_rule_the_file_names_would_close_it(self):
        initial = "[manner=plosive voiced=-] -> [release=aspirated] / # _ [vowel]"
        assert initial in (R.RULES_DIR / f"{ENGLISH}.rules").read_text(
            encoding="utf-8"
        ), "the file no longer states the repair it is recording"
        rules = R.RuleSet(rules=(*_set(ENGLISH).rules, R.parse(initial, FEATURES)))
        assert rules.apply("təmˈe͜ɪto͜ʊ") == "tʰəmˈe͜ɪɾo͜ʊ"
        # And it does not reach the /p/ of 'spin', which is behind the /s/.
        assert rules.apply("spˈɪn") == "spˈɪ̃n"


# --------------------------------------------------------------------------
# Set 1: Spanish-accented English -- prothesis
# --------------------------------------------------------------------------


class TestSpanishAccentedEnglishDerivesTheseForms:
    """Whole forms. The gloss is in the id so a failure names the word."""

    @pytest.mark.parametrize(
        "source,expected,gloss",
        [
            ("skul", "eskul", "school"),
            ("stap", "estap", "stop"),
            ("speɪn", "espein", "Spain"),
            ("snoʊ", "esnou", "snow"),
            ("stɹɛs", "estɾes", "stress"),
            ("slɪp", "eslip", "slip"),
            ("smɔl", "esmol", "small"),
            ("sfɪɹ", "esfiɾ", "sphere"),
            ("vɛɹi", "beɾi", "very"),
            ("zu", "su", "zoo"),
            ("ʃip", "t͡ʃip", "sheep"),
            ("θɪŋk", "tiŋk", "think"),
            ("ðɪs", "dis", "this"),
            ("hɛlp", "xelp", "help"),
            ("sɪŋ", "sin", "sing"),
            ("bʌtɚ", "bateɾ", "butter"),
            ("bɝd", "beɾd", "bird"),
            ("kʌt", "kat", "cut"),
            ("bʊk", "buk", "book"),
            ("æpəl", "apal", "apple"),
        ],
    )
    def test_derivation(self, source, expected, gloss):
        assert _set(SPANISH).apply(source) == expected, gloss

    def test_a_velar_nasal_survives_before_a_velar(self):
        """The rule is word-final only: 'sink' keeps [ŋ] by assimilation."""
        assert _set(SPANISH).apply("sɪŋk") == "siŋk"
        assert _set(SPANISH).apply("sɪŋ") == "sin"

    @pytest.mark.parametrize("source", ["swit", "sut", "sim", "sɪstəm"])
    def test_no_prothesis_where_spanish_permits_the_onset(self, source):
        """/sw sj/ and plain /sV/ need no repair, so the 'e' must not appear."""
        assert not _set(SPANISH).apply(source).startswith("e")

    @pytest.mark.parametrize(
        "source,expected,gloss",
        [
            ("ɹˈæt", "rˈat", "rat: word-initial is the trill"),
            ("ɹɛd", "red", "red"),
            ("ɛnɹɪt͡ʃ", "enrit͡ʃ", "after /n/, as in 'honra'"),
            ("ɔlɹa͜ɪt", "olra͜ɪt", "after /l/, as in 'alrededor'"),
            ("ɪzɹeɪl", "isreil", "after /s/, as in 'Israel'"),
            ("hɛnɹi", "xenri", "Henry"),
            ("vɛɹi", "beɾi", "very: between vowels it is the tap"),
            ("bɹɛd", "bɾed", "bread: and in an onset cluster, 'brazo'"),
            ("stɹɛs", "estɾes", "stress: the /s/ is not adjacent, 'estrés'"),
            ("bʌtɚ", "bateɾ", "butter: and after the decomposed rhotic"),
        ],
    )
    def test_spanish_has_two_rhotics_and_the_choice_is_positional(
        self, source, expected, gloss
    ):
        """The file's header used to say Spanish has "one rhotic tap".

        It has two, contrastively -- 'pero'/'perro' -- and the tap is the
        elsewhere case, not the only case. Everything word-initial and
        everything after a coda /n l s/ is the trill.
        """
        assert _set(SPANISH).apply(source) == expected, gloss


class TestProthesisIsNotHitByTheWordEdgeInsertionDefect:
    """An insertion anchored on '#' is documented to fire outside the word.

    Pinning both halves: the defect as it stands, and the reason this set
    escapes it. If the defect is ever fixed the first test fails, and the
    reasoning here needs rereading rather than silently going stale.
    """

    def test_the_defect_is_real_when_nothing_else_is_pinned(self):
        """The defect this class is named for has been closed.

        An insertion anchored on '#' used to fire outside the written marks
        as well, giving 'ə#əkæt#ə'. A boundary run is one boundary and the
        gap an insertion takes is the inner one, so it is now one schwa in
        the one place -- and the Spanish file, which argued its context on
        the old behavior, now says so. The class is kept because the second
        half below is still why the context is written as it is.
        """
        assert ipakit.rewrite("#kæt#", "∅ -> ə / # _") == "#əkæt#"

    def test_pinning_real_segments_to_the_right_kills_the_spurious_site(self):
        """Outside the word there is no /s/ to match, so the far gap fails."""
        rule = "∅ -> e / # _ s [-vowel -approximant]"
        assert ipakit.rewrite("#skul#", rule) == "#eskul#"
        assert ipakit.rewrite("skul", rule) == "eskul"

    @pytest.mark.parametrize(
        "form", ["skul", "#skul", "skul#", "#skul#", "#skul#skul#", "skul skul"]
    )
    def test_the_shipped_set_inserts_once_per_word_however_marked(self, form):
        got = _set(SPANISH).apply(form)
        assert got.count("e") == form.count("k"), got
        assert got == form.replace("skul", "eskul"), got

    def test_the_epenthetic_vowel_is_not_reached_by_a_later_rule(self):
        """Prothesis runs first, so a later vowel rule could bleed it.

        The vowel rules are literals and /e/ is on no left-hand side, which
        is the file's stated reason. This is that reason as a test.
        """
        rs = _set(SPANISH)
        after_prothesis = rs.derive("skul").steps[0].after
        assert after_prothesis == "eskul", "premise moved"
        assert rs.apply("skul") == "eskul"


# --------------------------------------------------------------------------
# Set 2: Japanese -- the mora, and context-dependent epenthesis
# --------------------------------------------------------------------------


class TestJapaneseMoraicDerivesTheseForms:
    @pytest.mark.parametrize(
        "source,expected,gloss",
        [
            ("hɑt", "hotːo", "hot"),
            ("bɛd", "bedːo", "bed"),
            ("mæt͡ʃ", "mat͡ɕːi", "match"),
            ("mɪlk", "miɾuku", "milk"),
            ("stɹa͜ɪk", "sutoɾaiku", "strike"),
            ("kɹɪsməs", "kuɾisumasu", "Christmas"),
            ("pɛn", "pen", "pen"),
            ("hæm", "hamu", "ham"),
            ("kæmp", "kampu", "camp"),
            ("fɪlm", "ɸiɾumu", "film"),
            ("bʊk", "bukːu", "book"),
            ("kʌp", "kapːu", "cup"),
            ("bit", "biːto", "beat"),
            ("ko͜ʊt", "koːto", "coat"),
            ("kɪŋ", "kiŋɡu", "king"),
            ("tɛnɪs", "tenisu", "tennis"),
            ("dɪʃ", "diɕu", "dish"),
            ("θæŋk", "saŋku", "thank"),
            ("ðɪs", "zisu", "this"),
            ("vɔ͜ɪs", "boisu", "voice"),
            ("skul", "sukuːɾu", "school"),
            ("bɑks", "bokusu", "box"),
            ("tɑp", "topːu", "top"),
            ("kjut", "kjuːto", "cute"),
            ("bjuti", "bjuːtiː", "beauty"),
            ("bʌtɚ", "bataː", "butter"),
            ("ha͜ʊs", "hausu", "house"),
            ("t͡ʃiz", "t͡ɕiːzu", "cheese"),
            ("dɹa͜ɪv", "doɾaibu", "drive"),
            ("lʌnt͡ʃ", "ɾant͡ɕi", "lunch"),
            ("bæd͡ʒ", "bad͡ʑːi", "badge"),
            ("ʌp", "apːu", "up: a vowel-initial short monosyllable"),
            ("ɛɡ", "eɡːu", "egg"),
            ("æd", "adːo", "add"),
            ("ɪt", "itːo", "it"),
            ("wɛb", "webːu", "web: and one with an onset, for contrast"),
        ],
    )
    def test_derivation(self, source, expected, gloss):
        assert _set(JAPANESE).apply(source) == expected, gloss


class TestTheUnitIsTheMoraNotTheSyllable:
    """The three claims the file's header says a (C)V template gets wrong.

    Each is a rule the file does *not* write, so each is asserted as an
    absence: a vowel that must not appear.
    """

    @pytest.mark.parametrize(
        "source,expected", [("pɛn", "pen"), ("mæn", "man"), ("tɛnɪs", "tenisu")]
    )
    def test_coda_n_is_its_own_mora_so_it_takes_no_vowel(self, source, expected):
        assert _set(JAPANESE).apply(source) == expected

    def test_a_nasal_before_a_consonant_takes_no_vowel_either(self):
        """'camp' [kampu], not *[kamupu] -- the /m/ is the moraic nasal."""
        assert _set(JAPANESE).apply("kæmp") == "kampu"

    def test_a_geminates_first_half_is_a_mora_so_nothing_is_inserted_in_it(self):
        """Spelled as a long consonant precisely so no C_C gap exists.

        Were it spelled 'hott', the epenthesis rules would find the gap
        between the two stops. The assertion is on the whole form and on
        the unit count, because 'hotːo' and 'hotto' spell the same word
        and only one of them has a cluster in it.
        """
        got = _set(JAPANESE).apply("hɑt")
        assert got == "hotːo"
        assert [u.core for u in R.units(got, FEATURES)] == ["h", "o", "t", "o"]
        assert R.units(got, FEATURES)[2].prosody == {"length": "long"}

    def test_a_long_vowel_blocks_gemination_but_a_short_one_does_not(self):
        rs = _set(JAPANESE)
        assert rs.apply("bit") == "biːto", "tense vowel: no geminate"
        assert rs.apply("bɪt") == "bitːo", "lax vowel: geminate"

    def test_a_vowel_initial_short_monosyllable_geminates_too(self):
        """The word class the one-context spelling silently dropped.

        '[-vowel] [vowel -long] _ #' demands a real consonant in front of
        the short vowel, and 'up', 'egg', 'add', 'it' have none, so the rule
        declined and Japanese アップ came out [apu]. The context is stated
        twice now -- after a consonant, or after nothing -- because that
        union is what "not after a vowel" means.
        """
        rs = _set(JAPANESE)
        for source, expected in [
            ("ʌp", "apːu"),
            ("ɛɡ", "eɡːu"),
            ("æd", "adːo"),
            ("ɪt", "itːo"),
        ]:
            assert rs.apply(source) == expected, source

    def test_and_the_two_spellings_the_file_rejects_are_each_wrong(self):
        """Both sides of the tradeoff the file records, measured.

        Demanding a consonant loses the vowel-initial monosyllables;
        dropping the requirement altogether lets every diphthong in. The
        file picks neither and states the union, so both of these have to
        stay wrong for its argument to hold.
        """
        stop = "[obstruent -fricative]"
        rules = (R.RULES_DIR / f"{JAPANESE}.rules").read_text(encoding="utf-8")
        assert f"{stop} -> [length=long] / [-vowel] [vowel -long] _ #" in rules
        assert f"{stop} -> [length=long] / # [vowel -long] _ #" in rules
        # Only the consonant context: the monosyllables lose their geminate.
        without = [
            r for r in _set(JAPANESE) if r.name != "gemination (word-initial vowel)"
        ]
        narrow = R.RuleSet(rules=tuple(without))
        assert narrow.apply("ʌp") == "apu"
        assert narrow.apply("ɪt") == "ito"
        # No left context at all: the diphthongs geminate, which is the
        # commoner error, and is the measurement that decides between them
        # if ever only one may stand.
        wide = R.RuleSet(
            rules=tuple(
                (
                    R.parse(
                        f"{stop} -> [length=long] / [vowel -long] _ # ; wide", FEATURES
                    )
                    if r.name.startswith("gemination")
                    else r
                )
                for r in without
            )
        )
        assert wide.apply("ʌp") == "apːu", "the wide spelling does get these right"
        assert wide.apply("stɹa͜ɪk") == "sutoɾaikːu"
        assert wide.apply("dɹa͜ɪv") == "doɾaibːu"
        assert wide.apply("a͜ʊt") == "autːo"
        # Not 'house' or 'voice': the class is stops and affricates, so a
        # final fricative is out of reach of either spelling.
        assert wide.apply("ha͜ʊs") == _set(JAPANESE).apply("ha͜ʊs") == "hausu"

    def test_the_whole_postalveolar_series_maps_to_the_alveolo_palatal(self):
        """One inventory claim, made once.

        /ʃ/ was mapped and the affricates were not, so 'dish' got [ɕ] while
        'match' kept [t͡ʃ] -- the same claim answered two ways in one file,
        invisible because no derivation contains both.
        """
        rs = _set(JAPANESE)
        assert rs.apply("dɪʃ") == "diɕu"
        assert rs.apply("mæt͡ʃ") == "mat͡ɕːi"
        assert rs.apply("bæd͡ʒ") == "bad͡ʑːi"
        assert rs.apply("lʌnt͡ʃ") == "ɾant͡ɕi"
        # The predicate rather than the three words: no derivation of this
        # corpus may contain a postalveolar at all.
        left = {
            unit.core
            for word in CORPUS[JAPANESE]
            for unit in R.units(rs.apply(word), FEATURES)
            if unit.segment is not None
            and FEATURES.get_features(unit.core).get("place") == "postalveolar"
        }
        assert left == set(), f"postalveolars survive: {sorted(left)}"

    def test_a_diphthong_blocks_gemination_because_of_what_precedes_it(self):
        """'strike' ends [...aiku]: the unit before the final /k/ is a short
        vowel too, and what distinguishes it from 'hot' is the unit before
        THAT. The context is stated over two positions for this reason."""
        rs = _set(JAPANESE)
        assert rs.apply("stɹa͜ɪk") == "sutoɾaiku"
        assert rs.apply("mɪlk") == "miɾuku", "no vowel before /k/ at all"

    def test_an_untied_diphthong_gives_a_different_and_wrong_answer(self):
        """The file requires tied diphthongs; this is what it costs not to."""
        rs = _set(JAPANESE)
        assert rs.apply("vɔ͜ɪs") == "boisu"
        assert rs.apply("vɔɪs") == "boːisu"


class TestTheEpentheticVowelsQualityIsContextDependent:
    """Three qualities, and the class-vs-literal choice that makes them work."""

    @pytest.mark.parametrize(
        "source,expected,because",
        [
            ("hɑt", "hotːo", "o after /t/"),
            ("bɛd", "bedːo", "o after /d/"),
            ("bɛst", "besuto", "o after /t/ in a cluster too"),
            ("mæt͡ʃ", "mat͡ɕːi", "i after an alveolo-palatal affricate"),
            ("bæd͡ʒ", "bad͡ʑːi", "i after the voiced one"),
            ("mɪlk", "miɾuku", "u elsewhere"),
            ("kɹɪsməs", "kuɾisumasu", "u elsewhere, three times"),
            ("dɪʃ", "diɕu", "u, not i: /ɕ/ is not an affricate"),
        ],
    )
    def test_quality(self, source, expected, because):
        assert _set(JAPANESE).apply(source) == expected, because

    def test_a_literal_is_bled_by_a_segmental_change_and_not_by_a_prosodic_one(self):
        """The correction to an argument that looked obviously right.

        The Japanese file first claimed its class-valued contexts were
        needed because gemination had made the /t/ into a 'tː' a literal
        could no longer see. Measured, that is false, and the reason is
        worth keeping: a prosodic change leaves the unit's *core* alone, so
        a literal still matches, while a segmental change goes into the core
        and a literal stops matching. The american-english syllabic-lateral
        defect was the second kind, which is why it bled -- and so was the
        lateral-release defect found in the same file two rounds later, one
        block below the note warning about it.
        """
        long_t = R.units("tː", FEATURES)[0]
        devoiced_l = R.units("l̥", FEATURES)[0]
        aspirated_t = R.units("tʰ", FEATURES)[0]
        assert (long_t.core, long_t.prosody) == ("t", {"length": "long"})
        assert R._pattern("t", FEATURES).matches(
            long_t, FEATURES
        ), "prosodic: still seen"
        assert (devoiced_l.core, devoiced_l.prosody) == ("l̥", {})
        assert not R._pattern("l", FEATURES).matches(devoiced_l, FEATURES)
        assert not R._pattern("t", FEATURES).matches(aspirated_t, FEATURES)
        # So both spellings of the epenthesis context work here, and the
        # class is chosen for stating the generalization, not for surviving.
        assert ipakit.rewrite("hotː", "∅ -> o / t _ #") == "hotːo"
        klass = R._pattern("[manner=plosive place=alveolar]", FEATURES)
        assert klass.matches(long_t, FEATURES)
        assert _set(JAPANESE).apply("hɑt") == "hotːo"

    @pytest.mark.parametrize(
        "source,expected", [("kjut", "kjuːto"), ("bjuti", "bjuːtiː")]
    )
    def test_nothing_is_inserted_before_a_glide(self, source, expected):
        """C+/j/ is one licit mora, so '[-vowel]' on the right was too wide."""
        assert _set(JAPANESE).apply(source) == expected

    def test_the_general_rule_lists_no_exceptions(self):
        """It is general *because* the specific rules ran first.

        The predicate is on the rule's own text: if somebody ever repairs
        an ordering bug by adding exclusions to the general rule, this
        fails and the file's argument has to be rewritten instead.
        """
        (general,) = [r for r in _set(JAPANESE) if r.name == "u elsewhere (final)"]
        assert general.source.startswith("∅ -> u / [-vowel -nasal] _ # ;")
        assert [str(p) for p in general.query.left] == ["[-vowel -nasal]"]


# --------------------------------------------------------------------------
# Set 3: French -- deletion
# --------------------------------------------------------------------------


class TestFrenchLiaisonDerivesTheseForms:
    @pytest.mark.parametrize(
        "source,expected,gloss",
        [
            ("lez‿ami", "le‿zami", "les amis"),
            ("pətit‿ami", "pəti‿tami", "petit ami"),
            ("lez‿ʃjɛ̃", "le‿ʃjɛ̃", "les chiens"),
            ("pətit‿ʃjɛ̃", "pəti‿ʃjɛ̃", "petit chien"),
            ("lez", "le", "les, alone"),
            ("mɔ̃n‿ami", "mɔ̃‿nami", "mon ami"),
            ("tʁop‿ɛmabl", "tʁo‿pɛmabl", "trop aimable"),
            ("pʁəmjeʁ‿etaʒ", "pʁəmjeʁ‿etaʒ", "premier étage: /ʁ/ is stable"),
            ("nuz‿avɔ̃", "nu‿zavɔ̃", "nous avons"),
            ("il‿ɛt‿ɛ̃", "il‿ɛ‿tɛ̃", "il est un"),
            ("pətitə", "pətit", "petite"),
            ("pətit", "pəti", "petit"),
            ("bɔnə", "bɔn", "bonne"),
            ("bɔn", "bɔ", "bon"),
        ],
    )
    def test_derivation(self, source, expected, gloss):
        assert _set(FRENCH).apply(source) == expected, gloss

    @pytest.mark.parametrize(
        "source,gloss",
        [
            ("bɔ̃ʒuʁ", "bonjour"),
            ("mɛʁ", "mer"),
            ("puʁ", "pour"),
            ("pʁəmjeʁ", "premier: the archaic latent one, now unrepaired"),
        ],
    )
    def test_a_final_rhotic_is_stable_and_is_not_deleted(self, source, gloss):
        """The set's central simplification, applied to /ʁ/, was backwards.

        A final /z t n p/ is latent often enough that deleting it is right
        more often than not; a final /ʁ/ is stable in the great majority of
        the language -- every -eur, -oir and -ir word -- so the same rule
        net-corrupted. The file singled out 'premier' as its reason to
        include /ʁ/, and that one archaic phrase is the whole of what
        removing it costs.
        """
        assert _set(FRENCH).apply(source) == source, gloss

    def test_no_rule_in_the_set_names_the_rhotic_any_more(self):
        """A predicate, not a spot check: the pair was a liaison rule and a
        deletion rule, and leaving either alone would be worse than both."""
        naming = [r.name for r in _set(FRENCH) if "ʁ" in r.source]
        assert naming == [], naming

    @pytest.mark.parametrize(
        "source,expected,gloss",
        [
            ("lə", "lə", "le: the schwa is the only vowel it has"),
            ("ʒə", "ʒə", "je"),
            ("sə", "sə", "ce"),
            ("ynə", "yn", "une: another vowel, so the schwa goes"),
            ("bɔnə", "bɔn", "bonne"),
            ("pətitə", "pətit", "petite"),
            ("katʁə", "katʁ", "quatre: after a cluster"),
        ],
    )
    def test_a_word_is_not_reduced_to_a_bare_consonant(self, source, expected, gloss):
        """'ə -> ∅ / _ #' stripped the clitics to [l], [ʒ], [s].

        Those are not words. The condition wanted is "the word has another
        vowel", which is a claim about a constituent; what is available is
        one more unit to the left, and since the failing case is exactly
        "a single word-initial consonant", that is enough -- in two lines,
        because a query is a conjunction and "any unit" cannot be said once.
        """
        assert _set(FRENCH).apply(source) == expected, gloss

    def test_liaison_does_not_cross_a_break(self):
        """A space is a break, so the latent consonant is simply lost."""
        assert _set(FRENCH).apply("lez ami") == "le ami"
        assert _set(FRENCH).apply("lez‿ami") == "le‿zami"

    def test_the_consonant_moves_rather_than_being_copied(self):
        """Resyllabification, expressed as a copy and then a deletion.

        Both edits are visible in the trace, and the intermediate form has
        two /z/ in it -- which is why the deletion cannot be conditional.
        """
        derivation = _set(FRENCH).derive("lez‿ami")
        fired = [(s.rule, s.after) for s in derivation.fired]
        assert fired == [
            ("liaison (z)", "lez‿zami"),
            ("final z deletion", "le‿zami"),
        ]
        assert derivation.result.count("z") == 1


class TestEachRuleKindHasAShippedExample:
    """The reason the French set exists: four operations, four examples.

    Read off the parsed rules rather than the prose, so the claim cannot
    drift from the data.
    """

    def test_substitution_insertion_and_deletion_are_all_shipped(self):
        kinds: dict[str, set[str]] = {
            "substitution": set(),
            "feature change": set(),
            "insertion": set(),
            "deletion": set(),
        }
        for name in ALL_SETS:
            for rule in _set(name):
                if rule.inserts:
                    kinds["insertion"].add(name)
                elif rule.deletes:
                    kinds["deletion"].add(name)
                elif isinstance(rule.becomes, dict):
                    kinds["feature change"].add(name)
                else:
                    kinds["substitution"].add(name)
        # Japanese joined the feature-change set when its eight literal
        # gemination lines collapsed into one rule over a class: length is
        # prosody, and writing prosody is a feature change like any other.
        assert kinds["feature change"] == {ENGLISH, GERMAN, JAPANESE}
        assert kinds["insertion"] == {SPANISH, JAPANESE, FRENCH}
        assert kinds["deletion"] == {FRENCH}
        # The French set is *only* insertion and deletion: every one of its
        # rules is one or the other, which is what makes it the deletion
        # example rather than a set that happens to contain one.
        assert kinds["substitution"] == {SPANISH, JAPANESE}
        assert all(kinds.values()), f"a rule kind has no example: {kinds}"


class TestWhatTheLinkingMarkDoes:
    """'‿' is new as a nameable context item, and it behaves three ways
    that are load-bearing for liaison and surprising out of it. Pinned so
    that if any changes, the French file's reasoning is revisited rather
    than quietly invalidated."""

    def test_the_linking_mark_is_opaque_to_context_scanning(self):
        """A syllable dot is stepped over; this is not.

        The mark's declared meaning is *absence* of a break, so a rule
        looking across it arguably should see through it. It does not --
        and that now follows from the declaration rather than from the
        absence of one: opacity is read off the level, and 'word' is
        opaque. Whether a mark meaning "no pause" ought to be transparent
        is an open question about the declaration.
        """
        spec = "t -> ɾ / [vowel] _ [vowel]"
        assert ipakit.rewrite("ata", spec) == "aɾa"
        assert ipakit.rewrite("a.ta", spec) == "a.ɾa", "the dot is transparent"
        assert ipakit.rewrite("a‿ta", spec) == "a‿ta", "the linking mark is not"

    def test_a_rule_may_name_the_linking_mark(self):
        """Which is how the liaison rules state their domain."""
        assert ipakit.rewrite("az‿ami", "z -> ∅ / _ ‿") == "a‿ami"

    def test_the_linking_mark_is_a_word_edge(self):
        """It declares level="word", so '#' reaches it -- which is what
        lets each French deletion be one rule rather than two."""
        assert R.units("a‿b", FEATURES)[1].level == "word", "the mark lost its level"
        assert ipakit.rewrite("lez‿ami", "z -> ∅ / _ #") == "le‿ami"
        assert ipakit.rewrite("lez ami", "z -> ∅ / _ #") == "le ami"
        assert ipakit.rewrite("lez.ami", "z -> ∅ / _ #") == "lez.ami", "not the dot"

    def test_any_boundary_does_reach_the_linking_mark(self):
        """'%' matches the mark that says there is no boundary."""
        assert ipakit.rewrite("lez‿ami", "z -> ∅ / _ %") == "le‿ami"

    def test_a_word_edge_pattern_is_what_a_word_final_rule_wants_and_not_any(self):
        """'#' and '%' both reach the mark; only '#' is the right question.

        This was the gap that made every French deletion rule two rules.
        '#' was too narrow -- the mark declared no level, so nothing in the
        level ladder reached it. '%' is too wide -- it also reaches the
        syllable dot, which is word-INTERNAL, and a word-final rule written
        with it silently depends on whether anybody typed the dots. Nothing
        sat between them. Declaring level="word" on the mark put it on the
        ladder, so '#' is now that pattern and '%' is still the wrong one.
        """
        # '#' reaches the mark and stops at the dot: both halves matter.
        assert ipakit.rewrite("lez‿z.ami", "z -> ∅ / _ #") == "le‿z.ami"
        assert ipakit.rewrite("lez‿ami", "z -> ∅ / _ #") == "le‿ami"
        # '%' catches the mark and the dot alike -- here, wrongly, deleting
        # the liaison consonant that had just been placed after the mark.
        assert ipakit.rewrite("lez‿z.ami", "z -> ∅ / _ %") == "le‿.ami"
        assert ipakit.rewrite("lez‿z.ami", "z -> ∅ / _ ‿") == "le‿z.ami"
        # So the set is written with '#', and 'les amis' survives its
        # dotted spellings -- except the one pinned as a known limit in
        # test_a_dot_after_the_linking_mark_loses_the_liaison_it_licensed.
        french = _set(FRENCH)
        assert french.apply("lez‿ami") == "le‿zami"
        # Invariant modulo the dots, which is the property that matters;
        # exactly where the dot lands is the tokenizer's business.
        for dotted in ("lez‿a.mi", "le.z‿ami", "lez.‿ami"):
            assert french.apply(dotted).replace(".", "") == "le‿zami", dotted

    def test_a_rule_can_insert_the_linking_mark(self):
        """So a set could mark the liaison it licenses."""
        assert ipakit.rewrite("lezami", "∅ -> ‿ / [vowel] _ z [vowel]") == "le‿zami"

    def test_a_boundary_can_be_rewritten_as_another_from_a_file_too(self):
        """The space CAN be put in the mark's place, in a set as on a line.

        Rewriting one boundary as another used to be refused outright, and
        that is the reason the French file gives for taking '‿' in its
        input rather than marking a space-separated phrase. It is
        expressible now: a boundary may be written, unwritten or restated
        at another level (``ipakit.rules``). The comment rule used to stop
        a *set* from saying it -- a line beginning with '#' was prose, so
        the word mark was the one boundary no file could name -- and the
        two are told apart by position now, the mark being a target
        exactly when it is the whole of what stands left of the arrow.
        """
        rule = R.parse("# -> ‿", FEATURES)
        assert R.spell(rule.apply("lez ami", FEATURES)[0]) == "lez‿ami"
        assert len(R.RuleSet.parse("# -> ‿", FEATURES)) == 1, "not read as a comment"
        assert ipakit.rewrite("lez ami", "# -> ‿") == "lez‿ami"
        # The copy-beside-the-space spelling still says its own thing.
        assert ipakit.rewrite("lez ami", "∅ -> ‿ / z # _ [vowel]") == "lez ‿ami"


# --------------------------------------------------------------------------
# Set 4: German -- the tier ladder read from the coda side
# --------------------------------------------------------------------------


class TestGermanFinalDevoicingDerivesTheseForms:
    @pytest.mark.parametrize(
        "source,expected,gloss",
        [
            ("ʁaːd", "ʁaːt", "Rad"),
            ("ʁaː.dəs", "ʁaː.dəs", "Rades: an onset, not a coda"),
            ("taːɡ", "taːk", "Tag"),
            ("taː.ɡəs", "taː.ɡəs", "Tages"),
            ("liːb", "liːp", "lieb"),
            ("liː.bə", "liː.bə", "liebe"),
            ("bʁaːv", "bʁaːf", "brav: a fricative devoices too"),
            ("bʁaː.və", "bʁaː.və", "brave"),
            ("kɪnd", "kɪnt", "Kind"),
            ("haʊz", "haʊs", "Haus"),
            ("hɔy.zɐ", "hɔy.zɐ", "Häuser"),
            ("liːb.lɪç", "liːp.lɪç", "lieblich: a word-internal coda"),
            ("zaːɡ.baːɐ̯", "zaːk.baːɐ̯", "sagbar"),
        ],
    )
    def test_derivation(self, source, expected, gloss):
        assert _set(GERMAN).apply(source) == expected, gloss

    @pytest.mark.parametrize("source", ["laŋ", "viːl", "maːn", "ʃøːn"])
    def test_sonorants_do_not_devoice(self, source):
        """The class is obstruents. A nasal or a liquid must come out whole."""
        assert _set(GERMAN).apply(source) == source

    def test_the_class_is_exactly_the_obstruents(self):
        """The rule asks for the declared 'obstruent' class, where it used
        to write that class out as a complement. This checks what the term
        reaches: every registered phone the query matches is a plosive,
        fricative or affricate, and every one of those is matched. A count
        would pass while a whole manner quietly fell out; the partition
        cannot.
        """
        # Named here rather than derived, deliberately and for the one
        # reason that justifies it: this is the INDEPENDENT statement the
        # query is checked against, so deriving it from the same place the
        # query resolves through would make the test agree with itself. The
        # names are checked against the declaration so a typo cannot make it
        # vacuous -- which is the failure mode a bare literal set invites.
        obstruent_manners = {"plosive", "fricative", "affricate"}
        declared = set(FEATURES.features["manner"].values)
        assert obstruent_manners <= declared, obstruent_manners - declared
        pattern = _set(GERMAN).rules[0].target
        assert pattern is not None
        matched, expected = set(), set()
        for phone in FEATURES.phones:
            units = R.units(phone, FEATURES)
            if len(units) != 1 or units[0].segment is None:
                continue
            if pattern.matches(units[0], FEATURES):
                matched.add(phone)
            if FEATURES.get_features(phone).get("manner") in obstruent_manners:
                expected.add(phone)
        assert expected, "no obstruents in the inventory; the test is vacuous"
        assert (
            matched == expected
        ), f"{len(matched - expected)} extra, {len(expected - matched)} missing"

    def test_the_query_a_reader_would_reach_for_first_is_refused(self):
        """'[manner=obstruent]' now fails loudly instead of matching nothing.

        This test was written as a PIN on an escape: the guard checked only
        the feature KEY, so an undeclared VALUE built a constraint no phone
        could satisfy and the rule silently never fired -- while
        docs/rules.md promised a misspelled feature fails loudly on both
        sides of the arrow. The pin fired when the value arm was guarded,
        which is the pin doing its job, so it now states the new behavior.
        'obstruent' is a natural thing to reach for and is a natural CLASS
        over the values of 'manner', not one of them, so the key=value
        spelling stays an error -- and the message names the one that
        works, because a reader who wrote this wanted something real.
        """
        assert "obstruent" not in FEATURES.features["manner"].values
        with pytest.raises(R.RuleError) as caught:
            R.parse("[manner=obstruent] -> [voiced=-] / _ .", FEATURES)
        message = str(caught.value)
        assert "obstruent" in message and "manner" in message
        # The error is useful, not merely loud: it names the alternatives.
        assert "plosive" in message
        assert "'[obstruent]'" in message

    def test_the_whole_grammar_is_one_rule(self):
        """Worth pinning: this is the set a reader learns the notation from,
        and a second rule appearing changes what it demonstrates."""
        assert len(_set(GERMAN)) == 1


class TestTheCodaConditionIsNotTheWordEdgeCondition:
    """'_ .' and '_ #' are different rules, and the difference is the point.

    The american-english set conditions aspiration on an onset margin,
    '. _'. Nothing shipped read the same declared ordinal ladder from the
    right-hand side until this set did. The tier nesting is
    one-directional -- a word edge IS a syllable margin, a syllable break
    is NOT a word edge -- so the coda formulation is strictly wider, and a
    word-internal coda is where they part company.
    """

    #: Read off the shipped rule, not written out again. A second copy of
    #: the class would let the file and the test drift apart, and then this
    #: test would be measuring a query nothing ships.
    OBSTRUENT = str(_set(GERMAN).rules[0].target)

    @pytest.mark.parametrize("form", ["ʁaːd", "taːɡ", "liːb", "bʁaːv", "kɪnd"])
    def test_they_agree_at_the_edge_of_the_form(self, form):
        """Neither needs a boundary typed: the end of a form is a word edge,
        and a word edge reaches the syllable level."""
        coda = ipakit.rewrite(form, f"{self.OBSTRUENT} -> [voiced=-] / _ .")
        edge = ipakit.rewrite(form, f"{self.OBSTRUENT} -> [voiced=-] / _ #")
        assert coda == edge != form, f"{coda!r} vs {edge!r}"

    @pytest.mark.parametrize(
        "form,coda_gives", [("liːb.lɪç", "liːp.lɪç"), ("zaːɡ.baːɐ̯", "zaːk.baːɐ̯")]
    )
    def test_they_diverge_on_a_word_internal_coda(self, form, coda_gives):
        """The finding, asserted rather than described: '_ #' misses these."""
        assert (
            ipakit.rewrite(form, f"{self.OBSTRUENT} -> [voiced=-] / _ .") == coda_gives
        )
        assert ipakit.rewrite(form, f"{self.OBSTRUENT} -> [voiced=-] / _ #") == form

    def test_the_reverse_nesting_does_not_hold(self):
        """A syllable break is not a word edge, which is what makes '_ .'
        the wider of the two and not merely a synonym."""
        assert R._reaches("word", "syllable", FEATURES)
        assert not R._reaches("syllable", "word", FEATURES)

    @pytest.mark.parametrize("form", ["liːblɪç", "zaːɡbaːɐ̯", "liːbliçə"])
    def test_an_unstated_interior_margin_is_not_guessed(self, form):
        """The same underspecification that keeps aspiration out of 'ətˈæk'.

        Absence of a dot is not "one syllable"; it is no claim at all, and
        the rule declines rather than inventing the structure.
        """
        assert _set(GERMAN).apply(form) == form


class TestTheGermanSetNamesTheBoundaryAndSoTheDotIsNotOptional:
    """The exception to the dot-transparency property, and why it is one.

    For every other shipped set a syllable dot must not change the answer,
    or one word gets two readings depending on who typed the dots. This
    set's rule NAMES the boundary, and a named boundary is not stepped
    over -- so here the dot is structure the rule was asked to read. The
    contrast is asserted in both directions so neither half can rot.
    """

    def test_adding_a_dot_changes_the_answer_deliberately(self):
        assert _set(GERMAN).apply("liːblɪç") == "liːblɪç"
        assert _set(GERMAN).apply("liːb.lɪç") == "liːp.lɪç"

    def test_and_that_is_because_the_rule_names_the_boundary(self):
        (rule,) = _set(GERMAN).rules
        assert rule.query.right[0].names_boundary
        for name in DOT_BLIND:
            named = [
                r.name
                for r in _set(name)
                if any(
                    p.names_boundary and p.boundary == "syllable"
                    for p in (*r.query.left, *r.query.right)
                )
            ]
            assert named == [], f"{name} names a syllable boundary: {named}"


# --------------------------------------------------------------------------
# Ordering
# --------------------------------------------------------------------------


class TestOrderingMattersWhereTheFileSaysItDoes:
    """Each file marks its load-bearing orderings. Each is permuted here.

    A dependency asserted in prose and untested is a comment, and comments
    have gone stale in this repo before. Every case names the word that
    moves and what it moves to, so a failure says which claim broke.
    """

    def test_spanish_decomposes_the_rhotic_vowel_before_tapping(self):
        """Feeding: the tap rule must reach the /ɹ/ decomposition produced."""
        permuted = _reordered(
            SPANISH,
            {"ɹ is the tap elsewhere", *_TRILLS},
            _index(SPANISH, "unstressed r-colored vowel decomposes"),
        )
        assert _set(SPANISH).apply("bʌtɚ") == "bateɾ"
        assert permuted.apply("bʌtɚ") == "bateɹ", "an English approximant left in"
        assert _set(SPANISH).apply("bɝd") == "beɾd"
        assert permuted.apply("bɝd") == "beɹd"

    def test_japanese_lengthens_the_tense_vowels_before_merging_the_lax_ones(self):
        """Bleeding: once /ɪ/ is /i/, a rule over /i/ cannot tell them apart."""
        lax = {
            "ɪ is short i",
            "ɛ is short e",
            "æ is short a",
            "ʌ is short a",
            "ə is short a",
            "ʊ is short u",
            "ɑ is short o",
        }
        permuted = _reordered(JAPANESE, lax, _index(JAPANESE, "tense i lengthens"))
        assert _set(JAPANESE).apply("mɪlk") == "miɾuku"
        assert permuted.apply("mɪlk") == "miːɾuku"
        assert _set(JAPANESE).apply("kɹɪsməs") == "kuɾisumasu"
        assert permuted.apply("kɹɪsməs") == "kuɾiːsumasu"

    def test_japanese_geminates_after_the_vowel_rules_have_set_the_length(self):
        gemination = {r.name for r in _set(JAPANESE) if r.name.startswith("gemination")}
        assert len(gemination) == 2, "the gemination block moved"
        permuted = _reordered(
            JAPANESE, gemination, _index(JAPANESE, "tense i lengthens")
        )
        assert _set(JAPANESE).apply("bit") == "biːto"
        assert permuted.apply("bit") == "biːtːo", "a geminate after a long vowel"
        assert permuted.apply("stɹa͜ɪk") == "sutoɾaikːu"

    def test_japanese_geminates_before_epenthesis_fills_the_site(self):
        gemination = {r.name for r in _set(JAPANESE) if r.name.startswith("gemination")}
        permuted = _reordered(JAPANESE, gemination, len(_set(JAPANESE).rules))
        for source, in_order, too_late in [
            ("hɑt", "hotːo", "hoto"),
            ("bɛd", "bedːo", "bedo"),
            ("mæt͡ʃ", "mat͡ɕːi", "mat͡ɕi"),
            ("kʌp", "kapːu", "kapu"),
        ]:
            assert _set(JAPANESE).apply(source) == in_order
            assert permuted.apply(source) == too_late, source

    def test_japanese_runs_the_specific_epenthesis_qualities_before_the_general_one(
        self,
    ):
        """The point of the set: the general rule is correct only because
        the specific rules have already taken their sites."""
        specific = {
            "o after a coronal stop (cluster)",
            "o after a coronal stop (final)",
            "i after an alveolo-palatal affricate (cluster)",
            "i after an alveolo-palatal affricate (final)",
        }
        permuted = _reordered(JAPANESE, specific, len(_set(JAPANESE).rules))
        for source, in_order, general_first in [
            ("hɑt", "hotːo", "hotːu"),
            ("bɛd", "bedːo", "bedːu"),
            ("mæt͡ʃ", "mat͡ɕːi", "mat͡ɕːu"),
            ("stɹa͜ɪk", "sutoɾaiku", "sutuɾaiku"),
            ("bit", "biːto", "biːtu"),
        ]:
            assert _set(JAPANESE).apply(source) == in_order
            assert permuted.apply(source) == general_first, source

    def test_french_licenses_liaison_before_deleting_the_latent_consonant(self):
        """Bleeding: deleted first, the consonant is gone before the rule
        that would have put a copy out of reach ever looked."""
        deletion = {
            r.name
            for r in _set(FRENCH)
            if "deletion" in r.name and "schwa" not in r.name
        }
        assert len(deletion) == 4, "the deletion block moved"
        permuted = _reordered(FRENCH, deletion, 0)
        for source, in_order, bled in [
            ("lez‿ami", "le‿zami", "le‿ami"),
            ("pətit‿ami", "pəti‿tami", "pəti‿ami"),
            ("mɔ̃n‿ami", "mɔ̃‿nami", "mɔ̃‿ami"),
        ]:
            assert _set(FRENCH).apply(source) == in_order
            assert permuted.apply(source) == bled, source

    def test_french_deletes_the_final_schwa_last_or_the_contrast_collapses(self):
        """The classical demonstration. Ordered first, 'petit' and 'petite'
        both come out [pəti] and the grammar has lost a distinction."""
        schwa = {r.name for r in _set(FRENCH) if "schwa" in r.name}
        assert len(schwa) == 2, "the schwa block moved"
        permuted = _reordered(FRENCH, schwa, 0)
        assert (_set(FRENCH).apply("pətitə"), _set(FRENCH).apply("pətit")) == (
            "pətit",
            "pəti",
        )
        assert (permuted.apply("pətitə"), permuted.apply("pətit")) == ("pəti", "pəti")
        assert permuted.apply("bɔnə") == "bɔ", "'bonne' loses its /n/ too"


#: Every ordering the shipped files argue, written as blocks because that
#: is how the files argue them -- see ``_reordered`` on why a dependency
#: between two blocks many lines apart is invisible to a neighbor sweep.
#: Each entry is (earlier, later): every rule named on the left runs
#: before every rule named on the right, and the class below asserts these
#: are the WHOLE of it. A transposition moves an answer exactly when it
#: puts one of these pairs the wrong way round, so a set that acquires a
#: dependency its file does not argue fails with the pair named, and an
#: ordering the corpus can no longer see fails with the block named.
_LENGTH = (
    "tense i lengthens",
    "tense u lengthens",
    "ɔ is long o",
    "eɪ is long e",
    "oʊ is long o",
    "unstressed r-colored vowel is long a",
    "stressed r-colored vowel is long a",
)
_DIPHTHONGS = ("aɪ is a + i", "aʊ is a + u", "ɔɪ is o + i")
_SHORT = (
    "ɪ is short i",
    "ɛ is short e",
    "æ is short a",
    "ʌ is short a",
    "ə is short a",
    "ʊ is short u",
    "ɑ is short o",
)
_GEMINATION = ("gemination (after a consonant)", "gemination (word-initial vowel)")
_SPECIFIC_EPENTHESIS = (
    "o after a coronal stop (cluster)",
    "o after a coronal stop (final)",
    "i after an alveolo-palatal affricate (cluster)",
    "i after an alveolo-palatal affricate (final)",
)
_GENERAL_EPENTHESIS = (
    "u elsewhere (cluster)",
    "u elsewhere (final)",
    "u after a final labial nasal",
)
_EPENTHESIS = _SPECIFIC_EPENTHESIS + _GENERAL_EPENTHESIS
_LIAISON = ("liaison (z)", "liaison (t)", "liaison (n)", "liaison (p)")
_LATENT_DELETION = (
    "final z deletion",
    "final t deletion",
    "final n deletion",
    "final p deletion",
)
_SCHWA_DELETION = (
    "final schwa deletion",
    "final schwa deletion (after a cluster)",
    "e caduc (first syllable)",
    "e caduc (interior)",
)

LOAD_BEARING: dict[str, tuple[tuple[tuple[str, ...], tuple[str, ...]], ...]] = {
    ENGLISH: (
        # The syllabic block before the two rules that read what it
        # decides. Only the LATERAL half is here: nothing in this set
        # asks whether a nasal is syllabic -- nasal release is stated
        # over the manner -- so the syllabic nasal rule may stand
        # anywhere, and saying otherwise would be a claim the corpus
        # cannot see.
        (
            ("syllabic lateral",),
            ("tapping (before a syllabic lateral)", "lateral release"),
        ),
        # 'bˈɑtl' is [bˈɑɾl̩]: the tap takes the /t/ before the release
        # rule reaches it.
        (("tapping (before a syllabic lateral)",), ("lateral release",)),
    ),
    SPANISH: (
        # Feeding, and the file does not argue this one -- it is the
        # third ordering in a file whose head says there are two. /z/
        # becomes /s/, and that /s/ is what licenses the trill in
        # 'Israel', which the rhotic block quotes as its own example.
        (("z is s",), ("ɹ is the trill after s",)),
        # ORDERING (1 of 2) in the file: decompose the r-colored vowels,
        # then the one tap rule reaches the rhotic that produced.
        (
            (
                "unstressed r-colored vowel decomposes",
                "stressed r-colored vowel decomposes",
            ),
            ("ɹ is the tap elsewhere",),
        ),
        # ORDERING (2 of 2): specific before general.
        (tuple(sorted(_TRILLS)), ("ɹ is the tap elsewhere",)),
    ),
    JAPANESE: (
        # ORDERING (1 of 6): an English liquid is not a site for
        # epenthesis until it is the tap, because the epenthesis contexts
        # exclude an approximant.
        (("liquids are the tap",), _EPENTHESIS),
        # ORDERING (2 of 6): the alveolo-palatal affricate the /i/
        # epenthesis rules ask for is one these two lines create. The
        # fricative has no reader and is not here.
        (
            (
                "t͡ʃ is the alveolo-palatal affricate",
                "d͡ʒ is the voiced alveolo-palatal affricate",
            ),
            _EPENTHESIS,
        ),
        # ORDERING (3 of 6): the velar stop this puts at the end of the
        # word is what the epenthesis rules then find.
        (("final ŋ takes a velar stop",), _EPENTHESIS),
        # ORDERING (4 of 6): lengthen the tense vowels before anything
        # else spells a short one with the same letter.
        (_LENGTH, _DIPHTHONGS + _SHORT),
        # ORDERING (5 of 6), twice over: gemination tests a length the
        # vowel rules have just created, and it has to take its sites
        # before epenthesis fills them.
        (_LENGTH + _DIPHTHONGS + _SHORT, _GEMINATION),
        (_GEMINATION, _EPENTHESIS),
        # ORDERING (6 of 6), the point of the file: specific before
        # general.
        (_SPECIFIC_EPENTHESIS, _GENERAL_EPENTHESIS),
    ),
    FRENCH: (
        # ORDERING (1 of 2) in the file: license the liaison before the
        # deletion rules take the latent consonant away.
        (_LIAISON, _LATENT_DELETION),
        # ORDERING (2 of 2): the schwa goes last, or 'petit' and
        # 'petite' collapse.
        (_LATENT_DELETION, _SCHWA_DELETION),
    ),
}

#: The sets with more than one rule, so a transposition exists to sweep.
#: The German set is one rule; see the escape pinned in the class below.
ORDERED_SETS = (ENGLISH, SPANISH, JAPANESE, FRENCH)


def _inverts(i: int, j: int, earlier: int, later: int) -> bool:
    """Does transposing the rules at positions ``i < j`` put ``earlier``
    after ``later``?

    Only the two swapped positions move, so the pair inverts when one of
    them is an end of it and the other end lies inside the span.
    """
    return (i == earlier and earlier < later <= j) or (
        j == later and i <= earlier < later
    )


class TestHowMuchOrderingMattersAtAll:
    """The other half of the ordering claim: what is *not* load-bearing.

    A file that says "the rest are independent, which was measured" has to
    have measured it. Adjacent transpositions are the cheap sweep and they
    are also the misleading one -- reported here with the number, because
    the temptation is to conclude from it that order does not matter.

    The two sweeps below are the honest measurement, and they are stated
    against LOAD_BEARING rather than against a count on its own, so a
    failure names rules. Neither carries the ``slow`` marker: what a
    deselected test costs is on the record here, since the English number
    was wrong from the commit that collapsed the nasal assimilation rules
    and nothing ran it to say so.
    """

    @pytest.mark.parametrize(
        "name,swaps_that_matter",
        [(ENGLISH, 1), (SPANISH, 1), (JAPANESE, 0), (FRENCH, 0), (GERMAN, 0)],
    )
    def test_adjacent_transpositions_are_almost_all_harmless(
        self, name, swaps_that_matter
    ):
        rules = _set(name).rules
        words = CORPUS[name]
        assert len(words) >= 15, f"corpus for {name} is only {len(words)} words"
        base = {w: _set(name).apply(w) for w in words}
        mattered = 0
        for i in range(len(rules) - 1):
            swapped = list(rules)
            swapped[i], swapped[i + 1] = swapped[i + 1], swapped[i]
            permuted = R.RuleSet(rules=tuple(swapped))
            if any(permuted.apply(w) != base[w] for w in words):
                mattered += 1
        assert mattered == swaps_that_matter, (
            f"{name}: {mattered} of {len(rules) - 1} adjacent swaps move an output, "
            f"expected {swaps_that_matter}"
        )

    @pytest.mark.parametrize(
        "name,words_that_move",
        [(ENGLISH, 3), (SPANISH, 7), (JAPANESE, 39), (FRENCH, 10), (GERMAN, 0)],
    )
    def test_reversing_the_whole_set_shows_where_the_order_lives(
        self, name, words_that_move
    ):
        """The Spanish set is nearly order-free and the other two are not.
        Worth pinning as a fact about the data: a change that makes the
        Spanish set order-dependent is a change worth noticing."""
        words = CORPUS[name]
        base = {w: _set(name).apply(w) for w in words}
        reversed_set = R.RuleSet(rules=tuple(reversed(_set(name).rules)))
        moved = [w for w in words if reversed_set.apply(w) != base[w]]
        assert (
            len(moved) == words_that_move
        ), f"{name}: reversal moves {len(moved)} of {len(words)}: {moved[:5]}"

    @pytest.mark.parametrize(
        "name,expected", [(ENGLISH, 23), (SPANISH, 75), (JAPANESE, 251), (FRENCH, 35)]
    )
    def test_every_pairwise_transposition_inverts_an_ordering_the_file_argues(
        self, name, expected
    ):
        """The full sweep, and the count is evidence for the claim rather
        than the claim itself.

        What the count on its own says when it moves is that it moved.
        MEASURED, and this is what the shape of the assertion is for: the
        English number was pinned against a set that stated nasal place
        assimilation once per place. Collapsing those two lines into one
        agreement-variable rule (docs/rules.md) took the set from fifteen
        rules to fourteen, and with them the four transpositions that
        crossed either enumerated line with a rule the syllabic block
        feeds -- replaced by two, over the one rule that stands where the
        two stood. Nothing else moved. A bare integer records that as a
        difference of two and names none of it.

        So the claim asserted here is the ordering fact: a transposition
        moves an answer **exactly when** it inverts one of the orderings
        the file argues. Both directions are checked and both name rules
        rather than a number -- a dependency the file does not argue, and
        an ordering the file argues that no permutation can reach.
        """
        rules = _set(name).rules
        words = CORPUS[name]
        assert len(words) >= 15, f"corpus for {name} is only {len(words)} words"
        at = {r.name: i for i, r in enumerate(rules)}
        blocks = LOAD_BEARING[name]
        assert blocks, f"no ordering declared for {name}"

        pairs = list(itertools.combinations(range(len(rules)), 2))
        declared: set[tuple[int, int]] = set()
        for earlier, later in blocks:
            for before in earlier:
                for after in later:
                    assert before in at, f"no rule {before!r} in {name}"
                    assert after in at, f"no rule {after!r} in {name}"
                    assert at[before] < at[after], (
                        f"{name}: {before!r} is declared before {after!r} "
                        "and the file does not run it there"
                    )
                    declared |= {
                        (i, j)
                        for i, j in pairs
                        if _inverts(i, j, at[before], at[after])
                    }

        base = {w: _set(name).apply(w) for w in words}
        checked = 0
        mattered: set[tuple[int, int]] = set()
        for i, j in pairs:
            swapped = list(rules)
            swapped[i], swapped[j] = swapped[j], swapped[i]
            permuted = R.RuleSet(rules=tuple(swapped))
            checked += 1
            if any(permuted.apply(w) != base[w] for w in words):
                mattered.add((i, j))
        assert checked == len(pairs), "sweep did not run"

        def named(swaps):
            return sorted(f"{rules[i].name!r} <-> {rules[j].name!r}" for i, j in swaps)

        assert not mattered - declared, (
            f"{name}: these transpositions move an answer and invert no "
            f"ordering the file argues: {named(mattered - declared)}"
        )
        for earlier, later in blocks:
            lifted = _reordered(
                name,
                set(later),
                [r.name for r in rules if r.name not in later].index(
                    min(earlier, key=lambda n: at[n])
                ),
            )
            assert any(lifted.apply(w) != base[w] for w in words), (
                f"{name}: {earlier[0]!r} before {later[0]!r} is declared "
                "load-bearing and running it the other way moves nothing"
            )
        assert len(mattered) == expected, (
            f"{name}: {len(mattered)} of {checked} transpositions move an "
            f"answer, expected {expected}: {named(mattered)}"
        )

    @pytest.mark.parametrize("name", ORDERED_SETS)
    def test_a_rule_in_no_declared_ordering_may_stand_anywhere(self, name):
        """The other side of the same claim, and the stronger half.

        A transposition moves two rules at once, so it can be accounted
        for by the wrong one of them: swap a rule with a load-bearing
        rule far away and the answer moves either way, whichever of the
        two the dependency belongs to. This lifts ONE rule to every
        position with the rest left alone, which is the move ``_reordered``
        exists for, and a rule the declaration does not name has to
        survive all of them.

        MEASURED, and this is what it caught: the Japanese set's two
        alveolo-palatal AFFRICATE rules make the segment its /i/
        epenthesis asks for, so they feed a block twenty-odd lines below
        and the file did not say so. The sweep above called those
        transpositions explained, because each of them also moves a rule
        that is load-bearing for another reason.

        A set may name every rule it has, and then there is nothing here
        to check for it -- which is a claim about that set, not a gap.
        """
        rules = _set(name).rules
        words = CORPUS[name]
        base = {w: _set(name).apply(w) for w in words}
        named: set[str] = set()
        for earlier, later in LOAD_BEARING[name]:
            named |= {*earlier, *later}
        for rule in (r.name for r in rules if r.name not in named):
            for where in range(len(rules)):
                lifted = _reordered(name, {rule}, where)
                moved = [w for w in words if lifted.apply(w) != base[w]]
                assert not moved, (
                    f"{name}: {rule!r} is in no declared ordering and moving "
                    f"it to position {where} moves {moved[:3]}"
                )

    def test_the_german_set_has_no_ordering_to_have(self):
        """The escape the sweep above cannot cover, pinned so it stays
        known rather than assumed shut.

        One rule is no pairs, and ``0 of 0`` is not a measurement. If this
        set ever gains a second rule it belongs in ORDERED_SETS with the
        orderings it then has, and this fails to say so.
        """
        assert len(_set(GERMAN).rules) == 1
        assert GERMAN not in ORDERED_SETS
        assert set(LOAD_BEARING) == set(ORDERED_SETS)


# --------------------------------------------------------------------------
# Properties over the whole corpus
# --------------------------------------------------------------------------


class TestOptionalNotationDoesNotChangeWhatTheseSetsDo:
    """The dot is spelling, not structure -- swept over these sets.

    tests/test_rules.py sweeps this for single rules. It is repeated here
    because these are the first shipped sets containing insertions, and an
    insertion is the rule kind that got it wrong: a gap-anchored rule sees
    two gaps around a transparent boundary and inserted twice where the
    undotted spelling inserted once.
    """

    @pytest.mark.parametrize(
        "name,expected,anchor_limit",
        [(SPANISH, 99, 0), (JAPANESE, 104, 0), (FRENCH, 143, 0)],
    )
    def test_a_dot_at_any_position_changes_nothing(self, name, expected, anchor_limit):
        """One exclusion, and it is a predicate rather than a list.

        A dot that lands beside a boundary an insertion's context names
        costs that insertion its anchor -- a known engine limit, pinned
        below in
        test_a_dot_after_the_linking_mark_loses_the_liaison_it_licensed.
        Rather than skip named words, ask the set's *insertion* rules
        alone: where they already disagree the dot never reached the
        deletion rules at all, so counting that against them measures the
        wrong thing. ``anchor_limit`` is how often that happens, asserted
        exactly, so the exclusion cannot quietly grow -- and it is 0 for
        the two sets whose corpora carry no boundary for a dot to sit
        beside, which is what keeps the same code honest for all three.
        """
        rule_set = _set(name)
        inserting = R.RuleSet(rules=tuple(r for r in rule_set if r.inserts))
        assert inserting.rules, f"{name} ships no insertion, so the excuse is idle"
        words = CORPUS[name]
        checked = 0
        bad: list[str] = []
        excused: list[str] = []
        for word in words:
            base = rule_set.apply(word)
            copied = inserting.apply(word)
            for cut in _cut_positions(word):
                dotted = word[:cut] + "." + word[cut:]
                assert R.spell(R.units(dotted, FEATURES)) == dotted, dotted
                got = rule_set.apply(dotted).replace(".", "")
                checked += 1
                if inserting.apply(dotted).replace(".", "") != copied:
                    excused.append(f"{word} vs {dotted}")
                    continue
                if got != base:
                    bad.append(f"{word}->{base} vs {dotted}->{got}")
        # Exact, not a floor: a floor cannot tell that a word dropped out of
        # the sweep because a cut landed inside a multi-codepoint unit.
        assert checked == expected, f"{name}: sweep covered {checked}, not {expected}"
        assert (
            len(excused) == anchor_limit
        ), f"{name}: {len(excused)} excused, expected {anchor_limit}: {excused[:3]}"
        assert bad == [], f"{name}: {len(bad)} violations, first: {bad[:3]}"

    def test_a_dot_after_the_linking_mark_keeps_the_liaison_it_licensed(self):
        """The limit this pinned has been closed in the engine.

        Written as a pin on a known limit: '‿.' is a boundary RUN, a run
        offers one gap so a redundant mark cannot change a derivation, and
        the gap *after* a run counted as that one only when the left context
        matched the run's LAST mark. A liaison rule names '‿', which a
        following dot displaces from last position, so the site vanished and
        seven forms derived differently with the dot than without it. No
        spelling of the rules avoided it, because the position the copy must
        land in was the one that stopped counting.

        `_anchors` now licenses the trailing gap on ANY mark the context
        matched, not only the run's last, so the pin fires and this states
        the invariant instead. The exclusion it told us to remove from
        test_a_dot_at_any_position_changes_nothing is gone with it.

        Kept rather than deleted, because the failure shape is subtle and
        the corpus predicate is what would catch it coming back.
        """
        french = _set(FRENCH)
        licensed = 0
        for word in CORPUS[FRENCH]:
            base = french.apply(word)
            for cut in _cut_positions(word):
                dotted = word[:cut] + "." + word[cut:]
                assert (
                    french.apply(dotted).replace(".", "") == base
                ), f"{word!r} at cut {cut}: {french.apply(dotted)!r} != {base!r}"
                if cut and word[cut - 1] == "\u203f":
                    licensed += 1
        # 11 dot-after-link positions in the corpus, of which 7 used to
        # lose their liaison. Asserting the positions swept, not the old
        # failure count -- conflating the two is what this line first did.
        assert licensed == 11, f"{licensed} dot-after-link positions swept, want 11"

    @pytest.mark.parametrize("name", ALL_SETS)
    def test_a_form_no_rule_reaches_spells_back_out_byte_identical(self, name):
        """Including its boundaries, which segments() would drop."""
        for form in ("#pa.pa#", "ka‿ka", "aːa"):
            got = _set(name).apply(form)
            assert R.spell(R.units(got, FEATURES)) == got, form

    @pytest.mark.parametrize("name", ALL_SETS)
    def test_every_derivation_re_spells_itself(self, name):
        """A rule set may not produce a string the tokenizer reads back
        differently -- that is a silent corruption, not a wrong rule."""
        checked = 0
        for word in CORPUS[name]:
            got = _set(name).apply(word)
            assert R.spell(R.units(got, FEATURES)) == got, f"{word} -> {got}"
            checked += 1
        assert checked == len(CORPUS[name]) and checked >= 15, "sweep did not run"

    @pytest.mark.parametrize("name", ALL_SETS)
    def test_every_rule_in_the_set_fires_on_the_corpus(self, name):
        """A rule that never fires is either dead or the corpus is too thin.

        Both are worth knowing, and neither shows up as a failure anywhere
        else. Any exceptions are listed, so the list is the claim.

        Asked of every derivation the set LICENSES, not only of the one
        ``derive`` settles on. An optional rule ('~>') never fires under
        ``derive`` -- one form comes out, so no optional choice is taken
        -- so the narrower reading declared every optional rule dead the
        moment one shipped, which is a wrong answer about a working rule.
        For a set with no optional rule this is the same question: the
        first variant's derivation *is* ``derive``'s.
        """
        fired: set[str] = set()
        for word in CORPUS[name]:
            for variant in _set(name).variants(word, FEATURES):
                fired.update(step.rule for step in variant.derivation.fired)
        idle = sorted({r.name for r in _set(name)} - fired)
        assert idle == [], f"{name}: {len(idle)} rules never fire: {idle}"


class TestTheTrapsTheFilesRecord:
    """Each file names a spelling that looks right and fails silently.

    Pinned here so the warnings stay true. If one of these starts working,
    the file's advice is wrong and needs rewriting -- which is the point.
    """

    def test_a_plain_vowel_carries_no_length_so_length_normal_matches_nothing(self):
        """Why gemination is conditioned on '[vowel -long]'.

        'normal' is the declared default for the feature, but the default
        is not written onto the unit, so the positive spelling matches no
        vowel at all -- and a rule that matches nothing is silent.
        """
        assert FEATURES.features["length"].default == "normal", "premise moved"
        positive = R._pattern("[vowel length=normal]", FEATURES)
        negative = R._pattern("[vowel -long]", FEATURES)
        short, long = R.units("a aː", FEATURES)[0], R.units("aː", FEATURES)[0]
        assert not positive.matches(short, FEATURES), "length=normal now works"
        assert not positive.matches(long, FEATURES)
        assert negative.matches(short, FEATURES)
        assert not negative.matches(long, FEATURES)

    def test_prosody_is_writable_so_gemination_need_not_be_per_phone(self):
        """The limit eight lines of the Japanese file paid for has been lifted.

        And has since been taken up: gemination is two rules over a class,
        one per context, where it was eight literals over one context.

        Written as a pin on "prosody is not writable": respell and
        compose_unit both answer None for a purely prosodic change, so
        gemination had to be spelled one literal line per phone. A sibling
        lane made prosody writable by rewriting Segment.prosody in feature
        space rather than going through either of those, and this pin fired
        -- which is what a pin is for. Both facts still hold and are worth
        keeping: the composers still decline, and the rule now works
        anyway, which is exactly the seam that was added.
        """
        assert FEATURES.respell("t", length="long") is None
        assert FEATURES.compose_unit("t", length="long") is None
        # The feature change now reaches the prosody writer instead.
        assert ipakit.rewrite("hot", "t -> [length=long] / [vowel] _ #") == "hotː"
        assert ipakit.rewrite("hot", "t -> tː / [vowel] _ #") == "hotː"
        # So the eight literal lines became one rule over a class, twice.
        assert (
            ipakit.rewrite("hot", "[manner=plosive] -> [length=long] / [vowel] _ #")
            == "hotː"
        )
        geminating = [r for r in _set(JAPANESE) if r.name.startswith("gemination")]
        assert len(geminating) == 2, [r.name for r in geminating]
        assert all(r.becomes == {"length": "long"} for r in geminating), geminating

    def test_add_ties_on_a_word_ties_every_adjacent_pair(self):
        """Why the Japanese file says to tie diphthongs by hand.

        add_ties is documented for a multi-phone *segment* and behaves that
        way; applied to a word it produces one tied chain, and then a rule
        conditioned on a following vowel no longer sees one.
        """
        assert ipakit.add_ties("kæt") == "k͡æ͡t"
        assert ipakit.add_ties("stɹaɪk") == "s͡t͡ɹ͡a͜ɪ͡k"
        assert ipakit.add_ties("aɪ") == "a͜ɪ", "a bare diphthong is fine"
        english = R.shipped("american-english", FEATURES)
        assert english.apply("pə.tˈe͜ɪ.to͜ʊ") == "pə.tʰˈe͜ɪ.ɾo͜ʊ"
        assert english.apply(ipakit.add_ties("pə.tˈeɪ.toʊ")) == "p͡ə.tʰˈe͜ɪ.t͡o͜ʊ"

    def test_the_wide_spelling_of_the_prothesis_context_over_applies(self):
        """'[-vowel]' would repair /sw/ and /sj/, which need no repair."""
        wide = "∅ -> e / # _ s [-vowel]"
        narrow = "∅ -> e / # _ s [-vowel -approximant]"
        assert ipakit.rewrite("swit", wide) == "eswit", "premise moved"
        assert ipakit.rewrite("swit", narrow) == "swit"
        assert ipakit.rewrite("stap", narrow) == "estap"

    def test_the_wide_spelling_of_the_epenthesis_context_over_applies_too(self):
        """'[-vowel]' on the right inserted before a glide: *[kujuːto]."""
        wide = "∅ -> u / [-vowel -nasal] _ [-vowel]"
        narrow = "∅ -> u / [-vowel -nasal] _ [-vowel -approximant]"
        assert ipakit.rewrite("kjuːto", wide) == "kujuːto", "premise moved"
        assert ipakit.rewrite("kjuːto", narrow) == "kjuːto"
        assert ipakit.rewrite("miɾku", narrow) == "miɾuku"
