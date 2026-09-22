"""Read a tiergraph attribute that ipakit declares as a scalar.

tiergraph carries two kinds of attribute value: a scalar with a lexical
spelling, and a JSON value. Every attribute ipakit reads by its lexical form
is one ipakit declares as a scalar, so a JSON value in that position is a graph
ipakit did not write, and is refused by name rather than read.
"""

from __future__ import annotations

import tiergraph as tg


def scalar_lexical(value: tg.AttributeValue | tg.JsonAttributeValue) -> str:
    """Return the lexical form of a scalar attribute; refuse a JSON value."""
    if isinstance(value, tg.JsonAttributeValue):
        raise TypeError(
            f"attribute {value.name.local_name!r} holds a JSON value where "
            f"ipakit reads a scalar"
        )
    return value.lexical
