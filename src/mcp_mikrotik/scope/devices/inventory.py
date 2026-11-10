from mcp.server.mcpserver import Context

from ...app import mcp, READ, annotate
from ...inventory import get_inventory


@mcp.tool(name="list_devices", annotations=annotate(READ, "List Devices"))
async def mikrotik_list_devices(ctx: Context) -> str:
    """Lists the MikroTik devices this server manages.

    Use this to discover which devices are available and what their titles are.
    Every other tool takes an optional `device` argument that must be one of the
    titles returned here. When only one device is configured, `device` may be
    omitted and that device is used automatically.

    Credentials are never returned.
    """
    await ctx.info("Listing inventory devices")

    inventory = get_inventory()
    devices = inventory.describe()

    if not devices:
        return "No MikroTik devices are configured."

    lines = [f"MIKROTIK DEVICES ({len(devices)}):", ""]
    for d in devices:
        parts = [f"  title: {d['title']}", f"host: {d['host']}:{d['port']}", f"user: {d['username']}"]
        if d.get("region"):
            parts.append(f"region: {d['region']}")
        if d.get("tags"):
            parts.append(f"tags: {', '.join(d['tags'])}")
        lines.append(" | ".join(parts))

    if len(devices) == 1:
        lines.append("")
        lines.append(
            "Only one device is configured, so the `device` argument can be omitted."
        )
    else:
        lines.append("")
        lines.append(
            "Multiple devices are configured — pass the chosen title as the "
            "`device` argument of each tool."
        )

    return "\n".join(lines)
