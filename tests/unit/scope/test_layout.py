"""The scope folder keeps one rule: everything lives in a feature-area package.

src/mcp_mikrotik/scope/__init__.py describes the layout; these tests turn it into checks so it cannot decay unnoticed:
a tool module that its area forgets to import registers nothing, an area that app.py forgets to import is silently
missing from the server, and a helper in the wrong place only shows up in review.
"""

import ast
from pathlib import Path

import pytest

import mcp_mikrotik.scope as scope_package

SCOPE_DIR = Path(scope_package.__file__).resolve().parent
APP_PY = SCOPE_DIR.parent / "app.py"
SHARED = "_shared"
PREFIX = ["mcp_mikrotik", "scope"]


def _packages():
    return sorted(p for p in SCOPE_DIR.iterdir() if p.is_dir() and p.name != "__pycache__")


def _areas():
    return [p for p in _packages() if p.name != SHARED]


def _modules(package, public_only=False):
    names = [p for p in sorted(package.glob("*.py")) if p.name != "__init__.py"]
    return [p for p in names if not (public_only and p.name.startswith("_"))]


def _tree(path):
    return ast.parse(path.read_text(encoding="utf-8"))


def _imported_names(tree, module, level):
    """The names in every `from <module> import a, b` of the given relative level."""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module and node.level == level:
            names.update(alias.name for alias in node.names)
    return names


def _registers_a_tool(tree):
    """True when the module decorates something with `<anything>.tool(...)`, which is how a tool is registered."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                call = decorator.func if isinstance(decorator, ast.Call) else decorator
                if isinstance(call, ast.Attribute) and call.attr == "tool":
                    return True
    return False


def _scope_targets(path, tree):
    """Every module under scope/ that `path` imports, as a list of dotted-name parts after `scope`."""
    package = PREFIX + list(path.relative_to(SCOPE_DIR).parent.parts)  # the package that holds the module
    targets = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            # `from . import x` starts at the package itself, `from .. import x` one level above, and so on
            base = package[: len(package) - (node.level - 1)] if node.level else []
            full = base + (node.module.split(".") if node.module else [])
            if full[:2] == PREFIX:
                rest = full[2:]
                # `from mcp_mikrotik.scope import firewall` names the area in the imported name, not in the module
                for alias in node.names:
                    targets.append(rest if rest else [alias.name])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                full = alias.name.split(".")
                if full[:2] == PREFIX:
                    targets.append(full[2:])
    return targets


def test_the_scope_is_found():
    """Every parametrized check below runs once per area: an empty scan would pass without checking anything."""
    assert len(_areas()) >= 10
    assert (SCOPE_DIR / SHARED).is_dir()


def test_the_root_holds_only_packages():
    modules = sorted(p.name for p in SCOPE_DIR.glob("*.py") if p.name != "__init__.py")
    assert not modules, (
        f"modules at the root of scope/: {modules}. Put each one in the package of its feature area "
        "(see scope/__init__.py)."
    )
    not_packages = sorted(p.name for p in _packages() if not (p / "__init__.py").exists())
    assert not not_packages, f"folders in scope/ without an __init__.py: {not_packages}"


def test_every_area_is_imported_by_app():
    imported = _imported_names(_tree(APP_PY), "mcp_mikrotik.scope", 0)
    areas = {p.name for p in _areas()}
    assert imported == areas, (
        f"app.py must import every area package and nothing else: missing {sorted(areas - imported)}, "
        f"not an area {sorted(imported - areas)}"
    )


@pytest.mark.parametrize("area", _areas(), ids=lambda p: p.name)
def test_every_tool_module_is_imported_by_its_area(area):
    """A tool module is registered by being imported: one that its area does not import has no tools."""
    imported = _imported_names(_tree(area / "__init__.py"), None, 1)
    modules = {p.stem for p in _modules(area, public_only=True)}
    assert imported == modules, (
        f"{area.name}/__init__.py must do `from . import ...` for every module of the area: "
        f"missing {sorted(modules - imported)}, not a module {sorted(imported - modules)}"
    )


@pytest.mark.parametrize("package", _packages(), ids=lambda p: p.name)
def test_helpers_register_no_tool(package):
    """A module with a leading underscore is a helper: the area does not import it, so a tool in it would never register."""
    offenders = [p.name for p in _modules(package) if (p.name.startswith("_") or package.name == SHARED) and _registers_a_tool(_tree(p))]
    assert not offenders, f"{package.name}: helpers that register tools: {offenders}"


@pytest.mark.parametrize("area", _areas(), ids=lambda p: p.name)
def test_an_area_never_imports_another_area(area):
    """Areas are independent: what two of them need goes to _shared, so one can change without the other."""
    allowed = {area.name, SHARED}
    violations = []
    for path in _modules(area):
        for target in _scope_targets(path, _tree(path)):
            if target and target[0] not in allowed:
                violations.append(f"{path.name} imports scope.{'.'.join(target)}")
    assert not violations, f"{area.name}: {violations}"


def test_shared_helpers_import_no_area():
    violations = []
    for path in _modules(SCOPE_DIR / SHARED):
        for target in _scope_targets(path, _tree(path)):
            if target and target[0] != SHARED:
                violations.append(f"{path.name} imports scope.{'.'.join(target)}")
    assert not violations, f"_shared must not depend on an area: {violations}"


REFERENCE_DIR = Path(__file__).resolve().parents[3] / "docs" / "reference"


@pytest.mark.parametrize("area", _areas(), ids=lambda p: p.name)
def test_every_area_has_reference_pages_that_are_listed(area):
    """docs/reference/<area>/ follows the code: an overview, listed in the index, that links every page of the area."""
    folder = REFERENCE_DIR / area.name
    overview = folder / "README.md"
    assert overview.is_file(), f"docs/reference/{area.name}/README.md is missing: describe the area's modules there"
    index = (REFERENCE_DIR / "README.md").read_text(encoding="utf-8")
    assert f"{area.name}/README.md" in index, f"docs/reference/README.md does not list the {area.name} area"
    text = overview.read_text(encoding="utf-8")
    unlisted = sorted(p.name for p in folder.glob("*.md") if p.name != "README.md" and p.name not in text)
    assert not unlisted, f"docs/reference/{area.name}/README.md does not link: {unlisted}"


@pytest.mark.parametrize("package", [SCOPE_DIR, *_packages()], ids=lambda p: p.name)
def test_every_package_has_a_charter(package):
    """The docstring of a package says what belongs in it, so a contributor can decide where a new module goes."""
    assert ast.get_docstring(_tree(package / "__init__.py")), f"{package.name}/__init__.py needs a docstring"
