"""Unit tests for the PoE scope (issue #90)."""

import asyncio

from tests.conftest import FakeExecutor


def _run(coro):
    return asyncio.run(coro)


def test_get_poe_monitor_uses_once_flag(ctx, monkeypatch):
    """The monitor command MUST include `once`, or it streams forever and hangs."""
    from mcp_mikrotik.scope.interfaces import poe

    fake = FakeExecutor()
    monkeypatch.setattr(poe, "execute_mikrotik_command", fake, raising=True)

    _run(poe.mikrotik_get_poe_monitor(ctx, interfaces="ether9-ap,ether10-ap"))

    assert fake.commands == [
        "/interface ethernet poe monitor ether9-ap,ether10-ap once"
    ]


def test_get_poe_monitor_returns_data(ctx, monkeypatch):
    from mcp_mikrotik.scope.interfaces import poe

    async def fake(cmd, _ctx, device=None):
        return "name: ether9-ap\npoe-out-status: powered-on\npoe-out-power: 4.2W"

    monkeypatch.setattr(poe, "execute_mikrotik_command", fake, raising=True)
    out = _run(poe.mikrotik_get_poe_monitor(ctx, interfaces="ether9-ap"))
    assert "POE MONITOR" in out
    assert "powered-on" in out


def test_get_poe_monitor_handles_empty(ctx, monkeypatch):
    from mcp_mikrotik.scope.interfaces import poe

    async def fake(cmd, _ctx, device=None):
        return ""

    monkeypatch.setattr(poe, "execute_mikrotik_command", fake, raising=True)
    out = _run(poe.mikrotik_get_poe_monitor(ctx, interfaces="ether1"))
    assert "No PoE monitor data" in out


def test_list_poe_command_and_filter(ctx, monkeypatch):
    from mcp_mikrotik.scope.interfaces import poe

    fake = FakeExecutor()
    monkeypatch.setattr(poe, "execute_mikrotik_command", fake, raising=True)

    _run(poe.mikrotik_list_poe(ctx))
    assert fake.commands[-1] == "/interface ethernet poe print"

    _run(poe.mikrotik_list_poe(ctx, interface_filter="ether"))
    assert fake.commands[-1] == '/interface ethernet poe print where name~"ether"'


def test_get_poe_settings_command(ctx, monkeypatch):
    from mcp_mikrotik.scope.interfaces import poe

    fake = FakeExecutor()
    monkeypatch.setattr(poe, "execute_mikrotik_command", fake, raising=True)

    _run(poe.mikrotik_get_poe_settings(ctx, name="ether1"))
    assert fake.commands[-1] == '/interface ethernet poe print detail where name="ether1"'
