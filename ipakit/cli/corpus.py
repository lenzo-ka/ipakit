"""Directory-corpus command group."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .. import corpus, rules
from .._corpus_query import _normalize_wild_query
from .base import IPA, Command, CommandGroup


def _location(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--corpus",
        "-C",
        type=Path,
        default=Path("."),
        help="Directory holding the corpus (default: the working directory)",
    )


class Init(Command):
    """Write the directory layout a corpus needs, with no entries in it.

    A corpus is a directory of JSON entries plus the assets they name;
    everything else in this group reads or writes one that already exists.
    """

    name, aliases, help = "init", [], "Create an empty corpus"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "location",
            type=Path,
            nargs="?",
            default=Path("."),
            help="Directory to create the corpus in (default: the working directory)",
        )

    def run(self) -> int:
        corpus.create(self.args.location)
        return 0


class Add(Command):
    """Store one transcription of one entry, under the role it plays.

    An entry holds several forms of the same item -- a cited pronunciation,
    a narrow transcription, an observed one -- and the role is what tells
    them apart. This writes a whole entry, and an ID already in the corpus
    is refused rather than overwritten; a second role on an entry that
    exists goes through the Python API.
    """

    name, aliases, help = "add", [], "Add a named form"
    reads_notation = IPA

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("fileid", help="Entry ID to store the form under")
        parser.add_argument(
            "text",
            nargs="?",
            help="IPA form to store; with none given, read it from stdin",
        )
        parser.add_argument(
            "--role",
            required=True,
            help="Which transcription of the entry this is, e.g. cited, broad",
        )
        parser.add_argument(
            "--segmented", action="store_true", help="read whitespace-delimited units"
        )
        parser.add_argument("--wild", action="store_true", help="normalize wild IPA")
        _location(parser)

    def run(self) -> int:
        text = (
            self.args.text
            if self.args.text is not None
            else sys.stdin.read().rstrip("\r\n")
        )
        corpus.open(self.args.corpus).add(
            self.args.fileid,
            {},
            {
                self.args.role: self.ipa.read(
                    text, segmented=self.args.segmented, wild=self.args.wild
                )
            },
        )
        return 0


class IngestCMUdict(Command):
    """Read a CMUdict file into a corpus, one entry per pronunciation.

    Each word arrives as a ``cited`` form. A line whose phones do not map
    is refused rather than approximated, and every refusal is reported on
    stderr with its line number and reason; the summary counts both.
    """

    name, aliases, help = "ingest-cmudict", [], "Ingest an external CMUdict file"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("corpus", type=Path, help="Corpus directory to add to")
        parser.add_argument("path", type=Path, help="CMUdict file to read")

    def run(self) -> int:
        report = corpus.ingest_cmudict(
            corpus.open(self.args.corpus),
            self.args.path,
            mapper=self.cmu,
            features=self.ipa,
        )
        for refusal in report.refusals:
            word = refusal.word or "-"
            print(
                f"refusal\t{refusal.line_number}\t{word}\t"
                f"{refusal.reason}\t{refusal.line}",
                file=sys.stderr,
            )
        self.print(f"summary\tadded={report.added}\trefused={len(report.refusals)}")
        return 0 if report.accepted else 1


class Validate(Command):
    """Check that every entry parses and every asset it names is there.

    One line per finding, then ``valid`` and the entry count if there were
    none. Exit status is 1 where anything was found.
    """

    name, aliases, help = "validate", [], "Validate a corpus and its assets"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        _location(parser)

    def run(self) -> int:
        report = corpus.validate(self.args.corpus)
        for finding in report.findings:
            self.print(
                "\t".join(
                    filter(
                        None,
                        (
                            finding.code,
                            finding.entry_id,
                            finding.kind,
                            finding.path,
                            finding.message,
                        ),
                    )
                )
            )
        if report.valid:
            self.print(f"valid\t{report.entry_count}")
        return 0 if report.valid else 1


class Ids(Command):
    """Print every entry ID in the corpus, one per line.

    The list the other subcommands take an ID from, and what to pipe into
    a shell loop over the collection.
    """

    name, aliases, help = "ids", [], "List corpus entry IDs"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        _location(parser)

    def run(self) -> int:
        for fileid in corpus.open(self.args.corpus).ids():
            self.print(fileid)
        return 0


class Show(Command):
    """Print one entry's forms as ID, role and IPA, one row per role."""

    name, aliases, help = "show", [], "Show an entry's named forms"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("fileid", help="Entry ID to read")
        _location(parser)

    def run(self) -> int:
        entry = corpus.open(self.args.corpus).read(self.args.fileid)
        for role in sorted(entry.forms):
            self.print(f"{entry.id}\t{role}\t{entry.forms[role].to_ipa()}")
        return 0


class Query(Command):
    """Run one structural query over every entry, and stream what matched.

    The query is the arrowless rule DSL (see ``ipakit query find``). One row
    per match: entry ID, role, the paths it matched at, the matching text,
    and any agreement variables it bound. How the query was read is printed
    on stderr, because a wild query is normalized before it runs.
    """

    name, aliases, help = "query", [], "Stream structural matches"
    reads_notation = IPA

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("dsl", help="Structural query in the arrowless rule DSL")
        parser.add_argument(
            "--role",
            default="cited",
            help="Which transcription of each entry to search (default: cited)",
        )
        parser.add_argument(
            "--exact",
            action="store_true",
            help="Take the query as written, skipping wild-IPA normalization",
        )
        _location(parser)

    def run(self) -> int:
        interpreted = (
            self.args.dsl
            if self.args.exact
            else _normalize_wild_query(self.args.dsl, self.ipa)
        )
        print(f"query read as: {interpreted}", file=sys.stderr)
        corpus.parse_query(interpreted, self.ipa)
        for found in corpus.query(
            corpus.open(self.args.corpus),
            interpreted,
            role=self.args.role,
            features=self.ipa,
        ):
            bindings = ",".join(f"{key}={value}" for key, value in found.bindings)
            self.print(
                "\t".join(
                    (
                        found.fileid,
                        found.role,
                        ",".join(found.paths),
                        found.text,
                        bindings,
                    )
                )
            )
        return 0


class Derives(Command):
    """Ask, entry by entry, whether the rules carry one role to the other.

    One row per entry: ``witness`` where the rules derive the target form
    from the source, ``refusal`` where they do not, ``unexplored`` where the
    search hit its budget and so answered neither. The summary counts all
    three. ``ipakit rules derives`` is the same question with a written
    report and a rule set that may come from notation or a file.
    """

    name, aliases, help = "derives", [], "Check role pairs under a rule set"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        # --set/-s, spelled as ``ipakit rules`` spells it: one verb naming
        # one thing one way. It was --rules here and --rule/--set/--file
        # there, for the same shipped rule set.
        parser.add_argument(
            "--set",
            "-s",
            dest="named_set",
            metavar="NAME",
            required=True,
            help="A shipped rule set (see 'ipakit rules list')",
        )
        parser.add_argument(
            "--source",
            required=True,
            help="Role the derivation starts from, e.g. broad",
        )
        parser.add_argument(
            "--target",
            required=True,
            help="Role the derivation must reach, e.g. narrow",
        )
        _location(parser)

    def run(self) -> int:
        grammar = rules.shipped(self.args.named_set, self.ipa)
        counts = {"witness": 0, "refusal": 0, "unexplored": 0}
        for fileid, answer in corpus.query_derivations(
            corpus.open(self.args.corpus),
            grammar,
            source_role=self.args.source,
            target_role=self.args.target,
            features=self.ipa,
        ):
            if isinstance(answer, rules.Derivation):
                kind = "witness"
            elif isinstance(answer, corpus.BudgetRefusal):
                kind = "unexplored"
            else:
                kind = "refusal"
            counts[kind] += 1
            self.print(f"{fileid}\t{kind}")
        self.print(
            "summary\t"
            + "\t".join(
                f"{key}={counts[key]}" for key in ("witness", "refusal", "unexplored")
            )
        )
        return 0


class CorpusGroup(CommandGroup):
    name, aliases, help = "corpus", [], "Build, inspect, query, and validate corpora"
    commands = [Init, Add, IngestCMUdict, Validate, Ids, Show, Query, Derives]
