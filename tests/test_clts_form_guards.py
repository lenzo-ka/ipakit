"""CLTS source-profile admission and the shared downstream guard."""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import ipakit
import pytest
from ipakit import textgrid
from ipakit.align import align_entry
from ipakit.bridges.mfa import MFABridge
from ipakit.clts import import_tokens
from ipakit.disagreement import DisagreementSpread, ProvenancedForm
from ipakit.form import Form, FormProjectionError
from ipakit.rules import RuleSet, parse
from ipakit.syllable import syllabify
from ipakit.tract import trajectory


def _source_form(*tokens: str) -> Form:
    result = import_tokens(list(tokens), unsupported="preserve")
    assert result.graph is not None
    return Form.from_dict(result.to_data()["form"])


@pytest.fixture(scope="module")
def complete() -> Form:
    return _source_form("p")


@pytest.fixture(scope="module")
def incomplete() -> Form:
    return _source_form("p", "a")


def test_source_profile_identity_and_native_persistence(
    complete: Form, incomplete: Form
) -> None:
    complete_again = Form.from_json(complete.to_json())
    incomplete_again = Form.from_json(incomplete.to_json())

    assert complete == complete_again
    assert hash(complete) == hash(complete_again)
    assert incomplete == incomplete_again
    assert hash(incomplete) == hash(incomplete_again)
    assert complete != ipakit.read("p")
    assert incomplete != _source_form("p", "ts")
    assert incomplete.to_dict() == incomplete_again.to_dict()
    assert "digraph" in incomplete.to_dot()
    assert "_source_profile_document" not in complete.__dict__


Consumer = Callable[[Form], Any]


CONSUMERS: tuple[Any, ...] = (
    pytest.param(lambda form: form.to_ipa(), id="to-ipa-exact"),
    pytest.param(lambda form: form.to_ipa("canonical"), id="to-ipa-canonical"),
    pytest.param(lambda form: form.units, id="units"),
    pytest.param(lambda form: form.intervals, id="intervals"),
    pytest.param(lambda form: form.segments, id="segments"),
    pytest.param(lambda form: form.phones, id="phones"),
    pytest.param(lambda form: form.attributes, id="attributes"),
    pytest.param(lambda form: form.boundaries, id="boundaries"),
    pytest.param(lambda form: form.tree(), id="tree"),
    pytest.param(lambda form: form.tier_intervals(), id="tier-intervals"),
    pytest.param(lambda form: form.roots, id="graph-navigation"),
    pytest.param(lambda form: form.tier_events("segment"), id="tier-events"),
    pytest.param(lambda form: tuple(form), id="iteration"),
    pytest.param(lambda form: len(form), id="length"),
    pytest.param(lambda form: form[0], id="indexing"),
    pytest.param(lambda form: str(form), id="string"),
    pytest.param(lambda form: repr(form), id="repr"),
    pytest.param(lambda form: ipakit.IPAFeatures().distance(form, "p"), id="distance"),
    pytest.param(lambda form: parse("p -> b").recognize(form), id="rules"),
    pytest.param(lambda form: textgrid.write(form), id="textgrid"),
    pytest.param(lambda form: trajectory(form, head="adult-male"), id="gesture"),
    pytest.param(
        lambda form: DisagreementSpread.compare(
            ProvenancedForm("source", form),
            ProvenancedForm("house", ipakit.read("p")),
        ),
        id="disagreement",
    ),
)


@pytest.mark.parametrize("consumer", CONSUMERS)
def test_every_house_projection_consumer_names_the_uncovered_occurrence(
    incomplete: Form, consumer: Consumer
) -> None:
    with pytest.raises(FormProjectionError) as caught:
        consumer(incomplete)
    message = str(caught.value)
    assert "uncovered source occurrence" in message
    assert "1 (outside-reviewed-token-context)" in message


@pytest.mark.parametrize("consumer", CONSUMERS)
def test_complete_source_profile_forms_keep_working(
    complete: Form, consumer: Consumer
) -> None:
    consumer(complete)


def test_converter_refuses_an_uncovered_source_occurrence(incomplete: Form) -> None:
    with pytest.raises(FormProjectionError) as caught:
        MFABridge().emit(incomplete)
    assert "1 (outside-reviewed-token-context)" in str(caught.value)


def test_complete_converter_keeps_its_existing_tier_requirement(complete: Form) -> None:
    bridge = MFABridge()
    with pytest.raises(ValueError) as ordinary:
        bridge.emit(ipakit.read("p"))
    with pytest.raises(ValueError) as source:
        bridge.emit(complete)
    assert str(source.value) == str(ordinary.value)


@pytest.mark.parametrize(
    "transform",
    [
        pytest.param(lambda form: form.with_tier_intervals(), id="tier-intervals"),
        pytest.param(lambda form: form.without_boundaries(), id="boundaries"),
        pytest.param(lambda form: parse("p -> b").rewrite(form), id="rule"),
        pytest.param(lambda form: syllabify(form, "english"), id="syllabifier"),
        pytest.param(lambda form: MFABridge().map(form), id="vocabulary"),
        pytest.param(
            lambda form: RuleSet((parse("p -> b"),)).derive(form), id="derive"
        ),
        pytest.param(
            lambda form: RuleSet((parse("p -> b"),)).variants(form), id="variants"
        ),
    ],
)
def test_source_profile_transformations_refuse_even_with_full_coverage(
    complete: Form, transform: Consumer
) -> None:
    with pytest.raises(FormProjectionError, match="authoritative source/profile facts"):
        transform(complete)


def test_alignment_refuses_a_source_profile_form_before_external_work(
    complete: Form,
) -> None:
    corpus = SimpleNamespace(
        read=lambda _: SimpleNamespace(forms={"source": complete}, meta={})
    )
    with pytest.raises(FormProjectionError, match="authoritative source/profile facts"):
        align_entry(corpus, "item", source_role="source")


def test_from_json_cli_inherits_the_positioned_guard(incomplete: Form) -> None:
    run = subprocess.run(
        [sys.executable, "-m", "ipakit", "convert", "from-json", "-"],
        check=False,
        text=True,
        capture_output=True,
        input=incomplete.to_json(),
    )
    assert run.returncode != 0
    assert "1 (outside-reviewed-token-context)" in run.stderr


def test_full_graph_exports_do_not_require_house_coverage(incomplete: Form) -> None:
    encoded = incomplete.to_json()
    assert json.loads(encoded) == incomplete.to_dict()
    assert Form.from_json(encoded) == incomplete
    assert "digraph" in incomplete.to_dot()


def test_source_only_tone_marker_and_unknown_occurrences_remain_storable() -> None:
    form = _source_form("t", "⁵", "+", "☃")
    encoded = form.to_json()

    assert Form.from_json(encoded) == form
    assert "⁵" in encoded
    assert "+" in encoded
    assert "☃" in encoded
    with pytest.raises(FormProjectionError) as caught:
        form.to_ipa()
    message = str(caught.value)
    assert "1 (outside-reviewed-token-context)" in message
    assert "2 (marker)" in message
    assert "3 (outside-artifact-domain)" in message
