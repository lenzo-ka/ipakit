"""Explicitly selected finite declarations, without native transcription parsing."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, ClassVar

from .. import feature_models
from ..bridges.costmodel import FAITHFUL, PANPHON_CONSERVING, CostPolicy
from ..feature_experiment import compare_declaration_encodings
from ..feature_transform import BinaryEncoding, ternary_to_binary
from ..finite_declaration import TernaryDeclaration, read_ternary_declaration
from ..finite_model import FiniteModel
from .base import NO_NOTATION, Command, CommandGroup, add_format_arg, add_output_arg

_POLICIES: dict[str, CostPolicy] = {
    "faithful": FAITHFUL,
    "conserving": PANPHON_CONSERVING,
}


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
    reads_notation = NO_NOTATION

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
    reads_notation = NO_NOTATION

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
    reads_notation = NO_NOTATION

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
    reads_notation = NO_NOTATION

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


class ModelTransformCommand(Command):
    """Apply an explicitly selected ternary-to-binary transform to one token.

    The token is an exact spelling in the selected finite declaration. The
    report includes the forward result, its decoded preimage and the transform's
    domain and observed-inventory loss evidence.
    """

    name = "transform"
    help = "Apply a declared binary encoding to one finite-model token"
    reads_notation = NO_NOTATION

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        _selection(parser)
        parser.add_argument("--token", required=True, help="One exact, opaque token")
        parser.add_argument(
            "--encoding",
            type=BinaryEncoding,
            choices=tuple(BinaryEncoding),
            required=True,
            help="Explicit ternary-to-binary encoding",
        )

    def run(self) -> int:
        model = load_model_declaration(self.args).model
        transform = ternary_to_binary(
            model, self.args.encoding, missing="require-complete"
        )
        witness = transform.apply(model.read(self.args.token))
        preimage = transform.decode(witness.target)
        collisions = transform.collisions()
        data = {
            "operation": "ternary_to_binary",
            "encoding": self.args.encoding.value,
            "name": model.name,
            "source_model_id": model.identity,
            "target_model_id": transform.target.identity,
            "transform_id": transform.identity,
            "missing": transform.missing,
            "input": self.args.token,
            "source": {"values": witness.source.values},
            "target": {
                "features": transform.target.schema.features,
                "values": witness.target.values,
            },
            "preimage": {
                "source_model_id": preimage.source_model_id,
                "operation_id": preimage.operation_id,
                "choices": [
                    {"feature": name, "values": values}
                    for name, values in preimage.choices
                ],
                "count": preimage.count,
                "inventory_candidates": preimage.inventory_candidates,
            },
            "loss": {
                "domain_injective": transform.injective,
                "observed_collision_groups": len(collisions),
                "collisions": [
                    {
                        "target_values": collision.target.values,
                        "source_values": [
                            source.values for source in collision.sources
                        ],
                        "tokens": collision.tokens,
                    }
                    for collision in collisions
                ],
            },
            "provenance": (
                witness.provenance.to_dict() if witness.provenance is not None else None
            ),
        }
        if self.format == "json":
            self.output_json(data)
        else:
            for key, value in data.items():
                self.print(f"{key}: {json.dumps(value, ensure_ascii=False)}")
        return 0


class ModelCompareCommand(Command):
    """Compare original and transformed costs over exact token arrays.

    The JSON document is an array containing at least two arrays of exact token
    spellings. Encodings, gap policy and cost policies are all explicit; no
    token is segmented, normalized or routed through the house model.
    """

    name = "compare"
    help = "Compare original and transformed finite-model costs"
    reads_notation = NO_NOTATION

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        _selection(parser)
        parser.add_argument(
            "--tokens-json",
            type=Path,
            required=True,
            help="JSON file with at least two exact token arrays, or '-' for stdin",
        )
        parser.add_argument(
            "--encoding",
            type=BinaryEncoding,
            choices=tuple(BinaryEncoding),
            action="append",
            required=True,
            help="Select a binary encoding; repeatable",
        )
        parser.add_argument(
            "--binary-gap",
            type=float,
            required=True,
            help="Explicit constant gap price for transformed binary arms",
        )
        parser.add_argument(
            "--policy",
            choices=tuple(_POLICIES),
            action="append",
            required=True,
            help="Select a named cost policy; repeatable",
        )
        parser.add_argument(
            "--all-pairs",
            action="store_true",
            help="Compare every ordered pair of distinct corpus positions",
        )
        parser.add_argument(
            "--include-house",
            action="store_true",
            help="Also include the native house cost arm",
        )

    def run(self) -> int:
        declaration = load_model_declaration(self.args)
        source = self.args.tokens_json
        content = (
            sys.stdin.read()
            if source == Path("-")
            else source.read_text(encoding="utf-8")
        )
        corpus = json.loads(content, parse_constant=_constant)
        report = compare_declaration_encodings(
            self.ipa,
            declaration,
            corpus,
            encodings=self.args.encoding,
            binary_gap=self.args.binary_gap,
            policies=[_POLICIES[name] for name in self.args.policy],
            all_pairs=self.args.all_pairs,
            include_house=self.args.include_house,
        )
        if self.format == "json":
            self.output_json(report)
        else:
            self.print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0


class ModelGroup(CommandGroup):
    name = "model"
    aliases: ClassVar[list[str]] = []
    help = "Inspect and operate on explicitly selected finite feature models"
    commands: ClassVar[list[type[Command]]] = [
        ModelListCommand,
        ModelInspectCommand,
        ModelRespellCommand,
        ModelQueryCommand,
        ModelTransformCommand,
        ModelCompareCommand,
    ]
