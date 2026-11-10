import asyncio
import inspect

import pytest

from tests.conftest import FakeExecutor, make_dummy_value


SCOPE_MODULES = [
    "system.backup",
    "interfaces.bridge",
    "dhcp.dhcp",
    "dns.dns",
    "firewall.address_list",
    "firewall.filter",
    "firewall.nat",
    "firewall.raw",
    "ip.address",
    "ip.ipv6_address",
    "firewall.ipv6_filter",
    "firewall.ipv6_raw",
    "ip.pool",
    "vpn.ipsec",
    "monitoring.logs",
    "ip.neighbors",
    "monitoring.netwatch",
    "interfaces.poe",
    "queue.queue",
    "routing.routes",
    "system.scheduler",
    "ip.services",
    "system.info",
    "users.users",
    "interfaces.vlan",
    "interfaces.wireless",
    "interfaces.wireguard",
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
