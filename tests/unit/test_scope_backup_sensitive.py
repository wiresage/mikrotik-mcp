import asyncio

from mcp_mikrotik.config import MikrotikConfig


def test_create_export_cannot_show_sensitive_in_sensitive_hiding_mode(ctx, monkeypatch):
    from mcp_mikrotik import config
    from mcp_mikrotik.scope.system import backup

    commands = []

    async def execute(command, _ctx, device=None):
        commands.append(command)
        return "" if len(commands) == 1 else "file details"

    monkeypatch.setattr(config, "mikrotik_config", MikrotikConfig(sensitive_hiding=True))
    monkeypatch.setattr(backup, "execute_mikrotik_command", execute)
    asyncio.run(backup.mikrotik_create_export(ctx, name="safe", hide_sensitive=False))

    assert "show-sensitive" not in commands[0]


def test_export_section_cannot_show_sensitive_in_sensitive_hiding_mode(ctx, monkeypatch):
    from mcp_mikrotik import config
    from mcp_mikrotik.scope.system import backup

    commands = []

    async def execute(command, _ctx, device=None):
        commands.append(command)
        return "configuration"

    monkeypatch.setattr(config, "mikrotik_config", MikrotikConfig(sensitive_hiding=True))
    monkeypatch.setattr(backup, "execute_mikrotik_command", execute)
    asyncio.run(backup.mikrotik_export_section(ctx, section="ip address", hide_sensitive=False))

    assert commands == ["/ip address export"]


def test_export_section_can_show_sensitive_when_mode_is_disabled(ctx, monkeypatch):
    from mcp_mikrotik import config
    from mcp_mikrotik.scope.system import backup

    commands = []

    async def execute(command, _ctx, device=None):
        commands.append(command)
        return "configuration"

    monkeypatch.setattr(config, "mikrotik_config", MikrotikConfig())
    monkeypatch.setattr(backup, "execute_mikrotik_command", execute)
    asyncio.run(backup.mikrotik_export_section(ctx, section="ip address", hide_sensitive=False))

    assert commands == ["/ip address export show-sensitive"]
