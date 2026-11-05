import ipaddress
from typing import Optional

from ..connector import execute_mikrotik_command
from ._quoting import ros_quoted
from mcp.server.mcpserver import Context
from ..app import mcp, READ, WRITE, DESTRUCTIVE, annotate


def _canonical_ipv6(value: str) -> str:
    """Return the RouterOS-canonical form of an IPv6 address or address/prefix.

    RouterOS stores IPv6 addresses lowercase and maximally zero-compressed
    (e.g. ``2001:db8::1/64``). User input may be uppercase or expanded
    (``2001:DB8:0:0::1/64``), which would not match an exact ``where address=``
    comparison and cause a spurious "not found". Canonicalizing the input makes
    the match reliable. Returns the input unchanged if it is not parseable as
    IPv6 (e.g. a RouterOS ``.id`` like ``*1``).
    """
    try:
        if "/" in value:
            return str(ipaddress.ip_interface(value))
        return str(ipaddress.ip_address(value))
    except ValueError:
        return value


@mcp.tool(name="add_ipv6_address", annotations=annotate(WRITE, "Add IPv6 Address"))
async def mikrotik_add_ipv6_address(
    ctx: Context,
    address: str,
    interface: str,
    advertise: Optional[bool] = None,
    eui_64: Optional[bool] = None,
    from_pool: Optional[str] = None,
    no_dad: Optional[bool] = None,
    comment: Optional[str] = None,
    disabled: bool = False,
    device: Optional[str] = None,
) -> str:
    """Adds an IPv6 address to an interface on the MikroTik device.

    Notes:
        address: IPv6 address with prefix length, e.g. "2001:db8::1/64" or
            "fe80::1/64". When `from_pool` is used, supply the host part only,
            e.g. "::1/64".
        advertise: include this prefix in Router Advertisements (default no).
        eui_64: derive the host part of the address from the interface MAC.
        from_pool: name of an IPv6 pool to take the prefix from.
        no_dad: skip Duplicate Address Detection.
    """
    await ctx.info(f"Adding IPv6 address: address={address}, interface={interface}")

    cmd = f"/ipv6 address add address={address} interface={interface}"

    if advertise is not None:
        cmd += f" advertise={'yes' if advertise else 'no'}"
    if eui_64:
        cmd += " eui-64=yes"
    if from_pool:
        cmd += f' from-pool="{from_pool}"'
    if no_dad:
        cmd += " no-dad=yes"
    if comment:
        cmd += f' comment="{ros_quoted(comment)}"'
    if disabled:
        cmd += " disabled=yes"

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to add IPv6 address: {result}"

    # Confirm by listing the interface's addresses. We deliberately query by
    # interface (not by the input address): with from_pool the stored prefix
    # comes from the pool, and with eui_64 the host part is derived from the
    # MAC — in both cases the stored address differs from the input, so a
    # by-address lookup would miss the very entry we just created.
    details_cmd = f'/ipv6 address print detail where interface="{interface}"'
    details = await execute_mikrotik_command(details_cmd, ctx, device=device)

    if details.strip() and "address=" in details:
        return f"IPv6 address added successfully (addresses on {interface}):\n\n{details}"
    return f"IPv6 address '{address}' added on interface '{interface}'."


@mcp.tool(name="list_ipv6_addresses", annotations=annotate(READ, "List IPv6 Addresses"))
async def mikrotik_list_ipv6_addresses(
    ctx: Context,
    interface_filter: Optional[str] = None,
    address_filter: Optional[str] = None,
    disabled_only: bool = False,
    dynamic_only: bool = False,
    global_only: bool = False,
    link_local_only: bool = False,
    device: Optional[str] = None,
) -> str:
    """Lists IPv6 addresses on the MikroTik device.

    Notes:
        address_filter: partial match on the address, e.g. "2001:db8" or "fe80".
        global_only: show only global (routable) addresses.
        link_local_only: show only link-local (fe80::/10) addresses.
    """
    await ctx.info(
        f"Listing IPv6 addresses with filters: interface={interface_filter}, address={address_filter}"
    )

    cmd = "/ipv6 address print"

    filters = []
    if interface_filter:
        filters.append(f'interface="{interface_filter}"')
    if address_filter:
        filters.append(f'address~"{address_filter}"')
    if disabled_only:
        filters.append("disabled=yes")
    if dynamic_only:
        filters.append("dynamic=yes")
    if global_only:
        filters.append("global=yes")
    if link_local_only:
        filters.append("link-local=yes")

    if filters:
        cmd += " where " + " ".join(filters)

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result or result.strip() == "":
        return "No IPv6 addresses found matching the criteria."

    return f"IPV6 ADDRESSES:\n\n{result}"


@mcp.tool(name="get_ipv6_address", annotations=annotate(READ, "Get IPv6 Address"))
async def mikrotik_get_ipv6_address(
    ctx: Context, address_id: str, device: Optional[str] = None
) -> str:
    """Gets detailed information about a specific IPv6 address by ID or address value.

    Notes:
        address_id: a RouterOS internal id (e.g. "*1") or the address value
            (e.g. "2001:db8::1/64").
    """
    await ctx.info(f"Getting IPv6 address details: address_id={address_id}")

    # An IPv6 address value always contains ':'; a RouterOS internal id looks
    # like "*1". Query by the matching attribute first. We validate on the
    # presence of real entry data ("address=") rather than non-emptiness,
    # because `print detail` returns the Flags legend (non-empty) even when no
    # row matches — so an emptiness check would yield a header with no entry.
    addr = _canonical_ipv6(address_id)
    if ":" in address_id:
        queries = [f'address="{addr}"', f'.id="{address_id}"']
    else:
        queries = [f'.id="{address_id}"', f'address="{addr}"']

    for where in queries:
        result = await execute_mikrotik_command(
            f"/ipv6 address print detail where {where}", ctx, device=device
        )
        if result and "address=" in result:
            return f"IPV6 ADDRESS DETAILS:\n\n{result}"

    return f"IPv6 address '{address_id}' not found."


@mcp.tool(name="remove_ipv6_address", annotations=annotate(DESTRUCTIVE, "Remove IPv6 Address"))
async def mikrotik_remove_ipv6_address(
    ctx: Context, address_id: str, device: Optional[str] = None
) -> str:
    """Removes an IPv6 address from the MikroTik device by ID or address value.

    Notes:
        address_id: a RouterOS internal id (e.g. "*1") or the address value
            (e.g. "2001:db8::1/64").
    """
    await ctx.info(f"Removing IPv6 address: address_id={address_id}")

    addr = _canonical_ipv6(address_id)

    # Try to find by ID first
    check_cmd = f'/ipv6 address print count-only where .id="{address_id}"'
    count = await execute_mikrotik_command(check_cmd, ctx, device=device)

    if count.strip() == "0":
        # Try finding by (canonicalized) address value
        check_cmd = f'/ipv6 address print count-only where address="{addr}"'
        count = await execute_mikrotik_command(check_cmd, ctx, device=device)

        if count.strip() == "0":
            return f"IPv6 address '{address_id}' not found."

        cmd = f'/ipv6 address remove [find address="{addr}"]'
    else:
        cmd = f'/ipv6 address remove [find .id="{address_id}"]'

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to remove IPv6 address: {result}"

    return f"IPv6 address '{address_id}' removed successfully."
