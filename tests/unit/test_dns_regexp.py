"""add_dns_regexp (issue #141): a regexp entry is nameless, and its value needs RouterOS string escaping.

RouterOS 7 answered the old command with "failure: only name or regexp allowed" (the tool sent
name="dummy" next to the regexp) and, once the name was gone, with "expected regexp value" (the regexp
was put into double quotes unescaped, so `\.` was read as an escape sequence).
"""

import asyncio

import pytest

from mcp_mikrotik.scope import dns as dns_mod
from mcp_mikrotik.scope._quoting import ros_quoted

BS = chr(92)  # one backslash, written this way so the tests do not depend on how a backslash is escaped here


def run(coro):
    return asyncio.run(coro)


def executor(replies):
    seen = []

    async def execute(command, _ctx, device=None):
        seen.append(command)
        for prefix, reply in replies:
            if command.startswith(prefix):
                return reply
        return ""

    execute.seen = seen
    return execute


# ----------------------------------------------------------------------------------------- the quoting helper
@pytest.mark.parametrize(
    "value,expected",
    [
        ("plain", "plain"),
        (f".*{BS}.example{BS}.com", f".*{BS}{BS}.example{BS}{BS}.com"),
        ("^a.b$", f"^a.b{BS}$"),
        ('say "hi"', f'say {BS}"hi{BS}"'),
        (f"{BS}{BS}", f"{BS}{BS}{BS}{BS}"),  # the backslash is doubled first, or it would escape the escapes
        ("[a-z]+", "[a-z]+"),
        ("", ""),
    ],
)
def test_ros_quoted(value, expected):
    assert ros_quoted(value) == expected


# ----------------------------------------------------------------------------------------- add_dns_regexp
def test_add_dns_regexp_sends_no_name_and_an_escaped_regexp(ctx, monkeypatch):
    execute = executor([(":put [/ip dns static add", "*3\r\n"), ("/ip dns static print detail where .id=*3", "regexp=... address=10.80.0.9")])
    monkeypatch.setattr(dns_mod, "execute_mikrotik_command", execute)

    result = run(dns_mod.mikrotik_add_dns_regexp(ctx, f".*{BS}.example{BS}.com$", "10.80.0.9", comment="x"))

    add = execute.seen[0]
    assert "name=" not in add
    assert "dummy" not in add
    assert f'regexp=".*{BS}{BS}.example{BS}{BS}.com{BS}$"' in add
    assert add.startswith(":put [/ip dns static add ") and add.endswith("]")
    assert result.startswith("Static DNS entry added successfully:")


def test_add_dns_static_with_a_regexp_ignores_the_name(ctx, monkeypatch):
    execute = executor([(":put", "*4")])
    monkeypatch.setattr(dns_mod, "execute_mikrotik_command", execute)

    run(dns_mod.mikrotik_add_dns_static(ctx, "ignored-name", address="10.0.0.1", regexp="a.*"))

    assert "ignored-name" not in execute.seen[0]
    assert "name=" not in execute.seen[0]


def test_add_dns_static_without_a_regexp_still_sends_the_name(ctx, monkeypatch):
    execute = executor([(":put", "*5"), ("/ip dns static print", "name=host.lab address=10.0.0.1")])
    monkeypatch.setattr(dns_mod, "execute_mikrotik_command", execute)

    result = run(dns_mod.mikrotik_add_dns_static(ctx, "host.lab", address="10.0.0.1", ttl="1h"))

    assert execute.seen[0] == ':put [/ip dns static add name="host.lab" address=10.0.0.1 ttl=1h]'
    assert "added successfully" in result


@pytest.mark.parametrize(
    "reply,fragment",
    [
        ("failure: only name or regexp allowed (/ip/dns/static/add; line 1)", "only name or regexp allowed"),
        ("expected regexp value (line 1 column 31)", "expected regexp value"),
        ("", "no entry ID returned"),
    ],
)
def test_add_dns_static_does_not_claim_success_without_an_id(reply, fragment, ctx, monkeypatch):
    monkeypatch.setattr(dns_mod, "execute_mikrotik_command", executor([(":put", reply)]))

    result = run(dns_mod.mikrotik_add_dns_regexp(ctx, "a.*", "10.80.0.9"))

    assert result.startswith("Failed to add static DNS entry:")
    assert fragment in result
    assert "successfully" not in result


# ----------------------------------------------------------------------------------------- update_dns_static
def test_update_dns_static_escapes_the_regexp_too(ctx, monkeypatch):
    execute = executor([])
    monkeypatch.setattr(dns_mod, "execute_mikrotik_command", execute)

    run(dns_mod.mikrotik_update_dns_static(ctx, "*7", regexp=f"^x{BS}.y$"))

    set_command = next(c for c in execute.seen if c.startswith("/ip dns static set"))
    assert f'regexp="^x{BS}{BS}.y{BS}$"' in set_command


def test_update_dns_static_can_still_clear_the_regexp(ctx, monkeypatch):
    execute = executor([])
    monkeypatch.setattr(dns_mod, "execute_mikrotik_command", execute)

    run(dns_mod.mikrotik_update_dns_static(ctx, "*7", regexp=""))

    assert any("!regexp" in c for c in execute.seen)
