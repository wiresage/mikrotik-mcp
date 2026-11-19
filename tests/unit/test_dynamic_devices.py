"""Runtime device management: the default-on add/remove tools and their state file.

Devices can be enrolled while the server runs, they survive a restart through
the dynamic inventory file, and the password used to reach one never leaves
that file. Removing is limited to runtime enrollments.
"""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from mcp_mikrotik import config as cfg_mod
from mcp_mikrotik import inventory as inv_mod
from mcp_mikrotik.config import DeviceConfig, MikrotikConfig
from mcp_mikrotik.inventory import reset_inventory
from mcp_mikrotik.safe_mode import (
    forget_safe_mode_manager,
    get_safe_mode_manager,
)
from mcp_mikrotik.scope.devices import inventory as scope_inventory
from tests.conftest import FakeExecutor


REPO_ROOT = Path(__file__).resolve().parents[2]
STATE_FILE = "dynamic-inventory.yaml"


def _config(**overrides):
    """One static device, everything else default."""
    return MikrotikConfig(
        inventory=[DeviceConfig(title="Seed", host="192.0.2.1")],
        **overrides,
    )


@pytest.fixture()
def state_file(monkeypatch, tmp_path):
    path = tmp_path / STATE_FILE
    monkeypatch.setattr(cfg_mod, "mikrotik_config", _config(dynamic_inventory_file=str(path)))
    reset_inventory()
    yield path
    reset_inventory()


def _add(ctx, monkeypatch, reply="name=RouterA", **kwargs):
    """Call add_device with a canned probe reply; returns (result, probe calls)."""
    calls = []

    async def fake(command, _ctx, device=None, **_kw):
        calls.append((command, device))
        return reply

    monkeypatch.setattr(scope_inventory, "execute_mikrotik_command", fake, raising=True)
    result = asyncio.run(scope_inventory.mikrotik_add_device(ctx, **kwargs))
    return result, calls


def _catalogue(**env_extra):
    """Tool names of a fresh server process under the given MIKROTIK_* settings."""
    script = (
        "import asyncio, json\n"
        "from mcp_mikrotik.app import mcp\n"
        "print(json.dumps([t.name for t in asyncio.run(mcp.list_tools())]))\n"
    )
    env = {
        key: value for key, value in os.environ.items()
        if not key.startswith("MIKROTIK_")
    } | {
        "PYTHONPATH": os.pathsep.join(
            filter(None, (str(REPO_ROOT / "src"), os.environ.get("PYTHONPATH")))
        )
    }
    env.update(env_extra)
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        cwd=REPO_ROOT,
        env=env,
        text=True,
    )
    return set(json.loads(completed.stdout))


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def test_dynamic_tools_are_in_the_default_catalogue():
    from mcp_mikrotik.app import mcp

    names = {tool.name for tool in asyncio.run(mcp.list_tools())}
    assert {"add_device", "remove_device", "list_devices"} <= names


def test_dynamic_tools_can_be_turned_off():
    names = _catalogue(MIKROTIK_ALLOW_DYNAMIC_DEVICES="false")
    assert "add_device" not in names and "remove_device" not in names
    assert "list_devices" in names and "list_mikrotik_neighbors" in names


def test_read_only_hides_dynamic_tools_but_keeps_the_read_tools():
    names = _catalogue(MIKROTIK_READ_ONLY="true")
    assert "add_device" not in names and "remove_device" not in names
    assert "list_devices" in names and "list_mikrotik_neighbors" in names


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def test_enrolled_device_is_persisted_and_survives_a_restart(state_file, ctx, monkeypatch):
    result, calls = _add(
        ctx, monkeypatch, title="BranchA", host="192.0.2.10", region="NL",
        tags=["branch"],
    )

    assert "BranchA" in result and "192.0.2.10" in result
    entries = yaml.safe_load(state_file.read_text(encoding="utf-8"))
    assert [(e["title"], e["host"]) for e in entries] == [("BranchA", "192.0.2.10")]
    assert entries[0]["region"] == "NL" and entries[0]["tags"] == ["branch"]

    # The probe resolved the new title and ran a command against it.
    assert calls == [("/system identity print", "BranchA")]

    reset_inventory()
    assert inv_mod.get_inventory().resolve("BranchA").host == "192.0.2.10"
    assert inv_mod.get_inventory().resolve("Seed").host == "192.0.2.1"


def test_new_state_file_gets_a_credentials_header_and_private_mode(state_file, ctx, monkeypatch):
    _add(ctx, monkeypatch, title="BranchA", host="192.0.2.10")

    text = state_file.read_text(encoding="utf-8")
    assert text.startswith("# holds credentials")
    assert oct(state_file.stat().st_mode & 0o777) == "0o600"


def test_state_file_is_private_from_the_moment_it_exists(state_file, ctx, monkeypatch):
    """No credential may be written while the file is readable by others.

    `open` honours the umask (0644 for a typical 022), so a write through it
    would leave every credential readable for the length of the write. The
    write handle must be owner-only the moment it exists.
    """
    modes = []
    real_fdopen = os.fdopen

    def spy(fd, *args, **kwargs):
        modes.append(oct(os.fstat(fd).st_mode & 0o777))
        return real_fdopen(fd, *args, **kwargs)

    monkeypatch.setattr(scope_inventory.os, "fdopen", spy)
    _add(ctx, monkeypatch, title="BranchA", host="192.0.2.10", password="S3cr3t")

    assert modes == ["0o600"]
    assert oct(state_file.stat().st_mode & 0o777) == "0o600"


def test_the_credentials_header_survives_a_second_enrollment(state_file, ctx, monkeypatch):
    _add(ctx, monkeypatch, title="BranchA", host="192.0.2.10")
    _add(ctx, monkeypatch, title="BranchB", host="192.0.2.11")

    text = state_file.read_text(encoding="utf-8")
    assert text.startswith("# holds credentials")
    assert [e["title"] for e in yaml.safe_load(text)] == ["BranchA", "BranchB"]


def test_a_corrupt_state_file_is_reported_not_crashed_on(state_file, ctx, monkeypatch):
    """A half-written file must fail as a ValueError naming the file.

    PyYAML's error has no `strerror`, so reading it through the OSError branch
    raised `AttributeError: 'ParserError' object has no attribute 'strerror'`
    with no path and no hint.
    """
    inv_mod.get_inventory()  # load while the state file is still absent
    state_file.write_text("title: [unclosed\n", encoding="utf-8")

    with pytest.raises(ValueError, match="not valid YAML"):
        _add(ctx, monkeypatch, title="BranchA", host="192.0.2.10")

    assert [d.title for d in inv_mod.get_inventory().all_devices()] == ["Seed"]


def test_the_password_stays_in_the_state_file_only(state_file, ctx, monkeypatch):
    secret = "S3cr3t-Enrollment-Pw"
    result, calls = _add(
        ctx, monkeypatch, title="SecA", host="192.0.2.11", password=secret,
    )

    notifications = " ".join(
        str(call.args) for call in ctx.info.await_args_list
    ) + " ".join(str(call.args) for call in ctx.error.await_args_list)
    assert secret not in result
    assert secret not in notifications
    assert secret not in str(calls)
    assert secret in state_file.read_text(encoding="utf-8")
    assert secret not in json.dumps(inv_mod.get_inventory().describe())


def test_the_default_state_file_is_created_owner_only(tmp_path, ctx, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("MIKROTIK_DYNAMIC_INVENTORY_FILE", raising=False)
    monkeypatch.setattr(
        cfg_mod, "mikrotik_config",
        MikrotikConfig(inventory=[DeviceConfig(title="Seed", host="192.0.2.1")]),
    )
    reset_inventory()

    _add(ctx, monkeypatch, title="BranchA", host="192.0.2.10")

    state = tmp_path / "mikrotik-mcp" / "dynamic-inventory.yaml"
    assert yaml.safe_load(state.read_text(encoding="utf-8"))[0]["title"] == "BranchA"
    assert oct(state.stat().st_mode & 0o777) == "0o600"
    assert oct(state.parent.stat().st_mode & 0o777) == "0o700"


# ---------------------------------------------------------------------------
# Removing a runtime enrollment
# ---------------------------------------------------------------------------

def test_remove_drops_the_device_from_memory_and_the_state_file(state_file, ctx, monkeypatch):
    _add(ctx, monkeypatch, title="BranchA", host="192.0.2.10")

    result = asyncio.run(scope_inventory.mikrotik_remove_device(ctx, "BranchA"))

    assert "BranchA" in result
    assert yaml.safe_load(state_file.read_text(encoding="utf-8")) == []
    assert [d.title for d in inv_mod.get_inventory().all_devices()] == ["Seed"]


def test_remove_refuses_a_static_device_and_leaves_the_file(state_file, ctx, monkeypatch):
    _add(ctx, monkeypatch, title="BranchA", host="192.0.2.10")

    with pytest.raises(ValueError, match="not enrolled at runtime"):
        asyncio.run(scope_inventory.mikrotik_remove_device(ctx, "Seed"))

    assert [e["title"] for e in yaml.safe_load(state_file.read_text(encoding="utf-8"))] == ["BranchA"]


def test_remove_refuses_an_unknown_title_and_lists_the_known_ones(state_file, ctx, monkeypatch):
    with pytest.raises(LookupError, match="Seed"):
        asyncio.run(scope_inventory.mikrotik_remove_device(ctx, "Ghost"))


def test_removing_the_only_device_leaves_guidance(ctx, monkeypatch, tmp_path):
    monkeypatch.setattr(
        cfg_mod, "mikrotik_config",
        MikrotikConfig(inventory=[], dynamic_inventory_file=str(tmp_path / STATE_FILE)),
    )
    reset_inventory()
    _add(ctx, monkeypatch, title="Only", host="192.0.2.20")

    asyncio.run(scope_inventory.mikrotik_remove_device(ctx, "Only"))
    result = asyncio.run(scope_inventory.mikrotik_list_devices(ctx))
    assert "add_device" in result


def test_removing_a_device_forgets_its_safe_mode_manager(state_file, ctx, monkeypatch):
    """Re-adding a title must never reuse the old router's live shell."""
    _add(ctx, monkeypatch, title="BranchA", host="192.0.2.10")
    before = get_safe_mode_manager("BranchA")

    asyncio.run(scope_inventory.mikrotik_remove_device(ctx, "BranchA"))
    _add(ctx, monkeypatch, title="BranchA", host="192.0.2.99")

    assert get_safe_mode_manager("BranchA") is not before


def test_removing_a_device_with_active_safe_mode_is_refused(state_file, ctx, monkeypatch):
    _add(ctx, monkeypatch, title="BranchA", host="192.0.2.10")
    manager = get_safe_mode_manager("BranchA")
    manager._active = True
    try:
        with pytest.raises(ValueError, match="Safe mode is active"):
            asyncio.run(scope_inventory.mikrotik_remove_device(ctx, "BranchA"))

        entries = yaml.safe_load(state_file.read_text(encoding="utf-8"))
        assert [e["title"] for e in entries] == ["BranchA"]
        assert "BranchA" in inv_mod.get_inventory().titles
    finally:
        manager._active = False
        forget_safe_mode_manager("BranchA")


# ---------------------------------------------------------------------------
# Listing and guidance
# ---------------------------------------------------------------------------

def test_the_empty_inventory_points_at_add_device(ctx, monkeypatch):
    monkeypatch.setattr(
        cfg_mod, "mikrotik_config",
        MikrotikConfig(inventory=[], dynamic_inventory_file=""),
    )
    reset_inventory()

    result = asyncio.run(scope_inventory.mikrotik_list_devices(ctx))
    assert "add_device" in result


def test_read_only_empty_inventory_does_not_advertise_add_device(ctx, monkeypatch):
    monkeypatch.setattr(
        cfg_mod, "mikrotik_config",
        MikrotikConfig(inventory=[], read_only=True, dynamic_inventory_file=""),
    )
    reset_inventory()

    result = asyncio.run(scope_inventory.mikrotik_list_devices(ctx))
    assert "add_device" not in result


# ---------------------------------------------------------------------------
# Rejected enrollments change nothing
# ---------------------------------------------------------------------------

def test_duplicate_title_against_the_static_inventory_is_rejected(state_file, ctx, monkeypatch):
    with pytest.raises(ValueError, match="Duplicate device title 'seed'"):
        _add(ctx, monkeypatch, title="seed", host="192.0.2.12")

    assert not state_file.exists()
    assert [d.title for d in inv_mod.get_inventory().all_devices()] == ["Seed"]


def test_duplicate_title_against_an_enrolled_device_is_rejected(state_file, ctx, monkeypatch):
    _add(ctx, monkeypatch, title="BranchA", host="192.0.2.10")

    with pytest.raises(ValueError, match="Duplicate device title 'BranchA'"):
        _add(ctx, monkeypatch, title="BranchA", host="192.0.2.99")

    entries = yaml.safe_load(state_file.read_text(encoding="utf-8"))
    assert [e["host"] for e in entries] == ["192.0.2.10"]


def test_a_state_file_that_duplicates_a_static_title_stops_startup(state_file):
    state_file.write_text("- title: Seed\n  host: 192.0.2.99\n", encoding="utf-8")
    reset_inventory()

    with pytest.raises(ValueError, match="Duplicate device title 'Seed'") as exc:
        inv_mod.get_inventory()

    assert str(state_file) in str(exc.value)

    reset_inventory()


def test_blank_title_is_rejected(state_file, ctx, monkeypatch):
    with pytest.raises(ValueError, match="title"):
        _add(ctx, monkeypatch, title="   ", host="192.0.2.13")

    assert not state_file.exists()


@pytest.mark.parametrize(
    "host",
    ["not a host", "192.0.2.", "-leading-hyphen.example", "router/1", ""],
)
def test_invalid_host_is_rejected(state_file, ctx, monkeypatch, host):
    with pytest.raises(ValueError, match="Invalid host"):
        _add(ctx, monkeypatch, title="BranchA", host=host)

    assert not state_file.exists()
    assert [d.title for d in inv_mod.get_inventory().all_devices()] == ["Seed"]


def test_blank_state_file_setting_is_refused(monkeypatch, ctx):
    monkeypatch.setattr(
        cfg_mod, "mikrotik_config", _config(dynamic_inventory_file=""),
    )
    reset_inventory()

    with pytest.raises(ValueError, match="state file"):
        asyncio.run(
            scope_inventory.mikrotik_add_device(ctx, title="BranchA", host="192.0.2.10")
        )

    assert [d.title for d in inv_mod.get_inventory().all_devices()] == ["Seed"]


def test_unwritable_state_file_path_is_named_in_the_error(monkeypatch, ctx, tmp_path):
    # A read-only Docker mount behaves the same way: the file cannot be written.
    blocker = tmp_path / "blocked"
    blocker.write_text("x", encoding="utf-8")
    path = blocker / "nested" / STATE_FILE
    monkeypatch.setattr(
        cfg_mod, "mikrotik_config", _config(dynamic_inventory_file=str(path)),
    )
    reset_inventory()

    with pytest.raises(ValueError) as exc:
        asyncio.run(
            scope_inventory.mikrotik_add_device(ctx, title="BranchA", host="192.0.2.10")
        )

    assert str(path) in str(exc.value)
    assert "write" in str(exc.value).lower()
    assert [d.title for d in inv_mod.get_inventory().all_devices()] == ["Seed"]


# ---------------------------------------------------------------------------
# A device that cannot be reached is still enrolled
# ---------------------------------------------------------------------------

def test_probe_failure_still_enrolls_the_device(state_file, ctx, monkeypatch):
    async def unreachable(command, _ctx, device=None, **_kw):
        return "Error: Failed to connect to MikroTik device 'BranchB' (192.0.2.13:22)"

    monkeypatch.setattr(
        scope_inventory, "execute_mikrotik_command", unreachable, raising=True,
    )
    result = asyncio.run(
        scope_inventory.mikrotik_add_device(ctx, title="BranchB", host="192.0.2.13")
    )

    assert "unreachable" in result
    assert "BranchB" in result
    entries = yaml.safe_load(state_file.read_text(encoding="utf-8"))
    assert [e["title"] for e in entries] == ["BranchB"]

    reset_inventory()
    assert inv_mod.get_inventory().resolve("BranchB").host == "192.0.2.13"


def test_fake_executor_is_used_for_the_probe(state_file, ctx, monkeypatch):
    """The plan's seam: enrollment runs its probe through the shared executor."""
    fake = FakeExecutor()
    monkeypatch.setattr(scope_inventory, "execute_mikrotik_command", fake, raising=True)

    asyncio.run(scope_inventory.mikrotik_add_device(ctx, title="BranchC", host="192.0.2.14"))

    assert fake.commands == ["/system identity print"]
    assert fake.devices == ["BranchC"]
