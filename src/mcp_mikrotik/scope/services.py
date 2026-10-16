"""Read-only view over `/ip service`: which management services answer, on
which port, and from where.

This is the device's remote-management attack surface in one table. The
`address` column is the part that matters: a service with no address
restriction answers anyone who can route to it, including from the internet
when the device has a public address.
"""

from typing import Optional

from mcp.server.mcpserver import Context

from ..app import mcp, READ, annotate
from ..connector import execute_mikrotik_command


@mcp.tool(name="list_ip_services", annotations=annotate(READ, "List IP Services"))
async def mikrotik_list_ip_services(
    ctx: Context,
    name_filter: Optional[str] = None,
    enabled_only: bool = False,
    device: Optional[str] = None
) -> str:
    """Lists the management services with their port and address restriction.

    Notes:
        `name_filter` is a substring match (`winbox`, `ssh`, `api`, `www`,
        `www-ssl`, `ftp`, `telnet`). `enabled_only=True` hides the disabled
        ones, which is the list that actually describes exposure.

        An empty `address` means unrestricted. Read that together with how the
        device is reached: unrestricted on a router whose WAN holds a public
        address means the service is published to the internet, whether or not
        the port was changed from its default.

        `ftp` deserves its own look: RouterOS also serves SFTP file transfers
        through the SSH service to users whose group holds the `ftp` policy,
        so the two are not the same control.
    """
    await ctx.info("Listing IP services")
    command = "/ip service print detail"
    filters = []
    if name_filter:
        filters.append(f'name~"{name_filter}"')
    if enabled_only:
        filters.append("disabled=no")
    if filters:
        command += " where " + " ".join(filters)

    result = await execute_mikrotik_command(command, ctx, device=device)
    if not result or "name=" not in result:
        return "No IP services found matching the criteria."
    return f"IP SERVICES:\n\n{result}"
