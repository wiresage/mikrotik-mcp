from typing import Optional, List
from ..connector import execute_mikrotik_command
from mcp.server.mcpserver import Context
from ..app import mcp, READ, WRITE, WRITE_IDEMPOTENT, DESTRUCTIVE, annotate
from ._selectors import resolve_item_id, item_count

@mcp.tool(name="add_route", annotations=annotate(WRITE, "Add Route"))
async def mikrotik_add_route(
    ctx: Context,
    dst_address: str,
    gateway: str,
    distance: Optional[int] = None,
    scope: Optional[int] = None,
    target_scope: Optional[int] = None,
    routing_table: Optional[str] = None,
    comment: Optional[str] = None,
    disabled: bool = False,
    vrf_interface: Optional[str] = None,
    pref_src: Optional[str] = None,
    check_gateway: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Adds a route to the routing table.

    Notes:
        dst_address: CIDR e.g. "0.0.0.0/0", "192.168.1.0/24"
        routing_table: name of a table from /routing table, e.g. "via_ISP2";
            defaults to "main". RouterOS 6 called this the routing mark.
        check_gateway: "ping" or "arp"
        distance: 1-255 (lower = higher priority)
    """
    await ctx.info(f"Adding route: dst={dst_address}, gateway={gateway}")

    cmd = f"/ip route add dst-address={dst_address} gateway={gateway}"

    if distance is not None:
        cmd += f" distance={distance}"
    if scope is not None:
        cmd += f" scope={scope}"
    if target_scope is not None:
        cmd += f" target-scope={target_scope}"
    if routing_table:
        cmd += f' routing-table="{routing_table}"'
    if comment:
        cmd += f' comment="{comment}"'
    if disabled:
        cmd += " disabled=yes"
    if vrf_interface:
        cmd += f' vrf-interface="{vrf_interface}"'
    if pref_src:
        cmd += f" pref-src={pref_src}"
    if check_gateway:
        cmd += f" check-gateway={check_gateway}"

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if result.strip():
        if "*" in result or result.strip().isdigit():
            route_id = result.strip()
            details_cmd = f"/ip route print detail where .id={route_id}"
            details = await execute_mikrotik_command(details_cmd, ctx, device=device)

            if details.strip():
                return f"Route added successfully:\n\n{details}"
            else:
                return f"Route added with ID: {result}"
        else:
            return f"Failed to add route: {result}"
    else:
        details_cmd = f'/ip route print detail where dst-address="{dst_address}" and gateway="{gateway}"'
        details = await execute_mikrotik_command(details_cmd, ctx, device=device)

        if details.strip():
            return f"Route added successfully:\n\n{details}"
        else:
            return "Route addition completed but unable to verify."

@mcp.tool(name="list_routes", annotations=annotate(READ, "List Routes"))
async def mikrotik_list_routes(
    ctx: Context,
    dst_filter: Optional[str] = None,
    gateway_filter: Optional[str] = None,
    routing_table_filter: Optional[str] = None,
    distance_filter: Optional[int] = None,
    active_only: bool = False,
    disabled_only: bool = False,
    dynamic_only: bool = False,
    static_only: bool = False,
    device: Optional[str] = None
) -> str:
    """Lists routes in MikroTik routing table."""
    await ctx.info(f"Listing routes with filters: dst={dst_filter}, gateway={gateway_filter}")

    cmd = "/ip route print"

    filters = []
    if dst_filter:
        filters.append(f'dst-address~"{dst_filter}"')
    if gateway_filter:
        filters.append(f'gateway~"{gateway_filter}"')
    if routing_table_filter:
        filters.append(f'routing-table="{routing_table_filter}"')
    if distance_filter is not None:
        filters.append(f"distance={distance_filter}")
    if active_only:
        filters.append("active=yes")
    if disabled_only:
        filters.append("disabled=yes")
    if dynamic_only:
        filters.append("dynamic=yes")
    if static_only:
        filters.append("static=yes")

    if filters:
        cmd += " where " + " ".join(filters)

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result or result.strip() == "" or result.strip() == "no such item":
        return "No routes found matching the criteria."

    return f"ROUTES:\n\n{result}"

@mcp.tool(name="get_route", annotations=annotate(READ, "Get Route"))
async def mikrotik_get_route(ctx: Context, route_id: str, device: Optional[str] = None) -> str:
    """Gets detailed information about a specific route.

    Notes:
        route_id: "*N" or "N" from list output e.g. "*3"
    """
    await ctx.info(f"Getting route details: route_id={route_id}")

    cmd = f"/ip route print detail where .id={route_id}"
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result or result.strip() == "":
        return f"Route with ID '{route_id}' not found."

    return f"ROUTE DETAILS:\n\n{result}"

@mcp.tool(name="update_route", annotations=annotate(WRITE_IDEMPOTENT, "Update Route"))
async def mikrotik_update_route(
    ctx: Context,
    route_id: str,
    dst_address: Optional[str] = None,
    gateway: Optional[str] = None,
    distance: Optional[int] = None,
    scope: Optional[int] = None,
    target_scope: Optional[int] = None,
    routing_table: Optional[str] = None,
    comment: Optional[str] = None,
    disabled: Optional[bool] = None,
    vrf_interface: Optional[str] = None,
    pref_src: Optional[str] = None,
    check_gateway: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Updates a route.

    Notes:
        route_id: "*N" or "N" from list output e.g. "*3"
        dst_address: CIDR e.g. "192.168.1.0/24"
        check_gateway: "ping" or "arp"
        distance: 1-255
        routing_table: name of a table from /routing table; "" moves the route
            back to "main", since every RouterOS 7 route belongs to a table.
        Pass "" to vrf_interface or pref_src to clear them.
    """
    await ctx.info(f"Updating route: route_id={route_id}")

    cmd = f"/ip route set {route_id}"

    updates = []
    if dst_address:
        updates.append(f"dst-address={dst_address}")
    if gateway:
        updates.append(f"gateway={gateway}")
    if distance is not None:
        updates.append(f"distance={distance}")
    if scope is not None:
        updates.append(f"scope={scope}")
    if target_scope is not None:
        updates.append(f"target-scope={target_scope}")
    if routing_table is not None:
        # There is no unset: "!routing-table" is a syntax error, and a route
        # always belongs to a table, so clearing means back to "main".
        updates.append(f'routing-table="{routing_table or "main"}"')
    if comment is not None:
        updates.append(f'comment="{comment}"')
    if disabled is not None:
        updates.append(f'disabled={"yes" if disabled else "no"}')
    if vrf_interface is not None:
        if vrf_interface == "":
            updates.append("!vrf-interface")
        else:
            updates.append(f'vrf-interface="{vrf_interface}"')
    if pref_src is not None:
        if pref_src == "":
            updates.append("!pref-src")
        else:
            updates.append(f"pref-src={pref_src}")
    if check_gateway is not None:
        updates.append(f"check-gateway={check_gateway}")

    if not updates:
        return "No updates specified."

    cmd += " " + " ".join(updates)

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to update route: {result}"

    details_cmd = f"/ip route print detail where .id={route_id}"
    details = await execute_mikrotik_command(details_cmd, ctx, device=device)

    return f"Route updated successfully:\n\n{details}"

@mcp.tool(name="remove_route", annotations=annotate(DESTRUCTIVE, "Remove Route"))
async def mikrotik_remove_route(ctx: Context, route_id: str, device: Optional[str] = None) -> str:
    """Removes a route.

    Notes:
        route_id: "*N" or "N" from list output e.g. "*3"
    """
    await ctx.info(f"Removing route: route_id={route_id}")

    menu = "/ip route"
    resolved = await resolve_item_id(menu, route_id, ctx, device, execute_mikrotik_command)
    if resolved is None:
        return f"Route with ID '{route_id}' not found."
    if await item_count(menu, resolved, ctx, device, execute_mikrotik_command) != "1":
        return f"Route with ID '{route_id}' not found."
    cmd = f"{menu} remove {resolved}"
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "no such item" in result.lower():
        return f"Route with ID '{route_id}' not found."
    if result.strip():
        return f"Failed to remove route: {result}"
    if await item_count(menu, resolved, ctx, device, execute_mikrotik_command) != "0":
        return f"Failed to remove route: route '{route_id}' is still present."

    return f"Route with ID '{route_id}' removed successfully."

@mcp.tool(name="enable_route", annotations=annotate(WRITE_IDEMPOTENT, "Enable Route"))
async def mikrotik_enable_route(ctx: Context, route_id: str, device: Optional[str] = None) -> str:
    """Enables a route.

    Notes:
        route_id: "*N" or "N" from list output e.g. "*3"
    """
    return await mikrotik_update_route(ctx, route_id, disabled=False, device=device)

@mcp.tool(name="disable_route", annotations=annotate(WRITE_IDEMPOTENT, "Disable Route"))
async def mikrotik_disable_route(ctx: Context, route_id: str, device: Optional[str] = None) -> str:
    """Disables a route.

    Notes:
        route_id: "*N" or "N" from list output e.g. "*3"
    """
    return await mikrotik_update_route(ctx, route_id, disabled=True, device=device)

@mcp.tool(name="get_routing_table", annotations=annotate(READ, "Routing Table"))
async def mikrotik_get_routing_table(
    ctx: Context,
    table_name: Optional[str] = "main",
    protocol_filter: Optional[str] = None,
    active_only: bool = True,
    device: Optional[str] = None
) -> str:
    """Gets a specific routing table."""
    await ctx.info(f"Getting routing table: table={table_name}")

    cmd = "/ip route print"

    filters = []
    if table_name and table_name != "main":
        filters.append(f'routing-table="{table_name}"')
    if protocol_filter:
        filters.append(f'protocol="{protocol_filter}"')
    if active_only:
        filters.append("active=yes")

    if filters:
        cmd += " where " + " ".join(filters)

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result or result.strip() == "":
        return f"No routes found in table '{table_name}'."

    return f"ROUTING TABLE ({table_name}):\n\n{result}"

@mcp.tool(name="check_route_path", annotations=annotate(READ, "Check Route Path"))
async def mikrotik_check_route_path(
    ctx: Context,
    destination: str,
    device: Optional[str] = None
) -> str:
    """Checks the route MikroTik would use to reach a destination."""
    await ctx.info(f"Checking route path to: {destination}")

    # "once" is required: without it RouterOS keeps streaming status updates
    # and the command never returns. RouterOS 7 takes no other argument here --
    # src-address and routing-mark/-table are all rejected after the address.
    cmd = f"/ip route check {destination} once"

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result:
        return f"Unable to check route to {destination}"

    return f"ROUTE PATH TO {destination}:\n\n{result}"

@mcp.tool(name="get_route_cache", annotations=annotate(READ, "Get Route Cache"))
async def mikrotik_get_route_cache(ctx: Context, device: Optional[str] = None) -> str:
    """Gets the route cache."""
    await ctx.info("Getting route cache")

    cmd = "/ip route cache print"
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result or result.strip() == "":
        return "Route cache is empty."

    return f"ROUTE CACHE:\n\n{result}"

@mcp.tool(name="flush_route_cache", annotations=annotate(DESTRUCTIVE, "Flush Route Cache"))
async def mikrotik_flush_route_cache(ctx: Context, device: Optional[str] = None) -> str:
    """Flushes the route cache."""
    await ctx.info("Flushing route cache")

    cmd = "/ip route cache flush"
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result.strip():
        return "Route cache flushed successfully."
    else:
        return f"Flush result: {result}"

@mcp.tool(name="add_default_route", annotations=annotate(WRITE, "Add Default Route"))
async def mikrotik_add_default_route(
    ctx: Context,
    gateway: str,
    distance: int = 1,
    comment: Optional[str] = None,
    check_gateway: str = "ping",
    device: Optional[str] = None
) -> str:
    """Adds a default route."""
    return await mikrotik_add_route(
        dst_address="0.0.0.0/0",
        gateway=gateway,
        distance=distance,
        comment=comment or "Default route",
        check_gateway=check_gateway,
        ctx=ctx,
        device=device
    )

@mcp.tool(name="add_blackhole_route", annotations=annotate(WRITE, "Add Blackhole Route"))
async def mikrotik_add_blackhole_route(
    ctx: Context,
    dst_address: str,
    distance: int = 1,
    comment: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Adds a blackhole route.

    Notes:
        dst_address: CIDR e.g. "10.0.0.0/8"
        distance: 1-255
    """
    await ctx.info(f"Adding blackhole route: dst={dst_address}")

    cmd = f"/ip route add dst-address={dst_address} type=blackhole distance={distance}"

    if comment:
        cmd += f' comment="{comment}"'

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if result.strip():
        if "*" in result or result.strip().isdigit():
            return f"Blackhole route added successfully. ID: {result}"
        else:
            return f"Failed to add blackhole route: {result}"
    else:
        return "Blackhole route added successfully."

@mcp.tool(name="get_route_statistics", annotations=annotate(READ, "Route Statistics"))
async def mikrotik_get_route_statistics(ctx: Context, device: Optional[str] = None) -> str:
    """Gets routing table statistics."""
    await ctx.info("Getting route statistics")

    total_cmd = "/ip route print count-only"
    total_count = await execute_mikrotik_command(total_cmd, ctx, device=device)

    active_cmd = "/ip route print count-only where active=yes"
    active_count = await execute_mikrotik_command(active_cmd, ctx, device=device)

    dynamic_cmd = "/ip route print count-only where dynamic=yes"
    dynamic_count = await execute_mikrotik_command(dynamic_cmd, ctx, device=device)

    static_cmd = "/ip route print count-only where static=yes"
    static_count = await execute_mikrotik_command(static_cmd, ctx, device=device)

    disabled_cmd = "/ip route print count-only where disabled=yes"
    disabled_count = await execute_mikrotik_command(disabled_cmd, ctx, device=device)

    stats = [
        f"Total routes: {total_count.strip()}",
        f"Active routes: {active_count.strip()}",
        f"Dynamic routes: {dynamic_count.strip()}",
        f"Static routes: {static_count.strip()}",
        f"Disabled routes: {disabled_count.strip()}"
    ]

    return "ROUTE STATISTICS:\n\n" + "\n".join(stats)
