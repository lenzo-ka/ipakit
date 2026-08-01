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
    separators: dict[str, Phone]
    zeros: dict[str, Phone]
    features: dict[str, Feature]
    lookalikes: dict[str, str]
    # <notations>: symbol -> the convention it comes from, and the one an
    # unlisted symbol belongs to. Read through `notation_of`.
    notations: dict[str, str]
    default_notation: str
    # The declared mode vocabulary: declaration order is precedence, and
    # `default_mode` is the mode a mark falls to when none of its keys is
    # claimed. `modifier_mode` reads these, and it takes this base so the
    # mixins can call it on `self`.
    modes: list[str]
    default_mode: str

    @property
    def feature_order(self) -> list[str]:
        raise NotImplementedError

    @property
    def features_by_mode(self) -> dict[str, frozenset[str]]:
        raise NotImplementedError

    @property
    def consonant_manners(self) -> frozenset[str]:
        raise NotImplementedError

    @property
    def stress_markers(self) -> dict[str, int]:
        raise NotImplementedError

    @property
    def stress_to_marker(self) -> dict[int, str]:
        raise NotImplementedError

    @property
    def syllable_break(self) -> str:
        raise NotImplementedError

    @property
    def carries_no_segment(self) -> frozenset[str]:
        raise NotImplementedError

    @property
    def tie_marks(self) -> dict[str, str]:
        raise NotImplementedError

    @property
    def tie_bar(self) -> str:
        raise NotImplementedError

    @property
    def seq_tie(self) -> str:
        raise NotImplementedError

    @property
    def tie_bars(self) -> frozenset[str]:
        raise NotImplementedError

    def feature_applies(self, feature: str, bundle: dict[str, str]) -> bool:
        raise NotImplementedError

    def get_features(self, phone: str, with_defaults: bool = True) -> dict[str, str]:
        raise NotImplementedError

    def expand_ligatures(self, ipa: str) -> str:
        raise NotImplementedError

    def canonicalize_unicode(self, text: str) -> str:
        raise NotImplementedError

    def notation_of(self, symbol: str) -> str:
        raise NotImplementedError

    def compose(
        self,
        segment: str,
        with_defaults: bool = True,
        phoneset: Phoneset | None = None,
    ) -> list[dict[str, str]]:
        raise NotImplementedError

    def tokenize(
        self,
        ipa: str,
        phoneset: Phoneset | None = None,
        strict: bool = False,
    ) -> list[str]:
        raise NotImplementedError

    def distance(self, phone1: str, phone2: str) -> float:
        raise NotImplementedError
