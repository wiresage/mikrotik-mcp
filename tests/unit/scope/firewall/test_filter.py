"""Unit tests for the IPv4 firewall filter rule tools (update, enable, disable on a rule that is not there)."""

import asyncio

from mcp_mikrotik.scope.firewall import filter as m


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


def test_update_of_an_id_that_does_not_exist_is_not_found(ctx, monkeypatch):
    """An internal id is used as it is, so RouterOS has to be asked: it answers "no such item", which is neither
    "failure:" nor "error", and the tool used to report "updated successfully" with an empty detail."""
    fake = _patch(monkeypatch, {"filter set": "no such item (4)\n"})
    out = _run(m.mikrotik_update_filter_rule(ctx, rule_id="*FFFF", comment="x"))
    assert out == "Firewall filter rule with ID '*FFFF' not found."
    assert not any("print detail" in c for c in fake.commands)


def test_disable_and_enable_of_a_missing_id_are_not_found(ctx, monkeypatch):
    _patch(monkeypatch, {"filter set": "no such item (4)\n"})
    assert "not found" in _run(m.mikrotik_disable_filter_rule(ctx, rule_id="*FFFF"))
    assert "not found" in _run(m.mikrotik_enable_filter_rule(ctx, rule_id="*FFFF"))


def test_update_reports_a_refusal_that_says_neither_failure_nor_error(ctx, monkeypatch):
    _patch(monkeypatch, {"filter set": "input does not match any value of in-interface\n"})
    out = _run(m.mikrotik_update_filter_rule(ctx, rule_id="*1", in_interface="nope"))
    assert out == "Failed to update firewall filter rule: input does not match any value of in-interface"


def test_update_succeeds_when_the_set_is_silent_and_the_rule_reads_back(ctx, monkeypatch):
    fake = _patch(monkeypatch, {"print detail": "0 chain=input action=accept comment=x\n"})
    out = _run(m.mikrotik_update_filter_rule(ctx, rule_id="*1", comment="x"))
    assert out.startswith("Firewall filter rule updated successfully:")
    assert "chain=input" in out
    assert fake.commands[0] == '/ip firewall filter set *1 comment="x"'


def test_update_is_not_success_when_the_rule_cannot_be_read_back(ctx, monkeypatch):
    _patch(monkeypatch, {"print detail": ""})
    out = _run(m.mikrotik_update_filter_rule(ctx, rule_id="*1", comment="x"))
    assert out.startswith("Failed to update firewall filter rule")
