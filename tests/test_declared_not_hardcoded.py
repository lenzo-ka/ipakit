"""Phonetic facts live in ipa.xml, not in Python constants.

The house rule: code the necessary features in the data or derive them
there; do not smuggle them in by hardcoding. Three tables used to break
it -- ``_MODE_EXCEPTIONS`` classified two diacritics *by symbol*,
``SECONDARY_PLACE``/``_SECONDARY_KEYS``/``_SECONDARY_DESC_ORDER`` were
three independent copies of one five-member set in three modules, and
``_BINARY_LABELS`` decided that ``channel=grooved`` reads "sibilant".
A fourth broke it without being a table at all: ``constants.TIE_BAR``
and ``SEQ_TIE`` pasted the two glyphs that spell the declared ``tie``
feature's values, one symbol per name, and so met none of the "two or
more" tests below. They are ``IPAFeatures.tie_bars`` now.

Three kinds of test here. The pins assert the derived reads still say
what the hardcoded tables said. The guard is a predicate over the source:
it looks for the *shape* of a smuggled constant rather than for today's
names, so a new one fails too, and it is fed synthetic sources as well as
the real package so its own coverage is measured rather than assumed.
The third kind pins what the guard *cannot* see, so its limits stay known
rather than assumed shut.

A predicate is only as wide as the vocabulary it is asked about, and
that is where this one had a hole: the symbols it knew were four tables
written out by hand, and ``<zeros>`` was not among them, so ``∅`` --
declared, and the same lone-glyph shape as the tie bars above -- was
invisible to the very test that narrates catching it. The vocabulary is
the loader's own enumeration of the element classes now, so the next
class added to the data cannot reopen it.

Where a constant restates the data on purpose, ``_JUSTIFIED`` says which
one and why, and is pinned in both directions: the house rule is that a
smuggle must be justified and declared, not that none may exist.
"""

from __future__ import annotations

import ast
import sys
import warnings
from pathlib import Path

import pytest
from ipakit import IPAFeatures
from ipakit.analysis import _MODIFIER_READ_ORDER, _PRIMARY_SLOTS
from ipakit.constants import METADATA_ATTRS
from ipakit.metric import excluded_keys
from ipakit.segment import _OBSTRUENT, modifier_mode

_PACKAGE = Path(__file__).resolve().parent.parent / "ipakit"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from invariants import declared_symbols  # noqa: E402


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


class TestTheDataSaysWhatThePythonUsedTo:
    """Each derived read reproduces the table it replaced, exactly."""

    def test_the_mode_partition(self, ipa: IPAFeatures) -> None:
        by_mode = {m: set(v) for m, v in ipa.features_by_mode.items()}
        # 'level' is here because a boundary level belongs to no segment's
        # feature bag, which is what that mode says. It sat in the additive
        # default while only separators declared a level and no diacritic
        # did, so nothing showed it was misfiled.
        assert by_mode["structural"] == {"tie", "linking", "break", "level"}
        assert by_mode["prosodic"] == {
            "stress",
            "length",
            "tone",
            "contour",
            "global",
            "step",
        }
        assert by_mode["release"] == {"release"}
        assert by_mode["secondary"] == {
            "palatalized",
            "labialized",
            "velarized",
            "pharyngealized",
            "labio-palatized",
        }
        # 'airstream' is here for the reason the other four are: a segment
        # holds one of each at a time, so a mark that states one states the
        # segment's. It sat in the additive default because nothing had
        # chosen, which left the only mark that states it inert on every
        # base declaring its own -- 'ǂʼ' read as 'ǂ'.
        assert by_mode["overriding"] == {
            "voiced",
            "place",
            "manner",
            "syllabic",
            "airstream",
        }

    def test_the_partition_is_total_and_declared(self, ipa: IPAFeatures) -> None:
        # Every feature lands in exactly one bucket, and every bucket is a
        # mode <modes> declares.
        assert set(ipa.features_by_mode) <= set(ipa.modes)
        seen = [n for names in ipa.features_by_mode.values() for n in names]
        assert sorted(seen) == sorted(ipa.features)

    def test_secondary_places(self, ipa: IPAFeatures) -> None:
        assert ipa.secondary_places == {
            "palatalized": "palatal",
            "labialized": "bilabial",
            "velarized": "velar",
            "pharyngealized": "pharyngeal",
            "labio-palatized": "bilabial^palatal",
        }

    def test_the_secondary_set_is_one_statement(self, ipa: IPAFeatures) -> None:
        # The property that stops the three copies drifting: the mode
        # partition and the place table are the same declaration read two
        # ways, so they cannot disagree about what a secondary is.
        assert set(ipa.secondary_places) == set(ipa.features_by_mode["secondary"])
        for place in ipa.secondary_places.values():
            assert set(ipa.features["place"].expand(place)) <= set(
                ipa.features["place"].values
            )

    def test_the_obstruent_manners(self, ipa: IPAFeatures) -> None:
        assert ipa.features["manner"].value_classes[_OBSTRUENT] == frozenset(
            {"plosive", "fricative", "affricate"}
        )

    def test_the_description_labels(self, ipa: IPAFeatures) -> None:
        labels = {n: f.labels for n, f in ipa.features.items() if f.labels}
        assert labels["voiced"] == {"+": "voiced", "-": "voiceless"}
        assert labels["rounded"] == {"+": "rounded", "-": "unrounded"}
        assert labels["channel"] == {"lateral": "lateral", "grooved": "sibilant"}
        assert "flat" not in labels["channel"]  # the unremarkable value is unsaid
        assert labels["rhotacized"] == {"+": "r-colored"}

    def test_class_applicability(self, ipa: IPAFeatures) -> None:
        assert not ipa.feature_applies("channel", {"manner": "vowel"})
        assert ipa.feature_applies("channel", {"manner": "plosive"})
        assert not ipa.feature_applies("retroflex", {"manner": "vowel"})
        assert not ipa.feature_applies("rhotacized", {"manner": "plosive"})
        assert ipa.feature_applies("nasalized", {"manner": "vowel"})
        assert ipa.feature_applies("nasalized", {"manner": "plosive"})

    def test_the_excluded_keys(self, ipa: IPAFeatures) -> None:
        from ipakit.constants import METADATA_ATTRS

        assert excluded_keys(ipa) == frozenset(
            set(METADATA_ATTRS)
            | {"place", "nasalized", "constriction-location"}
            | set(ipa.secondary_places)
        )

    def test_a_borrower_is_excluded_with_what_it_borrows(
        self, ipa: IPAFeatures
    ) -> None:
        """And it is excluded *because* the lender is, not by name.

        ``constriction-location`` declares ``vocabulary="place"``, and
        ``place`` is carried by the weighted place components rather than
        compared as a key. Comparing the borrower as a key would put the
        nominal place comparison back in a spelling those components
        cannot see -- and, since only some vowels state a location, it
        would score the ones that do not as maximally unlike the ones
        that do. Moving the lender out of the exclusion moves the
        borrower with it, so the two cannot agree only by habit.
        """
        borrowers = {n for n, f in ipa.features.items() if f.vocabulary is not None}
        assert borrowers, "nothing borrows a vocabulary: this check is vacuous"
        assert borrowers <= excluded_keys(ipa)
        for name in borrowers:
            assert ipa.features[name].vocabulary in excluded_keys(ipa), name

    def test_the_bridges(self, ipa: IPAFeatures) -> None:
        assert ipa.bridges == {
            "nasality": (
                ("manner", "nasal"),
                ("nasalized", "+"),
                ("release", "nasal"),
                ("approach", "nasal"),
            ),
            "laterality": (("channel", "lateral"), ("release", "lateral")),
        }

    def test_the_projections(self, ipa: IPAFeatures) -> None:
        """Which dimensions are one fact at two granularities.

        ``compose_unit`` needs this to tell a mark that says its one fact
        twice (the devoicing ring: phonation and voiced) from one that
        drags an independent dimension along (the linguolabial mark: place
        and articulator). It reads the declaration rather than carrying a
        pair table of its own.
        """
        assert ipa.projections == {
            ("phonation", "creaky"): ("voiced", "+"),
            ("phonation", "modal"): ("voiced", "+"),
            ("phonation", "breathy"): ("voiced", "+"),
            ("phonation", "devoiced"): ("voiced", "-"),
        }

    def test_a_projection_is_total_over_the_finer_features_values(
        self, ipa: IPAFeatures
    ) -> None:
        """A partial projection would leave the rest of the values looking
        like an independent dimension, so the loader refuses one."""
        fine_names = {f for f, _ in ipa.projections}
        assert fine_names, "no projection declared: the sweep would be vacuous"
        for name in fine_names:
            covered = {v for f, v in ipa.projections if f == name}
            assert covered == set(ipa.features[name].values), name

    def test_a_projection_is_not_resolved_onto_a_segments_features(
        self, ipa: IPAFeatures
    ) -> None:
        """What the declaration deliberately does *not* do, and what
        closed the gap it used to leave open.

        A read path that resolved the projection would give every segment
        carrying a voiced phonation ``voiced="+"`` *whether or not any
        mark said so*, which is a change to what every read returns. It
        still does not, and the assertions below are that limit.

        The limit used to have a visible cost: 76 units read a voiced
        phonation on a voiceless segment, and ``describe("c̤")`` was
        "voiceless breathy-voiced palatal plosive" -- a sentence that
        contradicts itself. That was never the read path's fault. The
        devoicing and voicing rings declared the voicing their phonation
        fixes and the breathy and creaky marks did not, so on a voiceless
        base the base's voicing stood: an asymmetry in the data, fixed in
        the data. All four marks state it now, and there is nothing left
        for a read path to resolve.

        ``scripts/invariants.py:check_projection_coherence`` is the guard,
        written as a predicate over whatever ``<projections>`` declares
        rather than over these two marks.
        """
        assert ipa.projections[("phonation", "breathy")] == ("voiced", "+")
        # Resolution is still not a read path: every segment that reads
        # voiced does so because some declaration said so.
        assert ipa.get_features("a̤").get("voiced") == "+"  # base and mark agree
        assert (
            ipa.get_features("s̤").get("voiced") == "+"
        )  # from the mark, not the base
        assert ipa.diacritics["̤"].features["voiced"] == "+"
        assert "voiced" not in ipa.get_features("␣")  # silence takes no default
        contradicting = [
            unit
            for phone in ipa.phones
            for mark in ("̤", "̰")
            if (unit := phone + mark)
            and ipa.segment(unit).to_ipa() == unit
            and (bundle := ipa.get_features(unit))
            and (
                target := ipa.projections.get(
                    ("phonation", bundle.get("phonation", ""))
                )
            )
            and bundle.get(target[0], target[1]) != target[1]
        ]
        assert contradicting == [], f"{len(contradicting)}, was 76"

    def test_the_projection_is_not_a_bridge(self, ipa: IPAFeatures) -> None:
        """Why it is a separate declaration, pinned as consequences.

        A bridge is a *presence*, derived as one binary for the metric.
        Declaring the glottal state as one would make devoiced and modal
        read alike and, every informative value of ``voiced`` then being
        claimed, drop ``voiced`` from the comparison outright: measured at
        3800 of 9591 pairs moved and d(t, d) = 0.
        """
        assert set(ipa.bridges) & {f for f, _ in ipa.projections} == set()
        assert "voiced" not in excluded_keys(ipa)
        assert ipa.distance("t", "d") > 0

    def test_modes_come_from_the_marks_own_features(self, ipa: IPAFeatures) -> None:
        assert modifier_mode(ipa, "ˀ") == "release"
        assert modifier_mode(ipa, "ᵊ") == "release"
        assert modifier_mode(ipa, "ʰ") == "release"
        assert modifier_mode(ipa, "ʲ") == "secondary"
        assert modifier_mode(ipa, "̥") == "overriding"
        assert modifier_mode(ipa, "͡") == "structural"
        assert modifier_mode(ipa, "ː") == "prosodic"
        assert modifier_mode(ipa, "̃") == "additive"


class TestTheOrderingTupleCanOnlyOrder:
    """The one ordered list left in Python names *where* a modifier goes in
    the sentence. It must not be able to decide *whether* one is read out:
    that is the data's call, through `label` and `applies`."""

    def test_every_ordered_name_is_admitted_by_the_data(self, ipa: IPAFeatures) -> None:
        for name in _MODIFIER_READ_ORDER:
            feat = ipa.features.get(name)
            assert feat is not None, name
            assert feat.labels, f"{name} is ordered but declares no label"
            assert name not in _PRIMARY_SLOTS, name

    def test_every_admitted_feature_is_reachable(self, ipa: IPAFeatures) -> None:
        # A label added in the data reaches descriptions without a code
        # change: membership is derived, so nothing can be declared and
        # then silently never read out.
        admitted = {
            n for n, f in ipa.features.items() if f.labels and n not in _PRIMARY_SLOTS
        }
        reachable = set()
        for manner in [*ipa.features["manner"].values, None]:
            bundle = {"manner": manner} if manner else {}
            reachable |= set(ipa._modifier_features(bundle))
            # A nucleus is vowel-or-syllabic, so a nucleus-only feature is
            # reachable on a consonantal manner that is marked syllabic.
            reachable |= set(ipa._modifier_features({**bundle, "syllabic": "+"}))
        assert admitted == reachable


def _stated(ipa: IPAFeatures, sym: str) -> dict[str, str]:
    """What a mark says, less the metadata every entry carries."""
    return {
        f: v for f, v in ipa.diacritics[sym].features.items() if f not in METADATA_ATTRS
    }


def _reads_back(ipa: IPAFeatures, text: str) -> bool:
    """Whether the inventory can spell this, strictly and unchanged."""
    try:
        return ipa.segment(text, strict=True).to_ipa() == text
    except ValueError:
        return False


def _bag(ipa: IPAFeatures, text: str) -> dict[str, str]:
    return {k: v for k, v in ipa.get_features(text).items() if k not in METADATA_ATTRS}


@pytest.fixture(scope="module")
def segmental_marks(ipa: IPAFeatures) -> list[str]:
    """The marks whose contribution a segment's feature bag carries.

    Derived, not listed. A prosodic or structural mark belongs to the
    unit rather than to its bag (docs/ties.md), so it reaches no bundle
    here and is correctly silent in a description -- a tone letter has
    nothing to contribute to the name of a sound. A mark that states only
    its features' defaults -- ``̯`` says ``syllabic="-"`` -- reports what
    an unmarked segment already reports. What is left is every mark that
    makes a difference to a bundle, which is exactly what a description
    is answerable for.
    """
    out = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for sym in ipa.diacritics:
            stated = _stated(ipa, sym)
            if all(v == ipa.features[f].default for f, v in stated.items()):
                continue
            if any(
                _bag(ipa, base + sym) != _bag(ipa, base)
                for base in ipa.phones
                if _reads_back(ipa, base + sym)
            ):
                out.append(sym)
    return out


class TestNothingAMarkStatesGoesUnsaid:
    """The converse of the reachability guard above.

    ``test_every_admitted_feature_is_reachable`` runs from the label to
    the description, so it can only see a feature that already declares
    one: a feature that declares *no* label is invisible to the very test
    meant to catch a description that cannot see it. Twelve marks sat in
    that blind spot -- ``describe("a̘")`` was word for word
    ``describe("a")`` while the feature bag and the metric both charged
    the difference.

    These run the other way, over every value the data lets a mark state.
    """

    @staticmethod
    def _requirements(
        ipa: IPAFeatures, marks: list[str]
    ) -> tuple[dict[tuple[str, str], set[str]], dict[tuple[str, str], set[str]]]:
        """What a segmental mark states, and which of those a slot covers.

        A value is left out when its feature is one of the slots the
        sentence renders itself (``describe`` reads those by name, not by
        label), and when it equals its feature's default. Everything else
        is a difference the mark makes, and the data has to say how it
        reads.
        """
        need: dict[tuple[str, str], set[str]] = {}
        covered: dict[tuple[str, str], set[str]] = {}
        for sym in marks:
            stated = _stated(ipa, sym)
            # A mark that also fills a slot has already changed the
            # sentence through it, so its other keys may go unlabeled
            # without the mark itself going unsaid.
            fills_a_slot = any(f in _PRIMARY_SLOTS for f in stated)
            for feature, value in stated.items():
                if feature in _PRIMARY_SLOTS or value == ipa.features[feature].default:
                    continue
                need.setdefault((feature, value), set()).add(sym)
                if fills_a_slot:
                    covered.setdefault((feature, value), set()).add(sym)
        return need, covered

    def _escapes(self, ipa: IPAFeatures, marks: list[str]) -> set[tuple[str, str]]:
        need, covered = self._requirements(ipa, marks)
        return {
            fv
            for fv, stating in need.items()
            if ipa.features[fv[0]].labels.get(fv[1]) is None
            and stating == covered.get(fv, set())
        }

    def test_every_value_a_mark_states_declares_how_it_reads(
        self, ipa: IPAFeatures, segmental_marks: list[str]
    ) -> None:
        need, _ = self._requirements(ipa, segmental_marks)
        # A silent collapse of the corpus would make the assertion below
        # vacuous, so the size is asserted, not assumed.
        assert len(segmental_marks) > 30, "sweep did not run"
        assert len(need) > 25, "sweep did not run"
        unlabeled = {fv for fv in need if ipa.features[fv[0]].labels.get(fv[1]) is None}
        assert not unlabeled - self._escapes(ipa, segmental_marks)

    def test_the_guard_states_what_it_lets_through(
        self, ipa: IPAFeatures, segmental_marks: list[str]
    ) -> None:
        """If a value starts or stops escaping, this fails and the
        documented limits need updating.

        Both escapes are one fact: the mark stating them also states the
        voicing, which is read out, so naming the phonation would only
        repeat it -- ``d̥`` reads "voiceless", not "voiceless devoiced" --
        and ``modal`` is the unremarkable value besides. That held on a
        consonant only until ``describe`` read the voicing slot on a
        vowel too: ``ḁ`` used to read exactly as ``a``, so the escape was
        letting a real omission through on half the inventory.
        """
        assert self._escapes(ipa, segmental_marks) == {
            ("phonation", "modal"),
            ("phonation", "devoiced"),
        }

    def test_no_segmental_mark_describes_as_its_bare_base(
        self, ipa: IPAFeatures, segmental_marks: list[str]
    ) -> None:
        """The symptom, swept: a mark that makes a difference to a
        feature bag makes one to some segment's name."""
        invisible = []
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for sym in segmental_marks:
                if not any(
                    ipa.describe(base + sym) != ipa.describe(base)
                    for base in ipa.phones
                    if _reads_back(ipa, base + sym)
                ):
                    invisible.append(sym)
        assert len(segmental_marks) > 30, "sweep did not run"
        assert invisible == []


# ---------------------------------------------------------------------------
# The guard
# ---------------------------------------------------------------------------

_SET_BUILDERS = {"set", "frozenset", "dict"}
_SEQ_BUILDERS = {"tuple", "list", "sorted"}
# Methods that build a collection out of what they are handed, named
# rather than the object they hang off so a rebound `re` or a subclassed
# `dict` is read the same way. `fromkeys` builds a mapping and a regex
# alternation or character class puts its members in one pattern, so both
# *classify*; `join` consumes a sequence and states an order.
_UNORDERED_METHODS = {"fromkeys", "compile"}
_SEQ_METHODS = {"split", "rsplit", "splitlines", "join"}
# Calls that consume a string as a *sequence of members* rather than as
# one value. Only these expand a string to its characters: doing it
# everywhere would read "stress" as the phones s, t, r, e.
_ITERATING = _SET_BUILDERS | _SEQ_BUILDERS | {"zip", "enumerate"}
# The same, written as a method. `dict.fromkeys("ˈˌ")` and `"".join("ˈˌ")`
# ask for the characters as plainly as `set("ˈˌ")` does. A regex is not
# here on purpose: expanding a pattern to its characters would read
# `re.compile("stress")` as the phones s, t, r, e.
_ITERATING_METHODS = {"fromkeys", "join"}

# Delimiters a member list may be written with. Trying them costs
# nothing on prose, because a string is only read as a list when *every*
# piece of it is a declared term -- see ``_pieces``.
_DELIMITERS: tuple[str | None, ...] = (None, ",", ";", "|", "/")


def _folded(node: ast.AST) -> str | None:
    """The string an expression spells, if it spells one outright.

    Constant addition is folded: splitting a literal across a ``+`` does
    not make it less of a literal, so ``"plo" + "sive"`` states
    ``plosive``. So is ``chr()`` of a literal code point, for the same
    reason: ``chr(0x361)`` states the over-tie as plainly as pasting the
    combining character does, and a guard that read only one of the two
    spellings would be a guard against typing style. So is an f-string
    whose every piece folds: ``f"{chr(0x361)}"`` interpolates nothing a
    reader could not have typed.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        pieces = [
            _folded(part.value if isinstance(part, ast.FormattedValue) else part)
            for part in node.values
        ]
        if pieces and all(piece is not None for piece in pieces):
            return "".join(piece for piece in pieces if piece is not None)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "chr"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, int)
    ):
        return chr(node.args[0].value)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _folded(node.left), _folded(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _delimiters(node: ast.AST) -> tuple[str | None, ...]:
    """The delimiters to try: the usual ones, plus any the source names."""
    named = [
        arg.value
        for sub in ast.walk(node)
        if isinstance(sub, ast.Call)
        and isinstance(sub.func, ast.Attribute)
        and sub.func.attr in {"split", "rsplit"}
        for arg in sub.args
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
    ]
    return (*_DELIMITERS, *named)


def _pieces(text: str, vocabulary: set[str], seps: tuple[str | None, ...]) -> list[str]:
    """``text`` read as a delimited member list, or ``[]`` if it is not one.

    A member list is *nothing but* declared terms joined by a delimiter.
    Requiring every piece to be declared is what separates
    ``"stress length tone"`` from a sentence that happens to mention two
    declared words, and it is what makes the choice of delimiter free:
    ``,`` and ``|`` can be tried without reading prose as members.
    """
    for sep in seps:
        parts = [p for p in (text.split() if sep is None else text.split(sep)) if p]
        if len(parts) >= 2 and all(p in vocabulary for p in parts):
            return parts
    return []


def _terms(node: ast.AST, vocabulary: set[str]) -> list[str]:
    """Every string an expression states, plus the pieces of a delimited one.

    Container-agnostic, because a value enumeration restates the same
    fact whether it is spelled as a set, as a sequence, or as one
    delimited string a caller will ``.split()`` at the use site.
    """
    seps = _delimiters(node)
    out: list[str] = []
    for sub in ast.walk(node):
        text = _folded(sub)
        if text is not None:
            out.append(text)
            out += _pieces(text, vocabulary, seps)
    return out


def _is_unordered(node: ast.AST) -> bool:
    """Whether an expression builds an unordered collection.

    Decided from the *outermost* node rather than by hunting for a
    literal anywhere inside, so `frozenset(x.split())`, `dict(zip(...))`
    and a set comprehension are all recognized. A method spelling counts
    the same way: `dict.fromkeys` builds a mapping, and a compiled
    alternation or character class puts everything it matches in one
    class, which is the classification itself.
    """
    if isinstance(node, ast.Set | ast.Dict | ast.SetComp | ast.DictComp):
        return True
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _SET_BUILDERS
    ):
        return True
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in _UNORDERED_METHODS
    ):
        return True
    if isinstance(node, ast.BinOp):  # set algebra: A | B, A - B
        return _is_unordered(node.left) or _is_unordered(node.right)
    if isinstance(node, ast.Subscript):
        return _is_unordered(node.value)
    return False


def _is_ordered(node: ast.AST) -> bool:
    """Whether an expression builds a sequence.

    The mirror of ``_is_unordered``, read from the outermost node for
    the same reason. A sequence is still a container: ``["ˈ", "ˌ"]`` is
    every bit the per-symbol table that ``{"ˈ", "ˌ"}`` is. What an order
    buys is the *classification* exemption below, not exemption from the
    guard.
    """
    if isinstance(node, ast.List | ast.Tuple | ast.ListComp | ast.GeneratorExp):
        return True
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _SEQ_BUILDERS
    ):
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return node.func.attr in _SEQ_METHODS
    if isinstance(node, ast.BinOp):  # sequence concatenation: A + B
        return _is_ordered(node.left) or _is_ordered(node.right)
    if isinstance(node, ast.Subscript):
        return _is_ordered(node.value)
    return False


def _candidates(node: ast.AST, vocabulary: set[str]) -> list[str]:
    """Every string an expression could contribute as a member.

    Deliberately generous about *how* a string is spelled, because the
    shape of the container is what the classification is, not the syntax
    that fills it: a symbol reached through `chr()`, a name list written
    as `"a b c".split()`, and the characters of a string handed to
    `set()` are all members of the collection they build.
    """
    out = _terms(node, vocabulary)
    for sub in ast.walk(node):
        if (
            isinstance(sub, ast.Call)
            and isinstance(sub.func, ast.Name)
            and sub.func.id == "chr"
            and len(sub.args) == 1
            and isinstance(sub.args[0], ast.Constant)
            and isinstance(sub.args[0].value, int)
        ):
            out.append(chr(sub.args[0].value))
        elif isinstance(sub, ast.Call) and (
            (isinstance(sub.func, ast.Name) and sub.func.id in _ITERATING)
            or (
                isinstance(sub.func, ast.Attribute)
                and sub.func.attr in _ITERATING_METHODS
            )
        ):
            for arg in sub.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    out += list(arg.value)  # set("ǀǁǂǃ") is four members
        elif isinstance(sub, ast.Starred):
            # `{*"ˈˌ"}` asks for the characters in the syntax itself, so
            # expanding them here reads nothing into the source that the
            # source did not write. A bare `"ˈˌ"` still escapes: nothing
            # there says to split it.
            text = _folded(sub.value)
            if text is not None:
                out += list(text)
    return out


def _members(node: ast.AST, vocabulary: set[str]) -> list[str]:
    """The strings a node collects, in a container of any kind.

    A container is a claim about what belongs together, and a table of
    registered symbols makes that claim whether it is written as a set,
    as a sequence, or as one delimited string.
    """
    if _is_unordered(node) or _is_ordered(node):
        return _candidates(node, vocabulary)
    text = _folded(node)
    if text is not None:  # a delimited string is a sequence written out
        return _pieces(text, vocabulary, _delimiters(node))
    return []


def _classified(node: ast.AST, vocabulary: set[str]) -> list[str]:
    """The strings a node puts into one *class*.

    An unordered container classifies whatever it holds -- keys and
    values alike, since a table mapping a mode to its symbols smuggles
    exactly as much as one mapping each symbol to its mode. A sequence
    classifies nothing: it states an order, and where feature names go
    in a sentence is a rendering decision the code is allowed to make.
    """
    if not _is_unordered(node):
        return []
    return _candidates(node, vocabulary)


def _bindings(target: ast.expr, value: ast.expr) -> list[tuple[str, ast.expr]]:
    """The names an assignment target binds, with what each is bound to.

    Unpacking pairs elementwise when both sides are written out, and
    otherwise attributes the whole right-hand side to every name. A
    subscript assignment binds no new name but adds an entry to the
    table it names, so ``_TABLE["ˀ"] = "release"`` is read as the
    one-entry mapping it is: a table filled a statement at a time is
    still the table.
    """
    if isinstance(target, ast.Name):
        return [(target.id, value)]
    if isinstance(target, ast.Starred):
        return _bindings(target.value, value)
    if isinstance(target, ast.Tuple | ast.List):
        parts: list[ast.expr] | None = None
        if isinstance(value, ast.Tuple | ast.List) and len(value.elts) == len(
            target.elts
        ):
            parts = value.elts
        out: list[tuple[str, ast.expr]] = []
        for i, elt in enumerate(target.elts):
            out += _bindings(elt, value if parts is None else parts[i])
        return out
    if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name):
        return [(target.value.id, ast.Dict(keys=[target.slice], values=[value]))]
    return []


_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _module_constants(source: str) -> list[tuple[str, ast.expr]]:
    """Every name bound at module level, with the expression bound to it.

    Descends into module-level ``if``/``try``/``with``/``for`` bodies --
    a constant behind a version check or an ``except`` fallback is still
    a module constant -- but not into class or function bodies, which
    are a documented escape. Augmented assignment and a module-level
    walrus bind a name too, and are collected for the same reason.
    """
    out: list[tuple[str, ast.expr]] = []

    def visit(body: list[ast.stmt]) -> None:
        for stmt in body:
            if isinstance(stmt, _SCOPES):
                continue
            if isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    out.extend(_bindings(target, stmt.value))
            elif isinstance(stmt, ast.AnnAssign | ast.AugAssign):
                if stmt.value is not None:
                    out.extend(_bindings(stmt.target, stmt.value))
            for child in ast.iter_child_nodes(stmt):
                if not isinstance(child, ast.expr):
                    continue
                for sub in ast.walk(child):
                    if isinstance(sub, ast.NamedExpr) and isinstance(
                        sub.target, ast.Name
                    ):
                        out.append((sub.target.id, sub.value))
            for field in ("body", "orelse", "finalbody"):
                nested = getattr(stmt, field, None)
                if isinstance(nested, list):
                    visit([s for s in nested if isinstance(s, ast.stmt)])
            for handler in getattr(stmt, "handlers", []):
                visit(handler.body)

    visit(ast.parse(source).body)
    return out


@pytest.fixture(scope="module")
def declared(ipa: IPAFeatures) -> dict[str, set[str]]:
    """What ipa.xml declares, as three vocabularies the guard tests against.

    The symbols come from ``invariants.declared_symbols`` rather than
    from a list of tables written out here. That is not tidiness: this
    fixture named four tables by hand and ``<zeros>`` was not one of
    them, so ``ZERO = "∅"`` -- the lone-declared-glyph shape the guard
    was extended to catch for the tie bars -- walked straight through
    the guard that names it. One enumeration of the element classes
    means the next class added to ``<classes>`` cannot open the hole
    again. The alias spellings are added on top because they are not an
    element class: they are input the package documents as accepted, and
    a table keyed off one restates the inventory just as plainly.
    """
    type_values = {v for vals in ipa.types.values() for v in vals}
    values = {
        v
        for feat in ipa.features.values()
        for v in (set(feat.values) | set(feat.value_aliases))
    } - type_values
    return {
        "values": values,
        "names": set(ipa.features),
        "symbols": set(declared_symbols(ipa)) | set(ipa.ligature_map),
    }


def test_the_symbol_vocabulary_covers_every_element_class(
    ipa: IPAFeatures, declared: dict[str, set[str]]
) -> None:
    """Nothing the loader routes is outside what the guard can see.

    The converse of the fixture's derivation, asserted so a table the
    guard reads and an element class the loader fills cannot come apart.
    """
    for table in (ipa.phones, ipa.diacritics, ipa.separators, ipa.zeros):
        assert table, "an element class loaded empty: the sweep would be vacuous"
        assert set(table) <= declared["symbols"]


def offenders(source: str, declared: dict[str, set[str]]) -> list[str]:
    """Module-level constants in ``source`` that restate the data."""
    vocabulary = declared["values"] | declared["names"] | declared["symbols"]
    found = []
    for name, value in _module_constants(source):
        literals = set(_terms(value, vocabulary))
        classified = set(_classified(value, vocabulary))
        members = set(_members(value, vocabulary))
        if len(literals & declared["values"]) >= 2:
            found.append(
                f"{name}: enumerates declared feature values "
                f"{sorted(literals & declared['values'])}"
            )
        elif len(classified & declared["names"]) >= 2:
            found.append(
                f"{name}: classifies declared features "
                f"{sorted(classified & declared['names'])}"
            )
        elif members & declared["symbols"]:
            found.append(
                f"{name}: keys off registered symbols "
                f"{sorted(members & declared['symbols'])}"
            )
        elif _folded(value) in declared["symbols"]:
            found.append(f"{name}: spells the registered symbol {_folded(value)!r}")
    return found


_GUARDED = sorted(p for p in _PACKAGE.rglob("*.py"))

#: Constants that restate the data on purpose, each with the reason. The
#: house rule is that a smuggle has to be justified and declared, not
#: that none may exist, and this is where the declaration lives -- next
#: to the predicate, where a reader checks whether something got past it.
#: Pinned in both directions by the two tests below, so a justification
#: cannot outlive the thing it justifies.
_JUSTIFIED = {
    ("rules.py", "NULL"): (
        "The rule notation for the empty string, and the declaration runs "
        "the other way round: '∅' was the notation first and <zeros> "
        "registered the same glyph afterwards, knowing it -- ipa.xml says "
        "so where it declares the zero. Reading NULL off "
        "IPAFeatures.zeros would make a second declared zero an accepted "
        "empty-string spelling on both sides of every arrow, silently "
        "changing what four shipped rule sets mean; _zero_named refuses a "
        "second zero rather than guess for the same reason. The coupling "
        "that matters is pinned instead, one test below: the declared "
        "zero and the notation agree today, and a change to either fails "
        "rather than drifts."
    ),
}


def _offender_name(finding: str) -> str:
    return finding.split(":", 1)[0]


def test_each_justified_smuggle_is_still_a_smuggle(
    declared: dict[str, set[str]],
) -> None:
    """A justification with nothing left to justify is stale prose.

    If one of these stops being an offender -- derived at last, or
    deleted -- this fails and the entry comes out, so the exemption list
    can only shrink deliberately.
    """
    assert _JUSTIFIED, "the exemption list is empty: this test is vacuous"
    for (relative, name), reason in _JUSTIFIED.items():
        path = _PACKAGE / relative
        assert path in _GUARDED, relative
        found = offenders(path.read_text(encoding="utf-8"), declared)
        assert name in {_offender_name(f) for f in found}, f"{relative}: {name}"
        assert reason.strip(), f"{relative}: {name} is exempted without a reason"


def test_the_rule_notation_and_the_declared_zero_agree(ipa: IPAFeatures) -> None:
    """The coupling ``rules.NULL`` is exempted from deriving.

    Two independent statements about one glyph: ``<zeros>`` declares it a
    symbol, and ``rules.py`` accepts it as the empty string. Neither is
    derived from the other, on the reason recorded in ``_JUSTIFIED``, so
    the agreement is asserted here -- a change to the declared zero, or a
    second one, fails loudly instead of leaving the notation behind.
    """
    from ipakit.rules import NULL

    assert set(ipa.zeros) == set(ipa.zeros) & NULL
    assert len(ipa.zeros) == 1, "a second zero: rules.NULL has to say which it means"


# The tables this package actually shipped, each removed by the commits
# these tests accompany. The guard has to reject every one of them, or it
# is only a description of today's source.
_SMUGGLED = [
    '_ORAL_OBSTRUENT = frozenset({"plosive", "fricative", "affricate"})',
    '_MODE_EXCEPTIONS = {"ˀ": "release", "ᵊ": "release"}',
    '_STRESS_MARKERS = {"ˈ": 1, "ˌ": 2}',
    '_PROSODIC_KEYS = frozenset({"stress", "length", "tone", "contour"})',
    '_OVERRIDING_KEYS = frozenset({"voiced", "place", "manner", "syllabic"})',
    '_SECONDARY_KEYS = frozenset({"palatalized", "labialized", "velarized"})',
    'SECONDARY_PLACE = {"palatalized": "palatal", "labialized": "bilabial"}',
    '_EXCLUDED_KEYS = METADATA_ATTRS | {"class", "place", "nasalized"}',
    '_BINARY_LABELS = {"channel": {"lateral": "lateral", "grooved": "sibilant"}}',
    # Shapes never shipped, but the same mistake spelled differently.
    # Each of these slipped past the first version of the guard: the
    # first is _MODE_EXCEPTIONS with its keys and values swapped.
    '_MODE_EXCEPTIONS = {"release": ("ˀ", "ᵊ")}',
    '_CLICK_SYMBOLS = set("ǀǁǂǃ")',
    '_MODE_BY_SYMBOL = dict(zip("ˀᵊ", ("release", "release")))',
    "_STRESS_MARKERS = {chr(0x2C8): 1, chr(0x2CC): 2}",
    '_PROSODIC_KEYS = frozenset("stress length tone contour step global".split())',
    '_SECONDARY_KEYS = frozenset(k for k in ("palatalized", "labialized"))',
    '_OVERRIDING_KEYS = frozenset(["voiced", "place", "manner", "syllabic"][:])',
    '_SONORANTS = set(["nasal", "trill", "approximant"])',
    '_TONES = {"low": 1, "mid": 2, "high": 3}',
    # Spelling is not a defense. Each of these is one of the tables
    # above wearing different syntax, and each slipped past the second
    # version of the guard -- including the stress table this file
    # names as its own worked example.
    '_STRESS_MARKERS = ["ˈ", "ˌ"]',
    '_STRESS_MARKERS = ("ˈ", "ˌ")',
    '_STRESS_MARKERS = "ˈ ˌ"',
    '_STRESS_MARKERS = "ˈ,ˌ"',
    '_STRESS_MARKERS, _TONE_MARKS = {"ˈ", "ˌ"}, {"˥", "˩"}',
    '_ORAL_OBSTRUENT = frozenset("plosive fricative affricate".split())',
    '_ORAL_OBSTRUENT = frozenset({"plo" + "sive", "frica" + "tive"})',
    '_PROSODIC_KEYS = frozenset("stress,length,tone".split(","))',
    "if sys.version_info >= (3, 12):\n" '    _MODE_EXCEPTIONS = {"ˀ": "release"}',
    "try:\n"
    '    _PROSODIC_KEYS = frozenset({"stress", "length", "tone"})\n'
    "except NameError:\n"
    "    _PROSODIC_KEYS = frozenset()",
    '_MODE_EXCEPTIONS = {}\n_MODE_EXCEPTIONS["ˀ"] = "release"',
    "_PROSODIC_KEYS = frozenset()\n" '_PROSODIC_KEYS |= {"stress", "length", "tone"}',
    '(_PROSODIC_KEYS := frozenset({"stress", "length", "tone"}))',
    # Not a table, and shipped for as long as any of them: one declared
    # glyph, alone, in a bare string. `ipa.xml` declares a `tie` feature
    # spelled by these two marks, so naming either in Python is the same
    # claim `_MODE_EXCEPTIONS` made about `\u02c0`, minus the container
    # that used to be what gave it away. The `chr` spelling is the same
    # constant with the combining character typed out of harm's way.
    'TIE_BAR = "\u0361"',
    'SEQ_TIE = "\u035c"',
    "TIE_BAR = chr(0x361)",
    # The same lone-glyph shape for the zero, and the tables around it.
    # `<zeros>` is an element class like any other and was missing from
    # the vocabulary the guard tests against, so the shape this file
    # narrates closing for the tie bars was still open for `\u2205` -- caught
    # now because the vocabulary is the loader's own enumeration rather
    # than a list of tables typed out here.
    'ZERO = "\u2205"',
    '_ZEROS = {"\u2205": "deletion", "0": "deletion"}',
    '_NULL = frozenset({"\u2205", "0", "\u00d8"})',
    # A literal wrapped in a call the member analysis did not recognize
    # walked through it whole, whatever was inside. These are the
    # realistic wrappers: a compiled alternation or character class puts
    # its members in one class exactly as a set does, `join` and
    # `fromkeys` consume a sequence, and an f-string of constants
    # interpolates nothing.
    '_STRESS_MARKERS = re.compile("\u02c8|\u02cc")',
    '_STRESS_MARKERS = "".join(["\u02c8", "\u02cc"])',
    '_STRESS_MARKERS = dict.fromkeys("\u02c8\u02cc")',
    '_STRESS_MARKERS = {*"\u02c8\u02cc"}',
    '_PROSODIC_KEYS = re.compile("stress|length|tone")',
    'TIE_BAR = f"{chr(0x361)}"',
]


def _label(source: str) -> str:
    """A one-line id for a case that may be several statements long."""
    return " ".join(source.split(" =")[0].split())


@pytest.mark.parametrize("source", _SMUGGLED, ids=_label)
def test_the_guard_rejects_the_tables_that_were_removed(
    source: str, declared: dict[str, set[str]]
) -> None:
    assert offenders(source, declared), f"guard missed: {source}"


def test_the_guard_spares_what_is_not_a_phonetic_fact(
    declared: dict[str, set[str]],
) -> None:
    # A rendering order, algorithm parameters, and a set of this
    # library's own classifications are not claims about phonetics. A
    # string that is *not* a registered symbol is not one either, however
    # glyph-like it looks -- `\u00d8` is one of the spellings `rules.NULL`
    # accepts for the empty string and is declared by nothing. The empty
    # set `\u2205` used to stand here making that point and no longer can:
    # `<zeros>` declares it, and the guard reads `<zeros>` now.
    for source in [
        '_MODIFIER_READ_ORDER = ("palatalized", "syllabic", "channel")',
        '_NOT_A_SYMBOL = "\u00d8"',
        "GAP_COST = 1.0",
        "ORDERED_KINDS = frozenset({Kind.AFFRICATE, Kind.DIPHTHONG})",
        "_JSON_VERSION = 1",
    ]:
        assert offenders(source, declared) == [], source


def test_the_comparison_escape_is_load_bearing(
    declared: dict[str, set[str]],
) -> None:
    """Why the comparison shape is not closed, measured rather than said.

    The counting rule, stated because a count is only as good as it:
    every ``ast.Compare`` in the package with a string literal on either
    side that is a declared symbol or a declared feature *value*. Feature
    *names* are excluded -- a bundle is keyed by name, so ``key ==
    "place"`` is a lookup rather than a claim about phonetics.

    A floor rather than an equality: the reason to keep the escape open
    is that the shape is common and mostly the vowel test, and that
    stops being true only if the number collapses. If it does, this
    fails and the escape is worth closing.
    """
    vocabulary = declared["values"] | declared["symbols"]
    comparisons = []
    for path in _GUARDED:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            operands = [node.left, *node.comparators]
            if any((_folded(o) or "") in vocabulary for o in operands):
                comparisons.append((path.name, ast.unparse(node)))
    assert len(comparisons) > 15, "the comparison shape is no longer common"
    vowel = [c for _, c in comparisons if '"vowel"' in c or "'vowel'" in c]
    assert vowel, "the vowel test is the escape's stated reason and is not there"
    """The escapes, pinned so they stay known rather than assumed shut.

    A guard that quietly stops covering a shape is worse than none,
    because it reads as protection. These are the shapes that get past
    it, asserted as getting past it: if one starts being caught, this
    fails and the docstring above needs updating.
    """
    escapes = [
        # A sequence of feature *names* states an order rather than a
        # class, and three legitimate ones exist. The delimited-string
        # spelling of one is a sequence too, and spared for the same
        # reason. Ordered *symbols* are caught -- see `_SMUGGLED`.
        '_ORDER = ["palatalized", "labialized", "velarized"]',
        '_ORDER = "palatalized labialized velarized"',
        # Not a module-level assignment at all.
        "class C:\n    KEYS = {'voiced', 'place', 'manner'}",
        "def f():\n    KEYS = {'voiced', 'place', 'manner'}",
        # A fact spelled as control flow rather than as data, in either
        # of the two spellings Python offers for it. `match`/`case` is
        # here for the same reason `if`/`elif` is: the guard reads
        # module-level constants, and a fact written as a branch is not
        # one wherever it sits.
        "def mode(sym):\n"
        "    if sym == 'ˀ':\n        return 'release'\n"
        "    elif sym == 'ᵊ':\n        return 'release'",
        "def mode(sym):\n"
        "    match sym:\n"
        "        case 'ˀ':\n            return 'release'\n"
        "        case 'ᵊ':\n            return 'release'",
        # The same shape with a declared *value* in place of a symbol.
        # `describe` shipped one of these: `if airstream != "pulmonic"`
        # named the default instead of reading it, and would have gone
        # quiet the moment the data moved it. It now reads
        # `features["airstream"].default`, but the shape stays invisible
        # here, and deliberately: the guard looks at module-level
        # constants, so a comparison escapes wherever it sits, and
        # widening it to comparisons would reject the eleven
        # `manner == "vowel"` tests the library is built on along with
        # it.
        'def f(feats):\n    return feats["airstream"] != "pulmonic"',
        # A run of glyphs with nothing to split on. Expanding every
        # string to its characters would read "stress" as s, t, r, e.
        # A regex character class is the same run wearing brackets: the
        # alternation spelling of it *is* caught, because `|` is a
        # delimiter the guard tries.
        '_STRESS_MARKERS = "ˈˌ"',
        '_STRESS_MARKERS = re.compile("[ˈˌ]")',
        # Indirection: nothing is resolved across statements, so a table
        # whose keys are names states nothing this can read. Narrower
        # than it was: the two assignments that used to stand above it,
        # binding these names to ˈ and ˌ, are each caught on their own
        # now (a lone declared glyph is an offender -- see `_SMUGGLED`),
        # so the escape needs the glyph bound where the guard does not
        # look.
        "_STRESS_MARKERS = {_PRIMARY: 1, _SECONDARY: 2}",
        # A delimiter the source never names and the guard does not
        # guess, with the split deferred to the use site.
        '_PROSODIC_KEYS = "stress~length~tone"',
    ]
    for source in escapes:
        assert (
            offenders(source, declared) == []
        ), f"now caught, so the documented escapes are stale: {source}"


@pytest.mark.parametrize("path", _GUARDED, ids=lambda p: p.name)
def test_no_module_level_constant_restates_the_data(
    path: Path, declared: dict[str, set[str]]
) -> None:
    """A module-level constant may not enumerate what ipa.xml declares.

    Three shapes fail, each one a real defect this package has shipped:

    * a **value enumeration** -- two or more declared feature values in
      one constant (``_ORAL_OBSTRUENT``, ``SECONDARY_PLACE``'s places,
      ``_BINARY_LABELS``' channel values). The data declares what the
      values are and what they mean; a second copy in Python is a fact
      that can go stale. The container does not matter here: a list
      restates as much as a set.
    * a **feature classification** -- an *unordered* container (set,
      frozenset, dict keys) holding two or more declared feature names
      (``_PROSODIC_KEYS``, ``_SECONDARY_KEYS``, ``_OVERRIDING_KEYS``).
      Which features are prosodic is a property of the features, so it
      belongs on them, as ``mode=``.
    * a **per-symbol table** -- a registered symbol used as a member of
      a container of *any* kind, or as a dict key (``_MODE_EXCEPTIONS``,
      ``mapper._STRESS_MARKERS``). Classifying ``ˀ`` by its glyph is the
      purest form of the mistake: the symbol is in the data already, and
      so is everything true of it.
    * a **lone declared glyph** -- one registered symbol, alone, in a
      bare string (``constants.TIE_BAR``, ``SEQ_TIE``). No container and
      nothing to count, so all three shapes above missed it, and it was
      spared here on the argument that the tokenizer has to know the tie
      characters before it can read anything that would tell it. The
      argument is false: what the data declares is readable as soon as
      the data is loaded, which is before anything is tokenized -- the
      glyphs are ``IPAFeatures.tie_bars`` now. ``chr()`` of a code point
      is the same constant and is folded to it.

    Spelling is not a defense. A constant counts however it is written:
    as a set or as a sequence, unpacked from a tuple, bound behind a
    module-level ``if`` or ``try``, filled one subscript at a time,
    extended with ``|=``, bound by a walrus, concatenated out of
    fragments, or joined into a single delimited string for the use site
    to ``.split()``. A string is read as a member list only when *every*
    piece of it is a declared term, so prose that happens to mention two
    of them stays prose.

    Deliberately *not* caught, so read this before trusting it:

    * an **ordered** list, tuple or delimited string of feature *names*.
      It states where names go in a sentence, not what class they are,
      and three legitimate ones exist: ``_MODIFIER_READ_ORDER``,
      ``_CONSONANT_SLOTS``, ``_VOWEL_SLOTS``.
      ``TestTheOrderingTupleCanOnlyOrder`` above pins the first so it
      can only order what the data already admits. Ordered *symbols*
      are caught: which glyphs belong together is not a rendering
      decision.
    * constants inside a class or function body.
    * anything outside ``ipakit/``. The walk is the package on purpose,
      not for want of trying the rest: a fixture that pins how ``ʰ``
      tokenizes has to write ``ʰ``, and a generator's curated override
      table exists to make the human judgment explicit. Both *fail*
      when the data moves under them, which is the opposite of the
      quiet staleness this guard is for. Run over ``scripts/`` and
      ``tests/`` today it reports four constants in two scripts and
      twenty-two in fourteen test modules, and every one of them is a
      corpus. What those two directories genuinely owed the data --
      three inline copies that had already drifted from a constant they
      were written from -- is fixed by importing the declaration
      instead, which is a stronger guarantee than a walk.
    * a fact spelled as a comparison -- an ``if``/``elif`` chain, a
      ``match``/``case``, or a single ``==`` against a declared symbol or
      value name. Comparisons of that shape are load-bearing throughout
      the package, most of them the vowel/consonant test a description's
      own sentence turns on, so this cannot be closed without rejecting
      them too. ``test_the_comparison_escape_is_load_bearing`` counts
      them against the source rather than quoting a number here, which
      is a figure nothing regenerates.
    * a run of glyphs with nothing to split on (``"ˈˌ"``). Expanding
      every string to its characters would read ``"stress"`` as the
      phones s, t, r, e.
    * a delimiter neither in ``_DELIMITERS`` nor named at a ``.split()``
      in the same expression.
    * indirection: ``{_PRIMARY: 1}`` where ``_PRIMARY = "ˈ"``. Nothing is
      resolved across statements, and a name is not a literal.
    * anything read from a file at import.

    ``test_the_guard_states_what_it_cannot_see`` asserts each of those
    still escapes, so this list cannot go stale in either direction.
    """
    relative = str(path.relative_to(_PACKAGE))
    found = [
        f
        for f in offenders(path.read_text(encoding="utf-8"), declared)
        if (relative, _offender_name(f)) not in _JUSTIFIED
    ]
    assert found == [], f"{relative}: " + "; ".join(found)
