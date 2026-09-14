"""Adapter observations, admission and outcomes retain each model's semantics."""

import pytest
from ipakit.feature_sets import FeatureSets, OutsideDomain
from ipakit.features import IPAFeatures
from ipakit.finite_model import FeatureSchema, FiniteModel, InvalidFeature, MissingToken
from ipakit.inventory_operations import (
    CanonicalRespelling,
    FiniteInventory,
    HouseInventory,
    MatchingInventory,
    RespellingInventory,
    SetInventory,
    SoundInventory,
)


@pytest.fixture
def finite():
    return FiniteInventory(
        FiniteModel(
            "opaque",
            FeatureSchema({"f": (False, 0, "0", True)}),
            {"A/B #": (False,), "zero": (0,), "alias": (0,), "absent": (None,)},
        )
    )


@pytest.fixture(scope="module")
def house():
    return HouseInventory(IPAFeatures())


def test_finite_exact_typed_queries_and_complete_aliases(finite):
    assert finite.admission == "exact-finite"
    assert finite.identity == finite.model.identity
    assert finite.name == "opaque"
    assert finite.declared_tokens == ("A/B #", "zero", "alias", "absent")
    assert finite.read("A/B #").values == (False,)
    assert finite.phones_matching({"f": False}) == ("A/B #",)
    assert finite.phones_matching({"f": 0}) == ("zero", "alias")
    assert finite.phones_matching({"f": None}) == ("absent",)
    assert finite.phones_matching({"f": "0"}) == ()
    assert finite.phones_matching({}) == finite.declared_tokens
    result = finite.respell("A/B #", {"f": 0})
    assert result == finite.model.respell("A/B #", {"f": 0})
    assert result.candidates == ("zero", "alias")
    assert result.status == "ambiguous"
    assert finite.respell("zero", {"f": True}).status == "none"
    assert finite.respell("absent", {}).status == "unique"
    for token in ("A/B", "A/B # ", "A", "p"):
        with pytest.raises(MissingToken):
            finite.read(token)
        with pytest.raises(MissingToken):
            finite.respell(token, {})


def test_finite_schema_errors_remain_errors(finite):
    for query in ({"unknown": 0}, {"f": 2}):
        with pytest.raises(InvalidFeature):
            finite.phones_matching(query)
        with pytest.raises(InvalidFeature):
            finite.respell("zero", query)


def test_finite_matching_delegates_to_named_model_operation(finite, monkeypatch):
    constraints = {"f": 0}
    seen = []

    def phones_matching(self, supplied):
        seen.append((self, supplied))
        return ("delegated",)

    monkeypatch.setattr(FiniteModel, "phones_matching", phones_matching, raising=False)
    assert finite.phones_matching(constraints) == ("delegated",)
    assert seen == [(finite.model, constraints)]
    assert seen[0][1] is constraints


def test_finite_unicode_keys_are_not_normalized():
    model = FiniteModel(
        "unicode", FeatureSchema({"f": (0, 1)}), {"é": (0,), "e\u0301": (1,)}
    )
    adapter = FiniteInventory(model)
    assert adapter.declared_tokens == ("é", "e\u0301")
    assert adapter.read("é").values == (0,)
    assert adapter.read("e\u0301").values == (1,)
    assert adapter.respell("é", {"f": 1}).candidates == ("e\u0301",)


def test_finite_identity_tracks_typed_content_and_owns_rows():
    rows = {"a": (False,)}
    schema = FeatureSchema({"f": (False, 0)})
    adapter = FiniteInventory(FiniteModel("same", schema, rows))
    changed = FiniteInventory(FiniteModel("same", schema, {"a": (0,)}))
    assert adapter.identity != changed.identity
    before = adapter.identity
    rows["a"] = (0,)
    assert adapter.identity == before
    assert adapter.read("a").values == (False,)


def test_house_queries_preserve_native_syntax_defaults_and_order(house):
    for query in ({"voiced": "+"}, ["+aspirated", "-voiced"], ["-normal"]):
        for defaults in (False, True):
            assert house.phones_matching(query, with_defaults=defaults) == tuple(
                house.ipa.phones_matching(query, with_defaults=defaults)
            )
    with pytest.raises(ValueError):
        house.phones_matching("voiced")
    with pytest.raises(ValueError):
        house.phones_matching({"voiced": "bogus"})
    assert house.declared_tokens == tuple(house.ipa.phones)


def test_house_composition_strict_admission_and_declared_only(house):
    assert house.admission == "single-unit"
    assert house.read("tː").to_ipa() == "tː"
    assert house.read("a͜ɪ").to_ipa() == "a͜ɪ"
    for token in ("pt", "p☃", "☃", "", "p#", "#p", "p|", " p ", "#p|"):
        with pytest.raises(ValueError):
            house.read(token)
        with pytest.raises(ValueError):
            house.respell(token, {})
    declared = HouseInventory(house.ipa, declared_only=True)
    assert declared.admission == "declared-only"
    assert declared.identity != house.identity
    assert "tː" not in declared.declared_tokens
    with pytest.raises(ValueError, match="declared"):
        declared.read("tː")
    with pytest.raises(ValueError, match="declared"):
        declared.read("#p|")
    assert declared.read("t").to_ipa() == "t"
    assert HouseInventory(house.ipa).identity == house.identity
    with pytest.raises(ValueError, match="bool"):
        HouseInventory(house.ipa, declared_only=1)


def test_house_canonical_result_and_prosody(house):
    result = house.respell("tː", {"voiced": "+"})
    assert result == CanonicalRespelling(house.identity, "dː")
    assert result.status == "canonical"
    assert not hasattr(result, "candidates")
    assert house.respell("a͜ɪ", {"voiced": "+"}).spelling == "a͜ɪ"
    assert house.respell("t͡s", {"voiced": "+"}).spelling == "d͡z"
    with pytest.raises(ValueError, match="prosodic"):
        house.respell("a", {"length": "long"})
    with pytest.raises(ValueError):
        house.respell("a", {"voiced": False})
    missing = house.respell("i", {"tongue_root": "+"})
    assert missing == CanonicalRespelling(house.identity, None)
    assert missing.status == "none"


def test_capability_protocols_and_set_geometry_are_separate(finite, house):
    geometry = FeatureSets("opaque", {"A/B #": set(), "alias": set()})
    sets = SetInventory(geometry)
    for adapter in (finite, house, sets):
        assert isinstance(adapter, SoundInventory)
    for adapter in (finite, house):
        assert isinstance(adapter, MatchingInventory)
        assert isinstance(adapter, RespellingInventory)
    assert not isinstance(sets, MatchingInventory)
    assert not isinstance(sets, RespellingInventory)
    assert sets.identity == geometry.identity
    assert sets.name == "opaque"
    assert sets.admission == "exact-finite"
    assert sets.declared_tokens == ("A/B #", "alias")
    assert sets.read("A/B #") == frozenset()
    assert sets.read("alias") == frozenset()
    with pytest.raises(OutsideDomain):
        sets.read("A/B")


@pytest.mark.parametrize("token", [None, 0, False, [], ""])
def test_invalid_token_shapes_are_refused(finite, house, token):
    sets = SetInventory(FeatureSets("x", {"a": set()}))
    for adapter in (finite, house, sets):
        with pytest.raises(ValueError, match="nonempty string"):
            adapter.read(token)
    for adapter in (finite, house):
        with pytest.raises(ValueError, match="nonempty string"):
            adapter.respell(token, {})


def test_operations_delegate_to_existing_public_methods(monkeypatch, finite, house):
    calls = []
    finite_query = FiniteModel.query
    house_query = IPAFeatures.phones_matching
    house_respell = IPAFeatures.respell

    def query(model, constraints):
        calls.append("finite-query")
        return finite_query(model, constraints)

    def phones(ipa, query, with_defaults=True):
        calls.append("house-query")
        return house_query(ipa, query, with_defaults=with_defaults)

    def respell(ipa, token, **changes):
        calls.append("house-respell")
        return house_respell(ipa, token, **changes)

    monkeypatch.setattr(FiniteModel, "query", query)
    monkeypatch.setattr(IPAFeatures, "phones_matching", phones)
    monkeypatch.setattr(IPAFeatures, "respell", respell)
    assert finite.phones_matching({"f": 0}) == ("zero", "alias")
    assert house.phones_matching({"voiced": "+"})
    assert house.respell("t", {"voiced": "+"}).spelling == "d"
    assert calls == ["finite-query", "house-query", "house-respell"]
