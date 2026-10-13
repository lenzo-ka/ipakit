"""Fresh imports leave the declared lazy modules unloaded."""

import subprocess
import sys

LAZY_MODULES = (
    "ipakit._cross_tier",
    "ipakit._match_ranges",
    "tiergraph.blob",
    "tiergraph.container_edit",
    "tiergraph.diff",
    "tiergraph.distance",
    "tiergraph.edit",
    "tiergraph.equivalence",
    "tiergraph.match",
    "tiergraph.match_text",
    "tiergraph.patch",
    "tiergraph.pathoutput",
    "tiergraph.profile",
    "tiergraph.reconcile",
    "tiergraph.replacement",
    "tiergraph.selected",
    "tiergraph.textgrid",
)


def test_import_leaves_declared_lazy_modules_unloaded() -> None:
    program = f"""
import sys

import ipakit

lazy = {LAZY_MODULES!r}
print(sorted(name for name in lazy if name in sys.modules))
"""
    completed = subprocess.run(
        [sys.executable, "-c", program],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.stdout == "[]\n"


def test_ordinary_queries_leave_cross_tier_matcher_unloaded() -> None:
    program = f"""
import sys
import tempfile

import ipakit

list(ipakit.corpus.find("kæt", "t"))
with tempfile.TemporaryDirectory() as directory:
    stored = ipakit.corpus.create(directory)
    stored.add("cat", {{}}, {{"cited": ipakit.read("kæt")}})
    list(ipakit.corpus.query(stored, "t", role="cited"))
lazy = {tuple(name for name in LAZY_MODULES if name != "ipakit._match_ranges")!r}
print(sorted(name for name in lazy if name in sys.modules))
"""
    completed = subprocess.run(
        [sys.executable, "-c", program],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.stdout == "[]\n"


def test_public_corpus_query_annotations_resolve_without_matcher_import() -> None:
    program = """
import sys
import typing

import ipakit

for function in (ipakit.corpus.parse_query, ipakit.corpus.find, ipakit.corpus.query):
    typing.get_type_hints(function)
print("ipakit._cross_tier" in sys.modules)
"""
    completed = subprocess.run(
        [sys.executable, "-c", program],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.stdout == "False\n"
