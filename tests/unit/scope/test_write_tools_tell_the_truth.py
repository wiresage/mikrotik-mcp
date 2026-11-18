"""A write tool must not say it worked when it did nothing.

Two routers that cannot succeed, and every write tool is called on both (the tools are found from the registry, so a new tool is
covered the moment it exists):

* EMPTY: nothing exists on it. It answers like RouterOS does: a set, remove, enable or disable through `[find ...]` that matches
  nothing is silent (no error, no change), an internal id that does not exist is "no such item (4)", a count is 0 and a print shows
  nothing but the Flags legend. A tool that changes an item by name or id must say that it found nothing.
* REFUSING: everything the tool looks at is there, but RouterOS refuses the write with a text that says neither "failure:" nor
  "error" ("input does not match any value of interface", "invalid value for argument vlan-id", ...). A tool must report it.
"""

import asyncio
import importlib
import inspect
import pkgutil
import re

import pytest

import mcp_mikrotik.app  # noqa: F401  (registers every tool)
import mcp_mikrotik.scope as scope_package
from mcp_mikrotik.app import mcp
from tests.conftest import make_dummy_value

# Tools that cannot run on a fake router or do not change an item by name or id (they have their own tests): they replace the
# whole configuration, drive a persistent shell, move files, or only run an action.
NOT_APPLICABLE = {
    "restore_backup", "import_configuration", "create_basic_firewall_setup",
    "enable_safe_mode", "commit_safe_mode", "rollback_safe_mode",
    "upload_file", "download_file", "create_backup", "create_export", "export_section", "export_logs", "export_dns_config",
    "export_user_config", "remove_file", "clear_logs", "flush_dns_cache", "flush_route_cache", "monitor_logs",
}

SUCCESS = re.compile(r"(?i)\b(successfully|created|added|updated|removed|deleted|enabled|disabled|moved|applied|expanded|cleared|flushed|imported|committed)\b")
FAILURE = re.compile(
    r"(?i)(fail|error|not found|no such|cannot|can't|unable|invalid|refus|denied|unknown|does not exist|expected|missing|"
    r"nothing to|no updates|not supported|could not|already|no entries|is not|not available|not applicable)"
)
TARGETED = ("update_", "remove_", "enable_", "disable_", "move_", "disconnect_", "expand_")
ID_PARAM = re.compile(r"(_id|^id)$")
PREFERRED_OPTIONS = ("comment", "disabled")


class Router:
    def __init__(self):
        self.commands = []

    async def __call__(self, command, _ctx, device=None, **kwargs):
        self.commands.append(command)
        return self.answer(command.strip(), command.strip().lower())


class EmptyRouter(Router):
    def answer(self, command, low):
        if "count-only" in low:
            return "0"
        if low.startswith(":put [:pick") or (low.startswith(":put [/") and " find" in low):
            return ""  # no item at that position, nothing found
        if re.search(r"\b(set|remove|enable|disable|move|unset)\s+(\*[0-9a-f]+|\d+)\b", low):
            return "no such item (4) (/ip/route/set; line 1)\n"  # an id and a position both end here (checked on 7.24 and 7.25)
        if "print" in low or low.startswith(":put"):
            return "Flags: X - DISABLED, I - INVALID\n" if "detail" in low else ""
        return ""  # a write through [find ...] that matches nothing


class RefusingRouter(Router):
    def answer(self, command, low):
        if "count-only" in low:
            return "1"
        if low.startswith(":put [:pick"):
            return "*1"
        if "print" in low or (low.startswith(":put") and "find" in low):
            return "Flags: X - DISABLED\n 0    name=x chain=input interface=ether1 address=10.0.0.1/24 comment=x\n"
        return "invalid value for argument name\n"


def _modules():
    prefix = scope_package.__name__ + "."
    for info in pkgutil.walk_packages(scope_package.__path__, prefix=prefix):
        if not info.ispkg:
            yield importlib.import_module(info.name)


def _write_tools():
    tools = [
        tool for tool in mcp._tool_manager.list_tools()
        if not (tool.annotations is not None and tool.annotations.read_only_hint) and tool.name not in NOT_APPLICABLE
    ]
    return sorted(tools, key=lambda t: t.name)


def _arguments(tool, id_value, with_option=False):
    """Dummy values for the required parameters (an id for the ones that name an item), plus one optional one on request."""
    params = [p for p in inspect.signature(tool.fn).parameters.values() if p.name != "ctx"]
    kwargs = {}
    for param in params:
        if param.default is not inspect._empty:
            continue
        kwargs[param.name] = id_value if ID_PARAM.search(param.name) and param.annotation in (str, "str") else make_dummy_value(param)
    if with_option:
        optional = {p.name: p for p in params if p.default is not inspect._empty and p.name != "device"}
        pick = next((optional[n] for n in PREFERRED_OPTIONS if n in optional), next(iter(optional.values()), None))
        if pick is not None:
            kwargs[pick.name] = True if pick.name == "disabled" else make_dummy_value(
                inspect.Parameter(pick.name, pick.kind, annotation=str if pick.name == "comment" else pick.annotation)
            )
    return kwargs


def _answer(tool, router, monkeypatch, ctx, id_value):
    for module in _modules():
        if hasattr(module, "execute_mikrotik_command"):
            monkeypatch.setattr(module, "execute_mikrotik_command", router, raising=True)
    kwargs = _arguments(tool, id_value)
    text = asyncio.run(tool.fn(ctx, **kwargs))
    if "no updates specified" in str(text).lower():  # an update tool needs a field to update
        kwargs = _arguments(tool, id_value, with_option=True)
        text = asyncio.run(tool.fn(ctx, **kwargs))
    return text, kwargs


def _lies(text):
    """The answer claims success and says nothing that points the other way. The Flags legend RouterOS prints even when nothing
    matches ("I - INVALID") is part of a listing, not of the verdict."""
    verdict = " ".join(line for line in text.splitlines() if not line.startswith("Flags:"))
    return bool(SUCCESS.search(verdict)) and not FAILURE.search(verdict)


def test_the_tools_are_found():
    names = {t.name for t in _write_tools()}
    assert len(names) >= 90
    assert {"update_filter_rule", "remove_user", "create_vlan_interface", "enable_queue_tree"} <= names


@pytest.mark.parametrize("tool", [t for t in _write_tools() if t.name.startswith(TARGETED)], ids=lambda t: t.name)
def test_a_tool_that_changes_an_item_says_when_there_is_none(tool, ctx, monkeypatch):
    for id_value in ("*FFFF", "7"):
        text, kwargs = _answer(tool, EmptyRouter(), monkeypatch, ctx, id_value)
        assert isinstance(text, str)
        assert not _lies(text), f"{tool.name}({kwargs}) on a router with nothing on it answered: {text[:200]!r}"


@pytest.mark.parametrize("tool", _write_tools(), ids=lambda t: t.name)
def test_a_refusal_is_reported_whatever_it_says(tool, ctx, monkeypatch):
    text, kwargs = _answer(tool, RefusingRouter(), monkeypatch, ctx, "*1")
    assert isinstance(text, str)
    assert not _lies(text), f"{tool.name}({kwargs}) answered {text[:200]!r} although RouterOS refused the write"
