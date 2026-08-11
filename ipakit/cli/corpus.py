"""Directory-corpus command group."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .. import corpus, rules
from .._corpus_query import _normalize_wild_query
from .base import Command, CommandGroup


def _location(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--corpus", "-C", type=Path, default=Path("."))


class Init(Command):
    name, aliases, help = "init", [], "Create an empty corpus"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("location", type=Path, nargs="?", default=Path("."))

    def run(self) -> int:
        corpus.create(self.args.location)
        return 0


class Add(Command):
    name, aliases, help = "add", [], "Add a named form"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("fileid")
        parser.add_argument("text", nargs="?")
        parser.add_argument("--role", "-r", required=True)
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
    name, aliases, help = "ingest-cmudict", [], "Ingest an external CMUdict file"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("corpus", type=Path)
        parser.add_argument("path", type=Path)

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
    name, aliases, help = "ids", [], "List corpus entry IDs"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        _location(parser)

    def run(self) -> int:
        for fileid in corpus.open(self.args.corpus).ids():
            self.print(fileid)
        return 0


class Show(Command):
    name, aliases, help = "show", [], "Show an entry's named forms"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("fileid")
        _location(parser)

    def run(self) -> int:
        entry = corpus.open(self.args.corpus).read(self.args.fileid)
        for role in sorted(entry.forms):
            self.print(f"{entry.id}\t{role}\t{entry.forms[role].to_ipa()}")
        return 0


class Query(Command):
    name, aliases, help = "query", [], "Stream structural matches"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("dsl")
        parser.add_argument("--role", "-r", default="cited")
        parser.add_argument("--exact", action="store_true")
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
    name, aliases, help = "derives", [], "Check role pairs under a rule set"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--rules", required=True)
        parser.add_argument("--source", required=True)
        parser.add_argument("--target", required=True)
        _location(parser)

    def run(self) -> int:
        grammar = rules.shipped(self.args.rules, self.ipa)
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
