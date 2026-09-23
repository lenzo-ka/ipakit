"""A tiergraph attribute's lexical spelling is read in one place, or behind a JSON test.

tiergraph 0.3 attribute values may be JSON, and a JSON value has no lexical
spelling. ``ipakit._scalar_attribute.scalar_lexical`` reads a scalar and refuses
a JSON value by name. Any other ``.lexical`` read in the package must be the
``else`` branch of an ``isinstance(value, tg.JsonAttributeValue)`` test on the
same value, which is what makes it safe; a bare read would hand back an
``AttributeError`` or a wrong value for a JSON attribute, and nothing else fails.
"""

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "ipakit"
READER = PACKAGE / "_scalar_attribute.py"


def _guarded_by_json_test(node: ast.Attribute, parents: dict[ast.AST, ast.AST]) -> bool:
    """True when ``node`` is the else-branch of a JSON type test on the same name."""
    child: ast.AST = node
    parent = parents.get(child)
    while parent is not None:
        if isinstance(parent, (ast.IfExp, ast.If)) and _in_orelse(parent, child):
            test = parent.test
            if (
                isinstance(test, ast.Call)
                and isinstance(test.func, ast.Name)
                and test.func.id == "isinstance"
                and len(test.args) == 2
                and isinstance(test.args[1], ast.Attribute)
                and test.args[1].attr == "JsonAttributeValue"
                and isinstance(test.args[0], ast.Name)
                and isinstance(node.value, ast.Name)
                and test.args[0].id == node.value.id
            ):
                return True
        child, parent = parent, parents.get(parent)
    return False


def _in_orelse(parent: ast.If | ast.IfExp, child: ast.AST) -> bool:
    branch = parent.orelse
    return child in branch if isinstance(branch, list) else child is branch


def unguarded_lexical_reads(root: Path = PACKAGE) -> list[str]:
    """Every ``.lexical`` read outside the reader that no JSON test guards."""
    found = []
    for path in sorted(root.rglob("*.py")):
        if path == READER:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        parents = {
            child: node
            for node in ast.walk(tree)
            for child in ast.iter_child_nodes(node)
        }
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and node.attr == "lexical"
                and not _guarded_by_json_test(node, parents)
            ):
                found.append(f"{path.relative_to(root.parent)}:{node.lineno}")
    return found


def test_every_lexical_read_goes_through_the_reader_or_a_json_test():
    assert unguarded_lexical_reads() == []


def test_a_bare_lexical_read_is_found(tmp_path: Path):
    package = tmp_path / "ipakit"
    package.mkdir()
    (package / "reader.py").write_text(
        "def spelling(value):\n    return value.lexical\n", encoding="utf-8"
    )
    assert unguarded_lexical_reads(package) == ["ipakit/reader.py:2"]


def test_a_read_guarded_by_a_different_name_is_found(tmp_path: Path):
    package = tmp_path / "ipakit"
    package.mkdir()
    (package / "reader.py").write_text(
        "import tiergraph as tg\n"
        "def spelling(value, other):\n"
        "    return other.to_value() if isinstance(other, tg.JsonAttributeValue)"
        " else value.lexical\n",
        encoding="utf-8",
    )
    assert unguarded_lexical_reads(package) == ["ipakit/reader.py:3"]


def test_a_read_in_the_json_branch_is_found(tmp_path: Path):
    package = tmp_path / "ipakit"
    package.mkdir()
    (package / "reader.py").write_text(
        "import tiergraph as tg\n"
        "def spelling(value):\n"
        "    return value.lexical if isinstance(value, tg.JsonAttributeValue)"
        " else value.lexical\n",
        encoding="utf-8",
    )
    assert unguarded_lexical_reads(package) == ["ipakit/reader.py:3"]


def test_the_guarded_else_branch_is_accepted(tmp_path: Path):
    package = tmp_path / "ipakit"
    package.mkdir()
    (package / "reader.py").write_text(
        "import tiergraph as tg\n"
        "def spelling(value):\n"
        "    return value.to_value() if isinstance(value, tg.JsonAttributeValue)"
        " else value.lexical\n",
        encoding="utf-8",
    )
    assert unguarded_lexical_reads(package) == []
