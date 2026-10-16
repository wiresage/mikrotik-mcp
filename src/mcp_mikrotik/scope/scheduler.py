"""Read-only views over `/system scheduler` and `/system script`.

Script bodies are withheld by default. A stored RouterOS script is a common
place to find a credential in clear text — an FTP password for a backup job,
an SMTP login for an alert — and a read tool that dumps every body by default
turns one careless script into an exposure. Ask for `include_source=True` when
you need the body, and even then the output is passed through the server's
redaction before it is returned.
"""

from typing import Optional

from mcp.server.mcpserver import Context

from ..app import mcp, READ, annotate
from ..connector import execute_mikrotik_command
from ..sensitive import redact_sensitive_text

# Everything a script has except `source`.
_SCRIPT_METADATA = (
    "name,owner,policy,dont-require-permissions,run-count,last-started,invalid,comment"
)


@mcp.tool(name="list_schedulers", annotations=annotate(READ, "List Schedulers"))
async def mikrotik_list_schedulers(
    ctx: Context,
    name_filter: Optional[str] = None,
    device: Optional[str] = None
) -> str:
    """Lists the scheduled tasks with their interval, next run and run count.

    Notes:
        `name_filter` is a substring match. Read `next-run` together with
        `interval`: a scheduler whose `run-count` is not advancing is firing
        into a script that errors out, which RouterOS does not surface here —
        it shows up in the log under the `script` topic.

        `on-event` is passed through the server's redaction, since a scheduler
        can carry commands inline rather than calling a named script.
    """
    await ctx.info("Listing schedulers")
    command = "/system scheduler print detail"
    if name_filter:
        command += f' where name~"{name_filter}"'

    result = await execute_mikrotik_command(command, ctx, device=device)
    if not result or "name=" not in result:
        return "No schedulers found matching the criteria."
    return f"SCHEDULERS:\n\n{redact_sensitive_text(result)}"


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
        command += f' where name~"{name_filter}"'

    result = await execute_mikrotik_command(command, ctx, device=device)
    if not result or "name=" not in result:
        return "No scripts found matching the criteria."

    heading = "SCRIPTS (with source)" if include_source else "SCRIPTS (metadata only)"
    return f"{heading}:\n\n{redact_sensitive_text(result)}"
