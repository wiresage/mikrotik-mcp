"""A tool is registered under its short name, `<action>_<resource>`; the function behind it is `mikrotik_<action>_<resource>`.

CONTRIBUTING.md and AGENTS.md say so. Clients see the short name and the website's API reference lists it, so a module that registered
`name="mikrotik_..."` would show a second naming style to every client, and a function that is not named after its tool breaks the
way the tests and the docs find the one from the other.
"""

import re

import mcp_mikrotik.app  # noqa: F401  (registers every tool)
from mcp_mikrotik.app import mcp

TOOLS = mcp._tool_manager.list_tools()


def test_no_tool_is_registered_under_its_function_name():
    prefixed = sorted(tool.name for tool in TOOLS if tool.name.startswith("mikrotik_"))
    assert not prefixed, f'register these with name="<action>_<resource>", without the mikrotik_ prefix: {prefixed}'


def test_the_function_behind_a_tool_is_named_after_it():
    odd = sorted((tool.name, tool.fn.__name__) for tool in TOOLS if tool.fn.__name__ != f"mikrotik_{tool.name}")
    assert not odd, f"name the function mikrotik_<tool name> (tool name, function name): {odd}"


def test_tool_names_are_lowercase_words_joined_by_underscores():
    odd = sorted(tool.name for tool in TOOLS if not re.fullmatch(r"[a-z][a-z0-9]*(_[a-z0-9]+)*", tool.name))
    assert not odd, f"use lowercase words joined by underscores: {odd}"
