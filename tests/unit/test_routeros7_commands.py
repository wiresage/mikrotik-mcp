"""Tools that sent RouterOS 6 syntax: add_blackhole_route, the route cache tools and the DNS cache statistics.

Each of these failed on RouterOS 7.21.4 with a syntax error ("expected end of command" /
"bad command name cache"). The router replies in the strings used below.
"""

import asyncio

import pytest

from mcp_mikrotik.scope import dns as dns_mod
from mcp_mikrotik.scope import routes as routes_mod


def run(coro):
    return asyncio.run(coro)


def executor(replies):
    """An executor that answers by the first matching prefix and records every command."""
    seen = []

    async def execute(command, _ctx, device=None):
        seen.append(command)
        for prefix, reply in replies:
            if command.startswith(prefix):
                return reply
        return ""

    execute.seen = seen
    return execute


# ----------------------------------------------------------------------------------------- add_blackhole_route
def test_blackhole_route_uses_the_routeros7_flag_and_reports_the_new_id(ctx, monkeypatch):
    execute = executor([(":put [/ip route add", "*80000006\r\n")])
    monkeypatch.setattr(routes_mod, "execute_mikrotik_command", execute)

    result = run(routes_mod.mikrotik_add_blackhole_route(ctx, "10.86.0.0/24", distance=5, comment="bh"))

    assert execute.seen == ['/ip route add dst-address=10.86.0.0/24 blackhole distance=5 comment="bh"'.join([":put [", "]"])]
    assert "type=blackhole" not in execute.seen[0]
    assert result == "Blackhole route added successfully. ID: *80000006"


@pytest.mark.parametrize(
    "reply,fragment",
    [
        ("expected end of command (line 1 column 40)", "expected end of command"),
        ("failure: already have such route", "already have such route"),
        ("", "no route ID returned"),
    ],
)
def test_blackhole_route_does_not_claim_success_without_an_id(reply, fragment, ctx, monkeypatch):
    monkeypatch.setattr(routes_mod, "execute_mikrotik_command", executor([(":put", reply)]))

    result = run(routes_mod.mikrotik_add_blackhole_route(ctx, "10.86.0.0/24"))

    assert result.startswith("Failed to add blackhole route:")
    assert fragment in result
    assert "successfully" not in result


# ----------------------------------------------------------------------------------------- route cache
ROUTEROS7_NO_CACHE = "bad command name cache (line 1 column 11)"


@pytest.mark.parametrize("tool", ["mikrotik_get_route_cache", "mikrotik_flush_route_cache"])
def test_route_cache_tools_explain_that_routeros7_has_none(tool, ctx, monkeypatch):
    monkeypatch.setattr(routes_mod, "execute_mikrotik_command", executor([("/ip route cache", ROUTEROS7_NO_CACHE)]))

    result = run(getattr(routes_mod, tool)(ctx))

    assert "no route cache" in result
    assert "RouterOS 7" in result
    assert "bad command name" not in result


def test_route_cache_still_works_where_it_exists(ctx, monkeypatch):
    monkeypatch.setattr(routes_mod, "execute_mikrotik_command", executor([("/ip route cache print", "0 dst=10.0.0.1\r\n")]))
    assert run(routes_mod.mikrotik_get_route_cache(ctx)).startswith("ROUTE CACHE:")

    monkeypatch.setattr(routes_mod, "execute_mikrotik_command", executor([]))
    assert run(routes_mod.mikrotik_get_route_cache(ctx)) == "Route cache is empty."
    assert run(routes_mod.mikrotik_flush_route_cache(ctx)) == "Route cache flushed successfully."


# ----------------------------------------------------------------------------------------- DNS cache statistics
DNS_PRINT = (
    "                      servers: 1.1.1.1\r\n"
    "              dynamic-servers: 10.0.2.3\r\n"
    "                   cache-size: 2048KiB \r\n"
    "                cache-max-ttl: 1w      \r\n"
    "                   cache-used: 37KiB   \r\n"
    "           allow-remote-requests: no\r\n"
)


def test_dns_cache_statistics_come_from_dns_settings_and_the_cache_count(ctx, monkeypatch):
    execute = executor([("/ip dns print", DNS_PRINT), ("/ip dns cache print count-only", "12\r\n")])
    monkeypatch.setattr(dns_mod, "execute_mikrotik_command", execute)

    result = run(dns_mod.mikrotik_get_dns_cache_statistics(ctx))

    assert execute.seen == ["/ip dns print", "/ip dns cache print count-only"]
    assert "stats" not in " ".join(execute.seen)
    assert result == (
        "DNS CACHE STATISTICS:\n\ncached-records: 12\ncache-size: 2048KiB\ncache-max-ttl: 1w\ncache-used: 37KiB"
    )
    assert "dynamic-servers" not in result


@pytest.mark.parametrize("settings", ["", "Error: Failed to connect to MikroTik device 'x'"])
def test_dns_cache_statistics_report_when_the_device_cannot_be_read(settings, ctx, monkeypatch):
    monkeypatch.setattr(dns_mod, "execute_mikrotik_command", executor([("/ip dns print", settings), ("/ip dns cache", "0")]))

    assert run(dns_mod.mikrotik_get_dns_cache_statistics(ctx)) == "Unable to retrieve DNS cache statistics."


def test_dns_cache_statistics_keep_the_record_count_when_the_settings_are_unreadable(ctx, monkeypatch):
    monkeypatch.setattr(dns_mod, "execute_mikrotik_command", executor([("/ip dns print", "nothing useful here"), ("/ip dns cache", "3")]))

    assert run(dns_mod.mikrotik_get_dns_cache_statistics(ctx)) == "DNS CACHE STATISTICS:\n\ncached-records: 3"
