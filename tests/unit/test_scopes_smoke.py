import asyncio
import inspect

import pytest

from tests.conftest import FakeExecutor, make_dummy_value


SCOPE_MODULES = [
    "backup",
    "dhcp",
    "dns",
    "firewall_address_list",
    "firewall_filter",
    "firewall_nat",
    "firewall_raw",
    "ip_address",
    "ipv6_address",
    "ipv6_firewall_filter",
    "ipv6_firewall_raw",
    "ip_pool",
    "ipsec",
    "logs",
    "neighbors",
    "netwatch",
    "poe",
    "queue",
    "routes",
    "scheduler",
    "services",
    "system",
    "users",
    "vlan",
    "wireless",
    "wireguard",
]

@pytest.mark.parametrize("module_name", SCOPE_MODULES)
def test_scope_module_functions_return_string(module_name, ctx, monkeypatch):
    module = __import__(f"mcp_mikrotik.scope.{module_name}", fromlist=["*"])

    # Patch module-level executor (each scope imports it directly)
    fake = FakeExecutor()
    monkeypatch.setattr(module, "execute_mikrotik_command", fake, raising=True)

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
