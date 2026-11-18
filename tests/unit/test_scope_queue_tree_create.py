"""A zero-match `print detail` still prints the Flags legend, and the create tools treated it as
proof of creation (issue #147). The reported `create_queue_tree` also interpolated `name`, `parent`,
`queue` and `packet-mark` unquoted, so a value with a space broke the command on the router while the
legend-only lookup answered "created successfully" anyway.
"""

import asyncio
from importlib import import_module

import pytest

from tests.conftest import FakeExecutor


def _run(coro):
    return asyncio.run(coro)


LEGEND_ONLY = "Flags: X - disabled, I - invalid \n"
ITEM_ROW = 'Flags: X - disabled, I - invalid \n 0    name="QoS" parent=bridge\n'


class ScriptedExecutor(FakeExecutor):
    """FakeExecutor whose replies are picked by substring, first match wins."""

    def __init__(self, answers):
        super().__init__()
        self.answers = answers

    async def __call__(self, command, _ctx, device=None):
        self.commands.append(command)
        self.devices.append(device)
        for needle, reply in self.answers:
            if needle in command:
                return reply
        return ""


def _create(monkeypatch, executor, ctx, **kwargs):
    module = import_module("mcp_mikrotik.scope.queue.queue")
    monkeypatch.setattr(module, "execute_mikrotik_command", executor, raising=True)
    return _run(module.mikrotik_create_queue_tree(ctx, **kwargs))


def test_legend_only_lookup_is_not_a_created_queue_tree(monkeypatch, ctx):
    """The add returns no id and the lookup only prints the legend (the #147 report)."""
    fake = ScriptedExecutor([("/queue tree print detail", LEGEND_ONLY)])
    result = _create(monkeypatch, fake, ctx, name="QoS-Download-AllISP", parent="Bridge LAN")
    assert "created successfully" not in result
    assert result == "Queue tree creation completed but unable to verify."


def test_legend_only_lookup_after_an_id_is_not_success_either(monkeypatch, ctx):
    fake = ScriptedExecutor([("/queue tree add", "*1A\n"), ("/queue tree print detail", LEGEND_ONLY)])
    result = _create(monkeypatch, fake, ctx, name="QoS", parent="bridge")
    assert result == "Queue tree created with ID: *1A"


def test_a_real_item_row_is_still_reported_as_success(monkeypatch, ctx):
    fake = ScriptedExecutor([("/queue tree print detail", ITEM_ROW)])
    result = _create(monkeypatch, fake, ctx, name="QoS", parent="bridge")
    assert result.startswith("Queue tree created successfully:")
    assert "name=\"QoS\"" in result


def test_values_that_can_contain_spaces_are_quoted(monkeypatch, ctx):
    fake = ScriptedExecutor([("/queue tree print detail", ITEM_ROW)])
    _create(
        monkeypatch, fake, ctx,
        name="QoS Download", parent="Bridge LAN", queue="PCQ Download", packet_mark="mark all",
    )
    assert fake.commands[0] == (
        '/queue tree add name="QoS Download" parent="Bridge LAN"'
        ' queue="PCQ Download" packet-mark="mark all"'
    )
