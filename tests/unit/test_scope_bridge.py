"""Unit tests for the bridge VLAN table and bridge-port PVID tools (issue #105).

RouterOS prints nothing for a successful set/remove and a set through a
[find] that matches nothing is silent too, so every write here is confirmed
rather than assumed. These tests pin that behaviour, observed on 7.21.4.
"""

import asyncio

import pytest

from tests.conftest import FakeExecutor


def _run(coro):
    return asyncio.run(coro)


def _patch(monkeypatch, fn):
    from mcp_mikrotik.scope import bridge

    monkeypatch.setattr(bridge, "execute_mikrotik_command", fn, raising=True)
    return bridge


def _scripted(count="1", on_write="", on_put="*4", after_count=None):
    """An executor whose answers depend on the kind of command.

    count:       what `print count-only` returns before the write
    after_count: what it returns once a write has been sent (defaults to count)
    on_write:    output of set/remove (empty means success)
    on_put:      output of `:put [add ...]` (the new *id on success)
    """
    sent = []
    wrote = []

    async def run(command, _ctx, device=None):
        sent.append(command)
        if command.startswith(":put"):
            return on_put
        if "count-only" in command:
            return after_count if (wrote and after_count is not None) else count
        if " set " in command or " remove " in command:
            wrote.append(command)
            return on_write
        return "Flags: X - disabled, D - dynamic\n 0 bridge=br1 vlan-ids=10"

    run.sent = sent
    return run


# ---------------------------------------------------------------------------
# vlan_ids validation: the value lands in where/find clauses
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", ["10", "4094", "20,30", "100-199", "10,20,100-199"])
def test_valid_vlan_ids_are_accepted(ctx, monkeypatch, value):
    fake = FakeExecutor()
    b = _patch(monkeypatch, fake)

    _run(b.mikrotik_list_bridge_vlans(ctx, vlan_ids_filter=value))
    assert f"vlan-ids={value}" in fake.commands[0]


@pytest.mark.parametrize("value", ["10 disabled=no", "10;", "ten", "10,", "-5", "12345", ""])
def test_malformed_vlan_ids_never_reach_the_device(ctx, monkeypatch, value):
    """Unchecked, "10 disabled=no" widened a remove's [find] to another entry."""
    fake = FakeExecutor()
    b = _patch(monkeypatch, fake)

    out = _run(b.mikrotik_remove_bridge_vlan(ctx, bridge="br1", vlan_ids=value))
    assert out.startswith("Error: invalid vlan_ids")
    assert fake.commands == []


def test_new_vlan_ids_is_validated_too(ctx, monkeypatch):
    fake = FakeExecutor()
    b = _patch(monkeypatch, fake)

    out = _run(b.mikrotik_update_bridge_vlan(ctx, bridge="br1", vlan_ids="10", new_vlan_ids="11 x=1"))
    assert out.startswith("Error: invalid vlan_ids")
    assert fake.commands == []


# ---------------------------------------------------------------------------
# add_bridge_vlan
# ---------------------------------------------------------------------------

def test_add_echoes_the_new_id_and_prints_that_entry(ctx, monkeypatch):
    run = _scripted(on_put="*1F")
    b = _patch(monkeypatch, run)

    out = _run(b.mikrotik_add_bridge_vlan(ctx, bridge="br1", vlan_ids="10", tagged="ether2,ether3"))
    assert run.sent[0] == ':put [/interface bridge vlan add bridge="br1" vlan-ids=10 tagged="ether2,ether3"]'
    assert run.sent[1] == "/interface bridge vlan print detail where .id=*1F"
    assert out.startswith("Bridge VLAN entry added successfully")


@pytest.mark.parametrize("refusal", [
    "not enough permissions (9) (/interface/bridge/vlan/add; line 1)",
    "failure: vlan already added (/interface/bridge/vlan/add; line 1)",
    "invalid value for argument interface",
])
def test_add_reports_any_refusal(ctx, monkeypatch, refusal):
    run = _scripted(on_put=refusal)
    b = _patch(monkeypatch, run)

    out = _run(b.mikrotik_add_bridge_vlan(ctx, bridge="br1", vlan_ids="10", tagged="ether2"))
    assert out == f"Failed to add bridge VLAN entry: {refusal}"
    assert len(run.sent) == 1


# ---------------------------------------------------------------------------
# update_bridge_vlan
# ---------------------------------------------------------------------------

def test_update_of_a_missing_entry_is_not_found_and_sends_no_set(ctx, monkeypatch):
    """A set through a [find] that matches nothing is silent on RouterOS."""
    run = _scripted(count="0")
    b = _patch(monkeypatch, run)

    out = _run(b.mikrotik_update_bridge_vlan(ctx, bridge="br1", vlan_ids="77", comment="x"))
    assert "not found" in out
    assert not any(" set " in c for c in run.sent)


def test_update_reports_a_refusal(ctx, monkeypatch):
    run = _scripted(on_write="not enough permissions (9)")
    b = _patch(monkeypatch, run)

    out = _run(b.mikrotik_update_bridge_vlan(ctx, bridge="br1", vlan_ids="10", disabled=True))
    assert out == "Failed to update bridge VLAN entry: not enough permissions (9)"


def test_update_rejects_a_silent_no_op(ctx, monkeypatch):
    run = _scripted(count="1", after_count="0")
    b = _patch(monkeypatch, run)

    out = _run(b.mikrotik_update_bridge_vlan(ctx, bridge="br1", vlan_ids="10", comment="AFTER"))
    assert out.startswith("Failed to update bridge VLAN entry: the device reported no error")


def test_update_asserts_scalars_and_the_new_vlan_ids(ctx, monkeypatch):
    run = _scripted()
    b = _patch(monkeypatch, run)

    out = _run(b.mikrotik_update_bridge_vlan(
        ctx, bridge="br1", vlan_ids="100-199", new_vlan_ids="200-299",
        comment="range", disabled=False, tagged="ether2"))
    assert out.startswith("Bridge VLAN entry updated successfully")
    set_cmd = next(c for c in run.sent if " set " in c)
    assert set_cmd == (
        '/interface bridge vlan set [find bridge="br1" vlan-ids=100-199 dynamic=no] '
        'vlan-ids=200-299 tagged="ether2" comment="range" disabled=no'
    )
    check = [c for c in run.sent if "count-only" in c][-1]
    assert 'vlan-ids=200-299 dynamic=no comment="range" disabled=no' in check
    # port lists are not asserted: RouterOS may reorder them
    assert "tagged" not in check


def test_clearing_a_port_list_sends_an_empty_quoted_value(ctx, monkeypatch):
    """Unquoted, `tagged=` left the list as it was while reporting success."""
    run = _scripted()
    b = _patch(monkeypatch, run)

    _run(b.mikrotik_update_bridge_vlan(ctx, bridge="br1", vlan_ids="10", tagged=""))
    assert next(c for c in run.sent if " set " in c).endswith(' tagged=""')


def test_update_with_nothing_to_change_touches_nothing(ctx, monkeypatch):
    run = _scripted()
    b = _patch(monkeypatch, run)

    assert _run(b.mikrotik_update_bridge_vlan(ctx, bridge="br1", vlan_ids="10")) == "No updates specified."
    assert run.sent == []


# ---------------------------------------------------------------------------
# remove_bridge_vlan
# ---------------------------------------------------------------------------

def test_remove_reports_a_refusal(ctx, monkeypatch):
    run = _scripted(on_write="not enough permissions (9)")
    b = _patch(monkeypatch, run)

    out = _run(b.mikrotik_remove_bridge_vlan(ctx, bridge="br1", vlan_ids="10"))
    assert out == "Failed to remove bridge VLAN entry: not enough permissions (9)"


def test_remove_confirms_the_entry_is_gone(ctx, monkeypatch):
    run = _scripted(count="1", after_count="1")
    b = _patch(monkeypatch, run)

    out = _run(b.mikrotik_remove_bridge_vlan(ctx, bridge="br1", vlan_ids="10"))
    assert out.startswith("Failed to remove bridge VLAN entry: the device reported no error")


def test_remove_success(ctx, monkeypatch):
    run = _scripted(count="1", after_count="0")
    b = _patch(monkeypatch, run)

    out = _run(b.mikrotik_remove_bridge_vlan(ctx, bridge="br1", vlan_ids="20,30"))
    assert out == "Bridge VLAN entry bridge=br1 vlan-ids=20,30 removed successfully."
    assert '/interface bridge vlan remove [find bridge="br1" vlan-ids=20,30 dynamic=no]' in run.sent


# ---------------------------------------------------------------------------
# update_bridge_port
# ---------------------------------------------------------------------------

def test_port_update_of_a_missing_interface_sends_no_set(ctx, monkeypatch):
    run = _scripted(count="0")
    b = _patch(monkeypatch, run)

    out = _run(b.mikrotik_update_bridge_port(ctx, interface="ghost", pvid=20))
    assert out == "Bridge port for interface 'ghost' not found."
    assert not any(" set " in c for c in run.sent)


def test_port_update_reports_a_refusal(ctx, monkeypatch):
    run = _scripted(on_write="not enough permissions (9)")
    b = _patch(monkeypatch, run)

    out = _run(b.mikrotik_update_bridge_port(ctx, interface="ether2", pvid=30))
    assert out == "Failed to update bridge port: not enough permissions (9)"


def test_port_update_asserts_every_field(ctx, monkeypatch):
    run = _scripted()
    b = _patch(monkeypatch, run)

    out = _run(b.mikrotik_update_bridge_port(
        ctx, interface="ether2", pvid=10, frame_types="admit-only-vlan-tagged", ingress_filtering=True))
    assert out.startswith("Bridge port updated successfully")
    check = [c for c in run.sent if "count-only" in c][-1]
    assert check == (
        '/interface bridge port print count-only where interface="ether2" '
        "pvid=10 frame-types=admit-only-vlan-tagged ingress-filtering=yes"
    )


def test_port_update_rejects_a_silent_no_op(ctx, monkeypatch):
    run = _scripted(count="1", after_count="0")
    b = _patch(monkeypatch, run)

    out = _run(b.mikrotik_update_bridge_port(ctx, interface="ether2", pvid=10))
    assert out.startswith("Failed to update bridge port: the device reported no error")
