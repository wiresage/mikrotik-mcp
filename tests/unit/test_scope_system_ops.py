import asyncio

from tests.conftest import FakeExecutor


def _run(coro):
    return asyncio.run(coro)


class Canned(FakeExecutor):
    """Returns a payload carrying every marker the system tools look for."""

    PAYLOAD = (
        "uptime: 2w6d  version: 7.24.4  time: 15:00:06  model: RB1100Dx4  "
        'name="thing" installed-version: 7.24.4 '
    )

    async def __call__(self, command, _ctx, device=None):
        result = await super().__call__(command, _ctx, device)
        return self.PAYLOAD + result if "print" in command.lower() else result


class Empty(FakeExecutor):
    async def __call__(self, command, _ctx, device=None):
        await super().__call__(command, _ctx, device)
        return ""


def test_system_commands_and_device(ctx, monkeypatch):
    from mcp_mikrotik.scope import system

    fake = Canned()
    monkeypatch.setattr(system, "execute_mikrotik_command", fake, raising=True)

    _run(system.mikrotik_get_system_resource(ctx, device="edge"))
    _run(system.mikrotik_get_system_clock(ctx))
    _run(system.mikrotik_get_system_routerboard(ctx))
    _run(system.mikrotik_get_system_package_update(ctx))
    _run(system.mikrotik_list_system_packages(ctx))
    _run(system.mikrotik_get_system_health(ctx))

    assert fake.commands == [
        "/system resource print",
        "/system clock print",
        "/system routerboard print",
        "/system package update print",
        "/system package print",
        "/system health print",
    ]
    assert fake.devices[0] == "edge"


def test_health_absence_is_explained_not_reported_as_failure(ctx, monkeypatch):
    """Most boards carry no sensors; an empty answer is not an error."""
    from mcp_mikrotik.scope import system

    monkeypatch.setattr(system, "execute_mikrotik_command", Empty(), raising=True)
    out = _run(system.mikrotik_get_system_health(ctx))
    assert "not an error" in out


def test_scripts_withhold_source_by_default(ctx, monkeypatch):
    from mcp_mikrotik.scope import scheduler

    fake = Canned()
    monkeypatch.setattr(scheduler, "execute_mikrotik_command", fake, raising=True)

    out = _run(scheduler.mikrotik_list_scripts(ctx))
    assert "proplist=" in fake.commands[-1]
    assert "source" not in fake.commands[-1]
    assert out.startswith("SCRIPTS (metadata only)")

    out = _run(scheduler.mikrotik_list_scripts(ctx, include_source=True))
    assert fake.commands[-1] == "/system script print detail"
    assert out.startswith("SCRIPTS (with source)")

    _run(scheduler.mikrotik_list_scripts(ctx, name_filter="backup", include_source=True))
    assert fake.commands[-1] == '/system script print detail where name~"backup"'


def test_script_and_scheduler_output_is_redacted(ctx, monkeypatch):
    """A credential left in a script body must not come back in clear text."""
    from mcp_mikrotik.scope import scheduler

    class WithSecret(FakeExecutor):
        async def __call__(self, command, _ctx, device=None):
            await super().__call__(command, _ctx, device)
            return 'name="backup" source=":put [/tool fetch password=\\"hunter2\\"]"\n'

    monkeypatch.setattr(scheduler, "execute_mikrotik_command", WithSecret(), raising=True)

    out = _run(scheduler.mikrotik_list_scripts(ctx, include_source=True))
    assert "hunter2" not in out
    assert 'name="backup"' in out

    out = _run(scheduler.mikrotik_list_schedulers(ctx))
    assert "hunter2" not in out


def test_services_command_and_filters(ctx, monkeypatch):
    from mcp_mikrotik.scope import services

    fake = Canned()
    monkeypatch.setattr(services, "execute_mikrotik_command", fake, raising=True)

    out = _run(services.mikrotik_list_ip_services(ctx, device="edge"))
    assert fake.commands == ["/ip service print detail"]
    assert out.startswith("IP SERVICES:")

    _run(services.mikrotik_list_ip_services(ctx, name_filter="winbox", enabled_only=True))
    assert fake.commands[-1] == '/ip service print detail where name~"winbox" disabled=no'


def test_new_tools_are_all_read_only(ctx):
    from mcp_mikrotik.scope import netwatch, scheduler, services, system  # noqa: F401
    from mcp_mikrotik.app import mcp

    names = {
        "list_netwatch", "get_system_resource", "get_system_health",
        "get_system_clock", "get_system_routerboard", "list_system_packages",
        "get_system_package_update", "list_schedulers", "list_scripts",
        "list_ip_services",
    }
    tools = {t.name: t for t in _run(mcp.list_tools()) if t.name in names}
    assert set(tools) == names, f"missing: {names - set(tools)}"
    for name, tool in tools.items():
        assert tool.annotations.read_only_hint is True, name
