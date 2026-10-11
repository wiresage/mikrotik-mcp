from typing import List, Literal, Optional, Dict, Any

from ..connector import execute_mikrotik_command
from mcp.server.mcpserver import Context
from ..app import mcp, READ, WRITE, WRITE_IDEMPOTENT, DESTRUCTIVE, annotate


async def mikrotik_detect_wireless_interface_type(ctx: Context, device: Optional[str] = None) -> Optional[str]:
    """
    Detects the wireless interface type based on RouterOS version.

    Returns:
        The appropriate wireless interface command path or None if not supported
    """
    await ctx.info("Detecting wireless interface type")

    # Try different wireless interface types in order of preference
    interface_types = [
        "/interface wifi",  # RouterOS v7.x (newest)
        "/interface wifiwave2",  # RouterOS v7.x (alternative)
        "/interface wireless",  # RouterOS v6.x
        "/interface wlan"  # Older versions
    ]

    for interface_type in interface_types:
        try:
            await ctx.debug(f"Testing interface type: {interface_type}")

            # Use a simpler test command that's less likely to hang
            test_cmd = f"{interface_type} print count-only"
            result = await execute_mikrotik_command(test_cmd, ctx, device=device)

            await ctx.debug(f"Result for {interface_type}: {result}")

            # Check for specific error patterns
            if result and isinstance(result, str):
                result_lower = result.lower()
                if ("bad command name" in result_lower or
                        "failure:" in result_lower or
                        "no such command prefix" in result_lower or
                        "invalid command name" in result_lower):
                    await ctx.debug(f"Interface type {interface_type} not supported")
                    continue
                else:
                    # If we get a numeric result or no error, this type is supported
                    await ctx.info(f"Detected wireless interface type: {interface_type}")
                    return interface_type

        except Exception as e:
            await ctx.debug(f"Interface type {interface_type} failed with exception: {e}")
            continue

    # If none work, return None
    await ctx.warning("No wireless interface type detected")
    return None


@mcp.tool(name="create_wireless_interface", annotations=annotate(WRITE, "Create Wireless Interface"))
async def mikrotik_create_wireless_interface(
        ctx: Context,
        name: str,
        ssid: Optional[str] = None,
        disabled: bool = False,
        comment: Optional[str] = None,
        radio_name: Optional[str] = None,
        mode: Optional[Literal["ap-bridge", "bridge", "station", "station-pseudobridge", "station-bridge", "station-wds", "ap-bridge-wds", "alignment-only"]] = None,
        frequency: Optional[str] = None,
        band: Optional[Literal["2ghz-b", "2ghz-b/g", "2ghz-b/g/n", "5ghz-a", "5ghz-a/n", "5ghz-a/n/ac", "2ghz-g", "2ghz-n", "5ghz-n", "5ghz-ac"]] = None,
        channel_width: Optional[Literal["20mhz", "40mhz", "80mhz", "160mhz", "20/40mhz-eC", "20/40mhz-Ce"]] = None,
        security_profile: Optional[str] = None,
        device: Optional[str] = None,
) -> str:
    """Creates a wireless interface on the MikroTik device (auto-detects RouterOS v6/v7 syntax)."""
    await ctx.info(f"Creating wireless interface: name={name}, ssid={ssid}")

    # Detect wireless interface type
    interface_type = await mikrotik_detect_wireless_interface_type(ctx, device=device)

    if not interface_type:
        return "Error: No wireless interface support detected on this device."

    # Build the command based on interface type
    if interface_type == "/interface wifi":
        # RouterOS v7.x newest wifi syntax - simplified
        cmd = f"{interface_type} add name={name}"

        if ssid:
            cmd += f' ssid="{ssid}"'
        if disabled:
            cmd += " disabled=yes"
        if comment:
            cmd += f' comment="{comment}"'

    elif interface_type == "/interface wifiwave2":
        # RouterOS v7.x wifiwave2 syntax
        cmd = f"{interface_type} add name={name}"

        if ssid:
            cmd += f' ssid="{ssid}"'
        if disabled:
            cmd += " disabled=yes"
        if comment:
            cmd += f' comment="{comment}"'

    else:
        # Legacy wireless syntax (RouterOS v6.x and older)
        if not radio_name:
            return "Error: radio_name is required for legacy wireless systems. Please specify the radio interface (e.g., 'wlan1')."

        cmd = f"{interface_type} add name={name} radio-name={radio_name} mode={mode or 'ap-bridge'}"

        if ssid:
            cmd += f' ssid="{ssid}"'
        if disabled:
            cmd += " disabled=yes"
        if comment:
            cmd += f' comment="{comment}"'

        # Add other legacy parameters if provided
        for param_name, param_value in [
            ('frequency', frequency), ('band', band),
            ('channel-width', channel_width), ('security-profile', security_profile),
        ]:
            if param_value:
                cmd += f" {param_name}={param_value}"

    await ctx.info(f"Executing command: {cmd}")
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to create wireless interface: {result}"

    # Get the created interface details
    details_cmd = f'{interface_type} print detail where name="{name}"'
    details = await execute_mikrotik_command(details_cmd, ctx, device=device)

    return f"Wireless interface created successfully using {interface_type}:\n\n{details}"


@mcp.tool(name="list_wireless_interfaces", annotations=annotate(READ, "List Wireless Interfaces"))
async def mikrotik_list_wireless_interfaces(
        ctx: Context,
        name_filter: Optional[str] = None,
        disabled_only: bool = False,
        running_only: bool = False,
        device: Optional[str] = None
) -> str:
    """Lists wireless interfaces on the MikroTik device."""
    await ctx.info(f"Listing wireless interfaces with filters: name={name_filter}")

    # Try multiple interface types to ensure we find all wireless interfaces
    interface_types_to_try = [
        "/interface wifi",
        "/interface wifiwave2",
        "/interface wireless",
        "/interface wlan"
    ]

    all_results = []
    working_types = []

    for interface_type in interface_types_to_try:
        try:
            # Build the command
            cmd = f"{interface_type} print"

            # Add filters
            filters = []
            if name_filter:
                filters.append(f'name~"{name_filter}"')
            if disabled_only:
                filters.append("disabled=yes")
            if running_only:
                filters.append("running=yes")

            if filters:
                cmd += " where " + " and ".join(filters)

            result = await execute_mikrotik_command(cmd, ctx, device=device)

            # Check if command worked and has results
            if (result and
                    result.strip() != "" and
                    "bad command name" not in result.lower() and
                    "failure:" not in result.lower() and
                    "no such command prefix" not in result.lower()):
                working_types.append(interface_type)
                all_results.append(f"=== {interface_type.upper()} ===\n{result}")

        except Exception as e:
            await ctx.debug(f"Interface type {interface_type} failed: {e}")
            continue

    # If we found results, return them
    if all_results:
        return f"WIRELESS INTERFACES:\n\n" + "\n\n".join(all_results)

    # If no results found, try to show all interfaces to help debug
    try:
        all_interfaces_cmd = "/interface print"
        all_interfaces = await execute_mikrotik_command(all_interfaces_cmd, ctx, device=device)
        return f"""No wireless interfaces found matching the criteria.

DEBUGGING INFO:
Working interface types: {', '.join(working_types) if working_types else 'None detected'}

ALL INTERFACES ON DEVICE:
{all_interfaces}

NOTE: If you see wireless interfaces above, they might be using a different command structure."""

    except Exception:
        return "No wireless interfaces found matching the criteria."


@mcp.tool(name="get_wireless_interface", annotations=annotate(READ, "Get Wireless Interface"))
async def mikrotik_get_wireless_interface(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Gets detailed information about a specific wireless interface."""
    await ctx.info(f"Getting wireless interface details: name={name}")

    # Detect wireless interface type
    interface_type = await mikrotik_detect_wireless_interface_type(ctx, device=device)

    if not interface_type:
        return "Error: No wireless interface support detected on this device."

    cmd = f'{interface_type} print detail where name="{name}"'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result or result.strip() == "":
        return f"Wireless interface '{name}' not found."

    return f"WIRELESS INTERFACE DETAILS:\n\n{result}"


@mcp.tool(name="remove_wireless_interface", annotations=annotate(DESTRUCTIVE, "Remove Wireless Interface"))
async def mikrotik_remove_wireless_interface(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Removes a wireless interface from the MikroTik device."""
    await ctx.info(f"Removing wireless interface: name={name}")

    # Detect wireless interface type
    interface_type = await mikrotik_detect_wireless_interface_type(ctx, device=device)

    if not interface_type:
        return "Error: No wireless interface support detected on this device."

    # Check if interface exists
    check_cmd = f'{interface_type} print count-only where name="{_ros_quoted(name)}"'
    count = await execute_mikrotik_command(check_cmd, ctx, device=device)

    if count.strip() == "0":
        return f"Wireless interface '{name}' not found."

    # Remove the interface
    cmd = f'{interface_type} remove [find name="{name}"]'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to remove wireless interface: {result}"

    return f"Wireless interface '{name}' removed successfully."


@mcp.tool(name="enable_wireless_interface", annotations=annotate(WRITE_IDEMPOTENT, "Enable Wireless Interface"))
async def mikrotik_enable_wireless_interface(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Enables a wireless interface."""
    await ctx.info(f"Enabling wireless interface: {name}")

    # Detect wireless interface type
    interface_type = await mikrotik_detect_wireless_interface_type(ctx, device=device)

    if not interface_type:
        return "Error: No wireless interface support detected on this device."

    cmd = f'{interface_type} enable [find name="{name}"]'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to enable wireless interface: {result}"

    return f"Wireless interface '{name}' enabled successfully."


@mcp.tool(name="disable_wireless_interface", annotations=annotate(WRITE_IDEMPOTENT, "Disable Wireless Interface"))
async def mikrotik_disable_wireless_interface(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Disables a wireless interface."""
    await ctx.info(f"Disabling wireless interface: {name}")

    # Detect wireless interface type
    interface_type = await mikrotik_detect_wireless_interface_type(ctx, device=device)

    if not interface_type:
        return "Error: No wireless interface support detected on this device."

    cmd = f'{interface_type} disable [find name="{name}"]'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to disable wireless interface: {result}"

    return f"Wireless interface '{name}' disabled successfully."


@mcp.tool(name="scan_wireless_networks", annotations=annotate(READ, "Scan Wireless Networks"))
async def mikrotik_scan_wireless_networks(
        ctx: Context,
        interface: str,
        duration: int = 5,
        device: Optional[str] = None
) -> str:
    """Scans for nearby wireless networks using the specified interface."""
    await ctx.info(f"Scanning wireless networks on interface: {interface}")

    # Detect wireless interface type
    interface_type = await mikrotik_detect_wireless_interface_type(ctx, device=device)

    if not interface_type:
        return "Error: No wireless interface support detected on this device."

    # Different scan commands for different versions
    scan_cmd = f'{interface_type} scan {interface} duration={duration}'

    result = await execute_mikrotik_command(scan_cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to scan wireless networks: {result}"

    return f"WIRELESS NETWORK SCAN RESULTS:\n\n{result}"


@mcp.tool(name="get_wireless_registration_table", annotations=annotate(READ, "Wireless Registration Table"))
async def mikrotik_get_wireless_registration_table(
        ctx: Context,
        interface: Optional[str] = None,
        device: Optional[str] = None
) -> str:
    """Gets the wireless registration table (connected clients) from the MikroTik device."""
    await ctx.info(f"Getting wireless registration table for interface: {interface}")

    # Detect wireless interface type
    interface_type = await mikrotik_detect_wireless_interface_type(ctx, device=device)

    if not interface_type:
        return "Error: No wireless interface support detected on this device."

    # Build command
    cmd = f"{interface_type} registration-table print"

    if interface:
        cmd += f' where interface="{interface}"'

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result or result.strip() == "":
        return "No wireless clients registered."

    return f"WIRELESS REGISTRATION TABLE:\n\n{result}"


@mcp.tool(name="check_wireless_support", annotations=annotate(READ, "Check Wireless Support"))
async def mikrotik_check_wireless_support(ctx: Context, device: Optional[str] = None) -> str:
    """Checks if the device supports wireless and reports the RouterOS version and wireless interface type."""
    await ctx.info("Checking wireless support")

    # Check RouterOS version
    version_cmd = "/system resource print"
    version_result = await execute_mikrotik_command(version_cmd, ctx, device=device)

    # Check installed packages
    package_cmd = "/system package print"
    package_result = await execute_mikrotik_command(package_cmd, ctx, device=device)

    # Check available interfaces
    interface_cmd = "/interface print"
    interface_result = await execute_mikrotik_command(interface_cmd, ctx, device=device)

    # Detect wireless interface type
    wireless_type = await mikrotik_detect_wireless_interface_type(ctx, device=device)

    report = f"""WIRELESS SUPPORT CHECK:

RouterOS Version:
{version_result}

Installed Packages:
{package_result}

Available Interfaces:
{interface_result}

Detected Wireless Interface Type: {wireless_type if wireless_type else 'None detected'}

Compatibility Notes:
- RouterOS v7.x uses '/interface wifi' (newest system)
- RouterOS v7.x also supports '/interface wifiwave2' (alternative)
- RouterOS v6.x uses '/interface wireless' (legacy system)
- Older versions may use '/interface wlan'

USAGE EXAMPLES:
For RouterOS v7.x:
  mikrotik_create_wireless_interface(name="wlan1", ssid="MyNetwork")

For legacy systems:
  mikrotik_create_wireless_interface(name="wlan1", radio_name="wlan1", ssid="MyNetwork")
"""

    return report


# Legacy compatibility functions (simplified versions for older RouterOS)
@mcp.tool(name="create_wireless_security_profile", annotations=annotate(WRITE, "Create Wireless Security Profile"))
async def mikrotik_create_wireless_security_profile(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Legacy function - not supported in RouterOS v7.x"""
    interface_type = await mikrotik_detect_wireless_interface_type(ctx, device=device)
    if interface_type in ["/interface wifi", "/interface wifiwave2"]:
        return "Security profiles are not used in RouterOS v7.x. Configure security directly on the wireless interface."
    return "Legacy security profile creation not implemented in this version."


@mcp.tool(name="list_wireless_security_profiles", annotations=annotate(READ, "List Wireless Security Profiles"))
async def mikrotik_list_wireless_security_profiles(ctx: Context, device: Optional[str] = None) -> str:
    """Legacy function - not supported in RouterOS v7.x"""
    interface_type = await mikrotik_detect_wireless_interface_type(ctx, device=device)
    if interface_type in ["/interface wifi", "/interface wifiwave2"]:
        return "Security profiles are not used in RouterOS v7.x. Security is configured directly on wireless interfaces."
    return "Legacy security profile listing not implemented in this version."


@mcp.tool(name="get_wireless_security_profile", annotations=annotate(READ, "Get Wireless Security Profile"))
async def mikrotik_get_wireless_security_profile(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Legacy function - not supported in RouterOS v7.x"""
    interface_type = await mikrotik_detect_wireless_interface_type(ctx, device=device)
    if interface_type in ["/interface wifi", "/interface wifiwave2"]:
        return "Security profiles are not used in RouterOS v7.x. Check security configuration on wireless interfaces directly."
    return "Legacy security profile details not implemented in this version."


@mcp.tool(name="remove_wireless_security_profile", annotations=annotate(DESTRUCTIVE, "Remove Wireless Security Profile"))
async def mikrotik_remove_wireless_security_profile(ctx: Context, name: str, device: Optional[str] = None) -> str:
    """Legacy function - not supported in RouterOS v7.x"""
    interface_type = await mikrotik_detect_wireless_interface_type(ctx, device=device)
    if interface_type in ["/interface wifi", "/interface wifiwave2"]:
        return "Security profiles are not used in RouterOS v7.x. Security is configured directly on wireless interfaces."
    return "Legacy security profile removal not implemented in this version."


@mcp.tool(name="set_wireless_security_profile", annotations=annotate(WRITE, "Set Wireless Security Profile"))
async def mikrotik_set_wireless_security_profile(ctx: Context, interface_name: str, security_profile: str, device: Optional[str] = None) -> str:
    """Legacy function - not supported in RouterOS v7.x"""
    interface_type = await mikrotik_detect_wireless_interface_type(ctx, device=device)
    if interface_type in ["/interface wifi", "/interface wifiwave2"]:
        return "Security profiles are not used in RouterOS v7.x. Configure security directly on the wireless interface."
    return "Legacy security profile setting not implemented in this version."


@mcp.tool(name="create_wireless_access_list", annotations=annotate(WRITE, "Create Wireless Access List"))
async def mikrotik_create_wireless_access_list(ctx: Context, device: Optional[str] = None) -> str:
    """Legacy function - different in RouterOS v7.x"""
    interface_type = await mikrotik_detect_wireless_interface_type(ctx, device=device)
    if interface_type in ["/interface wifi", "/interface wifiwave2"]:
        return "Access lists are configured differently in RouterOS v7.x. Use firewall rules or other access control methods."
    return "Legacy access list creation not implemented in this version."


@mcp.tool(name="list_wireless_access_list", annotations=annotate(READ, "List Wireless Access List"))
async def mikrotik_list_wireless_access_list(ctx: Context, device: Optional[str] = None) -> str:
    """Legacy function - different in RouterOS v7.x"""
    interface_type = await mikrotik_detect_wireless_interface_type(ctx, device=device)
    if interface_type in ["/interface wifi", "/interface wifiwave2"]:
        return "Access lists are configured differently in RouterOS v7.x. Check firewall rules or other access control configurations."
    return "Legacy access list listing not implemented in this version."


@mcp.tool(name="remove_wireless_access_list_entry", annotations=annotate(DESTRUCTIVE, "Remove Wireless Access List Entry"))
async def mikrotik_remove_wireless_access_list_entry(ctx: Context, entry_id: str, device: Optional[str] = None) -> str:
    """Legacy function - different in RouterOS v7.x"""
    interface_type = await mikrotik_detect_wireless_interface_type(ctx, device=device)
    if interface_type in ["/interface wifi", "/interface wifiwave2"]:
        return "Access lists are configured differently in RouterOS v7.x."
    return "Legacy access list removal not implemented in this version."


@mcp.tool(name="update_wireless_interface", annotations=annotate(WRITE_IDEMPOTENT, "Update Wireless Interface"))
async def mikrotik_update_wireless_interface(
        ctx: Context,
        name: str,
        new_name: Optional[str] = None,
        ssid: Optional[str] = None,
        disabled: Optional[bool] = None,
        comment: Optional[str] = None,
        device: Optional[str] = None,
) -> str:
    """Updates an existing wireless interface's settings (name, SSID, enabled state, etc.)."""
    await ctx.info(f"Updating wireless interface: name={name}")

    # Detect wireless interface type
    interface_type = await mikrotik_detect_wireless_interface_type(ctx, device=device)

    if not interface_type:
        return "Error: No wireless interface support detected on this device."

    # Check if interface exists
    check_cmd = f'{interface_type} print count-only where name="{_ros_quoted(name)}"'
    count = await execute_mikrotik_command(check_cmd, ctx, device=device)

    if count.strip() == "0":
        return f"Wireless interface '{name}' not found."

    # Build update command
    updates = []

    if new_name:
        updates.append(f"name={new_name}")
    if ssid:
        # v7 wifi/wifiwave2 has no top-level ssid property; it lives under
        # configuration.ssid (and setting it inline overrides any profile)
        if interface_type in ("/interface wifi", "/interface wifiwave2"):
            updates.append(f'configuration.ssid="{ssid}"')
        else:
            updates.append(f'ssid="{ssid}"')
    if disabled is not None:
        updates.append(f"disabled={'yes' if disabled else 'no'}")
    if comment:
        updates.append(f'comment="{comment}"')

    if not updates:
        return "No updates specified."

    cmd = f'{interface_type} set [find name="{name}"] {" ".join(updates)}'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    result_lower = result.lower()
    if ("failure:" in result_lower or "error" in result_lower
            or "expected end of command" in result_lower
            or "bad command name" in result_lower
            or "input does not match" in result_lower):
        return f"Failed to update wireless interface: {result}"

    # Get updated details
    target_name = new_name or name
    details_cmd = f'{interface_type} print detail where name="{target_name}"'
    details = await execute_mikrotik_command(details_cmd, ctx, device=device)

    return f"Wireless interface updated successfully:\n\n{details}"


# WPA-PSK accepts any printable ASCII, 8-63 characters.
_PSK_MIN, _PSK_MAX = 8, 63


def _ros_quoted(value: str) -> str:
    """Escape a value for a RouterOS double-quoted string.

    A bare `"` ends the string early, so RouterOS answers "expected end of
    command" and the write never happens -- and quotes are legal in a WPA
    passphrase. Backslash first, or it would escape the escapes.
    """
    return value.replace("\\", "\\\\").replace('"', '\\"')


@mcp.tool(name="set_wireless_passphrase", annotations=annotate(WRITE_IDEMPOTENT, "Set Wireless Passphrase"))
async def mikrotik_set_wireless_passphrase(
        ctx: Context,
        name: str,
        passphrase: str,
        authentication_types: Optional[str] = None,
        device: Optional[str] = None,
) -> str:
    """Sets the WiFi passphrase directly on a RouterOS v7 wireless interface (/interface wifi or wifiwave2).

    Notes:
        authentication_types: comma-separated RouterOS auth types, e.g. "wpa2-psk,wpa3-psk"; unset keeps the current setting.
    """
    # Deliberately do not log the passphrase. Note the connector still logs the
    # command it runs, so the passphrase reaches the server log and the client
    # until that is redacted centrally.
    await ctx.info(f"Setting wireless passphrase on interface: {name}")

    if not _PSK_MIN <= len(passphrase) <= _PSK_MAX:
        return (
            f"Passphrase must be {_PSK_MIN}-{_PSK_MAX} characters for WPA-PSK "
            f"(got {len(passphrase)})."
        )

    # Detect wireless interface type
    interface_type = await mikrotik_detect_wireless_interface_type(ctx, device=device)

    if not interface_type:
        return "Error: No wireless interface support detected on this device."

    if interface_type not in ["/interface wifi", "/interface wifiwave2"]:
        return "Legacy /interface wireless stores passphrases in security profiles and is not supported by this tool. Use RouterOS v7 (/interface wifi or wifiwave2)."

    # Check if interface exists
    check_cmd = f'{interface_type} print count-only where name="{_ros_quoted(name)}"'
    count = await execute_mikrotik_command(check_cmd, ctx, device=device)

    if count.strip() == "0":
        return f"Wireless interface '{name}' not found."

    # Inline dotted security.* settings override any assigned security profile
    cmd = (
        f'{interface_type} set [find name="{_ros_quoted(name)}"] '
        f'security.passphrase="{_ros_quoted(passphrase)}"'
    )
    if authentication_types:
        cmd += f" security.authentication-types={authentication_types}"

    # The command carries the passphrase and the connector logs every
    # command, so redact both forms: the escaped one is what reaches the
    # command line, the raw one is what a result might echo back.
    result = await execute_mikrotik_command(
        cmd, ctx, device=device, redact=[_ros_quoted(passphrase), passphrase]
    )

    # A successful `set` prints nothing, so ANY output means the write did not
    # happen. Matching on "failure:"/"error" missed the two refusals that
    # actually occur here -- "not enough permissions (9)" and "expected end of
    # command" -- and reported an unchanged passphrase as updated.
    if result.strip():
        # Never echo the passphrase back, even if RouterOS quoted it.
        detail = result.strip().replace(passphrase, "***")
        return f"Failed to set wireless passphrase on '{name}': {detail}"

    # Do not print details afterwards: detail output can include security.passphrase in plaintext
    return f"Wireless passphrase updated successfully on '{name}' using {interface_type}."
