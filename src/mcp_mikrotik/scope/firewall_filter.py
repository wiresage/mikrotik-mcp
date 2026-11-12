from typing import Literal, Optional, List
from mcp.server.mcpserver import Context
from ..app import mcp, READ, WRITE, WRITE_IDEMPOTENT, DESTRUCTIVE, DANGEROUS, annotate
from ..connector import execute_mikrotik_command
from ._quoting import ros_quoted
from ._selectors import _ID_RE, item_at_position, move_to_position, resolve_item_id

async def _resolve_filter_rule_id(rule_id: str, ctx: Context, device: Optional[str]) -> Optional[str]:
    return await resolve_item_id("/ip firewall filter", rule_id, ctx, device, execute_mikrotik_command)


@mcp.tool(name="create_filter_rule", annotations=annotate(WRITE, "Create Firewall Filter Rule"))
async def mikrotik_create_filter_rule(
    ctx: Context,
    chain: Literal["input", "forward", "output"],
    action: Literal["accept", "drop", "reject", "jump", "log", "passthrough", "return", "tarpit", "fasttrack-connection"],
    src_address: Optional[str] = None,
    dst_address: Optional[str] = None,
    src_port: Optional[str] = None,
    dst_port: Optional[str] = None,
    protocol: Optional[str] = None,
    in_interface: Optional[str] = None,
    out_interface: Optional[str] = None,
    in_interface_list: Optional[str] = None,
    out_interface_list: Optional[str] = None,
    connection_state: Optional[str] = None,
    connection_nat_state: Optional[str] = None,
    src_address_list: Optional[str] = None,
    dst_address_list: Optional[str] = None,
    limit: Optional[str] = None,
    tcp_flags: Optional[str] = None,
    comment: Optional[str] = None,
    disabled: bool = False,
    log: bool = False,
    log_prefix: Optional[str] = None,
    place_before: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Creates a firewall filter rule in the specified chain on the MikroTik device.

    Notes:
        connection_state: comma-separated e.g. "established,related,new,invalid"
        limit: RouterOS rate/burst string e.g. "10,5:packet" or "10/1s:packet"
        tcp_flags: RouterOS flag expression e.g. "syn,!ack"
        place_before: rule number or ID (*N) to insert before e.g. "0" or "*3"
        in_interface_list/out_interface_list: name of an /interface list (e.g. "LAN", "WAN") rather than a single interface
    """
    await ctx.info(f"Creating firewall filter rule: chain={chain}, action={action}")

    has_match = any((
        src_address, dst_address, src_port, dst_port, protocol,
        in_interface, out_interface, connection_state, connection_nat_state,
        src_address_list, dst_address_list, limit, tcp_flags
    ))
    warning = "" if has_match else (
        f"WARNING: this rule has no match conditions - it matches ALL traffic in the '{chain}' chain "
        f"and applies action '{action}' to every packet. Verify this is intentional (e.g. a final drop-all rule).\n\n"
    )
    if not has_match:
        await ctx.warning(f"Creating filter rule with no match conditions - it will match all traffic in chain '{chain}'")

    # Build the command
    cmd = f"/ip firewall filter add chain={chain} action={action}"

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

    if in_interface_list:
        cmd += f' in-interface-list="{in_interface_list}"'

    if out_interface_list:
        cmd += f' out-interface-list="{out_interface_list}"'

    if connection_state:
        cmd += f" connection-state={connection_state}"

    if connection_nat_state:
        cmd += f" connection-nat-state={connection_nat_state}"

    if src_address_list:
        cmd += f' src-address-list="{src_address_list}"'

    if dst_address_list:
        cmd += f' dst-address-list="{dst_address_list}"'

    if limit:
        cmd += f" limit={limit}"

    if tcp_flags:
        cmd += f" tcp-flags={tcp_flags}"

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

    # Wrapping the add in `:put [...]` makes RouterOS echo the new internal
    # id, the durable selector a caller can hold on to afterwards -- the half
    # of #109 that positional numbers cannot cover. It doubles as positive
    # evidence of success: a refused add prints an error and no id, so the
    # old "no output, assume it worked" path is gone.
    result = await execute_mikrotik_command(f":put [{cmd}]", ctx, device=device)

    new_id = result.strip()
    if not _ID_RE.fullmatch(new_id):
        return f"Failed to create firewall filter rule: {new_id or 'no rule ID returned'}"

    details_cmd = f"/ip firewall filter print detail where .id={new_id}"
    details = await execute_mikrotik_command(details_cmd, ctx, device=device)

    if details.strip():
        return f"{warning}Firewall filter rule created successfully (ID {new_id}):\n\n{details}"
    return f"{warning}Firewall filter rule created successfully with ID: {new_id}"

@mcp.tool(name="list_filter_rules", annotations=annotate(READ, "List Firewall Filter Rules"))
async def mikrotik_list_filter_rules(
    ctx: Context,
    chain_filter: Optional[str] = None,
    action_filter: Optional[str] = None,
    src_address_filter: Optional[str] = None,
    dst_address_filter: Optional[str] = None,
    protocol_filter: Optional[str] = None,
    interface_filter: Optional[str] = None,
    disabled_only: bool = False,
    invalid_only: bool = False,
    dynamic_only: bool = False,
    device: Optional[str] = None
) -> str:
    """Lists firewall filter rules on the MikroTik device."""
    await ctx.info(f"Listing firewall filter rules with filters: chain={chain_filter}, action={action_filter}")

    # Build the command
    cmd = "/ip firewall filter print"

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
    if dynamic_only:
        filters.append("dynamic=yes")

    if filters:
        cmd += " where " + " ".join(filters)

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    # Check for empty result
    if not result or result.strip() == "" or result.strip() == "no such item":
        return "No firewall filter rules found matching the criteria."

    return f"FIREWALL FILTER RULES:\n\n{result}"

@mcp.tool(name="get_filter_rule", annotations=annotate(READ, "Get Firewall Filter Rule"))
async def mikrotik_get_filter_rule(ctx: Context, rule_id: str, device: Optional[str] = None) -> str:
    """Gets detailed information about a specific firewall filter rule.

    Notes:
        rule_id: positional number from list output (e.g. "12") or internal ID (e.g. "*1A")
    """
    await ctx.info(f"Getting firewall filter rule details: rule_id={rule_id}")

    resolved = await _resolve_filter_rule_id(rule_id, ctx, device)
    if resolved is None:
        return f"Firewall filter rule with ID '{rule_id}' not found."

    cmd = f"/ip firewall filter print detail where .id={resolved}"
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    # A zero-match print still emits the "Flags: ..." legend line, so an
    # empty-string check alone lets not-found results through as details.
    meaningful_lines = [
        line for line in result.splitlines()
        if line.strip() and not line.strip().startswith("Flags:")
    ]
    if "no such item" in result or not meaningful_lines:
        return f"Firewall filter rule with ID '{rule_id}' not found."

    return f"FIREWALL FILTER RULE DETAILS:\n\n{result}"

@mcp.tool(name="update_filter_rule", annotations=annotate(WRITE_IDEMPOTENT, "Update Firewall Filter Rule"))
async def mikrotik_update_filter_rule(
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
    in_interface_list: Optional[str] = None,
    out_interface_list: Optional[str] = None,
    connection_state: Optional[str] = None,
    connection_nat_state: Optional[str] = None,
    src_address_list: Optional[str] = None,
    dst_address_list: Optional[str] = None,
    limit: Optional[str] = None,
    tcp_flags: Optional[str] = None,
    comment: Optional[str] = None,
    disabled: Optional[bool] = None,
    log: Optional[bool] = None,
    log_prefix: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Updates an existing firewall filter rule on the MikroTik device.

    Notes:
        rule_id: positional number from list output (e.g. "12") or internal ID (e.g. "*1A")
        connection_state: comma-separated e.g. "established,related"
        limit: RouterOS rate string e.g. "10,5:packet"
        tcp_flags: RouterOS flag expression e.g. "syn,!ack"
        Pass "" to clear an optional field (e.g. src_address="").
    """
    await ctx.info(f"Updating firewall filter rule: rule_id={rule_id}")

    resolved = await _resolve_filter_rule_id(rule_id, ctx, device)
    if resolved is None:
        return f"Firewall filter rule with ID '{rule_id}' not found."

    # Build the command
    cmd = f"/ip firewall filter set {resolved}"

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
    if in_interface_list is not None:
        if in_interface_list == "":
            updates.append("!in-interface-list")
        else:
            updates.append(f'in-interface-list="{in_interface_list}"')
    if out_interface_list is not None:
        if out_interface_list == "":
            updates.append("!out-interface-list")
        else:
            updates.append(f'out-interface-list="{out_interface_list}"')
    if connection_state is not None:
        if connection_state == "":
            updates.append("!connection-state")
        else:
            updates.append(f"connection-state={connection_state}")
    if connection_nat_state is not None:
        if connection_nat_state == "":
            updates.append("!connection-nat-state")
        else:
            updates.append(f"connection-nat-state={connection_nat_state}")
    if src_address_list is not None:
        if src_address_list == "":
            updates.append("!src-address-list")
        else:
            updates.append(f'src-address-list="{src_address_list}"')
    if dst_address_list is not None:
        if dst_address_list == "":
            updates.append("!dst-address-list")
        else:
            updates.append(f'dst-address-list="{dst_address_list}"')
    if limit is not None:
        if limit == "":
            updates.append("!limit")
        else:
            updates.append(f"limit={limit}")
    if tcp_flags is not None:
        if tcp_flags == "":
            updates.append("!tcp-flags")
        else:
            updates.append(f"tcp-flags={tcp_flags}")
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
        return f"Failed to update firewall filter rule: {result}"

    # Get the updated rule details
    details_cmd = f"/ip firewall filter print detail where .id={resolved}"
    details = await execute_mikrotik_command(details_cmd, ctx, device=device)

    return f"Firewall filter rule updated successfully:\n\n{details}"

@mcp.tool(name="remove_filter_rule", annotations=annotate(DESTRUCTIVE, "Remove Firewall Filter Rule"))
async def mikrotik_remove_filter_rule(ctx: Context, rule_id: str, device: Optional[str] = None) -> str:
    """Removes a firewall filter rule from the MikroTik device.

    Notes:
        rule_id: positional number from list output (e.g. "12") or internal ID (e.g. "*1A")
    """
    await ctx.info(f"Removing firewall filter rule: rule_id={rule_id}")

    resolved = await _resolve_filter_rule_id(rule_id, ctx, device)
    if resolved is None:
        return f"Firewall filter rule with ID '{rule_id}' not found."

    # First check if the rule exists
    check_cmd = f"/ip firewall filter print count-only where .id={resolved}"
    count = await execute_mikrotik_command(check_cmd, ctx, device=device)

    if count.strip() == "0":
        return f"Firewall filter rule with ID '{rule_id}' not found."

    # Remove the rule
    cmd = f"/ip firewall filter remove {resolved}"
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to remove firewall filter rule: {result}"

    return f"Firewall filter rule with ID '{rule_id}' removed successfully."

@mcp.tool(name="move_filter_rule", annotations=annotate(WRITE_IDEMPOTENT, "Move Filter Rule"))
async def mikrotik_move_filter_rule(ctx: Context, rule_id: str, destination: int, device: Optional[str] = None) -> str:
    """Moves a firewall filter rule to a different position in the chain.

    Notes:
        rule_id: positional number from list output (e.g. "12") or internal ID (e.g. "*1A")
        destination: 0-based target position index
    """
    await ctx.info(f"Moving firewall filter rule: rule_id={rule_id} to position {destination}")

    resolved = await _resolve_filter_rule_id(rule_id, ctx, device)
    if resolved is None:
        return f"Firewall filter rule with ID '{rule_id}' not found."

    # Check if the rule exists
    check_cmd = f"/ip firewall filter print count-only where .id={resolved}"
    count = await execute_mikrotik_command(check_cmd, ctx, device=device)

    if count.strip() == "0":
        return f"Firewall filter rule with ID '{rule_id}' not found."

    # Move the rule
    menu = "/ip firewall filter"
    result = await move_to_position(menu, resolved, destination, ctx, device, execute_mikrotik_command)

    if "no such item" in result.lower():
        return f"Firewall filter rule with ID '{rule_id}' not found."
    if result.strip():
        return f"Failed to move firewall filter rule: {result}"
    if await item_at_position(menu, destination, ctx, device, execute_mikrotik_command) != resolved:
        return f"Failed to move firewall filter rule: rule '{rule_id}' is not at position {destination}."

    return f"Firewall filter rule with ID '{rule_id}' moved to position {destination}."

@mcp.tool(name="enable_filter_rule", annotations=annotate(WRITE_IDEMPOTENT, "Enable Filter Rule"))
async def mikrotik_enable_filter_rule(ctx: Context, rule_id: str, device: Optional[str] = None) -> str:
    """Enables a firewall filter rule."""
    return await mikrotik_update_filter_rule(ctx, rule_id, disabled=False, device=device)

@mcp.tool(name="disable_filter_rule", annotations=annotate(WRITE_IDEMPOTENT, "Disable Filter Rule"))
async def mikrotik_disable_filter_rule(ctx: Context, rule_id: str, device: Optional[str] = None) -> str:
    """Disables a firewall filter rule."""
    return await mikrotik_update_filter_rule(ctx, rule_id, disabled=True, device=device)

@mcp.tool(name="create_basic_firewall_setup", annotations=annotate(DANGEROUS, "Create Basic Firewall Setup"))
async def mikrotik_create_basic_firewall_setup(ctx: Context, device: Optional[str] = None) -> str:
    """Creates a basic firewall setup with common security rules on the MikroTik device."""
    await ctx.info("Creating basic firewall setup")

    results = []

    # Allow established and related connections
    cmd1 = "/ip firewall filter add chain=input action=accept connection-state=established,related comment=\"Accept established,related\""
    result1 = await execute_mikrotik_command(cmd1, ctx, device=device)
    results.append("Rule 1 (established/related): " + ("Created" if not result1 or "*" in result1 else result1))

    # Drop invalid connections
    cmd2 = "/ip firewall filter add chain=input action=drop connection-state=invalid comment=\"Drop invalid\""
    result2 = await execute_mikrotik_command(cmd2, ctx, device=device)
    results.append("Rule 2 (drop invalid): " + ("Created" if not result2 or "*" in result2 else result2))

    # Allow ICMP
    cmd3 = "/ip firewall filter add chain=input action=accept protocol=icmp comment=\"Accept ICMP\""
    result3 = await execute_mikrotik_command(cmd3, ctx, device=device)
    results.append("Rule 3 (ICMP): " + ("Created" if not result3 or "*" in result3 else result3))

    # Allow management from specific network
    cmd4 = "/ip firewall filter add chain=input action=accept src-address=192.168.88.0/24 comment=\"Accept management network\""
    result4 = await execute_mikrotik_command(cmd4, ctx, device=device)
    results.append("Rule 4 (management network): " + ("Created" if not result4 or "*" in result4 else result4))

    # Drop everything else
    cmd5 = "/ip firewall filter add chain=input action=drop comment=\"Drop everything else\""
    result5 = await execute_mikrotik_command(cmd5, ctx, device=device)
    results.append("Rule 5 (drop all): " + ("Created" if not result5 or "*" in result5 else result5))

    return "BASIC FIREWALL SETUP RESULTS:\n\n" + "\n".join(results)
