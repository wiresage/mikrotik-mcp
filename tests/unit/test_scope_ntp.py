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


MOCK_NTP_CLIENT = """\
      enabled: yes
         mode: unicast
      servers: 161.53.123.5, 1.1.1.1
       status: synchronized
synced-server: 161.53.123.5
synced-stratum: 1
system-offset: -1.129 ms
   freq-drift: 10.081 PPM
"""

MOCK_CLOCK = """\
                time: 21:30:00
                date: 2026-11-04
time-zone-autodetect: no
      time-zone-name: Europe/Zagreb
          gmt-offset: +01:00
          dst-active: no
"""

MOCK_NTP_SERVERS = """\
 0  address=161.53.123.5 min-poll=6 max-poll=10 iburst=yes
 1  address=1.1.1.1 min-poll=6 max-poll=10 iburst=yes
"""

MOCK_NTP_SERVER_DAEMON = """\
            enabled: yes
          broadcast: yes
          multicast: yes
           manycast: yes
    use-local-clock: no
local-clock-stratum: 5
"""


def test_get_ntp_status_and_clock_sync(ctx, monkeypatch):
    from mcp_mikrotik.scope import ntp

    executor = FakeExecutor({
        "/system ntp client print": MOCK_NTP_CLIENT,
        "/system clock print": MOCK_CLOCK,
    })
    monkeypatch.setattr(ntp, "execute_mikrotik_command", executor)

    # Status
    status = _run(ntp.mikrotik_get_ntp_status(ctx))
    assert "NTP CLIENT STATUS:" in status
    assert "status: synchronized" in status

    # Clock sync: Synced
    sync_check = _run(ntp.mikrotik_check_clock_sync(ctx))
    assert "[SYNCED]" in sync_check
    assert "Europe/Zagreb" in sync_check
    assert "161.53.123.5" in sync_check
    assert "-1.129 ms" in sync_check

    # Clock sync: Disabled
    exec_dis = FakeExecutor({
        "/system ntp client print": "enabled: no\nstatus: stopped\n",
        "/system clock print": MOCK_CLOCK,
    })
    monkeypatch.setattr(ntp, "execute_mikrotik_command", exec_dis)
    dis_check = _run(ntp.mikrotik_check_clock_sync(ctx))
    assert "[DISABLED]" in dis_check

    # Clock sync: Unsynchronized
    exec_unsync = FakeExecutor({
        "/system ntp client print": "enabled: yes\nstatus: started\n",
        "/system clock print": MOCK_CLOCK,
    })
    monkeypatch.setattr(ntp, "execute_mikrotik_command", exec_unsync)
    unsync_check = _run(ntp.mikrotik_check_clock_sync(ctx))
    assert "[UNSYNCHRONIZED]" in unsync_check


def test_ntp_client_settings_and_update(ctx, monkeypatch):
    from mcp_mikrotik.scope import ntp

    executor = FakeExecutor({
        "/system ntp client print": MOCK_NTP_CLIENT,
        "/system ntp client servers print detail": MOCK_NTP_SERVERS,
        "/system ntp client set": "",
    })
    monkeypatch.setattr(ntp, "execute_mikrotik_command", executor)

    # Get settings
    settings = _run(ntp.mikrotik_get_ntp_client_settings(ctx))
    assert "NTP CLIENT CONFIGURATION:" in settings
    assert "161.53.123.5" in settings

    # Update client
    upd = _run(ntp.mikrotik_update_ntp_client(ctx, enabled=True, mode="unicast", vrf="main"))
    assert "NTP client updated successfully." in upd
    assert "enabled=yes" in executor.commands[-1]
    assert "mode=unicast" in executor.commands[-1]
    assert "vrf=main" in executor.commands[-1]

    # Error handling
    err_vrf = _run(ntp.mikrotik_update_ntp_client(ctx, vrf="bad;vrf"))
    assert "Invalid VRF name" in err_vrf

    err_empty = _run(ntp.mikrotik_update_ntp_client(ctx))
    assert "No NTP client settings provided" in err_empty


def test_add_and_remove_ntp_server(ctx, monkeypatch):
    from mcp_mikrotik.scope import ntp

    executor = FakeExecutor({
        'where address="time.cloudflare.com"': "Flags: X - disabled\n",
        'where address="161.53.123.5"': "0 address=161.53.123.5\n",
        "/system ntp client servers add": "",
        "/system ntp client servers remove": "",
    })
    monkeypatch.setattr(ntp, "execute_mikrotik_command", executor)

    # Add new server
    add_res = _run(ntp.mikrotik_add_ntp_server(ctx, address="time.cloudflare.com", iburst=True, min_poll=6, max_poll=10))
    assert "NTP server 'time.cloudflare.com' added successfully." in add_res
    assert 'address="time.cloudflare.com"' in executor.commands[-1]
    assert "iburst=yes" in executor.commands[-1]
    assert "min-poll=6" in executor.commands[-1]

    # Add already existing server
    dup_res = _run(ntp.mikrotik_add_ntp_server(ctx, address="161.53.123.5"))
    assert "already configured" in dup_res

    # Remove server
    rem_res = _run(ntp.mikrotik_remove_ntp_server(ctx, address="161.53.123.5"))
    assert "NTP server '161.53.123.5' removed successfully." in rem_res
    assert 'remove [find address="161.53.123.5"]' in executor.commands[-1]

    # Invalid address format
    err_addr = _run(ntp.mikrotik_add_ntp_server(ctx, address="bad;address!"))
    assert "Invalid NTP server address" in err_addr


def test_ntp_server_and_system_clock(ctx, monkeypatch):
    from mcp_mikrotik.scope import ntp

    executor = FakeExecutor({
        "/system ntp server print": MOCK_NTP_SERVER_DAEMON,
        "/system ntp server set": "",
        "/system clock set": "",
    })
    monkeypatch.setattr(ntp, "execute_mikrotik_command", executor)

    # Get NTP server daemon settings
    server_settings = _run(ntp.mikrotik_get_ntp_server_settings(ctx))
    assert "NTP SERVER SETTINGS:" in server_settings
    assert "broadcast: yes" in server_settings

    # Update NTP server daemon
    upd_server = _run(ntp.mikrotik_update_ntp_server(ctx, enabled=True, broadcast=True, manycast=True, local_clock_stratum=5))
    assert "NTP server settings updated successfully." in upd_server
    assert "enabled=yes" in executor.commands[-1]
    assert "broadcast=yes" in executor.commands[-1]
    assert "local-clock-stratum=5" in executor.commands[-1]

    # Update system clock
    upd_clock = _run(ntp.mikrotik_update_system_clock(ctx, time_zone_name="Europe/Zagreb", time_zone_autodetect=False))
    assert "System clock settings updated successfully." in upd_clock
    assert 'time-zone-name="Europe/Zagreb"' in executor.commands[-1]
    assert "time-zone-autodetect=no" in executor.commands[-1]

    # Invalid timezone
    err_tz = _run(ntp.mikrotik_update_system_clock(ctx, time_zone_name="bad;zone!"))
    assert "Invalid timezone name" in err_tz
