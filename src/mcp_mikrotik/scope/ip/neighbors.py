from typing import Optional

from mcp.server.mcpserver import Context

from ...app import mcp, READ, annotate
from ...connector import execute_mikrotik_command


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
) -> str:
    filters = []
    if address_filter:
        filters.append(f'address~"{address_filter}"')
    if mac_filter:
        filters.append(f'mac-address~"{mac_filter}"')
    if interface_filter:
        filters.append(f'interface="{interface_filter}"')
    if status_filter:
        filters.append(f'status="{status_filter}"')
    if filters:
        command += " where " + " ".join(filters)

    result = await execute_mikrotik_command(command, ctx, device=device)
    # `print detail` returns the Flags legend (non-empty) even when no row
    # matches, so we check for real entry data instead of non-emptiness.
    if not result or "address=" not in result:
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
