import asyncio

from tests.conftest import FakeExecutor


def _run(coro):
    return asyncio.run(coro)


class DetailFake(FakeExecutor):
    """FakeExecutor whose print output carries every marker the IPsec tools
    look for, so a command is exercised rather than short-circuited by the
    no-match check."""

    MARKERS = 'spi=0x1 remote-address=192.0.2.1 name="peer" dst-address=10.0.0.0/24 '

    async def __call__(self, command, _ctx, device=None):
        result = await super().__call__(command, _ctx, device)
        return self.MARKERS + result if "print" in command.lower() else result


class LegendOnlyFake(FakeExecutor):
    """RouterOS answers a no-match `print detail` with the Flags legend alone.

    That output is non-empty, so a tool that only checked for emptiness would
    report the legend as a result.
    """

    async def __call__(self, command, _ctx, device=None):
        await super().__call__(command, _ctx, device)
        return "Flags: A - ACTIVE; S - SEEN-TRAFFIC\n"


def test_installed_sa_command_filters_and_device(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipsec

    fake = DetailFake()
    monkeypatch.setattr(ipsec, "execute_mikrotik_command", fake, raising=True)

    out = _run(ipsec.mikrotik_get_ipsec_installed_sa(ctx, device="edge"))
    assert fake.commands == ["/ip ipsec installed-sa print detail"]
    assert fake.devices == ["edge"]
    assert out.startswith("IPSEC INSTALLED SAs:")

    _run(ipsec.mikrotik_get_ipsec_installed_sa(
        ctx, src_address_filter="192.0.2.1", dst_address_filter="198.51.100.2",
    ))
    assert fake.commands[-1] == (
        '/ip ipsec installed-sa print detail where '
        'src-address="192.0.2.1" dst-address="198.51.100.2"'
    )


def test_installed_sa_keeps_the_flags_legend(ctx, monkeypatch):
    """The `S` flag is the whole point: it must survive into the output."""
    from mcp_mikrotik.scope import ipsec

    class WithFlags(FakeExecutor):
        async def __call__(self, command, _ctx, device=None):
            await super().__call__(command, _ctx, device)
            return (
                "Flags: A - ACTIVE; S - SEEN-TRAFFIC\n"
                ' 0  AS spi=0x0A1B2C3D src-address=192.0.2.1 dst-address=198.51.100.2\n'
            )

    monkeypatch.setattr(ipsec, "execute_mikrotik_command", WithFlags(), raising=True)
    out = _run(ipsec.mikrotik_get_ipsec_installed_sa(ctx))
    assert "SEEN-TRAFFIC" in out
    assert "AS spi=" in out


def test_no_match_is_not_reported_as_a_result(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipsec

    monkeypatch.setattr(ipsec, "execute_mikrotik_command", LegendOnlyFake(), raising=True)
    for call in (
        ipsec.mikrotik_get_ipsec_installed_sa(ctx),
        ipsec.mikrotik_get_ipsec_active_peers(ctx),
        ipsec.mikrotik_list_ipsec_peers(ctx),
        ipsec.mikrotik_list_ipsec_policies(ctx),
        ipsec.mikrotik_list_ipsec_profiles(ctx),
        ipsec.mikrotik_list_ipsec_proposals(ctx),
    ):
        assert _run(call).startswith("No ")


def test_active_peers_command_and_filters(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipsec

    fake = DetailFake()
    monkeypatch.setattr(ipsec, "execute_mikrotik_command", fake, raising=True)

    out = _run(ipsec.mikrotik_get_ipsec_active_peers(ctx))
    assert fake.commands[-1] == "/ip ipsec active-peers print detail"
    assert out.startswith("IPSEC ACTIVE PEERS:")

    _run(ipsec.mikrotik_get_ipsec_active_peers(
        ctx, remote_address_filter="192.0.2.1", state_filter="established",
    ))
    assert fake.commands[-1] == (
        '/ip ipsec active-peers print detail where '
        'remote-address="192.0.2.1" state="established"'
    )


def test_peers_policies_profiles_proposals(ctx, monkeypatch):
    from mcp_mikrotik.scope import ipsec

    fake = DetailFake()
    monkeypatch.setattr(ipsec, "execute_mikrotik_command", fake, raising=True)

    _run(ipsec.mikrotik_list_ipsec_peers(ctx, name_filter="Azure", address_filter="192.0.2"))
    assert fake.commands[-1] == (
        '/ip ipsec peer print detail where name~"Azure" address~"192.0.2"'
    )

    _run(ipsec.mikrotik_list_ipsec_policies(
        ctx, peer_filter="Azure", src_address_filter="10.0", dst_address_filter="10.1",
    ))
    assert fake.commands[-1] == (
        '/ip ipsec policy print detail where peer~"Azure" '
        'src-address~"10.0" dst-address~"10.1"'
    )

    _run(ipsec.mikrotik_list_ipsec_profiles(ctx, name_filter="Azure"))
    assert fake.commands[-1] == '/ip ipsec profile print detail where name~"Azure"'

    _run(ipsec.mikrotik_list_ipsec_proposals(ctx, name_filter="Azure"))
    assert fake.commands[-1] == '/ip ipsec proposal print detail where name~"Azure"'


def test_every_tool_is_read_only(ctx):
    """These must survive --read-only: the module exists to be usable there."""
    from mcp_mikrotik.scope import ipsec  # noqa: F401
    from mcp_mikrotik.app import mcp

    names = {
        "get_ipsec_installed_sa", "get_ipsec_active_peers", "list_ipsec_peers",
        "list_ipsec_policies", "list_ipsec_profiles", "list_ipsec_proposals",
    }
    tools = _run(mcp.list_tools())
    found = {t.name: t for t in tools if t.name in names}
    assert set(found) == names, f"missing: {names - set(found)}"
    for name, tool in found.items():
        assert tool.annotations.read_only_hint is True, name


def test_no_tool_exposes_ipsec_identities(ctx):
    """`/ip ipsec identity print detail` carries `secret=` in clear text."""
    from mcp_mikrotik.scope import ipsec

    source = __import__("inspect").getsource(ipsec)
    assert "ipsec identity" not in source.replace("`/ip ipsec identity`", "")
