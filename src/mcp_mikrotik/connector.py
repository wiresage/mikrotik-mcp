import asyncio
import logging
from typing import Optional, Sequence

from mcp.server.mcpserver import Context

from .inventory import DeviceNotFoundError, get_inventory
from .sensitive import REDACTED, redact_if_enabled

logger = logging.getLogger(__name__)


def _redacted(text: str, secrets: Optional[Sequence[str]]) -> str:
    """Blank out secret values before anything is logged.

    Commands are logged to the server log and sent to the client as a log
    notification, so a tool carrying a credential has no way to keep it out
    of either sink on its own (issue #151). Longest first, so one secret
    that contains another cannot leave a fragment behind.
    """
    if not secrets:
        return text
    for secret in sorted((s for s in secrets if s), key=len, reverse=True):
        text = text.replace(secret, REDACTED)
    return text


def _shown(text: str, secrets: Optional[Sequence[str]]) -> str:
    """What the logs and client notifications may show of ``text``.

    Values a tool declared are always blanked, whatever the server mode.
    Sensitive-hiding mode then also blanks anything that looks like a
    credential. Declared values go first: a secret containing a quote or a
    comma is gone before the pattern pass could split it and leave its tail.
    """
    return redact_if_enabled(_redacted(text, secrets), secrets or ())


def _execute_sync(
    command: str,
    device: Optional[str] = None,
    redact: Optional[Sequence[str]] = None,
) -> str:
    """Execute a MikroTik command over a fresh SSH connection (blocking).

    Each call opens its own connection and closes it again, so concurrent
    sessions never share a client.
    """
    inventory = get_inventory()
    target = inventory.resolve(device)
    logger.info("Executing MikroTik command on '%s': %s", target.title, _shown(command, redact))

    with inventory.session(target.title) as client:
        result = client.execute_command(command)

    logger.info("Command result: %r", _shown(result, redact))
    return result


def download_file_sync(filename: str, device: Optional[str] = None) -> bytes:
    """Download a file from the target device over SFTP and return its bytes."""
    inventory = get_inventory()
    target = inventory.resolve(device)
    logger.info(f"Downloading file from '{target.title}': {filename}")

    with inventory.session(target.title) as client:
        return client.download_file(filename)


def upload_file_sync(filename: str, data: bytes, device: Optional[str] = None) -> None:
    """Upload bytes to a file on the target device over SFTP."""
    inventory = get_inventory()
    target = inventory.resolve(device)
    logger.info(f"Uploading file to '{target.title}': {filename} ({len(data)} bytes)")

    with inventory.session(target.title) as client:
        client.upload_file(filename, data)


async def execute_mikrotik_command(
    command: str,
    ctx: Context,
    device: Optional[str] = None,
    redact: Optional[Sequence[str]] = None,
) -> str:
    """Execute a MikroTik command on the selected device and return the output.

    ``device`` is the inventory title of the target. It may be omitted when the
    inventory holds exactly one device.

    ``redact`` lists values that must not reach the logs: each is replaced
    with ``***`` in the server log and in the notification sent to the
    client, in every server mode. The command itself is sent to the device
    unchanged, and the result is returned to the caller unchanged.

    When Safe Mode is active *for that device* the command is routed through
    that device's persistent interactive shell so it runs inside the safe-mode
    context.
    """
    from .safe_mode import get_safe_mode_manager

    # Resolve the target first so a bad/missing device is reported clearly and
    # never silently executed somewhere else.
    try:
        target = get_inventory().resolve(device)
    except DeviceNotFoundError as exc:
        msg = f"Error: {exc}"
        await ctx.error(msg)
        return msg

    safe_mgr = get_safe_mode_manager(target.title)
    if safe_mgr.is_active:
        await ctx.info(_shown(f"Executing on '{target.title}' (safe mode): {command}", redact))
        try:
            result = await asyncio.to_thread(safe_mgr.execute, command)
        except Exception as e:
            result = f"Error executing command in safe mode session: {str(e)}"
    else:
        await ctx.info(_shown(f"Executing on '{target.title}': {command}", redact))
        try:
            result = await asyncio.to_thread(_execute_sync, command, target.title, redact)
        except ConnectionError as e:
            result = f"Error: {str(e)}"
        except Exception as e:
            result = f"Error executing command: {str(e)}"

    logger.info("Command result: %r", _shown(result, redact))
    if result.startswith("Error"):
        await ctx.error(_shown(result, redact))
    return result
