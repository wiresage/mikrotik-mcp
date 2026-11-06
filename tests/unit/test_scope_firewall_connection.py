import asyncio
import pytest

from tests.conftest import FakeExecutor


def _run(coro):
    return asyncio.run(coro)


class ConntrackFake(FakeExecutor):
    async def __call__(self, command, _ctx, device=None):
        await super().__call__(command, _ctx, device)
        if "tracking print" in command:
            return "enabled: auto\ntotal-entries: 250\nmax-entries: 94208\ntcp-established-timeout: 1d"
        if "tracking set" in command:
            return ""
        if "count-only" in command:
            return "42\n"
        if "remove" in command:
            return ""
        if "print detail" in command:
            if "192.0.2.254" in command:
                return "Flags: S - SEEN-REPLY\n"
            return " 0 SACFs  protocol=tcp src-address=10.5.167.92 src-port=58295 dst-address=1.1.1.1 dst-port=443 tcp-state=established"
        return ""


def test_get_connection_tracking_settings(ctx, monkeypatch):
    from mcp_mikrotik.scope import firewall_connection

    fake = ConntrackFake()
    monkeypatch.setattr(firewall_connection, "execute_mikrotik_command", fake, raising=True)

    res = _run(firewall_connection.mikrotik_get_connection_tracking_settings(ctx, device="r1"))
    assert "CONNECTION TRACKING SETTINGS:" in res
    assert "total-entries: 250" in res
    assert fake.commands[-1] == "/ip firewall connection tracking print"
    assert fake.devices[-1] == "r1"


def test_update_connection_tracking_settings(ctx, monkeypatch):
    from mcp_mikrotik.scope import firewall_connection

    fake = ConntrackFake()
    monkeypatch.setattr(firewall_connection, "execute_mikrotik_command", fake, raising=True)

    # Success update
    res = _run(firewall_connection.mikrotik_update_connection_tracking_settings(
        ctx,
        tcp_established_timeout="12h",
        udp_timeout="30s",
        max_entries=100000,
        device="core"
    ))
    assert "Connection tracking settings updated successfully:" in res
    assert "/ip firewall connection tracking set tcp-established-timeout=12h udp-timeout=30s max-entries=100000" in fake.commands
    assert fake.devices[0] == "core"

    # Validation rejection for bad duration
    res_bad = _run(firewall_connection.mikrotik_update_connection_tracking_settings(
        ctx,
        tcp_established_timeout="12xyz"
    ))
    assert "Invalid tcp_established_timeout:" in res_bad


def test_get_connection_tracking_count(ctx, monkeypatch):
    from mcp_mikrotik.scope import firewall_connection

    fake = ConntrackFake()
    monkeypatch.setattr(firewall_connection, "execute_mikrotik_command", fake, raising=True)

    # Filtered count
    res = _run(firewall_connection.mikrotik_get_connection_tracking_count(
        ctx,
        protocol="tcp",
        tcp_state="established",
        dst_port=443,
        device="edge"
    ))
    assert "FIREWALL CONNECTION COUNT:" in res
    assert "42" in res
    assert fake.commands[-1] == '/ip firewall connection print count-only where protocol="tcp" tcp-state="established" dst-port=443'
    assert fake.devices[-1] == "edge"


def test_list_firewall_connections(ctx, monkeypatch):
    from mcp_mikrotik.scope import firewall_connection

    fake = ConntrackFake()
    monkeypatch.setattr(firewall_connection, "execute_mikrotik_command", fake, raising=True)

    # Found
    res = _run(firewall_connection.mikrotik_list_firewall_connections(
        ctx,
        src_address="10.5.167.92",
        protocol="tcp"
    ))
    assert "FIREWALL CONNECTIONS:" in res
    assert 'src-address~"10.5.167.92"' in fake.commands[-1]

    # Empty
    res_empty = _run(firewall_connection.mikrotik_list_firewall_connections(
        ctx,
        src_address="10.0.0.1",
        dst_address="192.0.2.254"
    ))
    assert "No firewall connections found matching the criteria." in res_empty


def test_remove_firewall_connections(ctx, monkeypatch):
    from mcp_mikrotik.scope import firewall_connection

    fake = ConntrackFake()
    monkeypatch.setattr(firewall_connection, "execute_mikrotik_command", fake, raising=True)

    # Rejected without filters
    res_no_filter = _run(firewall_connection.mikrotik_remove_firewall_connections(ctx))
    assert "At least one filter" in res_no_filter

    # Valid execution
    res = _run(firewall_connection.mikrotik_remove_firewall_connections(
        ctx,
        src_address="192.168.1.100",
        protocol="udp",
        device="gw"
    ))
    assert "Firewall connections terminated successfully." in res
    assert '/ip firewall connection remove [find where protocol="udp" src-address~"192.168.1.100"]' in fake.commands
