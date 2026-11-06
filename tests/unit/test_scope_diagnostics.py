"""Unit tests for the diagnostics scope (ping, traceroute, torch, quick sniffer, CPU profile)."""

import asyncio

import pytest

from tests.conftest import FakeExecutor


def _run(coro):
    return asyncio.run(coro)


class Reply(FakeExecutor):
    def __init__(self, reply):
        super().__init__()
        self.reply = reply

    async def __call__(self, command, _ctx, device=None, **kwargs):
        self.commands.append(command)
        self.devices.append(device)
        self.kwargs = kwargs
        return self.reply


@pytest.fixture()
def m():
    from mcp_mikrotik.scope import diagnostics
    return diagnostics


def _patch(monkeypatch, m, reply="output"):
    fake = Reply(reply)
    monkeypatch.setattr(m, "execute_mikrotik_command", fake)
    return fake


# --- ping -------------------------------------------------------------------

def test_ping_minimal(ctx, monkeypatch, m):
    fake = _patch(monkeypatch, m, "  SEQ HOST  SIZE TTL TIME\n    0 1.1.1.1 56 58 9ms\n    sent=1 received=1\n")
    out = _run(m.mikrotik_ping(ctx, address="1.1.1.1"))
    assert fake.commands == ["/ping address=1.1.1.1 count=4"]
    assert out.startswith("PING RESULT:")
    assert "received=1" in out


def test_ping_all_options(ctx, monkeypatch, m):
    fake = _patch(monkeypatch, m)
    _run(m.mikrotik_ping(ctx, address="2001:db8::1", count=2, size=1472, interval="200ms",
                         src_address="2001:db8::2", interface="ether1 WAN", routing_table="main",
                         ttl=64, do_not_fragment=True))
    assert fake.commands == [
        '/ping address=2001:db8::1 count=2 size=1472 interval=200ms src-address=2001:db8::2 '
        'interface="ether1 WAN" routing-table="main" ttl=64 do-not-fragment'
    ]


def test_ping_hostname(ctx, monkeypatch, m):
    fake = _patch(monkeypatch, m)
    _run(m.mikrotik_ping(ctx, address="example.com", count=1))
    assert fake.commands == ["/ping address=example.com count=1"]


@pytest.mark.parametrize("bad", ["1.1.1.1; /system reboot", "1.1.1.1 count=1000", "$(x)", '"a"', "[:put 1]"])
def test_ping_rejects_injection(ctx, monkeypatch, m, bad):
    fake = _patch(monkeypatch, m)
    out = _run(m.mikrotik_ping(ctx, address=bad))
    assert out.startswith("Failed to run ping: invalid address")
    assert fake.commands == []


def test_ping_quotes_interface(ctx, monkeypatch, m):
    fake = _patch(monkeypatch, m)
    _run(m.mikrotik_ping(ctx, address="10.0.0.1", interface='x" ; /system reboot "', arp_ping=True))
    assert 'interface="x\\" ; /system reboot \\""' in fake.commands[0]
    assert fake.commands[0].endswith("arp-ping=yes")


def test_ping_arp_needs_interface(ctx, monkeypatch, m):
    fake = _patch(monkeypatch, m)
    out = _run(m.mikrotik_ping(ctx, address="10.0.0.1", arp_ping=True))
    assert "needs interface" in out
    assert fake.commands == []


def test_ping_permission_refusal(ctx, monkeypatch, m):
    _patch(monkeypatch, m, "not enough permissions (9)\n")
    out = _run(m.mikrotik_ping(ctx, address="1.1.1.1"))
    assert out == "Failed to run ping: not enough permissions (9)"


# --- traceroute -------------------------------------------------------------

FRAME = "Columns: ADDRESS, LOSS, SENT, LAST\n#  ADDRESS   LOSS  SENT  LAST\n1  10.0.0.1  0%    {n}     1ms\n"


def test_traceroute_command_and_last_frame(ctx, monkeypatch, m):
    fake = _patch(monkeypatch, m, FRAME.format(n=1) + "\n" + FRAME.format(n=2) + "\n" + FRAME.format(n=3))
    out = _run(m.mikrotik_traceroute(ctx, address="9.9.9.9", count=3, max_hops=10, timeout="500ms"))
    assert fake.commands == [
        "/tool traceroute address=9.9.9.9 count=3 max-hops=10 protocol=icmp timeout=500ms use-dns=no"
    ]
    assert out.count("Columns:") == 1
    assert "0%    3" in out


def test_traceroute_udp_port(ctx, monkeypatch, m):
    fake = _patch(monkeypatch, m, FRAME.format(n=1))
    _run(m.mikrotik_traceroute(ctx, address="9.9.9.9", protocol="udp", port=33434, use_dns=True))
    assert "protocol=udp port=33434" in fake.commands[0]
    assert fake.commands[0].endswith("use-dns=yes")


def test_traceroute_ignores_port_for_icmp(ctx, monkeypatch, m):
    fake = _patch(monkeypatch, m, FRAME.format(n=1))
    _run(m.mikrotik_traceroute(ctx, address="9.9.9.9", port=33434))
    assert "port=" not in fake.commands[0]


# --- torch ------------------------------------------------------------------

def test_torch_default_breakdown(ctx, monkeypatch, m):
    fake = _patch(monkeypatch, m, FRAME.format(n=1))
    _run(m.mikrotik_torch(ctx, interface="ether1"))
    assert fake.commands == [
        '/tool torch interface="ether1" duration=5s src-address=0.0.0.0/0 dst-address=0.0.0.0/0 ip-protocol=any'
    ]


def test_torch_explicit_filters(ctx, monkeypatch, m):
    fake = _patch(monkeypatch, m, FRAME.format(n=1))
    _run(m.mikrotik_torch(ctx, interface="bridge", duration=10, src_address6="::/0",
                          ip_protocol="tcp", port="443", vlan_id="any"))
    assert fake.commands == [
        '/tool torch interface="bridge" duration=10s src-address6=::/0 ip-protocol=tcp port=443 vlan-id=any'
    ]


def test_torch_rejects_port_list(ctx, monkeypatch, m):
    fake = _patch(monkeypatch, m)
    out = _run(m.mikrotik_torch(ctx, interface="ether1", port="80,443"))
    assert "invalid port" in out
    assert fake.commands == []


# --- sniffer / profile ------------------------------------------------------

def test_sniff_command(ctx, monkeypatch, m):
    fake = _patch(monkeypatch, m, FRAME.format(n=1))
    _run(m.mikrotik_sniff_packets(ctx, interface="ether1", duration=3, ip_address="192.0.2.0/24",
                                  ip_protocol="udp", port="53,5353", mac_address="AA:BB:CC:DD:EE:FF"))
    assert fake.commands == [
        '/tool sniffer quick duration=3s interface="ether1" ip-address=192.0.2.0/24 ip-protocol=udp '
        "port=53,5353 mac-address=AA:BB:CC:DD:EE:FF"
    ]


def test_sniff_all_interfaces(ctx, monkeypatch, m):
    fake = _patch(monkeypatch, m, FRAME.format(n=1))
    _run(m.mikrotik_sniff_packets(ctx))
    assert fake.commands == ["/tool sniffer quick duration=5s"]


def test_sniff_rejects_bad_mac(ctx, monkeypatch, m):
    fake = _patch(monkeypatch, m)
    out = _run(m.mikrotik_sniff_packets(ctx, mac_address="AA:BB; /x"))
    assert "invalid mac_address" in out
    assert fake.commands == []


def test_profile(ctx, monkeypatch, m):
    fake = _patch(monkeypatch, m, "NAME CPU USAGE\nidle 0 97%\n")
    out = _run(m.mikrotik_profile_cpu(ctx, duration=3, cpu="all"))
    assert fake.commands == ["/tool profile duration=3s cpu=all"]
    assert "idle" in out


def test_empty_output_is_failure(ctx, monkeypatch, m):
    _patch(monkeypatch, m, "")
    out = _run(m.mikrotik_profile_cpu(ctx))
    assert out.startswith("Failed to run CPU profile")


# --- helpers ----------------------------------------------------------------

SNIFF = (
    "Columns: INTERFACE, TIME, NUM, SRC-ADDRESS\n1 0.1 1 10.0.0.1\n\n"
    "Columns: INTERFACE, TIME, NUM\n1 0.1 1\n2 1.1 2\n\n"
    "Columns: INTERFACE, TIME, NUM\n1 0.1 1\n2 1.1 2\n3 2.1 3\n"
)


def test_last_frame_when_header_changes(m):
    """Real sniffer output: the Columns line changes between frames (seen on RouterOS 7.24)."""
    assert m._last_frame(SNIFF) == "Columns: INTERFACE, TIME, NUM\n1 0.1 1\n2 1.1 2\n3 2.1 3"


def test_diagnostics_ask_for_a_wide_terminal(ctx, monkeypatch, m):
    fake = _patch(monkeypatch, m, FRAME.format(n=1))
    _run(m.mikrotik_torch(ctx, interface="ether1"))
    assert fake.kwargs == {"terminal_width": m.TERMINAL_WIDTH}


def test_last_frame_single_frame_unchanged(m):
    text = "Columns: A\n1 x\n"
    assert m._last_frame(text) == "Columns: A\n1 x"


def test_last_frame_handles_crlf(m):
    text = "H\r\n1\r\nH\r\n2\r\n"
    assert m._last_frame(text) == "H\n2"


def test_truncate(m):
    text = "\n".join(str(i) for i in range(m.MAX_OUTPUT_LINES + 5))
    out = m._truncate(text)
    assert out.endswith("(5 more lines not shown)")


def test_tools_are_read_only_and_open_world():
    from mcp_mikrotik.app import mcp
    tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
    for name in ("ping", "traceroute", "torch", "sniff_packets"):
        assert tools[name].annotations.read_only_hint is True
        assert tools[name].annotations.open_world_hint is True
    assert tools["profile_cpu"].annotations.read_only_hint is True
