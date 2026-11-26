import logging
import re
import secrets
import threading
import time
from typing import Dict, Optional, Tuple

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

# Output markers for the safe-mode shell (see execute()).  Each command is sent
# as  :put "<BEGIN>"; <command>; :put "<END>"  with a fresh nonce, and its
# output is exactly the lines between the BEGIN and END lines that :put prints.
# The echoed command line also contains both markers, but inside quotes and
# with the command around them, so an echo line never consists of a marker
# alone, not even when the console wraps a long echo across several lines.
_MARKER_PREFIX = "__MCP_SAFE_MODE_"

# A redraw can leave a prompt fragment without its trailing "> " on its own
# line; treat those as prompt noise too when cleaning command output.
_PROMPT_NOISE_RE = re.compile(r'^\[.+?@.+?\] (?:<SAFE> ?)?>? ?$')

# The "[user@identity]" part of a prompt, wherever it appears on a line (an
# echo line carries the prompt in front of the command).
_PROMPT_HEAD_RE = re.compile(r'\[[^\]\n]+@[^\]\n]+\]')

# A console error that stops a command line: a parse error means nothing on
# the line ran (not even the BEGIN marker), a runtime error ends the script
# before the END marker.
_CONSOLE_ERROR_RE = re.compile(
    r'^\s*(?:bad command name|syntax error|expected |input does not match|'
    r'invalid value|ambiguous value|not enough permissions|no such command|'
    r'failure:|error:)|\(line \d+ column \d+\)',
    re.IGNORECASE | re.MULTILINE,
)

# What RouterOS prints when Ctrl+X gives the safe-mode session back
# ("[Safe Mode released]" on 6.x, "Releasing Safe Mode... Success!" on 7.25).
_RELEASE_RE = re.compile(r'safe ?mode[^\n]*releas|releas[^\n]*safe ?mode', re.IGNORECASE)


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub('', text)


def _normalise(text: str) -> str:
    return _strip_ansi(text).replace('\r\n', '\n').replace('\r', '\n')


def _markers() -> tuple[str, str, str]:
    """Return (nonce, begin, end) markers unique to one command."""
    nonce = secrets.token_hex(4)
    return nonce, f"{_MARKER_PREFIX}BEGIN_{nonce}__", f"{_MARKER_PREFIX}END_{nonce}__"


def _standalone(marker: str) -> re.Pattern:
    return re.compile(rf'^[ \t]*{re.escape(marker)}[ \t]*$', re.MULTILINE)


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

        The command is bracketed by ``:put`` of a BEGIN and an END marker that
        carry a per-call nonce, and its output is exactly what arrives between
        the two printed markers.  Matching the rendered prompt instead is a
        race (the console redraws prompt + echo the moment the command is
        sent), and recognising the echo by its text breaks as soon as a long
        command wraps at the terminal width and splits the echo across lines.
        """
        if not self._active or not self._channel:
            raise RuntimeError("Safe mode session is not active.")

        with self._lock:
            _, begin, end = _markers()
            self._channel.send(f':put "{begin}"; {command}; :put "{end}"\n')
            raw = self._read_until_marker(begin, end)
            return self._extract_output(raw, begin, end)

    def commit(self) -> str:
        """Send Ctrl+X again to exit Safe Mode and persist all changes.

        RouterOS keeps the changes only if the safe-mode session is *released*
        before the connection closes; closing the channel while the session
        still holds safe mode reverts everything.  So the channel is closed
        only after a fresh prompt, rendered after the Ctrl+X, shows that the
        console has left safe mode.  Without that evidence the session is left
        open and an error is returned: the changes are then still pending, and
        commit_safe_mode can be retried or rollback_safe_mode called.
        """
        with self._lock:
            if not self._active:
                return "Safe mode is not active. Nothing to commit."

            # Make sure the console is idle and really still in safe mode, so
            # the Ctrl+X below cannot toggle safe mode back *on*.
            in_safe_mode, before = self._probe_safe_mode()
            if in_safe_mode is None:
                return (
                    "Error: Could not read the safe-mode console state, so nothing "
                    "was committed. The session is still open and the changes are "
                    "still pending (NOT persisted). Retry commit_safe_mode, or call "
                    f"rollback_safe_mode. Console: {before[-300:]!r}"
                )
            if not in_safe_mode:
                # Safe mode ended before this commit (an earlier commit that
                # could not confirm, or another session taking it over).
                self._cleanup()
                return (
                    "Error: The console was no longer in safe mode when the commit "
                    "started, so this call did not commit anything. The changes may "
                    "already be persisted or may have been reverted — check the "
                    "configuration before relying on them."
                )

            self._drain()
            self._channel.send('\x18')
            response = self._read_until_release(timeout=15)
            released_msg = next(
                (line.strip() for line in response.split('\n') if _RELEASE_RE.search(line)),
                None,
            )

            in_safe_mode, after = self._probe_safe_mode()
            if in_safe_mode is not False:
                return (
                    "Error: RouterOS did not confirm that safe mode was released, so "
                    "the session was left open: the changes are still pending and "
                    "NOT persisted. Retry commit_safe_mode, or call rollback_safe_mode. "
                    f"Console after Ctrl+X: {(response + after)[-300:]!r}"
                )

            # Released.  Let the console settle before hanging up.
            self._drain(idle=1.0, timeout=5.0)
            self._cleanup()
            evidence = (
                f'RouterOS said "{released_msg}" and the prompt'
                if released_msg else "The prompt"
            )
            return (
                "Changes committed successfully. Safe mode DISABLED. "
                f"{evidence} no longer shows <SAFE>."
            )

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

    def _read(self, done, timeout: float) -> str:
        """Read the channel until ``done(text, idle_for)`` holds, or timeout.

        ``text`` is everything read so far, ANSI-stripped with newlines
        normalised; ``idle_for`` is how long the channel has been quiet.
        Terminal probes are answered on the way.
        """
        buf = ""
        answered: Dict[str, int] = {}
        last_data = time.monotonic()
        deadline = last_data + timeout
        while time.monotonic() < deadline:
            try:
                if self._channel.recv_ready():
                    buf += self._channel.recv(4096).decode('utf-8', errors='replace')
                    self._answer_terminal_queries(buf, answered)
                    last_data = time.monotonic()
            except Exception:
                break
            if done(_normalise(buf), time.monotonic() - last_data):
                break
            time.sleep(0.05)
        return _normalise(buf)

    def _drain(self, idle: float = 0.3, timeout: float = 3.0) -> str:
        """Consume output until the console has been quiet for ``idle`` seconds."""
        return self._read(lambda _text, idle_for: idle_for >= idle, timeout)

    def _read_until_marker(
        self, begin: str, end: str, timeout: float = 30.0, then_prompt: bool = False
    ) -> str:
        """Read until the END marker is printed on its own line.

        A command that fails never prints END: a parse error stops the whole
        line (so BEGIN is missing too) and a runtime error ends the script.
        In both cases the console prints the error and a fresh prompt, which
        ends the read early instead of sitting out the timeout.  With
        ``then_prompt`` the read also waits (briefly) for the prompt that
        follows END, which shows the console state after the command.
        """
        begin_re, end_re = _standalone(begin), _standalone(end)
        end_seen: Dict[str, float] = {}

        def done(text: str, _idle_for: float) -> bool:
            end_m = end_re.search(text)
            if end_m:
                if not then_prompt:
                    return True
                if _PROMPT_HEAD_RE.search(text, end_m.end()):
                    return True
                first = end_seen.setdefault("at", time.monotonic())
                return time.monotonic() - first > 5.0
            begin_m = begin_re.search(text)
            error = _CONSOLE_ERROR_RE.search(text, begin_m.end() if begin_m else 0)
            return bool(error) and bool(_PROMPT_HEAD_RE.search(text, error.end()))

        return self._read(done, timeout)

    def _read_until_release(self, timeout: float = 15.0) -> str:
        """Read after Ctrl+X until RouterOS reports the release, or settles.

        This only paces the commit; whether safe mode really ended is decided
        afterwards by _probe_safe_mode, never by what arrives here.
        """
        def done(text: str, idle_for: float) -> bool:
            if _RELEASE_RE.search(text):
                return True
            return bool(_PROMPT_HEAD_RE.search(text)) and idle_for >= 2.0

        return self._read(done, timeout)

    def _probe_safe_mode(self, timeout: float = 15.0) -> Tuple[Optional[bool], str]:
        """Ask the console whether it is in safe mode right now.

        Sends a line that only prints two markers and looks at the prompt the
        console renders around it.  The console handles input in order, so
        that prompt reflects every keystroke sent before it (a Ctrl+X
        included) and cannot be a stale redraw.  Returns (True, text) in safe
        mode, (False, text) out of it, and (None, text) when the console did
        not answer in a recognisable way.
        """
        _, begin, end = _markers()
        self._drain()
        self._channel.send(f':put "{begin}"; :put "{end}"\n')
        text = self._read_until_marker(begin, end, timeout=timeout, then_prompt=True)

        end_matches = list(_standalone(end).finditer(text))
        if not end_matches:
            return None, text
        last_end = end_matches[-1]
        # The prompt printed after END is the newest; fall back to the echo
        # line, which carries the prompt in front of the typed command.
        prompts = [
            line for line in text[last_end.end():].split('\n')
            if _PROMPT_HEAD_RE.search(line)
        ] or [
            line for line in text[:last_end.start()].split('\n')
            if end in line and _PROMPT_HEAD_RE.search(line)
        ]
        if not prompts:
            return None, text
        return '<SAFE>' in prompts[-1], text

    def _extract_output(self, raw: str, begin: str, end: str) -> str:
        """Return what the command printed between the BEGIN and END markers.

        Without an END marker the command failed at runtime: the output is
        what it printed before the next prompt (the RouterOS error message).
        Without a BEGIN marker nothing ran (a parse error): the output is the
        console's error line.  No marker and no error means no answer at all.
        """
        text = _normalise(raw)
        begin_m = _standalone(begin).search(text)
        if begin_m is None:
            errors = [
                line.strip() for line in text.split('\n')
                if _CONSOLE_ERROR_RE.search(line) and begin not in line
            ]
            if errors:
                return '\n'.join(errors)
            raise RuntimeError(
                "No response from the safe-mode console within the timeout. "
                f"Got: {text[-300:]!r}"
            )

        end_m = _standalone(end).search(text, begin_m.end())
        body = text[begin_m.end():end_m.start() if end_m else len(text)]

        result_lines: list[str] = []
        for line in body.split('\n'):
            stripped = line.strip()
            if _PROMPT_RE.match(stripped) or _PROMPT_NOISE_RE.match(stripped):
                if end_m is None:
                    break           # the prompt after a failed command
                continue            # a redraw in the middle of the output
            if end_m is None and _PROMPT_HEAD_RE.search(stripped) and end in stripped:
                break
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


def forget_safe_mode_manager(title: str) -> None:
    """Drop the cached manager after a device leaves the inventory.

    Re-enrolling the same title must not inherit the old router's session;
    the caller refuses removal while that session is active, so nothing here
    still holds an open shell.
    """
    key = str(title).strip().casefold()
    with _manager_lock:
        _managers.pop(key, None)

