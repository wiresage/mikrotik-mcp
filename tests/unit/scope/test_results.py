"""The helpers a write tool uses to read RouterOS's answer (scope/_shared/results.py)."""

import asyncio

import pytest

from mcp_mikrotik.scope._shared.results import is_missing, no_such_item, refused


def _run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize("answer", [
    "failure: already have such address",
    "input does not match any value of interface",
    "invalid value for argument vlan-id",
    "expected end of command (line 1 column 40)",
    "not enough permissions (9)",
    "no such item (4)",
    "bad command name foo (line 1 column 1)",
])
def test_any_text_is_a_refusal(answer):
    """RouterOS says "failure:" or "error" for some refusals only; a write that worked prints nothing."""
    assert refused(answer)
    assert refused(answer + "\n")


@pytest.mark.parametrize("answer", ["", "\n", "  \r\n"])
def test_silence_is_success(answer):
    assert not refused(answer)


def test_no_such_item_is_what_a_missing_id_or_position_answers():
    assert no_such_item("no such item (4) (/ip/route/set; line 1)")
    assert no_such_item("No such item")
    assert not no_such_item("invalid value for argument name")
    assert not no_such_item("")


class Count:
    def __init__(self, answer):
        self.answer = answer
        self.commands = []

    async def __call__(self, command, _ctx, device=None, **kwargs):
        self.commands.append((command, device))
        return self.answer


@pytest.mark.parametrize("answer,missing", [("0", True), ("0\n", True), ("1", False), ("12", False), ("", False),
                                            ("not enough permissions (9)", False)])
def test_is_missing_only_when_routeros_counts_none(answer, missing):
    """Anything but a count of 0 (a refusal, no answer) is not "missing": the write that follows reports it."""
    execute = Count(answer)
    assert _run(is_missing("/queue tree", 'name="x"', None, "R1", execute)) is missing
    assert execute.commands == [('/queue tree print count-only where name="x"', "R1")]
