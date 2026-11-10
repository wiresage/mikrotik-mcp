"""Read-only views over `/system scheduler` and `/system script`.

Script bodies are withheld by default. A stored RouterOS script is a common
place to find a credential in clear text — an FTP password for a backup job,
an SMTP login for an alert — and a read tool that dumps every body by default
turns one careless script into an exposure. Ask for `include_source=True` when
you need the body, and even then the output is passed through the server's
redaction before it is returned.

The same goes for a scheduler's `on-event`, which can carry the same commands inline.
"""

from typing import Optional

from mcp.server.mcpserver import Context

from ...app import mcp, READ, annotate
from ...connector import execute_mikrotik_command
from .._shared.quoting import ros_quoted
from ...sensitive import redact_sensitive_text

# Everything a script has except `source`.
_SCRIPT_METADATA = (
    "name,owner,policy,dont-require-permissions,run-count,last-started,invalid,comment"
)


# Everything a scheduler has except `on-event`.
_SCHEDULER_METADATA = (
    "name,start-date,start-time,interval,owner,policy,run-count,next-run,comment,disabled"
)


@mcp.tool(name="list_schedulers", annotations=annotate(READ, "List Schedulers"))
async def mikrotik_list_schedulers(
    ctx: Context,
    name_filter: Optional[str] = None,
    include_source: bool = False,
    device: Optional[str] = None
) -> str:
    """Lists the scheduled tasks with their interval, next run and run count.

    Notes:
        `name_filter` is a substring match. Read `next-run` together with
        `interval`: a scheduler whose `run-count` is not advancing is firing
        into a script that errors out, which RouterOS does not surface here —
        it shows up in the log under the `script` topic.

        `include_source=False` (the default) omits `on-event`, because a
        scheduler can carry commands inline, and those routinely hold a bot
        token or a password inside a URL. Redaction only recognises labelled
        secrets, so withholding the field is what keeps them off the wire. Set
        it to True only when you intend to read the commands; the output is
        redacted either way, but redaction is pattern-based and is not a
        guarantee.
    """
    await ctx.info(
        "Listing schedulers with on-event" if include_source else "Listing schedulers (metadata only)"
    )
    command = "/system scheduler print detail"
    if not include_source:
        command += f" proplist={_SCHEDULER_METADATA}"
    if name_filter:
        command += f' where name~"{ros_quoted(name_filter)}"'

    result = await execute_mikrotik_command(command, ctx, device=device)
    if not result or "name=" not in result:
        return "No schedulers found matching the criteria."

    heading = "SCHEDULERS (with on-event)" if include_source else "SCHEDULERS (metadata only)"
    return f"{heading}:\n\n{redact_sensitive_text(result)}"


@mcp.tool(name="list_scripts", annotations=annotate(READ, "List Scripts"))
async def mikrotik_list_scripts(
    ctx: Context,
    name_filter: Optional[str] = None,
    include_source: bool = False,
    device: Optional[str] = None
) -> str:
    """Lists the stored scripts: owner, policy, run count and last start.

    Notes:
        `include_source=False` (the default) omits the script body, because
        bodies routinely hold credentials in clear text. Set it to True only
        when you intend to read the code; the output is redacted either way,
        but redaction is pattern-based and is not a guarantee.

        `policy` is what the script may do when it runs, which can exceed what
        the user who scheduled it may do interactively.
    """
    await ctx.info(
        "Listing scripts with source" if include_source else "Listing scripts (metadata only)"
    )
    command = "/system script print detail"
    if not include_source:
        command += f" proplist={_SCRIPT_METADATA}"
    if name_filter:
        command += f' where name~"{ros_quoted(name_filter)}"'

    result = await execute_mikrotik_command(command, ctx, device=device)
    if not result or "name=" not in result:
        return "No scripts found matching the criteria."

    heading = "SCRIPTS (with source)" if include_source else "SCRIPTS (metadata only)"
    return f"{heading}:\n\n{redact_sensitive_text(result)}"
