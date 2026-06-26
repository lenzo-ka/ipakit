"""Features command - get features for IPA phones."""

from __future__ import annotations

import argparse
from typing import Any

from .base import Command, add_format_arg, add_output_arg, add_strict_arg


class FeaturesCommand(Command):
    """Get phonetic features for an IPA phone or string.

    Returns the feature bundle for a phone. By default, only shows features
    explicitly defined on the phone. Use --all to include default values.

    Examples:
        ipakit features p              # Explicit features for /p/
        ipakit features p --all        # All features including defaults
        ipakit features p --short      # Short names: plo bil
        ipakit features "pʰ"           # Aspirated p (composed)
        ipakit features "kæt"          # Features for each segment
        ipakit f b --json              # JSON output
        ipakit f b -o out.json --json  # Save to file
    """

    name = "features"
    aliases = ["f"]
    help = "Get phonetic features for an IPA phone or string"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.description = cls.__doc__
        parser.formatter_class = argparse.RawDescriptionHelpFormatter

        parser.add_argument(
            "phone", help="IPA phone symbol or string (e.g., 'p', 'pʰ', 'kæt')"
        )
        add_format_arg(parser, ["text", "json", "short"])
        parser.add_argument(
            "--short",
            "-s",
            action="store_const",
            const="short",
            dest="format",
            help="Output as compact short names (e.g., 'plo bil -voi')",
        )
        parser.add_argument(
            "--all",
            "-a",
            action="store_true",
            help="Show all features including defaults (default: suppress default values)",
        )
        add_strict_arg(parser)
        add_output_arg(parser)

    def _build_entry(
        self, segment: str, feats: dict[str, str], is_composed: bool
    ) -> dict[str, Any]:
        """Build a feature entry dict with name, aliases, class, and features."""
        result: dict[str, Any] = {"name": segment}
        # Add aliases if any
        if aliases := self.get_aliases(segment):
            result["aliases"] = aliases
        if is_composed:
            result["class"] = "composed"
        elif "class" in feats:
            result["class"] = feats["class"]
        # Add remaining features
        for k, v in feats.items():
            if k not in ("name", "class"):
                result[k] = v
        return self.order_features(result)

    def _format_value(self, key: str, value: Any) -> str:
        """Format a value for text output."""
        if isinstance(value, list):
            return ", ".join(str(v) for v in value)
        return str(value)

    def _output_single(self, data: dict[str, Any]) -> None:
        """Output a single entry."""
        if self.format == "json":
            self.output_json(data)
        elif self.format == "short":
            shorts = self.ipa.features_to_shorts(data)
            self.print(" ".join(shorts))
        else:
            for k, v in data.items():
                self.print(f"{k}: {self._format_value(k, v)}")

    def _output_multiple(self, data: list[dict[str, Any]]) -> None:
        """Output multiple entries."""
        if self.format == "json":
            self.output_json(data)
        elif self.format == "short":
            for entry in data:
                name = entry.get("name", "?")
                shorts = self.ipa.features_to_shorts(entry)
                self.print(f"{name}: {' '.join(shorts)}")
        else:
            for i, entry in enumerate(data):
                if i > 0:
                    self.print()  # Blank line between segments
                name = entry.get("name", "?")
                self.print(f"{name}:")
                for k, v in entry.items():
                    if k != "name":  # Don't repeat name
                        self.print(f"  {k}: {self._format_value(k, v)}")

    def run(self) -> int:
        phone = self.args.phone
        strict = getattr(self.args, "strict", False)

        if not strict:
            # Normalize lookalikes (e.g., keyboard 'g' -> IPA 'ɡ')
            phone = self.ipa.normalize_lookalikes(phone)

        # Default: only show explicitly defined features; --all includes defaults
        with_defaults = getattr(self.args, "all", False)

        # Check if it's a diacritic passed in isolation
        if phone in self.ipa.diacritics:
            feats = dict(self.ipa.diacritics[phone].features)
            data = self._build_entry(phone, feats, is_composed=False)
            self._output_single(data)
            return 0

        # Single base phone (no diacritics)
        if len(phone) == 1 or phone in self.ipa.phones:
            feats = self.ipa.get_features(phone, with_defaults=with_defaults)
            if not feats:
                return self.error(f"Unknown phone: {phone}")
            data = self._build_entry(phone, feats, is_composed=False)
            self._output_single(data)
            return 0

        # Composed or multi-segment string
        bundles = self.ipa.compose(phone, with_defaults=with_defaults)
        if not bundles:
            return self.error(f"Could not parse: {phone}")

        tokens = self.ipa.tokenize_ipa(phone)

        # Build entries for each segment
        entries = []
        # tokens may include suprasegmentals (stress/breaks) that compose() drops,
        # so the two can differ in length; pair up to the shorter (strict=False).
        for t, b in zip(tokens, bundles, strict=False):
            # A segment is composed if it's longer than 1 char and not a known multi-char phone
            is_composed = len(t) > 1 and t not in self.ipa.phones
            entries.append(self._build_entry(t, b, is_composed))

        # Single segment - output without wrapper
        if len(entries) == 1:
            self._output_single(entries[0])
        else:
            self._output_multiple(entries)
        return 0
