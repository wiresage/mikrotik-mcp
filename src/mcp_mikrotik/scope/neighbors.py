"""Tools for inspecting ARP, IPv6 neighbors, and LLDP/CDP/MNDP neighbor discovery."""

import re
from typing import Annotated, Literal, Optional
from pydantic import Field

from mcp.server.mcpserver import Context

from ..app import mcp, READ, WRITE_IDEMPOTENT, annotate
from ..connector import execute_mikrotik_command
from ._quoting import ros_quoted
from ._selectors import has_item_rows, resolve_item_id

_NAME_RE = re.compile(r"^[a-zA-Z0-9_.\-]+$")
_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$")
_INTERFACE_NAME_RE = re.compile(r"^[a-zA-Z0-9_.\-/<>]+$")
_INTERVAL_RE = re.compile(r"^[0-9]+[smhd]?$")
_PROTOCOLS_RE = re.compile(r"^[a-zA-Z0-9_,\-]+$")


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


# ---------------------------------------------------------------------------
# ARP & IPv6 Neighbors
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# LLDP / CDP / MNDP Neighbor Discovery
# ---------------------------------------------------------------------------

@mcp.tool(name="list_discovered_neighbors", annotations=annotate(READ, "List Discovered Neighbors"))
async def mikrotik_list_discovered_neighbors(
    ctx: Context,
    interface_filter: Optional[str] = None,
    identity_filter: Optional[str] = None,
    mac_filter: Optional[str] = None,
    protocol_filter: Optional[Literal["cdp", "lldp", "mndp"]] = None,
    device: Optional[str] = None,
) -> str:
    """Lists neighbor devices discovered via MNDP, CDP, and LLDP protocols."""
    await ctx.info("Listing discovered neighbors (MNDP/CDP/LLDP)")

    cmd = "/ip neighbor print detail"
    filters = []

    if interface_filter:
        if not _INTERFACE_NAME_RE.fullmatch(interface_filter):
            return f"Invalid interface name filter: '{interface_filter}'"
        filters.append(f'interface~"{ros_quoted(interface_filter)}"')

    if identity_filter:
        filters.append(f'identity~"{ros_quoted(identity_filter)}"')

    if mac_filter:
        filters.append(f'mac-address~"{ros_quoted(mac_filter)}"')

    if protocol_filter:
        filters.append(f'discovered-by~"{protocol_filter}"')

    if filters:
        cmd += " where " + " and ".join(filters)

    result = await execute_mikrotik_command(cmd, ctx, device=device)
    if not has_item_rows(result):
        return "No discovered neighbors found matching the criteria."

    return f"DISCOVERED NEIGHBORS:\n\n{result}"


@mcp.tool(name="get_discovered_neighbor", annotations=annotate(READ, "Get Discovered Neighbor"))
async def mikrotik_get_discovered_neighbor(
    ctx: Context,
    identifier: str,
    device: Optional[str] = None,
) -> str:
    """Retrieves full details for a discovered neighbor identified by MAC address, identity, or row ID."""
    await ctx.info(f"Retrieving discovered neighbor details: identifier='{identifier}'")

    identifier = identifier.strip()
    if _MAC_RE.fullmatch(identifier):
        cmd = f'/ip neighbor print detail where mac-address="{identifier}"'
    elif identifier.startswith("*") or identifier.isdecimal():
        resolved_id = await resolve_item_id("/ip neighbor", identifier, ctx, device, execute_mikrotik_command)
        if not resolved_id:
            return f"No discovered neighbor found with ID: '{identifier}'"
        cmd = f"/ip neighbor print detail where .id={resolved_id}"
    else:
        cmd = f'/ip neighbor print detail where identity="{ros_quoted(identifier)}"'

    result = await execute_mikrotik_command(cmd, ctx, device=device)
    if not has_item_rows(result):
        return f"No discovered neighbor found matching: '{identifier}'"

    return f"DISCOVERED NEIGHBOR DETAILS:\n\n{result}"


@mcp.tool(name="get_neighbor_discovery_settings", annotations=annotate(READ, "Get Neighbor Discovery Settings"))
async def mikrotik_get_neighbor_discovery_settings(
    ctx: Context,
    device: Optional[str] = None,
) -> str:
    """Retrieves neighbor discovery protocol configuration including interface lists, intervals, and active protocols."""
    await ctx.info("Retrieving neighbor discovery settings")

    cmd = "/ip neighbor discovery-settings print"
    result = await execute_mikrotik_command(cmd, ctx, device=device)
    if not result:
        return "Failed to retrieve neighbor discovery settings."

    return f"NEIGHBOR DISCOVERY SETTINGS:\n\n{result}"


@mcp.tool(name="update_neighbor_discovery_settings", annotations=annotate(WRITE_IDEMPOTENT, "Update Neighbor Discovery Settings"))
async def mikrotik_update_neighbor_discovery_settings(
    ctx: Context,
    discover_interface_list: Optional[str] = None,
    protocol: Optional[str] = None,
    mode: Optional[Literal["tx-and-rx", "rx-only", "tx-only", "none"]] = None,
    discover_interval: Optional[str] = None,
    lldp_med: Optional[bool] = None,
    device: Optional[str] = None,
) -> str:
    """Configures neighbor discovery settings including allowed interface list, active discovery protocols, and broadcast mode."""
    await ctx.info("Updating neighbor discovery settings")

    params = []

    if discover_interface_list is not None:
        if not _NAME_RE.fullmatch(discover_interface_list) and discover_interface_list not in ("all", "none"):
            return f"Invalid interface list name: '{discover_interface_list}'"
        params.append(f"discover-interface-list={discover_interface_list}")

    if protocol is not None:
        if not _PROTOCOLS_RE.fullmatch(protocol):
            return f"Invalid protocol specification: '{protocol}'"
        params.append(f"protocol={protocol}")

    if mode is not None:
        params.append(f"mode={mode}")

    if discover_interval is not None:
        if not _INTERVAL_RE.fullmatch(discover_interval):
            return f"Invalid discover interval format: '{discover_interval}' (e.g. '30s', '1m')"
        params.append(f"discover-interval={discover_interval}")

    if lldp_med is not None:
        params.append(f"lldp-med={'yes' if lldp_med else 'no'}")

    if not params:
        return "No discovery settings provided to update."

    cmd = f"/ip neighbor discovery-settings set {' '.join(params)}"
    result = await execute_mikrotik_command(cmd, ctx, device=device)
    if result.strip():
        return f"Error updating neighbor discovery settings: {result.strip()}"

    return "Neighbor discovery settings updated successfully."
