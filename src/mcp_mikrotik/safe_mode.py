import logging
import re
import threading
import time
from typing import Dict, Optional

from .mikrotik_ssh_client import MikroTikSSHClient

logger = logging.getLogger(__name__)

# Matches MikroTik prompts in both normal and safe-mode:
#   [admin@MikroTik] >
#   [admin@MikroTik] <SAFE> >
_PROMPT_RE = re.compile(r'\[.+?@.+?\] (?:<SAFE> )?> ?$', re.MULTILINE)

# Strip ANSI/VT escape sequences that MikroTik emits on interactive shells
_ANSI_RE = re.compile(
    r'\x1b(?:'
    r'\[[0-9;]*[mABCDEFGHJKLMSTfhilmnprsu]'
    r'|[()][0-9A-Za-z]'
    r'|\[?\?[0-9]+[hl]'
    r'|\[\d*[ABCDEFGHJKLMST]'
    r'|\[c'
    r'|Z'
    r')'
)

# The RouterOS console treats the session as a real terminal: it measures the
# screen by moving the cursor to the extremes and asking where it ended up, and
# probes the terminal type. If nothing answers, the console stays
# half-initialised — slow to render, and RouterOS closes the channel outright
# when Ctrl-X asks it to redraw for safe mode. Answer as a healthy 220x50 VT.
_TERMINAL_QUERIES = (
    ('\x1b[6n', '\x1b[50;220R'),   # DSR: report cursor position
    ('\x1bZ', '\x1b[?6c'),         # DECID: identify terminal
    ('\x1b[c', '\x1b[?6c'),        # DA: device attributes
)

# End-of-command sentinel for the safe-mode shell (see execute()).  The echoed
# command line contains it inside quotes; the output occurrence stands alone.
_EOC = "__MCP_SAFE_MODE_EOC__"
_EOC_LINE_RE = re.compile(rf'^{_EOC}\s*$', re.MULTILINE)

# A redraw can leave a prompt fragment without its trailing "> " on its own
# line; treat those as prompt noise too when cleaning command output.
_PROMPT_NOISE_RE = re.compile(r'^\[.+?@.+?\] (?:<SAFE> ?)?>? ?$')


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub('', text)


class SafeModeManager:
    """
    Manages a persistent interactive SSH session for MikroTik Safe Mode.

    Safe Mode is activated by sending Ctrl+X (0x18) to the interactive shell.
    While active, any change is held in memory only — a reboot or session drop
    reverts all changes.  Sending Ctrl+X a second time commits the changes and
    exits Safe Mode.
    """

    def __init__(self, device: Optional[str] = None) -> None:
        # Inventory title of the device this session belongs to. ``None`` means
        # "the only device", resolved through the inventory at connect time.
        self.device = device
        self._ssh: Optional[MikroTikSSHClient] = None
        self._channel = None
        self._active = False
        self._lock = threading.Lock()

    @property
    def is_active(self) -> bool:
        return self._active

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enable(self) -> str:
        """Open a persistent SSH shell and activate MikroTik Safe Mode."""
        with self._lock:
            if self._active:
                return "Safe mode is already active."

            # Safe mode needs a persistent shell that outlives a single
            # command, so it holds its own connection rather than borrowing one
            # from the inventory, and builds it from the resolved device.
            from .inventory import DeviceNotFoundError, get_inventory

            try:
                target = get_inventory().resolve(self.device)
            except DeviceNotFoundError as exc:
                return f"Error: {exc}"

            ssh = MikroTikSSHClient(
                host=target.host,
                username=target.username,
                password=target.password,
                key_filename=target.key_filename,
                port=target.port,
                allow_ssh_agent=target.allow_ssh_agent,
                ssh_agent_key=target.ssh_agent_key,
            )
            if not ssh.connect():
                return (
                    f"Error: Failed to connect to MikroTik device '{target.title}' "
                    "for safe mode session."
                )

            channel = ssh.client.invoke_shell(term='dumb', width=220, height=50)
            channel.settimeout(1.0)
            self._ssh = ssh
            self._channel = channel

            # Wait for the initial shell prompt, answering RouterOS's
            # first-login dialogs on the way.
            initial = self._login_until_prompt(timeout=45)
            if not _PROMPT_RE.search(initial):
                self._cleanup()
                return (
                    f"Error: Timed out waiting for MikroTik shell prompt. "
                    f"Got: {repr(initial[:300])}"
                )

            # Ctrl+X activates safe mode
            channel.send('\x18')
            response = self._read_until_safe_mode_ack(timeout=30)

            # RouterOS 7.21+ confirms with "Taking Safe Mode session...
            # Success!" and only redraws the <SAFE> prompt afterwards — on a
            # slow (QEMU serial) console that redraw can outlast any sane read
            # window, so the confirmation message must count as activation too.
            activated = '<SAFE>' in response or (
                'Safe Mode session' in response and 'Success' in response
            )
            if not activated:
                self._cleanup()
                return (
                    f"Error: Safe mode did not activate. "
                    f"Response: {repr(response[:300])}"
                )

            self._active = True
            return (
                "Safe mode ENABLED. All changes are temporary — they will be "
                "reverted automatically if the connection drops or you call "
                "rollback_safe_mode. Call commit_safe_mode to make changes permanent."
            )

    def execute(self, command: str) -> str:
        """Execute a command through the safe-mode persistent shell session.

        The command is chained with ``:put`` of a sentinel, and the read runs
        until that sentinel arrives on a line of its own.  Matching the
        rendered prompt instead is a race: the console redraws prompt + echo
        the moment the command is sent, so a prompt-shaped fragment can end a
        chunk long before the command's real output has arrived.
        """
        if not self._active or not self._channel:
            raise RuntimeError("Safe mode session is not active.")

        with self._lock:
            self._channel.send(f'{command}; :put "{_EOC}"\n')
            raw = self._read_until_marker()
            return self._extract_output(raw, command)

    def commit(self) -> str:
        """Send Ctrl+X again to exit Safe Mode and persist all changes."""
        with self._lock:
            if not self._active:
                return "Safe mode is not active. Nothing to commit."

            self._channel.send('\x18')
            response = self._read_until_prompt(timeout=15)
            self._cleanup()

            # After exiting safe mode the prompt should no longer contain <SAFE>
            if '<SAFE>' not in response:
                return "Changes committed successfully. Safe mode DISABLED."
            return f"Commit attempted. Response: {response[:200]}"

    def rollback(self) -> str:
        """Close the session to trigger MikroTik's automatic safe-mode revert."""
        with self._lock:
            if not self._active:
                return "Safe mode is not active. Nothing to roll back."

            self._cleanup()
            # RouterOS applies the revert asynchronously after the session
            # drops; give it a moment so a follow-up read doesn't catch the
            # pre-revert state.
            time.sleep(2.0)
            return (
                "Safe mode session closed. MikroTik has reverted all "
                "uncommitted changes automatically."
            )

    def status(self) -> str:
        if self._active:
            return (
                "Safe mode is ACTIVE. Changes are pending — they are NOT yet "
                "persisted. Call commit_safe_mode to persist or "
                "rollback_safe_mode to revert."
            )
        return (
            "Safe mode is NOT active. Changes take effect and persist immediately."
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _answer_terminal_queries(self, buf: str, answered: Dict[str, int]) -> None:
        """Reply to VT terminal probes, remembering what was already answered.

        Counting against the accumulated buffer rather than the last chunk
        means a probe split across two network reads is still answered once
        its tail arrives — a missed probe can stall the console (the DA query
        after each prompt is sent exactly once and gates the final "> ").
        """
        for query, reply in _TERMINAL_QUERIES:
            seen = buf.count(query)
            for _ in range(seen - answered.get(query, 0)):
                self._channel.send(reply)
            answered[query] = seen

    def _login_until_prompt(self, timeout: float = 45.0) -> str:
        """Read the login stream until the shell prompt, answering dialogs.

        An interactive RouterOS login is not just a prompt: on a fresh device
        it first asks "Do you want to see the software license? [Y/n]:", and as
        long as the admin password is empty RouterOS 7.21+ interposes a
        "Change your password" / "new password>" step on *every* login.  Both
        block forever if unanswered, so decline the license and Ctrl-C the
        password step (changing credentials behind the operator's back is not
        this tool's call to make).  The QEMU serial console used by the test
        containers also needs ~20s just to render the login banner, hence the
        generous default timeout.
        """
        buf = ""
        answered: Dict[str, int] = {}
        answered_license = False
        skipped_password = False
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if self._channel.recv_ready():
                    chunk = self._channel.recv(4096).decode('utf-8', errors='replace')
                    buf += chunk
                    self._answer_terminal_queries(buf, answered)
                    cleaned = _strip_ansi(buf)
                    if _PROMPT_RE.search(cleaned):
                        return cleaned
                    if not answered_license and "[Y/n]" in cleaned:
                        self._channel.send('n')
                        answered_license = True
                    if not skipped_password and "new password>" in cleaned:
                        self._channel.send('\x03')
                        skipped_password = True
            except Exception:
                break
            time.sleep(0.05)
        return _strip_ansi(buf)

    def _read_until_safe_mode_ack(self, timeout: float = 30.0) -> str:
        """Read until safe-mode activation is acknowledged.

        Waiting for the prompt alone would stall: RouterOS 7.21 prints
        "Taking Safe Mode session... Success!" within a second, but its
        colored <SAFE> prompt redraw does not reliably match the prompt
        pattern — so without the early exit every enable would sit out the
        whole timeout before the fallback check rescued it.
        """
        buf = ""
        answered: Dict[str, int] = {}
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if self._channel.recv_ready():
                    chunk = self._channel.recv(4096).decode('utf-8', errors='replace')
                    buf += chunk
                    self._answer_terminal_queries(buf, answered)
                    cleaned = _strip_ansi(buf)
                    if '<SAFE>' in cleaned or (
                        'Safe Mode session' in cleaned and 'Success' in cleaned
                    ):
                        return cleaned
            except Exception:
                break
            time.sleep(0.05)
        return _strip_ansi(buf)

    def _read_until_marker(self, timeout: float = 30.0) -> str:
        """Read until the end-of-command sentinel appears on its own line."""
        buf = ""
        answered: Dict[str, int] = {}
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if self._channel.recv_ready():
                    chunk = self._channel.recv(4096).decode('utf-8', errors='replace')
                    buf += chunk
                    self._answer_terminal_queries(buf, answered)
                    cleaned = _strip_ansi(buf).replace('\r\n', '\n').replace('\r', '\n')
                    if _EOC_LINE_RE.search(cleaned):
                        return cleaned
            except Exception:
                break
            time.sleep(0.05)
        return _strip_ansi(buf)

    def _read_until_prompt(self, timeout: float = 15.0) -> str:
        """Read from the channel until a RouterOS prompt is detected."""
        buf = ""
        answered: Dict[str, int] = {}
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if self._channel.recv_ready():
                    chunk = self._channel.recv(4096).decode('utf-8', errors='replace')
                    buf += chunk
                    self._answer_terminal_queries(buf, answered)
                    cleaned = _strip_ansi(buf)
                    if _PROMPT_RE.search(cleaned):
                        return cleaned
            except Exception:
                break
            time.sleep(0.05)
        return _strip_ansi(buf)

    def _extract_output(self, raw: str, command: str) -> str:
        """Return the lines between the command's echo and the sentinel."""
        text = _strip_ansi(raw).replace('\r\n', '\n').replace('\r', '\n')

        result_lines: list[str] = []
        past_echo = False
        for line in text.split('\n'):
            stripped = line.strip()
            if stripped == _EOC:
                # The ':put' output — everything after it is the next prompt.
                break
            if _EOC in stripped or (not past_echo and command.strip() in stripped):
                # An echo of the sent line.  The console can replay it more
                # than once (typing echo, then a history reprint), and every
                # replay carries the chained ':put' suffix — skip them all.
                past_echo = True
                continue
            if not past_echo:
                continue
            if _PROMPT_RE.match(stripped) or _PROMPT_NOISE_RE.match(stripped):
                continue
            result_lines.append(line)

        return '\n'.join(result_lines).strip()

    def _cleanup(self) -> None:
        self._active = False
        if self._channel:
            try:
                self._channel.close()
            except Exception:
                pass
            self._channel = None
        if self._ssh:
            try:
                self._ssh.disconnect()
            except Exception:
                pass
            self._ssh = None


# ---------------------------------------------------------------------------
# One manager per device
# ---------------------------------------------------------------------------
#
# Safe mode holds a persistent shell, so it MUST be tracked per device: with a
# single shared manager, enabling safe mode on one router would silently route
# every other device's commands into that router's shell.

_managers: Dict[str, SafeModeManager] = {}
_manager_lock = threading.Lock()


def _manager_key(device: Optional[str]) -> str:
    """Resolve the device to a stable key.

    Resolution failures must propagate: swallowing them here would fabricate a
    fresh inactive manager under a phantom key, so a typo'd or omitted device
    would be told "safe mode is not active — nothing to commit" while the real
    device still holds uncommitted changes that revert when its session drops.
    """
    from .inventory import get_inventory

    return get_inventory().resolve(device).title.casefold()


def get_safe_mode_manager(device: Optional[str] = None) -> SafeModeManager:
    """Return the safe-mode manager for ``device`` (the only device if omitted).

    Raises :class:`~mcp_mikrotik.inventory.DeviceNotFoundError` when the device
    cannot be resolved, exactly like every other device-scoped operation.
    """
    key = _manager_key(device)
    manager = _managers.get(key)
    if manager is None:
        with _manager_lock:
            manager = _managers.get(key)
            if manager is None:
                manager = SafeModeManager(device)
                _managers[key] = manager
    return manager

