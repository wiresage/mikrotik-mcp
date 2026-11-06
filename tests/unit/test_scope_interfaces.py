import asyncio
import pytest

from tests.conftest import FakeExecutor


def _run(coro):
    return asyncio.run(coro)


class InterfacesFake(FakeExecutor):
    async def __call__(self, command, _ctx, device=None):
        await super().__call__(command, _ctx, device)
        if "monitor-traffic" in command:
            if "nonexistent" in command:
                return "input does not match any value of interface"
            return "name: eth1\nrx-bits-per-second: 0bps\ntx-bits-per-second: 1000bps"
        if "ethernet monitor" in command:
            if "nonexistent" in command or "bridge" in command:
                return ""
            return "name: eth1\nstatus: link-ok\nrate: 1Gbps\nfull-duplex: yes"
        if "print detail" in command:
            if "nonexistent" in command:
                return "Flags: X - disabled, R - running\n"
            return " 0  R  name=\"eth1\" type=\"ether\" mtu=1500"
        if "print stats" in command:
            return "Flags: D - DYNAMIC\n # NAME RX-BYTE TX-BYTE\n 0 eth1 100 200"
        if "print" in command:
            return "Flags: D - DYNAMIC\n # NAME TYPE\n 0 eth1 ether"
        return ""


def test_list_interfaces_plain_and_stats(ctx, monkeypatch):
    from mcp_mikrotik.scope import interfaces

    fake = InterfacesFake()
    monkeypatch.setattr(interfaces, "execute_mikrotik_command", fake, raising=True)

    # Plain list
    res_plain = _run(interfaces.mikrotik_list_interfaces(ctx, device="r1"))
    assert "INTERFACES:" in res_plain
    assert fake.commands[-1] == "/interface print"
    assert fake.devices[-1] == "r1"

    # With stats=True
    res_stats = _run(interfaces.mikrotik_list_interfaces(ctx, stats=True, type_filter="ether", running_only=True))
    assert "INTERFACES:" in res_stats
    assert fake.commands[-1] == '/interface print stats where type="ether" running=yes'


def test_get_interface_found_and_missing(ctx, monkeypatch):
    from mcp_mikrotik.scope import interfaces

    fake = InterfacesFake()
    monkeypatch.setattr(interfaces, "execute_mikrotik_command", fake, raising=True)

    # Found
    res = _run(interfaces.mikrotik_get_interface(ctx, name="eth1"))
    assert "INTERFACE DETAILS:" in res
    assert 'where name="eth1"' in fake.commands[-1]

    # Missing
    res_missing = _run(interfaces.mikrotik_get_interface(ctx, name="nonexistent"))
    assert "Interface 'nonexistent' not found." in res_missing


def test_monitor_interface_traffic(ctx, monkeypatch):
    from mcp_mikrotik.scope import interfaces

    fake = InterfacesFake()
    monkeypatch.setattr(interfaces, "execute_mikrotik_command", fake, raising=True)

    # Success
    res = _run(interfaces.mikrotik_monitor_interface_traffic(ctx, name="eth1", device="core"))
    assert "INTERFACE TRAFFIC (eth1):" in res
    assert "rx-bits-per-second: 0bps" in res
    assert fake.commands[-1] == '/interface monitor-traffic interface="eth1" once'
    assert fake.devices[-1] == "core"

    # Missing interface
    res_missing = _run(interfaces.mikrotik_monitor_interface_traffic(ctx, name="nonexistent"))
    assert "Interface 'nonexistent' not found." in res_missing

    # Invalid name rejected before execution
    cmd_count = len(fake.commands)
    res_invalid = _run(interfaces.mikrotik_monitor_interface_traffic(ctx, name="eth1; /system reboot"))
    assert "Invalid interface name:" in res_invalid
    assert len(fake.commands) == cmd_count  # No command was sent!


def test_monitor_ethernet_interface(ctx, monkeypatch):
    from mcp_mikrotik.scope import interfaces

    fake = InterfacesFake()
    monkeypatch.setattr(interfaces, "execute_mikrotik_command", fake, raising=True)

    # Success
    res = _run(interfaces.mikrotik_monitor_ethernet_interface(ctx, name="eth1", device="edge"))
    assert "ETHERNET INTERFACE MONITOR (eth1):" in res
    assert "status: link-ok" in res
    assert "rate: 1Gbps" in res
    assert fake.commands[-1] == '/interface ethernet monitor [find name="eth1"] once'
    assert fake.devices[-1] == "edge"

    # Missing / non-ethernet
    res_missing = _run(interfaces.mikrotik_monitor_ethernet_interface(ctx, name="bridge-LAN"))
    assert "Ethernet interface 'bridge-LAN' not found." in res_missing

    # Invalid name rejected before execution
    cmd_count = len(fake.commands)
    res_invalid = _run(interfaces.mikrotik_monitor_ethernet_interface(ctx, name="eth$name"))
    assert "Invalid interface name:" in res_invalid
    assert len(fake.commands) == cmd_count
