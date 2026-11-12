import re
from typing import List, Literal, Optional

from mcp.server.mcpserver import Context

from ..app import mcp, READ, WRITE, WRITE_IDEMPOTENT, DESTRUCTIVE, annotate
from ..connector import execute_mikrotik_command
from ._quoting import ros_quoted
from ._selectors import has_item_rows

_DURATION_RE = re.compile(r"(?:\d+[wdhms])+")


@mcp.tool(name="create_dhcp_server", annotations=annotate(WRITE, "Create DHCP Server"))
async def mikrotik_create_dhcp_server(
    ctx: Context,
    name: str,
    interface: str,
    lease_time: str = "1d",
    address_pool: Optional[str] = None,
    disabled: bool = False,
    authoritative: Literal["yes", "no", "after-2sec-delay"] = "yes",
    delay_threshold: Optional[str] = None,
    comment: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Creates a DHCP server bound to the specified interface on the MikroTik device.

    Notes:
        lease_time: duration e.g. "1d", "12h", "30m", "1h30m"
    """
    await ctx.info(f"Creating DHCP server: name={name}, interface={interface}")

    # Build the command
    cmd = f"/ip dhcp-server add name={name} interface={interface} lease-time={lease_time}"

    # Add optional parameters
    if address_pool:
        cmd += f" address-pool={address_pool}"

    if disabled:
        cmd += " disabled=yes"

    if authoritative != "yes":
        cmd += f" authoritative={authoritative}"

    if delay_threshold:
        cmd += f" delay-threshold={delay_threshold}"

    if comment:
        cmd += f' comment="{ros_quoted(comment)}"'

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to create DHCP server: {result}"

    # Get the created server details
    details_cmd = f'/ip dhcp-server print detail where name="{name}"'
    details = await execute_mikrotik_command(details_cmd, ctx, device=device)

    return f"DHCP server created successfully:\n\n{details}"

@mcp.tool(name="list_dhcp_servers", annotations=annotate(READ, "List DHCP Servers"))
async def mikrotik_list_dhcp_servers(
    ctx: Context,
    name_filter: Optional[str] = None,
    interface_filter: Optional[str] = None,
    disabled_only: bool = False,
    invalid_only: bool = False,
    device: Optional[str] = None
) -> str:
    """Lists DHCP servers on the MikroTik device."""
    await ctx.info(f"Listing DHCP servers with filters: name={name_filter}, interface={interface_filter}")

    # Build the command
    cmd = "/ip dhcp-server print"

    # Add filters
    filters = []
    if name_filter:
        filters.append(f'name~"{name_filter}"')
    if interface_filter:
        filters.append(f'interface="{interface_filter}"')
    if disabled_only:
        filters.append("disabled=yes")
    if invalid_only:
        filters.append("invalid=yes")

    if filters:
        cmd += " where " + " ".join(filters)

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result or result.strip() == "":
        return "No DHCP servers found matching the criteria."

    return f"DHCP SERVERS:\n\n{result}"

@mcp.tool(name="list_dhcp_leases", annotations=annotate(READ, "List DHCP Leases"))
async def mikrotik_list_dhcp_leases(
    ctx: Context,
    address_filter: Optional[str] = None,
    mac_filter: Optional[str] = None,
    client_id_filter: Optional[str] = None,
    server_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    lease_time_filter: Optional[str] = None,
    last_seen_within: Optional[str] = None,
    hostname_filter: Optional[str] = None,
    class_id_filter: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Lists detailed IPv4 DHCP leases, optionally filtering active lease fields.

    Notes:
        Address and identity filters are substring matches. Server, status, and
        lease time filters are exact matches against RouterOS `lease-time`.
    """
    await ctx.info("Listing detailed IPv4 DHCP leases")

    if last_seen_within and not _DURATION_RE.fullmatch(last_seen_within):
        return "Invalid last_seen_within duration. Use values such as '30m', '1h30m', or '1d'."

    filters = []
    for value, field in (
        (address_filter, "active-address"),
        (mac_filter, "active-mac-address"),
        (client_id_filter, "active-client-id"),
        (hostname_filter, "active-host-name"),
        (class_id_filter, "active-class-id"),
    ):
        if value:
            filters.append(f'{field}~"{value}"')
    for value, field in (
        (server_filter, "active-server"),
        (status_filter, "status"),
        (lease_time_filter, "lease-time"),
    ):
        if value:
            filters.append(f'{field}="{value}"')
    if last_seen_within:
        filters.append(f"last-seen<={last_seen_within}")
        filters.append('last-seen!="never"')

    cmd = "/ip dhcp-server lease print detail"
    if filters:
        cmd += " where " + " ".join(filters)

    result = await execute_mikrotik_command(cmd, ctx, device=device)
    # `print detail` returns the Flags legend (non-empty) even when no row
    # matches, so we check for real entry data instead of non-emptiness.
    if not result or "address=" not in result:
        return "No DHCP leases found matching the criteria."
    return f"DHCP LEASES:\n\n{result}"

@mcp.tool(name="list_dhcpv6_bindings", annotations=annotate(READ, "List DHCPv6 Bindings"))
async def mikrotik_list_dhcpv6_bindings(
    ctx: Context,
    address_filter: Optional[str] = None,
    duid_filter: Optional[str] = None,
    iaid_filter: Optional[str] = None,
    server_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    lease_time_filter: Optional[str] = None,
    last_seen_within: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Lists detailed DHCPv6 bindings.

    Notes:
        Address and DUID filters are substring matches. IAID, server, status,
        and lease time filters are exact matches; lease time maps to `life-time`.
    """
    await ctx.info("Listing detailed DHCPv6 bindings")

    if last_seen_within and not _DURATION_RE.fullmatch(last_seen_within):
        return "Invalid last_seen_within duration. Use values such as '30m', '1h30m', or '1d'."

    filters = []
    for value, field in ((address_filter, "address"), (duid_filter, "duid")):
        if value:
            filters.append(f'{field}~"{value}"')
    for value, field in (
        (iaid_filter, "iaid"),
        (server_filter, "server"),
        (status_filter, "status"),
        (lease_time_filter, "life-time"),
    ):
        if value:
            filters.append(f'{field}="{value}"')
    if last_seen_within:
        filters.append(f"last-seen<={last_seen_within}")
        filters.append('last-seen!="never"')

    cmd = "/ipv6 dhcp-server binding print detail"
    if filters:
        cmd += " where " + " ".join(filters)

    result = await execute_mikrotik_command(cmd, ctx, device=device)
    if not result or "address=" not in result:
        return "No DHCPv6 bindings found matching the criteria."
    return f"DHCPV6 BINDINGS:\n\n{result}"

@mcp.tool(name="get_dhcp_server", annotations=annotate(READ, "Get DHCP Server"))
async def mikrotik_get_dhcp_server(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Gets detailed information about a specific DHCP server."""
    await ctx.info(f"Getting DHCP server details: name={name}")

    cmd = f'/ip dhcp-server print detail where name="{name}"'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not has_item_rows(result):
        return f"DHCP server '{name}' not found."

    return f"DHCP SERVER DETAILS:\n\n{result}"

@mcp.tool(name="create_dhcp_network", annotations=annotate(WRITE, "Create DHCP Network"))
async def mikrotik_create_dhcp_network(
    ctx: Context,
    network: str,
    gateway: str,
    netmask: Optional[str] = None,
    dns_servers: Optional[List[str]] = None,
    domain: Optional[str] = None,
    wins_servers: Optional[List[str]] = None,
    ntp_servers: Optional[List[str]] = None,
    dhcp_option: Optional[List[str]] = None,
    comment: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Creates a DHCP network configuration (gateway, DNS, domain, etc.) on the MikroTik device."""
    await ctx.info(f"Creating DHCP network: network={network}, gateway={gateway}")

    # Build the command
    cmd = f"/ip dhcp-server network add address={network} gateway={gateway}"

    # Add optional parameters
    if netmask:
        cmd += f" netmask={netmask}"

    if dns_servers:
        cmd += f" dns-server={','.join(dns_servers)}"

    if domain:
        cmd += f' domain="{domain}"'

    if wins_servers:
        cmd += f" wins-server={','.join(wins_servers)}"

    if ntp_servers:
        cmd += f" ntp-server={','.join(ntp_servers)}"

    if dhcp_option:
        cmd += f" dhcp-option={','.join(dhcp_option)}"

    if comment:
        cmd += f' comment="{ros_quoted(comment)}"'

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to create DHCP network: {result}"

    # Get the created network details
    details_cmd = f'/ip dhcp-server network print detail where address="{network}"'
    details = await execute_mikrotik_command(details_cmd, ctx, device=device)

    return f"DHCP network created successfully:\n\n{details}"

@mcp.tool(name="update_dhcp_network", annotations=annotate(WRITE_IDEMPOTENT, "Update DHCP Network"))
async def mikrotik_update_dhcp_network(
    ctx: Context,
    network: str,
    gateway: Optional[str] = None,
    netmask: Optional[str] = None,
    dns_servers: Optional[List[str]] = None,
    domain: Optional[str] = None,
    wins_servers: Optional[List[str]] = None,
    ntp_servers: Optional[List[str]] = None,
    dhcp_option: Optional[List[str]] = None,
    comment: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Updates fields on an existing DHCP network entry on the MikroTik device.

    Notes:
        Pass an empty list for dns_servers/wins_servers/ntp_servers/dhcp_option
        (or "" for domain) to clear that field.
    """
    await ctx.info(f"Updating DHCP network: network={network}")

    # First check if the network exists
    check_cmd = f'/ip dhcp-server network print count-only where address="{network}"'
    count = await execute_mikrotik_command(check_cmd, ctx, device=device)

    if count.strip() == "0":
        return f"DHCP network '{network}' not found."

    # Build the command
    cmd = f'/ip dhcp-server network set [find address="{network}"]'

    # Add parameters to update
    updates = []
    if gateway:
        updates.append(f"gateway={gateway}")
    if netmask:
        updates.append(f"netmask={netmask}")
    if dns_servers is not None:
        updates.append("!dns-server" if not dns_servers else f"dns-server={','.join(dns_servers)}")
    if domain is not None:
        updates.append("!domain" if domain == "" else f'domain="{domain}"')
    if wins_servers is not None:
        updates.append("!wins-server" if not wins_servers else f"wins-server={','.join(wins_servers)}")
    if ntp_servers is not None:
        updates.append("!ntp-server" if not ntp_servers else f"ntp-server={','.join(ntp_servers)}")
    if dhcp_option is not None:
        updates.append("!dhcp-option" if not dhcp_option else f"dhcp-option={','.join(dhcp_option)}")
    if comment is not None:
        updates.append(f'comment="{ros_quoted(comment)}"')

    if not updates:
        return "No updates specified."

    cmd += " " + " ".join(updates)

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to update DHCP network: {result}"

    # Get the updated network details
    details_cmd = f'/ip dhcp-server network print detail where address="{network}"'
    details = await execute_mikrotik_command(details_cmd, ctx, device=device)

    return f"DHCP network updated successfully:\n\n{details}"

@mcp.tool(name="remove_dhcp_network", annotations=annotate(DESTRUCTIVE, "Remove DHCP Network"))
async def mikrotik_remove_dhcp_network(ctx: Context, network: str, device: Optional[str] = None) -> str:
    """Removes a DHCP network configuration from the MikroTik device."""
    await ctx.info(f"Removing DHCP network: network={network}")

    # First check if the network exists
    check_cmd = f'/ip dhcp-server network print count-only where address="{network}"'
    count = await execute_mikrotik_command(check_cmd, ctx, device=device)

    if count.strip() == "0":
        return f"DHCP network '{network}' not found."

    # Remove the network
    cmd = f'/ip dhcp-server network remove [find address="{network}"]'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to remove DHCP network: {result}"

    return f"DHCP network '{network}' removed successfully."

@mcp.tool(name="create_dhcp_pool", annotations=annotate(WRITE, "Create DHCP Pool"))
async def mikrotik_create_dhcp_pool(
    ctx: Context,
    name: str,
    ranges: str,
    next_pool: Optional[str] = None,
    comment: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Creates a DHCP address pool with the given IP ranges on the MikroTik device.

    Notes:
        ranges: hyphen-separated range(s) e.g. "192.168.1.1-192.168.1.100"
            Multiple ranges comma-separated: "10.0.0.1-10.0.0.50,10.0.0.100-10.0.0.120"
    """
    await ctx.info(f"Creating DHCP pool: name={name}, ranges={ranges}")

    # Build the command
    cmd = f'/ip pool add name={name} ranges={ranges}'

    # Add optional parameters
    if next_pool:
        cmd += f" next-pool={next_pool}"

    if comment:
        cmd += f' comment="{ros_quoted(comment)}"'

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to create DHCP pool: {result}"

    # Get the created pool details
    details_cmd = f'/ip pool print detail where name="{name}"'
    details = await execute_mikrotik_command(details_cmd, ctx, device=device)

    return f"DHCP pool created successfully:\n\n{details}"

@mcp.tool(name="remove_dhcp_server", annotations=annotate(DESTRUCTIVE, "Remove DHCP Server"))
async def mikrotik_remove_dhcp_server(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Removes a DHCP server from the MikroTik device."""
    await ctx.info(f"Removing DHCP server: name={name}")

    # First check if the server exists
    check_cmd = f'/ip dhcp-server print count-only where name="{name}"'
    count = await execute_mikrotik_command(check_cmd, ctx, device=device)

    if count.strip() == "0":
        return f"DHCP server '{name}' not found."

    # Remove the server
    cmd = f'/ip dhcp-server remove [find name="{name}"]'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to remove DHCP server: {result}"

    return f"DHCP server '{name}' removed successfully."
