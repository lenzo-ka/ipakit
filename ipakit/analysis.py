"""Analysis mixin for IPAFeatures - describe, natural_class, minimal_pairs."""

from __future__ import annotations

from ._base import IPAFeaturesBase
from ._convert import longest_match
from .constants import METADATA_ATTRS, TIE_BAR

# Feature ordering for description generation (most salient first)
_CONSONANT_DESC_ORDER = ["voiced", "place", "manner"]
_VOWEL_DESC_ORDER = ["height", "backness", "rounded"]

# Features to skip in descriptions (implied or structural)
_SKIP_FEATURES = {"class", "href", "xsampa", "airstream"}

# Binary feature labels for descriptions
_BINARY_LABELS: dict[str, dict[str, str | None]] = {
    "voiced": {"+": "voiced", "-": "voiceless"},
    "rounded": {"+": "rounded", "-": "unrounded"},
    "lateral": {"+": "lateral", "-": None},
    "retroflex": {"+": "retroflex", "-": None},
    "nasalized": {"+": "nasalized", "-": None},
    "syllabic": {"+": "syllabic", "-": None},
}


class AnalysisMixin(IPAFeaturesBase):
    """Mixin providing phonetic analysis functions."""

    def describe(self, phone: str, with_defaults: bool = True) -> str:
        """Generate human-readable IPA description for a phone.

        Examples:
            describe("p") → "voiceless bilabial plosive"
            describe("ɛ") → "open-mid front unrounded vowel"
            describe("t͡ʃ") → "voiceless postalveolar affricate"
            describe("l") → "voiced alveolar lateral approximant"
        """
        feats = self.get_features(phone, with_defaults=with_defaults)
        if not feats:
            return f"unknown phone: {phone}"

        manner = feats.get("manner", "")
        parts = []

        if manner == "vowel":
            # Vowel: height backness [rounded] vowel
            if height := feats.get("height"):
                parts.append(height)
            if backness := feats.get("backness"):
                parts.append(backness)
            # Rounded/unrounded
            if (rounded := feats.get("rounded")) and rounded in _BINARY_LABELS[
                "rounded"
            ]:
                if label := _BINARY_LABELS["rounded"][rounded]:
                    parts.append(label)
            parts.append("vowel")
        elif manner == "silence":
            return "silence"
        else:
            # Consonant: voiced/voiceless [modifiers] place manner
            # Voicing
            if (voiced := feats.get("voiced")) and voiced in _BINARY_LABELS["voiced"]:
                if label := _BINARY_LABELS["voiced"][voiced]:
                    parts.append(label)

            # Modifiers (lateral, retroflex, etc.)
            for feat in ["retroflex", "lateral", "nasalized"]:
                if (val := feats.get(feat)) and val == "+":
                    if label := _BINARY_LABELS.get(feat, {}).get("+"):
                        parts.append(label)

            # Place
            if place := feats.get("place"):
                parts.append(place)

            # Manner
            if manner:
                parts.append(manner)

            # Airstream (if not pulmonic)
            if (airstream := feats.get("airstream")) and airstream != "pulmonic":
                parts.append(airstream)

        return " ".join(parts)

    def natural_class(
        self,
        phones: list[str],
        with_defaults: bool = True,
        exclude_features: set[str] | None = None,
    ) -> dict[str, str]:
        """Find features shared by all phones in a set (natural class).

        Returns the intersection of features that all phones share.

        Examples:
            natural_class(["p", "t", "k"]) → {"manner": "plosive", "voiced": "-"}
            natural_class(["i", "e", "ɛ"]) → {"manner": "vowel", "backness": "front"}

        Args:
            phones: List of IPA phone symbols
            with_defaults: Include default feature values
            exclude_features: Features to exclude from result (default: class, href, xsampa)
        """
        if not phones:
            return {}

        exclude = exclude_features or set(METADATA_ATTRS)

        # Get features for all phones
        all_feats = [self.get_features(p, with_defaults=with_defaults) for p in phones]

        # Filter out phones not found
        all_feats = [f for f in all_feats if f]
        if not all_feats:
            return {}

        # Find intersection: features present in ALL phones with same value
        shared = {}
        first = all_feats[0]

        for feat, value in first.items():
            if feat in exclude:
                continue
            if all(f.get(feat) == value for f in all_feats[1:]):
                shared[feat] = value

        return shared

    def minimal_pairs(
        self,
        phone: str,
        with_defaults: bool = True,
        max_distance: float = 0.3,
    ) -> list[tuple[str, str, str | None]]:
        """Find phones that differ by approximately one feature (minimal pairs).

        Returns list of (phone, differing_feature, differing_value) tuples,
        sorted by phonetic distance.

        Examples:
            minimal_pairs("p") → [("b", "voiced", "+"), ("t", "place", "alveolar"), ...]
            minimal_pairs("i") → [("y", "rounded", "+"), ("ɪ", "height", "near-close"), ...]

        Args:
            phone: The reference phone
            with_defaults: Include default feature values in comparison
            max_distance: Maximum distance to consider (default 0.3 ≈ 1-2 features)
        """
        ref_feats = self.get_features(phone, with_defaults=with_defaults)
        if not ref_feats:
            return []

        results = []
        for candidate in self.phones:
            if candidate == phone:
                continue

            cand_feats = self.get_features(candidate, with_defaults=with_defaults)
            if not cand_feats:
                continue

            # Calculate distance
            dist = self.distance(phone, candidate)
            if dist > max_distance:
                continue

            # Find the differing features
            diffs = []
            for feat in ref_feats:
                if feat in METADATA_ATTRS:
                    continue
                ref_val = ref_feats.get(feat)
                cand_val = cand_feats.get(feat)
                if ref_val != cand_val:
                    diffs.append((feat, cand_val))

            # Only include if there are 1-2 differences
            if 1 <= len(diffs) <= 2:
                # Report the primary difference
                primary_feat, primary_val = diffs[0]
                results.append((candidate, primary_feat, primary_val, dist))

        # Sort by distance, then alphabetically
        results.sort(key=lambda x: (x[3], x[0]))

        # Return without the distance
        return [(p, f, v) for p, f, v, _ in results]

    def nearest_phones(
        self,
        phone: str,
        n: int = 10,
        with_defaults: bool = True,
    ) -> list[tuple[str, float]]:
        """Find the n nearest phones by phonetic distance.

        Returns list of (phone, distance) tuples sorted by distance.

        Args:
            phone: The reference phone
            n: Maximum number of results
            with_defaults: Include default feature values in comparison
        """
        if phone not in self.phones:
            return []

        distances = []
        for candidate in self.phones:
            if candidate == phone:
                continue
            dist = self.distance(phone, candidate)
            distances.append((candidate, dist))

        distances.sort(key=lambda x: (x[1], x[0]))
        return distances[:n]

    def validate_ipa(
        self,
        ipa: str,
        strict: bool = False,
    ) -> list[dict[str, str]]:
        """Validate an IPA string for well-formedness.

        Checks for:
        - Unknown symbols (not in phones, diacritics, or suprasegmentals)
        - Orphan diacritics (diacritic without preceding base phone)
        - Malformed tie bars (tie bar without phones on both sides)
        - Duplicate diacritics on the same segment

        Returns a list of issue dicts with keys:
        - type: "error" or "warning"
        - code: machine-readable issue code
        - message: human-readable description
        - position: character index in the string
        - symbol: the problematic symbol (if applicable)

        Examples:
            validate_ipa("kæt")     # [] (valid)
            validate_ipa("kæt̪")     # [] (valid - dental diacritic on t)
            validate_ipa("k4t")     # [{"type": "error", "code": "unknown_symbol", ...}]  ('x','y','z' are valid IPA)
            validate_ipa("̃a")       # [{"type": "error", "code": "orphan_diacritic", ...}]

        Args:
            ipa: The IPA string to validate
            strict: If True, treat warnings as errors
        """
        issues: list[dict[str, str]] = []
        ipa = self.expand_ligatures(ipa)

        # Known symbols
        known_phones = set(self.phones)
        known_diacritics = {
            s
            for s, p in self.diacritics.items()
            if p.features.get("class") == "diacritic"
        }
        suprasegmentals = {
            s
            for s, p in self.diacritics.items()
            if p.features.get("class") == "suprasegmental"
        }
        # Stress, length, tone, breaks, separators, and space stand alone (no
        # base phone required). The tie bar is a suprasegmental but checked below.
        standalone = (suprasegmentals | set(self.separators) | {" "}) - {TIE_BAR}

        i = 0
        last_was_phone = False
        current_segment_diacritics: set[str] = set()

        while i < len(ipa):
            char = ipa[i]

            # Try to match multi-character phones first (affricates, etc.)
            matched_phone, matched_len = longest_match(
                ipa, i, known_phones, 6, tie_set=known_phones
            )

            if matched_phone:
                # Valid phone found
                last_was_phone = True
                current_segment_diacritics = set()
                i += matched_len
                continue

            # Standalone symbols (stress, length, tone, breaks, separators)
            if char in standalone:
                # These are valid on their own or after phones
                last_was_phone = False
                current_segment_diacritics = set()
                i += 1
                continue

            # Check for diacritics (modifiers that require a base phone)
            if char in known_diacritics:
                if not last_was_phone:
                    issues.append(
                        {
                            "type": "error",
                            "code": "orphan_diacritic",
                            "message": f"Diacritic '{char}' without preceding base phone",
                            "position": str(i),
                            "symbol": char,
                        }
                    )
                elif char in current_segment_diacritics:
                    issues.append(
                        {
                            "type": "warning",
                            "code": "duplicate_diacritic",
                            "message": f"Duplicate diacritic '{char}' on same segment",
                            "position": str(i),
                            "symbol": char,
                        }
                    )
                else:
                    current_segment_diacritics.add(char)
                i += 1
                continue

            # Check for tie bar
            if char == TIE_BAR:
                # Tie bar should be between phones - check context
                if i == 0 or i == len(ipa) - 1:
                    issues.append(
                        {
                            "type": "error",
                            "code": "malformed_tie",
                            "message": "Tie bar at string boundary",
                            "position": str(i),
                            "symbol": char,
                        }
                    )
                i += 1
                continue

            # Unknown symbol
            issues.append(
                {
                    "type": "error",
                    "code": "unknown_symbol",
                    "message": f"Unknown symbol '{char}' (U+{ord(char):04X})",
                    "position": str(i),
                    "symbol": char,
                }
            )
            last_was_phone = False
            i += 1

        # If strict mode, upgrade warnings to errors
        if strict:
            for issue in issues:
                if issue["type"] == "warning":
                    issue["type"] = "error"

        return issues

    def is_valid_ipa(self, ipa: str) -> bool:
        """Check if an IPA string is valid (no errors).

        Returns True if the string has no validation errors.
        Warnings are allowed.
        """
        issues = self.validate_ipa(ipa)
        return not any(issue["type"] == "error" for issue in issues)
