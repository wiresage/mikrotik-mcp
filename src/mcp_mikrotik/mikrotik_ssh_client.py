import base64
import hashlib
import io
import logging
import socket
from typing import Optional

import paramiko

from .sensitive import redact_if_enabled

logger = logging.getLogger(__name__)

# Seconds allowed for the TCP connection, the SSH banner and the login. A device that does not
# answer within this time is treated as unreachable.
CONNECT_TIMEOUT = 10.0

# Seconds a command (or file transfer) may wait for the device before the call gives up. This is
# an idle timeout on the SSH channel: output that keeps arriving resets it, so a long export is
# fine, but a device that logs in and then never answers can no longer block a call (and the
# worker thread running it) for ever. Overridable with MIKROTIK_COMMAND_TIMEOUT.
DEFAULT_COMMAND_TIMEOUT = 180.0


class MikroTikSSHClient:
    """SSH client for MikroTik devices."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        key_filename: Optional[str],
        port: int = 22,
        command_timeout: float = DEFAULT_COMMAND_TIMEOUT,
        allow_agent: bool = False,
        agent_key: Optional[str] = None,
    ):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.client = None
        self.channel = None
        self.key_filename = key_filename
        self.command_timeout = command_timeout
        self.allow_agent = allow_agent
        self.agent_key = agent_key

    def _timeout_error(self) -> TimeoutError:
        # The command is left out of the message: it may carry a password or key.
        return TimeoutError(
            f"The device accepted the connection but did not answer within "
            f"{self.command_timeout:g} seconds."
        )

    @staticmethod
    def _decode_output(data: bytes) -> str:
        """Decode raw SSH output bytes with a multi-encoding fallback chain.

        RouterOS devices may return output encoded in UTF-8, CP1252 (Windows
        Western European), or ISO 8859-1 (Latin-1) depending on the locale
        configured on the device.  Strict UTF-8 decoding raises
        UnicodeDecodeError for characters such as Swedish å/ä/ö (issue #58).

        Fallback order:
          1. UTF-8       — covers ASCII and most modern configurations
          2. CP1252      — covers Windows Western European characters (å ä ö …)
          3. Latin-1     — always succeeds; covers all single-byte code points
        """
        if not data:
            return ""
        for encoding in ("utf-8", "cp1252", "latin-1"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        # Unreachable in practice (latin-1 never raises), but kept as a
        # safety net: replace unrecognised bytes rather than crashing.
        return data.decode("utf-8", errors="replace")

    @staticmethod
    def _agent_key_matches(agent_key: paramiko.PKey, selector: str) -> bool:
        """Return whether an SSH agent key matches the configured selector."""
        if selector.startswith("SHA256:"):
            digest = hashlib.sha256(agent_key.asbytes()).digest()
            fingerprint = "SHA256:" + base64.b64encode(digest).decode().rstrip("=")
            return fingerprint == selector
        parts = selector.split()
        return agent_key.get_base64() == (parts[1] if len(parts) > 1 else parts[0])

    def _connect(self) -> None:
        """Connect using the configured credentials, optionally via the SSH agent."""
        kwargs = {
            "hostname": self.host,
            "port": self.port,
            "username": self.username,
            "password": self.password,
            "key_filename": self.key_filename,
            "look_for_keys": False,
            "timeout": CONNECT_TIMEOUT,
            "banner_timeout": CONNECT_TIMEOUT,
            "auth_timeout": CONNECT_TIMEOUT,
        }
        selector = (self.agent_key or "").strip()
        if self.allow_agent and selector:
            agent = paramiko.Agent()
            try:
                key = next(
                    (k for k in agent.get_keys()
                     if self._agent_key_matches(k, selector)),
                    None,
                )
                if key is None:
                    raise paramiko.SSHException(
                        "agent_key did not match any key offered by the SSH agent"
                    )
                self.client.connect(pkey=key, allow_agent=False, **kwargs)
            finally:
                agent.close()
        else:
            self.client.connect(allow_agent=self.allow_agent, **kwargs)

    def connect(self):
        """Establish SSH connection to MikroTik device."""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self._connect()
            return True
        except Exception as e:
            logger.error("Failed to connect to MikroTik: %s", redact_if_enabled(str(e)))
            # A rejected login still leaves paramiko's transport running: it
            # keeps a thread and a socket, and paramiko holds a strong
            # reference to it, so it is never collected.  Close it here rather
            # than abandoning a half-open connection.
            try:
                self.client.close()
            except Exception:
                pass
            self.client = None
            return False

    def execute_command(self, command: str) -> str:
        """Execute a command on MikroTik device using exec_command."""
        if not self.client:
            raise Exception("Not connected to MikroTik device")

        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=self.command_timeout)

            output = self._decode_output(stdout.read())
            error = self._decode_output(stderr.read())

            if error and not output:
                return error

            return output
        except socket.timeout:
            logger.error("The device did not answer within %g seconds", self.command_timeout)
            raise self._timeout_error() from None
        except Exception as e:
            logger.error("Error executing command: %s", redact_if_enabled(str(e)))
            raise

    def _open_sftp(self):
        """Open an SFTP session, translating RouterOS's policy rejection.

        RouterOS accepts the SSH session but closes the channel when the
        "sftp" subsystem is requested by a user whose group lacks the "ftp"
        policy — paramiko surfaces that as SSHException("Channel closed.").
        Plain exec commands do not need the policy, so the rest of the tools
        keep working on the same credentials, which makes the bare message
        look like a transport bug (issue #113).  Translate it into an
        actionable error; every other SSHException passes through unchanged.
        """
        try:
            return self.client.open_sftp()
        except paramiko.SSHException as e:
            if "channel closed" in str(e).lower():
                raise ConnectionError(
                    "The device rejected the SFTP subsystem ('Channel closed'). "
                    "RouterOS serves file transfers over SFTP only when the SSH "
                    "user's group has the 'ftp' policy; ordinary commands do not "
                    "need it, which is why other tools still work. Check with "
                    "'/user group print' and add the policy with "
                    "'/user group set <group> policy=ftp,<existing policies>'."
                ) from e
            raise

    def download_file(self, remote_filename: str) -> bytes:
        """Download a file from the device over SFTP and return its raw bytes.

        RouterOS exposes its file store over the SSH/SFTP subsystem, so binary
        backups and text exports alike can be transferred without mangling.
        """
        if not self.client:
            raise Exception("Not connected to MikroTik device")

        sftp = self._open_sftp()
        try:
            sftp.get_channel().settimeout(self.command_timeout)
            buffer = io.BytesIO()
            sftp.getfo(remote_filename, buffer)
            return buffer.getvalue()
        except socket.timeout:
            raise self._timeout_error() from None
        finally:
            sftp.close()

    def upload_file(self, remote_filename: str, data: bytes) -> None:
        """Upload raw bytes to a file on the device over SFTP."""
        if not self.client:
            raise Exception("Not connected to MikroTik device")

        sftp = self._open_sftp()
        try:
            sftp.get_channel().settimeout(self.command_timeout)
            sftp.putfo(io.BytesIO(data), remote_filename)
        except socket.timeout:
            raise self._timeout_error() from None
        finally:
            sftp.close()

    def disconnect(self):
        """Close SSH connection."""
        if self.client:
            self.client.close()
