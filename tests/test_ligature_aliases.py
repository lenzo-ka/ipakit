"""A ligature alias reads exactly as the spelling it aliases, everywhere.

``ʧ``, ``ʦ``, ``ƛ``, ``˖`` and the rest are input spellings this package
documents as accepted: ``to_ipa``'s own docstring reads ``to_ipa(segments("ʧa"))``
as ``'t͡ʃa'``. They were resolved in :meth:`IPAFeatures.tokenize`, which meant
every *other* route into the inventory missed them -- ``compose_segments`` and
``_reject_unconvertible`` call :meth:`~IPAFeatures.parse` directly, and the CMU,
TIMIT, Kirshenbaum and X-SAMPA converters do not go through ``parse`` at all.
An alias reaching any of those matched nothing, counted as a character
registered nowhere, and was dropped: ``to_cmu("ʧe͜ɪnd͡ʒ")`` returned
``['EY0', 'N', 'JH']`` -- the same word, one phoneme shorter, and well formed
enough to pass for an answer. ``parse("ʦʰ", strict=True)`` raised while
``segments("ʦʰ", strict=True)`` succeeded on the same string.

The lane-by-lane tests below are the symptoms. The deliverable is
:class:`TestEveryEntryPointReadsAnAliasAsItsCanonical`: an alias and its
canonical are one string to every entry point, over every alias, every
diacritic on it, and the positions a unit can occupy. A future entry point
that reaches the inventory by a fourth route fails there rather than
returning a plausible short answer.
"""

from __future__ import annotations

import functools
import warnings
from collections.abc import Callable, Iterator

import ipakit
import pytest
from ipakit import IPAFeatures

# The seven that stand for a phone; ˖/˗ are spacing aliases of combining
# marks and are covered by the sweep and by TestTheSpacingAliases.
CONSONANT_ALIASES = ["ʦ", "ʣ", "ʧ", "ʤ", "ʨ", "ʥ", "ƛ"]
SPACING_ALIASES = ["˖", "˗"]
ALL_ALIASES = CONSONANT_ALIASES + SPACING_ALIASES


def _corpus(ipa: IPAFeatures) -> Iterator[tuple[str, str]]:
    """(alias spelling, canonical spelling) over the positions a unit takes.

    Every diacritic goes on every alias because that family is where the
    breach outlived the fix to ``tokenize``: ``ʦ`` alone resolved through
    the whole-token lookup, ``ʦʰ`` did not.
    """
    for alias in ipa.ligature_map:
        for text in (
            alias,
            *(alias + mark for mark in ipa.diacritics),
            "k͡" + alias,  # inside a tie chain
            alias + "a",
            "a" + alias,
            "ˈ" + alias + "a",
        ):
            yield text, ipa.expand_ligatures(text)


@pytest.fixture(scope="module")
def corpus(ipa: IPAFeatures) -> list[tuple[str, str]]:
    return list(_corpus(ipa))


def _answer(fn: Callable[[str], object], text: str) -> object:
    """What an entry point says, raising counted as an answer.

    Only the exception *type* is compared: a message that names the
    caller's own input differs between the two spellings by design.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            return fn(text)
        except Exception as exc:  # noqa: BLE001 - the type is the answer
            return type(exc).__name__


ENTRY_POINTS: dict[str, Callable[[str], object]] = {
    "features": ipakit.features,
    "compose": lambda s: IPAFeatures().compose(s),
    "scalar": lambda s: ipakit.segment(s).scalar(),
    "feature_values": ipakit.feature_values,
    "feature_bundles": ipakit.feature_bundles,
    "describe": lambda s: ipakit.describe(s) if s in IPAFeatures() else None,
    "tokenize": ipakit.tokenize,
    "segmented": ipakit.segmented,
    "segments": lambda s: [u.to_ipa() for u in ipakit.segments(s)],
    "segments_strict": lambda s: [u.to_ipa() for u in ipakit.segments(s, strict=True)],
    "parse": lambda s: IPAFeatures().parse(s),
    "parse_strict": lambda s: IPAFeatures().parse(s, strict=True),
    "normalize": ipakit.normalize,
    "respell": ipakit.respell,
    "is_valid_ipa": ipakit.is_valid_ipa,
    "validate_ipa": ipakit.validate_ipa,
    "to_cmu": ipakit.to_cmu,
    "to_timit": ipakit.to_timit,
    "to_kirshenbaum": ipakit.to_kirshenbaum,
    "ipa_to_xsampa": ipakit.ipa_to_xsampa,
    "word_distance": lambda s: ipakit.word_distance(s, "ta").distance,
    "distance": lambda s: ipakit.distance(s, "t"),
    "contains": lambda s: s in IPAFeatures(),
    "get_phone": lambda s: IPAFeatures().get_phone(s),
    "get_diacritic": lambda s: IPAFeatures().get_diacritic(s),
}


class TestEveryEntryPointReadsAnAliasAsItsCanonical:
    """The equivalence sweep: one string, one answer, whichever way in."""

    def test_the_sweep_is_wide(self, corpus: list[tuple[str, str]]) -> None:
        assert len(corpus) > 500
        assert {alias for alias, _ in corpus if len(alias) == 1} == set(ALL_ALIASES)

    @pytest.mark.parametrize("entry", sorted(ENTRY_POINTS))
    def test_it_agrees_with_the_canonical_spelling(
        self, entry: str, corpus: list[tuple[str, str]]
    ) -> None:
        fn = ENTRY_POINTS[entry]
        disagreements = [
            (alias, canonical, _answer(fn, alias), _answer(fn, canonical))
            for alias, canonical in corpus
            if _answer(fn, alias) != _answer(fn, canonical)
        ]
        assert not disagreements[:5], (
            f"{entry} reads {len(disagreements)} alias spellings "
            f"differently from their canonical form"
        )

    def test_an_alias_never_warns_where_its_canonical_does_not(
        self, corpus: list[tuple[str, str]]
    ) -> None:
        """The drop was audible in principle and inaudible in practice.

        Every route warned when it lost the alias, but the warning went to
        a stream nobody reads while the return value stayed plausible. A
        spelling the package accepts must produce no warning at all.
        """
        noisy = []
        for alias, canonical in corpus:
            for name, fn in ENTRY_POINTS.items():
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    _answer(fn, canonical)
                    if caught:
                        continue  # the canonical is malformed too; not our case
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    _answer(fn, alias)
                if caught:
                    noisy.append((name, alias, str(caught[0].message)[:60]))
        assert not noisy[:5]


class TestTheConverterLanes:
    """The lanes that never call ``parse`` and so never saw the alias."""

    @pytest.mark.parametrize("alias", CONSONANT_ALIASES)
    def test_to_cmu(self, ipa: IPAFeatures, alias: str) -> None:
        canonical = ipa.ligature_map[alias]
        assert ipakit.to_cmu(alias) == ipakit.to_cmu(canonical) != []

    @pytest.mark.parametrize("alias", CONSONANT_ALIASES)
    def test_to_timit(self, ipa: IPAFeatures, alias: str) -> None:
        canonical = ipa.ligature_map[alias]
        assert ipakit.to_timit(alias) == ipakit.to_timit(canonical) != []

    @pytest.mark.parametrize("alias", CONSONANT_ALIASES)
    def test_to_kirshenbaum(self, ipa: IPAFeatures, alias: str) -> None:
        canonical = ipa.ligature_map[alias]
        assert ipakit.to_kirshenbaum(alias) == ipakit.to_kirshenbaum(canonical) != ""

    @pytest.mark.parametrize("alias", CONSONANT_ALIASES)
    def test_ipa_to_xsampa(self, ipa: IPAFeatures, alias: str) -> None:
        canonical = ipa.ligature_map[alias]
        assert ipakit.ipa_to_xsampa(alias) == ipakit.ipa_to_xsampa(canonical) != ""

    @pytest.mark.parametrize("alias", CONSONANT_ALIASES)
    def test_word_distance_reads_the_two_spellings_as_one_word(
        self, ipa: IPAFeatures, alias: str
    ) -> None:
        canonical = ipa.ligature_map[alias]
        assert ipakit.word_distance(f"a{alias}a", f"a{canonical}a").distance == 0.0

    def test_the_word_that_lost_its_affricate(self) -> None:
        # to_cmu("ʧe͜ɪnd͡ʒ") returned ['EY0', 'N', 'JH']: no error, no CH.
        assert ipakit.to_cmu("ʧe͜ɪnd͡ʒ") == ipakit.to_cmu("t͡ʃe͜ɪnd͡ʒ")
        assert ipakit.to_cmu("ʧe͜ɪnd͡ʒ") == ["CH", "EY0", "N", "JH"]
        assert ipakit.word_distance("ʧe͜ɪnd͡ʒ", "t͡ʃe͜ɪnd͡ʒ").distance == 0.0


class TestAnAliasCarryingDiacritics:
    """``ʦ`` resolved through a whole-token lookup; ``ʦʰ`` did not."""

    @pytest.mark.parametrize("alias", CONSONANT_ALIASES)
    @pytest.mark.parametrize("mark", ["ʰ", "ʲ", "ʷ", "̥", "̪", "ː"])
    def test_the_flat_reads_agree_with_the_structured_one(
        self, ipa: IPAFeatures, alias: str, mark: str
    ) -> None:
        unit = alias + mark
        scalar = ipa.segment(unit).scalar()
        assert scalar
        assert ipakit.features(unit) == scalar or unit.endswith("ː")
        assert ipa.compose(unit)[0] == ipa.compose(ipa.expand_ligatures(unit))[0]

    def test_it_is_not_read_as_an_unknown_phone(self, ipa: IPAFeatures) -> None:
        assert ipakit.features("ʦʰ")["manner"] == "affricate"
        assert ipakit.features("ʦʰ")["release"] == "aspirated"
        assert ipakit.describe("ʦʰ") == ipakit.describe("t͡sʰ")
        assert ipakit.ipa_to_xsampa("ʦʰ") == "t_s_h"


class TestAnAliasInsideATieChain:
    """The drop yielded a plausible bundle here, not an empty one.

    ``feature_bundles("k͡ƛʰ")`` returned the ``k`` constituent alone, the
    ``ƛʰ`` silently gone -- a well-formed answer about a different unit.
    """

    def test_the_chain_keeps_its_second_constituent(self, ipa: IPAFeatures) -> None:
        assert ipa.tokenize("k͡ƛʰ") == ["k͡t͡ɬʰ"]
        assert ipakit.feature_bundles("k͡ƛʰ") == ipakit.feature_bundles("k͡t͡ɬʰ")
        assert len(ipa.segment("k͡ƛʰ").constituents) == 3

    @pytest.mark.parametrize("alias", CONSONANT_ALIASES)
    @pytest.mark.parametrize("tie", ["͡", "͜"])
    def test_a_chain_is_the_same_chain_either_spelling(
        self, ipa: IPAFeatures, alias: str, tie: str
    ) -> None:
        canonical = ipa.ligature_map[alias]
        assert ipa.tokenize(f"k{tie}{alias}") == ipa.tokenize(f"k{tie}{canonical}")
        assert ipakit.feature_bundles(f"k{tie}{alias}") == ipakit.feature_bundles(
            f"k{tie}{canonical}"
        )


class TestTheSpacingAliases:
    """``˖``/``˗`` alias combining marks, so they read on the base before."""

    @pytest.mark.parametrize("alias", SPACING_ALIASES)
    def test_it_modifies_the_preceding_base(self, ipa: IPAFeatures, alias: str) -> None:
        mark = ipa.ligature_map[alias]
        assert ipa.tokenize("a" + alias) == ipa.tokenize("a" + mark) == ["a" + mark]
        assert ipakit.features("a" + alias) == ipakit.features("a" + mark)

    @pytest.mark.parametrize("alias", SPACING_ALIASES)
    def test_the_inventory_knows_it_by_either_spelling(
        self, ipa: IPAFeatures, alias: str
    ) -> None:
        assert ipa.get_diacritic(alias) is ipa.get_diacritic(ipa.ligature_map[alias])


class TestStrictAgreesWithItself:
    """``parse(strict=True)`` raised where ``segments(strict=True)`` did not."""

    @pytest.mark.parametrize("alias", ALL_ALIASES)
    def test_no_strict_route_rejects_an_accepted_spelling(
        self, ipa: IPAFeatures, alias: str
    ) -> None:
        text = "a" + alias + "a"
        assert ipa.parse(text, strict=True) == ipa.parse(
            ipa.expand_ligatures(text), strict=True
        )
        assert ipa.tokenize(text, strict=True) == ipa.tokenize(
            ipa.expand_ligatures(text), strict=True
        )
        assert [u.to_ipa() for u in ipa.segments(text, strict=True)] == [
            u.to_ipa() for u in ipa.segments(ipa.expand_ligatures(text), strict=True)
        ]
        assert ipakit.word_distance(text, text, strict=True).distance == 0.0

    @pytest.mark.parametrize("alias", CONSONANT_ALIASES)
    def test_the_converters_reject_neither_more_nor_less(
        self, ipa: IPAFeatures, alias: str
    ) -> None:
        """Not "the alias converts" -- some of these have no ARPABET
        symbol and neither spelling converts -- but "the alias is judged
        on what it spells", so the two verdicts are the same verdict."""
        canonical = ipa.ligature_map[alias]
        for convert in (
            ipakit.to_cmu,
            ipakit.to_timit,
            ipakit.to_kirshenbaum,
            ipakit.ipa_to_xsampa,
        ):
            strictly = functools.partial(convert, strict=True)
            assert _answer(strictly, alias) == _answer(strictly, canonical)
        assert ipakit.ipa_to_xsampa(alias, strict=True) == ipakit.ipa_to_xsampa(
            canonical, strict=True
        )


class TestAGenuinelyUnknownSymbolIsUnchanged:
    """Resolving aliases must not soften the report on anything else."""

    @pytest.mark.parametrize("text", ["aQb", "a%b", "ag", "a:b", "a?b", "a'b"])
    def test_it_still_warns_by_default(self, ipa: IPAFeatures, text: str) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            ipa.tokenize(text)
        assert caught and "unregistered symbol" in str(caught[0].message)

    @pytest.mark.parametrize("text", ["aQb", "a%b", "ag", "a:b", "a?b", "a'b"])
    def test_it_still_raises_under_strict(self, ipa: IPAFeatures, text: str) -> None:
        with pytest.raises(ValueError, match="unknown symbols"):
            ipa.parse(text, strict=True)
        with pytest.raises(ValueError, match="unknown symbols"):
            ipa.tokenize(text, strict=True)
        with pytest.raises(ValueError, match="unknown symbols"):
            ipakit.word_distance(text, "ta")

    def test_an_unbound_tie_is_still_reported(self, ipa: IPAFeatures) -> None:
        with pytest.raises(ValueError, match="malformed tie"):
            ipa.parse("ʧ͡", strict=True)


class TestResolutionHappensInOnePlace:
    """The structural guard: one function, reachable from every route."""

    def test_parse_resolves_without_help_from_its_callers(
        self, ipa: IPAFeatures
    ) -> None:
        # tokenize used to expand first; parse's other callers did not.
        assert ipa.parse("ʧa") == ipa.parse("t͡ʃa") == [("t͡ʃ", []), ("a", [])]

    def test_resolve_token_is_expand_ligatures(self, ipa: IPAFeatures) -> None:
        for alias in ipa.ligature_map:
            for text in (alias, alias + "ʰ", "a" + alias):
                assert ipa._resolve_token(text) == ipa.expand_ligatures(text)

    def test_the_converters_share_that_one_resolution(self, ipa: IPAFeatures) -> None:
        from ipakit._convert import resolve_aliases

        for alias, canonical in ipa.ligature_map.items():
            assert resolve_aliases(alias) == ipa.expand_ligatures(alias)
            assert resolve_aliases(alias) == ipa.canonicalize_unicode(canonical)

    def test_expanding_twice_changes_nothing(self, ipa: IPAFeatures) -> None:
        for text, _ in _corpus(ipa):
            once = ipa.expand_ligatures(text)
            assert ipa.expand_ligatures(once) == once
