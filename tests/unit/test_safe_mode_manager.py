"""Tests for SafeModeManager's interactive login bring-up.

A real RouterOS login is not just a prompt: fresh devices ask the software-
license question, and RouterOS 7.21+ interposes a "new password>" step on
every login while the admin password is empty.  enable() must answer both or
it times out on exactly the routers the test environment ships.
"""

import re
import time
from types import SimpleNamespace

import pytest

import mcp_mikrotik.safe_mode as safe_mode_mod
from mcp_mikrotik.config import DeviceConfig
from mcp_mikrotik.safe_mode import SafeModeManager


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
        from mcp.server.mcpserver.exceptions import ToolError

        with pytest.raises(ToolError) as excinfo:
            asyncio.run(tool(ctx, device="Ghost"))
        result = str(excinfo.value)
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


class ConsoleSim:
    """A RouterOS console double that handles input strictly in order.

    Each line sent is echoed (prompt + typed text, wrapped at the 220-column
    terminal width like the real console) and then run: ``:put "x"`` prints
    x, other commands print what ``responses`` holds for them.  Ctrl+X
    toggles safe mode.  Closing the channel while still in safe mode is what
    makes RouterOS revert, so ``close()`` records whether that happened.

    Output can be held back by a number of ``recv_ready`` polls to model a
    console that answers late; later input still queues behind it, exactly
    as the real console handles keystrokes in order.
    """

    PROMPT_HEAD = "[admin@RouterA-NL]"
    WIDTH = 220

    def __init__(self, responses=None, parse_errors=None, release="ok",
                 release_delay=0, release_message=True):
        self.responses = responses or {}
        self.parse_errors = parse_errors or {}
        self.release = release            # "ok" | "stale-then-ok" | "ignore"
        self.release_delay = release_delay
        self.release_message = release_message
        self.safe = False
        self.sent = []
        self.events = []
        self.closed = False
        self.rolled_back = None
        self._pending = "\r\n" + self.prompt()
        self._queue = []                  # [polls_to_wait, text or callable]

    # -- rendering -------------------------------------------------------
    def prompt(self):
        return f"{self.PROMPT_HEAD} <SAFE> > " if self.safe else f"{self.PROMPT_HEAD} > "

    def _echo(self, line):
        typed = self.prompt() + line
        rows = [typed[i:i + self.WIDTH] for i in range(0, len(typed), self.WIDTH)]
        return "\r\n".join(rows) + "\r\n"

    def _run(self, line):
        out = self._echo(line)
        if line in self.parse_errors:
            return out + self.parse_errors[line] + "\r\n" + self.prompt()
        for part in line.split("; "):
            m = re.fullmatch(r':put "([^"]*)"', part)
            if m:
                out += m.group(1) + "\r\n"
                continue
            reply = self.responses.get(part, "")
            if isinstance(reply, Exception):
                return out + str(reply) + "\r\n" + self.prompt()   # script aborts
            if reply:
                out += reply + "\r\n"
        return out + self.prompt()

    # -- channel API ---------------------------------------------------------
    def settimeout(self, _t):
        pass

    def recv_ready(self):
        if not self._pending and self._queue:
            head = self._queue[0]
            if head[0] > 0:
                head[0] -= 1
            else:
                self._queue.pop(0)
                item = head[1]
                self._pending += item() if callable(item) else item
        return bool(self._pending)

    def recv(self, n):
        out, self._pending = self._pending[:n], self._pending[n:]
        return out.encode("utf-8")

    def send(self, data):
        self.sent.append(data)
        self.events.append(("send", data))
        if data == "\x18":
            self._ctrl_x()
        elif data.endswith("\n"):
            line = data[:-1]
            self._queue.append([0, lambda: self._run(line)])

    def _ctrl_x(self):
        if not self.safe:
            def take():
                self.safe = True
                return "\r\nTaking Safe Mode session... Success!\r\n" + self.prompt()
            self._queue.append([0, take])
            return

        def release():
            self.safe = False
            msg = "Releasing Safe Mode... Success!\r\n" if self.release_message else ""
            return "\r\n" + msg + self.prompt()

        if self.release == "ok":
            self._queue.append([self.release_delay, release])
        elif self.release == "stale-then-ok":
            # A redraw that looks like a plain prompt arrives first, while
            # RouterOS has not released the session yet.
            self._queue.append([0, "\r\n" + f"{self.PROMPT_HEAD} > "])
            self._queue.append([self.release_delay, release])
        else:  # "ignore": Ctrl+X never takes effect
            self._queue.append([0, "\r\n" + self.prompt()])

    def close(self):
        self.closed = True
        self.events.append(("close",))
        self.rolled_back = self.safe


def _sim_manager(monkeypatch, sim):
    mgr = _patched_manager(monkeypatch, sim)
    assert "ENABLED" in mgr.enable()
    assert sim.safe
    return mgr


# ---------------------------------------------------------------------------
# execute(): output between the BEGIN and END markers
# ---------------------------------------------------------------------------


def test_execute_returns_only_the_command_output(monkeypatch, single_device_inventory):
    sim = ConsoleSim(responses={"/system identity print": "  name: RouterA-NL"})
    mgr = _sim_manager(monkeypatch, sim)

    out = mgr.execute("/system identity print")

    assert out == "name: RouterA-NL"
    sent = sim.sent[-1]
    assert sent.startswith(':put "__MCP_SAFE_MODE_BEGIN_')
    assert '; /system identity print; :put "__MCP_SAFE_MODE_END_' in sent


def test_execute_survives_an_echo_wrapped_at_the_terminal_width(
    monkeypatch, single_device_inventory
):
    """A command longer than 220 columns wraps its echo, splitting the command
    and the markers across lines; none of those fragments may leak into the
    output (create_filter_rule then reported 'Failed' for a rule it created)."""
    cmd = (
        ':put [/ip firewall filter add chain=input action=accept dst-port=53,67,123 '
        'protocol=udp in-interface-list="GUEST" '
        'comment="guest: DNS/DHCP/NTP to router only" place-before="12"]'
    )
    sim = ConsoleSim(responses={cmd: "*1A"})
    mgr = _sim_manager(monkeypatch, sim)

    out = mgr.execute(cmd)

    assert out == "*1A"
    echo_rows = sim._echo(sim.sent[-1][:-1]).split("\r\n")
    assert len([r for r in echo_rows if r]) >= 2      # the echo really wrapped


def test_execute_ignores_stale_markers_from_an_earlier_command(
    monkeypatch, single_device_inventory
):
    sim = ConsoleSim(responses={"/system identity print": "  name: RouterA-NL"})
    mgr = _sim_manager(monkeypatch, sim)
    sim._pending += (
        "__MCP_SAFE_MODE_BEGIN_deadbeef__\r\nold output\r\n"
        "__MCP_SAFE_MODE_END_deadbeef__\r\n"
    )

    assert mgr.execute("/system identity print") == "name: RouterA-NL"


def test_execute_skips_redraws_between_the_markers(monkeypatch, single_device_inventory):
    sim = ConsoleSim(responses={
        "/ip address print": "0 10.0.0.1/24 ether1\r\n[admin@RouterA-NL] <SAFE>\r\n1 10.0.1.1/24 ether2",
    })
    mgr = _sim_manager(monkeypatch, sim)

    assert mgr.execute("/ip address print") == "0 10.0.0.1/24 ether1\n1 10.0.1.1/24 ether2"


def test_execute_waits_for_output_that_arrives_after_the_echo(
    monkeypatch, single_device_inventory
):
    """A prompt-shaped echo fragment must not end the read early."""
    sim = ConsoleSim(responses={"/ip firewall filter add chain=forward action=drop": ""})
    mgr = _sim_manager(monkeypatch, sim)
    original_run = sim._run

    def slow_run(line):
        # echo first; output, END and the prompt only some polls later
        full = original_run(line)
        echo = sim._echo(line)
        sim._queue.insert(0, [10, full[len(echo):]])
        return echo

    sim._run = slow_run

    assert mgr.execute("/ip firewall filter add chain=forward action=drop") == ""


def test_execute_returns_a_runtime_error_without_waiting_for_the_timeout(
    monkeypatch, single_device_inventory
):
    """A failing command aborts the line before END; its error is the output."""
    cmd = '/interface list add name="GUEST"'
    sim = ConsoleSim(responses={cmd: RuntimeError("failure: already have such entry")})
    mgr = _sim_manager(monkeypatch, sim)

    started = time.monotonic()
    out = mgr.execute(cmd)

    assert out == "failure: already have such entry"
    assert time.monotonic() - started < 5


def test_execute_returns_a_parse_error(monkeypatch, single_device_inventory):
    sim = ConsoleSim()
    mgr = _sim_manager(monkeypatch, sim)
    original_send = sim.send

    def send(data):
        if "/bogus" in data:
            sim.parse_errors[data[:-1]] = "bad command name bogus (line 1 column 40)"
        original_send(data)

    sim.send = send

    assert mgr.execute("/bogus") == "bad command name bogus (line 1 column 40)"


# ---------------------------------------------------------------------------
# commit(): close only after RouterOS has released safe mode
# ---------------------------------------------------------------------------


def test_commit_closes_only_after_safe_mode_is_released(monkeypatch, single_device_inventory):
    sim = ConsoleSim(release="ok")
    mgr = _sim_manager(monkeypatch, sim)

    result = mgr.commit()

    assert result.startswith("Changes committed successfully"), result
    assert "Releasing Safe Mode... Success!" in result   # the evidence is reported
    assert sim.closed and sim.rolled_back is False
    assert not mgr.is_active


def test_commit_does_not_trust_a_stale_prompt_redraw(monkeypatch, single_device_inventory):
    """The bug: a plain-looking prompt redraw arrived before RouterOS released
    the session, commit() closed the channel on it, and RouterOS reverted
    every change while the tool said 'committed successfully'."""
    sim = ConsoleSim(release="stale-then-ok", release_delay=15)
    mgr = _sim_manager(monkeypatch, sim)

    result = mgr.commit()

    assert result.startswith("Changes committed successfully"), result
    assert sim.rolled_back is False
    ctrl_x = sim.events.index(("send", "\x18"), 1)
    close = sim.events.index(("close",))
    # a state probe went out between Ctrl+X and the close
    assert any(e[0] == "send" and "__MCP_SAFE_MODE_BEGIN_" in e[1]
               for e in sim.events[ctrl_x + 1:close])


def test_commit_accepts_a_release_without_a_message(monkeypatch, single_device_inventory):
    sim = ConsoleSim(release="ok", release_message=False)
    mgr = _sim_manager(monkeypatch, sim)

    result = mgr.commit()

    assert result.startswith("Changes committed successfully"), result
    assert sim.rolled_back is False


def test_commit_never_reports_success_when_safe_mode_is_not_released(
    monkeypatch, single_device_inventory
):
    sim = ConsoleSim(release="ignore")
    mgr = _sim_manager(monkeypatch, sim)

    result = mgr.commit()

    assert result.startswith("Error:"), result
    assert "committed successfully" not in result
    assert "NOT persisted" in result
    # the session stays open, so nothing is reverted and the caller can retry
    assert not sim.closed
    assert mgr.is_active


def test_commit_retry_after_unconfirmed_release_does_not_toggle_safe_mode_back_on(
    monkeypatch, single_device_inventory
):
    """If Ctrl+X did take effect after all, a retry must not send another one
    (that would re-enter safe mode); it reports instead."""
    sim = ConsoleSim(release="ignore")
    mgr = _sim_manager(monkeypatch, sim)
    assert mgr.commit().startswith("Error:")
    sim.safe = False                      # the release happened late
    ctrl_x_count = sim.sent.count("\x18")

    result = mgr.commit()

    assert sim.sent.count("\x18") == ctrl_x_count
    assert result.startswith("Error:"), result
    assert "no longer in safe mode" in result


def test_commit_tool_raises_when_release_is_not_confirmed(ctx, monkeypatch):
    import asyncio

    from mcp.server.mcpserver.exceptions import ToolError
    from mcp_mikrotik.scope.devices import safe_mode as scope_safe_mode

    manager = SimpleNamespace(commit=lambda: "Error: RouterOS did not confirm ...")
    monkeypatch.setattr(scope_safe_mode, "get_safe_mode_manager", lambda device=None: manager)

    with pytest.raises(ToolError, match="did not confirm"):
        asyncio.run(scope_safe_mode.mikrotik_commit_safe_mode(ctx))
