"""Rewrite-rule commands - apply, trace, recognize, and list rule sets.

Wraps :mod:`ipakit.rules`. Three things about the shape of this group are
worth knowing before reading it.

**Rules are named the same way everywhere.** Every command that needs
rules takes exactly one of ``--rule`` (notation, repeatable and ordered),
``--set`` (a shipped set) or ``--file`` (one rule per line), so a rule
written on the command line and a rule kept in a file go through the same
parser.

**Forms come from the argument list or from stdin.** With no positional
form, one form is read per line from stdin, which is what makes the group
composable with the rest of the CLI.

**Recognition is not application.** ``recognize`` asks each rule of a set
against the form *as given*, with no rewriting, so the ordering effects
that ``apply`` and ``trace`` show are deliberately absent there. A rule
late in a cascade may recognize nothing on the input and still fire on
what an earlier rule produced.

**An optional rule needs a set to answer in.** ``A ~> B`` may fire at a
site or not, so a cascade carrying one derives several forms rather than
one. ``apply`` and ``trace`` answer with a single form and therefore take
no optional choice at all; ``variants`` is where the set is, and its
first member is exactly what ``apply`` printed. Whether the answer is
complete is printed with it -- the count line says so, and ``-j`` carries
``complete`` and ``truncations`` -- because a capped set of
pronunciations reads exactly like an exhaustive one.

**A derived form is a surface form.** A rule may write a zero -- a
position kept open with nothing in it -- and a derivation carries it
where a pronunciation does not, so the last thing ``apply``, ``trace``
and ``variants`` do is the rewrite that removes them. ``--keep-zeros``
declines it and prints the derivation's own answer instead.

**An agreement variable is reported where it bound.** A rule may write
``n -> [place=α] / _ [place=α]``, and then what it did at a site depends
on what ``α`` took there. ``recognize`` prints that after the
environment, and ``-j`` carries it as ``bindings``: a site licensed by
"these two agree" has said something the neighbor list alone does not.
Nothing is printed where a rule names no variable, so the report of
every rule written before this is byte-identical.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..form import Unit, spell, units
from ..rules import (
    DEFAULT_LIMIT,
    Edit,
    Rule,
    RuleError,
    RuleSet,
    Site,
    VariantSet,
    available,
    parse,
    shipped,
)
from .base import Command, CommandGroup, add_format_arg, add_output_arg

if TYPE_CHECKING:  # pragma: no cover
    from ..features import IPAFeatures


# --------------------------------------------------------------------------
# Shared arguments
# --------------------------------------------------------------------------


def add_rules_args(parser: argparse.ArgumentParser) -> None:
    """Add the three ways of naming rules. Exactly one is required.

    ``--rule`` repeats, and repeats are an **ordered** cascade -- the same
    semantics as consecutive lines of a rule file, so ``-r A -r B`` is not
    the same rule set as ``-r B -r A``.
    """
    parser.add_argument(
        "--rule",
        "-r",
        action="append",
        metavar="NOTATION",
        help="Rule notation, e.g. 't -> ʔ / _ # ; glottalling' (repeatable, ordered)",
    )
    parser.add_argument(
        "--set",
        "-s",
        dest="named_set",
        metavar="NAME",
        help="A shipped rule set (see 'ipakit rules list')",
    )
    parser.add_argument(
        "--file",
        dest="rules_file",
        type=Path,
        metavar="FILE",
        help="A rule file, one rule per line ('#' at line start is a comment)",
    )


def add_forms_arg(parser: argparse.ArgumentParser) -> None:
    """Add the positional forms, which fall back to stdin."""
    parser.add_argument(
        "forms",
        nargs="*",
        metavar="FORM",
        help="IPA forms; with none given, read one per line from stdin",
    )


def add_zeros_arg(parser: argparse.ArgumentParser) -> None:
    """Add the switch that declines the final surface rewrite.

    A derivation carries a zero and a pronunciation does not, so the
    rewrite that removes one runs last by default. This is how to ask for
    the derivation's own last form instead. It is on the three commands
    that print a derived form and nowhere else: 'recognize' and 'units'
    rewrite nothing.
    """
    parser.add_argument(
        "--keep-zeros",
        action="store_true",
        help="Skip the final surface rewrite, keeping any zero a rule wrote",
    )


def load_file(path: Path, features: IPAFeatures) -> RuleSet:
    """Load a rule set from a path, reporting a missing file as a RuleError.

    So a mistyped path reads like every other rule problem instead of like
    an interpreter accident.
    """
    if not path.is_file():
        raise RuleError(f"no rule file {str(path)!r}")
    return RuleSet.from_file(path, features)


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def unit_text(items: list[Unit], index: int | None) -> str:
    """How one context index reads. ``None`` is the form's own edge."""
    # None, not -1: a context that matched the virtual edge past the end of
    # the form matched no unit at all, and printing items[-1] there would
    # name the last unit of the form as its own licensor.
    return "#" if index is None else items[index].text


def environment(items: list[Unit], site: Site) -> str:
    """The site's licensing neighbors, written as the notation writes them.

    ``Site.left`` is innermost-first, so it is reversed for display: the
    engine reads context outward from the target, the page reads it inward
    from the margins.
    """
    left = " ".join(unit_text(items, i) for i in reversed(site.left))
    right = " ".join(unit_text(items, i) for i in site.right)
    return " ".join(part for part in (left, "_", right) if part)


def bindings_text(bindings: dict[str, str]) -> str:
    """What the site's agreement variables took, or the empty string.

    Empty where a rule names none, which is every rule written before
    variables existed, so the line a reader has been reading does not
    move. Written from the same mapping ``site_data`` carries, so the
    text and JSON reports cannot come to disagree about it.
    """
    return " ".join(f"{name}={value}" for name, value in bindings.items())


def site_data(items: list[Unit], rule: Rule, site: Site) -> dict[str, Any]:
    """One recognized site as JSON-ready data."""
    return {
        "rule": rule.name,
        "start": site.start,
        "end": site.end,
        "target": spell(items[site.start : site.end]),
        "environment": environment(items, site),
        "left": list(site.left),
        "right": list(site.right),
        "insertion": site.is_insertion,
        "bindings": dict(site.bindings),
    }


def edit_data(edit: Edit) -> dict[str, Any]:
    """One edit as JSON-ready data."""
    return {
        "rule": edit.rule,
        "start": edit.start,
        "end": edit.end,
        "before": edit.before,
        "after": edit.after,
        "insertion": edit.is_insertion,
        "deletion": edit.is_deletion,
    }


def plural(count: int, noun: str) -> str:
    """``1 site`` / ``0 sites`` -- so a count line never reads as a typo."""
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def variant_data(found: VariantSet) -> dict[str, Any]:
    """One form's variant set as JSON-ready data.

    ``complete`` and ``truncations`` are in every row, not only in the
    truncated ones, so a consumer reads the same shape either way and
    cannot mistake an absent key for a complete answer.
    """
    return {
        "start": found.start,
        "limit": found.limit,
        "complete": found.complete,
        "truncations": [
            {
                "step": cut.step,
                "rule": cut.rule,
                "kept": cut.kept,
                "unexplored": cut.unexplored,
            }
            for cut in found.truncations
        ],
        "variants": [
            {
                "form": variant.form,
                "choices": variant.choices,
                "fired": [step.rule for step in variant.derivation.fired],
            }
            for variant in found
        ],
    }


def truncation_note(found: VariantSet) -> str:
    """How a count line says the cap was reached, or says nothing."""
    if found.complete:
        return ""
    first = found.truncations[0]
    return (
        f" -- INCOMPLETE: cut at rule {first.step + 1} ({first.rule}), "
        f"{found.unexplored} choice combination(s) unexplored; raise --limit"
    )


# --------------------------------------------------------------------------
# Shared resolution
# --------------------------------------------------------------------------


class RuleCommand(Command):
    """A command that resolves a rule set and a list of forms.

    Both resolutions raise :class:`~ipakit.rules.RuleError`, and every
    ``run`` below reports that through :meth:`Command.error` rather than
    letting it reach the caller as a traceback.
    """

    def resolve_rules(self) -> RuleSet:
        """The rule set named on the command line."""
        named = [
            bool(self.args.rule),
            bool(self.args.named_set),
            self.args.rules_file is not None,
        ]
        if sum(named) != 1:
            raise RuleError(
                "name exactly one source of rules: --rule NOTATION, "
                "--set NAME or --file FILE"
            )
        if self.args.rule:
            # Parsed one at a time rather than joined into a block: a rule
            # cannot begin with '#' (a boundary is not a legal target), but
            # a joined block would drop such a line as a comment instead of
            # saying what was wrong with it.
            return RuleSet(
                rules=tuple(parse(text, self.ipa) for text in self.args.rule)
            )
        if self.args.named_set:
            return shipped(self.args.named_set, self.ipa)
        return load_file(self.args.rules_file, self.ipa)

    def resolve_forms(self) -> list[str]:
        """The forms named on the command line, or stdin's lines."""
        if self.args.forms:
            return list(self.args.forms)
        forms = [line.strip() for line in sys.stdin if line.strip()]
        if not forms:
            raise RuleError("no forms given, and none arrived on stdin")
        return forms


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------


class ApplyCommand(RuleCommand):
    """Apply rules to IPA forms and print the derived forms.

    One derived form per line of output, in the order the forms were
    given, so the command composes in a pipeline. Use 'rules trace' when
    the question is which rule did it.

    Rules are ordered: each sees the previous rule's output. Repeating
    -r builds that cascade on the command line.

    An optional rule ('A ~> B') does NOT fire here: one form comes out,
    so no optional choice is taken and this prints the citation form.
    'rules variants' is the set.

    Quoting: rule notation contains '#', '|' and ';', all of which the
    shell reads. Single-quote the whole rule.

    Examples:
        ipakit rules apply -s american-english pˈɪn        # pʰˈɪ̃n
        ipakit rules apply -r 't -> ʔ / _ #' kæt bʌt       # kæʔ bʌʔ
        ipakit rules apply -r 'a -> i / _ t' -r 't -> ʔ / i _' at   # iʔ
        ipakit rules apply --file my.rules kˈæt
        printf 'pˈɪn\\nbˈʌtɚ\\n' | ipakit rules apply -s american-english
        ipakit rules apply -s american-english pˈɪn -j     # [{"form": ..., ...}]
    """

    name = "apply"
    aliases = ["a"]
    help = "Apply rules to forms and print the derived forms"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        add_forms_arg(parser)
        add_rules_args(parser)
        add_zeros_arg(parser)
        add_format_arg(parser)
        add_output_arg(parser)

    def run(self) -> int:
        try:
            ruleset = self.resolve_rules()
            forms = self.resolve_forms()
        except RuleError as exc:
            return self.error(str(exc))

        keep = self.args.keep_zeros
        results = [
            {"form": form, "derived": ruleset.apply(form, self.ipa, keep_zeros=keep)}
            for form in forms
        ]
        if self.format == "json":
            self.output_json(results)
        else:
            for row in results:
                self.print(row["derived"])
        return 0


class TraceCommand(RuleCommand):
    """Show the derivation: which rule fired where, and what it changed.

    A rule set is a cascade, so the interesting output is not the answer
    but the account of it. By default only the rules that fired are
    listed; --all lists every rule's turn, including the ones that did
    nothing, which is what you want when a rule you expected did not fire.

    An optional rule ('A ~> B') is listed under --all as '(not taken)'
    rather than '(no change)': the environment held and the choice was
    declined, which is a different thing from a rule that found nothing.
    Use 'rules variants' to see the choices taken.

    Examples:
        ipakit rules trace -s american-english bˈʌtɚ
        ipakit rules trace -s american-english pˈɪn --all
        ipakit rules trace -r '[vowel] -> [nasalized=+] / _ [manner=nasal]' pɪn
        ipakit rules trace -s american-english pˈɪn -j
    """

    name = "trace"
    aliases = ["t"]
    help = "Show the derivation trace (which rule fired where)"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        add_forms_arg(parser)
        add_rules_args(parser)
        parser.add_argument(
            "--all",
            "-a",
            dest="all_steps",
            action="store_true",
            help="Include the rules that did not fire",
        )
        add_zeros_arg(parser)
        add_format_arg(parser)
        add_output_arg(parser)

    def run(self) -> int:
        try:
            ruleset = self.resolve_rules()
            forms = self.resolve_forms()
        except RuleError as exc:
            return self.error(str(exc))

        all_steps: bool = self.args.all_steps
        keep = self.args.keep_zeros
        derivations = [
            (form, ruleset.derive(form, self.ipa, keep_zeros=keep)) for form in forms
        ]

        if self.format == "json":
            self.output_json(
                [
                    {
                        "form": form,
                        "derived": derivation.result,
                        "steps": [
                            {
                                "rule": step.rule,
                                "before": step.before,
                                "after": step.after,
                                "fired": step.fired,
                                "edits": [edit_data(e) for e in step.edits],
                            }
                            for step in (
                                derivation.steps if all_steps else derivation.fired
                            )
                        ],
                    }
                    for form, derivation in derivations
                ]
            )
            return 0

        for index, (_, derivation) in enumerate(derivations):
            if index:
                self.print()
            self.print(derivation.trace(all_steps=all_steps))
        return 0


class VariantsCommand(RuleCommand):
    """Every form the rules derive, not only the one they settle on.

    A rule written with the optional arrow -- 'A ~> B' rather than
    'A -> B' -- may fire at a site or not, and each site branches on its
    own. So a word with two optional sites has up to four pronunciations,
    which is what 'petite' [pətit] ~ [ptit] and its kind need.

    The first variant listed is always what 'rules apply' prints: the one
    that takes no optional choice. The rest follow by how many choices
    they take, fewest first.

    A set with no optional rule has exactly one variant, which is the
    honest answer and not a defect.

    THE COUNT LINE SAYS WHETHER THE ANSWER IS COMPLETE. Optional rules
    multiply, so --limit bounds what the cascade carries between rules
    (default 256). Reaching it is reported in the count line and in -j,
    never merely dropped.

    Examples:
        ipakit rules variants -s french-liaison pətitə     # pətit, ptit
        ipakit rules variants -r 't ~> ʔ / _ #' kæt        # kæt, kæʔ
        ipakit rules variants -r '[vowel] ~> [length=long]' aaaa --limit 4
        ipakit rules variants -s french-liaison dəvəniʁ -j
    """

    name = "variants"
    aliases = ["v"]
    help = "Every form the rules derive, when a rule is optional ('~>')"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        add_forms_arg(parser)
        add_rules_args(parser)
        parser.add_argument(
            "--limit",
            type=int,
            default=DEFAULT_LIMIT,
            metavar="N",
            help=(
                "Most variants to carry between rules "
                f"(default {DEFAULT_LIMIT}); reaching it is reported"
            ),
        )
        add_zeros_arg(parser)
        add_format_arg(parser)
        add_output_arg(parser)

    def run(self) -> int:
        try:
            ruleset = self.resolve_rules()
            forms = self.resolve_forms()
            if self.args.limit < 1:
                raise RuleError(f"--limit must be at least 1, not {self.args.limit}")
        except RuleError as exc:
            return self.error(str(exc))

        found = [
            (
                form,
                ruleset.variants(
                    form,
                    self.ipa,
                    limit=self.args.limit,
                    keep_zeros=self.args.keep_zeros,
                ),
            )
            for form in forms
        ]

        if self.format == "json":
            self.output_json(
                [{"form": form, **variant_data(result)} for form, result in found]
            )
            return 0

        for form, result in found:
            self.print(
                f"{form}: {plural(len(result), 'variant')}" f"{truncation_note(result)}"
            )
            for variant in result:
                self.print(f"  {variant.form}")
        return 0


class RecognizeCommand(RuleCommand):
    """Report where a rule's environment holds, without rewriting anything.

    The left of the arrow recognizes and the right acts; this is the left
    half alone. "Where does a plosive stand between vowels" is a question
    with no rewrite attached, and this answers it.

    Each site prints as its rule, the index of the target in the unit
    sequence (see 'ipakit rules units'), the target, and the neighbors
    that licensed it. '#' in the environment is the form's own edge --
    matched without one having been typed.

    A rule with an agreement variable ('n -> [place=α] / _ [place=α]')
    prints what the variable took at that site after the environment, as
    'α=velar'. Nothing is added for a rule that names none.

    With a rule *set*, every rule is asked against the form as given. No
    rewriting happens, so the ordering effects 'apply' and 'trace' show
    are absent: a rule that fires only on an earlier rule's output
    recognizes nothing here. That is the honest answer to the question
    asked, not a defect.

    A form with no site is reported as such, and is not an error.

    Examples:
        ipakit rules recognize -r '[manner=plosive] -> [voiced=+] / [vowel] _ [vowel]' atapa
        ipakit rules recognize -r 't -> ʔ / _ #' kæt bʌtɚ
        ipakit rules recognize -s american-english bˈʌtɚ
        ipakit rules recognize -r 't -> ʔ / _ #' kæt -j
    """

    name = "recognize"
    aliases = ["rec"]
    help = "Report where a rule's environment holds, with no rewriting"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        add_forms_arg(parser)
        add_rules_args(parser)
        add_format_arg(parser)

    def run(self) -> int:
        try:
            ruleset = self.resolve_rules()
            forms = self.resolve_forms()
        except RuleError as exc:
            return self.error(str(exc))

        results: list[dict[str, Any]] = []
        for form in forms:
            items = units(form, self.ipa)
            sites = [
                site_data(items, rule, site)
                for rule in ruleset
                for site in rule.recognize(items, self.ipa)
            ]
            results.append(
                {"form": form, "units": [u.text for u in items], "sites": sites}
            )

        if self.format == "json":
            self.output_json(results)
            return 0

        for row in results:
            found: list[dict[str, Any]] = row["sites"]
            self.print(f"{row['form']}: {plural(len(found), 'site')}")
            for site in found:
                target = site["target"] or "∅"
                bound = bindings_text(site["bindings"])
                self.print(
                    f"  {site['rule']}  @{site['start']}  "
                    f"{target}  {site['environment']}" + (f"  {bound}" if bound else "")
                )
        return 0


class UnitsCommand(RuleCommand):
    """Split a form the way rules see it: boundaries kept as units.

    'convert tokenize' drops boundaries; a rule may name one, so the rule
    engine cannot. The site indices 'rules recognize' and 'rules trace'
    report count these units.

    A syllable boundary is transparent -- context scanning steps over it
    unless a rule names it -- while a word boundary is opaque. -j reports
    which is which.

    Examples:
        ipakit rules units bˈʌ.tɚ          # b ˈʌ . t ɚ
        ipakit rules units 'kæt#dɒɡ'       # k æ t # d ɒ ɡ
        ipakit rules units bˈʌ.tɚ -j       # per-unit boundary/transparency
    """

    name = "units"
    aliases = ["u"]
    help = "Split a form into rule units (boundaries kept)"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        add_forms_arg(parser)
        add_format_arg(parser)

    def run(self) -> int:
        try:
            forms = self.resolve_forms()
        except RuleError as exc:
            return self.error(str(exc))

        results: list[dict[str, Any]] = [
            {
                "form": form,
                "units": [
                    {
                        "index": index,
                        "text": unit.text,
                        "boundary": unit.is_boundary,
                        "transparent": unit.transparent,
                        "level": unit.level,
                    }
                    for index, unit in enumerate(units(form, self.ipa))
                ],
            }
            for form in forms
        ]

        if self.format == "json":
            self.output_json(results)
        else:
            for row in results:
                spelled: list[dict[str, Any]] = row["units"]
                self.print(" ".join(str(u["text"]) for u in spelled))
        return 0


class ListCommand(Command):
    """List the shipped rule sets, or the rules in one.

    With no argument, the names 'rules apply --set' accepts. With a name
    (or --file), every rule of that set in order, verbatim -- each line is
    exactly what 'rules apply -r' takes back.

    Examples:
        ipakit rules list                          # american-english
        ipakit rules list american-english         # the rules, in order
        ipakit rules list --file my.rules
        ipakit rules list -j
    """

    name = "list"
    aliases = ["l"]
    help = "List the shipped rule sets, or the rules in one"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument(
            "name", nargs="?", help="A shipped rule set to show the rules of"
        )
        parser.add_argument(
            "--file",
            dest="rules_file",
            type=Path,
            metavar="FILE",
            help="Show the rules in this file instead of a shipped set",
        )
        add_format_arg(parser)

    def run(self) -> int:
        if self.args.name and self.args.rules_file is not None:
            return self.error("name a shipped set or --file, not both")

        ruleset: RuleSet
        try:
            if self.args.rules_file is not None:
                ruleset = load_file(self.args.rules_file, self.ipa)
            elif self.args.name:
                ruleset = shipped(self.args.name, self.ipa)
            else:
                names = available()
                if self.format == "json":
                    self.output_json(names)
                else:
                    for name in names:
                        self.print(name)
                return 0
        except RuleError as exc:
            return self.error(str(exc))

        if self.format == "json":
            self.output_json(
                {
                    "name": ruleset.name,
                    "rules": [
                        {
                            "name": rule.name,
                            "source": rule.source,
                            "optional": rule.optional,
                        }
                        for rule in ruleset
                    ],
                }
            )
        else:
            self.print(f"{ruleset.name}: {plural(len(ruleset), 'rule')}")
            width = len(str(len(ruleset)))
            for index, rule in enumerate(ruleset, start=1):
                self.print(f"  {str(index).rjust(width)}  {rule.source}")
        return 0


class RulesGroup(CommandGroup):
    """Context-sensitive rewrite rules over IPA forms (A -> B / C _ D).

    Subcommands:
        apply      Rewrite forms and print the result
        variants   Every form the rules derive, when a rule is optional
        trace      Show which rule fired where, and what it changed
        recognize  Where an environment holds, with no rewriting
        units      Split a form the way rules see it (boundaries kept)
        list       The shipped rule sets, or the rules in one

    Rules come from exactly one of -r NOTATION (repeatable and ordered),
    -s NAME (a shipped set) or --file FILE. Forms are positional, or one
    per line on stdin when none are given.

    Single-quote rule notation: it contains '#', '|' and ';'. The rule's
    name is separated by ';', not '|' -- '|' is a declared prosodic break
    and so a legal context item.

    The arrow '~>' marks a rule optional: it may fire at a site or not,
    and 'variants' enumerates the choices. 'apply' and 'trace' take none
    of them, so 'apply' prints the first variant.

    Examples:
        ipakit rules list                                  # american-english
        ipakit rules apply -s american-english pˈɪn        # pʰˈɪ̃n
        ipakit rules variants -s french-liaison pətitə     # pətit, ptit
        ipakit rules trace -s american-english bˈʌtɚ       # tapping, and where
        ipakit rules apply -r 't -> ʔ / _ #' kæt           # kæʔ
        ipakit rules recognize -r 't -> ʔ / _ #' kæt       # the site, no rewrite
        ipakit rules units bˈʌ.tɚ                          # b ˈʌ . t ɚ

    See docs/rules.md for the notation and docs/calculus.md for the
    calculus over the set that '~>' opens.
    """

    name = "rules"
    aliases = ["r"]
    help = "Rewrite rules (apply, variants, trace, recognize, units, list)"
    commands = [
        ApplyCommand,
        VariantsCommand,
        TraceCommand,
        RecognizeCommand,
        UnitsCommand,
        ListCommand,
    ]
