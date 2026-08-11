"""Base kind for external inventory providers."""

from .base import Bridge


class ProviderBridge(Bridge):
    """A bridge that supplies declared inventories."""
