"""Tools for managing RouterOS Network Time Protocol (NTP/SNTP) client, server, and clock synchronization."""

import re
from typing import Annotated, Literal, Optional
from pydantic import Field

from mcp.server.mcpserver import Context

from ..app import mcp, READ, WRITE_IDEMPOTENT, DESTRUCTIVE, annotate
from ..connector import execute_mikrotik_command
from ._quoting import ros_quoted
from ._selectors import has_item_rows

_DOMAIN_OR_IP_RE = re.compile(r"^[a-zA-Z0-9_.\-]+$")
_TZ_RE = re.compile(r"^[a-zA-Z0-9_/.\-+]+$")
_VRF_RE = re.compile(r"^[a-zA-Z0-9_.\-]+$")


# ---------------------------------------------------------------------------
# NTP Status & Clock Diagnostics
# ---------------------------------------------------------------------------

@mcp.tool(name="get_ntp_status", annotations=annotate(READ, "Get NTP Status"))
async def mikrotik_get_ntp_status(
    ctx: Context,
    device: Optional[str] = None,
) -> str:
    """Retrieves current NTP client synchronization status, active peer, offset, and frequency drift."""
    await ctx.info("Retrieving NTP synchronization status")

    cmd = "/system ntp client print"
    result = await execute_mikrotik_command(cmd, ctx, device=device)
    if not result:
        return "Failed to retrieve NTP client status."

    return f"NTP CLIENT STATUS:\n\n{result}"


@mcp.tool(name="check_clock_sync", annotations=annotate(READ, "Check Clock Sync"))
async def mikrotik_check_clock_sync(
    ctx: Context,
    device: Optional[str] = None,
) -> str:
    """Performs a healthcheck on router clock synchronization and reports current time, timezone, and offset."""
    await ctx.info("Checking system clock synchronization health")

    ntp_res = await execute_mikrotik_command("/system ntp client print", ctx, device=device)
    clock_res = await execute_mikrotik_command("/system clock print", ctx, device=device)

    # Parse NTP state
    is_synced = "status: synchronized" in ntp_res.lower()
    is_enabled = "enabled: yes" in ntp_res.lower()

    synced_server = "unknown"
    offset = "unknown"
    stratum = "unknown"
    for line in ntp_res.splitlines():
        line_clean = line.strip()
        if line_clean.startswith("synced-server:"):
            synced_server = line_clean.split(":", 1)[1].strip()
        elif line_clean.startswith("system-offset:"):
            offset = line_clean.split(":", 1)[1].strip()
        elif line_clean.startswith("synced-stratum:"):
            stratum = line_clean.split(":", 1)[1].strip()

    # Parse Clock state
    cur_time = "unknown"
    cur_date = "unknown"
    tz = "unknown"
    for line in clock_res.splitlines():
        line_clean = line.strip()
        if line_clean.startswith("time:"):
            cur_time = line_clean.split(":", 1)[1].strip()
        elif line_clean.startswith("date:"):
            cur_date = line_clean.split(":", 1)[1].strip()
        elif line_clean.startswith("time-zone-name:"):
            tz = line_clean.split(":", 1)[1].strip()

    if is_synced:
        summary = (
            f"[SYNCED] Router clock is accurately synchronized via NTP.\n"
            f"- Date & Time: {cur_date} {cur_time} ({tz})\n"
            f"- Synced Peer: {synced_server} (Stratum {stratum})\n"
            f"- System Offset: {offset}"
        )
    elif not is_enabled:
        summary = (
            f"[DISABLED] NTP client is currently disabled on this router.\n"
            f"- Local Time: {cur_date} {cur_time} ({tz})"
        )
    else:
        summary = (
            f"[UNSYNCHRONIZED] NTP client is enabled but not synchronized.\n"
            f"- Local Time: {cur_date} {cur_time} ({tz})\n"
            f"- NTP Raw Status:\n{ntp_res.strip()}"
        )

    return summary


# ---------------------------------------------------------------------------
# NTP Client Configuration & Servers
# ---------------------------------------------------------------------------

@mcp.tool(name="get_ntp_client_settings", annotations=annotate(READ, "Get NTP Client Settings"))
async def mikrotik_get_ntp_client_settings(
    ctx: Context,
    device: Optional[str] = None,
) -> str:
    """Retrieves NTP client configuration and configured upstream NTP servers."""
    await ctx.info("Retrieving NTP client configuration and server list")

    client_res = await execute_mikrotik_command("/system ntp client print", ctx, device=device)
    servers_res = await execute_mikrotik_command("/system ntp client servers print detail", ctx, device=device)

    out = ["NTP CLIENT CONFIGURATION:\n", client_res.strip(), "\nCONFIGURED NTP SERVERS:\n"]
    if has_item_rows(servers_res):
        out.append(servers_res.strip())
    else:
        out.append("No upstream NTP servers configured.")

    return "\n".join(out)


@mcp.tool(name="update_ntp_client", annotations=annotate(WRITE_IDEMPOTENT, "Update NTP Client"))
async def mikrotik_update_ntp_client(
    ctx: Context,
    enabled: Optional[bool] = None,
    mode: Optional[Literal["unicast", "broadcast", "multicast"]] = None,
    vrf: Optional[str] = None,
    device: Optional[str] = None,
) -> str:
    """Configures NTP client operation mode, administrative state, and VRF binding."""
    await ctx.info("Updating NTP client settings")

    params = []
    if enabled is not None:
        params.append(f"enabled={'yes' if enabled else 'no'}")
    if mode is not None:
        params.append(f"mode={mode}")
    if vrf is not None:
        if not _VRF_RE.fullmatch(vrf):
            return f"Invalid VRF name: '{vrf}'"
        params.append(f"vrf={vrf}")

    if not params:
        return "No NTP client settings provided to update."

    cmd = f"/system ntp client set {' '.join(params)}"
    result = await execute_mikrotik_command(cmd, ctx, device=device)
    if result.strip():
        return f"Error updating NTP client: {result.strip()}"

    return "NTP client updated successfully."


@mcp.tool(name="add_ntp_server", annotations=annotate(WRITE_IDEMPOTENT, "Add NTP Server"))
async def mikrotik_add_ntp_server(
    ctx: Context,
    address: str,
    iburst: bool = True,
    min_poll: Optional[Annotated[int, Field(ge=4, le=17)]] = None,
    max_poll: Optional[Annotated[int, Field(ge=4, le=17)]] = None,
    device: Optional[str] = None,
) -> str:
    """Adds an upstream NTP server address with optional polling intervals and iburst acceleration."""
    await ctx.info(f"Adding NTP upstream server: address='{address}'")

    address = address.strip()
    if not _DOMAIN_OR_IP_RE.fullmatch(address):
        return f"Invalid NTP server address or hostname: '{address}'"

    # Check if already present
    check_cmd = f'/system ntp client servers print where address="{ros_quoted(address)}"'
    check_res = await execute_mikrotik_command(check_cmd, ctx, device=device)
    if has_item_rows(check_res):
        return f"NTP server '{address}' is already configured."

    params = [f'address="{ros_quoted(address)}"', f"iburst={'yes' if iburst else 'no'}"]
    if min_poll is not None:
        params.append(f"min-poll={min_poll}")
    if max_poll is not None:
        params.append(f"max-poll={max_poll}")

    cmd = f"/system ntp client servers add {' '.join(params)}"
    result = await execute_mikrotik_command(cmd, ctx, device=device)
    if result.strip():
        return f"Error adding NTP server: {result.strip()}"

    return f"NTP server '{address}' added successfully."


@mcp.tool(name="remove_ntp_server", annotations=annotate(DESTRUCTIVE, "Remove NTP Server"))
async def mikrotik_remove_ntp_server(
    ctx: Context,
    address: str,
    device: Optional[str] = None,
) -> str:
    """Removes an upstream NTP server by its hostname or IP address."""
    await ctx.info(f"Removing NTP server: address='{address}'")

    address = address.strip()
    if not _DOMAIN_OR_IP_RE.fullmatch(address):
        return f"Invalid NTP server address or hostname: '{address}'"

    cmd = f'/system ntp client servers remove [find address="{ros_quoted(address)}"]'
    result = await execute_mikrotik_command(cmd, ctx, device=device)
    if result.strip():
        return f"Error removing NTP server: {result.strip()}"

    return f"NTP server '{address}' removed successfully."


# ---------------------------------------------------------------------------
# NTP Server & System Clock
# ---------------------------------------------------------------------------

@mcp.tool(name="get_ntp_server_settings", annotations=annotate(READ, "Get NTP Server Settings"))
async def mikrotik_get_ntp_server_settings(
    ctx: Context,
    device: Optional[str] = None,
) -> str:
    """Retrieves local NTP server settings for serving time to LAN clients."""
    await ctx.info("Retrieving local NTP server settings")

    cmd = "/system ntp server print"
    result = await execute_mikrotik_command(cmd, ctx, device=device)
    if not result:
        return "Failed to retrieve NTP server settings."

    return f"NTP SERVER SETTINGS:\n\n{result}"


@mcp.tool(name="update_ntp_server", annotations=annotate(WRITE_IDEMPOTENT, "Update NTP Server"))
async def mikrotik_update_ntp_server(
    ctx: Context,
    enabled: Optional[bool] = None,
    broadcast: Optional[bool] = None,
    multicast: Optional[bool] = None,
    manycast: Optional[bool] = None,
    use_local_clock: Optional[bool] = None,
    local_clock_stratum: Optional[Annotated[int, Field(ge=1, le=15)]] = None,
    device: Optional[str] = None,
) -> str:
    """Configures the local NTP server daemon to distribute time across the network."""
    await ctx.info("Updating local NTP server settings")

    params = []
    if enabled is not None:
        params.append(f"enabled={'yes' if enabled else 'no'}")
    if broadcast is not None:
        params.append(f"broadcast={'yes' if broadcast else 'no'}")
    if multicast is not None:
        params.append(f"multicast={'yes' if multicast else 'no'}")
    if manycast is not None:
        params.append(f"manycast={'yes' if manycast else 'no'}")
    if use_local_clock is not None:
        params.append(f"use-local-clock={'yes' if use_local_clock else 'no'}")
    if local_clock_stratum is not None:
        params.append(f"local-clock-stratum={local_clock_stratum}")

    if not params:
        return "No NTP server settings provided to update."

    cmd = f"/system ntp server set {' '.join(params)}"
    result = await execute_mikrotik_command(cmd, ctx, device=device)
    if result.strip():
        return f"Error updating NTP server: {result.strip()}"

    return "NTP server settings updated successfully."


@mcp.tool(name="update_system_clock", annotations=annotate(WRITE_IDEMPOTENT, "Update System Clock"))
async def mikrotik_update_system_clock(
    ctx: Context,
    time_zone_name: Optional[str] = None,
    time_zone_autodetect: Optional[bool] = None,
    device: Optional[str] = None,
) -> str:
    """Configures router timezone name and automatic timezone detection."""
    await ctx.info("Updating system clock timezone settings")

    params = []
    if time_zone_name is not None:
        if not _TZ_RE.fullmatch(time_zone_name):
            return f"Invalid timezone name: '{time_zone_name}'"
        params.append(f'time-zone-name="{ros_quoted(time_zone_name)}"')

    if time_zone_autodetect is not None:
        params.append(f"time-zone-autodetect={'yes' if time_zone_autodetect else 'no'}")

    if not params:
        return "No clock settings provided to update."

    cmd = f"/system clock set {' '.join(params)}"
    result = await execute_mikrotik_command(cmd, ctx, device=device)
    if result.strip():
        return f"Error updating system clock: {result.strip()}"

    return "System clock settings updated successfully."
