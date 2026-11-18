"""Unit tests for the NAT rule tools."""

import asyncio

from mcp_mikrotik.scope.firewall import nat as m


def _run(coro):
    return asyncio.run(coro)


class Script:
    """Answers each command with the first reply whose key it contains; anything else gets ""."""

    def __init__(self, replies):
        self.replies = replies
        self.commands = []

    async def __call__(self, command, _ctx, device=None, **kwargs):
        self.commands.append(command)
        for key, reply in self.replies.items():
            if key in command:
                return reply
        return ""


def _patch(monkeypatch, replies):
    fake = Script(replies)
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)
    return fake


def test_create_reads_the_new_rule_back_by_its_id(ctx, monkeypatch):
    """A plain add prints nothing and the old fallback read `print from=<last>`, which names an item number that only exists
    after a print in the same session: the answer said "created successfully" and then "no such item"."""
    fake = _patch(monkeypatch, {":put [": "*7\n", "print detail where": "0 chain=srcnat action=masquerade out-interface=ether1\n"})

    out = _run(m.mikrotik_create_nat_rule(ctx, chain="srcnat", action="masquerade", out_interface="ether1"))

    assert fake.commands[0] == ':put [/ip firewall nat add chain=srcnat action=masquerade out-interface="ether1"]'
    assert fake.commands[1] == "/ip firewall nat print detail where .id=*7"
    assert out.startswith("NAT rule created successfully (ID *7):")
    assert "action=masquerade" in out
    assert "no such item" not in out
    assert not any("from=" in c for c in fake.commands)


def test_create_without_details_still_gives_the_id(ctx, monkeypatch):
    _patch(monkeypatch, {":put [": "*8"})
    out = _run(m.mikrotik_create_nat_rule(ctx, chain="srcnat", action="masquerade"))
    assert out == "NAT rule created successfully with ID: *8"


def test_create_reports_what_routeros_refused(ctx, monkeypatch):
    fake = _patch(monkeypatch, {":put [": "input does not match any value of out-interface\n"})
    out = _run(m.mikrotik_create_nat_rule(ctx, chain="srcnat", action="masquerade", out_interface="nope"))
    assert out == "Failed to create NAT rule: input does not match any value of out-interface"
    assert len(fake.commands) == 1


def test_create_without_an_id_is_not_success(ctx, monkeypatch):
    _patch(monkeypatch, {})
    out = _run(m.mikrotik_create_nat_rule(ctx, chain="srcnat", action="masquerade"))
    assert out == "Failed to create NAT rule: no rule ID returned"


def test_create_rejects_an_action_the_chain_does_not_have(ctx, monkeypatch):
    fake = _patch(monkeypatch, {})
    out = _run(m.mikrotik_create_nat_rule(ctx, chain="srcnat", action="dst-nat"))
    assert out.startswith("Error: Invalid action 'dst-nat' for srcnat")
    assert fake.commands == []
