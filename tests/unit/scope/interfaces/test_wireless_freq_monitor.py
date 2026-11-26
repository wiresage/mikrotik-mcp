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

    out = _run(m.mikrotik_monitor_wireless_frequency(ctx, interface="wlan5", duration=5, device="SmarkyDSL"))

    assert fake.commands == ['/interface wireless frequency-monitor "wlan5" duration=5']
    assert "FREQUENCY MONITOR (wlan5):" in out
    assert "5180MHz  3.2%  -103" in out
    assert "5200MHz  4.9%  -102" in out


def test_frequency_monitor_last_frame(ctx, monkeypatch):
    """monitor_wireless_frequency filters out earlier frames if multiple frames were drawn."""
    output_frames = (
        "Columns: FREQ, USE, NF\nFREQ USE NF\n5180MHz 1.0% -103\n"
        "Columns: FREQ, USE, NF\nFREQ USE NF\n5180MHz 3.5% -101\n5200MHz 0.5% -102"
    )
    fake = MultiFakeExecutor({"frequency-monitor": output_frames})
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    async def fake_detect(_ctx, device=None):
        return "/interface wireless"

    monkeypatch.setattr(m, "mikrotik_detect_wireless_interface_type", fake_detect, raising=True)

    out = _run(m.mikrotik_monitor_wireless_frequency(ctx, interface="wlan5", duration=2))

    assert "5180MHz 3.5% -101" in out
    assert "5180MHz 1.0% -103" not in out


def test_frequency_monitor_wifi_not_supported(ctx, monkeypatch):
    """monitor_wireless_frequency returns informative message on RouterOS v7 wifi interface."""
    async def fake_detect(_ctx, device=None):
        return "/interface wifi"

    monkeypatch.setattr(m, "mikrotik_detect_wireless_interface_type", fake_detect, raising=True)

    out = _run(m.mikrotik_monitor_wireless_frequency(ctx, interface="wifi5"))
    assert "only supported on legacy wireless interfaces" in out


def test_frequency_monitor_no_wireless_support(ctx, monkeypatch):
    """monitor_wireless_frequency returns error when device has no wireless support."""
    async def fake_detect(_ctx, device=None):
        return None

    monkeypatch.setattr(m, "mikrotik_detect_wireless_interface_type", fake_detect, raising=True)

    out = _run(m.mikrotik_monitor_wireless_frequency(ctx, interface="wlan1"))
    assert "Error: No wireless interface support detected" in out


def test_frequency_monitor_interface_not_found(ctx, monkeypatch):
    """monitor_wireless_frequency reports non-existent interface."""
    fake = MultiFakeExecutor({"frequency-monitor": "no such item (/interface/wireless/frequency-monitor; line 1)"})
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    async def fake_detect(_ctx, device=None):
        return "/interface wireless"

    monkeypatch.setattr(m, "mikrotik_detect_wireless_interface_type", fake_detect, raising=True)

    out = _run(m.mikrotik_monitor_wireless_frequency(ctx, interface="wlan99"))
    assert "Error: Wireless interface 'wlan99' not found." in out


def test_frequency_monitor_failure(ctx, monkeypatch):
    """monitor_wireless_frequency reports command failure."""
    fake = MultiFakeExecutor({"frequency-monitor": "failure: interface is disabled"})
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    async def fake_detect(_ctx, device=None):
        return "/interface wireless"

    monkeypatch.setattr(m, "mikrotik_detect_wireless_interface_type", fake_detect, raising=True)

    out = _run(m.mikrotik_monitor_wireless_frequency(ctx, interface="wlan1"))
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
    out = _run(m.mikrotik_monitor_wireless_frequency(ctx, interface=bad_name))
    assert "Error: Invalid or empty interface name" in out


def test_frequency_monitor_annotation():
    """Tool is registered as READ-only."""
    from mcp_mikrotik.app import mcp

    tools = {tool.name: tool for tool in _run(mcp.list_tools())}
    tool = tools.get("monitor_wireless_frequency")
    assert tool is not None
    assert tool.annotations.read_only_hint is True
    assert tool.annotations.title == "Monitor Wireless Frequency"


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


def _dual_band_listing(wlan1_flag):
    """Two legacy radios on frequency=auto, laid out the way RouterOS 7 prints /interface wireless (name first)."""
    record = (
        ' {n}  {flag} name="{name}" mtu=1500 l2mtu=1600 mac-address=48:8F:5A:00:00:0{n} arp=enabled\n'
        '       interface-type=Atheros AR9888 mode=ap-bridge ssid="home" frequency=auto\n'
        '       band={band} channel-width=20/40mhz-XX secondary-frequency=""\n\n'
    )
    return (
        "Flags: X - DISABLED; R - RUNNING\n"
        + record.format(n=0, flag=wlan1_flag, name="wlan1", band="2ghz-b/g/n")
        + record.format(n=1, flag="R", name="wlan2", band="5ghz-a/n/ac")
    )


def _dual_band_executor(listing, running, channels):
    commands = []

    async def fake(command, _ctx, device=None, redact=None):
        commands.append(command)
        if command.startswith("/interface wireless print proplist=name"):
            return "".join(f' {i}  R name="{name}"\n' for i, name in enumerate(running))
        if command.startswith("/interface wireless print"):
            return listing
        for name, channel in channels.items():
            if f'monitor "{name}" once as-value' in command:
                return channel
        return ""

    fake.commands = commands
    return fake


def _frequency_of(out, name):
    """The frequency=... text of one record of the listing."""
    record = out.split(f'name="{name}"', 1)[1].split("name=", 1)[0]
    return record.split("frequency=", 1)[1].split("\n", 1)[0].strip()


def test_list_wireless_interfaces_annotates_each_radio_with_its_own_channel(ctx, monkeypatch):
    """Dual-band default config: both radios on frequency=auto. Each one gets its own channel, once."""
    channels = {"wlan1": "2437/20-Ce/gn(20dBm)", "wlan2": "5180/20-Ceee/ac/P(23dBm)"}
    fake = _dual_band_executor(_dual_band_listing("R"), ["wlan1", "wlan2"], channels)
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    out = _run(m.mikrotik_list_wireless_interfaces(ctx))

    assert _frequency_of(out, "wlan1") == "auto (active: 2437/20-Ce/gn(20dBm))"
    assert _frequency_of(out, "wlan2") == "auto (active: 5180/20-Ceee/ac/P(23dBm))"


def test_list_wireless_interfaces_leaves_a_radio_that_is_not_running_alone(ctx, monkeypatch):
    """A disabled radio above a running one keeps plain frequency=auto; the running one's channel stays on it."""
    channels = {"wlan2": "5180/20-Ceee/ac/P(23dBm)"}
    fake = _dual_band_executor(_dual_band_listing("X"), ["wlan2"], channels)
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    out = _run(m.mikrotik_list_wireless_interfaces(ctx))

    assert _frequency_of(out, "wlan1") == "auto"
    assert _frequency_of(out, "wlan2") == "auto (active: 5180/20-Ceee/ac/P(23dBm))"


@pytest.mark.parametrize("reply", [
    "Error executing command: timed out",
    "Error: connection refused",
    "expected end of command (line 1 column 40)",
    "input does not match any value of interface",
])
def test_list_wireless_interfaces_does_not_show_an_error_as_the_channel(ctx, monkeypatch, reply):
    """When the channel lookup fails, the listing keeps frequency=auto instead of showing the error as a channel."""
    fake = _dual_band_executor(_dual_band_listing("R"), ["wlan1", "wlan2"], {"wlan1": reply, "wlan2": reply})
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    out = _run(m.mikrotik_list_wireless_interfaces(ctx))

    assert "(active:" not in out


def test_list_wireless_interfaces_name_filter_quoted(ctx, monkeypatch):
    """name_filter is safely quoted via ros_quoted in both print and auto-check commands."""
    responses = {
        "/interface wireless print": ' 0 R name="wlan5" frequency=auto running=yes\n',
        "proplist=name where frequency=auto and running=yes": ' 0 R name="wlan5"\n',
        'monitor "wlan5" once as-value': '5200/20-eCee/ac/P(21dBm)',
    }
    fake = MultiFakeExecutor(responses)
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_list_wireless_interfaces(ctx, name_filter='wlan"5'))

    assert any('name~"wlan\\"5"' in cmd for cmd in fake.commands)
    assert any('proplist=name where frequency=auto and running=yes and name~"wlan\\"5"' in cmd for cmd in fake.commands)


def test_monitor_wireless_interface_ok(ctx, monkeypatch):
    """monitor_wireless_interface runs once snapshot and returns status."""
    fake = MultiFakeExecutor({"monitor": "status: running-ap\nchannel: 5200/20-eCee/ac/P(21dBm)\nnoise-floor: -102"})
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    async def fake_detect(_ctx, device=None):
        return "/interface wireless"

    monkeypatch.setattr(m, "mikrotik_detect_wireless_interface_type", fake_detect, raising=True)

    out = _run(m.mikrotik_monitor_wireless_interface(ctx, interface="wlan5"))
    assert fake.commands == ['/interface wireless monitor "wlan5" once']
    assert "WIRELESS MONITOR (wlan5):" in out
    assert "noise-floor: -102" in out


def test_monitor_wireless_interface_not_found(ctx, monkeypatch):
    """monitor_wireless_interface reports missing interface."""
    fake = MultiFakeExecutor({"monitor": "no such item"})
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    async def fake_detect(_ctx, device=None):
        return "/interface wireless"

    monkeypatch.setattr(m, "mikrotik_detect_wireless_interface_type", fake_detect, raising=True)

    out = _run(m.mikrotik_monitor_wireless_interface(ctx, interface="wlan99"))
    assert "Error: Wireless interface 'wlan99' not found." in out


def test_monitor_wireless_interface_failure(ctx, monkeypatch):
    """monitor_wireless_interface reports command failure."""
    fake = MultiFakeExecutor({"monitor": "failure: interface disabled"})
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    async def fake_detect(_ctx, device=None):
        return "/interface wireless"

    monkeypatch.setattr(m, "mikrotik_detect_wireless_interface_type", fake_detect, raising=True)

    out = _run(m.mikrotik_monitor_wireless_interface(ctx, interface="wlan1"))
    assert out.startswith("Failed to monitor wireless interface:")


def test_monitor_wireless_interface_invalid_name(ctx):
    """monitor_wireless_interface rejects invalid interface names."""
    out = _run(m.mikrotik_monitor_wireless_interface(ctx, interface="wlan1; reboot"))
    assert "Error: Invalid or empty interface name" in out


def test_monitor_wireless_interface_annotation():
    """monitor_wireless_interface is registered as READ-only."""
    from mcp_mikrotik.app import mcp

    tools = {tool.name: tool for tool in _run(mcp.list_tools())}
    tool = tools.get("monitor_wireless_interface")
    assert tool is not None
    assert tool.annotations.read_only_hint is True
    assert tool.annotations.title == "Monitor Wireless Interface"
