"""Unit tests for the IPv4 firewall NAT scope (issue #137)."""

import asyncio

from tests.conftest import FakeExecutor


def _run(coro):
    return asyncio.run(coro)


def test_nat_create_jump_carries_target(ctx, monkeypatch):
    from mcp_mikrotik.scope import firewall_nat as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_create_nat_rule(ctx, chain="srcnat", action="jump", jump_target="custom-nat"))
    assert any('/ip firewall nat add chain=srcnat action=jump jump-target="custom-nat"' in c for c in fake.commands)


def test_nat_create_jump_requires_target(ctx, monkeypatch):
    from mcp_mikrotik.scope import firewall_nat as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    res = _run(m.mikrotik_create_nat_rule(ctx, chain="srcnat", action="jump"))
    assert "jump_target is required" in res
    assert not fake.commands


def test_nat_update_jump_target(ctx, monkeypatch):
    from mcp_mikrotik.scope import firewall_nat as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_update_nat_rule(ctx, rule_id="*1", action="jump", jump_target="target-nat"))
    assert any('/ip firewall nat set *1' in c and 'jump-target="target-nat"' in c for c in fake.commands)
