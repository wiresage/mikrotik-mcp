import asyncio
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from unittest.mock import MagicMock

import pytest

from mcp.server.mcpserver import Context


FILE_CREATING_COMMAND = re.compile(r"(?:export|print)\s+file=|backup\s+save")


def test_health_check_returns_ok():
    from mcp_mikrotik.app import health_check

    resp = asyncio.run(health_check(MagicMock()))
    assert resp.body == b"OK"
    assert resp.media_type == "text/plain"


def test_device_guidance_lives_in_server_instructions_not_every_tool():
    """The `device` argument is explained once, at initialize.

    Repeating it in each tool description put the same sentence in front of
    the model ~192 times, for no extra information.
    """
    from mcp_mikrotik.app import mcp

    instructions = mcp.instructions or ""
    assert "device" in instructions
    assert "list_devices" in instructions

    tools = asyncio.run(mcp.list_tools())
    repeated = [
        t.name for t in tools
        if "title of the target device" in (t.description or "")
        or "Device title from the inventory" in (t.description or "")
    ]
    assert repeated == [], f"device guidance duplicated into tool descriptions: {repeated}"


def test_every_tool_still_accepts_a_device_argument():
    """Dropping the prose must not drop the parameter."""
    from mcp_mikrotik.app import mcp

    tools = asyncio.run(mcp.list_tools())
    missing = [
        t.name for t in tools
        if t.name != "list_devices"
        and "device" not in (t.input_schema.get("properties") or {})
    ]
    assert missing == []


def test_read_only_server_registers_only_read_tools(monkeypatch):
    from mcp_mikrotik import config
    from mcp_mikrotik.app import READ, WRITE, annotate
    from mcp_mikrotik.config import MikrotikConfig
    from mcp_mikrotik.configured_mcp_server import ConfiguredMCPServer

    monkeypatch.setattr(config, "mikrotik_config", MikrotikConfig(read_only=True))
    server = ConfiguredMCPServer("read-only-test")

    @server.tool(name="read", annotations=annotate(READ, "Read"))
    async def read_tool() -> str:
        return "read"

    @server.tool(name="write", annotations=annotate(WRITE, "Write"))
    async def write_tool() -> str:
        return "write"

    tools = asyncio.run(server.list_tools())
    assert [tool.name for tool in tools] == ["read"]
    assert tools[0].annotations.title == "Read"
    assert tools[0].annotations.read_only_hint is True


def test_sensitive_hiding_server_omits_unsafe_tools_and_redacts_output(monkeypatch, ctx):
    from mcp_mikrotik import config
    from mcp_mikrotik.app import READ, annotate
    from mcp_mikrotik.config import MikrotikConfig
    from mcp_mikrotik.configured_mcp_server import ConfiguredMCPServer

    monkeypatch.setattr(config, "mikrotik_config", MikrotikConfig(sensitive_hiding=True))
    server = ConfiguredMCPServer("sensitive-test")

    @server.tool(name="safe", annotations=annotate(READ, "Safe"))
    async def safe_tool(ctx: Context, password: str) -> str:
        await ctx.info(f"Using {password}")
        return f'password="{password}" public-key=visible'

    @server.tool(name="download_file", annotations=annotate(READ, "Download"))
    async def download_tool() -> str:
        return "opaque"

    @server.tool(name="generate_wireguard_client_config", annotations=annotate(READ, "WireGuard"))
    async def wireguard_tool() -> str:
        return "private"

    tools = asyncio.run(server.list_tools())
    assert [tool.name for tool in tools] == ["safe"]
    assert set(tools[0].input_schema["properties"]) == {"password"}
    assert asyncio.run(safe_tool(ctx, "hunter2")) == 'password="***" public-key=visible'
    assert ctx.info.await_args.args == ("Using ***",)


def test_sensitive_hiding_server_redacts_exceptions(monkeypatch):
    from mcp_mikrotik import config
    from mcp_mikrotik.app import READ, annotate
    from mcp_mikrotik.config import MikrotikConfig
    from mcp_mikrotik.configured_mcp_server import ConfiguredMCPServer

    monkeypatch.setattr(config, "mikrotik_config", MikrotikConfig(sensitive_hiding=True))
    server = ConfiguredMCPServer("sensitive-error-test")

    @server.tool(name="failure", annotations=annotate(READ, "Failure"))
    async def failure_tool(private_key: str) -> str:
        raise ValueError(f"Rejected {private_key}")

    with pytest.raises(RuntimeError, match=r"Rejected \*\*\*"):
        asyncio.run(failure_tool("private-material"))


def test_sensitive_hiding_redacts_sdk_validation_errors(monkeypatch):
    from mcp_mikrotik import config
    from mcp_mikrotik.app import READ, annotate
    from mcp_mikrotik.config import MikrotikConfig
    from mcp_mikrotik.configured_mcp_server import ConfiguredMCPServer

    monkeypatch.setattr(config, "mikrotik_config", MikrotikConfig(sensitive_hiding=True))
    server = ConfiguredMCPServer("sensitive-validation-test")

    @server.tool(name="typed", annotations=annotate(READ, "Typed"))
    async def typed_tool(password: str) -> str:
        return password

    with pytest.raises(Exception) as exc_info:
        asyncio.run(server.call_tool("typed", {"password": ["TOPSECRET"]}))

    assert "TOPSECRET" not in str(exc_info.value)
    assert "***" in str(exc_info.value)


def _file_creating_tool_names():
    scope_dir = Path(__file__).parents[2] / "src/mcp_mikrotik/scope"
    names = set()

    for path in scope_dir.rglob("*.py"):
        source = path.read_text()
        for function in ast.walk(ast.parse(source)):
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not FILE_CREATING_COMMAND.search(ast.get_source_segment(source, function) or ""):
                continue
            for decorator in function.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                    continue
                if decorator.func.attr != "tool":
                    continue
                name = next(
                    (keyword.value.value for keyword in decorator.keywords
                     if keyword.arg == "name" and isinstance(keyword.value, ast.Constant)),
                    None,
                )
                if name:
                    names.add(name)
    return names


def test_file_creating_tools_are_not_marked_read_only():
    from mcp_mikrotik.app import mcp

    tools = {tool.name: tool for tool in asyncio.run(mcp.list_tools())}
    names = _file_creating_tool_names()
    assert names
    for name in names:
        assert tools[name].annotations.read_only_hint is not True


def _read_only_catalogue(*args, env=None):
    script = """
import asyncio
import json
import sys

if sys.argv[1:]:
    from mcp_mikrotik import config
    from mcp_mikrotik.config import MikrotikConfig
    config.mikrotik_config = MikrotikConfig(_cli_parse_args=True)

from mcp_mikrotik.app import mcp

tools = asyncio.run(mcp.list_tools())
print(json.dumps({tool.name: tool.annotations.read_only_hint for tool in tools}))
"""
    command = [sys.executable, "-c", script, *args]
    repo_root = Path(__file__).parents[2]
    env = {
        key: value for key, value in (env or os.environ).items()
        if not key.startswith("MIKROTIK_")
    } | {
        "PYTHONPATH": os.pathsep.join(
            filter(None, (str(repo_root / "src"), os.environ.get("PYTHONPATH")))
        ),
    }
    if not args:
        env["MIKROTIK_READ_ONLY"] = "true"
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        cwd=repo_root,
        env=env,
        text=True,
    )
    return json.loads(result.stdout)


def _assert_read_only_catalogue(tools):
    assert tools
    assert all(read_only is True for read_only in tools.values())
    for name in _file_creating_tool_names():
        assert name not in tools


def test_read_only_env_registers_only_read_tools():
    env = os.environ | {"MIKROTIK_READ_ONLY": "true"}
    _assert_read_only_catalogue(_read_only_catalogue(env=env))


def test_read_only_cli_registers_only_read_tools():
    _assert_read_only_catalogue(_read_only_catalogue("--read-only", env=os.environ.copy()))


def _sensitive_catalogue(*args, env=None):
    script = """
import asyncio
import json
import sys

if sys.argv[1:]:
    from mcp_mikrotik import config
    from mcp_mikrotik.config import MikrotikConfig
    config.mikrotik_config = MikrotikConfig(_cli_parse_args=True)

from mcp_mikrotik.app import mcp
print(json.dumps([tool.name for tool in asyncio.run(mcp.list_tools())]))
"""
    command = [sys.executable, "-c", script, *args]
    repo_root = Path(__file__).parents[2]
    env = {
        key: value for key, value in (env or os.environ).items()
        if not key.startswith("MIKROTIK_")
    } | {
        "PYTHONPATH": os.pathsep.join(
            filter(None, (str(repo_root / "src"), os.environ.get("PYTHONPATH")))
        ),
    }
    if not args:
        env["MIKROTIK_SENSITIVE_HIDING"] = "true"
    result = subprocess.run(command, check=True, capture_output=True, cwd=repo_root, env=env, text=True)
    return json.loads(result.stdout)


@pytest.mark.parametrize("args", [(), ("--sensitive-hiding",)])
def test_sensitive_hiding_env_and_cli_omit_unsafe_tools(args):
    tools = _sensitive_catalogue(*args, env=os.environ.copy())
    assert tools
    assert "download_file" not in tools
    assert "generate_wireguard_client_config" not in tools
    assert "list_devices" in tools
