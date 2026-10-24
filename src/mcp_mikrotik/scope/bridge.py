import re
from typing import Annotated, Literal, Optional
from pydantic import Field
from ..connector import execute_mikrotik_command
from mcp.server.mcpserver import Context
from ..app import mcp, READ, WRITE, WRITE_IDEMPOTENT, DESTRUCTIVE, annotate

_VLAN = "/interface bridge vlan"
_PORT = "/interface bridge port"
_ID_RE = re.compile(r"\*[0-9A-Fa-f]+")
# A VLAN ID, a range, or a comma list of either: "10", "100-199", "10,20".
# Checked before the value reaches a where/find clause, where RouterOS would
# read anything after a space as a further condition.
_VLAN_IDS_RE = re.compile(r"\d{1,4}(?:-\d{1,4})?(?:,\d{1,4}(?:-\d{1,4})?)*")


def _bad_vlan_ids(value: str) -> Optional[str]:
    if _VLAN_IDS_RE.fullmatch(value):
        return None
    return (
        f"Error: invalid vlan_ids {value!r}: expected a VLAN ID, a range or a comma "
        'list of either, e.g. "10", "100-199", "10,20".'
    )


def _static(bridge: str, vlan_ids: str) -> str:
    # vlan-ids matches the stored list exactly: an entry holding "20,30" is
    # found by vlan-ids=20,30 and not by vlan-ids=20.
    return f'bridge="{bridge}" vlan-ids={vlan_ids} dynamic=no'


async def _count(menu: str, where: str, ctx: Context, device: Optional[str]) -> str:
    out = await execute_mikrotik_command(
        f"{menu} print count-only where {where}", ctx, device=device
    )
    return out.strip()


@mcp.tool(name="list_bridge_vlans", annotations=annotate(READ, "List Bridge VLANs"))
async def mikrotik_list_bridge_vlans(
    ctx: Context,
    bridge_filter: Optional[str] = None,
    vlan_ids_filter: Optional[str] = None,
    dynamic_only: bool = False,
    device: Optional[str] = None
) -> str:
    """Lists bridge VLAN table entries (tagged/untagged port membership per VLAN)."""
    if vlan_ids_filter and (error := _bad_vlan_ids(vlan_ids_filter)):
        return error

    await ctx.info(f"Listing bridge VLANs with filters: bridge={bridge_filter}, vlan_ids={vlan_ids_filter}")

    cmd = f"{_VLAN} print"

    filters = []
    if bridge_filter:
        filters.append(f'bridge="{bridge_filter}"')
    if vlan_ids_filter:
        filters.append(f"vlan-ids={vlan_ids_filter}")
    if dynamic_only:
        filters.append("dynamic=yes")

    if filters:
        cmd += " where " + " ".join(filters)

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result or result.strip() == "" or result.strip() == "no such item":
        return "No bridge VLAN entries found matching the criteria."

    return f"BRIDGE VLAN ENTRIES:\n\n{result}"


@mcp.tool(name="add_bridge_vlan", annotations=annotate(WRITE, "Add Bridge VLAN"))
async def mikrotik_add_bridge_vlan(
    ctx: Context,
    bridge: str,
    vlan_ids: str,
    tagged: Optional[str] = None,
    untagged: Optional[str] = None,
    comment: Optional[str] = None,
    disabled: bool = False,
    device: Optional[str] = None
) -> str:
    """Adds an entry to the bridge VLAN table defining tagged/untagged port membership.

    Notes:
        vlan_ids: single ID, comma list, or range e.g. "10", "10,20", "100-199"
        tagged: comma-separated ports carrying these VLANs tagged e.g. "ether1,ether2"
        untagged: comma-separated ports carrying these VLANs untagged
    """
    if error := _bad_vlan_ids(vlan_ids):
        return error

    await ctx.info(f"Adding bridge VLAN: bridge={bridge}, vlan_ids={vlan_ids}")

    cmd = f'{_VLAN} add bridge="{bridge}" vlan-ids={vlan_ids}'

    if tagged:
        cmd += f' tagged="{tagged}"'

    if untagged:
        cmd += f' untagged="{untagged}"'

    if comment:
        cmd += f' comment="{comment}"'

    if disabled:
        cmd += " disabled=yes"

    # :put echoes the new entry's *id. A refusal prints text instead, and not
    # every refusal says "failure:" -- a read-only account gets
    # "not enough permissions (9)", an unknown port "invalid value ...".
    result = await execute_mikrotik_command(f":put [{cmd}]", ctx, device=device)
    new_id = result.strip()
    if not _ID_RE.fullmatch(new_id):
        return f"Failed to add bridge VLAN entry: {new_id}"

    details = await execute_mikrotik_command(
        f"{_VLAN} print detail where .id={new_id}", ctx, device=device
    )
    return f"Bridge VLAN entry added successfully:\n\n{details}"


@mcp.tool(name="update_bridge_vlan", annotations=annotate(WRITE_IDEMPOTENT, "Update Bridge VLAN"))
async def mikrotik_update_bridge_vlan(
    ctx: Context,
    bridge: str,
    vlan_ids: str,
    new_vlan_ids: Optional[str] = None,
    tagged: Optional[str] = None,
    untagged: Optional[str] = None,
    comment: Optional[str] = None,
    disabled: Optional[bool] = None,
    device: Optional[str] = None
) -> str:
    """Updates an existing bridge VLAN table entry.

    Notes:
        vlan_ids: must match the stored value exactly (it is a list property)
            e.g. an entry created with "100-199" is matched by "100-199", not "150"
        tagged/untagged: comma-separated port lists; pass "" to clear the list
        Dynamic (D-flag) entries auto-created from PVIDs cannot be updated.
        A change is confirmed on the device before success is reported.
    """
    for value in (vlan_ids, new_vlan_ids):
        if value and (error := _bad_vlan_ids(value)):
            return error

    await ctx.info(f"Updating bridge VLAN: bridge={bridge}, vlan_ids={vlan_ids}")

    # Port lists are not asserted afterwards: RouterOS may store them in its
    # own order, so an exact-match check could fail a change that landed.
    updates, assertions = [], []
    if new_vlan_ids:
        updates.append(f"vlan-ids={new_vlan_ids}")
    if tagged is not None:
        updates.append(f'tagged="{tagged}"')
    if untagged is not None:
        updates.append(f'untagged="{untagged}"')
    if comment is not None:
        updates.append(f'comment="{comment}"')
        if comment:
            assertions.append(f'comment="{comment}"')
    if disabled is not None:
        state = "yes" if disabled else "no"
        updates.append(f"disabled={state}")
        assertions.append(f"disabled={state}")

    if not updates:
        return "No updates specified."

    where = _static(bridge, vlan_ids)
    # A set through a [find] that matches nothing succeeds silently.
    if await _count(_VLAN, where, ctx, device) == "0":
        return (
            f"Bridge VLAN entry bridge={bridge} vlan-ids={vlan_ids} not found "
            "(dynamic entries cannot be updated)."
        )

    result = await execute_mikrotik_command(
        f"{_VLAN} set [find {where}] " + " ".join(updates), ctx, device=device
    )

    # A successful set prints nothing; any output is the device refusing it.
    if result.strip():
        return f"Failed to update bridge VLAN entry: {result.strip()}"

    lookup = _static(bridge, new_vlan_ids or vlan_ids)
    if await _count(_VLAN, " ".join([lookup, *assertions]), ctx, device) == "0":
        return (
            "Failed to update bridge VLAN entry: the device reported no error but the "
            f"change is not present on bridge={bridge} vlan-ids={new_vlan_ids or vlan_ids}."
        )

    details = await execute_mikrotik_command(
        f"{_VLAN} print detail where {lookup}", ctx, device=device
    )
    return f"Bridge VLAN entry updated successfully:\n\n{details}"


@mcp.tool(name="remove_bridge_vlan", annotations=annotate(DESTRUCTIVE, "Remove Bridge VLAN"))
async def mikrotik_remove_bridge_vlan(
    ctx: Context,
    bridge: str,
    vlan_ids: str,
    device: Optional[str] = None
) -> str:
    """Removes an entry from the bridge VLAN table.

    Notes:
        vlan_ids: must match the stored value exactly (it is a list property)
    """
    if error := _bad_vlan_ids(vlan_ids):
        return error

    await ctx.info(f"Removing bridge VLAN: bridge={bridge}, vlan_ids={vlan_ids}")

    where = _static(bridge, vlan_ids)
    if await _count(_VLAN, where, ctx, device) == "0":
        return f"Bridge VLAN entry bridge={bridge} vlan-ids={vlan_ids} not found (dynamic entries cannot be removed)."

    result = await execute_mikrotik_command(f"{_VLAN} remove [find {where}]", ctx, device=device)

    if result.strip():
        return f"Failed to remove bridge VLAN entry: {result.strip()}"

    if await _count(_VLAN, where, ctx, device) != "0":
        return (
            "Failed to remove bridge VLAN entry: the device reported no error but "
            f"bridge={bridge} vlan-ids={vlan_ids} is still present."
        )

    return f"Bridge VLAN entry bridge={bridge} vlan-ids={vlan_ids} removed successfully."


@mcp.tool(name="list_bridge_ports", annotations=annotate(READ, "List Bridge Ports"))
async def mikrotik_list_bridge_ports(
    ctx: Context,
    bridge_filter: Optional[str] = None,
    interface_filter: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Lists bridge ports on the MikroTik device, including each port's PVID."""
    await ctx.info(f"Listing bridge ports with filters: bridge={bridge_filter}, interface={interface_filter}")

    cmd = f"{_PORT} print"

    filters = []
    if bridge_filter:
        filters.append(f'bridge="{bridge_filter}"')
    if interface_filter:
        filters.append(f'interface="{interface_filter}"')

    if filters:
        cmd += " where " + " ".join(filters)

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result or result.strip() == "" or result.strip() == "no such item":
        return "No bridge ports found matching the criteria."

    return f"BRIDGE PORTS:\n\n{result}"


@mcp.tool(name="update_bridge_port", annotations=annotate(WRITE_IDEMPOTENT, "Update Bridge Port"))
async def mikrotik_update_bridge_port(
    ctx: Context,
    interface: str,
    pvid: Optional[Annotated[int, Field(ge=1, le=4094)]] = None,
    frame_types: Optional[Literal["admit-all", "admit-only-untagged-and-priority-tagged", "admit-only-vlan-tagged"]] = None,
    ingress_filtering: Optional[bool] = None,
    device: Optional[str] = None
) -> str:
    """Updates per-port VLAN settings (PVID, frame types, ingress filtering) on a bridge port.

    Notes:
        interface: the port's interface name e.g. "ether2"; an interface can only
            belong to one bridge, so it uniquely identifies the bridge port
        pvid: VLAN ID assigned to untagged ingress traffic on this port
        A change is confirmed on the device before success is reported.
    """
    await ctx.info(f"Updating bridge port: interface={interface}")

    updates = []
    if pvid is not None:
        updates.append(f"pvid={pvid}")
    if frame_types:
        updates.append(f"frame-types={frame_types}")
    if ingress_filtering is not None:
        updates.append(f'ingress-filtering={"yes" if ingress_filtering else "no"}')

    if not updates:
        return "No updates specified."

    where = f'interface="{interface}"'
    # A set through a [find] that matches nothing succeeds silently.
    if await _count(_PORT, where, ctx, device) == "0":
        return f"Bridge port for interface '{interface}' not found."

    result = await execute_mikrotik_command(
        f"{_PORT} set [find {where}] " + " ".join(updates), ctx, device=device
    )

    # A successful set prints nothing; any output is the device refusing it.
    if result.strip():
        return f"Failed to update bridge port: {result.strip()}"

    # Every field here is a scalar, so all of them can be asserted.
    if await _count(_PORT, " ".join([where, *updates]), ctx, device) == "0":
        return (
            "Failed to update bridge port: the device reported no error but the new "
            f"values are not present on '{interface}'."
        )

    details = await execute_mikrotik_command(f"{_PORT} print detail where {where}", ctx, device=device)
    return f"Bridge port updated successfully:\n\n{details}"
