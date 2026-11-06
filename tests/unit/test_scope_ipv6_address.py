"""Unit tests for the IPv6 address scope (issue #92)."""

import asyncio

from tests.conftest import FakeExecutor


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# add_ipv6_address — command construction
# ---------------------------------------------------------------------------

def test_add_minimal(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_address as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_add_ipv6_address(ctx, address="2001:db8::1/64", interface="ether1"))
    assert fake.commands[0] == "/ipv6 address add address=2001:db8::1/64 interface=ether1"


def test_add_all_options(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_address as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_add_ipv6_address(
        ctx, address="::1/64", interface="bridge",
        advertise=True, eui_64=True, from_pool="pool6", no_dad=True,
        comment="lan", disabled=True,
    ))
    cmd = fake.commands[0]
    assert cmd.startswith("/ipv6 address add address=::1/64 interface=bridge")
    assert "advertise=yes" in cmd
    assert "eui-64=yes" in cmd
    assert 'from-pool="pool6"' in cmd
    assert "no-dad=yes" in cmd
    assert 'comment="lan"' in cmd
    assert "disabled=yes" in cmd


def test_add_advertise_false_is_explicit(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_address as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_add_ipv6_address(ctx, address="2001:db8::1/64", interface="ether1", advertise=False))
    assert "advertise=no" in fake.commands[0]


def test_add_no_broadcast_field(ctx, monkeypatch):
    """IPv6 has no broadcast — make sure we never emit one."""
    from mcp_mikrotik.scope import ipv6_address as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_add_ipv6_address(ctx, address="2001:db8::1/64", interface="ether1"))
    assert "broadcast" not in fake.commands[0]


# ---------------------------------------------------------------------------
# list_ipv6_addresses — filters
# ---------------------------------------------------------------------------

def test_list_no_filters(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_address as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_list_ipv6_addresses(ctx))
    assert fake.commands[0] == "/ipv6 address print"


def test_list_with_filters(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_address as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_list_ipv6_addresses(
        ctx, interface_filter="ether1", address_filter="2001:db8",
        global_only=True, link_local_only=False, dynamic_only=True, disabled_only=True,
    ))
    cmd = fake.commands[0]
    assert cmd.startswith("/ipv6 address print where ")
    assert 'interface="ether1"' in cmd
    assert 'address~"2001:db8"' in cmd
    assert "global=yes" in cmd
    assert "dynamic=yes" in cmd
    assert "disabled=yes" in cmd


def test_list_link_local_filter(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_address as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_list_ipv6_addresses(ctx, link_local_only=True))
    assert fake.commands[0] == "/ipv6 address print where link-local=yes"


def test_list_empty_message(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_address as m

    async def fake(cmd, _ctx, device=None):
        return ""

    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)
    out = _run(m.mikrotik_list_ipv6_addresses(ctx))
    assert "No IPv6 addresses found" in out


# ---------------------------------------------------------------------------
# get / remove — id-or-address resolution
# ---------------------------------------------------------------------------

def test_get_by_id_queries_id_first(ctx, monkeypatch):
    """A non-colon value (a RouterOS id) is queried by .id first."""
    from mcp_mikrotik.scope import ipv6_address as m

    calls = []

    async def fake(cmd, _ctx, device=None):
        calls.append(cmd)
        return "address=2001:db8::1/64 interface=ether1"  # real entry data

    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)
    out = _run(m.mikrotik_get_ipv6_address(ctx, address_id="*1"))
    assert calls[0] == '/ipv6 address print detail where .id=*1'
    assert "IPV6 ADDRESS DETAILS" in out


def test_get_by_address_queries_address_first(ctx, monkeypatch):
    """A value containing ':' (an IPv6 address) is queried by address first."""
    from mcp_mikrotik.scope import ipv6_address as m

    calls = []

    async def fake(cmd, _ctx, device=None):
        calls.append(cmd)
        return "address=2001:db8::1/64 interface=ether1"

    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)
    out = _run(m.mikrotik_get_ipv6_address(ctx, address_id="2001:db8::1/64"))
    assert calls[0] == '/ipv6 address print detail where address="2001:db8::1/64"'
    assert "IPV6 ADDRESS DETAILS" in out


def test_get_legend_only_is_treated_as_not_found(ctx, monkeypatch):
    """Regression (caught live): `print detail` returns the Flags legend even
    when nothing matches — that must NOT be reported as a found entry."""
    from mcp_mikrotik.scope import ipv6_address as m

    legend = "Flags: X - disabled, I - invalid; D - dynamic; G - global, L - link-local"

    async def fake(cmd, _ctx, device=None):
        return legend  # non-empty, but no real "address=" row

    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)
    out = _run(m.mikrotik_get_ipv6_address(ctx, address_id="2001:db8::1/64"))
    assert "not found" in out


def test_remove_by_id(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_address as m

    async def fake(cmd, _ctx, device=None):
        if "count-only" in cmd:
            return "1"      # found by id
        return ""           # remove succeeds

    seen = []
    async def tracking(cmd, _ctx, device=None):
        seen.append(cmd)
        return await fake(cmd, _ctx)

    monkeypatch.setattr(m, "execute_mikrotik_command", tracking, raising=True)
    out = _run(m.mikrotik_remove_ipv6_address(ctx, address_id="*2"))
    assert '/ipv6 address remove *2' in seen
    assert "removed successfully" in out


def test_remove_not_found(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_address as m

    async def fake(cmd, _ctx, device=None):
        return "0"  # count-only returns 0 for both id and address

    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)
    out = _run(m.mikrotik_remove_ipv6_address(ctx, address_id="nope"))
    assert "not found" in out


# ---------------------------------------------------------------------------
# IPv6 address normalization (review finding) — non-canonical input must match
# the RouterOS-canonical stored form (lowercase, zero-compressed).
# ---------------------------------------------------------------------------

def test_get_canonicalizes_noncanonical_address(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_address as m

    calls = []

    async def fake(cmd, _ctx, device=None):
        calls.append(cmd)
        return "address=2001:db8::1/64 interface=ether1"

    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)
    # Uppercase + expanded zeros -> must be normalized to 2001:db8::1/64
    _run(m.mikrotik_get_ipv6_address(ctx, address_id="2001:DB8:0:0::1/64"))
    assert calls[0] == '/ipv6 address print detail where address="2001:db8::1/64"'


def test_remove_by_address_path_canonicalized(ctx, monkeypatch):
    """The primary real-world path: .id lookup misses, address lookup matches,
    and the input is canonicalized before the remove."""
    from mcp_mikrotik.scope import ipv6_address as m

    seen = []

    async def fake(cmd, _ctx, device=None):
        seen.append(cmd)
        if "count-only" in cmd:
            return "0" if ".id=" in cmd else "1"
        return ""  # remove succeeds

    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)
    out = _run(m.mikrotik_remove_ipv6_address(ctx, address_id="2001:DB8::1/64"))
    assert '/ipv6 address remove [find address="2001:db8::1/64"]' in seen
    assert "removed successfully" in out


# ---------------------------------------------------------------------------
# from_pool / eui_64 confirmation + failure paths (review findings)
# ---------------------------------------------------------------------------

def test_add_from_pool_confirms_via_interface(ctx, monkeypatch):
    """With from_pool the stored address differs from the input, so the
    confirmation must look up by interface, not by the (host-only) input."""
    from mcp_mikrotik.scope import ipv6_address as m

    seen = []

    async def fake(cmd, _ctx, device=None):
        seen.append(cmd)
        if cmd.startswith("/ipv6 address add"):
            return ""  # success
        if 'print detail where interface="bridge"' in cmd:
            return "address=2001:db8:abcd::1/64 from-pool=pool6 interface=bridge"
        return ""

    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)
    out = _run(m.mikrotik_add_ipv6_address(ctx, address="::1/64", interface="bridge", from_pool="pool6"))
    assert any('print detail where interface="bridge"' in c for c in seen)
    assert "added successfully" in out.lower()
    assert "2001:db8:abcd::1" in out


def test_add_failure_path(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_address as m

    async def fake(cmd, _ctx, device=None):
        return "failure: already have such address"

    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)
    out = _run(m.mikrotik_add_ipv6_address(ctx, address="2001:db8::1/64", interface="ether1"))
    assert "Failed to add IPv6 address" in out


def test_remove_by_positional_number(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_address as m

    seen = []

    async def fake(cmd, _ctx, device=None):
        seen.append(cmd)
        if "pick" in cmd:
            return "*5A"
        if "count-only where .id=*5A" in cmd:
            return "1"
        return ""

    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)
    out = _run(m.mikrotik_remove_ipv6_address(ctx, address_id="0"))
    assert "/ipv6 address remove *5A" in seen
    assert "removed successfully" in out.lower()


def test_remove_by_internal_id(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_address as m

    seen = []

    async def fake(cmd, _ctx, device=None):
        seen.append(cmd)
        if "count-only where .id=*1" in cmd:
            return "1"
        return ""

    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)
    out = _run(m.mikrotik_remove_ipv6_address(ctx, address_id="*1"))
    assert "/ipv6 address remove *1" in seen
    assert "removed successfully" in out.lower()


def test_remove_failure_path(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipv6_address as m

    async def fake(cmd, _ctx, device=None):
        if "count-only" in cmd:
            return "1"  # found by id
        return "failure: cannot remove"

    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)
    out = _run(m.mikrotik_remove_ipv6_address(ctx, address_id="*1"))
    assert "Failed to remove IPv6 address" in out
