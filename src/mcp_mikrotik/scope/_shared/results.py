"""Reading what RouterOS answers to a write command.

A write that works prints nothing (or, wrapped in `:put [...]`, the id of what it created). A refusal does not always say "failure:"
or "error": `input does not match any value of interface`, `invalid value for argument vlan-id`, `expected end of command (line 1
column 40)`, `not enough permissions (9)` and `no such item (4)` say neither. And a set, remove, enable or disable through
`[find ...]` that matches nothing is not even a refusal: RouterOS prints nothing and changes nothing, so a tool that only looks at
the answer reports success for a name that does not exist. Hence the two questions a tool asks: is there something to change
(`is_missing`, or `no_such_item` for an internal id), and did RouterOS refuse the change (`refused`).
"""


import re

from mcp.server.mcpserver.exceptions import ToolError

# How the RouterOS console reports a command it would not run. A read tool that
# looks for a data marker (`address=`, `uptime`, ...) must not mistake one of
# these for "nothing configured".
_ROUTEROS_ERROR = re.compile(
    r"^\s*(?:bad command name|syntax error|expected |input does not match|"
    r"invalid value|ambiguous value|not enough permissions|no such command|"
    r"failure:|error:)"
    r"|\(line \d+ column \d+\)",
    re.IGNORECASE | re.MULTILINE,
)


def routeros_error(result: str) -> bool:
    """True when ``result`` is RouterOS refusing the command rather than data."""
    return bool(result and _ROUTEROS_ERROR.search(result))


def raise_if_routeros_error(result: str, what: str = "run the command") -> None:
    """Raise ToolError carrying RouterOS's own words when a read was refused.

    Read tools call this before their "No ... found" fallback, so a refused
    command (missing package, lack of permission, syntax) is reported as an
    error with its text instead of looking like an empty table.
    """
    if routeros_error(result):
        raise ToolError(f"RouterOS refused to {what}: {result.strip()}")


def refused(result: str) -> bool:
    """True when RouterOS printed anything in answer to a write: a write that worked is silent."""
    return bool(result.strip())


def no_such_item(result: str) -> bool:
    """True for the answer to a command that names an internal id (`*1F`) or a position that does not exist."""
    return "no such item" in result.lower()


async def is_missing(menu: str, where: str, ctx, device, execute) -> bool:
    """True when RouterOS counts no item of ``menu`` that matches ``where`` (for example `name="x"`).

    Any other answer, a refusal for lack of permissions included, is not "missing": the write that follows reports it.
    """
    count = await execute(f"{menu} print count-only where {where}", ctx, device=device)
    return count.strip() == "0"
