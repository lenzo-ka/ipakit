"""The final CLTS receipt is independently reproducible and can go stale."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import ipakit
import pytest
from ipakit._clts_profile import (
    ADAPTER_OUTCOMES,
    FINAL_MANIFEST_KIND,
    SourceProfileSpec,
    core_bipa_resolutions,
    core_bipa_spec,
    manifest_metadata,
    require_final_manifest,
    verify_manifest,
)
from ipakit._identity import identity_fingerprint
from ipakit._provenance import SourceMetadata
from ipakit.clts import ArtifactInvalid, read_snapshot

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "ipakit/data/clts"
MANIFEST = DATA / "manifest.json"

SOURCE_INPUTS = {
    ".zenodo.json": "74cccea55b3ce72643e12bd873cc03d3d51ff548ebc777e134c11b6a082cc9ae",
    "cldf-metadata.json": "b1676ed1d1862863c818a42f1fad6e0656abbbadcd8aa036752d14633ec4bde2",
    "pkg/transcriptionsystems/bipa/consonants.tsv": "9b65866bd7408e65dfd4aca0172be2e2788ee37bd5a3cb8933de512471de9730",
    "pkg/transcriptionsystems/bipa/diacritics.tsv": "a49f76d508bc10b0cad02c13c6da8406dc1d5ae2ccf6377fe79aa31b03a38994",
    "pkg/transcriptionsystems/bipa/markers.tsv": "c4cb93c429e40552d2c566fc597b6809355f1da41a8bae158ab0ccb81edc65ab",
    "pkg/transcriptionsystems/bipa/normalize.tsv": "1c40164510ce444f310a6f6a7130d30d045712dda218f3a30f6c2f4269370c39",
    "pkg/transcriptionsystems/bipa/tones.tsv": "30eca769939d71c7bd88d34d4ee3fee1e2a73a5cde53e374d57f778c6c0aaf2f",
    "pkg/transcriptionsystems/bipa/vowels.tsv": "fdbe4c7be2c665acad0370c6572dbb5b54e8dff1bff36c38b7063f818b2d3a81",
    "pkg/transcriptionsystems/features.json": "4a2964f6ccdfde87625b7adccc63323996bbf28ce469f62bcc08f437fde03211",
    "pkg/transcriptionsystems/transcription-system-metadata.json": "b9fd25ae151e63c0717daa91addc53de052e4b6b2de19a88ee761efdd5a3e1f9",
}
RESOLVER_INPUTS = {
    "__init__.py": "aca68ab0edb7488769227d2998ef87fed73e1ea8bb0615a3c8718c08bad780b6",
    "__main__.py": "d02e1cedeef2aeeb607b44615a2ae33ab73ac63f9adc52e85be4d9b3849787af",
    "_compat.py": "d4597b95f9c20103a23c91c624a59ac8ac8901d809f5f07de38e49e139f8b910",
    "api.py": "0d655cda36cf341032615d9cf3b8ec1b7003ff533f3e0eebcf7dc55739784bdd",
    "cldf.py": "b976ceadec499fcc2826aea07949438bc9dad46f053a5a3d88f22c2d6b03a02d",
    "cli_util.py": "73682213f6845ba90b5471f91f67733e166c96f102c1262b89d69787332df5c0",
    "commands/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "commands/dist.py": "1a6a5f8e2ce957e3a2f7a8c2d305baf486f443400381cfddce7f93991f042adc",
    "commands/features.py": "25d3c72a131a5f31628b7a214d78dd13bb5adebaeed096bf402c2f8445569601",
    "commands/ls.py": "14487cdbf78573e664dccdc9e805dd4be644768d34aa844fd1691245bb34bf0b",
    "commands/make_app.py": "d57203fcfb9660c9fb143fd434aa843bfb13112741b7c25ae0270dc306f60560",
    "commands/make_dataset.py": "99d0f91fd35cc9a7f6d708fc7741e30fc7f9976e87a4cf9f7b9d2637080e1bd0",
    "commands/make_pkg.py": "12fd10ad90782fd404d5439fbe035eb076e993e72e9ef55b3ae559f0b172dd1f",
    "commands/map.py": "109bd6716b316fb1055b66233919ed3ef99462137d8c988e77ec615da2f3036a",
    "commands/sounds.py": "00ea4a87fdf85189b2d3504255f9c103d99cad2fff8b1674bd8d511df069be42",
    "commands/stats.py": "3933faafc65045a6923146d31e5fa5e8113583d236160648ea521e819e8566d5",
    "commands/table.py": "e37c793150c2e05a1658f89368857c06c4f05f358632e78b423bd0f6be9f9a6c",
    "commands/tdstats.py": "fd29e4956cec8b93fcf7f9695564d83cc1768b7572aa04063f9eda09a777c7bf",
    "commands/test.py": "b31830fbc8ccd9e3ca9fcfad3ce43b04e88903411363034bb9868964aa83aac2",
    "commands/test_dataset.py": "c15bfca201a59e7aecc38f16ea4281cd0d9e3f65f58fe46012ea676978d9fb6d",
    "datatypes.py": "c7e35187345b9e983c1f77a25ffcf4e641951f2993297e58f0caf6912c6e4bb1",
    "datatypes_util.py": "7158bb80422537126a1e4b6f3e2ded820279deb91c84e040eab6a19d200a82f3",
    "features.py": "abfe53466ad83b25866a5354fb22e23894bb878eea090e1d239fd8b06169a833",
    "inventories.py": "45f03bb0e0a9aa14190b4cd90c4c7a619b14979be7b16ba9ab373bf664debaf6",
    "ipachart.py": "9fc74671f021bc13df2d51b56c106c1a155d1010f3737306c534b4fd1f9647ad",
    "metadata.py": "c92f715c8d0444955a4a67af9d9bc6e1a7f0ec02c210e071b181ac9504acb38a",
    "models.py": "a9b0430b362910f21855623cd68e8fde92dca6abf2334dd8eed8eb86256187f4",
    "util.py": "8c4ecaf1c18407d8d773f70d081121dd4e6648cd5406adc98383e1c524be6e2a",
}


def _copy_data(tmp_path: Path) -> Path:
    target = tmp_path / "clts"
    shutil.copytree(DATA, target)
    return target


def _write_manifest(path: Path, data: dict[str, object]) -> None:
    material = {key: value for key, value in data.items() if key != "fingerprint"}
    data["fingerprint"] = identity_fingerprint(material)
    path.write_text(
        json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )


def test_manifest_fields_are_literal_and_complete() -> None:
    manifest = json.loads(MANIFEST.read_bytes())
    assert set(manifest) == {
        "schema",
        "kind",
        "domain",
        "source-policy",
        "extractor",
        "artifacts",
        "license",
        "house-declarations",
        "adapter",
        "projection-policy",
        "profile-family",
        "fingerprint",
    }
    assert manifest["schema"] == {"id": "ipakit-source-receipt", "version": 1}
    assert manifest["kind"] == "final"
    assert manifest["domain"] == "core-bipa"
    policy = manifest["source-policy"]
    assert policy["version"] == 1
    assert policy["source"] == {
        "artifact": "core BIPA Sound declarations and explicit aliases",
        "kind": "finite-feature-set-geometry",
        "license": "CC-BY-4.0",
        "upstream": "CLTS",
        "upstream-url": "https://github.com/cldf-clts/clts",
        "version": "4da03b1d0bc2c96839df693d3123be72cfac8419",
    }
    assert policy["inputs"] == SOURCE_INPUTS
    assert policy["resolver"] == {
        "name": "pyclts",
        "version": "4.0.2",
        "inputs": RESOLVER_INPUTS,
    }
    assert policy["credit"] == {
        "creators": [
            "Johann-Mattis List",
            "Cormac Anderson",
            "Tiago Tresoldi",
            "Christoph Rzymski",
            "Robert Forkel",
        ],
        "doi": "https://doi.org/10.5281/zenodo.3515744",
        "license-url": "https://creativecommons.org/licenses/by/4.0/",
        "source-url": "https://github.com/cldf-clts/clts/tree/4da03b1d0bc2c96839df693d3123be72cfac8419/pkg/transcriptionsystems/bipa",
        "title": "CLTS. Cross-Linguistic Transcription Systems",
        "transformations": [
            "Extract exact Sound.featureset labels and canonical spellings with pyclts; retain core dictionary keys and verified literal source aliases, recording normalization.",
            "Omit marker scoring, articulatory mappings, productive resolution, and unused upstream fields.",
            "Sort keys and labels; serialize as versioned JSON.",
        ],
    }
    assert manifest["extractor"] == {
        "id": "ipakit.clts.extract_snapshot",
        "version": "1",
    }
    assert manifest["artifacts"] == {
        "ipakit/data/clts/core.json": {
            "identity": "sha256:8b5620aed4b88e6d14d02ddbd6e404fbe9bf9b13577851acd244a95b5793dcc4",
            "schema": {"id": "ipakit-clts-feature-snapshot", "version": 1},
            "sha256": "14ecd5f6961dcb4251b1aee2e13bc45a804c5807de1b7507030ad639159bc2ec",
        }
    }
    assert manifest["license"] == {
        "id": "CC-BY-4.0",
        "notices": {
            "MAPPING-NOTICE.txt": "6974e817afce8120613d54ed84638c712f100175d5b8156dfdd87204830117f7",
            "NOTICE.txt": "a4d1d7d82ff911435d6ee8ee76a77e0dfee426172c72ed6cd2b51db80c844f67",
        },
    }
    assert manifest["house-declarations"] == {
        "fingerprint": "sha256:fccdd9a6ebb0ad98688d3e3065a19a25f1b60ec7a9ad0cd0faffa739dfcae5fe"
    }
    assert manifest["adapter"] == {
        "schema": {"id": "ipakit-clts-core-bipa-resolution", "version": 1},
        "outcomes": {
            "entry": "resolved",
            "excluded": {
                "marker": "marker",
                "unknown-source-spelling": "unknown-sound",
            },
            "absent": "outside-artifact-domain",
        },
    }
    assert manifest["projection-policy"] == {
        "name": "explicit-only",
        "version": 1,
        "unsupported": "error",
    }
    assert manifest["profile-family"] == {
        "id": "ipakit-clts-source",
        "version": 1,
    }
    assert manifest["fingerprint"] == (
        "sha256:354f45e761e8550ac6f99e7439cc8849ebbd93ccd3122db1f8660062c0d1b73e"
    )
    assert "mapping" not in manifest
    assert "profile-fingerprint" not in manifest


def test_manifest_verifies_and_final_profile_binds_its_fingerprint() -> None:
    assert verify_manifest() == (
        "sha256:354f45e761e8550ac6f99e7439cc8849ebbd93ccd3122db1f8660062c0d1b73e"
    )
    spec = core_bipa_spec()
    assert spec.manifest_kind == FINAL_MANIFEST_KIND
    require_final_manifest(spec)


def test_manifest_kind_has_no_default_and_fabricated_final_is_refused() -> None:
    with pytest.raises(TypeError, match="manifest_kind"):
        SourceProfileSpec(
            source=SourceMetadata("x", "urn:x", "a", "1", "l", "k"),
            provider_fingerprint="any-provider",
            manifest_fingerprint="not-a-manifest",
            mapping_identity="any-mapping",
            kinds=("vowel",),
        )
    fabricated = replace(core_bipa_spec(), manifest_fingerprint="not-a-manifest")
    with pytest.raises(ArtifactInvalid, match="does not bind"):
        require_final_manifest(fabricated)


def test_resealed_core_edit_makes_manifest_stale(tmp_path: Path) -> None:
    data_dir = _copy_data(tmp_path)
    core_path = data_dir / "core.json"
    core = json.loads(core_path.read_bytes())
    core["entries"]["a"]["canonical"] = "fault"
    material = {key: value for key, value in core.items() if key != "identity"}
    core["identity"] = identity_fingerprint(material)
    core_path.write_text(
        json.dumps(core, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )
    with pytest.raises(ArtifactInvalid, match="stale CLTS manifest field: artifacts"):
        verify_manifest(data_dir=data_dir)


def test_mutated_house_declarations_make_manifest_stale() -> None:
    inventory = ipakit.load_ipa_features()
    inventory.classes.append("fault-injected-class")
    with pytest.raises(
        ArtifactInvalid, match="stale CLTS manifest field: house-declarations"
    ):
        verify_manifest(inventory=inventory)


def test_adapter_uses_manifested_outcome_table_and_a_change_is_stale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(ADAPTER_OUTCOMES["excluded"], "marker", "unknown-sound")
    assert core_bipa_resolutions(read_snapshot(), ["+"])[0]["status"] == "unknown-sound"
    with pytest.raises(ArtifactInvalid, match="stale CLTS manifest field: adapter"):
        verify_manifest()


@pytest.mark.parametrize("operation", ["alter", "remove"])
def test_notice_change_or_removal_is_refused(tmp_path: Path, operation: str) -> None:
    data_dir = _copy_data(tmp_path)
    notice = data_dir / "NOTICE.txt"
    if operation == "alter":
        notice.write_bytes(notice.read_bytes() + b"fault\n")
        message = "stale CLTS manifest field: license"
    else:
        notice.unlink()
        message = "required CLTS manifest input is unavailable"
    with pytest.raises(ArtifactInvalid, match=message):
        verify_manifest(data_dir=data_dir)


@pytest.mark.parametrize("forbidden", ["mapping", "profile-fingerprint"])
def test_schema_refuses_cycle_edges(tmp_path: Path, forbidden: str) -> None:
    data_dir = _copy_data(tmp_path)
    path = data_dir / "manifest.json"
    manifest = json.loads(path.read_bytes())
    manifest[forbidden] = "sha256:" + "0" * 64
    _write_manifest(path, manifest)
    with pytest.raises(ArtifactInvalid, match="unexpected receipt fields"):
        verify_manifest(data_dir=data_dir)


def test_interim_kind_is_refused() -> None:
    spec = replace(core_bipa_spec(), manifest_kind="interim")
    with pytest.raises(ValueError, match="manifest kind mismatch"):
        require_final_manifest(spec)


def test_duplicate_json_key_is_refused(tmp_path: Path) -> None:
    data_dir = _copy_data(tmp_path)
    path = data_dir / "manifest.json"
    original = path.read_text(encoding="utf-8")
    path.write_text(original.replace("{\n", '{\n  "kind": "final",\n', 1))
    with pytest.raises(ArtifactInvalid, match="duplicate JSON key: kind"):
        verify_manifest(data_dir=data_dir)


def test_offline_regeneration_is_byte_equal_with_pyclts_blocked(tmp_path: Path) -> None:
    code = r"""
import builtins, runpy, sys
original = builtins.__import__
def blocked(name, *args, **kwargs):
    if name.split('.')[0] == 'pyclts':
        raise AssertionError('pyclts import attempted')
    return original(name, *args, **kwargs)
builtins.__import__ = blocked
sys.argv = [sys.argv[1]]
runpy.run_path(sys.argv[0], run_name='__main__')
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(ROOT / "scripts/clts_manifest.py")],
        cwd=tmp_path,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr.decode()
    assert result.stdout == MANIFEST.read_bytes()
    assert manifest_metadata() == json.loads(result.stdout)
