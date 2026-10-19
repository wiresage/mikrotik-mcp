import asyncio

from tests.conftest import FakeExecutor

from mcp_mikrotik.scope.netwatch import _PROBE_CONFIG as _CONFIG
from mcp_mikrotik.scope.netwatch import _PROBE_STATE as _STATE


def _run(coro):
    return asyncio.run(coro)


# The three properties of `/tool netwatch` that hold commands, and therefore
# the credentials a probe uses to raise an alert.
_SCRIPT_PROPS = ("up-script", "down-script", "test-script")

# Read-only arguments `print detail` never returns, measured on RouterOS
# 7.24.2, 7.24.4 and 7.24.5. Naming one in its proplist does not help.
_LIVE_ONLY = ("since", "rtt-avg", "rtt-min", "loss-percent", "failed-tests")

_AS_VALUE = (
    ".id=*1;comment=Internet;failed-tests=1;host=192.0.2.1;loss-percent=0;"
    "rtt-avg=00:00:00.013017;since=2026-10-19 10:19:10;status=up"
)


class DetailFake(FakeExecutor):
    """Answers the two commands the tool issues, each with its own shape."""

    async def __call__(self, command, _ctx, device=None):
        await super().__call__(command, _ctx, device)
        if "as-value" in command:
            return _AS_VALUE
        return "host=192.0.2.1 status=up\n"


class ScriptFake(FakeExecutor):
    """A probe whose scripts alert through a webhook carrying a token."""

    async def __call__(self, command, _ctx, device=None):
        await super().__call__(command, _ctx, device)
        if "as-value" in command:
            return _AS_VALUE
        return (
            'host=192.0.2.1 status=up down-script="/tool fetch '
            'url=https://hooks.example/notify password=hunter2" '
            'test-script="/tool e-mail send to=a@b.c password=hunter2"\n'
        )


class LegendOnlyFake(FakeExecutor):
    """A no-match `print detail` still returns the Flags legend."""

    async def __call__(self, command, _ctx, device=None):
        await super().__call__(command, _ctx, device)
        return "Flags: X - DISABLED\n"


class NoStateFake(FakeExecutor):
    """The configuration reads, the live state is refused."""

    async def __call__(self, command, _ctx, device=None):
        await super().__call__(command, _ctx, device)
        if "as-value" in command:
            return "input does not match any value of value-name"
        return "host=192.0.2.1 status=up\n"


def test_command_filters_and_device(ctx, monkeypatch):
    from mcp_mikrotik.scope import netwatch

    fake = DetailFake()
    monkeypatch.setattr(netwatch, "execute_mikrotik_command", fake, raising=True)

    out = _run(netwatch.mikrotik_list_netwatch(ctx, device="edge"))
    assert fake.commands == [
        f"/tool netwatch print detail proplist={_CONFIG}",
        f":put [/tool netwatch print as-value proplist={_STATE}]",
    ]
    assert fake.devices == ["edge", "edge"]
    assert out.startswith("NETWATCH PROBES:")

    fake.commands.clear()
    _run(netwatch.mikrotik_list_netwatch(
        ctx, host_filter="1.1.1.1", comment_filter="Internet",
        status_filter="down", type_filter="simple",
    ))
    where = ('where host~"1.1.1.1" comment~"Internet" status="down" '
             'type="simple"')
    # The same filter has to reach both commands, or the live state would
    # describe probes the configuration block never mentioned.
    assert fake.commands == [
        f"/tool netwatch print detail proplist={_CONFIG} {where}",
        f":put [/tool netwatch print as-value proplist={_STATE} {where}]",
    ]


def test_scripts_are_withheld_unless_asked_for(ctx, monkeypatch):
    """The default must not be able to return a script at all.

    `up-script`/`down-script` are commands, so a probe that alerts through a
    webhook or an e-mail carries the token or the password inline. The proplist
    is what keeps them off the wire; redaction alone would not, since it only
    matches patterns it recognises.
    """
    from mcp_mikrotik.scope import netwatch

    fake = ScriptFake()
    monkeypatch.setattr(netwatch, "execute_mikrotik_command", fake, raising=True)

    _run(netwatch.mikrotik_list_netwatch(ctx))
    assert f"proplist={_CONFIG}" in fake.commands[0]
    for prop in _SCRIPT_PROPS:
        assert prop not in _CONFIG
        assert prop not in _STATE

    fake.commands.clear()
    out = _run(netwatch.mikrotik_list_netwatch(ctx, include_source=True))
    assert "proplist" not in fake.commands[0]
    assert out.startswith("NETWATCH PROBES (with scripts):")
    assert "hunter2" not in out


def test_detail_proplist_drops_what_detail_never_returns(ctx):
    """`print detail` answers with configuration and `status`, nothing else.

    Measured on RouterOS 7.24.2, 7.24.4 and 7.24.5, with no proplist, with the
    full one, and with `proplist=host,status,since`: every read-only argument
    but `status` is absent. Carrying them in the detail proplist cost nothing
    on the wire but stated a capability the command does not have.
    """
    config = _CONFIG.split(",")
    state = _STATE.split(",")

    assert len(config) == len(set(config)), "duplicate property in the proplist"
    assert len(state) == len(set(state)), "duplicate property in the proplist"

    assert "status" in config, "`status` is the one read-only detail returns"
    for prop in _LIVE_ONLY:
        assert prop not in config, f"{prop} is not reachable through print detail"
        assert prop in state, f"{prop} has to come from the live state command"

    # The thresholds decide whether a probe is up at all: `type=icmp` brings a
    # 100 ms `thr-avg` default, so a healthy WAN with a 120 ms round trip
    # reports down and this is the field that says why.
    for prop in ("thr-avg", "thr-loss-count", "packet-count", "packet-interval"):
        assert prop in config


def test_live_state_is_a_second_command(ctx, monkeypatch):
    """The numbers only `print as-value` carries have to reach the caller."""
    from mcp_mikrotik.scope import netwatch

    monkeypatch.setattr(netwatch, "execute_mikrotik_command", DetailFake(), raising=True)

    out = _run(netwatch.mikrotik_list_netwatch(ctx))
    assert "LIVE STATE:" in out
    for value in ("since=2026-10-19 10:19:10", "rtt-avg=00:00:00.013017",
                  "failed-tests=1"):
        assert value in out


def test_live_state_records_split_on_id_only(ctx):
    """A `;` inside a value must not be read as a record boundary.

    `as-value` concatenates every record into one line with `;`, and a comment
    or a script may hold a semicolon of its own — RouterOS scripts usually do.
    """
    from mcp_mikrotik.scope.netwatch import _split_records

    out = _split_records(
        '.id=*1;comment=first;host=a;.id=*2;comment=has; a semicolon;host=b'
    )
    assert out.splitlines() == [
        ".id=*1;comment=first;host=a",
        ".id=*2;comment=has; a semicolon;host=b",
    ]


def test_a_refused_live_state_still_returns_the_configuration(ctx, monkeypatch):
    """A refusal prints on stdout with a zero exit status.

    The live state is an addition, so failing to read it must not cost the
    caller the configuration that was already in hand.
    """
    from mcp_mikrotik.scope import netwatch

    monkeypatch.setattr(netwatch, "execute_mikrotik_command", NoStateFake(), raising=True)

    out = _run(netwatch.mikrotik_list_netwatch(ctx))
    assert out.startswith("NETWATCH PROBES:")
    assert "host=192.0.2.1" in out
    assert "LIVE STATE:" not in out


def test_no_match_is_not_the_legend(ctx, monkeypatch):
    from mcp_mikrotik.scope import netwatch

    fake = LegendOnlyFake()
    monkeypatch.setattr(netwatch, "execute_mikrotik_command", fake, raising=True)
    out = _run(netwatch.mikrotik_list_netwatch(ctx, status_filter="down"))
    assert out == "No netwatch probes found matching the criteria."
    # Nothing matched, so the second command is never worth its round trip.
    assert len(fake.commands) == 1
