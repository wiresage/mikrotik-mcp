"""Read-only views over `/system`: what the board is, how it is doing, and
which RouterOS it runs.

These answer the questions an export header only hints at — model, serial and
version — plus the ones it cannot carry at all: uptime, CPU and memory load,
board voltage and temperature, and whether a newer release is available.
"""

from typing import Optional

from mcp.server.mcpserver import Context

from ..app import mcp, READ, annotate
from ..connector import execute_mikrotik_command


async def _print(
    ctx: Context,
    command: str,
    heading: str,
    empty_message: str,
    data_marker: str,
    device: Optional[str],
) -> str:
    """Run a settings-style `print` and return it verbatim under *heading*.

    Unlike the list prints, these return `key: value` blocks rather than rows,
    so the marker is a field name rather than a row field.
    """
    result = await execute_mikrotik_command(command, ctx, device=device)
    if not result or data_marker not in result:
        return empty_message
    return f"{heading}:\n\n{result}"


@mcp.tool(name="get_system_resource", annotations=annotate(READ, "System Resource"))
async def mikrotik_get_system_resource(ctx: Context, device: Optional[str] = None) -> str:
    """Reports uptime, RouterOS version, board name, architecture, CPU and memory.

    Notes:
        `free-memory` against `total-memory` and `cpu-load` are the two numbers
        worth reading before blaming the network for a slow device. On the
        low-power boards a single packet-sniffing tool can saturate the CPU on
        its own.
    """
    await ctx.info("Reading system resource")
    return await _print(
        ctx, "/system resource print", "SYSTEM RESOURCE",
        "No system resource information returned.", "uptime", device,
    )


@mcp.tool(name="get_system_health", annotations=annotate(READ, "System Health"))
async def mikrotik_get_system_health(ctx: Context, device: Optional[str] = None) -> str:
    """Reports the board sensors: voltage, temperature, fan and PSU state.

    Notes:
        Many boards carry no sensors at all and legitimately report nothing.
        An empty answer here means "this model does not measure it", not "the
        reading failed".
    """
    await ctx.info("Reading system health")
    result = await execute_mikrotik_command("/system health print", ctx, device=device)
    if not result or not result.strip():
        return (
            "No health sensors reported. Many MikroTik boards carry none; "
            "this is not an error."
        )
    return f"SYSTEM HEALTH:\n\n{result}"


@mcp.tool(name="get_system_clock", annotations=annotate(READ, "System Clock"))
async def mikrotik_get_system_clock(ctx: Context, device: Optional[str] = None) -> str:
    """Reports the device clock, time zone and DST setting.

    Notes:
        Log timestamps are only as trustworthy as this. A device without a
        working time source dates its own evidence wrongly, which matters when
        correlating an incident across sites.
    """
    await ctx.info("Reading system clock")
    return await _print(
        ctx, "/system clock print", "SYSTEM CLOCK",
        "No clock information returned.", "time", device,
    )


@mcp.tool(name="get_system_routerboard", annotations=annotate(READ, "RouterBOARD Info"))
async def mikrotik_get_system_routerboard(ctx: Context, device: Optional[str] = None) -> str:
    """Reports the model, serial number and bootloader firmware revision.

    Notes:
        `current-firmware` against `upgrade-firmware` is the RouterBOOT
        bootloader, which is upgraded separately from RouterOS and is easy to
        leave behind after a package upgrade.
    """
    await ctx.info("Reading RouterBOARD information")
    return await _print(
        ctx, "/system routerboard print", "ROUTERBOARD",
        "No RouterBOARD information returned (not a RouterBOARD device).",
        "model", device,
    )


@mcp.tool(name="list_system_packages", annotations=annotate(READ, "List Packages"))
async def mikrotik_list_system_packages(ctx: Context, device: Optional[str] = None) -> str:
    """Lists the installed RouterOS packages and which are disabled."""
    await ctx.info("Listing system packages")
    result = await execute_mikrotik_command("/system package print", ctx, device=device)
    if not result or "name" not in result.lower():
        return "No packages returned."
    return f"SYSTEM PACKAGES:\n\n{result}"


@mcp.tool(name="get_system_package_update", annotations=annotate(READ, "Check for Updates"))
async def mikrotik_get_system_package_update(ctx: Context, device: Optional[str] = None) -> str:
    """Reports the installed RouterOS version against the latest on its channel.

    Notes:
        This reads the stored result of the last check; it does not contact
        MikroTik. `latest-version` can therefore be stale or empty on a device
        that has never checked or cannot reach the update server.
    """
    await ctx.info("Reading package update status")
    return await _print(
        ctx, "/system package update print", "PACKAGE UPDATE",
        "No update information returned.", "installed-version", device,
    )
