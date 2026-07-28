"""Phonetic facts live in ipa.xml, not in Python constants.

The house rule: code the necessary features in the data or derive them
there; do not smuggle them in by hardcoding. Three tables used to break
it -- ``_MODE_EXCEPTIONS`` classified two diacritics *by symbol*,
``SECONDARY_PLACE``/``_SECONDARY_KEYS``/``_SECONDARY_DESC_ORDER`` were
three independent copies of one five-member set in three modules, and
``_BINARY_LABELS`` decided that ``channel=grooved`` reads "sibilant".

Two kinds of test here. The pins assert the derived reads still say what
the hardcoded tables said. The guard is a predicate over the source: it
looks for the *shape* of a smuggled constant rather than for today's
names, so a new one fails too.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from ipakit import IPAFeatures
from ipakit.analysis import _MODIFIER_READ_ORDER, _PRIMARY_SLOTS
from ipakit.metric import excluded_keys
from ipakit.segment import _OBSTRUENT, modifier_mode

_PACKAGE = Path(__file__).resolve().parent.parent / "ipakit"


@pytest.fixture(scope="module")
def ipa() -> IPAFeatures:
    return IPAFeatures()


class TestTheDataSaysWhatThePythonUsedTo:
    """Each derived read reproduces the table it replaced, exactly."""

    def test_the_mode_partition(self, ipa: IPAFeatures) -> None:
        by_mode = {m: set(v) for m, v in ipa.features_by_mode.items()}
        assert by_mode["structural"] == {"tie", "linking", "break"}
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
        assert by_mode["overriding"] == {"voiced", "place", "manner", "syllabic"}

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
            set(METADATA_ATTRS) | {"place", "nasalized"} | set(ipa.secondary_places)
        )

    def test_the_bridges(self, ipa: IPAFeatures) -> None:
        assert ipa.bridges == {
            "nasality": (("manner", "nasal"), ("nasalized", "+"), ("release", "nasal")),
            "laterality": (("channel", "lateral"), ("release", "lateral")),
        }

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


# ---------------------------------------------------------------------------
# The guard
# ---------------------------------------------------------------------------

_UNORDERED = (ast.Set, ast.Dict)
_SET_BUILDERS = {"set", "frozenset", "dict"}


def _strings(node: ast.AST) -> list[str]:
    """Every string literal anywhere in an expression."""
    return [
        n.value
        for n in ast.walk(node)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    ]


def _membership(node: ast.AST) -> list[str]:
    """The string literals a node offers as *membership*: set elements,
    dict keys, and the elements of a set()/frozenset()/dict() call. A
    sequence (list/tuple) offers none -- it states an order, not a class."""
    out: list[str] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Set):
            out += [
                e.value
                for e in sub.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)
            ]
        elif isinstance(sub, ast.Dict):
            out += [
                k.value
                for k in sub.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)
            ]
        elif (
            isinstance(sub, ast.Call)
            and isinstance(sub.func, ast.Name)
            and sub.func.id in _SET_BUILDERS
        ):
            for arg in sub.args:
                if isinstance(arg, ast.List | ast.Tuple | ast.Set):
                    out += [
                        e.value
                        for e in arg.elts
                        if isinstance(e, ast.Constant) and isinstance(e.value, str)
                    ]
    return out


def _module_constants(source: str) -> list[tuple[str, ast.AST]]:
    tree = ast.parse(source)
    out: list[tuple[str, ast.AST]] = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and node.value is not None:
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            out += [(n, node.value) for n in names]
        elif (
            isinstance(node, ast.AnnAssign)
            and node.value is not None
            and isinstance(node.target, ast.Name)
        ):
            out.append((node.target.id, node.value))
    return out


@pytest.fixture(scope="module")
def declared(ipa: IPAFeatures) -> dict[str, set[str]]:
    """What ipa.xml declares, as three vocabularies the guard tests against."""
    type_values = {v for vals in ipa.types.values() for v in vals}
    values = {
        v
        for feat in ipa.features.values()
        for v in (set(feat.values) | set(feat.value_aliases))
    } - type_values
    return {
        "values": values,
        "names": set(ipa.features),
        "symbols": set(ipa.phones)
        | set(ipa.diacritics)
        | set(ipa.separators)
        | set(ipa.ligature_map),
    }


def offenders(source: str, declared: dict[str, set[str]]) -> list[str]:
    """Module-level constants in ``source`` that restate the data."""
    found = []
    for name, value in _module_constants(source):
        literals = set(_strings(value))
        members = set(_membership(value))
        if len(literals & declared["values"]) >= 2:
            found.append(
                f"{name}: enumerates declared feature values "
                f"{sorted(literals & declared['values'])}"
            )
        elif len(members & declared["names"]) >= 2:
            found.append(
                f"{name}: classifies declared features "
                f"{sorted(members & declared['names'])}"
            )
        elif members & declared["symbols"]:
            found.append(
                f"{name}: keys off registered symbols "
                f"{sorted(members & declared['symbols'])}"
            )
    return found


_GUARDED = sorted(p for p in _PACKAGE.rglob("*.py"))

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
    '_SONORANTS = set(["nasal", "trill", "approximant"])',
    '_TONES = {"low": 1, "mid": 2, "high": 3}',
]


@pytest.mark.parametrize("source", _SMUGGLED, ids=lambda s: s.split(" =")[0])
def test_the_guard_rejects_the_tables_that_were_removed(
    source: str, declared: dict[str, set[str]]
) -> None:
    assert offenders(source, declared), f"guard missed: {source}"


def test_the_guard_spares_what_is_not_a_phonetic_fact(
    declared: dict[str, set[str]],
) -> None:
    # A bare glyph constant (the tokenizer's bootstrap), a rendering
    # order, algorithm parameters, and a set of this library's own
    # classifications are not claims about phonetics.
    for source in [
        'TIE_BAR = "\u0361"',
        '_MODIFIER_READ_ORDER = ("palatalized", "syllabic", "channel")',
        "GAP_COST = 1.0",
        "ORDERED_KINDS = frozenset({Kind.AFFRICATE, Kind.DIPHTHONG})",
        "_JSON_VERSION = 1",
    ]:
        assert offenders(source, declared) == [], source


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
      that can go stale.
    * a **feature classification** -- an unordered container (set,
      frozenset, dict keys) holding two or more declared feature names
      (``_PROSODIC_KEYS``, ``_SECONDARY_KEYS``, ``_OVERRIDING_KEYS``).
      Which features are prosodic is a property of the features, so it
      belongs on them, as ``mode=``.
    * a **per-symbol table** -- a registered symbol used as a container
      member or dict key (``_MODE_EXCEPTIONS``, ``mapper._STRESS_MARKERS``).
      Classifying ``ˀ`` by its glyph is the purest form of the mistake:
      the symbol is in the data already, and so is everything true of it.
      Naming a single glyph is not a table and is spared -- the tokenizer
      has to know the tie characters (``constants.TIE_BAR``) before it can
      read anything that would tell it.

    Deliberately *not* caught, so read this before trusting it: an
    ordered list or tuple of feature names states an order rather than a
    class, and is spared -- ``_MODIFIER_READ_ORDER`` is one, and
    ``TestTheOrderingTupleCanOnlyOrder`` above pins it so it can only
    order what the data already admits. Also uncaught: constants inside a
    class or function body, a fact spelled as an ``if``/``elif`` chain
    rather than a container, and anything read from a file at import.
    """
    found = offenders(path.read_text(encoding="utf-8"), declared)
    assert found == [], f"{path.name}: " + "; ".join(found)
