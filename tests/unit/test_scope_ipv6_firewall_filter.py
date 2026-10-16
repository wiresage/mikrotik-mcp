"""Unit tests for the IPv6 firewall filter scope (issue #136)."""

import asyncio

from tests.conftest import FakeExecutor


def _run(coro):
    return asyncio.run(coro)


def _set_cmd(fake):
    """Return the `set` command."""
    return next(c for c in fake.commands if " set " in c)


# ---------------------------------------------------------------------------
# create_ipv6_filter_rule — command construction
# ---------------------------------------------------------------------------

def test_create_minimal(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_create_ipv6_filter_rule(ctx, chain="input", action="accept"))
    assert fake.commands[0] == "/ipv6 firewall filter add chain=input action=accept"


def test_create_targets_the_ipv6_tree(ctx, monkeypatch):
    """The whole point of the scope: never emit an /ip firewall command."""
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_create_ipv6_filter_rule(ctx, chain="forward", action="drop"))
    assert all(c.startswith("/ipv6 firewall filter") for c in fake.commands)


def test_create_all_options(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_create_ipv6_filter_rule(
        ctx, chain="forward", action="accept",
        src_address="2001:db8::/64", dst_address="2001:db8:1::/64",
        src_port="1024-65535", dst_port="443", protocol="tcp",
        in_interface="ether1", out_interface="bridge",
        connection_state="established,related",
        src_address_list="trusted", dst_address_list="servers",
        src_address_type="unicast", dst_address_type="unicast",
        hop_limit="equal:255", headers="!hop",
        limit="10,5:packet", tcp_flags="syn,!ack",
        comment="web", disabled=True, log=True, log_prefix="WEB",
        place_before="0",
    ))
    cmd = fake.commands[0]
    assert cmd.startswith("/ipv6 firewall filter add chain=forward action=accept")
    assert "src-address=2001:db8::/64" in cmd
    assert "dst-address=2001:db8:1::/64" in cmd
    assert "protocol=tcp" in cmd
    assert 'in-interface="ether1"' in cmd
    assert "connection-state=established,related" in cmd
    assert 'src-address-list="trusted"' in cmd
    assert "src-address-type=unicast" in cmd
    assert "hop-limit=equal:255" in cmd
    assert "headers=!hop" in cmd
    assert "tcp-flags=syn,!ack" in cmd
    assert 'comment="web"' in cmd
    assert "disabled=yes" in cmd
    assert 'log=yes log-prefix="WEB"' in cmd
    assert "place-before=0" in cmd


def test_create_icmpv6_protocol(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_create_ipv6_filter_rule(
        ctx, chain="input", action="accept", protocol="icmpv6", icmp_options="128:0",
    ))
    cmd = fake.commands[0]
    assert "protocol=icmpv6" in cmd
    assert "icmp-options=128:0" in cmd


def test_create_jump_carries_a_target(ctx, monkeypatch):
    """action=jump is useless without jump-target, so the parameter exists."""
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_create_ipv6_filter_rule(
        ctx, chain="forward", action="jump", jump_target="icmpv6-chain",
    ))
    assert 'jump-target="icmpv6-chain"' in fake.commands[0]


def test_create_omits_connection_nat_state(ctx, monkeypatch):
    """IPv6 here is NAT-free; the IPv4-only match field must not appear."""
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_create_ipv6_filter_rule(ctx, chain="input", action="accept"))
    assert "connection-nat-state" not in fake.commands[0]


# ---------------------------------------------------------------------------
# list_ipv6_filter_rules — filters
# ---------------------------------------------------------------------------

def test_list_no_filters(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_list_ipv6_filter_rules(ctx))
    assert fake.commands[0] == "/ipv6 firewall filter print"


def test_list_quotes_protocol_filter(ctx, monkeypatch):
    """Regression for #135: an unquoted value matches nothing on RouterOS."""
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_list_ipv6_filter_rules(ctx, protocol_filter="icmpv6"))
    assert 'protocol="icmpv6"' in fake.commands[0]
    assert "protocol=icmpv6" not in fake.commands[0].replace('protocol="icmpv6"', "")


def test_list_quotes_chain_and_action(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_list_ipv6_filter_rules(ctx, chain_filter="input", action_filter="accept"))
    cmd = fake.commands[0]
    assert 'chain="input"' in cmd
    assert 'action="accept"' in cmd


def test_list_address_filters_are_partial_matches(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_list_ipv6_filter_rules(
        ctx, src_address_filter="2001:db8", dst_address_filter="fe80",
    ))
    cmd = fake.commands[0]
    assert 'src-address~"2001:db8"' in cmd
    assert 'dst-address~"fe80"' in cmd


def test_list_interface_filter_matches_both_directions(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_list_ipv6_filter_rules(ctx, interface_filter="ether1"))
    assert '(in-interface~"ether1" or out-interface~"ether1")' in fake.commands[0]


def test_list_boolean_filters(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_list_ipv6_filter_rules(
        ctx, disabled_only=True, invalid_only=True, dynamic_only=True,
    ))
    cmd = fake.commands[0]
    assert "disabled=yes" in cmd
    assert "invalid=yes" in cmd
    assert "dynamic=yes" in cmd


def test_list_empty_result_message(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    async def empty(command, _ctx, device=None):
        return ""

    monkeypatch.setattr(m, "execute_mikrotik_command", empty, raising=True)

    out = _run(m.mikrotik_list_ipv6_filter_rules(ctx))
    assert out == "No IPv6 firewall filter rules found matching the criteria."


# ---------------------------------------------------------------------------
# get / remove / move
# ---------------------------------------------------------------------------

def test_get_not_found_on_flags_only_output(ctx, monkeypatch):
    """`print detail` returns the Flags legend even with no match."""
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    async def legend(command, _ctx, device=None):
        return "Flags: X - DISABLED, I - INVALID; D - DYNAMIC"

    monkeypatch.setattr(m, "execute_mikrotik_command", legend, raising=True)

    out = _run(m.mikrotik_get_ipv6_filter_rule(ctx, rule_id="*99"))
    assert "not found" in out


def test_remove_missing_rule(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    async def absent(command, _ctx, device=None):
        return "no such item (4)"

    monkeypatch.setattr(m, "execute_mikrotik_command", absent, raising=True)

    out = _run(m.mikrotik_remove_ipv6_filter_rule(ctx, rule_id="*99"))
    assert "not found" in out


def test_remove_existing_rule(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    commands = []

    async def execute(command, _ctx, device=None):
        commands.append(command)
        if "count-only" in command:
            return "0" if any(" remove " in c for c in commands) else "1"
        return ""

    monkeypatch.setattr(m, "execute_mikrotik_command", execute, raising=True)

    out = _run(m.mikrotik_remove_ipv6_filter_rule(ctx, rule_id="*1"))
    assert "/ipv6 firewall filter remove *1" in commands
    assert "removed successfully" in out


def test_move_rule(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    commands = []

    async def execute(command, _ctx, device=None):
        commands.append(command)
        if command == ":put [/ipv6 firewall filter find]":
            return "*0;*1;*2;*3;*4"
        if "count-only" in command:
            return "1"
        if command.startswith(":put [:pick"):
            return "*1"
        return ""

    monkeypatch.setattr(m, "execute_mikrotik_command", execute, raising=True)

    out = _run(m.mikrotik_move_ipv6_filter_rule(ctx, rule_id="*1", destination=3))
    # *1 is at position 1; to end up at position 3 it goes in front of the item now at position 4
    assert "/ipv6 firewall filter move *1 destination=*4" in commands
    assert "moved to position 3" in out


# ---------------------------------------------------------------------------
# update / enable / disable
# ---------------------------------------------------------------------------

def test_update_no_fields(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    out = _run(m.mikrotik_update_ipv6_filter_rule(ctx, rule_id="*1"))
    assert out == "No updates specified."
    assert fake.commands == []


def test_update_sets_and_clears(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_update_ipv6_filter_rule(
        ctx, rule_id="*1", protocol="icmpv6", src_address="",
    ))
    cmd = _set_cmd(fake)
    assert cmd.startswith("/ipv6 firewall filter set *1 ")
    assert "protocol=icmpv6" in cmd
    assert "!src-address" in cmd


def test_update_quotes_only_name_bearing_fields(ctx, monkeypatch):
    """Same split as `create` and the IPv4 scope: names quoted, values bare."""
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_update_ipv6_filter_rule(
        ctx, rule_id="*1",
        in_interface="ether1", src_address_list="trusted", jump_target="chain-a",
        hop_limit="equal:255", tcp_flags="syn,!ack", limit="10,5:packet",
        dst_port="443", protocol="tcp",
    ))
    cmd = _set_cmd(fake)
    for quoted in ('in-interface="ether1"', 'src-address-list="trusted"',
                   'jump-target="chain-a"'):
        assert quoted in cmd
    for bare in ("hop-limit=equal:255", "tcp-flags=syn,!ack", "limit=10,5:packet",
                 "dst-port=443", "protocol=tcp"):
        assert bare in cmd


def test_enable_and_disable_wrappers(ctx, monkeypatch):
    """These must not repeat the positional-ctx bug tracked in #108."""
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_disable_ipv6_filter_rule(ctx, rule_id="*1"))
    assert "disabled=yes" in _set_cmd(fake)

    fake.commands.clear()
    _run(m.mikrotik_enable_ipv6_filter_rule(ctx, rule_id="*1"))
    assert "disabled=no" in _set_cmd(fake)


def test_device_argument_is_forwarded(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_list_ipv6_filter_rules(ctx, device="RouterB"))
    assert fake.devices == ["RouterB"]


# ---------------------------------------------------------------------------
# failure paths
# ---------------------------------------------------------------------------

def test_create_failure_path(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    async def failing(command, _ctx, device=None):
        return "failure: already have such entry"

    monkeypatch.setattr(m, "execute_mikrotik_command", failing, raising=True)

    out = _run(m.mikrotik_create_ipv6_filter_rule(ctx, chain="input", action="accept"))
    assert out.startswith("Failed to create IPv6 firewall filter rule:")


def test_create_rejects_error_text_that_says_neither_failure_nor_error(ctx, monkeypatch):
    """RouterOS rejections do not all contain "failure:" or "error".

    Without a positive-evidence check the rejection is mistaken for a rule id
    and reported as a successful create.
    """
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    async def odd(command, _ctx, device=None):
        return "no such item (4)"

    monkeypatch.setattr(m, "execute_mikrotik_command", odd, raising=True)

    out = _run(m.mikrotik_create_ipv6_filter_rule(ctx, chain="input", action="accept"))
    assert out.startswith("Failed to create IPv6 firewall filter rule:")
    assert "created" not in out.lower()


def test_create_returns_detail_when_router_echoes_an_id(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    async def echo_id(command, _ctx, device=None):
        if command.startswith("/ipv6 firewall filter add"):
            return "*7"
        return "Flags: X - disabled\n 0  chain=input action=accept"

    monkeypatch.setattr(m, "execute_mikrotik_command", echo_id, raising=True)

    out = _run(m.mikrotik_create_ipv6_filter_rule(ctx, chain="input", action="accept"))
    assert "created successfully" in out
    assert "chain=input" in out


def test_get_positive_path(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    async def detail(command, _ctx, device=None):
        return "Flags: X - disabled\n 0  chain=forward action=drop protocol=icmpv6"

    monkeypatch.setattr(m, "execute_mikrotik_command", detail, raising=True)

    out = _run(m.mikrotik_get_ipv6_filter_rule(ctx, rule_id="*1"))
    assert out.startswith("IPV6 FIREWALL FILTER RULE DETAILS:")
    assert "protocol=icmpv6" in out


def test_remove_failure_path(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    async def exists_then_fails(command, _ctx, device=None):
        if "count-only" in command:
            return "1"
        return "failure: cannot remove builtin"

    monkeypatch.setattr(m, "execute_mikrotik_command", exists_then_fails, raising=True)

    out = _run(m.mikrotik_remove_ipv6_filter_rule(ctx, rule_id="*1"))
    assert out.startswith("Failed to remove IPv6 firewall filter rule:")


def test_move_missing_rule(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    async def absent(command, _ctx, device=None):
        return "no such item (4)"

    monkeypatch.setattr(m, "execute_mikrotik_command", absent, raising=True)

    out = _run(m.mikrotik_move_ipv6_filter_rule(ctx, rule_id="*99", destination=1))
    assert "not found" in out

# ---------------------------------------------------------------------------
# review follow-ups: match-all warning (#111/#132) and update on a missing rule
# ---------------------------------------------------------------------------

def test_create_warns_when_no_match_conditions(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    out = _run(m.mikrotik_create_ipv6_filter_rule(ctx, chain="forward", action="drop"))
    assert out.startswith("WARNING: this rule has no match conditions")
    assert "'forward'" in out and "'drop'" in out
    ctx.warning.assert_awaited()


def test_create_does_not_warn_when_a_match_condition_is_present(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    out = _run(m.mikrotik_create_ipv6_filter_rule(
        ctx, chain="forward", action="drop", protocol="icmpv6"))
    assert "WARNING" not in out


def test_create_ipv6_only_match_field_counts_as_a_condition(ctx, monkeypatch):
    """hop_limit et al are real matches; they must suppress the warning."""
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    out = _run(m.mikrotik_create_ipv6_filter_rule(
        ctx, chain="input", action="drop", hop_limit="equal:255"))
    assert "WARNING" not in out


def test_update_missing_rule_is_not_reported_as_success(ctx, monkeypatch):
    """RouterOS says "no such item (4)" — neither "failure:" nor "error"."""
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    async def absent(command, _ctx, device=None):
        return "no such item (4)"

    monkeypatch.setattr(m, "execute_mikrotik_command", absent, raising=True)

    out = _run(m.mikrotik_update_ipv6_filter_rule(ctx, rule_id="*99", disabled=True))
    assert "not found" in out
    assert "updated successfully" not in out


def test_disable_on_missing_rule_does_not_claim_success(ctx, monkeypatch):
    """enable/disable delegate to update, so they inherit the guard."""
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    async def absent(command, _ctx, device=None):
        return "no such item (4)"

    monkeypatch.setattr(m, "execute_mikrotik_command", absent, raising=True)

    out = _run(m.mikrotik_disable_ipv6_filter_rule(ctx, rule_id="*99"))
    assert "not found" in out
    assert "successfully" not in out


def test_update_requires_real_content_before_claiming_success(ctx, monkeypatch):
    """A legend-only details print must not read as a successful update."""
    from mcp_mikrotik.scope import ipv6_firewall_filter as m

    async def legend(command, _ctx, device=None):
        if "count-only" in command:
            return "1"
        if "print detail" in command:
            return "Flags: X - disabled, I - invalid; D - dynamic"
        return ""

    monkeypatch.setattr(m, "execute_mikrotik_command", legend, raising=True)

    out = _run(m.mikrotik_update_ipv6_filter_rule(ctx, rule_id="*1", disabled=True))
    assert out.startswith("Failed to update IPv6 firewall filter rule:")
