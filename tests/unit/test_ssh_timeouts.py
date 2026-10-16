"""A device that accepts the login but never answers a command must not block a call for ever.

Before the fix, ``exec_command`` and ``stdout.read()`` had no timeout: the tool call, and the
worker thread running it, waited until the TCP connection died. Enough stuck calls exhaust the
thread pool and every other device stops answering as well.
"""

import socket
import threading
import time

import paramiko
import pytest

from mcp_mikrotik.mikrotik_ssh_client import (
    CONNECT_TIMEOUT,
    DEFAULT_COMMAND_TIMEOUT,
    MikroTikSSHClient,
)


class _Silent(paramiko.ServerInterface):
    """Logs anybody in and accepts a command, then says nothing."""

    def check_auth_password(self, username, password):
        return paramiko.AUTH_SUCCESSFUL

    def get_allowed_auths(self, username):
        return "password"

    def check_channel_request(self, kind, chanid):
        return paramiko.OPEN_SUCCEEDED

    def check_channel_exec_request(self, channel, command):
        return True


@pytest.fixture()
def silent_ssh_server():
    """A real SSH server on localhost whose commands never return."""
    key = paramiko.ECDSAKey.generate()
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(4)
    listener.settimeout(0.2)
    stop = threading.Event()

    def serve(connection):
        transport = paramiko.Transport(connection)
        transport.add_server_key(key)
        try:
            transport.start_server(server=_Silent())
            channel = transport.accept(30)  # keep a reference: a collected channel would be closed
            stop.wait()
            del channel
        except Exception:
            pass
        finally:
            transport.close()

    def accept_loop():
        while not stop.is_set():
            try:
                connection, _ = listener.accept()
            except OSError:
                continue
            threading.Thread(target=serve, args=(connection,), daemon=True).start()
        listener.close()

    threading.Thread(target=accept_loop, daemon=True).start()
    try:
        yield listener.getsockname()[1]
    finally:
        stop.set()


def test_defaults_are_finite_and_sensible():
    assert 0 < CONNECT_TIMEOUT <= 30
    assert 30 <= DEFAULT_COMMAND_TIMEOUT <= 600


def test_command_that_never_answers_times_out(silent_ssh_server):
    client = MikroTikSSHClient("127.0.0.1", "admin", "", None, silent_ssh_server, command_timeout=1.0)
    assert client.connect() is True
    try:
        started = time.monotonic()
        with pytest.raises(TimeoutError) as raised:
            client.execute_command("/ip address print")
        elapsed = time.monotonic() - started
    finally:
        client.disconnect()
    assert 0.5 < elapsed < 10, f"gave up after {elapsed:.1f}s"
    assert "did not answer within 1 seconds" in str(raised.value)


def test_timeout_message_does_not_contain_the_command(silent_ssh_server):
    secret = "/user add name=x password=hunter2-secret"
    client = MikroTikSSHClient("127.0.0.1", "admin", "", None, silent_ssh_server, command_timeout=0.5)
    assert client.connect() is True
    try:
        with pytest.raises(TimeoutError) as raised:
            client.execute_command(secret)
    finally:
        client.disconnect()
    assert "hunter2" not in str(raised.value)


def test_exec_command_is_given_the_configured_timeout(monkeypatch):
    seen = {}

    class _Stream:
        def read(self):
            return b"ok"

    class _SSH:
        def exec_command(self, command, **kwargs):
            seen.update(kwargs)
            return None, _Stream(), _Stream()

    client = MikroTikSSHClient("h", "u", "p", None, command_timeout=42.0)
    client.client = _SSH()
    assert client.execute_command("/system identity print") == "ok"
    assert seen == {"timeout": 42.0}


def test_connect_sets_banner_and_auth_timeouts(monkeypatch):
    seen = {}

    class _SSH:
        def set_missing_host_key_policy(self, policy):
            pass

        def connect(self, **kwargs):
            seen.update(kwargs)

        def close(self):
            pass

    monkeypatch.setattr(paramiko, "SSHClient", _SSH)
    assert MikroTikSSHClient("h", "u", "p", None).connect() is True
    assert seen["timeout"] == seen["banner_timeout"] == seen["auth_timeout"] == CONNECT_TIMEOUT


def test_connect_to_a_silent_listener_fails_instead_of_hanging():
    # accepts TCP but never sends an SSH banner
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    held = []
    threading.Thread(target=lambda: held.append(listener.accept()), daemon=True).start()
    try:
        client = MikroTikSSHClient("127.0.0.1", "admin", "", None, listener.getsockname()[1])
        started = time.monotonic()
        assert client.connect() is False
        assert time.monotonic() - started < CONNECT_TIMEOUT + 5
    finally:
        listener.close()


def test_command_timeout_must_be_positive():
    from pydantic import ValidationError

    from mcp_mikrotik.config import MikrotikConfig

    assert MikrotikConfig(command_timeout=30).command_timeout == 30
    for bad in (0, -5):
        with pytest.raises(ValidationError):
            MikrotikConfig(command_timeout=bad)


def test_inventory_passes_the_configured_timeout_to_the_client(monkeypatch):
    from mcp_mikrotik import config
    from mcp_mikrotik import inventory as inv_module
    from mcp_mikrotik.config import DeviceConfig

    created = {}

    class _Client:
        def __init__(self, **kwargs):
            created.update(kwargs)

        def connect(self):
            return True

    monkeypatch.setattr(inv_module, "MikroTikSSHClient", _Client)
    monkeypatch.setattr(config.mikrotik_config, "command_timeout", 7.5, raising=False)
    inventory = inv_module.Inventory([DeviceConfig(title="A", host="192.0.2.1")])
    inventory.connect("A")
    assert created["command_timeout"] == 7.5
