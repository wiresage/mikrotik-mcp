import asyncio

from tests.conftest import FakeExecutor


def _run(coro):
    return asyncio.run(coro)


_META = "host,type,interval,timeout,status,since,comment,disabled,src-address"


class DetailFake(FakeExecutor):
    async def __call__(self, command, _ctx, device=None):
        result = await super().__call__(command, _ctx, device)
        return "host=192.0.2.1 status=up " + result if "print" in command.lower() else result


class ScriptFake(FakeExecutor):
    """A probe whose down-script alerts through a webhook carrying a token."""

    async def __call__(self, command, _ctx, device=None):
        await super().__call__(command, _ctx, device)
        return (
            'host=192.0.2.1 status=up down-script="/tool fetch '
            'url=https://hooks.example/notify password=hunter2"\n'
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
    assert "script" not in _META

    out = _run(netwatch.mikrotik_list_netwatch(ctx, include_source=True))
    assert "proplist" not in fake.commands[-1]
    assert out.startswith("NETWATCH PROBES (with scripts):")
    assert "hunter2" not in out


def test_no_match_is_not_the_legend(ctx, monkeypatch):
    from mcp_mikrotik.scope import netwatch

    monkeypatch.setattr(netwatch, "execute_mikrotik_command", LegendOnlyFake(), raising=True)
    out = _run(netwatch.mikrotik_list_netwatch(ctx, status_filter="down"))
    assert out == "No netwatch probes found matching the criteria."
