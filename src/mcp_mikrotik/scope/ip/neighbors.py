from typing import Optional

from mcp.server.mcpserver import Context

from ...app import mcp, READ, annotate
from ...connector import execute_mikrotik_command
from .._shared.quoting import ros_quoted


async def _list_neighbors(
    ctx: Context,
    command: str,
    heading: str,
    empty_message: str,
    address_filter: Optional[str],
    mac_filter: Optional[str],
    interface_filter: Optional[str],
    status_filter: Optional[str],
    device: Optional[str],
    identity_filter: Optional[str] = None,
    data_marker: str = "address=",
) -> str:
    filters = []
    if identity_filter:
        filters.append(f'identity~"{ros_quoted(identity_filter)}"')
    if address_filter:
        filters.append(f'address~"{ros_quoted(address_filter)}"')
    if mac_filter:
        filters.append(f'mac-address~"{ros_quoted(mac_filter)}"')
    if interface_filter:
        filters.append(f'interface="{ros_quoted(interface_filter)}"')
    if status_filter:
        filters.append(f'status="{ros_quoted(status_filter)}"')
    if filters:
        command += " where " + " ".join(filters)

    result = await execute_mikrotik_command(command, ctx, device=device)
    # `print detail` returns the Flags legend (non-empty) even when no row
    # matches, so we check for real entry data instead of non-emptiness.
    # MNDP entries carry `identity=` but may have no address announced.
    if not result or data_marker not in result:
        return empty_message
    return f"{heading}:\n\n{result}"


@mcp.tool(name="list_arp_entries", annotations=annotate(READ, "List ARP Entries"))
async def mikrotik_list_arp_entries(
    ctx: Context,
    address_filter: Optional[str] = None,
    mac_filter: Optional[str] = None,
    interface_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Lists detailed IPv4 ARP entries.

    Notes:
        Address and MAC filters are substring matches. Interface and status
        filters are exact matches.
    """
    await ctx.info("Listing detailed IPv4 ARP entries")
    return await _list_neighbors(
        ctx, "/ip arp print detail", "ARP ENTRIES",
        "No ARP entries found matching the criteria.",
        address_filter, mac_filter, interface_filter, status_filter, device,
    )


@mcp.tool(name="list_ipv6_neighbors", annotations=annotate(READ, "List IPv6 Neighbors"))
async def mikrotik_list_ipv6_neighbors(
    ctx: Context,
    address_filter: Optional[str] = None,
    mac_filter: Optional[str] = None,
    interface_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Lists detailed IPv6 neighbor-discovery entries.

    Notes:
        Address and MAC filters are substring matches. Interface and status
        filters are exact matches.
    """
    await ctx.info("Listing detailed IPv6 neighbor-discovery entries")
    return await _list_neighbors(
        ctx, "/ipv6 neighbor print detail", "IPV6 NEIGHBORS",
        "No IPv6 neighbors found matching the criteria.",
        address_filter, mac_filter, interface_filter, status_filter, device,
    )


@mcp.tool(name="list_mikrotik_neighbors", annotations=annotate(READ, "List MikroTik Neighbors"))
async def mikrotik_list_mikrotik_neighbors(
    ctx: Context,
    identity_filter: Optional[str] = None,
    address_filter: Optional[str] = None,
    interface_filter: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Lists the MikroTik neighbors this router has discovered through MNDP.

    Notes:
        Identity and address filters are substring matches; interface is an
        exact match.
    """
    await ctx.info("Listing MNDP-discovered MikroTik neighbors")
    return await _list_neighbors(
        ctx, "/ip neighbor print detail", "MIKROTIK NEIGHBORS",
        "No MikroTik neighbors found matching the criteria.",
        address_filter, None, interface_filter, None, device,
        identity_filter=identity_filter,
        data_marker="identity=",
    )
