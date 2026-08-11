"""Base kind for provenance-marked form generators."""

from .base import Bridge


class GeneratorDoor(Bridge):
    """A generator door whose output provenance remains visible."""
