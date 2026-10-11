from typing import Optional

from mcp.server.mcpserver import Context

from ..connector import execute_mikrotik_command
from ._selectors import resolve_item_id, item_count
from ..app import mcp, READ, WRITE, WRITE_IDEMPOTENT, DESTRUCTIVE, annotate


# ---------------------------------------------------------------------------
# WireGuard Interface Management
# ---------------------------------------------------------------------------

@mcp.tool(name="create_wireguard_interface", annotations=annotate(WRITE, "Create WireGuard Interface"))
async def mikrotik_create_wireguard_interface(
    ctx: Context,
    name: str,
    listen_port: Optional[int] = None,
    private_key: Optional[str] = None,
    mtu: Optional[int] = None,
    comment: Optional[str] = None,
    disabled: bool = False,
    device: Optional[str] = None,
) -> str:
    """Creates a WireGuard interface on the MikroTik device."""
    await ctx.info(f"Creating WireGuard interface: name={name}")

    cmd = f"/interface wireguard add name={name}"

    if listen_port is not None:
        cmd += f" listen-port={listen_port}"
    if private_key:
        cmd += f' private-key="{private_key}"'
    if mtu is not None:
        cmd += f" mtu={mtu}"
    if comment:
        cmd += f' comment="{comment}"'
    if disabled:
        cmd += " disabled=yes"

    result = await execute_mikrotik_command(
        cmd, ctx, device=device, redact=[private_key] if private_key else None
    )

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to create WireGuard interface: {result}"

    details_cmd = f'/interface wireguard print detail where name="{name}"'
    details = await execute_mikrotik_command(details_cmd, ctx, device=device)

    if details.strip():
        return f"WireGuard interface created successfully:\n\n{details}"
    return "WireGuard interface created successfully."


@mcp.tool(name="list_wireguard_interfaces", annotations=annotate(READ, "List WireGuard Interfaces"))
async def mikrotik_list_wireguard_interfaces(
    ctx: Context,
    name_filter: Optional[str] = None,
    disabled_only: bool = False,
    running_only: bool = False,
    device: Optional[str] = None,
) -> str:
    """Lists WireGuard interfaces on the MikroTik device."""
    await ctx.info("Listing WireGuard interfaces")

    cmd = "/interface wireguard print"

    filters = []
    if name_filter:
        filters.append(f'name~"{name_filter}"')
    if disabled_only:
        filters.append("disabled=yes")
    if running_only:
        filters.append("running=yes")

    if filters:
        cmd += " where " + " ".join(filters)

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result or result.strip() == "" or result.strip() == "no such item":
        return "No WireGuard interfaces found."

    return f"WIREGUARD INTERFACES:\n\n{result}"


@mcp.tool(name="get_wireguard_interface", annotations=annotate(READ, "Get WireGuard Interface"))
async def mikrotik_get_wireguard_interface(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Gets detailed information about a specific WireGuard interface."""
    await ctx.info(f"Getting WireGuard interface details: name={name}")

    cmd = f'/interface wireguard print detail where name="{name}"'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result or result.strip() == "":
        return f"WireGuard interface '{name}' not found."

    return f"WIREGUARD INTERFACE DETAILS:\n\n{result}"


@mcp.tool(name="update_wireguard_interface", annotations=annotate(WRITE_IDEMPOTENT, "Update WireGuard Interface"))
async def mikrotik_update_wireguard_interface(
    ctx: Context,
    name: str,
    new_name: Optional[str] = None,
    listen_port: Optional[int] = None,
    private_key: Optional[str] = None,
    mtu: Optional[int] = None,
    comment: Optional[str] = None,
    disabled: Optional[bool] = None,
    device: Optional[str] = None,
) -> str:
    """Updates an existing WireGuard interface's settings on the MikroTik device."""
    await ctx.info(f"Updating WireGuard interface: name={name}")

    updates = []
    if new_name:
        updates.append(f"name={new_name}")
    if listen_port is not None:
        updates.append(f"listen-port={listen_port}")
    if private_key:
        updates.append(f'private-key="{private_key}"')
    if mtu is not None:
        updates.append(f"mtu={mtu}")
    if comment is not None:
        updates.append(f'comment="{comment}"')
    if disabled is not None:
        updates.append(f'disabled={"yes" if disabled else "no"}')

    if not updates:
        return "No updates specified."

    cmd = f'/interface wireguard set [find name="{name}"] ' + " ".join(updates)
    result = await execute_mikrotik_command(
        cmd, ctx, device=device, redact=[private_key] if private_key else None
    )

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to update WireGuard interface: {result}"

    lookup_name = new_name if new_name else name
    details_cmd = f'/interface wireguard print detail where name="{lookup_name}"'
    details = await execute_mikrotik_command(details_cmd, ctx, device=device)

    return f"WireGuard interface updated successfully:\n\n{details}"


@mcp.tool(name="remove_wireguard_interface", annotations=annotate(DESTRUCTIVE, "Remove WireGuard Interface"))
async def mikrotik_remove_wireguard_interface(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Removes a WireGuard interface from the MikroTik device."""
    await ctx.info(f"Removing WireGuard interface: name={name}")

    check_cmd = f'/interface wireguard print count-only where name="{name}"'
    count = await execute_mikrotik_command(check_cmd, ctx, device=device)

    if count.strip() == "0":
        return f"WireGuard interface '{name}' not found."

    cmd = f'/interface wireguard remove [find name="{name}"]'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to remove WireGuard interface: {result}"

    return f"WireGuard interface '{name}' removed successfully."


@mcp.tool(name="enable_wireguard_interface", annotations=annotate(WRITE_IDEMPOTENT, "Enable WireGuard Interface"))
async def mikrotik_enable_wireguard_interface(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Enables a WireGuard interface."""
    await ctx.info(f"Enabling WireGuard interface: name={name}")

    cmd = f'/interface wireguard enable [find name="{name}"]'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to enable WireGuard interface: {result}"

    return f"WireGuard interface '{name}' enabled successfully."


@mcp.tool(name="disable_wireguard_interface", annotations=annotate(WRITE_IDEMPOTENT, "Disable WireGuard Interface"))
async def mikrotik_disable_wireguard_interface(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Disables a WireGuard interface."""
    await ctx.info(f"Disabling WireGuard interface: name={name}")

    cmd = f'/interface wireguard disable [find name="{name}"]'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to disable WireGuard interface: {result}"

    return f"WireGuard interface '{name}' disabled successfully."


# ---------------------------------------------------------------------------
# WireGuard Peer Management
# ---------------------------------------------------------------------------

@mcp.tool(name="add_wireguard_peer", annotations=annotate(WRITE, "Add WireGuard Peer"))
async def mikrotik_add_wireguard_peer(
    ctx: Context,
    interface: str,
    public_key: str,
    allowed_address: str,
    endpoint_address: Optional[str] = None,
    endpoint_port: Optional[int] = None,
    preshared_key: Optional[str] = None,
    persistent_keepalive: Optional[str] = None,
    comment: Optional[str] = None,
    disabled: bool = False,
    device: Optional[str] = None,
) -> str:
    """Adds a WireGuard peer (with public key and allowed addresses) to an interface on the MikroTik device.

    Notes:
        allowed_address: CIDR, comma-separated for multiple e.g. "10.0.0.2/32" or "10.0.0.0/24,192.168.0.0/24"
        endpoint_address: remote host IP or hostname e.g. "203.0.113.1"
        persistent_keepalive: seconds as string e.g. "25"
    """
    await ctx.info(f"Adding WireGuard peer: interface={interface}, public_key={public_key[:12]}...")

    cmd = (
        f'/interface wireguard peers add interface="{interface}"'
        f' public-key="{public_key}"'
        f' allowed-address="{allowed_address}"'
    )

    if endpoint_address:
        cmd += f' endpoint-address="{endpoint_address}"'
    if endpoint_port is not None:
        cmd += f" endpoint-port={endpoint_port}"
    if preshared_key:
        cmd += f' preshared-key="{preshared_key}"'
    if persistent_keepalive:
        cmd += f' persistent-keepalive={persistent_keepalive}'
    if comment:
        cmd += f' comment="{comment}"'
    if disabled:
        cmd += " disabled=yes"

    result = await execute_mikrotik_command(
        cmd, ctx, device=device, redact=[preshared_key] if preshared_key else None
    )

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to add WireGuard peer: {result}"

    details_cmd = (
        f'/interface wireguard peers print detail where'
        f' interface="{interface}" public-key="{public_key}"'
    )
    details = await execute_mikrotik_command(details_cmd, ctx, device=device)

    if details.strip():
        return f"WireGuard peer added successfully:\n\n{details}"
    return "WireGuard peer added successfully."


@mcp.tool(name="list_wireguard_peers", annotations=annotate(READ, "List WireGuard Peers"))
async def mikrotik_list_wireguard_peers(
    ctx: Context,
    interface_filter: Optional[str] = None,
    disabled_only: bool = False,
    device: Optional[str] = None,
) -> str:
    """Lists WireGuard peers on the MikroTik device."""
    await ctx.info("Listing WireGuard peers")

    cmd = "/interface wireguard peers print"

    filters = []
    if interface_filter:
        filters.append(f'interface="{interface_filter}"')
    if disabled_only:
        filters.append("disabled=yes")

    if filters:
        cmd += " where " + " ".join(filters)

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result or result.strip() == "" or result.strip() == "no such item":
        return "No WireGuard peers found."

    return f"WIREGUARD PEERS:\n\n{result}"


@mcp.tool(name="get_wireguard_peer", annotations=annotate(READ, "Get WireGuard Peer"))
async def mikrotik_get_wireguard_peer(ctx: Context, peer_id: str, device: Optional[str] = None) -> str:
    """Gets detailed information about a specific WireGuard peer by ID.

    Notes:
        peer_id: "*N" or "N" from list output e.g. "*2"
    """
    await ctx.info(f"Getting WireGuard peer details: peer_id={peer_id}")

    cmd = f"/interface wireguard peers print detail where .id={peer_id}"
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result or result.strip() == "":
        return f"WireGuard peer with ID '{peer_id}' not found."

    return f"WIREGUARD PEER DETAILS:\n\n{result}"


@mcp.tool(name="update_wireguard_peer", annotations=annotate(WRITE_IDEMPOTENT, "Update WireGuard Peer"))
async def mikrotik_update_wireguard_peer(
    ctx: Context,
    peer_id: str,
    allowed_address: Optional[str] = None,
    endpoint_address: Optional[str] = None,
    endpoint_port: Optional[int] = None,
    preshared_key: Optional[str] = None,
    persistent_keepalive: Optional[str] = None,
    comment: Optional[str] = None,
    disabled: Optional[bool] = None,
    device: Optional[str] = None,
) -> str:
    """Updates an existing WireGuard peer's allowed addresses, endpoint, keepalive, or enabled state.

    Notes:
        peer_id: "*N" or "N" from list output e.g. "*2"
        allowed_address: CIDR, comma-separated e.g. "10.0.0.2/32" or "10.0.0.0/24,192.168.0.0/24"
        persistent_keepalive: seconds as string e.g. "25"
        Pass "" for endpoint_address or preshared_key to clear them.
    """
    await ctx.info(f"Updating WireGuard peer: peer_id={peer_id}")

    updates = []
    if allowed_address is not None:
        updates.append(f'allowed-address="{allowed_address}"')
    if endpoint_address is not None:
        if endpoint_address == "":
            updates.append("!endpoint-address")
        else:
            updates.append(f'endpoint-address="{endpoint_address}"')
    if endpoint_port is not None:
        updates.append(f"endpoint-port={endpoint_port}")
    if preshared_key is not None:
        if preshared_key == "":
            updates.append("!preshared-key")
        else:
            updates.append(f'preshared-key="{preshared_key}"')
    if persistent_keepalive is not None:
        updates.append(f"persistent-keepalive={persistent_keepalive}")
    if comment is not None:
        updates.append(f'comment="{comment}"')
    if disabled is not None:
        updates.append(f'disabled={"yes" if disabled else "no"}')

    if not updates:
        return "No updates specified."

    cmd = f"/interface wireguard peers set {peer_id} " + " ".join(updates)
    result = await execute_mikrotik_command(
        cmd, ctx, device=device, redact=[preshared_key] if preshared_key else None
    )

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to update WireGuard peer: {result}"

    details_cmd = f"/interface wireguard peers print detail where .id={peer_id}"
    details = await execute_mikrotik_command(details_cmd, ctx, device=device)

    return f"WireGuard peer updated successfully:\n\n{details}"


@mcp.tool(name="remove_wireguard_peer", annotations=annotate(DESTRUCTIVE, "Remove WireGuard Peer"))
async def mikrotik_remove_wireguard_peer(ctx: Context, peer_id: str, device: Optional[str] = None) -> str:
    """Removes a WireGuard peer from the MikroTik device.

    Notes:
        peer_id: "*N" or "N" from list output e.g. "*2"
    """
    await ctx.info(f"Removing WireGuard peer: peer_id={peer_id}")

    menu = "/interface wireguard peers"
    resolved = await resolve_item_id(menu, peer_id, ctx, device, execute_mikrotik_command)
    if resolved is None:
        return f"WireGuard peer with ID '{peer_id}' not found."
    if await item_count(menu, resolved, ctx, device, execute_mikrotik_command) != "1":
        return f"WireGuard peer with ID '{peer_id}' not found."
    cmd = f"{menu} remove {resolved}"
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "no such item" in result.lower():
        return f"WireGuard peer with ID '{peer_id}' not found."
    if result.strip():
        return f"Failed to remove WireGuard peer: {result}"
    if await item_count(menu, resolved, ctx, device, execute_mikrotik_command) != "0":
        return f"Failed to remove WireGuard peer: peer '{peer_id}' is still present."

    return f"WireGuard peer '{peer_id}' removed successfully."


@mcp.tool(name="enable_wireguard_peer", annotations=annotate(WRITE_IDEMPOTENT, "Enable WireGuard Peer"))
async def mikrotik_enable_wireguard_peer(ctx: Context, peer_id: str, device: Optional[str] = None) -> str:
    """Enables a WireGuard peer.

    Notes:
        peer_id: "*N" or "N" from list output e.g. "*2"
    """
    await ctx.info(f"Enabling WireGuard peer: peer_id={peer_id}")

    cmd = f"/interface wireguard peers enable {peer_id}"
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to enable WireGuard peer: {result}"

    return f"WireGuard peer '{peer_id}' enabled successfully."


@mcp.tool(name="disable_wireguard_peer", annotations=annotate(WRITE_IDEMPOTENT, "Disable WireGuard Peer"))
async def mikrotik_disable_wireguard_peer(ctx: Context, peer_id: str, device: Optional[str] = None) -> str:
    """Disables a WireGuard peer.

    Notes:
        peer_id: "*N" or "N" from list output e.g. "*2"
    """
    await ctx.info(f"Disabling WireGuard peer: peer_id={peer_id}")

    cmd = f"/interface wireguard peers disable {peer_id}"
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to disable WireGuard peer: {result}"

    return f"WireGuard peer '{peer_id}' disabled successfully."


@mcp.tool(name="generate_wireguard_client_config", annotations=annotate(READ, "Generate WireGuard Client Config"))
async def mikrotik_generate_wireguard_client_config(
    ctx: Context,
    client_private_key: str,
    client_address: str,
    server_public_key: str,
    server_endpoint: str,
    server_port: int = 51820,
    allowed_ips: str = "0.0.0.0/0",
    dns: Optional[str] = None,
    persistent_keepalive: int = 25,
    device: Optional[str] = None,
) -> str:
    """Generates a wg0.conf client config string from the given keys and server endpoint. Does not communicate with the router."""
    await ctx.info("Generating WireGuard client configuration")

    lines = [
        "[Interface]",
        f"PrivateKey = {client_private_key}",
        f"Address = {client_address}",
    ]

    if dns:
        lines.append(f"DNS = {dns}")

    lines += [
        "",
        "[Peer]",
        f"PublicKey = {server_public_key}",
        f"Endpoint = {server_endpoint}:{server_port}",
        f"AllowedIPs = {allowed_ips}",
    ]

    if persistent_keepalive > 0:
        lines.append(f"PersistentKeepalive = {persistent_keepalive}")

    config_text = "\n".join(lines)

    return (
        "WIREGUARD CLIENT CONFIGURATION\n"
        "Save as /etc/wireguard/wg0.conf (Linux) or import into your WireGuard app:\n\n"
        f"{config_text}\n\n"
        "NEXT STEPS:\n"
        "1. Generate the client key-pair on the client device:\n"
        "     wg genkey | tee private.key | wg pubkey > public.key\n"
        "2. Replace 'PrivateKey' above with the content of private.key.\n"
        "3. Register the client's public key on the server with add_wireguard_peer,\n"
        f"   setting allowed_address to {client_address.split('/')[0]}/32.\n"
        "4. Bring the tunnel up:\n"
        "     wg-quick up wg0"
    )
