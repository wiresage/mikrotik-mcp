from typing import Literal, Optional

from ..connector import execute_mikrotik_command
from ._quoting import ros_quoted
from mcp.server.mcpserver import Context
from ..app import mcp, READ, WRITE, WRITE_IDEMPOTENT, DESTRUCTIVE, annotate
from ._selectors import resolve_item_id, item_count, item_at_position, move_to_position


@mcp.tool(name="create_ipv6_filter_rule", annotations=annotate(WRITE, "Create IPv6 Filter Rule"))
async def mikrotik_create_ipv6_filter_rule(
    ctx: Context,
    chain: Literal["input", "forward", "output"],
    action: Literal["accept", "drop", "reject", "jump", "log", "passthrough", "return", "tarpit"],
    jump_target: Optional[str] = None,
    src_address: Optional[str] = None,
    dst_address: Optional[str] = None,
    src_port: Optional[str] = None,
    dst_port: Optional[str] = None,
    protocol: Optional[str] = None,
    in_interface: Optional[str] = None,
    out_interface: Optional[str] = None,
    connection_state: Optional[str] = None,
    src_address_list: Optional[str] = None,
    dst_address_list: Optional[str] = None,
    src_address_type: Optional[str] = None,
    dst_address_type: Optional[str] = None,
    icmp_options: Optional[str] = None,
    hop_limit: Optional[str] = None,
    headers: Optional[str] = None,
    limit: Optional[str] = None,
    tcp_flags: Optional[str] = None,
    comment: Optional[str] = None,
    disabled: bool = False,
    log: bool = False,
    log_prefix: Optional[str] = None,
    place_before: Optional[str] = None,
    device: Optional[str] = None,
) -> str:
    """Creates an IPv6 firewall filter rule on the MikroTik device.

    Notes:
        protocol: IPv6 uses "icmpv6", not the IPv4 spelling "icmp".
        jump_target: only used with action="jump".
    """
    await ctx.info(f"Creating IPv6 firewall filter rule: chain={chain}, action={action}")

    has_match = any((
        src_address, dst_address, src_port, dst_port, protocol,
        in_interface, out_interface, connection_state,
        src_address_list, dst_address_list, src_address_type, dst_address_type,
        icmp_options, hop_limit, headers, limit, tcp_flags
    ))
    warning = "" if has_match else (
        f"WARNING: this rule has no match conditions - it matches ALL traffic in the '{chain}' chain "
        f"and applies action '{action}' to every packet. Verify this is intentional (e.g. a final drop-all rule).\n\n"
    )
    if not has_match:
        await ctx.warning(f"Creating filter rule with no match conditions - it will match all traffic in chain '{chain}'")

    cmd = f"/ipv6 firewall filter add chain={chain} action={action}"

    if jump_target:
        cmd += f' jump-target="{jump_target}"'
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
    if connection_state:
        cmd += f" connection-state={connection_state}"
    if src_address_list:
        cmd += f' src-address-list="{src_address_list}"'
    if dst_address_list:
        cmd += f' dst-address-list="{dst_address_list}"'
    if src_address_type:
        cmd += f" src-address-type={src_address_type}"
    if dst_address_type:
        cmd += f" dst-address-type={dst_address_type}"
    if icmp_options:
        cmd += f" icmp-options={icmp_options}"
    if hop_limit:
        cmd += f" hop-limit={hop_limit}"
    if headers:
        cmd += f" headers={headers}"
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

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    # A successful add prints nothing or the new id; anything else is RouterOS
    # rejecting the command, and not every rejection says "failure:" or "error"
    # ("no such item", "input does not match any value of …").
    if result.strip():
        if "*" not in result and not result.strip().isdigit():
            return f"Failed to create IPv6 firewall filter rule: {result}"

        rule_id = result.strip()
        details = await execute_mikrotik_command(
            f'/ipv6 firewall filter print detail where .id={rule_id}', ctx, device=device
        )
        if "chain=" in details:
            return f"{warning}IPv6 firewall filter rule created successfully:\n\n{details}"
        return f"{warning}IPv6 firewall filter rule created with ID: {rule_id}"

    count = await execute_mikrotik_command(
        "/ipv6 firewall filter print count-only", ctx, device=device
    )
    if count.strip().isdigit() and int(count.strip()) > 0:
        details = await execute_mikrotik_command(
            f"/ipv6 firewall filter print detail from={int(count.strip()) - 1}", ctx, device=device
        )
        if "chain=" in details:
            return f"{warning}IPv6 firewall filter rule created successfully:\n\n{details}"

    return f"{warning}IPv6 firewall filter rule created in chain '{chain}'."


@mcp.tool(name="list_ipv6_filter_rules", annotations=annotate(READ, "List IPv6 Filter Rules"))
async def mikrotik_list_ipv6_filter_rules(
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
    device: Optional[str] = None,
) -> str:
    """Lists IPv6 firewall filter rules on the MikroTik device.

    Notes:
        protocol_filter: IPv6 uses "icmpv6", not the IPv4 spelling "icmp".
        src_address_filter/dst_address_filter: partial match on the address,
            e.g. "2001:db8" matches every rule whose address starts with it.
    """
    await ctx.info(
        f"Listing IPv6 firewall filter rules with filters: chain={chain_filter}, action={action_filter}"
    )

    cmd = "/ipv6 firewall filter print"

    # RouterOS returns no matches for an unquoted value on several fields
    # (protocol among them), so every `where` term quotes its value.
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

    if not result or result.strip() == "" or result.strip() == "no such item":
        return "No IPv6 firewall filter rules found matching the criteria."

    return f"IPV6 FIREWALL FILTER RULES:\n\n{result}"


@mcp.tool(name="get_ipv6_filter_rule", annotations=annotate(READ, "Get IPv6 Filter Rule"))
async def mikrotik_get_ipv6_filter_rule(
    ctx: Context, rule_id: str, device: Optional[str] = None
) -> str:
    """Gets detailed information about a specific IPv6 firewall filter rule.

    Notes:
        rule_id: a RouterOS internal id ("*1") or a print position ("0").
    """
    await ctx.info(f"Getting IPv6 firewall filter rule details: rule_id={rule_id}")

    cmd = f'/ipv6 firewall filter print detail where .id={rule_id}'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    # `print detail` emits the Flags legend even when nothing matches, so the
    # presence of an actual field decides whether a rule was found.
    if not result or "chain=" not in result:
        return f"IPv6 firewall filter rule with ID '{rule_id}' not found."

    return f"IPV6 FIREWALL FILTER RULE DETAILS:\n\n{result}"


@mcp.tool(name="update_ipv6_filter_rule", annotations=annotate(WRITE_IDEMPOTENT, "Update IPv6 Filter Rule"))
async def mikrotik_update_ipv6_filter_rule(
    ctx: Context,
    rule_id: str,
    chain: Optional[str] = None,
    action: Optional[str] = None,
    jump_target: Optional[str] = None,
    src_address: Optional[str] = None,
    dst_address: Optional[str] = None,
    src_port: Optional[str] = None,
    dst_port: Optional[str] = None,
    protocol: Optional[str] = None,
    in_interface: Optional[str] = None,
    out_interface: Optional[str] = None,
    connection_state: Optional[str] = None,
    src_address_list: Optional[str] = None,
    dst_address_list: Optional[str] = None,
    src_address_type: Optional[str] = None,
    dst_address_type: Optional[str] = None,
    icmp_options: Optional[str] = None,
    hop_limit: Optional[str] = None,
    headers: Optional[str] = None,
    limit: Optional[str] = None,
    tcp_flags: Optional[str] = None,
    comment: Optional[str] = None,
    disabled: Optional[bool] = None,
    log: Optional[bool] = None,
    log_prefix: Optional[str] = None,
    device: Optional[str] = None,
) -> str:
    """Updates an existing IPv6 firewall filter rule on the MikroTik device.

    Notes:
        rule_id: a RouterOS internal id ("*1") or a print position ("0").
        Pass "" to clear an optional field (e.g. src_address="").
    """
    await ctx.info(f"Updating IPv6 firewall filter rule: rule_id={rule_id}")

    # Name-bearing fields are quoted, everything else bare — the same split the
    # IPv4 scope and this scope's own `create` use.
    quoted = {
        "jump-target": jump_target,
        "in-interface": in_interface,
        "out-interface": out_interface,
        "src-address-list": src_address_list,
        "dst-address-list": dst_address_list,
    }
    bare = {
        "src-address": src_address,
        "dst-address": dst_address,
        "src-port": src_port,
        "dst-port": dst_port,
        "protocol": protocol,
        "connection-state": connection_state,
        "src-address-type": src_address_type,
        "dst-address-type": dst_address_type,
        "icmp-options": icmp_options,
        "hop-limit": hop_limit,
        "headers": headers,
        "limit": limit,
        "tcp-flags": tcp_flags,
    }

    updates = []
    if chain:
        updates.append(f"chain={chain}")
    if action:
        updates.append(f"action={action}")
    for field, value in quoted.items():
        if value is not None:
            updates.append(f"!{field}" if value == "" else f'{field}="{value}"')
    for field, value in bare.items():
        if value is not None:
            updates.append(f"!{field}" if value == "" else f"{field}={value}")
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

    menu = "/ipv6 firewall filter"
    resolved = await resolve_item_id(menu, rule_id, ctx, device, execute_mikrotik_command)
    if resolved is None:
        return f"IPv6 firewall filter rule with ID '{rule_id}' not found."
    cmd = f'{menu} set {resolved} ' + " ".join(updates)
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "no such item" in result.lower():
        return f"IPv6 firewall filter rule with ID '{rule_id}' not found."
    if result.strip():
        return f"Failed to update IPv6 firewall filter rule: {result}"

    details = await execute_mikrotik_command(
        f'{menu} print detail where .id={resolved}', ctx, device=device
    )
    if "chain=" not in details:
        return f"Failed to update IPv6 firewall filter rule: {result or details}"

    return f"IPv6 firewall filter rule updated successfully:\n\n{details}"


@mcp.tool(name="remove_ipv6_filter_rule", annotations=annotate(DESTRUCTIVE, "Remove IPv6 Filter Rule"))
async def mikrotik_remove_ipv6_filter_rule(
    ctx: Context, rule_id: str, device: Optional[str] = None
) -> str:
    """Removes an IPv6 firewall filter rule from the MikroTik device.

    Notes:
        rule_id: a RouterOS internal id ("*1") or a print position ("0").
    """
    await ctx.info(f"Removing IPv6 firewall filter rule: rule_id={rule_id}")

    menu = "/ipv6 firewall filter"
    resolved = await resolve_item_id(menu, rule_id, ctx, device, execute_mikrotik_command)
    if resolved is None:
        return f"IPv6 firewall filter rule with ID '{rule_id}' not found."
    if await item_count(menu, resolved, ctx, device, execute_mikrotik_command) != "1":
        return f"IPv6 firewall filter rule with ID '{rule_id}' not found."
    result = await execute_mikrotik_command(f"{menu} remove {resolved}", ctx, device=device)

    if "no such item" in result.lower():
        return f"IPv6 firewall filter rule with ID '{rule_id}' not found."
    if result.strip():
        return f"Failed to remove IPv6 firewall filter rule: {result}"
    if await item_count(menu, resolved, ctx, device, execute_mikrotik_command) != "0":
        return f"Failed to remove IPv6 firewall filter rule: rule '{rule_id}' is still present."

    return f"IPv6 firewall filter rule with ID '{rule_id}' removed successfully."


@mcp.tool(name="move_ipv6_filter_rule", annotations=annotate(WRITE_IDEMPOTENT, "Move IPv6 Filter Rule"))
async def mikrotik_move_ipv6_filter_rule(
    ctx: Context, rule_id: str, destination: int, device: Optional[str] = None
) -> str:
    """Moves an IPv6 firewall filter rule to a different position in the chain.

    Notes:
        rule_id: a RouterOS internal id ("*1") or a print position ("0").
        destination: 0-based target position index
    """
    await ctx.info(f"Moving IPv6 firewall filter rule: rule_id={rule_id} to position {destination}")

    menu = "/ipv6 firewall filter"
    resolved = await resolve_item_id(menu, rule_id, ctx, device, execute_mikrotik_command)
    if resolved is None:
        return f"IPv6 firewall filter rule with ID '{rule_id}' not found."
    if await item_count(menu, resolved, ctx, device, execute_mikrotik_command) != "1":
        return f"IPv6 firewall filter rule with ID '{rule_id}' not found."
    result = await move_to_position(menu, resolved, destination, ctx, device, execute_mikrotik_command)

    if "no such item" in result.lower():
        return f"IPv6 firewall filter rule with ID '{rule_id}' not found."
    if result.strip():
        return f"Failed to move IPv6 firewall filter rule: {result}"
    if await item_at_position(menu, destination, ctx, device, execute_mikrotik_command) != resolved:
        return f"Failed to move IPv6 firewall filter rule: rule '{rule_id}' is not at position {destination}."

    return f"IPv6 firewall filter rule with ID '{rule_id}' moved to position {destination}."


@mcp.tool(name="enable_ipv6_filter_rule", annotations=annotate(WRITE_IDEMPOTENT, "Enable IPv6 Filter Rule"))
async def mikrotik_enable_ipv6_filter_rule(
    ctx: Context, rule_id: str, device: Optional[str] = None
) -> str:
    """Enables an IPv6 firewall filter rule."""
    return await mikrotik_update_ipv6_filter_rule(ctx, rule_id, disabled=False, device=device)


@mcp.tool(name="disable_ipv6_filter_rule", annotations=annotate(WRITE_IDEMPOTENT, "Disable IPv6 Filter Rule"))
async def mikrotik_disable_ipv6_filter_rule(
    ctx: Context, rule_id: str, device: Optional[str] = None
) -> str:
    """Disables an IPv6 firewall filter rule."""
    return await mikrotik_update_ipv6_filter_rule(ctx, rule_id, disabled=True, device=device)
