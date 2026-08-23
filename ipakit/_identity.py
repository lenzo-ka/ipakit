"""Model-independent canonical-identity fingerprinting.

A stable hash over an arbitrary provider's canonical JSON identity, used to
version corpus declarations, experiments, and feature providers. It carries no
graph or wire representation, so it is independent of the graph engine and its
serialization.
"""

from __future__ import annotations

import hashlib
import json


def identity_fingerprint(identity: object) -> str:
    """Fingerprint a declaration provider's canonical JSON identity."""
    payload = json.dumps(
        identity,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
