import asyncio
import pytest
from unittest.mock import AsyncMock


def _run(coro):
    return asyncio.run(coro)


class FakeExecutor:
    def __init__(self, responses=None):
        self.commands = []
        self.devices = []
        self.responses = responses or {}
        self.default_response = ""

    async def __call__(self, command, ctx, device=None, **kwargs):
        self.commands.append(command)
        self.devices.append(device)
        for pattern, resp in self.responses.items():
            if pattern in command:
                return resp
        return self.default_response


@pytest.fixture
def ctx():
    class DummyContext:
        info = AsyncMock()
        warning = AsyncMock()
        error = AsyncMock()
    return DummyContext()


def test_scheduler_crud(ctx, monkeypatch):
    from mcp_mikrotik.scope import scheduler

    fake = FakeExecutor({
        "/system scheduler print detail where name=\"backup-task\"": " 0   name=\"backup-task\" interval=1d next-run=nov/05/2026 on-event=\"do-backup\"\n",
        "/system scheduler add": "",
        "/system scheduler set": "",
        "/system scheduler enable": "",
        "/system scheduler disable": "",
        "/system scheduler remove": "",
    })
    monkeypatch.setattr(scheduler, "execute_mikrotik_command", fake, raising=True)

    # 1. Get scheduler
    res_get = _run(scheduler.mikrotik_get_scheduler(ctx, name="backup-task", device="r1"))
    assert "SCHEDULER DETAILS (backup-task):" in res_get
    assert 'name="backup-task"' in res_get
    assert fake.devices[-1] == "r1"

    # Get not found
    res_not_found = _run(scheduler.mikrotik_get_scheduler(ctx, name="unknown-task"))
    assert "Scheduler 'unknown-task' not found." in res_not_found

    # 2. Create scheduler
    res_create = _run(scheduler.mikrotik_create_scheduler(
        ctx,
        name="daily-backup",
        on_event="/system script run backup",
        interval="1d",
        start_time="03:00:00",
        comment="Nightly backup",
        disabled=True
    ))
    assert "created successfully" in res_create
    assert '/system scheduler add name="daily-backup"' in fake.commands[-1]
    assert 'on-event="/system script run backup"' in fake.commands[-1]
    assert 'interval="1d"' in fake.commands[-1]
    assert 'start-time="03:00:00"' in fake.commands[-1]
    assert 'comment="Nightly backup"' in fake.commands[-1]
    assert "disabled=yes" in fake.commands[-1]

    # 3. Update scheduler
    res_upd = _run(scheduler.mikrotik_update_scheduler(
        ctx,
        name="daily-backup",
        interval="12h",
        disabled=False
    ))
    assert "updated successfully" in res_upd
    assert '/system scheduler set [find name="daily-backup"]' in fake.commands[-1]
    assert 'interval="12h"' in fake.commands[-1]
    assert "disabled=no" in fake.commands[-1]

    # Update with no changes
    assert "No updates specified." in _run(scheduler.mikrotik_update_scheduler(ctx, name="daily-backup"))

    # 4. Enable / Disable
    res_en = _run(scheduler.mikrotik_enable_scheduler(ctx, name="daily-backup"))
    assert "enabled successfully" in res_en
    assert '/system scheduler enable [find name="daily-backup"]' in fake.commands[-1]

    res_dis = _run(scheduler.mikrotik_disable_scheduler(ctx, name="daily-backup"))
    assert "disabled successfully" in res_dis
    assert '/system scheduler disable [find name="daily-backup"]' in fake.commands[-1]

    # 5. Remove
    res_rem = _run(scheduler.mikrotik_remove_scheduler(ctx, name="daily-backup"))
    assert "removed successfully" in res_rem
    assert '/system scheduler remove [find name="daily-backup"]' in fake.commands[-1]


def test_script_crud_and_execution(ctx, monkeypatch):
    from mcp_mikrotik.scope import scheduler

    fake = FakeExecutor({
        "/system script print detail where name=\"my-script\"": " 0   name=\"my-script\" owner=\"admin\" run-count=5 source=\":put hello\"\n",
        "/system script run": "hello world\n",
        "/system script add": "",
        "/system script set": "",
        "/system script remove": "",
    })
    monkeypatch.setattr(scheduler, "execute_mikrotik_command", fake, raising=True)

    # 1. Get script
    res_get = _run(scheduler.mikrotik_get_script(ctx, name="my-script", device="r1"))
    assert "SCRIPT DETAILS (my-script):" in res_get
    assert 'name="my-script"' in res_get
    assert fake.devices[-1] == "r1"

    # Get not found
    assert "Script 'nonexistent' not found." in _run(scheduler.mikrotik_get_script(ctx, name="nonexistent"))

    # 2. Run script with output
    res_run = _run(scheduler.mikrotik_run_script(ctx, name="my-script"))
    assert "SCRIPT OUTPUT (my-script):" in res_run
    assert "hello world" in res_run
    assert '/system script run [find name="my-script"]' in fake.commands[-1]

    # Run script silent
    fake.responses["/system script run"] = "\n"
    res_silent = _run(scheduler.mikrotik_run_script(ctx, name="my-script"))
    assert "Script 'my-script' executed successfully." in res_silent

    # 3. Create script
    res_create = _run(scheduler.mikrotik_create_script(
        ctx,
        name="new-task",
        source=":log info \"Running\"",
        policy="read,write,test",
        dont_require_permissions=True,
        comment="Test script"
    ))
    assert "created successfully" in res_create
    assert '/system script add name="new-task"' in fake.commands[-1]
    assert 'source=":log info \\"Running\\""' in fake.commands[-1]
    assert 'policy="read,write,test"' in fake.commands[-1]
    assert "dont-require-permissions=yes" in fake.commands[-1]

    # 4. Update script
    res_upd = _run(scheduler.mikrotik_update_script(
        ctx,
        name="new-task",
        source=":log info \"Updated\"",
        comment="Updated comment"
    ))
    assert "updated successfully" in res_upd
    assert '/system script set [find name="new-task"]' in fake.commands[-1]
    assert 'source=":log info \\"Updated\\""' in fake.commands[-1]

    assert "No updates specified." in _run(scheduler.mikrotik_update_script(ctx, name="new-task"))

    # 5. Remove script
    res_rem = _run(scheduler.mikrotik_remove_script(ctx, name="new-task"))
    assert "removed successfully" in res_rem
    assert '/system script remove [find name="new-task"]' in fake.commands[-1]


def test_script_jobs_and_environment(ctx, monkeypatch):
    from mcp_mikrotik.scope import scheduler

    fake = FakeExecutor({
        "/system script job print detail": " 0   owner=\"admin\" started=2026-11-04 20:00:00\n",
        "/system script job remove": "",
        "/system script environment print detail": " 0   name=\"myVar\" value=\"123\"\n",
        "/system script environment remove": "",
    })
    monkeypatch.setattr(scheduler, "execute_mikrotik_command", fake, raising=True)

    # 1. Script Jobs
    res_jobs = _run(scheduler.mikrotik_list_script_jobs(ctx))
    assert "SCRIPT JOBS:" in res_jobs
    assert 'owner="admin"' in res_jobs

    res_rem_job = _run(scheduler.mikrotik_remove_script_job(ctx, job_id="*1"))
    assert "Script job '*1' stopped and removed successfully." in res_rem_job
    assert "/system script job remove *1" in fake.commands[-1]

    assert "Invalid script job ID:" in _run(scheduler.mikrotik_remove_script_job(ctx, job_id="invalid;;;"))

    # 2. Script Environment
    res_env = _run(scheduler.mikrotik_list_script_environment(ctx))
    assert "SCRIPT ENVIRONMENT:" in res_env
    assert 'name="myVar"' in res_env

    res_rem_env = _run(scheduler.mikrotik_remove_script_environment(ctx, name="myVar"))
    assert "Script environment variable 'myVar' removed successfully." in res_rem_env
    assert '/system script environment remove [find name="myVar"]' in fake.commands[-1]


def test_invalid_names_are_rejected(ctx):
    from mcp_mikrotik.scope import scheduler

    assert "Invalid script name" in _run(scheduler.mikrotik_get_script(ctx, name="bad name with spaces!"))
    assert "Invalid scheduler name" in _run(scheduler.mikrotik_get_scheduler(ctx, name="bad;name"))
    assert "Invalid variable name" in _run(scheduler.mikrotik_remove_script_environment(ctx, name="bad;var"))
