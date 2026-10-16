import asyncio

from tests.conftest import FakeExecutor


def _run(coro):
    return asyncio.run(coro)


from mcp_mikrotik.scope.netwatch import _PROBE_METADATA as _META

# The three properties of `/tool netwatch` that hold commands, and therefore
# the credentials a probe uses to raise an alert.
_SCRIPT_PROPS = ("up-script", "down-script", "test-script")


class DetailFake(FakeExecutor):
    async def __call__(self, command, _ctx, device=None):
        result = await super().__call__(command, _ctx, device)
        return "host=192.0.2.1 status=up " + result if "print" in command.lower() else result


class ScriptFake(FakeExecutor):
    """A probe whose scripts alert through a webhook carrying a token."""

    async def __call__(self, command, _ctx, device=None):
        await super().__call__(command, _ctx, device)
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


def test_command_filters_and_device(ctx, monkeypatch):
    from mcp_mikrotik.scope import netwatch

    fake = DetailFake()
    monkeypatch.setattr(netwatch, "execute_mikrotik_command", fake, raising=True)

    out = _run(netwatch.mikrotik_list_netwatch(ctx, device="edge"))
    assert fake.commands == [f"/tool netwatch print detail proplist={_META}"]
    assert fake.devices == ["edge"]
    assert out.startswith("NETWATCH PROBES:")

    _run(netwatch.mikrotik_list_netwatch(
        ctx, host_filter="1.1.1.1", comment_filter="Internet",
        status_filter="down", type_filter="simple",
    ))
    assert fake.commands[-1] == (
        f'/tool netwatch print detail proplist={_META} where host~"1.1.1.1" '
        'comment~"Internet" status="down" type="simple"'
    )


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
    assert f"proplist={_META}" in fake.commands[-1]
    for prop in _SCRIPT_PROPS:
        assert prop not in _META

    out = _run(netwatch.mikrotik_list_netwatch(ctx, include_source=True))
    assert "proplist" not in fake.commands[-1]
    assert out.startswith("NETWATCH PROBES (with scripts):")
    assert "hunter2" not in out


def test_proplist_keeps_the_measurements(ctx):
    """Hiding the scripts must not cost the numbers the probe exists to report.

    A proplist is a whitelist, so every property not named in it is lost. An
    export already says which probes exist; what only `print detail` adds is
    the live state and the ICMP statistics, so dropping those in order to hide
    the scripts would trade one gap for another.
    """
    fields = _META.split(",")

    assert len(fields) == len(set(fields)), "duplicate property in the proplist"
    for prop in _SCRIPT_PROPS:
        assert prop not in fields

    for prop in (
        "status", "since", "rtt-avg", "loss-percent", "failed-tests",
        "thr-avg", "thr-loss-count", "packet-count", "packet-interval",
    ):
        assert prop in fields, f"{prop} is not reachable through the default"


def test_no_match_is_not_the_legend(ctx, monkeypatch):
    from mcp_mikrotik.scope import netwatch

    monkeypatch.setattr(netwatch, "execute_mikrotik_command", LegendOnlyFake(), raising=True)
    out = _run(netwatch.mikrotik_list_netwatch(ctx, status_filter="down"))
    assert out == "No netwatch probes found matching the criteria."
