"""Explicitly selected finite declarations, without native transcription parsing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, ClassVar

from .. import feature_models
from ..finite_declaration import TernaryDeclaration, read_ternary_declaration
from ..finite_model import FiniteModel
from .base import Command, CommandGroup, add_format_arg, add_output_arg


def add_model_selector(
    parser: argparse.ArgumentParser, *, required: bool = True
) -> None:
    """Declare the same named/path choice for model and finite-rule commands."""
    selectors = parser.add_mutually_exclusive_group(required=required)
    selectors.add_argument("--model", help="Explicit shipped feature-model name")
    selectors.add_argument(
        "--model-declaration", type=Path, help="Caller-supplied ternary XML declaration"
    )


def _selection(parser: argparse.ArgumentParser) -> None:
    add_model_selector(parser)
    add_format_arg(parser)
    add_output_arg(parser)


def load_model_declaration(args: argparse.Namespace) -> TernaryDeclaration:
    if args.ipa_xml is not None or args.cmu_xml is not None:
        raise ValueError("native --ipa-xml/--cmu-xml cannot select a finite model")
    if args.model is not None:
        return feature_models.read(args.model)
    if args.model_declaration is None:
        raise ValueError("select a finite model with --model or --model-declaration")
    return read_ternary_declaration(args.model_declaration)


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _feature_object(text: str, option: str) -> dict[str, Any]:
    result = json.loads(text, object_pairs_hook=_object, parse_constant=_constant)
    if not isinstance(result, dict):
        raise ValueError(f"{option} requires a JSON object of feature values")
    return result


def _changes(text: str) -> dict[str, Any]:
    return _feature_object(text, "--changes-json")


class ModelListCommand(Command):
    """List shipped feature declarations; these names are not house Styles."""

    name = "list"
    help = "List shipped finite feature models"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        add_format_arg(parser)
        add_output_arg(parser)

    def run(self) -> int:
        names = feature_models.available()
        if self.format == "json":
            self.output_json(names)
        else:
            self.output_lines(list(names))
        return 0


class ModelInspectCommand(Command):
    """Inspect an explicitly selected ternary declaration and its actual schema."""

    name = "inspect"
    help = "Inspect a finite model's schema, identity and provenance"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        _selection(parser)
        parser.add_argument(
            "--rows", action="store_true", help="Include every token row"
        )

    def run(self) -> int:
        declaration = load_model_declaration(self.args)
        model: FiniteModel = declaration.model
        data: dict[str, Any] = {
            "operation": "inspect",
            "name": model.name,
            "model_id": model.identity,
            "schema": [
                {"feature": name, "domain": domain}
                for name, domain in model.schema.domains.items()
            ],
            "token_count": len(model.rows),
            "source": model.source.to_dict() if model.source is not None else None,
            "codec": {
                "name": "ternary-xml",
                "declaration_keys": "NFD required",
                "input_tokens": "exact; no normalization or segmentation",
                "missing_cell": None,
            },
        }
        if self.args.rows:
            data["rows"] = [
                {"token": token, "values": values}
                for token, values in model.rows.items()
            ]
        if self.format == "json":
            self.output_json(data)
        else:
            for key, value in data.items():
                self.print(f"{key}: {json.dumps(value, ensure_ascii=False)}")
        return 0


class ModelRespellCommand(Command):
    """Edit one opaque token's bundle and report every exact realization."""

    name = "respell"
    help = "Respell one token under an explicitly selected finite model"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        _selection(parser)
        parser.add_argument("--token", required=True, help="One exact, opaque token")
        parser.add_argument(
            "--changes-json", required=True, help="JSON feature-edit object"
        )

    def run(self) -> int:
        declaration = load_model_declaration(self.args)
        model: FiniteModel = declaration.model
        changes = _changes(self.args.changes_json)
        result = model.respell(self.args.token, changes)
        data = {
            "operation": "respell",
            "name": model.name,
            "model_id": model.identity,
            "input": self.args.token,
            "changes": changes,
            "status": result.status,
            "candidates": result.candidates,
            "values": result.bundle.values,
        }
        if self.format == "json":
            self.output_json(data)
        else:
            for key, value in data.items():
                self.print(f"{key}: {json.dumps(value, ensure_ascii=False)}")
        return 0


class ModelQueryCommand(Command):
    """Find every declared token satisfying typed feature constraints."""

    name = "query"
    help = "List phones matching features in an explicitly selected finite model"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        _selection(parser)
        parser.add_argument(
            "--features-json",
            required=True,
            help="JSON feature constraints; {} lists all tokens",
        )

    def run(self) -> int:
        from ..inventory_operations import FiniteInventory

        model = load_model_declaration(self.args).model
        constraints = _feature_object(self.args.features_json, "--features-json")
        matches = FiniteInventory(model).phones_matching(constraints)
        data = {
            "operation": "phones_matching",
            "name": model.name,
            "model_id": model.identity,
            "constraints": constraints,
            "matches": matches,
        }
        if self.format == "json":
            self.output_json(data)
        else:
            self.output_lines(list(matches))
        return 0


class ModelGroup(CommandGroup):
    name = "model"
    aliases: ClassVar[list[str]] = []
    help = "Inspect, query and respell with explicitly selected finite feature models"
    commands: ClassVar[list[type[Command]]] = [
        ModelListCommand,
        ModelInspectCommand,
        ModelRespellCommand,
        ModelQueryCommand,
    ]
