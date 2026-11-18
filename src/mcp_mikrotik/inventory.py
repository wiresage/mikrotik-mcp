"""Device inventory for multi-device (fleet) support — issue #44.

The :class:`Inventory` owns the list of MikroTik devices and knows how to reach
each one.  Tools pass a device ``title`` down to the connector, which asks the
inventory to open a connection to the matching device and runs the command over
it.

Connections are **never pooled or shared**.  Every call gets a brand-new
``MikroTikSSHClient`` that is closed as soon as the command finishes, so
concurrent MCP sessions are fully isolated from one another: one session
disconnecting, timing out or failing to authenticate cannot disturb a command
another session is running against the same device.
"""

import json
import logging
import os
import threading
from contextlib import contextmanager
from typing import Dict, Iterator, List, Optional

import yaml
from pydantic import ValidationError

from . import config
from .config import DeviceConfig
from .mikrotik_ssh_client import MikroTikSSHClient

logger = logging.getLogger(__name__)


class DeviceNotFoundError(LookupError):
    """Raised when a requested device title cannot be resolved."""


class Inventory:
    """Holds the device definitions, keyed by title.

    The map is not immutable — :meth:`add` enrols devices at runtime — but the
    inventory still holds no connection state, so a single instance is safe to
    share across sessions and threads.
    """

    # Class-level: an instance's own dict is asserted to hold nothing but the
    # device map, so the lock that guards it cannot live in that dict.
    _add_lock = threading.Lock()

    def __init__(self, devices: List[DeviceConfig]) -> None:
        self._devices: Dict[str, DeviceConfig] = {}

        for device in devices:
            key = device.title.casefold()
            if key in self._devices:
                raise ValueError(
                    f"Duplicate device title {device.title!r} in inventory — "
                    "titles must be unique."
                )
            self._devices[key] = device

    def add(self, device: DeviceConfig) -> None:
        """Insert a device discovered at runtime.

        Titles stay unique case-insensitively, with the same error the
        constructor raises, so a title already in the inventory is refused
        rather than shadowed.
        """
        key = device.title.casefold()
        with self._add_lock:
            if key in self._devices:
                raise ValueError(
                    f"Duplicate device title {device.title!r} in inventory — "
                    "titles must be unique."
                )
            # Copy-on-write: a reader iterating the previous dict keeps walking
            # an object nobody mutates, so `list_devices` cannot fail with
            # "dictionary changed size during iteration" while `device_add` runs.
            self._devices = {**self._devices, key: device}

    # ── Introspection ──────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._devices)

    @property
    def titles(self) -> List[str]:
        return [d.title for d in self._devices.values()]

    def all_devices(self) -> List[DeviceConfig]:
        return list(self._devices.values())

    def describe(self) -> List[dict]:
        """Device metadata for the LLM. Never includes credentials."""
        return [
            {
                "title": d.title,
                "host": d.host,
                "port": d.port,
                "username": d.username,
                "tags": d.tags,
                "region": d.region,
            }
            for d in self._devices.values()
        ]

    # ── Resolution ─────────────────────────────────────────────────────────

    def resolve(self, title: Optional[str] = None) -> DeviceConfig:
        """Resolve a device title to its definition.

        With a single-device inventory the title may be omitted.  With more
        than one device the title is required, and an unknown title raises
        :class:`DeviceNotFoundError` listing the valid titles so the caller can
        correct itself in one step.
        """
        if not self._devices:
            raise DeviceNotFoundError(
                "No MikroTik devices are configured. Set MIKROTIK_INVENTORY "
                "(or the single-device MIKROTIK_HOST settings)."
            )

        if title is None or not str(title).strip():
            if len(self._devices) == 1:
                return next(iter(self._devices.values()))
            raise DeviceNotFoundError(
                "This server manages multiple MikroTik devices, so a device "
                f"must be specified. Available devices: {', '.join(self.titles)}."
            )

        device = self._devices.get(str(title).strip().casefold())
        if device is None:
            raise DeviceNotFoundError(
                f"Unknown device {title!r}. "
                f"Available devices: {', '.join(self.titles)}."
            )
        return device

    # ── SSH clients ────────────────────────────────────────────────────────

    def connect(
        self, title: Optional[str] = None, terminal_width: Optional[int] = None
    ) -> MikroTikSSHClient:
        """Open and return a **new** SSH connection to the resolved device.

        Connections are deliberately not pooled.  Sharing one client between
        concurrent MCP sessions would make them share a fate — a disconnect,
        timeout or dropped transport in one session would break a command
        another session was running — so every caller gets its own.

        ``terminal_width`` appends RouterOS's console login option
        ``+<n>w`` to the user name, so tables are laid out for ``n`` columns
        instead of 80.

        The caller owns the returned client and must close it.  Prefer
        :meth:`session`, which closes it automatically.
        """
        device = self.resolve(title)
        username = device.username
        if terminal_width:
            if not 40 <= int(terminal_width) <= 1000:
                raise ValueError("terminal_width must be between 40 and 1000")
            username = f"{username}+{int(terminal_width)}w"

        client = MikroTikSSHClient(
            host=device.host,
            username=username,
            password=device.password,
            key_filename=device.key_filename,
            port=device.port,
            command_timeout=config.mikrotik_config.command_timeout,
            allow_ssh_agent=device.allow_ssh_agent,
            ssh_agent_key=device.ssh_agent_key,
        )
        if not client.connect():
            raise ConnectionError(
                f"Failed to connect to MikroTik device '{device.title}' "
                f"({device.host}:{device.port})"
            )
        logger.debug(f"Opened SSH connection to '{device.title}'")
        return client

    @contextmanager
    def session(
        self, title: Optional[str] = None, terminal_width: Optional[int] = None
    ) -> Iterator[MikroTikSSHClient]:
        """Yield a fresh SSH connection to the device, closed on exit.

        The connection is closed even if the command raises, so a failing
        command cannot leak a session on the router.
        """
        client = self.connect(title, terminal_width=terminal_width)
        try:
            yield client
        finally:
            try:
                client.disconnect()
            except Exception:
                logger.debug("Error closing SSH connection", exc_info=True)


# ---------------------------------------------------------------------------
# Module-level inventory
# ---------------------------------------------------------------------------

_inventory: Optional[Inventory] = None
_inventory_lock = threading.Lock()


def _validate_entries(raw, source: str) -> List[DeviceConfig]:
    """Turn parsed YAML/JSON into DeviceConfigs with credential-safe errors.

    A malformed entry must fail with the entry's position and the offending
    field names only — the inventory holds passwords, and anything raised here
    can end up verbatim in a tool result or a log line.
    """
    if isinstance(raw, dict):
        raw = raw.get("inventory", [raw])
    if not isinstance(raw, list):
        raise ValueError(
            f"{source}: the inventory must be a list of devices "
            f"(got {type(raw).__name__})"
        )

    devices: List[DeviceConfig] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(
                f"{source}: device #{index} must be a mapping "
                f"(got {type(item).__name__})"
            )
        try:
            devices.append(DeviceConfig(**item))
        except ValidationError as exc:
            problems = "; ".join(
                f"{'.'.join(str(p) for p in err['loc']) or 'entry'}: {err['msg']}"
                for err in exc.errors()
            )
            label = item.get("title") or f"#{index}"
            raise ValueError(
                f"{source}: device {label!r} is invalid — {problems}"
            ) from None
    return devices


def _read_inventory_file(path: str) -> List[DeviceConfig]:
    """Read one inventory file into validated devices."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        raise ValueError(
            f"Cannot read inventory file {path!r}: {exc.strerror or exc}"
        ) from exc
    # JSON first: PyYAML's scanner rejects tab whitespace, which is legal
    # in JSON, so yaml.safe_load alone would break previously working
    # tab-indented inventory.json files.
    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        try:
            raw = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            where = (
                f" (line {mark.line + 1}, column {mark.column + 1})"
                if mark else ""
            )
            raise ValueError(
                f"Inventory file {path!r} is not valid YAML{where}"
            ) from exc
    return _validate_entries(raw, source=path)


def _merge_dynamic(
    devices: List[DeviceConfig], extra: List[DeviceConfig], source: str
) -> List[DeviceConfig]:
    """Append runtime-enrolled devices, refusing a title already taken."""
    known = {device.title.casefold() for device in devices}
    for device in extra:
        if device.title.casefold() in known:
            raise ValueError(
                f"Duplicate device title {device.title!r} in inventory — "
                f"titles must be unique, and {source} repeats a title that is "
                "already configured."
            )
        known.add(device.title.casefold())
        devices.append(device)
    return devices


def _load_devices() -> List[DeviceConfig]:
    """Build the device list from configuration.

    Precedence: inline ``MIKROTIK_INVENTORY`` (YAML, or its JSON subset) >
    ``MIKROTIK_INVENTORY_FILE`` (a YAML file) > the flat single-device
    settings.  The last case keeps every existing single-device deployment
    working with no configuration change.

    The runtime-enrolled ``MIKROTIK_DYNAMIC_INVENTORY_FILE`` is merged on top
    of whichever of those won, so a fleet survives a restart.
    """
    cfg = config.mikrotik_config

    if cfg.inventory:
        devices = list(cfg.inventory)
    elif cfg.inventory_file:
        devices = _read_inventory_file(os.path.expanduser(cfg.inventory_file))
    else:
        # Backwards-compatible single device.
        devices = [
            DeviceConfig(
                title=cfg.host,
                host=cfg.host,
                port=cfg.port,
                username=cfg.username,
                password=cfg.password,
                key_filename=cfg.key_filename,
                allow_ssh_agent=cfg.allow_ssh_agent,
                ssh_agent_key=cfg.ssh_agent_key,
            )
        ]

    if cfg.dynamic_inventory_file:
        path = os.path.expanduser(cfg.dynamic_inventory_file)
        # Absent until the first enrollment creates it.
        if os.path.exists(path):
            devices = _merge_dynamic(devices, _read_inventory_file(path), path)

    return devices


def get_inventory() -> Inventory:
    global _inventory
    if _inventory is None:
        with _inventory_lock:
            if _inventory is None:
                _inventory = Inventory(_load_devices())
    return _inventory


def reset_inventory() -> None:
    """Drop the cached inventory (used by tests and after config reloads)."""
    global _inventory
    with _inventory_lock:
        _inventory = None
