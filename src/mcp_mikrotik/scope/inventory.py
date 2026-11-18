import os
import re
import tempfile
import threading
from typing import Annotated, List, Optional

import yaml
from mcp.server.mcpserver import Context
from pydantic import Field

from .. import config
from ..app import mcp, READ, WRITE, annotate
from ..config import DeviceConfig
from ..connector import execute_mikrotik_command
from ..inventory import get_inventory


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
        return "No MikroTik devices are configured."

    lines = [f"MIKROTIK DEVICES ({len(devices)}):", ""]
    for d in devices:
        parts = [f"  title: {d['title']}", f"host: {d['host']}:{d['port']}", f"user: {d['username']}"]
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


def _persist_device(device: DeviceConfig, path: str) -> None:
    """Append *device* to the dynamic inventory file.

    Read-modify-write rather than a text append, so the file stays valid YAML
    if a human is editing it, and written through a temporary file so a failure
    cannot truncate the credentials the file already holds.
    """
    path = os.path.expanduser(path)
    entries: List[dict] = []
    if os.path.exists(path):
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

    # Empty defaults are dropped: each of them is the field's default again
    # when the file is read back, and the entry stays readable.
    entries.append(
        {
            key: value
            for key, value in device.model_dump().items()
            if value not in (None, "", [], False)
        }
    )

    temporary = None
    try:
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


async def mikrotik_device_add(
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
            "Runtime enrollment needs MIKROTIK_DYNAMIC_INVENTORY_FILE (or "
            "--dynamic-inventory-file) so enrolled devices survive a restart."
        )

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
        _persist_device(device, state_file)
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


# Registered only when runtime enrollment is enabled: with the flag off the
# tool must be absent from `tools/list`, not merely refuse to run.
if config.mikrotik_config.allow_dynamic_devices:
    mcp.tool(name="device_add", annotations=annotate(WRITE, "Enroll Device"))(
        mikrotik_device_add
    )
