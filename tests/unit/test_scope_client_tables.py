import asyncio

import pytest

from tests.conftest import FakeExecutor


def _run(coro):
    return asyncio.run(coro)


class DetailFake(FakeExecutor):
    """FakeExecutor whose print output looks like a real `print detail` row,
    since the tools check for `address=` to distinguish it from the
    Flags-legend-only output RouterOS returns on a no-match."""

    async def __call__(self, command, _ctx, device=None):
        result = await super().__call__(command, _ctx, device)
        return 'address="192.0.2.1" ' + result if "print" in command.lower() else result


def test_dhcp_lease_commands_and_device(ctx, monkeypatch):
    from mcp_mikrotik.scope.dhcp import dhcp

    fake = DetailFake()
    monkeypatch.setattr(dhcp, "execute_mikrotik_command", fake, raising=True)

    out = _run(dhcp.mikrotik_list_dhcp_leases(ctx, device="edge"))
    assert fake.commands == ["/ip dhcp-server lease print detail"]
    assert fake.devices == ["edge"]
    assert out.startswith("DHCP LEASES:")

    _run(dhcp.mikrotik_list_dhcp_leases(
        ctx, address_filter="192.0.2", mac_filter="AA:BB", client_id_filter="client",
        server_filter="lan", status_filter="bound", lease_time_filter="1d",
        last_seen_within="1h", hostname_filter="laptop", class_id_filter="vendor",
    ))
    assert fake.commands[-1] == (
        '/ip dhcp-server lease print detail where active-address~"192.0.2" '
        'active-mac-address~"AA:BB" active-client-id~"client" '
        'active-host-name~"laptop" active-class-id~"vendor" '
        'active-server="lan" status="bound" lease-time="1d" last-seen<=1h '
        'last-seen!="never"'
    )


def test_dhcpv6_binding_commands(ctx, monkeypatch):
    from mcp_mikrotik.scope.dhcp import dhcp

    fake = DetailFake()
    monkeypatch.setattr(dhcp, "execute_mikrotik_command", fake, raising=True)

    _run(dhcp.mikrotik_list_dhcpv6_bindings(ctx))
    assert fake.commands[-1] == "/ipv6 dhcp-server binding print detail"

    _run(dhcp.mikrotik_list_dhcpv6_bindings(
        ctx, address_filter="2001:db8", duid_filter="0001", iaid_filter="7",
        server_filter="v6", status_filter="bound", lease_time_filter="3d",
        last_seen_within="24h",
    ))
    assert fake.commands[-1] == (
        '/ipv6 dhcp-server binding print detail where address~"2001:db8" '
        'duid~"0001" iaid="7" server="v6" status="bound" life-time="3d" '
        'last-seen<=24h last-seen!="never"'
    )


@pytest.mark.parametrize("function_name", ["mikrotik_list_dhcp_leases", "mikrotik_list_dhcpv6_bindings"])
def test_last_seen_duration_validation(function_name, ctx, monkeypatch):
    from mcp_mikrotik.scope.dhcp import dhcp

    fake = DetailFake()
    monkeypatch.setattr(dhcp, "execute_mikrotik_command", fake, raising=True)

    out = _run(getattr(dhcp, function_name)(ctx, last_seen_within='1h] do={/system reboot}'))
    assert out.startswith("Invalid last_seen_within duration")
    assert fake.commands == []


def test_neighbor_commands_and_filters(ctx, monkeypatch):
    from mcp_mikrotik.scope.ip import neighbors

    fake = DetailFake()
    monkeypatch.setattr(neighbors, "execute_mikrotik_command", fake, raising=True)

    _run(neighbors.mikrotik_list_arp_entries(
        ctx, address_filter="192.0.2", mac_filter="AA:BB",
        interface_filter="bridge", status_filter="reachable",
    ))
    assert fake.commands[-1] == (
        '/ip arp print detail where address~"192.0.2" mac-address~"AA:BB" '
        'interface="bridge" status="reachable"'
    )

    out = _run(neighbors.mikrotik_list_ipv6_neighbors(
        ctx, address_filter="fe80", mac_filter="AA:BB",
        interface_filter="bridge", status_filter="reachable", device="edge",
    ))
    assert fake.commands[-1] == (
        '/ipv6 neighbor print detail where address~"fe80" mac-address~"AA:BB" '
        'interface="bridge" status="reachable"'
    )
    assert fake.devices[-1] == "edge"
    assert out.startswith("IPV6 NEIGHBORS:")


def test_client_table_tools_are_read_only():
    from mcp_mikrotik.app import mcp

    names = {"list_dhcp_leases", "list_dhcpv6_bindings", "list_arp_entries", "list_ipv6_neighbors"}
    tools = {tool.name: tool for tool in _run(mcp.list_tools()) if tool.name in names}
    assert tools.keys() == names
    assert all(tool.annotations.read_only_hint is True for tool in tools.values())


def test_empty_results(ctx, monkeypatch):
    from mcp_mikrotik.scope.dhcp import dhcp
    from mcp_mikrotik.scope.ip import neighbors

    async def empty(command, _ctx, device=None):
        return ""

    monkeypatch.setattr(dhcp, "execute_mikrotik_command", empty, raising=True)
    monkeypatch.setattr(neighbors, "execute_mikrotik_command", empty, raising=True)

    assert "No DHCP leases" in _run(dhcp.mikrotik_list_dhcp_leases(ctx))
    assert "No DHCPv6 bindings" in _run(dhcp.mikrotik_list_dhcpv6_bindings(ctx))
    assert "No ARP entries" in _run(neighbors.mikrotik_list_arp_entries(ctx))
    assert "No IPv6 neighbors" in _run(neighbors.mikrotik_list_ipv6_neighbors(ctx))


@pytest.mark.parametrize("function_name,expected", [
    ("mikrotik_list_dhcp_leases", "No DHCP leases"),
    ("mikrotik_list_dhcpv6_bindings", "No DHCPv6 bindings"),
])
def test_dhcp_legend_only_is_treated_as_no_results(function_name, expected, ctx, monkeypatch):
    # RouterOS `print detail` returns a non-empty Flags legend even when no
    # row matches; a bare non-emptiness check would mistake that for a hit.
    from mcp_mikrotik.scope.dhcp import dhcp

    async def legend_only(command, _ctx, device=None):
        return "Flags: X - disabled, D - dynamic"

    monkeypatch.setattr(dhcp, "execute_mikrotik_command", legend_only, raising=True)
    out = _run(getattr(dhcp, function_name)(ctx))
    assert expected in out


@pytest.mark.parametrize("function_name,expected", [
    ("mikrotik_list_arp_entries", "No ARP entries"),
    ("mikrotik_list_ipv6_neighbors", "No IPv6 neighbors"),
])
def test_neighbor_legend_only_is_treated_as_no_results(function_name, expected, ctx, monkeypatch):
    from mcp_mikrotik.scope.ip import neighbors

    async def legend_only(command, _ctx, device=None):
        return "Flags: X - disabled, D - dynamic"

    monkeypatch.setattr(neighbors, "execute_mikrotik_command", legend_only, raising=True)
    out = _run(getattr(neighbors, function_name)(ctx))
    assert expected in out
