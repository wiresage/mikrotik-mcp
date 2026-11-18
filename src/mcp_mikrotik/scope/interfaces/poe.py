from typing import Optional
from ...connector import execute_mikrotik_command
from mcp.server.mcpserver import Context
from ...app import mcp, READ, annotate


@mcp.tool(name="get_poe_monitor", annotations=annotate(READ, "PoE Monitor"))
async def mikrotik_get_poe_monitor(ctx: Context, interfaces: str, device: Optional[str] = None) -> str:
    """Reads real-time Power-over-Ethernet (PoE) monitor data for one or more
    ethernet interfaces — PoE-out status, voltage, current, and power.

    Runs ``/interface ethernet poe monitor <interfaces> once``.

    Notes:
        interfaces: comma-separated ethernet interface name(s), e.g.
            "ether1" or "ether9-ap,ether10-ap,ether11-ap,ether12-ap"
    """
    await ctx.info(f"Reading PoE monitor for: {interfaces}")

    # `once` is required — without it the monitor streams continuously and the
    # command never returns (it would hang the SSH session).
    cmd = f"/interface ethernet poe monitor {interfaces} once"
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result or not result.strip():
        return (
            f"No PoE monitor data returned for: {interfaces}. "
            "The interface(s) may not exist or the device may not support PoE."
        )

    return f"POE MONITOR:\n\n{result}"


@mcp.tool(name="list_poe", annotations=annotate(READ, "List PoE"))
async def mikrotik_list_poe(ctx: Context, interface_filter: Optional[str] = None, device: Optional[str] = None) -> str:
    """Lists the Power-over-Ethernet (PoE) configuration of PoE-capable
    ethernet interfaces (PoE-out mode, priority).

    Runs ``/interface ethernet poe print``.

    Notes:
        interface_filter: partial name match, e.g. "ether" matches ether1, ether2 …
    """
    await ctx.info("Listing PoE configuration")

    cmd = "/interface ethernet poe print"
    if interface_filter:
        cmd += f' where name~"{interface_filter}"'

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result or not result.strip():
        return (
            "No PoE-capable ethernet interfaces found. "
            "The device may not support PoE."
        )

    return f"POE CONFIGURATION:\n\n{result}"


@mcp.tool(name="get_poe_settings", annotations=annotate(READ, "PoE Settings"))
async def mikrotik_get_poe_settings(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Gets the detailed PoE-out settings of a specific ethernet interface
    (PoE-out mode, priority, voltage, low/high thresholds, …).

    Runs ``/interface ethernet poe print detail where name=<name>``.

    Notes:
        name: exact ethernet interface name, e.g. "ether1"
    """
    await ctx.info(f"Getting PoE settings for: {name}")

    cmd = f'/interface ethernet poe print detail where name="{name}"'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result or not result.strip():
        return f"No PoE settings found for interface '{name}'."

    return f"POE SETTINGS:\n\n{result}"
