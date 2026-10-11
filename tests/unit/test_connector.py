"""Connector tests for the inventory-backed (multi-device) execution path."""

import asyncio
from contextlib import contextmanager

import pytest

from mcp_mikrotik.config import DeviceConfig
from mcp_mikrotik.inventory import DeviceNotFoundError, Inventory


class DummyClient:
    """Stand-in for MikroTikSSHClient."""

    def __init__(self, output="identity", raises=None):
        self.output = output
        self.raises = raises
        self.commands = []
        self.uploaded = None
        self.downloaded = None

    def execute_command(self, command: str) -> str:
        self.commands.append(command)
        if self.raises:
            raise self.raises
        return self.output

    def download_file(self, filename: str) -> bytes:
        self.downloaded = filename
        return b"\x00binary"

    def upload_file(self, filename: str, data: bytes) -> None:
        self.uploaded = (filename, data)


class FakeInventory:
    """Minimal inventory double: resolves titles and hands out connections.

    Each device keeps one ``DummyClient`` so assertions can see the commands
    that reached it, while ``opened``/``closed`` record the connection
    lifecycle the connector drives.
    """

    def __init__(self, clients: dict):
        self._clients = clients
        self.opened: list = []
        self.closed: list = []
        self._devices = {
            t.casefold(): DeviceConfig(title=t, host=f"10.0.0.{i + 1}")
            for i, t in enumerate(clients)
        }

    def resolve(self, title=None):
        if title is None:
            if len(self._devices) == 1:
                return next(iter(self._devices.values()))
            raise DeviceNotFoundError("multiple devices; specify one")
        dev = self._devices.get(str(title).casefold())
        if dev is None:
            raise DeviceNotFoundError(f"Unknown device {title!r}.")
        return dev

    def connect(self, title=None):
        client = self._clients[self.resolve(title).title]
        self.opened.append(client)
        return client

    @contextmanager
    def session(self, title=None):
        client = self.connect(title)
        try:
            yield client
        finally:
            self.closed.append(client)


def _patch_inventory(monkeypatch, inv):
    from mcp_mikrotik import connector
    from mcp_mikrotik import inventory as inv_mod

    monkeypatch.setattr(connector, "get_inventory", lambda: inv)
    # The safe-mode manager resolves through the module-level inventory when
    # the connector checks for an active session — keep both views consistent.
    monkeypatch.setattr(inv_mod, "get_inventory", lambda: inv)
    return connector


# ---------------------------------------------------------------------------
# _execute_sync
# ---------------------------------------------------------------------------

def test_execute_sync_uses_single_device_when_unspecified(monkeypatch):
    client = DummyClient()
    connector = _patch_inventory(monkeypatch, FakeInventory({"OnlyOne": client}))

    assert connector._execute_sync("/system identity print") == "identity"
    assert client.commands == ["/system identity print"]


def test_execute_sync_routes_to_named_device(monkeypatch):
    a, b = DummyClient("from-A"), DummyClient("from-B")
    connector = _patch_inventory(monkeypatch, FakeInventory({"RouterA": a, "RouterB": b}))

    assert connector._execute_sync("/x", device="RouterB") == "from-B"
    assert b.commands == ["/x"] and a.commands == []


def test_execute_sync_unknown_device_raises(monkeypatch):
    connector = _patch_inventory(monkeypatch, FakeInventory({"RouterA": DummyClient()}))
    with pytest.raises(DeviceNotFoundError):
        connector._execute_sync("/x", device="Nope")


# ---------------------------------------------------------------------------
# Connection lifecycle — one connection per command, never shared
# ---------------------------------------------------------------------------

def test_each_execution_opens_and_closes_its_own_connection(monkeypatch):
    """Two commands must not ride on one shared client."""
    inv = FakeInventory({"OnlyOne": DummyClient()})
    connector = _patch_inventory(monkeypatch, inv)

    connector._execute_sync("/one")
    connector._execute_sync("/two")

    assert len(inv.opened) == 2
    assert len(inv.closed) == 2


def test_connection_is_closed_when_the_command_fails(monkeypatch):
    """A failing command must not leak an SSH session on the router."""
    boom = DummyClient(raises=RuntimeError("boom"))
    inv = FakeInventory({"OnlyOne": boom})
    connector = _patch_inventory(monkeypatch, inv)

    with pytest.raises(RuntimeError, match="boom"):
        connector._execute_sync("/bad")

    assert inv.closed == [boom]


def test_file_transfers_close_their_connection(monkeypatch):
    inv = FakeInventory({"OnlyOne": DummyClient()})
    connector = _patch_inventory(monkeypatch, inv)

    connector.download_file_sync("backup_1.backup")
    connector.upload_file_sync("restore.rsc", b"bytes")

    assert len(inv.opened) == 2
    assert len(inv.closed) == 2


# ---------------------------------------------------------------------------
# file transfer
# ---------------------------------------------------------------------------

def test_download_file_sync_targets_device(monkeypatch):
    a, b = DummyClient(), DummyClient()
    connector = _patch_inventory(monkeypatch, FakeInventory({"RouterA": a, "RouterB": b}))

    assert connector.download_file_sync("backup_1.backup", device="RouterB") == b"\x00binary"
    assert b.downloaded == "backup_1.backup"
    assert a.downloaded is None


def test_upload_file_sync_targets_device(monkeypatch):
    a, b = DummyClient(), DummyClient()
    connector = _patch_inventory(monkeypatch, FakeInventory({"RouterA": a, "RouterB": b}))

    connector.upload_file_sync("restore.rsc", b"config-bytes", device="RouterA")
    assert a.uploaded == ("restore.rsc", b"config-bytes")
    assert b.uploaded is None


# ---------------------------------------------------------------------------
# execute_mikrotik_command
# ---------------------------------------------------------------------------

def test_execute_mikrotik_command_logs_error(ctx, monkeypatch):
    connector = _patch_inventory(monkeypatch, FakeInventory({"OnlyOne": DummyClient()}))

    async def fake_to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)
    monkeypatch.setattr(
        connector, "_execute_sync",
        lambda cmd, device=None, redact=None: "Error: nope",
    )

    result = asyncio.run(connector.execute_mikrotik_command("/bad", ctx))
    assert result == "Error: nope"
    assert ctx.error.await_count == 1


def test_execute_mikrotik_command_unknown_device_is_reported(ctx, monkeypatch):
    """A bad device must fail loudly and never execute somewhere else."""
    client = DummyClient()
    connector = _patch_inventory(monkeypatch, FakeInventory({"RouterA": client}))

    result = asyncio.run(connector.execute_mikrotik_command("/x", ctx, device="Ghost"))
    assert "Unknown device" in result
    assert client.commands == []          # nothing ran anywhere
    assert ctx.error.await_count == 1


def test_execute_mikrotik_command_passes_resolved_device(ctx, monkeypatch):
    a, b = DummyClient("A-out"), DummyClient("B-out")
    connector = _patch_inventory(monkeypatch, FakeInventory({"RouterA": a, "RouterB": b}))

    async def fake_to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)

    result = asyncio.run(connector.execute_mikrotik_command("/y", ctx, device="RouterB"))
    assert result == "B-out"
    assert b.commands == ["/y"] and a.commands == []


def test_sensitive_hiding_redacts_notifications_and_logs_but_not_execution(ctx, monkeypatch, caplog):
    from mcp_mikrotik import config
    from mcp_mikrotik.config import MikrotikConfig

    secret = "hunter2"
    client = DummyClient(f'failure: password="{secret}"')
    connector = _patch_inventory(monkeypatch, FakeInventory({"OnlyOne": client}))
    monkeypatch.setattr(config, "mikrotik_config", MikrotikConfig(sensitive_hiding=True))

    async def fake_to_thread(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", fake_to_thread)
    command = f'/user add name="test" password="{secret}"'
    with caplog.at_level("INFO"):
        result = asyncio.run(connector.execute_mikrotik_command(command, ctx))

    assert client.commands == [command]
    assert result == f'failure: password="{secret}"'
    assert secret not in ctx.info.await_args.args[0]
    assert secret not in caplog.text
