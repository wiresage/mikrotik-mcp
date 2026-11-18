"""List filters must quote enum values in the `where` clause (issue #135).

On RouterOS an unquoted `where protocol=udp` matches nothing, with no error, so
the tool answers "no rules" for rules that exist. The IPv6 filter scope already
quotes its values; these tests keep the IPv4 filter and NAT scopes the same.
"""

import asyncio

import pytest

from tests.conftest import FakeExecutor


def _run(coro):
    return asyncio.run(coro)


CASES = [
    ("firewall.filter", "mikrotik_list_filter_rules", "/ip firewall filter print"),
    ("firewall.nat", "mikrotik_list_nat_rules", "/ip firewall nat print"),
]


def _call(module, function, ctx, monkeypatch, **kwargs):
    from importlib import import_module

    m = import_module(f"mcp_mikrotik.scope.{module}")
    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)
    _run(getattr(m, function)(ctx, **kwargs))
    return fake.commands[0]


@pytest.mark.parametrize("module,function,base", CASES)
def test_protocol_filter_is_quoted(ctx, monkeypatch, module, function, base):
    cmd = _call(module, function, ctx, monkeypatch, protocol_filter="udp")
    assert cmd == f'{base} where protocol="udp"'


@pytest.mark.parametrize("module,function,base", CASES)
def test_chain_and_action_filters_are_quoted(ctx, monkeypatch, module, function, base):
    cmd = _call(module, function, ctx, monkeypatch, chain_filter="srcnat", action_filter="masquerade")
    assert cmd == f'{base} where chain="srcnat" action="masquerade"'


@pytest.mark.parametrize("module,function,base", CASES)
def test_enum_filters_compose_with_the_other_filters(ctx, monkeypatch, module, function, base):
    cmd = _call(
        module, function, ctx, monkeypatch,
        chain_filter="input", protocol_filter="tcp", src_address_filter="192.0.2.", disabled_only=True,
    )
    assert cmd == f'{base} where chain="input" src-address~"192.0.2." protocol="tcp" disabled=yes'


@pytest.mark.parametrize("module,function,base", CASES)
def test_no_filters_leaves_the_command_bare(ctx, monkeypatch, module, function, base):
    assert _call(module, function, ctx, monkeypatch) == base


@pytest.mark.parametrize("module,function,base", CASES)
def test_no_enum_value_is_ever_left_unquoted(ctx, monkeypatch, module, function, base):
    """Guards the whole family, not just protocol: every enum term carries quotes."""
    cmd = _call(
        module, function, ctx, monkeypatch,
        chain_filter="forward", action_filter="accept", protocol_filter="icmp",
    )
    for term in ("chain=forward", "action=accept", "protocol=icmp"):
        assert term not in cmd
