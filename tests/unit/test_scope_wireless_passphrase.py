"""Tests for set_wireless_passphrase (issue #107).

These pin the two review findings: a refused write must not be reported as
success, and a passphrase containing characters WPA allows must survive into
the command intact.
"""

import asyncio

import pytest


def _run(coro):
    return asyncio.run(coro)


class FakeWifi:
    """Executor double: v7 wifi detected, one interface, scripted set result."""

    def __init__(self, set_result=""):
        self.set_result = set_result
        self.commands = []

    async def __call__(self, command, _ctx, device=None, redact=None):
        self.commands.append(command)
        if "print count-only" in command:
            return "1"
        if " set " in command:
            return self.set_result
        return ""

    @property
    def set_command(self):
        return next(c for c in self.commands if " set " in c)


def _patch(monkeypatch, fake):
    from mcp_mikrotik.scope import wireless as m

    monkeypatch.setattr(m, "execute_mikrotik_command", fake, raising=True)

    async def _detect(ctx, device=None):
        return "/interface wifi"

    monkeypatch.setattr(m, "mikrotik_detect_wireless_interface_type", _detect, raising=True)
    return m


# ---------------------------------------------------------------------------
# a refused write must not be reported as success
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("refusal", [
    "not enough permissions (9)",          # read-only account
    "expected end of command (line 1)",    # malformed command
    "syntax error (line 1 column 12)",
    "no such item",
])
def test_refused_write_is_reported_as_failure(ctx, monkeypatch, refusal):
    """RouterOS prints nothing on success, so any output means it did not happen."""
    fake = FakeWifi(set_result=refusal)
    m = _patch(monkeypatch, fake)

    out = _run(m.mikrotik_set_wireless_passphrase(
        ctx, name="wifi1", passphrase="correct-horse", device="RouterA"))

    assert out.startswith("Failed to set wireless passphrase"), out
    assert "successfully" not in out


def test_empty_output_is_success(ctx, monkeypatch):
    fake = FakeWifi(set_result="")
    m = _patch(monkeypatch, fake)

    out = _run(m.mikrotik_set_wireless_passphrase(
        ctx, name="wifi1", passphrase="correct-horse", device="RouterA"))

    assert "updated successfully" in out


def test_failure_never_echoes_the_passphrase(ctx, monkeypatch):
    secret = "hunter2-hunter2"
    fake = FakeWifi(set_result=f'bad value "{secret}"')
    m = _patch(monkeypatch, fake)

    out = _run(m.mikrotik_set_wireless_passphrase(
        ctx, name="wifi1", passphrase=secret, device="RouterA"))

    assert secret not in out
    assert "***" in out


# ---------------------------------------------------------------------------
# values WPA allows must survive into the command
# ---------------------------------------------------------------------------

def test_passphrase_with_a_quote_is_escaped(ctx, monkeypatch):
    """A bare quote would end the string early and the write would be lost."""
    fake = FakeWifi()
    m = _patch(monkeypatch, fake)

    _run(m.mikrotik_set_wireless_passphrase(
        ctx, name="wifi1", passphrase='abc"def123', device="RouterA"))

    assert 'security.passphrase="abc\\"def123"' in fake.set_command


def test_passphrase_with_a_backslash_is_escaped(ctx, monkeypatch):
    fake = FakeWifi()
    m = _patch(monkeypatch, fake)

    _run(m.mikrotik_set_wireless_passphrase(
        ctx, name="wifi1", passphrase="abc\\def123", device="RouterA"))

    assert 'security.passphrase="abc\\\\def123"' in fake.set_command


def test_interface_name_is_escaped_too(ctx, monkeypatch):
    fake = FakeWifi()
    m = _patch(monkeypatch, fake)

    _run(m.mikrotik_set_wireless_passphrase(
        ctx, name='we"ird', passphrase="correct-horse", device="RouterA"))

    assert '[find name="we\\"ird"]' in fake.set_command


# ---------------------------------------------------------------------------
# WPA-PSK length is enforced before anything is sent
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad", ["short", "x" * 64])
def test_out_of_range_passphrase_is_rejected_without_touching_the_device(ctx, monkeypatch, bad):
    fake = FakeWifi()
    m = _patch(monkeypatch, fake)

    out = _run(m.mikrotik_set_wireless_passphrase(
        ctx, name="wifi1", passphrase=bad, device="RouterA"))

    assert "8-63 characters" in out
    assert fake.commands == [], "nothing may be sent for an invalid passphrase"


def test_device_argument_is_forwarded(ctx, monkeypatch):
    fake = FakeWifi()
    m = _patch(monkeypatch, fake)

    async def _detect(ctx, device=None):
        assert device == "RouterB"
        return "/interface wifi"

    monkeypatch.setattr(m, "mikrotik_detect_wireless_interface_type", _detect, raising=True)
    _run(m.mikrotik_set_wireless_passphrase(
        ctx, name="wifi1", passphrase="correct-horse", device="RouterB"))

    assert fake.commands, "no command reached the executor"
