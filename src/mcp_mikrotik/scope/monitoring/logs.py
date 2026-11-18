import asyncio
import re
import time
from typing import Literal, Optional
from mcp.server.mcpserver import Context
from ...connector import execute_mikrotik_command
from ...app import mcp, READ, WRITE, annotate

# RouterOS durations like 5m, 1h, 2d — validated before being spliced into a
# where clause so a malformed value fails here with a clear message instead of
# as a console syntax error (which also lands in the router's own log).
_DURATION_RE = re.compile(r"^(\d+[smhdw])+$")

_ROS_REGEX_SPECIALS = r"\.^$*+?()[]{}|"


def _escape_term(term: str) -> str:
    """Escape a literal search term for a RouterOS ~ regex match."""
    return "".join("\\" + ch if ch in _ROS_REGEX_SPECIALS else ch for ch in term)


def _case_insensitive(pattern: str) -> str:
    """RouterOS ~ is case-sensitive; emulate insensitivity with char classes."""
    return "".join(
        f"[{ch.lower()}{ch.upper()}]" if ch.isalpha() else ch for ch in pattern
    )


def _time_clause(time_filter: str) -> str:
    if not _DURATION_RE.match(time_filter):
        raise ValueError(
            f"Invalid time_filter {time_filter!r}: use a RouterOS duration "
            'like "30s", "5m", "1h" or "2d".'
        )
    return f"time > ([:timestamp] - {time_filter})"


def _tail(result: str, limit: Optional[int]) -> str:
    """Keep the newest entries: /log print has no limit parameter."""
    if not limit:
        return result
    lines = [line for line in result.splitlines() if line.strip()]
    return "\n".join(lines[-limit:])


@mcp.tool(name="get_logs", annotations=annotate(READ, "Get Logs"))
async def mikrotik_get_logs(
    ctx: Context,
    topics: Optional[str] = None,
    time_filter: Optional[str] = None,
    message_filter: Optional[str] = None,
    prefix_filter: Optional[str] = None,
    limit: Optional[int] = None,
    print_as: Literal["plain", "detail", "terse"] = "plain",
    device: Optional[str] = None
) -> str:
    """Gets logs from the MikroTik device with optional topic, time, and message filters.

    Notes:
        topics: comma-separated, entry matches any of them e.g. "system,dhcp"
        time_filter: RouterOS duration e.g. "30s", "5m", "1h", "2d"
        message_filter: RouterOS regex matched against the message (case-sensitive)
        limit: keep only the newest N entries
    """
    await ctx.info(f"Getting logs with filters: topics={topics}, time={time_filter}")

    style = "" if print_as == "plain" else f" {print_as}"
    cmd = f"/log print{style}"

    filters = []

    if topics:
        topic_list = [t.strip() for t in topics.split(',') if t.strip()]
        if len(topic_list) > 1:
            filters.append(f'topics~"({"|".join(topic_list)})"')
        elif topic_list:
            filters.append(f'topics~"{topic_list[0]}"')

    if message_filter:
        filters.append(f'message~"{message_filter}"')

    if prefix_filter:
        filters.append(f'message~"^{_escape_term(prefix_filter)}"')

    if time_filter:
        try:
            filters.append(_time_clause(time_filter))
        except ValueError as exc:
            return f"Error: {exc}"

    if filters:
        cmd += " where " + " and ".join(filters)

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result or not result.strip() or result.strip() == "no such item":
        return "No log entries found matching the criteria."

    return f"LOG ENTRIES:\n\n{_tail(result, limit)}"


@mcp.tool(name="get_logs_by_severity", annotations=annotate(READ, "Get Logs by Severity"))
async def mikrotik_get_logs_by_severity(
    ctx: Context,
    severity: Literal["debug", "info", "warning", "error", "critical"],
    time_filter: Optional[str] = None,
    limit: Optional[int] = None,
    device: Optional[str] = None
) -> str:
    """Gets logs filtered by severity level (debug/info/warning/error/critical)."""
    await ctx.info(f"Getting logs by severity: severity={severity}")

    severity_topics = {
        "debug": "debug",
        "info": "info",
        "warning": "warning",
        "error": "error,critical",
        "critical": "critical"
    }

    return await mikrotik_get_logs(
        topics=severity_topics[severity],
        time_filter=time_filter,
        limit=limit,
        ctx=ctx,
        device=device
    )


@mcp.tool(name="get_logs_by_topic", annotations=annotate(READ, "Get Logs by Topic"))
async def mikrotik_get_logs_by_topic(
    ctx: Context,
    topic: str,
    time_filter: Optional[str] = None,
    limit: Optional[int] = None,
    device: Optional[str] = None
) -> str:
    """Gets logs for a specific topic/facility (system, dhcp, interface, firewall, etc.)."""
    await ctx.info(f"Getting logs by topic: topic={topic}")

    return await mikrotik_get_logs(
        topics=topic,
        time_filter=time_filter,
        limit=limit,
        ctx=ctx,
        device=device
    )


@mcp.tool(name="search_logs", annotations=annotate(READ, "Search Logs"))
async def mikrotik_search_logs(
    ctx: Context,
    search_term: str,
    time_filter: Optional[str] = None,
    case_sensitive: bool = False,
    limit: Optional[int] = None,
    device: Optional[str] = None
) -> str:
    """Searches log messages for a literal term.

    Notes:
        search_term: treated literally (regex specials are escaped)
        case_sensitive: RouterOS matching is case-sensitive; by default the
            search emulates case-insensitivity with character classes
    """
    await ctx.info(f"Searching logs for: term={search_term}")

    pattern = _escape_term(search_term)
    if not case_sensitive:
        pattern = _case_insensitive(pattern)

    return await mikrotik_get_logs(
        message_filter=pattern,
        time_filter=time_filter,
        limit=limit,
        ctx=ctx,
        device=device
    )


@mcp.tool(name="get_system_events", annotations=annotate(READ, "System Events"))
async def mikrotik_get_system_events(
    ctx: Context,
    event_type: Optional[str] = None,
    time_filter: Optional[str] = None,
    limit: Optional[int] = None,
    device: Optional[str] = None
) -> str:
    """Gets system-related log events (login, reboot, config-change, etc.)."""
    await ctx.info(f"Getting system events: type={event_type}")

    message_filter = None
    if event_type:
        event_patterns = {
            "login": "logged in",
            "logout": "logged out",
            "reboot": "reboot",
            "config-change": "config changed",
            "backup": "backup",
            "restore": "restore",
            "upgrade": "upgrade"
        }
        pattern = event_patterns.get(event_type.lower(), event_type)
        message_filter = _case_insensitive(_escape_term(pattern))

    return await mikrotik_get_logs(
        topics="system",
        message_filter=message_filter,
        time_filter=time_filter,
        limit=limit,
        ctx=ctx,
        device=device
    )


@mcp.tool(name="get_security_logs", annotations=annotate(READ, "Security Logs"))
async def mikrotik_get_security_logs(
    ctx: Context,
    time_filter: Optional[str] = None,
    limit: Optional[int] = None,
    device: Optional[str] = None
) -> str:
    """Gets security-related log entries (logins, failures, blocked connections, etc.)."""
    await ctx.info("Getting security logs")

    # account carries login/logout events; the message alternation catches
    # firewall drops and auth failures logged under other topics
    topics = "(system|firewall|warning|error|critical|account)"
    keywords = _case_insensitive(
        "(logged|login|logout|failure|failed|denied|blocked|attack|invalid|unauthorized)"
    )

    cmd = f'/log print where topics~"{topics}" and message~"{keywords}"'

    if time_filter:
        try:
            cmd += f" and {_time_clause(time_filter)}"
        except ValueError as exc:
            return f"Error: {exc}"

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result or not result.strip() or result.strip() == "no such item":
        return "No security-related log entries found."

    return f"SECURITY LOG ENTRIES:\n\n{_tail(result, limit)}"


@mcp.tool(name="clear_logs", annotations=annotate(READ, "Clear Logs"))
async def mikrotik_clear_logs(ctx: Context, device: Optional[str] = None) -> str:
    """Explains why MikroTik's in-memory log cannot be cleared on demand."""
    await ctx.info("Clear logs requested")

    # RouterOS has no command to clear the in-memory log. The previous
    # implementation ran "/log print follow-only", which clears nothing and
    # blocks forever on a non-interactive channel.
    return (
        "RouterOS does not support clearing the in-memory log: there is no "
        "/log clear or remove command. The memory buffer empties on reboot, "
        "rotates automatically at its configured size, and can be redirected "
        "or resized via /system logging action."
    )


@mcp.tool(name="get_log_statistics", annotations=annotate(READ, "Log Statistics"))
async def mikrotik_get_log_statistics(ctx: Context, device: Optional[str] = None) -> str:
    """Gets log entry counts by topic and severity from the MikroTik device."""
    await ctx.info("Getting log statistics")

    total_cmd = "/log print count-only"
    total_count = await execute_mikrotik_command(total_cmd, ctx, device=device)

    stats = [f"Total log entries: {total_count.strip()}"]

    topics = ["info", "warning", "error", "system", "dhcp", "firewall", "interface"]
    for topic in topics:
        count_cmd = f'/log print count-only where topics~"{topic}"'
        count = await execute_mikrotik_command(count_cmd, ctx, device=device)
        if count.strip().isdigit() and int(count.strip()) > 0:
            stats.append(f"{topic.capitalize()}: {count.strip()}")

    recent_cmd = "/log print count-only where time > ([:timestamp] - 1h)"
    recent_count = await execute_mikrotik_command(recent_cmd, ctx, device=device)
    stats.append(f"\nEntries in last hour: {recent_count.strip()}")

    today_cmd = "/log print count-only where time > ([:timestamp] - 1d)"
    today_count = await execute_mikrotik_command(today_cmd, ctx, device=device)
    stats.append(f"Entries in last 24 hours: {today_count.strip()}")

    return "LOG STATISTICS:\n\n" + "\n".join(stats)


@mcp.tool(name="export_logs", annotations=annotate(WRITE, "Export Logs"))
async def mikrotik_export_logs(
    ctx: Context,
    filename: Optional[str] = None,
    topics: Optional[str] = None,
    time_filter: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Exports logs to a .txt file on the MikroTik device with optional topic and time filters."""
    if not filename:
        filename = f"logs_export_{int(time.time())}"

    await ctx.info(f"Exporting logs to file: {filename}")

    cmd = f"/log print file={filename}"

    filters = []
    if topics:
        topic_list = [t.strip() for t in topics.split(',') if t.strip()]
        if topic_list:
            filters.append(f'topics~"({"|".join(topic_list)})"')

    if time_filter:
        try:
            filters.append(_time_clause(time_filter))
        except ValueError as exc:
            return f"Error: {exc}"

    if filters:
        cmd += " where " + " and ".join(filters)

    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if not result.strip():
        return f"Logs exported to file: {filename}.txt"
    return f"Export result: {result}"


@mcp.tool(name="monitor_logs", annotations=annotate(READ, "Monitor Logs"))
async def mikrotik_monitor_logs(
    ctx: Context,
    topics: Optional[str] = None,
    duration: int = 10,
    device: Optional[str] = None
) -> str:
    """Watches for new log entries for a limited duration (max 60s) and returns them.

    Notes:
        duration: seconds to wait for new entries, capped at 60
    """
    duration = max(1, min(duration, 60))
    await ctx.info(f"Monitoring logs for {duration} seconds")

    # A non-interactive channel cannot stream "/log print follow", so take a
    # count snapshot, wait, and return whatever arrived in between.
    before = await execute_mikrotik_command("/log print count-only", ctx, device=device)
    await asyncio.sleep(duration)
    after = await execute_mikrotik_command("/log print count-only", ctx, device=device)

    try:
        new_entries = int(after.strip()) - int(before.strip())
    except ValueError:
        return f"Error reading log counts: before={before.strip()!r} after={after.strip()!r}"

    if new_entries <= 0:
        return f"LOG MONITOR: no new log entries in the last {duration} seconds."

    cmd = "/log print"
    if topics:
        topic_list = [t.strip() for t in topics.split(',') if t.strip()]
        if topic_list:
            cmd += f' where topics~"({"|".join(topic_list)})"'

    result = await execute_mikrotik_command(cmd, ctx, device=device)
    return (
        f"LOG MONITOR ({new_entries} new entries in {duration}s):\n\n"
        f"{_tail(result, new_entries)}"
    )
