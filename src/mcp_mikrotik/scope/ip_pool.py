from typing import Optional, List

from mcp.server.mcpserver import Context

from ..connector import execute_mikrotik_command
from ._quoting import ros_quoted
from ..app import mcp, READ, WRITE, WRITE_IDEMPOTENT, DESTRUCTIVE, annotate

@mcp.tool(name="create_ip_pool", annotations=annotate(WRITE, "Add IP Pool"))
async def mikrotik_create_ip_pool(
    ctx: Context,
    name: str,
    ranges: str,
    next_pool: Optional[str] = None,
    comment: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Creates an IP pool with the given address ranges on the MikroTik device.

    Notes:
        ranges: hyphen-separated range(s) e.g. "192.168.1.1-192.168.1.100"
            Multiple ranges comma-separated: "10.0.0.1-10.0.0.50,10.0.0.100-10.0.0.120"
    """
    await ctx.info(f"Creating IP pool: name={name}, ranges={ranges}")

    # Build the command
    cmd = f"/ip pool add name={name} ranges={ranges}"

    # Add optional parameters
    if next_pool:
        cmd += f' next-pool="{next_pool}"'

    if comment:
        cmd += f' comment="{ros_quoted(comment)}"'

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    # Check if creation was successful
    if result.strip():
        # MikroTik returns the ID of created item on success
        if "*" in result or result.strip().isdigit():
            # Success - get the details
            details_cmd = f'/ip pool print detail where name="{name}"'
            details = await execute_mikrotik_command(details_cmd, ctx, device=device)

            if details.strip():
                return f"IP pool created successfully:\n\n{details}"
            else:
                return f"IP pool created with ID: {result}"
        else:
            # Error occurred
            return f"Failed to create IP pool: {result}"
    else:
        # No output might mean success, let's check
        details_cmd = f'/ip pool print detail where name="{name}"'
        details = await execute_mikrotik_command(details_cmd, ctx, device=device)

        if details.strip():
            return f"IP pool created successfully:\n\n{details}"
        else:
            return "IP pool creation completed but unable to verify."

@mcp.tool(name="list_ip_pools", annotations=annotate(READ, "List IP Pools"))
async def mikrotik_list_ip_pools(
    ctx: Context,
    name_filter: Optional[str] = None,
    ranges_filter: Optional[str] = None,
    include_used: bool = False,
    device: Optional[str] = None
) -> str:
    """Lists IP pools on the MikroTik device."""
    await ctx.info(f"Listing IP pools with filters: name={name_filter}, ranges={ranges_filter}")

    # Build the command
    cmd = "/ip pool print"

    if include_used:
        cmd += " detail"

    # Add filters
    filters = []
    if name_filter:
        filters.append(f'name~"{name_filter}"')
    if ranges_filter:
        filters.append(f'ranges~"{ranges_filter}"')

    if filters:
        cmd += " where " + " ".join(filters)

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    # Check for empty result
    if not result or result.strip() == "" or result.strip() == "no such item":
        return "No IP pools found matching the criteria."

    if include_used:
        # Parse and add used information
        result_lines = result.strip().split('\n')
        output_lines = []

        for line in result_lines:
            output_lines.append(line)
            if "name=" in line:
                # Extract pool name from the line
                name_start = line.find('name="') + 6
                name_end = line.find('"', name_start)
                if name_start > 5 and name_end > name_start:
                    pool_name = line[name_start:name_end]
                    # Get used addresses for this pool
                    used_cmd = f'/ip pool used print count-only where pool="{pool_name}"'
                    used_count = await execute_mikrotik_command(used_cmd, ctx, device=device)
                    if used_count.strip().isdigit():
                        output_lines.append(f"      used-addresses={used_count.strip()}")

        return f"IP POOLS:\n\n" + "\n".join(output_lines)

    return f"IP POOLS:\n\n{result}"

@mcp.tool(name="get_ip_pool", annotations=annotate(READ, "Get IP Pool"))
async def mikrotik_get_ip_pool(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Gets detailed information about a specific IP pool including used address count."""
    await ctx.info(f"Getting IP pool details: name={name}")

    cmd = f'/ip pool print detail where name="{name}"'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result or result.strip() == "":
        return f"IP pool '{name}' not found."

    # Get used addresses count
    used_cmd = f'/ip pool used print count-only where pool="{name}"'
    used_count = await execute_mikrotik_command(used_cmd, ctx, device=device)

    if used_count.strip().isdigit():
        return f"IP POOL DETAILS:\n\n{result}\n      used-addresses={used_count.strip()}"

    return f"IP POOL DETAILS:\n\n{result}"

@mcp.tool(name="update_ip_pool", annotations=annotate(WRITE_IDEMPOTENT, "Update IP Pool"))
async def mikrotik_update_ip_pool(
    ctx: Context,
    name: str,
    new_name: Optional[str] = None,
    ranges: Optional[str] = None,
    next_pool: Optional[str] = None,
    comment: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Updates an existing IP pool's name, ranges, or next-pool reference.

    Notes:
        ranges: hyphen-separated range(s) e.g. "192.168.1.1-192.168.1.100"
            Multiple ranges comma-separated: "10.0.0.1-10.0.0.50,10.0.0.100-10.0.0.120"
        Pass "" for next_pool to clear it.
    """
    await ctx.info(f"Updating IP pool: name={name}")

    # Build the command
    cmd = f'/ip pool set [find name="{name}"]'

    # Add parameters to update
    updates = []
    if new_name:
        updates.append(f'name={new_name}')
    if ranges:
        updates.append(f'ranges={ranges}')
    if next_pool is not None:
        if next_pool == "":
            updates.append('!next-pool')
        else:
            updates.append(f'next-pool="{next_pool}"')
    if comment is not None:
        updates.append(f'comment="{ros_quoted(comment)}"')

    if not updates:
        return "No updates specified."

    cmd += " " + " ".join(updates)

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    # Check if update was successful
    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to update IP pool: {result}"

    # Get the updated pool details
    details_name = new_name if new_name else name
    details_cmd = f'/ip pool print detail where name="{details_name}"'
    details = await execute_mikrotik_command(details_cmd, ctx, device=device)

    return f"IP pool updated successfully:\n\n{details}"

@mcp.tool(name="remove_ip_pool", annotations=annotate(DESTRUCTIVE, "Remove IP Pool"))
async def mikrotik_remove_ip_pool(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Removes an IP pool from the MikroTik device (fails if pool is in use)."""
    await ctx.info(f"Removing IP pool: name={name}")

    # First check if the pool exists
    check_cmd = f'/ip pool print count-only where name="{name}"'
    count = await execute_mikrotik_command(check_cmd, ctx, device=device)

    if count.strip() == "0":
        return f"IP pool '{name}' not found."

    # Check if pool is in use
    pool_used_cmd = f'/ip pool used print count-only where pool="{name}"'
    used_count = await execute_mikrotik_command(pool_used_cmd, ctx, device=device)

    if used_count.strip() != "0":
        return f"Cannot remove IP pool '{name}': {used_count.strip()} addresses are currently in use."

    # Check if pool is referenced by DHCP servers
    dhcp_check_cmd = f'/ip dhcp-server print count-only where address-pool="{name}"'
    dhcp_count = await execute_mikrotik_command(dhcp_check_cmd, ctx, device=device)

    if dhcp_count.strip() != "0":
        return f"Cannot remove IP pool '{name}': It is used by {dhcp_count.strip()} DHCP server(s)."

    # Remove the pool
    cmd = f'/ip pool remove [find name="{name}"]'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to remove IP pool: {result}"

    return f"IP pool '{name}' removed successfully."

@mcp.tool(name="list_ip_pool_used", annotations=annotate(READ, "List IP Pool Used"))
async def mikrotik_list_ip_pool_used(
    ctx: Context,
    pool_name: Optional[str] = None,
    address_filter: Optional[str] = None,
    mac_filter: Optional[str] = None,
    info_filter: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Lists currently used (allocated) addresses from IP pools."""
    await ctx.info(f"Listing used IP pool addresses: pool={pool_name}, address={address_filter}")

    cmd = "/ip pool used print"

    # Add filters
    filters = []
    if pool_name:
        filters.append(f'pool="{pool_name}"')
    if address_filter:
        filters.append(f'address~"{address_filter}"')
    if mac_filter:
        filters.append(f'mac-address~"{mac_filter}"')
    if info_filter:
        filters.append(f'info~"{info_filter}"')

    if filters:
        cmd += " where " + " ".join(filters)

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result or result.strip() == "" or result.strip() == "no such item":
        return "No used addresses found matching the criteria."

    return f"USED IP POOL ADDRESSES:\n\n{result}"

@mcp.tool(name="expand_ip_pool", annotations=annotate(WRITE_IDEMPOTENT, "Expand IP Pool"))
async def mikrotik_expand_ip_pool(ctx: Context, name: str, additional_ranges: str, device: Optional[str] = None) -> str:
    """Expands an existing IP pool by appending additional address ranges.

    Notes:
        additional_ranges: hyphen-separated range(s) e.g. "192.168.1.101-192.168.1.150"
            Multiple ranges comma-separated: "10.0.0.51-10.0.0.60,10.0.0.70-10.0.0.80"
    """
    await ctx.info(f"Expanding IP pool: name={name}, additional_ranges={additional_ranges}")

    # Get current ranges
    get_cmd = f'/ip pool print detail where name="{name}"'
    current = await execute_mikrotik_command(get_cmd, ctx, device=device)

    if not current or "no such item" in current:
        return f"IP pool '{name}' not found."

    # Extract current ranges
    import re
    ranges_match = re.search(r'ranges=([^\s]+)', current)
    if not ranges_match:
        return "Unable to determine current ranges."

    current_ranges = ranges_match.group(1)

    # Combine ranges
    new_ranges = f"{current_ranges},{additional_ranges}"

    # Update the pool
    return await mikrotik_update_ip_pool(ctx, name, ranges=new_ranges, device=device)
