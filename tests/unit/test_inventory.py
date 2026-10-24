"""Tests for the multi-device Inventory (issue #44)."""

import copy
import json

import pytest

from mcp_mikrotik.config import DeviceConfig, MikrotikConfig
from mcp_mikrotik.inventory import DeviceNotFoundError, Inventory


def _dev(title, host="10.0.0.1", **kw):
    return DeviceConfig(title=title, host=host, **kw)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def test_titles_and_len():
    inv = Inventory([_dev("RouterA"), _dev("RouterB", "10.0.0.2")])
    assert len(inv) == 2
    assert inv.titles == ["RouterA", "RouterB"]


def test_duplicate_titles_rejected():
    with pytest.raises(ValueError, match="Duplicate device title"):
        Inventory([_dev("Same"), _dev("Same", "10.0.0.2")])


def test_duplicate_titles_are_case_insensitive():
    with pytest.raises(ValueError, match="Duplicate device title"):
        Inventory([_dev("RouterA"), _dev("routera", "10.0.0.2")])


def test_blank_title_rejected():
    with pytest.raises(ValueError):
        DeviceConfig(title="   ", host="10.0.0.1")


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def test_single_device_resolves_without_a_title():
    inv = Inventory([_dev("OnlyOne")])
    assert inv.resolve().title == "OnlyOne"
    assert inv.resolve(None).title == "OnlyOne"
    assert inv.resolve("").title == "OnlyOne"


def test_multiple_devices_require_a_title():
    inv = Inventory([_dev("RouterA"), _dev("RouterB", "10.0.0.2")])
    with pytest.raises(DeviceNotFoundError) as exc:
        inv.resolve()
    # The error must list the choices so the caller can self-correct.
    assert "RouterA" in str(exc.value) and "RouterB" in str(exc.value)


def test_resolve_is_case_insensitive_and_trims():
    inv = Inventory([_dev("RouterA"), _dev("RouterB", "10.0.0.2")])
    assert inv.resolve("routera").title == "RouterA"
    assert inv.resolve("  RouterB  ").title == "RouterB"


def test_unknown_title_lists_available_devices():
    inv = Inventory([_dev("RouterA"), _dev("RouterB", "10.0.0.2")])
    with pytest.raises(DeviceNotFoundError) as exc:
        inv.resolve("Ghost")
    msg = str(exc.value)
    assert "Ghost" in msg and "RouterA" in msg and "RouterB" in msg


def test_empty_inventory_resolution_error():
    with pytest.raises(DeviceNotFoundError, match="No MikroTik devices"):
        Inventory([]).resolve()


# ---------------------------------------------------------------------------
# describe() — what the LLM sees
# ---------------------------------------------------------------------------

def test_describe_never_exposes_credentials():
    inv = Inventory([
        _dev("RouterA", username="admin", password="super-secret",
             key_filename="/keys/id_ed25519", tags=["eu"], region="NL")
    ])
    described = inv.describe()
    blob = json.dumps(described)
    assert "super-secret" not in blob
    assert "id_ed25519" not in blob
    assert "password" not in blob and "key_filename" not in blob
    assert described[0]["title"] == "RouterA"
    assert described[0]["tags"] == ["eu"] and described[0]["region"] == "NL"


# ---------------------------------------------------------------------------
# Connections — never pooled, always closed
# ---------------------------------------------------------------------------

def _recording_ssh(monkeypatch):
    """Patch MikroTikSSHClient with a recorder. Returns (built, closed)."""
    import mcp_mikrotik.inventory as inv_mod

    built, closed = [], []

    class FakeSSH:
        def __init__(self, **kw):
            self.host = kw["host"]
            self.client = object()
            built.append(self)

        def connect(self):
            return True

        def disconnect(self):
            closed.append(self)

    monkeypatch.setattr(inv_mod, "MikroTikSSHClient", FakeSSH)
    return built, closed


def test_each_call_opens_a_fresh_connection(monkeypatch):
    """Clients are never pooled, so concurrent sessions cannot share one."""
    built, _ = _recording_ssh(monkeypatch)
    inv = Inventory([_dev("RouterA", "10.0.0.1"), _dev("RouterB", "10.0.0.2")])

    a1 = inv.connect("RouterA")
    a2 = inv.connect("RouterA")
    b1 = inv.connect("RouterB")

    # Two calls for the SAME device must still be two distinct connections.
    assert a1 is not a2
    assert b1 is not a1 and b1 is not a2
    assert [c.host for c in built] == ["10.0.0.1", "10.0.0.1", "10.0.0.2"]


def test_inventory_holds_no_connection_state(monkeypatch):
    """Opening connections must not mutate the inventory.

    Anything the inventory retained between calls would be state shared by
    every session in the process — exactly what this design removes.
    """
    _recording_ssh(monkeypatch)
    inv = Inventory([_dev("RouterA", "10.0.0.1")])

    before = copy.deepcopy(vars(inv))
    inv.connect("RouterA")
    inv.connect("RouterA")
    with inv.session("RouterA"):
        pass

    assert vars(inv) == before


def test_session_closes_the_connection(monkeypatch):
    built, closed = _recording_ssh(monkeypatch)
    inv = Inventory([_dev("RouterA", "10.0.0.1")])

    with inv.session("RouterA") as client:
        assert closed == []          # still open while the command runs

    assert closed == [client]
    assert built == [client]


def test_session_closes_the_connection_on_error(monkeypatch):
    """A failing command must not leak an SSH session on the router."""
    built, closed = _recording_ssh(monkeypatch)
    inv = Inventory([_dev("RouterA", "10.0.0.1")])

    with pytest.raises(RuntimeError, match="command blew up"):
        with inv.session("RouterA"):
            raise RuntimeError("command blew up")

    assert closed == built and len(closed) == 1


def test_connect_raises_on_connect_failure(monkeypatch):
    import mcp_mikrotik.inventory as inv_mod

    class FailingSSH:
        def __init__(self, **kw):
            self.client = None

        def connect(self):
            return False

        def disconnect(self):
            pass

    monkeypatch.setattr(inv_mod, "MikroTikSSHClient", FailingSSH)
    inv = Inventory([_dev("RouterA", "10.0.0.1")])
    with pytest.raises(ConnectionError, match="RouterA"):
        inv.connect("RouterA")


def test_session_propagates_connect_failure(monkeypatch):
    """An unreachable device fails at the `with`, never yielding a client."""
    import mcp_mikrotik.inventory as inv_mod

    class FailingSSH:
        def __init__(self, **kw):
            self.client = None

        def connect(self):
            return False

        def disconnect(self):
            raise AssertionError("nothing was opened, so nothing may be closed")

    monkeypatch.setattr(inv_mod, "MikroTikSSHClient", FailingSSH)
    inv = Inventory([_dev("RouterA", "10.0.0.1")])
    with pytest.raises(ConnectionError, match="RouterA"):
        with inv.session("RouterA"):
            raise AssertionError("body must not run")


# ---------------------------------------------------------------------------
# Loading from configuration
# ---------------------------------------------------------------------------

def test_inventory_parses_json_from_env(monkeypatch):
    """JSON is a YAML subset, so the old inline JSON form keeps working."""
    payload = json.dumps([
        {"title": "TitleA", "host": "127.0.0.1", "port": 2222,
         "username": "admin", "password": "pw", "tags": ["t1"], "region": "NL"},
        {"title": "TitleB", "host": "192.168.88.1"},
    ])
    monkeypatch.setenv("MIKROTIK_INVENTORY", payload)
    cfg = MikrotikConfig()
    assert [d.title for d in cfg.inventory] == ["TitleA", "TitleB"]
    assert cfg.inventory[0].port == 2222
    assert cfg.inventory[0].tags == ["t1"]
    assert cfg.inventory[1].port == 22          # default


def test_inventory_parses_yaml_flow_from_env(monkeypatch):
    """YAML flow syntax needs no escaped quotes inside an MCP JSON config."""
    monkeypatch.setenv(
        "MIKROTIK_INVENTORY",
        "[{title: TitleA, host: 127.0.0.1, port: 2222, region: NL, tags: [t1]},"
        " {title: TitleB, host: 192.168.88.1}]",
    )
    cfg = MikrotikConfig()
    assert [d.title for d in cfg.inventory] == ["TitleA", "TitleB"]
    assert cfg.inventory[0].port == 2222
    assert cfg.inventory[0].tags == ["t1"]
    assert cfg.inventory[0].region == "NL"


def test_inventory_env_accepts_tab_whitespace_json(monkeypatch):
    """PyYAML rejects tabs that JSON allows — the JSON-first parse must win.

    A tab-indented inventory.json worked before the YAML migration; it must
    keep working after it.
    """
    monkeypatch.setenv(
        "MIKROTIK_INVENTORY",
        '[\n\t{"title": "TitleA", "host": "10.0.0.1"},\n\t{"title":\t"TitleB", "host": "10.0.0.2"}\n]',
    )
    cfg = MikrotikConfig()
    assert [d.title for d in cfg.inventory] == ["TitleA", "TitleB"]


def test_inventory_file_accepts_tab_whitespace_json(monkeypatch, tmp_path):
    import mcp_mikrotik.inventory as inv_mod
    from mcp_mikrotik import config as cfg_mod

    path = tmp_path / "inventory.json"
    path.write_text(
        '[\n\t{"title": "TitleA", "host": "10.0.0.1"}\n]', encoding="utf-8"
    )
    monkeypatch.delenv("MIKROTIK_INVENTORY", raising=False)
    monkeypatch.setattr(
        cfg_mod, "mikrotik_config", MikrotikConfig(inventory_file=str(path))
    )

    devices = inv_mod._load_devices()
    assert [d.title for d in devices] == ["TitleA"]


def test_invalid_inventory_yaml_is_rejected_without_echoing_it(monkeypatch):
    """The value holds credentials, so the error must not quote it back."""
    monkeypatch.setenv("MIKROTIK_INVENTORY", "[{title: A, password: hunter2, ]")
    with pytest.raises(Exception) as exc:
        MikrotikConfig()
    assert "hunter2" not in str(exc.value)


def test_invalid_inventory_entry_error_hides_credentials(monkeypatch):
    """A schema-invalid entry (e.g. 'hostname' typo) must not echo values."""
    monkeypatch.setenv(
        "MIKROTIK_INVENTORY",
        '[{"title": "core-nl", "hostname": "10.0.0.1", "password": "FleetSecret9!"}]',
    )
    with pytest.raises(Exception) as exc:
        MikrotikConfig()
    msg = str(exc.value)
    assert "FleetSecret9!" not in msg
    assert "host" in msg                        # the offending field is named


def test_inventory_file_accepts_yaml(monkeypatch, tmp_path):
    import mcp_mikrotik.inventory as inv_mod
    from mcp_mikrotik import config as cfg_mod

    path = tmp_path / "inventory.yaml"
    path.write_text(
        "- title: TitleA\n"
        "  host: 127.0.0.1\n"
        "  port: 2222\n"
        "  tags: [lab, primary]\n"
        "  region: NL\n"
        "- title: TitleB\n"
        "  host: 192.168.88.1\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("MIKROTIK_INVENTORY", raising=False)
    monkeypatch.setattr(
        cfg_mod, "mikrotik_config", MikrotikConfig(inventory_file=str(path))
    )

    devices = inv_mod._load_devices()
    assert [d.title for d in devices] == ["TitleA", "TitleB"]
    assert devices[0].port == 2222
    assert devices[0].tags == ["lab", "primary"]
    assert devices[1].port == 22


def test_inline_inventory_wins_over_file(monkeypatch, tmp_path):
    import mcp_mikrotik.inventory as inv_mod
    from mcp_mikrotik import config as cfg_mod

    path = tmp_path / "inventory.yaml"
    path.write_text("- title: FromFile\n  host: 10.0.0.9\n", encoding="utf-8")
    monkeypatch.setenv("MIKROTIK_INVENTORY", "[{title: Inline, host: 10.0.0.1}]")
    monkeypatch.setattr(
        cfg_mod, "mikrotik_config", MikrotikConfig(inventory_file=str(path))
    )

    devices = inv_mod._load_devices()
    assert [d.title for d in devices] == ["Inline"]


def test_inventory_file_error_names_entry_without_credentials(monkeypatch, tmp_path):
    import mcp_mikrotik.inventory as inv_mod
    from mcp_mikrotik import config as cfg_mod

    path = tmp_path / "inventory.yaml"
    path.write_text(
        "- title: core-nl\n"
        "  hostname: 10.0.0.1\n"          # typo: should be 'host'
        "  password: FleetSecret9!\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("MIKROTIK_INVENTORY", raising=False)
    monkeypatch.setattr(
        cfg_mod, "mikrotik_config", MikrotikConfig(inventory_file=str(path))
    )

    with pytest.raises(ValueError) as exc:
        inv_mod._load_devices()
    msg = str(exc.value)
    assert "FleetSecret9!" not in msg
    assert "core-nl" in msg and "host" in msg


def test_shipped_example_inventory_is_valid(monkeypatch):
    """inventory.example.yml at the repo root must always match the schema."""
    import pathlib

    import mcp_mikrotik.inventory as inv_mod
    from mcp_mikrotik import config as cfg_mod

    example = pathlib.Path(__file__).resolve().parents[2] / "inventory.example.yml"
    assert example.is_file(), "inventory.example.yml is missing from the repo root"

    monkeypatch.delenv("MIKROTIK_INVENTORY", raising=False)
    monkeypatch.setattr(
        cfg_mod, "mikrotik_config", MikrotikConfig(inventory_file=str(example))
    )

    devices = inv_mod._load_devices()
    assert [d.title for d in devices] == ["TitleA", "TitleB"]
    assert devices[0].password == "change-me"
    assert devices[1].key_filename == "/config/keys/id_ed25519"
    # and the example is usable as-is: unique titles, resolvable
    inv = Inventory(devices)
    assert inv.resolve("titlea").title == "TitleA"


def test_inventory_file_rejects_non_list_shapes(monkeypatch, tmp_path):
    import mcp_mikrotik.inventory as inv_mod
    from mcp_mikrotik import config as cfg_mod

    path = tmp_path / "inventory.yaml"
    path.write_text("inventory:\n  title: NotAList\n  host: 10.0.0.1\n",
                    encoding="utf-8")
    monkeypatch.delenv("MIKROTIK_INVENTORY", raising=False)
    monkeypatch.setattr(
        cfg_mod, "mikrotik_config", MikrotikConfig(inventory_file=str(path))
    )

    with pytest.raises(ValueError, match="must be a list"):
        inv_mod._load_devices()


def test_falls_back_to_single_device_config(monkeypatch):
    """No inventory configured -> synthesise one device from the flat settings."""
    import mcp_mikrotik.inventory as inv_mod
    from mcp_mikrotik import config as cfg_mod

    monkeypatch.delenv("MIKROTIK_INVENTORY", raising=False)
    monkeypatch.setattr(
        cfg_mod, "mikrotik_config",
        MikrotikConfig(host="192.168.88.1", username="u", password="p", port=2022),
    )

    devices = inv_mod._load_devices()
    assert len(devices) == 1
    assert devices[0].host == "192.168.88.1"
    assert devices[0].port == 2022
    assert devices[0].username == "u"


def test_connect_appends_terminal_width_login_option(monkeypatch):
    """RouterOS reads `<user>+<n>w` as "console width n"; only requested connections get it."""
    from mcp_mikrotik import inventory as inv_mod
    from mcp_mikrotik.config import DeviceConfig

    seen = []

    class FakeClient:
        def __init__(self, **kwargs):
            seen.append(kwargs["username"])

        def connect(self):
            return True

    monkeypatch.setattr(inv_mod, "MikroTikSSHClient", FakeClient)
    inv = inv_mod.Inventory([DeviceConfig(title="R", host="192.0.2.1", username="mcp")])
    inv.connect("R")
    inv.connect("R", terminal_width=250)
    assert seen == ["mcp", "mcp+250w"]


def test_connect_rejects_absurd_terminal_width(monkeypatch):
    import pytest
    from mcp_mikrotik import inventory as inv_mod
    from mcp_mikrotik.config import DeviceConfig

    inv = inv_mod.Inventory([DeviceConfig(title="R", host="192.0.2.1")])
    with pytest.raises(ValueError):
        inv.connect("R", terminal_width=5)
