"""Management and inspection tools for `/system scheduler` and `/system script`.

Script bodies and scheduler event commands are withheld by default in list
views. Stored RouterOS scripts and schedulers are common places to find
credentials in clear text — an FTP password for a backup job, an SMTP login for
an alert — and dumping every body by default turns one careless script into an
exposure. Ask for `include_source=True` when you need the body, and even then
the output is passed through the server's redaction before it is returned.
"""

import re
from typing import Optional

from mcp.server.mcpserver import Context

from ..app import mcp, READ, WRITE_IDEMPOTENT, DESTRUCTIVE, annotate
from ..connector import execute_mikrotik_command
from ._quoting import ros_quoted
from ._selectors import has_item_rows
from ..sensitive import redact_sensitive_text

_NAME_RE = re.compile(r"^[a-zA-Z0-9_.\-]+$")
_JOB_ID_RE = re.compile(r"^(\*?[0-9a-fA-F]+|[0-9]+)$")

# Everything a script has except `source`.
_SCRIPT_METADATA = (
    "name,owner,policy,dont-require-permissions,run-count,last-started,invalid,comment"
)

# Everything a scheduler has except `on-event`.
_SCHEDULER_METADATA = (
    "name,start-date,start-time,interval,owner,policy,run-count,next-run,comment,disabled"
)


# ---------------------------------------------------------------------------
# Schedulers (/system scheduler)
# ---------------------------------------------------------------------------

@mcp.tool(name="list_schedulers", annotations=annotate(READ, "List Schedulers"))
async def mikrotik_list_schedulers(
    ctx: Context,
    name_filter: Optional[str] = None,
    include_source: bool = False,
    device: Optional[str] = None,
) -> str:
    """Lists the scheduled tasks with their interval, next run and run count."""
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


@mcp.tool(name="get_scheduler", annotations=annotate(READ, "Get Scheduler"))
async def mikrotik_get_scheduler(
    ctx: Context,
    name: str,
    device: Optional[str] = None,
) -> str:
    """Gets details, interval, next run and on-event code of a specific scheduler."""
    if not _NAME_RE.match(name):
        return f"Invalid scheduler name: '{name}'"

    await ctx.info(f"Getting scheduler: {name}")
    command = f'/system scheduler print detail where name="{ros_quoted(name)}"'
    result = await execute_mikrotik_command(command, ctx, device=device)

    if not has_item_rows(result):
        return f"Scheduler '{name}' not found."

    return f"SCHEDULER DETAILS ({name}):\n\n{redact_sensitive_text(result)}"


@mcp.tool(name="create_scheduler", annotations=annotate(WRITE_IDEMPOTENT, "Create Scheduler"))
async def mikrotik_create_scheduler(
    ctx: Context,
    name: str,
    on_event: str,
    interval: str = "1d",
    start_date: Optional[str] = None,
    start_time: Optional[str] = None,
    policy: Optional[str] = None,
    comment: Optional[str] = None,
    disabled: bool = False,
    device: Optional[str] = None,
) -> str:
    """Creates a new scheduled task in RouterOS."""
    if not _NAME_RE.match(name):
        return f"Invalid scheduler name: '{name}'"

    await ctx.info(f"Creating scheduler: {name}")
    cmd = f'/system scheduler add name="{ros_quoted(name)}" on-event="{ros_quoted(on_event)}" interval="{ros_quoted(interval)}"'

    if start_date:
        cmd += f' start-date="{ros_quoted(start_date)}"'
    if start_time:
        cmd += f' start-time="{ros_quoted(start_time)}"'
    if policy:
        cmd += f' policy="{ros_quoted(policy)}"'
    if comment:
        cmd += f' comment="{ros_quoted(comment)}"'
    if disabled:
        cmd += " disabled=yes"

    result = await execute_mikrotik_command(cmd, ctx, device=device)
    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to create scheduler: {result}"

    return f"Scheduler '{name}' created successfully."


@mcp.tool(name="update_scheduler", annotations=annotate(WRITE_IDEMPOTENT, "Update Scheduler"))
async def mikrotik_update_scheduler(
    ctx: Context,
    name: str,
    on_event: Optional[str] = None,
    interval: Optional[str] = None,
    start_date: Optional[str] = None,
    start_time: Optional[str] = None,
    policy: Optional[str] = None,
    comment: Optional[str] = None,
    disabled: Optional[bool] = None,
    device: Optional[str] = None,
) -> str:
    """Updates an existing scheduled task in RouterOS."""
    if not _NAME_RE.match(name):
        return f"Invalid scheduler name: '{name}'"

    updates = []
    if on_event is not None:
        updates.append(f'on-event="{ros_quoted(on_event)}"')
    if interval is not None:
        updates.append(f'interval="{ros_quoted(interval)}"')
    if start_date is not None:
        updates.append(f'start-date="{ros_quoted(start_date)}"')
    if start_time is not None:
        updates.append(f'start-time="{ros_quoted(start_time)}"')
    if policy is not None:
        updates.append(f'policy="{ros_quoted(policy)}"')
    if comment is not None:
        updates.append(f'comment="{ros_quoted(comment)}"')
    if disabled is not None:
        updates.append(f'disabled={"yes" if disabled else "no"}')

    if not updates:
        return "No updates specified."

    await ctx.info(f"Updating scheduler: {name}")
    cmd = f'/system scheduler set [find name="{ros_quoted(name)}"] ' + " ".join(updates)
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower() or "no such item" in result.lower():
        return f"Failed to update scheduler: {result}"

    return f"Scheduler '{name}' updated successfully."


@mcp.tool(name="enable_scheduler", annotations=annotate(WRITE_IDEMPOTENT, "Enable Scheduler"))
async def mikrotik_enable_scheduler(
    ctx: Context,
    name: str,
    device: Optional[str] = None,
) -> str:
    """Enables a scheduled task by name."""
    if not _NAME_RE.match(name):
        return f"Invalid scheduler name: '{name}'"

    await ctx.info(f"Enabling scheduler: {name}")
    cmd = f'/system scheduler enable [find name="{ros_quoted(name)}"]'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to enable scheduler: {result}"

    return f"Scheduler '{name}' enabled successfully."


@mcp.tool(name="disable_scheduler", annotations=annotate(WRITE_IDEMPOTENT, "Disable Scheduler"))
async def mikrotik_disable_scheduler(
    ctx: Context,
    name: str,
    device: Optional[str] = None,
) -> str:
    """Disables a scheduled task by name."""
    if not _NAME_RE.match(name):
        return f"Invalid scheduler name: '{name}'"

    await ctx.info(f"Disabling scheduler: {name}")
    cmd = f'/system scheduler disable [find name="{ros_quoted(name)}"]'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to disable scheduler: {result}"

    return f"Scheduler '{name}' disabled successfully."


@mcp.tool(name="remove_scheduler", annotations=annotate(DESTRUCTIVE, "Remove Scheduler"))
async def mikrotik_remove_scheduler(
    ctx: Context,
    name: str,
    device: Optional[str] = None,
) -> str:
    """Removes a scheduled task by name."""
    if not _NAME_RE.match(name):
        return f"Invalid scheduler name: '{name}'"

    await ctx.info(f"Removing scheduler: {name}")
    cmd = f'/system scheduler remove [find name="{ros_quoted(name)}"]'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to remove scheduler: {result}"

    return f"Scheduler '{name}' removed successfully."


# ---------------------------------------------------------------------------
# Scripts (/system script)
# ---------------------------------------------------------------------------

@mcp.tool(name="list_scripts", annotations=annotate(READ, "List Scripts"))
async def mikrotik_list_scripts(
    ctx: Context,
    name_filter: Optional[str] = None,
    include_source: bool = False,
    device: Optional[str] = None,
) -> str:
    """Lists the stored scripts: owner, policy, run count and last start."""
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


@mcp.tool(name="get_script", annotations=annotate(READ, "Get Script"))
async def mikrotik_get_script(
    ctx: Context,
    name: str,
    device: Optional[str] = None,
) -> str:
    """Gets details, policies, run stats and source code of a specific script."""
    if not _NAME_RE.match(name):
        return f"Invalid script name: '{name}'"

    await ctx.info(f"Getting script: {name}")
    command = f'/system script print detail where name="{ros_quoted(name)}"'
    result = await execute_mikrotik_command(command, ctx, device=device)

    if not has_item_rows(result):
        return f"Script '{name}' not found."

    return f"SCRIPT DETAILS ({name}):\n\n{redact_sensitive_text(result)}"


@mcp.tool(name="run_script", annotations=annotate(DESTRUCTIVE, "Run Script"))
async def mikrotik_run_script(
    ctx: Context,
    name: str,
    device: Optional[str] = None,
) -> str:
    """Executes a stored RouterOS script by name."""
    if not _NAME_RE.match(name):
        return f"Invalid script name: '{name}'"

    await ctx.info(f"Running script: {name}")
    command = f'/system script run [find name="{ros_quoted(name)}"]'
    result = await execute_mikrotik_command(command, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower() or "no such item" in result.lower():
        return f"Failed to run script: {result}"

    stripped = result.strip()
    if stripped:
        return f"SCRIPT OUTPUT ({name}):\n\n{redact_sensitive_text(stripped)}"
    return f"Script '{name}' executed successfully."


@mcp.tool(name="create_script", annotations=annotate(WRITE_IDEMPOTENT, "Create Script"))
async def mikrotik_create_script(
    ctx: Context,
    name: str,
    source: str,
    policy: Optional[str] = None,
    dont_require_permissions: bool = False,
    comment: Optional[str] = None,
    device: Optional[str] = None,
) -> str:
    """Creates a new stored RouterOS script."""
    if not _NAME_RE.match(name):
        return f"Invalid script name: '{name}'"

    await ctx.info(f"Creating script: {name}")
    cmd = f'/system script add name="{ros_quoted(name)}" source="{ros_quoted(source)}"'

    if policy:
        cmd += f' policy="{ros_quoted(policy)}"'
    if dont_require_permissions:
        cmd += " dont-require-permissions=yes"
    if comment:
        cmd += f' comment="{ros_quoted(comment)}"'

    result = await execute_mikrotik_command(cmd, ctx, device=device)
    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to create script: {result}"

    return f"Script '{name}' created successfully."


@mcp.tool(name="update_script", annotations=annotate(WRITE_IDEMPOTENT, "Update Script"))
async def mikrotik_update_script(
    ctx: Context,
    name: str,
    source: Optional[str] = None,
    policy: Optional[str] = None,
    dont_require_permissions: Optional[bool] = None,
    comment: Optional[str] = None,
    device: Optional[str] = None,
) -> str:
    """Updates an existing stored RouterOS script."""
    if not _NAME_RE.match(name):
        return f"Invalid script name: '{name}'"

    updates = []
    if source is not None:
        updates.append(f'source="{ros_quoted(source)}"')
    if policy is not None:
        updates.append(f'policy="{ros_quoted(policy)}"')
    if dont_require_permissions is not None:
        updates.append(f'dont-require-permissions={"yes" if dont_require_permissions else "no"}')
    if comment is not None:
        updates.append(f'comment="{ros_quoted(comment)}"')

    if not updates:
        return "No updates specified."

    await ctx.info(f"Updating script: {name}")
    cmd = f'/system script set [find name="{ros_quoted(name)}"] ' + " ".join(updates)
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower() or "no such item" in result.lower():
        return f"Failed to update script: {result}"

    return f"Script '{name}' updated successfully."


@mcp.tool(name="remove_script", annotations=annotate(DESTRUCTIVE, "Remove Script"))
async def mikrotik_remove_script(
    ctx: Context,
    name: str,
    device: Optional[str] = None,
) -> str:
    """Removes a stored RouterOS script by name."""
    if not _NAME_RE.match(name):
        return f"Invalid script name: '{name}'"

    await ctx.info(f"Removing script: {name}")
    cmd = f'/system script remove [find name="{ros_quoted(name)}"]'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to remove script: {result}"

    return f"Script '{name}' removed successfully."


# ---------------------------------------------------------------------------
# Script Jobs (/system script job)
# ---------------------------------------------------------------------------

@mcp.tool(name="list_script_jobs", annotations=annotate(READ, "List Script Jobs"))
async def mikrotik_list_script_jobs(
    ctx: Context,
    device: Optional[str] = None,
) -> str:
    """Lists currently running script jobs and background tasks."""
    await ctx.info("Listing script jobs")
    command = "/system script job print detail"
    result = await execute_mikrotik_command(command, ctx, device=device)

    if not result or not has_item_rows(result):
        return "No active script jobs running."

    return f"SCRIPT JOBS:\n\n{result}"


@mcp.tool(name="remove_script_job", annotations=annotate(DESTRUCTIVE, "Remove Script Job"))
async def mikrotik_remove_script_job(
    ctx: Context,
    job_id: str,
    device: Optional[str] = None,
) -> str:
    """Stops and removes a running script job by ID."""
    job_id_clean = job_id.strip()
    if not _JOB_ID_RE.match(job_id_clean):
        return f"Invalid script job ID: '{job_id}'"

    await ctx.info(f"Removing script job: {job_id_clean}")
    cmd = f"/system script job remove {job_id_clean}"
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower() or "no such item" in result.lower():
        return f"Failed to remove script job: {result}"

    return f"Script job '{job_id_clean}' stopped and removed successfully."


# ---------------------------------------------------------------------------
# Script Environment (/system script environment)
# ---------------------------------------------------------------------------

@mcp.tool(name="list_script_environment", annotations=annotate(READ, "List Script Environment"))
async def mikrotik_list_script_environment(
    ctx: Context,
    device: Optional[str] = None,
) -> str:
    """Lists RouterOS global variables and environment entries."""
    await ctx.info("Listing script environment")
    command = "/system script environment print detail"
    result = await execute_mikrotik_command(command, ctx, device=device)

    if not result or not has_item_rows(result):
        return "No script environment variables defined."

    return f"SCRIPT ENVIRONMENT:\n\n{redact_sensitive_text(result)}"


@mcp.tool(name="remove_script_environment", annotations=annotate(DESTRUCTIVE, "Remove Script Environment"))
async def mikrotik_remove_script_environment(
    ctx: Context,
    name: str,
    device: Optional[str] = None,
) -> str:
    """Removes a global variable from the RouterOS script environment."""
    if not _NAME_RE.match(name):
        return f"Invalid variable name: '{name}'"

    await ctx.info(f"Removing script environment variable: {name}")
    cmd = f'/system script environment remove [find name="{ros_quoted(name)}"]'
    result = await execute_mikrotik_command(cmd, ctx, device=device)

    if "failure:" in result.lower() or "error" in result.lower():
        return f"Failed to remove script environment variable: {result}"

    return f"Script environment variable '{name}' removed successfully."
