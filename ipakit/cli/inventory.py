"""Inspect the shipped inventory registry."""

from __future__ import annotations

import argparse
from typing import ClassVar

from ..inventories import inventories, inventory
from .base import Command, CommandGroup, add_format_arg


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
        return 0


class InventoryGroup(CommandGroup):
    name = "inventory"
    aliases: ClassVar[list[str]] = []
    help = "Inspect named phoneset inventories and styles"
    commands: ClassVar[list[type[Command]]] = [
        InventoryListCommand,
        InventoryShowCommand,
    ]
