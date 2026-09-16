"""Scalar warnings name omissions and a retaining read when one exists."""

from __future__ import annotations

import ast
import importlib.util
import sys
import warnings
from pathlib import Path

import ipakit
import ipakit.cli
import pytest
from ipakit import FeatureNarrowingWarning, IPAFeatures
from ipakit.segment import Sense, modifier_mode


def _one_warning(call, text: str) -> str:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        call()
    narrowed = [w for w in caught if w.category is FeatureNarrowingWarning]
    assert len(narrowed) == 1, (text, caught)
    message = str(narrowed[0].message)
    assert repr(text) in message
    return message


POINTER_CASES = [
    pytest.param(
        "u͜i",
        "sequential constituent(s) ['i']",
        "feature_values()",
        "feature",
        ("backness", "front"),
        id="distinct sequential value",
    ),
    pytest.param(
        "aː",
        "prosodic mark(s) ['ː']",
        "feature_values()",
        "feature",
        ("length", "long"),
        id="unit prosody",
    ),
    pytest.param(
        "a͜a",
        "sequential constituent(s) ['a']",
        "segments()",
        "constituents",
        ["a", "a"],
        id="repeated spelling",
    ),
    pytest.param(
        "b̥͜p̥",
        "sequential constituent(s) ['p̥']",
        "segments()",
        "constituents",
        ["b̥", "p̥"],
        id="distinct equal-bundle constituents",
    ),
    pytest.param(
        "p͜d͜t",
        "sequential constituent(s) ['d', 't']",
        "segments()",
        "constituents",
        ["p", "d", "t"],
        id="constituent covered across other bundles",
    ),
    pytest.param(
        "a͜p͜b",
        "sequential constituent(s) ['p', 'b']",
        "segments()",
        "constituents",
        ["a", "p", "b"],
        id="inventory-found covered constituent",
    ),
    pytest.param(
        "aː̆",
        "prosodic mark(s) ['ː', '̆']",
        "segments()",
        "prosody",
        ("ː", "̆"),
        id="contradictory prosody",
    ),
    pytest.param(
        "a̺̻",
        "diacritic mark(s) ['̻']",
        "segments()",
        "modifiers",
        ("̺", "̻"),
        id="contradictory constituent marks",
    ),
    pytest.param(
        "a a",
        "multiple units ['a', 'a']",
        "segments()",
        "units",
        ["a", "a"],
        id="multiple units",
    ),
    pytest.param(
        "ː",
        "prosodic mark(s) ['ː']",
        "read()",
        "form",
        "ː",
        id="standalone registered prosodic mark",
    ),
    pytest.param(
        "a|",
        "structural mark(s) ['|']",
        "read()",
        "form",
        "a|",
        id="form boundary",
    ),
    pytest.param(
        "̃a",
        "unplaced diacritic mark(s) ['̃']",
        "read()",
        "form",
        "̃a",
        id="unplaced registered mark",
    ),
    pytest.param(
        "∅",
        "non-segmental symbol(s) ['∅']",
        "read()",
        "form",
        "∅",
        id="registered zero",
    ),
    pytest.param(
        "g",
        "unregistered symbol(s) ['g']",
        "read(from_wild(...), strict=True)",
        "wild-form",
        "ɡ",
        id="recoverable wild spelling",
    ),
]


def _assert_pointer_retains(
    ipa: IPAFeatures,
    text: str,
    omission: str,
    reader: str,
    witness: str,
    expected: object,
) -> None:
    """Couple warning advice to executing the exact reader it names."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        assert (omission, reader) in ipa._feature_omissions(text)
    message = _one_warning(lambda: ipa.get_features(text), text)
    assert f"use {reader} for {omission}" in message

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if reader == "feature_values()":
            key, value = expected
            assert value in ipa.feature_values(text)[key]
        elif reader == "segments()":
            segments = ipa.segments(text)
            if witness == "constituents":
                assert [str(part) for part in segments[0].constituents] == expected
            elif witness == "prosody":
                assert segments[0].prosody == expected
            elif witness == "modifiers":
                assert segments[0].constituents[0].modifiers == expected
            elif witness == "units":
                assert [segment.to_ipa() for segment in segments] == expected
            else:  # pragma: no cover - guarded by the table above
                raise AssertionError(f"unknown segments() witness {witness!r}")
        elif reader == "read()":
            assert ipa.read(text).to_ipa() == expected
        elif reader == "read(from_wild(...), strict=True)":
            converted = ipa.from_wild(text)
            assert converted == expected
            assert ipa.read(converted, strict=True).to_ipa() == expected
        else:  # pragma: no cover - a newly advertised reader needs an executor
            raise AssertionError(f"no test executor for warning reader {reader!r}")


@pytest.mark.parametrize(
    ("text", "omission", "reader", "witness", "expected"), POINTER_CASES
)
def test_every_pointer_executes_and_retains_its_named_omission(
    ipa: IPAFeatures,
    text: str,
    omission: str,
    reader: str,
    witness: str,
    expected: object,
) -> None:
    _assert_pointer_retains(ipa, text, omission, reader, witness, expected)


class TestNarrowingByConstruction:
    def test_every_sequential_phone_names_the_constituents_after_the_cut(
        self, ipa: IPAFeatures
    ) -> None:
        checked = 0
        for symbol in ipa.phones:
            segment = ipa.segment(symbol)
            if Sense.SEQ not in segment.junctures:
                continue
            cut = list(segment.junctures).index(Sense.SEQ) + 1
            dropped = [str(c) for c in segment.constituents[cut:]]
            message = _one_warning(
                lambda symbol=symbol: ipa.get_features(symbol), symbol
            )
            assert "sequential constituent" in message
            assert all(repr(part) in message for part in dropped)
            checked += 1
        assert checked >= 8, "the sequential inventory sweep was vacuous"

    def test_every_prosodic_mark_warns_and_is_kept_by_feature_values(
        self, ipa: IPAFeatures
    ) -> None:
        marks = [
            mark for mark in ipa.diacritics if modifier_mode(ipa, mark) == "prosodic"
        ]
        for mark in marks:
            text = mark + "a" if mark in ipa.stress_markers else "a" + mark
            message = _one_warning(lambda text=text: ipa.get_features(text), text)
            assert "prosodic mark" in message
            asserted = {
                key: value
                for key in ipa.diacritics[mark].features
                for value in (ipa.diacritics[mark].features[key],)
                if key in ipa.features_by_mode["prosodic"]
            }
            values = ipa.feature_values(text)
            assert all(values[key] == (value,) for key, value in asserted.items())
        assert len(marks) >= 20, "the prosodic-mark sweep was vacuous"

    @pytest.mark.parametrize(
        ("text", "phrase"),
        [
            ("^a", "structural mark"),
            ("a|", "structural mark"),
            ("a͡", "structural mark"),
            ("̃a", "unplaced diacritic"),
            ("qX", "unregistered symbol"),
            ("a̺̻", "diacritic mark"),
            ("a a", "multiple units"),
            ("∅", "non-segmental symbol"),
        ],
    )
    def test_other_unrepresented_material_is_named(
        self, ipa: IPAFeatures, text: str, phrase: str
    ) -> None:
        assert phrase in _one_warning(lambda: ipa.get_features(text), text)

    def test_all_losses_in_one_call_make_one_warning(self, ipa: IPAFeatures) -> None:
        text = "ˈa͜ɪ|"
        message = _one_warning(lambda: ipa.get_features(text), text)
        assert "prosodic mark" in message
        assert "sequential constituent" in message
        assert "structural mark" in message

    def test_repeated_constituent_points_to_the_structured_read(
        self, ipa: IPAFeatures
    ) -> None:
        text = "a͜a"
        message = _one_warning(lambda: ipa.get_features(text), text)
        assert "segments()" in message
        (unit,) = ipa.segments(text, strict=True)
        assert [str(part) for part in unit.constituents] == ["a", "a"]

    def test_distinct_equal_bundle_constituents_point_to_the_structured_read(
        self, ipa: IPAFeatures
    ) -> None:
        text = "b̥͜p̥"
        unit = ipa.segment(text, strict=True)
        first, second = unit.constituents
        assert {first.base, second.base} <= ipa.phones.keys()
        assert "̥" in ipa.diacritics
        assert str(first) != str(second)
        assert first.bundle(ipa, with_defaults=True) == second.bundle(
            ipa, with_defaults=True
        )
        assert unit.bag() == ipa.segment("b̥", strict=True).bag()
        message = _one_warning(lambda: ipa.get_features(text), text)
        assert "segments()" in message
        assert [str(part) for part in unit.constituents] == ["b̥", "p̥"]

    @pytest.mark.parametrize(
        ("text", "hidden"),
        [("p͜d͜t", "t"), ("a͜p͜b", "b")],
    )
    def test_a_constituent_covered_across_other_bundles_needs_structure(
        self, ipa: IPAFeatures, text: str, hidden: str
    ) -> None:
        """The bag loses a part even when no two whole bundles are equal."""
        unit = ipa.segment(text, strict=True)
        bundles = [
            frozenset(part.bundle(ipa, with_defaults=True).items())
            for part in unit.constituents
        ]
        assert len(set(bundles)) == len(bundles)
        index = [str(part) for part in unit.constituents].index(hidden)
        remaining = unit.constituents[:index] + unit.constituents[index + 1 :]
        assert unit._bag(remaining) == unit.bag()
        message = _one_warning(lambda: ipa.get_features(text), text)
        assert "segments()" in message
        assert "feature_values()" not in message

    def test_constituent_observability_includes_value_order(
        self, ipa: IPAFeatures
    ) -> None:
        text = "t͜d͜p"
        unit = ipa.segment(text, strict=True)
        bag = unit.bag()
        assert all(
            unit._bag(unit.constituents[:index] + unit.constituents[index + 1 :]) != bag
            for index in range(len(unit.constituents))
        )

        without_t = unit._bag(unit.constituents[1:])
        assert bag["voiced"] == ("-", "+")
        assert without_t["voiced"] == ("+", "-")
        assert {key for key in bag if bag[key] != without_t[key]} == {"voiced"}
        assert {key: set(values) for key, values in bag.items()} == {
            key: set(values) for key, values in without_t.items()
        }
        assert ipa.feature_values(text)["voiced"] == ("-", "+")
        assert ipa.feature_values("d͜p")["voiced"] == ("+", "-")
        message = _one_warning(lambda: ipa.get_features(text), text)
        assert (
            "use feature_values() for sequential constituent(s) ['d', 'p']" in message
        )

        structured_text = "p͜d͜t"
        structured = ipa.segment(structured_text, strict=True)
        without_t = structured._bag(structured.constituents[:-1])
        assert without_t == structured.bag()
        message = _one_warning(
            lambda: ipa.get_features(structured_text), structured_text
        )
        assert "use segments() for sequential constituent(s) ['d', 't']" in message
        assert "feature_values()" not in message

    def test_contradictory_prosody_points_to_the_structured_read(
        self, ipa: IPAFeatures
    ) -> None:
        text = "aː̆"
        message = _one_warning(lambda: ipa.get_features(text), text)
        assert "segments()" in message
        with pytest.warns(UserWarning, match="two marks state 'length'"):
            (unit,) = ipa.segments(text, strict=True)
        assert unit.prosody == ("ː", "̆")

    def test_contradictory_segmental_marks_point_to_the_structured_read(
        self, ipa: IPAFeatures
    ) -> None:
        text = "a̺̻"
        message = _one_warning(lambda: ipa.get_features(text), text)
        assert "diacritic mark(s) ['̻']" in message
        assert "segments()" in message
        with pytest.warns(UserWarning, match="two marks state 'articulator'"):
            (unit,) = ipa.segments(text, strict=True)
        assert unit.constituents[0].modifiers == ("̺", "̻")

    def test_unregistered_symbol_with_no_wild_read_points_only_to_refusal(
        self, ipa: IPAFeatures
    ) -> None:
        text = "X"
        message = _one_warning(lambda: ipa.get_features(text), text)
        assert "unregistered symbol(s) ['X']" in message
        assert "no read retains unregistered symbol(s) ['X']" in message
        assert "use strict=True to refuse instead" in message
        assert "from_wild" not in message
        assert ipa.from_wild(text) == text
        with pytest.raises(ValueError, match="unknown symbols"):
            ipa.read(text, strict=True)

    @pytest.mark.parametrize("text", ["͜", "͡"])
    def test_orphan_tie_has_no_retaining_read(
        self, ipa: IPAFeatures, text: str
    ) -> None:
        message = _one_warning(lambda: ipa.get_features(text), text)
        omission = f"structural mark(s) {[text]!r}"
        assert f"no read retains {omission}" in message
        assert "use strict=True to refuse instead" in message
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            assert text not in ipa.read(text).to_ipa()
        with pytest.raises(ValueError, match="bind nothing"):
            ipa.read(text, strict=True)

    def test_multiple_units_point_to_a_read_that_keeps_both(
        self, ipa: IPAFeatures
    ) -> None:
        text = "a a"
        message = _one_warning(lambda: ipa.get_features(text), text)
        assert "multiple units ['a', 'a']" in message
        assert "segments()" in message
        assert [unit.to_ipa() for unit in ipa.segments(text, strict=True)] == ["a", "a"]

    def test_nonsegmental_material_points_to_the_form_read(
        self, ipa: IPAFeatures
    ) -> None:
        text = "∅"
        message = _one_warning(lambda: ipa.get_features(text), text)
        assert "read()" in message
        assert ipa.read(text, strict=True).to_ipa() == text


class TestNonNarrowingStaysSilent:
    def test_plain_phones_and_simultaneous_compositions_stay_silent(
        self, ipa: IPAFeatures
    ) -> None:
        simultaneous = [
            symbol
            for symbol in ipa.phones
            if (segment := ipa.segment(symbol)).junctures
            and Sense.SEQ not in segment.junctures
        ]
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            ipa.get_features("p")
            ipa.get_features("u͡i")
            for symbol in simultaneous:
                ipa.get_features(symbol)
        assert len(simultaneous) >= 10, "the simultaneous sweep was vacuous"

    def test_every_placeable_segmental_mark_is_represented(
        self, ipa: IPAFeatures
    ) -> None:
        checked = 0
        atomic = [
            symbol
            for symbol in ipa.phones
            if Sense.SEQ not in ipa.segment(symbol).junctures
        ]
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            for base in atomic:
                for mark in ipa.diacritics:
                    if modifier_mode(ipa, mark) in {"prosodic", "structural"}:
                        continue
                    text = base + mark
                    try:
                        segment = ipa.segment(text, strict=True)
                    except ValueError:
                        continue
                    if segment.to_ipa() != text:
                        continue
                    ipa.get_features(text)
                    checked += 1
        assert checked > 4_000, "the segmental-mark sweep was vacuous"

    def test_every_placeable_approach_mark_is_represented(
        self, ipa: IPAFeatures
    ) -> None:
        checked = 0
        atomic = [
            symbol
            for symbol in ipa.phones
            if Sense.SEQ not in ipa.segment(symbol).junctures
        ]
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            for base in atomic:
                for mark in ipa.approach_marks:
                    text = mark + base
                    try:
                        segment = ipa.segment(text, strict=True)
                    except ValueError:
                        continue
                    if not any(mark in part.approach for part in segment.constituents):
                        continue
                    ipa.get_features(text)
                    checked += 1
        assert checked >= 100, "the approach-mark sweep was vacuous"

    def test_a_semantically_redundant_mark_stays_silent(self, ipa: IPAFeatures) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert ipa.get_features("ã̃")["nasalized"] == "+"


class TestCallBoundary:
    def test_top_level_warning_points_here(self) -> None:
        with pytest.warns(FeatureNarrowingWarning) as caught:
            ipakit.features("d̆")
        assert caught[0].filename == __file__

    def test_inventory_warning_points_here(self, ipa: IPAFeatures) -> None:
        with pytest.warns(FeatureNarrowingWarning) as caught:
            ipa.get_features("a͜ɪ")
        assert caught[0].filename == __file__

    def test_pseudo_filename_is_external_inside_package_cwd(
        self,
        ipa: IPAFeatures,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        package = tmp_path / "ipakit"
        package.mkdir()
        (package / "<string>").write_text("", encoding="utf-8")
        features_module = sys.modules[IPAFeatures.__module__]
        monkeypatch.setattr(features_module, "__file__", package / "features.py")
        monkeypatch.chdir(package)
        with pytest.warns(FeatureNarrowingWarning) as caught:
            exec(
                compile("inventory.get_features('aː')", "<string>", "exec"),
                {"inventory": ipa},
            )
        assert caught[0].filename == "<string>"

    def test_loaded_package_module_stays_internal_after_source_is_removed(
        self,
        ipa: IPAFeatures,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        package = tmp_path / "ipakit"
        package.mkdir()
        source = package / "_boundary_probe.py"
        source.write_text(
            "def scalar_read(inventory):\n" "    return inventory.get_features('aː')\n",
            encoding="utf-8",
        )
        module_name = f"{ipakit.__name__}._boundary_probe"
        spec = importlib.util.spec_from_file_location(module_name, source)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, module_name, module)
        spec.loader.exec_module(module)
        source.unlink()

        features_module = sys.modules[IPAFeatures.__module__]
        monkeypatch.setattr(features_module, "__file__", package / "features.py")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with pytest.raises(RuntimeError, match="internal code called"):
                module.scalar_read(ipa)
        assert caught == []

    def test_representative_internal_consumers_do_not_call_the_warning_path(
        self, ipa: IPAFeatures
    ) -> None:
        operations = {
            "analysis tied": lambda: ipa.describe("a͜ɪ"),
            "analysis marked": lambda: ipa.describe("d̆"),
            "metric tied": lambda: ipa.distance("a͜ɪ", "a͜ʊ"),
            "metric marked": lambda: ipa.distance("d", "d̆"),
            "query": lambda: ipa.find("ˈa͜ɪd̆", ["vow"]),
            "rules": lambda: ipakit.rewrite("ˈa͜ɪd̆", "d̆ -> t"),
            "respelling tied": lambda: ipa.respell("a͜ɪ", voiced="+"),
            "respelling marked": lambda: ipa.respell("d̆", voiced="-"),
            "mapping": lambda: ipakit.phoneset_mapping(
                ["a͜ɪ", "d̆"], ["a͜ʊ", "d"], ipa=ipa
            ),
        }
        with warnings.catch_warnings():
            warnings.simplefilter("error", FeatureNarrowingWarning)
            results = {name: operation() for name, operation in operations.items()}
        assert all(result is not None for result in results.values())

    def test_runtime_guard_catches_an_aliased_internal_call(
        self, ipa: IPAFeatures
    ) -> None:
        """Emission-site enforcement catches what syntax cannot enumerate."""
        # The direct-call AST scan cannot see the alias call, while the
        # emission site observes the package caller regardless of how the
        # public read was reached.
        package_file = Path(ipakit.__file__).resolve().parent / "features.py"
        namespace: dict[str, object] = {
            "__name__": f"{ipakit.__name__}._boundary_probe"
        }
        source = (
            "def injected(inventory):\n"
            "    scalar_read = inventory.get_features\n"
            "    return scalar_read('aː')\n"
        )
        tree = ast.parse(source, filename=str(package_file))
        assert not [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "get_features"
        ]
        exec(
            compile(source, str(package_file), "exec"),
            namespace,
        )
        injected = namespace["injected"]
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with pytest.raises(RuntimeError, match="internal code called"):
                injected(ipa)
        assert caught == []


class TestTheWarningGuardIsCausal:
    def test_an_observed_loss_requires_a_warning(self, ipa: IPAFeatures) -> None:
        text = "a͜ɪ"
        with pytest.warns(FeatureNarrowingWarning):
            scalar = ipa.get_features(text)
        complete = ipa.feature_values(text)
        missing = {
            (key, value)
            for key, values in complete.items()
            for value in values
            if value != scalar.get(key)
        }
        assert missing, "the warning witness did not actually lose a feature value"

    def test_fault_injected_bag_pointer_fails_the_pointer_check(
        self, ipa: IPAFeatures, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        original = IPAFeatures._feature_omissions

        def point_prosody_at_bag(
            inventory: IPAFeatures, text: str
        ) -> list[tuple[str, str | None]]:
            return [
                (omission, "bag()" if reader == "feature_values()" else reader)
                for omission, reader in original(inventory, text)
            ]

        monkeypatch.setattr(IPAFeatures, "_feature_omissions", point_prosody_at_bag)
        message = _one_warning(lambda: ipa.get_features("aː"), "aː")
        assert "use bag() for prosodic mark(s) ['ː']" in message
        assert ipa.segment("aː").bag()["length"] == ("normal",)
        with pytest.raises(AssertionError):
            _assert_pointer_retains(
                ipa,
                "aː",
                "prosodic mark(s) ['ː']",
                "feature_values()",
                "feature",
                ("length", "long"),
            )


def test_package_internals_do_not_call_the_public_scalar_read() -> None:
    """Fast syntactic tripwire, not proof of the boundary.

    No test can prove every internal call absent, and this enumerated AST
    sweep cannot see aliases.  The emission-site check is the enforcement;
    this remains a cheap extra check for direct calls.
    """
    root = Path(ipakit.__file__).resolve().parent
    violations: list[str] = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            call = node.func
            public = (
                isinstance(call, ast.Attribute)
                and call.attr == "get_features"
                or isinstance(call, ast.Name)
                and call.id == "features"
                or isinstance(call, ast.Attribute)
                and isinstance(call.value, ast.Name)
                and call.value.id == "ipakit"
                and call.attr == "features"
            )
            if public:
                violations.append(f"{path.relative_to(root)}:{node.lineno}")
    assert violations == []


@pytest.mark.parametrize("text", ["a͜ɪ", "aː", "d̆"])
def test_features_cli_is_quiet_and_successful(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], text: str
) -> None:
    monkeypatch.setattr(sys, "argv", ["ipakit", "features", text])
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        rc = ipakit.cli.main()
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out
    assert captured.err == ""


def test_feature_values_retains_the_witnessed_length(ipa: IPAFeatures) -> None:
    assert ipa.feature_values("d̆")["length"] == ("extra-short",)


def test_feature_values_uses_the_first_contradictory_prosody_mark(
    ipa: IPAFeatures,
) -> None:
    with pytest.warns(UserWarning, match="two marks state 'length'"):
        values = ipa.feature_values("aː̆")
    assert values["length"] == ("long",)
