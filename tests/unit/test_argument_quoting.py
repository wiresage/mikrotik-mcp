"""A tool argument must stay a value and never become a command.

RouterOS ends a double-quoted string at the first unescaped `"`, and `;`
separates commands, so a free-text argument that reaches the device unescaped
can append a command of its own. `--read-only` does not stop it: that flag
decides which tools are registered and never inspects their arguments.

This test discovers the surface instead of listing it. It walks every scope
module, every `mikrotik_*` tool and every string parameter, drives that one
parameter with a payload carrying an unescaped quote, and asserts the payload
never reaches the command verbatim. A parameter that is validated, rejected or
never interpolated passes on its own; the failure means the payload crossed
into the command as written.
"""

import asyncio
import inspect
import pkgutil
import typing
from typing import get_args, get_origin

import pytest

import mcp_mikrotik.scope as scope_pkg
from tests.conftest import FakeExecutor, make_dummy_value

# An unescaped `"` closes the value, `;` starts a command. The marker makes a
# failure unmistakable in the assertion message.
BREAKOUT = 'zz" ; :log info QUOTE-BREAKOUT ; "zz'

SCOPE_MODULES = sorted(
    m.name for m in pkgutil.iter_modules(scope_pkg.__path__)
    if not m.name.startswith("_")
)


def _is_free_text(param: inspect.Parameter) -> bool:
    """True for a parameter whose value is arbitrary text.

    `Literal` parameters are a fixed set and cannot carry a payload, and a
    non-string annotation is not free text either. An unannotated parameter is
    treated as text, which is the cautious reading.
    """
    ann = param.annotation
    if ann is inspect._empty:
        return True
    if get_origin(ann) is typing.Union:
        args = [a for a in get_args(ann) if a is not type(None)]
        if not args:
            return False
        ann = args[0]
    if get_origin(ann) is typing.Literal:
        return False
    return ann is str


def _tools(module):
    for name, fn in inspect.getmembers(module, inspect.iscoroutinefunction):
        if name.startswith("mikrotik_"):
            yield name, fn


@pytest.mark.parametrize("module_name", SCOPE_MODULES)
def test_free_text_arguments_cannot_leave_their_quotes(module_name, ctx, monkeypatch):
    module = __import__(f"mcp_mikrotik.scope.{module_name}", fromlist=["*"])
    if not hasattr(module, "execute_mikrotik_command"):
        pytest.skip(f"{module_name} builds no commands, so it has nothing to quote")
    fake = FakeExecutor()
    monkeypatch.setattr(module, "execute_mikrotik_command", fake, raising=True)

    violations = []
    for tool_name, fn in _tools(module):
        params = inspect.signature(fn).parameters
        targets = [
            p for p in params.values()
            if p.name not in {"ctx", "device"} and _is_free_text(p)
        ]
        for target in targets:
            kwargs = {}
            for param in params.values():
                if param.name == "ctx":
                    kwargs["ctx"] = ctx
                elif param.name == target.name:
                    kwargs[param.name] = BREAKOUT
                elif param.default is inspect._empty:
                    kwargs[param.name] = make_dummy_value(param)

            fake.commands.clear()
            try:
                asyncio.run(fn(**kwargs))
            except Exception:
                # A tool that refuses the value never builds a command; that is
                # a valid defence and leaves nothing to assert.
                continue

            for command in fake.commands:
                if BREAKOUT in command:
                    violations.append(f"  {tool_name}({target.name}=...) -> {command}")
                    break

    # Every violation is collected before failing. A test that stops at the
    # first one hides the rest of the work and has to be re-run to find it.
    assert not violations, (
        f"{len(violations)} argument(s) in {module_name} reach the command with the "
        f"quote intact:\n" + "\n".join(violations)
    )
