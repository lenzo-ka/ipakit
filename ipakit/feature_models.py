"""Named shipped feature declarations, without optional provider packages.

These are finite model resources, not house notation styles. Explicit external
paths remain supported by :func:`read_ternary_declaration` itself.
"""

from pathlib import Path

from .constants import DATA_DIR
from .finite_declaration import TernaryDeclaration, read_ternary_declaration

DATA = DATA_DIR / "feature-models"


def available() -> tuple[str, ...]:
    """Name the packaged declarations, without importing their producers."""
    return tuple(sorted(path.stem for path in DATA.glob("*.xml")))


def resource_path(name: str) -> Path:
    """Resolve a declared name, refusing paths and unknown model names."""
    if name not in available():
        raise ValueError(
            f"unknown shipped feature model {name!r}; available: {', '.join(available())}; "
            "use read_ternary_declaration(path) for a supplied declaration"
        )
    return DATA / f"{name}.xml"


def read(name: str) -> TernaryDeclaration:
    """Read one named model through the existing validated ternary codec."""
    return read_ternary_declaration(resource_path(name))
