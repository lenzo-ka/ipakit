"""Fresh imports leave Tiergraph's opt-in modules unloaded."""

import subprocess
import sys

LAZY_MODULES = (
    "tiergraph.blob",
    "tiergraph.container_edit",
    "tiergraph.diff",
    "tiergraph.distance",
    "tiergraph.edit",
    "tiergraph.equivalence",
    "tiergraph.patch",
    "tiergraph.pathoutput",
    "tiergraph.profile",
    "tiergraph.reconcile",
    "tiergraph.replacement",
    "tiergraph.selected",
    "tiergraph.textgrid",
)


def test_import_leaves_tiergraph_opt_in_modules_unloaded() -> None:
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
