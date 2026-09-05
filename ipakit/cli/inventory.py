"""Inspect the shipped inventory registry."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import ClassVar

from ..inventories import inventories, inventory, inventory_from_dictionary
from .base import Command, CommandGroup, add_format_arg, add_output_arg


class InventoryListCommand(Command):
    """List every shipped inventory and style."""

    name = "list"
    aliases: ClassVar[list[str]] = []
    help = "List named inventories and styles"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        add_format_arg(parser)

    def run(self) -> int:
        rows = []
        for name in inventories():
            item = inventory(name)
            kind = "inventory" if item.phones is not None else "style"
            count = "-" if item.phones is None else str(len(item.phones))
            rows.append((name, kind, count, item.provenance))
        if self.format == "json":
            self.output_json(
                [
                    {
                        "name": name,
                        "kind": kind,
                        "phones": count,
                        "provenance": provenance,
                    }
                    for name, kind, count, provenance in rows
                ]
            )
            return 0
        self.print("name\tkind\tphones\tprovenance")
        for row in rows:
            self.print("\t".join(row))
        return 0


class InventoryShowCommand(Command):
    """Show one inventory's provenance and its phones in house IPA and its own notation."""

    name = "show"
    aliases: ClassVar[list[str]] = []
    help = "Show one named inventory"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.add_argument("inventory", help="Named inventory or notation to show")

    def run(self) -> int:
        try:
            item = inventory(self.args.inventory)
        except ValueError as error:
            return self.error(str(error))
        self.print(f"name: {item.name}")
        if item.version is not None:
            self.print(f"version: {item.version}")
        self.print(f"provenance: {item.provenance}")
        if item.phones is None:
            self.print("kind: style")
            return 0
        self.print("house IPA\tspelling")
        for phone in item.phones:
            try:
                spelling = item.style.spell(phone)
            except ValueError as error:
                spelling = f"refused: {error}"
            self.print(f"{phone}\t{spelling}")
        if item.style.collapses:
            self.print("collapses")
            self.print("spelling\thouse IPA members")
            for spelling, members in item.style.collapses.items():
                self.print(f"{spelling}\t{' '.join(members)}")
        if item.refusals:
            self.print("refusals")
            self.print("spelling\treason")
            for spelling, reason in item.refusals.items():
                self.print(f"{spelling}\t{reason}")
        return 0


class InventoryFromDictionaryCommand(Command):
    """Derive a phone inventory from a pronunciation dictionary."""

    name = "from-dict"
    aliases: ClassVar[list[str]] = []
    help = "Derive an inventory from a pronunciation dictionary"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.add_argument("file", type=Path, help="Pronunciation dictionary to read")
        parser.add_argument("--style", required=True, help="Dictionary phone notation")
        parser.add_argument("--name", help="Name for the derived inventory")
        parser.add_argument(
            "--spell",
            choices=("house", "native"),
            default="house",
            help="Phone spelling for text output (default: house)",
        )
        add_format_arg(parser)
        add_output_arg(parser)

    def run(self) -> int:
        try:
            item = inventory_from_dictionary(
                self.args.file, self.args.style, name=self.args.name, ipa=self.ipa
            )
            assert item.phones is not None
            rows = [
                {
                    "house_ipa": phone,
                    "spelling": item.style.spell(phone),
                }
                for phone in item.phones
            ]
        except ValueError as error:
            return self.error(str(error))
        if self.format == "json":
            self.output_json(
                {
                    "name": item.name,
                    "style": item.style.name,
                    "provenance": item.provenance,
                    "phones": rows,
                }
            )
        else:
            key = "house_ipa" if self.args.spell == "house" else "spelling"
            for row in rows:
                self.print(row[key])
        return 0


class InventoryGroup(CommandGroup):
    name = "inventory"
    aliases: ClassVar[list[str]] = []
    help = "Inspect named phoneset inventories and styles"
    commands: ClassVar[list[type[Command]]] = [
        InventoryListCommand,
        InventoryShowCommand,
        InventoryFromDictionaryCommand,
    ]
