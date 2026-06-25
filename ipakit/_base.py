"""Shared base for IPAFeatures mixins.

The mixins (Analysis/Distance/Hierarchy/Validation) call attributes and methods
that live on the concrete ``IPAFeatures`` class or on sibling mixins. Inheriting
this base lets a type checker resolve those references without each mixin
annotating ``self`` as ``IPAFeatures`` (which strict mypy rejects, since the
erased self type must be a supertype of the defining class).

At runtime these declarations are inert: ``IPAFeatures`` and the mixins override
every member below, so the stub bodies are never executed.
"""

from __future__ import annotations

from .models import Feature, Phone, Phoneset


class IPAFeaturesBase:
    """Declares the cross-mixin surface of ``IPAFeatures`` for type checking."""

    # Data populated by IPAFeatures._load()
    phones: dict[str, Phone]
    diacritics: dict[str, Phone]
    features: dict[str, Feature]

    @property
    def feature_order(self) -> list[str]:
        raise NotImplementedError

    @property
    def consonant_manners(self) -> frozenset[str]:
        raise NotImplementedError

    def get_features(self, phone: str, with_defaults: bool = True) -> dict[str, str]:
        raise NotImplementedError

    def expand_ligatures(self, ipa: str) -> str:
        raise NotImplementedError

    def compose(
        self,
        segment: str,
        with_defaults: bool = True,
        phoneset: Phoneset | None = None,
    ) -> list[dict[str, str]]:
        raise NotImplementedError

    def tokenize_ipa(self, ipa: str, phoneset: Phoneset | None = None) -> list[str]:
        raise NotImplementedError

    def distance(self, phone1: str, phone2: str) -> float:
        raise NotImplementedError
