"""Tests for wireless menu detection (issue #226)."""

import asyncio

import pytest

from mcp_mikrotik.scope.interfaces import wireless as m


def _detect(ctx, replies):
    async def fake(command, _ctx, device=None, redact=None):
        for prefix, reply in replies.items():
            if command.startswith(prefix):
                return reply
        return "bad command name"

    return fake


def _run(ctx, monkeypatch, replies):
    monkeypatch.setattr(m, "execute_mikrotik_command", _detect(ctx, replies), raising=True)
    return asyncio.run(m.mikrotik_detect_wireless_interface_type(ctx))


def test_empty_wifi_menu_does_not_hide_legacy_wireless(ctx, monkeypatch):
    """wifi answers 0 on a legacy-wireless router; wireless has interfaces."""
    result = _run(ctx, monkeypatch, {"/interface wifi ": "0", "/interface wireless ": "3"})
    assert result == "/interface wireless"


def test_wifi_with_interfaces_still_wins(ctx, monkeypatch):
    result = _run(ctx, monkeypatch, {"/interface wifi ": "2", "/interface wireless ": "3"})
    assert result == "/interface wifi"


def test_all_empty_falls_back_to_first_supported(ctx, monkeypatch):
    result = _run(ctx, monkeypatch, {"/interface wifi ": "0", "/interface wireless ": "0"})
    assert result == "/interface wifi"


def test_unsupported_menus_are_skipped(ctx, monkeypatch):
    result = _run(ctx, monkeypatch, {"/interface wireless ": "1"})
    assert result == "/interface wireless"


def test_nothing_supported_returns_none(ctx, monkeypatch):
    assert _run(ctx, monkeypatch, {}) is None


async def _router_without_radios(command, _ctx, device=None, redact=None):
    """What a CHR on RouterOS 7.24/7.25 answers: the wifi and wifiwave2 menus exist but hold no
    interface, the legacy menus do not exist."""
    if command.startswith(("/interface wifi ", "/interface wifiwave2 ")):
        return "0" if "count-only" in command else ""
    for menu in ("wireless", "wlan"):
        if command.startswith(f"/interface {menu} "):
            return f"bad command name {menu} (line 1 column 12)\n"
    if command == "/interface print":
        return "Flags: R - RUNNING\nColumns: NAME, TYPE\n#   NAME    TYPE \n0 R ether1  ether\n"
    return ""


def test_list_and_detection_agree_on_a_router_without_radios(ctx, monkeypatch):
    """The health check of 0.30.0 saw list_wireless_interfaces say 'None detected' while
    check_wireless_support and the monitor tools named /interface wifi on the same CHR."""
    monkeypatch.setattr(m, "execute_mikrotik_command", _router_without_radios, raising=True)

    detected = asyncio.run(m.mikrotik_detect_wireless_interface_type(ctx))
    listed = asyncio.run(m.mikrotik_list_wireless_interfaces(ctx))

    assert detected == "/interface wifi"
    assert listed.startswith("No wireless interfaces found matching the criteria.")
    assert "Working interface types: /interface wifi, /interface wifiwave2\n" in listed
