"""restore_backup on RouterOS 7.

Two things were wrong, both seen on RouterOS 7.21.4:

* the command was sent without the password argument unless the caller gave one, and the router answers
  "Script Error: missing value(s) of argument(s) password" (an unencrypted backup takes an empty password);
* a successful restore answers "System configuration restored, rebooting now", but the tool only
  recognised "Restoring system configuration" and reported its own success as a failure.
"""

import asyncio

import pytest

from mcp_mikrotik.scope import backup as mod

BS = chr(92)


def run(coro):
    return asyncio.run(coro)


def router(load_reply, file_count="1"):
    seen = []

    async def execute(command, _ctx, device=None):
        seen.append(command)
        if command.startswith("/file print count-only"):
            return file_count
        if command.startswith("/system backup load"):
            return load_reply
        return ""

    execute.seen = seen
    return execute


def test_an_unencrypted_backup_is_loaded_with_an_empty_password(ctx, monkeypatch):
    execute = router("System configuration restored, rebooting now")
    monkeypatch.setattr(mod, "execute_mikrotik_command", execute)

    run(mod.mikrotik_restore_backup(ctx, "mine.backup"))

    assert execute.seen[-1] == '/system backup load name=mine.backup password=""'


def test_the_password_is_sent_and_escaped(ctx, monkeypatch):
    execute = router("System configuration restored, rebooting now")
    monkeypatch.setattr(mod, "execute_mikrotik_command", execute)

    run(mod.mikrotik_restore_backup(ctx, "mine.backup", password=f'a"b$c{BS}d'))

    assert execute.seen[-1] == f'/system backup load name=mine.backup password="a{BS}"b{BS}$c{BS}{BS}d"'


@pytest.mark.parametrize(
    "reply",
    [
        "System configuration restored, rebooting now",  # RouterOS 7.21.4
        "Restoring system configuration",  # older releases
        "",  # the connection dropped with the reboot
        "  \r\n",
    ],
)
def test_the_routers_own_success_replies_are_reported_as_success(reply, ctx, monkeypatch):
    monkeypatch.setattr(mod, "execute_mikrotik_command", router(reply))

    result = run(mod.mikrotik_restore_backup(ctx, "mine.backup"))

    assert result == "Backup 'mine.backup' restored successfully. System will reboot."


@pytest.mark.parametrize(
    "reply",
    [
        "Script Error: missing value(s) of argument(s) password",
        "failure: wrong password",
        "failure: no such file",
        "bad command name backup (line 1 column 9)",
    ],
)
def test_a_refusal_is_reported_as_a_failure(reply, ctx, monkeypatch):
    monkeypatch.setattr(mod, "execute_mikrotik_command", router(reply))

    result = run(mod.mikrotik_restore_backup(ctx, "mine.backup"))

    assert result == f"Failed to restore backup: {reply}"


def test_a_missing_file_is_not_found_and_nothing_is_loaded(ctx, monkeypatch):
    execute = router("System configuration restored, rebooting now", file_count="0")
    monkeypatch.setattr(mod, "execute_mikrotik_command", execute)

    result = run(mod.mikrotik_restore_backup(ctx, "nope.backup"))

    assert result == "Backup file 'nope.backup' not found."
    assert not any(c.startswith("/system backup load") for c in execute.seen)
