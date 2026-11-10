"""Unit tests for the IPv4 firewall filter scope (issue #108)."""

import asyncio

from tests.conftest import FakeExecutor


def _run(coro):
    return asyncio.run(coro)


def test_enable_disable_delegates_to_update_implementation(ctx, monkeypatch):
    from mcp_mikrotik.scope import firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_enable_filter_rule(ctx, rule_id="*1"))
    assert any("/ip firewall filter set *1" in c and "disabled=no" in c for c in fake.commands)

    fake.commands.clear()
    _run(m.mikrotik_disable_filter_rule(ctx, rule_id="*1"))
    assert any("/ip firewall filter set *1" in c and "disabled=yes" in c for c in fake.commands)


def test_update_filter_rule_direct(ctx, monkeypatch):
    from mcp_mikrotik.scope import firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_update_filter_rule(ctx, rule_id="*1", comment="test-rule"))
    assert any('/ip firewall filter set *1' in c and 'comment="test-rule"' in c for c in fake.commands)
