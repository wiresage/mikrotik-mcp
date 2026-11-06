"""Unit tests for the IPv4 address scope (issue #154)."""

import asyncio

from tests.conftest import FakeExecutor


def _run(coro):
    return asyncio.run(coro)


def test_remove_by_positional_number(ctx, monkeypatch):
    from mcp_mikrotik.scope import ip_address as m

    seen = []

    async def fake(cmd, _ctx, device=None):
        seen.append(cmd)
        if "pick" in cmd:
            return "*3B"
        if "count-only where .id=*3B" in cmd:
            return "1"
        return ""

    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)
    out = _run(m.mikrotik_remove_ip_address(ctx, address_id="1"))
    assert "/ip address remove *3B" in seen
    assert "removed successfully" in out.lower()


def test_remove_by_internal_id(ctx, monkeypatch):
    from mcp_mikrotik.scope import ip_address as m

    seen = []

    async def fake(cmd, _ctx, device=None):
        seen.append(cmd)
        if "count-only where .id=*1" in cmd:
            return "1"
        return ""

    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)
    out = _run(m.mikrotik_remove_ip_address(ctx, address_id="*1"))
    assert "/ip address remove *1" in seen
    assert "removed successfully" in out.lower()


def test_remove_by_address_value(ctx, monkeypatch):
    from mcp_mikrotik.scope import ip_address as m

    seen = []

    async def fake(cmd, _ctx, device=None):
        seen.append(cmd)
        if 'count-only where address="192.168.88.1/24"' in cmd:
            return "1"
        return ""

    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)
    out = _run(m.mikrotik_remove_ip_address(ctx, address_id="192.168.88.1/24"))
    assert '/ip address remove [find address="192.168.88.1/24"]' in seen
    assert "removed successfully" in out.lower()
