"""Unit tests for set_dns_servers."""

import asyncio

from mcp_mikrotik.scope.dns import dns as m


def _run(coro):
    return asyncio.run(coro)


class Script:
    def __init__(self, replies):
        self.replies = replies
        self.commands = []

    async def __call__(self, command, _ctx, device=None, **kwargs):
        self.commands.append(command)
        for key, reply in self.replies.items():
            if key in command:
                return reply
        return ""


def _patch(monkeypatch, replies=None):
    fake = Script(replies or {"/ip dns print": "servers: 1.1.1.1\n"})
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)
    return fake


def test_servers_are_set_and_nothing_else_is_touched(ctx, monkeypatch):
    """allow-remote-requests used to be written as "no" on every call, which stopped a router from answering the DNS
    queries of its own clients whenever someone only wanted to change the upstream servers."""
    fake = _patch(monkeypatch)
    out = _run(m.mikrotik_set_dns_servers(ctx, servers=["1.1.1.1", "9.9.9.9"]))
    assert fake.commands[0] == "/ip dns set servers=1.1.1.1,9.9.9.9"
    assert out.startswith("DNS settings updated successfully:")


def test_allow_remote_requests_is_written_when_it_is_given(ctx, monkeypatch):
    fake = _patch(monkeypatch)
    _run(m.mikrotik_set_dns_servers(ctx, servers=["1.1.1.1"], allow_remote_requests=True))
    _run(m.mikrotik_set_dns_servers(ctx, servers=["1.1.1.1"], allow_remote_requests=False))
    assert fake.commands[0] == "/ip dns set servers=1.1.1.1 allow-remote-requests=yes"
    assert [c for c in fake.commands if c.startswith("/ip dns set")][1] == "/ip dns set servers=1.1.1.1 allow-remote-requests=no"


def test_an_empty_list_clears_the_servers(ctx, monkeypatch):
    """`servers=` followed by a space is not an empty value for RouterOS: the servers stayed as they were."""
    fake = _patch(monkeypatch)
    _run(m.mikrotik_set_dns_servers(ctx, servers=[]))
    assert fake.commands[0] == '/ip dns set servers=""'


def test_a_refusal_without_the_word_failure_is_reported(ctx, monkeypatch):
    fake = _patch(monkeypatch, {"/ip dns set": "invalid value for argument servers\n"})
    out = _run(m.mikrotik_set_dns_servers(ctx, servers=["not-an-address"]))
    assert out == "Failed to update DNS settings: invalid value for argument servers"
    assert fake.commands == ["/ip dns set servers=not-an-address"]
