"""Context-sensitive rewrite rules over IPA forms.

A rule is the classic generative statement ``A -> B / C _ D``: rewrite
``A`` as ``B`` when it stands between ``C`` and ``D``. This module gives
that a typed representation, a small notation that builds one, and an
ordered engine that applies a sequence of them.

The two halves are separable, and that is the main structural claim
here. A :class:`Query` is the left-hand side: it *recognizes*, turning a
form into the :class:`Site` list where the rule's environment holds. An
:class:`Action` is the right-hand side: it *acts*, turning a site into
an :class:`Edit`. A :class:`Rule` is their composition, and the trace is
simply the edits kept rather than discarded. Recognition is useful on
its own -- "where in this corpus does a plosive stand between vowels" is
a question with no rewrite attached -- so it is reachable without one.

The decisions below are each worth stating, because each is a place the
obvious implementation is wrong. They are counted by their headings and
not in this sentence, which said "three" while there were four.

**Stress is not part of a phone's identity.** ``features("a")``,
``features("ˈa")`` and ``features("aː")`` are the same bundle: the six
``mode="prosodic"`` features live on the unit, outside the feature bag
(docs/ties.md). So the pattern ``a`` matches a stressed ``ˈa``, which is
what a rule about the vowel /a/ should do. Prosody is a second
*namespace*, not a second phone, and it is both askable and writable in
it: ``[vowel stress=primary]`` matches only the stressed one,
``[stress=primary]`` assigns it, ``[stress=∅]`` clears it. A term is
routed to whichever namespace declares it, read off ``Feature.mode``, so
no list of prosodic feature names is restated here.

A literal may name prosody on either side, and on the left it is an
*additional* constraint rather than part of the identity: ``aː`` is "the
phone ``a``, bearing ``length=long``", so ``a`` goes on matching ``ˈa``
while ``aː`` matches only the long one. On the right a literal spells a
whole unit, so the target's prosody is carried across except where one of
the two sides named it -- which is what makes ``aː -> a`` shorten rather
than do nothing, while ``t -> ʔ`` still leaves ``tː`` long.

**A syllable break is transparent to context.** The dot is optional
notation: ``bʌtɚ`` and ``bʌ.tɚ`` are the same word. If ``.`` blocked a
context, flapping would fire on one spelling and not the other, so the
same word would get two answers depending on whether someone typed the
dots. Separators are therefore stepped over when scanning context
*unless a rule names one*. Which are transparent is read from the
declared ``level``: ``syllable`` is optional annotation and transparent,
``word`` is a real edge and opaque. Both are preserved in the output
either way, because the dot is what lets nucleus-marked stress be turned
back into syllable-marked stress.

**A boundary run is one boundary, and the virtual edge is part of it.**
The general form of the claim above, stated so it can be swept: for any
rule ``r`` and form ``f`` whose ends carry no boundary run,

    ``r(f) == strip(r("#" + f)) == strip(r(f + "#")) == strip(r("#" + f + "#"))``

A form's end *is* a word boundary whether or not a ``#`` is typed
(docs/rules.md), so typing one adds no information and must not change
the derivation -- and neither must doubling it. This held for
substitutions and deletions and failed for every insertion whose context
named a boundary, because the written mark and the virtual edge past it
were two anchors: ``∅ -> ə / # _`` took ``tæt`` to ``ətæt`` but ``#tæt#``
to ``ə#ətæt#ə``. :func:`_anchors` coalesces the anchor set, and the same
run rule refuses a context that names two boundaries in a row.

**A boundary can be written and unwritten, and exchanged with a segment
in neither direction.** A boundary is a relation between segments rather
than a segment of its own (``ipakit.form``), and for a while that was
read as "a rule may not touch one": a boundary named as a *target* was
refused, because :meth:`Query.sites` skipped boundary units and such a
rule would otherwise parse and then silently never fire. The right of
the arrow never carried the restriction, though: ``∅ -> .`` with a
plosive-vowel context inserted a syllable break and fired, and the
shipped French set documents ``∅ -> ‿`` as the way to mark a join -- so
the engine would *assert* a relation and refuse to *retract* one. That is
indefensible in either direction, and refusing both would cost the half
that works: resyllabification is a real process and rules do need to
write boundaries.

The line is drawn around the segments instead. A rule may **write** a
boundary (``∅ -> .``), **unwrite** one (``. -> ∅``) and **restate** one
at another level (``. -> #``); it may not **exchange** one for a
segment, in either direction -- ``. -> t`` is refused, and so is
``t -> .``, which used to fire. What survives of form.py's thesis is the
invariant that makes it checkable: *a boundary rewrite leaves the
segmental string byte-identical*, changing only how the same segments
are related. That is what resyllabification is, which is why the two
directions belong together; a segment that goes away and a relation
asserted where it stood are two statements, and an ordered cascade
already spells that pair. A *feature change* on a boundary stays refused
for the original reason: a query is compared against a feature bundle
and a boundary has none, so ``. -> [level=word]`` would be the next
silent no-op.

Allowing it cost one clause. :meth:`Query.sites` skipped every boundary
unit before asking the target whether it matched, and
:meth:`Pattern.matches` already answers ``False`` for a boundary unless
the pattern names one -- so the skip was doing nothing else, and
removing it is the whole of the scan-side change.

Two consequences are worth stating. A boundary pattern is a **class** in
a target exactly as in a context: ``.`` is "a boundary at syllable level
or stronger", so ``. -> ∅`` deletes a written ``#`` too, and with it the
word division the dot never named -- as ``[vowel] -> ∅`` deletes a stress
it never named. Naming the mark (``‿``, ``|``) is how a rule is exact
about which one. And edge redundancy is untouched: the virtual edge past
the end of a form is not a unit, so there is nothing there to delete, and
``strip(r("#" + f)) == r(f)`` holds for a deleting rule as for any other.

**A rule matches against a snapshot of its input.** Every site is found
before any is rewritten, so a rule cannot read its own output and cannot
feed itself; the pass terminates by construction. Rules are then
ordered, and each sees the previous rule's output, which is where
feeding and bleeding live. Iterative within-rule spreading (vowel
harmony as a single rule) is deliberately not expressible: it needs a
loop guard, and an ordered cascade says the same thing with repeated
rules.

**A rule may bind a feature value and re-use it.** SPE's agreement
variable, ``n -> [place=α] / _ [place=α]``: one rule for a process that
was otherwise one rule per place value. :class:`Agreement` is the term,
and the semantics is stated in three parts, because each of them is a
place a looser reading would be silently wrong.

*Recognition binds; the action refers.* The left of the arrow is where a
variable takes a value -- from the target, from a context item, or from
both -- and the right of the arrow may only name one the left already
bound. A variable on the right that the left never binds is refused at
parse time rather than left to resolve to nothing at some site and not
at another.

*Every occurrence of a variable in the recognition half must agree.* So
the direction does not matter and no "first occurrence" rule has to be
remembered: the site holds exactly where all of its occurrences read the
same value, and that value is what the action writes. (Stated as an
implementation it is "the leftmost occurrence in form order binds and
the rest check", and the two are the same predicate.)

*A variable stands for a value of ONE feature.* ``[place=α]`` and
``[voiced=α]`` in one rule is refused: the declared values of the two
features are different sets, so a variable ranging over both ranges over
nothing a phone can satisfy. ``-α`` is the opposite value, and is legal
only where the feature is binary -- for an n-ary feature like ``place``
there is no opposite to mean, and saying so is a real rule rather than a
fudge.

The notation is a Greek small letter, which is what the literature
writes, restricted to the letters that spell **nothing this inventory
registers** -- a predicate over the declaration, not a list. ``β``, ``θ``
and ``χ`` are registered phones and are refused by name, which is the
loud half of a decision whose quiet half would have been the defect:
a variable that reached a form would be a phone. See :func:`_agreement`.

Metathesis does **not** fall out of this, and the two are worth keeping
apart because they rhyme. An agreement variable copies a feature *value*
between positions the rule already matched; metathesis *reorders* the
positions themselves, which needs a target spanning more than one unit
and a permutation on the right of the arrow. A :class:`Pattern`
constrains one unit and a :class:`Site` spans one, so ``ab -> ba`` is
refused by the parser exactly as it was before this. docs/calculus.md
records that as a limit that agreement variables do not lift.

**A rule may be optional, and optionality is per site.** ``ə ~> ∅ / ...``
says the rule *may* fire, not that it does, and the branch point is the
choice of which **subset** of its edits to apply. Rule-level optionality
-- the whole rule fires or does not -- is the cheaper reading and the
wrong one: French *petit* is [pəti] ~ [pti] and a word with two
deletable schwas has each independently deletable, so the unit of choice
is the site. :meth:`RuleSet.variants` is the entry point, and it answers
with a :class:`VariantSet` rather than a form.

The architecture already had the branch point isolated, which is why
this costs so little: :meth:`Query.sites` answers with a *set* of sites
and :meth:`Action.edit` maps one site to one :class:`Edit`, so nothing
about recognition or action changes. What changes is that the fold over
rules carries a set of branches instead of one, and an optional rule
maps each branch to one child per subset of its edits. Applying every
edit is still the last of those subsets, which is why
``rewrite``/``derive`` are untouched for a set that marks nothing
optional.

Optionality is a statement about the **derivation**, so :class:`RuleSet`
honours it and :meth:`Rule.apply` does not -- that method is the
mechanism, "apply this rule once", and it goes on applying every edit it
finds. Everything public (:func:`~ipakit.rewrite`, :func:`~ipakit.derive`,
:func:`~ipakit.variants`, the CLI) reaches a rule through a
:class:`RuleSet`. Under the form-to-form entry points an optional rule
does **not** fire, and that is the same statement said the other way:
``ruleset.apply(f)`` is exactly ``variants(f)[0].form``, the member that
takes no optional choice.

The set is finite for every rule set and every form, insertion included,
because no rule feeds itself: sites are found against a snapshot, so one
rule contributes at most ``2 ** len(edits)`` children per branch and the
cascade is a finite fold of finite steps. Finite is not small -- an
insertion rule lengthens the form the next rule scans, so the bound is
doubly exponential in the number of rules -- which is what
:data:`DEFAULT_LIMIT` is for, and why a truncation is *reported* in the
answer rather than logged. See docs/calculus.md for the closure,
composition and finiteness claims, and for what this algebra cannot say.

The query language is not new. Patterns resolve through the same
``_resolve_query`` that backs :meth:`~ipakit.IPAFeatures.phones_matching`
and :meth:`~ipakit.IPAFeatures.find`, so a natural class means one thing
across the library rather than one thing per caller.
"""

from __future__ import annotations

import dataclasses
import itertools
import unicodedata
import warnings
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .constants import DATA_DIR, ZERO_CLASS
from .form import (
    Unit,
    _default,
    _unit_for,
    boundary_marks,
    declared_prosody,
    edge_tier,
    spell,
    split_prosody,
    units,
    with_prosody,
)

if TYPE_CHECKING:  # pragma: no cover
    from .features import IPAFeatures

#: Spellings accepted for the empty string in a rule (insertion/deletion).
#:
#: ``∅`` is written here rather than read off :attr:`IPAFeatures.zeros`,
#: which is a deliberate exemption from the house rule, declared in
#: ``tests/test_declared_not_hardcoded.py``'s ``_JUSTIFIED``. The
#: declaration runs the other way round: this was the notation first and
#: ``<zeros>`` registered the same glyph afterwards, knowing it. Reading
#: the set off the declaration would make a *second* declared zero an
#: accepted empty-string spelling on both sides of every arrow, silently
#: changing what four shipped rule sets mean -- :func:`_zero_named`
#: refuses a second zero rather than guess, for the same reason. That the
#: two agree today is asserted beside the exemption, so a change to
#: either fails instead of drifting.
NULL = frozenset({"∅", "0", "Ø"})

#: Spellings accepted for the rewrite arrow.
ARROWS = ("->", "→", "=>")

#: Marks an arrow **optional**: the rule may fire at a site or not, and a
#: derivation carrying it yields a *set* of forms rather than one
#: (:meth:`RuleSet.variants`, docs/calculus.md).
#:
#: Derived from :data:`ARROWS` rather than listed beside it, so a fourth
#: arrow spelling gets its optional counterpart without an edit here and
#: the two cannot come to disagree about how many arrows there are.
#: ``~>`` is the canonical spelling and is the wavy-shafted counterpart of
#: ``->``; ``~->``, ``~→`` and ``~=>`` let a set that has settled on one
#: arrow mark optionality without switching dialects.
#:
#: Longest first, because ``~->`` must be recognized before ``~>`` would
#: be looked for -- and every optional spelling must be looked for before
#: any plain one, since ``~=>`` contains ``=>``.
OPTIONAL_ARROWS = tuple("~" + arrow for arrow in ARROWS) + ("~>",)

#: The character that makes an arrow optional. Checked against the
#: inventory rather than assumed free: it spells no phone, no diacritic,
#: no separator and no break mark, and ``ipa.xml`` does not contain it at
#: all, so it can be notation without shadowing anything writable.
OPTIONAL_MARK = "~"

#: Separates a rule from its name. Not ``|``, which is a declared
#: prosodic break and therefore a legal context item.
NAME_SEP = ";"

#: The namespace an agreement variable is named from, as a Unicode
#: property rather than a list of letters. SPE writes ``α β γ``, and the
#: series has no end, so asking the character what it *is* keeps the
#: notation open without pasting an alphabet here -- and keeps a typo
#: (``[manner=plosiv]``) out of it, which any "a name that resolves to
#: nothing is a variable" reading would have swallowed.
VARIABLE_SERIES = "GREEK SMALL LETTER"

#: Written before a variable to mean **the opposite value**: SPE's
#: ``-α``. The same character already spells feature-value negation in a
#: bare term (``[-voiced]``), and it means the same thing here -- "not
#: this value" -- which is well defined only where the feature has
#: exactly one other value. See :func:`_agreement`.
OPPOSITE_MARK = "-"


class RuleError(ValueError):
    """A rule could not be parsed, or names something undeclared."""


@dataclass(frozen=True)
class Agreement:
    """A variable standing for a value of one feature: SPE's ``α``.

    ``same`` is ``False`` for ``-α``, the *opposite* value, which is why
    this is a small object rather than a bare name string: the two occur
    in the same slot and mean different things, and a string could only
    have carried one of them.
    """

    #: The letter as written, without the ``-``.
    name: str
    #: Whether this occurrence means the bound value or its opposite.
    same: bool = True

    def __str__(self) -> str:
        return self.name if self.same else OPPOSITE_MARK + self.name


#: What the right of an arrow says to do: a feature change -- whose
#: values may be a declared value, ``None`` for "clear it", or an
#: :class:`Agreement` -- a literal spelling, or ``None`` to delete.
Change = dict[str, "str | None | Agreement"]
Becomes = Change | str | None


# --------------------------------------------------------------------------
# Patterns: what matches one unit
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Pattern:
    """A constraint on a single unit.

    Built from the same query language as
    :meth:`~ipakit.IPAFeatures.phones_matching`, then split by declared
    mode into a segmental part (matched against the feature bundle) and
    a prosodic part (matched against the unit's prosody).
    """

    source: str
    literal: str | None = None
    boundary: str | None = None
    #: A declared separating mark named literally in a context: the
    #: prosodic break ``|``, the major break ``‖``, the linking mark ``‿``.
    mark: str | None = None
    seg_required: dict[str, str] = field(default_factory=dict)
    seg_excluded: dict[str, frozenset[str]] = field(default_factory=dict)
    pro_required: dict[str, str] = field(default_factory=dict)
    pro_excluded: dict[str, frozenset[str]] = field(default_factory=dict)
    #: Agreement variables this pattern constrains, keyed by feature.
    #: Split by declared mode exactly as the required/excluded pairs
    #: above are, so a variable on ``stress`` is read off the unit's
    #: prosody and one on ``place`` off its feature bag, and no list of
    #: prosodic feature names appears here either.
    seg_agreements: dict[str, Agreement] = field(default_factory=dict)
    pro_agreements: dict[str, Agreement] = field(default_factory=dict)
    #: Whether the scan may pass this item by when nothing there matches
    #: it. Written ``(∅)``, and only of a zero today: it is how one rule
    #: declares a zero transparent to its own context without deciding
    #: the question for every rule. See :func:`_optional`.
    optional: bool = False

    @property
    def names_boundary(self) -> bool:
        return self.boundary is not None or self.mark is not None

    @property
    def prosodic_keys(self) -> frozenset[str]:
        """The prosodic features this pattern speaks about, either way round.

        The right-hand side needs this. A literal rewrite carries across
        prosody the rule never mentioned -- ``t -> ʔ`` must not shorten
        ``tː`` -- but prosody the rule *did* mention is the rule's own
        business, and its silence on the right is what makes ``aː -> a``
        mean "and the length goes away". A variable is a mention: a rule
        that binds ``[stress=α]`` has spoken about stress.
        """
        return (
            frozenset(self.pro_required)
            | frozenset(self.pro_excluded)
            | frozenset(self.pro_agreements)
        )

    @property
    def agreements(self) -> dict[str, Agreement]:
        """Every variable this pattern names, whichever namespace it is in."""
        return {**self.seg_agreements, **self.pro_agreements}

    def matches(
        self,
        unit: Unit,
        features: IPAFeatures,
        bindings: dict[str, str] | None = None,
    ) -> bool:
        """Whether ``unit`` satisfies this pattern.

        ``bindings`` is the site's variable environment. A variable binds
        into it where it is not yet bound and is *checked* against it
        where it is, which is what makes every occurrence in a rule agree
        without any of them being privileged as "the" binder.

        Passing ``None`` where the pattern carries a variable is refused
        rather than ignored. A pattern that quietly dropped its agreement
        term would match wherever the rest of it held -- assimilation to
        every following consonant instead of the agreeing ones -- and a
        well-formed wrong answer is the shape of every defect this
        library has had (docs/reviewing.md).
        """
        if self.mark is not None:
            return unit.is_boundary and unit.text == self.mark
        if self.boundary is not None:
            if not unit.is_boundary:
                return False
            if self.boundary == "any":
                return True
            return _reaches(unit.level, self.boundary, features)
        if unit.is_boundary:
            return False
        if self.literal is not None and unit.core != self.literal:
            return False
        if not (
            features._query_matches(
                unit.features,
                self.seg_required,
                {k: set(v) for k, v in self.seg_excluded.items()},
            )
            and features._query_matches(
                unit.prosody,
                self.pro_required,
                {k: set(v) for k, v in self.pro_excluded.items()},
            )
        ):
            return False
        return self._agrees(unit, features, bindings)

    def _agrees(
        self, unit: Unit, features: IPAFeatures, bindings: dict[str, str] | None
    ) -> bool:
        """Bind or check this pattern's variables against ``unit``."""
        if not self.seg_agreements and not self.pro_agreements:
            return True
        if bindings is None:
            raise RuleError(
                f"{self.source!r} names the agreement variable(s) "
                f"{' '.join(sorted(str(a) for a in self.agreements.values()))} "
                "and was matched with no environment to bind them in. A "
                "variable is a statement about a whole rule, so it is matched "
                "through Query.sites rather than against a unit on its own."
            )
        for bag, terms in (
            (unit.features, self.seg_agreements),
            (unit.prosody, self.pro_agreements),
        ):
            for key, variable in terms.items():
                value = bag.get(key)
                # No value, nothing to agree with. A vowel declares no
                # 'place', so '[place=α]' does not reach one -- which is
                # what keeps nasal assimilation off the vowel to its right.
                if value is None:
                    return False
                bound = bindings.get(variable.name)
                if bound is None:
                    bindings[variable.name] = (
                        value if variable.same else _opposite(key, value, features)
                    )
                    continue
                wanted = bound if variable.same else _opposite(key, bound, features)
                if value != wanted:
                    return False
        return True

    def __str__(self) -> str:
        return self.source


def _is_prosodic(name: str, features: IPAFeatures) -> bool:
    return getattr(features.features.get(name), "mode", None) == "prosodic"


def _reaches(level: str | None, wanted: str, features: IPAFeatures) -> bool:
    """Whether a boundary at ``level`` counts as one at ``wanted``.

    The tiers nest, so a word boundary *is* a syllable boundary: a rule
    conditioned on a syllable margin fires at a word margin too, and
    aspiration is syllable-initial rather than only word-initial. The
    containment is not asserted here -- ``<feature name="level">``
    declares its values in order (``syllable`` then ``word``) and is
    ordinal, so the ranking is read off the data.
    """
    if level is None:
        return False
    order = features.features["level"].values
    try:
        return order.index(level) >= order.index(wanted)
    except ValueError:  # pragma: no cover - undeclared level
        return level == wanted


def _edge_level(features: IPAFeatures) -> str:
    """The level a form's own edge asserts, which is ``form.edge_tier()``.

    ``_ #`` fires at the end of a form without a ``#`` having been typed,
    and since the tiers nest, so does every weaker level. Which level
    that *is* is a question ``ipakit.form`` already answers for the tree
    it builds, so it is asked there rather than answered again here.

    It used to be answered again here, as ``level.values[-1]`` -- the top
    of the whole ladder -- and the two **already disagreed**:
    ``edge_tier()`` is ``word`` and ``values[-1]`` is ``utterance``,
    because ``|`` and ``‖`` declare levels above ``word`` while no
    *separator* spells one. That was harmless only by accident. A level
    pattern is built for a declared separator, so the virtual edge is
    only ever tested against ``syllable`` and ``word``, and
    ``_reaches`` answers alike from either; declare a separator above
    ``word`` and the safety net that was supposed to catch this -- "if a
    separator above word is ever declared, those two must be made one
    read" -- is exactly what would not have fired, since one of them
    tracks the separators and the other does not.
    """
    return edge_tier(features)


#: Notation for "a boundary of any level". Not a declared separator -- it
#: is a wildcard over the declared ones, which is why it is spelled here
#: and the marks are not.
ANY_BOUNDARY = "%"


def _reads_as(text: str, features: IPAFeatures) -> list[Unit]:
    """What ``text`` reads as, quietly.

    The read warns about what it dropped -- "dropped 1 unregistered
    symbol" -- which names the symbol but not the consequence, and the
    consequence is what a rule writer needs: a literal nothing registers
    matches nothing on the left and *deletes* on the right. The parser
    says that itself, so the read is probed with the warning suppressed
    rather than left to speak for it.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return list(units(text, features))


#: Said in both refusals below, because the mistake it describes reaches
#: both: a rule written with the old name separator parses its name as
#: context items, so the rule matches nothing and says nothing.
_NAME_HINT = (
    "If it was meant to name the rule, the separator is ';' -- '|' is a "
    "declared prosodic break and therefore a legal context item, which is "
    "why it is not the separator."
)


def _check_literal(text: str, features: IPAFeatures) -> list[Unit]:
    """Refuse a literal the inventory cannot read, and say what to write.

    A bare glyph is a literal phone, and one that spells no registered
    phone builds a constraint nothing can satisfy -- the third member of
    a family whose other two are already refused here: ``[mannr=plosive]``
    (undeclared key) and ``[manner=obstruent]`` (undeclared value) both
    used to match nothing in silence. The right-hand side is worse than
    silent, because an unread literal spells zero units and a substitution
    becomes a deletion: ``t -> Q`` did what ``t -> ∅`` does.

    What "the inventory registers" means is asked of
    :meth:`~ipakit.IPAFeatures.expand_ligatures` -- the library's one
    resolution of a declared input spelling, the same read
    ``_resolve_token`` and the converters use -- rather than of the
    characters as typed. A declared ``alias`` is an accepted spelling
    everywhere else (tests/test_ligature_aliases.py sweeps twenty-five
    entry points for exactly this), and comparing the read against the
    raw text made this module the twenty-sixth: ``ʦ`` reads as one
    ``t͡s`` unit, so ``spell(read)`` was the canonical spelling and never
    the alias, and every ligature was refused as a literal while
    ``features('ʦ')`` and ``units('aʦa')`` handled it. Refusing loudly
    was an improvement on the silent no-op it replaced and still the
    wrong answer.
    """
    read = _reads_as(text, features)
    if not read or spell(read) != features.expand_ligatures(text):
        raise RuleError(
            f"{text!r} spells nothing this inventory registers, so it can only "
            "match nothing on the left of the arrow and delete on the right. "
            "Write the phone as the inventory spells it ('ɡ' is not 'g'), a "
            "feature query for a class ('[manner=plosive]'), a declared "
            f"boundary for a margin ({', '.join(sorted(features.separators))} "
            f"{ANY_BOUNDARY}), or '∅' if deletion is what was meant. " + _NAME_HINT
        )
    return read


def _zero_named(terms: Sequence[str], features: IPAFeatures) -> str | None:
    """The declared zero a bracketed class term names, or ``None``.

    ``[zero]`` is read off ``<zeros>``: the term is the element *class*
    those symbols carry and the answer is the symbol declared under it,
    so neither the word ``zero`` nor the glyph ``∅`` is spelled in this
    module. That is what makes the notation follow the data -- rename the
    class or change the glyph and the rule notation moves with it.

    ``∅`` is deliberately not this. On the left of the arrow ``∅`` is the
    empty string (:data:`NULL`), which is what makes ``∅ -> ə``
    epenthesis in two shipped sets; freeing the glyph would silently
    change every shipped insertion rule. ``[zero]`` is a different
    statement in a notation -- brackets already mean *described, not
    spelled* -- and it was a hard error before this, so it collides with
    nothing.
    """
    if len(terms) != 1:
        return None
    found = [
        symbol
        for symbol, declared in features.zeros.items()
        if (declared.features or {}).get("class") == terms[0]
    ]
    if len(found) > 1:
        raise RuleError(
            f"[{terms[0]}] names {len(found)} declared zeros "
            f"({' '.join(sorted(found))}), so it does not say which to "
            "write. Name the one you mean as a literal."
        )
    return found[0] if found else None


#: The series itself, in alphabetical order: ``α`` to ``ω``. Enumerated
#: from Unicode rather than pasted, and bounded by the alphabet's own
#: endpoints, so it is 24 letters and not the accented and archaic forms
#: the block also holds -- ``ά`` is a letter with a tonos on it, and a
#: notation whose members differ by a diacritic is one whose typos are
#: invisible.
SERIES = tuple(
    chr(code)
    for code in range(ord("α"), ord("ω") + 1)
    if unicodedata.name(chr(code), "").startswith(VARIABLE_SERIES)
)


def _in_the_series(text: str) -> bool:
    """Whether ``text`` is one letter of the variable series.

    One character, so ``[place=αγ]`` is not a variable with a long name;
    the series is a supply of *distinct* letters, and a name of more than
    one of them would be the first place two could be confused.
    """
    return text in SERIES


def _free_variables(features: IPAFeatures) -> list[str]:
    """The letters of the series this inventory leaves free, in order.

    Asked of the declaration on every call rather than computed once,
    for the reason :func:`_pattern` reads ``features.separators`` rather
    than restating ``#``: a rule's notation follows the data it is
    written against, and a second inventory is a second answer.
    """
    return [letter for letter in SERIES if not _reads_as(letter, features)]


def _agreement(value: str, features: IPAFeatures) -> Agreement | None:
    """The agreement variable ``value`` names, or ``None``.

    **The collision, and why it is answered by a predicate.** The
    traditional series is ``α β γ``, and its second member is a
    registered phone -- the voiced bilabial fricative -- as are ``θ`` and
    ``χ`` further along it. Nothing about a *value* slot makes that
    ambiguous today, since no feature declares a one-letter value; what
    makes it intolerable is the other direction. A variable must never be
    able to reach a form, because a leak would then be a **phone**, and
    the whole failure mode of this library is a well-formed wrong answer
    (docs/reviewing.md). ``α`` and ``γ`` do not survive a read -- they are
    dropped, loudly -- and ``β`` does.

    So the test is the property, not the letter: a variable is a letter of
    :data:`VARIABLE_SERIES` that **spells nothing this inventory reads**.
    ``β`` is refused, by name and with the reason, rather than skipped in
    silence; and an inventory that declares ``α`` tomorrow takes it back
    the same way, since the declaration is always what wins and the
    notation only claims what it leaves free. That is the rule ``~``
    already follows (:data:`OPTIONAL_MARK`) and the reason ``[zero]`` is
    read off ``<zeros>``.

    ``-α`` is the opposite value. It is checked against the feature by
    the caller, which is the only place the feature is known.
    """
    same = not value.startswith(OPPOSITE_MARK)
    name = value if same else value[len(OPPOSITE_MARK) :]
    if not _in_the_series(name):
        return None
    if _reads_as(name, features):
        raise RuleError(
            f"{name!r} spells something this inventory registers "
            f"({' '.join(u.text for u in _reads_as(name, features))}), so it "
            "cannot also be an agreement variable -- a variable that reached a "
            "form would be a phone. The letters free today are "
            f"{' '.join(_free_variables(features)[:6])} ..."
        )
    return Agreement(name=name, same=same)


def _opposite(key: str, value: str, features: IPAFeatures) -> str:
    """The other declared value of a two-valued feature.

    ``-α`` means "the opposite", and an opposite exists only where there
    is exactly one other value to be. ``[voiced=-α]`` is the classical
    use and is well defined; ``[place=-α]`` is not, because the opposite
    of ``velar`` is thirteen things. Refused at parse time by
    :func:`_check_opposite`, which asks the declaration; this reads the
    answer off the same declaration rather than assuming ``+``/``-``.
    """
    values = list(features.features[key].values)
    return values[0] if values[1] == value else values[1]


def _check_opposite(source: str, key: str, features: IPAFeatures) -> None:
    """Refuse ``-α`` where the feature has no opposite to name."""
    feature = features.features[key]
    if feature.type == "binary" and len(feature.values) == 2:
        return
    raise RuleError(
        f"{source!r} writes the opposite of a variable on {key!r}, which "
        f"declares {len(feature.values)} values "
        f"({', '.join(feature.values)}). 'The opposite' is well defined only "
        "for a binary feature with two of them; for an n-ary feature name the "
        "value you mean, or use the plain variable to say the two agree."
    )


def _optional(text: str, features: IPAFeatures) -> Pattern:
    """``(∅)``: a context item the scan may pass by.

    Transparency, chosen per rule and per place rather than globally.
    Whether a zero should block a context **depends on what the zero is
    being used for**: a latent consonant's zero marks where a segment
    could surface, and a rule about the vowels either side has no
    business seeing it; a zero standing for an empty mora is a position
    that counts, and a rule reaching across it would be wrong. Neither
    reading can be the library's, so the rule states which it wants.

    The precedent is the syllable dot, which is transparent by default
    and stops being stepped over once a rule names it -- and it does not
    fit here. The dot is *optional notation*, so transparent is the only
    safe default for it; a zero is a claim the transcription makes, and
    the dot's shape offers "step over unless named" with no way to say
    the opposite. So the default is unchanged -- a zero is a position and
    blocks -- and a rule that wants to reach across one says so, in the
    place it wants it, with the parenthesis generative phonology already
    uses for an optional element.

    Deliberately not general. ``(t)`` and ``([vowel])`` are refused
    rather than quietly meaning something: an optional *boundary* item
    would have to answer to the boundary-run rule and the virtual edge
    (:func:`_anchors`), and that is a separate question from this one.
    The limit is pinned by a test, so it changes deliberately.
    """
    inner = _pattern(text[1:-1], features)
    if inner.literal is None or inner.literal not in features.zeros:
        raise RuleError(
            f"{text!r} marks {text[1:-1].strip()!r} optional, and only a "
            "declared zero may be optional today -- a zero is the one item "
            "whose transparency depends on what it is being used for. "
            f"Write '({''.join(sorted(features.zeros))})', or name the item "
            "without the parentheses to require it."
        )
    return dataclasses.replace(inner, source=text, optional=True)


def _pattern(source: str, features: IPAFeatures) -> Pattern:
    """Build a pattern from one notation item."""
    text = source.strip()
    if not text:
        raise RuleError("empty pattern")
    if text.startswith("(") and text.endswith(")"):
        if not text[1:-1].strip():
            raise RuleError(f"{text!r} is an empty optional item")
        return _optional(text, features)
    # A separator's notation is the separator, and its level is the level
    # ipa.xml declares for it -- '<separator name="." level="syllable"/>'.
    # Read, not restated: writing '#' -> word here meant a newly declared
    # tier had notation nothing would parse.
    declared = features.separators.get(text)
    if declared is not None:
        level = (declared.features or {}).get("level")
        if level is not None:
            return Pattern(source=text, boundary=level)
    if text == ANY_BOUNDARY:
        return Pattern(source=text, boundary="any")
    if text in boundary_marks(features):
        # A declared break or linking mark, named in a context. Without
        # this it fell through to the literal branch, which only ever
        # matches a segment, so the context could never hold.
        return Pattern(source=text, mark=text)

    if text.startswith("[") and text.endswith("]"):
        terms = [t for t in text[1:-1].replace(",", " ").split() if t]
        if not terms:
            raise RuleError(f"{text!r} is an empty query")
        # A declared zero, named by its element class. It is matched as
        # the literal it is: a zero carries no phonetic features, so
        # there is no bundle for a query to be compared against.
        if (zero := _zero_named(terms, features)) is not None:
            return Pattern(source=text, literal=zero)

        # 'key=value' terms and bare class terms may be mixed --
        # '[vowel stress=primary]' is the natural way to say it. Each
        # form goes through the same resolver and the results merge,
        # rather than this growing a second query language.
        pairs = dict(t.split("=", 1) for t in terms if "=" in t)
        bare = [t for t in terms if "=" not in t]
        # A bare term that resolves to nothing is refused by the resolver,
        # but a 'key=value' term went straight through: '[mannr=plosive]'
        # and '[manner!=vowel]' both built a constraint on a key no phone
        # has, so the pattern silently matched nothing. A misspelled
        # feature has to fail loudly, as it does on the right of the arrow.
        undeclared = sorted(k for k in pairs if k not in features.features)
        if undeclared:
            raise RuleError(f"{text!r} names undeclared feature(s): {undeclared}")
        # An agreement variable stands for a VALUE, so it needs a feature
        # to be a value of. A bare one has none, and would otherwise reach
        # the resolver as a term that resolves to nothing -- the one shape
        # this query language must never accept quietly.
        for term in bare:
            stripped = term[1:] if term[:1] in "+-0" else term
            if _in_the_series(stripped):
                raise RuleError(
                    f"{text!r} names the agreement variable {stripped!r} on its "
                    "own. A variable stands for a value of one feature, so it "
                    f"has to say which: write '[place={stripped}]'."
                )
        # Variables are taken out of the query HERE, before the value arm
        # below and before the resolver, and they never go back in. That
        # is the whole of the interaction with the resolver's own policy
        # on a term it cannot resolve: a variable is not an unresolvable
        # query term that has to be tolerated, it is not a query term at
        # all. Whatever `_resolve_query` does with something it cannot
        # place -- drop it, or raise -- it never sees one of these.
        seg_agreements: dict[str, Agreement] = {}
        pro_agreements: dict[str, Agreement] = {}
        for key in list(pairs):
            variable = _agreement(pairs[key], features)
            if variable is None:
                continue
            if not variable.same:
                _check_opposite(text, key, features)
            del pairs[key]
            if _is_prosodic(key, features):
                pro_agreements[key] = variable
            else:
                seg_agreements[key] = variable
        # The VALUE arm, which the first cut of this guard left open. Only
        # the key was checked, so '[manner=obstruent]' -- the query a
        # reader reaches for first -- built a constraint no phone can
        # satisfy and matched nothing, silently. Values go through the
        # alias table and expand(), as they do on every other write path,
        # so a spelled alias and a generative overlap (bilabial^velar) are
        # accepted on the same terms respell accepts them.
        for key, value in pairs.items():
            feature = features.features[key]
            resolved = feature.value_aliases.get(value, value)
            # Both ways a value can be more than one name: a sequence is a
            # run of values in time order (a contour) and a combination is
            # values held at once (a double articulation). Each step of a
            # sequence expands in its own right.
            unknown = [
                part
                for step in feature.steps(resolved)
                for part in feature.expand(step)
                if part not in feature.values_set
            ]
            if unknown:
                # A natural class is not a value, so 'manner=obstruent'
                # stays an error -- but the reader who wrote it wanted a
                # class that exists, and the message says how to spell it.
                hint = (
                    f". {value!r} is a natural class over those values; ask "
                    f"for it as the bare term '[{value}]'"
                    if value in feature.value_classes
                    else ""
                )
                raise RuleError(
                    f"{text!r}: {value!r} is not a value of feature {key!r}; "
                    f"declared values are {sorted(feature.values_set)}{hint}"
                )
        required: dict[str, str] = {}
        excluded: dict[str, set[str]] = {}
        for part in (pairs, bare):
            if not part:
                continue
            try:
                got_required, got_excluded = features._resolve_query(part)
            except Exception as exc:  # pragma: no cover - resolver messages vary
                raise RuleError(f"{text!r}: {exc}") from None
            for key, value in got_required.items():
                if required.get(key, value) != value:
                    raise RuleError(
                        f"{text!r} constrains {key!r} to both "
                        f"{required[key]!r} and {value!r}"
                    )
                required[key] = value
            for key, values in got_excluded.items():
                excluded.setdefault(key, set()).update(values)

        return Pattern(
            source=text,
            seg_required={
                k: v for k, v in required.items() if not _is_prosodic(k, features)
            },
            seg_excluded={
                k: frozenset(v)
                for k, v in excluded.items()
                if not _is_prosodic(k, features)
            },
            pro_required={
                k: v for k, v in required.items() if _is_prosodic(k, features)
            },
            pro_excluded={
                k: frozenset(v)
                for k, v in excluded.items()
                if _is_prosodic(k, features)
            },
            seg_agreements=seg_agreements,
            pro_agreements=pro_agreements,
        )

    # A bare glyph is a literal phone -- and any prosody written on it is
    # an ADDITIONAL constraint, layered on top of the identity match,
    # rather than part of the identity. 'aː' means "the phone a, bearing
    # length=long", which is why 'a' goes on matching 'ˈa' while 'aː'
    # matches only the long one; putting prosody back into identity would
    # break the first of those, and that is the position the library
    # holds (docs/ties.md). Comparing the whole spelling against
    # 'Unit.core' -- which is what this did -- could never match at all,
    # since core has the prosody glyphs stripped out of it.
    core, _worn = split_prosody(text, features)
    if not core:
        raise RuleError(
            f"{text!r} is prosody with no phone under it. A prosodic mark is a "
            "property of a unit, not a position between units, so it cannot be "
            "matched on its own: write it on the phone it rides ('ˈa'), or ask "
            "for the feature ('[stress=primary]')."
        )
    read = _check_literal(text, features)
    if len(read) > 1:
        # A pattern is a constraint on ONE unit, so a literal naming two
        # could never hold either -- the same silence, one step further
        # along. Refused with the same breath as the unregistered one,
        # since the commonest way to write it is the name-separator
        # mistake: '/ _ # | flapping' reads as three context items.
        raise RuleError(
            f"{source.strip()!r} names {len(read)} units "
            f"({' '.join(u.text for u in read)}), and a pattern constrains a "
            "single unit. Write one item per unit ('_ k t'), or tie a compound "
            f"the inventory registers ('t͡s'). {_NAME_HINT}"
        )
    # The identity and the prosody are taken from the unit the notation
    # READ AS, not from the characters as typed. Those are the same thing
    # for a phone the inventory spells one way, and not for a declared
    # alias: 'ʦ' splits to the core 'ʦ' while the unit it reads as has
    # core 't͡s', so a literal built from the notation could never equal
    # the `Unit.core` it is compared against in `Pattern.matches`. That is
    # why accepting the alias in `_check_literal` alone is not the fix --
    # it turns a loud refusal back into the silent no-op that came before
    # it. Reading the literal off the unit makes the two sides of that
    # comparison one read, so a spelling the inventory accepts cannot be
    # accepted by the parser and then match nothing.
    #
    # `split_prosody` is still the right question above, because "is
    # there a phone under these marks" has to be answerable before the
    # text is handed to a parser that would drop them.
    return Pattern(
        source=text, literal=read[0].core, pro_required=dict(read[0].prosody)
    )


# --------------------------------------------------------------------------
# Recognition: Query -> Site
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Site:
    """Where a rule's environment holds, against one form.

    ``start``/``end`` bound the target in the unit sequence; they are
    equal for an insertion, which occupies no position. ``left`` and
    ``right`` record the indices the context matched, so a trace can say
    *which* neighbors licensed the change and not merely that some did.
    An entry is ``None`` where no unit licensed that item: the context
    matched the virtual edge past the end of the form, or the item was
    optional (``(∅)``) and nothing was there. One entry per context
    item either way, so the two sequences stay alignable with the
    notation.

    ``bindings`` is the same kind of record for the other thing a site
    can carry: what each agreement variable took as its value here. It is
    provenance, not a result -- a trace can say ``α = velar`` -- and it is
    what the action reads to write the value back out.
    """

    start: int
    end: int
    left: tuple[int | None, ...] = ()
    right: tuple[int | None, ...] = ()
    #: ``(variable, value)`` pairs, in the order they bound.
    bindings: tuple[tuple[str, str], ...] = ()

    @property
    def is_insertion(self) -> bool:
        return self.start == self.end


def _run(items: Sequence[Unit], gap: int) -> tuple[int, int]:
    """The maximal boundary run the gap ``gap`` sits in, as ``[lo, hi)``.

    Empty (``lo == hi == gap``) where neither neighbor is a boundary.
    """
    lo = gap
    while lo > 0 and items[lo - 1].is_boundary:
        lo -= 1
    hi = gap
    while hi < len(items) and items[hi].is_boundary:
        hi += 1
    return lo, hi


def _anchors(
    items: Sequence[Unit], gap: int, limit: int, left: tuple[int | None, ...]
) -> bool:
    """Whether ``gap`` is the one gap its boundary run offers an insertion.

    **Edge redundancy.** For any rule ``r`` and form ``f`` whose ends carry
    no boundary run, ``r(f) == strip(r("#" + f)) == strip(r(f + "#")) ==
    strip(r("#" + f + "#"))``. Writing a mark the form's own edge already
    asserts must not change the derivation, exactly as writing an optional
    dot must not -- and this is the same invariant, generalized from ``.``
    to every boundary. A run of marks is likewise one boundary, so ``kæt##``
    derives as ``kæt#`` does.

    That fails for insertions unless the anchor set is coalesced, because a
    run offers one gap per mark plus one. In ``#tæt#`` the gap before the
    leading ``#`` and the gap after it both satisfy ``# _``, so ``∅ -> ə /
    # _`` inserted twice where ``tæt`` inserted once: ``ə#ətæt#ə``. The
    explicit mark and the virtual edge past it are **one** boundary, not
    two anchors.

    So a run -- with the virtual edge counted as part of any run it touches
    -- contributes ONE gap, and which one is a real choice:

    * A run touching a form edge offers only its **inner** gap. There is
      nothing outside the form to insert into, and prothesis puts the
      schwa *in* the word: ``#ətæt#``, not ``ə#tæt#``. Anchoring the outer
      gap would spell a second word.
    * An interior run offers its first gap, and *also* its last gap when
      the left context matched the mark itself. ``[vowel] _ [vowel]``
      steps over the dot in ``a.a`` and sees the same two vowels from
      either gap, so those are one position; ``. _`` names the margin, and
      then "after the margin" is a position of its own. Testing whether
      the mark is among the matched left indices is the precise question --
      asking merely whether the context names *some* boundary is not,
      because ``# _`` matches the virtual edge instead and every gap would
      qualify. Restricting the exception to the run's last gap is what
      keeps ``a..a`` deriving as ``a.a`` does.

    Anchoring only the run's first gap is wrong in the other direction: at
    a form-final dot it discards the only gap ``. _`` can hold at, and
    paragoge stops firing.
    """
    lo, hi = _run(items, gap)
    if lo == 0:
        # Touches the start edge (or is the empty run at gap 0).
        return gap == hi
    if hi == limit:
        # Touches the end edge (or is the empty run at the last gap).
        return gap == lo
    # `(hi - 1) in left` conflated "the left context matched a mark in this
    # run" with "it matched the run's LAST mark". A liaison rule naming '‿'
    # lost its site the moment a syllable dot was written after the link:
    # the dot displaced '‿' from last position, so the gap after the run
    # stopped being an anchor and the copy had nowhere to land. No spelling
    # of the rule avoided it -- '#', '%', '‿' were all measured and all
    # failed identically -- because the position that must be written to is
    # the one that stopped counting. Any mark the context matched licenses
    # the trailing gap; 'a.a' and 'a..a' are unaffected, which is what shows
    # this is the last-mark test and not the run rule itself.
    return gap == lo or (gap == hi and any(i in left for i in range(lo, hi)))


def _bound(bindings: dict[str, str]) -> tuple[tuple[str, str], ...]:
    """A site's variable environment, frozen for the record.

    Insertion order, which is binding order, so nothing here depends on a
    hash and a :class:`Site` stays hashable.
    """
    return tuple(bindings.items())


@dataclass(frozen=True)
class Query:
    """The left-hand side of a rule: what to recognize.

    Usable without an action. :meth:`sites` answers "where does this
    environment hold", which is a question worth asking of a corpus with
    no rewrite attached.
    """

    target: Pattern | None
    left: tuple[Pattern, ...] = ()
    right: tuple[Pattern, ...] = ()

    def _side(
        self,
        items: Sequence[Unit],
        anchor: int,
        patterns: Sequence[Pattern],
        step: int,
        features: IPAFeatures,
        bindings: dict[str, str] | None = None,
    ) -> tuple[int | None, ...] | None:
        """Match context outward from ``anchor``; None if it fails.

        ``patterns`` is ordered innermost-first, so it reads outward from
        the target in both directions.

        ``bindings`` is the site's variable environment, threaded through
        so a context item can agree with the target or with an item on
        the other side. It is mutated as items bind, and the caller
        discards it if the site does not hold -- a half-matched side must
        not leave a binding behind for the next position to check against.
        """
        matched: list[int | None] = []
        index = anchor
        past_the_end = False
        on_boundary = False
        probe = {} if bindings is None else bindings
        for pattern in patterns:
            if past_the_end:
                # The form has one edge, not an unbounded run of them:
                # '_ # # #' used to match it once per '#' and fire.
                return None
            if on_boundary and pattern.names_boundary:
                # A boundary RUN is one boundary, so two boundary patterns
                # in a row cannot both hold. Scanning outward, the previous
                # pattern has just taken a boundary; the next unit is either
                # another boundary in the same run -- the same boundary, so
                # not a second one -- or a segment, which no boundary
                # pattern matches anyway. Without this, '_ # #' matched
                # 'kæt#' (written mark, then the virtual edge) while not
                # matching 'kæt', so typing a redundant final '#' turned a
                # rule on. A non-boundary pattern may still follow, which is
                # what makes '_ # [vowel]' reach across a word mark.
                return None
            resume = index
            index += step
            # Step over optional notation the pattern does not want. Not
            # "unless the pattern names a boundary": naming '.' should
            # stop the skip, but naming '#' should not, or a dot beside a
            # word edge blocks a '#' context and the optional dot changes
            # which rules fire after all.
            #
            # These two are PROBES -- they ask whether an item is there,
            # and the answer decides where the real match happens -- so
            # they are asked of a copy of the environment. A probe that
            # bound a variable would let a position the rule stepped over
            # decide what a position it kept has to agree with.
            while (
                0 <= index < len(items)
                and items[index].transparent
                and not pattern.matches(items[index], features, dict(probe))
            ):
                index += step
            if pattern.optional and (
                not 0 <= index < len(items)
                or not pattern.matches(items[index], features, dict(probe))
            ):
                # Nothing here to take, and the item said it need not be.
                # The cursor goes back to where this item started, so the
                # next one reads the position the absent one would have
                # occupied -- which is what makes '_ (∅) ʃ' hold of 'eʃ'
                # as well as of 'e∅ʃ'. None, as for the virtual edge:
                # no unit licensed this item, because there is none.
                index = resume
                matched.append(None)
                continue
            if not 0 <= index < len(items):
                # Running off the form is the strongest edge there is, so
                # '#' matches there without one having been typed -- and
                # since the tiers nest, so does any weaker level: the edge
                # of a form is a syllable margin as well as a word margin.
                edge = pattern.boundary
                if edge is not None and (
                    edge == "any" or _reaches(_edge_level(features), edge, features)
                ):
                    # None, not -1: -1 is a valid index, so a consumer
                    # reading items[site.right[0]] would be handed the
                    # last unit of the form as its own licensor.
                    matched.append(None)
                    past_the_end = True
                    continue
                return None
            if not pattern.matches(items[index], features, bindings):
                return None
            matched.append(index)
            on_boundary = items[index].is_boundary
        return tuple(matched)

    def sites(self, items: Sequence[Unit], features: IPAFeatures) -> list[Site]:
        """Every non-overlapping position where this environment holds.

        Scanned left to right against ``items`` as given -- the caller
        passes a snapshot, and nothing here mutates it.
        """
        found: list[Site] = []
        index = 0
        limit = len(items)
        while index <= limit:
            # One environment per candidate position, discarded with the
            # candidate. A variable is a statement about ONE site, so a
            # binding must not outlive the attempt that made it.
            bindings: dict[str, str] = {}
            if self.target is None:
                # An insertion sits between units, so it is anchored on
                # the gap: left context ends at index-1, right begins at
                # index.
                left = self._side(items, index, self.left, -1, features, bindings)
                right = self._side(items, index - 1, self.right, +1, features, bindings)
                if (
                    left is not None
                    and right is not None
                    and _anchors(items, index, limit, left)
                ):
                    found.append(Site(index, index, left, right, _bound(bindings)))
                index += 1
                continue
            if index >= limit:
                break
            unit = items[index]
            # Not `unit.is_boundary or ...`: a boundary target is a real
            # rule (module docstring), and Pattern.matches already answers
            # False for a boundary unless the pattern names one, so the
            # extra clause skipped exactly the rules the parser then had
            # to refuse -- it is what made `∅ -> .` fire while `. -> ∅`
            # could not have.
            if not self.target.matches(unit, features, bindings):
                index += 1
                continue
            left = self._side(items, index, self.left, -1, features, bindings)
            right = self._side(items, index, self.right, +1, features, bindings)
            if left is None or right is None:
                index += 1
                continue
            found.append(Site(index, index + 1, left, right, _bound(bindings)))
            index += 1
        return found


# --------------------------------------------------------------------------
# Action: Site -> Edit
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Edit:
    """One change, as a replacement of a span by a (possibly empty) run.

    Holds enough to be reported without re-deriving anything: the rule
    that made it, the span it covers, and how that span read before and
    after.
    """

    rule: str
    start: int
    end: int
    replacement: tuple[Unit, ...]
    before: str
    after: str
    site: Site

    @property
    def is_insertion(self) -> bool:
        return self.start == self.end

    @property
    def is_deletion(self) -> bool:
        return not self.replacement and self.start != self.end

    def __str__(self) -> str:
        before = self.before or "∅"
        after = self.after or "∅"
        return f"{self.rule}: {before} {ARROWS[0]} {after} @{self.start}"


def _carry_prosody(
    written: Sequence[Unit], carried: Sequence[str], features: IPAFeatures
) -> tuple[Unit, ...]:
    """Put the target's surviving prosody onto the units replacing it.

    A literal right-hand side of one unit has one place to put a mark,
    and a right-hand side of two or more has to answer a question the
    single-unit case never asked: ``rewrite("katː", "t -> ts")`` gave
    ``kats``, the geminate's length dropped on the floor, because
    "carry it across" does not say *which* of the new units carries it.

    **A mark stays on the side of the span it was written on.** The
    replacement occupies the position the target occupied, and a
    prosodic mark is written either before its unit (``ˈa``) or after it
    (``aː``); so a mark written before the target goes on the first of
    the units replacing it and a mark written after goes on the last. It
    is the same claim :func:`_anchors` makes about a boundary run --
    the position is the span's edge, not one of its members -- applied
    to the marks that ride the span rather than divide it.

    That is one rule, not a rule per feature, and it lands where each
    feature wants to be. ``t -> ts`` on ``tː`` gives ``tsː``: length on
    a coda belongs at the end of it, which is the answer LAST alone
    would give. ``a -> ai`` on ``ˈa`` gives ``ˈai``: stress belongs on
    the nucleus, which here is the first unit, and is the answer FIRST
    alone would give. Neither of those is chosen; both fall out of where
    the notation puts the glyph. ALL is excluded by the same reading --
    ``tːsː`` states the length twice and ``ˈaˈi`` two stresses inside
    one syllable, and a mark is a property of the position, not a
    property distributed over whatever fills it.

    Which side a mark is written on is asked of
    :attr:`~ipakit.IPAFeatures.stress_markers`, the library's one derived
    read of that partition -- the same read :meth:`Segment.to_ipa` uses
    to decide where to put the glyph. So the side a mark *lands* on here
    and the side it is *spelled* on there cannot come apart, and no list
    of prosodic feature names appears in this module for this either.
    Today that is 2 leading marks (``ˈ ˌ``) and 19 trailing.

    Degenerate on the single-unit case, where first and last are the
    same unit: this changes nothing about ``t -> ʔ`` on ``tː``.
    """
    if not carried:
        return tuple(written)
    bearers = [i for i, unit in enumerate(written) if unit.segment is not None]
    if not bearers:
        # Nothing here can wear a mark -- a zero right-hand side, say.
        # The prosody goes with the segment it was a property of.
        return tuple(written)
    leading = tuple(g for g in carried if g in features.stress_markers)
    trailing = tuple(g for g in carried if g not in features.stress_markers)
    # One assignment per side; the two coincide when there is one bearer,
    # which is what makes the single-unit case fall out rather than be a
    # branch of its own.
    landed: dict[int, tuple[str, ...]] = {bearers[0]: leading}
    landed[bearers[-1]] = landed.get(bearers[-1], ()) + trailing
    out = list(written)
    for index, glyphs in landed.items():
        if not glyphs:
            continue
        segment = out[index].segment
        assert segment is not None  # bearers are the units that have one
        out[index] = _unit_for(
            dataclasses.replace(segment, prosody=segment.prosody + glyphs),
            features,
        )
    return tuple(out)


def _resolve_agreements(
    change: Change, site: Site, features: IPAFeatures, rule: str
) -> dict[str, str | None]:
    """Replace each variable in a change by what this site bound it to.

    The last place a variable could go quiet, and it does not. A change
    naming an unbound variable **raises** rather than dropping the term
    or writing nothing: dropping it would apply the rest of the change
    and report an edit, which is a well-formed wrong answer of exactly
    the shape docs/reviewing.md is about. :func:`parse` refuses the rule
    that would reach here, so this is a guard on the invariant rather
    than a path a written rule can take.
    """
    bound = dict(site.bindings)
    out: dict[str, str | None] = {}
    for key, value in change.items():
        if not isinstance(value, Agreement):
            out[key] = value
            continue
        if value.name not in bound:
            raise RuleError(
                f"{rule or 'this rule'} writes {key}={value} at a site where "
                f"{value.name!r} never bound. A variable takes its value from "
                "the left of the arrow, so it has to be named there too."
            )
        out[key] = (
            bound[value.name]
            if value.same
            else _opposite(key, bound[value.name], features)
        )
    return out


@dataclass(frozen=True)
class Action:
    """The right-hand side of a rule: what to do at a site.

    ``becomes`` is a feature change (a mapping), a literal spelling, or
    ``None`` to delete. A feature change is realized through
    :meth:`~ipakit.IPAFeatures.respell` where the result is a registered
    phone, and otherwise by composing the declared marks -- so
    ``[voiced=+]`` on ``t`` gives the registered ``d`` while
    ``[release=aspirated]`` gives the composed ``tʰ``. A change the
    inventory can spell neither way does not fire, rather than inventing
    a symbol.

    A change naming a **prosodic** feature takes a third route, because
    the first two cannot carry it. Prosody lives on the unit and not in
    the feature bag (docs/ties.md), so ``respell`` reports
    ``length=normal`` for a long vowel and answers the unchanged phone,
    and ``compose_unit`` verifies through the bag and therefore answers
    ``None``. Both are right about what they spell; neither spells
    prosody. :func:`~ipakit.form.with_prosody` does, by rewriting
    :attr:`Segment.prosody`, and a change is split by declared mode so
    each half goes where it can be realized. Before this the prosodic
    half passed the parser's feature-name check -- which advertises that
    prosody is writable -- and then evaporated.

    A change may name an :class:`Agreement` rather than a value, and the
    site is where that is answered: the value is whatever the recognition
    half bound at *this* site, so ``n -> [place=α] / _ [place=α]`` writes
    a different place at each of them. The variable is resolved into a
    plain value before anything else looks, so ``respell``,
    ``compose_unit`` and ``with_prosody`` see exactly what they saw
    before and this feature adds no case to any of them.
    """

    becomes: Becomes

    def edit(
        self,
        site: Site,
        items: Sequence[Unit],
        features: IPAFeatures,
        rule: str = "",
        named: frozenset[str] = frozenset(),
    ) -> Edit | None:
        """The edit this action makes at ``site``, or ``None`` for none.

        ``named`` is the prosody the *recognition* half spoke about, which
        a literal rewrite needs in order to know what its own silence
        means; :class:`Rule` supplies it from its target pattern. Empty by
        default, so an action driven from a site found some other way
        still behaves -- it then carries every prosody across, which is
        the safe reading when nothing said otherwise.
        """
        before = spell(items[site.start : site.end])
        target = items[site.start] if site.start < site.end else None
        replacement: tuple[Unit, ...]

        if self.becomes is None:
            replacement = ()
        elif isinstance(self.becomes, str):
            written = tuple(units(self.becomes, features))
            # A literal on the right spells a whole unit, prosody
            # included, so what it leaves unspelled has to be decided
            # rather than defaulted. The target's prosody carries across
            # -- 't -> ʔ' silently shortened 'aːtː' and dropped tone
            # before it did, and length and tone are phonemic in many
            # inventories, so that was a wrong answer and not a nicety --
            # EXCEPT for a feature either side named. Naming length on
            # the left and not on the right is how 'aː -> a' says the
            # length goes away; without the exception it is the no-op it
            # used to be.
            #
            # A replacement of MORE THAN ONE unit has to say which of them
            # inherits, and the answer is read off where the mark is
            # written rather than chosen per feature: see _carry_prosody.
            if target is not None and target.segment:
                stated = set(named)
                for unit in written:
                    stated |= set(unit.prosody)
                carried = tuple(
                    glyph
                    for glyph in target.segment.prosody
                    if not stated & set(declared_prosody(glyph, features))
                )
                written = _carry_prosody(written, carried, features)
            replacement = written
        else:
            if target is None or target.segment is None:
                return None
            change = _resolve_agreements(self.becomes, site, features, rule)
            # Split by declared mode, read off Feature.mode, so no list of
            # prosodic feature names appears here either.
            prosodic = {k: v for k, v in change.items() if _is_prosodic(k, features)}
            segmental = {
                k: v
                for k, v in change.items()
                if v is not None and not _is_prosodic(k, features)
            }
            seg = target.segment
            if segmental:
                spelled = features.respell(target.core, **segmental)
                if spelled is None:
                    # respell only answers with a *registered* phone, and
                    # the fine-grained phones an allophonic rule produces
                    # are composed rather than registered -- there is no
                    # entry for tʰ or ɪ̃. Compose from the declared marks
                    # instead, which is the library's own inverse and
                    # knows the mode order.
                    spelled = features.compose_unit(target.core, **segmental)
                if spelled is None:
                    # Neither registered nor composable. A rule that
                    # cannot be realized does not fire, rather than
                    # inventing a symbol.
                    return None
                seg = dataclasses.replace(
                    features.segment(spelled), prosody=seg.prosody
                )
            if prosodic:
                written_seg = with_prosody(seg, prosodic, features)
                if written_seg is None:
                    # The inventory cannot spell the prosody asked for, or
                    # the result did not read back as what was asked. Same
                    # rule as a segmental change it cannot spell: do not
                    # fire.
                    return None
                seg = written_seg
            replacement = (_unit_for(seg, features),)

        after = spell(replacement)
        if before == after:
            return None
        return Edit(
            rule=rule,
            start=site.start,
            end=site.end,
            replacement=replacement,
            before=before,
            after=after,
            site=site,
        )


# --------------------------------------------------------------------------
# Rules
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Rule:
    """A :class:`Query` composed with an :class:`Action`.

    The halves stay reachable: :attr:`query` recognizes without acting,
    :attr:`action` acts on a site found any other way.
    """

    name: str
    query: Query
    action: Action
    source: str = ""
    #: Written ``~>``: the rule *may* fire at a site rather than does.
    #: Honoured by :class:`RuleSet`, which is where a derivation lives;
    #: :meth:`apply` below is the mechanism and applies every edit it
    #: finds, optional or not.
    optional: bool = False

    @property
    def target(self) -> Pattern | None:
        return self.query.target

    @property
    def becomes(self) -> Becomes:
        return self.action.becomes

    @property
    def inserts(self) -> bool:
        return self.query.target is None

    @property
    def deletes(self) -> bool:
        return self.action.becomes is None and self.query.target is not None

    def recognize(
        self, form: str | Sequence[Unit], features: IPAFeatures | None = None
    ) -> list[Site]:
        """Where this rule's environment holds. No rewriting."""
        features = _default(features)
        items = units(form, features) if isinstance(form, str) else form
        return self.query.sites(items, features)

    def edits(
        self, form: str | Sequence[Unit], features: IPAFeatures | None = None
    ) -> list[Edit]:
        """The edits this rule would make, without making them."""
        features = _default(features)
        items = units(form, features) if isinstance(form, str) else form
        # What the left half named is what the right half's silence is
        # about; see Action.edit and Pattern.prosodic_keys. The halves stay
        # separable -- this is the composition telling the action something
        # it could not otherwise know, not the action reaching backwards.
        named = self.query.target.prosodic_keys if self.query.target else frozenset()
        out = []
        for site in self.query.sites(items, features):
            edit = self.action.edit(site, items, features, rule=self.name, named=named)
            if edit is not None:
                out.append(edit)
        return out

    def apply(
        self, form: str | Sequence[Unit], features: IPAFeatures | None = None
    ) -> tuple[list[Unit], list[Edit]]:
        """Apply this rule once, against a snapshot of ``form``.

        Every edit, including those of an :attr:`optional` rule. This is
        the mechanism; whether an optional rule *is* applied is a fact
        about a derivation, and :class:`RuleSet` is where derivations
        live. Pinned by a test, so the limit stays known rather than
        assumed shut.
        """
        features = _default(features)
        items = list(units(form, features) if isinstance(form, str) else form)
        found = self.edits(items, features)
        return _apply_edits(items, found), found

    def __str__(self) -> str:
        return self.source or self.name


def _apply_edits(items: list[Unit], edits: Sequence[Edit]) -> list[Unit]:
    """Splice edits into a sequence, rightmost first so indices hold."""
    out = list(items)
    for edit in sorted(edits, key=lambda e: e.start, reverse=True):
        out[edit.start : edit.end] = list(edit.replacement)
    return out


# --------------------------------------------------------------------------
# Notation
# --------------------------------------------------------------------------


def parse(text: str, features: IPAFeatures | None = None) -> Rule:
    """Build a :class:`Rule` from the notation.

    ::

        t -> [manner=tap voiced=+] / [vowel stress=primary] _ [vowel]
        ∅ -> ə / [manner=plosive] _ [manner=plosive] #
        ə -> ∅ / [vowel] [manner=plosive] _
        t -> ʔ / _ #  ; glottalling

    The arrow may be ``->``, ``→`` or ``=>``. Everything after ``/`` is
    the context, with ``_`` where the target sits. ``#`` is a word edge,
    ``.`` a syllable break, ``%`` either, and ``∅`` (or ``0``) the empty
    string. A bracketed item is a feature query in the language
    :meth:`~ipakit.IPAFeatures.phones_matching` accepts; a bare glyph is
    a literal phone. Anything after ``;`` names the rule -- not ``|``,
    which is a declared prosodic break and so a legal context item.

    ``~>`` in place of the arrow marks the rule **optional**: it may fire
    at a site or not, and :meth:`RuleSet.variants` enumerates the choices.
    ``~->``, ``~→`` and ``~=>`` say the same of the other two arrows.
    """
    features = _default(features)
    source = text.strip()
    if not source:
        raise RuleError("empty rule")

    # ';' not '|': '|' is a declared prosodic break, so a context naming
    # it ('t -> ʔ / _ |') was silently swallowed as the name separator and
    # the rule became unconditional -- a misparse that fires everywhere.
    body, _, name = source.partition(NAME_SEP)
    body, name = body.strip(), name.strip()

    # Optional spellings first, and longest first within them: '~=>'
    # contains '=>' and '~->' contains '->', so asking the plain arrows
    # first would read every optional rule as an obligatory one with a
    # stray '~' on its left-hand side -- which then fails as an
    # unregistered literal, loudly, but for the wrong reason.
    optional = False
    arrow = next((a for a in OPTIONAL_ARROWS if a in body), None)
    if arrow is not None:
        optional = True
    else:
        arrow = next((a for a in ARROWS if a in body), None)
    if arrow is None:
        if OPTIONAL_MARK in body:
            raise RuleError(
                f"{source!r} has no rewrite arrow. {OPTIONAL_MARK!r} marks an "
                f"arrow optional and is not one on its own; write "
                f"'{OPTIONAL_ARROWS[-1]}' (or "
                f"{', '.join(repr(a) for a in OPTIONAL_ARROWS[:-1])})."
            )
        raise RuleError(
            f"{source!r} has no rewrite arrow; expected one of {', '.join(ARROWS)}"
        )
    lhs, _, rest = body.partition(arrow)
    rhs, slash, context = rest.partition("/")
    lhs, rhs, context = lhs.strip(), rhs.strip(), context.strip()

    if not lhs:
        raise RuleError(f"{source!r} has nothing on the left of the arrow")
    if not rhs:
        raise RuleError(f"{source!r} has nothing on the right of the arrow")

    target = None if lhs in NULL else _pattern(lhs, features)
    becomes = _becomes(rhs, features)
    if target is None and becomes is None:
        raise RuleError(f"{source!r} rewrites nothing as nothing")
    if target is not None:
        _check_no_exchange(source, target, becomes, features)
        _check_zero_target(source, target, becomes, features)
    if target is not None and target.optional:
        raise RuleError(
            f"{source!r} marks its target optional, and a target is what the "
            "rule rewrites: there is nothing to rewrite where it is absent. "
            "Optionality is for context items."
        )
    if target is None and isinstance(becomes, str) and becomes in features.zeros:
        raise RuleError(
            f"{source!r} inserts a zero. A zero records that a position had "
            "content and now has none; an insertion had none to lose, so "
            "there is nothing here for it to record. Write the zero on the "
            f"left of the arrow instead ('x -> [{ZERO_CLASS}]')."
        )

    left: tuple[Pattern, ...] = ()
    right: tuple[Pattern, ...] = ()
    if slash:
        if "_" not in context:
            raise RuleError(
                f"{source!r} has a context but no '_' marking where the target sits"
            )
        before, _, after = context.partition("_")
        # Innermost first, so both sides read outward from the target.
        left = tuple(reversed([_pattern(i, features) for i in _items(before)]))
        right = tuple(_pattern(i, features) for i in _items(after))

    _check_variables(source, target, left, right, becomes)

    return Rule(
        name=name or source,
        query=Query(target=target, left=left, right=right),
        action=Action(becomes=becomes),
        source=source,
        optional=optional,
    )


def _check_variables(
    source: str,
    target: Pattern | None,
    left: Sequence[Pattern],
    right: Sequence[Pattern],
    becomes: Becomes,
) -> None:
    """Refuse a rule whose variables cannot mean anything.

    Three refusals, and each is here rather than at match time because
    each would otherwise be a **site-dependent** answer: a rule that is
    fine on one form and quietly does nothing on the next. That is the
    live lesson of this repository, and adding a second instance of it
    while adding a feature would be the fourth time this session that
    documentation and behavior came apart.

    *One feature per variable.* ``[place=α] ... [voiced=α]`` asks a value
    of ``place`` to equal a value of ``voiced``, which no phone can
    satisfy; a rule that merely never fired would say nothing about why.

    *Bound before referred to.* Recognition binds and the action refers,
    so a variable on the right that the left never names is refused. This
    is the one the arrow's shape makes easy to get wrong -- the right of
    the arrow is written first and read first, and it is not where a
    value comes from.

    *Used at least twice.* A variable naming one position agrees with
    nothing. It is the shape a typo takes -- ``α`` on the left and ``γ``
    on the right is two lone variables, not one shared one -- and
    refusing it is what turns that into a message instead of a rule that
    parses and matches the wrong thing.
    """
    query = [p for p in (target, *left, *right) if p is not None]
    features_of: dict[str, str] = {}
    counted: dict[str, int] = {}
    bound: set[str] = set()

    def record(key: str, variable: Agreement, binds: bool) -> None:
        counted[variable.name] = counted.get(variable.name, 0) + 1
        if binds:
            bound.add(variable.name)
        seen = features_of.setdefault(variable.name, key)
        if seen != key:
            raise RuleError(
                f"{source!r} uses the variable {variable.name!r} on two "
                f"features, {seen!r} and {key!r}. A variable ranges over the "
                "declared values of ONE feature -- two features declare two "
                "different sets of values, so there is nothing for it to be. "
                "Use a second variable for the second feature."
            )

    for pattern in query:
        for key, variable in pattern.agreements.items():
            record(key, variable, binds=True)
    if isinstance(becomes, dict):
        for key, value in becomes.items():
            if isinstance(value, Agreement):
                record(key, value, binds=False)

    unbound = sorted(name for name in counted if name not in bound)
    if unbound:
        raise RuleError(
            f"{source!r} writes the variable(s) {', '.join(unbound)} on the "
            "right of the arrow, and nothing on the left binds them. A "
            "variable takes its value from what the rule MATCHED, so it has "
            "to appear in the target or the context: "
            f"'n -> [place={unbound[0]}] / _ [place={unbound[0]}]'."
        )
    lonely = sorted(name for name, count in counted.items() if count < 2)
    if lonely:
        raise RuleError(
            f"{source!r} uses the variable(s) {', '.join(lonely)} once. A "
            "variable says that two positions carry the same value, so one "
            "occurrence says nothing; name the value if that is what was "
            "meant, or write the second occurrence."
        )


def _boundary_spellings(features: IPAFeatures) -> frozenset[str]:
    """Every glyph that spells a boundary, asked of the declaration.

    ``<separators>`` plus the declared break and linking marks, on the
    same terms :func:`_pattern` asks it, so a newly declared mark is
    covered without an edit here. ``%`` is deliberately not among them:
    it is a wildcard over the declared marks and names no particular one,
    so it can be recognized and never written.
    """
    return frozenset(features.separators) | frozenset(boundary_marks(features))


def _check_no_exchange(
    source: str,
    target: Pattern,
    becomes: Becomes,
    features: IPAFeatures,
) -> None:
    """Refuse a rewrite that trades a boundary for a segment, either way.

    A boundary may be written, unwritten and restated at another level;
    what it may not do is change places with a segment, because it is a
    relation between segments and not one of them (module docstring). The
    invariant that states this positively is that a boundary rewrite
    leaves the segmental string byte-identical, and these are the three
    shapes that would break it.
    """
    marks = _boundary_spellings(features)
    written = becomes if isinstance(becomes, str) else ""
    if target.names_boundary:
        if isinstance(becomes, dict):
            raise RuleError(
                f"{source!r} changes features of the boundary "
                f"{target.source!r}; a query is compared against a feature "
                "bundle and a boundary has none, so this could only ever "
                f"match nothing. Write the boundary you mean "
                f"('{target.source} -> #'), or delete it "
                f"('{target.source} -> ∅')."
            )
        if becomes is not None and written not in marks:
            raise RuleError(
                f"{source!r} rewrites the boundary {target.source!r} as "
                f"{written!r}, which is not a boundary; a boundary is a "
                "relation between segments, not a segment, so the two cannot "
                "be exchanged. A boundary may be written ('∅ -> .'), unwritten "
                "('. -> ∅') or restated at another level ('. -> #'); to put a "
                "segment where one stood, delete the boundary and insert the "
                "segment, which is two ordered rules."
            )
        return
    offending = [glyph for glyph in written if glyph in marks]
    if offending:
        raise RuleError(
            f"{source!r} rewrites {target.source!r} as the boundary "
            f"{offending[0]!r}; a boundary is a relation between segments, "
            "not a segment, so the two cannot be exchanged. Delete the "
            f"segment ('{target.source} -> ∅') and assert the boundary "
            f"('∅ -> {offending[0]}' with the context that places it), which "
            "is two ordered rules."
        )


def _check_zero_target(
    source: str,
    target: Pattern,
    becomes: Becomes,
    features: IPAFeatures,
) -> None:
    """Refuse a feature change on a zero, for the boundary's reason.

    A query is compared against a feature bundle and a zero has none --
    that is what a zero *is* -- so ``[zero] -> [voiced=+]`` could only
    ever match and then decline, silently, in :meth:`Action.edit`. The
    two things a rule can legitimately do with a zero are fill it
    (``[zero] -> z``) and unwrite it (``[zero] -> ∅``).
    """
    if target.literal is None or target.literal not in features.zeros:
        return
    if isinstance(becomes, dict):
        raise RuleError(
            f"{source!r} changes features of the zero {target.source!r}; a "
            "zero is a position with no content, so it has no bundle for a "
            "change to be applied to. Fill it with the phone you mean "
            f"('{target.source} -> z'), or unwrite it "
            f"('{target.source} -> ∅')."
        )


def _becomes(rhs: str, features: IPAFeatures) -> Becomes:
    """What the right of the arrow says to do.

    A bracketed change comes back as a mapping, with ``None`` for a value
    the rule **clears** -- written with the same ``∅`` the notation
    already uses for the empty string, one dimension at a time instead of
    the whole unit. Clearing is only meaningful for prosody: a segmental
    feature always has a value, so ``[voiced=∅]`` names nothing and is
    refused rather than guessed at.

    Prosodic values are checked against the declaration here, because the
    prosodic path does not go through ``respell`` and would otherwise be
    the one place a misspelled value stayed quiet.
    """
    if rhs in NULL:
        return None
    if rhs.startswith("[") and rhs.endswith("]"):
        terms = [t for t in rhs[1:-1].replace(",", " ").split() if t]
        # '[zero]' writes a zero: a position that had content and now has
        # none, recorded. That is a different statement from '∅', which is
        # the empty string -- 'z -> ∅' says the /z/ is gone, 'z -> [zero]'
        # says a /z/ was here and could surface, which is what a latent
        # consonant needs. The symbol is the declared one, so this is a
        # literal from here on and the rest of the machinery is untouched.
        if (zero := _zero_named(terms, features)) is not None:
            return zero
        if not terms or not all("=" in t for t in terms):
            raise RuleError(
                f"{rhs!r} is a change, so every term must be 'key=value'; "
                "a bare class does not say what to change it to"
            )
        pairs = dict(t.split("=", 1) for t in terms)
        unknown = sorted(k for k in pairs if k not in features.features)
        if unknown:
            raise RuleError(f"{rhs!r} names undeclared feature(s): {unknown}")
        change: Change = {}
        for key, value in pairs.items():
            prosodic = _is_prosodic(key, features)
            # A variable is taken before the value checks below, exactly
            # as on the left of the arrow, so it is never a value that
            # failed to resolve. Which variables may appear here is
            # :func:`parse`'s question, because only the whole rule knows
            # what the recognition half bound.
            variable = _agreement(value, features)
            if variable is not None:
                if not variable.same:
                    _check_opposite(rhs, key, features)
                change[key] = variable
                continue
            if value in NULL:
                if not prosodic:
                    raise RuleError(
                        f"{rhs!r} clears {key!r}, but only prosody can be absent: "
                        f"every phone has some {key!r}, so there is nothing for "
                        "'∅' to mean. Name the value to change it to."
                    )
                change[key] = None
                continue
            feature = features.features[key]
            resolved = feature.value_aliases.get(value, value)
            # A sequence-valued feature takes a run of its values in time
            # order, so every step is checked rather than the spelling of
            # the whole -- 'low>high' is a tone the data never lists and
            # every contour is one.
            if prosodic and any(
                step not in feature.values_set for step in feature.steps(resolved)
            ):
                raise RuleError(
                    f"{rhs!r}: {value!r} is not a declared value of {key!r}; "
                    f"declared are {list(feature.values)}"
                )
            change[key] = resolved
        return change
    # A literal that spells no phone spells nothing to put anywhere. An
    # insertion inserts a position, and a prosodic mark is a property of a
    # position rather than one of its own, so '∅ -> ˈ' had no unit to
    # attach to and quietly did nothing at all.
    core, _ = split_prosody(rhs, features)
    if not core:
        raise RuleError(
            f"{rhs!r} is prosody with no phone under it. A prosodic mark rides "
            "on a unit rather than occupying a position of its own, so there is "
            "nothing here to insert; write the feature on the unit instead -- "
            "'[vowel] -> [length=long] / _ #', not '∅ -> ː / [vowel] _ #'."
        )
    # The same question of the other side, and here the silence was a
    # wrong answer rather than a no-op: an unregistered literal reads as
    # zero units, so 't -> Q' spelled the empty replacement and deleted
    # the 't' exactly as 't -> ∅' does. A rule that changes OPERATION on a
    # typo cannot be left to the read's own "dropped 1 unregistered
    # symbol", which reports the symbol and not the substitution it
    # turned into a deletion. Several units are fine here, unlike in a
    # pattern: a rule may insert a cluster.
    _check_literal(rhs, features)
    return rhs


#: The grouping pairs a context item may be wrapped in: a feature query
#: and an optional item. Both nest, and both may contain spaces, so
#: neither can be split on whitespace alone -- '([vowel])' has to arrive
#: as one item to be refused as one, rather than as three of which the
#: middle one looks fine.
_GROUPS = {"[": "]", "(": ")"}
_CLOSERS = {close: open_ for open_, close in _GROUPS.items()}


def _items(text: str) -> list[str]:
    """Split one context side into notation items."""
    out: list[str] = []
    buffer = ""
    depth = 0
    for char in text:
        if char in _GROUPS:
            if depth == 0 and buffer.strip():
                out.append(buffer.strip())
                buffer = ""
            depth += 1
        elif char in _CLOSERS:
            depth -= 1
            if depth < 0:
                raise RuleError(f"unbalanced {char!r} in {text!r}")
        if depth == 0 and char.isspace():
            if buffer.strip():
                out.append(buffer.strip())
            buffer = ""
            continue
        buffer += char
        if depth == 0 and char in _CLOSERS:
            out.append(buffer.strip())
            buffer = ""
    if depth:
        raise RuleError(f"unbalanced grouping in {text!r}")
    if buffer.strip():
        out.append(buffer.strip())
    return out


# --------------------------------------------------------------------------
# Ordered application
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Step:
    """One rule's turn in a derivation, whether or not it fired."""

    rule: str
    before: str
    after: str
    edits: tuple[Edit, ...]
    #: Whether the rule was written with the optional arrow. A step that
    #: is optional and did not fire is a **choice not taken**, not a rule
    #: whose environment failed, and a trace that spelled the two alike
    #: would be the first silent wrong answer this feature could tell.
    optional: bool = False

    @property
    def fired(self) -> bool:
        return bool(self.edits)


@dataclass(frozen=True)
class Derivation:
    """A form, its result, and every rule's turn in between.

    :attr:`start` is the form **as the engine read it**, not the string
    handed in, so it is ``steps[0].before`` by construction. Reading a form
    can drop what the inventory does not register -- with a warning -- and
    when it did, ``derive("KÆT", ...)`` reported ``start='KÆT'`` beside
    ``steps[0].before=''``, so the trace printed the input, then
    ``(no rule fired)``, and yet :attr:`result` was not the input. A trace
    whose first line is not what the first rule saw accounts for a
    derivation that did not happen.
    """

    start: str
    result: str
    steps: tuple[Step, ...]

    @property
    def fired(self) -> tuple[Step, ...]:
        """Only the steps that changed something."""
        return tuple(s for s in self.steps if s.fired)

    @property
    def edits(self) -> tuple[Edit, ...]:
        return tuple(e for s in self.steps for e in s.edits)

    def trace(self, all_steps: bool = False) -> str:
        """A readable account of what fired, and where.

        Under ``all_steps`` the rules that did nothing are shown too, and
        they are marked **after** the name rather than before it. The
        marker used to be a prefix -- ``"  "`` against
        ``"  (no change) "`` -- so the names sat at two different columns
        and the one column a reader scans down was the one that moved:
        ``  aspiration`` under ``  (no change) tapping``. Reading a trace
        is looking for a rule by name, and a list whose names do not line
        up is harder to read the moment it is long enough to need
        ``--all`` at all.

        Marking after the name is what keeps the default output
        **byte-identical**: without ``all_steps`` every step shown has
        fired, so the marker is empty and each line is the two-space
        indent and the name, exactly as before. The two spellings differ
        only where the old one was misaligned.
        """
        lines = [self.start]
        for step in self.steps if all_steps else self.fired:
            if step.fired:
                mark = ""
            elif step.optional:
                mark = "  (not taken)"
            else:
                mark = "  (no change)"
            detail = ", ".join(str(e) for e in step.edits) or "-"
            lines.append(f"  {step.rule}{mark}\n      {detail}\n  = {step.after}")
        if not self.fired:
            lines.append("  (no rule fired)")
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.result


# --------------------------------------------------------------------------
# Optionality: one form to a set of forms
# --------------------------------------------------------------------------

#: How many variants a derivation carries from one rule to the next.
#:
#: A bound is unavoidable -- an optional rule with *n* sites offers
#: ``2 ** n`` children per branch, and the sites multiply across a cascade
#: -- and the only question is whether a caller can tell it fired. Here
#: they can: a truncated :class:`VariantSet` names the rule it was cut at
#: and how many combinations went unexplored, in the returned object,
#: because a truncated set of variants otherwise reads exactly like a
#: complete one and that is this repository's whole failure mode.
#:
#: 256 is 2**8: eight independently varying sites in a single word, which
#: is past anything a natural language offers and short of the memory a
#: mistake would take. Raise it per call; there is no ceiling on the
#: parameter.
DEFAULT_LIMIT = 256


@dataclass(frozen=True)
class Truncation:
    """One rule's expansion, cut because the limit was reached.

    ``unexplored`` counts **combinations of optional choices** the step
    did not enumerate, not distinct forms: distinct choices can spell the
    same form, so it is an upper bound on what is missing and an exact
    count of what was not looked at. It is exact rather than estimated
    because the arithmetic is known before the enumeration -- a branch
    with *n* edits offers ``2 ** n`` -- which is what makes it reportable
    without doing the work the limit exists to avoid.
    """

    #: Index of the rule in the cascade.
    step: int
    rule: str
    #: Variants carried forward from this step. Equals the limit.
    kept: int
    unexplored: int

    def __str__(self) -> str:
        return (
            f"rule {self.step + 1} ({self.rule}): kept {self.kept}, "
            f"{self.unexplored} choice combination(s) unexplored"
        )


@dataclass(frozen=True)
class Variant:
    """One member of a :class:`VariantSet`, with the derivation that made it.

    ``choices`` is how many optional edits this member takes, so the
    citation form is the one with ``choices == 0`` and a set can be read
    by how far each member departs from it.
    """

    form: str
    derivation: Derivation
    choices: int = 0

    def __str__(self) -> str:
        return self.form


@dataclass(frozen=True)
class VariantSet:
    """Every form a rule set derives from one input, and what it cost.

    Ordered, and the order is part of the answer: members appear in the
    order the cascade produced them, and within one optional rule the
    subsets of its edits are enumerated by **size** first. So
    ``variants[0]`` is always the member that takes no optional choice at
    all, which is exactly :meth:`RuleSet.apply`'s answer, and a truncated
    set keeps the members that depart least rather than an arbitrary
    prefix. Nothing here iterates a set or a hash, so the order does not
    depend on ``PYTHONHASHSEED``.

    :attr:`truncations` is empty when the answer is complete, and
    :attr:`complete` says so in one word. Ask it. A capped set of
    pronunciations is indistinguishable by eye from an exhaustive one.
    """

    start: str
    variants: tuple[Variant, ...]
    limit: int = DEFAULT_LIMIT
    truncations: tuple[Truncation, ...] = ()

    @property
    def forms(self) -> tuple[str, ...]:
        """The derived forms, in order. ``forms[0]`` takes no option."""
        return tuple(variant.form for variant in self.variants)

    @property
    def complete(self) -> bool:
        """Whether every choice the rules offer was enumerated."""
        return not self.truncations

    @property
    def truncated(self) -> bool:
        return bool(self.truncations)

    @property
    def unexplored(self) -> int:
        """Choice combinations the limit kept this answer from reaching."""
        return sum(cut.unexplored for cut in self.truncations)

    def __len__(self) -> int:
        return len(self.variants)

    def __iter__(self) -> Iterator[Variant]:
        return iter(self.variants)

    def __getitem__(self, index: int) -> Variant:
        return self.variants[index]

    def __contains__(self, item: object) -> bool:
        if isinstance(item, Variant):
            return item in self.variants
        return item in self.forms

    def __str__(self) -> str:
        return " ~ ".join(self.forms)


def _subsets(count: int) -> Iterator[tuple[int, ...]]:
    """Index subsets of ``count`` items, smallest first, then in order.

    Graded rather than binary-counted, and the grading is what makes a
    truncated answer defensible. Counting in binary enumerates every
    subset of a *prefix* of the sites and none of the rest, so a cut set
    would show the leftmost schwa varying and the rightmost never
    varying at all -- a biased sample dressed as a set. By size, the cut
    falls on the members that take the most optional choices, which is
    both the linguistically peripheral end and the one a reader expects
    to lose.
    """
    for size in range(count + 1):
        yield from itertools.combinations(range(count), size)


@dataclass(frozen=True)
class RuleSet:
    """An ordered cascade of rules.

    Order is the semantics: each rule sees the previous rule's output,
    which is where feeding and bleeding live. Within a rule, every site
    is found against a snapshot before any is rewritten, so no rule can
    feed itself.
    """

    rules: tuple[Rule, ...]
    name: str = ""

    @classmethod
    def parse(
        cls, text: str, features: IPAFeatures | None = None, name: str = ""
    ) -> RuleSet:
        """Build a rule set from one rule per line.

        Blank lines are skipped, and ``#`` begins a comment only where a
        line starts with it, since ``#`` is also the word edge.
        """
        features = _default(features)
        parsed = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parsed.append(parse(stripped, features))
        return cls(rules=tuple(parsed), name=name)

    @classmethod
    def from_file(
        cls, path: str | Path, features: IPAFeatures | None = None, name: str = ""
    ) -> RuleSet:
        """Load a rule set from a ``.rules`` file, one rule per line.

        Shipped sets live in ``ipakit/data/rules``; :func:`shipped` names
        them without a path.
        """
        text = Path(path).read_text(encoding="utf-8")
        return cls.parse(text, features, name=name or Path(path).stem)

    @property
    def optional(self) -> bool:
        """Whether any rule here is optional, so the answer is a set."""
        return any(rule.optional for rule in self.rules)

    def derive(self, form: str, features: IPAFeatures | None = None) -> Derivation:
        """Apply every obligatory rule in order, keeping the trace.

        An **optional** rule does not fire here. One form comes out, so
        one of the choices it offers has to be taken, and the only
        defensible one is the null choice: the answer is then the citation
        form, and it is exactly ``variants(form)[0].form``. Its step is
        still recorded, marked :attr:`Step.optional`, so a trace says
        *not taken* rather than passing a choice off as a failed
        environment.
        """
        features = _default(features)
        items = units(form, features)
        # Not ``form``: reading it can drop what the inventory does not
        # register, and the trace has to start from what the rules saw or
        # it accounts for a derivation that did not happen. See Derivation.
        current = spell(items)
        start = current
        steps: list[Step] = []
        for rule in self.rules:
            before = current
            if rule.optional:
                steps.append(
                    Step(
                        rule=rule.name,
                        before=before,
                        after=before,
                        edits=(),
                        optional=True,
                    )
                )
                continue
            items, edits = rule.apply(items, features)
            current = spell(items)
            steps.append(
                Step(rule=rule.name, before=before, after=current, edits=tuple(edits))
            )
        return Derivation(start=start, result=current, steps=tuple(steps))

    def apply(self, form: str, features: IPAFeatures | None = None) -> str:
        """The derived form, discarding the trace."""
        return self.derive(form, features).result

    def variants(
        self,
        form: str,
        features: IPAFeatures | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> VariantSet:
        """Every form this cascade derives, with a derivation for each.

        The set-valued counterpart of :meth:`apply`. An obligatory rule
        maps each branch to one child; an optional rule maps it to one
        child per **subset** of the edits it found, which is what makes
        the choice per site rather than per rule. Branches that converge
        on the same spelling are one member, and the derivation kept is
        the first in the order -- the one taking fewest optional edits.

        The answer is always finite: a rule is matched against a snapshot
        and cannot feed itself, so each step is finite and the cascade is
        a finite fold of them. It can nonetheless be enormous, so
        ``limit`` bounds what is carried between rules and any cut is
        reported in :attr:`VariantSet.truncations`.
        """
        features = _default(features)
        if limit < 1:
            raise ValueError(f"limit must be at least 1, not {limit!r}")
        items = list(units(form, features))
        start = spell(items)
        #: (units, the steps that produced them, optional edits taken)
        branches: list[tuple[list[Unit], tuple[Step, ...], int]] = [(items, (), 0)]
        truncations: list[Truncation] = []

        for index, rule in enumerate(self.rules):
            # Keyed by spelling, so convergent branches are one member and
            # the FIRST is kept; insertion order is the answer's order.
            carried: dict[str, tuple[list[Unit], tuple[Step, ...], int]] = {}
            unexplored = 0
            for current, steps, choices in branches:
                before = spell(current)
                found = rule.edits(current, features)
                if not rule.optional:
                    # One child per branch, so this can never exceed the
                    # limit that already held of ``branches``: an
                    # obligatory rule is a function and truncating it
                    # would drop a form that was already in the set.
                    after_items = _apply_edits(list(current), found)
                    after = spell(after_items)
                    carried.setdefault(
                        after,
                        (
                            after_items,
                            steps
                            + (
                                Step(
                                    rule=rule.name,
                                    before=before,
                                    after=after,
                                    edits=tuple(found),
                                ),
                            ),
                            choices,
                        ),
                    )
                    continue
                taken = 0
                for subset in _subsets(len(found)):
                    if len(carried) >= limit:
                        break
                    picked = tuple(found[i] for i in subset)
                    after_items = _apply_edits(list(current), picked)
                    after = spell(after_items)
                    carried.setdefault(
                        after,
                        (
                            after_items,
                            steps
                            + (
                                Step(
                                    rule=rule.name,
                                    before=before,
                                    after=after,
                                    edits=picked,
                                    optional=True,
                                ),
                            ),
                            choices + len(picked),
                        ),
                    )
                    taken += 1
                unexplored += (1 << len(found)) - taken
            if unexplored:
                truncations.append(
                    Truncation(
                        step=index,
                        rule=rule.name,
                        kept=len(carried),
                        unexplored=unexplored,
                    )
                )
            branches = list(carried.values())

        out = []
        for final, steps, choices in branches:
            spelled = spell(final)
            out.append(
                Variant(
                    form=spelled,
                    derivation=Derivation(
                        start=start, result=spelled, steps=tuple(steps)
                    ),
                    choices=choices,
                )
            )
        return VariantSet(
            start=start,
            variants=tuple(out),
            limit=limit,
            truncations=tuple(truncations),
        )

    def __iter__(self):  # type: ignore[no-untyped-def]
        return iter(self.rules)

    def __len__(self) -> int:
        return len(self.rules)


#: Directory holding the shipped rule sets.
RULES_DIR = DATA_DIR / "rules"


def shipped(name: str, features: IPAFeatures | None = None) -> RuleSet:
    """Load a rule set that ships with the library.

    ``shipped("american-english")`` is the worked example: English
    phonemes rewritten to fine-grained phones by flapping, aspiration,
    unreleased codas, dark l and vowel nasalization.
    """
    path = RULES_DIR / f"{name}.rules"
    if not path.exists():
        available = sorted(p.stem for p in RULES_DIR.glob("*.rules"))
        raise RuleError(f"no shipped rule set {name!r}; have {available}")
    return RuleSet.from_file(path, features, name=name)


def available() -> list[str]:
    """The names :func:`shipped` accepts."""
    return sorted(p.stem for p in RULES_DIR.glob("*.rules"))
