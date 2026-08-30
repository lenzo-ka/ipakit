"""Commands for the externally mounted PHOIBLE inventory provider."""

from __future__ import annotations

import argparse
import warnings

from ..bridges.phoible import PhoibleBridge
from .base import Command, CommandGroup, add_output_arg


def _bridge(args: argparse.Namespace) -> PhoibleBridge:
    """Construct the provider from the optional command-line mount path."""
    return PhoibleBridge(args.phoible)


def _path_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--phoible",
        help="PHOIBLE checkout or data/phoible.csv (else IPAKIT_PHOIBLE)",
    )


class PhoibleLanguageCommand(Command):
    """List every separately attributed inventory for a language."""

    name = "language"
    aliases = ["spread"]
    help = "Report the inventory spread for an ISO code or Glottocode"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("code", help="ISO 639-3 code or Glottocode to report on")
        _path_argument(parser)

    def run(self) -> int:
        spread = _bridge(self.args).language(self.args.code)
        for item in spread.inventories:
            keys = ",".join(item.bibtex_keys)
            self.print(
                f"{item.inventory_id}\t{item.glottocode}\t{item.source}\t"
                f"{keys}\t{item.language_name}"
            )
        return 0


class PhoibleInventoryCommand(Command):
    """Write one selected inventory as a house phoneset file."""

    name = "inventory"
    aliases = ["phoneset"]
    help = "Write one InventoryID as a --phoneset-compatible file"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "inventory_id",
            help="PHOIBLE InventoryID to write (see 'ipakit phoible language')",
        )
        _path_argument(parser)
        add_output_arg(parser)

    def run(self) -> int:
        inventory = _bridge(self.args).inventory(self.args.inventory_id, ipa=self.ipa)
        for phone in inventory.phoneset:
            self.print(phone)
        for refusal in inventory.refusals:
            warnings.warn(
                f"PHOIBLE row {refusal.row} {refusal.field} {refusal.value!r}: "
                f"{refusal.reason}",
                stacklevel=1,
            )
        return 0


class PhoibleAuditCommand(Command):
    """Measure strict primary-segment coverage over the mounted checkout."""

    name = "audit"
    aliases: list[str] = []
    help = "Count accepted/refused rows and inventories"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        _path_argument(parser)

    def run(self) -> int:
        audit = _bridge(self.args).audit(ipa=self.ipa)
        self.print(
            f"rows: {audit.accepted_rows} accepted, {audit.refused_rows} refused, "
            f"{audit.rows} total"
        )
        self.print(
            f"inventories: {audit.accepted_inventories} accepted, "
            f"{audit.refused_inventories} with refusals, {audit.inventories} total"
        )
        for reason, count in audit.refusal_reasons:
            self.print(f"{count}\t{reason}")
        return 0


class PhoibleGroup(CommandGroup):
    """Query PHOIBLE without pretending rival doculects are one inventory."""

    name = "phoible"
    aliases: list[str] = []
    help = "Read separately mounted PHOIBLE doculect inventories"
    commands = [PhoibleLanguageCommand, PhoibleInventoryCommand, PhoibleAuditCommand]
