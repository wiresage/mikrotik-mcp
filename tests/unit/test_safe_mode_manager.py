"""Tests for SafeModeManager's interactive login bring-up.

A real RouterOS login is not just a prompt: fresh devices ask the software-
license question, and RouterOS 7.21+ interposes a "new password>" step on
every login while the admin password is empty.  enable() must answer both or
it times out on exactly the routers the test environment ships.
"""

from types import SimpleNamespace

import pytest

import mcp_mikrotik.safe_mode as safe_mode_mod
from mcp_mikrotik.config import DeviceConfig
from mcp_mikrotik.safe_mode import _EOC, SafeModeManager


class ScriptedChannel:
    """Interactive-shell double that releases output in response to input."""

    BANNER = "\r\n" * 5 + "  MMM      MMM       KKK\r\n  MikroTik RouterOS 7.21.4\r\n"

    def __init__(self, license_prompt=True, password_nag=True):
        self.sent = []
        self._pending = self.BANNER
        if license_prompt:
            self._pending += "Do you want to see the software license? [Y/n]: "
        elif password_nag:
            self._pending += "Change your password (Ctrl-C to skip)\r\nnew password> "
        else:
            self._pending += "[admin@RouterA-NL] > "
        self._password_nag = password_nag
        self._license_prompt = license_prompt

    def settimeout(self, _t):
        pass

    def recv_ready(self):
        return bool(self._pending)

    def recv(self, n):
        out, self._pending = self._pending[:n], self._pending[n:]
        return out.encode("utf-8")

    def send(self, data):
        self.sent.append(data)
        if data == "n" and self._license_prompt:
            self._license_prompt = False
            if self._password_nag:
                self._pending += "Change your password (Ctrl-C to skip)\r\nnew password> "
            else:
                self._pending += "\r\n[admin@RouterA-NL] > "
        elif data == "\x03" and self._password_nag:
            self._password_nag = False
            self._pending += "\r\n[admin@RouterA-NL] > "
        elif data == "\x18":
            self._pending += "\r\n[admin@RouterA-NL] <SAFE> > "

    def close(self):
        pass


class FakeSSH:
    def __init__(self, channel):
        self._channel = channel
        self.client = SimpleNamespace(invoke_shell=lambda **kw: channel)

    def connect(self):
        return True

    def disconnect(self):
        pass


@pytest.fixture()
def single_device_inventory(monkeypatch):
    import mcp_mikrotik.inventory as inv_mod

    device = DeviceConfig(title="RouterA", host="10.0.0.1")
    fake = SimpleNamespace(resolve=lambda title=None: device)
    monkeypatch.setattr(inv_mod, "get_inventory", lambda: fake)
    return device


def _patched_manager(monkeypatch, channel):
    monkeypatch.setattr(safe_mode_mod, "MikroTikSSHClient",
                        lambda **kw: FakeSSH(channel))
    return SafeModeManager("RouterA")


def test_get_safe_mode_manager_propagates_resolution_errors(monkeypatch):
    """A typo'd or omitted device must error — not fabricate a fresh manager.

    A phantom manager answers "safe mode is not active — nothing to commit"
    while the real device still holds uncommitted changes that revert when its
    session drops.
    """
    import mcp_mikrotik.inventory as inv_mod
    from mcp_mikrotik.inventory import DeviceNotFoundError

    def raising_resolve(title=None):
        raise DeviceNotFoundError("Unknown device 'Ghost'. Available: RouterA.")

    monkeypatch.setattr(
        inv_mod, "get_inventory",
        lambda: SimpleNamespace(resolve=raising_resolve),
    )

    with pytest.raises(DeviceNotFoundError):
        safe_mode_mod.get_safe_mode_manager("Ghost")


def test_safe_mode_tools_surface_resolution_errors(monkeypatch):
    """status/commit/rollback report the error instead of 'not active'."""
    import asyncio

    from mcp_mikrotik.inventory import DeviceNotFoundError
    from mcp_mikrotik.scope.devices import safe_mode as scope_safe_mode
    from unittest.mock import AsyncMock, MagicMock

    def raising(device=None):
        raise DeviceNotFoundError(
            "Unknown device 'Ghost'. Available devices: RouterA, RouterB."
        )

    monkeypatch.setattr(scope_safe_mode, "get_safe_mode_manager", raising)
    ctx = MagicMock()
    ctx.info = AsyncMock()

    for tool in (
        scope_safe_mode.mikrotik_safe_mode_status,
        scope_safe_mode.mikrotik_commit_safe_mode,
        scope_safe_mode.mikrotik_rollback_safe_mode,
        scope_safe_mode.mikrotik_enable_safe_mode,
    ):
        result = asyncio.run(tool(ctx, device="Ghost"))
        assert result.startswith("Error:"), result
        assert "RouterA" in result          # the choices are listed


def test_enable_answers_license_and_password_dialogs(monkeypatch, single_device_inventory):
    channel = ScriptedChannel(license_prompt=True, password_nag=True)
    mgr = _patched_manager(monkeypatch, channel)

    result = mgr.enable()

    assert "ENABLED" in result, result
    assert mgr.is_active
    # license declined, password step skipped, then Ctrl-X for safe mode
    assert channel.sent == ["n", "\x03", "\x18"]


def test_enable_skips_persistent_password_nag_alone(monkeypatch, single_device_inventory):
    """The nag repeats on every login while the password is empty."""
    channel = ScriptedChannel(license_prompt=False, password_nag=True)
    mgr = _patched_manager(monkeypatch, channel)

    result = mgr.enable()

    assert "ENABLED" in result, result
    assert channel.sent == ["\x03", "\x18"]


def test_enable_with_plain_prompt_sends_nothing_extra(monkeypatch, single_device_inventory):
    channel = ScriptedChannel(license_prompt=False, password_nag=False)
    mgr = _patched_manager(monkeypatch, channel)

    result = mgr.enable()

    assert "ENABLED" in result, result
    assert channel.sent == ["\x18"]


def test_login_answers_terminal_size_probe(monkeypatch, single_device_inventory):
    """The console measures the terminal and waits for the answer.

    An unanswered probe leaves the console half-initialised and RouterOS
    closes the channel when Ctrl-X asks for the safe-mode redraw.
    """
    channel = ScriptedChannel(license_prompt=False, password_nag=False)
    channel._pending = channel.BANNER + "\x1b[9999B\x1b[6n"

    original_send = channel.send

    def send(data):
        if data == "\x1b[50;220R":
            channel.sent.append(data)
            channel._pending += "\r\n[admin@RouterA-NL] > "
        else:
            original_send(data)

    channel.send = send
    mgr = _patched_manager(monkeypatch, channel)

    result = mgr.enable()

    assert "ENABLED" in result, result
    assert channel.sent == ["\x1b[50;220R", "\x18"]


def test_execute_returns_output_between_echo_and_sentinel(
    monkeypatch, single_device_inventory
):
    """execute() must return the command's output — not echo, not prompt."""
    channel = ScriptedChannel(license_prompt=False, password_nag=False)
    original_send = channel.send

    def send(data):
        if data.startswith("/system identity print"):
            channel.sent.append(data)
            # colored echo on the prompt line, real output, bare sentinel,
            # then a prompt fragment from a redraw — only the output survives
            # typing echo, then the console's history reprint of the same
            # line (without '>'), then output, sentinel, and redraw noise
            channel._pending += (
                f'\r\n[admin@RouterA-NL] <SAFE> > /system identity print; :put "{_EOC}"\r\n'
                f'[admin@RouterA-NL] <SAFE> /system identity print; :put "{_EOC}"\r\n'
                "  name: RouterA-NL\r\n"
                f"{_EOC}\r\n"
                "[admin@RouterA-NL] <SAFE>\r\n"
                "[admin@RouterA-NL] <SAFE> > "
            )
        else:
            original_send(data)

    channel.send = send
    mgr = _patched_manager(monkeypatch, channel)
    assert "ENABLED" in mgr.enable()

    out = mgr.execute("/system identity print")

    assert out == "name: RouterA-NL"
    assert channel.sent[-1] == f'/system identity print; :put "{_EOC}"\n'


def test_execute_ignores_prompt_shaped_fragment_arriving_before_output(
    monkeypatch, single_device_inventory
):
    """A redrawn prompt mid-stream must not end the read early."""
    channel = ScriptedChannel(license_prompt=False, password_nag=False)
    original_send = channel.send
    state = {"phase": 0}

    def send(data):
        if data.startswith("/ip firewall filter add"):
            channel.sent.append(data)
            # first only prompt + echo arrive (the old failure mode)...
            channel._pending += f"\r\n[admin@RouterA-NL] <SAFE> > {data.strip()}\r\n"
            state["phase"] = 1
        else:
            original_send(data)

    def recv(n):
        out, channel._pending = channel._pending[:n], channel._pending[n:]
        # ...and the sentinel only lands after the echo has fully drained
        if not channel._pending and state["phase"] == 1:
            channel._pending = f"{_EOC}\r\n[admin@RouterA-NL] <SAFE> > "
            state["phase"] = 2
        return out.encode("utf-8")

    channel.send = send
    channel.recv = recv
    mgr = _patched_manager(monkeypatch, channel)
    assert "ENABLED" in mgr.enable()

    out = mgr.execute("/ip firewall filter add chain=forward action=drop")

    assert out == ""          # a clean add produces no output — and no junk


def test_terminal_probe_split_across_chunks_is_still_answered(
    monkeypatch, single_device_inventory
):
    """A 4-byte probe can straddle two network reads; the answer must not be lost.

    The DA probe after each prompt is sent exactly once and gates the final
    "> ", so a missed probe stalls the console until a timeout.
    """
    channel = ScriptedChannel(license_prompt=False, password_nag=False)
    # Deliver the size probe split in the middle: "\x1b[6" ... "n"
    channel._pending = channel.BANNER + "\x1b[6"
    original_send = channel.send
    state = {"tail_sent": False}

    def recv(n):
        out, channel._pending = channel._pending[:n], channel._pending[n:]
        if not channel._pending and not state["tail_sent"]:
            channel._pending = "n"          # the probe's last byte arrives late
            state["tail_sent"] = True
        return out.encode("utf-8")

    def send(data):
        if data == "\x1b[50;220R":
            channel.sent.append(data)
            channel._pending += "\r\n[admin@RouterA-NL] > "
        else:
            original_send(data)

    channel.recv = recv
    channel.send = send
    mgr = _patched_manager(monkeypatch, channel)

    result = mgr.enable()

    assert "ENABLED" in result, result
    assert channel.sent == ["\x1b[50;220R", "\x18"]


def test_enable_accepts_ros721_success_message_without_safe_prompt(
    monkeypatch, single_device_inventory
):
    """RouterOS 7.21 confirms in prose; the <SAFE> prompt redraw may lag."""
    channel = ScriptedChannel(license_prompt=False, password_nag=False)

    def send(data):
        channel.sent.append(data)
        if data == "\x18":
            channel._pending += (
                "\r\nTaking Safe Mode session... Success!\r\n[admin@RouterA-NL] > "
            )

    channel.send = send
    mgr = _patched_manager(monkeypatch, channel)

    result = mgr.enable()

    assert "ENABLED" in result, result
    assert mgr.is_active
