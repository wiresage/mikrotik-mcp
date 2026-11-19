"""Unit tests for the firewall address-list scope (IPv4 + IPv6)."""

import asyncio

from tests.conftest import FakeExecutor


def _run(coro):
    return asyncio.run(coro)


def _cmd(fake, needle):
    return next(c for c in fake.commands if needle in c)


# ---------------------------------------------------------------------------
# family routing
# ---------------------------------------------------------------------------

def test_ipv4_targets_the_ip_tree(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_list_address_list_entries(ctx, family="ipv4"))
    assert fake.commands[0] == "/ip firewall address-list print"


def test_ipv6_targets_the_ipv6_tree(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_list_address_list_entries(ctx, family="ipv6"))
    assert fake.commands[0] == "/ipv6 firewall address-list print"
    assert not any(c.startswith("/ip firewall") for c in fake.commands)


# ---------------------------------------------------------------------------
# address canonicalisation — IPv6 stores host entries with /128
# ---------------------------------------------------------------------------

def test_ipv6_host_address_gets_128(ctx, monkeypatch):
    """`where address="2001:db8::5"` matches nothing; RouterOS stores /128."""
    from mcp_mikrotik.scope.firewall import address_list as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_get_address_list_entry(ctx, family="ipv6", list_name="l", address="2001:db8::5"))
    assert 'address="2001:db8::5/128"' in fake.commands[0]


def test_ipv6_address_is_lowercased_and_compressed(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_get_address_list_entry(ctx, family="ipv6", list_name="l",
                                           address="2001:DB8:0:0:0:0:0:5"))
    assert 'address="2001:db8::5/128"' in fake.commands[0]


def test_ipv6_prefix_is_left_alone(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_get_address_list_entry(ctx, family="ipv6", list_name="l",
                                           address="2001:db8:1::/64"))
    assert 'address="2001:db8:1::/64"' in fake.commands[0]


def test_ipv4_address_is_not_rewritten(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_get_address_list_entry(ctx, family="ipv4", list_name="l",
                                           address="203.0.113.9"))
    assert 'address="203.0.113.9"' in fake.commands[0]
    assert "/32" not in fake.commands[0]


def test_is_hostname_classifies_correctly():
    """FQDN detection decides whether an entry may be rewritten at all."""
    from mcp_mikrotik.scope.firewall.address_list import _is_hostname

    assert _is_hostname("one.one.one.one")
    assert _is_hostname("example.com")
    assert not _is_hostname("203.0.113.9")
    assert not _is_hostname("203.0.113.0/24")
    assert not _is_hostname("2001:db8::5")
    assert not _is_hostname("2001:db8:1::/64")


def test_hostname_is_passed_through_unchanged(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_get_address_list_entry(ctx, family="ipv6", list_name="l",
                                           address="www.example.com"))
    assert 'address="www.example.com"' in fake.commands[0]


# ---------------------------------------------------------------------------
# list names are exact — a trailing space is significant
# ---------------------------------------------------------------------------

def test_trailing_space_in_list_name_is_preserved(ctx, monkeypatch):
    """A real device had a list named "Axigen internal NS " with a trailing
    space; stripping it silently targets a different (nonexistent) list."""
    from mcp_mikrotik.scope.firewall import address_list as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_create_address_list_entry(
        ctx, family="ipv4", list_name="trailing space ", address="203.0.113.1"))
    assert 'list="trailing space "' in fake.commands[0]


def test_list_filter_keeps_the_exact_name(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_list_address_list_entries(ctx, family="ipv4", list_filter="  padded  "))
    assert 'list="  padded  "' in fake.commands[0]


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------

def test_create_minimal(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_create_address_list_entry(
        ctx, family="ipv4", list_name="trusted", address="203.0.113.0/24"))
    assert fake.commands[0] == (
        '/ip firewall address-list add list="trusted" address=203.0.113.0/24')


def test_create_all_options(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_create_address_list_entry(
        ctx, family="ipv6", list_name="l", address="2001:db8::1",
        comment="note", timeout="1h", disabled=True))
    cmd = fake.commands[0]
    assert 'comment="note"' in cmd
    assert "timeout=1h" in cmd
    assert "disabled=yes" in cmd


def test_create_rejection_is_not_reported_as_success(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    async def refuses(command, _ctx, device=None):
        return "no such item (4)"

    monkeypatch.setattr(m, "execute_mikrotik_command", refuses, raising=True)

    out = _run(m.mikrotik_create_address_list_entry(
        ctx, family="ipv4", list_name="l", address="203.0.113.1"))
    assert out.startswith("Failed to create address list entry:")


# ---------------------------------------------------------------------------
# list filters
# ---------------------------------------------------------------------------

def test_static_only_excludes_dynamic_children(ctx, monkeypatch):
    """A hostname entry spawns dynamic children per resolved address."""
    from mcp_mikrotik.scope.firewall import address_list as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_list_address_list_entries(ctx, family="ipv4", static_only=True))
    assert "!dynamic" in fake.commands[0]


def test_dynamic_only(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_list_address_list_entries(ctx, family="ipv4", dynamic_only=True))
    cmd = fake.commands[0]
    assert cmd.endswith("dynamic") and "!dynamic" not in cmd


def test_partial_filters(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_list_address_list_entries(
        ctx, family="ipv4", address_filter="203.0", comment_filter="dns", disabled_only=True))
    cmd = fake.commands[0]
    assert 'address~"203.0"' in cmd
    assert 'comment~"dns"' in cmd
    assert "disabled=yes" in cmd


def test_list_empty_result_message(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    async def empty(command, _ctx, device=None):
        return ""

    monkeypatch.setattr(m, "execute_mikrotik_command", empty, raising=True)

    out = _run(m.mikrotik_list_address_list_entries(ctx, family="ipv4"))
    assert out == "No address list entries found matching the criteria."


# ---------------------------------------------------------------------------
# get / update / remove
# ---------------------------------------------------------------------------

def test_get_not_found_on_legend_only_output(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    async def legend(command, _ctx, device=None):
        return "Flags: X - disabled, D - dynamic"

    monkeypatch.setattr(m, "execute_mikrotik_command", legend, raising=True)

    out = _run(m.mikrotik_get_address_list_entry(
        ctx, family="ipv4", list_name="l", address="203.0.113.1"))
    assert "not found" in out


def test_update_no_fields(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    out = _run(m.mikrotik_update_address_list_entry(
        ctx, family="ipv4", list_name="l", address="203.0.113.1"))
    assert out == "No updates specified."
    assert fake.commands == []


def test_update_missing_entry_is_not_success(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    async def absent(command, _ctx, device=None):
        if "count-only" in command:
            return "0"
        return "no such item (4)"

    monkeypatch.setattr(m, "execute_mikrotik_command", absent, raising=True)

    out = _run(m.mikrotik_update_address_list_entry(
        ctx, family="ipv4", list_name="l", address="203.0.113.1", comment="x"))
    assert "not found" in out
    assert "successfully" not in out


def test_update_sets_and_clears(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_update_address_list_entry(
        ctx, family="ipv4", list_name="l", address="203.0.113.1",
        new_list_name="l2", comment="", timeout="2h"))
    cmd = _cmd(fake, " set ")
    assert 'list="l2"' in cmd
    assert 'comment=""' in cmd
    assert "timeout=2h" in cmd


def test_update_rename_looks_up_the_new_list(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_update_address_list_entry(
        ctx, family="ipv4", list_name="old", address="203.0.113.1", new_list_name="new"))
    assert 'list="new"' in fake.commands[-1]


def test_remove_missing_entry(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    async def absent(command, _ctx, device=None):
        return "0"

    monkeypatch.setattr(m, "execute_mikrotik_command", absent, raising=True)

    out = _run(m.mikrotik_remove_address_list_entry(
        ctx, family="ipv4", list_name="l", address="203.0.113.1"))
    assert "not found" in out


def test_remove_existing_entry(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_remove_address_list_entry(
        ctx, family="ipv4", list_name="l", address="203.0.113.1"))
    assert _cmd(fake, " remove ") == (
        '/ip firewall address-list remove [find list="l" address="203.0.113.1"]')
    # and the outcome is confirmed afterwards, not assumed
    assert fake.commands[-1].startswith("/ip firewall address-list print count-only")


def test_enable_and_disable_wrappers(ctx, monkeypatch):
    """Must not repeat the positional-ctx bug tracked in #108."""
    from mcp_mikrotik.scope.firewall import address_list as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_disable_address_list_entry(
        ctx, family="ipv4", list_name="l", address="203.0.113.1"))
    assert "disabled=yes" in _cmd(fake, " set ")

    fake.commands.clear()
    _run(m.mikrotik_enable_address_list_entry(
        ctx, family="ipv4", list_name="l", address="203.0.113.1"))
    assert "disabled=no" in _cmd(fake, " set ")


def test_device_argument_is_forwarded(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_list_address_list_entries(ctx, family="ipv4", device="RouterB"))
    assert fake.devices == ["RouterB"]


def test_fqdn_survives_ipv6_canonicalisation_on_create(ctx, monkeypatch):
    """An FQDN is a real entry type — it must not gain a /128."""
    from mcp_mikrotik.scope.firewall import address_list as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_create_address_list_entry(
        ctx, family="ipv6", list_name="l", address="one.one.one.one"))
    assert "address=one.one.one.one" in fake.commands[0]
    assert "/128" not in fake.commands[0]


# ---------------------------------------------------------------------------
# review follow-ups: a refused write must not be reported as success
# ---------------------------------------------------------------------------

def test_update_rejects_a_refusal_that_says_neither_failure_nor_error(ctx, monkeypatch):
    """A read-only account answers "not enough permissions (9)"."""
    from mcp_mikrotik.scope.firewall import address_list as m

    async def refused(command, _ctx, device=None):
        if "count-only" in command:
            return "1"
        if " set " in command:
            return "not enough permissions (9)"
        return "Flags: X - disabled, D - dynamic\n 0 ;;; BEFORE\n  address=203.0.113.1"

    monkeypatch.setattr(m, "execute_mikrotik_command", refused, raising=True)

    out = _run(m.mikrotik_update_address_list_entry(
        ctx, family="ipv4", list_name="l", address="203.0.113.1", comment="AFTER"))
    assert out.startswith("Failed to update address list entry:")
    assert "updated successfully" not in out


def test_update_rejects_a_silent_no_op(ctx, monkeypatch):
    """Silent set, but the new value never lands — assert it, do not assume."""
    from mcp_mikrotik.scope.firewall import address_list as m

    async def silent_noop(command, _ctx, device=None):
        if "count-only" in command:
            # entry exists, but not with the asserted comment
            return "0" if 'comment="AFTER"' in command else "1"
        if " set " in command:
            return ""
        return "address=203.0.113.1"

    monkeypatch.setattr(m, "execute_mikrotik_command", silent_noop, raising=True)

    out = _run(m.mikrotik_update_address_list_entry(
        ctx, family="ipv4", list_name="l", address="203.0.113.1", comment="AFTER"))
    assert out.startswith("Failed to update address list entry:")
    assert "not present" in out


def test_disable_inherits_the_update_guard(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    async def refused(command, _ctx, device=None):
        if "count-only" in command:
            return "1"
        if " set " in command:
            return "not enough permissions (9)"
        return "address=203.0.113.1"

    monkeypatch.setattr(m, "execute_mikrotik_command", refused, raising=True)

    out = _run(m.mikrotik_disable_address_list_entry(
        ctx, family="ipv4", list_name="l", address="203.0.113.1"))
    assert out.startswith("Failed to update address list entry:")
    assert "successfully" not in out


def test_remove_rejects_a_refusal_that_says_neither_failure_nor_error(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    async def refused(command, _ctx, device=None):
        if "count-only" in command:
            return "1"
        return "not enough permissions (9)"

    monkeypatch.setattr(m, "execute_mikrotik_command", refused, raising=True)

    out = _run(m.mikrotik_remove_address_list_entry(
        ctx, family="ipv4", list_name="l", address="203.0.113.1"))
    assert out.startswith("Failed to remove address list entry:")
    assert "removed from" not in out


def test_remove_requires_the_entry_to_be_gone(ctx, monkeypatch):
    """Silent remove, entry still there — a false success on a firewall list."""
    from mcp_mikrotik.scope.firewall import address_list as m

    async def still_there(command, _ctx, device=None):
        if "count-only" in command:
            return "1"
        return ""

    monkeypatch.setattr(m, "execute_mikrotik_command", still_there, raising=True)

    out = _run(m.mikrotik_remove_address_list_entry(
        ctx, family="ipv4", list_name="l", address="203.0.113.1"))
    assert out.startswith("Failed to remove address list entry:")
    assert "still present" in out


def test_timeout_is_cleared_with_zero_not_an_unset_flag(ctx, monkeypatch):
    """This menu rejects "!timeout"; the empty value for a duration is 0."""
    from mcp_mikrotik.scope.firewall import address_list as m

    fake = FakeExecutor()
    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    _run(m.mikrotik_update_address_list_entry(
        ctx, family="ipv4", list_name="l", address="203.0.113.1", timeout=""))
    cmd = _cmd(fake, " set ")
    assert "timeout=0" in cmd
    assert "!timeout" not in cmd


# ---------------------------------------------------------------------------
# success paths — FakeExecutor's generic print output never contains
# "address=", so these need an executor that answers like a real device
# ---------------------------------------------------------------------------

DETAIL = (
    "Flags: X - disabled, D - dynamic \n"
    " 0   ;;; note\n"
    "     list=trusted address=203.0.113.0/24 creation-time=2026-09-21 12:00:00 \n"
    "     dynamic=no"
)


def _device(detail=DETAIL, count="1", after_remove="0", write=""):
    """Executor that answers the way RouterOS does on the happy path."""
    state = {"removed": False}

    async def run(command, _ctx, device=None):
        if "count-only" in command:
            return after_remove if state["removed"] else count
        if command.startswith(("/ip firewall address-list remove",
                               "/ipv6 firewall address-list remove")):
            state["removed"] = True
            return write
        if " add " in command or " set " in command:
            return write
        return detail

    return run


def test_create_success_response(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    monkeypatch.setattr(m, "execute_mikrotik_command", _device(), raising=True)

    out = _run(m.mikrotik_create_address_list_entry(
        ctx, family="ipv4", list_name="trusted", address="203.0.113.0/24"))
    assert out.startswith("Address list entry created successfully:")
    assert "list=trusted" in out


def test_create_falls_back_when_the_entry_cannot_be_read_back(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    monkeypatch.setattr(m, "execute_mikrotik_command",
                        _device(detail="Flags: X - disabled, D - dynamic"), raising=True)

    out = _run(m.mikrotik_create_address_list_entry(
        ctx, family="ipv4", list_name="trusted", address="203.0.113.0/24"))
    assert out == "Address list entry '203.0.113.0/24' added to 'trusted'."


def test_get_success_response(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    monkeypatch.setattr(m, "execute_mikrotik_command", _device(), raising=True)

    out = _run(m.mikrotik_get_address_list_entry(
        ctx, family="ipv4", list_name="trusted", address="203.0.113.0/24"))
    assert out.startswith("IPV4 ADDRESS LIST ENTRY:")
    assert "list=trusted" in out


def test_get_success_response_names_the_ipv6_family(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    monkeypatch.setattr(m, "execute_mikrotik_command", _device(), raising=True)

    out = _run(m.mikrotik_get_address_list_entry(
        ctx, family="ipv6", list_name="trusted", address="2001:db8::5"))
    assert out.startswith("IPV6 ADDRESS LIST ENTRY:")


def test_update_success_response(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    monkeypatch.setattr(m, "execute_mikrotik_command", _device(), raising=True)

    out = _run(m.mikrotik_update_address_list_entry(
        ctx, family="ipv4", list_name="trusted", address="203.0.113.0/24", comment="note"))
    assert out.startswith("Address list entry updated successfully:")
    assert "list=trusted" in out


def test_enable_success_response(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    monkeypatch.setattr(m, "execute_mikrotik_command", _device(), raising=True)

    out = _run(m.mikrotik_enable_address_list_entry(
        ctx, family="ipv4", list_name="trusted", address="203.0.113.0/24"))
    assert out.startswith("Address list entry updated successfully:")


def test_remove_success_response(ctx, monkeypatch):
    """Present before the remove, absent after — the post-check must pass."""
    from mcp_mikrotik.scope.firewall import address_list as m

    monkeypatch.setattr(m, "execute_mikrotik_command", _device(), raising=True)

    out = _run(m.mikrotik_remove_address_list_entry(
        ctx, family="ipv4", list_name="trusted", address="203.0.113.0/24"))
    assert out == "Address list entry '203.0.113.0/24' removed from 'trusted'."


def test_list_success_response_labels_the_family(ctx, monkeypatch):
    from mcp_mikrotik.scope.firewall import address_list as m

    monkeypatch.setattr(m, "execute_mikrotik_command", _device(), raising=True)

    assert _run(m.mikrotik_list_address_list_entries(ctx, family="ipv4")).startswith(
        "IPV4 ADDRESS LIST ENTRIES:")
    assert _run(m.mikrotik_list_address_list_entries(ctx, family="ipv6")).startswith(
        "IPV6 ADDRESS LIST ENTRIES:")
