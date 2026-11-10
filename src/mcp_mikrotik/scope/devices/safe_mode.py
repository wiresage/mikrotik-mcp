import asyncio
from typing import Optional

from mcp.server.mcpserver import Context

from ...app import mcp, READ, WRITE, annotate
from ...inventory import DeviceNotFoundError
from ...safe_mode import get_safe_mode_manager


@mcp.tool(name="safe_mode_status", annotations=annotate(READ, "Safe Mode Status"))
async def mikrotik_safe_mode_status(ctx: Context, device: Optional[str] = None) -> str:
    """Returns whether MikroTik Safe Mode is currently active."""
    await ctx.info(f"Checking safe mode status (device={device})")
    try:
        manager = get_safe_mode_manager(device)
    except DeviceNotFoundError as exc:
        return f"Error: {exc}"
    return manager.status()


@mcp.tool(name="enable_safe_mode", annotations=annotate(WRITE, "Enable Safe Mode"))
async def mikrotik_enable_safe_mode(ctx: Context, device: Optional[str] = None) -> str:
    """Activates MikroTik Safe Mode; changes are held in memory and auto-reverted on disconnect until committed."""
    await ctx.info(f"Enabling MikroTik safe mode (device={device})")
    try:
        manager = get_safe_mode_manager(device)
    except DeviceNotFoundError as exc:
        return f"Error: {exc}"
    return await asyncio.to_thread(manager.enable)


@mcp.tool(name="commit_safe_mode", annotations=annotate(WRITE, "Commit Safe Mode"))
async def mikrotik_commit_safe_mode(ctx: Context, device: Optional[str] = None) -> str:
    """Commits all pending Safe Mode changes to persistent storage and exits Safe Mode."""
    await ctx.info(f"Committing safe mode changes (device={device})")
    try:
        manager = get_safe_mode_manager(device)
    except DeviceNotFoundError as exc:
        return f"Error: {exc}"
    return await asyncio.to_thread(manager.commit)


@mcp.tool(name="rollback_safe_mode", annotations=annotate(WRITE, "Rollback Safe Mode"))
async def mikrotik_rollback_safe_mode(ctx: Context, device: Optional[str] = None) -> str:
    """Discards all pending Safe Mode changes by closing the SSH session, triggering automatic rollback."""
    await ctx.info(f"Rolling back safe mode changes (device={device})")
    try:
        manager = get_safe_mode_manager(device)
    except DeviceNotFoundError as exc:
        return f"Error: {exc}"
    return await asyncio.to_thread(manager.rollback)
