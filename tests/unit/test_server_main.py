import types

import pytest


def test_server_main_runs_mcp_stdio(monkeypatch):
    """stdio takes no transport options — run() must be called bare."""
    from mcp_mikrotik import server

    calls = {"run": 0, "kwargs": None, "transport": None}

    class FakeMcp:
        def run(self, transport: str, **kwargs):
            calls["run"] += 1
            calls["transport"] = transport
            calls["kwargs"] = kwargs

    cfg = types.SimpleNamespace(
        host="10.0.0.1",
        username="admin",
        password="",
        port=22,
        key_filename=None,
        allow_ssh_agent=False,
        ssh_agent_key=None,
        inventory=[],
        inventory_file=None,
        mcp=types.SimpleNamespace(host="127.0.0.1", port=8123, transport="stdio",
                                  allowed_hosts="", allowed_origins=""),
    )

    monkeypatch.setattr(server, "MikrotikConfig", lambda _cli_parse_args=True: cfg)
    monkeypatch.setattr(server, "mcp", FakeMcp())

    server.main()
    assert calls["run"] == 1
    assert calls["transport"] == "stdio"
    assert calls["kwargs"] == {}, "stdio must not receive host/port/transport_security"


def test_server_main_passes_http_options_to_run(monkeypatch):
    """mcp 2.0 removed mcp.settings: host/port/security go to run() as kwargs."""
    from mcp_mikrotik import server

    calls = {"transport": None, "kwargs": None}

    class FakeMcp:
        def run(self, transport: str, **kwargs):
            calls["transport"] = transport
            calls["kwargs"] = kwargs

    cfg = types.SimpleNamespace(
        host="10.0.0.1",
        username="admin",
        password="",
        port=22,
        key_filename=None,
        allow_ssh_agent=False,
        ssh_agent_key=None,
        inventory=[],
        inventory_file=None,
        mcp=types.SimpleNamespace(host="0.0.0.0", port=8123, transport="streamable-http",
                                  allowed_hosts="mcp.example.com", allowed_origins=""),
    )

    monkeypatch.setattr(server, "MikrotikConfig", lambda _cli_parse_args=True: cfg)
    monkeypatch.setattr(server, "mcp", FakeMcp())

    server.main()
    assert calls["transport"] == "streamable-http"
    assert calls["kwargs"]["host"] == "0.0.0.0"
    assert calls["kwargs"]["port"] == 8123
    ts = calls["kwargs"]["transport_security"]
    assert ts.enable_dns_rebinding_protection is True
    assert ts.allowed_hosts == ["mcp.example.com"]


def test_server_main_exits_on_exception(monkeypatch):
    from mcp_mikrotik import server

    class FakeMcp:
        def __init__(self):
            self.settings = types.SimpleNamespace(host=None, port=None)

        def run(self, transport: str):
            raise RuntimeError("boom")

    cfg = types.SimpleNamespace(
        host="10.0.0.1",
        username="admin",
        password="",
        port=22,
        key_filename=None,
        allow_ssh_agent=False,
        ssh_agent_key=None,
        inventory=[],
        inventory_file=None,
        mcp=types.SimpleNamespace(host="127.0.0.1", port=8123, transport="stdio"),
    )

    monkeypatch.setattr(server, "MikrotikConfig", lambda _cli_parse_args=True: cfg)
    monkeypatch.setattr(server, "mcp", FakeMcp())

    def fake_exit(code: int):
        raise SystemExit(code)

    monkeypatch.setattr(server.sys, "exit", fake_exit)

    with pytest.raises(SystemExit) as exc:
        server.main()
    assert exc.value.code == 1


def test_server_main_exits_cleanly_on_bad_inventory_file(monkeypatch, tmp_path, caplog):
    """A broken inventory stops the server at startup: exit 1, run() never called."""
    import logging

    from mcp_mikrotik import server

    calls = {"run": 0}

    class FakeMcp:
        def run(self, transport: str, **kwargs):
            calls["run"] += 1

    bad = tmp_path / "inventory.yaml"
    bad.write_text(
        "- title: core-nl\n  hostname: 10.0.0.1\n  password: FleetSecret9!\n",
        encoding="utf-8",
    )
    cfg = types.SimpleNamespace(
        host="10.0.0.1", username="admin", password="", port=22,
        key_filename=None, inventory=[], inventory_file=str(bad),
        mcp=types.SimpleNamespace(host="127.0.0.1", port=8123, transport="stdio",
                                  allowed_hosts="", allowed_origins=""),
    )
    monkeypatch.setattr(server, "MikrotikConfig", lambda _cli_parse_args=True: cfg)
    monkeypatch.setattr(server, "mcp", FakeMcp())

    with caplog.at_level(logging.ERROR):
        with pytest.raises(SystemExit) as exc:
            server.main()

    assert exc.value.code == 1
    assert calls["run"] == 0, "the server must not start with a broken inventory"
    assert "Invalid MikroTik inventory" in caplog.text
    assert "FleetSecret9!" not in caplog.text


def test_server_main_exits_cleanly_on_bad_inline_inventory(monkeypatch, caplog):
    """Config-level validation errors get the clean message, not a traceback."""
    import logging

    from pydantic import ValidationError

    from mcp_mikrotik import server
    from mcp_mikrotik.config import MikrotikConfig

    def bad_config(_cli_parse_args=True):
        # A schema-invalid inline inventory raises at config construction.
        return MikrotikConfig(inventory='[{title: A, password: Hunter22}]')

    monkeypatch.setattr(server, "MikrotikConfig", bad_config)

    with caplog.at_level(logging.ERROR):
        with pytest.raises(SystemExit) as exc:
            server.main()

    assert exc.value.code == 1
    assert "Invalid MikroTik configuration" in caplog.text
    assert "host" in caplog.text            # the missing field is named
    assert "Hunter22" not in caplog.text    # the credential is not


def test_credential_warning_emitted_in_container_with_password(monkeypatch):
    """Warning fires when a plaintext password is set inside a container."""
    from mcp_mikrotik.server import _warn_if_plaintext_password_in_container
    import logging, io, types

    monkeypatch.setattr("os.path.exists", lambda p: p == "/.dockerenv")

    cfg = types.SimpleNamespace(password="secret", key_filename=None)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logger = logging.getLogger("test_warn")
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    _warn_if_plaintext_password_in_container(cfg, logger)
    logger.removeHandler(handler)
    assert "plaintext password" in stream.getvalue()


def test_credential_warning_suppressed_without_password(monkeypatch):
    """No warning when no password is set (e.g. key-only / unauthenticated setup)."""
    from mcp_mikrotik.server import _warn_if_plaintext_password_in_container
    import logging, io, types

    monkeypatch.setattr("os.path.exists", lambda p: p == "/.dockerenv")

    cfg = types.SimpleNamespace(password="", key_filename="/keys/id_ed25519")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logger = logging.getLogger("test_warn_nopw")
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    _warn_if_plaintext_password_in_container(cfg, logger)
    logger.removeHandler(handler)
    assert stream.getvalue() == ""


def test_credential_warning_suppressed_outside_container(monkeypatch):
    """No warning when not running inside a container."""
    from mcp_mikrotik.server import _warn_if_plaintext_password_in_container
    import logging, io, types

    monkeypatch.setattr("os.path.exists", lambda p: False)
    monkeypatch.delenv("container", raising=False)

    cfg = types.SimpleNamespace(password="secret", key_filename=None)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logger = logging.getLogger("test_warn_nocontainer")
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    _warn_if_plaintext_password_in_container(cfg, logger)
    logger.removeHandler(handler)
    assert stream.getvalue() == ""


def _mcp_cfg(host="0.0.0.0", allowed_hosts="", allowed_origins=""):
    import types
    return types.SimpleNamespace(
        host=host, allowed_hosts=allowed_hosts, allowed_origins=allowed_origins
    )


def test_transport_security_localhost_uses_localhost_allowlist():
    """Localhost bind with no allowlist keeps the secure localhost default."""
    import logging
    from mcp_mikrotik.server import _build_transport_security

    s = _build_transport_security(_mcp_cfg(host="127.0.0.1"), logging.getLogger("t"))
    assert s.enable_dns_rebinding_protection is True
    assert "127.0.0.1:*" in s.allowed_hosts


def test_transport_security_non_localhost_disables_without_allowlist(caplog):
    """Non-localhost bind with no allowlist disables protection (and warns)."""
    import logging
    from mcp_mikrotik.server import _build_transport_security

    with caplog.at_level(logging.WARNING):
        s = _build_transport_security(_mcp_cfg(host="0.0.0.0"), logging.getLogger("t"))
    assert s.enable_dns_rebinding_protection is False
    assert "non-localhost" in caplog.text


def test_transport_security_explicit_allowlist_enabled():
    """A configured allowlist enables protection with those hosts (the #86 fix)."""
    import logging
    from mcp_mikrotik.server import _build_transport_security

    s = _build_transport_security(
        _mcp_cfg(host="0.0.0.0", allowed_hosts="mcp.example.com, mcp.example.com:*"),
        logging.getLogger("t"),
    )
    assert s.enable_dns_rebinding_protection is True
    assert s.allowed_hosts == ["mcp.example.com", "mcp.example.com:*"]


def test_transport_security_wildcard_disables():
    """allowed_hosts='*' is an explicit opt-out."""
    import logging
    from mcp_mikrotik.server import _build_transport_security

    s = _build_transport_security(
        _mcp_cfg(host="0.0.0.0", allowed_hosts="*"), logging.getLogger("t")
    )
    assert s.enable_dns_rebinding_protection is False


def test_transport_security_allowed_origins_parsed():
    """Origins are parsed and protection is enabled."""
    import logging
    from mcp_mikrotik.server import _build_transport_security

    s = _build_transport_security(
        _mcp_cfg(host="0.0.0.0", allowed_origins="https://app.example.com"),
        logging.getLogger("t"),
    )
    assert s.enable_dns_rebinding_protection is True
    assert s.allowed_origins == ["https://app.example.com"]


def test_server_main_handles_keyboard_interrupt(monkeypatch):
    from mcp_mikrotik import server

    class FakeMcp:
        def __init__(self):
            self.settings = types.SimpleNamespace(host=None, port=None)

        def run(self, transport: str):
            raise KeyboardInterrupt()

    cfg = types.SimpleNamespace(
        host="10.0.0.1",
        username="admin",
        password="",
        port=22,
        key_filename=None,
        allow_ssh_agent=False,
        ssh_agent_key=None,
        inventory=[],
        inventory_file=None,
        mcp=types.SimpleNamespace(host="127.0.0.1", port=8123, transport="stdio"),
    )

    monkeypatch.setattr(server, "MikrotikConfig", lambda _cli_parse_args=True: cfg)
    monkeypatch.setattr(server, "mcp", FakeMcp())

    server.main()

