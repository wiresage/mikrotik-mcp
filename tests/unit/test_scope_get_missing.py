"""A get_* tool for an item that does not exist must say "not found".

``print detail where ...`` prints the Flags legend even when nothing matches, so a reply that is only the
legend (which can run over several lines) used to be treated as a hit and returned as "<X> DETAILS:" with
nothing in it. That also meant get_ip_address never reached its fallback of looking the address up by value.
"""

import asyncio
import importlib

import pytest

from mcp_mikrotik.scope._selectors import has_item_rows

# the legend a router prints for an empty result, one line or several
LEGEND_ONE_LINE = "Flags: X - disabled, I - invalid; D - dynamic\r\n"
LEGEND_SEVERAL_LINES = (
    "Flags: D - dynamic; X - disabled, I - inactive, A - active; \r\n"
    "c - connect, s - static, r - rip, b - bgp, o - ospf, i - is-is, d - dhcp, v - vpn, m - modem, y - bgp-mpls-vpn;\r\n"
    "H - hw-offloaded; + - ecmp \r\n"
)
ROW = ' 0    ;;; a comment\r\n      name="thing" disabled=no\r\n'
ROW_NO_COMMENT = ' 1 R  name="other" address=10.0.0.1/24\r\n'


@pytest.mark.parametrize(
    "output,expected",
    [
        (None, False),
        ("", False),
        ("   \r\n", False),
        (LEGEND_ONE_LINE, False),
        (LEGEND_SEVERAL_LINES, False),
        (LEGEND_ONE_LINE + ROW, True),
        (LEGEND_SEVERAL_LINES + ROW_NO_COMMENT, True),
        (ROW, True),
        ("12 X  name=twelve", True),
    ],
)
def test_has_item_rows(output, expected):
    assert has_item_rows(output) is expected


#            module           tool                                 identifier keyword  menu words the "details" header has
TOOLS = [
    ("dhcp", "mikrotik_get_dhcp_server", "name", "DHCP SERVER DETAILS"),
    ("dns", "mikrotik_get_dns_static", "entry_id", "STATIC DNS ENTRY DETAILS"),
    ("firewall_nat", "mikrotik_get_nat_rule", "rule_id", "NAT RULE DETAILS"),
    ("interfaces", "mikrotik_get_interface", "name", "INTERFACE DETAILS"),
    ("ip_address", "mikrotik_get_ip_address", "address_id", "IP ADDRESS DETAILS"),
    ("queue", "mikrotik_get_queue_type", "name", "QUEUE TYPE DETAILS"),
    ("queue", "mikrotik_get_queue_tree", "name", "QUEUE TREE DETAILS"),
    ("queue", "mikrotik_get_simple_queue", "name", "SIMPLE QUEUE DETAILS"),
    ("routes", "mikrotik_get_route", "route_id", "ROUTE DETAILS"),
    ("users", "mikrotik_get_user", "name", "USER DETAILS"),
    ("vlan", "mikrotik_get_vlan_interface", "name", "VLAN INTERFACE DETAILS"),
    ("wireguard", "mikrotik_get_wireguard_interface", "name", "WIREGUARD INTERFACE DETAILS"),
    ("wireguard", "mikrotik_get_wireguard_peer", "peer_id", "WIREGUARD PEER DETAILS"),
    ("wireless", "mikrotik_get_wireless_interface", "name", "WIRELESS INTERFACE DETAILS"),
]


def run(coro):
    return asyncio.run(coro)


def answer(module, function, keyword, reply, ctx, monkeypatch):
    """Calls the tool; every ``print detail`` gets ``reply``, anything else a plausible answer."""
    mod = importlib.import_module(f"mcp_mikrotik.scope.{module}")
    seen = []

    async def execute(command, _ctx, device=None):
        seen.append(command)
        if "print detail" in command:
            return reply
        if "count-only" in command:
            return "1"
        return ""

    monkeypatch.setattr(mod, "execute_mikrotik_command", execute)
    return run(getattr(mod, function)(ctx, **{keyword: "*1" if keyword.endswith("_id") else "x"})), seen


@pytest.mark.parametrize("module,function,keyword,header", TOOLS, ids=[t[1] for t in TOOLS])
@pytest.mark.parametrize("legend", [LEGEND_ONE_LINE, LEGEND_SEVERAL_LINES], ids=["one-line legend", "multi-line legend"])
def test_a_legend_only_reply_is_not_found(module, function, keyword, header, legend, ctx, monkeypatch):
    result, _ = answer(module, function, keyword, legend, ctx, monkeypatch)

    assert "not found" in result
    assert header not in result


@pytest.mark.parametrize("module,function,keyword,header", TOOLS, ids=[t[1] for t in TOOLS])
def test_a_reply_with_an_item_is_returned(module, function, keyword, header, ctx, monkeypatch):
    result, _ = answer(module, function, keyword, LEGEND_ONE_LINE + ROW, ctx, monkeypatch)

    assert result.startswith(header + ":")
    assert 'name="thing"' in result
    assert "not found" not in result


@pytest.mark.parametrize("module,function,keyword,header", TOOLS, ids=[t[1] for t in TOOLS])
def test_a_silent_router_is_still_not_found(module, function, keyword, header, ctx, monkeypatch):
    result, _ = answer(module, function, keyword, "", ctx, monkeypatch)

    assert "not found" in result


def test_get_ip_address_falls_back_to_the_address_value(ctx, monkeypatch):
    """By id nothing matches (a legend comes back); by address value the row does."""
    from mcp_mikrotik.scope import ip_address as mod

    seen = []

    async def execute(command, _ctx, device=None):
        seen.append(command)
        if command.startswith('/ip address print detail where .id='):
            return LEGEND_ONE_LINE
        if command.startswith('/ip address print detail where address='):
            return LEGEND_ONE_LINE + ' 2    ;;; mine\r\n      address=10.78.0.1/24 interface=ether1\r\n'
        return ""

    monkeypatch.setattr(mod, "execute_mikrotik_command", execute)
    result = run(mod.mikrotik_get_ip_address(ctx, address_id="10.78.0.1/24"))

    assert result.startswith("IP ADDRESS DETAILS:")
    assert "10.78.0.1/24" in result
    assert seen == [
        '/ip address print detail where .id="10.78.0.1/24"',
        '/ip address print detail where address="10.78.0.1/24"',
    ]
