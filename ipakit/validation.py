"""Validation and statistics mixin for IPAFeatures."""

from __future__ import annotations

from collections import Counter
from typing import Any

from ._base import IPAFeaturesBase
from .constants import METADATA_ATTRS


class ValidationMixin(IPAFeaturesBase):
    """Mixin providing validation and statistics methods."""

    def validate(self) -> list[str]:
        """Validate phones against feature definitions."""
        errors = []
        undeclared: set[str] = set()

        for symbol, phone in self.phones.items():
            manner = phone.features.get("manner")

            for feat, value in phone.features.items():
                if feat in METADATA_ATTRS:  # Skip structural metadata
                    continue
                if feat not in self.features and feat != "manner":
                    undeclared.add(feat)
                    continue
                if feat in self.features and value not in self.features[feat].values:
                    errors.append(
                        f"Invalid value '{value}' for feature '{feat}' in phone '{symbol}'"
                    )

            if manner in self.consonant_manners and "place" not in phone.features:
                errors.append(f"Missing 'place' for consonant '{symbol}'")
            if manner == "vowel":
                if "height" not in phone.features:
                    errors.append(f"Missing 'height' for vowel '{symbol}'")
                if "backness" not in phone.features:
                    errors.append(f"Missing 'backness' for vowel '{symbol}'")

        for feat in sorted(undeclared):
            n = sum(1 for p in self.phones.values() if feat in p.features)
            errors.append(f"Undeclared feature '{feat}' used by {n} phones")

        return errors

    def feature_counts(self) -> dict[str, dict[str, int]]:
        """Count occurrences of each feature value across phones."""
        counts: dict[str, Counter[str]] = {name: Counter() for name in self.features}
        for phone in self.phones.values():
            for feat, value in phone.features.items():
                if feat in counts:
                    counts[feat][value] += 1
        return {k: dict(v) for k, v in counts.items()}

    def feature_usage(self) -> dict[str, int]:
        """Count how many phones specify each feature (explicitly)."""
        counts = {name: 0 for name in self.features}
        for phone in self.phones.values():
            for feat in phone.features:
                if feat in counts:
                    counts[feat] += 1
        return counts

    def summary(self) -> dict[str, Any]:
        """Generate summary statistics."""
        manner_counts = Counter(p.features.get("manner") for p in self.phones.values())
        return {
            "feature_counts": self.feature_counts(),
            "feature_usage": self.feature_usage(),
            "manner_distribution": dict(manner_counts),
            "n_diacritics": len(self.diacritics),
            "n_features": len(self.features),
            "n_phones": len(self.phones),
        }
