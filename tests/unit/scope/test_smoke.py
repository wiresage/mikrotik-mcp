"""Every tool function of every tool module runs with dummy arguments and returns a string.

The modules are discovered from the package, so a new module is covered the moment it exists: there is no list to keep.
"""

import asyncio
import importlib
import inspect
import pkgutil

import pytest

import mcp_mikrotik.scope as scope_package
from mcp_mikrotik.config import DeviceConfig
from mcp_mikrotik.inventory import Inventory
from tests.conftest import FakeExecutor, make_dummy_value

SCOPE = scope_package.__name__ + "."

# The two modules that cannot run under the fake executor. Every other module is patched with raising=True, so a tool
# module that reaches RouterOS in some other way fails here instead of opening a real SSH connection.
#
# safe_mode drives a persistent SSH shell instead of the executor, so the fake cannot stand in for it; it has its own
# tests (tests/unit/scope/devices/test_safe_mode.py and tests/unit/test_safe_mode_manager.py).
NOT_EXERCISED = {SCOPE + "devices.safe_mode"}
# inventory runs no RouterOS command at all: it lists the configured devices, so it gets a fake inventory instead.
LISTS_DEVICES = SCOPE + "devices.inventory"


def tool_modules():
    """Every module that holds tools: not the packages and not the helpers (a leading underscore)."""
    found = []
    for info in pkgutil.walk_packages(scope_package.__path__, prefix=SCOPE):
        parts = info.name.removeprefix(SCOPE).split(".")
        if info.ispkg or any(part.startswith("_") for part in parts) or info.name in NOT_EXERCISED:
            continue
        found.append(info.name)
    return sorted(found)


def test_the_discovery_finds_the_tool_modules():
    """The parametrized test below runs once per module found: an empty discovery would pass without checking anything."""
    assert len(tool_modules()) >= 25
    assert LISTS_DEVICES in tool_modules()


@pytest.mark.parametrize("module_name", tool_modules(), ids=lambda name: name.removeprefix(SCOPE))
def test_scope_module_functions_return_string(module_name, ctx, monkeypatch, tmp_path):
    module = importlib.import_module(module_name)

    if module_name == LISTS_DEVICES:
        # The real get_inventory() reads the environment and caches the inventory for every test that follows.
        inventory = Inventory([DeviceConfig(title="R1", host="192.0.2.1", username="mcp")])
        monkeypatch.setattr(module, "get_inventory", lambda: inventory, raising=True)
        # add_device and remove_device persist to the runtime state file; keep it out of the real config directory.
        monkeypatch.setattr(
            module.config, "mikrotik_config",
            module.config.mikrotik_config.model_copy(
                update={"dynamic_inventory_file": str(tmp_path / "dynamic-inventory.yaml")}
            ),
            raising=True,
        )
    else:
        # Each tool module imports the executor by name; raising=True fails the test when one does not.
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
