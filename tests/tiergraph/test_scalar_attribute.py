"""A scalar attribute reads as its lexical form; a JSON value is refused by name."""

import pytest
from ipakit._scalar_attribute import scalar_lexical

import tiergraph as tg

NAME = tg.QualifiedName("urn:ipakit-test", "stress")


def test_a_scalar_attribute_reads_as_its_lexical_form():
    value = tg.AttributeValue(NAME, tg.XsdType.INTEGER, "1")
    assert scalar_lexical(value) == "1"


@pytest.mark.parametrize("payload", [1, "1", None, [1], {"level": 1}])
def test_a_json_value_where_a_scalar_is_read_is_refused_by_name(payload):
    with pytest.raises(TypeError, match="'stress' holds a JSON value"):
        scalar_lexical(tg.JsonAttributeValue(NAME, payload))
