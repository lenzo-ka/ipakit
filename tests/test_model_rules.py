"""Finite semantics use the existing scanner, splice and feeding cascade."""

from dataclasses import replace
from unittest.mock import patch

import pytest
from ipakit import load_ipa_features
from ipakit.feature_models import resource_path
from ipakit.finite_declaration import read_ternary_declaration
from ipakit.finite_model import FeatureSchema, FiniteModel, InvalidFeature, MissingToken
from ipakit.rules import (
    Action,
    FeatureChanges,
    FeatureConstraint,
    LiteralTokens,
    ModelRuleError,
    Pattern,
    Query,
    Rule,
    RuleSet,
    parse,
)


@pytest.fixture
def model():
    return FiniteModel(
        "foreign",
        FeatureSchema({"spark": ("dim", "bright"), "host": ("gate", "body")}),
        {"@D": ("dim", "body"), "@B": ("bright", "body"), "@G": ("bright", "gate")},
    )


def constrained(name, value):
    return Pattern("typed", constraints=(FeatureConstraint(name, (value,)),))


def change(model, name, value, target=None):
    return Rule(
        "typed",
        Query(target or Pattern("any")),
        Action(finite=FeatureChanges({name: value})),
    ).bind(model)


def test_shared_context_and_two_rule_feeding_without_house(model):
    # All native interpretation/state/finalization entrances are poisoned.
    with (
        patch("ipakit.rules._default", side_effect=AssertionError("native default")),
        patch("ipakit.rules.Form.of", side_effect=AssertionError("native Form")),
        patch("ipakit.rules.units", side_effect=AssertionError("native parser")),
        patch("ipakit.rules.surface", side_effect=AssertionError("native surface")),
    ):
        first = parse("[spark=dim] -> [spark=bright] / _ [host=gate]", model=model)
        source = ("@D", "@G", "@D", "@B")
        actual = first.rewrite_tokens(source)
        assert actual.tokens == ("@B", "@G", "@D", "@B")
        assert [(e.start, e.end) for e in actual.steps[0].edits] == [(0, 1)]
        assert actual.steps[0].edits[0].site.right == (1,)
        assert source == ("@D", "@G", "@D", "@B")
        assert first.rewrite_tokens(("@D",)).tokens == ("@D",)
        assert first.rewrite_tokens(()).tokens == ()
        second = parse("[spark=bright host=body] -> [host=gate]", model=model)
        assert second.rewrite_tokens(("@D", "@G")).tokens == ("@D", "@G")
        fed = RuleSet((first, second)).derive_tokens(("@D", "@G"))
        assert fed.tokens == ("@G", "@G")
        assert fed.steps[0].after_tokens == fed.steps[1].before_tokens == ("@B", "@G")
        assert fed.steps[1].edits[0].start == 0
        # This is the existing engine, not an adjacent implementation.
        with patch.object(Query, "sites", side_effect=RuntimeError("shared sites")):
            with pytest.raises(RuntimeError, match="shared sites"):
                first.rewrite_tokens(source)


def test_left_context_and_snapshot_nonfeeding(model):
    rule = parse("[spark=dim] -> [spark=bright] / [spark=bright] _", model=model)
    assert rule.rewrite_tokens(("@B", "@D", "@D")).tokens == ("@B", "@B", "@D")
    assert RuleSet((rule, rule)).derive_tokens(("@B", "@D", "@D")).tokens == (
        "@B",
        "@B",
        "@B",
    )


def test_direct_ast_and_dsl_bind_the_same_operation(model):
    ast = Rule(
        "direct",
        Query(constrained("spark", "dim"), right=(constrained("host", "gate"),)),
        Action(finite=FeatureChanges({"spark": "bright"})),
    ).bind(model)
    dsl = parse("[spark=dim] -> [spark=bright] / _ [host=gate]", model=model)
    assert ast.binding == dsl.binding
    assert (
        ast.rewrite_tokens(("@D", "@G")).tokens
        == dsl.rewrite_tokens(("@D", "@G")).tokens
    )


@pytest.fixture
def typed():
    return FiniteModel(
        "typed",
        FeatureSchema({"x": (False, 0, True, 1, "1")}),
        {
            "false": (False,),
            "zero": (0,),
            "true": (True,),
            "one": (1,),
            "string": ("1",),
            "missing": (None,),
        },
    )


@pytest.mark.parametrize(
    "value,token",
    [
        (False, "false"),
        (0, "zero"),
        (True, "true"),
        (1, "one"),
        ("1", "string"),
        (None, "missing"),
    ],
)
def test_typed_matching_and_realization(typed, value, token):
    rule = change(typed, "x", value, constrained("x", value))
    assert [s.start for s in rule.recognize_tokens(tuple(typed.rows))] == [
        tuple(typed.rows).index(token)
    ]
    assert change(typed, "x", value).rewrite_tokens(("zero",)).tokens == (token,)


def test_typed_inclusion_exclusion_and_hash(typed):
    included = Pattern("typed set", constraints=(FeatureConstraint("x", (False, 0)),))
    rule = change(typed, "x", "1", included)
    assert [
        s.start
        for s in rule.recognize_tokens(("false", "zero", "true", "one", "missing"))
    ] == [0, 1]
    excluded = replace(
        included, constraints=(FeatureConstraint("x", (False, 0), exclude=True),)
    )
    assert [
        s.start
        for s in change(typed, "x", "1", excluded).recognize_tokens(
            ("false", "zero", "true", "one", "missing")
        )
    ] == [2, 3, 4]
    assert len({FeatureConstraint("x", (False,)), FeatureConstraint("x", (0,))}) == 2
    assert len({FeatureChanges({"x": False}), FeatureChanges({"x": 0})}) == 2


def test_ambiguous_dsl_type_requires_ast(typed):
    with pytest.raises(ModelRuleError, match="unique declared typed reading"):
        parse("[x=1] -> [x=0]", model=typed)
    assert parse("[x=False] -> [x=0]", model=typed).rewrite_tokens(
        ("false",)
    ).tokens == ("zero",)


@pytest.mark.parametrize("tokens", [(), ("@G",), ("@D",)])
def test_wrong_model_refuses_before_scanning(model, tokens):
    wrong = FiniteModel("other", model.schema, model.rows)
    rule = parse("[spark=dim] -> ∅", model=model)
    with patch.object(Query, "sites", side_effect=AssertionError("must not scan")):
        with pytest.raises(ModelRuleError, match="another model"):
            rule.rewrite_tokens(tokens, model=wrong)
        with pytest.raises(ModelRuleError, match="another model"):
            rule.recognize_tokens(tokens, model=wrong)
        with pytest.raises(ModelRuleError, match="another model"):
            RuleSet((rule,)).derive_tokens(tokens, model=wrong)


def test_complete_input_validation_even_when_unmatched(model):
    rule = parse("[spark=dim] -> [spark=bright]", model=model)
    with pytest.raises(MissingToken):
        rule.rewrite_tokens(("@D", "UNKNOWN"))
    with pytest.raises(MissingToken):
        rule.recognize_tokens(("UNKNOWN",))


@pytest.mark.parametrize(
    "field,value",
    [
        ("tier", "word"),
        ("boundary", "any"),
        ("brace_base", True),
        ("repeated", True),
        ("optional", True),
        ("seg_required", {"spark": "dim"}),
        ("pro_required", {"stress": "primary"}),
    ],
)
def test_unsupported_ast_refuses_at_bind(model, field, value):
    pattern = replace(Pattern("unsupported"), **{field: value})
    with pytest.raises(ModelRuleError, match="typed constraints"):
        change(model, "spark", "bright", pattern)


@pytest.mark.parametrize(
    "text",
    [
        "[spark=dim spark=bright] -> @B",
        "[spark=α] -> @B",
        "[spark=dim] ~> @B",
        "[spark=dim] -> @B / _ ([host=gate])*",
        "[spark=dim] -> @B / _ <word",
        '"@D" -> @B',
    ],
)
def test_unsupported_or_invalid_dsl_refuses(model, text):
    with pytest.raises((ModelRuleError, InvalidFeature, MissingToken)):
        parse(text, model=model)


def test_invalid_feature_and_value_are_not_no_match(model):
    with pytest.raises(InvalidFeature, match="undeclared feature"):
        change(model, "invented", 0)
    with pytest.raises(InvalidFeature, match="invalid value"):
        change(model, "spark", 0)
    with pytest.raises(ModelRuleError, match="mutually exclusive"):
        parse("@D -> @B", load_ipa_features(), model=model)


def test_ordinary_foreign_stress_is_not_prosody():
    model = FiniteModel(
        "stress", FeatureSchema({"stress": (0, 1)}), {"@D": (0,), "@B": (1,)}
    )
    with patch("ipakit.rules._is_prosodic", side_effect=AssertionError("native role")):
        assert parse("[stress=0] -> [stress=1]", model=model).rewrite_tokens(
            ("@D",)
        ).tokens == ("@B",)


def test_realization_none_and_ambiguity_are_distinct(model):
    with pytest.raises(ModelRuleError) as caught:
        change(model, "host", "gate", constrained("spark", "dim")).rewrite_tokens(
            ("@D",)
        )
    assert caught.value.code == "unrealizable" and caught.value.candidates == ()
    alias = FiniteModel(
        "alias", model.schema, {**model.rows, "aliasB": ("bright", "body")}
    )
    with pytest.raises(ModelRuleError) as caught:
        change(alias, "spark", "bright").rewrite_tokens(("@D",))
    assert caught.value.code == "ambiguous" and caught.value.candidates == (
        "@B",
        "aliasB",
    )
    # Unique-or-refuse does not silently preserve an alias on a requested no-op.
    with pytest.raises(ModelRuleError, match="ambiguous"):
        change(alias, "spark", "bright").rewrite_tokens(("@B",))


def test_panphon_realization_is_not_first_candidate():
    model = read_ternary_declaration(resource_path("panphon")).model
    with pytest.raises(ModelRuleError) as caught:
        change(model, "voi", 1).rewrite_tokens(("p",))
    assert caught.value.code == "ambiguous"
    assert caught.value.candidates == ("b", "b̟", "b̠")


def test_token_boundaries_and_reserved_literal_ast():
    model = FiniteModel(
        "opaque",
        FeatureSchema({"x": (0, 1, 2)}),
        {"ab": (0,), "c": (1,), "a": (0,), "bc": (1,), "/;_ -> []": (2,)},
    )
    empty = RuleSet(())
    left = empty.derive_tokens(("ab", "c"), model=model)
    right = empty.derive_tokens(("a", "bc"), model=model)
    assert left != right and left.tokens != right.tokens
    rule = Rule(
        "literal",
        Query(Pattern("exact", literal="/;_ -> []")),
        Action(finite=LiteralTokens(("a", "bc"))),
    ).bind(model)
    assert rule.rewrite_tokens(("/;_ -> []",)).tokens == ("a", "bc")
    assert RuleSet((rule,)).derive_tokens(("/;_ -> []",)).steps[0].after_tokens == (
        "a",
        "bc",
    )
    with pytest.raises(ModelRuleError, match="token-projection"):
        RuleSet((rule,)).variants([])


def test_equal_display_replacement_still_changes_token_state():
    model = FiniteModel(
        "collision", FeatureSchema({"x": (0,)}), {"abc": (0,), "ab": (0,), "c": (0,)}
    )
    rule = Rule(
        "split",
        Query(Pattern("atom", literal="abc")),
        Action(finite=LiteralTokens(("ab", "c"))),
    ).bind(model)
    result = RuleSet((rule,)).derive_tokens(("abc",))
    assert result.tokens == ("ab", "c")
    assert result.steps[0].before == result.steps[0].after == "abc"
    assert result.steps[0].fired
    assert result.steps[0].before_tokens == ("abc",)
    assert result.steps[0].after_tokens == ("ab", "c")


def test_deletion_feeds_empty_state_and_empty_cascade_is_bound(model):
    deletion = parse("@D -> ∅", model=model)
    assert RuleSet((deletion, deletion)).derive_tokens(("@D",)).tokens == ()
    assert RuleSet(()).derive_tokens((), model=model).model_id == model.identity
    with pytest.raises(ModelRuleError, match="identity"):
        RuleSet(()).derive_tokens(())


def test_shared_splice_and_cascade_are_observable_dependencies(model):
    rule = parse("@D -> @B", model=model)
    with patch("ipakit.rules._apply_edits", side_effect=RuntimeError("shared splice")):
        with pytest.raises(RuntimeError, match="shared splice"):
            rule.rewrite_tokens(("@D",))
    with patch("ipakit.rules._cascade", side_effect=RuntimeError("shared cascade")):
        with pytest.raises(RuntimeError, match="shared cascade"):
            RuleSet((rule,)).derive_tokens(("@D",))


def test_public_low_level_callbacks_reject_native_context(model):
    from ipakit._rule_model import read_tokens
    from ipakit.rules import Site

    rule = parse("@D -> @B", model=model)
    native = load_ipa_features()
    items = read_tokens(("@D",), model)
    with pytest.raises(ModelRuleError, match="native features"):
        rule.target.matches(items[0], native)
    with pytest.raises(ModelRuleError, match="native features"):
        rule.action.edit(Site(0, 1), items, native)
    with pytest.raises(ModelRuleError, match="native features"):
        rule.query.sites(items, native)


def test_refuse_graph_form_string_and_native_entry_points(model):
    from ipakit.form import Form

    rule = parse("@D -> @B", model=model)
    graph_form = Form.parse("p")
    for bad in ("@D", graph_form, graph_form._graph, (graph_form.units[0],)):
        with pytest.raises(ModelRuleError, match="explicit tuple/list"):
            rule.rewrite_tokens(bad)
    with pytest.raises(ModelRuleError, match="native Forms"):
        rule.rewrite_tokens(("@D",)).to_form()
    for operation in (rule.apply, rule.rewrite, rule.edits, rule.recognize):
        with pytest.raises(ModelRuleError, match="token-projection"):
            operation(())
    with pytest.raises(ModelRuleError, match="token-projection"):
        RuleSet((rule,)).derive(())


def test_binding_freezes_input_and_detects_semantic_replacement(model):
    values = {"spark": "bright"}
    constraints = [FeatureConstraint("spark", ("dim",))]
    ast = Rule(
        "mutable",
        Query(Pattern("target", constraints=constraints)),
        Action(finite=FeatureChanges(values)),
    )
    rule = ast.bind(model)
    values["spark"] = "dim"
    constraints.clear()
    assert rule.rewrite_tokens(("@D",)).tokens == ("@B",)
    corrupted = replace(
        rule, action=replace(rule.action, finite=FeatureChanges({"host": "gate"}))
    )
    with pytest.raises(ModelRuleError, match="operation was changed"):
        corrupted.rewrite_tokens(())
    with pytest.raises(ModelRuleError, match="compile"):
        ast.recognize_tokens(())


def mixed_child(left, right, part):
    if part in ("query", "action"):
        return replace(left, **{part: getattr(right, part)})
    if part == "target":
        return replace(left, query=replace(left.query, target=right.query.target))
    return replace(
        left, query=replace(left.query, **{part: getattr(right.query, part)})
    )


@pytest.fixture
def bound_pair():
    schema = FeatureSchema({"x": (0, 1)})
    first = FiniteModel("first", schema, {"a": (0,), "b": (1,)})
    second = FiniteModel("second", schema, {"a": (0,), "b": (1,)})
    text = "[x=0] -> [x=1] / [x=1] _ [x=1]"
    return first, parse(text, model=first), parse(text, model=second)


@pytest.mark.parametrize("part", ["query", "action", "target", "left", "right"])
@pytest.mark.parametrize("tokens", [(), ("b",)])
def test_nested_compiled_ownership_checked_before_every_scan(bound_pair, part, tokens):
    model, left, right = bound_pair
    mixed = mixed_child(left, right, part)
    with patch.object(
        Query, "sites", side_effect=AssertionError("ownership must precede scanning")
    ):
        for operation in (mixed.recognize_tokens, mixed.rewrite_tokens):
            with pytest.raises(ModelRuleError) as caught:
                operation(tokens)
            assert caught.value.code == "model-mismatch"
        with pytest.raises(ModelRuleError) as caught:
            RuleSet((mixed,)).derive_tokens(tokens, model=model)
        assert caught.value.code == "model-mismatch"


@pytest.mark.parametrize("part", ["query", "action", "target", "left", "right"])
def test_fresh_compilation_does_not_reassign_bound_children(bound_pair, part):
    model, left, right = bound_pair
    mixed = mixed_child(left, right, part)
    fresh = Rule("fresh", mixed.query, mixed.action)
    with pytest.raises(ModelRuleError) as caught:
        fresh.bind(model)
    assert caught.value.code == "model-mismatch"


@pytest.mark.parametrize("part", ["query", "action", "target", "left", "right"])
def test_compiled_rule_requires_children_to_keep_their_binding(bound_pair, part):
    _, left, _ = bound_pair
    if part in ("query", "action"):
        broken = replace(left, **{part: replace(getattr(left, part), _model=None)})
    elif part == "target":
        broken = replace(
            left, query=replace(left.query, target=replace(left.target, _model=None))
        )
    else:
        broken = replace(
            left,
            query=replace(
                left.query,
                **{
                    part: tuple(
                        replace(p, _model=None) for p in getattr(left.query, part)
                    )
                },
            ),
        )
    for operation in (broken.recognize_tokens, broken.rewrite_tokens):
        with pytest.raises(ModelRuleError) as caught:
            operation(())
        assert caught.value.code == "model-mismatch"


def test_genuine_unbound_ast_and_same_model_children_remain_reusable(bound_pair):
    model, left, _ = bound_pair
    assert Rule("same children", left.query, left.action).bind(model).rewrite_tokens(
        ("b", "a", "b")
    ).tokens == ("b", "b", "b")
    unbound = Rule(
        "unbound", Query(constrained("x", 0)), Action(finite=FeatureChanges({"x": 1}))
    )
    assert unbound.bind(model).rewrite_tokens(("a",)).tokens == ("b",)
    # Mixing an unbound context with same-model compiled children is explicit
    # compilation of a fresh AST, not reassignment of a foreign bound child.
    fresh = Rule(
        "mixed ownership", Query(left.target, right=(constrained("x", 1),)), left.action
    ).bind(model)
    assert fresh.rewrite_tokens(("a", "b")).tokens == ("b", "b")
