"""Named inventories share one strict house-IPA boundary."""

from __future__ import annotations

import functools
import json
import sys
from pathlib import Path

import ipakit
import ipakit.cli
import pytest


def _run_cli(monkeypatch, capsys, *arguments: str):
    monkeypatch.setattr(sys, "argv", ["ipakit", *arguments])
    rc = ipakit.cli.main()
    captured = capsys.readouterr()
    return rc, captured.out, captured.err


def _style_failures(item):
    refused = set()
    mismatches = set()
    for phone in item.phones or ():
        try:
            spelling = item.style.spell(phone)
        except ValueError:
            refused.add(phone)
            continue
        if item.style.read(spelling) != phone:
            mismatches.add(phone)
    return refused, mismatches


def _fresh_inventory(name: str):
    """Build from the declaration, bypassing inventory-object caches."""
    from ipakit.inventories import _registry

    builder = _registry()[name][0]
    if isinstance(builder, functools.partial):
        function = getattr(builder.func, "__wrapped__", builder.func)
        return function(*builder.args, **(builder.keywords or {}))
    return getattr(builder, "__wrapped__", builder)()


def test_registry_discovers_every_espeak_declaration() -> None:
    from ipakit.bridges.espeak import _DATA

    assert {
        name.removeprefix("espeak:")
        for name in ipakit.inventories()
        if name.startswith("espeak:")
    } == {path.stem for path in _DATA.glob("*.xml")}
    assert {"cmudict", "pocketsphinx", "espeak"} <= set(ipakit.inventories())


def test_registry_discovers_every_mfa_declaration() -> None:
    from ipakit.bridges.mfa import declarations

    assert {f"mfa:{name}" for name in declarations()} <= set(ipakit.inventories())


def test_mfa_union_and_english_keep_declared_atom_order() -> None:
    from ipakit.bridges.mfa import MFA, UNION, MFABridge

    union = MFABridge(UNION)
    assert list(ipakit.inventory("mfa").phones or ()) == [
        ipakit.normalize(atom.spelling) for atom in union.atoms
    ]
    assert list(ipakit.inventory("mfa:english").phones or ()) == [
        ipakit.normalize(atom.spelling) for atom in MFA.atoms
    ]


def test_mfa_korean_carries_atoms_and_refusals() -> None:
    korean = ipakit.inventory("mfa:korean")
    assert korean.phones is not None
    assert len(korean.phones) == 90
    assert len(korean.refusals) == 15
    assert korean.version == "korean_mfa-v3.0.0"


def test_unknown_mfa_declaration_names_every_member() -> None:
    from ipakit.bridges.mfa import declarations

    with pytest.raises(ValueError) as caught:
        ipakit.inventory("mfa:nosuch")
    assert all(name in str(caught.value) for name in declarations())


def test_unknown_name_reports_what_is_available() -> None:
    with pytest.raises(ValueError, match="no shipped inventory 'nosuch'; have"):
        ipakit.inventory("nosuch")


def test_espeak_union_is_larger_than_every_language_inventory() -> None:
    union = ipakit.inventory("espeak")
    languages = [
        ipakit.inventory(name)
        for name in ipakit.inventories()
        if name.startswith("espeak:")
    ]
    assert union.phones is not None
    assert all(item.phones is not None for item in languages)
    assert len(union.phones) > max(
        len(item.phones) for item in languages if item.phones is not None
    )


def test_espeak_union_reads_only_agreed_names() -> None:
    style = ipakit.inventory("espeak").style
    assert style.read("p") == "p"
    with pytest.raises(ValueError) as caught:
        style.read("&")
    message = str(caught.value)
    assert "af='æ'" in message
    assert "da='a'" in message
    assert "espeak:<code>" in message


def test_espeak_union_spells_with_the_ranked_unambiguous_name() -> None:
    style = ipakit.inventory("espeak").style
    assert style.spell("p") == "p"
    assert style.spell("ə") == "@-"


def test_espeak_union_spell_refusal_names_ambiguous_candidates() -> None:
    style = ipakit.inventory("espeak").style
    with pytest.raises(ValueError) as caught:
        style.spell("a͜ɛ")
    message = str(caught.value)
    assert "candidate 'aE'" in message
    assert "espeak:lb='ɛː'" in message
    assert "espeak:sjn='a͜ɛ'" in message
    assert "espeak:<code>" in message


def test_espeak_union_witnesses_match_the_declarations() -> None:
    union = ipakit.inventory("espeak")
    assert union.phones is not None
    refused = object()
    witnesses = {
        "p": "p",
        "b": "b",
        "t": "t",
        "d": "d",
        "k": "k",
        "ɡ": "g",
        "ĩ": "i~",
        "ũ": "u~",
        "ə": "@-",
        "t͡ʃ": "tS",
        "d͡ʒ": "dZ",
        "ʃ": refused,
        "ʒ": refused,
        "a͜ɛ": refused,
    }
    for phone, expected in witnesses.items():
        try:
            spelling = union.style.spell(phone)
        except ValueError:
            assert expected is refused
        else:
            assert spelling == expected
            assert union.style.read(spelling) == phone


def test_every_finite_style_round_trips_except_its_declared_collapses() -> None:
    for name in ipakit.inventories():
        item = ipakit.inventory(name)
        if item.phones is None:
            continue
        refused, mismatches = _style_failures(item)
        expected_refused, _ = _style_failures(_fresh_inventory(name))
        declared = {
            phone
            for spelling, phones in item.style.collapses.items()
            for phone in phones
            if item.style.read(spelling) != phone
        }
        assert refused == expected_refused, name
        assert mismatches == declared, name


def test_round_trip_sweep_detects_an_injected_spelling_refusal() -> None:
    item = ipakit.inventory("cmudict")
    expected_refused, _ = _style_failures(_fresh_inventory("cmudict"))
    original = item.style._speller

    def refusing(phone: str) -> str:
        if phone == "p":
            raise ValueError("injected refusal")
        return original(phone)

    object.__setattr__(item.style, "_speller", refusing)
    try:
        refused, _ = _style_failures(item)
        assert refused != expected_refused
    finally:
        object.__setattr__(item.style, "_speller", original)


def test_styles_normalize_canonically_equivalent_input() -> None:
    for name in ("espeak", "espeak:pt"):
        style = ipakit.inventory(name).style
        assert style.spell("ĩ") == style.spell("i\N{COMBINING TILDE}")
    ipa = ipakit.inventory("ipa").style
    assert ipa.read("ĩ") == ipa.read("i\N{COMBINING TILDE}")


def test_mfa_inventory_bridge_is_cached_per_parser_identity() -> None:
    from ipakit.inventories import _mfa_bridge

    default = _mfa_bridge("korean")
    supplemented = ipakit.IPAFeatures(supplements=["aspirated-stops"])
    custom = _mfa_bridge("korean", supplemented)
    assert custom is not default
    assert custom is _mfa_bridge("korean", supplemented)
    assert custom.ipa is supplemented
    assert custom.read(["pʰ"]).to_ipa() == "pʰ"


def test_espeak_union_maps_to_mfa() -> None:
    mapping = ipakit.phoneset_mapping("espeak", "mfa")
    assert mapping.source_inventory is not None
    assert mapping.source_inventory.name == "espeak"


def test_mfa_english_maps_to_cmudict_and_spells() -> None:
    mapping = ipakit.phoneset_mapping("mfa:english", "cmudict")
    assert mapping.source_inventory is not None
    assert mapping.source_inventory.name == "mfa:english"
    assert all(item.source_spelling is not None for item in mapping)


def test_cli_shows_bare_espeak(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["ipakit", "inventory", "show", "espeak"])
    assert ipakit.cli.main() == 0
    output = capsys.readouterr().out
    assert "espeak" in output
    assert "a͜ɛ\trefused: cannot spell 'a͜ɛ' in espeak" in output
    assert "candidate 'aE'" in output


def test_cli_shows_mfa_refusals(monkeypatch, capsys) -> None:
    rc, output, _ = _run_cli(monkeypatch, capsys, "inventory", "show", "mfa:korean")
    assert rc == 0
    assert "refusals\nspelling\treason" in output
    assert "c͈\toutside-house-ipa: U+0348" in output


def test_cli_lists_bare_espeak(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["ipakit", "inventory", "list"])
    assert ipakit.cli.main() == 0
    output = capsys.readouterr().out
    assert "name\tkind\tphones\tprovenance" in output
    assert "espeak:en\t" in output


def test_no_finite_inventory_contains_a_silence_or_boundary() -> None:
    from ipakit.models import _silence_spellings

    forbidden = _silence_spellings() | {"#", "∅"}
    for name in ipakit.inventories():
        phones = ipakit.inventory(name).phones
        if phones is not None:
            assert forbidden.isdisjoint(phones), name


def test_an_uncollapsed_phone_is_not_reported_as_a_collapse() -> None:
    assert "p" not in ipakit.phoneset_mapping("cmudict", "mfa").collapses


@pytest.mark.parametrize("name", ["xsampa", "kirshenbaum"])
def test_pure_ascii_converters_are_not_inventory_styles(name: str) -> None:
    with pytest.raises(ValueError, match="no shipped inventory"):
        ipakit.inventory(name)


def test_named_mapping_keeps_house_and_external_spellings() -> None:
    mapping = ipakit.phoneset_mapping("cmudict", "mfa")
    schwa = next(item for item in mapping if item.source == "ə" and item.target == "ə")
    assert (schwa.source_spelling, schwa.target_spelling) == ("AH", "ə")
    assert mapping.source_inventory is not None
    assert mapping.source_inventory.name == "cmudict"
    assert mapping.target_inventory is not None
    assert mapping.target_inventory.name == "mfa"


def test_notation_without_phones_is_refused_as_a_side() -> None:
    with pytest.raises(ValueError, match="notation, not a finite inventory"):
        ipakit.phoneset_mapping("wild", ["p"])


def test_a_named_side_already_supplies_its_style() -> None:
    with pytest.raises(ValueError, match="already declares its style"):
        ipakit.phoneset_mapping("mfa", ["p"], source_style="ipa")


def test_distance_map_accepts_named_sides_and_reports_json(monkeypatch, capsys) -> None:
    rc, output, _ = _run_cli(
        monkeypatch, capsys, "distance", "map", "cmudict", "mfa", "-f", "json"
    )
    assert rc == 0
    report = json.loads(output)
    assert report["source_inventory"] == "cmudict"
    assert report["target_inventory"] == "mfa"
    assert {"source_spelling", "target_spelling"} <= report["correspondences"][0].keys()


def test_distance_map_refuses_a_source_its_style_cannot_read(
    tmp_path, monkeypatch, capsys
) -> None:
    source = tmp_path / "source.txt"
    source.write_text("p\n", encoding="utf-8")
    target = tmp_path / "target.txt"
    target.write_text("b\n", encoding="utf-8")
    rc, output, error = _run_cli(
        monkeypatch,
        capsys,
        "distance",
        "map",
        str(source),
        str(target),
        "--from-style",
        "cmudict",
        "-f",
        "json",
    )
    assert rc == 3
    assert "cannot read 'p' as cmudict on source side" in error
    refused = json.loads(output)["correspondences"][0]
    assert refused["source"] == "p"
    assert refused["source_spelling"] is None
    assert refused["reason"] is not None


def test_distance_map_refuses_a_target_its_style_cannot_read(
    tmp_path, monkeypatch, capsys
) -> None:
    source = tmp_path / "source.txt"
    source.write_text("b\n", encoding="utf-8")
    target = tmp_path / "target.txt"
    target.write_text("p\n", encoding="utf-8")
    rc, output, error = _run_cli(
        monkeypatch,
        capsys,
        "distance",
        "map",
        str(source),
        str(target),
        "--to-style",
        "cmudict",
        "-f",
        "json",
    )
    assert rc == 3
    assert "cannot read 'p' as cmudict on target side" in error
    report = json.loads(output)
    assert report["unreadable_targets"][0][0] == "p"
    assert report["unused_targets"] == []


def test_distance_map_refuses_name_file_collision_and_accepts_escape(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "mfa").write_text("p\n", encoding="utf-8")
    rc, _, error = _run_cli(monkeypatch, capsys, "distance", "map", "mfa", "cmudict")
    assert rc != 0
    assert "both an inventory and a file" in error
    rc, _, _ = _run_cli(monkeypatch, capsys, "distance", "map", "./mfa", "cmudict")
    assert rc == 0


def test_file_styles_and_wild_are_reachable(tmp_path, monkeypatch, capsys) -> None:
    source = tmp_path / "source.txt"
    source.write_text("G\n", encoding="utf-8")
    target = tmp_path / "target.txt"
    target.write_text("g\n", encoding="utf-8")
    rc, output, _ = _run_cli(
        monkeypatch,
        capsys,
        "distance",
        "map",
        str(source),
        str(target),
        "--from-style",
        "cmudict",
        "--to-style",
        "wild",
    )
    assert rc == 0
    assert "G" in output
    rc, _, error = _run_cli(
        monkeypatch,
        capsys,
        "distance",
        "map",
        str(source),
        str(target),
        "--wild",
        "--from-style",
        "cmudict",
    )
    assert rc != 0
    assert "cannot be combined" in error


def test_named_side_honors_max_distance(monkeypatch, capsys) -> None:
    rc, output, _ = _run_cli(
        monkeypatch,
        capsys,
        "distance",
        "map",
        "cmudict",
        "mfa",
        "--max-distance",
        "0",
    )
    assert rc == 0
    assert "unmapped:" in output


def test_convert_phoneset_reports_style_bucket(tmp_path, monkeypatch, capsys) -> None:
    source = tmp_path / "source.txt"
    source.write_text("AH\nP\n", encoding="utf-8")
    rc, output, error = _run_cli(
        monkeypatch,
        capsys,
        "convert",
        "phoneset",
        str(source),
        "--from-style",
        "cmudict",
    )
    assert rc == 0
    assert "ə" in output
    assert "cmudict: AH -> ə" in error
    assert "tied: AH" not in error


def test_inventory_show_style_and_unknown_name(monkeypatch, capsys) -> None:
    rc, output, _ = _run_cli(monkeypatch, capsys, "inventory", "show", "wild")
    assert rc == 0
    assert "kind: style" in output
    rc, _, error = _run_cli(monkeypatch, capsys, "inventory", "show", "nosuch")
    assert rc != 0
    assert "espeak:<code>" in error
    assert "inventory list" in error


@pytest.mark.parametrize("name", ["pocketsphinx", "timit"])
def test_less_common_inventories_load(name: str) -> None:
    assert ipakit.inventory(name).phones is not None


def test_inventory_from_cmudict_keeps_first_seen_order(tmp_path) -> None:
    source = tmp_path / "sample.dict"
    source.write_text(
        ";;; header\nWORD  W ER1 D # note\nWORD(2)  W AO1 R D\nSIL  SIL\n",
        encoding="utf-8",
    )
    derived = ipakit.inventory_from_dictionary(source, "cmudict")
    assert list(derived.phones or ()) == ["w", "ˈɝ", "d", "ˈɔ", "ɹ"]
    assert derived.style.name == "cmudict"
    assert str(source) in derived.provenance


def test_inventory_from_mfa_dictionary_uses_its_declaration() -> None:
    source = Path(__file__).parent / "fixtures" / "mfa_english_us_v3_1_0.dict"
    derived = ipakit.inventory_from_dictionary(source, "mfa:english_us")
    assert list(derived.phones or ())[:4] == ["m", "e͜j", "t", "s"]


@pytest.mark.parametrize("line", ["bad\t\n", "bad\t   \n"])
def test_inventory_from_mfa_dictionary_refuses_an_empty_pronunciation(
    tmp_path, line: str
) -> None:
    source = tmp_path / "bad.dict"
    source.write_text(line, encoding="utf-8")
    with pytest.raises(ValueError) as caught:
        ipakit.inventory_from_dictionary(source, "mfa:english_us")
    message = str(caught.value)
    assert "line 1" in message
    assert "entry 'bad\\t" in message
    assert "MFA dictionary line has no pronunciation" in message


def test_inventory_from_mfa_dictionary_filters_silence_before_reading(tmp_path) -> None:
    source = tmp_path / "sample.dict"
    source.write_text("mates\tm ej t s SIL\n", encoding="utf-8")
    derived = ipakit.inventory_from_dictionary(source, "mfa:english_us")
    assert list(derived.phones or ()) == ["m", "e͜j", "t", "s"]


def test_inventory_from_mfa_phone_refusal_has_one_entry_prefix(tmp_path) -> None:
    source = tmp_path / "bad.dict"
    source.write_text("mates\tm NOPE\n", encoding="utf-8")
    with pytest.raises(ValueError) as caught:
        ipakit.inventory_from_dictionary(source, "mfa:english_us")
    message = str(caught.value)
    assert message.count("entry ") == 1
    assert "entry 'mates', phone 'NOPE'" in message


def test_inventory_from_dictionary_refusals_are_specific(tmp_path) -> None:
    source = tmp_path / "bad.dict"
    source.write_text("GOOD P\nBAD NOPE\n", encoding="utf-8")
    with pytest.raises(ValueError) as caught:
        ipakit.inventory_from_dictionary(source, "cmudict")
    message = str(caught.value)
    assert "line 2" in message
    assert "'bad'" in message
    assert "'NOPE'" in message


def test_inventory_from_dictionary_refuses_a_style_without_a_reader(
    tmp_path,
) -> None:
    source = tmp_path / "sample.dict"
    source.write_text("word p\n", encoding="utf-8")
    with pytest.raises(ValueError) as caught:
        ipakit.inventory_from_dictionary(source, "timit")
    assert "cmudict" in str(caught.value)
    assert "pocketsphinx" in str(caught.value)
    assert "mfa:<name>" in str(caught.value)


def test_derived_inventory_is_a_mapping_side(tmp_path) -> None:
    source = tmp_path / "sample.dict"
    source.write_text("word P AH0\n", encoding="utf-8")
    derived = ipakit.inventory_from_dictionary(source, "cmudict")
    mapping = ipakit.phoneset_mapping(derived, "mfa")
    assert mapping.source_inventory is derived


def test_inventory_from_dictionary_cli_text_native_and_json(
    tmp_path, monkeypatch, capsys
) -> None:
    source = tmp_path / "sample.dict"
    source.write_text("word P AH0\n", encoding="utf-8")
    rc, output, _ = _run_cli(
        monkeypatch, capsys, "inventory", "from-dict", str(source), "--style", "cmudict"
    )
    assert (rc, output) == (0, "p\nə\n")
    rc, output, _ = _run_cli(
        monkeypatch,
        capsys,
        "inventory",
        "from-dict",
        str(source),
        "--style",
        "cmudict",
        "--spell",
        "native",
    )
    assert (rc, output) == (0, "P\nAH\n")
    rc, output, _ = _run_cli(
        monkeypatch,
        capsys,
        "inventory",
        "from-dict",
        str(source),
        "--style",
        "cmudict",
        "-f",
        "json",
    )
    report = json.loads(output)
    assert report["phones"] == [
        {"house_ipa": "p", "spelling": "P"},
        {"house_ipa": "ə", "spelling": "AH"},
    ]
