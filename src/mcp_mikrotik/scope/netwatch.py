"""Read-only view over `/tool netwatch`.

A configuration export shows which probes exist; what it cannot give you is
the live state — `since`, and on an ICMP probe the measurements themselves
(`rtt-avg`, `loss-percent`, `failed-tests`) — which is what says whether a
monitored host is up right now, and how badly. That needs a second command:
`print detail` returns no read-only argument but `status`.

Three properties hold scripts: `up-script`, `down-script` and `test-script`.
They are withheld by default. A netwatch probe fires commands on every
transition, and those commands are a common place to find a credential in
clear text — a bot token inside a webhook URL, an SMTP `password=` on an
alert mail — which is the same exposure `scheduler.py` gates for
`/system script`. Ask for `include_source=True` when you need to read what a
probe runs, and even then the output goes through the server's redaction.
"""

from typing import Optional

from mcp.server.mcpserver import Context

from ..app import mcp, READ, annotate
from ..connector import execute_mikrotik_command
from ..sensitive import redact_sensitive_text

# What `print detail` is willing to return: configuration, plus `status`.
# A proplist is a whitelist, so anything missing here is silently lost.
# Measured on RouterOS 7.24.2, 7.24.4 and 7.24.5: `print detail` emits no
# read-only argument other than `status`, not even when the proplist names
# one explicitly — `proplist=host,status,since` comes back as
# `host=... status=...`. The live values are read separately, below.
_PROBE_CONFIG = ",".join((
    # Identity and scheduling.
    "name", "host", "type", "src-address", "interval", "timeout",
    "start-delay", "startup-delay", "ignore-initial-up", "ignore-initial-down",
    "comment", "disabled",
    # ICMP probe: what it sends and what counts as a failure.
    "packet-interval", "packet-count", "packet-size", "ttl",
    "accept-icmp-time-exceeded", "early-success-detection",
    "early-failure-detection", "thr-max", "thr-avg", "thr-stdev", "thr-jitter",
    "thr-loss-percent", "thr-loss-count",
    # TCP, HTTP/S and DNS probes.
    "port", "thr-tcp-conn-time", "thr-http-time", "http-codes", "certificate",
    "check-certificate", "record-type", "dns-server",
    # The one read-only argument `print detail` does return.
    "status",
))

# The live state, which only the non-detail print carries. Two other ways to
# ask for it were measured and rejected: the plain table silently drops the
# columns that do not fit the terminal width (fourteen asked for, seven came
# back), and `print value-list` follows `print detail` and omits them too.
# `as-value` is neither tabular nor paged, so nothing is truncated, and it
# adds `.id` and `comment` on its own — `.id` is rejected in a proplist.
_PROBE_STATE = ",".join((
    "host", "status", "since", "done-tests", "failed-tests", "sent-count",
    "response-count", "loss-count", "loss-percent", "rtt-avg", "rtt-min",
    "rtt-max", "rtt-jitter", "rtt-stdev", "tcp-connect-time",
    "http-status-code", "http-resp-time",
))


def _split_records(value: str) -> str:
    """One `as-value` record per line.

    The records come back concatenated into a single line with `;`, so
    `.id=` is the only safe boundary: a `comment` or a script may contain a
    semicolon of its own, and RouterOS scripts usually do.
    """
    return value.strip().replace(";.id=", "\n.id=")


@mcp.tool(name="list_netwatch", annotations=annotate(READ, "List Netwatch Probes"))
async def mikrotik_list_netwatch(
    ctx: Context,
    host_filter: Optional[str] = None,
    comment_filter: Optional[str] = None,
    status_filter: Optional[str] = None,
    type_filter: Optional[str] = None,
    include_source: bool = False,
    device: Optional[str] = None
) -> str:
    """Lists the netwatch probes with their live status and measurements.

    Configuration first, then a LIVE STATE block with `status`, `since` — the
    timestamp of the last transition — and, on an ICMP probe, the last test's
    numbers: `rtt-avg`, `loss-percent`, `failed-tests`. Match the two blocks
    by `host`, or by the `.id` the live one carries.

    Notes:
        `host_filter` and `comment_filter` are substring matches; `status_filter`
        and `type_filter` are exact. Pass `status_filter="down"` to list only
        what is currently failing.

        `include_source=False` (the default) omits `up-script`,
        `down-script` and `test-script`, because a probe that alerts through a
        webhook or an e-mail carries the token or the password inline. Set it
        to True only when you intend to read those commands; the output is
        redacted either way, but redaction is pattern-based and is not a
        guarantee.

        A probe with no `src-address` follows whichever WAN is active, so it
        keeps reporting across a failover; one pinned to a source address
        reports that path only. Which of the two you want depends on whether
        you are watching the internet or a specific link.
    """
    await ctx.info(
        "Listing netwatch probes with scripts" if include_source
        else "Listing netwatch probes (status only)"
    )
    command = "/tool netwatch print detail"
    if not include_source:
        command += f" proplist={_PROBE_CONFIG}"
    filters = []
    if host_filter:
        filters.append(f'host~"{host_filter}"')
    if comment_filter:
        filters.append(f'comment~"{comment_filter}"')
    if status_filter:
        filters.append(f'status="{status_filter}"')
    if type_filter:
        filters.append(f'type="{type_filter}"')
    if filters:
        command += " where " + " ".join(filters)

    result = await execute_mikrotik_command(command, ctx, device=device)
    # `print detail` prints the Flags legend (non-empty) even when no row
    # matches, so emptiness is decided by real entry data, not by length.
    if not result or "host=" not in result:
        return "No netwatch probes found matching the criteria."

    heading = "NETWATCH PROBES (with scripts)" if include_source else "NETWATCH PROBES"
    out = f"{heading}:\n\n{redact_sensitive_text(result)}"

    state_command = f":put [/tool netwatch print as-value proplist={_PROBE_STATE}]"
    if filters:
        state_command = state_command[:-1] + " where " + " ".join(filters) + "]"
    state = await execute_mikrotik_command(state_command, ctx, device=device)
    # A refusal prints on stdout with a zero exit status, so anything without
    # a record is treated as one. The live state is an addition: failing to
    # read it must not cost the caller the configuration already in hand.
    if state and "host=" in state:
        out += f"\n\nLIVE STATE:\n\n{_split_records(redact_sensitive_text(state))}"
    return out
