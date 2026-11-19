"""MNDP neighbor listing (issue: expose /ip/neighbor).

`print detail` prints the Flags legend even when nothing matches, so the
empty check must look for real entry data. MNDP rows always carry `identity=`
but may announce no address, so this tool markers on `identity=` while the
ARP/IPv6 tools keep their `address=` default.
"""

import asyncio

from mcp_mikrotik.scope.ip import neighbors


def _call(ctx, monkeypatch, reply, **kwargs):
    """Run list_mikrotik_neighbors with a canned router reply."""
    seen = []

    async def fake(command, _ctx, device=None, **_kw):
        seen.append((command, device))
        return reply

    monkeypatch.setattr(neighbors, "execute_mikrotik_command", fake, raising=True)
    result = asyncio.run(neighbors.mikrotik_list_mikrotik_neighbors(ctx, **kwargs))
    return result, seen


ROW = (
    "Flags: X - disabled, R - running\n"
    " 0  R  identity=BranchA address=10.0.0.1 interface=ether1\n"
)


def test_no_filters_sends_a_bare_print(ctx, monkeypatch):
    _, seen = _call(ctx, monkeypatch, ROW)
    assert seen == [("/ip neighbor print detail", None)]


def test_filters_are_composed_in_the_where_clause(ctx, monkeypatch):
    _, seen = _call(
        ctx, monkeypatch, ROW,
        identity_filter="Branch", address_filter="10.0.", interface_filter="ether1",
    )
    assert seen == [(
        '/ip neighbor print detail where identity~"Branch" '
        'address~"10.0." interface="ether1"',
        None,
    )]


def test_the_device_title_is_passed_through(ctx, monkeypatch):
    _, seen = _call(ctx, monkeypatch, ROW, device="RouterA")
    assert seen == [("/ip neighbor print detail", "RouterA")]


def test_every_filter_value_is_ros_quoted(ctx, monkeypatch):
    """Identity is free text; address and interface need the same escaping.

    An unquoted `$` or `"` in any of the three ends the command early or is
    silently eaten by RouterOS (issue #135).
    """
    _, seen = _call(
        ctx, monkeypatch, ROW,
        identity_filter='Branch "HQ" $1',
        address_filter="10.0.0.$1",
        interface_filter='e"1',
    )
    command = seen[0][0]
    assert r'identity~"Branch \"HQ\" \$1"' in command
    assert r'address~"10.0.0.\$1"' in command
    assert r'interface="e\"1"' in command
    assert 'identity~"Branch "HQ" $1"' not in command


def test_a_flags_legend_without_an_entry_is_reported_as_empty(ctx, monkeypatch):
    result, _ = _call(
        ctx, monkeypatch, "Flags: X - disabled, R - running\n"
    )
    assert result == "No MikroTik neighbors found matching the criteria."


def test_a_neighbor_that_announced_no_address_still_counts(ctx, monkeypatch):
    """MNDP rows always carry identity= even when no address was announced."""
    reply = "Flags: X - disabled\n 0  R  identity=BranchA interface=ether1\n"
    result, _ = _call(ctx, monkeypatch, reply)
    assert result.startswith("MIKROTIK NEIGHBORS:")


def test_matching_rows_are_returned_with_the_heading(ctx, monkeypatch):
    result, _ = _call(ctx, monkeypatch, ROW)
    assert result.startswith("MIKROTIK NEIGHBORS:\n\n")
    assert "identity=BranchA" in result


def test_empty_reply_is_reported_as_empty(ctx, monkeypatch):
    result, _ = _call(ctx, monkeypatch, "")
    assert result == "No MikroTik neighbors found matching the criteria."


def test_arp_filters_are_escaped_too(ctx, monkeypatch):
    """The shared helper quotes every caller's filters, not just the MNDP one.

    Unescaped, a `"` ends the quoted string and a `;` starts a second command.
    """
    seen = []

    async def fake(command, _ctx, device=None, **_kw):
        seen.append(command)
        return ROW

    monkeypatch.setattr(neighbors, "execute_mikrotik_command", fake, raising=True)
    asyncio.run(
        neighbors.mikrotik_list_arp_entries(ctx, address_filter='x"; /system reboot; "')
    )

    assert seen == ['/ip arp print detail where address~"x\\"; /system reboot; \\""']


def test_arp_entries_keep_the_address_marker(ctx, monkeypatch):
    """The shared helper's default must not change the existing ARP tools."""
    seen = []

    async def fake(command, _ctx, device=None, **_kw):
        seen.append(command)
        return "Flags: X - disabled\n 0  R  address=10.0.0.1 interface=ether1\n"

    monkeypatch.setattr(neighbors, "execute_mikrotik_command", fake, raising=True)
    result = asyncio.run(neighbors.mikrotik_list_arp_entries(ctx))

    assert seen == ["/ip arp print detail"]
    assert result.startswith("ARP ENTRIES:")


def test_arp_entries_still_report_an_address_less_reply_as_empty(ctx, monkeypatch):
    async def fake(command, _ctx, device=None, **_kw):
        return "Flags: X - disabled, R - running\n"

    monkeypatch.setattr(neighbors, "execute_mikrotik_command", fake, raising=True)
    result = asyncio.run(neighbors.mikrotik_list_ipv6_neighbors(ctx))

    assert result == "No IPv6 neighbors found matching the criteria."
