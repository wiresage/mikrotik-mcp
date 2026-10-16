from typing import Annotated, Literal, Optional
from pydantic import Field
from ..connector import execute_mikrotik_command
from mcp.server.mcpserver import Context
from ..app import mcp, READ, WRITE, WRITE_IDEMPOTENT, DESTRUCTIVE, annotate
from ._selectors import has_item_rows

@mcp.tool(name="create_vlan_interface", annotations=annotate(WRITE, "Create VLAN"))
async def mikrotik_create_vlan_interface(
    ctx: Context,
    name: str,
    vlan_id: Annotated[int, Field(ge=1, le=4094)],
    interface: str,
    comment: Optional[str] = None,
    disabled: bool = False,
    mtu: Optional[int] = None,
    use_service_tag: bool = False,
    arp: Literal["enabled", "disabled", "proxy-arp", "reply-only"] = "enabled",
    arp_timeout: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Creates a VLAN interface on the MikroTik device with the given VLAN ID and parent interface."""
    await ctx.info(f"Creating VLAN interface: name={name}, vlan_id={vlan_id}, interface={interface}")

    # Build the command
    cmd = f"/interface vlan add name={name} vlan-id={vlan_id} interface={interface}"

    # Add optional parameters
    if comment:
        cmd += f' comment="{comment}"'

    if disabled:
        cmd += " disabled=yes"

    if mtu:
        cmd += f" mtu={mtu}"

    if use_service_tag:
        cmd += " use-service-tag=yes"

    if arp != "enabled":
        cmd += f" arp={arp}"

    if arp_timeout:
        cmd += f" arp-timeout={arp_timeout}"

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    # Check if creation was successful
    if result.strip():
        # MikroTik returns the ID of created item on success
        if "*" in result or result.strip().isdigit():
            # Success - get the details
            details_cmd = f"/interface vlan print detail where name={name}"
            details = await execute_mikrotik_command(details_cmd, ctx, device=device)

            if details.strip():
                return f"VLAN interface created successfully:\n\n{details}"
            else:
                return f"VLAN interface created with ID: {result}"
        else:
            # Error occurred
            return f"Failed to create VLAN interface: {result}"
    else:
        # No output might mean success, let's check
        details_cmd = f"/interface vlan print detail where name={name}"
        details = await execute_mikrotik_command(details_cmd, ctx, device=device)

        if details.strip():
            return f"VLAN interface created successfully:\n\n{details}"
        else:
            return "VLAN interface creation completed but unable to verify."

@mcp.tool(name="list_vlan_interfaces", annotations=annotate(READ, "List VLANs"))
async def mikrotik_list_vlan_interfaces(
    ctx: Context,
    name_filter: Optional[str] = None,
    vlan_id_filter: Optional[int] = None,
    interface_filter: Optional[str] = None,
    disabled_only: bool = False,
    device: Optional[str] = None
) -> str:
    """Lists VLAN interfaces on the MikroTik device."""
    await ctx.info(f"Listing VLAN interfaces with filters: name={name_filter}, vlan_id={vlan_id_filter}, interface={interface_filter}")

    # Build the command
    cmd = "/interface vlan print"

    # Add filters
    filters = []
    if name_filter:
        filters.append(f'name~"{name_filter}"')
    if vlan_id_filter:
        filters.append(f"vlan-id={vlan_id_filter}")
    if interface_filter:
        filters.append(f'interface="{interface_filter}"')
    if disabled_only:
        filters.append("disabled=yes")

    if filters:
        cmd += " where " + " ".join(filters)

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    # Check for empty result
    if not result or result.strip() == "" or result.strip() == "no such item":
        return "No VLAN interfaces found matching the criteria."

    return f"VLAN INTERFACES:\n\n{result}"

@mcp.tool(name="get_vlan_interface", annotations=annotate(READ, "Get VLAN"))
async def mikrotik_get_vlan_interface(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Gets detailed information about a specific VLAN interface."""
    await ctx.info(f"Getting VLAN interface details: name={name}")

    cmd = f'/interface vlan print detail where name="{name}"'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not has_item_rows(result):
        return f"VLAN interface '{name}' not found."

    return f"VLAN INTERFACE DETAILS:\n\n{result}"

@mcp.tool(name="update_vlan_interface", annotations=annotate(WRITE_IDEMPOTENT, "Update VLAN"))
async def mikrotik_update_vlan_interface(
    ctx: Context,
    name: str,
    new_name: Optional[str] = None,
    vlan_id: Optional[Annotated[int, Field(ge=1, le=4094)]] = None,
    interface: Optional[str] = None,
    comment: Optional[str] = None,
    disabled: Optional[bool] = None,
    mtu: Optional[int] = None,
    use_service_tag: Optional[bool] = None,
    arp: Optional[Literal["enabled", "disabled", "proxy-arp", "reply-only"]] = None,
    arp_timeout: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Updates an existing VLAN interface's settings on the MikroTik device."""
    await ctx.info(f"Updating VLAN interface: name={name}")

    # Build the command
    cmd = f'/interface vlan set [find name="{name}"]'

    # Add parameters to update
    updates = []
    if new_name:
        updates.append(f'name={new_name}')
    if vlan_id is not None:
        updates.append(f'vlan-id={vlan_id}')
    if interface:
        updates.append(f'interface={interface}')
    if comment is not None:
        updates.append(f'comment="{comment}"')
    if disabled is not None:
        updates.append(f'disabled={"yes" if disabled else "no"}')
    if mtu:
        updates.append(f'mtu={mtu}')
    if use_service_tag is not None:
        updates.append(f'use-service-tag={"yes" if use_service_tag else "no"}')
    if arp:
        updates.append(f'arp={arp}')
    if arp_timeout:
        updates.append(f'arp-timeout={arp_timeout}')

    if not updates:
        return "No updates specified."

    cmd += " " + " ".join(updates)

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    # Check if update was successful
    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to update VLAN interface: {result}"

    # Get the updated interface details
    details_name = new_name if new_name else name
    details_cmd = f'/interface vlan print detail where name="{details_name}"'
    details = await execute_mikrotik_command(details_cmd, ctx, device=device)

    return f"VLAN interface updated successfully:\n\n{details}"

@mcp.tool(name="remove_vlan_interface", annotations=annotate(DESTRUCTIVE, "Remove VLAN"))
async def mikrotik_remove_vlan_interface(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Removes a VLAN interface from the MikroTik device."""
    await ctx.info(f"Removing VLAN interface: name={name}")

    # First check if the interface exists
    check_cmd = f'/interface vlan print count-only where name="{name}"'
    count = await execute_mikrotik_command(check_cmd, ctx, device=device)

    if count.strip() == "0":
        return f"VLAN interface '{name}' not found."

    # Remove the interface
    cmd = f'/interface vlan remove [find name="{name}"]'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to remove VLAN interface: {result}"

    return f"VLAN interface '{name}' removed successfully."
