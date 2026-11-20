"""Device selection fallback and error surfacing (no more "No ... found" for failures)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from mcp_mikrotik import config
from mcp_mikrotik.config import DeviceConfig, MikrotikConfig
from mcp_mikrotik.inventory import DeviceNotFoundError, Inventory
from mcp_mikrotik.scope._shared.results import routeros_error


def _inventory():
    return Inventory([
        DeviceConfig(title="RouterA", host="10.0.0.1"),
        DeviceConfig(title="RouterB", host="10.0.0.2"),
    ])


def test_multi_device_requires_device_name_without_default(monkeypatch):
    monkeypatch.setattr(config, "mikrotik_config", MikrotikConfig())
    with pytest.raises(DeviceNotFoundError, match="`device_name` argument is required"):
        _inventory().resolve(None)


def test_default_device_is_used_when_no_device_name_given(monkeypatch):
    monkeypatch.setattr(config, "mikrotik_config", MikrotikConfig(default_device="routerb"))
    assert _inventory().resolve(None).title == "RouterB"
    # an explicit device_name still wins
    assert _inventory().resolve("RouterA").title == "RouterA"


def test_unknown_default_device_is_an_error(monkeypatch):
    monkeypatch.setattr(config, "mikrotik_config", MikrotikConfig(default_device="Ghost"))
    with pytest.raises(DeviceNotFoundError, match="Unknown device 'Ghost'"):
        _inventory().resolve(None)


@pytest.mark.parametrize("text", [
    "bad command name resource (line 1 column 9)",
    "syntax error (line 1 column 5)",
    "expected end of command (line 1 column 40)",
    "not enough permissions (9)",
    "input does not match any value of interface",
    "failure: already have such entry",
])
def test_routeros_errors_are_recognised(text):
    assert routeros_error(text)


@pytest.mark.parametrize("text", [
    "",
    "Flags: X - disabled, R - running",
    "                   uptime: 1d2h\n                  version: 7.16",
    " 0   address=192.168.88.50 mac-address=02:00:00:00:00:01 status=bound",
])
def test_data_is_not_mistaken_for_an_error(text):
    assert not routeros_error(text)


def _ctx():
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.error = AsyncMock()
    return ctx


def test_read_tool_surfaces_routeros_refusal(monkeypatch):
    from mcp_mikrotik.scope.system import info

    async def fake_execute(command, ctx, device=None, **kw):
        return "not enough permissions (9)"

    monkeypatch.setattr(info, "execute_mikrotik_command", fake_execute)
    with pytest.raises(ToolError, match="not enough permissions"):
        asyncio.run(info.mikrotik_get_system_resource(_ctx(), device="RouterA"))


def test_read_tool_still_reports_genuinely_empty(monkeypatch):
    from mcp_mikrotik.scope.dhcp import dhcp

    async def fake_execute(command, ctx, device=None, **kw):
        return "Flags: X - disabled, R - radius, D - dynamic, B - blocked"

    monkeypatch.setattr(dhcp, "execute_mikrotik_command", fake_execute)
    result = asyncio.run(dhcp.mikrotik_list_dhcp_leases(_ctx(), device="RouterA"))
    assert result.startswith("No DHCP leases found")


def test_device_selection_failure_is_not_reported_as_empty(monkeypatch):
    """The original symptom: a missing device_name used to read as 'No ... found'."""
    from mcp_mikrotik import connector, inventory
    from mcp_mikrotik.scope.dhcp import dhcp

    monkeypatch.setattr(config, "mikrotik_config", MikrotikConfig())
    monkeypatch.setattr(inventory, "_inventory", _inventory())
    monkeypatch.setattr(connector, "get_inventory", lambda: inventory._inventory)
    monkeypatch.setattr(dhcp, "execute_mikrotik_command", connector.execute_mikrotik_command)
    with pytest.raises(ToolError, match="Available devices: RouterA, RouterB"):
        asyncio.run(dhcp.mikrotik_list_dhcp_leases(_ctx()))
