"""Content-keyed containment projection caching contracts."""

import pytest
from ipakit import IPAFeatures
from ipakit._containment_projection import (
    ContainmentProjection,
    ContainmentProjectionInput,
    _projection_cache_clear,
    _projection_cache_info,
)
from ipakit._graph_facts import Declarations


def test_equal_forms_share_projection_without_sharing_form(ipa: IPAFeatures) -> None:
    _projection_cache_clear()
    first = ipa.read("kæt")
    second = ipa.read("kæt")

    assert first is not second
    assert first.segments == second.segments
    assert first.units == second.units
    hits, misses, size, _ = _projection_cache_info()
    assert hits >= 1
    assert misses >= 1
    assert size == 1


def test_different_content_does_not_collide(ipa: IPAFeatures) -> None:
    _projection_cache_clear()

    assert ipa.read("kæt").segments != ipa.read("dɒɡ").segments
    hits, misses, size, _ = _projection_cache_info()
    assert hits == 0
    assert misses == 2
    assert size == 2


def test_unreferenced_event_tier_does_not_collide() -> None:
    _projection_cache_clear()
    declarations = Declarations((), (), ())
    first_input = ContainmentProjectionInput((), declarations, (), {}, {}, {}, (), ())
    second_input = ContainmentProjectionInput(
        (), declarations, (), {"unreferenced": "extra"}, {}, {}, (), ()
    )

    first = ContainmentProjection.from_input(first_input)
    second = ContainmentProjection.from_input(second_input)

    assert first.event_tiers == {}
    assert second.event_tiers == {"unreferenced": "extra"}
    assert second is not first


def test_read_diagnostics_are_never_cached(ipa: IPAFeatures) -> None:
    for _ in range(2):
        with pytest.warns(UserWarning):
            ipa.read("k4t")
        with pytest.raises(ValueError):
            ipa.read("k4t", strict=True)


# A diverse read corpus: single segments, clusters, stress, boundaries, word
# and syllable separators, and multi-word forms. Together they exercise every
# _event_payload branch a string read produces and a spread of declarations,
# relations, roots, and clock shapes.
_INVARIANT_CORPUS = (
    "kæt",
    "dɒɡ",
    "ˈkæt",
    "kæt#dɒɡ",
    "aɪ",
    "hello",
    "ˈɪnpʊt",
    "an",
    "ap",
    "amp",
    "aat",
    "a i",
    "a#.b",
    "kæʔ",
    "kat dɒɡ",
    "pat",
    "tap",
    "sɪŋ",
    "θɪn",
    "ðɪs",
    "wɪʃ",
    "aːa",
    "ˌmɪs",
)


def _harvested_inputs(ipa: IPAFeatures) -> list[ContainmentProjectionInput]:
    inputs: list[ContainmentProjectionInput] = []
    for text in _INVARIANT_CORPUS:
        for strict in (False, True):
            try:
                form = ipa.read(text, strict=strict)
            except ValueError:
                continue
            # Resolve lazy unit views so both the pending and resolved payload
            # states are represented among the harvested inputs.
            for unit in form.units:
                _ = unit.features
            inputs.append(form.__dict__["_tiergraph_index"].containment_input)
    return inputs


def test_cache_hit_matches_fresh_rebuild(ipa: IPAFeatures) -> None:
    """A cache HIT must return a projection identical to a fresh rebuild.

    This is the projection cache's core safety invariant. It holds only when
    the signature fully determines the built projection -- so two distinct
    inputs never share one entry -- and nothing mutates a cached entry in
    place. It generalizes the single ``event_tiers`` collision guard below to
    any projection field a future change forgets to fold into the signature,
    and to any consumer that mutates a shared projection.
    """
    inputs = _harvested_inputs(ipa)

    # Two inputs that differ only in an unreferenced event tier must not share
    # a cached projection; the signature has to carry the whole event_tiers
    # map, not merely the entries named by ``refs``.
    declarations = Declarations((), (), ())
    inputs.append(ContainmentProjectionInput((), declarations, (), {}, {}, {}, (), ()))
    inputs.append(
        ContainmentProjectionInput(
            (), declarations, (), {"unreferenced": "extra"}, {}, {}, (), ()
        )
    )

    _projection_cache_clear()
    # First pass primes the cache (misses); the second forces hits. Every
    # returned projection -- hit or miss -- must equal an independent rebuild.
    for containment_input in inputs + inputs:
        cached = ContainmentProjection.from_input(containment_input)
        fresh = ContainmentProjection._build_from_input(containment_input, frozenset())
        assert cached == fresh

    hits, _misses, _size, _ = _projection_cache_info()
    assert hits > 0  # the corpus must actually exercise cache hits


def test_cached_projection_mapping_fields_are_read_only(ipa: IPAFeatures) -> None:
    """Every mapping field of a shared projection is read-only.

    The cache hands the same ``ContainmentProjection`` to every reader whose
    input shares a signature, so a writable mapping would let one reader poison
    all the others. ``MappingProxyType`` makes each field reject mutation.
    """
    _projection_cache_clear()
    containment = ipa.read("kæt")._containment
    for field in (
        "old_to_new",
        "new_to_old",
        "tier_names",
        "containment_names",
        "relation_names",
        "parent_order",
        "event_tiers",
        "admitted_sources",
        "admitted_targets",
        "active_by_parent",
    ):
        mapping = getattr(containment, field)
        with pytest.raises(TypeError):
            mapping["\x00poison"] = None  # type: ignore[index]
