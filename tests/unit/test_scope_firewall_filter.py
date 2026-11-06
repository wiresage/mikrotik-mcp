"""Unit tests for the IPv4 firewall filter scope (issue #138)."""

import asyncio

from tests.conftest import FakeExecutor


def _run(coro):
    return asyncio.run(coro)


def test_create_reject_carries_reject_with(ctx, monkeypatch):
    from mcp_mikrotik.scope import firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_create_filter_rule(ctx, chain="forward", action="reject", reject_with="icmp-admin-prohibited"))
    assert any("action=reject reject-with=icmp-admin-prohibited" in c for c in fake.commands)


def test_create_reject_invalid_chars(ctx, monkeypatch):
    from mcp_mikrotik.scope import firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    res = _run(m.mikrotik_create_filter_rule(ctx, chain="forward", action="reject", reject_with='icmp"inject'))
    assert "contains invalid characters" in res
    assert not fake.commands


def test_update_reject_with(ctx, monkeypatch):
    from mcp_mikrotik.scope import firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_update_filter_rule(ctx, rule_id="*1", action="reject", reject_with="tcp-reset"))
    assert any("/ip firewall filter set *1" in c and "reject-with=tcp-reset" in c for c in fake.commands)


def test_update_reject_with_clear(ctx, monkeypatch):
    from mcp_mikrotik.scope import firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_update_filter_rule(ctx, rule_id="*1", reject_with=""))
    assert any("/ip firewall filter set *1" in c and "!reject-with" in c for c in fake.commands)
