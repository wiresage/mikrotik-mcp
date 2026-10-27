"""Unit tests for the /ip firewall raw and /ipv6 firewall raw scopes."""

import asyncio

import pytest

from tests.conftest import FakeExecutor


def _run(coro):
    return asyncio.run(coro)


class ScriptedExecutor(FakeExecutor):
    """FakeExecutor that answers commands containing a key with a scripted reply."""

    def __init__(self, replies):
        super().__init__()
        self.replies = replies

    async def __call__(self, command, _ctx, device=None):
        self.commands.append(command)
        self.devices.append(device)
        for key, reply in self.replies.items():
            if key in command:
                return reply
        return ""


DETAIL = "Flags: X - disabled\n 0    chain=prerouting action=drop src-address=192.0.2.0/24\n"


@pytest.fixture(params=["v4", "v6"])
def scope(request):
    if request.param == "v4":
        from mcp_mikrotik.scope import firewall_raw as m
        return m, "/ip firewall raw", "raw_rule"
    from mcp_mikrotik.scope import ipv6_firewall_raw as m
    return m, "/ipv6 firewall raw", "ipv6_raw_rule"


def fn(m, verb, suffix):
    return getattr(m, f"mikrotik_{verb}_{suffix}")


# --- create -----------------------------------------------------------------

def test_create_minimal_echoes_id(ctx, monkeypatch, scope):
    m, menu, sfx = scope
    fake = ScriptedExecutor({":put [": "*1A", "print detail": DETAIL})
    monkeypatch.setattr(m, "execute_mikrotik_command", fake)

    out = _run(fn(m, "create", sfx)(ctx, chain="prerouting", action="drop", src_address="192.0.2.0/24"))
    assert fake.commands[0] == f":put [{menu} add chain=prerouting action=drop src-address=192.0.2.0/24]"
    assert fake.commands[1] == f"{menu} print detail where .id=*1A"
    assert "created successfully (ID *1A)" in out
    assert "WARNING" not in out


def test_create_refusal_is_reported(ctx, monkeypatch, scope):
    m, _, sfx = scope
    fake = ScriptedExecutor({":put [": "not enough permissions (9)"})
    monkeypatch.setattr(m, "execute_mikrotik_command", fake)

    out = _run(fn(m, "create", sfx)(ctx, chain="prerouting", action="notrack", protocol="udp"))
    assert out.startswith("Failed to create")
    assert "not enough permissions" in out
    assert len(fake.commands) == 1


def test_create_quotes_names_and_resolves_place_before(ctx, monkeypatch, scope):
    m, menu, sfx = scope
    fake = ScriptedExecutor({":pick [": "*5", ":put [": "*1B", "print detail": DETAIL})
    monkeypatch.setattr(m, "execute_mikrotik_command", fake)

    _run(fn(m, "create", sfx)(
        ctx, chain="prerouting", action="add-src-to-address-list", address_list='bad "guys"',
        address_list_timeout="1d", in_interface_list="WAN", dst_port="22,23", protocol="tcp",
        tcp_flags="syn,!ack", comment="ssh $scan", log=True, log_prefix="RAW", place_before="0",
    ))
    assert fake.commands[0] == f":put [:pick [{menu} find] 0]"
    cmd = fake.commands[1]
    assert 'address-list="bad \\"guys\\""' in cmd
    assert "address-list-timeout=1d" in cmd
    assert 'in-interface-list="WAN"' in cmd
    assert "dst-port=22,23" in cmd and "protocol=tcp" in cmd and "tcp-flags=syn,!ack" in cmd
    assert 'comment="ssh \\$scan"' in cmd
    assert 'log=yes log-prefix="RAW"' in cmd
    assert cmd.endswith("place-before=*5]")


def test_create_rejects_injection_in_bare_value(ctx, monkeypatch, scope):
    m, _, sfx = scope
    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake)

    out = _run(fn(m, "create", sfx)(ctx, chain="prerouting", action="drop",
                                    src_address="1.2.3.4; /system reset-configuration"))
    assert out.startswith("Failed to create")
    assert fake.commands == []


def test_create_rejects_bad_chain(ctx, monkeypatch, scope):
    m, _, sfx = scope
    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake)

    out = _run(fn(m, "create", sfx)(ctx, chain="pre routing", action="drop", protocol="udp"))
    assert "Invalid chain name" in out
    assert fake.commands == []


def test_create_jump_needs_target(ctx, monkeypatch, scope):
    m, _, sfx = scope
    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake)

    out = _run(fn(m, "create", sfx)(ctx, chain="prerouting", action="jump", protocol="udp"))
    assert "needs jump_target" in out
    assert fake.commands == []


def test_create_without_matcher_warns(ctx, monkeypatch, scope):
    m, _, sfx = scope
    fake = ScriptedExecutor({":put [": "*2", "print detail": DETAIL})
    monkeypatch.setattr(m, "execute_mikrotik_command", fake)

    out = _run(fn(m, "create", sfx)(ctx, chain="prerouting", action="notrack"))
    assert out.startswith("WARNING")


def test_family_specific_matchers():
    from mcp_mikrotik.scope import firewall_raw, ipv6_firewall_raw
    import inspect
    assert "ttl" in inspect.signature(firewall_raw.mikrotik_create_raw_rule).parameters
    assert "hop_limit" not in inspect.signature(firewall_raw.mikrotik_create_raw_rule).parameters
    assert "hop_limit" in inspect.signature(ipv6_firewall_raw.mikrotik_create_ipv6_raw_rule).parameters
    assert "ttl" not in inspect.signature(ipv6_firewall_raw.mikrotik_create_ipv6_raw_rule).parameters


# --- list / get -------------------------------------------------------------

def test_list_quotes_filters_and_stats(ctx, monkeypatch, scope):
    m, menu, sfx = scope
    fake = ScriptedExecutor({"print": "Flags: X\nColumns: CHAIN, ACTION\n#  CHAIN       ACTION\n0  prerouting  drop\n"})
    monkeypatch.setattr(m, "execute_mikrotik_command", fake)

    out = _run(fn(m, "list", sfx.replace("rule", "rules"))(
        ctx, chain_filter="prerouting", protocol_filter="udp", stats=True))
    assert fake.commands[0] == f'{menu} print stats where chain="prerouting" protocol="udp"'
    assert "(STATS)" in out


def test_list_empty_legend_only(ctx, monkeypatch, scope):
    m, _, sfx = scope
    fake = ScriptedExecutor({"print": "Flags: X - disabled, I - invalid; D - dynamic\n"})
    monkeypatch.setattr(m, "execute_mikrotik_command", fake)

    out = _run(fn(m, "list", sfx.replace("rule", "rules"))(ctx))
    assert out.startswith("No ")


def test_get_not_found_on_legend_only(ctx, monkeypatch, scope):
    m, _, sfx = scope
    fake = ScriptedExecutor({"print detail": "Flags: X - disabled\n"})
    monkeypatch.setattr(m, "execute_mikrotik_command", fake)

    out = _run(fn(m, "get", sfx)(ctx, rule_id="*9"))
    assert "not found" in out


def test_get_rejects_garbage_id(ctx, monkeypatch, scope):
    m, _, sfx = scope
    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake)

    out = _run(fn(m, "get", sfx)(ctx, rule_id="*1 or 1"))
    assert "not found" in out
    assert fake.commands == []


# --- update / remove / move -------------------------------------------------

def test_update_set_and_clear(ctx, monkeypatch, scope):
    m, menu, sfx = scope
    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake)

    out = _run(fn(m, "update", sfx)(ctx, rule_id="*3", action="drop", src_address="", dst_port="53"))
    set_cmd = next(c for c in fake.commands if " set " in c)
    assert set_cmd == f"{menu} set *3 action=drop !src-address dst-port=53"
    assert "updated successfully" in out


def test_update_refusal(ctx, monkeypatch, scope):
    m, _, sfx = scope
    fake = ScriptedExecutor({"count-only": "1", " set ": "not enough permissions (9)"})
    monkeypatch.setattr(m, "execute_mikrotik_command", fake)

    out = _run(fn(m, "disable", sfx)(ctx, rule_id="*3"))
    assert out.startswith("Failed to update")


def test_update_not_found(ctx, monkeypatch, scope):
    m, _, sfx = scope
    fake = ScriptedExecutor({"count-only": "0"})
    monkeypatch.setattr(m, "execute_mikrotik_command", fake)

    out = _run(fn(m, "enable", sfx)(ctx, rule_id="*3"))
    assert "not found" in out
    assert not any(" set " in c for c in fake.commands)


def test_remove_confirms(ctx, monkeypatch, scope):
    m, menu, sfx = scope
    counts = iter(["1", "0"])

    class Exec(FakeExecutor):
        async def __call__(self, command, _ctx, device=None):
            self.commands.append(command)
            return next(counts) if "count-only" in command else ""

    fake = Exec()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake)
    out = _run(fn(m, "remove", sfx)(ctx, rule_id="*4"))
    assert f"{menu} remove *4" in fake.commands
    assert "removed successfully" in out


def test_remove_still_present(ctx, monkeypatch, scope):
    m, _, sfx = scope
    fake = ScriptedExecutor({"count-only": "1"})
    monkeypatch.setattr(m, "execute_mikrotik_command", fake)

    out = _run(fn(m, "remove", sfx)(ctx, rule_id="*4"))
    assert "still present" in out


def test_move_uses_ids(ctx, monkeypatch, scope):
    m, menu, sfx = scope
    fake = ScriptedExecutor({"count-only": "1", ":put [:pick": "*2", ":put [": "*1;*2;*3"})
    monkeypatch.setattr(m, "execute_mikrotik_command", fake)

    out = _run(fn(m, "move", sfx)(ctx, rule_id="*2", destination=0))
    assert f"{menu} move *2 destination=*1" in fake.commands
    assert "moved to position 0" in out
