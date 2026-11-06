"""Tools for managing PPP, VPN tunnels (SSTP, OpenVPN, L2TP), secrets and active sessions."""

import ipaddress
import re
from typing import Annotated, Literal, Optional
from pydantic import Field

from mcp.server.mcpserver import Context

from ..app import mcp, READ, WRITE_IDEMPOTENT, DESTRUCTIVE, annotate
from ..connector import execute_mikrotik_command
from ._quoting import ros_quoted
from ._selectors import has_item_rows
from ..sensitive import redact_sensitive_text

_NAME_RE = re.compile(r"^[a-zA-Z0-9_.\-]+$")
_HOST_RE = re.compile(r"^[a-zA-Z0-9_.\-:]+$")

_SECRET_METADATA = (
    "name,service,profile,local-address,remote-address,comment,disabled,last-logged-out"
)


def _validate_ip_or_subnet(addr: str) -> bool:
    try:
        ipaddress.ip_network(addr.strip(), strict=False)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Active PPP Sessions (/ppp active)
# ---------------------------------------------------------------------------

@mcp.tool(name="list_ppp_active", annotations=annotate(READ, "List Active PPP Sessions"))
async def mikrotik_list_ppp_active(
    ctx: Context,
    service: Optional[Literal["any", "sstp", "ovpn", "l2tp", "pptp", "pppoe"]] = None,
    name: Optional[str] = None,
    device: Optional[str] = None,
) -> str:
    """Lists active PPP and VPN sessions with usernames, IPs, uptime and encoding."""
    await ctx.info("Listing active PPP sessions")

    cmd = "/ppp active print detail"
    filters = []
    if service and service != "any":
        filters.append(f"service={service}")
    if name:
        if not _NAME_RE.match(name):
            return f"Invalid username filter: '{name}'"
        filters.append(f'name~"{ros_quoted(name)}"')

    if filters:
        cmd += " where " + " ".join(filters)

    result = await execute_mikrotik_command(cmd, ctx, device=device)
    if not has_item_rows(result):
        return "No active PPP sessions found matching the criteria."

    return f"ACTIVE PPP SESSIONS:\n\n{result}"


@mcp.tool(name="get_ppp_active", annotations=annotate(READ, "Get Active PPP Session"))
async def mikrotik_get_ppp_active(
    ctx: Context,
    name: str,
    device: Optional[str] = None,
) -> str:
    """Gets detailed connection status and counters for a specific active PPP/VPN session."""
    if not _NAME_RE.match(name):
        return f"Invalid username: '{name}'"

    await ctx.info(f"Getting active PPP session: {name}")
    cmd = f'/ppp active print detail where name="{ros_quoted(name)}"'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not has_item_rows(result):
        return f"Active session for user '{name}' not found."

    return f"ACTIVE PPP SESSION ({name}):\n\n{result}"


@mcp.tool(name="disconnect_ppp_session", annotations=annotate(DESTRUCTIVE, "Disconnect PPP Session"))
async def mikrotik_disconnect_ppp_session(
    ctx: Context,
    name: str,
    device: Optional[str] = None,
) -> str:
    """Terminates an active PPP/VPN connection session by username."""
    if not _NAME_RE.match(name):
        return f"Invalid username: '{name}'"

    await ctx.info(f"Disconnecting PPP session: {name}")
    cmd = f'/ppp active remove [find name="{ros_quoted(name)}"]'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to disconnect PPP session: {result}"

    return f"PPP session '{name}' disconnected successfully."


# ---------------------------------------------------------------------------
# PPP User Accounts (/ppp secret)
# ---------------------------------------------------------------------------

@mcp.tool(name="list_ppp_secrets", annotations=annotate(READ, "List PPP Secrets"))
async def mikrotik_list_ppp_secrets(
    ctx: Context,
    service: Optional[Literal["any", "sstp", "ovpn", "l2tp", "pptp", "pppoe"]] = None,
    device: Optional[str] = None,
) -> str:
    """Lists configured PPP/VPN user accounts and assigned address configurations."""
    await ctx.info("Listing PPP secrets")

    cmd = f"/ppp secret print detail proplist={_SECRET_METADATA}"
    if service and service != "any":
        cmd += f" where service={service}"

    result = await execute_mikrotik_command(cmd, ctx, device=device)
    if not has_item_rows(result):
        return "No PPP secrets found."

    return f"PPP SECRETS:\n\n{redact_sensitive_text(result)}"


@mcp.tool(name="get_ppp_secret", annotations=annotate(READ, "Get PPP Secret"))
async def mikrotik_get_ppp_secret(
    ctx: Context,
    name: str,
    device: Optional[str] = None,
) -> str:
    """Gets detailed configuration for a specific PPP/VPN user account."""
    if not _NAME_RE.match(name):
        return f"Invalid username: '{name}'"

    await ctx.info(f"Getting PPP secret: {name}")
    cmd = f'/ppp secret print detail where name="{ros_quoted(name)}"'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not has_item_rows(result):
        return f"PPP secret for user '{name}' not found."

    return f"PPP SECRET ({name}):\n\n{redact_sensitive_text(result)}"


@mcp.tool(name="create_ppp_secret", annotations=annotate(WRITE_IDEMPOTENT, "Create PPP Secret"))
async def mikrotik_create_ppp_secret(
    ctx: Context,
    name: str,
    password: str,
    service: Literal["any", "sstp", "ovpn", "l2tp", "pptp", "pppoe"] = "any",
    profile: Optional[str] = None,
    local_address: Optional[str] = None,
    remote_address: Optional[str] = None,
    comment: Optional[str] = None,
    disabled: bool = False,
    device: Optional[str] = None,
) -> str:
    """Creates a new PPP/VPN user account with credentials and address properties."""
    if not _NAME_RE.match(name):
        return f"Invalid username: '{name}'"
    if local_address and not _validate_ip_or_subnet(local_address):
        return f"Invalid local_address: '{local_address}'"
    if remote_address and not _validate_ip_or_subnet(remote_address):
        return f"Invalid remote_address: '{remote_address}'"

    await ctx.info(f"Creating PPP secret: name={name}, service={service}")
    cmd = f'/ppp secret add name="{ros_quoted(name)}" password="{ros_quoted(password)}" service={service}'

    if profile:
        cmd += f' profile="{ros_quoted(profile)}"'
    if local_address:
        cmd += f' local-address="{ros_quoted(local_address)}"'
    if remote_address:
        cmd += f' remote-address="{ros_quoted(remote_address)}"'
    if comment:
        cmd += f' comment="{ros_quoted(comment)}"'
    if disabled:
        cmd += " disabled=yes"

    result = await execute_mikrotik_command(
        cmd, ctx, device=device, redact=[password] if password else None
    )
    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to create PPP secret: {result}"

    return f"PPP secret '{name}' created successfully."


@mcp.tool(name="update_ppp_secret", annotations=annotate(WRITE_IDEMPOTENT, "Update PPP Secret"))
async def mikrotik_update_ppp_secret(
    ctx: Context,
    name: str,
    password: Optional[str] = None,
    service: Optional[Literal["any", "sstp", "ovpn", "l2tp", "pptp", "pppoe"]] = None,
    profile: Optional[str] = None,
    local_address: Optional[str] = None,
    remote_address: Optional[str] = None,
    comment: Optional[str] = None,
    disabled: Optional[bool] = None,
    device: Optional[str] = None,
) -> str:
    """Updates an existing PPP/VPN user account's credentials, profile or addresses."""
    if not _NAME_RE.match(name):
        return f"Invalid username: '{name}'"
    if local_address and not _validate_ip_or_subnet(local_address):
        return f"Invalid local_address: '{local_address}'"
    if remote_address and not _validate_ip_or_subnet(remote_address):
        return f"Invalid remote_address: '{remote_address}'"

    updates = []
    if password is not None:
        updates.append(f'password="{ros_quoted(password)}"')
    if service is not None:
        updates.append(f"service={service}")
    if profile is not None:
        updates.append(f'profile="{ros_quoted(profile)}"')
    if local_address is not None:
        updates.append(f'local-address="{ros_quoted(local_address)}"')
    if remote_address is not None:
        updates.append(f'remote-address="{ros_quoted(remote_address)}"')
    if comment is not None:
        updates.append(f'comment="{ros_quoted(comment)}"')
    if disabled is not None:
        updates.append(f'disabled={"yes" if disabled else "no"}')

    if not updates:
        return "No updates specified."

    await ctx.info(f"Updating PPP secret: {name}")
    cmd = f'/ppp secret set [find name="{ros_quoted(name)}"] ' + " ".join(updates)
    result = await execute_mikrotik_command(
        cmd, ctx, device=device, redact=[password] if password else None
    )

    if "failure:" in result.lower() or "error" in result.lower() or "no such item" in result.lower():
        return f"Failed to update PPP secret: {result}"

    return f"PPP secret '{name}' updated successfully."


@mcp.tool(name="remove_ppp_secret", annotations=annotate(DESTRUCTIVE, "Remove PPP Secret"))
async def mikrotik_remove_ppp_secret(
    ctx: Context,
    name: str,
    device: Optional[str] = None,
) -> str:
    """Removes a configured PPP/VPN user account by name."""
    if not _NAME_RE.match(name):
        return f"Invalid username: '{name}'"

    await ctx.info(f"Removing PPP secret: {name}")
    cmd = f'/ppp secret remove [find name="{ros_quoted(name)}"]'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to remove PPP secret: {result}"

    return f"PPP secret '{name}' removed successfully."


@mcp.tool(name="list_ppp_profiles", annotations=annotate(READ, "List PPP Profiles"))
async def mikrotik_list_ppp_profiles(
    ctx: Context,
    device: Optional[str] = None,
) -> str:
    """Lists PPP/VPN profiles specifying encryption, DNS, limits and bridge assignments."""
    await ctx.info("Listing PPP profiles")
    cmd = "/ppp profile print detail"
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not has_item_rows(result):
        return "No PPP profiles found."

    return f"PPP PROFILES:\n\n{result}"


# ---------------------------------------------------------------------------
# Outgoing VPN Client Interfaces (/interface sstp/ovpn/l2tp-client)
# ---------------------------------------------------------------------------

@mcp.tool(name="list_vpn_clients", annotations=annotate(READ, "List VPN Clients"))
async def mikrotik_list_vpn_clients(
    ctx: Context,
    vpn_type: Literal["sstp", "ovpn", "l2tp"] = "sstp",
    device: Optional[str] = None,
) -> str:
    """Lists configured outgoing VPN client tunnel interfaces of the specified protocol."""
    await ctx.info(f"Listing {vpn_type.upper()} client interfaces")
    cmd = f"/interface {vpn_type}-client print detail"
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not has_item_rows(result):
        return f"No {vpn_type.upper()} client interfaces found."

    return f"{vpn_type.upper()} CLIENT INTERFACES:\n\n{redact_sensitive_text(result)}"


@mcp.tool(name="monitor_vpn_client", annotations=annotate(READ, "Monitor VPN Client"))
async def mikrotik_monitor_vpn_client(
    ctx: Context,
    name: str,
    vpn_type: Literal["sstp", "ovpn", "l2tp"] = "sstp",
    device: Optional[str] = None,
) -> str:
    """Takes a real-time status snapshot of an outgoing VPN client connection."""
    if not _NAME_RE.match(name):
        return f"Invalid client interface name: '{name}'"

    await ctx.info(f"Monitoring {vpn_type.upper()} client: {name}")
    cmd = f'/interface {vpn_type}-client monitor [find name="{ros_quoted(name)}"] once'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    stripped = result.strip()
    if not stripped or "status:" not in stripped:
        return f"{vpn_type.upper()} client '{name}' not found or monitor returned no status."

    return f"{vpn_type.upper()} CLIENT STATUS ({name}):\n\n{stripped}"


@mcp.tool(name="create_vpn_client", annotations=annotate(WRITE_IDEMPOTENT, "Create VPN Client"))
async def mikrotik_create_vpn_client(
    ctx: Context,
    name: str,
    connect_to: str,
    user: str,
    password: str,
    vpn_type: Literal["sstp", "ovpn", "l2tp"] = "sstp",
    port: Optional[Annotated[int, Field(ge=1, le=65535)]] = None,
    profile: Optional[str] = None,
    comment: Optional[str] = None,
    disabled: bool = False,
    device: Optional[str] = None,
) -> str:
    """Creates a new outgoing VPN client tunnel interface for SSTP, OpenVPN or L2TP."""
    if not _NAME_RE.match(name):
        return f"Invalid interface name: '{name}'"
    if not _HOST_RE.match(connect_to):
        return f"Invalid connect_to host: '{connect_to}'"

    await ctx.info(f"Creating {vpn_type.upper()} client: name={name}, connect-to={connect_to}")
    cmd = (
        f'/interface {vpn_type}-client add name="{ros_quoted(name)}" '
        f'connect-to="{ros_quoted(connect_to)}" user="{ros_quoted(user)}" '
        f'password="{ros_quoted(password)}"'
    )

    if port is not None:
        cmd += f" port={port}"
    if profile:
        cmd += f' profile="{ros_quoted(profile)}"'
    if comment:
        cmd += f' comment="{ros_quoted(comment)}"'
    if disabled:
        cmd += " disabled=yes"

    result = await execute_mikrotik_command(
        cmd, ctx, device=device, redact=[password] if password else None
    )
    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to create {vpn_type.upper()} client: {result}"

    return f"{vpn_type.upper()} client '{name}' created successfully."


@mcp.tool(name="update_vpn_client", annotations=annotate(WRITE_IDEMPOTENT, "Update VPN Client"))
async def mikrotik_update_vpn_client(
    ctx: Context,
    name: str,
    vpn_type: Literal["sstp", "ovpn", "l2tp"] = "sstp",
    connect_to: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    port: Optional[Annotated[int, Field(ge=1, le=65535)]] = None,
    profile: Optional[str] = None,
    comment: Optional[str] = None,
    disabled: Optional[bool] = None,
    device: Optional[str] = None,
) -> str:
    """Updates an existing outgoing VPN client tunnel interface settings."""
    if not _NAME_RE.match(name):
        return f"Invalid interface name: '{name}'"
    if connect_to and not _HOST_RE.match(connect_to):
        return f"Invalid connect_to host: '{connect_to}'"

    updates = []
    if connect_to is not None:
        updates.append(f'connect-to="{ros_quoted(connect_to)}"')
    if user is not None:
        updates.append(f'user="{ros_quoted(user)}"')
    if password is not None:
        updates.append(f'password="{ros_quoted(password)}"')
    if port is not None:
        updates.append(f"port={port}")
    if profile is not None:
        updates.append(f'profile="{ros_quoted(profile)}"')
    if comment is not None:
        updates.append(f'comment="{ros_quoted(comment)}"')
    if disabled is not None:
        updates.append(f'disabled={"yes" if disabled else "no"}')

    if not updates:
        return "No updates specified."

    await ctx.info(f"Updating {vpn_type.upper()} client: {name}")
    cmd = f'/interface {vpn_type}-client set [find name="{ros_quoted(name)}"] ' + " ".join(updates)
    result = await execute_mikrotik_command(
        cmd, ctx, device=device, redact=[password] if password else None
    )

    if "failure:" in result.lower() or "error" in result.lower() or "no such item" in result.lower():
        return f"Failed to update {vpn_type.upper()} client: {result}"

    return f"{vpn_type.upper()} client '{name}' updated successfully."


@mcp.tool(name="remove_vpn_client", annotations=annotate(DESTRUCTIVE, "Remove VPN Client"))
async def mikrotik_remove_vpn_client(
    ctx: Context,
    name: str,
    vpn_type: Literal["sstp", "ovpn", "l2tp"] = "sstp",
    device: Optional[str] = None,
) -> str:
    """Removes an outgoing VPN client tunnel interface by name."""
    if not _NAME_RE.match(name):
        return f"Invalid interface name: '{name}'"

    await ctx.info(f"Removing {vpn_type.upper()} client: {name}")
    cmd = f'/interface {vpn_type}-client remove [find name="{ros_quoted(name)}"]'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to remove {vpn_type.upper()} client: {result}"

    return f"{vpn_type.upper()} client '{name}' removed successfully."


# ---------------------------------------------------------------------------
# VPN Server Settings (/interface sstp/ovpn/l2tp-server server)
# ---------------------------------------------------------------------------

@mcp.tool(name="get_vpn_server_settings", annotations=annotate(READ, "Get VPN Server Settings"))
async def mikrotik_get_vpn_server_settings(
    ctx: Context,
    vpn_type: Literal["sstp", "ovpn", "l2tp"] = "sstp",
    device: Optional[str] = None,
) -> str:
    """Inspects the VPN server listening configuration, ciphers and status."""
    await ctx.info(f"Getting {vpn_type.upper()} server settings")

    cmd = f"/interface {vpn_type}-server server print"
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result.strip():
        return f"No {vpn_type.upper()} server configuration found."

    return f"{vpn_type.upper()} SERVER SETTINGS:\n\n{result.strip()}"


@mcp.tool(name="update_vpn_server_settings", annotations=annotate(WRITE_IDEMPOTENT, "Update VPN Server Settings"))
async def mikrotik_update_vpn_server_settings(
    ctx: Context,
    vpn_type: Literal["sstp", "ovpn", "l2tp"] = "sstp",
    enabled: Optional[bool] = None,
    port: Optional[Annotated[int, Field(ge=1, le=65535)]] = None,
    default_profile: Optional[str] = None,
    certificate: Optional[str] = None,
    device: Optional[str] = None,
) -> str:
    """Updates VPN server listening properties, enabled status and default profiles."""
    updates = []
    if enabled is not None:
        updates.append(f'enabled={"yes" if enabled else "no"}')
    if port is not None:
        updates.append(f"port={port}")
    if default_profile is not None:
        updates.append(f'default-profile="{ros_quoted(default_profile)}"')
    if certificate is not None:
        updates.append(f'certificate="{ros_quoted(certificate)}"')

    if not updates:
        return "No updates specified."

    await ctx.info(f"Updating {vpn_type.upper()} server settings")
    cmd = f"/interface {vpn_type}-server server set " + " ".join(updates)
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to update {vpn_type.upper()} server settings: {result}"

    return f"{vpn_type.upper()} server settings updated successfully."
