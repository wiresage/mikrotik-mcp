"""Shared implementation of the /ip firewall raw and /ipv6 firewall raw tools.

The two menus take the same commands; only the menu path, a handful of family-specific matchers (ttl for
IPv4, hop-limit for IPv6) and the wording of the messages differ. The scope modules ``firewall_raw`` and
``ipv6_firewall_raw`` register thin tools that call into here and pass their own ``execute`` so that tests
can patch the executor on the scope module, as for every other scope.

Every value interpolated into a command is validated or quoted here, since all of it is model-controlled:
names and free text go inside double quotes through ``ros_quoted``; matcher values that RouterOS takes bare
(addresses, ports, flags, limits...) must match ``_BARE_RE``, which rules out spaces, quotes, ``;``,
brackets and ``$``.
"""

import re
from typing import Awaitable, Callable, Dict, Optional

from ._quoting import ros_quoted
from ._selectors import _ID_RE, has_item_rows, item_at_position, item_count, move_to_position, resolve_item_id

Execute = Callable[..., Awaitable[str]]

RAW_ACTIONS = (
    "accept", "drop", "notrack", "jump", "return", "log", "passthrough",
    "add-src-to-address-list", "add-dst-to-address-list",
)

_CHAIN_RE = re.compile(r"[A-Za-z0-9_.\-]{1,64}")
_BARE_RE = re.compile(r"!?[A-Za-z0-9_.:/,!\-]{1,256}")
_TIMEOUT_RE = re.compile(r"(none-dynamic|none-static|\d+[smhdw]?|(\d+[wdhms])+|\d{1,2}:\d{2}:\d{2})")

# RouterOS property name -> how the value is written. Quoted values are names or free text.
QUOTED_FIELDS = (
    "jump-target", "in-interface", "out-interface", "in-interface-list", "out-interface-list",
    "src-address-list", "dst-address-list", "address-list",
)
BARE_FIELDS = (
    "src-address", "dst-address", "src-port", "dst-port", "port", "protocol",
    "src-address-type", "dst-address-type", "tcp-flags", "icmp-options", "packet-size",
    "limit", "dscp", "ttl", "hop-limit",
)


class RawFamily:
    def __init__(self, menu: str, label: str):
        self.menu = menu
        self.label = label  # "Raw rule" / "IPv6 raw rule"

    def not_found(self, rule_id: str) -> str:
        return f"{self.label} with ID '{rule_id}' not found."


IPV4 = RawFamily("/ip firewall raw", "Firewall raw rule")
IPV6 = RawFamily("/ipv6 firewall raw", "IPv6 firewall raw rule")


def _field_param(field: str) -> str:
    return field.replace("-", "_")


def _render(field: str, value: str) -> str:
    """Render one ``field=value`` pair, raising ValueError on a value that cannot be sent safely."""
    if field in QUOTED_FIELDS:
        return f'{field}="{ros_quoted(value)}"'
    if field == "address-list-timeout":
        if not _TIMEOUT_RE.fullmatch(value):
            raise ValueError(f"address_list_timeout {value!r} is not a RouterOS duration (e.g. 1d, 12h, 00:30:00)")
        return f"{field}={value}"
    if not _BARE_RE.fullmatch(value):
        raise ValueError(
            f"{_field_param(field)} {value!r} contains characters RouterOS does not accept here "
            "(no spaces, quotes, ';', brackets or '$')"
        )
    return f"{field}={value}"


def _check_chain(chain: str) -> Optional[str]:
    if not _CHAIN_RE.fullmatch(chain):
        return f"Invalid chain name {chain!r}: use letters, digits, '_', '-' or '.'."
    return None


def _detail_cmd(family: RawFamily, rule_id: str) -> str:
    return f"{family.menu} print detail where .id={rule_id}"


async def create_rule(
    family: RawFamily, execute: Execute, ctx, *, chain: str, action: str,
    fields: Dict[str, Optional[str]], comment: Optional[str], disabled: bool,
    log: bool, log_prefix: Optional[str], place_before: Optional[str], device: Optional[str],
) -> str:
    await ctx.info(f"Creating {family.label.lower()}: chain={chain}, action={action}")

    if (err := _check_chain(chain)):
        return f"Failed to create {family.label.lower()}: {err}"
    if action == "jump" and not fields.get("jump-target"):
        return f"Failed to create {family.label.lower()}: action=jump needs jump_target."
    if action in ("add-src-to-address-list", "add-dst-to-address-list") and not fields.get("address-list"):
        return f"Failed to create {family.label.lower()}: action={action} needs address_list."

    parts = [f"{family.menu} add chain={chain} action={action}"]
    try:
        for field, value in fields.items():
            if value:
                parts.append(_render(field, value))
    except ValueError as exc:
        return f"Failed to create {family.label.lower()}: {exc}"
    if comment:
        parts.append(f'comment="{ros_quoted(comment)}"')
    if disabled:
        parts.append("disabled=yes")
    if log:
        parts.append("log=yes")
        if log_prefix:
            parts.append(f'log-prefix="{ros_quoted(log_prefix)}"')
    if place_before:
        before = await resolve_item_id(family.menu, place_before, ctx, device, execute)
        if before is None:
            return f"Failed to create {family.label.lower()}: place_before rule '{place_before}' not found."
        parts.append(f"place-before={before}")

    match_fields = set(fields) - {"jump-target", "address-list", "address-list-timeout"}
    has_match = any(fields.get(f) for f in match_fields)
    warning = ""
    if not has_match:
        warning = (
            f"WARNING: this rule has no match conditions - it matches ALL traffic in the '{chain}' raw chain "
            f"and applies action '{action}' to every packet, before connection tracking. "
            "Verify this is intentional.\n\n"
        )
        await ctx.warning(f"Creating raw rule with no match conditions in chain '{chain}'")

    # `:put [... add ...]` echoes the new *id: positive evidence the add landed, and a durable handle.
    result = (await execute(f":put [{' '.join(parts)}]", ctx, device=device)).strip()
    if not _ID_RE.fullmatch(result):
        return f"Failed to create {family.label.lower()}: {result or 'no rule ID returned'}"

    details = await execute(_detail_cmd(family, result), ctx, device=device)
    if has_item_rows(details):
        return f"{warning}{family.label} created successfully (ID {result}):\n\n{details}"
    return f"{warning}{family.label} created successfully with ID: {result}"


async def list_rules(
    family: RawFamily, execute: Execute, ctx, *, chain_filter, action_filter, src_address_filter,
    dst_address_filter, protocol_filter, interface_filter, comment_filter, disabled_only,
    invalid_only, dynamic_only, stats, device,
) -> str:
    await ctx.info(f"Listing {family.label.lower()}s: chain={chain_filter}, action={action_filter}")

    # Every value is quoted: an unquoted enum can silently match nothing (issue #135).
    q = ros_quoted
    filters = []
    if chain_filter:
        filters.append(f'chain="{q(chain_filter)}"')
    if action_filter:
        filters.append(f'action="{q(action_filter)}"')
    if src_address_filter:
        filters.append(f'src-address~"{q(src_address_filter)}"')
    if dst_address_filter:
        filters.append(f'dst-address~"{q(dst_address_filter)}"')
    if protocol_filter:
        filters.append(f'protocol="{q(protocol_filter)}"')
    if interface_filter:
        v = q(interface_filter)
        filters.append(f'(in-interface~"{v}" or out-interface~"{v}" '
                       f'or in-interface-list~"{v}" or out-interface-list~"{v}")')
    if comment_filter:
        filters.append(f'comment~"{q(comment_filter)}"')
    if disabled_only:
        filters.append("disabled=yes")
    if invalid_only:
        filters.append("invalid=yes")
    if dynamic_only:
        filters.append("dynamic=yes")

    cmd = f"{family.menu} print" + (" stats" if stats else "")
    if filters:
        cmd += " where " + " ".join(filters)

    result = await execute(cmd, ctx, device=device)
    if not has_item_rows(result):
        if result.strip() and "Flags:" not in result and "Columns:" not in result:
            return f"Failed to list {family.label.lower()}s: {result.strip()}"
        return f"No {family.label.lower()}s found matching the criteria."
    heading = family.label.upper() + "S" + (" (STATS)" if stats else "")
    return f"{heading}:\n\n{result}"


async def get_rule(family: RawFamily, execute: Execute, ctx, rule_id: str, device) -> str:
    await ctx.info(f"Getting {family.label.lower()} details: rule_id={rule_id}")
    resolved = await resolve_item_id(family.menu, rule_id, ctx, device, execute)
    if resolved is None:
        return family.not_found(rule_id)
    result = await execute(_detail_cmd(family, resolved), ctx, device=device)
    if "no such item" in result or not has_item_rows(result):
        return family.not_found(rule_id)
    return f"{family.label.upper()} DETAILS:\n\n{result}"


async def update_rule(
    family: RawFamily, execute: Execute, ctx, rule_id: str, *, chain: Optional[str], action: Optional[str],
    fields: Dict[str, Optional[str]], comment: Optional[str], disabled: Optional[bool],
    log: Optional[bool], log_prefix: Optional[str], device,
) -> str:
    await ctx.info(f"Updating {family.label.lower()}: rule_id={rule_id}")

    updates = []
    if chain:
        if (err := _check_chain(chain)):
            return f"Failed to update {family.label.lower()}: {err}"
        updates.append(f"chain={chain}")
    if action:
        updates.append(f"action={action}")
    try:
        for field, value in fields.items():
            if value is not None:
                updates.append(f"!{field}" if value == "" else _render(field, value))
    except ValueError as exc:
        return f"Failed to update {family.label.lower()}: {exc}"
    if comment is not None:
        updates.append(f'comment="{ros_quoted(comment)}"')
    if disabled is not None:
        updates.append(f'disabled={"yes" if disabled else "no"}')
    if log is not None:
        updates.append(f'log={"yes" if log else "no"}')
    if log_prefix is not None:
        updates.append(f'log-prefix="{ros_quoted(log_prefix)}"')
    if not updates:
        return "No updates specified."

    resolved = await resolve_item_id(family.menu, rule_id, ctx, device, execute)
    if resolved is None or await item_count(family.menu, resolved, ctx, device, execute) != "1":
        return family.not_found(rule_id)

    # A successful `set` prints nothing; any output is a refusal (e.g. "not enough permissions (9)").
    result = await execute(f"{family.menu} set {resolved} " + " ".join(updates), ctx, device=device)
    if "no such item" in result.lower():
        return family.not_found(rule_id)
    if result.strip():
        return f"Failed to update {family.label.lower()}: {result.strip()}"

    details = await execute(_detail_cmd(family, resolved), ctx, device=device)
    return f"{family.label} updated successfully:\n\n{details}"


async def remove_rule(family: RawFamily, execute: Execute, ctx, rule_id: str, device) -> str:
    await ctx.info(f"Removing {family.label.lower()}: rule_id={rule_id}")
    resolved = await resolve_item_id(family.menu, rule_id, ctx, device, execute)
    if resolved is None or await item_count(family.menu, resolved, ctx, device, execute) != "1":
        return family.not_found(rule_id)

    result = await execute(f"{family.menu} remove {resolved}", ctx, device=device)
    if "no such item" in result.lower():
        return family.not_found(rule_id)
    if result.strip():
        return f"Failed to remove {family.label.lower()}: {result.strip()}"
    if await item_count(family.menu, resolved, ctx, device, execute) != "0":
        return f"Failed to remove {family.label.lower()}: rule '{rule_id}' is still present."
    return f"{family.label} with ID '{rule_id}' removed successfully."


async def move_rule(family: RawFamily, execute: Execute, ctx, rule_id: str, destination: int, device) -> str:
    await ctx.info(f"Moving {family.label.lower()}: rule_id={rule_id} to position {destination}")
    resolved = await resolve_item_id(family.menu, rule_id, ctx, device, execute)
    if resolved is None or await item_count(family.menu, resolved, ctx, device, execute) != "1":
        return family.not_found(rule_id)

    result = await move_to_position(family.menu, resolved, destination, ctx, device, execute)
    if "no such item" in result.lower():
        return family.not_found(rule_id)
    if result.strip():
        return f"Failed to move {family.label.lower()}: {result.strip()}"
    if await item_at_position(family.menu, destination, ctx, device, execute) != resolved:
        return f"Failed to move {family.label.lower()}: rule '{rule_id}' is not at position {destination}."
    return f"{family.label} with ID '{rule_id}' moved to position {destination}."
