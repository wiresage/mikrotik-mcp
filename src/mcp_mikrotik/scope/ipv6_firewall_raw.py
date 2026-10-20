from typing import Literal, Optional

from mcp.server.mcpserver import Context

from ..app import mcp, READ, WRITE, WRITE_IDEMPOTENT, DESTRUCTIVE, annotate
from ..connector import execute_mikrotik_command
from . import _firewall_raw as raw

RawAction = Literal[
    "accept", "drop", "notrack", "jump", "return", "log", "passthrough",
    "add-src-to-address-list", "add-dst-to-address-list",
]


def _fields(**kw):
    return {name.replace("_", "-"): value for name, value in kw.items()}


@mcp.tool(name="list_ipv6_raw_rules", annotations=annotate(READ, "List IPv6 Firewall Raw Rules"))
async def mikrotik_list_ipv6_raw_rules(
    ctx: Context,
    chain_filter: Optional[str] = None,
    action_filter: Optional[str] = None,
    src_address_filter: Optional[str] = None,
    dst_address_filter: Optional[str] = None,
    protocol_filter: Optional[str] = None,
    interface_filter: Optional[str] = None,
    comment_filter: Optional[str] = None,
    disabled_only: bool = False,
    invalid_only: bool = False,
    dynamic_only: bool = False,
    stats: bool = False,
    device: Optional[str] = None,
) -> str:
    """Lists /ipv6 firewall raw rules on the MikroTik device.

    Notes:
        chain_filter, action_filter, protocol_filter: exact match. src/dst_address_filter, interface_filter
        (interfaces and interface lists), comment_filter: substring match. stats=True shows byte/packet counters.
    """
    return await raw.list_rules(
        raw.IPV6, execute_mikrotik_command, ctx,
        chain_filter=chain_filter, action_filter=action_filter, src_address_filter=src_address_filter,
        dst_address_filter=dst_address_filter, protocol_filter=protocol_filter,
        interface_filter=interface_filter, comment_filter=comment_filter, disabled_only=disabled_only,
        invalid_only=invalid_only, dynamic_only=dynamic_only, stats=stats, device=device,
    )


@mcp.tool(name="get_ipv6_raw_rule", annotations=annotate(READ, "Get IPv6 Firewall Raw Rule"))
async def mikrotik_get_ipv6_raw_rule(ctx: Context, rule_id: str, device: Optional[str] = None) -> str:
    """Gets detailed information about a specific /ipv6 firewall raw rule.

    Notes:
        rule_id: a RouterOS internal id ("*1A") or a print position ("0").
    """
    return await raw.get_rule(raw.IPV6, execute_mikrotik_command, ctx, rule_id, device)


@mcp.tool(name="create_ipv6_raw_rule", annotations=annotate(WRITE, "Create IPv6 Firewall Raw Rule"))
async def mikrotik_create_ipv6_raw_rule(
    ctx: Context,
    chain: str,
    action: RawAction,
    jump_target: Optional[str] = None,
    address_list: Optional[str] = None,
    address_list_timeout: Optional[str] = None,
    src_address: Optional[str] = None,
    dst_address: Optional[str] = None,
    src_port: Optional[str] = None,
    dst_port: Optional[str] = None,
    port: Optional[str] = None,
    protocol: Optional[str] = None,
    in_interface: Optional[str] = None,
    out_interface: Optional[str] = None,
    in_interface_list: Optional[str] = None,
    out_interface_list: Optional[str] = None,
    src_address_list: Optional[str] = None,
    dst_address_list: Optional[str] = None,
    src_address_type: Optional[str] = None,
    dst_address_type: Optional[str] = None,
    tcp_flags: Optional[str] = None,
    icmp_options: Optional[str] = None,
    packet_size: Optional[str] = None,
    hop_limit: Optional[str] = None,
    dscp: Optional[str] = None,
    limit: Optional[str] = None,
    comment: Optional[str] = None,
    disabled: bool = False,
    log: bool = False,
    log_prefix: Optional[str] = None,
    place_before: Optional[str] = None,
    device: Optional[str] = None,
) -> str:
    """Creates an /ipv6 firewall raw rule (applied before connection tracking).

    Notes:
        chain: "prerouting" or "output", or a custom chain reached by jump.
        jump_target: required with action="jump". address_list (+ optional address_list_timeout, e.g. "1d"):
        required with add-src/dst-to-address-list. Prefix a matcher value with "!" to negate it.
        protocol: IPv6 uses "icmpv6", not "icmp".
        place_before: internal id ("*3") or print position ("0").
    """
    fields = _fields(
        jump_target=jump_target, address_list=address_list, address_list_timeout=address_list_timeout,
        src_address=src_address, dst_address=dst_address, src_port=src_port, dst_port=dst_port, port=port,
        protocol=protocol, in_interface=in_interface, out_interface=out_interface,
        in_interface_list=in_interface_list, out_interface_list=out_interface_list,
        src_address_list=src_address_list, dst_address_list=dst_address_list,
        src_address_type=src_address_type, dst_address_type=dst_address_type, tcp_flags=tcp_flags,
        icmp_options=icmp_options, packet_size=packet_size, hop_limit=hop_limit, dscp=dscp, limit=limit,
    )
    return await raw.create_rule(
        raw.IPV6, execute_mikrotik_command, ctx, chain=chain, action=action, fields=fields,
        comment=comment, disabled=disabled, log=log, log_prefix=log_prefix,
        place_before=place_before, device=device,
    )


@mcp.tool(name="update_ipv6_raw_rule", annotations=annotate(WRITE_IDEMPOTENT, "Update IPv6 Firewall Raw Rule"))
async def mikrotik_update_ipv6_raw_rule(
    ctx: Context,
    rule_id: str,
    chain: Optional[str] = None,
    action: Optional[RawAction] = None,
    jump_target: Optional[str] = None,
    address_list: Optional[str] = None,
    address_list_timeout: Optional[str] = None,
    src_address: Optional[str] = None,
    dst_address: Optional[str] = None,
    src_port: Optional[str] = None,
    dst_port: Optional[str] = None,
    port: Optional[str] = None,
    protocol: Optional[str] = None,
    in_interface: Optional[str] = None,
    out_interface: Optional[str] = None,
    in_interface_list: Optional[str] = None,
    out_interface_list: Optional[str] = None,
    src_address_list: Optional[str] = None,
    dst_address_list: Optional[str] = None,
    src_address_type: Optional[str] = None,
    dst_address_type: Optional[str] = None,
    tcp_flags: Optional[str] = None,
    icmp_options: Optional[str] = None,
    packet_size: Optional[str] = None,
    hop_limit: Optional[str] = None,
    dscp: Optional[str] = None,
    limit: Optional[str] = None,
    comment: Optional[str] = None,
    disabled: Optional[bool] = None,
    log: Optional[bool] = None,
    log_prefix: Optional[str] = None,
    device: Optional[str] = None,
) -> str:
    """Updates an existing /ipv6 firewall raw rule.

    Notes:
        rule_id: a RouterOS internal id ("*1A") or a print position ("0").
        Pass "" to clear an optional matcher (e.g. src_address="").
    """
    fields = _fields(
        jump_target=jump_target, address_list=address_list, address_list_timeout=address_list_timeout,
        src_address=src_address, dst_address=dst_address, src_port=src_port, dst_port=dst_port, port=port,
        protocol=protocol, in_interface=in_interface, out_interface=out_interface,
        in_interface_list=in_interface_list, out_interface_list=out_interface_list,
        src_address_list=src_address_list, dst_address_list=dst_address_list,
        src_address_type=src_address_type, dst_address_type=dst_address_type, tcp_flags=tcp_flags,
        icmp_options=icmp_options, packet_size=packet_size, hop_limit=hop_limit, dscp=dscp, limit=limit,
    )
    return await raw.update_rule(
        raw.IPV6, execute_mikrotik_command, ctx, rule_id, chain=chain, action=action, fields=fields,
        comment=comment, disabled=disabled, log=log, log_prefix=log_prefix, device=device,
    )


@mcp.tool(name="remove_ipv6_raw_rule", annotations=annotate(DESTRUCTIVE, "Remove IPv6 Firewall Raw Rule"))
async def mikrotik_remove_ipv6_raw_rule(ctx: Context, rule_id: str, device: Optional[str] = None) -> str:
    """Removes an /ipv6 firewall raw rule.

    Notes:
        rule_id: a RouterOS internal id ("*1A") or a print position ("0").
    """
    return await raw.remove_rule(raw.IPV6, execute_mikrotik_command, ctx, rule_id, device)


@mcp.tool(name="move_ipv6_raw_rule", annotations=annotate(WRITE_IDEMPOTENT, "Move IPv6 Firewall Raw Rule"))
async def mikrotik_move_ipv6_raw_rule(ctx: Context, rule_id: str, destination: int, device: Optional[str] = None) -> str:
    """Moves an /ipv6 firewall raw rule to a different position.

    Notes:
        rule_id: a RouterOS internal id ("*1A") or a print position ("0").
        destination: 0-based target position index.
    """
    return await raw.move_rule(raw.IPV6, execute_mikrotik_command, ctx, rule_id, destination, device)


@mcp.tool(name="enable_ipv6_raw_rule", annotations=annotate(WRITE_IDEMPOTENT, "Enable IPv6 Firewall Raw Rule"))
async def mikrotik_enable_ipv6_raw_rule(ctx: Context, rule_id: str, device: Optional[str] = None) -> str:
    """Enables an /ipv6 firewall raw rule."""
    return await mikrotik_update_ipv6_raw_rule(ctx, rule_id, disabled=False, device=device)


@mcp.tool(name="disable_ipv6_raw_rule", annotations=annotate(WRITE_IDEMPOTENT, "Disable IPv6 Firewall Raw Rule"))
async def mikrotik_disable_ipv6_raw_rule(ctx: Context, rule_id: str, device: Optional[str] = None) -> str:
    """Disables an /ipv6 firewall raw rule."""
    return await mikrotik_update_ipv6_raw_rule(ctx, rule_id, disabled=True, device=device)
