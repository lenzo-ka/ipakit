"""Content-keyed containment projection caching contracts."""

import random
import threading

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
    hits, misses, _evictions, size, _ = _projection_cache_info()
    assert hits >= 1
    assert misses >= 1
    assert size == 1


def test_different_content_does_not_collide(ipa: IPAFeatures) -> None:
    _projection_cache_clear()

    assert ipa.read("kæt").segments != ipa.read("dɒɡ").segments
    hits, misses, _evictions, size, _ = _projection_cache_info()
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

    hits, _misses, _evictions, _size, _ = _projection_cache_info()
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


def test_concurrent_from_input_keeps_cache_and_counters_consistent(
    ipa: IPAFeatures,
) -> None:
    """Concurrent from_input callers leave the cache and counters consistent.

    Many threads call from_input over a mix of equal and distinct forms.
    Regardless of interleaving: every call is counted exactly once
    (hits + misses == calls), the cache never exceeds its bound, and every
    returned projection equals an independent fresh rebuild.
    """
    distinct = _harvested_inputs(ipa)
    assert len(distinct) > 1  # the mix must contain repeats and variety
    # A workload with heavy repetition across threads maximizes contention on
    # the read-modify-write the lock guards.
    rng = random.Random(1234)
    workload = distinct * 12
    rng.shuffle(workload)

    thread_count = 16
    chunks: list[list[ContainmentProjectionInput]] = [[] for _ in range(thread_count)]
    for index, item in enumerate(workload):
        chunks[index % thread_count].append(item)

    _projection_cache_clear()
    barrier = threading.Barrier(thread_count)
    collected: list[tuple[ContainmentProjectionInput, ContainmentProjection]] = []
    collect_lock = threading.Lock()

    def worker(chunk: list[ContainmentProjectionInput]) -> None:
        barrier.wait()
        local = [(ci, ContainmentProjection.from_input(ci)) for ci in chunk]
        with collect_lock:
            collected.extend(local)

    threads = [threading.Thread(target=worker, args=(chunk,)) for chunk in chunks]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    hits, misses, _evictions, size, maxsize = _projection_cache_info()
    assert hits + misses == len(workload)
    assert size <= maxsize
    assert len(collected) == len(workload)
    for containment_input, projection in collected:
        assert projection == ContainmentProjection._build_from_input(
            containment_input, frozenset()
        )


def test_eviction_is_lru_capped_and_counted(
    ipa: IPAFeatures, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exceeding the bound evicts LRU-first, caps size, and counts evictions.

    Drives real eviction with a tiny bound: three distinct inputs against a
    maxsize of 2. Re-touching the first before inserting the third makes the
    second the least-recently-used entry, so it -- not the re-touched first --
    must be the one evicted.
    """
    import ipakit._containment_projection as cp

    # Distinct inputs with distinct signatures, harvested from varied reads.
    by_signature: dict[tuple[object, ...], ContainmentProjectionInput] = {}
    for text in _INVARIANT_CORPUS:
        source = ipa.read(text).__dict__["_tiergraph_index"].containment_input
        by_signature.setdefault(cp._projection_signature(source, frozenset()), source)
    distinct = list(by_signature.values())
    assert len(distinct) >= 3

    monkeypatch.setattr(cp, "_PROJECTION_CACHE_MAXSIZE", 2)
    _projection_cache_clear()
    try:
        first, second, third = distinct[0], distinct[1], distinct[2]
        ContainmentProjection.from_input(first)  # cache: [first]
        ContainmentProjection.from_input(second)  # cache: [first, second]
        ContainmentProjection.from_input(first)  # HIT, LRU touch -> [second, first]

        _hits, _misses, evictions, size, maxsize = _projection_cache_info()
        assert size == 2
        assert maxsize == 2
        assert evictions == 0

        # Inserting a third distinct entry exceeds the bound of 2.
        ContainmentProjection.from_input(third)  # evict LRU (second) -> [first, third]
        _hits, _misses, evictions, size, maxsize = _projection_cache_info()
        assert size == 2  # capped at the bound
        assert maxsize == 2
        assert evictions == 1  # exactly one entry evicted

        # LRU discipline: the re-touched `first` survived (a HIT, no rebuild);
        # the least-recently-used `second` was evicted (a MISS, rebuilt).
        hits_a, misses_a, _e, _s, _m = _projection_cache_info()
        ContainmentProjection.from_input(first)
        hits_b, misses_b, _e, _s, _m = _projection_cache_info()
        assert hits_b == hits_a + 1  # first was still cached
        assert misses_b == misses_a  # no rebuild for first

        ContainmentProjection.from_input(second)
        _h, misses_c, _e, _s, _m = _projection_cache_info()
        assert misses_c == misses_b + 1  # second had been evicted, rebuilt now
    finally:
        _projection_cache_clear()
