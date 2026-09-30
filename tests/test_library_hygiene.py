"""Predicates over public library readers that may accept lossy input.

The CLI has its own parser-tree sweep. This gate covers flat top-level functions
plus the five enumerated ``CMUMapper`` and ``IPAFeatures`` methods below. Every
declared soft reader receives a literal input containing one symbol that none of
the supported notations registers.
"""

from __future__ import annotations

import inspect
import warnings
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import ipakit
import ipakit.clts
import ipakit.corpus
import ipakit.textgrid
import pytest
from ipakit._warning_policy import input_reports

PROBE_SYMBOL = "§"
PROBE = f"c{PROBE_SYMBOL}t"

# These strict readers live on the opt-in ``ipakit.clts`` surface rather than
# in ``ipakit.__all__``. Exact equality makes every future reader declare and
# exercise its refusal behavior here.
PUBLIC_IMPORT_READERS = {"import_tokens", "import_document", "load_import"}
PUBLIC_CLTS_OPERATIONS = PUBLIC_IMPORT_READERS | {"emit_tokens"}


# Every function exported by ``ipakit.__all__`` is classified literally.  The
# non-reader side matters as much as the reader side: deriving it by subtraction
# would let a new public reader pass merely because nobody declared it.
SOFT_READERS = {
    "derive",
    "describe",
    "directional_transcription_distance",
    "distance",
    "distance_model",
    "distance_position",
    "explain_transcription_distance",
    "feature_bundles",
    "feature_values",
    "features",
    "features_from_cmu",
    "features_from_xsampa",
    "find",
    "from_cmu",
    "from_kirshenbaum",
    "from_phonemap",
    "from_timit",
    "from_xsampa",
    "hierarchy",
    "hierarchy_dot",
    "hierarchy_text",
    "inventory_from_dictionary",
    "minimal_pairs",
    "natural_class",
    "nearest_phones",
    "nearest_pronunciation",
    "pairwise_distances",
    "phoneset_comparison",
    "phoneset_mapping",
    "rank_pronunciations",
    "rank_sequences",
    "read",
    "respell",
    "rewrite",
    "segment",
    "segment_distance",
    "segmented",
    "segments",
    "sequence_distance",
    "sequence_similarity",
    "similarity_position",
    "syllabify",
    "to_cmu",
    "to_kirshenbaum",
    "to_phonemap",
    "to_timit",
    "to_xsampa",
    "tokenize",
    "transcription_distance",
    "transcription_similarity",
    "units",
    "variants",
}

NON_SOFT_PUBLIC_FUNCTIONS = {
    "add_ties",
    "available",
    "available_supplements",
    "extensions_in",
    "features_to_shorts",
    "from_wild",
    "import_phoneset",
    "inventories",
    "inventory",
    "is_pure_ipa",
    "is_valid_ipa",
    "language",
    "languages",
    "levels",
    "load_ipa_features",
    "morae",
    "normalize",
    "normalize_lookalikes",
    "notebook",
    "parse_query",
    "phones_matching",
    "read_graph_json",
    "read_json",
    "rebase",
    "rule",
    "ruleset",
    "shipped",
    "shorts_to_features",
    "stress_markers",
    "supplement_path",
    "syllabifier",
    "tier_names",
    "to_dot",
    "to_ipa",
    "to_katakana",
    "to_phone",
    "validate_ipa",
    "wiki",
    "wiki_ref",
    "wiki_refs",
    "write_graph_json",
}


def _public_functions() -> set[str]:
    return {
        name
        for name in ipakit.__all__
        if inspect.isfunction(getattr(ipakit, name, None))
    }


def test_every_flat_public_function_is_classified() -> None:
    declared = SOFT_READERS | NON_SOFT_PUBLIC_FUNCTIONS
    public = _public_functions()
    assert SOFT_READERS.isdisjoint(NON_SOFT_PUBLIC_FUNCTIONS)
    assert declared == public, (
        f"unclassified public functions: {sorted(public - declared)}; "
        f"declared names absent from the public surface: {sorted(declared - public)}"
    )


def _public_clts_operations() -> set[str]:
    return {
        name
        for name, function in inspect.getmembers(ipakit.clts, inspect.isfunction)
        if not name.startswith("_") and function.__module__ == "ipakit._clts_import"
    }


def test_every_public_clts_import_reader_is_classified() -> None:
    assert _public_clts_operations() == PUBLIC_CLTS_OPERATIONS


@pytest.fixture
def clear_import_cache():
    from ipakit import _clts_import

    _clts_import._cache_clear()
    yield
    _clts_import._cache_clear()


@pytest.mark.usefixtures("clear_import_cache")
@pytest.mark.parametrize("name", sorted(PUBLIC_CLTS_OPERATIONS))
def test_public_clts_operation_refuses_or_reports_loss(name: str) -> None:
    reader = getattr(ipakit.clts, name)
    if name == "emit_tokens":
        held = ipakit.clts.import_tokens(["t͜s"], unsupported="preserve")
        result = reader(held, spelling="bipa")
        assert result.status == "refused"
        assert result.to_data()["error"]["code"] == "loss-not-authorized"
        assert result.report()["losses"][0]["claim"] == "sequential-juncture"
        return
    with pytest.raises(ipakit.clts.CLTSInputError) as caught:
        reader("unsegmented")
    assert caught.value.code == (
        "invalid-envelope" if name == "load_import" else "segmentation-required"
    )
    if name == "import_tokens":
        value = ["a"]
    else:
        value = {
            "format": "ipakit-clts-input",
            "version": 1,
            "tokens": [{"raw": "a"}],
        }
    if name == "load_import":
        value = ipakit.clts.import_document(value).to_data()
    result = reader(value)
    assert result.status == "refused"
    assert result.report()["diagnostics"] == [
        {
            "action": "refused",
            "code": "outside-reviewed-token-context",
            "stage": "house-projection",
            "token": 0,
        }
    ]


def test_fault_injection_new_clts_import_reader_is_named(monkeypatch) -> None:
    def import_extra(value):
        return value

    import_extra.__module__ = "ipakit._clts_import"
    monkeypatch.setattr(ipakit.clts, "import_extra", import_extra, raising=False)
    assert _public_clts_operations() - PUBLIC_CLTS_OPERATIONS == {"import_extra"}


def test_input_loss_warning_is_a_public_contract() -> None:
    assert "InputLossWarning" in ipakit.__all__
    assert issubclass(ipakit.InputLossWarning, UserWarning)


def test_loss_classifier_is_library_visible_without_the_cli() -> None:
    assert input_reports.__module__ == "ipakit._warning_policy"


@dataclass(frozen=True)
class Probe:
    surface: str
    invoke: Callable[[Path], object]
    expected: Literal["warns", "refuses"]


def _dictionary_probe(tmp_path: Path) -> object:
    source = tmp_path / "probe.dict"
    source.write_text("WORD c § t\n", encoding="utf-8")
    return ipakit.inventory_from_dictionary(source, "ipa")


PROBES = (
    Probe("read", lambda _: ipakit.read(PROBE), "warns"),
    # The wild path rewrites the ASCII stand-in first and must still report
    # the genuinely unreadable symbol that follows it.
    Probe("read", lambda _: ipakit.read("g§", wild=True), "warns"),
    Probe("tokenize", lambda _: ipakit.tokenize(PROBE), "warns"),
    Probe("segmented", lambda _: ipakit.segmented(PROBE), "warns"),
    Probe("segments", lambda _: ipakit.segments(PROBE), "warns"),
    Probe("segment", lambda _: ipakit.segment("c§"), "warns"),
    Probe("units", lambda _: ipakit.units(PROBE), "warns"),
    Probe("features", lambda _: ipakit.features("c§"), "warns"),
    Probe("feature_values", lambda _: ipakit.feature_values("c§"), "warns"),
    Probe("feature_bundles", lambda _: ipakit.feature_bundles(PROBE), "warns"),
    Probe("find", lambda _: ipakit.find(PROBE, ["vowel"]), "warns"),
    Probe("describe", lambda _: ipakit.describe("c§"), "warns"),
    Probe("distance", lambda _: ipakit.distance("c§", "t"), "warns"),
    Probe(
        "segment_distance",
        lambda _: ipakit.segment_distance(PROBE, "ct"),
        "warns",
    ),
    Probe(
        "pairwise_distances",
        lambda _: ipakit.pairwise_distances(["c§", "t"]),
        "warns",
    ),
    Probe(
        "distance_model",
        lambda _: ipakit.distance_model(["c§", "p", "t", "k"]),
        "warns",
    ),
    Probe(
        "distance_position",
        lambda _: ipakit.distance_position("c§", "t"),
        "warns",
    ),
    Probe(
        "similarity_position",
        lambda _: ipakit.similarity_position("c§", "t"),
        "warns",
    ),
    Probe("hierarchy", lambda _: ipakit.hierarchy(["c§", "t"]), "warns"),
    Probe("hierarchy_text", lambda _: ipakit.hierarchy_text(["c§", "t"]), "warns"),
    Probe("hierarchy_dot", lambda _: ipakit.hierarchy_dot(["c§", "t"]), "warns"),
    Probe("minimal_pairs", lambda _: ipakit.minimal_pairs("c§"), "warns"),
    Probe("natural_class", lambda _: ipakit.natural_class(["c§", "t"]), "refuses"),
    Probe("nearest_phones", lambda _: ipakit.nearest_phones("c§"), "refuses"),
    Probe("respell", lambda _: ipakit.respell("c§", voiced="+"), "refuses"),
    Probe(
        "transcription_distance",
        lambda _: ipakit.transcription_distance(PROBE, "ct", strict=False),
        "warns",
    ),
    Probe(
        "directional_transcription_distance",
        lambda _: ipakit.directional_transcription_distance(PROBE, "ct", strict=False),
        "warns",
    ),
    Probe(
        "transcription_similarity",
        lambda _: ipakit.transcription_similarity(PROBE, "ct", strict=False),
        "warns",
    ),
    Probe(
        "explain_transcription_distance",
        lambda _: ipakit.explain_transcription_distance(PROBE, "ct", strict=False),
        "warns",
    ),
    Probe(
        "nearest_pronunciation",
        lambda _: ipakit.nearest_pronunciation(PROBE, ["ct"], strict=False),
        "warns",
    ),
    Probe(
        "rank_pronunciations",
        lambda _: ipakit.rank_pronunciations(PROBE, ["ct"], strict=False),
        "warns",
    ),
    Probe(
        "sequence_distance",
        lambda _: ipakit.sequence_distance(["c§", "t"], ["c", "t"]),
        "warns",
    ),
    Probe(
        "sequence_similarity",
        lambda _: ipakit.sequence_similarity(["c§", "t"], ["c", "t"]),
        "warns",
    ),
    Probe(
        "rank_sequences",
        lambda _: ipakit.rank_sequences(["c§", "t"], [["c", "t"]]),
        "warns",
    ),
    Probe("to_cmu", lambda _: ipakit.to_cmu("k§t"), "warns"),
    Probe("from_cmu", lambda _: ipakit.from_cmu(["K", "§", "T"]), "warns"),
    Probe(
        "features_from_cmu",
        lambda _: ipakit.features_from_cmu(["K", "§", "T"]),
        "warns",
    ),
    Probe("to_xsampa", lambda _: ipakit.to_xsampa("k§t"), "warns"),
    Probe("from_xsampa", lambda _: ipakit.from_xsampa("k§t"), "warns"),
    Probe(
        "features_from_xsampa",
        lambda _: ipakit.features_from_xsampa("k§t"),
        "warns",
    ),
    Probe("to_kirshenbaum", lambda _: ipakit.to_kirshenbaum("k§t"), "warns"),
    Probe("from_kirshenbaum", lambda _: ipakit.from_kirshenbaum("k§t"), "warns"),
    Probe("to_timit", lambda _: ipakit.to_timit("k§t"), "warns"),
    Probe("from_timit", lambda _: ipakit.from_timit(["k", "§", "t"]), "warns"),
    Probe("to_phonemap", lambda _: ipakit.to_phonemap("k§t", "timit"), "warns"),
    Probe(
        "from_phonemap",
        lambda _: ipakit.from_phonemap(["k", "§", "t"], "timit"),
        "warns",
    ),
    Probe(
        "phoneset_mapping",
        lambda _: ipakit.phoneset_mapping(["c§"], ["c"]),
        "warns",
    ),
    Probe(
        "phoneset_comparison",
        lambda _: ipakit.phoneset_comparison(["c§"], ["c"]),
        "refuses",
    ),
    Probe("inventory_from_dictionary", _dictionary_probe, "refuses"),
    Probe("rewrite", lambda _: ipakit.rewrite(PROBE, "c -> t"), "warns"),
    Probe("derive", lambda _: ipakit.derive(PROBE, "c -> t"), "warns"),
    Probe("variants", lambda _: ipakit.variants(PROBE, "c -> t"), "warns"),
    Probe("syllabify", lambda _: ipakit.syllabify("c§at", "english"), "warns"),
)


def test_every_declared_soft_reader_has_a_probe() -> None:
    probed = {probe.surface for probe in PROBES}
    assert probed == SOFT_READERS, (
        f"soft readers without probes: {sorted(SOFT_READERS - probed)}; "
        f"probes without declarations: {sorted(probed - SOFT_READERS)}"
    )


@pytest.mark.parametrize("probe", PROBES, ids=lambda probe: probe.surface)
def test_public_soft_reader_warns_or_refuses(probe: Probe, tmp_path: Path) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            probe.invoke(tmp_path)
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            assert PROBE_SYMBOL in str(error), (
                f"{probe.surface} refused for a reason that does not name the probe: "
                f"{error}"
            )
            result = "refuses"
        else:
            reports = input_reports(caught)
            assert all(PROBE_SYMBOL in report for report in reports)
            result = "warns" if reports else "SILENT"
    assert result == probe.expected, f"{probe.surface}: {result}"


def test_classifier_ignores_an_unrelated_package_warning_beside_loss() -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        ipakit.tokenize(PROBE)
        warnings.warn_explicit(
            "unrelated package warning",
            UserWarning,
            "/site-packages/unrelated/__init__.py",
            1,
        )
    reports = input_reports(caught)
    assert len(reports) == 1
    assert PROBE_SYMBOL in reports[0]


@pytest.mark.parametrize(
    "surface, invoke",
    (
        ("CMUMapper.ipa_to_cmu", lambda: ipakit.CMUMapper().ipa_to_cmu("k§t")),
        (
            "CMUMapper.cmu_to_ipa",
            lambda: ipakit.CMUMapper().cmu_to_ipa(["K", "§", "T"]),
        ),
        ("IPAFeatures.get_features", lambda: ipakit.IPAFeatures().get_features("c§")),
        ("IPAFeatures.to_xsampa", lambda: ipakit.IPAFeatures().to_xsampa("k§t")),
        (
            "IPAFeatures.from_xsampa",
            lambda: ipakit.IPAFeatures().from_xsampa("k§t"),
        ),
    ),
)
def test_exported_reader_class_surfaces_report_loss(
    surface: str, invoke: Callable[[], object]
) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        invoke()
    reports = input_reports(caught)
    assert reports and all(PROBE_SYMBOL in report for report in reports), surface


def test_documented_textgrid_reader_refuses_an_unreadable_label() -> None:
    document = ipakit.textgrid.write(ipakit.read("c", strict=True), "segments")
    document = document.replace('text = "c"', 'text = "c§"', 1)
    with pytest.raises(ValueError, match="c§.*unreadable"):
        ipakit.textgrid.read(document, profile="segments")


def test_documented_cmudict_reader_retains_an_unreadable_line_as_a_refusal(
    tmp_path: Path,
) -> None:
    corpus = ipakit.corpus.create(tmp_path / "corpus")
    source = tmp_path / "probe.dict"
    source.write_text("WORD K § T\n", encoding="utf-8")
    report = ipakit.corpus.ingest_cmudict(corpus, source)
    assert report.added == 0
    assert len(report.refusals) == 1
    assert PROBE_SYMBOL in report.refusals[0].line
    assert PROBE_SYMBOL in report.refusals[0].reason
