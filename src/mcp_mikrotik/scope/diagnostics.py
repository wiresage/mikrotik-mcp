"""Bounded diagnostic commands: ping, traceroute, torch, quick packet capture and CPU profile.

None of these change the configuration, so they are annotated READ and stay available with
``--read-only``. They do need RouterOS policies beyond ``read``: ``test`` for ping and traceroute,
``sniff`` for torch and the packet sniffer (and ``read`` for all of them). A refusal from the router
("not enough permissions") is returned as is.

Every command here is bounded so that it ends on its own in a non-interactive session: ping and
traceroute take a ``count``, torch, the sniffer and the profiler a ``duration``. The commands that
redraw a table on every refresh print one frame per second when there is no terminal, so only the
last frame is returned (``_last_frame``). They also lay their tables out for 80 columns and drop
the columns that do not fit (torch loses its rates), so the connection asks for a wider console.

All values are model-controlled. Names (interfaces, routing tables) are sent quoted through
``ros_quoted``; everything else must match a narrow pattern before a command is built.
"""

import re
from typing import Annotated, Literal, Optional

from mcp.server.mcpserver import Context
from mcp.types import ToolAnnotations
from pydantic import Field

from ..app import mcp, READ, annotate
from ..connector import execute_mikrotik_command
from ._quoting import ros_quoted

# These tools reach hosts outside the router (ping, traceroute) or observe live traffic; they
# change nothing on the device, so they keep READ's read_only_hint, but they are open-world.
_DIAG = ToolAnnotations(read_only_hint=True, idempotent_hint=False, open_world_hint=True)

_HOST_RE = re.compile(r"[A-Za-z0-9:][A-Za-z0-9.:%\-]{0,252}")
_PREFIX_RE = re.compile(r"[0-9A-Fa-f.:]+(/\d{1,3})?")
_PORT_RE = re.compile(r"any|\d{1,5}")
_PORTS_RE = re.compile(r"\d{1,5}(-\d{1,5})?(,\d{1,5}(-\d{1,5})?)*")
_PROTO_RE = re.compile(r"any|[a-z][a-z0-9\-]{0,20}|\d{1,3}")
_MAC_RE = re.compile(r"[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}(/[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5})?")
_INTERVAL_RE = re.compile(r"\d{1,4}(ms|s)?")
_CPU_RE = re.compile(r"any|all|total|\d{1,3}")

MAX_OUTPUT_LINES = 300
# Wide enough for torch with IPv6 addresses, ports and the four rate columns.
TERMINAL_WIDTH = 250


class _Invalid(ValueError):
    pass


def _check(name: str, value: Optional[str], pattern: re.Pattern) -> Optional[str]:
    if value is None or value == "":
        return None
    value = value.strip()
    if not pattern.fullmatch(value):
        raise _Invalid(f"invalid {name} {value!r}")
    return value


def _last_frame(output: str) -> str:
    """Keep only the last redraw of a command that reprints its table on every refresh.

    Without a terminal RouterOS prints each refresh one after the other. RouterOS 7 starts every
    frame with a "Columns: ..." line, whose content can change between frames (a column appears or
    goes away as the data changes width), so the text after the last such line is the final state.
    Output without that marker falls back to the first non-empty line repeating.
    """
    lines = output.replace("\r", "").split("\n")
    starts = [i for i, line in enumerate(lines) if line.startswith("Columns:")]
    if not starts:
        header = next((line for line in lines if line.strip()), None)
        if header is None:
            return output
        starts = [i for i, line in enumerate(lines) if line == header]
    frame = lines[starts[-1]:] if len(starts) > 1 else lines
    return "\n".join(frame).strip("\n")


def _truncate(text: str) -> str:
    lines = text.split("\n")
    if len(lines) <= MAX_OUTPUT_LINES:
        return text
    hidden = len(lines) - MAX_OUTPUT_LINES
    return "\n".join(lines[:MAX_OUTPUT_LINES]) + f"\n... ({hidden} more lines not shown)"


def _refused(result: str) -> bool:
    text = result.strip().lower()
    return (
        not text
        or "not enough permissions" in text
        or text.startswith(("failure", "error", "syntax error", "expected", "bad command", "no such"))
        or "input does not match" in text
        or text.startswith("invalid value")
    )


async def _run(ctx: Context, what: str, cmd: str, device: Optional[str], last_frame: bool) -> str:
    result = await execute_mikrotik_command(cmd, ctx, device=device, terminal_width=TERMINAL_WIDTH)
    if _refused(result):
        return f"Failed to run {what}: {result.strip() or 'no output'}"
    text = _last_frame(result) if last_frame else result.replace("\r", "").strip("\n")
    return f"{what.upper()} RESULT:\n\n{_truncate(text)}"


@mcp.tool(name="ping", annotations=annotate(_DIAG, "Ping"))
async def mikrotik_ping(
    ctx: Context,
    address: str,
    count: Annotated[int, Field(ge=1, le=20)] = 4,
    size: Optional[Annotated[int, Field(ge=14, le=65535)]] = None,
    interval: Optional[str] = None,
    src_address: Optional[str] = None,
    interface: Optional[str] = None,
    routing_table: Optional[str] = None,
    ttl: Optional[Annotated[int, Field(ge=1, le=255)]] = None,
    do_not_fragment: bool = False,
    arp_ping: bool = False,
    device: Optional[str] = None,
) -> str:
    """Pings an IPv4/IPv6 address or host name from the router (needs the "test" policy).

    Notes:
        interval: e.g. "200ms" or "1s". arp_ping=True sends ARP requests instead of ICMP and needs interface.
        do_not_fragment with size finds the path MTU.
    """
    await ctx.info(f"Ping {address} count={count}")
    try:
        address = _check("address", address, _HOST_RE)
        interval = _check("interval", interval, _INTERVAL_RE)
        src_address = _check("src_address", src_address, _HOST_RE)
    except _Invalid as exc:
        return f"Failed to run ping: {exc}"
    if not address:
        return "Failed to run ping: address is required."
    if arp_ping and not interface:
        return "Failed to run ping: arp_ping needs interface."

    parts = [f"/ping address={address} count={count}"]
    if size:
        parts.append(f"size={size}")
    if interval:
        parts.append(f"interval={interval}")
    if src_address:
        parts.append(f"src-address={src_address}")
    if interface:
        parts.append(f'interface="{ros_quoted(interface)}"')
    if routing_table:
        parts.append(f'routing-table="{ros_quoted(routing_table)}"')
    if ttl:
        parts.append(f"ttl={ttl}")
    if do_not_fragment:
        parts.append("do-not-fragment")
    if arp_ping:
        parts.append("arp-ping=yes")
    return await _run(ctx, "ping", " ".join(parts), device, last_frame=False)


@mcp.tool(name="traceroute", annotations=annotate(_DIAG, "Traceroute"))
async def mikrotik_traceroute(
    ctx: Context,
    address: str,
    count: Annotated[int, Field(ge=1, le=5)] = 1,
    max_hops: Annotated[int, Field(ge=1, le=64)] = 30,
    protocol: Literal["icmp", "udp"] = "icmp",
    port: Optional[Annotated[int, Field(ge=1, le=65535)]] = None,
    size: Optional[Annotated[int, Field(ge=28, le=1500)]] = None,
    timeout: Optional[str] = None,
    src_address: Optional[str] = None,
    interface: Optional[str] = None,
    routing_table: Optional[str] = None,
    use_dns: bool = False,
    device: Optional[str] = None,
) -> str:
    """Traces the route from the router to an IPv4/IPv6 address or host name (needs the "test" policy).

    Notes:
        count: probes per hop; the run takes roughly count x hops x timeout at worst.
        timeout: per-probe timeout, e.g. "500ms" or "1s". port applies to protocol="udp".
    """
    await ctx.info(f"Traceroute {address} max_hops={max_hops}")
    try:
        address = _check("address", address, _HOST_RE)
        timeout = _check("timeout", timeout, _INTERVAL_RE)
        src_address = _check("src_address", src_address, _HOST_RE)
    except _Invalid as exc:
        return f"Failed to run traceroute: {exc}"
    if not address:
        return "Failed to run traceroute: address is required."

    parts = [f"/tool traceroute address={address} count={count} max-hops={max_hops} protocol={protocol}"]
    if port and protocol == "udp":
        parts.append(f"port={port}")
    if size:
        parts.append(f"size={size}")
    if timeout:
        parts.append(f"timeout={timeout}")
    if src_address:
        parts.append(f"src-address={src_address}")
    if interface:
        parts.append(f'interface="{ros_quoted(interface)}"')
    if routing_table:
        parts.append(f'routing-table="{ros_quoted(routing_table)}"')
    parts.append(f"use-dns={'yes' if use_dns else 'no'}")
    return await _run(ctx, "traceroute", " ".join(parts), device, last_frame=True)


@mcp.tool(name="torch", annotations=annotate(_DIAG, "Torch"))
async def mikrotik_torch(
    ctx: Context,
    interface: str,
    duration: Annotated[int, Field(ge=1, le=30)] = 5,
    src_address: Optional[str] = None,
    dst_address: Optional[str] = None,
    src_address6: Optional[str] = None,
    dst_address6: Optional[str] = None,
    ip_protocol: Optional[str] = None,
    port: Optional[str] = None,
    mac_protocol: Optional[str] = None,
    vlan_id: Optional[str] = None,
    dscp: Optional[str] = None,
    device: Optional[str] = None,
) -> str:
    """Shows live traffic rates per flow on an interface for a few seconds (needs the "sniff" policy).

    Notes:
        Each filter both filters and breaks the table down by that field: "0.0.0.0/0" (or "::/0") lists
        every address, "any" every protocol/port/VLAN/DSCP. With no filter, flows are broken down by
        IPv4 src/dst address and IP protocol. Torch turns off fasttrack while it runs (higher CPU).
    """
    await ctx.info(f"Torch on {interface} for {duration}s")
    try:
        src_address = _check("src_address", src_address, _PREFIX_RE)
        dst_address = _check("dst_address", dst_address, _PREFIX_RE)
        src_address6 = _check("src_address6", src_address6, _PREFIX_RE)
        dst_address6 = _check("dst_address6", dst_address6, _PREFIX_RE)
        ip_protocol = _check("ip_protocol", ip_protocol, _PROTO_RE)
        port = _check("port", port, _PORT_RE)
        mac_protocol = _check("mac_protocol", mac_protocol, _PROTO_RE)
        vlan_id = _check("vlan_id", vlan_id, _PORT_RE)
        dscp = _check("dscp", dscp, _PORT_RE)
    except _Invalid as exc:
        return f"Failed to run torch: {exc}"

    filters = {
        "src-address": src_address, "dst-address": dst_address,
        "src-address6": src_address6, "dst-address6": dst_address6,
        "ip-protocol": ip_protocol, "port": port, "mac-protocol": mac_protocol,
        "vlan-id": vlan_id, "dscp": dscp,
    }
    if not any(filters.values()):
        filters.update({"src-address": "0.0.0.0/0", "dst-address": "0.0.0.0/0", "ip-protocol": "any"})

    parts = [f'/tool torch interface="{ros_quoted(interface)}" duration={duration}s']
    parts += [f"{key}={value}" for key, value in filters.items() if value]
    return await _run(ctx, "torch", " ".join(parts), device, last_frame=True)


@mcp.tool(name="sniff_packets", annotations=annotate(_DIAG, "Quick Packet Capture"))
async def mikrotik_sniff_packets(
    ctx: Context,
    interface: Optional[str] = None,
    duration: Annotated[int, Field(ge=1, le=30)] = 5,
    ip_address: Optional[str] = None,
    ip_protocol: Optional[str] = None,
    port: Optional[str] = None,
    mac_address: Optional[str] = None,
    device: Optional[str] = None,
) -> str:
    """Captures packet headers for a few seconds with the quick packet sniffer (needs the "sniff" policy).

    Notes:
        Shows headers only (interface, direction, MACs, addresses, protocol, size); nothing is saved on
        the router. ip_address matches source or destination. port: "53", "80,443" or "1000-2000".
    """
    await ctx.info(f"Quick sniff on {interface or 'all interfaces'} for {duration}s")
    try:
        ip_address = _check("ip_address", ip_address, _PREFIX_RE)
        ip_protocol = _check("ip_protocol", ip_protocol, _PROTO_RE)
        port = _check("port", port, _PORTS_RE)
        mac_address = _check("mac_address", mac_address, _MAC_RE)
    except _Invalid as exc:
        return f"Failed to run packet capture: {exc}"

    parts = [f"/tool sniffer quick duration={duration}s"]
    if interface:
        parts.append(f'interface="{ros_quoted(interface)}"')
    if ip_address:
        parts.append(f"ip-address={ip_address}")
    if ip_protocol:
        parts.append(f"ip-protocol={ip_protocol}")
    if port:
        parts.append(f"port={port}")
    if mac_address:
        parts.append(f"mac-address={mac_address}")
    return await _run(ctx, "packet capture", " ".join(parts), device, last_frame=True)


@mcp.tool(name="profile_cpu", annotations=annotate(READ, "CPU Profile"))
async def mikrotik_profile_cpu(
    ctx: Context,
    duration: Annotated[int, Field(ge=1, le=30)] = 5,
    cpu: Optional[str] = None,
    device: Optional[str] = None,
) -> str:
    """Shows which RouterOS processes use the CPU, sampled over a few seconds.

    Notes:
        cpu: "total" (default), "all" for one column per core, or a core number.
    """
    await ctx.info(f"CPU profile for {duration}s")
    try:
        cpu = _check("cpu", cpu, _CPU_RE)
    except _Invalid as exc:
        return f"Failed to run CPU profile: {exc}"
    cmd = f"/tool profile duration={duration}s"
    if cpu:
        cmd += f" cpu={cpu}"
    return await _run(ctx, "CPU profile", cmd, device, last_frame=True)
