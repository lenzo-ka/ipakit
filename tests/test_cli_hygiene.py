"""Predicates over the whole parser tree.

Four properties every command line in this package has to hold, each
written as a walk over ``create_parser()`` rather than as a list of
today's offenders. A command added tomorrow is covered without this file
being touched, which is the only version of these checks worth having:
the four defects they close were all found by reading the parser by hand,
and reading it by hand is not repeatable.

* a short flag means one thing everywhere (``-f`` was --format, --file and
  --features);
* every leaf says what it is, and every argument says what it takes;
* a command that reads IPA says so, because orthography parses;
* every leaf accepts the global flags, whichever family it was registered
  in.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import string
import sys
import warnings
from collections import defaultdict
from typing import Any

import ipakit
import ipakit.cli
import pytest
from ipakit.cli.base import NOTATION_NOTES, Command, register_command

#: A word in English spelling, and no kind of transcription. Every letter
#: in it is a registered phone, so nothing in the reader can refuse it --
#: which is the whole reason the note the predicates below require exists.
ORTHOGRAPHIC = "cat"


def _subparsers(
    parser: argparse.ArgumentParser,
) -> argparse._SubParsersAction[argparse.ArgumentParser] | None:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def _walk(
    parser: argparse.ArgumentParser, path: tuple[str, ...]
) -> list[tuple[tuple[str, ...], argparse.ArgumentParser]]:
    """Every parser in the tree, canonical name first, aliases folded in.

    Aliases share one parser object, so they are visited once: the checks
    are about what a parser declares, and an alias declares nothing.
    """
    found = [(path, parser)]
    action = _subparsers(parser)
    if action is None:
        return found
    seen: set[int] = set()
    for name, child in action.choices.items():
        if id(child) in seen:
            continue
        seen.add(id(child))
        found.extend(_walk(child, (*path, name)))
    return found


PARSERS = _walk(ipakit.cli.create_parser(), ())

#: A leaf is a parser with no subcommands of its own -- the things a user
#: actually runs.
LEAVES = [(path, parser) for path, parser in PARSERS if _subparsers(parser) is None]

IDS = [" ".join(path) or "<root>" for path, _ in LEAVES]


def _command_of(parser: argparse.ArgumentParser) -> type[Command] | None:
    return parser.get_default("cmd_cls")  # type: ignore[no-any-return]


def _real_actions(parser: argparse.ArgumentParser) -> list[argparse.Action]:
    """The arguments a user passes: not -h, not the subcommand slot."""
    return [
        action
        for action in parser._actions
        if not isinstance(action, argparse._HelpAction | argparse._SubParsersAction)
        and action.help is not argparse.SUPPRESS
    ]


def _run(monkeypatch: Any, argv: list[str]) -> int:
    """Run one command line in process, with stdin empty and output eaten.

    Empty stdin matters: several commands fall back to reading forms from
    it, and a probe that blocks is a probe that never reports.
    """
    monkeypatch.setattr(sys, "argv", ["ipakit", *argv])
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    out, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            return ipakit.cli.main()
    except SystemExit as exit_:  # argparse rejected the line
        return int(exit_.code or 0)


class TestAShortFlagMeansOneThing:
    """``-f`` was --format on 46 leaves, --file on one and --features on three.

    A user learns one and is wrong everywhere else, and the wrong reading
    is silent: ``rules apply -f json`` picks a format, ``query find -f x``
    opened a file. Stated over the whole tree on purpose -- relaxed to
    per-group it would stop flagging exactly the collisions left behind.
    """

    def test_a_short_flag_binds_to_at_most_one_long_name(self):
        bindings: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
        for path, parser in PARSERS:
            for action in parser._actions:
                shorts = [
                    option
                    for option in action.option_strings
                    if len(option) == 2 and not option.startswith("--")
                ]
                longs = [
                    option
                    for option in action.option_strings
                    if option.startswith("--")
                ]
                if not longs:
                    continue
                # An action may spell itself several ways (--warnings-as-errors
                # and --strict are one option); the first long name is the one
                # it is called by, and aliases of one option are not a
                # collision. Two different options sharing a letter are.
                for short in shorts:
                    bindings[short][longs[0]].add(" ".join(path) or "<root>")

        collisions = {
            short: {name: sorted(where) for name, where in names.items()}
            for short, names in bindings.items()
            if len(names) > 1
        }
        assert collisions == {}

    def test_the_sweep_is_not_vacuous(self):
        assert len(PARSERS) > 80, f"only {len(PARSERS)} parsers walked"
        assert len(LEAVES) > 60, f"only {len(LEAVES)} leaves walked"


class TestEveryCommandSaysWhatItIs:
    """Fourteen leaves printed no description and 34 arguments printed no
    help, six of them on required flags -- and a required flag with empty
    help cannot be used from ``--help`` alone."""

    @pytest.mark.parametrize("path, parser", LEAVES, ids=IDS)
    def test_the_leaf_has_a_description(self, path, parser):
        assert (parser.description or "").strip(), f"{' '.join(path)} describes nothing"

    @pytest.mark.parametrize("path, parser", LEAVES, ids=IDS)
    def test_every_argument_has_help(self, path, parser):
        blank = [
            action.option_strings or action.dest
            for action in _real_actions(parser)
            if not (action.help or "").strip()
        ]
        assert blank == [], f"{' '.join(path)} has arguments with no help"


#: One invocation per notation-reading route that ANSWERS a plain
#: orthographic word, each spelling a real English word. Written out because the
#: unconditional sweep below can only hand a leaf one word, and a command
#: wanting two forms or a rule set is never reached that way.
WITNESSES = [
    ["distance", "word", "cat", "cad"],
    ["distance", "seq", "cat", "cad"],
    ["distance", "nearest", "cat", "cad", "cat"],
    ["distance", "segment", "c", "t"],
    ["distance", "pair", "c", "t"],
    ["distance", "confusability", "c", "t"],
    ["distance", "directional", "cat", "cad"],
    ["distance", "matrix", "cat"],
    ["rules", "apply", "-s", "american-english", "pin"],
    ["rules", "trace", "-s", "american-english", "pin"],
    ["rules", "variants", "-s", "american-english", "pin"],
    ["rules", "recognize", "-s", "american-english", "pin"],
    ["rules", "units", "pin"],
    ["syllabify", "cat", "--language", "english"],
    ["query", "find", "n", "pin"],
    ["tiergraph", "cat"],
    ["features", "cat"],
    ["describe", "cat"],
    ["tract", "draw", "c"],
    ["convert", "to-cmu", "pin"],
    ["convert", "to-json", "cat"],
    ["convert", "to-xsampa", "cat"],
    ["convert", "to-kirshenbaum", "cat"],
    ["convert", "to-timit", "pin"],
    ["convert", "tokenize", "cat"],
    ["convert", "normalize", "cat"],
    ["convert", "add-ties", "cat"],
    # Not IPA: 'cat' is read as three X-SAMPA (Kirshenbaum) symbols, and
    # the answer is glyph-identical to the input, so nothing on screen
    # says a reading happened at all.
    ["convert", "from-xsampa", "cat"],
    ["convert", "from-kirshenbaum", "cat"],
    ["analysis", "describe", "cat"],
    ["analysis", "validate", "cat"],
    ["analysis", "natural-class", "c", "t"],
    ["analysis", "minimal-pairs", "c"],
    ["analysis", "nearest", "c"],
]

#: The IPA-reading routes that refuse an orthographic word for a reason of
#: their own -- neither has an attested Japanese adaptation for it -- so no
#: witness can be written for them.
REFUSERS = [
    ["convert", "to-katakana", "pin"],
    ["rules", "morae", "pin"],
]

#: The IPA-reading routes reached by neither, because both want a corpus on
#: disk before they read anything. Named so the coverage check below stays
#: a statement about all of them rather than about the ones easy to run.
NEEDS_A_CORPUS = [
    ("corpus", "add"),
    ("corpus", "query"),
]


class TestOrthographyIsNotIPA:
    """``distance word cat cad`` answers 0.9870 and ``rules apply -s
    american-english pin`` answers ``pĩn``: English spelling, read as IPA,
    answered confidently.

    Neither a warning nor a refusal can fix that, because both have to
    guess whether an all-ASCII string is spelling or transcription, and
    ``kat`` is genuine IPA used throughout the test corpus. A guess that
    blocks correct input is worse than the hazard. What is left is to say
    so at the point of use, and to keep saying it -- which is these three
    checks: the note is attached where a command declares the notation it
    reads, the routes that swallow an orthographic word are exactly the
    ones carrying a note, and the escapes are pinned rather than assumed
    shut.

    The hazard is not ipakit's alone. ``convert from-xsampa cat`` answers
    ``cat``, because all 52 ASCII letters are X-SAMPA symbols -- so the
    word is read as a palatal plosive, an open front vowel and an alveolar
    plosive, and the answer is glyph-identical to what was typed. Each
    notation therefore carries its own note rather than sharing one:
    ipakit's wording, "every ASCII letter is a registered phone", is false
    of an alphabet whose letters mostly do not denote themselves.
    """

    NOTATION_ROUTES = [
        (path, parser)
        for path, parser in LEAVES
        if getattr(_command_of(parser), "reads_notation", None) is not None
    ]

    #: Leaves that answer a plain orthographic word with exit 0 and read
    #: no phonetic notation at all. Pinned rather than skipped: if one
    #: starts reading a notation, or a new leaf joins them, this fails and
    #: the limit gets looked at instead of quietly widening.
    #:
    #: ``convert from-xsampa`` and ``from-kirshenbaum`` were held here
    #: because ipakit's own note would have been false on them -- their
    #: letters are symbols of a different alphabet. They now declare that
    #: alphabet and carry its own note. ``query shorts`` was held because
    #: it reads short codes rather than phones; it now says so when a term
    #: names no code, so it no longer answers this word with exit 0.
    NOT_A_NOTATION = {
        # 'cat' is a directory name here, not a transcription.
        ("corpus", "init"),
    }

    def test_the_sweep_is_not_vacuous(self):
        assert (
            len(self.NOTATION_ROUTES) >= 30
        ), f"only {len(self.NOTATION_ROUTES)} notation routes"

    def test_every_notation_route_is_measured_somewhere(self):
        """The three tables above cover every declared IPA route between
        them. Without this a route could be declared, get the note by
        construction, and never be run against an orthographic word at
        all -- which is the half of the predicate that is evidence."""
        declared = {path for path, _ in self.NOTATION_ROUTES}
        measured = set(NEEDS_A_CORPUS)
        for argv in [*WITNESSES, *REFUSERS]:
            measured.add(
                next(path for path, _ in LEAVES if list(path) == argv[: len(path)])
            )
        assert declared - measured == set()
        assert measured - declared == set()

    @pytest.mark.parametrize(
        "path, parser",
        NOTATION_ROUTES,
        ids=[" ".join(path) for path, _ in NOTATION_ROUTES],
    )
    def test_a_route_that_reads_a_notation_says_it_is_not_orthography(
        self, path, parser
    ):
        assert "orthograph" in parser.format_help()

    @pytest.mark.parametrize("path, parser", LEAVES, ids=IDS)
    def test_a_route_that_answers_an_orthographic_word_says_the_input_is_ipa(
        self, monkeypatch, tmp_path, path, parser
    ):
        """The measured half, and the one that cannot be forgotten.

        Every leaf is handed the word, not only the ones declared to read
        IPA -- so a command added without the declaration is caught by
        having answered, rather than by anyone noticing.
        """
        monkeypatch.chdir(tmp_path)
        if _run(monkeypatch, [*path, ORTHOGRAPHIC]) != 0:
            return
        if tuple(path) in self.NOT_A_NOTATION:
            return
        assert "orthograph" in parser.format_help(), (
            f"{' '.join(path)} answered {ORTHOGRAPHIC!r} without saying "
            "its input is IPA"
        )

    @pytest.mark.parametrize(
        "argv",
        WITNESSES,
        ids=lambda argv: " ".join(argv),
    )
    def test_the_witness_answers_and_carries_the_note(
        self, monkeypatch, tmp_path, argv
    ):
        """The routes that need more than one word to reach, spelled out.

        The unconditional sweep above hands every leaf a single word, so a
        command wanting two forms or a rule set is never reached by it.
        These are those, and each is asserted to *succeed*: an invocation
        that stopped running would satisfy 'exits 0 implies the note' for
        the wrong reason.
        """
        monkeypatch.chdir(tmp_path)
        assert _run(monkeypatch, argv) == 0, f"{' '.join(argv)} did not run"
        leaf = next(
            parser for path, parser in LEAVES if list(path) == argv[: len(path)]
        )
        assert "orthograph" in leaf.format_help()

    @pytest.mark.parametrize("argv", REFUSERS, ids=lambda argv: " ".join(argv))
    def test_the_route_that_refuses_an_orthographic_word_still_does(
        self, monkeypatch, tmp_path, argv
    ):
        """Two routes answer no word they have no attestation for, so
        orthography bounces off them for a reason that has nothing to do
        with the note. Pinned, not skipped: if one starts answering, the
        note is the thing that then has to carry the warning, and this
        says so instead of leaving the change invisible."""
        monkeypatch.chdir(tmp_path)
        assert _run(monkeypatch, argv) == 1


class TestEveryLeafTakesTheGlobalFlags:
    """Registration used to be written out twice -- once for the leaves
    that hang off the top level, once for the ones under a group -- and
    ``--lax`` standing in both copies was the evidence that the pair had
    already been edited in lockstep once. The next per-command flag would
    have reached one family. It is one function now; this is what keeps it
    one, and it was already true before the merge, so a failure here means
    a leaf got registered outside it.
    """

    @pytest.mark.parametrize("path, parser", LEAVES, ids=IDS)
    def test_the_leaf_accepts_lax(self, path, parser):
        options = {
            option for action in parser._actions for option in action.option_strings
        }
        assert "--lax" in options

    @pytest.mark.parametrize("path, parser", LEAVES, ids=IDS)
    def test_the_leaf_names_the_class_that_runs_it(self, path, parser):
        assert _command_of(parser) is not None


class TestANotationCannotBeDeclaredWithoutItsNote:
    """``reads_notation`` names an alphabet rather than answering "is this
    IPA?", which means the next notation ipakit reads is one string away
    from being declared -- and its note is a separate act that nothing
    would otherwise require.

    So registration refuses a notation it has no note for. Without this
    the declaration would attach nothing and the command would look
    exactly like one that reads no transcription at all, which is the
    silent-wrong-answer shape the notes exist to close.
    """

    def _leaf(self, notation):
        class _Probe(Command):
            name = "probe"
            help = "probe"
            reads_notation = notation

            def run(self) -> int:  # pragma: no cover - never executed
                return 0

        return _Probe

    def _register(self, cmd_cls):
        parser = argparse.ArgumentParser()
        return register_command(parser.add_subparsers(), cmd_cls)

    def test_an_unwritten_notation_is_refused_by_name(self):
        with pytest.raises(ValueError, match="Cyrillic"):
            self._register(self._leaf("Cyrillic"))

    def test_every_written_notation_registers(self):
        """The other half: the refusal above must be about the note being
        missing, not about registration rejecting every notation."""
        for notation in NOTATION_NOTES:
            parser = self._register(self._leaf(notation))
            assert "orthograph" in parser.format_help(), notation

    def test_a_leaf_that_declares_nothing_still_registers(self):
        parser = self._register(self._leaf(None))
        assert "orthograph" not in parser.format_help()


class TestTheNotesSayTheTrueThingAboutTheirAlphabet:
    """Each note claims every LOWERCASE ASCII letter is a symbol of the
    notation it heads. That is the claim the hazard rests on -- an English
    word is spelled in lowercase, so if any lowercase letter were
    unassigned the reader would refuse the word and there would be nothing
    to warn about.

    It is checked rather than asserted because it is a fact about three
    conversion tables that no one edits with this note in mind. Kirshenbaum
    already leaves four UPPERCASE letters unassigned, which is why the note
    says lowercase and why the difference is worth a test rather than a
    comment.
    """

    READERS = {
        "IPA": lambda s: ipakit.tokenize(s),
        "X-SAMPA": lambda s: ipakit.from_xsampa(s),
        "Kirshenbaum": lambda s: ipakit.from_kirshenbaum(s),
    }

    #: ASCII ``g`` is not house IPA, and that is the settled design rather
    #: than a gap.
    #:
    #: IPA's ``g`` is U+0261 LATIN SMALL LETTER SCRIPT G, so ASCII ``g``
    #: (U+0067) is a different character: a keyboard stand-in, which
    #: ``docs/ties.md`` calls a soft read and puts behind the wild-import
    #: door. Strict parsing therefore refuses it -- ``tokenize("dog") ==
    #: ["d", "o"]``, reported, never quietly substituted -- while
    #: ``from_wild`` and ``normalize_lookalikes`` read it as ``ɡ``, and
    #: ``ipakit features`` opens that door deliberately for interactive
    #: lookup (``--no-lookalikes`` closes it; ``docs/cli-api-sync.md``
    #: records the intent).
    #:
    #: Pinned because it is the one letter where "every lowercase letter
    #: is a symbol" is true of the wild reading and false of the strict
    #: one, and a reader of this class should not have to rediscover
    #: which of the two the notes are about.
    KNOWN_UNASSIGNED = {"IPA": ["g"]}

    def test_every_declared_notation_has_a_reader_here(self):
        """Otherwise a notation could be added, get an unchecked note, and
        this class would pass by not looking at it."""
        assert set(self.READERS) == set(NOTATION_NOTES)

    @pytest.mark.parametrize("notation", sorted(READERS))
    def test_every_lowercase_letter_is_a_symbol(self, notation):
        read = self.READERS[notation]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            unassigned = [c for c in string.ascii_lowercase if not read(c)]
        assert unassigned == self.KNOWN_UNASSIGNED.get(notation, []), (
            f"{notation} leaves {unassigned} unassigned, so its note's claim "
            "that a spelled word is read rather than refused has changed"
        )
