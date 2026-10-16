"""move_filter_rule, move_nat_rule and move_ipv6_filter_rule must put a rule at the requested position.

They sent ``move <id> destination=<position>``. RouterOS reads a bare number there as the N-th item in
CREATION order, not as a position in the current list, so on a real router (7.21.4):

    [a, b, c]  move c destination=0  ->  [c, a, b]                          (looked right)
    [c, a, b]  move a destination=0  ->  failure: can not move object before itself
    [c, a, b]  move b destination=0  ->  [c, b, a]                          (position 1, not 0)

The fake router below behaves like the real one and refuses what the real one mishandles: a bare number
or a nonexistent id as the destination (the router silently moves the rule to the end for the latter).
"""

import asyncio

import pytest

from mcp_mikrotik.scope import firewall_filter, firewall_nat, ipv6_firewall_filter

TOOLS = [
    (firewall_filter, "mikrotik_move_filter_rule", "/ip firewall filter"),
    (firewall_nat, "mikrotik_move_nat_rule", "/ip firewall nat"),
    (ipv6_firewall_filter, "mikrotik_move_ipv6_filter_rule", "/ipv6 firewall filter"),
]
IDS = ["*A", "*B", "*C", "*D", "*E"]


class FakeRouter:
    def __init__(self, menu, order):
        self.menu = menu
        self.order = list(order)
        self.moves = []

    async def __call__(self, command, _ctx, device=None):
        menu = self.menu
        if command == f":put [{menu} find]":
            return ";".join(self.order) + "\r\n"
        if command.startswith(f":put [:pick [{menu} find] "):
            position = int(command.rsplit(" ", 1)[1].rstrip("]"))
            return (self.order[position] if 0 <= position < len(self.order) else "") + "\r\n"
        if command.startswith(f"{menu} print count-only where .id="):
            return ("1" if command.rsplit("=", 1)[1] in self.order else "0") + "\r\n"
        if command.startswith(f"{menu} move "):
            self.moves.append(command)
            arguments = command[len(f"{menu} move ") :].split()
            item = arguments[0]
            destination = arguments[1].split("=", 1)[1] if len(arguments) > 1 else None
            if destination is not None:
                assert destination in self.order, f"the destination must be an existing internal id, got {destination!r}"
                if destination == item:
                    return "failure: can not move object before itself (/move; line 1)"
            self.order.remove(item)
            self.order.insert(self.order.index(destination) if destination else len(self.order), item)
            return ""
        return ""


def move(module, function, menu, order, rule, destination, ctx, monkeypatch):
    router = FakeRouter(menu, order)
    monkeypatch.setattr(module, "execute_mikrotik_command", router)
    result = asyncio.run(getattr(module, function)(ctx, rule_id=rule, destination=destination))
    return router, result


@pytest.mark.parametrize("module,function,menu", TOOLS, ids=[t[1] for t in TOOLS])
@pytest.mark.parametrize("current", range(5))
@pytest.mark.parametrize("destination", range(5))
def test_the_rule_ends_up_at_the_requested_position(module, function, menu, current, destination, ctx, monkeypatch):
    rule = IDS[current]
    router, result = move(module, function, menu, IDS, rule, destination, ctx, monkeypatch)

    assert router.order[destination] == rule, (router.order, result)
    assert sorted(router.order) == IDS  # nothing lost or duplicated
    assert f"moved to position {destination}" in result
    if current == destination:
        assert router.moves == []  # already there: nothing to send


@pytest.mark.parametrize("module,function,menu", TOOLS, ids=[t[1] for t in TOOLS])
def test_moving_to_the_top_works_repeatedly_the_case_that_used_to_fail(module, function, menu, ctx, monkeypatch):
    router = FakeRouter(menu, IDS)
    monkeypatch.setattr(module, "execute_mikrotik_command", router)
    for rule in ["*C", "*A", "*E", "*B", "*D"]:
        result = asyncio.run(getattr(module, function)(ctx, rule_id=rule, destination=0))
        assert router.order[0] == rule
        assert "moved to position 0" in result
        assert "Failed" not in result


@pytest.mark.parametrize("module,function,menu", TOOLS, ids=[t[1] for t in TOOLS])
@pytest.mark.parametrize("destination", [-1, 5, 99])
def test_an_out_of_range_position_is_refused_without_moving_anything(module, function, menu, destination, ctx, monkeypatch):
    router, result = move(module, function, menu, IDS, "*C", destination, ctx, monkeypatch)

    assert result.startswith("Failed to move")
    assert "out of range" in result
    assert router.moves == []
    assert router.order == IDS


@pytest.mark.parametrize("module,function,menu", TOOLS, ids=[t[1] for t in TOOLS])
def test_an_unknown_rule_is_not_found(module, function, menu, ctx, monkeypatch):
    router, result = move(module, function, menu, IDS, "*FFFF", 0, ctx, monkeypatch)

    assert "not found" in result
    assert router.moves == []
