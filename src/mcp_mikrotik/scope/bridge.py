from typing import Annotated, Literal, Optional
from pydantic import Field
from ..connector import execute_mikrotik_command
from mcp.server.mcpserver import Context
from ..app import mcp, READ, WRITE, WRITE_IDEMPOTENT, DESTRUCTIVE, annotate

@mcp.tool(name="list_bridge_vlans", annotations=annotate(READ, "List Bridge VLANs"))
async def mikrotik_list_bridge_vlans(
    ctx: Context,
    bridge_filter: Optional[str] = None,
    vlan_ids_filter: Optional[str] = None,
    dynamic_only: bool = False,
    device: Optional[str] = None
) -> str:
    """Lists bridge VLAN table entries (tagged/untagged port membership per VLAN)."""
    await ctx.info(f"Listing bridge VLANs with filters: bridge={bridge_filter}, vlan_ids={vlan_ids_filter}")

    cmd = "/interface bridge vlan print"

    filters = []
    if bridge_filter:
        filters.append(f'bridge="{bridge_filter}"')
    if vlan_ids_filter:
        filters.append(f"vlan-ids={vlan_ids_filter}")
    if dynamic_only:
        filters.append("dynamic=yes")

    if filters:
        cmd += " where " + " ".join(filters)

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result or result.strip() == "" or result.strip() == "no such item":
        return "No bridge VLAN entries found matching the criteria."

    return f"BRIDGE VLAN ENTRIES:\n\n{result}"

@mcp.tool(name="add_bridge_vlan", annotations=annotate(WRITE, "Add Bridge VLAN"))
async def mikrotik_add_bridge_vlan(
    ctx: Context,
    bridge: str,
    vlan_ids: str,
    tagged: Optional[str] = None,
    untagged: Optional[str] = None,
    comment: Optional[str] = None,
    disabled: bool = False,
    device: Optional[str] = None
) -> str:
    """Adds an entry to the bridge VLAN table defining tagged/untagged port membership.

    Notes:
        vlan_ids: single ID, comma list, or range e.g. "10", "10,20", "100-199"
        tagged: comma-separated ports carrying these VLANs tagged e.g. "ether1,ether2"
        untagged: comma-separated ports carrying these VLANs untagged
    """
    await ctx.info(f"Adding bridge VLAN: bridge={bridge}, vlan_ids={vlan_ids}")

    cmd = f"/interface bridge vlan add bridge={bridge} vlan-ids={vlan_ids}"

    if tagged:
        cmd += f" tagged={tagged}"

    if untagged:
        cmd += f" untagged={untagged}"

    if comment:
        cmd += f' comment="{comment}"'

    if disabled:
        cmd += " disabled=yes"

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if result.strip():
        if "*" in result or result.strip().isdigit():
            details_cmd = f'/interface bridge vlan print detail where bridge="{bridge}" vlan-ids={vlan_ids}'
            details = await execute_mikrotik_command(details_cmd, ctx, device=device)

            if details.strip():
                return f"Bridge VLAN entry added successfully:\n\n{details}"
            else:
                return f"Bridge VLAN entry added with ID: {result}"
        else:
            return f"Failed to add bridge VLAN entry: {result}"
    else:
        details_cmd = f'/interface bridge vlan print detail where bridge="{bridge}" vlan-ids={vlan_ids}'
        details = await execute_mikrotik_command(details_cmd, ctx, device=device)

        if details.strip():
            return f"Bridge VLAN entry added successfully:\n\n{details}"
        else:
            return "Bridge VLAN entry addition completed but unable to verify."

@mcp.tool(name="update_bridge_vlan", annotations=annotate(WRITE_IDEMPOTENT, "Update Bridge VLAN"))
async def mikrotik_update_bridge_vlan(
    ctx: Context,
    bridge: str,
    vlan_ids: str,
    new_vlan_ids: Optional[str] = None,
    tagged: Optional[str] = None,
    untagged: Optional[str] = None,
    comment: Optional[str] = None,
    disabled: Optional[bool] = None,
    device: Optional[str] = None
) -> str:
    """Updates an existing bridge VLAN table entry.

    Notes:
        vlan_ids: must match the stored value exactly (it is a list property)
            e.g. an entry created with "100-199" is matched by "100-199", not "150"
        tagged/untagged: comma-separated port lists; pass "" to clear the list
        Dynamic (D-flag) entries auto-created from PVIDs cannot be updated.
    """
    await ctx.info(f"Updating bridge VLAN: bridge={bridge}, vlan_ids={vlan_ids}")

    cmd = f'/interface bridge vlan set [find bridge="{bridge}" vlan-ids={vlan_ids} dynamic=no]'

    updates = []
    if new_vlan_ids:
        updates.append(f'vlan-ids={new_vlan_ids}')
    if tagged is not None:
        updates.append(f'tagged={tagged}')
    if untagged is not None:
        updates.append(f'untagged={untagged}')
    if comment is not None:
        updates.append(f'comment="{comment}"')
    if disabled is not None:
        updates.append(f'disabled={"yes" if disabled else "no"}')

    if not updates:
        return "No updates specified."

    cmd += " " + " ".join(updates)

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to update bridge VLAN entry: {result}"

    details_vlan_ids = new_vlan_ids if new_vlan_ids else vlan_ids
    details_cmd = f'/interface bridge vlan print detail where bridge="{bridge}" vlan-ids={details_vlan_ids}'
    details = await execute_mikrotik_command(details_cmd, ctx, device=device)

    return f"Bridge VLAN entry updated successfully:\n\n{details}"

@mcp.tool(name="remove_bridge_vlan", annotations=annotate(DESTRUCTIVE, "Remove Bridge VLAN"))
async def mikrotik_remove_bridge_vlan(
    ctx: Context,
    bridge: str,
    vlan_ids: str,
    device: Optional[str] = None
) -> str:
    """Removes an entry from the bridge VLAN table.

    Notes:
        vlan_ids: must match the stored value exactly (it is a list property)
    """
    await ctx.info(f"Removing bridge VLAN: bridge={bridge}, vlan_ids={vlan_ids}")

    check_cmd = f'/interface bridge vlan print count-only where bridge="{bridge}" vlan-ids={vlan_ids} dynamic=no'
    count = await execute_mikrotik_command(check_cmd, ctx, device=device)

    if count.strip() == "0":
        return f"Bridge VLAN entry bridge={bridge} vlan-ids={vlan_ids} not found (dynamic entries cannot be removed)."

    cmd = f'/interface bridge vlan remove [find bridge="{bridge}" vlan-ids={vlan_ids} dynamic=no]'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to remove bridge VLAN entry: {result}"

    return f"Bridge VLAN entry bridge={bridge} vlan-ids={vlan_ids} removed successfully."

@mcp.tool(name="list_bridge_ports", annotations=annotate(READ, "List Bridge Ports"))
async def mikrotik_list_bridge_ports(
    ctx: Context,
    bridge_filter: Optional[str] = None,
    interface_filter: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Lists bridge ports on the MikroTik device, including each port's PVID."""
    await ctx.info(f"Listing bridge ports with filters: bridge={bridge_filter}, interface={interface_filter}")

    cmd = "/interface bridge port print"

    filters = []
    if bridge_filter:
        filters.append(f'bridge="{bridge_filter}"')
    if interface_filter:
        filters.append(f'interface="{interface_filter}"')

    if filters:
        cmd += " where " + " ".join(filters)

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result or result.strip() == "" or result.strip() == "no such item":
        return "No bridge ports found matching the criteria."

    return f"BRIDGE PORTS:\n\n{result}"

@mcp.tool(name="update_bridge_port", annotations=annotate(WRITE_IDEMPOTENT, "Update Bridge Port"))
async def mikrotik_update_bridge_port(
    ctx: Context,
    interface: str,
    pvid: Optional[Annotated[int, Field(ge=1, le=4094)]] = None,
    frame_types: Optional[Literal["admit-all", "admit-only-untagged-and-priority-tagged", "admit-only-vlan-tagged"]] = None,
    ingress_filtering: Optional[bool] = None,
    device: Optional[str] = None
) -> str:
    """Updates per-port VLAN settings (PVID, frame types, ingress filtering) on a bridge port.

    Notes:
        interface: the port's interface name e.g. "ether2"; an interface can only
            belong to one bridge, so it uniquely identifies the bridge port
        pvid: VLAN ID assigned to untagged ingress traffic on this port
    """
    await ctx.info(f"Updating bridge port: interface={interface}")

    cmd = f'/interface bridge port set [find interface="{interface}"]'

    updates = []
    if pvid is not None:
        updates.append(f'pvid={pvid}')
    if frame_types:
        updates.append(f'frame-types={frame_types}')
    if ingress_filtering is not None:
        updates.append(f'ingress-filtering={"yes" if ingress_filtering else "no"}')

    if not updates:
        return "No updates specified."

    cmd += " " + " ".join(updates)

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to update bridge port: {result}"

    details_cmd = f'/interface bridge port print detail where interface="{interface}"'
    details = await execute_mikrotik_command(details_cmd, ctx, device=device)

    if not details.strip():
        return f"Bridge port for interface '{interface}' not found."

    return f"Bridge port updated successfully:\n\n{details}"
