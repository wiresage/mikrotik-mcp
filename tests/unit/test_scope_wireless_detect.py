"""Tests for wireless menu detection (issue #226)."""

import asyncio

import pytest

from mcp_mikrotik.scope import wireless as m


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
