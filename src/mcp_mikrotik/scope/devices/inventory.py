import os
import re
import tempfile
import threading
from typing import Annotated, List, Optional

import yaml
from mcp.server.mcpserver import Context
from pydantic import Field

from ... import config
from ...app import mcp, DESTRUCTIVE, READ, WRITE, annotate
from ...config import DeviceConfig
from ...connector import execute_mikrotik_command
from ...inventory import get_inventory
from ...safe_mode import forget_safe_mode_manager, get_safe_mode_manager


def _dynamic_available() -> bool:
    """Whether the agent may enroll and remove devices right now."""
    cfg = config.mikrotik_config
    return cfg.allow_dynamic_devices and not cfg.read_only


@mcp.tool(name="list_devices", annotations=annotate(READ, "List Devices"))
async def mikrotik_list_devices(ctx: Context) -> str:
    """Lists the MikroTik devices this server manages.

    Use this to discover which devices are available and what their titles are.
    Every other tool takes an optional `device` argument that must be one of the
    titles returned here. When only one device is configured, `device` may be
    omitted and that device is used automatically.

    Credentials are never returned.
    """
    await ctx.info("Listing inventory devices")

    inventory = get_inventory()
    devices = inventory.describe()

    if not devices:
        if _dynamic_available():
            return (
                "No MikroTik devices are configured. Ask the user for the "
                "device address and SSH credentials, then enroll it with "
                "add_device."
            )
        return (
            "No MikroTik devices are configured. Set MIKROTIK_INVENTORY "
            "(or the single-device MIKROTIK_HOST settings)."
        )

    lines = [f"MIKROTIK DEVICES ({len(devices)}):", ""]
    for d in devices:
        parts = [
            f"  title: {d['title']}",
            f"host: {d['host']}:{d['port']}",
            f"user: {d['username']}",
            f"source: {d['source']}",
        ]
        if d.get("region"):
            parts.append(f"region: {d['region']}")
        if d.get("tags"):
            parts.append(f"tags: {', '.join(d['tags'])}")
        lines.append(" | ".join(parts))

    if len(devices) == 1:
        lines.append("")
        lines.append(
            "Only one device is configured, so the `device` argument can be omitted."
        )
    else:
        lines.append("")
        lines.append(
            "Multiple devices are configured — pass the chosen title as the "
            "`device` argument of each tool."
        )

    if _dynamic_available():
        lines.append("")
        lines.append(
            "Enroll another device with add_device; remove one you enrolled "
            "with remove_device."
        )

    return "\n".join(lines)


# An IPv4 literal or a chain of DNS labels: no spaces or slashes, no colon
# (so no bare IPv6), no hyphen at either end of a label, label at most 63
# characters. Everything here is model-controlled input.
_HOST_RE = re.compile(
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)*"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\Z"
)

# Enrollments are a read-modify-write of one file, so they serialise within
# this process. The unique temp name also keeps a second process from
# overwriting the bytes this one is writing.
# shortcut: two processes sharing the file can still both read the old list and
# one enrollment is lost; add file locking if a fleet ever needs that.
_persist_lock = threading.Lock()


def _read_state(path: str) -> List[dict]:
    """Read the runtime state file; a missing file is an empty list."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            entries = yaml.safe_load(fh.read()) or []
    except OSError as exc:
        raise ValueError(
            f"Cannot read dynamic inventory file {path!r}: {exc.strerror or exc}"
        ) from exc
    except yaml.YAMLError as exc:
        # Position only: this file holds passwords, and PyYAML echoes the
        # offending line in str(exc).
        mark = getattr(exc, "problem_mark", None)
        where = (
            f" (line {mark.line + 1}, column {mark.column + 1})"
            if mark else ""
        )
        raise ValueError(
            f"Dynamic inventory file {path!r} is not valid YAML{where}"
        ) from exc
    if not isinstance(entries, list):
        raise ValueError(
            f"Dynamic inventory file {path!r} must hold a list of devices."
        )
    return entries


def _write_state(entries: List[dict], path: str) -> None:
    """Replace the state file atomically, owner-only."""
    temporary = None
    try:
        # A missing parent is created 0700, so a credential never sits in a
        # directory others can read.
        os.makedirs(os.path.dirname(path) or ".", mode=0o700, exist_ok=True)
        # mkstemp creates the file 0600 whatever the umask, so a credential is
        # never in a world-readable file even briefly, and its unique name keeps
        # a second process off the bytes this one is writing.
        fd, temporary = tempfile.mkstemp(
            prefix=f".{os.path.basename(path)}.", suffix=".tmp",
            dir=os.path.dirname(path) or ".",
        )
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("# holds credentials — chmod 600\n")
            yaml.safe_dump(entries, fh, sort_keys=False)
        os.replace(temporary, path)
    except OSError as exc:
        if temporary:
            try:
                os.unlink(temporary)
            except OSError:
                pass
        raise ValueError(
            f"Cannot write dynamic inventory file {path!r}: {exc.strerror or exc}"
        ) from exc


def _persist_device(device: DeviceConfig, path: str) -> None:
    """Append *device* to the dynamic inventory file.

    Read-modify-write rather than a text append, so the file stays valid YAML
    if a human is editing it, and written through a temporary file so a failure
    cannot truncate the credentials the file already holds.
    """
    entries = _read_state(path)
    # Empty defaults are dropped: each of them is the field's default again
    # when the file is read back, and the entry stays readable.
    entries.append(
        {
            key: value
            for key, value in device.model_dump().items()
            if value not in (None, "", [], False)
        }
    )
    _write_state(entries, path)


def _forget_persisted(title: str, path: str) -> None:
    """Drop *title* from the dynamic inventory file."""
    entries = _read_state(path)
    kept = [
        entry for entry in entries
        if not (
            isinstance(entry, dict)
            and str(entry.get("title", "")).casefold() == title.casefold()
        )
    ]
    if len(kept) == len(entries):
        raise ValueError(
            f"Device {title!r} is not in the dynamic inventory file {path!r} — "
            "it may have been edited outside the server."
        )
    _write_state(kept, path)


async def mikrotik_add_device(
    ctx: Context,
    title: str,
    host: str,
    port: Annotated[int, Field(ge=1, le=65535)] = 22,
    username: str = "admin",
    password: Optional[str] = None,
    key_filename: Optional[str] = None,
    region: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> str:
    """Enrolls a new MikroTik device into the inventory so later tool calls can target it by title."""
    await ctx.info(f"Enrolling device {title!r} at {host}")

    state_file = config.mikrotik_config.dynamic_inventory_file
    if not state_file:
        raise ValueError(
            "Runtime enrollment needs a state file; set "
            "MIKROTIK_DYNAMIC_INVENTORY_FILE."
        )
    path = os.path.expanduser(state_file)

    device = DeviceConfig(
        title=title,
        host=host.strip(),
        port=port,
        username=username,
        password=password or "",
        key_filename=key_filename,
        region=region,
        tags=tags or [],
    )
    if not _HOST_RE.fullmatch(device.host):
        raise ValueError(
            f"Invalid host {device.host!r}: expected an IPv4 address or a hostname."
        )

    inventory = get_inventory()
    with _persist_lock:
        # Uniqueness is settled before the file gains an entry: a refusal
        # after the write would leave a state file the next start rejects.
        if any(
            existing.title.casefold() == device.title.casefold()
            for existing in inventory.all_devices()
        ):
            raise ValueError(
                f"Duplicate device title {device.title!r} in inventory — "
                "titles must be unique."
            )
        _persist_device(device, path)
        inventory.add(device)

    result = await execute_mikrotik_command(
        "/system identity print", ctx, device=device.title
    )
    if result.startswith("Error"):
        return (
            f"Enrolled {device.title} ({device.host}:{device.port}), but the "
            f"device is unreachable.\n\n{result}\n\n"
            "The enrollment is saved and will be reloaded on the next start."
        )
    return f"Enrolled {device.title} ({device.host}:{device.port}).\n\n{result}"


async def mikrotik_remove_device(ctx: Context, title: str) -> str:
    """Removes a device enrolled at runtime; devices from the inventory file or settings cannot be removed here."""
    await ctx.info(f"Removing device {title!r}")

    state_file = config.mikrotik_config.dynamic_inventory_file
    if not state_file:
        raise ValueError(
            "Runtime removal needs a state file; set "
            "MIKROTIK_DYNAMIC_INVENTORY_FILE."
        )

    inventory = get_inventory()
    with _persist_lock:
        # A live safe-mode shell still points at this host. Removing the
        # device would strand that session, and re-adding the title would
        # route its commands through the old router.
        if get_safe_mode_manager(title).is_active:
            raise ValueError(
                f"Safe mode is active on {title!r}; use commit_safe_mode or "
                "rollback_safe_mode before removing the device."
            )

        # Removing from memory first means an unknown or static title is
        # refused before the file is touched. A failed write puts it back.
        device = inventory.remove(title)
        try:
            _forget_persisted(device.title, os.path.expanduser(state_file))
        except Exception:
            inventory.add(device)
            raise
        forget_safe_mode_manager(device.title)

    return f"Removed {device.title} ({device.host}:{device.port})."


# Registered only when runtime management is enabled: with the flag off the
# tools must be absent from `tools/list`, not merely refuse to run.
if config.mikrotik_config.allow_dynamic_devices:
    mcp.tool(name="add_device", annotations=annotate(WRITE, "Add Device"))(
        mikrotik_add_device
    )
    mcp.tool(name="remove_device", annotations=annotate(DESTRUCTIVE, "Remove Device"))(
        mikrotik_remove_device
    )
