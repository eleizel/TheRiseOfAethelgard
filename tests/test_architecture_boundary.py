"""Architectural boundary enforcement test suite.

Inspects all domain modules in `src/` to ensure they never import GUI frameworks
(`pygame`, `pygame_ce`) or frontend presentation layers (`src.frontends`).
"""

import ast
from pathlib import Path

import pytest

SRC_ROOT = Path(__file__).resolve().parent.parent / "src"
DOMAIN_DIRS = ["core", "entities", "systems", "data"]
FORBIDDEN_MODULES = ("pygame", "pygame_ce", "src.frontends")


def get_domain_python_files():
    """Discover all python source files across domain directories."""
    files = []
    for d in DOMAIN_DIRS:
        dir_path = SRC_ROOT / d
        if not dir_path.exists():
            continue
        for file_path in dir_path.rglob("*.py"):
            rel_path = file_path.relative_to(SRC_ROOT.parent).as_posix()
            files.append(rel_path)
    return sorted(files)


@pytest.mark.parametrize("file_rel_path", get_domain_python_files())
def test_no_forbidden_gui_imports(file_rel_path):
    """Enforce that domain files do not import GUI libraries or presentation modules."""
    full_path = SRC_ROOT.parent / file_rel_path

    with open(full_path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=str(full_path))

    imported_modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.append((node.module, node.lineno))

    violations = []
    for mod, lineno in imported_modules:
        for forbidden in FORBIDDEN_MODULES:
            if mod == forbidden or mod.startswith(f"{forbidden}."):
                violations.append((mod, lineno))

    assert not violations, (
        f"Architectural boundary violation in {file_rel_path}: "
        f"Domain core cannot import presentation/GUI layers: {violations}"
    )
