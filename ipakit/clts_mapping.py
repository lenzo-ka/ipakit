"""Reviewed directional predicates used by the bounded CLTS import.

The authority is deliberately bounded to reviewed plain-stop projections and the
adjudicated release and duration declarations. Other declarations remain explicitly
unresolved; the public adapter reports them as refused or preserved source material.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from . import load_ipa_features
from ._identity import identity_fingerprint
from .clts import (
    Snapshot,
    _unique_object,
    declaration_audit,
    read_snapshot,
    source_policy,
    validate_declaration_census,
    validate_source,
)
from .extraction import BuildResult
from .features import IPAFeatures
from .metric import metric_fingerprint

DATA = Path(__file__).parent / "data" / "clts"

DISPOSITION_CLASSES = (
    "exact under stated conditions",
    "conditional/composite",
    "convention-based or lossy",
    "unsupported by the adapter despite native expressibility",
    "not expressible in the target model",
    "conflicting",
    "unresolved pending evidence",
)

ENHANCEMENT_GAP_KINDS = (
    "adapter gap",
    "notation gap",
    "model gap",
    "source-side collapse",
)
ENHANCEMENT_DECISIONS = ("accepted", "deferred", "rejected")


class MappingInvalid(ValueError):
    """Invalid/stale mapping content or incompatible supplied evidence."""


def _require_profile_binding(
    rules: dict[str, Any], snapshot: Snapshot | None = None
) -> str:
    """Require the reviewed rules to bind the recomputed acyclic profile basis."""
    from ._clts_profile import PROFILE_FAMILY, core_bipa_basis

    basis = core_bipa_basis(snapshot)
    binding = rules.get("profile_binding")
    if (
        not isinstance(binding, dict)
        or set(binding) != {"profile", "basis"}
        or binding.get("profile") != PROFILE_FAMILY
    ):
        raise MappingInvalid(
            f"profile binding does not name the current profile family; "
            f"recomputed basis: {basis}"
        )
    if binding.get("basis") != basis:
        raise MappingInvalid(
            f"profile binding differs from recomputed profile basis: {basis}"
        )
    return basis


def reviewed_rules() -> dict[str, Any]:
    """Read the one authored correspondence authority, not a second feature map."""
    return cast(
        dict[str, Any],
        json.loads(
            (DATA / "semantic-rules.json").read_bytes(),
            object_pairs_hook=_unique_object,
        ),
    )


def _native_witnesses(rules: dict[str, Any], ipa: IPAFeatures) -> dict[str, Any]:
    results = {}
    for rule in rules["rules"]:
        form = ipa.read(rule["target"], strict=True)
        if len(form.units) != 1 or form.units[0].segment is None:
            raise MappingInvalid("native witness is not one segment")
        segment = form.units[0].segment
        structure = {
            "constituents": len(segment.constituents),
            "modifiers": sum(len(c.modifiers) for c in segment.constituents),
            "approach": sum(len(c.approach) for c in segment.constituents),
            "junctures": len(segment.junctures),
            "prosody": len(segment.prosody),
        }
        if identity_fingerprint(structure) != identity_fingerprint(
            rules["target_structure"]
        ):
            raise MappingInvalid("native witness structure changed")
        features = ipa._get_features(rule["target"])
        if any(features.get(k) != v for k, v in rule["target_predicates"].items()):
            raise MappingInvalid("native witness predicates changed")
        if "house_projection" in rule:
            projection = rule["house_projection"]
            if rule["disposition"] not in {
                "exact under stated conditions",
                "conditional/composite",
            }:
                raise MappingInvalid(
                    "house projection is not licensed by the rule disposition"
                )
            if (
                not isinstance(projection, list)
                or len(projection) != 1
                or not isinstance(projection[0], dict)
                or set(projection[0]) != {"house-symbol", "house-kind"}
                or projection[0]["house-symbol"] != rule["target"]
                or projection[0]["house-kind"] != "segment"
            ):
                raise MappingInvalid(
                    "house projection differs from the strict native witness"
                )
        results[rule["id"]] = {
            "structure": structure,
            "asserted_target_predicates": rule["target_predicates"],
            "additional_native_claims": {
                k: v for k, v in features.items() if k not in rule["target_predicates"]
            },
        }
    for rule in rules["declaration_rules"]:
        if "house_projection" in rule:
            raise MappingInvalid(
                "house projection is not licensed on a declaration rule"
            )
        target = rule["target"]
        witness = target["witness"]
        form = ipa.read(witness, strict=True)
        if len(form.units) != 1 or form.units[0].segment is None:
            raise MappingInvalid("declaration witness is not one segment")
        segment = form.units[0].segment
        if target["form"] == "feature":
            path = target["path"]
            if len(path) != 3 or path[0] != "ipakit" or len(segment.constituents) != 1:
                raise MappingInvalid("invalid native feature-value witness")
            if path[1] == "release":
                observed_value = segment.constituents[0].bundle(ipa).get(path[1])
                read = "constituent-bundle"
            elif path[1] == "length":
                values = ipa.feature_values(witness)
                observed_values = values.get(path[1])
                observed_value = (
                    observed_values[0]
                    if observed_values is not None and len(observed_values) == 1
                    else None
                )
                read = "feature_values"
            else:
                raise MappingInvalid("unsupported native feature witness family")
            if observed_value != path[2]:
                raise MappingInvalid("native feature-value witness changed")
            results[rule["id"]] = {
                "form": "feature",
                "target": path,
                "witness": witness,
                "constituents": 1,
                "read": read,
                "observed_value": observed_value,
            }
        elif target["form"] == "sequence":
            expected = target["constituents"]
            if len(segment.constituents) != len(expected):
                raise MappingInvalid("native release sequence structure changed")
            observed_junctures = [juncture.value for juncture in segment.junctures]
            if target["juncture"] != "unasserted" or observed_junctures != [
                target["witness_juncture"]
            ]:
                raise MappingInvalid("native release sequence juncture changed")
            observed_constituents = []
            for constituent, predicates in zip(
                segment.constituents, expected, strict=True
            ):
                bundle = constituent.bundle(ipa)
                if any(bundle.get(name) != value for name, value in predicates.items()):
                    raise MappingInvalid("native release sequence predicates changed")
                observed_constituents.append(predicates)
            results[rule["id"]] = {
                "form": "sequence",
                "name": target["name"],
                "witness": witness,
                "constituents": observed_constituents,
                "juncture": target["juncture"],
                "observed_junctures": observed_junctures,
            }
        else:
            raise MappingInvalid("unknown release target form")
    enhancement_ids: set[str] = set()
    for item in rules["enhancements"]:
        if set(item) != {
            "id",
            "gap_kind",
            "decision",
            "affected_source_declarations",
            "evidence",
            "native_construction_attempts",
            "reason",
            "consequence",
            *({"accepted_for"} if item.get("decision") == "accepted" else set()),
            *({"deciding_evidence"} if item.get("decision") == "deferred" else set()),
        }:
            raise MappingInvalid("invalid enhancement record fields")
        if item["id"] in enhancement_ids:
            raise MappingInvalid("duplicate enhancement id")
        enhancement_ids.add(item["id"])
        if item["gap_kind"] not in ENHANCEMENT_GAP_KINDS:
            raise MappingInvalid("unknown enhancement gap kind")
        if item["decision"] not in ENHANCEMENT_DECISIONS:
            raise MappingInvalid("unknown enhancement decision")
        if item.get("accepted_for") not in (None, "H"):
            raise MappingInvalid("accepted enhancement has unknown owner")
        if item["decision"] == "accepted" and item.get("accepted_for") != "H":
            raise MappingInvalid("accepted enhancement is not assigned to H")
        for field in ("affected_source_declarations", "evidence"):
            if (
                not isinstance(item[field], list)
                or not item[field]
                or not all(isinstance(value, str) and value for value in item[field])
            ):
                raise MappingInvalid(f"enhancement {field} must be non-empty text")
        if item["decision"] == "deferred" and not item.get("deciding_evidence"):
            raise MappingInvalid("deferred enhancement lacks deciding evidence")
        attempts = item["native_construction_attempts"]
        if not isinstance(attempts, list) or not attempts:
            raise MappingInvalid("enhancement lacks a native construction attempt")
        observed_attempts = []
        for attempt in attempts:
            if set(attempt) != {"witness", "expected", "distinction"}:
                raise MappingInvalid("invalid native construction attempt")
            if attempt["expected"] not in ("succeeds", "fails"):
                raise MappingInvalid("unknown native construction outcome")
            try:
                ipa.read(attempt["witness"], strict=True)
            except ValueError as exc:
                observed = "fails"
                detail = str(exc)
            else:
                observed = "succeeds"
                detail = "strict native construction succeeded"
            if observed != attempt["expected"]:
                raise MappingInvalid("native enhancement construction outcome changed")
            observed_attempts.append(
                {
                    "witness": attempt["witness"],
                    "distinction": attempt["distinction"],
                    "outcome": observed,
                    "detail": detail,
                }
            )
        if item["gap_kind"] == "model gap" and any(
            attempt["outcome"] != "fails" for attempt in observed_attempts
        ):
            raise MappingInvalid(
                "model gap is constructible by the strict native reader"
            )
        results[f"enhancement:{item['id']}"] = {
            "gap_kind": item["gap_kind"],
            "attempts": observed_attempts,
        }
    return results


def _native_phones(rules: dict[str, Any]) -> tuple[str, ...]:
    """Return every native spelling whose semantics bind this authority."""
    return tuple(rule["target"] for rule in rules["rules"]) + tuple(
        rule["target"]["witness"] for rule in rules["declaration_rules"]
    )


def _queues(census: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    if tuple(rules["disposition_classes"]) != DISPOSITION_CLASSES:
        raise MappingInvalid("reviewed disposition classes changed")
    valid_classes = set(DISPOSITION_CLASSES)
    for rule in [*rules["rules"], *rules["declaration_rules"]]:
        if rule["disposition"] == "exact under stated conditions" and not rule.get(
            "preconditions"
        ):
            raise MappingInvalid(
                "exact under stated conditions rule lacks preconditions"
            )
    supported: dict[tuple[str, ...], list[str]] = {}
    rule_classes: dict[str, str] = {}
    for rule in rules["rules"]:
        if rule["disposition"] not in valid_classes:
            raise MappingInvalid("unknown reviewed disposition class")
        rule_classes[rule["id"]] = rule["disposition"]
        for name, value in rule["source"].items():
            supported.setdefault(
                ("clts", rules["source_kind"], name, value), []
            ).append(rule["id"])
    declared = {tuple(row["source"]) for row in census["clts_to_ipakit"]}
    native = {tuple(row["source"]) for row in census["ipakit_to_clts"]}
    if not set(supported) <= declared:
        raise MappingInvalid(
            "reviewed source predicate is no longer declared/cataloged"
        )
    refusal_ids: set[str] = set()
    enhancements = {item["id"]: item for item in rules["enhancements"]}
    for refusal in rules.get("projection_refusals", []):
        if set(refusal) != {"id", "source", "code", "deferred_by"}:
            raise MappingInvalid("invalid projection refusal fields")
        if (
            not all(
                isinstance(refusal[field], str) and refusal[field]
                for field in ("id", "code", "deferred_by")
            )
            or refusal["id"] in refusal_ids
        ):
            raise MappingInvalid("invalid projection refusal identity")
        refusal_ids.add(refusal["id"])
        source = refusal["source"]
        if (
            not isinstance(source, list)
            or len(source) != 4
            or not all(isinstance(value, str) and value for value in source)
            or source[0] != "clts"
            or tuple(source) not in declared
        ):
            raise MappingInvalid("projection refusal source is not declared")
        enhancement = enhancements.get(refusal["deferred_by"])
        if (
            enhancement is None
            or enhancement.get("decision") != "deferred"
            or " / ".join(source)
            not in enhancement.get("affected_source_declarations", [])
        ):
            raise MappingInvalid(
                "projection refusal is not backed by its deferred enhancement"
            )
    for rule in rules["rules"]:
        if any(
            ("ipakit", name, value) not in native
            for name, value in rule["target_predicates"].items()
        ):
            raise MappingInvalid("reviewed target predicate is no longer declared")
    declaration_rules: dict[tuple[str, ...], dict[str, Any]] = {}
    for rule in rules["declaration_rules"]:
        if rule["disposition"] not in valid_classes:
            raise MappingInvalid("unknown reviewed disposition class")
        source = tuple(rule["source"])
        if source in declaration_rules:
            raise MappingInvalid("duplicate declaration rule")
        declaration_rules[source] = rule
        if source not in declared:
            raise MappingInvalid("reviewed declaration source is no longer declared")
        preconditions = rule.get("preconditions", {})
        if not isinstance(preconditions, dict):
            raise MappingInvalid("declaration preconditions must be an object")
        unknown = set(preconditions) - {"source", "host"}
        if unknown:
            raise MappingInvalid("unknown declaration precondition")
        if "source" in preconditions and preconditions["source"] != "asserted":
            raise MappingInvalid("unknown source precondition")
        host = preconditions.get("host", {})
        if not isinstance(host, dict) or ("host" in preconditions and not host):
            raise MappingInvalid("host precondition must state features")
        for feature, value in host.items():
            if (
                not isinstance(feature, str)
                or not isinstance(value, str)
                or ("clts", source[1], feature, value) not in declared
            ):
                raise MappingInvalid("unknown host precondition declaration")
        target = rule["target"]
        if target["form"] == "feature" and tuple(target["path"]) not in native:
            raise MappingInvalid("reviewed declaration target is no longer declared")
    queues: dict[str, Any] = {}
    for direction in ("clts_to_ipakit", "ipakit_to_clts"):
        records = []
        for row in census[direction]:
            witness_ids = (
                supported.get(tuple(row["source"]), [])
                if direction == "clts_to_ipakit"
                else []
            )
            declaration = (
                declaration_rules.get(tuple(row["source"]))
                if direction == "clts_to_ipakit"
                else None
            )
            ids = [*witness_ids, *([declaration["id"]] if declaration else [])]
            dispositions = {
                *[rule_classes[rule_id] for rule_id in witness_ids],
                *([declaration["disposition"]] if declaration else []),
            }
            records.append(
                {
                    **row,
                    "status": (
                        "conflicting"
                        if len(dispositions) > 1
                        else (
                            next(iter(dispositions))
                            if dispositions
                            else "unresolved pending evidence"
                        )
                    ),
                    "rule_ids": ids,
                    "targets": [declaration["target"]] if declaration else [],
                }
            )
        queues[direction] = records
    return queues


def _source_witnesses(rules: dict[str, Any], snapshot: Snapshot) -> None:
    entries = snapshot.to_data()["entries"]
    for rule in rules["rules"]:
        row = entries.get(rule["raw"])
        expected = {rules["source_kind"], *rule["source"].values()}
        if (
            row is None
            or row["kind"] != rules["source_kind"]
            or set(row["features"]) != expected
        ):
            raise MappingInvalid("complete source claims differ from reviewed witness")
        if row["canonical"] != rule["raw"]:
            raise MappingInvalid("source witness canonical spelling changed")


class MappingAuthority:
    """Content-bound correspondence authority for the bounded import adapter."""

    def __init__(self, data: dict[str, Any]) -> None:
        try:
            self._initialize(data)
        except MappingInvalid:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise MappingInvalid(f"invalid mapping authority: {exc}") from exc

    def _initialize(self, data: dict[str, Any]) -> None:
        data = json.loads(json.dumps(data, allow_nan=False))
        if set(data) != {
            "schema",
            "version",
            "identity",
            "bindings",
            "rules",
            "census",
            "dispositions",
            "native_witnesses",
        }:
            raise MappingInvalid("unexpected authority fields")
        if (
            data["schema"] != "ipakit-clts-semantic-authority"
            or type(data["version"]) is not int
            or data["version"] != 2
        ):
            raise MappingInvalid("unsupported authority version")
        if (
            identity_fingerprint({k: v for k, v in data.items() if k != "identity"})
            != data["identity"]
        ):
            raise MappingInvalid("mapping content identity mismatch")
        if identity_fingerprint(data["rules"]) != identity_fingerprint(
            reviewed_rules()
        ):
            raise MappingInvalid("reviewed rule authority changed")
        if data["bindings"]["source_policy"] != identity_fingerprint(source_policy()):
            raise MappingInvalid("source policy changed")
        pin = source_policy()
        if (
            data["bindings"]["source_inputs"] != pin["inputs"]
            or data["bindings"]["source_metadata"] != pin["source"]
        ):
            raise MappingInvalid("source identity receipt differs from accepted policy")
        _require_profile_binding(data["rules"])
        validate_declaration_census(data["census"])
        for name, actual in data["census"]["sources"]["clts"].items():
            if pin["inputs"].get(name) != actual:
                raise MappingInvalid(
                    f"census source input differs from accepted policy: {name}"
                )
        if "catalog" in data["census"]:
            raise MappingInvalid(
                "catalog research payload is not admitted in shipped mapping authority"
            )
        if identity_fingerprint(data["dispositions"]) != identity_fingerprint(
            _queues(data["census"], data["rules"])
        ):
            raise MappingInvalid("declaration dispositions do not reconcile")
        self._json = (
            json.dumps(
                data, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2
            )
            + "\n"
        )
        self.validate_context(data["census"], read_snapshot(), load_ipa_features())

    @property
    def identity(self) -> str:
        return str(self.to_data()["identity"])

    def to_data(self) -> dict[str, Any]:
        """Return a detached JSON view; caller edits cannot alter authority."""
        return json.loads(self._json)  # type: ignore[no-any-return]

    def dumps(self) -> str:
        """Serialize the mapping artifact, not a graph representation."""
        return self._json

    def validate_context(
        self, census: dict[str, Any], snapshot: Snapshot, ipa: IPAFeatures
    ) -> None:
        """Refuse stale declarations, geometry and provider artifact identity."""
        data = self.to_data()
        phones = _native_phones(data["rules"])
        if identity_fingerprint(census) != identity_fingerprint(data["census"]):
            raise MappingInvalid(
                "declaration population or source inputs changed; reconcile first"
            )
        if snapshot.identity != data["bindings"]["snapshot"]:
            raise MappingInvalid("source artifact identity changed")
        if metric_fingerprint(ipa, phones) != data["bindings"]["native_metric"]:
            raise MappingInvalid("effective native geometry changed")
        if (
            hashlib.sha256(ipa.xml_path.read_bytes()).hexdigest()
            != census["sources"]["ipakit"]["ipa.xml"]
        ):
            raise MappingInvalid("native declaration source changed")
        if identity_fingerprint(
            _native_witnesses(data["rules"], ipa)
        ) != identity_fingerprint(data["native_witnesses"]):
            raise MappingInvalid("native witness claims changed")
        _source_witnesses(data["rules"], snapshot)

    def eligibility(
        self,
        token: str,
        snapshot: Snapshot,
        *,
        direction: str = "clts-to-ipakit",
        profile: Any = None,
    ) -> dict[str, Any]:
        """Return finite complete-claim eligibility, not a projected Form."""
        data = self.to_data()
        self.validate_context(data["census"], snapshot, load_ipa_features())
        if snapshot.identity != data["bindings"]["snapshot"]:
            raise MappingInvalid("source artifact identity changed")
        if direction != data["rules"]["direction"]:
            raise MappingInvalid("no reviewed inverse direction")
        matches = [r for r in data["rules"]["rules"] if r["raw"] == token]
        result: dict[str, Any] = {
            "token": token,
            "mapping_identity": self.identity,
            "source_identity": snapshot.identity,
            "status": "unresolved",
            "rule_id": None,
            "target": None,
            "import_ready": False,
            "losses": [],
            "reason": "import-profile-not-supplied",
            "projection": None,
        }
        if len(matches) > 1:
            raise MappingInvalid("conflicting eligibility rules")
        if matches:
            _source_witnesses(data["rules"], snapshot)
            rule = matches[0]
            result.update(
                status="eligible-witness",
                rule_id=rule["id"],
                target=rule["target"],
            )
        if profile is None:
            return result
        self.require_import_profile(profile)
        projection = self._projection_record(token, snapshot, profile)
        result["projection"] = projection
        if projection["status"] == "supported":
            result.update(import_ready=True, reason="reviewed-house-projection")
        elif projection["status"] == "unsupported":
            result["reason"] = projection["code"]
        else:
            result["reason"] = "not-attempted"
        return result

    def _projection_record(
        self, token: str, snapshot: Snapshot, profile: Any
    ) -> dict[str, Any]:
        """Derive one projection after the caller has validated the full context."""
        rules = self.to_data()["rules"]
        entry = snapshot.to_data()["entries"].get(token)
        record: dict[str, Any] = {"mapping": profile.mapping_identity}
        if entry is None:
            return {**record, "status": "not-attempted"}
        token_rules = [rule for rule in rules["rules"] if rule["raw"] == token]
        refusals = [
            refusal
            for refusal in rules.get("projection_refusals", [])
            if entry["kind"] == refusal["source"][1]
            and refusal["source"][3] in entry["features"]
        ]
        if len(token_rules) > 1 or len(refusals) > 1 or (token_rules and refusals):
            raise MappingInvalid("conflicting projection rules and refusals")
        if token_rules and token_rules[0].get("house_projection") is not None:
            return {
                **record,
                "status": "supported",
                "facts": json.loads(json.dumps(token_rules[0]["house_projection"])),
            }
        if refusals:
            return {**record, "status": "unsupported", "code": refusals[0]["code"]}
        return {
            **record,
            "status": "unsupported",
            "code": "outside-reviewed-token-context",
        }

    def _projection_records(
        self, tokens: Sequence[str], snapshot: Snapshot, profile: Any
    ) -> tuple[dict[str, Any], ...]:
        """Derive a batch while validating its source and profile context once."""
        data = self.to_data()
        self.validate_context(data["census"], snapshot, load_ipa_features())
        self.require_import_profile(profile)
        return tuple(
            self._projection_record(token, snapshot, profile) for token in tokens
        )

    def declaration_target(
        self, source: Sequence[str], token: str, snapshot: Snapshot
    ) -> dict[str, Any]:
        """Return one declaration target only when its occurrence conditions hold."""
        source = tuple(source)
        if len(source) != 4 or source[:1] != ("clts",):
            raise MappingInvalid("invalid qualified declaration source")
        rules = self.to_data()["rules"]["declaration_rules"]
        matches = [rule for rule in rules if tuple(rule["source"]) == source]
        if len(matches) != 1:
            raise MappingInvalid("declaration has no unique reviewed rule")
        entry = snapshot.to_data()["entries"].get(token)
        if (
            entry is None
            or entry["kind"] != source[1]
            or source[3] not in entry["features"]
        ):
            raise MappingInvalid("source occurrence does not assert the declaration")
        rule = matches[0]
        for condition, value in rule.get("preconditions", {}).items():
            if condition == "source":
                if value != "asserted":
                    raise MappingInvalid("unknown source precondition")
                if source[3] not in entry["features"]:
                    raise MappingInvalid(
                        "source occurrence does not assert the declaration"
                    )
            elif condition == "host":
                for feature, feature_value in value.items():
                    if feature_value not in entry["features"]:
                        raise MappingInvalid(
                            "declaration target requires host "
                            f"{feature}={feature_value}"
                        )
            else:
                raise MappingInvalid("unknown declaration precondition")
        return cast(dict[str, Any], json.loads(json.dumps(rule["target"])))

    def _require_profile_basis(self, spec: Any) -> None:
        from ._clts_profile import profile_basis

        actual = profile_basis(spec)
        expected = self.to_data()["rules"]["profile_binding"]["basis"]
        if actual != expected:
            raise MappingInvalid(
                f"source profile basis mismatch; recomputed basis: {actual}"
            )

    def require_import_profile(self, spec: Any) -> None:
        """Require the reviewed mapping, final manifest and complete profile basis."""
        from ._clts_profile import SourceProfileSpec, require_final_manifest

        if not isinstance(spec, SourceProfileSpec):
            raise MappingInvalid("import profile must be a SourceProfileSpec")
        try:
            require_final_manifest(spec)
        except ValueError as error:
            raise MappingInvalid(str(error)) from error
        if spec.mapping_identity != self.identity:
            raise MappingInvalid("source profile mapping identity mismatch")
        self._require_profile_basis(spec)

    def gap_report(self) -> str:
        """Derive one deterministic report, not another classification source."""
        data = self.to_data()
        lines = [
            "# CLTS semantic correspondence — bounded initial authority",
            "",
            f"Mapping identity: `{self.identity}`.",
            "",
            "Finite declaration accounting is not complete semantic conversion. "
            "Reviewed token projections are bound to the source profile; public import accepts the plain-stop domain and otherwise reports refusal or preservation.",
            "",
            "Generated from the [reviewed mapping authority](clts-mapping.md). "
            "Only master declarations are included; catalog observations remain external research. "
            "CLTS master declarations are CC BY 4.0; see the [mapping notice](../ipakit/data/clts/MAPPING-NOTICE.txt), [source policy](../ipakit/data/clts/source.json) "
            "and [CLTS audit](clts-audit.md). Native declarations retain their repository license.",
            "",
            "| Direction | Qualified declaration | Disposition | Witness rules |",
            "| --- | --- | --- | --- |",
        ]
        for direction, records in data["dispositions"].items():
            for row in records:
                lines.append(
                    f"| {direction} | {' / '.join(row['source'])} | {row['status']} | {', '.join(row['rule_ids'])} |"
                )
        lines.extend(
            [
                "",
                "## Release adjudication",
                "",
                data["rules"]["release_adjudication"],
                "",
            ]
        )
        for rule in data["rules"]["declaration_rules"]:
            target = rule["target"]
            rendered = (
                " / ".join(target["path"])
                if target["form"] == "feature"
                else f"{target['name']} (`{target['witness']}`)"
            )
            lines.append(
                f"- `{' / '.join(rule['source'])}` → {rendered} ({rule['id']})."
            )
        lines.extend(["", "## Projection refusals", ""])
        for refusal in data["rules"].get("projection_refusals", []):
            lines.append(
                f"- `{' / '.join(refusal['source'])}` → `{refusal['code']}` "
                f"({refusal['id']}; deferred by `{refusal['deferred_by']}`)."
            )
        enhancements = data["rules"]["enhancements"]
        for heading, selected in (
            (
                "Accepted for lane H",
                [item for item in enhancements if item["decision"] == "accepted"],
            ),
            (
                "Other structural and enhancement dispositions",
                [item for item in enhancements if item["decision"] != "accepted"],
            ),
        ):
            lines.extend(["", f"## {heading}", ""])
            for item in selected:
                attempts = "; ".join(
                    f"`{attempt['witness']}` {attempt['expected']} ({attempt['distinction']})"
                    for attempt in item["native_construction_attempts"]
                )
                lines.append(
                    f"- `{item['id']}` — {item['gap_kind']}; {item['decision']}. "
                    f"{item['reason']} {item['consequence']} "
                    f"Evidence: {' '.join(item['evidence'])} "
                    f"Native construction: {attempts}."
                )
                if item["decision"] == "deferred":
                    lines.append(f"  Deciding evidence: {item['deciding_evidence']}")
        lines.extend(
            [
                "",
                "Other gaps remain unresolved; labels or strict segment refusals do not prove house inexpressibility.",
                "",
            ]
        )
        return "\n".join(lines)


def build_authority(
    root: Path, *, snapshot: Snapshot | None = None, ipa: IPAFeatures | None = None
) -> MappingAuthority:
    """Validate pinned inputs and construct the bounded authority without writing."""
    snapshot = snapshot or read_snapshot()
    rules = reviewed_rules()
    _require_profile_binding(rules, snapshot)
    source = validate_source(root)
    census = declaration_audit(root, include_catalog=False)
    ipa = ipa or load_ipa_features()
    _source_witnesses(rules, snapshot)
    native = _native_witnesses(rules, ipa)
    phones = _native_phones(rules)
    data = {
        "schema": "ipakit-clts-semantic-authority",
        "version": 2,
        "bindings": {
            "source_policy": identity_fingerprint(source_policy()),
            "source_metadata": source.metadata.to_dict(),
            "source_inputs": dict(source.digests),
            "snapshot": snapshot.identity,
            "native_metric": metric_fingerprint(ipa, phones),
        },
        "rules": rules,
        "census": census,
        "dispositions": _queues(census, rules),
        "native_witnesses": native,
    }
    data["identity"] = identity_fingerprint(data)
    return MappingAuthority(data)


def read_authority(path: Path | None = None) -> MappingAuthority:
    """Restore a frozen authority offline and revalidate current provider bindings."""
    return MappingAuthority(
        json.loads(
            (path or DATA / "semantic-mapping.json").read_bytes(),
            object_pairs_hook=_unique_object,
        )
    )


def build_mapping_artifacts(
    root: Path, *, snapshot: Snapshot | None = None
) -> BuildResult:
    """Explicit development output using the shared artifact-build contract."""
    authority = build_authority(root, snapshot=snapshot)
    path = Path("ipakit/data/clts/semantic-mapping.json")
    report = Path("docs/clts-gaps.md")
    return BuildResult(
        {path: authority.dumps().encode(), report: authority.gap_report().encode()},
        (path, report),
        validate_source(root),
    )
