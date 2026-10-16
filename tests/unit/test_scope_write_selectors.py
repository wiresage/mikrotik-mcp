import asyncio
from typing import Any

import pytest


CASES = [
    ("routes", "mikrotik_remove_route", "route_id", "/ip route", "remove"),
    ("dns", "mikrotik_remove_dns_static", "entry_id", "/ip dns static", "remove"),
    ("firewall_nat", "mikrotik_remove_nat_rule", "rule_id", "/ip firewall nat", "remove"),
    ("firewall_nat", "mikrotik_move_nat_rule", "rule_id", "/ip firewall nat", "move"),
    ("wireguard", "mikrotik_remove_wireguard_peer", "peer_id", "/interface wireguard peers", "remove"),
    ("ipv6_firewall_filter", "mikrotik_update_ipv6_filter_rule", "rule_id", "/ipv6 firewall filter", "set"),
    ("ipv6_firewall_filter", "mikrotik_remove_ipv6_filter_rule", "rule_id", "/ipv6 firewall filter", "remove"),
    ("ipv6_firewall_filter", "mikrotik_move_ipv6_filter_rule", "rule_id", "/ipv6 firewall filter", "move"),
]


@pytest.mark.parametrize("module_name,function_name,id_name,menu,action", CASES)
def test_write_selectors(module_name, function_name, id_name, menu, action, ctx, monkeypatch):
    module = __import__(f"mcp_mikrotik.scope.{module_name}", fromlist=["*"])
    commands = []
    present = True
    moved = False

    async def execute(command, _ctx, device=None):
        nonlocal present, moved
        commands.append(command)
        if command == f":put [{menu} find]":
            return "*2;*1;*3;*4"  # the list in print order; the item under test is at position 1
        if command.startswith(":put [:pick"):
            return "*1" if (present and ("find] 0]" in command or moved)) else "*2"
        if "count-only" in command:
            return "1" if present else "0"
        if f" {action} " in command:
            if action == "remove":
                present = False
            if action == "move":
                moved = True
        if "print detail" in command:
            return "chain=forward"
        return ""

    monkeypatch.setattr(module, "execute_mikrotik_command", execute)
    kwargs: dict[str, Any] = {id_name: "0"}
    if action == "move":
        kwargs["destination"] = 2
    if action == "set":
        kwargs["disabled"] = True
    result = asyncio.run(getattr(module, function_name)(ctx, **kwargs))
    assert commands[0] == f":put [:pick [{menu} find] 0]"
    assert any(command.startswith(f"{menu} {action} *1") for command in commands)
    if action == "remove":
        assert commands[-1] == f"{menu} print count-only where .id=*1"
    assert "success" in result or "moved" in result


@pytest.mark.parametrize("module_name,function_name,id_name,menu,action", CASES)
@pytest.mark.parametrize("bad_id", ['[find]', '[find comment="managed"]', '*1;remove [find]', '*nothex'])
def test_invalid_selector_never_writes(module_name, function_name, id_name, menu, action, bad_id, ctx, monkeypatch):
    module = __import__(f"mcp_mikrotik.scope.{module_name}", fromlist=["*"])
    commands = []

    async def execute(command, _ctx, device=None):
        commands.append(command)
        return ""

    monkeypatch.setattr(module, "execute_mikrotik_command", execute)
    kwargs: dict[str, Any] = {id_name: bad_id}
    if action == "move":
        kwargs["destination"] = 2
    if action == "set":
        kwargs["disabled"] = True
    result = asyncio.run(getattr(module, function_name)(ctx, **kwargs))
    assert "not found" in result
    assert not commands


@pytest.mark.parametrize("module_name,function_name,id_name,menu,action", CASES)
def test_missing_position_never_writes(module_name, function_name, id_name, menu, action, ctx, monkeypatch):
    module = __import__(f"mcp_mikrotik.scope.{module_name}", fromlist=["*"])
    commands = []

    async def execute(command, _ctx, device=None):
        commands.append(command)
        return ""

    monkeypatch.setattr(module, "execute_mikrotik_command", execute)
    kwargs: dict[str, Any] = {id_name: "999"}
    if action == "move":
        kwargs["destination"] = 2
    if action == "set":
        kwargs["disabled"] = True
    result = asyncio.run(getattr(module, function_name)(ctx, **kwargs))
    assert "not found" in result
    assert commands == [f":put [:pick [{menu} find] 999]"]


@pytest.mark.parametrize("module_name,function_name,id_name,menu,action", CASES)
@pytest.mark.parametrize("response", ["no such item (4)", "not enough permissions (9)"])
def test_write_refusals(module_name, function_name, id_name, menu, action, response, ctx, monkeypatch):
    module = __import__(f"mcp_mikrotik.scope.{module_name}", fromlist=["*"])

    async def execute(command, _ctx, device=None):
        if command == f":put [{menu} find]":
            return "*0;*1;*2;*3"
        if "count-only" in command:
            return "1"
        if f" {action} " in command:
            return response
        return "chain=forward"

    monkeypatch.setattr(module, "execute_mikrotik_command", execute)
    kwargs: dict[str, Any] = {id_name: "*1"}
    if action == "move":
        kwargs["destination"] = 2
    if action == "set":
        kwargs["disabled"] = True
    result = asyncio.run(getattr(module, function_name)(ctx, **kwargs))
    assert ("not found" if response.startswith("no such item") else "Failed") in result
    assert "success" not in result


@pytest.mark.parametrize("module_name,function_name,id_name,menu,action", [case for case in CASES if case[-1] != "set"])
def test_silent_noop_is_not_success(module_name, function_name, id_name, menu, action, ctx, monkeypatch):
    module = __import__(f"mcp_mikrotik.scope.{module_name}", fromlist=["*"])

    async def execute(command, _ctx, device=None):
        if command == f":put [{menu} find]":
            return "*0;*1;*2;*3"
        if "count-only" in command:
            return "1"
        if command.startswith(":put [:pick"):
            return "*2"
        return ""

    monkeypatch.setattr(module, "execute_mikrotik_command", execute)
    kwargs: dict[str, Any] = {id_name: "*1"}
    if action == "move":
        kwargs["destination"] = 2
    result = asyncio.run(getattr(module, function_name)(ctx, **kwargs))
    assert result.startswith("Failed")
