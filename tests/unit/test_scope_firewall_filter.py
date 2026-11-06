"""Unit tests for the IPv4 firewall filter scope (issue #137)."""

import asyncio

from tests.conftest import FakeExecutor


def _run(coro):
    return asyncio.run(coro)


def test_create_jump_carries_target(ctx, monkeypatch):
    from mcp_mikrotik.scope import firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_create_filter_rule(ctx, chain="forward", action="jump", jump_target="probe-chain"))
    assert any('action=jump jump-target="probe-chain"' in c for c in fake.commands)


def test_create_jump_requires_target(ctx, monkeypatch):
    from mcp_mikrotik.scope import firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    res = _run(m.mikrotik_create_filter_rule(ctx, chain="forward", action="jump"))
    assert "jump_target is required" in res
    assert not fake.commands


def test_create_jump_target_invalid_chars(ctx, monkeypatch):
    from mcp_mikrotik.scope import firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    res = _run(m.mikrotik_create_filter_rule(ctx, chain="forward", action="jump", jump_target='target"inject'))
    assert "contains invalid characters" in res
    assert not fake.commands


def test_update_jump_target(ctx, monkeypatch):
    from mcp_mikrotik.scope import firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_update_filter_rule(ctx, rule_id="*1", action="jump", jump_target="my-target"))
    assert any('/ip firewall filter set *1' in c and 'jump-target="my-target"' in c for c in fake.commands)
