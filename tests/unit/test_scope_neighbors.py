import asyncio
import pytest
from unittest.mock import AsyncMock


def _run(coro):
    return asyncio.run(coro)


class FakeExecutor:
    def __init__(self, responses=None):
        self.commands = []
        self.devices = []
        self.redacted = []
        self.responses = responses or {}
        self.default_response = ""

    async def __call__(self, command, ctx, device=None, redact=None, **kwargs):
        self.commands.append(command)
        self.devices.append(device)
        if redact:
            self.redacted.extend(redact)
        for pattern in sorted(self.responses.keys(), key=len, reverse=True):
            if pattern in command:
                return self.responses[pattern]
        return self.default_response


@pytest.fixture
def ctx():
    class DummyContext:
        info = AsyncMock()
        warning = AsyncMock()
        error = AsyncMock()
    return DummyContext()


MOCK_NEIGHBORS = """\
 0  interface=eth2,bridge-LAN address=10.5.167.3 mac-address=CC:2D:E0:2B:F2:96 identity="Tavan" platform="MikroTik" version="7.25.1" board="RB962UiGS-5HacT2HnT" discovered-by=cdp,mndp
 1  interface=eth2,bridge-LAN address=10.5.167.5 mac-address=E4:8D:8C:AB:9D:4C identity="Podrum2" platform="MikroTik" version="7.24.5" board="RB951G-2HnD" discovered-by=cdp,mndp
"""

MOCK_SETTINGS = """\
discover-interface-list: LAN
         discover-interval: 30s
                  protocol: cdp,lldp,mndp
                      mode: tx-and-rx
                  lldp-med: yes
"""


def test_list_discovered_neighbors(ctx, monkeypatch):
    from mcp_mikrotik.scope import neighbors

    executor = FakeExecutor({
        "/ip neighbor print detail": MOCK_NEIGHBORS,
    })
    monkeypatch.setattr(neighbors, "execute_mikrotik_command", executor)

    # All neighbors
    res = _run(neighbors.mikrotik_list_discovered_neighbors(ctx))
    assert "DISCOVERED NEIGHBORS:" in res
    assert 'identity="Tavan"' in res

    # Filters
    _run(neighbors.mikrotik_list_discovered_neighbors(
        ctx,
        interface_filter="bridge-LAN",
        identity_filter="Tavan",
        mac_filter="CC:2D:E0:2B:F2:96",
        protocol_filter="mndp",
        device="Mikrotik-ADSL",
    ))
    last_cmd = executor.commands[-1]
    assert 'interface~"bridge-LAN"' in last_cmd
    assert 'identity~"Tavan"' in last_cmd
    assert 'mac-address~"CC:2D:E0:2B:F2:96"' in last_cmd
    assert 'discovered-by~"mndp"' in last_cmd

    # Invalid interface filter
    err = _run(neighbors.mikrotik_list_discovered_neighbors(ctx, interface_filter="bad;rm"))
    assert "Invalid interface name filter" in err

    # Empty result
    empty_exec = FakeExecutor({"/ip neighbor print detail": "Flags: X - disabled\n"})
    monkeypatch.setattr(neighbors, "execute_mikrotik_command", empty_exec)
    empty_res = _run(neighbors.mikrotik_list_discovered_neighbors(ctx))
    assert "No discovered neighbors found" in empty_res


def test_get_discovered_neighbor(ctx, monkeypatch):
    from mcp_mikrotik.scope import neighbors

    executor = FakeExecutor({
        'where mac-address="CC:2D:E0:2B:F2:96"': MOCK_NEIGHBORS.splitlines()[0] + "\n",
        'where identity="Tavan"': MOCK_NEIGHBORS.splitlines()[0] + "\n",
        ":put [:pick [/ip neighbor find] 0]": "*A1",
        "where .id=*A1": MOCK_NEIGHBORS.splitlines()[0] + "\n",
    })
    monkeypatch.setattr(neighbors, "execute_mikrotik_command", executor)

    # By MAC
    res_mac = _run(neighbors.mikrotik_get_discovered_neighbor(ctx, identifier="CC:2D:E0:2B:F2:96"))
    assert "DISCOVERED NEIGHBOR DETAILS:" in res_mac
    assert "CC:2D:E0:2B:F2:96" in res_mac

    # By Identity
    res_id = _run(neighbors.mikrotik_get_discovered_neighbor(ctx, identifier="Tavan"))
    assert "DISCOVERED NEIGHBOR DETAILS:" in res_id

    # By position ID
    res_num = _run(neighbors.mikrotik_get_discovered_neighbor(ctx, identifier="0"))
    assert "DISCOVERED NEIGHBOR DETAILS:" in res_num

    # Not found
    empty_exec = FakeExecutor()
    monkeypatch.setattr(neighbors, "execute_mikrotik_command", empty_exec)
    nf = _run(neighbors.mikrotik_get_discovered_neighbor(ctx, identifier="Nonexistent"))
    assert "No discovered neighbor found" in nf


def test_neighbor_discovery_settings(ctx, monkeypatch):
    from mcp_mikrotik.scope import neighbors

    executor = FakeExecutor({
        "/ip neighbor discovery-settings print": MOCK_SETTINGS,
        "/ip neighbor discovery-settings set": "",
    })
    monkeypatch.setattr(neighbors, "execute_mikrotik_command", executor)

    # Get settings
    settings = _run(neighbors.mikrotik_get_neighbor_discovery_settings(ctx))
    assert "NEIGHBOR DISCOVERY SETTINGS:" in settings
    assert "discover-interface-list: LAN" in settings

    # Update settings
    upd = _run(neighbors.mikrotik_update_neighbor_discovery_settings(
        ctx,
        discover_interface_list="LAN",
        protocol="cdp,lldp,mndp",
        mode="tx-and-rx",
        discover_interval="30s",
        lldp_med=True,
    ))
    assert "Neighbor discovery settings updated successfully." in upd
    assert "discover-interface-list=LAN" in executor.commands[-1]
    assert "protocol=cdp,lldp,mndp" in executor.commands[-1]
    assert "mode=tx-and-rx" in executor.commands[-1]
    assert "discover-interval=30s" in executor.commands[-1]
    assert "lldp-med=yes" in executor.commands[-1]

    # Validation errors
    err_list = _run(neighbors.mikrotik_update_neighbor_discovery_settings(ctx, discover_interface_list="bad;list"))
    assert "Invalid interface list name" in err_list

    err_interval = _run(neighbors.mikrotik_update_neighbor_discovery_settings(ctx, discover_interval="bad"))
    assert "Invalid discover interval format" in err_interval

    err_empty = _run(neighbors.mikrotik_update_neighbor_discovery_settings(ctx))
    assert "No discovery settings provided" in err_empty
