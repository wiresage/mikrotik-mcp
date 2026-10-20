import base64
import hashlib
import io
import types

import paramiko
import pytest


# ---------------------------------------------------------------------------
# _decode_output: encoding fallback (issue #58)
# ---------------------------------------------------------------------------

class TestDecodeOutput:
    """Unit tests for MikroTikSSHClient._decode_output."""

    def setup_method(self):
        from mcp_mikrotik.mikrotik_ssh_client import MikroTikSSHClient
        self.decode = MikroTikSSHClient._decode_output

    def test_empty_bytes_returns_empty_string(self):
        assert self.decode(b"") == ""

    def test_pure_ascii_decoded_correctly(self):
        assert self.decode(b"hello world") == "hello world"

    def test_valid_utf8_decoded_correctly(self):
        # UTF-8 encoded euro sign and em-dash
        data = "€—".encode("utf-8")
        assert self.decode(data) == "€—"

    def test_cp1252_swedish_chars_decoded_correctly(self):
        # Swedish å ä ö — encoded as CP1252 / Latin-1 overlapping bytes
        # CP1252: å=0xE5, ä=0xE4, ö=0xF6
        data = "från Gör om ö".encode("cp1252")
        result = self.decode(data)
        assert "å" in result or "\xe5" in result  # å
        assert "ö" in result or "\xf6" in result  # ö

    def test_latin1_only_bytes_decoded_without_error(self):
        # Bytes that are valid latin-1 but not valid UTF-8 or CP1252
        # 0x9D is undefined in CP1252 but valid latin-1
        data = bytes([0x48, 0x65, 0x6C, 0x6C, 0x6F, 0x9D])
        result = self.decode(data)
        assert isinstance(result, str)
        assert result.startswith("Hello")

    def test_cp1252_nat_rule_comment_does_not_raise(self):
        # Simulated RouterOS NAT print output with a Swedish comment
        # b"\xf6" = ö in cp1252
        raw = b"chain=srcnat action=masquerade comment=\"\xf6ppet n\xe4t\""
        result = self.decode(raw)
        assert isinstance(result, str)
        assert "ppet" in result  # partial match regardless of exact char

    def test_swedish_bytes_reported_in_issue_do_not_raise(self):
        # Exact bytes mentioned in the issue: 0xf6 (ö) and 0xe5 (å)
        raw = bytes([0xF6, 0x20, 0xE5])
        result = self.decode(raw)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# execute_command with non-ASCII stdout/stderr
# ---------------------------------------------------------------------------

def test_execute_command_handles_cp1252_stdout(monkeypatch):
    from mcp_mikrotik.mikrotik_ssh_client import MikroTikSSHClient
    import mcp_mikrotik.mikrotik_ssh_client as mod

    # Simulate RouterOS returning CP1252-encoded bytes on stdout
    cp1252_bytes = "comment=\"från\"".encode("cp1252")

    class DummySSH:
        def set_missing_host_key_policy(self, _): pass
        def connect(self, **kwargs): pass
        def exec_command(self, command, timeout=None):
            return (None, io.BytesIO(cp1252_bytes), io.BytesIO(b""))
        def close(self): pass

    monkeypatch.setattr(mod.paramiko, "SSHClient", lambda: DummySSH())

    client = MikroTikSSHClient(host="h", username="u", password="p", key_filename=None)
    assert client.connect() is True
    result = client.execute_command("/ip firewall nat print")
    assert isinstance(result, str)
    assert "comment=" in result


def test_execute_command_handles_cp1252_stderr(monkeypatch):
    from mcp_mikrotik.mikrotik_ssh_client import MikroTikSSHClient
    import mcp_mikrotik.mikrotik_ssh_client as mod

    # Non-ASCII bytes on stderr, empty stdout → should return decoded stderr
    cp1252_err = "failure: ej till\xe5ten".encode("cp1252")

    class DummySSH:
        def set_missing_host_key_policy(self, _): pass
        def connect(self, **kwargs): pass
        def exec_command(self, command, timeout=None):
            return (None, io.BytesIO(b""), io.BytesIO(cp1252_err))
        def close(self): pass

    monkeypatch.setattr(mod.paramiko, "SSHClient", lambda: DummySSH())

    client = MikroTikSSHClient(host="h", username="u", password="p", key_filename=None)
    assert client.connect() is True
    result = client.execute_command("/ip firewall nat print")
    assert isinstance(result, str)
    assert "failure" in result


def test_ssh_client_requires_connect_for_execute():
    from mcp_mikrotik.mikrotik_ssh_client import MikroTikSSHClient

    client = MikroTikSSHClient(host="h", username="u", password="p", key_filename=None, port=22)
    with pytest.raises(Exception, match="Not connected"):
        client.execute_command("/system identity print")


def test_ssh_client_connect_and_execute(monkeypatch):
    from mcp_mikrotik.mikrotik_ssh_client import MikroTikSSHClient
    import mcp_mikrotik.mikrotik_ssh_client as mod

    state = {"connect_kwargs": None, "closed": 0}

    class DummySSH:
        def set_missing_host_key_policy(self, _policy):
            pass

        def connect(self, **kwargs):
            state["connect_kwargs"] = kwargs

        def exec_command(self, command: str, timeout=None):
            assert command == "/system identity print"
            return (None, io.BytesIO(b"out"), io.BytesIO(b""))

        def close(self):
            state["closed"] += 1

    monkeypatch.setattr(mod.paramiko, "SSHClient", lambda: DummySSH())

    client = MikroTikSSHClient(host="h", username="u", password="p", key_filename="k", port=2222)
    assert client.connect() is True
    assert state["connect_kwargs"]["hostname"] == "h"
    assert state["connect_kwargs"]["port"] == 2222
    assert state["connect_kwargs"]["username"] == "u"
    assert state["connect_kwargs"]["password"] == "p"
    assert state["connect_kwargs"]["key_filename"] == "k"

    assert client.execute_command("/system identity print") == "out"
    client.disconnect()
    assert state["closed"] == 1


def test_failed_connect_closes_the_half_open_client(monkeypatch):
    """A rejected login must not leave paramiko's transport running."""
    from mcp_mikrotik.mikrotik_ssh_client import MikroTikSSHClient
    import mcp_mikrotik.mikrotik_ssh_client as mod

    state = {"closed": 0}

    class RejectingSSH:
        def set_missing_host_key_policy(self, _policy):
            pass

        def connect(self, **kwargs):
            raise mod.paramiko.AuthenticationException("bad password")

        def close(self):
            state["closed"] += 1

    monkeypatch.setattr(mod.paramiko, "SSHClient", lambda: RejectingSSH())

    client = MikroTikSSHClient(host="h", username="u", password="wrong", key_filename=None)
    assert client.connect() is False
    assert state["closed"] == 1
    # and the object reports itself as unusable rather than half-connected
    assert client.client is None
    with pytest.raises(Exception, match="Not connected"):
        client.execute_command("/system identity print")


def test_ssh_client_returns_stderr_when_no_stdout(monkeypatch):
    from mcp_mikrotik.mikrotik_ssh_client import MikroTikSSHClient
    import mcp_mikrotik.mikrotik_ssh_client as mod

    class DummySSH:
        def set_missing_host_key_policy(self, _policy):
            pass

        def connect(self, **kwargs):
            pass

        def exec_command(self, command: str, timeout=None):
            return (None, io.BytesIO(b""), io.BytesIO(b"failure: nope"))

        def close(self):
            pass

    monkeypatch.setattr(mod.paramiko, "SSHClient", lambda: DummySSH())

    client = MikroTikSSHClient(host="h", username="u", password="p", key_filename=None, port=22)
    assert client.connect() is True
    assert client.execute_command("/x") == "failure: nope"


# ---------------------------------------------------------------------------
# SFTP file transfer: download_file / upload_file
# ---------------------------------------------------------------------------

def _connect_client_with_sftp(monkeypatch, sftp):
    from mcp_mikrotik.mikrotik_ssh_client import MikroTikSSHClient
    import mcp_mikrotik.mikrotik_ssh_client as mod

    class DummySSH:
        def set_missing_host_key_policy(self, _policy):
            pass

        def connect(self, **kwargs):
            pass

        def open_sftp(self):
            return sftp

        def close(self):
            pass

    monkeypatch.setattr(mod.paramiko, "SSHClient", lambda: DummySSH())
    client = MikroTikSSHClient(host="h", username="u", password="p", key_filename=None)
    assert client.connect() is True
    return client


def test_ssh_client_download_file_via_sftp(monkeypatch):
    class DummySFTP:
        def __init__(self, payload):
            self.payload = payload
            self.closed = False
            self.requested = None

        def get_channel(self):
            return types.SimpleNamespace(settimeout=lambda seconds: None)

        def getfo(self, remotepath, fileobj):
            self.requested = remotepath
            fileobj.write(self.payload)

        def close(self):
            self.closed = True

    # Binary payload that is NOT valid UTF-8 — proves raw bytes survive intact.
    sftp = DummySFTP(b"\x00\x01\x02backup\xff")
    client = _connect_client_with_sftp(monkeypatch, sftp)

    data = client.download_file("backup_123.backup")
    assert data == b"\x00\x01\x02backup\xff"
    assert sftp.requested == "backup_123.backup"
    assert sftp.closed is True


def test_ssh_client_upload_file_via_sftp(monkeypatch):
    captured = {}

    class DummySFTP:
        def __init__(self):
            self.closed = False

        def get_channel(self):
            return types.SimpleNamespace(settimeout=lambda seconds: None)

        def putfo(self, fileobj, remotepath):
            captured["remotepath"] = remotepath
            captured["data"] = fileobj.read()

        def close(self):
            self.closed = True

    sftp = DummySFTP()
    client = _connect_client_with_sftp(monkeypatch, sftp)

    client.upload_file("restore.rsc", b"/system identity\n")
    assert captured["remotepath"] == "restore.rsc"
    assert captured["data"] == b"/system identity\n"
    assert sftp.closed is True


def test_ssh_client_download_requires_connect():
    from mcp_mikrotik.mikrotik_ssh_client import MikroTikSSHClient

    client = MikroTikSSHClient(host="h", username="u", password="p", key_filename=None, port=22)
    with pytest.raises(Exception, match="Not connected"):
        client.download_file("x.backup")


def test_ssh_client_upload_requires_connect():
    from mcp_mikrotik.mikrotik_ssh_client import MikroTikSSHClient

    client = MikroTikSSHClient(host="h", username="u", password="p", key_filename=None, port=22)
    with pytest.raises(Exception, match="Not connected"):
        client.upload_file("x.rsc", b"data")


# ---------------------------------------------------------------------------
# SSH agent authentication
# ---------------------------------------------------------------------------

def _agent_client(monkeypatch, keys, password="p", **kwargs):
    import mcp_mikrotik.mikrotik_ssh_client as mod

    seen = {}
    agents = []

    class FakeAgent:
        def __init__(self):
            self.closed = False

        def get_keys(self):
            return tuple(keys)

        def close(self):
            self.closed = True

    class FakeSSH:
        def set_missing_host_key_policy(self, policy):
            pass

        def connect(self, **connect_kwargs):
            seen.update(connect_kwargs)

        def close(self):
            pass

    def make_agent():
        agent = FakeAgent()
        agents.append(agent)
        return agent

    monkeypatch.setattr(mod.paramiko, "SSHClient", FakeSSH)
    monkeypatch.setattr(mod.paramiko, "Agent", make_agent)
    return mod.MikroTikSSHClient("h", "u", password, None, **kwargs), seen, agents


class TestAgentKeyMatches:
    def test_full_ecdsa_public_key_line(self):
        from mcp_mikrotik.mikrotik_ssh_client import MikroTikSSHClient

        key = paramiko.ECDSAKey.generate()
        selector = f"{key.get_name()} {key.get_base64()} user@host"
        assert MikroTikSSHClient._agent_key_matches(key, selector)

    def test_bare_base64_blob(self):
        from mcp_mikrotik.mikrotik_ssh_client import MikroTikSSHClient

        key = paramiko.ECDSAKey.generate()
        assert MikroTikSSHClient._agent_key_matches(key, key.get_base64())

    def test_sha256_fingerprint(self):
        from mcp_mikrotik.mikrotik_ssh_client import MikroTikSSHClient

        key = paramiko.ECDSAKey.generate()
        digest = hashlib.sha256(key.asbytes()).digest()
        fingerprint = "SHA256:" + base64.b64encode(digest).decode().rstrip("=")
        assert MikroTikSSHClient._agent_key_matches(key, fingerprint)

    def test_other_key_does_not_match(self):
        from mcp_mikrotik.mikrotik_ssh_client import MikroTikSSHClient

        key = paramiko.ECDSAKey.generate()
        other = paramiko.ECDSAKey.generate()
        assert not MikroTikSSHClient._agent_key_matches(key, other.get_base64())


class TestAgentConnect:
    def test_selects_only_matching_key(self, monkeypatch):
        key = paramiko.ECDSAKey.generate()
        other = paramiko.ECDSAKey.generate()
        client, seen, agents = _agent_client(
            monkeypatch, (other, key), allow_agent=True, agent_key=key.get_base64()
        )

        assert client.connect() is True
        assert seen["pkey"] is key
        assert seen["allow_agent"] is False
        assert agents[0].closed is True

    def test_strips_whitespace_from_selector(self, monkeypatch):
        key = paramiko.ECDSAKey.generate()
        client, seen, _ = _agent_client(
            monkeypatch, (key,), allow_agent=True, agent_key=f"  {key.get_base64()}  "
        )

        assert client.connect() is True
        assert seen["pkey"] is key

    def test_without_selector_uses_paramiko_agent(self, monkeypatch):
        client, seen, agents = _agent_client(monkeypatch, (), allow_agent=True)

        assert client.connect() is True
        assert seen["allow_agent"] is True
        assert "pkey" not in seen
        assert agents == []

    def test_unknown_selector_fails(self, monkeypatch):
        key = paramiko.ECDSAKey.generate()
        other = paramiko.ECDSAKey.generate()
        client, seen, agents = _agent_client(
            monkeypatch, (other,), allow_agent=True, agent_key=key.get_base64()
        )

        assert client.connect() is False
        assert client.client is None
        assert seen == {}
        assert agents[0].closed is True

    def test_blank_password_is_forwarded(self, monkeypatch):
        key = paramiko.ECDSAKey.generate()
        client, seen, _ = _agent_client(
            monkeypatch, (key,), password="", allow_agent=True, agent_key=key.get_base64()
        )

        assert client.connect() is True
        assert seen["password"] == ""

