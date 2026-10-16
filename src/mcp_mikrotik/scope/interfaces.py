from typing import Literal, Optional
from ..connector import execute_mikrotik_command
from mcp.server.mcpserver import Context
from ..app import mcp, READ, WRITE_IDEMPOTENT, annotate
from ._selectors import has_item_rows


@mcp.tool(name="list_interfaces", annotations=annotate(READ, "List Interfaces"))
async def mikrotik_list_interfaces(
    ctx: Context,
    type_filter: Optional[Literal[
        "ether", "wg", "bridge", "vlan", "pppoe-out", "pppoe-server",
        "wifi", "wireless", "lte", "loopback", "sfp", "sfp-sfpplus"
    ]] = None,
    name_filter: Optional[str] = None,
    running_only: bool = False,
    disabled_only: bool = False,
    device: Optional[str] = None,
) -> str:
    """Lists all interfaces on the MikroTik device (ethernet, bridge, WireGuard,
    PPPoE, VLAN, WiFi, SFP, LTE, loopback, and any other type).

    Notes:
        type_filter: RouterOS interface type e.g. "ether", "bridge", "vlan",
            "wg", "pppoe-out", "wifi", "lte", "loopback"
        name_filter: partial name match e.g. "ether" matches ether1, ether2 …
    """
    await ctx.info("Listing all interfaces")

    cmd = "/interface print"

    filters = []
    if type_filter:
        filters.append(f'type="{type_filter}"')
    if name_filter:
        filters.append(f'name~"{name_filter}"')
    if running_only:
        filters.append("running=yes")
    if disabled_only:
        filters.append("disabled=yes")

    if filters:
        cmd += " where " + " ".join(filters)

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result or result.strip() == "":
        return "No interfaces found matching the criteria."

    return f"INTERFACES:\n\n{result}"


@mcp.tool(name="get_interface", annotations=annotate(READ, "Get Interface"))
async def mikrotik_get_interface(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Gets detailed information about a specific interface by name.

    Notes:
        name: exact interface name e.g. "ether1", "bridge", "pppoe-out1", "wg0"
    """
    await ctx.info(f"Getting interface details: name={name}")

    cmd = f'/interface print detail where name="{name}"'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not has_item_rows(result):
        return f"Interface '{name}' not found."

    return f"INTERFACE DETAILS:\n\n{result}"


@mcp.tool(name="enable_interface", annotations=annotate(WRITE_IDEMPOTENT, "Enable Interface"))
async def mikrotik_enable_interface(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Enables an interface on the MikroTik device.

    Notes:
        name: exact interface name e.g. "ether1", "bridge", "pppoe-out1"
    """
    await ctx.info(f"Enabling interface: name={name}")

    cmd = f'/interface enable [find name="{name}"]'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to enable interface '{name}': {result}"

    # Verify the change
    check_cmd = f'/interface print detail where name="{name}"'
    details = await execute_mikrotik_command(check_cmd, ctx, device=device)

    if not details.strip():
        return f"Interface '{name}' not found."

    return f"Interface '{name}' enabled successfully:\n\n{details}"


@mcp.tool(name="disable_interface", annotations=annotate(WRITE_IDEMPOTENT, "Disable Interface"))
async def mikrotik_disable_interface(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Disables an interface on the MikroTik device.

    Notes:
        name: exact interface name e.g. "ether1", "bridge", "pppoe-out1"
    """
    await ctx.info(f"Disabling interface: name={name}")

    cmd = f'/interface disable [find name="{name}"]'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to disable interface '{name}': {result}"

    # Verify the change
    check_cmd = f'/interface print detail where name="{name}"'
    details = await execute_mikrotik_command(check_cmd, ctx, device=device)

    if not details.strip():
        return f"Interface '{name}' not found."

    return f"Interface '{name}' disabled successfully:\n\n{details}"
