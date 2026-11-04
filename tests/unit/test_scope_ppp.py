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


def test_ppp_active(ctx, monkeypatch):
    from mcp_mikrotik.scope import ppp

    fake = FakeExecutor({
        "/ppp active print detail where service=sstp": " 0   name=\"medulin\" service=sstp caller-id=\"93.136.90.189\" address=172.12.3.2 uptime=10h\n",
        "/ppp active print detail where service=ovpn": "Flags: R - RADIUS\n",
        "/ppp active print detail where name=\"medulin\"": " 0   name=\"medulin\" service=sstp caller-id=\"93.136.90.189\" address=172.12.3.2 uptime=10h\n",
        "/ppp active print detail where name=\"unknown-user\"": "",
        "/ppp active print detail": " 0   name=\"medulin\" service=sstp caller-id=\"93.136.90.189\" address=172.12.3.2 uptime=10h\n 1   name=\"cjeplak1\" service=sstp caller-id=\"78.0.37.167\" address=172.12.2.2 uptime=10h\n",
        "/ppp active remove": "",
    })
    monkeypatch.setattr(ppp, "execute_mikrotik_command", fake, raising=True)

    # 1. List active
    res_list = _run(ppp.mikrotik_list_ppp_active(ctx, device="r1"))
    assert "ACTIVE PPP SESSIONS:" in res_list
    assert 'name="medulin"' in res_list
    assert fake.devices[-1] == "r1"

    # With service filter
    res_svc = _run(ppp.mikrotik_list_ppp_active(ctx, service="sstp"))
    assert "where service=sstp" in fake.commands[-1]
    assert 'name="medulin"' in res_svc

    # Empty list
    fake.default_response = "Flags: R - RADIUS\n"
    res_empty = _run(ppp.mikrotik_list_ppp_active(ctx, service="ovpn"))
    assert "No active PPP sessions found" in res_empty

    # 2. Get active
    res_get = _run(ppp.mikrotik_get_ppp_active(ctx, name="medulin"))
    assert "ACTIVE PPP SESSION (medulin):" in res_get
    assert 'name="medulin"' in res_get

    # Get not found
    res_not_found = _run(ppp.mikrotik_get_ppp_active(ctx, name="unknown-user"))
    assert "Active session for user 'unknown-user' not found." in res_not_found

    # 3. Disconnect session
    res_disc = _run(ppp.mikrotik_disconnect_ppp_session(ctx, name="medulin"))
    assert "disconnected successfully" in res_disc
    assert '/ppp active remove [find name="medulin"]' in fake.commands[-1]


def test_ppp_secrets(ctx, monkeypatch):
    from mcp_mikrotik.scope import ppp

    fake = FakeExecutor({
        "/ppp secret print detail where name=\"medulin\"": " 0   name=\"medulin\" service=sstp profile=default-encryption local-address=172.12.3.1 remote-address=172.12.3.2\n",
        "/ppp secret print detail where name=\"unknown\"": "",
        "/ppp secret print detail": " 0   name=\"medulin\" service=sstp profile=default-encryption local-address=172.12.3.1 remote-address=172.12.3.2\n",
        "/ppp secret add": "",
        "/ppp secret set": "",
        "/ppp secret remove": "",
    })
    monkeypatch.setattr(ppp, "execute_mikrotik_command", fake, raising=True)

    # 1. List secrets
    res_list = _run(ppp.mikrotik_list_ppp_secrets(ctx, service="sstp", device="r1"))
    assert "PPP SECRETS:" in res_list
    assert 'name="medulin"' in res_list
    assert fake.devices[-1] == "r1"

    # 2. Get secret
    res_get = _run(ppp.mikrotik_get_ppp_secret(ctx, name="medulin"))
    assert "PPP SECRET (medulin):" in res_get
    assert 'name="medulin"' in res_get

    # Not found
    fake.default_response = ""
    res_not_found = _run(ppp.mikrotik_get_ppp_secret(ctx, name="unknown"))
    assert "PPP secret for user 'unknown' not found." in res_not_found

    # 3. Create secret
    res_create = _run(ppp.mikrotik_create_ppp_secret(
        ctx,
        name="newvpn",
        password="secretpassword",
        service="sstp",
        profile="default-encryption",
        local_address="172.12.4.1",
        remote_address="172.12.4.2",
        comment="Test client",
        disabled=True
    ))
    assert "created successfully" in res_create
    assert '/ppp secret add name="newvpn"' in fake.commands[-1]
    assert 'password="secretpassword"' in fake.commands[-1]
    assert 'service=sstp' in fake.commands[-1]
    assert 'local-address="172.12.4.1"' in fake.commands[-1]
    assert 'disabled=yes' in fake.commands[-1]
    assert "secretpassword" in fake.redacted

    # Validation errors on IP
    assert "Invalid local_address" in _run(ppp.mikrotik_create_ppp_secret(ctx, name="u", password="p", local_address="invalid-ip"))
    assert "Invalid remote_address" in _run(ppp.mikrotik_create_ppp_secret(ctx, name="u", password="p", remote_address="invalid-ip"))

    # 4. Update secret
    res_upd = _run(ppp.mikrotik_update_ppp_secret(
        ctx,
        name="newvpn",
        password="newsecretpassword",
        disabled=False
    ))
    assert "updated successfully" in res_upd
    assert '/ppp secret set [find name="newvpn"]' in fake.commands[-1]
    assert 'password="newsecretpassword"' in fake.commands[-1]
    assert "disabled=no" in fake.commands[-1]
    assert "newsecretpassword" in fake.redacted

    assert "No updates specified." in _run(ppp.mikrotik_update_ppp_secret(ctx, name="newvpn"))

    # 5. Remove secret
    res_rem = _run(ppp.mikrotik_remove_ppp_secret(ctx, name="newvpn"))
    assert "removed successfully" in res_rem
    assert '/ppp secret remove [find name="newvpn"]' in fake.commands[-1]


def test_ppp_profiles(ctx, monkeypatch):
    from mcp_mikrotik.scope import ppp

    fake = FakeExecutor({
        "/ppp profile print detail": " 0 * name=\"default\" bridge-learning=default\n 1 * name=\"default-encryption\" use-encryption=yes\n"
    })
    monkeypatch.setattr(ppp, "execute_mikrotik_command", fake, raising=True)

    res = _run(ppp.mikrotik_list_ppp_profiles(ctx, device="r1"))
    assert "PPP PROFILES:" in res
    assert 'name="default-encryption"' in res


def test_vpn_clients(ctx, monkeypatch):
    from mcp_mikrotik.scope import ppp

    fake = FakeExecutor({
        "/interface sstp-client print detail": " 0  R name=\"sstp-zagreb\" connect-to=vpn.example.com user=\"client1\"\n",
        "/interface sstp-client monitor [find name=\"sstp-zagreb\"] once": "               status: connected\n               uptime: 10h\n             encoding: AES256-CBC\n        local-address: 172.12.3.2\n       remote-address: 172.12.3.1\n",
        "/interface sstp-client add": "",
        "/interface sstp-client set": "",
        "/interface sstp-client remove": "",
    })
    monkeypatch.setattr(ppp, "execute_mikrotik_command", fake, raising=True)

    # 1. List clients
    res_list = _run(ppp.mikrotik_list_vpn_clients(ctx, vpn_type="sstp"))
    assert "SSTP CLIENT INTERFACES:" in res_list
    assert 'name="sstp-zagreb"' in res_list

    # 2. Monitor client
    res_mon = _run(ppp.mikrotik_monitor_vpn_client(ctx, name="sstp-zagreb", vpn_type="sstp"))
    assert "SSTP CLIENT STATUS (sstp-zagreb):" in res_mon
    assert "status: connected" in res_mon
    assert "172.12.3.2" in res_mon

    # Monitor not found
    fake.default_response = ""
    res_mon_nf = _run(ppp.mikrotik_monitor_vpn_client(ctx, name="unknown", vpn_type="sstp"))
    assert "not found or monitor returned no status." in res_mon_nf

    # 3. Create client
    res_create = _run(ppp.mikrotik_create_vpn_client(
        ctx,
        name="sstp-backup",
        connect_to="backup.example.com",
        user="client2",
        password="clientpassword",
        vpn_type="sstp",
        port=444,
        disabled=True
    ))
    assert "created successfully" in res_create
    assert '/interface sstp-client add name="sstp-backup"' in fake.commands[-1]
    assert 'connect-to="backup.example.com"' in fake.commands[-1]
    assert 'port=444' in fake.commands[-1]
    assert "disabled=yes" in fake.commands[-1]
    assert "clientpassword" in fake.redacted

    # Invalid host
    assert "Invalid connect_to host" in _run(ppp.mikrotik_create_vpn_client(ctx, name="c", connect_to="bad host!;", user="u", password="p"))

    # 4. Update client
    res_upd = _run(ppp.mikrotik_update_vpn_client(
        ctx,
        name="sstp-backup",
        vpn_type="sstp",
        connect_to="primary.example.com",
        port=443
    ))
    assert "updated successfully" in res_upd
    assert '/interface sstp-client set [find name="sstp-backup"]' in fake.commands[-1]
    assert 'connect-to="primary.example.com"' in fake.commands[-1]
    assert 'port=443' in fake.commands[-1]

    assert "No updates specified." in _run(ppp.mikrotik_update_vpn_client(ctx, name="sstp-backup", vpn_type="sstp"))

    # 5. Remove client
    res_rem = _run(ppp.mikrotik_remove_vpn_client(ctx, name="sstp-backup", vpn_type="sstp"))
    assert "removed successfully" in res_rem
    assert '/interface sstp-client remove [find name="sstp-backup"]' in fake.commands[-1]


def test_vpn_server_settings(ctx, monkeypatch):
    from mcp_mikrotik.scope import ppp

    fake = FakeExecutor({
        "/interface sstp-server server print": "enabled: yes\nport: 444\ndefault-profile: default-encryption\n",
        "/interface sstp-server server set": "",
    })
    monkeypatch.setattr(ppp, "execute_mikrotik_command", fake, raising=True)

    # 1. Get server settings
    res_get = _run(ppp.mikrotik_get_vpn_server_settings(ctx, vpn_type="sstp"))
    assert "SSTP SERVER SETTINGS:" in res_get
    assert "port: 444" in res_get

    # 2. Update server settings
    res_upd = _run(ppp.mikrotik_update_vpn_server_settings(
        ctx,
        vpn_type="sstp",
        enabled=True,
        port=444,
        default_profile="default-encryption"
    ))
    assert "updated successfully" in res_upd
    assert "/interface sstp-server server set enabled=yes port=444 default-profile=\"default-encryption\"" in fake.commands[-1]

    assert "No updates specified." in _run(ppp.mikrotik_update_vpn_server_settings(ctx, vpn_type="sstp"))


def test_invalid_names(ctx):
    from mcp_mikrotik.scope import ppp

    assert "Invalid username" in _run(ppp.mikrotik_get_ppp_active(ctx, name="bad user;!"))
    assert "Invalid username" in _run(ppp.mikrotik_disconnect_ppp_session(ctx, name="bad user;!"))
    assert "Invalid username" in _run(ppp.mikrotik_get_ppp_secret(ctx, name="bad;user"))
    assert "Invalid client interface name" in _run(ppp.mikrotik_monitor_vpn_client(ctx, name="bad;name"))
