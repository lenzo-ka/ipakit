"""Named selection preserves existing scores, admission and receipts."""

from dataclasses import replace

import pytest
from ipakit import feature_models
from ipakit.bridges.costmodel import (
    AbsentCell,
    DeclaredCostFamily,
    set_feature_pack,
)
from ipakit.distance_registry import (
    DistanceRegistry,
    Metric,
    builtin_registry,
    ternary_metric,
)
from ipakit.feature_sets import FeatureSets


def custom(name="custom", *, reference="reference-a", config=None):
    geometry = FeatureSets("opaque", {"A/B #": frozenset({"x"}), "Q": frozenset({"y"})})
    return Metric(
        name,
        geometry.identity,
        config or {"gap": 1},
        lambda c: replace(
            set_feature_pack(geometry, gap=c["gap"]),
            reference=reference,
            validate_token=geometry.features,
        ),
    )


def test_builtins_all_preserves_unavailable_and_scores():
    registry = builtin_registry()
    report = registry.distances(["p"], ["b"])
    assert report["selection"] == list(registry.names)
    assert [arm["status"] for arm in report["arms"]] == [
        "available",
        "available",
        "unavailable",
        "available",
    ]
    assert "one weight per feature" in report["arms"][2]["error"]["message"]
    assert [row["normalized"] for row in report["rows"]] == pytest.approx(
        [2 / 21, 1 / 24, 0.4]
    )
    assert all(
        row["arm_id"] and row["policy"] and "reference" in row for row in report["rows"]
    )


@pytest.mark.parametrize(
    "selection",
    [
        ["all"],
        ["custom", "all"],
        ["custom", "custom"],
        "missing",
        [],
        {"custom"},
        {"custom": 1},
    ],
)
def test_selection_refusals(selection):
    with pytest.raises(ValueError):
        DistanceRegistry([custom()]).distances([], [], metrics=selection)


def test_registration_refusals():
    with pytest.raises(ValueError, match="duplicate"):
        DistanceRegistry([custom(), custom()])
    for name in ("", "all"):
        with pytest.raises(ValueError):
            custom(name)
    for config in ({"x": float("nan")}, {0: "not-json-key"}, {"x": {False: "bad"}}):
        with pytest.raises(ValueError):
            custom(config=config)


def test_order_exact_tokens_and_detached_receipts():
    config = {"gap": 1, "nested": [False, 0, None]}
    first = custom("first", config=config)
    config["nested"].append("mutation")
    first.config["nested"].append("another")
    registry = DistanceRegistry([first, custom("second")])
    corpus = [["A/B #"], ["Q"], []]
    report = registry.compare_corpus(
        corpus, metrics=["second", "first"], all_pairs=True
    )
    corpus[0].append("bad")
    assert report["corpus"][0] == ["A/B #"]
    assert report["selection"] == ["second", "first"]
    assert len(report["pairs"]) == 6
    assert len(report["rows"]) == 12
    assert report["arms"][1]["config"]["nested"] == [False, 0, None]
    assert len(DistanceRegistry(registry.registrations).names) == 2


@pytest.mark.parametrize(
    "left,right", [(["unknown"], []), ([], ["unknown"]), (["unknown"], ["unknown"])]
)
def test_refused_identity_and_empty_side(left, right):
    report = DistanceRegistry([custom()]).distances(left, right)
    row = report["rows"][0]
    assert row["status"] == "refused"
    assert row["reference"] == "reference-a"
    assert row["arm_id"] == report["arms"][0]["arm_id"]
    assert row["config"] == {"gap": 1}


def test_content_config_and_reference_distinguish_arms():
    reports = [
        DistanceRegistry([metric]).distances([], [])
        for metric in (
            custom(),
            custom(reference="reference-b"),
            custom(config={"gap": 2}),
        )
    ]
    assert len({report["arms"][0]["arm_id"] for report in reports}) == 3
    assert all(report["rows"][0]["normalized"] == 0 for report in reports)


def test_weighted_complete_custom_declaration_admits_before_shortcuts():
    declaration = feature_models.read("panphon")
    complete = replace(
        declaration, weights=(1.0,) * 24, weight_names=declaration.model.schema.features
    )
    metric = ternary_metric(
        "custom-weighted",
        complete,
        family=DeclaredCostFamily.WEIGHTED_DIFFERENCE,
        absent=AbsentCell.SKIP,
    )
    registry = DistanceRegistry([metric])
    for left, right in (
        (["unknown"], []),
        ([], ["unknown"]),
        (["unknown"], ["unknown"]),
    ):
        assert registry.distances(left, right)["rows"][0]["status"] == "refused"
    assert registry.distances(["p"], ["b"])["rows"][0]["status"] == "scored"


def test_input_string_refuses_instead_of_tokenizing():
    with pytest.raises(ValueError, match="exact tokens"):
        DistanceRegistry([custom()]).distances("A/B #", ["Q"])


@pytest.mark.parametrize("tokens", [{"p"}, {"p": 1}, iter(["p"])])
def test_unordered_and_iterator_tokens_refuse(tokens):
    with pytest.raises(ValueError, match="explicit sequence"):
        DistanceRegistry([custom()]).distances(tokens, [])


def test_ordered_tuple_tokens_work():
    assert (
        DistanceRegistry([custom()]).distances(("A/B #",), ("Q",))["rows"][0]["status"]
        == "scored"
    )


@pytest.mark.parametrize("token", ["p#", "#p", "p|", " p", "p "])
def test_house_arm_refuses_discarded_material(token):
    report = builtin_registry().distances([token], [], metrics="house/articulatory")
    assert report["rows"][0]["status"] == "refused"


@pytest.mark.parametrize("token", ["p", "pʰ", "t͡ʃ"])
def test_house_arm_retains_compositional_units(token):
    report = builtin_registry().distances(
        [token], [token], metrics="house/articulatory"
    )
    assert report["rows"][0]["normalized"] == 0


def test_constructor_failure_is_an_arm_not_a_refused_input():
    def missing(_):
        raise ImportError("optional caller-owned provider absent")

    registry = DistanceRegistry(
        [
            Metric("missing", "declared-source-content", {"version": 1}, missing),
            custom(),
        ]
    )
    report = registry.distances(["A/B #"], ["Q"])
    assert report["arms"][0]["status"] == "unavailable"
    assert report["arms"][0]["error"]["type"] == "ImportError"
    assert len(report["rows"]) == 1
    assert report["rows"][0]["status"] == "scored"


def test_typed_configuration_identity_and_actual_pack_policy():
    from ipakit.bridges.costmodel import CostPolicy

    identities = []
    for value in (False, 0, None):
        metric = custom(config={"gap": 1, "typed": value})
        identities.append(
            DistanceRegistry([metric]).distances([], [])["arms"][0]["arm_id"]
        )
    assert len(set(identities)) == 3
    original = custom()
    actual = CostPolicy(substitution_scale=2)
    metric = Metric(
        "actual",
        original.inventory_identity,
        {},
        lambda _: replace(
            original.factory({"gap": 1}),
            policy=actual,
        ),
    )
    assert (
        DistanceRegistry([metric]).distances([], [])["rows"][0]["policy"]
        == actual.identity
    )


def test_invalid_pack_metadata_and_missing_validator_are_unavailable():
    original = custom()
    for changes in (
        {"validate_token": None},
        {"indel_ceiling": float("nan")},
        {"reference": []},
    ):
        metric = Metric(
            "bad",
            original.inventory_identity,
            {},
            lambda _, changes=changes: replace(
                original.factory({"gap": 1}),
                **changes,
            ),
        )
        report = DistanceRegistry([metric]).distances([], [])
        assert report["arms"][0]["status"] == "unavailable"
        assert report["rows"] == []


@pytest.mark.parametrize(
    "bad", [-1, float("nan"), float("inf"), -float("inf"), None, "1", True]
)
@pytest.mark.parametrize("field", ["sub_cost", "insert_cost", "delete_cost"])
def test_invalid_callback_prices_refuse_without_hiding_or_aborting(bad, field):
    original = custom()

    def callback(*args):
        return bad

    metric = Metric(
        "bad-price",
        original.inventory_identity,
        {},
        lambda _: replace(
            original.factory({"gap": 1}),
            **{field: callback},
        ),
    )
    report = DistanceRegistry([metric, custom()]).distances(["A/B #"], ["Q"])
    assert report["rows"][0]["status"] == "refused"
    assert report["rows"][1]["status"] == "scored"


@pytest.mark.parametrize("field", ["sub_cost", "insert_cost", "delete_cost"])
@pytest.mark.parametrize("bad", [None, "1", {}])
def test_invalid_callback_shapes_are_unavailable(field, bad):
    original = custom()
    metric = Metric(
        "bad-shape",
        original.inventory_identity,
        {},
        lambda _: replace(
            original.factory({"gap": 1}),
            **{field: bad},
        ),
    )
    report = DistanceRegistry([metric, custom()]).distances([], [])
    assert report["arms"][0]["status"] == "unavailable"
    assert len(report["rows"]) == 1
    assert report["rows"][0]["status"] == "scored"


def test_finite_price_accumulation_overflow_is_a_row_refusal():
    original = custom()
    metric = Metric(
        "overflow",
        original.inventory_identity,
        {},
        lambda _: replace(
            original.factory({"gap": 1}),
            insert_cost=1e308,
            delete_cost=1e308,
        ),
    )
    report = DistanceRegistry([metric, custom()]).distances(["Q", "Q"], [])
    assert [row["status"] for row in report["rows"]] == ["refused", "scored"]
