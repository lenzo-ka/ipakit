"""Tests for the distribution-aware DistanceModel (CDF renormalization)."""

import pytest
from ipakit import IPAFeatures
from ipakit.distance_model import DistanceModel, _load_matrix_json, _load_matrix_tsv

CORE = [
    "p",
    "b",
    "t",
    "d",
    "k",
    "ɡ",
    "s",
    "z",
    "f",
    "v",
    "m",
    "n",
    "l",
    "ɹ",
    "a",
    "i",
    "u",
]


@pytest.fixture(scope="module")
def ipa():
    return IPAFeatures()


@pytest.fixture(scope="module")
def full_inputs(ipa):
    phones = list(ipa.phones)
    return phones, ipa.pairwise_distances(phones)


@pytest.fixture(scope="module")
def full(ipa, full_inputs):
    phones, M = full_inputs
    return DistanceModel(ipa, "ipa", phones, M, "distance")


def _core_phones(ipa):
    return [p for p in CORE if p in ipa]


def _model(ipa, phones, **kw):
    return DistanceModel(
        ipa, "core", phones, ipa.pairwise_distances(phones), "distance", **kw
    )


class TestPercentile:
    def test_bounds_identity_unknown(self, ipa):
        m = _model(ipa, _core_phones(ipa))
        assert m.distance("p", "p") == 0.0
        assert m.confusability("p", "p") == 1.0
        assert 0.0 < m.distance("p", "a") <= 1.0
        assert m.distance("p", "ZZZ") == 1.0
        assert m.distance("p", "b") == pytest.approx(1.0 - m.confusability("p", "b"))

    def test_monotone_in_raw_distance(self, ipa):
        phones = _core_phones(ipa)
        m = _model(ipa, phones)
        pairs = [(a, b) for a in phones for b in phones if a < b]
        for a1, b1 in pairs:
            for a2, b2 in pairs:
                if ipa.distance(a1, b1) < ipa.distance(a2, b2):
                    assert m.distance(a1, b1) <= m.distance(a2, b2) + 1e-12

    def test_uniformized_range(self, ipa):
        phones = _core_phones(ipa)
        m = _model(ipa, phones)
        ds = [m.distance(a, b) for a in phones for b in phones if a < b]
        assert max(ds) - min(ds) > 0.8  # CDF spreads bunched raw values


class TestGamma:
    def test_gamma_pushes_dissimilar_apart(self, ipa):
        phones = _core_phones(ipa)
        base = _model(ipa, phones)
        sharp = _model(ipa, phones, gamma=2.0)
        for a, b in [("p", "k"), ("s", "f"), ("p", "a")]:
            assert sharp.distance(a, b) >= base.distance(a, b) - 1e-12  # 1-p**2 >= 1-p
        assert sharp.distance("p", "p") == base.distance("p", "p") == 0.0


class TestInventoryRelativity:
    def test_reference_changes_percentile(self, ipa):
        phones = _core_phones(ipa)
        M = ipa.pairwise_distances(phones)
        full_ref = DistanceModel(ipa, "core", phones, M, "distance")
        sub = [p for p in ["p", "b", "t", "d", "k", "ɡ"] if p in phones]
        sub_ref = DistanceModel(ipa, "sub", phones, M, "distance", ref_phones=sub)
        assert any(
            full_ref.distance(a, b) != sub_ref.distance(a, b)
            for a in sub
            for b in sub
            if a < b
        )


class TestNearest:
    def test_sorted_restricted_excludes_self(self, ipa):
        phones = _core_phones(ipa)
        m = _model(ipa, phones)
        near = m.nearest("p", n=3)
        assert len(near) == 3
        assert [d for _, d in near] == sorted(d for _, d in near)
        assert "p" not in [p for p, _ in near]
        assert all(p in phones for p, _ in near)


class TestWord:
    def test_identical_and_minimal_pair(self, full):
        assert full.word_similarity("kæt", "kæt") == 1.0
        assert full.word_similarity("kæt", "kæd") > 0.85

    def test_di_separates_more_than_simple(self, ipa, full_inputs):
        phones, M = full_inputs
        simple = DistanceModel(ipa, "ipa", phones, M, "distance", sub_mode="simple")
        di = DistanceModel(ipa, "ipa", phones, M, "distance", sub_mode="di")
        assert di.word_similarity("kæt", "dɒɡ") < simple.word_similarity("kæt", "dɒɡ")
        assert di.word_similarity("kæt", "kæd") > di.word_similarity("kæt", "dɒɡ")


class TestLengthGating:
    def test_short_circuit_and_ratio_reject(self, full):
        assert full.is_similar("kæt", "kæt", threshold=0.9) is True
        assert full.is_similar("kæt", "kætəloɡ", threshold=0.95) is False
        assert (
            full.is_similar("a", "kætəloɡ", threshold=0.5, max_length_ratio=2.0)
            is False
        )

    def test_threshold_required(self, full):
        with pytest.raises(ValueError):
            full.is_similar("kæt", "kæd")


class TestLoaders:
    def test_json_round_trip(self, tmp_path, ipa):
        import json

        phones = ["p", "b", "t"]
        M = ipa.pairwise_distances(phones)
        tri = [M[i][j] for i in range(3) for j in range(i + 1, 3)]
        p = tmp_path / "c.json"
        p.write_text(
            json.dumps(
                {
                    "version": "1.0",
                    "reference": "x",
                    "space": "distance",
                    "phones": phones,
                    "triangle": tri,
                }
            )
        )
        ph, m, sp = _load_matrix_json(p)
        assert ph == phones and sp == "distance"
        assert m[0][1] == m[1][0] == tri[0] and m[0][0] == 0.0

    def test_tsv_symmetrizes(self, tmp_path):
        p = tmp_path / "c.tsv"
        p.write_text("\tp\tb\np\t1.0\t0.9\nb\t0.0\t1.0\n")
        ph, m, sp = _load_matrix_tsv(p)
        assert sp == "similarity"
        assert m[ph.index("p")][ph.index("b")] == m[ph.index("b")][ph.index("p")] == 0.9
