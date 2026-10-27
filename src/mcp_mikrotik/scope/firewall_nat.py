from typing import Literal, Optional
from mcp.server.mcpserver import Context
from ..connector import execute_mikrotik_command
from ._quoting import ros_quoted
from ..app import mcp, READ, WRITE, WRITE_IDEMPOTENT, DESTRUCTIVE, annotate
from ._selectors import resolve_item_id, item_count, item_at_position, move_to_position, has_item_rows

@mcp.tool(name="create_nat_rule", annotations=annotate(WRITE, "Create NAT Rule"))
async def mikrotik_create_nat_rule(
    ctx: Context,
    chain: Literal["srcnat", "dstnat"],
    action: str,
    src_address: Optional[str] = None,
    dst_address: Optional[str] = None,
    src_port: Optional[str] = None,
    dst_port: Optional[str] = None,
    protocol: Optional[str] = None,
    in_interface: Optional[str] = None,
    out_interface: Optional[str] = None,
    to_addresses: Optional[str] = None,
    to_ports: Optional[str] = None,
    comment: Optional[str] = None,
    disabled: bool = False,
    log: bool = False,
    log_prefix: Optional[str] = None,
    place_before: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Creates a NAT rule (srcnat or dstnat) on the MikroTik device.

    Notes:
        to_addresses: single IP or range e.g. "10.0.0.1" or "10.0.0.1-10.0.0.10"
        to_ports: single port or range e.g. "8080" or "8080-8090"
        place_before: rule number or ID (*N) to insert before e.g. "0" or "*3"
    """
    await ctx.info(f"Creating NAT rule: chain={chain}, action={action}")

    # Validate action based on chain
    srcnat_actions = ["accept", "drop", "masquerade", "src-nat", "same", "netmap", "jump", "return", "log", "passthrough"]
    dstnat_actions = ["accept", "drop", "dst-nat", "jump", "return", "log", "passthrough", "redirect", "netmap", "same"]

    if chain == "srcnat" and action not in srcnat_actions:
        return f"Error: Invalid action '{action}' for srcnat. Must be one of: {', '.join(srcnat_actions)}"
    elif chain == "dstnat" and action not in dstnat_actions:
        return f"Error: Invalid action '{action}' for dstnat. Must be one of: {', '.join(dstnat_actions)}"

    # Build the command
    cmd = f"/ip firewall nat add chain={chain} action={action}"

    # Add optional parameters
    if src_address:
        cmd += f" src-address={src_address}"

    if dst_address:
        cmd += f" dst-address={dst_address}"

    if src_port:
        cmd += f" src-port={src_port}"

    if dst_port:
        cmd += f" dst-port={dst_port}"

    if protocol:
        cmd += f" protocol={protocol}"

    if in_interface:
        cmd += f' in-interface="{in_interface}"'

    if out_interface:
        cmd += f' out-interface="{out_interface}"'

    if to_addresses:
        cmd += f" to-addresses={to_addresses}"

    if to_ports:
        cmd += f" to-ports={to_ports}"

    if comment:
        cmd += f' comment="{ros_quoted(comment)}"'

    if disabled:
        cmd += " disabled=yes"

    if log:
        cmd += " log=yes"
        if log_prefix:
            cmd += f' log-prefix="{ros_quoted(log_prefix)}"'

    if place_before:
        cmd += f" place-before={place_before}"

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    # Check if creation was successful
    if result.strip():
        # MikroTik returns the ID of created item on success
        if "*" in result or result.strip().isdigit():
            # Success - get the details
            rule_id = result.strip()
            details_cmd = f"/ip firewall nat print detail where .id={rule_id}"
            details = await execute_mikrotik_command(details_cmd, ctx, device=device)

            if details.strip():
                return f"NAT rule created successfully:\n\n{details}"
            else:
                return f"NAT rule created with ID: {result}"
        else:
            # Error occurred
            return f"Failed to create NAT rule: {result}"
    else:
        # No output might mean success, let's check by getting the last rule
        details_cmd = "/ip firewall nat print detail count-only"
        count = await execute_mikrotik_command(details_cmd, ctx, device=device)

        if count.strip().isdigit() and int(count.strip()) > 0:
            # Get the last rule
            last_rule_cmd = f"/ip firewall nat print detail from={int(count.strip())-1}"
            details = await execute_mikrotik_command(last_rule_cmd, ctx, device=device)
            return f"NAT rule created successfully:\n\n{details}"
        else:
            return "NAT rule creation completed but unable to verify."

@mcp.tool(name="list_nat_rules", annotations=annotate(READ, "List NAT Rules"))
async def mikrotik_list_nat_rules(
    ctx: Context,
    chain_filter: Optional[str] = None,
    action_filter: Optional[str] = None,
    src_address_filter: Optional[str] = None,
    dst_address_filter: Optional[str] = None,
    protocol_filter: Optional[str] = None,
    interface_filter: Optional[str] = None,
    disabled_only: bool = False,
    invalid_only: bool = False,
    device: Optional[str] = None
) -> str:
    """Lists NAT rules on the MikroTik device."""
    await ctx.info(f"Listing NAT rules with filters: chain={chain_filter}, action={action_filter}")

    # Build the command
    cmd = "/ip firewall nat print"

    # Add filters
    filters = []
    if chain_filter:
        filters.append(f'chain="{chain_filter}"')
    if action_filter:
        filters.append(f'action="{action_filter}"')
    if src_address_filter:
        filters.append(f'src-address~"{src_address_filter}"')
    if dst_address_filter:
        filters.append(f'dst-address~"{dst_address_filter}"')
    if protocol_filter:
        filters.append(f'protocol="{protocol_filter}"')
    if interface_filter:
        filters.append(f'(in-interface~"{interface_filter}" or out-interface~"{interface_filter}")')
    if disabled_only:
        filters.append("disabled=yes")
    if invalid_only:
        filters.append("invalid=yes")

    if filters:
        cmd += " where " + " ".join(filters)

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    # Check for empty result
    if not result or result.strip() == "" or result.strip() == "no such item":
        return "No NAT rules found matching the criteria."

    return f"NAT RULES:\n\n{result}"

@mcp.tool(name="get_nat_rule", annotations=annotate(READ, "Get NAT Rule"))
async def mikrotik_get_nat_rule(ctx: Context, rule_id: str, device: Optional[str] = None) -> str:
    """Gets detailed information about a specific NAT rule.

    Notes:
        rule_id: use the ID from list output e.g. "*1" or "0"
    """
    await ctx.info(f"Getting NAT rule details: rule_id={rule_id}")

    cmd = f"/ip firewall nat print detail where .id={rule_id}"
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not has_item_rows(result):
        return f"NAT rule with ID '{rule_id}' not found."

    return f"NAT RULE DETAILS:\n\n{result}"

@mcp.tool(name="update_nat_rule", annotations=annotate(WRITE_IDEMPOTENT, "Update NAT Rule"))
async def mikrotik_update_nat_rule(
    ctx: Context,
    rule_id: str,
    chain: Optional[str] = None,
    action: Optional[str] = None,
    src_address: Optional[str] = None,
    dst_address: Optional[str] = None,
    src_port: Optional[str] = None,
    dst_port: Optional[str] = None,
    protocol: Optional[str] = None,
    in_interface: Optional[str] = None,
    out_interface: Optional[str] = None,
    to_addresses: Optional[str] = None,
    to_ports: Optional[str] = None,
    comment: Optional[str] = None,
    disabled: Optional[bool] = None,
    log: Optional[bool] = None,
    log_prefix: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Updates an existing NAT rule on the MikroTik device.

    Notes:
        rule_id: use the ID from list output e.g. "*1" or "0"
        to_addresses: single IP or range e.g. "10.0.0.1" or "10.0.0.1-10.0.0.10"
        to_ports: single port or range e.g. "8080" or "8080-8090"
        Pass "" to clear an optional field.
    """
    await ctx.info(f"Updating NAT rule: rule_id={rule_id}")

    # Build the command
    cmd = f"/ip firewall nat set {rule_id}"

    # Add parameters to update
    updates = []
    if chain:
        updates.append(f"chain={chain}")
    if action:
        updates.append(f"action={action}")
    if src_address is not None:
        if src_address == "":
            updates.append("!src-address")
        else:
            updates.append(f"src-address={src_address}")
    if dst_address is not None:
        if dst_address == "":
            updates.append("!dst-address")
        else:
            updates.append(f"dst-address={dst_address}")
    if src_port is not None:
        if src_port == "":
            updates.append("!src-port")
        else:
            updates.append(f"src-port={src_port}")
    if dst_port is not None:
        if dst_port == "":
            updates.append("!dst-port")
        else:
            updates.append(f"dst-port={dst_port}")
    if protocol is not None:
        if protocol == "":
            updates.append("!protocol")
        else:
            updates.append(f"protocol={protocol}")
    if in_interface is not None:
        if in_interface == "":
            updates.append("!in-interface")
        else:
            updates.append(f'in-interface="{in_interface}"')
    if out_interface is not None:
        if out_interface == "":
            updates.append("!out-interface")
        else:
            updates.append(f'out-interface="{out_interface}"')
    if to_addresses is not None:
        if to_addresses == "":
            updates.append("!to-addresses")
        else:
            updates.append(f"to-addresses={to_addresses}")
    if to_ports is not None:
        if to_ports == "":
            updates.append("!to-ports")
        else:
            updates.append(f"to-ports={to_ports}")
    if comment is not None:
        updates.append(f'comment="{ros_quoted(comment)}"')
    if disabled is not None:
        updates.append(f'disabled={"yes" if disabled else "no"}')
    if log is not None:
        updates.append(f'log={"yes" if log else "no"}')
        if log and log_prefix:
            updates.append(f'log-prefix="{ros_quoted(log_prefix)}"')

    if not updates:
        return "No updates specified."

    cmd += " " + " ".join(updates)

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    # Check if update was successful
    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to update NAT rule: {result}"

    # Get the updated rule details
    details_cmd = f"/ip firewall nat print detail where .id={rule_id}"
    details = await execute_mikrotik_command(details_cmd, ctx, device=device)

    return f"NAT rule updated successfully:\n\n{details}"

@mcp.tool(name="remove_nat_rule", annotations=annotate(DESTRUCTIVE, "Remove NAT Rule"))
async def mikrotik_remove_nat_rule(ctx: Context, rule_id: str, device: Optional[str] = None) -> str:
    """Removes a NAT rule from the MikroTik device.

    Notes:
        rule_id: use the ID from list output e.g. "*1" or "0"
    """
    await ctx.info(f"Removing NAT rule: rule_id={rule_id}")

    menu = "/ip firewall nat"
    resolved = await resolve_item_id(menu, rule_id, ctx, device, execute_mikrotik_command)
    if resolved is None:
        return f"NAT rule with ID '{rule_id}' not found."
    if await item_count(menu, resolved, ctx, device, execute_mikrotik_command) != "1":
        return f"NAT rule with ID '{rule_id}' not found."
    cmd = f"{menu} remove {resolved}"
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "no such item" in result.lower():
        return f"NAT rule with ID '{rule_id}' not found."
    if result.strip():
        return f"Failed to remove NAT rule: {result}"
    if await item_count(menu, resolved, ctx, device, execute_mikrotik_command) != "0":
        return f"Failed to remove NAT rule: rule '{rule_id}' is still present."

    return f"NAT rule with ID '{rule_id}' removed successfully."

@mcp.tool(name="move_nat_rule", annotations=annotate(WRITE_IDEMPOTENT, "Move NAT Rule"))
async def mikrotik_move_nat_rule(ctx: Context, rule_id: str, destination: int, device: Optional[str] = None) -> str:
    """Moves a NAT rule to a different position in the chain.

    Notes:
        rule_id: use the ID from list output e.g. "*1" or "0"
        destination: 0-based target position index
    """
    await ctx.info(f"Moving NAT rule: rule_id={rule_id} to position {destination}")

    menu = "/ip firewall nat"
    resolved = await resolve_item_id(menu, rule_id, ctx, device, execute_mikrotik_command)
    if resolved is None:
        return f"NAT rule with ID '{rule_id}' not found."
    if await item_count(menu, resolved, ctx, device, execute_mikrotik_command) != "1":
        return f"NAT rule with ID '{rule_id}' not found."
    result = await move_to_position(menu, resolved, destination, ctx, device, execute_mikrotik_command)

    if "no such item" in result.lower():
        return f"NAT rule with ID '{rule_id}' not found."
    if result.strip():
        return f"Failed to move NAT rule: {result}"
    if await item_at_position(menu, destination, ctx, device, execute_mikrotik_command) != resolved:
        return f"Failed to move NAT rule: rule '{rule_id}' is not at position {destination}."

    return f"NAT rule with ID '{rule_id}' moved to position {destination}."

@mcp.tool(name="enable_nat_rule", annotations=annotate(WRITE_IDEMPOTENT, "Enable NAT Rule"))
async def mikrotik_enable_nat_rule(ctx: Context, rule_id: str, device: Optional[str] = None) -> str:
    """Enables a NAT rule."""
    return await mikrotik_update_nat_rule(ctx, rule_id, disabled=False, device=device)

@mcp.tool(name="disable_nat_rule", annotations=annotate(WRITE_IDEMPOTENT, "Disable NAT Rule"))
async def mikrotik_disable_nat_rule(ctx: Context, rule_id: str, device: Optional[str] = None) -> str:
    """Disables a NAT rule."""
    return await mikrotik_update_nat_rule(ctx, rule_id, disabled=True, device=device)
