"""Free-text filters of the read-only scopes must not be able to leave their quotes.

RouterOS ends a double-quoted string at the first unescaped `"`, and `;` separates
commands on a CLI line. A filter value such as `x" ; /ip firewall address-list add ...`
therefore ran a second command, even on a server started with `--read-only`.
"""

import asyncio
import re

import pytest

from tests.conftest import FakeExecutor

PAYLOAD = 'x" ; /ip firewall address-list add list=pwn ; :put "y'

# (module, function, parameter) for every free-text filter in the IPsec, netwatch,
# scheduler and services scopes.
CASES = [
    ("vpn.ipsec", "mikrotik_get_ipsec_installed_sa", "src_address_filter"),
    ("vpn.ipsec", "mikrotik_get_ipsec_installed_sa", "dst_address_filter"),
    ("vpn.ipsec", "mikrotik_get_ipsec_active_peers", "remote_address_filter"),
    ("vpn.ipsec", "mikrotik_get_ipsec_active_peers", "state_filter"),
    ("vpn.ipsec", "mikrotik_list_ipsec_peers", "name_filter"),
    ("vpn.ipsec", "mikrotik_list_ipsec_peers", "address_filter"),
    ("vpn.ipsec", "mikrotik_list_ipsec_policies", "peer_filter"),
    ("vpn.ipsec", "mikrotik_list_ipsec_policies", "src_address_filter"),
    ("vpn.ipsec", "mikrotik_list_ipsec_policies", "dst_address_filter"),
    ("vpn.ipsec", "mikrotik_list_ipsec_profiles", "name_filter"),
    ("vpn.ipsec", "mikrotik_list_ipsec_proposals", "name_filter"),
    ("monitoring.netwatch", "mikrotik_list_netwatch", "host_filter"),
    ("monitoring.netwatch", "mikrotik_list_netwatch", "comment_filter"),
    ("monitoring.netwatch", "mikrotik_list_netwatch", "status_filter"),
    ("monitoring.netwatch", "mikrotik_list_netwatch", "type_filter"),
    ("system.scheduler", "mikrotik_list_schedulers", "name_filter"),
    ("system.scheduler", "mikrotik_list_scripts", "name_filter"),
    ("ip.services", "mikrotik_list_ip_services", "name_filter"),
]

# A double-quoted RouterOS string, escapes included.
QUOTED = re.compile(r'"(?:[^"\\]|\\.)*"')


@pytest.mark.parametrize("module_name,func,param", CASES)
def test_filter_value_cannot_leave_its_quotes(ctx, monkeypatch, module_name, func, param):
    from mcp_mikrotik.scope._shared.quoting import ros_quoted

    module = __import__(f"mcp_mikrotik.scope.{module_name}", fromlist=["*"])
    fake = FakeExecutor()
    monkeypatch.setattr(module, "execute_mikrotik_command", fake, raising=True)

    asyncio.run(getattr(module, func)(ctx, **{param: PAYLOAD}))

    command = fake.commands[-1]
    assert ros_quoted(PAYLOAD) in command
    assert PAYLOAD not in command
    # Take every quoted string out: what is left is the command the tool built, and
    # nothing the caller supplied may be in it.
    outside = QUOTED.sub('""', command)
    assert ";" not in outside, command
    assert "address-list" not in outside, command
    assert ":put" not in outside, command
