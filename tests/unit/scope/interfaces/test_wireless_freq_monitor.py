"""Tests for frequency_monitor and list_wireless_interfaces auto-frequency enrichment."""

import asyncio
import pytest

from mcp_mikrotik.scope.interfaces import wireless as m


def _run(coro):
    return asyncio.run(coro)


class MultiFakeExecutor:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.default_reply = ""
        self.commands = []

    async def __call__(self, command, _ctx, device=None, redact=None):
        self.commands.append(command)
        for pattern, reply in self.responses.items():
            if pattern in command:
                return reply
        return self.default_reply


def test_frequency_monitor_legacy(ctx, monkeypatch):
    """frequency_monitor runs /interface wireless frequency-monitor with duration."""
    fake = MultiFakeExecutor({
        "frequency-monitor": "Columns: FREQ, USE, NF\nFREQ     USE   NF  \n5180MHz  3.2%  -103\n5200MHz  4.9%  -102"
    })
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    async def fake_detect(_ctx, device=None):
        return "/interface wireless"

    monkeypatch.setattr(m, "mikrotik_detect_wireless_interface_type", fake_detect, raising=True)

    out = _run(m.mikrotik_frequency_monitor(ctx, interface="wlan5", duration=5, device="SmarkyDSL"))

    assert fake.commands == ['/interface wireless frequency-monitor "wlan5" duration=5']
    assert "FREQUENCY MONITOR (wlan5):" in out
    assert "5180MHz  3.2%  -103" in out
    assert "5200MHz  4.9%  -102" in out


def test_frequency_monitor_last_frame(ctx, monkeypatch):
    """frequency_monitor filters out earlier frames if multiple frames were drawn."""
    output_frames = (
        "Columns: FREQ, USE, NF\nFREQ USE NF\n5180MHz 1.0% -103\n"
        "Columns: FREQ, USE, NF\nFREQ USE NF\n5180MHz 3.5% -101\n5200MHz 0.5% -102"
    )
    fake = MultiFakeExecutor({"frequency-monitor": output_frames})
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    async def fake_detect(_ctx, device=None):
        return "/interface wireless"

    monkeypatch.setattr(m, "mikrotik_detect_wireless_interface_type", fake_detect, raising=True)

    out = _run(m.mikrotik_frequency_monitor(ctx, interface="wlan5", duration=2))

    assert "5180MHz 3.5% -101" in out
    assert "5180MHz 1.0% -103" not in out


def test_frequency_monitor_wifi_not_supported(ctx, monkeypatch):
    """frequency_monitor returns informative message on RouterOS v7 wifi interface."""
    async def fake_detect(_ctx, device=None):
        return "/interface wifi"

    monkeypatch.setattr(m, "mikrotik_detect_wireless_interface_type", fake_detect, raising=True)

    out = _run(m.mikrotik_frequency_monitor(ctx, interface="wifi5"))
    assert "only supported on legacy wireless interfaces" in out


def test_frequency_monitor_no_wireless_support(ctx, monkeypatch):
    """frequency_monitor returns error when device has no wireless support."""
    async def fake_detect(_ctx, device=None):
        return None

    monkeypatch.setattr(m, "mikrotik_detect_wireless_interface_type", fake_detect, raising=True)

    out = _run(m.mikrotik_frequency_monitor(ctx, interface="wlan1"))
    assert "Error: No wireless interface support detected" in out


def test_frequency_monitor_interface_not_found(ctx, monkeypatch):
    """frequency_monitor reports non-existent interface."""
    fake = MultiFakeExecutor({"frequency-monitor": "no such item (/interface/wireless/frequency-monitor; line 1)"})
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    async def fake_detect(_ctx, device=None):
        return "/interface wireless"

    monkeypatch.setattr(m, "mikrotik_detect_wireless_interface_type", fake_detect, raising=True)

    out = _run(m.mikrotik_frequency_monitor(ctx, interface="wlan99"))
    assert "Error: Wireless interface 'wlan99' not found." in out


def test_frequency_monitor_failure(ctx, monkeypatch):
    """frequency_monitor reports command failure."""
    fake = MultiFakeExecutor({"frequency-monitor": "failure: interface is disabled"})
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    async def fake_detect(_ctx, device=None):
        return "/interface wireless"

    monkeypatch.setattr(m, "mikrotik_detect_wireless_interface_type", fake_detect, raising=True)

    out = _run(m.mikrotik_frequency_monitor(ctx, interface="wlan1"))
    assert out.startswith("Failed to monitor frequency:")
    assert "failure: interface is disabled" in out


@pytest.mark.parametrize("bad_name", [
    "wlan1; /system reboot",
    "wlan1\nreboot",
    "wlan1\r\nreboot",
    'wlan"1',
    "wlan 1",
    "wlan$foo",
    "   ",
])
def test_frequency_monitor_invalid_name(ctx, bad_name):
    """Invalid names are rejected without running commands."""
    out = _run(m.mikrotik_frequency_monitor(ctx, interface=bad_name))
    assert "Error: Invalid or empty interface name" in out


def test_frequency_monitor_annotation():
    """Tool is registered as READ-only."""
    from mcp_mikrotik.app import mcp

    tools = {tool.name: tool for tool in _run(mcp.list_tools())}
    tool = tools.get("frequency_monitor")
    assert tool is not None
    assert tool.annotations.read_only_hint is True
    assert tool.annotations.title == "Frequency Monitor"


def test_list_wireless_interfaces_auto_frequency_enriched(ctx, monkeypatch):
    """list_wireless_interfaces augments frequency=auto with the active channel."""
    responses = {
        "/interface wireless print": (
            'Flags: R - RUNNING\n'
            ' 0 R name="wlan2.4" frequency=2412 running=yes\n'
            ' 1 R name="wlan5" frequency=auto running=yes\n'
        ),
        'proplist=name where frequency=auto and running=yes': (
            'Flags: R - RUNNING\n'
            ' 1 R name="wlan5"\n'
        ),
        'monitor "wlan5" once as-value': (
            '5200/20-eCee/ac/P(21dBm)'
        ),
    }
    fake = MultiFakeExecutor(responses)
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    out = _run(m.mikrotik_list_wireless_interfaces(ctx))

    assert "frequency=2412" in out
    assert "frequency=auto (active: 5200/20-eCee/ac/P(21dBm))" in out


def test_list_wireless_interfaces_auto_frequency_unchanged_when_no_active_channel(ctx, monkeypatch):
    """If channel query fails or interface is not running, frequency=auto remains intact."""
    responses = {
        "/interface wireless print": (
            'Flags: X - DISABLED\n'
            ' 0 X name="wlan5" frequency=auto running=no\n'
        ),
        'proplist=name where frequency=auto and running=yes': '',
    }
    fake = MultiFakeExecutor(responses)
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    out = _run(m.mikrotik_list_wireless_interfaces(ctx))

    assert "frequency=auto" in out
    assert "(active:" not in out
