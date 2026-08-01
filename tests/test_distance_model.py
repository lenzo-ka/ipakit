"""Tests for the distribution-aware DistanceModel (CDF renormalization)."""

import itertools
import json
import warnings

import ipakit
import pytest
from ipakit import IPAFeatures
from ipakit.constants import DATA_DIR, DEFAULT_CONFUSION
from ipakit.distance_model import (
    DistanceModel,
    _global_matrix,
    _load_matrix_json,
    _load_matrix_tsv,
)
from ipakit.metric import metric_fingerprint

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


class TestPhoneLevelOOVFallback:
    """Phones outside the matrix fall back to feature-derived similarity,
    matching the fallback sub_cost already applies at word level. Phones
    whose features cannot be derived keep the explicit out-of-model
    sentinels (0.0 / 1.0 / [])."""

    def test_registered_phone_outside_model_inventory(self, ipa):
        m = _model(ipa, _core_phones(ipa))  # t͡ʃ not in the core inventory
        # Structural metric: an affricate sits near segments that share its
        # phase structure, not near its bare fricative component.
        assert m.confusability("t͡ʃ", "t") >= 0.0
        assert m.distance("t͡ʃ", "s") == pytest.approx(
            1.0 - m.confusability("t͡ʃ", "s")
        )
        assert ipa.distance("t͡ʃ", "t͡s") < ipa.distance("t͡ʃ", "s")

    def test_composed_tie_sequence(self, ipa, full):
        assert "q͡χ" not in ipa.phones  # composable, not registered
        near = full.nearest("q͡χ", n=3)
        assert len(near) == 3
        # Under the structural metric an unregistered affricate's nearest
        # neighbors are other affricates (shared phase structure), not its
        # bare components.
        kinds = {ipa.segment(p).kind.value for p, _ in near}
        assert kinds <= {"affricate", "double-articulation", "prenasalized"}
        assert ipa.distance("q͡χ", "t͡ʃ") < ipa.distance("q͡χ", "χ")

    def test_both_sides_oov(self, ipa):
        m = _model(ipa, _core_phones(ipa))
        assert m.confusability("t͡ʃ", "q͡χ") > 0.0

    def test_underivable_keeps_sentinels(self, ipa):
        m = _model(ipa, _core_phones(ipa))
        assert m.confusability("p", "ZZZ") == 0.0
        assert m.distance("p", "ZZZ") == 1.0
        assert m.nearest("ZZZ") == []

    def test_oov_nearest_sorted_and_excludes_self(self, ipa):
        m = _model(ipa, _core_phones(ipa))
        near = m.nearest("t͡ʃ", n=5)
        assert len(near) == 5
        assert [d for _, d in near] == sorted(d for _, d in near)
        assert "t͡ʃ" not in [p for p, _ in near]


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
        ph, m, sp, fingerprint = _load_matrix_json(p)
        assert ph == phones and sp == "distance"
        assert fingerprint is None, "a file recording no metric records None"
        assert m[0][1] == m[1][0] == tri[0] and m[0][0] == 0.0

    def test_tsv_symmetrizes_averages_genuine_zero(self, tmp_path):
        # Both directions present: p->b=0.9, b->p=0.0. A genuine 0 is a real
        # value, so the symmetrized cell is the average (0.45), not 0.9.
        p = tmp_path / "c.tsv"
        p.write_text("\tp\tb\np\t1.0\t0.9\nb\t0.0\t1.0\n")
        ph, m, sp = _load_matrix_tsv(p)
        assert sp == "similarity"
        pb = m[ph.index("p")][ph.index("b")]
        bp = m[ph.index("b")][ph.index("p")]
        assert pb == bp == pytest.approx(0.45)


class TestPublicApi:
    def test_confusability_complements_normalized_distance(self):
        import ipakit

        assert ipakit.confusability("p", "p") == 1.0
        c = ipakit.confusability("p", "b")
        d = ipakit.normalized_distance("p", "b")
        assert c == pytest.approx(1.0 - d)
        assert "confusability" in ipakit.__all__

    def test_introspection_properties(self, ipa):
        from ipakit.models import Phoneset

        m = DistanceModel.for_phoneset(
            ipa, Phoneset.from_list(["p", "b", "t"], name="tiny")
        )
        assert m.reference_name == "tiny"
        assert set(m.reference_phones) <= {"p", "b", "t"}
        assert m.gamma == 1.0
        assert m.sub_mode == "simple"


class TestDistanceCli:
    def _run(self, monkeypatch, capsys, *argv):
        import sys

        import ipakit.cli

        monkeypatch.setattr(sys, "argv", ["ipakit", *argv])
        rc = ipakit.cli.main()
        return rc, capsys.readouterr().out

    def test_confusability_command(self, monkeypatch, capsys):
        rc, out = self._run(monkeypatch, capsys, "distance", "confusability", "p", "b")
        assert rc == 0
        assert "confusability=" in out and "reference: ipa" in out

    def test_word_command_json(self, monkeypatch, capsys):
        import json

        rc, out = self._run(monkeypatch, capsys, "distance", "word", "kæt", "kæd", "-j")
        assert rc == 0
        data = json.loads(out)
        assert data["word1"] == "kæt" and 0.0 <= data["similarity"] <= 1.0
        assert data["reference"] == "ipa"

    def test_word_threshold(self, monkeypatch, capsys):
        rc, out = self._run(
            monkeypatch, capsys, "distance", "word", "kæt", "kæd", "--threshold", "0.9"
        )
        assert rc == 0
        assert "similar=True" in out

    def test_confusability_phoneset(self, tmp_path, monkeypatch, capsys):
        pf = tmp_path / "tiny.txt"
        pf.write_text("p\nb\nt\nd\nk\n")
        rc, out = self._run(
            monkeypatch, capsys, "distance", "conf", "p", "b", "--phoneset", str(pf)
        )
        assert rc == 0
        assert "reference: tiny" in out


class TestFeatureSpaceFingerprint:
    """A saved matrix says which feature space its numbers mean something in.

    ``phones`` says which inventory the rows are, and a bridge or a
    changed feature declaration leaves it byte-identical while moving up
    to 98% of the distances underneath it. So a perturbed inventory could
    read the shipped matrix and answer -- 0.9982 where its own derived
    matrix says 0.9447, with nothing to tell the two apart.
    """

    BRIDGE = """
    <bridge name="posteriority">
      <spelling feature="retroflex" value="+"/>
      <spelling feature="place" value="postalveolar"/>
    </bridge>
  </bridges>"""

    @pytest.fixture
    def bridged(self, tmp_path):
        """The shipped inventory plus one bridge: same phones, other space."""
        text = (DATA_DIR / "ipa.xml").read_text(encoding="utf-8")
        assert text.count("\n  </bridges>") == 1, "the data moved; fix this test"
        path = tmp_path / "ipa.xml"
        path.write_text(text.replace("\n  </bridges>", self.BRIDGE), encoding="utf-8")
        return IPAFeatures(xml_path=path)

    def test_save_records_it(self, tmp_path, ipa):
        model = DistanceModel.derive(ipa, phones=["p", "b", "t"])
        saved = json.loads(model.save(tmp_path / "c.json").read_text(encoding="utf-8"))
        assert saved["metric"] == metric_fingerprint(ipa, saved["phones"])

    def test_round_trip(self, tmp_path, ipa):
        model = DistanceModel.derive(ipa, phones=_core_phones(ipa))
        reloaded = DistanceModel.from_matrix_file(ipa, model.save(tmp_path / "c.json"))
        assert reloaded.reference_phones == model.reference_phones
        for a, b in itertools.combinations(model.reference_phones, 2):
            assert reloaded.confusability(a, b) == model.confusability(a, b)

    def test_a_supplemented_inventory_round_trips(self, tmp_path):
        # The direction the fingerprint must not break: a supplement adds
        # phones and declares nothing, so its own derived matrix reads back
        # and the shipped one stays readable too.
        inventory = IPAFeatures(supplements=["aspirated-stops"])
        model = DistanceModel.derive(inventory, phones=["p", "t", "tʰ", "s"])
        saved = model.save(tmp_path / "c.json")
        assert DistanceModel.from_matrix_file(inventory, saved).reference_phones == [
            "p",
            "t",
            "tʰ",
            "s",
        ]
        DistanceModel.from_matrix_file(inventory, DEFAULT_CONFUSION)

    def test_a_disagreeing_fingerprint_is_refused(self, tmp_path, ipa, bridged):
        # The hole itself: same phones in the same order, different space.
        saved = DistanceModel.derive(ipa, phones=_core_phones(ipa)).save(
            tmp_path / "c.json"
        )
        with pytest.raises(ValueError, match="different feature space"):
            DistanceModel.from_matrix_file(bridged, saved)

    def test_the_shipped_matrix_is_refused_a_perturbed_inventory(self, bridged):
        with pytest.raises(ValueError, match="different feature space"):
            DistanceModel.from_matrix_file(bridged, DEFAULT_CONFUSION)

    def test_the_refusal_names_the_fix(self, bridged):
        with pytest.raises(ValueError) as caught:
            DistanceModel.from_matrix_file(bridged, DEFAULT_CONFUSION)
        message = str(caught.value)
        # Whoever hits this has usually edited the inventory and not
        # regenerated, so the message has to carry the command.
        assert "confusion.py generate --write" in message
        assert "DistanceModel.derive(ipa).save(path)" in message
        assert DEFAULT_CONFUSION.name in message and "ipa.xml" in message

    def test_a_matrix_with_no_fingerprint_loads_silently(self, tmp_path, ipa, bridged):
        # A hand-written or externally derived matrix records no metric and
        # has nothing to agree with. Refusing it would refuse the
        # mechanism's main external use.
        model = DistanceModel.derive(ipa, phones=["p", "b", "t"])
        path = model.save(tmp_path / "c.json")
        stripped = json.loads(path.read_text(encoding="utf-8"))
        del stripped["metric"]
        path.write_text(json.dumps(stripped), encoding="utf-8")
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert DistanceModel.from_matrix_file(bridged, path).reference_phones == [
                "p",
                "b",
                "t",
            ]

    def test_a_tsv_grid_is_never_checked(self, tmp_path, bridged):
        path = tmp_path / "c.tsv"
        path.write_text("\tp\tb\np\t1.0\t0.9\nb\t0.9\t1.0\n", encoding="utf-8")
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert DistanceModel.from_matrix_file(bridged, path).reference_phones == [
                "p",
                "b",
            ]


class TestTheShippedMatrixIsCheckedWhereItIsRead:
    """The acceptance case, over the public entry points.

    ``data/confusion.json`` is read by ``global_`` -- which
    ``ipakit.distance_model()`` and ``ipakit.confusability`` build on --
    and by ``for_phoneset``, which re-slices the same values without
    coming through ``global_``. Someone who edits an installed
    ``ipa.xml`` and does not regenerate reaches the shipped matrix by
    those paths and not by ``from_matrix_file``, so a check that only
    covered the loader would be a check on a path nobody takes.
    """

    @pytest.fixture
    def bridged(self, tmp_path):
        text = (DATA_DIR / "ipa.xml").read_text(encoding="utf-8")
        assert text.count("\n  </bridges>") == 1, "the data moved; fix this test"
        path = tmp_path / "ipa.xml"
        path.write_text(
            text.replace(
                "\n  </bridges>",
                '\n    <bridge name="posteriority">'
                '<spelling feature="retroflex" value="+"/>'
                '<spelling feature="place" value="postalveolar"/>'
                "</bridge>\n  </bridges>",
            ),
            encoding="utf-8",
        )
        return IPAFeatures(xml_path=path)

    @pytest.fixture
    def as_the_module_inventory(self, monkeypatch, bridged):
        """As if the ipa.xml this install ships had been edited in place."""
        monkeypatch.setattr(ipakit, "_get_ipa", lambda: bridged)
        ipakit._get_default_model.cache_clear()
        yield bridged
        ipakit._get_default_model.cache_clear()

    def test_the_refusal_stands_between_two_real_answers(self, bridged):
        # Not hypothetical, and the reason a warning is not enough: both
        # numbers are perfectly reasonable confusabilities for /s/ and
        # /ʃ/, and nothing about the wrong one looks wrong. The bare
        # constructor is the deliberate escape -- it takes a matrix as an
        # argument and makes no claim about where it came from.
        phones, m, space, _ = _global_matrix()
        shipped = DistanceModel(bridged, "ipa", phones, m, space)
        own = DistanceModel.derive(bridged)
        assert shipped.confusability("s", "ʃ") != own.confusability("s", "ʃ")

    def test_distance_model_refuses(self, as_the_module_inventory):
        with pytest.raises(ValueError, match="different feature space"):
            ipakit.distance_model()

    def test_confusability_refuses(self, as_the_module_inventory):
        with pytest.raises(ValueError, match="different feature space"):
            ipakit.confusability("s", "ʃ")

    def test_a_phoneset_reference_refuses(self, as_the_module_inventory):
        # for_phoneset re-slices the shipped values and does not come
        # through global_, so the check has to reach it separately.
        with pytest.raises(ValueError, match="different feature space"):
            ipakit.distance_model(reference=["p", "t", "k", "s", "a"])

    def test_global_refuses_directly(self, bridged):
        with pytest.raises(ValueError, match="different feature space"):
            DistanceModel.global_(bridged)

    def test_for_phoneset_refuses_directly(self, bridged):
        from ipakit.models import Phoneset

        with pytest.raises(ValueError, match="different feature space"):
            DistanceModel.for_phoneset(bridged, Phoneset.from_list(["p", "t", "a"]))

    def test_the_shipped_inventory_still_reads_it(self, ipa):
        # Guard the guard: if the check refused the inventory the matrix
        # was derived from, every test above would pass for the wrong
        # reason and the library would not start.
        assert DistanceModel.global_(ipa).reference_phones == list(ipa.phones)

    def test_a_supplemented_inventory_still_reads_it(self):
        # The direction that must survive the check reaching global_: a
        # supplement declares nothing, so the shipped matrix is still the
        # right matrix for the phones it holds.
        inventory = IPAFeatures(supplements=["aspirated-stops"])
        assert DistanceModel.global_(inventory).reference_phones == list(
            IPAFeatures().phones
        )
