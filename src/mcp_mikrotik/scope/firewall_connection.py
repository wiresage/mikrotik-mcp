"""Tools for inspecting and managing RouterOS firewall connection tracking table and settings."""

import re
from typing import Annotated, Literal, Optional

from mcp.server.mcpserver import Context
from pydantic import Field

from ..app import mcp, READ, WRITE_IDEMPOTENT, DESTRUCTIVE, annotate
from ..connector import execute_mikrotik_command
from ._quoting import ros_quoted
from ._selectors import has_item_rows

_IP_OR_PREFIX_RE = re.compile(r"^[0-9a-fA-F\.\:\/\-]+$")
_DURATION_RE = re.compile(r"^\d{1,4}(ms|s|m|h|d)$")
MAX_CONNECTION_LINES = 150


def _build_filters(
    protocol: Optional[str] = None,
    tcp_state: Optional[str] = None,
    src_address: Optional[str] = None,
    dst_address: Optional[str] = None,
    src_port: Optional[int] = None,
    dst_port: Optional[int] = None,
) -> list[str]:
    filters = []
    if protocol and protocol != "all":
        filters.append(f'protocol="{protocol}"')
    if tcp_state:
        filters.append(f'tcp-state="{tcp_state}"')
    if src_address:
        if not _IP_OR_PREFIX_RE.fullmatch(src_address):
            raise ValueError(f"Invalid src_address: {src_address!r}")
        filters.append(f'src-address~"{ros_quoted(src_address)}"')
    if dst_address:
        if not _IP_OR_PREFIX_RE.fullmatch(dst_address):
            raise ValueError(f"Invalid dst_address: {dst_address!r}")
        filters.append(f'dst-address~"{ros_quoted(dst_address)}"')
    if src_port is not None:
        filters.append(f"src-port={src_port}")
    if dst_port is not None:
        filters.append(f"dst-port={dst_port}")
    return filters


def _truncate_output(text: str, max_lines: int = MAX_CONNECTION_LINES) -> str:
    lines = text.split("\n")
    if len(lines) <= max_lines:
        return text
    hidden = len(lines) - max_lines
    return "\n".join(lines[:max_lines]) + f"\n... ({hidden} more lines not shown, use more specific filters)"


@mcp.tool(name="get_connection_tracking_settings", annotations=annotate(READ, "Connection Tracking Settings"))
async def mikrotik_get_connection_tracking_settings(
    ctx: Context,
    device: Optional[str] = None,
) -> str:
    """Reports global firewall connection tracking settings, timeouts, and table capacity."""
    await ctx.info("Reading connection tracking settings")

    cmd = "/ip firewall connection tracking print"
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result or not result.strip():
        return "No connection tracking settings returned."

    return f"CONNECTION TRACKING SETTINGS:\n\n{result}"


@mcp.tool(name="update_connection_tracking_settings", annotations=annotate(WRITE_IDEMPOTENT, "Update Connection Tracking Settings"))
async def mikrotik_update_connection_tracking_settings(
    ctx: Context,
    enabled: Optional[Literal["yes", "no", "auto"]] = None,
    tcp_established_timeout: Optional[str] = None,
    tcp_syn_sent_timeout: Optional[str] = None,
    tcp_close_wait_timeout: Optional[str] = None,
    udp_timeout: Optional[str] = None,
    udp_stream_timeout: Optional[str] = None,
    icmp_timeout: Optional[str] = None,
    generic_timeout: Optional[str] = None,
    max_entries: Optional[Annotated[int, Field(ge=1024, le=10000000)]] = None,
    loose_tcp_tracking: Optional[Literal["yes", "no"]] = None,
    device: Optional[str] = None,
) -> str:
    """Updates global firewall connection tracking settings such as timeouts, capacity, and state handling."""
    await ctx.info("Updating connection tracking settings")

    updates = []
    if enabled is not None:
        updates.append(f"enabled={enabled}")
    if tcp_established_timeout is not None:
        if not _DURATION_RE.fullmatch(tcp_established_timeout):
            return f"Invalid tcp_established_timeout: '{tcp_established_timeout}'."
        updates.append(f"tcp-established-timeout={tcp_established_timeout}")
    if tcp_syn_sent_timeout is not None:
        if not _DURATION_RE.fullmatch(tcp_syn_sent_timeout):
            return f"Invalid tcp_syn_sent_timeout: '{tcp_syn_sent_timeout}'."
        updates.append(f"tcp-syn-sent-timeout={tcp_syn_sent_timeout}")
    if tcp_close_wait_timeout is not None:
        if not _DURATION_RE.fullmatch(tcp_close_wait_timeout):
            return f"Invalid tcp_close_wait_timeout: '{tcp_close_wait_timeout}'."
        updates.append(f"tcp-close-wait-timeout={tcp_close_wait_timeout}")
    if udp_timeout is not None:
        if not _DURATION_RE.fullmatch(udp_timeout):
            return f"Invalid udp_timeout: '{udp_timeout}'."
        updates.append(f"udp-timeout={udp_timeout}")
    if udp_stream_timeout is not None:
        if not _DURATION_RE.fullmatch(udp_stream_timeout):
            return f"Invalid udp_stream_timeout: '{udp_stream_timeout}'."
        updates.append(f"udp-stream-timeout={udp_stream_timeout}")
    if icmp_timeout is not None:
        if not _DURATION_RE.fullmatch(icmp_timeout):
            return f"Invalid icmp_timeout: '{icmp_timeout}'."
        updates.append(f"icmp-timeout={icmp_timeout}")
    if generic_timeout is not None:
        if not _DURATION_RE.fullmatch(generic_timeout):
            return f"Invalid generic_timeout: '{generic_timeout}'."
        updates.append(f"generic-timeout={generic_timeout}")
    if max_entries is not None:
        updates.append(f"max-entries={max_entries}")
    if loose_tcp_tracking is not None:
        updates.append(f"loose-tcp-tracking={loose_tcp_tracking}")

    if not updates:
        return "No connection tracking settings specified to update."

    cmd = "/ip firewall connection tracking set " + " ".join(updates)
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to update connection tracking settings: {result}"

    # Verify updated settings
    check_cmd = "/ip firewall connection tracking print"
    details = await execute_mikrotik_command(check_cmd, ctx, device=device)

    return f"Connection tracking settings updated successfully:\n\n{details}"


@mcp.tool(name="get_connection_tracking_count", annotations=annotate(READ, "Connection Tracking Count"))
async def mikrotik_get_connection_tracking_count(
    ctx: Context,
    protocol: Optional[Literal["tcp", "udp", "icmp", "gre", "ipsec-esp", "all"]] = None,
    tcp_state: Optional[Literal["established", "time-wait", "close", "syn-sent", "syn-received", "fin-wait", "close-wait", "last-ack"]] = None,
    src_address: Optional[str] = None,
    dst_address: Optional[str] = None,
    src_port: Optional[Annotated[int, Field(ge=1, le=65535)]] = None,
    dst_port: Optional[Annotated[int, Field(ge=1, le=65535)]] = None,
    device: Optional[str] = None,
) -> str:
    """Reports the total number of tracked firewall connections matching optional protocol, state, address, and port filters."""
    await ctx.info("Counting tracked firewall connections")

    try:
        filters = _build_filters(protocol, tcp_state, src_address, dst_address, src_port, dst_port)
    except ValueError as exc:
        return str(exc)

    cmd = "/ip firewall connection print count-only"
    if filters:
        cmd += " where " + " ".join(filters)

    result = await execute_mikrotik_command(cmd, ctx, device=device)
    count = result.strip()

    return f"FIREWALL CONNECTION COUNT:\n\n{count}"


@mcp.tool(name="list_firewall_connections", annotations=annotate(READ, "List Firewall Connections"))
async def mikrotik_list_firewall_connections(
    ctx: Context,
    protocol: Optional[Literal["tcp", "udp", "icmp", "gre", "ipsec-esp"]] = None,
    tcp_state: Optional[Literal["established", "time-wait", "close", "syn-sent", "syn-received", "fin-wait", "close-wait", "last-ack"]] = None,
    src_address: Optional[str] = None,
    dst_address: Optional[str] = None,
    src_port: Optional[Annotated[int, Field(ge=1, le=65535)]] = None,
    dst_port: Optional[Annotated[int, Field(ge=1, le=65535)]] = None,
    device: Optional[str] = None,
) -> str:
    """Lists active firewall connections with addresses, ports, protocol states, and transfer counters."""
    await ctx.info("Listing active firewall connections")

    try:
        filters = _build_filters(protocol, tcp_state, src_address, dst_address, src_port, dst_port)
    except ValueError as exc:
        return str(exc)

    cmd = "/ip firewall connection print detail"
    if filters:
        cmd += " where " + " ".join(filters)

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not has_item_rows(result):
        return "No firewall connections found matching the criteria."

    return f"FIREWALL CONNECTIONS:\n\n{_truncate_output(result)}"


@mcp.tool(name="remove_firewall_connections", annotations=annotate(DESTRUCTIVE, "Remove Firewall Connections"))
async def mikrotik_remove_firewall_connections(
    ctx: Context,
    src_address: Optional[str] = None,
    dst_address: Optional[str] = None,
    src_port: Optional[Annotated[int, Field(ge=1, le=65535)]] = None,
    dst_port: Optional[Annotated[int, Field(ge=1, le=65535)]] = None,
    protocol: Optional[Literal["tcp", "udp", "icmp", "gre", "ipsec-esp"]] = None,
    device: Optional[str] = None,
) -> str:
    """Terminates active firewall connections matching specific address, port, or protocol filters."""
    await ctx.info("Terminating active firewall connections")

    try:
        filters = _build_filters(protocol, None, src_address, dst_address, src_port, dst_port)
    except ValueError as exc:
        return str(exc)

    if not filters:
        return "At least one filter (src_address, dst_address, src_port, dst_port, protocol) must be specified to prevent clearing all connections."

    cmd = "/ip firewall connection remove [find where " + " ".join(filters) + "]"
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to remove connections: {result}"

    # Confirm remaining count matching filter
    count_cmd = "/ip firewall connection print count-only where " + " ".join(filters)
    remaining = (await execute_mikrotik_command(count_cmd, ctx, device=device)).strip()

    return f"Firewall connections terminated successfully. Remaining matching connections: {remaining}"
