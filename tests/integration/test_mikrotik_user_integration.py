"""Integration tests for MikroTik user management using testcontainers."""

import asyncio
import os
import subprocess
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip("testcontainers.core.container")
from testcontainers.core.container import DockerContainer

from mcp_mikrotik import config as mikrotik_config_module
from mcp_mikrotik.scope.users import mikrotik_add_user, mikrotik_list_users, mikrotik_remove_user


def _make_ctx():
    """Create a mock FastMCP Context for direct tool function calls."""
    ctx = MagicMock()
    ctx.info = AsyncMock()
    ctx.debug = AsyncMock()
    ctx.warning = AsyncMock()
    ctx.error = AsyncMock()
    return ctx


def _docker_available() -> bool:
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0
    except Exception:
        return False


# One boot attempt is given BOOT_WAIT_ATTEMPTS polls of about ten seconds each; a healthy RouterOS under
# QEMU emulation answers within one to two minutes.
BOOT_ATTEMPTS = 3
BOOT_WAIT_ATTEMPTS = 15


@pytest.fixture(scope="class")
def mikrotik_container():
    """Start a MikroTik RouterOS container."""
    if not _docker_available():
        pytest.skip("Docker is not available/running; skipping integration tests.")

    # with_kwargs REPLACES earlier kwargs rather than merging them, so
    # everything must go in a single call — a second call silently dropped
    # privileged/cap_add, and the entrypoint died in ~5s without them.
    # (The ROUTEROS_* env vars are gone: the image never reads them.)
    #
    # The entrypoint of the image sacrifices one container interface to its QEMU bridge. On a
    # container with a single network that is eth0, and it then enables NO port forwarding, so
    # the published SSH port never reaches the router (issue #143, "breaks the test fixture
    # always"). When eth1 exists it sacrifices eth1 instead, keeps the IP on eth0 and turns the
    # forwarding on. testcontainers attaches only one network, so create a dummy eth1 first.
    kwargs = {
        "privileged": True,
        "cap_add": ["NET_ADMIN", "NET_RAW"],
        "entrypoint": [
            "/bin/bash",
            "-c",
            "ip link add eth1 type dummy && ip addr add 10.99.0.2/24 dev eth1 && ip link set eth1 up; "
            "exec /routeros_source/entrypoint.sh",
        ],
    }
    if os.name != "nt":
        kwargs["devices"] = ["/dev/net/tun:/dev/net/tun"]

    # About one boot in five wedges after RouterOS prints its version banner and never answers on
    # SSH (issue #143, "residual ~20%"). Waiting longer does not help, so give each container a
    # fixed time to come up and start a fresh one if it does not.
    container = None
    for attempt in range(1, BOOT_ATTEMPTS + 1):
        candidate = (
            DockerContainer("evilfreelancer/docker-routeros:latest")
            .with_exposed_ports(22)
            .with_kwargs(**kwargs)
        )
        candidate.start()
        try:
            host = candidate.get_container_host_ip()
            port = int(candidate.get_exposed_port(22))
            _wait_for_mikrotik_ready(host, port, max_attempts=BOOT_WAIT_ATTEMPTS)
            container = candidate
            break
        except Exception as boot_error:
            print(f"RouterOS container did not boot (attempt {attempt} of {BOOT_ATTEMPTS}): {boot_error}")
            try:
                candidate.stop()
            except Exception as cleanup_error:
                print(f"Warning: Cleanup failed: {cleanup_error}")
    if container is None:
        pytest.fail(f"The RouterOS container did not boot in {BOOT_ATTEMPTS} attempts (see issue #143).")

    try:
        _ensure_mikrotik_password(host, port, "mikrotik123")

        yield {
            "host": host,
            "port": port,
            "username": "admin",
            "password": "mikrotik123",
        }
    finally:
        try:
            container.stop()
        except Exception as cleanup_error:
            print(f"Warning: Cleanup failed: {cleanup_error}")


def _wait_for_mikrotik_ready(host: str, port: int, max_attempts: int = 60, delay: int = 5):
    """Wait for the guest's SSH banner — a bare TCP accept proves nothing.

    QEMU's hostfwd listener accepts connections the moment QEMU starts, long
    before RouterOS inside has booted, so connect_ex()==0 was permanently
    true against dead routers. Only the "SSH-..." greeting comes from the
    actual guest.
    """
    import socket
    for attempt in range(max_attempts):
        try:
            sock = socket.create_connection((host, port), timeout=5)
            sock.settimeout(5)
            banner = sock.recv(64)
            sock.close()
            if banner.startswith(b"SSH-"):
                print(f"MikroTik SSH banner received after {attempt + 1} attempts")
                return True
        except Exception as e:
            print(f"Attempt {attempt + 1}: not ready - {e}")
        time.sleep(delay)
    raise Exception("MikroTik container failed to become ready within timeout period")


def _try_set_mikrotik_password(host: str, port: int, new_password: str) -> bool:
    import paramiko
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            hostname=host,
            port=port,
            username="admin",
            password="",
            timeout=20,
            look_for_keys=False,
            allow_agent=False,
        )
        # "/password set ..." is not a RouterOS command; the router answers
        # "expected end of command" on stdout with a zero exit status, so the
        # old fire-and-forget call silently did nothing. Use the real command
        # and read the reply back: any output at all means it was rejected.
        stdin, stdout, stderr = ssh.exec_command(f'/user set 0 password={new_password}')
        reply = (stdout.read() + stderr.read()).decode(errors="replace").strip()
        ssh.close()
        if reply:
            print(f"Password set rejected by RouterOS: {reply[:120]}")
            return False
        print("MikroTik password set from the empty factory default.")
        return True
    except Exception:
        return False


def _verify_ssh_auth(host: str, port: int, password: str, max_attempts: int = 10, delay: int = 10) -> bool:
    import paramiko
    for attempt in range(max_attempts):
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                hostname=host,
                port=port,
                username="admin",
                password=password,
                timeout=10,
                look_for_keys=False,
                allow_agent=False,
            )
            stdin, stdout, stderr = ssh.exec_command('/system identity print')
            result = stdout.read().decode()
            ssh.close()
            if result:
                print(f"SSH authentication verified after {attempt + 1} attempts")
                return True
        except Exception as e:
            print(f"SSH auth attempt {attempt + 1}: {e}")
        time.sleep(delay)
    return False


@pytest.fixture(autouse=True)
def setup_mikrotik_config(mikrotik_container, monkeypatch):
    """Point the library config at the integration-test container."""
    monkeypatch.setattr(mikrotik_config_module.mikrotik_config, "host", mikrotik_container["host"], raising=False)
    monkeypatch.setattr(mikrotik_config_module.mikrotik_config, "port", mikrotik_container["port"], raising=False)
    monkeypatch.setattr(mikrotik_config_module.mikrotik_config, "username", mikrotik_container["username"], raising=False)
    monkeypatch.setattr(mikrotik_config_module.mikrotik_config, "password", mikrotik_container["password"], raising=False)
    monkeypatch.setattr(mikrotik_config_module.mikrotik_config, "key_filename", None, raising=False)


def _ensure_mikrotik_password(host: str, port: int, password: str) -> None:
    # A fresh RouterOS always boots as admin with an EMPTY password (the
    # ROUTEROS_PASS env var was never implemented by the image), so set the
    # password from that state first. Trying the target password first burned
    # the whole 60s retry budget on guaranteed failures.
    if _try_set_mikrotik_password(host, port, password):
        if _verify_ssh_auth(host, port, password, max_attempts=6, delay=5):
            return
    # Fall back for a reused container that already has the password.
    if _verify_ssh_auth(host, port, password, max_attempts=6, delay=5):
        return
    raise Exception("Unable to authenticate to MikroTik container over SSH")


# RouterOS boots under QEMU emulation (no KVM in most Docker setups), and the fixture may have to start
# a second or third container (see BOOT_ATTEMPTS). The default 300 s in pytest.ini would cut that off.
@pytest.mark.timeout(1200)
@pytest.mark.integration
class TestMikroTikUserIntegration:
    test_username = "integration_test_user"
    test_password = "test_password_123"

    def test_01_create_user(self, mikrotik_container):
        print(f"\n=== Testing user creation ===")
        ctx = _make_ctx()
        result = asyncio.run(mikrotik_add_user(
            name=self.test_username,
            password=self.test_password,
            ctx=ctx,
            group="read",
            comment="Integration test user"
        ))
        assert "failed" not in result.lower()
        assert self.test_username in result

    def test_02_list_users(self, mikrotik_container):
        print(f"\n=== Testing user listing ===")
        ctx = _make_ctx()
        result = asyncio.run(mikrotik_list_users(ctx=ctx))
        print(result)
        assert "admin" in result
        assert self.test_username in result

    def test_03_delete_user(self, mikrotik_container):
        print(f"\n=== Testing user deletion ===")
        ctx = _make_ctx()
        result = asyncio.run(mikrotik_remove_user(ctx=ctx, name=self.test_username))
        assert "removed successfully" in result.lower()

        # confirm it's gone
        result = asyncio.run(mikrotik_list_users(ctx=ctx))
        assert self.test_username not in result
