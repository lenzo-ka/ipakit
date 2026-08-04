"""ipakit - IPA phonetic features library.

Simple API:
    import ipakit as ipa

    ipa.distance("p", "b")              # a voicing difference
    ipa.features("p")                   # {'manner': 'plosive', ...}
    ipa.to_cmu("ˈhɛlo͜ʊ")               # ['HH', 'EH1', 'L', 'OW0']
    ipa.to_ipa(ipa.segments("hɛl"))     # 'hɛl'
    ipa.tokenize("t͡ʃe͜ɪnd͡ʒ")          # ['t͡ʃ', 'e͜ɪ', 'n', 'd͡ʒ']
    ipa.normalize("tʃ eɪ n dʒ")         # 't͡ʃe͜ɪnd͡ʒ'

Class API:
    from ipakit import IPAFeatures, CMUMapper

Converter return types follow the target format: converters to a token-oriented
phone set (``to_cmu``, ``to_timit``) return ``list[str]``, while converters to a
transcription string (``ipa_to_xsampa``, ``to_kirshenbaum``) return ``str``.
"""

from __future__ import annotations

import functools
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

__version__ = "0.1.0"

# Re-export classes
# ``tract_svg`` is imported here so ``import ipakit`` is enough to draw: the
# tract figure is the classroom's headline output and a student should not
# have to learn a second module name to get one. It reads ``ipakit.tract``
# and ``ipakit.features`` and nothing else in the package, so the dependency
# runs one way and the model stays free of the renderer.
from . import rules, tract_svg

# The tutorial notebook is carried in the package and copied out on
# request, so `pip install ipakit` is the whole of getting the teaching
# material too -- see ipakit._notebook.
from ._notebook import notebook
from .constants import (
    DATA_DIR,
    DEFAULT_CMU_MAP,
    DEFAULT_IPA_FEATS,
    PHONEMAPS_DIR,
    SUPPLEMENTS_DIR,
)
from .distance import (
    CostSchedule,
    PhoneCost,
    PronunciationMatch,
    ScoringParameters,
    SequenceMatch,
    WordDistanceResult,
)
from .distance_model import DistanceModel
from .features import IPAFeatures, _Query, available_supplements, supplement_path
from .form import (
    Attribute,
    Boundary,
    Form,
    Interval,
    Node,
    Unit,
    levels,
    tier_names,
    units,
)
from .mapper import CMUMapper
from .models import Feature, Phone, PhoneMapping, Phoneset
from .phonemaps import (
    from_kirshenbaum,
    from_timit,
    ipa_to_phonemap,
    phonemap_to_ipa,
    to_kirshenbaum,
    to_timit,
)
from .rules import (
    DEFAULT_LIMIT,
    Action,
    Derivation,
    Edit,
    Matchable,
    Query,
    RebaseError,
    Rule,
    RuleError,
    RuleSet,
    Site,
    Step,
    Truncation,
    Variant,
    VariantSet,
    available,
    rebase,
    shipped,
)
from .segment import Constituent, Kind, Segment, Sense

# X-SAMPA string conversion lives in ipakit.xsampa, the single source of truth
# for the IPA <-> X-SAMPA table. Re-exported here for the flat module API.
from .xsampa import ipa_to_xsampa, xsampa_to_ipa

# ======================================================================
# Module-level API (lazy singletons)
# ======================================================================


@functools.lru_cache(maxsize=1)
def _get_ipa() -> IPAFeatures:
    return IPAFeatures()


@functools.lru_cache(maxsize=1)
def _get_cmu() -> CMUMapper:
    return CMUMapper()


@functools.lru_cache(maxsize=1)
def _get_default_model() -> DistanceModel:
    return DistanceModel.global_(_get_ipa())


def load_ipa_features(
    xml_path: Path = DEFAULT_IPA_FEATS,
    supplements: Sequence[Path | str] = (),
) -> IPAFeatures:
    """Convenience function to load IPA features.

    ``supplements`` are extra inventory files merged over ``xml_path``,
    each adding symbols and declaring nothing else (docs/supplements.md).
    A member is a path to a file of yours, or the bare name of one the
    package ships -- ``supplements=["aspirated-stops"]`` loads the worked
    example, and :func:`available_supplements` says what else answers.

    The instance they build is the caller's own: the module-level
    functions, the shipped distance matrix and every derived artifact in
    this package are built from the bare inventory and do not see it.
    """
    return IPAFeatures(xml_path, supplements=supplements)


# --- Distance & Features ---


def distance(phone1: str, phone2: str) -> float:
    """Compute phonetic distance between two IPA phones (0.0-1.0)."""
    return _get_ipa().distance(phone1, phone2)


def segment_distance(seg1: str, seg2: str) -> float:
    """Structural distance between two segment strings (0.0-1.0).

    Unlike :func:`distance`, accepts multi-unit strings: units are
    compared positionally with a length penalty.

    Examples:
        >>> 0.0 < segment_distance("t͡s", "t͡ʃ") < 1.0
        True
    """
    return _get_ipa().segment_distance(seg1, seg2)


def pairwise_distances(phones: list[str]) -> list[list[float]]:
    """Full distance matrix over a list of phones.

    Examples:
        >>> m = pairwise_distances(["p", "b", "t"])
        >>> m[0][0], m[0][1] == m[1][0]
        (0.0, True)
    """
    return _get_ipa().pairwise_distances(phones)


def word_distance(
    ipa1: str,
    ipa2: str,
    weighted: bool = True,
    return_alignment: bool = False,
    strict: bool = True,
) -> WordDistanceResult:
    """Compute phonetic edit distance between two IPA words.

    Uses Levenshtein-style dynamic programming with phonetic feature costs.

    Args:
        ipa1: First IPA string
        ipa2: Second IPA string
        weighted: If True, use feature distance for substitution costs.
        return_alignment: If True, include the alignment path in result.

    Returns:
        WordDistanceResult with the summed edit cost, the normalized
        similarity, the length coverage, and an optional alignment.

    Examples:
        >>> ipakit.word_distance("kæt", "kæd")
        WordDistanceResult(edit_cost=0.1, similarity=0.98..., coverage=1.0, costs='insert=1.0 delete=1.0', alignment=None)
        >>> ipakit.word_distance("kæt", "kæ").coverage
        0.666...
    """
    return _get_ipa().word_distance(
        ipa1,
        ipa2,
        weighted=weighted,
        return_alignment=return_alignment,
        strict=strict,
    )


def directional_word_distance(
    reference: str,
    hypothesis: str,
    *,
    insert_cost: PhoneCost | None = None,
    delete_cost: PhoneCost | None = None,
    weighted: bool = True,
    return_alignment: bool = False,
    strict: bool = True,
) -> WordDistanceResult:
    """Edit distance from a reference form to a hypothesis, sides named.

    ``delete_cost`` prices the phones of ``reference`` -- what went missing
    -- and ``insert_cost`` the phones of ``hypothesis`` -- what was
    supplied. Give either one a :class:`CostSchedule` and the score stops
    being symmetric, which is the point: a reference and a hypothesis are
    not interchangeable. See
    :meth:`IPAFeatures.directional_word_distance`.

    Examples:
        >>> drop = ipakit.CostSchedule("example/schwa-drops", {"ə": 0.25}, 1.0)
        >>> r = ipakit.directional_word_distance("kætə", "kæt", delete_cost=drop)
        >>> r.costs
        'insert=1.0 delete=example/schwa-drops'
        >>> r.edit_cost < ipakit.word_distance("kætə", "kæt").edit_cost
        True
    """
    return _get_ipa().directional_word_distance(
        reference,
        hypothesis,
        insert_cost=insert_cost,
        delete_cost=delete_cost,
        weighted=weighted,
        return_alignment=return_alignment,
        strict=strict,
    )


def word_similarity(
    ipa1: str, ipa2: str, weighted: bool = True, strict: bool = True
) -> float:
    """Compute phonetic similarity between two IPA words.

    Returns a value from 0.0 (completely different) to 1.0 (identical):
    the alignment cost against the cost of the null alignment, which
    deletes every token of one word and inserts every token of the other.

    Args:
        ipa1: First IPA string
        ipa2: Second IPA string
        weighted: If True, use feature distance for substitution costs.

    Examples:
        >>> ipakit.word_similarity("kæt", "kæd")
        0.98...
        >>> ipakit.word_similarity("kæt", "dɒɡ")  # weighted subs are cheap (shared features)
        0.8...
    """
    return _get_ipa().word_similarity(ipa1, ipa2, weighted=weighted, strict=strict)


def nearest_pronunciation(
    forms: str | Iterable[str],
    acceptable: str | Iterable[str],
    weighted: bool = True,
    strict: bool = True,
    *,
    mode: str = "global",
) -> PronunciationMatch:
    """The nearest acceptable pronunciation in a set, and which pair matched.

    For "is this an acceptable pronunciation of the word?" -- the best match
    over a set of variants a lexicon lists. Every real lexicon has them:
    CMUdict lists several pronunciations per entry, and a homograph reads two
    ways. Not for word-to-word distance, where a maximum over variants would
    depend on how many each side lists; see
    :class:`~ipakit.distance.PronunciationMatch`.

    Examples:
        >>> # "family" with and without the optional medial schwa
        >>> m = ipakit.nearest_pronunciation("fæmli", ["fæməli", "fæmli"])
        >>> m.accepted, round(m.similarity, 2)
        ('fæmli', 1.0)
    """
    return _get_ipa().nearest_pronunciation(
        forms, acceptable, weighted=weighted, strict=strict, mode=mode
    )


def rank_pronunciations(
    forms: str | Iterable[str],
    acceptable: str | Iterable[str],
    *,
    n: int | None = None,
    weighted: bool = True,
    strict: bool = True,
    mode: str = "global",
) -> list[PronunciationMatch]:
    """The acceptable pronunciations ranked, best first -- the n-best form of
    :func:`nearest_pronunciation`. ``mode="local"`` matches each as a target
    embedded in the form.

    Examples:
        >>> ms = ipakit.rank_pronunciations("fæmli", ["fæmɪli", "fæməli", "fæmli"])
        >>> [round(m.similarity, 2) for m in ms][:1]
        [1.0]
    """
    return _get_ipa().rank_pronunciations(
        forms, acceptable, n=n, weighted=weighted, strict=strict, mode=mode
    )


def sequence_distance(
    seq1: Sequence[str],
    seq2: Sequence[str],
    *,
    weighted: bool = True,
    mode: str = "global",
    return_alignment: bool = False,
) -> WordDistanceResult:
    """Distance between two pre-tokenized phone sequences (each element one
    phone unit), aligned as given -- see
    :meth:`~ipakit.distance.DistanceMixin.sequence_distance`.

    Examples:
        >>> ipakit.sequence_distance(["t", "ʃ"], ["t͡ʃ"]).similarity < 1.0
        True
    """
    return _get_ipa().sequence_distance(
        seq1, seq2, weighted=weighted, mode=mode, return_alignment=return_alignment
    )


def sequence_similarity(
    seq1: Sequence[str],
    seq2: Sequence[str],
    *,
    weighted: bool = True,
    mode: str = "global",
) -> float:
    """The ``similarity`` of :func:`sequence_distance`, in [0, 1].

    Examples:
        >>> round(ipakit.sequence_similarity(["k", "æ", "t"], ["k", "æ", "d"]), 2)
        0.98
    """
    return _get_ipa().sequence_similarity(seq1, seq2, weighted=weighted, mode=mode)


def rank_sequences(
    observed: Sequence[str],
    candidates: Iterable[Sequence[str]],
    *,
    n: int | None = None,
    weighted: bool = True,
    mode: str = "global",
) -> list[SequenceMatch]:
    """Candidate phone sequences ranked by similarity to ``observed``, best
    first -- see :meth:`~ipakit.distance.DistanceMixin.rank_sequences`.

    Examples:
        >>> ms = ipakit.rank_sequences(["k", "æ", "t"], [["k", "æ", "t"], ["k", "ʊ", "t"]])
        >>> ms[0].similarity
        1.0
    """
    return _get_ipa().rank_sequences(
        observed, candidates, n=n, weighted=weighted, mode=mode
    )


def normalized_distance(phone1: str, phone2: str) -> float:
    """CDF-renormalized distance (percentile within the bundled IPA inventory)."""
    return _get_default_model().distance(phone1, phone2)


def confusability(phone1: str, phone2: str) -> float:
    """Normalized confusability (percentile similarity) in the bundled IPA inventory.

    The complement of :func:`normalized_distance`; 1.0 for identical phones.
    For an inventory-scoped model, build one with :func:`distance_model`.

    Examples:
        >>> round(ipakit.confusability("p", "b"), 3)
        0.959
        >>> ipakit.confusability("p", "p")
        1.0
    """
    return _get_default_model().confusability(phone1, phone2)


def distance_model(
    reference: Phoneset | list[str] | None = None,
    *,
    gamma: float = 1.0,
    insert_cost: PhoneCost = 1.0,
    delete_cost: PhoneCost = 1.0,
    threshold: float | None = None,
    max_length_ratio: float | None = None,
) -> DistanceModel:
    """Build a distribution-aware distance model over a reference inventory.

    ``reference=None`` uses the bundled global IPA inventory (default).
    """
    ipa = _get_ipa()
    if reference is None:
        return DistanceModel.global_(
            ipa,
            gamma=gamma,
            insert_cost=insert_cost,
            delete_cost=delete_cost,
            threshold=threshold,
            max_length_ratio=max_length_ratio,
        )
    ps = reference if isinstance(reference, Phoneset) else Phoneset.from_list(reference)
    return DistanceModel.for_phoneset(
        ipa,
        ps,
        gamma=gamma,
        insert_cost=insert_cost,
        delete_cost=delete_cost,
        threshold=threshold,
        max_length_ratio=max_length_ratio,
    )


def features(phone: str, with_defaults: bool = True) -> dict[str, str]:
    """Get phonetic features for an IPA phone.

    The scalar read: one value per feature. :func:`feature_values` is the
    multi-valued companion, for units whose constituents disagree.
    """
    return _get_ipa().get_features(phone, with_defaults=with_defaults)


def feature_values(unit: str) -> dict[str, tuple[str, ...]]:
    """Every value each feature takes across one unit's constituents.

    The bridge from the flat string API to the structured reads on
    ``Segment``: ``scalar()`` is what :func:`features` returns, ``bag()`` is
    this, and ``disagreements()`` is this filtered to the multi-valued
    features. Raises ``ValueError`` unless the text is exactly one unit.

    Examples:
        >>> features("u͜i")["backness"]  # scalar: the first element
        'back'
        >>> feature_values("u͜i")["backness"]
        ('back', 'front')
    """
    return _get_ipa().feature_values(unit)


def features_from_cmu(
    cmu_symbols: list[str], with_defaults: bool = True
) -> list[dict[str, str]]:
    """Get feature bundles from CMU ARPABET symbols."""
    ipa_str = _get_cmu().cmu_to_ipa(cmu_symbols)
    return _get_ipa().compose(ipa_str, with_defaults=with_defaults)


def features_from_xsampa(
    xsampa: str, with_defaults: bool = True
) -> list[dict[str, str]]:
    """Get feature bundles from X-SAMPA string."""
    ipa_str = xsampa_to_ipa(xsampa)
    return _get_ipa().compose(ipa_str, with_defaults=with_defaults)


# --- CMU ARPABET Conversion ---


def to_cmu(
    ipa_string: str,
    with_stress: bool = True,
    include_extras: bool = False,
    strict: bool = False,
) -> list[str]:
    """Convert IPA string to list of CMU ARPABET symbols.

    One symbol per segment :func:`segments` reads, so a word has the same
    number of phones under both. A tie is what makes two vowels one
    segment: ``ɔ͜ɪ`` is ``OY`` and untied ``ɔɪ`` is ``AO IH``. Either tie
    glyph is accepted, since ARPABET draws no distinction between them.

    With ``strict=True``, raise ``ValueError`` on unconvertible phones.
    """
    return _get_cmu().ipa_to_cmu(
        ipa_string,
        with_stress=with_stress,
        include_extras=include_extras,
        strict=strict,
    )


def from_cmu(
    cmu_symbols: list[str], include_extras: bool = True, strict: bool = False
) -> str:
    """Convert list of CMU ARPABET symbols to IPA string.

    With ``strict=True``, raise ``ValueError`` on unknown CMU symbols.

    Examples:
        >>> ipakit.from_cmu(["K", "AE1", "T"])
        'kˈæt'
    """
    return _get_cmu().cmu_to_ipa(
        cmu_symbols, include_extras=include_extras, strict=strict
    )


# --- Tokenization & Normalization ---


def tokenize(ipa_string: str, strict: bool = False) -> list[str]:
    """Parse IPA string into list of segment tokens.

    Parsing is strict house style: ASCII stand-ins (``g``, ``:``, ``?``,
    ``'``) are not IPA and are never read as IPA here -- import such text
    with :func:`from_wild` first. A character registered nowhere cannot be
    represented, so it is dropped with a warning; ``strict=True`` raises
    ``ValueError`` naming it instead.

    Examples:
        >>> tokenize("t͡ʃa")
        ['t͡ʃ', 'a']
    """
    return _get_ipa().tokenize(ipa_string, strict=strict)


def segmented(ipa_string: str, strict: bool = False) -> str:
    """Parse IPA and return its units, whitespace-separated.

    A display convenience; :func:`tokenize` returns the same units as a
    list and :func:`segments` as Segment objects.

    Examples:
        >>> segmented("t͡ʃa")
        't͡ʃ a'
    """
    return _get_ipa().segmented(ipa_string, strict=strict)


def segments(ipa_string: str, strict: bool = False) -> list[Segment]:
    """Parse IPA text into structured Segment units (see docs/ties.md).

    ``strict=True`` raises on any character the inventory does not
    register, which is what guarantees ``to_ipa(segments(x)) == x``
    rather than a quietly shortened result.

    Examples:
        >>> [s.kind.value for s in segments("t͡ʃa͜ɪ")]
        ['affricate', 'diphthong']
    """
    return _get_ipa().segments(ipa_string, strict=strict)


def segment(ipa_string: str, strict: bool = False) -> Segment:
    """Parse exactly one unit into a structured Segment.

    Examples:
        >>> segment("t͡s").kind.value
        'affricate'
        >>> segment("u͜i").bag()["backness"]
        ('back', 'front')
    """
    return _get_ipa().segment(ipa_string, strict=strict)


def to_ipa(segments: list[Segment]) -> str:
    """Join structured Segment units back into one IPA string.

    The inverse of :func:`segments`, and no stronger than
    ``Segment.to_ipa``: lossy on the legacy alias spellings, and marks
    belonging to no unit (breaks, the linking undertie) are not carried by
    a Segment at all (docs/ties.md).

    Examples:
        >>> to_ipa(segments("t͡ʃe͜ɪnd͡ʒ"))
        't͡ʃe͜ɪnd͡ʒ'
        >>> to_ipa(segments("ʧa"))  # the ligature parsed, its canonical spelling back
        't͡ʃa'
    """
    return _get_ipa().to_ipa(segments)


def normalize(segments: str) -> str:
    """Normalize whitespace-separated IPA segments into decodable IPA string."""
    return _get_ipa().normalize(segments)


def from_wild(text: str) -> str:
    """Import IPA written in other conventions into house style.

    The explicit door for wild text, and the only place soft reads apply:
    tie-glyph conventions canonicalize, and the ASCII stand-ins ``g``,
    ``:``, ``?`` and ``'`` become ``ɡ``, ``ː``, ``ʔ`` and ``ˈ`` (primary
    stress). ``!`` is left alone -- click, downstep and punctuation are
    all live readings of it (docs/ties.md).

    Examples:
        >>> from_wild("t͜sa͡ɪ")
        't͡sa͜ɪ'
        >>> from_wild("'gu:d")
        'ˈɡuːd'
    """
    return _get_ipa().from_wild(text)


def import_phoneset(phoneset: Phoneset) -> Phoneset:
    """Import a phoneset written in other tie conventions into house style.

    Examples:
        >>> import_phoneset(Phoneset.from_list(["t͜s", "e͡ɪ"], name="x")).phones
        ['t͡s', 'e͜ɪ']
    """
    return _get_ipa().import_phoneset(phoneset)


def normalize_lookalikes(text: str) -> str:
    """Apply the ASCII soft reads: keyboard stand-ins -> IPA symbols.

    ``g`` -> ``ɡ``, ``:`` -> ``ː``, ``?`` -> ``ʔ``, ``'`` -> ``ˈ``. A
    wild-import step, not a parsing step -- default parsing never calls
    it. :func:`from_wild` does.

    Examples:
        >>> normalize_lookalikes("gɑ:t")
        'ɡɑːt'
    """
    return _get_ipa().normalize_lookalikes(text)


def add_ties(segment: str) -> str:
    """Add tie bars between base phones in a multi-phone segment."""
    return _get_ipa().add_ties(segment)


def feature_bundles(
    ipa_string: str, with_defaults: bool = True
) -> list[dict[str, str]]:
    """Get list of feature dicts for each segment in an IPA string."""
    return _get_ipa().compose(ipa_string, with_defaults=with_defaults)


def phones_matching(query: _Query, with_defaults: bool = True) -> list[str]:
    """Get all phones matching features.

    Accepts a dict of feature to value, or any collection of names that is
    not a string. See :meth:`IPAFeatures.phones_matching`.
    """
    return _get_ipa().phones_matching(query, with_defaults=with_defaults)


def to_phone(bundle: dict[str, str]) -> str | None:
    """Realize a feature bundle as a registered IPA symbol.

    The inverse of :func:`features`: exact on the keys given, free on the
    keys omitted, ``None`` when nothing matches. See
    :meth:`IPAFeatures.to_phone` for the tie rule.

    Examples:
        >>> ipakit.to_phone({"manner": "plosive", "place": "alveolar"})
        't'
        >>> ipakit.to_phone(ipakit.features("ʃ"))
        'ʃ'
        >>> ipakit.to_phone({"manner": "vowel", "place": "velar"}) is None
        True
    """
    return _get_ipa().to_phone(bundle)


def respell(phone: str, **changes: str) -> str | None:
    """Apply a feature change to a phone and realize the result.

    ``None`` when the changed bundle names no registered phone; raises
    ``ValueError`` on an unresolvable phone or an undeclared feature or
    value.

    Examples:
        >>> ipakit.respell("t", voiced="+")
        'd'
        >>> ipakit.respell("p", place="velar")
        'k'
        >>> ipakit.respell("d", manner="nasal")   # a stop becomes its nasal
        'n'
        >>> ipakit.respell("i", rounded="+")      # round a front vowel
        'y'
        >>> ipakit.respell("t", manner="nasal") is None  # unattested
        True
    """
    return _get_ipa().respell(phone, **changes)


def find(
    ipa_string: str,
    query: _Query,
    with_defaults: bool = True,
) -> list[tuple[int, Segment]]:
    """Find the units of an IPA string matching a feature query.

    The same query language :func:`phones_matching` takes, run over a
    transcription instead of the inventory. Positions index :func:`segments`
    and each match is that Segment, so the unit's structure is in hand and
    ``to_ipa()`` spells it.

    Examples:
        >>> [(i, s.to_ipa()) for i, s in find("t͡ʃe͜ɪnd͡ʒ", ["vow"])]
        [(1, 'e͜ɪ')]
        >>> [i for i, _ in find("kæt", ["plo"])]
        [0, 2]
    """
    return _get_ipa().find(ipa_string, query, with_defaults=with_defaults)


def features_to_shorts(bundle: dict[str, str]) -> list[str]:
    """Convert a feature dict to list of short names."""
    return _get_ipa().features_to_shorts(bundle)


def shorts_to_features(shorts: list[str] | set[str]) -> dict[str, str]:
    """Convert list of short names to feature dict."""
    return _get_ipa().shorts_to_features(shorts)


def _make_wiki_url(ipa: IPAFeatures, href: str | None) -> str | None:
    """Construct full Wikipedia URL from article name."""
    if href and ipa.wiki_base and not href.startswith("http"):
        return ipa.wiki_base + href
    return href


def wiki(phone: str) -> str | None:
    """Get Wikipedia URL for an IPA phone symbol.

    Example:
        >>> ipakit.wiki("p")
        'https://en.wikipedia.org/wiki/Voiceless_bilabial_plosive'
    """
    ipa = _get_ipa()
    href = None
    if phone in ipa.phones:
        href = ipa.phones[phone].features.get("href")
    elif phone in ipa.diacritics:
        href = ipa.diacritics[phone].features.get("href")
    return _make_wiki_url(ipa, href)


def wiki_ref(name: str) -> str | None:
    """Get Wikipedia URL for a general IPA reference.

    Example:
        >>> ipakit.wiki_ref("IPA")
        'https://en.wikipedia.org/wiki/International_Phonetic_Alphabet'
        >>> ipakit.wiki_ref("X-SAMPA")
        'https://en.wikipedia.org/wiki/X-SAMPA'
    """
    ipa = _get_ipa()
    href = ipa.references.get(name)
    return _make_wiki_url(ipa, href)


def wiki_refs() -> dict[str, str]:
    """Get all general IPA reference URLs.

    Returns dict mapping reference names to full Wikipedia URLs.
    """
    ipa = _get_ipa()
    return {
        name: url
        for name, href in ipa.references.items()
        if (url := _make_wiki_url(ipa, href)) is not None
    }


# --- Analysis functions ---


def describe(phone: str, with_defaults: bool = True) -> str:
    """Generate human-readable IPA description for a phone.

    Examples:
        >>> ipakit.describe("p")
        'voiceless bilabial plosive'
        >>> ipakit.describe("ɛ")
        'open-mid front unrounded vowel'
        >>> ipakit.describe("t͡ʃ")
        'voiceless sibilant postalveolar affricate'
        >>> ipakit.describe("ɫ")
        'voiced velarized lateral alveolar approximant'
        >>> ipakit.describe("ã")
        'nasalized open front unrounded vowel'
    """
    return _get_ipa().describe(phone, with_defaults=with_defaults)


def natural_class(
    phones: list[str],
    with_defaults: bool = True,
    exclude_features: set[str] | None = None,
) -> dict[str, str]:
    """Find features shared by all phones in a set (natural class).

    Examples:
        >>> ipakit.natural_class(["p", "t", "k"])  # shared features (incl. defaults)
        {'manner': 'plosive', ...'voiced': '-', ...}
        >>> ipakit.natural_class(["i", "e", "ɛ"])
        {'manner': 'vowel', ...'backness': 'front', ...}
    """
    return _get_ipa().natural_class(
        phones, with_defaults=with_defaults, exclude_features=exclude_features
    )


def minimal_pairs(
    phone: str,
    with_defaults: bool = True,
    max_distance: float = 0.3,
) -> list[tuple[str, str, str | None]]:
    """Find phones that differ by approximately one feature (minimal pairs).

    Returns list of (phone, differing_feature, differing_value) tuples.

    Examples:
        >>> ipakit.minimal_pairs("p")
        [('t', 'place', 'alveolar'), ('ɸ', 'manner', 'fricative'), ...]
    """
    return _get_ipa().minimal_pairs(
        phone, with_defaults=with_defaults, max_distance=max_distance
    )


def nearest_phones(
    phone: str,
    n: int = 10,
    with_defaults: bool = True,
) -> list[tuple[str, float]]:
    """Find the n nearest phones by phonetic distance.

    Returns list of (phone, distance) tuples sorted by distance.

    Examples:
        >>> [(p, round(d, 3)) for p, d in ipakit.nearest_phones("p", n=3)]
        [('t', 0.019), ('ɸ', 0.027), ('f', 0.03)]
    """
    return _get_ipa().nearest_phones(phone, n=n, with_defaults=with_defaults)


def hierarchy(
    phones: list[str] | None = None,
    feature_order: list[str] | None = None,
) -> dict[str, Any]:
    """Group the inventory into a tree, splitting on one feature per level.

    The read behind ``ipakit hierarchy json``. Interior nodes are
    ``{"feature": name, "children": {value: node}}`` and leaves are
    ``{"phones": [...]}``. :func:`hierarchy_text` and :func:`hierarchy_dot`
    render the same tree.

    Examples:
        >>> hierarchy(["p", "b", "t"])["feature"]  # all three are plosives
        'place'
        >>> hierarchy(["p", "s"])["feature"]
        'manner'
        >>> hierarchy(["p", "b"], ["voiced"])
        {'children': {'+': {'phones': ['b']}, '-': {'phones': ['p']}}, 'feature': 'voiced'}
    """
    return _get_ipa().build_hierarchy(phones, feature_order)


def hierarchy_text(
    phones: list[str] | None = None,
    feature_order: list[str] | None = None,
    indent: str = "  ",
) -> str:
    """Render :func:`hierarchy` as an indented tree (``ipakit hierarchy text``).

    Examples:
        >>> print(hierarchy_text(["p", "b"], ["voiced"]))
          voiced=+: [b]
          voiced=-: [p]
    """
    return _get_ipa().hierarchy_to_text(phones, feature_order, indent=indent)


def hierarchy_dot(
    phones: list[str] | None = None,
    feature_order: list[str] | None = None,
    title: str = "Phone Hierarchy",
) -> str:
    """Render :func:`hierarchy` as Graphviz DOT (``ipakit hierarchy dot``).

    Examples:
        >>> hierarchy_dot(["p", "b"], ["voiced"]).splitlines()[0]
        'digraph PhoneHierarchy {'
    """
    return _get_ipa().hierarchy_to_dot(phones, feature_order, title=title)


def stress_markers() -> dict[str, int]:
    """The declared stress marks, each mapped to its level.

    The read behind ``ipakit info stress``. Declared in ``ipa.xml``, not
    listed here, so the command line and the library cannot disagree
    about which marks exist.

    Examples:
        >>> stress_markers()
        {'ˈ': 1, 'ˌ': 2}
    """
    return dict(_get_ipa().stress_markers)


def validate_ipa(ipa: str, strict: bool = False) -> list[dict[str, str]]:
    """Validate an IPA string for well-formedness.

    Returns a list of issue dicts. Empty list means valid.

    Examples:
        >>> ipakit.validate_ipa("kæt")
        []
        >>> ipakit.validate_ipa("k4t")  # 'x', 'y', 'z' are all valid IPA; '4' is not
        [{'type': 'error', 'code': 'unknown_symbol', 'message': "Unknown symbol '4' (U+0034)", 'position': '1', 'symbol': '4'}]
    """
    return _get_ipa().validate_ipa(ipa, strict=strict)


def is_valid_ipa(ipa: str) -> bool:
    """Check if an IPA string is valid (no errors).

    Examples:
        >>> ipakit.is_valid_ipa("kæt")
        True
        >>> ipakit.is_valid_ipa("k4t")  # 'x', 'y', 'z' are valid IPA; '4' is not
        False
    """
    return _get_ipa().is_valid_ipa(ipa)


def extensions_in(text: str) -> list[str]:
    """The symbols in ``text`` that are not on the IPA chart, in order.

    The informative half of a pair, in the shape of
    :func:`validate_ipa` / :func:`is_valid_ipa`: this one names what it
    found, and :func:`is_pure_ipa` is the yes-or-no over it. Which
    symbols are extensions is declared in ``ipa.xml``'s ``<notations>``
    block, so a further convention answers the same question with
    nothing new invented for it.

    An unregistered character is not an extension -- it is unknown, and
    :func:`validate_ipa` is what reports it.

    Examples:
        >>> ipakit.extensions_in("lez‿ami")
        []
        >>> ipakit.extensions_in("#a∅b␣")
        ['#', '∅', '␣']
    """
    return _get_ipa().extensions_in(text)


def is_pure_ipa(text: str) -> bool:
    """Whether ``text`` uses no symbol declared as a NON-chart notation.

    **Not a validity check, and it does not imply one.** This is the
    boolean over :func:`extensions_in`, so it sees only symbols this
    inventory declares and puts outside ``chart``. A character registered
    nowhere resolves to the default notation and is invisible to it, so
    ``is_pure_ipa("xyz$")`` is True. :func:`validate_ipa`, or
    :func:`is_valid_ipa` for the boolean, is what reports unknown
    characters -- and is almost certainly the question a caller reaching
    for this one means. Do not use it as a pre-render gate: green here is
    not "well-formed".

    The two questions are independent in both directions, which is why
    neither stands in for the other.

    Examples:
        >>> ipakit.is_pure_ipa("ˈkæt.dɒɡ")
        True
        >>> ipakit.is_pure_ipa("#kæt#")  # '#' is generative notation, not IPA
        False
        >>> ipakit.is_valid_ipa("#kæt#")  # ... and valid all the same
        True
        >>> ipakit.is_pure_ipa("xyz$")    # '$' is UNKNOWN, not an extension
        True
        >>> ipakit.is_valid_ipa("xyz$")   # ... which is what reports it
        False
    """
    return _get_ipa().is_pure_ipa(text)


# --- Rewrite rules ---


def rule(text: str) -> Rule:
    """Build one rewrite rule from the notation (see :mod:`ipakit.rules`).

    The name separator is ``;``, not ``|``: ``|`` is a declared prosodic
    break and therefore a legal context item.

    ``ipa.rule("t -> ʔ / _ # ; glottalling")``
    """
    return rules.parse(text, _get_ipa())


def ruleset(text: str, name: str = "") -> RuleSet:
    """Build an ordered rule set, from rule text or from a shipped name.

    ``ruleset("american-english")`` loads the shipped set of that name;
    anything else is read as notation, one rule per line. The test is
    membership in :func:`available`, not a guess at the shape of the
    string: a name is a name exactly when the library ships one, so no
    rule text can be mistaken for a name and no name can be mistaken for
    rule text. (Rule notation needs a rewrite arrow, and a shipped name
    has none, which is why the wrong branch used to raise "has no
    rewrite arrow" at the documented entry point to the feature.)

    :func:`shipped` is the unambiguous spelling when the argument comes
    from elsewhere and must not be read as notation.

    Examples:
        >>> len(ruleset("american-english")) > 0
        True
        >>> ruleset("american-english").name
        'american-english'
        >>> len(ruleset("t -> ʔ / _ #"))
        1
    """
    if text in rules.available():
        return rules.shipped(text, _get_ipa())
    return RuleSet.parse(text, _get_ipa(), name=name)


def rewrite(
    form: Matchable, spec: str | Rule | RuleSet, keep_zeros: bool = False
) -> str:
    """Apply rules to an IPA form and return the derived form.

    ``spec`` may be a shipped set's name, rule notation, a single
    :class:`Rule`, or a :class:`RuleSet`. Use :func:`derive` when the
    trace is wanted.

    The answer is a **surface** form: :func:`ipakit.rules.surface` runs
    last, so no pronunciation carries a zero. ``keep_zeros`` declines
    that final rewrite, for a caller assembling one derivation out of
    several.

    Examples:
        >>> rewrite("pˈɪn", "american-english")
        'pʰˈɪ̃n'
        >>> rewrite("kæt", "t -> ʔ / _ #")
        'kæʔ'
        >>> rewrite("lezami", "z -> [zero] / [vowel] _ [vowel]")
        'leami'
        >>> rewrite("lezami", "z -> [zero] / [vowel] _ [vowel]", keep_zeros=True)
        'le∅ami'
    """
    return derive(form, spec, keep_zeros=keep_zeros).result


def derive(
    form: Matchable, spec: str | Rule | RuleSet, keep_zeros: bool = False
) -> Derivation:
    """Apply rules to an IPA form, keeping the rule-by-rule trace.

    ``spec`` is read exactly as :func:`ruleset` reads it -- through that
    function, not beside it, so a shipped name works in all three string
    entry points or in none of them.

    The trace holds the zero wherever a rule wrote one, and the final
    ``surface`` step is what takes it out again; ``keep_zeros`` stops
    before it.

    ``form`` may be a :class:`~ipakit.form.Form`, and then a tier it
    carries survives the cascade: each rule sees the spans as the rule
    before it left them, and :attr:`Derivation.intervals` is where they
    come back. A string carries none and none is derived from it.
    """
    features = _get_ipa()
    if isinstance(spec, str):
        spec = ruleset(spec)
    elif isinstance(spec, Rule):
        spec = RuleSet(rules=(spec,))
    return spec.derive(form, features, keep_zeros=keep_zeros)


def variants(
    form: Matchable,
    spec: str | Rule | RuleSet,
    limit: int = DEFAULT_LIMIT,
    keep_zeros: bool = False,
) -> VariantSet:
    """Every form the rules derive, not only the one they settle on.

    The set-valued entry point, and the reason the notation has a second
    arrow. ``spec`` is read exactly as :func:`rewrite` and :func:`derive`
    read it. A rule written ``A ~> B`` may fire at a site or not, and each
    site branches independently, so a word with two optional sites has up
    to four pronunciations rather than two.

    ``variants(...)[0]`` is always :func:`rewrite`'s answer -- the member
    that takes no optional choice -- so the two entry points cannot come
    to disagree. ``limit`` bounds what the cascade carries between rules;
    ask :attr:`VariantSet.complete` whether it was reached, because a
    truncated set of pronunciations reads exactly like a whole one.

    Every member is a surface form, and members are deduplicated after
    that projection, so two branches that differed only in where a zero
    stood are one pronunciation. ``keep_zeros`` answers with what the
    cascade itself derived.

    Examples:
        >>> variants("kæt", "t -> ʔ / _ #").forms
        ('kæʔ',)
        >>> variants("kæt", "t ~> ʔ / _ #").forms
        ('kæt', 'kæʔ')
        >>> variants("kæt", "t ~> ʔ / _ #").complete
        True
        >>> variants("dəvəniʁ", "ə ~> [zero] / [-vowel] _ [-vowel]").forms
        ('dəvəniʁ', 'dvəniʁ', 'dəvniʁ', 'dvniʁ')
    """
    features = _get_ipa()
    if isinstance(spec, str):
        spec = ruleset(spec)
    elif isinstance(spec, Rule):
        spec = RuleSet(rules=(spec,))
    return spec.variants(form, features, limit=limit, keep_zeros=keep_zeros)


# ``units`` is :func:`ipakit.form.units`, re-exported above rather than
# wrapped: the read is one function, so the two spellings cannot come to
# mean different things. It belongs to the Form layer rather than the rules
# layer -- nothing about splitting a transcription into units is specific
# to rewriting -- which is why there is no second spelling of it here.


__all__ = [
    # Classes
    "CMUMapper",
    "DistanceModel",
    "Feature",
    "IPAFeatures",
    "Phone",
    "Segment",
    "Constituent",
    "Sense",
    "Kind",
    "segments",
    "segmented",
    "from_wild",
    "import_phoneset",
    "PhoneMapping",
    "Phoneset",
    "CostSchedule",
    "PhoneCost",
    "WordDistanceResult",
    "ScoringParameters",
    "PronunciationMatch",
    "SequenceMatch",
    # Constants
    "DATA_DIR",
    "DEFAULT_CMU_MAP",
    "DEFAULT_IPA_FEATS",
    "PHONEMAPS_DIR",
    "SUPPLEMENTS_DIR",
    # Functions
    "add_ties",
    "available_supplements",
    "confusability",
    "describe",
    "distance",
    "distance_model",
    "extensions_in",
    "feature_bundles",
    "feature_values",
    "features",
    "features_from_cmu",
    "features_from_xsampa",
    "find",
    "from_cmu",
    "from_kirshenbaum",
    "from_timit",
    "hierarchy",
    "hierarchy_dot",
    "hierarchy_text",
    "ipa_to_phonemap",
    "ipa_to_xsampa",
    "is_pure_ipa",
    "is_valid_ipa",
    "load_ipa_features",
    "minimal_pairs",
    "natural_class",
    "nearest_phones",
    "normalize",
    "normalize_lookalikes",
    "notebook",
    "normalized_distance",
    "phonemap_to_ipa",
    "phones_matching",
    "respell",
    "segment",
    "stress_markers",
    "supplement_path",
    "to_cmu",
    "to_ipa",
    "to_kirshenbaum",
    "to_phone",
    "to_timit",
    "tokenize",
    "validate_ipa",
    "word_distance",
    "directional_word_distance",
    "segment_distance",
    "pairwise_distances",
    "word_similarity",
    "nearest_pronunciation",
    "rank_pronunciations",
    "sequence_distance",
    "sequence_similarity",
    "rank_sequences",
    "xsampa_to_ipa",
    # Form representation
    "Attribute",
    "Boundary",
    "Form",
    "Interval",
    "Node",
    "levels",
    "tier_names",
    # Rewrite rules
    "Action",
    "Derivation",
    "Edit",
    "Query",
    "RebaseError",
    "Rule",
    "RuleError",
    "RuleSet",
    "Site",
    "Step",
    "Unit",
    "available",
    "rebase",
    "rule",
    "ruleset",
    "rewrite",
    "derive",
    "shipped",
    "units",
    # The tract, drawn
    "tract_svg",
    # The calculus over the string set (docs/calculus.md)
    "DEFAULT_LIMIT",
    "Truncation",
    "Variant",
    "VariantSet",
    "variants",
]
