"""Secrets must not reach the logs (issue #151).

The connector logs every command to the server log and sends it to the client
as a log notification, so a tool carrying a credential cannot keep it out of
either sink on its own. These tests pin both sinks.
"""

import asyncio
import io
import logging

import pytest

from mcp_mikrotik.connector import _redacted


SECRET = "SuperSecretWiFiPw123"


# ---------------------------------------------------------------------------
# the helper
# ---------------------------------------------------------------------------

def test_redacted_replaces_every_occurrence():
    text = f'set passphrase="{SECRET}" other="{SECRET}"'
    out = _redacted(text, [SECRET])
    assert SECRET not in out
    assert out.count("***") == 2


def test_redacted_is_a_noop_without_secrets():
    assert _redacted("nothing to hide", None) == "nothing to hide"
    assert _redacted("nothing to hide", []) == "nothing to hide"
    assert _redacted("nothing to hide", [""]) == "nothing to hide"


def test_longer_secrets_are_replaced_first():
    """A secret containing another must not leave a fragment behind."""
    out = _redacted("value=abc123456", ["abc123456", "abc"])
    assert out == "value=***"


# ---------------------------------------------------------------------------
# both sinks, through the real code path
# ---------------------------------------------------------------------------

def _run_command(monkeypatch, ctx, command, redact):
    """Drive execute_mikrotik_command with the device layer stubbed out."""
    from mcp_mikrotik import connector

    class FakeSafeMgr:
        is_active = False

    monkeypatch.setattr(connector, "get_safe_mode_manager", lambda *_: FakeSafeMgr(),
                        raising=False)
    monkeypatch.setattr(
        "mcp_mikrotik.safe_mode.get_safe_mode_manager", lambda *_: FakeSafeMgr(),
        raising=False,
    )

    class FakeTarget:
        title = "RouterA"

    class FakeInventory:
        def resolve(self, _device=None):
            return FakeTarget()

    monkeypatch.setattr(connector, "get_inventory", lambda: FakeInventory())
    monkeypatch.setattr(connector, "_execute_sync",
                        lambda cmd, device=None, redact=None: f'echoed {SECRET}')

    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    log = logging.getLogger("mcp_mikrotik.connector")
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    try:
        result = asyncio.run(
            connector.execute_mikrotik_command(command, ctx, device="RouterA", redact=redact)
        )
    finally:
        log.removeHandler(handler)

    client_msgs = " | ".join(str(c.args[0]) for c in ctx.info.await_args_list)
    return result, stream.getvalue(), client_msgs


def test_secret_reaches_neither_sink(ctx, monkeypatch):
    command = f'/interface wifi set [find name="wifi1"] security.passphrase="{SECRET}"'
    result, server_log, client_log = _run_command(monkeypatch, ctx, command, [SECRET])

    assert SECRET not in server_log, "secret leaked into the server log"
    assert SECRET not in client_log, "secret leaked to the MCP client"
    assert "***" in client_log


def test_a_secret_echoed_in_the_result_is_redacted_in_logs(ctx, monkeypatch):
    """A device that echoes the value back must not put it in the log either."""
    _, server_log, _ = _run_command(
        monkeypatch, ctx, f'set passphrase="{SECRET}"', [SECRET])

    assert SECRET not in server_log


def test_the_command_still_reaches_the_device_unchanged(ctx, monkeypatch):
    """Redaction is for logging only; the device must get the real command."""
    from mcp_mikrotik import connector

    seen = {}

    class FakeSafeMgr:
        is_active = False

    class FakeTarget:
        title = "RouterA"

    class FakeInventory:
        def resolve(self, _device=None):
            return FakeTarget()

    def fake_sync(cmd, device=None, redact=None):
        seen["cmd"] = cmd
        return ""

    monkeypatch.setattr("mcp_mikrotik.safe_mode.get_safe_mode_manager",
                        lambda *_: FakeSafeMgr(), raising=False)
    monkeypatch.setattr(connector, "get_inventory", lambda: FakeInventory())
    monkeypatch.setattr(connector, "_execute_sync", fake_sync)

    command = f'set password="{SECRET}"'
    result = asyncio.run(
        connector.execute_mikrotik_command(command, ctx, device="RouterA", redact=[SECRET])
    )

    assert seen["cmd"] == command, "the device must receive the real command"
    assert result == ""


def test_result_returned_to_the_caller_is_not_redacted(ctx, monkeypatch):
    """Only logging is redacted: the tool decides what to show the user."""
    result, _, _ = _run_command(monkeypatch, ctx, "print", [SECRET])
    assert SECRET in result


# ---------------------------------------------------------------------------
# every tool that carries a credential declares it
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("module,function", [
    ("users", "mikrotik_add_user"),
    ("users", "mikrotik_update_user"),
    ("wireguard", "mikrotik_create_wireguard_interface"),
    ("wireguard", "mikrotik_update_wireguard_interface"),
    ("wireguard", "mikrotik_add_wireguard_peer"),
    ("wireguard", "mikrotik_update_wireguard_peer"),
    ("backup", "mikrotik_restore_backup"),
    ("wireless", "mikrotik_set_wireless_passphrase"),
])
def test_secret_bearing_tools_pass_redact(module, function):
    """A credential tool that forgets redact= puts the secret in the logs."""
    import inspect

    mod = __import__(f"mcp_mikrotik.scope.{module}", fromlist=["*"])
    source = inspect.getsource(getattr(mod, function))
    assert "redact=" in source, f"{function} does not declare its secret to the connector"


# ---------------------------------------------------------------------------
# alongside sensitive-hiding mode
# ---------------------------------------------------------------------------

def _hiding(monkeypatch, enabled):
    from mcp_mikrotik import config
    from mcp_mikrotik.config import MikrotikConfig

    monkeypatch.setattr(config, "mikrotik_config", MikrotikConfig(sensitive_hiding=enabled))


def test_declared_secrets_are_blanked_with_hiding_off(monkeypatch):
    """The fix for #151 must not depend on the opt-in mode."""
    from mcp_mikrotik.connector import _shown

    _hiding(monkeypatch, False)
    assert SECRET not in _shown(f'set passphrase="{SECRET}"', [SECRET])


def test_hiding_mode_still_blanks_undeclared_credentials(monkeypatch):
    from mcp_mikrotik.connector import _shown

    _hiding(monkeypatch, True)
    assert "not-declared" not in _shown('set password="not-declared"', None)


def test_declared_secrets_go_before_the_pattern_pass(monkeypatch):
    """A quote inside the secret would let the pattern pass split it first."""
    from mcp_mikrotik.connector import _shown

    _hiding(monkeypatch, True)
    secret = 'ab"cdTAIL'
    assert "TAIL" not in _shown(f'set password="{secret}"', [secret])
