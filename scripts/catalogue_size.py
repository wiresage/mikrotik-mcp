#!/usr/bin/env python3
"""Measure the tools/list answer a client receives, as quoted in docs/getting-started/context-optimization.md.

Starts the server over stdio twice (all tools, then ``--read-only``), asks for ``tools/list`` and prints the
size of the answer as it arrives (one JSON-RPC line), a token estimate at four characters per token, and the
description lengths the page quotes. No device is contacted: the inventory names a documentation address.

    uv run python scripts/catalogue_size.py

The numbers depend a little on the MCP SDK that serializes the answer (descriptions, for example, keep the
indentation of their docstrings in some versions), so measure with the locked dependencies.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

EXAMPLES = (
    "generate_wireguard_client_config",
    "create_queue_type",
    "create_filter_rule",
    "get_ipsec_installed_sa",
    "list_netwatch",
)


def tools_list(*flags: str) -> tuple[int, list[dict]]:
    """Bytes of the ``tools/list`` answer and the tools in it, for a server started with ``flags``."""
    env = {key: value for key, value in os.environ.items() if not key.startswith("MIKROTIK_")}
    env["MIKROTIK_INVENTORY"] = json.dumps([{"title": "Size", "host": "192.0.2.1", "username": "admin"}])
    server = subprocess.Popen(
        [sys.executable, "-m", "mcp_mikrotik.server", *flags],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env,
    )

    def send(message: dict) -> None:
        server.stdin.write((json.dumps(message) + "\n").encode())
        server.stdin.flush()

    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "catalogue_size", "version": "1"}}})
        server.stdout.readline()
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        answer = server.stdout.readline().rstrip(b"\r\n")
    finally:
        server.kill()
        server.wait()
    return len(answer), json.loads(answer)["result"]["tools"]


def main() -> int:
    size, tools = tools_list()
    read_only_size, read_only_tools = tools_list("--read-only")
    for label, n, count in (("all tools", size, len(tools)), ("--read-only", read_only_size, len(read_only_tools))):
        print(f"{label:12} {count:4} tools  {n / 1000:6.1f} KB  ~{n / 4:7,.0f} tokens")
    average = sum(len(tool.get("description") or "") for tool in tools) / len(tools)
    print(f"average description: {average:.0f} characters")
    by_name = {tool["name"]: tool for tool in tools}
    for name in EXAMPLES:
        print(f"  {name}: {len(by_name[name].get('description') or '')} characters")
    return 0


if __name__ == "__main__":
    sys.exit(main())
