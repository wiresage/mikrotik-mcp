"""Every tool function of every tool module runs with dummy arguments and returns a string.

The modules are discovered from the package, so a new module is covered the moment it exists: there is no list to keep.
"""

import asyncio
import importlib
import inspect
import pkgutil

import pytest

import mcp_mikrotik.scope as scope_package
from tests.conftest import FakeExecutor, make_dummy_value

# safe_mode drives a persistent SSH shell instead of the executor, so the fake cannot stand in for it; it has its own
# tests (tests/unit/scope/devices/test_safe_mode.py and tests/unit/test_safe_mode_manager.py).
NOT_EXERCISED = {"mcp_mikrotik.scope.devices.safe_mode"}


def tool_modules():
    """Every module that holds tools: not the packages and not the helpers (a leading underscore)."""
    prefix = scope_package.__name__ + "."
    found = []
    for info in pkgutil.walk_packages(scope_package.__path__, prefix=prefix):
        parts = info.name.removeprefix(prefix).split(".")
        if info.ispkg or any(part.startswith("_") for part in parts) or info.name in NOT_EXERCISED:
            continue
        found.append(info.name)
    return sorted(found)


def test_the_discovery_finds_the_tool_modules():
    """The parametrized test below runs once per module found: an empty discovery would pass without checking anything."""
    assert len(tool_modules()) >= 25


@pytest.mark.parametrize("module_name", tool_modules(), ids=lambda name: name.removeprefix("mcp_mikrotik.scope."))
def test_scope_module_functions_return_string(module_name, ctx, monkeypatch):
    module = importlib.import_module(module_name)

    # Patch module-level executor (each tool module imports it directly). devices.inventory does not run a RouterOS
    # command at all: it lists the configured devices, so there is nothing to patch and the call is purely local.
    if hasattr(module, "execute_mikrotik_command"):
        monkeypatch.setattr(module, "execute_mikrotik_command", FakeExecutor(), raising=True)

    # Run every coroutine function once with dummy args.
    for name, fn in inspect.getmembers(module, inspect.iscoroutinefunction):
        if not name.startswith("mikrotik_"):
            continue

        sig = inspect.signature(fn)
        kwargs = {}
        for param in sig.parameters.values():
            if param.name == "ctx":
                kwargs["ctx"] = ctx
                continue
            if param.default is not inspect._empty:
                continue
            kwargs[param.name] = make_dummy_value(param)

        result = asyncio.run(fn(**kwargs))
        assert isinstance(result, str)
