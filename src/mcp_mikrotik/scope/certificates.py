"""Tools for managing RouterOS SSL/TLS certificates, CA templates, and ACME (Let's Encrypt)."""

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
_DOMAIN_RE = re.compile(r"^[a-zA-Z0-9_.\-]+$")


# ---------------------------------------------------------------------------
# Certificate Inspection & Expiry Monitoring
# ---------------------------------------------------------------------------

@mcp.tool(name="list_certificates", annotations=annotate(READ, "List Certificates"))
async def mikrotik_list_certificates(
    ctx: Context,
    name_filter: Optional[str] = None,
    expired_only: bool = False,
    trusted_only: bool = False,
    ca_only: bool = False,
    device: Optional[str] = None,
) -> str:
    """Lists SSL/TLS certificates with common names, flags, validity periods, and fingerprints."""
    await ctx.info("Listing certificates")

    cmd = "/certificate print detail"
    filters = []
    if name_filter:
        if not _NAME_RE.match(name_filter):
            return f"Invalid name filter: '{name_filter}'"
        filters.append(f'name~"{ros_quoted(name_filter)}"')
    if expired_only:
        filters.append("expired=yes")
    if trusted_only:
        filters.append("trusted=yes")
    if ca_only:
        filters.append("authority=yes")

    if filters:
        cmd += " where " + " ".join(filters)

    result = await execute_mikrotik_command(cmd, ctx, device=device)
    if not has_item_rows(result):
        return "No certificates found matching the criteria."

    return f"CERTIFICATES:\n\n{result}"


@mcp.tool(name="get_certificate", annotations=annotate(READ, "Get Certificate"))
async def mikrotik_get_certificate(
    ctx: Context,
    name: str,
    device: Optional[str] = None,
) -> str:
    """Gets detailed information, fingerprints, key usage, and validity for a specific certificate."""
    if not _NAME_RE.match(name):
        return f"Invalid certificate name: '{name}'"

    await ctx.info(f"Getting certificate: {name}")
    cmd = f'/certificate print detail where name="{ros_quoted(name)}"'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not has_item_rows(result):
        return f"Certificate '{name}' not found."

    return f"CERTIFICATE DETAILS ({name}):\n\n{result}"


@mcp.tool(name="check_certificate_expiry", annotations=annotate(READ, "Check Certificate Expiry"))
async def mikrotik_check_certificate_expiry(
    ctx: Context,
    device: Optional[str] = None,
) -> str:
    """Checks all certificates on the router and reports any that are expired or expiring soon."""
    await ctx.info("Checking certificate expiry status")

    cmd = "/certificate print detail"
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not has_item_rows(result):
        return "No certificates found on the device."

    expired_certs = []
    valid_certs = []

    # Parse items from print detail output
    blocks = re.split(r"\n(?=\s*\d+\s+)", "\n" + result)
    for block in blocks:
        if not block.strip() or not re.match(r"^\s*\d+\s+", block):
            continue

        name_match = re.search(r'name="([^"]+)"', block)
        name = name_match.group(1) if name_match else "unknown"

        flags_match = re.match(r"^\s*\d+\s+([A-Z]+)\s", block)
        flags = flags_match.group(1) if flags_match else ""

        invalid_after_match = re.search(r"invalid-after=([^\s]+ [^\s]+)", block)
        invalid_after = invalid_after_match.group(1) if invalid_after_match else "unknown"

        expires_after_match = re.search(r"expires-after=([^\s]+)", block)
        expires_after = expires_after_match.group(1) if expires_after_match else ""

        is_expired = "E" in flags or "expired" in block.lower()

        info_line = f"- {name} (valid until: {invalid_after}"
        if expires_after:
            info_line += f", remaining: {expires_after}"
        info_line += ")"

        if is_expired:
            expired_certs.append(f"{info_line} [EXPIRED]")
        else:
            valid_certs.append(info_line)

    report = ["CERTIFICATE EXPIRY REPORT:\n"]
    if expired_certs:
        report.append(f"WARNING: {len(expired_certs)} EXPIRED certificate(s) detected:")
        report.extend(expired_certs)
        report.append("")
    else:
        report.append("OK: No expired certificates found.\n")

    if valid_certs:
        report.append(f"Active & Valid certificates ({len(valid_certs)}):")
        report.extend(valid_certs)

    return "\n".join(report)


# ---------------------------------------------------------------------------
# Certificate Lifecycle & Management
# ---------------------------------------------------------------------------

@mcp.tool(name="create_certificate", annotations=annotate(WRITE_IDEMPOTENT, "Create Certificate"))
async def mikrotik_create_certificate(
    ctx: Context,
    name: str,
    common_name: str,
    key_size: Literal[1024, 2048, 4096] = 2048,
    days_valid: int = 365,
    key_usage: Optional[str] = None,
    subject_alt_name: Optional[str] = None,
    trusted: bool = False,
    device: Optional[str] = None,
) -> str:
    """Creates a new certificate template on the router."""
    if not _NAME_RE.match(name):
        return f"Invalid certificate name: '{name}'"

    await ctx.info(f"Creating certificate template: {name}")
    cmd = (
        f'/certificate add name="{ros_quoted(name)}" '
        f'common-name="{ros_quoted(common_name)}" '
        f"key-size={key_size} days-valid={days_valid}"
    )

    if key_usage:
        cmd += f' key-usage="{ros_quoted(key_usage)}"'
    if subject_alt_name:
        cmd += f' subject-alt-name="{ros_quoted(subject_alt_name)}"'
    if trusted:
        cmd += " trusted=yes"

    result = await execute_mikrotik_command(cmd, ctx, device=device)
    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to create certificate: {result}"

    return f"Certificate template '{name}' created successfully."


@mcp.tool(name="sign_certificate", annotations=annotate(WRITE_IDEMPOTENT, "Sign Certificate"))
async def mikrotik_sign_certificate(
    ctx: Context,
    name: str,
    ca: Optional[str] = None,
    device: Optional[str] = None,
) -> str:
    """Signs a certificate template, making it active for SSL/TLS services."""
    if not _NAME_RE.match(name):
        return f"Invalid certificate name: '{name}'"
    if ca and not _NAME_RE.match(ca):
        return f"Invalid CA name: '{ca}'"

    await ctx.info(f"Signing certificate: {name}")
    cmd = f'/certificate sign [find name="{ros_quoted(name)}"]'
    if ca:
        cmd += f' ca="{ros_quoted(ca)}"'

    result = await execute_mikrotik_command(cmd, ctx, device=device)
    if "failure:" in result.lower() or "error" in result.lower() or "no such item" in result.lower():
        return f"Failed to sign certificate: {result}"

    return f"Certificate '{name}' signed successfully."


@mcp.tool(name="update_certificate", annotations=annotate(WRITE_IDEMPOTENT, "Update Certificate"))
async def mikrotik_update_certificate(
    ctx: Context,
    name: str,
    trusted: Optional[bool] = None,
    new_name: Optional[str] = None,
    device: Optional[str] = None,
) -> str:
    """Updates properties such as trusted status or name on an existing certificate."""
    if not _NAME_RE.match(name):
        return f"Invalid certificate name: '{name}'"
    if new_name and not _NAME_RE.match(new_name):
        return f"Invalid new name: '{new_name}'"

    updates = []
    if trusted is not None:
        updates.append(f'trusted={"yes" if trusted else "no"}')
    if new_name is not None:
        updates.append(f'name="{ros_quoted(new_name)}"')

    if not updates:
        return "No updates specified."

    await ctx.info(f"Updating certificate: {name}")
    cmd = f'/certificate set [find name="{ros_quoted(name)}"] ' + " ".join(updates)
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower() or "no such item" in result.lower():
        return f"Failed to update certificate: {result}"

    return f"Certificate '{name}' updated successfully."


@mcp.tool(name="remove_certificate", annotations=annotate(DESTRUCTIVE, "Remove Certificate"))
async def mikrotik_remove_certificate(
    ctx: Context,
    name: str,
    device: Optional[str] = None,
) -> str:
    """Removes a certificate and its associated private key from the router."""
    if not _NAME_RE.match(name):
        return f"Invalid certificate name: '{name}'"

    await ctx.info(f"Removing certificate: {name}")
    cmd = f'/certificate remove [find name="{ros_quoted(name)}"]'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to remove certificate: {result}"

    return f"Certificate '{name}' removed successfully."


# ---------------------------------------------------------------------------
# ACME / Let's Encrypt Automation
# ---------------------------------------------------------------------------

@mcp.tool(name="request_acme_certificate", annotations=annotate(WRITE_IDEMPOTENT, "Request ACME Certificate"))
async def mikrotik_request_acme_certificate(
    ctx: Context,
    domain: str,
    email: Optional[str] = None,
    device: Optional[str] = None,
) -> str:
    """Requests and provisions an automated Let's Encrypt ACME certificate for a domain."""
    if not _DOMAIN_RE.match(domain):
        return f"Invalid domain name: '{domain}'"

    await ctx.info(f"Requesting ACME certificate for domain: {domain}")
    cmd = f'/certificate add-acme domain="{ros_quoted(domain)}"'
    if email:
        cmd += f' email="{ros_quoted(email)}"'

    result = await execute_mikrotik_command(cmd, ctx, device=device)
    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to request ACME certificate: {result}"

    return f"ACME certificate request for '{domain}' initiated successfully:\n\n{result.strip()}"


# ---------------------------------------------------------------------------
# Import / Export
# ---------------------------------------------------------------------------

@mcp.tool(name="import_certificate", annotations=annotate(WRITE_IDEMPOTENT, "Import Certificate"))
async def mikrotik_import_certificate(
    ctx: Context,
    file_name: str,
    passphrase: Optional[str] = None,
    device: Optional[str] = None,
) -> str:
    """Imports a certificate or private key from an existing file on the router storage."""
    await ctx.info(f"Importing certificate from file: {file_name}")
    cmd = f'/certificate import file-name="{ros_quoted(file_name)}"'
    if passphrase:
        cmd += f' passphrase="{ros_quoted(passphrase)}"'

    result = await execute_mikrotik_command(
        cmd, ctx, device=device, redact=[passphrase] if passphrase else None
    )

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to import certificate: {result}"

    return f"Certificate imported successfully from '{file_name}':\n\n{result.strip()}"


@mcp.tool(name="export_certificate", annotations=annotate(WRITE_IDEMPOTENT, "Export Certificate"))
async def mikrotik_export_certificate(
    ctx: Context,
    name: str,
    file_name: str,
    export_passphrase: Optional[str] = None,
    type: Literal["pkcs12", "pem"] = "pem",
    device: Optional[str] = None,
) -> str:
    """Exports a certificate and its key to a file on router storage."""
    if not _NAME_RE.match(name):
        return f"Invalid certificate name: '{name}'"

    await ctx.info(f"Exporting certificate '{name}' to '{file_name}'")
    cmd = (
        f'/certificate export-certificate [find name="{ros_quoted(name)}"] '
        f'file-name="{ros_quoted(file_name)}" type={type}'
    )
    if export_passphrase:
        cmd += f' export-passphrase="{ros_quoted(export_passphrase)}"'

    result = await execute_mikrotik_command(
        cmd, ctx, device=device, redact=[export_passphrase] if export_passphrase else None
    )

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to export certificate: {result}"

    return f"Certificate '{name}' exported successfully to '{file_name}'."


# ---------------------------------------------------------------------------
# CRL & Global Certificate Settings
# ---------------------------------------------------------------------------

@mcp.tool(name="list_crl", annotations=annotate(READ, "List CRL Entries"))
async def mikrotik_list_crl(
    ctx: Context,
    device: Optional[str] = None,
) -> str:
    """Lists Certificate Revocation Lists (CRL) and their update status."""
    await ctx.info("Listing CRL entries")
    cmd = "/certificate crl print detail"
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not has_item_rows(result):
        return "No CRL entries found."

    return f"CERTIFICATE REVOCATION LISTS (CRL):\n\n{result}"


@mcp.tool(name="get_certificate_settings", annotations=annotate(READ, "Get Certificate Settings"))
async def mikrotik_get_certificate_settings(
    ctx: Context,
    device: Optional[str] = None,
) -> str:
    """Inspects global certificate settings such as trust store and CRL usage."""
    await ctx.info("Getting certificate settings")
    cmd = "/certificate settings print"
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result.strip():
        return "No certificate settings available."

    return f"CERTIFICATE SETTINGS:\n\n{result.strip()}"


@mcp.tool(name="update_certificate_settings", annotations=annotate(WRITE_IDEMPOTENT, "Update Certificate Settings"))
async def mikrotik_update_certificate_settings(
    ctx: Context,
    crl_download: Optional[bool] = None,
    crl_use: Optional[bool] = None,
    crl_store: Optional[Literal["ram", "system"]] = None,
    builtin_trust_store: Optional[str] = None,
    device: Optional[str] = None,
) -> str:
    """Updates global certificate settings for trust store and automatic CRL verification."""
    updates = []
    if crl_download is not None:
        updates.append(f'crl-download={"yes" if crl_download else "no"}')
    if crl_use is not None:
        updates.append(f'crl-use={"yes" if crl_use else "no"}')
    if crl_store is not None:
        updates.append(f"crl-store={crl_store}")
    if builtin_trust_store is not None:
        updates.append(f'builtin-trust-store="{ros_quoted(builtin_trust_store)}"')

    if not updates:
        return "No updates specified."

    await ctx.info("Updating certificate settings")
    cmd = "/certificate settings set " + " ".join(updates)
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to update certificate settings: {result}"

    return "Certificate settings updated successfully."
