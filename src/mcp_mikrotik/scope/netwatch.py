"""Read-only view over `/tool netwatch`.

A configuration export shows which probes exist; only `print detail` carries
the live state — `status`, `since`, and on an ICMP probe the measurements
themselves (`rtt-avg`, `loss-percent`, `failed-tests`) — which is what says
whether a monitored host is up right now, and how badly.

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

# Every property `/tool netwatch` has except the three that hold scripts.
# A proplist is a whitelist, so anything missing here is silently lost: the
# measurements below are the reason to call this tool rather than read an
# export, and dropping them to hide the scripts would trade one gap for
# another. Listed against the CLI reference for 7.26; properties added after
# 7.16 (`ttl`, `accept-icmp-time-exceeded`, the DNS probe), 7.17
# (`ignore-initial-*`) and 7.20 (`early-*-detection`) are included, and this
# has only been exercised on 7.24.5 — see the note in the pull request.
_PROBE_METADATA = ",".join((
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
    # Read-only: the state and the measurements an export cannot give you.
    "status", "since", "done-tests", "failed-tests", "sent-count",
    "response-count", "loss-count", "loss-percent", "rtt-avg", "rtt-min",
    "rtt-max", "rtt-jitter", "rtt-stdev", "tcp-connect-time",
    "http-status-code", "http-resp-time", "ip", "ip6",
))


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

    Each entry reports `status` (up / down / unknown), `since` — the timestamp
    of the last transition — and, on an ICMP probe, the last test's numbers:
    `rtt-avg`, `loss-percent`, `failed-tests`. None of that is in an export.

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
        command += f" proplist={_PROBE_METADATA}"
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
    return f"{heading}:\n\n{redact_sensitive_text(result)}"
