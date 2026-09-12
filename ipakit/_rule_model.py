"""Finite semantic callbacks for the shared rule engine (token projections only)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING

from ._identity import identity_fingerprint
from .finite_model import FeatureBundle, FiniteModel, Scalar

if TYPE_CHECKING:
    from .rules import Action, Edit, Pattern, Query, Rule, Site, Step


class ModelRuleError(ValueError):
    """A typed refusal, separate from a valid rule with no matching sites."""

    def __init__(self, code: str, message: str, *, candidates: tuple[str, ...] = ()):
        self.code = code
        self.candidates = candidates
        super().__init__(message)


@dataclass(frozen=True)
class FeatureConstraint:
    """Typed inclusion/exclusion; tuples do not collapse False and zero."""

    feature: str
    values: tuple[Scalar | None, ...] = field(compare=False)
    exclude: bool = False
    _key: tuple[tuple[type, Scalar | None], ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", tuple(self.values))
        object.__setattr__(
            self, "_key", tuple((type(value), value) for value in self.values)
        )
        if not self.values or type(self.exclude) is not bool:
            raise ModelRuleError("invalid-constraint", "a constraint needs values")


@dataclass(frozen=True)
class FeatureChanges:
    """Explicit typed feature writes; None writes a missing cell."""

    values: Mapping[str, Scalar | None] = field(compare=False)
    _key: tuple[tuple[str, type, Scalar | None], ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", MappingProxyType(dict(self.values)))
        object.__setattr__(
            self,
            "_key",
            tuple((name, type(value), value) for name, value in self.values.items()),
        )


@dataclass(frozen=True)
class LiteralTokens:
    """An explicit sequence of opaque tokens, never a string tokenizer."""

    tokens: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "tokens", tuple(self.tokens))


@dataclass(frozen=True)
class TokenOccurrence:
    """Ephemeral occurrence view; deliberately has no native Segment."""

    text: str
    bundle: FeatureBundle
    is_boundary: bool = field(default=False, init=False)
    transparent: bool = field(default=False, init=False)


@dataclass(frozen=True)
class TokenDerivation:
    """Explicit token projection; not a graph-preserving utterance operation."""

    start: tuple[str, ...]
    tokens: tuple[str, ...]
    steps: tuple[Step, ...]
    model_id: str

    def to_form(self) -> None:
        raise ModelRuleError(
            "unsupported-operation", "token projections cannot become native Forms"
        )


def same(left: Scalar | None, right: Scalar | None) -> bool:
    return type(left) is type(right) and left == right


def validate_constraints(pattern: Pattern, model: FiniteModel) -> None:
    if (
        pattern.brace_base
        or pattern.boundary is not None
        or pattern.mark is not None
        or pattern.tier is not None
        or pattern.tier_edge is not None
        or pattern.seg_required
        or pattern.seg_included
        or pattern.seg_excluded
        or pattern.pro_required
        or pattern.pro_included
        or pattern.pro_excluded
        or pattern.seg_agreements
        or pattern.pro_agreements
        or pattern.optional
        or pattern.repeated
        or pattern.repeat_min != 1
        or pattern.repeat_max != 1
    ):
        raise ModelRuleError(
            "unsupported-operation",
            "finite rules require typed constraints, not native/structural terms",
        )
    if pattern.literal is not None:
        model.read(pattern.literal)
    names: set[str] = set()
    for constraint in pattern.constraints:
        if constraint.feature in names:
            raise ModelRuleError(
                "invalid-constraint", f"repeated feature: {constraint.feature!r}"
            )
        names.add(constraint.feature)
        for value in constraint.values:
            model.schema.validate({constraint.feature: value})


def validate_query(query: Query, model: FiniteModel) -> None:
    if query.target is None:
        raise ModelRuleError(
            "unsupported-operation", "finite insertion is outside this slice"
        )
    for pattern in (query.target, *query.left, *query.right):
        validate_constraints(pattern, model)
        if pattern._model != model:
            raise ModelRuleError(
                "model-mismatch", "pattern belongs to another model or is not compiled"
            )


def read_tokens(tokens: object, model: FiniteModel) -> tuple[TokenOccurrence, ...]:
    if not isinstance(tokens, (tuple, list)) or any(
        type(token) is not str for token in tokens
    ):
        raise ModelRuleError(
            "unsupported-input",
            "pass an explicit tuple/list of token strings; graphs, Forms and strings are not projections",
        )
    return tuple(TokenOccurrence(token, model.read(token)) for token in tokens)


def validate_occurrences(items: Sequence[object], model: FiniteModel) -> None:
    for item in items:
        if not isinstance(item, TokenOccurrence) or item.bundle != model.read(
            item.text
        ):
            raise ModelRuleError(
                "model-mismatch",
                "input occurrence is not this model's exact token/bundle",
            )


def matches(pattern: Pattern, unit: object, model: FiniteModel) -> bool:
    validate_constraints(pattern, model)
    validate_occurrences((unit,), model)
    assert isinstance(unit, TokenOccurrence)
    if pattern.literal is not None and pattern.literal != unit.text:
        return False
    values = dict(zip(model.schema.features, unit.bundle.values, strict=True))
    return all(
        any(same(values[term.feature], value) for value in term.values) != term.exclude
        for term in pattern.constraints
    )


def edit(
    action: Action, site: Site, items: Sequence[object], model: FiniteModel, rule: str
) -> Edit | None:
    from .rules import Edit

    validate_occurrences(items, model)
    if not 0 <= site.start < site.end <= len(items) or site.end != site.start + 1:
        raise ModelRuleError(
            "unsupported-operation", "finite actions require one input token"
        )
    target = items[site.start]
    assert isinstance(target, TokenOccurrence)
    payload = action.finite
    if isinstance(payload, FeatureChanges):
        result = model.respell(target.text, payload.values)
        if result.status != "unique":
            raise ModelRuleError(
                "unrealizable" if result.status == "none" else "ambiguous",
                f"{rule!r} at [{site.start},{site.end}) has {result.status} realization for {result.bundle.values!r}",
                candidates=result.candidates,
            )
        tokens = result.candidates
    elif isinstance(payload, LiteralTokens):
        tokens = payload.tokens
    else:
        tokens = ()
    replacement = read_tokens(tokens, model)
    if tokens == (target.text,):
        return None
    return Edit(
        rule, site.start, site.end, replacement, target.text, "".join(tokens), site
    )


def bind(rule: Rule, model: FiniteModel) -> Rule:
    """Compile/copy the public AST, including paths which might never match."""
    from dataclasses import replace

    from .rules import Query

    if rule._model is not None and rule._model != model:
        raise ModelRuleError("model-mismatch", "rule belongs to another model")
    if rule.optional or rule.source_tiers not in ((), ("segment",)):
        raise ModelRuleError(
            "unsupported-operation",
            "finite optional/graph rules are outside this slice",
        )
    if rule.query.target is None:
        raise ModelRuleError(
            "unsupported-operation", "finite insertion is outside this slice"
        )
    if rule.action.becomes is not None:
        raise ModelRuleError(
            "unsupported-operation",
            "use FeatureChanges or LiteralTokens for finite actions",
        )
    payload = rule.action.finite
    if isinstance(payload, FeatureChanges):
        model.schema.validate(payload.values)
        payload = FeatureChanges(payload.values)
    elif isinstance(payload, LiteralTokens):
        read_tokens(payload.tokens, model)
        payload = LiteralTokens(payload.tokens)
    elif payload is not None:
        raise ModelRuleError("invalid-action", "unknown finite action payload")

    def pattern(value: Pattern) -> Pattern:
        validate_constraints(value, model)
        return replace(value, constraints=tuple(value.constraints), _model=model)

    query = Query(
        pattern(rule.query.target),
        tuple(map(pattern, rule.query.left)),
        tuple(map(pattern, rule.query.right)),
        _model=model,
    )
    identity = identity_fingerprint(
        {
            "format": "finite-rule/1",
            "model": model.identity,
            "notation": "typed-ast/safe-bare-v1",
            "realization": "unique-or-refuse/1",
            "patterns": [
                {
                    "literal": p.literal,
                    "constraints": [
                        (t.feature, t.values, t.exclude) for t in p.constraints
                    ],
                }
                for p in (query.target, *query.left, *query.right)
                if p is not None
            ],
            "left_width": len(query.left),
            "right_width": len(query.right),
            "action": (
                {"changes": dict(payload.values)}
                if isinstance(payload, FeatureChanges)
                else (
                    {"tokens": payload.tokens}
                    if isinstance(payload, LiteralTokens)
                    else {"delete": True}
                )
            ),
        }
    )
    return replace(
        rule,
        query=query,
        action=replace(rule.action, finite=payload, _model=model),
        _model=model,
        binding=identity,
        source_tiers=(),
    )


def decode(raw: str, name: str, model: FiniteModel) -> Scalar:
    if name not in model.schema.domains:
        model.schema.validate({name: None})
    candidates = tuple(v for v in model.schema.domains[name] if str(v) == raw)
    if len(candidates) != 1:
        raise ModelRuleError(
            "invalid-value",
            f"{name}={raw} has no unique declared typed reading; use typed AST",
        )
    return candidates[0]


def pattern_from_text(text: str, model: FiniteModel) -> Pattern:
    from .rules import Pattern

    if text.startswith("[") and text.endswith("]"):
        terms = text[1:-1].split()
        constraints = []
        for term in terms:
            if term.count("=") != 1:
                raise ModelRuleError(
                    "unsupported-notation",
                    "finite DSL uses explicit feature=value terms",
                )
            name, value = term.split("=")
            constraints.append(FeatureConstraint(name, (decode(value, name, model),)))
        if not constraints:
            raise ModelRuleError("invalid-constraint", "empty finite query")
        return Pattern(text, constraints=tuple(constraints))
    if (
        not text
        or any(c.isspace() or c in "[]{}()/;_<>~=\"'|#%" for c in text)
        or text in ("0", "Ø", "∅")
    ):
        raise ModelRuleError(
            "unsupported-notation",
            "use typed AST for punctuation-bearing literal tokens",
        )
    model.read(text)
    return Pattern(text, literal=text)


def action_from_text(
    text: str, model: FiniteModel
) -> FeatureChanges | LiteralTokens | None:
    if text == "∅":
        return None
    pattern = pattern_from_text(text, model)
    if pattern.literal is not None:
        return LiteralTokens((pattern.literal,))
    validate_constraints(pattern, model)
    return FeatureChanges(
        {term.feature: term.values[0] for term in pattern.constraints}
    )
